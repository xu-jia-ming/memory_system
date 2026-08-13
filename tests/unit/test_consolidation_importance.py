"""Unit tests for CON-001 consolidation importance pure functions (NC-1..NC-14, U1..U9, F1..F3)."""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import pytest

from memory_system.domain.models.consolidation_importance import (
    ConsolidationImportanceInput,
    ConsolidationImportanceSkip,
    ConsolidationImportanceSuccess,
)
from memory_system.domain.services.consolidation_importance import (
    base_importance_for_type,
    compute_confidence_score,
    compute_consolidation_importance,
    compute_consolidation_importance_components,
    compute_evidence_score,
    compute_inactive_days,
    compute_new_importance,
    compute_recency_score,
    compute_reference_time,
    compute_reinforcement_score,
    half_life_days_for,
)
from memory_system.settings import get_settings

SETTINGS = get_settings().memory_consolidation
_LN_2 = math.log(2)


def make_input(
    *,
    memory_type: str = "fact",
    confidence: float = 0.85,
    status: str = "active",
    created_time: int = 1_000_000,
    latest_source_time: int | None = None,
    independent_archive_count: int = 5,
    evaluation_time: int = 1_000_000,
) -> ConsolidationImportanceInput:
    return ConsolidationImportanceInput(
        memory_type=memory_type,
        confidence=confidence,
        status=status,
        created_time=created_time,
        latest_source_time=latest_source_time,
        independent_archive_count=independent_archive_count,
        evaluation_time=evaluation_time,
    )


class TestNC1BaseImportance:
    def test_profile(self) -> None:
        assert base_importance_for_type("profile") == 0.75

    def test_fact(self) -> None:
        assert base_importance_for_type("fact") == 0.70

    def test_preference(self) -> None:
        assert base_importance_for_type("preference") == 0.65

    def test_event(self) -> None:
        assert base_importance_for_type("event") == 0.55


class TestNC2ConfidenceScore:
    def test_negative_clamped(self) -> None:
        assert compute_confidence_score(-0.2) == 0.0

    def test_zero(self) -> None:
        assert compute_confidence_score(0.0) == 0.0

    def test_mid(self) -> None:
        assert compute_confidence_score(0.85) == 0.85

    def test_one(self) -> None:
        assert compute_confidence_score(1.0) == 1.0

    def test_above_one_clamped(self) -> None:
        assert compute_confidence_score(1.5) == 1.0


class TestNC3EvidenceScore:
    def test_count_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="> 0"):
            compute_evidence_score(0, SETTINGS.evidence_saturation_count)

    def test_count_one(self) -> None:
        expected = math.log(2) / math.log(6)
        assert compute_evidence_score(1, 5) == pytest.approx(expected, abs=1e-9)
        assert compute_evidence_score(1, 5) == pytest.approx(0.386853, abs=1e-6)

    def test_count_five_saturated(self) -> None:
        assert compute_evidence_score(5, 5) == 1.0

    def test_count_ten_saturated(self) -> None:
        assert compute_evidence_score(10, 5) == 1.0


class TestNC4ReferenceTimeInactiveDays:
    CREATED = 1_000_000
    EVAL_PLUS_ONE_DAY = CREATED + 86400

    def test_none_latest_source(self) -> None:
        assert compute_reference_time(None, self.CREATED) == self.CREATED
        assert compute_inactive_days(self.CREATED, self.EVAL_PLUS_ONE_DAY) == 1.0

    def test_latest_after_evaluation(self) -> None:
        ref = compute_reference_time(2_000_000, self.CREATED)
        assert ref == 2_000_000
        assert compute_inactive_days(ref, self.EVAL_PLUS_ONE_DAY) == 0.0

    def test_latest_before_created(self) -> None:
        ref = compute_reference_time(500_000, self.CREATED)
        assert ref == self.CREATED
        assert compute_inactive_days(ref, self.EVAL_PLUS_ONE_DAY) == 1.0


class TestNC5RecencyScore:
    def test_half_life_elapsed(self) -> None:
        assert compute_recency_score(180.0, 180) == 0.5

    def test_zero_inactive(self) -> None:
        assert compute_recency_score(0.0, 180) == 1.0


class TestNC6SupersededHalfLife:
    def test_event_superseded_uses_min_half_life(self) -> None:
        half_life = half_life_days_for("event", "superseded", SETTINGS)
        assert half_life == 30

    def test_superseded_recency_at_half_life(self) -> None:
        assert compute_recency_score(30.0, 30) == 0.5


class TestNC7ReinforcementScore:
    def test_full_scores(self) -> None:
        score = compute_reinforcement_score(1.0, 1.0, SETTINGS)
        assert score == 1.0

    def test_zero_confidence(self) -> None:
        score = compute_reinforcement_score(0.0, 1.0, SETTINGS)
        assert score == 0.45


class TestNC8FullComposition:
    def test_active_fact_clamped_to_max(self) -> None:
        raw = 0.70 * 1.0 + 0.35 * 1.0
        assert raw == pytest.approx(1.05)
        new = compute_new_importance(raw, "active", SETTINGS)
        assert new == 1.0


class TestNC9ConflictedMin:
    def test_conflicted_floor(self) -> None:
        new = compute_new_importance(0.10, "conflicted", SETTINGS)
        assert new == 0.30


class TestNC10ActiveMin:
    def test_active_floor(self) -> None:
        new = compute_new_importance(0.01, "active", SETTINGS)
        assert new == 0.05


class TestNC11RoundFourDecimals:
    def test_boundary_rounding(self) -> None:
        new = compute_new_importance(0.712345678, "active", SETTINGS)
        assert new == 0.7123


class TestNC12MissingEvidence:
    def test_skip_outcome(self) -> None:
        outcome = compute_consolidation_importance(
            make_input(independent_archive_count=0),
            SETTINGS,
        )
        assert isinstance(outcome, ConsolidationImportanceSkip)
        assert outcome.reason == "missing_evidence"

    def test_components_not_computed_for_zero_count(self) -> None:
        with pytest.raises(ValueError, match="> 0"):
            compute_consolidation_importance_components(
                make_input(independent_archive_count=0),
                SETTINGS,
            )


class TestNC13DeterministicReplay:
    def test_same_input_same_outcome(self) -> None:
        inp = make_input()
        first = compute_consolidation_importance(inp, SETTINGS)
        second = compute_consolidation_importance(inp, SETTINGS)
        assert first == second


class TestNC14NoImportanceInContract:
    def test_input_fields_exclude_forbidden(self) -> None:
        from dataclasses import fields

        field_names = {f.name for f in fields(ConsolidationImportanceInput)}
        forbidden = {"importance", "retrieval_count", "last_retrieved_time", "user_id"}
        assert forbidden.isdisjoint(field_names)


class TestU2Monotonicity:
    MEMORY_TYPES = ("profile", "fact", "preference", "event")

    def test_longer_inactive_never_increases_importance(self) -> None:
        base_eval = 2_000_000_000
        for memory_type in self.MEMORY_TYPES:
            prev = None
            for inactive_days in (0, 30, 90, 180, 365, 730):
                created = base_eval - int(inactive_days * 86400)
                inp = make_input(
                    memory_type=memory_type,
                    created_time=created,
                    evaluation_time=base_eval,
                    independent_archive_count=3,
                    confidence=0.8,
                )
                outcome = compute_consolidation_importance(inp, SETTINGS)
                assert isinstance(outcome, ConsolidationImportanceSuccess)
                if prev is not None:
                    assert outcome.new_importance <= prev
                prev = outcome.new_importance


class TestU3SupersededVsActive:
    def test_superseded_le_active_for_long_inactive(self) -> None:
        base_eval = 3_000_000_000
        inactive_days = 120
        created = base_eval - inactive_days * 86400
        common = {
            "memory_type": "event",
            "created_time": created,
            "evaluation_time": base_eval,
            "independent_archive_count": 3,
            "confidence": 0.8,
        }
        active_outcome = compute_consolidation_importance(
            make_input(status="active", **common),
            SETTINGS,
        )
        superseded_outcome = compute_consolidation_importance(
            make_input(status="superseded", **common),
            SETTINGS,
        )
        assert isinstance(active_outcome, ConsolidationImportanceSuccess)
        assert isinstance(superseded_outcome, ConsolidationImportanceSuccess)
        assert superseded_outcome.new_importance <= active_outcome.new_importance


class TestU4IllegalMemoryType:
    def test_invalid_memory_type(self) -> None:
        inp = make_input(memory_type="invalid")
        with pytest.raises(ValueError, match="memory_type"):
            compute_consolidation_importance(inp, SETTINGS)


class TestU5IllegalStatus:
    def test_invalid_status(self) -> None:
        inp = make_input(status="deleted")
        with pytest.raises(ValueError, match="status"):
            compute_consolidation_importance(inp, SETTINGS)


class TestU6NegativeTimestamps:
    def test_negative_created_time(self) -> None:
        inp = make_input(created_time=-1)
        with pytest.raises(ValueError, match="created_time"):
            compute_consolidation_importance(inp, SETTINGS)

    def test_negative_evaluation_time(self) -> None:
        inp = make_input(evaluation_time=-1)
        with pytest.raises(ValueError, match="evaluation_time"):
            compute_consolidation_importance(inp, SETTINGS)


class TestU7InjectableEvaluationTime:
    def test_different_evaluation_times_change_outcome(self) -> None:
        inp_early = make_input(
            created_time=1_000_000,
            evaluation_time=1_000_000 + 86400,
        )
        inp_late = make_input(
            created_time=1_000_000,
            evaluation_time=1_000_000 + 86400 * 180,
        )
        early = compute_consolidation_importance(inp_early, SETTINGS)
        late = compute_consolidation_importance(inp_late, SETTINGS)
        assert isinstance(early, ConsolidationImportanceSuccess)
        assert isinstance(late, ConsolidationImportanceSuccess)
        assert late.new_importance < early.new_importance


class TestU8UserIsolation:
    def test_two_independent_inputs_same_outcome(self) -> None:
        inp_a = make_input(memory_type="fact", confidence=0.9)
        inp_b = make_input(memory_type="fact", confidence=0.9)
        outcome_a = compute_consolidation_importance(inp_a, SETTINGS)
        outcome_b = compute_consolidation_importance(inp_b, SETTINGS)
        assert outcome_a == outcome_b


class TestU9HalfLifeZeroDefensive:
    def test_recency_zero_when_half_life_non_positive(self) -> None:
        assert compute_recency_score(10.0, 0) == 0.0
        assert compute_recency_score(10.0, -5) == 0.0


class TestF1MissingEvidenceEdge:
    def test_zero_count_skip(self) -> None:
        outcome = compute_consolidation_importance(
            make_input(independent_archive_count=0),
            SETTINGS,
        )
        assert isinstance(outcome, ConsolidationImportanceSkip)
        assert outcome.reason == "missing_evidence"


class TestF2ConcurrentCalls:
    def test_hundred_concurrent_identical_calls(self) -> None:
        inp = make_input()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(compute_consolidation_importance, inp, SETTINGS)
                for _ in range(100)
            ]
            results = [f.result() for f in futures]
        first = results[0]
        assert all(r == first for r in results)


class TestF3ExtremeInactiveDays:
    def test_recency_near_zero_but_min_floor(self) -> None:
        inp = make_input(
            created_time=0,
            evaluation_time=10_000_000_000,
            independent_archive_count=1,
            confidence=0.0,
        )
        components = compute_consolidation_importance_components(inp, SETTINGS)
        assert components.recency_score < 0.01
        outcome = compute_consolidation_importance(inp, SETTINGS)
        assert isinstance(outcome, ConsolidationImportanceSuccess)
        assert outcome.new_importance >= SETTINGS.min_importance


class TestSF2NegativeArchiveCount:
    def test_negative_count_raises(self) -> None:
        inp = make_input(independent_archive_count=-1)
        with pytest.raises(ValueError, match="independent_archive_count"):
            compute_consolidation_importance(inp, SETTINGS)


class TestU1AggregateNC:
    """U1 — NC-1..NC-14 covered by dedicated NC test classes above."""

    def test_nc_coverage_marker(self) -> None:
        assert SETTINGS.evidence_saturation_count == 5
