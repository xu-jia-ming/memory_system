"""Archive event republish internal result enumerations (STM-011)."""

from __future__ import annotations

from enum import StrEnum


class ArchiveEventRepublishStatus(StrEnum):
    """Stable internal literals for archive created event republish."""

    SUCCESS = "success"
    ARCHIVE_NOT_FOUND = "archive_not_found"
    ARCHIVE_OWNERSHIP_MISMATCH = "archive_ownership_mismatch"
    INVALID_ARCHIVE = "invalid_archive"
    KAFKA_PUBLISH_FAILED = "kafka_publish_failed"
    INVALID_INPUT = "invalid_input"
