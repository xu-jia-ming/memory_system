"""RET-004 ACT-R scoring and evidence aggregation domain models (§2.2.11 / §2.2.12)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from memory_system.domain.models.authoritative_recall import (
    AuthoritativeRecallSuccess,
    CandidateOrigin,
    InternalRetrievalWarning,
    RetrievalSource,
)
from memory_system.domain.models.retrieval_memory_snapshot import RetrievalEntitySnapshot

RetrievalScoringFailureKind = Literal["neo4j_read_failure", "graph_load_failed"]


class ActRScoreComponents(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    retrieval_score: float
    importance_score: float
    confidence_score: float
    frequency_score: float
    recency_score: float


class EvidenceAggregationResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    evidence_count: int
    source_message_ids: list[str]


class ScoredRetrievalMemory(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    memory_id: str
    memory_type: str
    status: str
    content: str
    subject_entity: RetrievalEntitySnapshot | None
    object_entity: RetrievalEntitySnapshot | None
    predicate: str
    object_value: str | None
    event_status: str | None
    start_time: int | None
    end_time: int | None
    confidence: float
    importance: float
    latest_source_time: int | None
    retrieval_source: list[RetrievalSource]
    bm25_rank: int | None
    vector_rank: int | None
    bm25_score: float | None
    vector_score: float | None
    rrf_score: float | None
    min_available_rank: int | None
    candidate_origin: CandidateOrigin
    act_r_components: ActRScoreComponents
    final_score: float
    evidence_count: int
    source_message_ids: list[str]


class RetrievalScoringQuery(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    authoritative_success: AuthoritativeRecallSuccess
    top_k: int = Field(ge=1)
    current_time: int = Field(ge=0)


class RetrievalScoringSuccess(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str
    retrieval_mode: Literal["hybrid", "bm25_only", "vector_only", "none"]
    effective_channel_count: int
    scored_memories: list[ScoredRetrievalMemory]
    warnings: list[InternalRetrievalWarning]


class RetrievalScoringFailure(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: RetrievalScoringFailureKind
    message: str


class RetrievalScoringOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    outcome: Literal["success", "failure"]
    success: RetrievalScoringSuccess | None = None
    failure: RetrievalScoringFailure | None = None
