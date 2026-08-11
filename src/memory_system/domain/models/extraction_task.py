"""Memory extraction task domain models (§2.1.3 schema only; no IO)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus


def _is_valid_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4


class ExtractionLastError(BaseModel):
    """``last_error`` shape: error_code / failed_stage / message."""

    model_config = ConfigDict(strict=True, extra="forbid")

    error_code: str
    failed_stage: str
    message: str


class MemoryExtractionTask(BaseModel):
    """Persisted ``memory_extraction_task`` document fields (C1 only)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    task_id: str
    archive_id: str
    user_id: str
    status: ExtractionTaskStatus
    attempt_count: int = Field(ge=0)
    extraction_result: dict[str, Any] | None = None
    last_error: ExtractionLastError | None = None
    created_time: int
    updated_time: int
    completed_time: int | None = None

    @field_validator("task_id")
    @classmethod
    def _validate_task_id_uuid_v4(cls, value: str) -> str:
        if not _is_valid_uuid4(value):
            raise ValueError("task_id must be a UUID v4 string")
        return value


class ProcessArchiveCreatedResult(BaseModel):
    """Outcome of processing one validated archive-created event."""

    model_config = ConfigDict(strict=True, extra="forbid")

    should_commit_offset: bool
    task: MemoryExtractionTask | None = None
