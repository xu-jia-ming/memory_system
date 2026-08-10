"""Context read internal result enumerations (§1.2.1 / §1.2.3)."""

from __future__ import annotations

from enum import StrEnum


class ContextReadStatus(StrEnum):
    """Stable internal literals aligned with Lua returns and STM-009 HTTP mapping."""

    SUCCESS = "success"
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_SESSION_STATE = "invalid_session_state"
