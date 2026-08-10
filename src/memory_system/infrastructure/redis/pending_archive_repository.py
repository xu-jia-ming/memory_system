"""Redis repository for atomic pending_archive_* write via Lua (STM-006)."""

from __future__ import annotations

import redis.asyncio as redis

from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.infrastructure.redis.keys import compression_lock_key, working_memory_meta_key
from memory_system.infrastructure.redis.pending_archive_script import run_pending_archive_write_lua

# Lua returns a subset of CompressionPreparationStatus literals (not publish_failed).
_LUA_RESULT_STATUSES: frozenset[CompressionPreparationStatus] = frozenset(
    {
        CompressionPreparationStatus.SUCCESS,
        CompressionPreparationStatus.LOCK_NOT_ACQUIRED,
        CompressionPreparationStatus.SESSION_NOT_FOUND,
        CompressionPreparationStatus.SESSION_CLOSING,
        CompressionPreparationStatus.PENDING_CONFLICT,
        CompressionPreparationStatus.INVALID_SESSION_STATE,
    }
)


class PendingArchiveLuaError(Exception):
    """Raised when Lua returns an unrecognized status string."""


def parse_pending_archive_lua_result(raw: str) -> CompressionPreparationStatus:
    """Map Lua return string to CompressionPreparationStatus; fail on unknown values."""
    try:
        status = CompressionPreparationStatus(raw)
    except ValueError:
        raise PendingArchiveLuaError(f"Unknown pending archive Lua result: {raw!r}") from None
    if status not in _LUA_RESULT_STATUSES:
        raise PendingArchiveLuaError(f"Unexpected pending archive Lua result: {raw!r}")
    return status


async def execute_pending_archive_write_lua(
    *,
    redis: redis.Redis,
    user_id: str,
    session_id: str,
    archive_id: str,
    archive_batch_key: str,
    message_count: int,
    estimated_tokens: int,
    expected_lock_owner_token: str,
) -> CompressionPreparationStatus:
    """Run pending write Lua with ownership verification in the same atomic window."""
    meta_key = working_memory_meta_key(user_id, session_id)
    lock_key = compression_lock_key(user_id, session_id)

    raw = await run_pending_archive_write_lua(
        redis,
        meta_key=meta_key,
        lock_key=lock_key,
        expected_user_id=user_id,
        expected_session_id=session_id,
        archive_id=archive_id,
        archive_batch_key=archive_batch_key,
        message_count=message_count,
        estimated_tokens=estimated_tokens,
        expected_lock_owner_token=expected_lock_owner_token,
    )
    return parse_pending_archive_lua_result(raw)
