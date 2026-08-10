"""Working Memory field models aligned with §1.2.1 (schema only; no Redis I/O)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.enums.working_memory import MessageRole, SessionStatus


class WorkingMemoryMeta(BaseModel):
    """Redis Hash metadata fields for a Working Memory session."""

    model_config = ConfigDict(strict=True)

    user_id: str
    session_id: str
    compressed_context: str = ""
    estimated_tokens: int = 0
    compression_version: int = 0
    status: SessionStatus = SessionStatus.ACTIVE
    pending_archive_id: str | None = None
    pending_archive_batch_key: str | None = None
    pending_archive_message_count: int = 0
    pending_archive_estimated_tokens: int = 0
    created_time: int
    updated_time: int


class WorkingMemoryMessage(BaseModel):
    """Single message element stored in the Working Memory messages List."""

    model_config = ConfigDict(strict=True)

    message_id: str
    role: MessageRole
    content: str
    estimated_tokens: int = Field(ge=0)
    timestamp: int
