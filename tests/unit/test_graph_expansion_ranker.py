"""Unit tests for graph expansion ranker (RET-003 U8-U13, U16)."""

from __future__ import annotations

import pytest
from tests.unit.test_authoritative_recall_service import make_validated_direct

from memory_system.domain.models.hybrid_retrieval import FusedRetrievalCandidate
from memory_system.domain.services.graph_expansion_ranker import (
    ExpansionEdge,
    aggregate_expanded_candidates,
    dedupe_rrf_candidates,
    merge_overlap_with_direct,
    rank_per_seed_edges,
)


def test_u8_tier_zero_preferred() -> None:
    edges = [
        ExpansionEdge("seed-1", "rel-a", 2, 0.5, 100, "fact", "active"),
        ExpansionEdge("seed-1", "rel-b", 0, 0.5, 100, "fact", "active"),
        ExpansionEdge("seed-1", "rel-c", 1, 0.5, 100, "fact", "active"),
    ]
    ranked = rank_per_seed_edges(edges, per_seed_limit=3)
    assert [edge.related_id for edge in ranked] == ["rel-b", "rel-c", "rel-a"]


def test_u9_per_seed_limit_two() -> None:
    edges = [
        ExpansionEdge("seed-1", f"rel-{index}", 0, 1.0 - index * 0.1, 100, "fact", "active")
        for index in range(5)
    ]
    ranked = rank_per_seed_edges(edges, per_seed_limit=2)
    assert len(ranked) == 2


def test_u10_global_max_graph_candidates() -> None:
    edges = [
        ExpansionEdge("seed-1", f"rel-{index:02d}", 0, 1.0, index, "fact", "active")
        for index in range(25)
    ]
    per_seed = rank_per_seed_edges(edges, per_seed_limit=25)
    aggregated = aggregate_expanded_candidates(
        per_seed,
        seed_scores={"seed-1": 1.0},
        max_graph_candidates=20,
        graph_decay=0.60,
    )
    assert len(aggregated) == 20


def test_u11_graph_retrieval_score_decay() -> None:
    edges = [ExpansionEdge("seed-1", "rel-1", 0, 1.0, 100, "fact", "active")]
    aggregated = aggregate_expanded_candidates(
        edges,
        seed_scores={"seed-1": 0.8},
        max_graph_candidates=20,
        graph_decay=0.60,
    )
    assert aggregated[0].graph_retrieval_score == pytest.approx(0.48)


def test_u12_multi_seed_max_score() -> None:
    edges = [
        ExpansionEdge("seed-1", "rel-shared", 0, 1.0, 100, "fact", "active"),
        ExpansionEdge("seed-2", "rel-shared", 0, 1.0, 100, "fact", "active"),
    ]
    aggregated = aggregate_expanded_candidates(
        edges,
        seed_scores={"seed-1": 0.5, "seed-2": 0.9},
        max_graph_candidates=20,
        graph_decay=0.60,
    )
    assert aggregated[0].graph_retrieval_score == pytest.approx(0.54)


def test_u13_overlap_appends_graph_source() -> None:
    direct = [
        make_validated_direct(
            memory_id="mem-overlap",
            normalized_retrieval_score=0.75,
            retrieval_source=["vector"],
        ),
    ]
    aggregated = aggregate_expanded_candidates(
        [ExpansionEdge("seed-1", "mem-overlap", 0, 1.0, 100, "fact", "active")],
        seed_scores={"seed-1": 0.2},
        max_graph_candidates=20,
        graph_decay=0.60,
    )
    updated, pure = merge_overlap_with_direct(direct, aggregated)
    assert pure == []
    assert updated[0].retrieval_source == ["graph", "vector"]
    assert updated[0].normalized_retrieval_score == 0.75


def test_u3_rrf_dedupe_keeps_best_rank() -> None:
    candidates = [
        FusedRetrievalCandidate(
            memory_id="mem-dup",
            bm25_rank=3,
            vector_rank=None,
            bm25_score=1.0,
            vector_score=None,
            retrieval_source=["bm25"],
            rrf_score=0.2,
            min_available_rank=3,
            normalized_retrieval_score=0.2,
        ),
        FusedRetrievalCandidate(
            memory_id="mem-dup",
            bm25_rank=None,
            vector_rank=1,
            bm25_score=None,
            vector_score=1.5,
            retrieval_source=["vector"],
            rrf_score=0.5,
            min_available_rank=1,
            normalized_retrieval_score=0.5,
        ),
    ]
    deduped = dedupe_rrf_candidates(candidates)
    assert len(deduped) == 1
    assert deduped[0].min_available_rank == 1
    assert deduped[0].retrieval_source == ["vector"]
