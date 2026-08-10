"""Compression finalize: single Lua atomic write-back (STM-008)."""

from __future__ import annotations

import time
from collections.abc import Callable

import redis.asyncio as redis

from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.domain.models.compression_finalize import (
    CompressionFinalizeInput,
    CompressionFinalizeResult,
)
from memory_system.infrastructure.redis.compression_finalize_repository import (
    finalize_compression_in_redis,
)

Clock = Callable[[], int]


class CompressionFinalizeValidationError(ValueError):
    """Raised when service-layer input validation fails before Redis."""


def _default_clock() -> int:
    return int(time.time())


def _validate_input(input: CompressionFinalizeInput) -> None:
    if not input.user_id.strip():
        raise CompressionFinalizeValidationError("user_id must not be empty")
    if not input.session_id.strip():
        raise CompressionFinalizeValidationError("session_id must not be empty")
    if not input.pending_archive_id.strip():
        raise CompressionFinalizeValidationError("pending_archive_id must not be empty")
    if not input.pending_archive_batch_key.strip():
        raise CompressionFinalizeValidationError(
            "pending_archive_batch_key must not be empty"
        )
    if input.pending_archive_message_count <= 0:
        raise CompressionFinalizeValidationError(
            "pending_archive_message_count must be > 0"
        )
    if input.pending_archive_estimated_tokens < 0:
        raise CompressionFinalizeValidationError(
            "pending_archive_estimated_tokens must be >= 0"
        )
    if not input.expected_first_message_id.strip():
        raise CompressionFinalizeValidationError(
            "expected_first_message_id must not be empty"
        )
    if not input.expected_last_message_id.strip():
        raise CompressionFinalizeValidationError(
            "expected_last_message_id must not be empty"
        )
    if not input.lock_owner_token.strip():
        raise CompressionFinalizeValidationError("lock_owner_token must not be empty")
    if not isinstance(input.llm_payload.compressed_context, str):
        raise CompressionFinalizeValidationError(
            "llm_payload.compressed_context must be a string"
        )
    if input.archived_message_tokens != input.pending_archive_estimated_tokens:
        raise CompressionFinalizeValidationError(
            "archived_message_tokens must equal pending_archive_estimated_tokens"
        )


async def finalize_compression(
    *,
    redis: redis.Redis,
    input: CompressionFinalizeInput,
    clock: Clock | None = None,
) -> CompressionFinalizeResult:
    """Validate input and atomically finalize compression via single Redis Lua."""
    _validate_input(input)
    now_fn = clock or _default_clock
    updated_time = input.updated_time if input.updated_time is not None else now_fn()

    outcome = await finalize_compression_in_redis(
        redis=redis,
        input=input,
        updated_time=updated_time,
    )

    if outcome.status == CompressionFinalizeStatus.SUCCESS:
        return CompressionFinalizeResult(
            status=CompressionFinalizeStatus.SUCCESS,
            new_compression_version=outcome.new_compression_version,
            new_estimated_tokens=outcome.new_estimated_tokens,
        )

    return CompressionFinalizeResult(status=outcome.status)
