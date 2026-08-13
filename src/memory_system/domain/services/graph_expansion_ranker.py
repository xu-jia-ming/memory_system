"""RET-003 pure graph expansion ranking and overlap merge (§8)."""

from __future__ import annotations

from dataclasses import dataclass

from memory_system.domain.models.authoritative_recall import (
    RetrievalSource,
    ValidatedRetrievalCandidate,
)
from memory_system.domain.models.hybrid_retrieval import FusedRetrievalCandidate

_SOURCE_ORDER: dict[RetrievalSource, int] = {"bm25": 0, "graph": 1, "vector": 2}


@dataclass(frozen=True, slots=True)
class ExpansionEdge:
    seed_id: str
    related_id: str
    expansion_tier: int
    importance: float
    latest_source_time: int | None
    memory_type: str
    status: str


@dataclass(frozen=True, slots=True)
class AggregatedExpansionCandidate:
    related_id: str
    graph_retrieval_score: float
    expansion_tier: int
    importance: float
    latest_source_time: int | None


def dedupe_rrf_candidates(
    candidates: list[FusedRetrievalCandidate],
) -> list[FusedRetrievalCandidate]:
    best_by_id: dict[str, FusedRetrievalCandidate] = {}
    for candidate in candidates:
        existing = best_by_id.get(candidate.memory_id)
        if existing is None:
            best_by_id[candidate.memory_id] = candidate
            continue
        if candidate.min_available_rank < existing.min_available_rank or (
            candidate.min_available_rank == existing.min_available_rank
            and candidate.memory_id < existing.memory_id
        ):
            best_by_id[candidate.memory_id] = candidate
    deduped = list(best_by_id.values())
    deduped.sort(key=lambda item: (item.min_available_rank, item.memory_id))
    return deduped


def _edge_sort_key(edge: ExpansionEdge) -> tuple[int, float, int, str]:
    return (
        edge.expansion_tier,
        -edge.importance,
        -(edge.latest_source_time or 0),
        edge.related_id,
    )


def _dedupe_edges_per_seed(edges: list[ExpansionEdge]) -> list[ExpansionEdge]:
    best: dict[str, ExpansionEdge] = {}
    for edge in edges:
        existing = best.get(edge.related_id)
        if existing is None or edge.expansion_tier < existing.expansion_tier:
            best[edge.related_id] = edge
        elif edge.expansion_tier == existing.expansion_tier and _edge_sort_key(
            edge
        ) < _edge_sort_key(existing):
            best[edge.related_id] = edge
    return list(best.values())


def rank_per_seed_edges(
    edges: list[ExpansionEdge],
    *,
    per_seed_limit: int,
) -> list[ExpansionEdge]:
    grouped: dict[str, list[ExpansionEdge]] = {}
    for edge in edges:
        grouped.setdefault(edge.seed_id, []).append(edge)

    selected: list[ExpansionEdge] = []
    for seed_edges in grouped.values():
        deduped = _dedupe_edges_per_seed(seed_edges)
        deduped.sort(key=_edge_sort_key)
        selected.extend(deduped[:per_seed_limit])
    return selected


def compute_graph_retrieval_score(
    related_id: str,
    *,
    seed_scores: dict[str, float | None],
    edges: list[ExpansionEdge],
    graph_decay: float,
) -> float:
    score = 0.0
    for edge in edges:
        if edge.related_id != related_id:
            continue
        normalized = seed_scores.get(edge.seed_id)
        if normalized is None:
            continue
        score = max(score, normalized * graph_decay)
    return score


def aggregate_expanded_candidates(
    per_seed_edges: list[ExpansionEdge],
    *,
    seed_scores: dict[str, float | None],
    max_graph_candidates: int,
    graph_decay: float,
) -> list[AggregatedExpansionCandidate]:
    best_edge_by_related: dict[str, ExpansionEdge] = {}
    for edge in per_seed_edges:
        existing = best_edge_by_related.get(edge.related_id)
        if existing is None or _edge_sort_key(edge) < _edge_sort_key(existing):
            best_edge_by_related[edge.related_id] = edge

    ranked = sorted(best_edge_by_related.values(), key=_edge_sort_key)
    truncated = ranked[:max_graph_candidates]
    return [
        AggregatedExpansionCandidate(
            related_id=edge.related_id,
            graph_retrieval_score=compute_graph_retrieval_score(
                edge.related_id,
                seed_scores=seed_scores,
                edges=per_seed_edges,
                graph_decay=graph_decay,
            ),
            expansion_tier=edge.expansion_tier,
            importance=edge.importance,
            latest_source_time=edge.latest_source_time,
        )
        for edge in truncated
    ]


def sort_retrieval_source(sources: list[RetrievalSource]) -> list[RetrievalSource]:
    return sorted(set(sources), key=lambda item: _SOURCE_ORDER[item])


def append_graph_source(sources: list[RetrievalSource]) -> list[RetrievalSource]:
    combined: list[RetrievalSource] = list(sources)
    if "graph" not in combined:
        combined.append("graph")
    return sort_retrieval_source(combined)


def merge_overlap_with_direct(
    direct_candidates: list[ValidatedRetrievalCandidate],
    aggregated: list[AggregatedExpansionCandidate],
) -> tuple[list[ValidatedRetrievalCandidate], list[AggregatedExpansionCandidate]]:
    direct_ids = {candidate.memory_id for candidate in direct_candidates}
    updated_direct: list[ValidatedRetrievalCandidate] = []
    pure_expanded: list[AggregatedExpansionCandidate] = []

    direct_by_id = {candidate.memory_id: candidate for candidate in direct_candidates}

    for item in aggregated:
        if item.related_id in direct_ids:
            direct = direct_by_id[item.related_id]
            direct_by_id[item.related_id] = direct.model_copy(
                update={
                    "retrieval_source": append_graph_source(list(direct.retrieval_source)),
                },
            )
        else:
            pure_expanded.append(item)

    for candidate in direct_candidates:
        updated_direct.append(direct_by_id[candidate.memory_id])
    return updated_direct, pure_expanded


def expanded_candidate_sort_key(
    candidate: AggregatedExpansionCandidate,
) -> tuple[int, float, int, str]:
    return (
        candidate.expansion_tier,
        -candidate.importance,
        -(candidate.latest_source_time or 0),
        candidate.related_id,
    )
