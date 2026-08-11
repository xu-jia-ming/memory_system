"""Redis repository for session close Lua scripts (STM-010)."""

from __future__ import annotations

import redis.asyncio as redis

from memory_system.domain.enums.session_close import (
    SessionCloseEnterStatus,
    SessionCloseRevertStatus,
    SessionCloseTerminalStatus,
)
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.session_close_script import (
    run_session_close_enter_lua,
    run_session_close_revert_active_lua,
    run_session_close_terminal_lua,
)


class SessionCloseLuaError(Exception):
    """Raised when Lua returns an unrecognized status string."""


def parse_enter_lua_result(raw: str) -> SessionCloseEnterStatus:
    try:
        return SessionCloseEnterStatus(raw)
    except ValueError:
        raise SessionCloseLuaError(f"Unknown session close enter Lua result: {raw!r}") from None


def parse_revert_lua_result(raw: str) -> SessionCloseRevertStatus:
    try:
        return SessionCloseRevertStatus(raw)
    except ValueError:
        raise SessionCloseLuaError(f"Unknown session close revert Lua result: {raw!r}") from None


def parse_terminal_lua_result(raw: str) -> SessionCloseTerminalStatus:
    try:
        return SessionCloseTerminalStatus(raw)
    except ValueError:
        raise SessionCloseLuaError(f"Unknown session close terminal Lua result: {raw!r}") from None


async def execute_enter_closing_lua(
    *,
    redis: redis.Redis,
    user_id: str,
    session_id: str,
    updated_time: int,
) -> SessionCloseEnterStatus:
    meta_key = working_memory_meta_key(user_id, session_id)
    raw = await run_session_close_enter_lua(
        redis,
        meta_key=meta_key,
        expected_user_id=user_id,
        expected_session_id=session_id,
        updated_time=updated_time,
    )
    return parse_enter_lua_result(raw)


async def execute_revert_active_lua(
    *,
    redis: redis.Redis,
    user_id: str,
    session_id: str,
    updated_time: int,
) -> SessionCloseRevertStatus:
    meta_key = working_memory_meta_key(user_id, session_id)
    raw = await run_session_close_revert_active_lua(
        redis,
        meta_key=meta_key,
        expected_user_id=user_id,
        expected_session_id=session_id,
        updated_time=updated_time,
    )
    return parse_revert_lua_result(raw)


async def execute_terminal_delete_lua(
    *,
    redis: redis.Redis,
    user_id: str,
    session_id: str,
) -> SessionCloseTerminalStatus:
    meta_key = working_memory_meta_key(user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)
    message_ids_key = working_memory_message_ids_key(user_id, session_id)
    raw = await run_session_close_terminal_lua(
        redis,
        meta_key=meta_key,
        messages_key=messages_key,
        message_ids_key=message_ids_key,
        expected_user_id=user_id,
        expected_session_id=session_id,
    )
    return parse_terminal_lua_result(raw)
