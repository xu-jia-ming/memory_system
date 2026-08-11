"""Session close domain models (STM-010)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.models.working_memory import WorkingMemoryMessage


class CloseArchiveBatch(BaseModel):
    """Single archive batch in a deterministic close plan."""

    model_config = ConfigDict(strict=True)

    archive_batch_key: str
    messages: list[WorkingMemoryMessage]
    is_pending_reuse: bool = False
    archive_id: str | None = None


class ClosePlan(BaseModel):
    """Deterministic close plan; built once per close attempt after enter_closing."""

    model_config = ConfigDict(strict=True)

    session_id: str
    user_id: str
    base_compression_version: int = Field(ge=0)
    batches: list[CloseArchiveBatch]


class SessionCloseResult(BaseModel):
    """Successful session close outcome."""

    model_config = ConfigDict(strict=True)

    session_id: str
    archive_ids: list[str]
    status: Literal["closed"]


class CloseProgress(BaseModel):
    """Tracks close attempt progress for failure/revert decisions."""

    model_config = ConfigDict(strict=True)

    close_new_archive_persisted: bool = False
    all_archives_confirmed: bool = False
