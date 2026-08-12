"""Pydantic schemas for Extraction Admin API (§2.1.14)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionLastErrorResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    error_code: str
    failed_stage: str
    message: str


class ExtractionStatusResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    archive_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    attempt_count: int = Field(ge=0)
    last_error: ExtractionLastErrorResponse | None = None
    completed_time: int | None = None


class ExtractionMutationResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    archive_id: str
    status: Literal["pending"]
