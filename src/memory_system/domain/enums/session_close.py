"""Session close Lua status enumerations (STM-010)."""

from __future__ import annotations

from enum import StrEnum


class SessionCloseEnterStatus(StrEnum):
    """Return values from session_close_enter.lua."""

    SUCCESS = "success"
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_SESSION_STATE = "invalid_session_state"


class SessionCloseRevertStatus(StrEnum):
    """Return values from session_close_revert_active.lua."""

    SUCCESS = "success"
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_SESSION_STATE = "invalid_session_state"


class SessionCloseTerminalStatus(StrEnum):
    """Return values from session_close_terminal.lua."""

    SUCCESS = "success"
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_SESSION_STATE = "invalid_session_state"
