"""Compression preparation input/result models (STM-006; no HTTP)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus


class CompressionPreparationInput(BaseModel):
    """Caller-supplied archive identity + pending accounting + optional pre-held lock."""

    model_config = ConfigDict(strict=True)

    user_id: str
    session_id: str
    archive_id: str
    archive_batch_key: str
    pending_archive_message_count: int = Field(gt=0)
    pending_archive_estimated_tokens: int = Field(ge=0)
    lock_owner_token: str | None = None
    event_created_time: int | None = None


class CompressionPreparationResult(BaseModel):
    """Stable internal result for lock + pending + Kafka publish orchestration."""

    model_config = ConfigDict(strict=True)

    status: CompressionPreparationStatus
    lock_owner_token: str | None = None
    event_id: str | None = None
