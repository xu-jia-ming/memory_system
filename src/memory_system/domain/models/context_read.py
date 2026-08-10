"""Context read domain input, snapshot, and result models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.domain.models.working_memory import WorkingMemoryMessage


class ContextReadInput(BaseModel):
    """Service-layer read request aligned with §1.2.3 (user_id + session_id only)."""

    model_config = ConfigDict(strict=True)

    user_id: str
    session_id: str


class WorkingMemorySnapshot(BaseModel):
    """Atomic Working Memory snapshot from a single Lua read window."""

    model_config = ConfigDict(strict=True)

    compression_version: int
    compressed_context: str
    messages: list[WorkingMemoryMessage]


class ContextReadResult(BaseModel):
    """Internal read outcome for STM-009 HTTP mapping."""

    model_config = ConfigDict(strict=True)

    status: ContextReadStatus
    snapshot: WorkingMemorySnapshot | None = None
