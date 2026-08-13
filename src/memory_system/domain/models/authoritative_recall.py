"""RET-003 authoritative recall domain models (§2.2.10 internal outcome)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from memory_system.domain.models.hybrid_retrieval import HybridRetrievalSuccess
from memory_system.domain.models.retrieval_memory_snapshot import RetrievalMemorySnapshot

RetrievalSource = Literal["bm25", "vector", "graph"]
CandidateOrigin = Literal["direct", "expanded"]
InternalWarningKind = Literal[
    "dirty_index_document",
    "stale_index_document",
    "graph_expansion_failed",
]


class AuthoritativeRecallQuery(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    hybrid_success: HybridRetrievalSuccess
    memory_types: list[str] | None = None
    include_conflicted: bool = False
    include_history: bool = False
    graph_expand: bool = True


class ValidatedRetrievalCandidate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    bm25_rank: int | None
    vector_rank: int | None
    bm25_score: float | None
    vector_score: float | None
    retrieval_source: list[RetrievalSource]
    rrf_score: float | None
    min_available_rank: int | None
    normalized_retrieval_score: float | None
    graph_retrieval_score: float | None = None
    candidate_origin: CandidateOrigin
    memory: RetrievalMemorySnapshot


class InternalRetrievalWarning(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: InternalWarningKind
    memory_id: str | None = None


class AuthoritativeRecallSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    retrieval_mode: Literal["hybrid", "bm25_only", "vector_only", "none"]
    effective_channel_count: int
    direct_candidates: list[ValidatedRetrievalCandidate]
    expanded_candidates: list[ValidatedRetrievalCandidate]
    warnings: list[InternalRetrievalWarning]


class AuthoritativeRecallFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["neo4j_read_failure"] = "neo4j_read_failure"
    message: str


class AuthoritativeRecallOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: Literal["success", "failure"]
    success: AuthoritativeRecallSuccess | None = None
    failure: AuthoritativeRecallFailure | None = None
