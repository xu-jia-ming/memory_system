"""EXT-005 reconciliation plan builder (§2.1.11 aggregation / §2.1.12 / §2.1.13)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from memory_system.domain.models.memory_recall import MemoryNodeSnapshot
from memory_system.domain.models.reconciliation import (
    PerCandidateDecision,
    PlannedExistingMemoryUpdate,
    PlannedMemoryCreate,
    ReasonCode,
    ReconciliationAction,
    ReconciliationErrorCode,
    ReconciliationFailure,
    ReconciliationOutcome,
    ReconciliationOutcomeKind,
    ReconciliationSuccess,
)
from memory_system.domain.services.aligned_memory_key import (
    compute_aligned_memory_key,
    normalize_memory_content_for_aggregation,
)

IMPORTANCE_BY_TYPE: dict[str, float] = {
    "profile": 0.75,
    "fact": 0.70,
    "preference": 0.65,
    "event": 0.55,
}

MemoryIdFactory = Callable[[], str]


@dataclass(frozen=True, slots=True)
class CandidatePlanInput:
    candidate_index: int
    candidate_fingerprint: str
    evidence_id: str
    action: ReconciliationAction
    target_memory_id: str | None
    reason_code: ReasonCode | None
    skip_reason: Literal["evidence_already_processed"] | None
    merged_content: str | None
    recalled_memory_count: int
    aligned_memory_key: str | None
    memory_type: str
    content: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None
    object_value: str | None
    event_status: str | None
    start_time: str | None
    end_time: str | None
    original_time_text: str | None
    confidence: float
    candidate_source_time: int
    recalled_memories: list[MemoryNodeSnapshot]


def _round_confidence(value: float) -> float:
    return round(value, 4)


def _merge_confidence(old_confidence: float, new_confidence: float) -> float:
    return _round_confidence(
        min(1.0, old_confidence + (1.0 - old_confidence) * new_confidence * 0.25)
    )


def _importance_for_type(memory_type: str) -> float:
    return IMPORTANCE_BY_TYPE[memory_type]


def _select_create_content(candidates: list[CandidatePlanInput]) -> str:
    normalized = [normalize_memory_content_for_aggregation(item.content) for item in candidates]
    if len(set(normalized)) == 1:
        return normalized[0]
    winner = sorted(
        candidates,
        key=lambda item: (
            -item.confidence,
            -item.candidate_source_time,
            item.candidate_fingerprint,
        ),
    )[0]
    return winner.content


def _select_structural_representative(candidates: list[CandidatePlanInput]) -> CandidatePlanInput:
    return sorted(
        candidates,
        key=lambda item: (
            -item.confidence,
            -item.candidate_source_time,
            item.candidate_fingerprint,
        ),
    )[0]


def _resolve_merge_merged_content(
    candidates: list[CandidatePlanInput],
) -> str | None | ReconciliationFailure:
    normalized_values: list[str | None] = [
        normalize_memory_content_for_aggregation(item.merged_content)
        if item.merged_content is not None
        else None
        for item in candidates
    ]
    non_null = [value for value in normalized_values if value is not None]
    if not non_null:
        return None
    distinct = set(non_null)
    if len(distinct) == 1:
        return non_null[0]
    return ReconciliationFailure(error_code=ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT)


def _participates_in_aggregation(candidate: CandidatePlanInput) -> bool:
    if candidate.skip_reason == "evidence_already_processed":
        return False
    if candidate.action == ReconciliationAction.SKIP:
        return False
    return candidate.action in {
        ReconciliationAction.MERGE,
        ReconciliationAction.SUPERSEDE,
        ReconciliationAction.CONFLICT,
        ReconciliationAction.CREATE,
    }


def build_reconciliation_plan(
    *,
    user_id: str,
    archive_id: str,
    candidates: list[CandidatePlanInput],
    memory_id_factory: MemoryIdFactory,
) -> ReconciliationOutcome:
    per_candidate_decisions = [
        PerCandidateDecision(
            candidate_index=item.candidate_index,
            candidate_fingerprint=item.candidate_fingerprint,
            evidence_id=item.evidence_id,
            action=item.action,
            target_memory_id=item.target_memory_id,
            reason_code=item.reason_code,
            skip_reason=item.skip_reason,
            merged_content=item.merged_content,
            recalled_memory_count=item.recalled_memory_count,
            aligned_memory_key=item.aligned_memory_key,
        )
        for item in candidates
    ]

    aggregating = [item for item in candidates if _participates_in_aggregation(item)]

    existing_groups: dict[str, list[CandidatePlanInput]] = defaultdict(list)
    create_groups: dict[str, list[CandidatePlanInput]] = defaultdict(list)

    for item in aggregating:
        if item.action == ReconciliationAction.CREATE:
            if item.aligned_memory_key is None:
                return ReconciliationOutcome(
                    outcome=ReconciliationOutcomeKind.FAILURE,
                    failure=ReconciliationFailure(
                        error_code=ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT
                    ),
                )
            create_groups[item.aligned_memory_key].append(item)
            continue
        if item.target_memory_id is None:
            return ReconciliationOutcome(
                outcome=ReconciliationOutcomeKind.FAILURE,
                failure=ReconciliationFailure(
                    error_code=ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT
                ),
            )
        existing_groups[item.target_memory_id].append(item)

    existing_memory_update_plans: list[PlannedExistingMemoryUpdate] = []
    new_memory_create_plans: list[PlannedMemoryCreate] = []

    for target_memory_id, group in existing_groups.items():
        actions = {item.action for item in group}
        if len(actions) != 1:
            return ReconciliationOutcome(
                outcome=ReconciliationOutcomeKind.FAILURE,
                failure=ReconciliationFailure(
                    error_code=ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT
                ),
            )
        action = next(iter(actions))
        if (
            action in {ReconciliationAction.SUPERSEDE, ReconciliationAction.CONFLICT}
            and len(group) > 1
        ):
            return ReconciliationOutcome(
                outcome=ReconciliationOutcomeKind.FAILURE,
                failure=ReconciliationFailure(
                    error_code=ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT
                ),
            )

        target_memory = next(
            (
                memory
                for item in group
                for memory in item.recalled_memories
                if memory.memory_id == target_memory_id
            ),
            None,
        )
        if target_memory is None:
            return ReconciliationOutcome(
                outcome=ReconciliationOutcomeKind.FAILURE,
                failure=ReconciliationFailure(
                    error_code=ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT
                ),
            )

        max_candidate_confidence = _round_confidence(max(item.confidence for item in group))
        planned_latest_source_time = max(item.candidate_source_time for item in group)
        planned_merged_content: str | None = None
        planned_merged_confidence: float | None = None

        if action == ReconciliationAction.MERGE:
            merge_content_result = _resolve_merge_merged_content(group)
            if isinstance(merge_content_result, ReconciliationFailure):
                return ReconciliationOutcome(
                    outcome=ReconciliationOutcomeKind.FAILURE,
                    failure=merge_content_result,
                )
            planned_merged_content = merge_content_result
            planned_merged_confidence = _merge_confidence(
                target_memory.confidence,
                max_candidate_confidence,
            )

        planned_new_memory_id: str | None = None
        if action in {ReconciliationAction.SUPERSEDE, ReconciliationAction.CONFLICT}:
            representative = group[0]
            planned_new_memory_id = memory_id_factory()
            create_kind: Literal["supersede_new", "conflict_new"] = (
                "supersede_new" if action == ReconciliationAction.SUPERSEDE else "conflict_new"
            )
            new_memory_create_plans.append(
                PlannedMemoryCreate(
                    create_kind=create_kind,
                    planned_memory_id=planned_new_memory_id,
                    aligned_memory_key=None,
                    supersedes_target_memory_id=(
                        target_memory_id if create_kind == "supersede_new" else None
                    ),
                    conflicts_with_target_memory_id=(
                        target_memory_id if create_kind == "conflict_new" else None
                    ),
                    memory_type=representative.memory_type,
                    planned_content=representative.content,
                    subject_entity_id=representative.subject_entity_id,
                    predicate=representative.predicate,
                    object_entity_id=representative.object_entity_id,
                    object_value=representative.object_value,
                    event_status=representative.event_status,
                    start_time=representative.start_time,
                    end_time=representative.end_time,
                    original_time_text=representative.original_time_text,
                    planned_confidence=_round_confidence(representative.confidence),
                    planned_importance=_importance_for_type(representative.memory_type),
                    planned_latest_source_time=representative.candidate_source_time,
                    contributing_candidate_indices=[item.candidate_index for item in group],
                    contributing_evidence_ids=[item.evidence_id for item in group],
                )
            )

        existing_memory_update_plans.append(
            PlannedExistingMemoryUpdate(
                target_memory_id=target_memory_id,
                aggregated_action=action,  # type: ignore[arg-type]
                contributing_candidate_indices=[item.candidate_index for item in group],
                contributing_evidence_ids=[item.evidence_id for item in group],
                planned_merged_content=planned_merged_content,
                planned_merged_confidence=planned_merged_confidence,
                planned_latest_source_time=planned_latest_source_time,
                increment_memory_version=True,
                planned_new_memory_id=planned_new_memory_id,
            )
        )

    for aligned_key, group in create_groups.items():
        representative = _select_structural_representative(group)
        planned_memory_id = memory_id_factory()
        new_memory_create_plans.append(
            PlannedMemoryCreate(
                create_kind="create",
                planned_memory_id=planned_memory_id,
                aligned_memory_key=aligned_key,
                supersedes_target_memory_id=None,
                conflicts_with_target_memory_id=None,
                memory_type=representative.memory_type,
                planned_content=_select_create_content(group),
                subject_entity_id=representative.subject_entity_id,
                predicate=representative.predicate,
                object_entity_id=representative.object_entity_id,
                object_value=representative.object_value,
                event_status=representative.event_status,
                start_time=representative.start_time,
                end_time=representative.end_time,
                original_time_text=representative.original_time_text,
                planned_confidence=_round_confidence(max(item.confidence for item in group)),
                planned_importance=_importance_for_type(representative.memory_type),
                planned_latest_source_time=max(item.candidate_source_time for item in group),
                contributing_candidate_indices=[item.candidate_index for item in group],
                contributing_evidence_ids=[item.evidence_id for item in group],
            )
        )

    return ReconciliationOutcome(
        outcome=ReconciliationOutcomeKind.SUCCESS,
        success=ReconciliationSuccess(
            user_id=user_id,
            archive_id=archive_id,
            per_candidate_decisions=per_candidate_decisions,
            existing_memory_update_plans=existing_memory_update_plans,
            new_memory_create_plans=new_memory_create_plans,
        ),
        failure=None,
    )


def compute_create_aligned_memory_key(candidate: CandidatePlanInput) -> str:
    return compute_aligned_memory_key(
        memory_type=candidate.memory_type,
        final_subject_entity_id=candidate.subject_entity_id,
        predicate=candidate.predicate,
        final_object_entity_id=candidate.object_entity_id,
        object_value=candidate.object_value,
        event_status=candidate.event_status,
        start_time=candidate.start_time,
        end_time=candidate.end_time,
    )
