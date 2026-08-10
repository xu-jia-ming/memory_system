"""Compression preparation internal result enumerations (§1.2.1 / §1.2.4 / §1.2.6)."""

from __future__ import annotations

from enum import StrEnum


class CompressionPreparationStatus(StrEnum):
    """Stable internal literals for compression lock + pending + Kafka publish."""

    SUCCESS = "success"
    PUBLISH_FAILED = "publish_failed"
    LOCK_NOT_ACQUIRED = "lock_not_acquired"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_CLOSING = "session_closing"
    PENDING_CONFLICT = "pending_conflict"
    INVALID_SESSION_STATE = "invalid_session_state"
