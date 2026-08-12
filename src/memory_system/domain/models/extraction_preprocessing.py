"""Strict, non-durable EXT-002 archive handoff models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ExtractionArchiveMessage(_StrictModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: int

    @field_validator("message_id")
    @classmethod
    def _message_id_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("message_id must not be empty")
        return value


class ValidatedRawArchive(_StrictModel):
    """Validated raw shape; created only after complete structural validation."""

    archive_id: str
    user_id: str
    session_id: str
    archive_batch_key: str
    base_compression_version: int
    messages: list[ExtractionArchiveMessage]
    created_time: int

    @field_validator("archive_id", "user_id", "session_id", "archive_batch_key")
    @classmethod
    def _identity_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("archive identity must not be empty")
        return value


class ExtractionReadyArchive(_StrictModel):
    """Finalized internal handoff; never persisted by EXT-002."""

    archive_id: str
    user_id: str
    session_id: str
    messages: list[ExtractionArchiveMessage]
