"""Compression finalize input/result models (STM-008; no HTTP)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.domain.models.compression_llm import CompressionFinalizeLlmPayload


class CompressionFinalizeInput(BaseModel):
    """Caller-supplied finalize preconditions + STM-007 LLM payload handoff."""

    model_config = ConfigDict(strict=True)

    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    expected_compression_version: int = Field(ge=0)
    pending_archive_id: str = Field(min_length=1)
    pending_archive_batch_key: str = Field(min_length=1)
    pending_archive_message_count: int = Field(gt=0)
    pending_archive_estimated_tokens: int = Field(ge=0)
    expected_first_message_id: str = Field(min_length=1)
    expected_last_message_id: str = Field(min_length=1)
    archived_message_tokens: int = Field(ge=0)
    old_compressed_context_tokens: int = Field(ge=0)
    lock_owner_token: str = Field(min_length=1)
    llm_payload: CompressionFinalizeLlmPayload
    updated_time: int | None = None

    @model_validator(mode="after")
    def _archived_tokens_match_pending(self) -> CompressionFinalizeInput:
        if self.archived_message_tokens != self.pending_archive_estimated_tokens:
            raise ValueError(
                "archived_message_tokens must equal pending_archive_estimated_tokens"
            )
        return self


class CompressionFinalizeResult(BaseModel):
    """Stable internal result for compression finalize orchestration."""

    model_config = ConfigDict(strict=True)

    status: CompressionFinalizeStatus
    new_compression_version: int | None = None
    new_estimated_tokens: int | None = None
