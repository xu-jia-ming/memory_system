"""Compression coordinator: message write + synchronous compression orchestration (STM-009)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import redis.asyncio as redis
import structlog
from pymongo import AsyncMongoClient

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.models.compression_coordinator import (
    ArchiveSelection,
    CompressionCoordinationResult,
    WriteMessageCoordinatorResult,
)
from memory_system.domain.models.compression_finalize import CompressionFinalizeInput
from memory_system.domain.models.compression_llm import (
    CompressionFinalizeLlmPayload,
    CompressionLlmInput,
    CompressionLlmOutcome,
)
from memory_system.domain.models.compression_preparation import CompressionPreparationInput
from memory_system.domain.models.context_archive import (
    ContextArchiveCreateInput,
    ContextArchiveMessage,
    wm_message_to_archive_message,
)
from memory_system.domain.models.context_read import ContextReadInput
from memory_system.domain.models.message_write import MessageWriteInput
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.compression_finalize_service import finalize_compression
from memory_system.domain.services.compression_llm_service import run_compression_llm
from memory_system.domain.services.compression_preparation_service import (
    prepare_pending_archive_and_publish,
)
from memory_system.domain.services.context_archive_service import (
    build_archive_batch_key,
    create_or_reuse_context_archive,
)
from memory_system.domain.services.context_read_service import read_working_memory_context
from memory_system.domain.services.message_write_service import (
    MessageWriteValidationError,
    write_message,
)
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.kafka.archive_created_publisher import KafkaProducerLike
from memory_system.infrastructure.mongodb.context_archive_repository import (
    find_context_archive_by_batch_key,
)
from memory_system.infrastructure.redis.working_memory_repository import get_working_memory_meta
from memory_system.observability.metrics import record_compression
from memory_system.settings.models import ContextSettings, Settings

if TYPE_CHECKING:
    from memory_system.infrastructure.llm.protocol import LLMClient

Clock = Callable[[], int]
_logger = structlog.get_logger(__name__)


def _finalize_coordination(
    result: CompressionCoordinationResult,
) -> CompressionCoordinationResult:
    record_compression(result.status.value)
    return result


class InvalidMessageTimestampError(ValueError):
    """Raised when client timestamp exceeds allowed future skew."""


class SessionNotFoundCoordinatorError(Exception):
    """Session missing before write (HTTP 404)."""


class SessionClosingCoordinatorError(Exception):
    """Session closing rejects new write (HTTP 409)."""


class MessageTooLargeCoordinatorError(Exception):
    """Single message exceeds max tokens (HTTP 400)."""


class WorkingMemoryFullCoordinatorError(Exception):
    """Capacity backpressure after compression retry (HTTP 503)."""


def _default_clock() -> int:
    return int(time.time())


def _candidate_score(*, remaining: int, target: int, prefix_len: int) -> tuple[int, int]:
    if remaining <= target:
        return (target - remaining, -prefix_len)
    return (remaining - target + 10**9, -prefix_len)


def _pick_better(
    best: ArchiveSelection | None,
    candidate: ArchiveSelection,
    *,
    target: int,
) -> ArchiveSelection:
    if best is None:
        return candidate
    cand_score = _candidate_score(
        remaining=candidate.projected_remaining,
        target=target,
        prefix_len=len(candidate.prefix),
    )
    best_score = _candidate_score(
        remaining=best.projected_remaining,
        target=target,
        prefix_len=len(best.prefix),
    )
    return candidate if cand_score < best_score else best


def _shrink_prefix_to_cap(
    prefix: list[WorkingMemoryMessage],
    max_tokens: int,
) -> list[WorkingMemoryMessage]:
    shrunk = list(prefix)
    while shrunk:
        total = sum(message.estimated_tokens for message in shrunk)
        if total <= max_tokens:
            return shrunk
        shrunk = shrunk[:-1]
    return []


def select_archive_prefix(
    *,
    messages: list[WorkingMemoryMessage],
    meta_estimated_tokens: int,
    context: ContextSettings,
) -> ArchiveSelection | None:
    """Select head-prefix per §1.2.6 (pure function for unit testing)."""
    n = len(messages)
    if n <= context.absolute_min_recent_messages:
        return None

    best: ArchiveSelection | None = None
    for tail_keep in range(
        context.preferred_recent_messages,
        context.absolute_min_recent_messages - 1,
        -1,
    ):
        effective_tail_keep = min(tail_keep, n - 1)
        prefix = list(messages[: n - effective_tail_keep])
        if not prefix:
            continue

        prefix_tokens = sum(message.estimated_tokens for message in prefix)
        if prefix_tokens > context.max_archive_estimated_tokens:
            prefix = _shrink_prefix_to_cap(prefix, context.max_archive_estimated_tokens)
            if not prefix:
                continue
            prefix_tokens = sum(message.estimated_tokens for message in prefix)

        retained = n - len(prefix)
        if retained < context.absolute_min_recent_messages:
            continue

        remaining = meta_estimated_tokens - prefix_tokens
        if remaining < 0:
            continue

        candidate = ArchiveSelection(
            prefix=prefix,
            prefix_tokens=prefix_tokens,
            projected_remaining=remaining,
        )
        best = _pick_better(best, candidate, target=context.compression_target_tokens)

    return best


def _aggregate_round_failure(
    *,
    rounds_completed: int,
    round_status: CompressionStatus,
) -> CompressionStatus:
    if rounds_completed > 0:
        return CompressionStatus.FAILED
    return round_status


async def _run_single_compression_round(
    *,
    redis: redis.Redis,
    mongodb: AsyncMongoClient[Any],
    kafka_producer: KafkaProducerLike,
    llm_client: LLMClient,
    settings: Settings,
    user_id: str,
    session_id: str,
    request_id: str | None,
    clock: Clock,
    stage_log: list[str] | None = None,
) -> CompressionStatus:
    """Execute one compression round: read → archive → pending → LLM → finalize."""
    context = settings.context
    meta = await get_working_memory_meta(redis, user_id, session_id)
    if meta is None:
        return CompressionStatus.FAILED

    read_result = await read_working_memory_context(
        redis=redis,
        input=ContextReadInput(user_id=user_id, session_id=session_id),
    )
    if read_result.status != ContextReadStatus.SUCCESS or read_result.snapshot is None:
        return CompressionStatus.FAILED

    snapshot = read_result.snapshot
    old_compressed_tokens = estimate_tokens(snapshot.compressed_context)

    archive_id: str
    batch_key: str
    pending_count: int
    pending_tokens: int
    first_message_id: str
    last_message_id: str
    archived_messages_for_llm: list[ContextArchiveMessage]

    if meta.pending_archive_id:
        if (
            not meta.pending_archive_batch_key
            or meta.pending_archive_message_count <= 0
        ):
            return CompressionStatus.FAILED
        archive_id = meta.pending_archive_id
        batch_key = meta.pending_archive_batch_key
        pending_count = meta.pending_archive_message_count
        pending_tokens = meta.pending_archive_estimated_tokens
        existing = await find_context_archive_by_batch_key(mongodb, batch_key)
        if existing is None:
            return CompressionStatus.FAILED
        archived_messages_for_llm = existing.messages
        first_message_id = existing.messages[0].message_id
        last_message_id = existing.messages[-1].message_id
    else:
        selection = select_archive_prefix(
            messages=snapshot.messages,
            meta_estimated_tokens=meta.estimated_tokens,
            context=context,
        )
        if selection is None:
            return CompressionStatus.INSUFFICIENT_MESSAGES

        prefix = selection.prefix
        first_message_id = prefix[0].message_id
        last_message_id = prefix[-1].message_id
        batch_key = build_archive_batch_key(session_id, first_message_id, last_message_id)
        pending_count = len(prefix)
        pending_tokens = selection.prefix_tokens

        if stage_log is not None:
            stage_log.append("archive")
        archive_result = await create_or_reuse_context_archive(
            mongodb=mongodb,
            input=ContextArchiveCreateInput(
                user_id=user_id,
                session_id=session_id,
                archive_batch_key=batch_key,
                base_compression_version=snapshot.compression_version,
                messages=prefix,
            ),
            clock=clock,
        )
        archive_id = archive_result.archive_id
        archived_messages_for_llm = [
            wm_message_to_archive_message(message) for message in prefix
        ]

    if stage_log is not None:
        stage_log.append("pending")
    prep_result = await prepare_pending_archive_and_publish(
        redis=redis,
        kafka_producer=kafka_producer,
        topic=settings.kafka.topic,
        input=CompressionPreparationInput(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
            archive_batch_key=batch_key,
            pending_archive_message_count=pending_count,
            pending_archive_estimated_tokens=pending_tokens,
        ),
        lock_ttl_seconds=context.compression_lock_ttl_seconds,
        clock=clock,
        logger=logging.getLogger(__name__),
    )

    if prep_result.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED:
        return CompressionStatus.SKIPPED_LOCK
    if prep_result.status in {
        CompressionPreparationStatus.SESSION_NOT_FOUND,
        CompressionPreparationStatus.SESSION_CLOSING,
        CompressionPreparationStatus.PENDING_CONFLICT,
        CompressionPreparationStatus.INVALID_SESSION_STATE,
    }:
        return CompressionStatus.FAILED

    lock_token = prep_result.lock_owner_token
    if lock_token is None:
        return CompressionStatus.FAILED

    if prep_result.status == CompressionPreparationStatus.PUBLISH_FAILED:
        _logger.warning(
            "compression_kafka_publish_failed",
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
            request_id=request_id,
        )

    if stage_log is not None:
        stage_log.append("llm")
    llm_result = await run_compression_llm(
        CompressionLlmInput(
            existing_compressed_context=snapshot.compressed_context,
            archived_messages=archived_messages_for_llm,
            max_compressed_context_estimated_tokens=context.max_compressed_context_estimated_tokens,
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        ),
        llm_client,
        settings,
        request_id=request_id,
    )
    if llm_result.outcome != CompressionLlmOutcome.SUCCESS or llm_result.success is None:
        return CompressionStatus.FAILED

    if stage_log is not None:
        stage_log.append("finalize")
    finalize_result = await finalize_compression(
        redis=redis,
        input=CompressionFinalizeInput(
            user_id=user_id,
            session_id=session_id,
            expected_compression_version=snapshot.compression_version,
            pending_archive_id=archive_id,
            pending_archive_batch_key=batch_key,
            pending_archive_message_count=pending_count,
            pending_archive_estimated_tokens=pending_tokens,
            expected_first_message_id=first_message_id,
            expected_last_message_id=last_message_id,
            archived_message_tokens=pending_tokens,
            old_compressed_context_tokens=old_compressed_tokens,
            lock_owner_token=lock_token,
            llm_payload=CompressionFinalizeLlmPayload(
                compressed_context=llm_result.success.compressed_context,
                new_compressed_context_tokens=llm_result.success.new_compressed_context_tokens,
            ),
        ),
        clock=clock,
    )

    if finalize_result.status == CompressionFinalizeStatus.SUCCESS:
        return CompressionStatus.COMPLETED
    if finalize_result.status == CompressionFinalizeStatus.VERSION_CONFLICT:
        return CompressionStatus.VERSION_CONFLICT
    return CompressionStatus.FAILED


async def run_compression_coordination(
    *,
    redis: redis.Redis,
    mongodb: AsyncMongoClient[Any],
    kafka_producer: KafkaProducerLike,
    llm_client: LLMClient,
    settings: Settings,
    user_id: str,
    session_id: str,
    request_id: str | None = None,
    max_rounds: int | None = None,
    clock: Clock | None = None,
    stage_log: list[str] | None = None,
) -> CompressionCoordinationResult:
    """Run up to max_rounds synchronous compression rounds for a session."""
    context = settings.context
    limit = (
        max_rounds
        if max_rounds is not None
        else context.max_compression_rounds_per_request
    )
    now_fn = clock or _default_clock
    rounds_completed = 0

    for _round_idx in range(limit):
        meta = await get_working_memory_meta(redis, user_id, session_id)
        if meta is None:
            status = _aggregate_round_failure(
                rounds_completed=rounds_completed,
                round_status=CompressionStatus.FAILED,
            )
            return _finalize_coordination(
                CompressionCoordinationResult(
                status=status,
                rounds_completed=rounds_completed,
                )
            )

        if meta.estimated_tokens < context.compression_trigger_tokens:
            if rounds_completed > 0:
                return _finalize_coordination(
                    CompressionCoordinationResult(
                        status=CompressionStatus.COMPLETED,
                        rounds_completed=rounds_completed,
                    )
                )
            return _finalize_coordination(
                CompressionCoordinationResult(
                    status=CompressionStatus.NOT_TRIGGERED,
                    rounds_completed=0,
                )
            )

        round_status = await _run_single_compression_round(
            redis=redis,
            mongodb=mongodb,
            kafka_producer=kafka_producer,
            llm_client=llm_client,
            settings=settings,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            clock=now_fn,
            stage_log=stage_log,
        )

        if round_status == CompressionStatus.COMPLETED:
            rounds_completed += 1
            meta_after = await get_working_memory_meta(redis, user_id, session_id)
            if (
                meta_after is not None
                and meta_after.estimated_tokens < context.compression_trigger_tokens
            ):
                return _finalize_coordination(
                    CompressionCoordinationResult(
                        status=CompressionStatus.COMPLETED,
                        rounds_completed=rounds_completed,
                    )
                )
            continue

        status = _aggregate_round_failure(
            rounds_completed=rounds_completed,
            round_status=round_status,
        )
        return _finalize_coordination(
            CompressionCoordinationResult(
                status=status,
                rounds_completed=rounds_completed,
            )
        )

    meta_final = await get_working_memory_meta(redis, user_id, session_id)
    if (
        meta_final is not None
        and meta_final.estimated_tokens >= context.compression_trigger_tokens
    ):
        return _finalize_coordination(
            CompressionCoordinationResult(
                status=CompressionStatus.PARTIAL_COMPLETED,
                rounds_completed=rounds_completed,
            )
        )
    return _finalize_coordination(
        CompressionCoordinationResult(
            status=CompressionStatus.COMPLETED,
            rounds_completed=rounds_completed,
        )
    )


async def write_working_message_with_coordination(
    *,
    redis: redis.Redis,
    mongodb: AsyncMongoClient[Any],
    kafka_producer: KafkaProducerLike,
    llm_client: LLMClient,
    settings: Settings,
    input: MessageWriteInput,
    request_id: str | None = None,
    clock: Clock | None = None,
) -> WriteMessageCoordinatorResult:
    """Write via STM-003 then optionally run synchronous compression coordination."""
    now_fn = clock or _default_clock
    context = settings.context

    if input.timestamp is not None:
        now = now_fn()
        if input.timestamp > now + context.allowed_future_timestamp_skew_seconds:
            raise InvalidMessageTimestampError(
                "timestamp exceeds allowed future skew"
            )

    try:
        write_result = await write_message(
            redis=redis,
            input=input,
            context=context,
            clock=now_fn,
        )
    except MessageWriteValidationError as exc:
        raise exc

    if write_result.status == MessageWriteStatus.SESSION_NOT_FOUND:
        raise SessionNotFoundCoordinatorError()
    if write_result.status == MessageWriteStatus.SESSION_CLOSING:
        raise SessionClosingCoordinatorError()
    if write_result.status == MessageWriteStatus.MESSAGE_TOO_LARGE:
        raise MessageTooLargeCoordinatorError()

    if write_result.status == MessageWriteStatus.CAPACITY_EXCEEDED:
        await run_compression_coordination(
            redis=redis,
            mongodb=mongodb,
            kafka_producer=kafka_producer,
            llm_client=llm_client,
            settings=settings,
            user_id=input.user_id,
            session_id=input.session_id,
            request_id=request_id,
            clock=now_fn,
        )
        write_result = await write_message(
            redis=redis,
            input=input,
            context=context,
            clock=now_fn,
        )
        if write_result.status == MessageWriteStatus.CAPACITY_EXCEEDED:
            raise WorkingMemoryFullCoordinatorError()
        if write_result.status == MessageWriteStatus.SESSION_NOT_FOUND:
            raise SessionNotFoundCoordinatorError()
        if write_result.status == MessageWriteStatus.SESSION_CLOSING:
            raise SessionClosingCoordinatorError()
        if write_result.status == MessageWriteStatus.MESSAGE_TOO_LARGE:
            raise MessageTooLargeCoordinatorError()

    if write_result.status == MessageWriteStatus.DUPLICATE:
        record_compression(CompressionStatus.NOT_TRIGGERED.value)
        return WriteMessageCoordinatorResult(
            message_id=input.message_id,
            status="duplicate",
            compression_status=CompressionStatus.NOT_TRIGGERED,
        )

    if write_result.status != MessageWriteStatus.SUCCESS:
        raise RuntimeError(f"unexpected write status: {write_result.status}")

    meta_tokens = write_result.estimated_tokens
    if meta_tokens is None:
        meta = await get_working_memory_meta(
            redis, input.user_id, input.session_id
        )
        meta_tokens = meta.estimated_tokens if meta is not None else 0

    compression_status = CompressionStatus.NOT_TRIGGERED
    if meta_tokens >= context.compression_trigger_tokens:
        coord = await run_compression_coordination(
            redis=redis,
            mongodb=mongodb,
            kafka_producer=kafka_producer,
            llm_client=llm_client,
            settings=settings,
            user_id=input.user_id,
            session_id=input.session_id,
            request_id=request_id,
            clock=now_fn,
        )
        compression_status = coord.status
    else:
        record_compression(CompressionStatus.NOT_TRIGGERED.value)

    _logger.info(
        "message_write_coordination",
        request_id=request_id,
        user_id=input.user_id,
        session_id=input.session_id,
        message_id=input.message_id,
        compression_status=compression_status.value,
    )

    return WriteMessageCoordinatorResult(
        message_id=input.message_id,
        status="success",
        compression_status=compression_status,
    )
