"""Unit tests for Lua result string mapping."""

from __future__ import annotations

import pytest

from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.infrastructure.redis.message_write_repository import (
    MessageWriteLuaError,
    parse_message_write_lua_result,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("success", MessageWriteStatus.SUCCESS),
        ("duplicate", MessageWriteStatus.DUPLICATE),
        ("capacity_exceeded", MessageWriteStatus.CAPACITY_EXCEEDED),
        ("session_closing", MessageWriteStatus.SESSION_CLOSING),
        ("session_not_found", MessageWriteStatus.SESSION_NOT_FOUND),
        ("invalid_session_state", MessageWriteStatus.INVALID_SESSION_STATE),
    ],
)
def test_parse_lua_status_known_values(raw: str, expected: MessageWriteStatus) -> None:
    assert parse_message_write_lua_result(raw) == expected


def test_parse_lua_status_unknown_raises() -> None:
    with pytest.raises(MessageWriteLuaError, match="Unknown message write Lua result"):
        parse_message_write_lua_result("bogus_status")
