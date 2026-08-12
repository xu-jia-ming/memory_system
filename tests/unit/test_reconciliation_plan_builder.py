"""Unit tests for reconciliation plan builder (EXT-005)."""

from __future__ import annotations

import pytest

from memory_system.domain.models.memory_recall import MemoryNodeSnapshot
from memory_system.domain.models.reconciliation import (
    ReasonCode,
    ReconciliationAction,
    ReconciliationErrorCode,
    ReconciliationOutcomeKind,
)
from memory_system.domain.services.reconciliation_plan_builder import (
    CandidatePlanInput,
    build_reconciliation_plan,
    compute_create_aligned_memory_key,
)


def _memory(
    memory_id: str = "mem-1",
    *,
    confidence: float = 0.8,
    content: str = "existing content",
) -> MemoryNodeSnapshot:
    return MemoryNodeSnapshot(
        memory_id=memory_id,
        user_id="user-1",
        memory_type="fact",
        content=content,
        subject_entity_id="user:user-1",
        predicate="likes",
        object_entity_id=None,
        object_value="tea",
        status="active",
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        confidence=confidence,
        latest_source_time=100,
    )


def _candidate(
    *,
    candidate_index: int = 0,
    action: ReconciliationAction = ReconciliationAction.MERGE,
    target_memory_id: str | None = "mem-1",
    merged_content: str | None = None,
    evidence_id: str = "ev-1",
    confidence: float = 0.9,
    candidate_source_time: int = 200,
    content: str = "candidate content",
    object_value: str | None = "tea",
    skip_reason: str | None = None,
    reason_code: ReasonCode | None = ReasonCode.SAME_SEMANTIC_MEMORY,
    aligned_memory_key: str | None = None,
    recalled: list[MemoryNodeSnapshot] | None = None,
) -> CandidatePlanInput:
    recalled_memories = recalled if recalled is not None else [_memory()]
    if action == ReconciliationAction.CREATE and aligned_memory_key is None:
        item = CandidatePlanInput(
            candidate_index=candidate_index,
            candidate_fingerprint=f"fp-{candidate_index}",
            evidence_id=evidence_id,
            action=action,
            target_memory_id=target_memory_id,
            reason_code=reason_code or ReasonCode.NEW_MEMORY,
            skip_reason=skip_reason,  # type: ignore[arg-type]
            merged_content=merged_content,
            recalled_memory_count=len(recalled_memories),
            aligned_memory_key=None,
            memory_type="fact",
            content=content,
            subject_entity_id="user:user-1",
            predicate="likes",
            object_entity_id=None,
            object_value=object_value,
            event_status=None,
            start_time=None,
            end_time=None,
            original_time_text=None,
            confidence=confidence,
            candidate_source_time=candidate_source_time,
            recalled_memories=recalled_memories,
        )
        aligned_memory_key = compute_create_aligned_memory_key(item)
    return CandidatePlanInput(
        candidate_index=candidate_index,
        candidate_fingerprint=f"fp-{candidate_index}",
        evidence_id=evidence_id,
        action=action,
        target_memory_id=target_memory_id,
        reason_code=reason_code,
        skip_reason=skip_reason,  # type: ignore[arg-type]
        merged_content=merged_content,
        recalled_memory_count=len(recalled_memories),
        aligned_memory_key=aligned_memory_key,
        memory_type="fact",
        content=content,
        subject_entity_id="user:user-1",
        predicate="likes",
        object_entity_id=None,
        object_value=object_value,
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        confidence=confidence,
        candidate_source_time=candidate_source_time,
        recalled_memories=recalled_memories,
    )


def _build(
    candidates: list[CandidatePlanInput],
    *,
    memory_ids: list[str] | None = None,
):
    ids = iter(memory_ids or ["new-1", "new-2", "new-3", "new-4"])
    return build_reconciliation_plan(
        user_id="user-1",
        archive_id="archive-1",
        candidates=candidates,
        memory_id_factory=lambda: next(ids),
    )


def test_p1_merge_group_multiple_candidates() -> None:
    outcome = _build(
        [
            _candidate(candidate_index=0, evidence_id="ev-0"),
            _candidate(candidate_index=1, evidence_id="ev-1", confidence=0.95),
        ]
    )
    assert outcome.outcome == ReconciliationOutcomeKind.SUCCESS
    assert outcome.success is not None
    assert len(outcome.success.existing_memory_update_plans) == 1
    plan = outcome.success.existing_memory_update_plans[0]
    assert plan.aggregated_action == "MERGE"
    assert plan.contributing_evidence_ids == ["ev-0", "ev-1"]


def test_p2_merge_conflicting_merged_content() -> None:
    outcome = _build(
        [
            _candidate(candidate_index=0, merged_content="alpha detail"),
            _candidate(candidate_index=1, merged_content="beta detail"),
        ]
    )
    assert outcome.outcome == ReconciliationOutcomeKind.FAILURE
    assert outcome.failure is not None
    assert outcome.failure.error_code == ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT


def test_p2b_merge_mixed_null_and_single_non_null() -> None:
    outcome = _build(
        [
            _candidate(candidate_index=0, merged_content=None),
            _candidate(candidate_index=1, merged_content="same detail"),
        ]
    )
    assert outcome.success is not None
    assert outcome.success.existing_memory_update_plans[0].planned_merged_content == "same detail"


def test_p2c_merge_all_null_merged_content() -> None:
    outcome = _build([_candidate(candidate_index=0, merged_content=None)])
    assert outcome.success is not None
    assert outcome.success.existing_memory_update_plans[0].planned_merged_content is None


def test_p3_same_target_different_actions_conflict() -> None:
    outcome = _build(
        [
            _candidate(candidate_index=0, action=ReconciliationAction.MERGE),
            _candidate(candidate_index=1, action=ReconciliationAction.SUPERSEDE),
        ]
    )
    assert outcome.failure is not None
    assert outcome.failure.error_code == ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT


def test_p4_multiple_supersede_same_target_conflict() -> None:
    outcome = _build(
        [
            _candidate(candidate_index=0, action=ReconciliationAction.SUPERSEDE),
            _candidate(candidate_index=1, action=ReconciliationAction.SUPERSEDE),
        ],
        memory_ids=["new-a", "new-b"],
    )
    assert outcome.failure is not None


def test_p5_create_same_aligned_key_single_plan() -> None:
    outcome = _build(
        [
            _candidate(
                candidate_index=0,
                action=ReconciliationAction.CREATE,
                target_memory_id=None,
            ),
            _candidate(
                candidate_index=1,
                action=ReconciliationAction.CREATE,
                target_memory_id=None,
            ),
        ],
        memory_ids=["create-1"],
    )
    assert outcome.success is not None
    assert len(outcome.success.new_memory_create_plans) == 1
    plan = outcome.success.new_memory_create_plans[0]
    assert plan.create_kind == "create"
    assert plan.planned_memory_id == "create-1"
    assert len(plan.contributing_evidence_ids) == 2


def test_p6_create_different_keys_multiple_plans() -> None:
    first = _candidate(
        candidate_index=0,
        action=ReconciliationAction.CREATE,
        target_memory_id=None,
        object_value="tea",
    )
    second = _candidate(
        candidate_index=1,
        action=ReconciliationAction.CREATE,
        target_memory_id=None,
        object_value="coffee",
    )
    outcome = _build([first, second], memory_ids=["create-a", "create-b"])
    assert outcome.success is not None
    assert len(outcome.success.new_memory_create_plans) == 2


def test_p7_confidence_and_importance() -> None:
    outcome = _build([_candidate(confidence=0.91234)])
    assert outcome.success is not None
    merge_plan = outcome.success.existing_memory_update_plans[0]
    assert merge_plan.planned_merged_confidence == pytest.approx(0.8456)
    create_outcome = _build(
        [_candidate(action=ReconciliationAction.CREATE, target_memory_id=None, confidence=0.91234)],
        memory_ids=["create-1"],
    )
    create_plan = create_outcome.success.new_memory_create_plans[0]  # type: ignore[union-attr]
    assert create_plan.planned_confidence == 0.9123
    assert create_plan.planned_importance == 0.70


def test_p8_increment_memory_version_for_merge() -> None:
    outcome = _build([_candidate()])
    assert outcome.success is not None
    assert outcome.success.existing_memory_update_plans[0].increment_memory_version is True


def test_p8_skip_does_not_increment() -> None:
    outcome = _build(
        [
            _candidate(
                action=ReconciliationAction.SKIP,
                target_memory_id=None,
                skip_reason="evidence_already_processed",
                reason_code=None,
            )
        ]
    )
    assert outcome.success is not None
    assert outcome.success.existing_memory_update_plans == []


def test_p9_supersede_and_conflict_create_rows() -> None:
    supersede = _build(
        [_candidate(action=ReconciliationAction.SUPERSEDE)],
        memory_ids=["sup-new"],
    )
    assert supersede.success is not None
    assert supersede.success.new_memory_create_plans[0].create_kind == "supersede_new"
    assert (
        supersede.success.existing_memory_update_plans[0].planned_new_memory_id
        == "sup-new"
    )

    conflict = _build(
        [_candidate(action=ReconciliationAction.CONFLICT)],
        memory_ids=["conf-new"],
    )
    assert conflict.success is not None
    assert conflict.success.new_memory_create_plans[0].create_kind == "conflict_new"


def test_p10_llm_skip_excluded_from_aggregation() -> None:
    outcome = _build(
        [
            _candidate(
                action=ReconciliationAction.SKIP,
                target_memory_id=None,
                reason_code=ReasonCode.INVALID_CANDIDATE,
            )
        ]
    )
    assert outcome.success is not None
    assert outcome.success.existing_memory_update_plans == []
    assert outcome.success.new_memory_create_plans == []


def test_p11_new_memory_create_plans_contains_all_kinds() -> None:
    outcome = _build(
        [
            _candidate(action=ReconciliationAction.CREATE, target_memory_id=None),
            _candidate(
                candidate_index=1,
                action=ReconciliationAction.SUPERSEDE,
                target_memory_id="mem-1",
            ),
            _candidate(
                candidate_index=2,
                action=ReconciliationAction.CONFLICT,
                target_memory_id="mem-2",
                recalled=[_memory(memory_id="mem-2")],
            ),
        ],
        memory_ids=["create-1", "sup-1", "conf-1"],
    )
    assert outcome.success is not None
    kinds = {plan.create_kind for plan in outcome.success.new_memory_create_plans}
    assert kinds == {"create", "supersede_new", "conflict_new"}


def test_p12_create_kind_link_fields() -> None:
    outcome = _build(
        [_candidate(action=ReconciliationAction.SUPERSEDE)],
        memory_ids=["sup-1"],
    )
    assert outcome.success is not None
    create_plan = outcome.success.new_memory_create_plans[0]
    update_plan = outcome.success.existing_memory_update_plans[0]
    assert create_plan.supersedes_target_memory_id == "mem-1"
    assert create_plan.conflicts_with_target_memory_id is None
    assert update_plan.aggregated_action == "SUPERSEDE"
    assert update_plan.planned_new_memory_id == create_plan.planned_memory_id
