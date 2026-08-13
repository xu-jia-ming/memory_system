"""RET-001 BM25 keyword retrieval domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Bm25RetrievalQuery(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    query: str
    memory_types: list[str] | None = None
    include_conflicted: bool = False
    include_history: bool = False


class Bm25RetrievalHit(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    rank: int
    score: float


class Bm25RetrievalSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    hits: list[Bm25RetrievalHit]
    total_hits: int


class Bm25RetrievalFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["channel_failure"] = "channel_failure"
    message: str
    retryable: bool


class Bm25RetrievalOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: Literal["success", "failure"]
    success: Bm25RetrievalSuccess | None = None
    failure: Bm25RetrievalFailure | None = None
