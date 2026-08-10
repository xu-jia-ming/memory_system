"""Loader and runner for the context read Redis Lua script."""

from __future__ import annotations

from pathlib import Path

import redis.asyncio as redis

_LUA_PATH = Path(__file__).resolve().parent / "scripts" / "context_read.lua"


def load_context_read_lua() -> str:
    """Return the context read Lua script source."""
    return _LUA_PATH.read_text(encoding="utf-8")


async def run_context_read_lua(
    redis_client: redis.Redis,
    *,
    meta_key: str,
    messages_key: str,
    expected_user_id: str,
    expected_session_id: str,
) -> str | list[str]:
    """Execute the context read Lua script and return status or success payload."""
    script = redis_client.register_script(load_context_read_lua())
    result = await script(
        keys=[meta_key, messages_key],
        args=[expected_user_id, expected_session_id],
    )
    if isinstance(result, str):
        return result
    if isinstance(result, bytes):
        return result.decode("utf-8")
    if isinstance(result, list):
        decoded: list[str] = []
        for item in result:
            if isinstance(item, bytes):
                decoded.append(item.decode("utf-8"))
            else:
                decoded.append(str(item))
        return decoded
    return str(result)
