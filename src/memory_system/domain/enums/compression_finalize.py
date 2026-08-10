"""Compression finalize internal result enumerations (§1.2.5 / STM-008)."""

from __future__ import annotations

from enum import StrEnum


class CompressionFinalizeStatus(StrEnum):
    """Stable internal literals for compression finalize Lua outcomes."""

    SUCCESS = "success"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_CLOSING = "session_closing"
    LOCK_NOT_ACQUIRED = "lock_not_acquired"
    VERSION_CONFLICT = "version_conflict"
    PENDING_CONFLICT = "pending_conflict"
    INVALID_SESSION_STATE = "invalid_session_state"
    MESSAGE_BOUNDARY_MISMATCH = "message_boundary_mismatch"
