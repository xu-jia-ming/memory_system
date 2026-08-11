"""Compression coordinator domain input and result models (STM-009)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.models.working_memory import WorkingMemoryMessage


class ArchiveSelection(BaseModel):
    """Selected head-prefix batch for a compression round."""

    model_config = ConfigDict(strict=True)

    prefix: list[WorkingMemoryMessage]
    prefix_tokens: int = Field(ge=0)
    projected_remaining: int = Field(ge=0)


class CompressionCoordinationResult(BaseModel):
    """Outcome of run_compression_coordination."""

    model_config = ConfigDict(strict=True)

    status: CompressionStatus
    rounds_completed: int = Field(ge=0)


class WriteMessageCoordinatorResult(BaseModel):
    """HTTP-ready write + coordination outcome."""

    model_config = ConfigDict(strict=True)

    message_id: str
    status: Literal["success", "duplicate"]
    compression_status: CompressionStatus
