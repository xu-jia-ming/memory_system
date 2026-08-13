"""RET-004 retrieval scoring orchestration: ACT-R, Top-K, Evidence aggregation."""

from __future__ import annotations

from typing import Protocol

from neo4j import AsyncDriver

from memory_system.domain.models.retrieval_scoring import (
    RetrievalScoringFailure,
    RetrievalScoringOutcome,
    RetrievalScoringQuery,
    RetrievalScoringSuccess,
    ScoredRetrievalMemory,
)
from memory_system.domain.services.act_r_scoring import (
    ScoredCandidateIntermediate,
    compute_act_r_components,
    compute_final_score,
    sort_scored_candidates,
)
from memory_system.domain.services.evidence_aggregation import (
    EvidenceRow,
    aggregate_evidence_for_memory,
    group_evidence_rows_by_memory,
)
from memory_system.infrastructure.neo4j.retrieval_evidence_read_repository import (
    RetrievalEvidenceReadError,
    RetrievalEvidenceReadRepository,
)
from memory_system.settings.models import Settings


class RetrievalEvidenceReadPort(Protocol):
    async def load_evidence_for_memories(
        self,
        user_id: str,
        memory_ids: list[str],
    ) -> list[EvidenceRow]: ...


class RetrievalScoringService:
    """ACT-R scoring, deterministic ordering, Top-K truncation, and Evidence aggregation."""

    def __init__(
        self,
        evidence_repo: RetrievalEvidenceReadPort,
        *,
        settings: Settings,
    ) -> None:
        self._evidence_repo = evidence_repo
        self._settings = settings

    async def score(self, query: RetrievalScoringQuery) -> RetrievalScoringOutcome:
        retrieval_settings = self._settings.memory_retrieval
        authoritative = query.authoritative_success

        if not authoritative.user_id:
            raise ValueError("user_id must be non-empty")
        if query.top_k < 1 or query.top_k > retrieval_settings.max_top_k:
            raise ValueError(
                f"top_k must be between 1 and {retrieval_settings.max_top_k} inclusive"
            )
        if query.current_time < 0:
            raise ValueError("current_time must be non-negative")

        merged_candidates = list(authoritative.direct_candidates) + list(
            authoritative.expanded_candidates
        )

        scored_intermediates: list[ScoredCandidateIntermediate] = []
        for candidate in merged_candidates:
            components = compute_act_r_components(
                candidate,
                query.current_time,
                retrieval_settings,
            )
            if components is None:
                continue
            final_score = compute_final_score(
                components,
                candidate.memory.status,
                retrieval_settings,
            )
            scored_intermediates.append(
                ScoredCandidateIntermediate(
                    candidate=candidate,
                    act_r_components=components,
                    final_score=final_score,
                )
            )

        sorted_candidates = sort_scored_candidates(scored_intermediates)
        top_k_candidates = sorted_candidates[: query.top_k]

        if not top_k_candidates:
            return RetrievalScoringOutcome(
                outcome="success",
                success=RetrievalScoringSuccess(
                    user_id=authoritative.user_id,
                    retrieval_mode=authoritative.retrieval_mode,
                    effective_channel_count=authoritative.effective_channel_count,
                    scored_memories=[],
                    warnings=list(authoritative.warnings),
                ),
            )

        top_k_ids = [item.candidate.memory_id for item in top_k_candidates]
        try:
            evidence_rows = await self._evidence_repo.load_evidence_for_memories(
                authoritative.user_id,
                top_k_ids,
            )
        except RetrievalEvidenceReadError as exc:
            return RetrievalScoringOutcome(
                outcome="failure",
                failure=RetrievalScoringFailure(
                    kind="graph_load_failed",
                    message=str(exc),
                ),
            )

        evidence_by_memory = group_evidence_rows_by_memory(evidence_rows)
        scored_memories: list[ScoredRetrievalMemory] = []
        for item in top_k_candidates:
            candidate = item.candidate
            memory = candidate.memory
            aggregation = aggregate_evidence_for_memory(
                evidence_by_memory.get(candidate.memory_id, []),
                retrieval_settings.max_source_message_ids,
            )
            scored_memories.append(
                ScoredRetrievalMemory(
                    memory_id=candidate.memory_id,
                    memory_type=memory.memory_type,
                    status=memory.status,
                    content=memory.content,
                    subject_entity=memory.subject_entity,
                    object_entity=memory.object_entity,
                    predicate=memory.predicate,
                    object_value=memory.object_value,
                    event_status=memory.event_status,
                    start_time=memory.start_time,
                    end_time=memory.end_time,
                    confidence=memory.confidence,
                    importance=memory.importance,
                    latest_source_time=memory.latest_source_time,
                    retrieval_source=list(candidate.retrieval_source),
                    bm25_rank=candidate.bm25_rank,
                    vector_rank=candidate.vector_rank,
                    bm25_score=candidate.bm25_score,
                    vector_score=candidate.vector_score,
                    rrf_score=candidate.rrf_score,
                    min_available_rank=candidate.min_available_rank,
                    candidate_origin=candidate.candidate_origin,
                    act_r_components=item.act_r_components,
                    final_score=item.final_score,
                    evidence_count=aggregation.evidence_count,
                    source_message_ids=aggregation.source_message_ids,
                )
            )

        return RetrievalScoringOutcome(
            outcome="success",
            success=RetrievalScoringSuccess(
                user_id=authoritative.user_id,
                retrieval_mode=authoritative.retrieval_mode,
                effective_channel_count=authoritative.effective_channel_count,
                scored_memories=scored_memories,
                warnings=list(authoritative.warnings),
            ),
        )


def create_retrieval_scoring_service(
    *,
    neo4j_driver: AsyncDriver,
    settings: Settings,
) -> RetrievalScoringService:
    retrieval_settings = settings.memory_retrieval
    evidence_repo = RetrievalEvidenceReadRepository(
        neo4j_driver,
        neo4j_timeout_seconds=float(retrieval_settings.neo4j_timeout_seconds),
    )
    return RetrievalScoringService(
        evidence_repo=evidence_repo,
        settings=settings,
    )
