"""RET-002 RRF fusion pure function (§2.2.9)."""

from __future__ import annotations

from typing import Literal

from memory_system.domain.models.bm25_retrieval import Bm25RetrievalOutcome
from memory_system.domain.models.hybrid_retrieval import (
    FusedRetrievalCandidate,
    HybridRetrievalFailure,
    HybridRetrievalOutcome,
    HybridRetrievalSuccess,
)
from memory_system.domain.models.vector_retrieval import VectorRetrievalOutcome


def fuse_rrf(
    bm25: Bm25RetrievalOutcome,
    vector: VectorRetrievalOutcome,
    *,
    rrf_k: int,
    fused_top_n: int,
    user_id: str,
) -> HybridRetrievalOutcome:
    bm25_effective, bm25_rank_map, bm25_score_map = _effective_channel_maps(bm25)
    vector_effective, vector_rank_map, vector_score_map = _effective_channel_maps(vector)

    effective_channel_count = int(bm25_effective) + int(vector_effective)

    if effective_channel_count == 0:
        if _is_channel_failure(bm25) and _is_channel_failure(vector):
            return HybridRetrievalOutcome(
                outcome="failure",
                failure=HybridRetrievalFailure(
                    message="both retrieval channels unavailable",
                ),
            )
        return HybridRetrievalOutcome(
            outcome="success",
            success=HybridRetrievalSuccess(
                user_id=user_id,
                retrieval_mode="none",
                candidates=[],
                effective_channel_count=0,
            ),
        )

    retrieval_mode = _resolve_retrieval_mode(bm25_effective, vector_effective)
    rrf_max = effective_channel_count / (rrf_k + 1)

    memory_ids = set(bm25_rank_map) | set(vector_rank_map)
    candidates: list[FusedRetrievalCandidate] = []
    for memory_id in memory_ids:
        bm25_rank = bm25_rank_map.get(memory_id)
        vector_rank = vector_rank_map.get(memory_id)
        rrf_score = _compute_rrf_score(
            bm25_rank=bm25_rank,
            vector_rank=vector_rank,
            rrf_k=rrf_k,
        )
        sources: list[Literal["bm25", "vector"]] = []
        if bm25_rank is not None:
            sources.append("bm25")
        if vector_rank is not None:
            sources.append("vector")
        sources.sort()

        ranks = [rank for rank in (bm25_rank, vector_rank) if rank is not None]
        min_available_rank = min(ranks)

        normalized = min(1.0, rrf_score / rrf_max)

        candidates.append(
            FusedRetrievalCandidate(
                memory_id=memory_id,
                bm25_rank=bm25_rank,
                vector_rank=vector_rank,
                bm25_score=bm25_score_map.get(memory_id),
                vector_score=vector_score_map.get(memory_id),
                retrieval_source=sources,
                rrf_score=rrf_score,
                min_available_rank=min_available_rank,
                normalized_retrieval_score=normalized,
            )
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate.rrf_score,
            candidate.min_available_rank,
            candidate.memory_id,
        )
    )
    candidates = candidates[:fused_top_n]

    return HybridRetrievalOutcome(
        outcome="success",
        success=HybridRetrievalSuccess(
            user_id=user_id,
            retrieval_mode=retrieval_mode,
            candidates=candidates,
            effective_channel_count=effective_channel_count,
        ),
    )


def _compute_rrf_score(
    *,
    bm25_rank: int | None,
    vector_rank: int | None,
    rrf_k: int,
) -> float:
    score = 0.0
    if bm25_rank is not None:
        score += 1.0 / (rrf_k + bm25_rank)
    if vector_rank is not None:
        score += 1.0 / (rrf_k + vector_rank)
    return score


def _resolve_retrieval_mode(
    bm25_effective: bool,
    vector_effective: bool,
) -> Literal["hybrid", "bm25_only", "vector_only", "none"]:
    if bm25_effective and vector_effective:
        return "hybrid"
    if bm25_effective:
        return "bm25_only"
    if vector_effective:
        return "vector_only"
    return "none"


def _is_channel_failure(outcome: Bm25RetrievalOutcome | VectorRetrievalOutcome) -> bool:
    if outcome.outcome != "failure":
        return False
    if outcome.failure is None:
        return True
    return outcome.failure.kind in {"channel_failure", "skipped_query_too_long"}


def _effective_channel_maps(
    outcome: Bm25RetrievalOutcome | VectorRetrievalOutcome,
) -> tuple[bool, dict[str, int], dict[str, float]]:
    if outcome.outcome != "success" or outcome.success is None:
        return False, {}, {}

    hits = outcome.success.hits
    if not hits:
        return False, {}, {}

    rank_map: dict[str, int] = {}
    score_map: dict[str, float] = {}
    for hit in hits:
        if hit.memory_id in rank_map:
            return False, {}, {}
        rank_map[hit.memory_id] = hit.rank
        score_map[hit.memory_id] = hit.score

    return True, rank_map, score_map
