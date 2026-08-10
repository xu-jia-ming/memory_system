"""Message write internal result enumerations (§1.2.1 / §1.2.3)."""

from __future__ import annotations

from enum import StrEnum


class MessageWriteStatus(StrEnum):
    """Stable internal literals aligned with Lua returns and STM-009 HTTP mapping."""

    SUCCESS = "success"
    DUPLICATE = "duplicate"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    SESSION_CLOSING = "session_closing"
    SESSION_NOT_FOUND = "session_not_found"
    MESSAGE_TOO_LARGE = "message_too_large"
    INVALID_SESSION_STATE = "invalid_session_state"
