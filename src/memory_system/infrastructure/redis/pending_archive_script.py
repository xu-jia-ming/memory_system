"""Loader and runner for the pending archive write Redis Lua script."""

from __future__ import annotations

from pathlib import Path

import redis.asyncio as redis

_LUA_PATH = Path(__file__).resolve().parent / "scripts" / "pending_archive_write.lua"


def load_pending_archive_write_lua() -> str:
    """Return the pending archive write Lua script source."""
    return _LUA_PATH.read_text(encoding="utf-8")


async def run_pending_archive_write_lua(
    redis_client: redis.Redis,
    *,
    meta_key: str,
    lock_key: str,
    expected_user_id: str,
    expected_session_id: str,
    archive_id: str,
    archive_batch_key: str,
    message_count: int,
    estimated_tokens: int,
    expected_lock_owner_token: str,
) -> str:
    """Execute pending archive Lua and return the status string."""
    script = redis_client.register_script(load_pending_archive_write_lua())
    result = await script(
        keys=[meta_key, lock_key],
        args=[
            expected_user_id,
            expected_session_id,
            archive_id,
            archive_batch_key,
            str(message_count),
            str(estimated_tokens),
            expected_lock_owner_token,
        ],
    )
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return str(result)
