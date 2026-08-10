"""Loader and runner for the compression finalize Redis Lua script."""

from __future__ import annotations

from pathlib import Path

import redis.asyncio as redis

_LUA_PATH = Path(__file__).resolve().parent / "scripts" / "compression_finalize.lua"


def load_compression_finalize_lua() -> str:
    """Return the compression finalize Lua script source."""
    return _LUA_PATH.read_text(encoding="utf-8")


async def run_compression_finalize_lua(
    redis_client: redis.Redis,
    *,
    meta_key: str,
    messages_key: str,
    lock_key: str,
    expected_user_id: str,
    expected_session_id: str,
    expected_compression_version: int,
    pending_archive_id: str,
    pending_archive_batch_key: str,
    pending_archive_message_count: int,
    pending_archive_estimated_tokens: int,
    lock_owner_token: str,
    expected_first_message_id: str,
    expected_last_message_id: str,
    archived_message_tokens: int,
    old_compressed_context_tokens: int,
    new_compressed_context_tokens: int,
    compressed_context: str,
    updated_time: int,
) -> str | list[str]:
    """Execute compression finalize Lua and return status or success tuple."""
    script = redis_client.register_script(load_compression_finalize_lua())
    result = await script(
        keys=[meta_key, messages_key, lock_key],
        args=[
            expected_user_id,
            expected_session_id,
            str(expected_compression_version),
            pending_archive_id,
            pending_archive_batch_key,
            str(pending_archive_message_count),
            str(pending_archive_estimated_tokens),
            lock_owner_token,
            expected_first_message_id,
            expected_last_message_id,
            str(archived_message_tokens),
            str(old_compressed_context_tokens),
            str(new_compressed_context_tokens),
            compressed_context,
            str(updated_time),
        ],
    )
    if isinstance(result, list):
        decoded: list[str] = []
        for item in result:
            if isinstance(item, bytes):
                decoded.append(item.decode("utf-8"))
            else:
                decoded.append(str(item))
        return decoded
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return str(result)
