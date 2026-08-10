"""Redis repository for atomic compression finalize via Lua (STM-008)."""

from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as redis

from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.domain.models.compression_finalize import CompressionFinalizeInput
from memory_system.infrastructure.redis.compression_finalize_script import (
    run_compression_finalize_lua,
)
from memory_system.infrastructure.redis.keys import (
    compression_lock_key,
    working_memory_messages_key,
    working_memory_meta_key,
)

_LUA_FAILURE_STATUSES: frozenset[CompressionFinalizeStatus] = frozenset(
    {
        CompressionFinalizeStatus.SESSION_NOT_FOUND,
        CompressionFinalizeStatus.SESSION_CLOSING,
        CompressionFinalizeStatus.LOCK_NOT_ACQUIRED,
        CompressionFinalizeStatus.VERSION_CONFLICT,
        CompressionFinalizeStatus.PENDING_CONFLICT,
        CompressionFinalizeStatus.INVALID_SESSION_STATE,
        CompressionFinalizeStatus.MESSAGE_BOUNDARY_MISMATCH,
    }
)


class CompressionFinalizeLuaError(Exception):
    """Raised when Lua returns an unrecognized status string."""


@dataclass(frozen=True)
class CompressionFinalizeLuaOutcome:
    """Parsed Lua outcome including success metadata."""

    status: CompressionFinalizeStatus
    new_compression_version: int | None = None
    new_estimated_tokens: int | None = None


def parse_compression_finalize_lua_result(
    raw: str | list[str],
) -> CompressionFinalizeLuaOutcome:
    """Map Lua return value to CompressionFinalizeLuaOutcome; fail on unknown values."""
    if isinstance(raw, list):
        if len(raw) != 3 or raw[0] != CompressionFinalizeStatus.SUCCESS.value:
            raise CompressionFinalizeLuaError(f"Unexpected success tuple from Lua: {raw!r}")
        try:
            new_version = int(raw[1])
            new_tokens = int(raw[2])
        except (TypeError, ValueError) as exc:
            raise CompressionFinalizeLuaError(
                f"Invalid success numeric fields from Lua: {raw!r}"
            ) from exc
        return CompressionFinalizeLuaOutcome(
            status=CompressionFinalizeStatus.SUCCESS,
            new_compression_version=new_version,
            new_estimated_tokens=new_tokens,
        )

    try:
        status = CompressionFinalizeStatus(raw)
    except ValueError:
        raise CompressionFinalizeLuaError(
            f"Unknown compression finalize Lua result: {raw!r}"
        ) from None
    if status not in _LUA_FAILURE_STATUSES:
        raise CompressionFinalizeLuaError(
            f"Unexpected compression finalize Lua result: {raw!r}"
        )
    return CompressionFinalizeLuaOutcome(status=status)


async def finalize_compression_in_redis(
    *,
    redis: redis.Redis,
    input: CompressionFinalizeInput,
    updated_time: int,
) -> CompressionFinalizeLuaOutcome:
    """Run finalize Lua with ownership verification in the same atomic window."""
    meta_key = working_memory_meta_key(input.user_id, input.session_id)
    messages_key = working_memory_messages_key(input.user_id, input.session_id)
    lock_key = compression_lock_key(input.user_id, input.session_id)

    raw = await run_compression_finalize_lua(
        redis,
        meta_key=meta_key,
        messages_key=messages_key,
        lock_key=lock_key,
        expected_user_id=input.user_id,
        expected_session_id=input.session_id,
        expected_compression_version=input.expected_compression_version,
        pending_archive_id=input.pending_archive_id,
        pending_archive_batch_key=input.pending_archive_batch_key,
        pending_archive_message_count=input.pending_archive_message_count,
        pending_archive_estimated_tokens=input.pending_archive_estimated_tokens,
        lock_owner_token=input.lock_owner_token,
        expected_first_message_id=input.expected_first_message_id,
        expected_last_message_id=input.expected_last_message_id,
        archived_message_tokens=input.archived_message_tokens,
        old_compressed_context_tokens=input.old_compressed_context_tokens,
        new_compressed_context_tokens=input.llm_payload.new_compressed_context_tokens,
        compressed_context=input.llm_payload.compressed_context,
        updated_time=updated_time,
    )
    return parse_compression_finalize_lua_result(raw)
