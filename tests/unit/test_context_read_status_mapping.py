"""Unit tests for context read Lua result string mapping."""

from __future__ import annotations

import pytest

from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.infrastructure.redis.context_read_repository import (
    ContextReadLuaError,
    parse_context_read_lua_result,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("session_not_found", ContextReadStatus.SESSION_NOT_FOUND),
        ("invalid_session_state", ContextReadStatus.INVALID_SESSION_STATE),
    ],
)
def test_parse_lua_status_error_strings(raw: str, expected: ContextReadStatus) -> None:
    assert parse_context_read_lua_result(raw) == expected


def test_parse_lua_status_success_minimal_three_elements() -> None:
    result = parse_context_read_lua_result(["success", "0", ""])
    assert result == ("0", "", [])


def test_parse_lua_status_success_with_messages() -> None:
    result = parse_context_read_lua_result(
        ["success", "2", "summary", '{"message_id":"m1"}', '{"message_id":"m2"}']
    )
    assert result == ("2", "summary", ['{"message_id":"m1"}', '{"message_id":"m2"}'])


def test_parse_lua_status_unknown_raises() -> None:
    with pytest.raises(ContextReadLuaError, match="Unknown context read Lua result"):
        parse_context_read_lua_result("bogus_status")


def test_parse_lua_status_malformed_array_raises() -> None:
    with pytest.raises(ContextReadLuaError, match="Malformed context read Lua success payload"):
        parse_context_read_lua_result(["success", "0"])


def test_parse_lua_status_unexpected_array_status_raises() -> None:
    with pytest.raises(ContextReadLuaError, match="Unexpected context read Lua array status"):
        parse_context_read_lua_result(["session_not_found", "0", ""])
