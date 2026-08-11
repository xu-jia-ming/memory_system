"""HTTP schemas for POST /api/v1/memory/working/message (§1.2.3)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from memory_system.domain.enums.compression_coordinator import CompressionStatus


class WriteMessageRequest(BaseModel):
    """Client write request; no client estimated_tokens."""

    model_config = ConfigDict(strict=True)

    message_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    role: Literal["user", "assistant"]
    content: str
    timestamp: int | None = None

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("content must not be empty")
        return value


class WriteMessageResponse(BaseModel):
    """Success response with exactly three fields."""

    model_config = ConfigDict(strict=True)

    message_id: str
    status: Literal["success", "duplicate"]
    compression_status: CompressionStatus
