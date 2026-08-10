"""Compression preparation: lock + pending_archive_* + Kafka publish (STM-006)."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

import redis.asyncio as redis

from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.compression_preparation import (
    CompressionPreparationInput,
    CompressionPreparationResult,
)
from memory_system.infrastructure.kafka.archive_created_publisher import (
    KafkaProducerLike,
    publish_archive_created_event,
)
from memory_system.infrastructure.redis.compression_lock_repository import (
    acquire_compression_lock,
    release_compression_lock,
)
from memory_system.infrastructure.redis.pending_archive_repository import (
    execute_pending_archive_write_lua,
)

Clock = Callable[[], int]
LoggerFactory = logging.Logger

_HARD_FAIL_LUA_STATUSES: frozenset[CompressionPreparationStatus] = frozenset(
    {
        CompressionPreparationStatus.LOCK_NOT_ACQUIRED,
        CompressionPreparationStatus.SESSION_NOT_FOUND,
        CompressionPreparationStatus.SESSION_CLOSING,
        CompressionPreparationStatus.PENDING_CONFLICT,
        CompressionPreparationStatus.INVALID_SESSION_STATE,
    }
)


class CompressionPreparationValidationError(ValueError):
    """Raised when service-layer input validation fails before Redis/Kafka."""


def _default_clock() -> int:
    return int(time.time())


def _validate_input(input: CompressionPreparationInput) -> None:
    if not input.user_id.strip():
        raise CompressionPreparationValidationError("user_id must not be empty")
    if not input.session_id.strip():
        raise CompressionPreparationValidationError("session_id must not be empty")
    if not input.archive_id.strip():
        raise CompressionPreparationValidationError("archive_id must not be empty")
    if not input.archive_batch_key.strip():
        raise CompressionPreparationValidationError("archive_batch_key must not be empty")
    if input.pending_archive_message_count <= 0:
        raise CompressionPreparationValidationError(
            "pending_archive_message_count must be > 0"
        )
    if input.pending_archive_estimated_tokens < 0:
        raise CompressionPreparationValidationError(
            "pending_archive_estimated_tokens must be >= 0"
        )
    if input.lock_owner_token is not None and input.lock_owner_token == "":
        raise CompressionPreparationValidationError(
            "lock_owner_token must not be an empty string"
        )


async def prepare_pending_archive_and_publish(
    *,
    redis: redis.Redis,
    kafka_producer: KafkaProducerLike,
    topic: str,
    input: CompressionPreparationInput,
    lock_ttl_seconds: int,
    clock: Clock | None = None,
    logger: LoggerFactory | None = None,
) -> CompressionPreparationResult:
    """Acquire/verify lock, atomically write pending, then publish Kafka event."""
    _validate_input(input)
    log = logger or logging.getLogger(__name__)
    now_fn = clock or _default_clock

    acquired_in_this_call = False
    token: str

    if input.lock_owner_token is None:
        acquired = await acquire_compression_lock(
            redis,
            user_id=input.user_id,
            session_id=input.session_id,
            ttl_seconds=lock_ttl_seconds,
        )
        if acquired is None:
            return CompressionPreparationResult(
                status=CompressionPreparationStatus.LOCK_NOT_ACQUIRED,
                lock_owner_token=None,
                event_id=None,
            )
        token = acquired
        acquired_in_this_call = True
    else:
        token = input.lock_owner_token

    lua_status = await execute_pending_archive_write_lua(
        redis=redis,
        user_id=input.user_id,
        session_id=input.session_id,
        archive_id=input.archive_id,
        archive_batch_key=input.archive_batch_key,
        message_count=input.pending_archive_message_count,
        estimated_tokens=input.pending_archive_estimated_tokens,
        expected_lock_owner_token=token,
    )

    if lua_status in _HARD_FAIL_LUA_STATUSES:
        if acquired_in_this_call:
            await release_compression_lock(
                redis,
                user_id=input.user_id,
                session_id=input.session_id,
                token=token,
            )
            return_token: str | None = None
        elif lua_status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED:
            return_token = None
        else:
            # Pre-held ownership still valid; pending/session hard-fail keeps lock.
            return_token = token
        return CompressionPreparationResult(
            status=lua_status,
            lock_owner_token=return_token,
            event_id=None,
        )

    # Lua success only — Kafka publish gate
    event_id = str(uuid.uuid4())
    created_time = (
        input.event_created_time if input.event_created_time is not None else now_fn()
    )
    event = ArchiveCreatedEvent(
        event_id=event_id,
        event_type=ARCHIVE_CREATED_EVENT_TYPE,
        archive_id=input.archive_id,
        user_id=input.user_id,
        session_id=input.session_id,
        created_time=created_time,
    )

    try:
        await publish_archive_created_event(kafka_producer, topic, event)
    except Exception:
        log.error(
            "Kafka publish failed for context.archive.created archive_id=%s",
            input.archive_id,
            exc_info=True,
        )
        return CompressionPreparationResult(
            status=CompressionPreparationStatus.PUBLISH_FAILED,
            lock_owner_token=token,
            event_id=None,
        )

    return CompressionPreparationResult(
        status=CompressionPreparationStatus.SUCCESS,
        lock_owner_token=token,
        event_id=event_id,
    )
