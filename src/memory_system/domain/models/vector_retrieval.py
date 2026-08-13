"""RET-002 Vector semantic retrieval domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class VectorRetrievalQuery(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    query_vector: list[float]
    memory_types: list[str] | None = None
    include_conflicted: bool = False
    include_history: bool = False


class VectorRetrievalHit(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    rank: int
    score: float


class VectorRetrievalSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    hits: list[VectorRetrievalHit]
    total_hits: int


class VectorRetrievalFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["channel_failure", "skipped_query_too_long"]
    message: str
    retryable: bool


class VectorRetrievalOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: Literal["success", "failure"]
    success: VectorRetrievalSuccess | None = None
    failure: VectorRetrievalFailure | None = None
