"""Redis repository for atomic context read via Lua."""

from __future__ import annotations

import redis.asyncio as redis

from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.infrastructure.redis.context_read_script import run_context_read_lua
from memory_system.infrastructure.redis.keys import (
    working_memory_messages_key,
    working_memory_meta_key,
)


class ContextReadLuaError(Exception):
    """Raised when Lua returns an unrecognized status or malformed success payload."""


def parse_context_read_lua_result(
    raw: str | list[str],
) -> ContextReadStatus | tuple[str, str, list[str]]:
    """Map Lua return to ContextReadStatus or success tuple; fail on unknown values."""
    if isinstance(raw, str):
        try:
            return ContextReadStatus(raw)
        except ValueError:
            raise ContextReadLuaError(
                f"Unknown context read Lua result: {raw!r}"
            ) from None

    if not isinstance(raw, list) or len(raw) < 3:
        raise ContextReadLuaError(f"Malformed context read Lua success payload: {raw!r}")

    status = raw[0]
    if status != ContextReadStatus.SUCCESS.value:
        raise ContextReadLuaError(f"Unexpected context read Lua array status: {status!r}")

    compression_version = str(raw[1])
    compressed_context = str(raw[2])
    message_jsons = [str(item) for item in raw[3:]]
    return compression_version, compressed_context, message_jsons


async def execute_context_read_lua(
    *,
    redis: redis.Redis,
    user_id: str,
    session_id: str,
) -> ContextReadStatus | tuple[str, str, list[str]]:
    """Run context read Lua with STM-001 key helpers and parse the result."""
    meta_key = working_memory_meta_key(user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)

    raw = await run_context_read_lua(
        redis,
        meta_key=meta_key,
        messages_key=messages_key,
        expected_user_id=user_id,
        expected_session_id=session_id,
    )
    return parse_context_read_lua_result(raw)
