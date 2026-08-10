"""Compression LLM domain models (STM-007)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.models.context_archive import ContextArchiveMessage


class CompressionLlmOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class CompressionLlmInput(BaseModel):
    """Prepared LLM input; does not include coordinator lock/archive I/O fields."""

    model_config = ConfigDict(strict=True)

    existing_compressed_context: str
    archived_messages: list[ContextArchiveMessage]
    max_compressed_context_estimated_tokens: int = Field(gt=0)
    request_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    archive_id: str | None = None


class CompressionLlmOutput(BaseModel):
    """LLM JSON output schema (§1.2.5)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    compressed_context: str


class CompressionLlmSuccess(BaseModel):
    model_config = ConfigDict(strict=True)

    compressed_context: str
    new_compressed_context_tokens: int = Field(ge=0)
    prompt_version: str
    model: str


class CompressionLlmFailure(BaseModel):
    model_config = ConfigDict(strict=True)

    error_code: Literal[
        "llm_empty_output",
        "llm_invalid_output",
        "compression_output_too_large",
        "llm_timeout",
        "llm_request_failed",
        "invalid_compression_input",
    ]
    prompt_version: str
    model: str
    attempt_count: int = Field(ge=1, le=2)


class CompressionLlmResult(BaseModel):
    model_config = ConfigDict(strict=True)

    outcome: CompressionLlmOutcome
    success: CompressionLlmSuccess | None = None
    failure: CompressionLlmFailure | None = None


class CompressionFinalizeLlmPayload(BaseModel):
    """Handoff payload for STM-008 Finalize Lua (typing-only in STM-007)."""

    model_config = ConfigDict(strict=True)

    compressed_context: str
    new_compressed_context_tokens: int = Field(ge=0)
