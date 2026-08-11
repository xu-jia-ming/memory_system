"""Session close orchestration domain service (STM-010)."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

import redis.asyncio as redis
import structlog
from pymongo import AsyncMongoClient

from memory_system.domain.enums.context_archive import ContextArchiveOutcome
from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.domain.enums.session_close import (
    SessionCloseEnterStatus,
    SessionCloseTerminalStatus,
)
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.context_archive import ContextArchiveCreateInput
from memory_system.domain.models.context_read import ContextReadInput
from memory_system.domain.models.session_close import (
    CloseArchiveBatch,
    ClosePlan,
    CloseProgress,
    SessionCloseResult,
)
from memory_system.domain.models.working_memory import WorkingMemoryMessage, WorkingMemoryMeta
from memory_system.domain.services.context_archive_service import (
    build_archive_batch_key,
    create_or_reuse_context_archive,
)
from memory_system.domain.services.context_read_service import read_working_memory_context
from memory_system.infrastructure.kafka.archive_created_publisher import (
    KafkaProducerLike,
    publish_archive_created_event,
)
from memory_system.infrastructure.redis.compression_lock_repository import (
    acquire_compression_lock,
    release_compression_lock,
)
from memory_system.infrastructure.redis.session_close_repository import (
    execute_enter_closing_lua,
    execute_revert_active_lua,
    execute_terminal_delete_lua,
)
from memory_system.infrastructure.redis.working_memory_repository import get_working_memory_meta
from memory_system.settings.models import Settings

Clock = Callable[[], int]
_logger = structlog.get_logger(__name__)


class SessionNotFoundCloseError(Exception):
    """Session missing before or during close (HTTP 404)."""


class SessionCloseLockNotAcquiredError(Exception):
    """Compression lock not acquired (HTTP 503 internal_error)."""


class MalformedCompressionVersionError(Exception):
    """compression_version missing or invalid (HTTP 503 internal_error)."""


class BaseCompressionVersionMismatchError(Exception):
    """REUSED archive base_compression_version mismatch (HTTP 503 internal_error)."""


class MessageBoundaryMismatchError(Exception):
    """Close plan messages do not match Redis snapshot (HTTP 503 internal_error)."""


class SessionCloseIncompleteError(Exception):
    """Terminal delete failed or unconfirmed (HTTP 503 close_incomplete)."""


class SingleMessageExceedsArchiveCapError(ValueError):
    """Single message exceeds max_archive_estimated_tokens (fail-closed)."""


def _default_clock() -> int:
    return int(time.time())


def split_close_suffix_batches(
    messages: list[WorkingMemoryMessage],
    max_archive_estimated_tokens: int,
) -> list[list[WorkingMemoryMessage]]:
    """Archive ALL suffix messages; split only by max_archive cap."""
    if not messages:
        return []
    batches: list[list[WorkingMemoryMessage]] = []
    current: list[WorkingMemoryMessage] = []
    current_tokens = 0
    for message in messages:
        token_count = message.estimated_tokens
        if token_count > max_archive_estimated_tokens:
            raise SingleMessageExceedsArchiveCapError(
                f"message {message.message_id!r} estimated_tokens={token_count} "
                f"exceeds max_archive_estimated_tokens={max_archive_estimated_tokens}"
            )
        if current and current_tokens + token_count > max_archive_estimated_tokens:
            batches.append(current)
            current = [message]
            current_tokens = token_count
        else:
            current.append(message)
            current_tokens += token_count
    if current:
        batches.append(current)
    return batches


def _extract_base_compression_version(meta: WorkingMemoryMeta) -> int:
    try:
        version = meta.compression_version
    except (ValueError, KeyError, TypeError) as exc:
        raise MalformedCompressionVersionError(
            "Working memory meta compression_version is malformed"
        ) from exc
    if version < 0:
        raise MalformedCompressionVersionError(
            "Working memory meta compression_version must be >= 0"
        )
    return version


def build_close_plan(
    *,
    meta: WorkingMemoryMeta,
    messages: list[WorkingMemoryMessage],
    max_archive_estimated_tokens: int,
) -> ClosePlan:
    """Build deterministic close plan with frozen base_compression_version."""
    base_version = _extract_base_compression_version(meta)
    batches: list[CloseArchiveBatch] = []

    if meta.pending_archive_id:
        if (
            not meta.pending_archive_batch_key
            or meta.pending_archive_message_count <= 0
        ):
            raise MessageBoundaryMismatchError("Pending archive meta is incomplete")
        pending_count = meta.pending_archive_message_count
        if len(messages) < pending_count:
            raise MessageBoundaryMismatchError(
                "Message count less than pending_archive_message_count"
            )
        pending_messages = messages[:pending_count]
        batches.append(
            CloseArchiveBatch(
                archive_batch_key=meta.pending_archive_batch_key,
                messages=pending_messages,
                is_pending_reuse=True,
                archive_id=meta.pending_archive_id,
            )
        )
        suffix_messages = messages[pending_count:]
    else:
        suffix_messages = list(messages)

    for suffix_batch in split_close_suffix_batches(
        suffix_messages,
        max_archive_estimated_tokens,
    ):
        batch_key = build_archive_batch_key(
            meta.session_id,
            suffix_batch[0].message_id,
            suffix_batch[-1].message_id,
        )
        batches.append(
            CloseArchiveBatch(
                archive_batch_key=batch_key,
                messages=suffix_batch,
                is_pending_reuse=False,
            )
        )

    return ClosePlan(
        session_id=meta.session_id,
        user_id=meta.user_id,
        base_compression_version=base_version,
        batches=batches,
    )


async def _maybe_revert_active(
    *,
    redis: redis.Redis,
    user_id: str,
    session_id: str,
    progress: CloseProgress,
    clock: Clock,
) -> None:
    if progress.close_new_archive_persisted or progress.all_archives_confirmed:
        return
    await execute_revert_active_lua(
        redis=redis,
        user_id=user_id,
        session_id=session_id,
        updated_time=clock(),
    )


async def close_session(
    *,
    redis: redis.Redis,
    mongodb: AsyncMongoClient[Any],
    kafka_producer: KafkaProducerLike,
    settings: Settings,
    user_id: str,
    session_id: str,
    request_id: str | None = None,
    clock: Clock | None = None,
    logger: logging.Logger | None = None,
) -> SessionCloseResult:
    """Close a working memory session: archive remaining messages and delete Redis keys."""
    now_fn = clock or _default_clock
    log = logger or logging.getLogger(__name__)
    context = settings.context
    progress = CloseProgress()

    lock_token: str | None = None
    try:
        lock_token = await acquire_compression_lock(
            redis,
            user_id=user_id,
            session_id=session_id,
            ttl_seconds=context.compression_lock_ttl_seconds,
        )
        if lock_token is None:
            raise SessionCloseLockNotAcquiredError("Compression lock not acquired")

        enter_status = await execute_enter_closing_lua(
            redis=redis,
            user_id=user_id,
            session_id=session_id,
            updated_time=now_fn(),
        )
        if enter_status == SessionCloseEnterStatus.SESSION_NOT_FOUND:
            raise SessionNotFoundCloseError("Working memory session not found")
        if enter_status == SessionCloseEnterStatus.INVALID_SESSION_STATE:
            raise MalformedCompressionVersionError("Session is not in active or closing state")

        meta = await get_working_memory_meta(redis, user_id, session_id)
        if meta is None:
            raise SessionNotFoundCloseError("Working memory session not found")

        read_result = await read_working_memory_context(
            redis=redis,
            input=ContextReadInput(user_id=user_id, session_id=session_id),
        )
        if read_result.status != ContextReadStatus.SUCCESS or read_result.snapshot is None:
            raise MessageBoundaryMismatchError("Failed to read working memory context")

        try:
            close_plan = build_close_plan(
                meta=meta,
                messages=read_result.snapshot.messages,
                max_archive_estimated_tokens=context.max_archive_estimated_tokens,
            )
        except (
            MalformedCompressionVersionError,
            MessageBoundaryMismatchError,
            SingleMessageExceedsArchiveCapError,
        ):
            await _maybe_revert_active(
                redis=redis,
                user_id=user_id,
                session_id=session_id,
                progress=progress,
                clock=now_fn,
            )
            raise

        archive_ids: list[str] = []
        for batch in close_plan.batches:
            if batch.is_pending_reuse:
                if batch.archive_id is None:
                    raise MessageBoundaryMismatchError("Pending reuse batch missing archive_id")
                archive_ids.append(batch.archive_id)
                continue

            try:
                archive_result = await create_or_reuse_context_archive(
                    mongodb=mongodb,
                    input=ContextArchiveCreateInput(
                        user_id=close_plan.user_id,
                        session_id=close_plan.session_id,
                        archive_batch_key=batch.archive_batch_key,
                        base_compression_version=close_plan.base_compression_version,
                        messages=batch.messages,
                    ),
                    clock=now_fn,
                )
            except Exception:
                await _maybe_revert_active(
                    redis=redis,
                    user_id=user_id,
                    session_id=session_id,
                    progress=progress,
                    clock=now_fn,
                )
                raise

            if archive_result.outcome == ContextArchiveOutcome.REUSED:
                existing_version = archive_result.archive.base_compression_version
                if existing_version != close_plan.base_compression_version:
                    progress.close_new_archive_persisted = True
                    raise BaseCompressionVersionMismatchError(
                        f"REUSED archive base_compression_version={existing_version} "
                        f"!= close_plan={close_plan.base_compression_version}"
                    )
                progress.close_new_archive_persisted = True
            else:
                progress.close_new_archive_persisted = True

            archive_ids.append(archive_result.archive_id)

        progress.all_archives_confirmed = True

        topic = settings.kafka.topic
        for archive_id in archive_ids:
            event_id = str(uuid.uuid4())
            event = ArchiveCreatedEvent(
                event_id=event_id,
                event_type=ARCHIVE_CREATED_EVENT_TYPE,
                archive_id=archive_id,
                user_id=user_id,
                session_id=session_id,
                created_time=now_fn(),
            )
            try:
                await publish_archive_created_event(kafka_producer, topic, event)
            except Exception:
                log.error(
                    "Kafka publish failed for context.archive.created archive_id=%s",
                    archive_id,
                    exc_info=True,
                )
                _logger.warning(
                    "close_kafka_publish_failed",
                    user_id=user_id,
                    session_id=session_id,
                    archive_id=archive_id,
                    request_id=request_id,
                )

        terminal_status = await execute_terminal_delete_lua(
            redis=redis,
            user_id=user_id,
            session_id=session_id,
        )
        if terminal_status != SessionCloseTerminalStatus.SUCCESS:
            raise SessionCloseIncompleteError(
                f"Terminal delete failed with status {terminal_status.value}"
            )

        return SessionCloseResult(
            session_id=session_id,
            archive_ids=archive_ids,
            status="closed",
        )
    finally:
        if lock_token is not None:
            await release_compression_lock(
                redis,
                user_id=user_id,
                session_id=session_id,
                token=lock_token,
            )
