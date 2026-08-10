"""Loader and runner for the message write Redis Lua script."""

from __future__ import annotations

from pathlib import Path

import redis.asyncio as redis

_LUA_PATH = Path(__file__).resolve().parent / "scripts" / "message_write.lua"


def load_message_write_lua() -> str:
    """Return the message write Lua script source."""
    return _LUA_PATH.read_text(encoding="utf-8")


async def run_message_write_lua(
    redis_client: redis.Redis,
    *,
    meta_key: str,
    messages_key: str,
    message_ids_key: str,
    message_json: str,
    message_estimated_tokens: int,
    max_wm_tokens: int,
    updated_time: int,
    expected_user_id: str,
    expected_session_id: str,
    message_id: str,
) -> str:
    """Execute the message write Lua script and return the status string."""
    script = redis_client.register_script(load_message_write_lua())
    result = await script(
        keys=[meta_key, messages_key, message_ids_key],
        args=[
            message_json,
            str(message_estimated_tokens),
            str(max_wm_tokens),
            str(updated_time),
            expected_user_id,
            expected_session_id,
            message_id,
        ],
    )
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return str(result)
