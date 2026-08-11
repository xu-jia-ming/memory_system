"""Loader and runner for session close Redis Lua scripts (STM-010)."""

from __future__ import annotations

from pathlib import Path

import redis.asyncio as redis

_SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"


def load_session_close_enter_lua() -> str:
    return (_SCRIPTS_DIR / "session_close_enter.lua").read_text(encoding="utf-8")


def load_session_close_revert_active_lua() -> str:
    return (_SCRIPTS_DIR / "session_close_revert_active.lua").read_text(encoding="utf-8")


def load_session_close_terminal_lua() -> str:
    return (_SCRIPTS_DIR / "session_close_terminal.lua").read_text(encoding="utf-8")


async def run_session_close_enter_lua(
    redis_client: redis.Redis,
    *,
    meta_key: str,
    expected_user_id: str,
    expected_session_id: str,
    updated_time: int,
) -> str:
    script = redis_client.register_script(load_session_close_enter_lua())
    result = await script(
        keys=[meta_key],
        args=[expected_user_id, expected_session_id, str(updated_time)],
    )
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return str(result)


async def run_session_close_revert_active_lua(
    redis_client: redis.Redis,
    *,
    meta_key: str,
    expected_user_id: str,
    expected_session_id: str,
    updated_time: int,
) -> str:
    script = redis_client.register_script(load_session_close_revert_active_lua())
    result = await script(
        keys=[meta_key],
        args=[expected_user_id, expected_session_id, str(updated_time)],
    )
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return str(result)


async def run_session_close_terminal_lua(
    redis_client: redis.Redis,
    *,
    meta_key: str,
    messages_key: str,
    message_ids_key: str,
    expected_user_id: str,
    expected_session_id: str,
) -> str:
    script = redis_client.register_script(load_session_close_terminal_lua())
    result = await script(
        keys=[meta_key, messages_key, message_ids_key],
        args=[expected_user_id, expected_session_id],
    )
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return str(result)
