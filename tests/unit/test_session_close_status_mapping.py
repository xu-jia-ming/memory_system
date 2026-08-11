"""Unit tests for session close HTTP/Lua status mapping (STM-010)."""

from __future__ import annotations

from memory_system.domain.enums.session_close import (
    SessionCloseEnterStatus,
    SessionCloseRevertStatus,
    SessionCloseTerminalStatus,
)
from memory_system.infrastructure.redis.session_close_repository import (
    SessionCloseLuaError,
    parse_enter_lua_result,
    parse_revert_lua_result,
    parse_terminal_lua_result,
)


def test_enter_status_mapping() -> None:
    assert parse_enter_lua_result("success") == SessionCloseEnterStatus.SUCCESS
    assert (
        parse_enter_lua_result("session_not_found")
        == SessionCloseEnterStatus.SESSION_NOT_FOUND
    )
    assert (
        parse_enter_lua_result("invalid_session_state")
        == SessionCloseEnterStatus.INVALID_SESSION_STATE
    )


def test_revert_status_mapping() -> None:
    assert parse_revert_lua_result("success") == SessionCloseRevertStatus.SUCCESS
    assert (
        parse_revert_lua_result("session_not_found")
        == SessionCloseRevertStatus.SESSION_NOT_FOUND
    )
    assert (
        parse_revert_lua_result("invalid_session_state")
        == SessionCloseRevertStatus.INVALID_SESSION_STATE
    )


def test_terminal_status_mapping() -> None:
    assert parse_terminal_lua_result("success") == SessionCloseTerminalStatus.SUCCESS
    assert (
        parse_terminal_lua_result("session_not_found")
        == SessionCloseTerminalStatus.SESSION_NOT_FOUND
    )
    assert (
        parse_terminal_lua_result("invalid_session_state")
        == SessionCloseTerminalStatus.INVALID_SESSION_STATE
    )


def test_unknown_lua_result_raises() -> None:
    try:
        parse_enter_lua_result("bogus")
        raise AssertionError("expected SessionCloseLuaError")
    except SessionCloseLuaError:
        pass
