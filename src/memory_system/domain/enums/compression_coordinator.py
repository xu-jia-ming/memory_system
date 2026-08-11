"""Compression coordinator HTTP compression_status enumerations (§1.2.3)."""

from __future__ import annotations

from enum import StrEnum


class CompressionStatus(StrEnum):
    """Stable literals for POST /working/message compression_status field."""

    NOT_TRIGGERED = "not_triggered"
    COMPLETED = "completed"
    PARTIAL_COMPLETED = "partial_completed"
    FAILED = "failed"
    SKIPPED_LOCK = "skipped_lock"
    INSUFFICIENT_MESSAGES = "insufficient_messages"
    VERSION_CONFLICT = "version_conflict"
