"""Unit tests for ACT-R scoring pure functions (RET-004 NC-1..NC-7)."""

from __future__ import annotations

import math

import pytest

from memory_system.domain.models.authoritative_recall import ValidatedRetrievalCandidate
from memory_system.domain.models.retrieval_memory_snapshot import (
    RetrievalEntitySnapshot,
    RetrievalMemorySnapshot,
)
from memory_system.domain.models.retrieval_scoring import ActRScoreComponents
from memory_system.domain.services.act_r_scoring import (
    ScoredCandidateIntermediate,
    compute_act_r_components,
    compute_final_score,
    compute_frequency_score,
    compute_recency_score,
    select_retrieval_score,
    sort_scored_candidates,
)
from memory_system.settings import get_settings

USER_ID = "user-a"
SETTINGS = get_settings().memory_retrieval
_LN_2 = math.log(2)
_LN_21 = math.log(21)


def make_memory_snapshot(
    *,
    memory_id: str = "mem-1",
    status: str = "active",
    importance: float = 0.8,
    confidence: float = 0.9,
    retrieval_count: int = 0,
    last_retrieved_time: int | None = None,
    latest_source_time: int | None = None,
) -> RetrievalMemorySnapshot:
    return RetrievalMemorySnapshot(
        memory_id=memory_id,
        user_id=USER_ID,
        memory_type="fact",
        status=status,
        content=f"content-{memory_id}",
        subject_entity_id="ent-subject",
        predicate="works_on",
        object_entity_id="ent-object",
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        importance=importance,
        confidence=confidence,
        retrieval_count=retrieval_count,
        last_retrieved_time=last_retrieved_time,
        latest_source_time=latest_source_time,
        updated_time=1_700_000_000,
        subject_entity=RetrievalEntitySnapshot(
            entity_id="ent-subject",
            canonical_name="Subject",
            aliases=[],
            entity_type="concept",
            normalized_name="subject",
        ),
        object_entity=None,
    )


def make_candidate(
    *,
    memory_id: str = "mem-1",
    candidate_origin: str = "direct",
    normalized_retrieval_score: float | None = 0.8,
    graph_retrieval_score: float | None = None,
    memory: RetrievalMemorySnapshot | None = None,
) -> ValidatedRetrievalCandidate:
    return ValidatedRetrievalCandidate(
        memory_id=memory_id,
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.5,
        vector_score=None,
        retrieval_source=["bm25"],
        rrf_score=0.5,
        min_available_rank=1,
        normalized_retrieval_score=normalized_retrieval_score,
        graph_retrieval_score=graph_retrieval_score,
        candidate_origin=candidate_origin,  # type: ignore[arg-type]
        memory=memory or make_memory_snapshot(memory_id=memory_id),
    )


class TestNC1FrequencyScore:
    @pytest.mark.parametrize(
        ("retrieval_count", "expected"),
        [
            (0, 0.0),
            (1, _LN_2 / _LN_21),
            (19, math.log(20) / _LN_21),
            (20, 1.0),
            (100, 1.0),
        ],
    )
    def test_frequency_score(self, retrieval_count: int, expected: float) -> None:
        assert compute_frequency_score(retrieval_count) == pytest.approx(expected)


class TestNC2RecencyScore:
    @pytest.mark.parametrize(
        ("current_time", "reference_time", "expected"),
        [
            (86400, 0, math.exp(-_LN_2 / 30)),
            (86400 * 30, 0, 0.5),
            (86400 * 60, 86400 * 30, 0.5),
            (0, 0, 1.0),
        ],
    )
    def test_recency_score(
        self,
        current_time: int,
        reference_time: int,
        expected: float,
    ) -> None:
        if reference_time == 0:
            last_retrieved_time = None
            latest_source_time = None
        else:
            last_retrieved_time = None
            latest_source_time = reference_time
        score = compute_recency_score(
            last_retrieved_time,
            latest_source_time,
            current_time,
            30,
        )
        assert score == pytest.approx(expected)

    def test_recency_with_last_retrieved_time(self) -> None:
        current_time = 1_000_000
        score = compute_recency_score(None, None, current_time, 30)
        age_days = current_time / 86400
        assert score == pytest.approx(math.exp(-_LN_2 * age_days / 30))


class TestNC3WeightedScore:
    def test_all_ones_active(self) -> None:
        components = ActRScoreComponents(
            retrieval_score=1.0,
            importance_score=1.0,
            confidence_score=1.0,
            frequency_score=1.0,
            recency_score=1.0,
        )
        assert compute_final_score(components, "active", SETTINGS) == 1.0

    def test_mixed_components(self) -> None:
        components = ActRScoreComponents(
            retrieval_score=0.8,
            importance_score=0.6,
            confidence_score=0.9,
            frequency_score=0.5,
            recency_score=0.4,
        )
        assert compute_final_score(components, "active", SETTINGS) == pytest.approx(0.71)


class TestNC4StatusPenalty:
    def test_conflicted_penalty(self) -> None:
        components = ActRScoreComponents(
            retrieval_score=0.8,
            importance_score=0.6,
            confidence_score=0.9,
            frequency_score=0.5,
            recency_score=0.4,
        )
        assert compute_final_score(components, "conflicted", SETTINGS) == pytest.approx(0.6035)

    def test_superseded_penalty(self) -> None:
        components = ActRScoreComponents(
            retrieval_score=0.8,
            importance_score=0.6,
            confidence_score=0.9,
            frequency_score=0.5,
            recency_score=0.4,
        )
        assert compute_final_score(components, "superseded", SETTINGS) == pytest.approx(0.426)


class TestNC5RetrievalScoreSelection:
    def test_direct_uses_normalized(self) -> None:
        candidate = make_candidate(
            candidate_origin="direct",
            normalized_retrieval_score=0.75,
            graph_retrieval_score=0.30,
        )
        assert select_retrieval_score(candidate) == 0.75

    def test_expanded_uses_graph(self) -> None:
        candidate = make_candidate(
            candidate_origin="expanded",
            normalized_retrieval_score=None,
            graph_retrieval_score=0.42,
        )
        assert select_retrieval_score(candidate) == 0.42

    def test_direct_missing_normalized_skipped(self) -> None:
        candidate = make_candidate(
            candidate_origin="direct",
            normalized_retrieval_score=None,
            graph_retrieval_score=0.50,
        )
        assert select_retrieval_score(candidate) is None
        assert compute_act_r_components(candidate, 0, SETTINGS) is None


class TestNC6Clamp:
    def test_importance_clamped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        memory = make_memory_snapshot(importance=1.2)
        candidate = make_candidate(memory=memory, normalized_retrieval_score=0.5)
        components = compute_act_r_components(candidate, 0, SETTINGS)
        assert components is not None
        assert components.importance_score == 1.0


class TestNC7SortTieBreak:
    def test_latest_source_time_wins(self) -> None:
        shared_score = 0.71
        components = ActRScoreComponents(
            retrieval_score=0.8,
            importance_score=0.6,
            confidence_score=0.9,
            frequency_score=0.5,
            recency_score=0.4,
        )
        candidate_a = make_candidate(
            memory_id="mem-a",
            memory=make_memory_snapshot(
                memory_id="mem-a",
                latest_source_time=100,
                importance=0.5,
            ),
        )
        candidate_b = make_candidate(
            memory_id="mem-b",
            memory=make_memory_snapshot(
                memory_id="mem-b",
                latest_source_time=200,
                importance=0.9,
            ),
        )
        sorted_result = sort_scored_candidates(
            [
                ScoredCandidateIntermediate(candidate_a, components, shared_score),
                ScoredCandidateIntermediate(candidate_b, components, shared_score),
            ]
        )
        assert sorted_result[0].candidate.memory_id == "mem-b"

    def test_importance_tie_break(self) -> None:
        components = ActRScoreComponents(
            retrieval_score=0.8,
            importance_score=0.6,
            confidence_score=0.9,
            frequency_score=0.5,
            recency_score=0.4,
        )
        candidate_a = make_candidate(
            memory_id="mem-a",
            memory=make_memory_snapshot(
                memory_id="mem-a",
                latest_source_time=100,
                importance=0.5,
            ),
        )
        candidate_b = make_candidate(
            memory_id="mem-b",
            memory=make_memory_snapshot(
                memory_id="mem-b",
                latest_source_time=100,
                importance=0.9,
            ),
        )
        sorted_result = sort_scored_candidates(
            [
                ScoredCandidateIntermediate(candidate_a, components, 0.71),
                ScoredCandidateIntermediate(candidate_b, components, 0.71),
            ]
        )
        assert sorted_result[0].candidate.memory_id == "mem-b"

    def test_memory_id_tie_break(self) -> None:
        components = ActRScoreComponents(
            retrieval_score=0.8,
            importance_score=0.6,
            confidence_score=0.9,
            frequency_score=0.5,
            recency_score=0.4,
        )
        candidate_a = make_candidate(
            memory_id="mem-a",
            memory=make_memory_snapshot(
                memory_id="mem-a",
                latest_source_time=100,
                importance=0.5,
            ),
        )
        candidate_b = make_candidate(
            memory_id="mem-b",
            memory=make_memory_snapshot(
                memory_id="mem-b",
                latest_source_time=100,
                importance=0.5,
            ),
        )
        sorted_result = sort_scored_candidates(
            [
                ScoredCandidateIntermediate(candidate_b, components, 0.71),
                ScoredCandidateIntermediate(candidate_a, components, 0.71),
            ]
        )
        assert sorted_result[0].candidate.memory_id == "mem-a"
