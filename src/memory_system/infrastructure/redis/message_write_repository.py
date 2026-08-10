"""Redis repository for atomic message write via Lua."""

from __future__ import annotations

import redis.asyncio as redis

from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.message_write_script import run_message_write_lua


class MessageWriteLuaError(Exception):
    """Raised when Lua returns an unrecognized status string."""


def parse_message_write_lua_result(raw: str) -> MessageWriteStatus:
    """Map Lua return string to MessageWriteStatus; fail on unknown values."""
    try:
        return MessageWriteStatus(raw)
    except ValueError:
        raise MessageWriteLuaError(f"Unknown message write Lua result: {raw!r}") from None


async def execute_message_write_lua(
    *,
    redis: redis.Redis,
    user_id: str,
    session_id: str,
    message_id: str,
    message_json: str,
    message_estimated_tokens: int,
    max_wm_tokens: int,
    updated_time: int,
) -> MessageWriteStatus:
    """Run message write Lua with STM-001 key helpers and parse the result."""
    meta_key = working_memory_meta_key(user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)
    message_ids_key = working_memory_message_ids_key(user_id, session_id)

    raw = await run_message_write_lua(
        redis,
        meta_key=meta_key,
        messages_key=messages_key,
        message_ids_key=message_ids_key,
        message_json=message_json,
        message_estimated_tokens=message_estimated_tokens,
        max_wm_tokens=max_wm_tokens,
        updated_time=updated_time,
        expected_user_id=user_id,
        expected_session_id=session_id,
        message_id=message_id,
    )
    return parse_message_write_lua_result(raw)
