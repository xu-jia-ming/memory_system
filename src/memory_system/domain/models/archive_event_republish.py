"""Archive event republish input/result models (STM-011; CLI-only)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus


class ArchiveEventRepublishInput(BaseModel):
    """Caller-supplied archive identity and optional ownership check."""

    model_config = ConfigDict(strict=True)

    archive_id: str
    expected_user_id: str | None = None


class ArchiveEventRepublishResult(BaseModel):
    """Stable internal result for archive created event republish."""

    model_config = ConfigDict(strict=True)

    status: ArchiveEventRepublishStatus
    event_id: str | None = None
