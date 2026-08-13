"""RET-002 hybrid retrieval and RRF fusion domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HybridRetrievalQuery(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    query: str
    memory_types: list[str] | None = None
    include_conflicted: bool = False
    include_history: bool = False


class FusedRetrievalCandidate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    bm25_rank: int | None
    vector_rank: int | None
    bm25_score: float | None
    vector_score: float | None
    retrieval_source: list[Literal["bm25", "vector"]]
    rrf_score: float
    min_available_rank: int
    normalized_retrieval_score: float | None


class HybridRetrievalSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    retrieval_mode: Literal["hybrid", "bm25_only", "vector_only", "none"]
    candidates: list[FusedRetrievalCandidate]
    effective_channel_count: int


class HybridRetrievalFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["retrieval_unavailable"] = "retrieval_unavailable"
    message: str


class HybridRetrievalOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: Literal["success", "failure"]
    success: HybridRetrievalSuccess | None = None
    failure: HybridRetrievalFailure | None = None
