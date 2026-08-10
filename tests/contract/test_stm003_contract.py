"""STM-003 contract tests (no network, no Redis I/O)."""

from __future__ import annotations

from memory_system.domain.enums.message_write import MessageWriteStatus

LUA_RETURN_STATUSES = frozenset(
    {
        MessageWriteStatus.SUCCESS,
        MessageWriteStatus.DUPLICATE,
        MessageWriteStatus.CAPACITY_EXCEEDED,
        MessageWriteStatus.SESSION_CLOSING,
        MessageWriteStatus.SESSION_NOT_FOUND,
        MessageWriteStatus.INVALID_SESSION_STATE,
    }
)


def test_message_write_status_literals_stable() -> None:
    assert MessageWriteStatus.SUCCESS.value == "success"
    assert MessageWriteStatus.DUPLICATE.value == "duplicate"
    assert MessageWriteStatus.CAPACITY_EXCEEDED.value == "capacity_exceeded"
    assert MessageWriteStatus.SESSION_CLOSING.value == "session_closing"
    assert MessageWriteStatus.SESSION_NOT_FOUND.value == "session_not_found"
    assert MessageWriteStatus.MESSAGE_TOO_LARGE.value == "message_too_large"
    assert MessageWriteStatus.INVALID_SESSION_STATE.value == "invalid_session_state"


def test_lua_return_strings_match_enum_values() -> None:
    for status in LUA_RETURN_STATUSES:
        assert status.value == status


def test_message_too_large_is_python_only_not_lua_return() -> None:
    assert MessageWriteStatus.MESSAGE_TOO_LARGE not in LUA_RETURN_STATUSES
