"""STM-004 contract tests (no network, no Redis I/O)."""

from __future__ import annotations

from memory_system.domain.enums.context_read import ContextReadStatus

LUA_RETURN_STATUSES = frozenset(
    {
        ContextReadStatus.SUCCESS,
        ContextReadStatus.SESSION_NOT_FOUND,
        ContextReadStatus.INVALID_SESSION_STATE,
    }
)


def test_context_read_status_literals_stable() -> None:
    assert ContextReadStatus.SUCCESS.value == "success"
    assert ContextReadStatus.SESSION_NOT_FOUND.value == "session_not_found"
    assert ContextReadStatus.INVALID_SESSION_STATE.value == "invalid_session_state"


def test_lua_return_strings_match_enum_values() -> None:
    for status in LUA_RETURN_STATUSES:
        assert status.value == status


def test_lua_return_set_has_exactly_three_values() -> None:
    assert len(LUA_RETURN_STATUSES) == 3
