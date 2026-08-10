"""Message write domain input and result models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.enums.working_memory import MessageRole


class MessageWriteInput(BaseModel):
    """Service-layer write request aligned with §1.2.3 (no client estimated_tokens)."""

    model_config = ConfigDict(strict=True)

    user_id: str
    session_id: str
    message_id: str
    role: MessageRole
    content: str
    timestamp: int | None = None


class MessageWriteResult(BaseModel):
    """Internal write outcome for STM-009 HTTP mapping."""

    model_config = ConfigDict(strict=True)

    status: MessageWriteStatus
    message_id: str
    estimated_tokens: int | None = None
    message_estimated_tokens: int | None = None
