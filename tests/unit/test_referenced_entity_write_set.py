"""Unit tests for referenced_entity_write_set (EXT-006)."""

from __future__ import annotations

from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.extraction_llm import (
    ExtractionEntityCandidate,
    ExtractionMemoryCandidate,
    ExtractionValidatedResult,
)
from memory_system.domain.models.reconciliation import (
    PerCandidateDecision,
    PlannedMemoryCreate,
    ReasonCode,
    ReconciliationAction,
    ReconciliationSuccess,
)
from memory_system.domain.services.referenced_entity_write_set import (
    build_referenced_entity_write_set,
    collect_referenced_entity_ids,
)


def _alignment(user_id: str = "user-1") -> EntityAlignmentSuccess:
    return EntityAlignmentSuccess(
        user_id=user_id,
        alignments=[
            AlignedEntity(
                local_entity_id="user",
                entity_id=f"user:{user_id}",
                match_kind=EntityMatchKind.RESERVED_USER_EXISTING,
                entity_type="person",
                canonical_name="current_user",
                normalized_name="current_user",
                entity_key="user-key",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=[],
                    planned_aliases=[],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=False,
            ),
            AlignedEntity(
                local_entity_id="entity_1",
                entity_id="entity-uuid-1",
                match_kind=EntityMatchKind.PLANNED_CREATE,
                entity_type="project",
                canonical_name="Agent Memory System",
                normalized_name="agent memory system",
                entity_key="entity-key-1",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=[],
                    planned_aliases=[],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=True,
            ),
            AlignedEntity(
                local_entity_id="entity_2",
                entity_id="entity-uuid-2",
                match_kind=EntityMatchKind.PLANNED_CREATE,
                entity_type="concept",
                canonical_name="Unused Entity",
                normalized_name="unused entity",
                entity_key="entity-key-2",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=[],
                    planned_aliases=[],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=True,
            ),
        ],
    )


def _extraction() -> ExtractionValidatedResult:
    return ExtractionValidatedResult(
        entities=[
            ExtractionEntityCandidate(
                local_entity_id="entity_1",
                name="Agent Memory System",
                type="project",
                aliases=[],
            ),
            ExtractionEntityCandidate(
                local_entity_id="entity_2",
                name="Unused Entity",
                type="concept",
                aliases=[],
            ),
        ],
        memories=[
            ExtractionMemoryCandidate(
                memory_type="event",
                content="content",
                subject_entity_id="user",
                predicate="works_on",
                object_entity_id="entity_1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                confidence=0.9,
                source_message_ids=["msg-1"],
                candidate_source_time=100,
                candidate_fingerprint="fp-1",
            ),
            ExtractionMemoryCandidate(
                memory_type="fact",
                content="other",
                subject_entity_id="user",
                predicate="likes",
                object_entity_id=None,
                object_value="tea",
                event_status=None,
                start_time=None,
                end_time=None,
                original_time_text=None,
                confidence=0.8,
                source_message_ids=["msg-2"],
                candidate_source_time=101,
                candidate_fingerprint="fp-2",
            ),
        ],
    )


def _reconciliation_with_create() -> ReconciliationSuccess:
    return ReconciliationSuccess(
        user_id="user-1",
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-1",
                evidence_id="ev-1",
                action=ReconciliationAction.CREATE,
                target_memory_id=None,
                reason_code=ReasonCode.NEW_MEMORY,
                skip_reason=None,
                merged_content=None,
                recalled_memory_count=0,
                aligned_memory_key="key-1",
            ),
            PerCandidateDecision(
                candidate_index=1,
                candidate_fingerprint="fp-2",
                evidence_id="ev-2",
                action=ReconciliationAction.SKIP,
                target_memory_id=None,
                reason_code=None,
                skip_reason="evidence_already_processed",
                merged_content=None,
                recalled_memory_count=0,
                aligned_memory_key=None,
            ),
        ],
        existing_memory_update_plans=[],
        new_memory_create_plans=[
            PlannedMemoryCreate(
                create_kind="create",
                planned_memory_id="mem-new-1",
                aligned_memory_key="key-1",
                supersedes_target_memory_id=None,
                conflicts_with_target_memory_id=None,
                memory_type="event",
                planned_content="content",
                subject_entity_id="user:user-1",
                predicate="works_on",
                object_entity_id="entity-uuid-1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                planned_confidence=0.9,
                planned_importance=0.55,
                planned_latest_source_time=100,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
            ),
        ],
    )


def test_e1_only_referenced_entities_in_write_set() -> None:
    alignment = _alignment()
    extraction = _extraction()
    reconciliation = _reconciliation_with_create()
    write_set = build_referenced_entity_write_set(reconciliation, alignment, extraction)
    entity_ids = {item.entity_id for item in write_set}
    assert entity_ids == {"user:user-1", "entity-uuid-1"}
    assert "entity-uuid-2" not in entity_ids


def test_e2_user_entity_reference_preserved() -> None:
    alignment = _alignment()
    extraction = _extraction()
    reconciliation = _reconciliation_with_create()
    referenced = collect_referenced_entity_ids(
        reconciliation,
        extraction,
        alignment.local_entity_id_map(),
    )
    assert "user:user-1" in referenced


def test_e3_null_object_entity_not_referenced() -> None:
    alignment = _alignment()
    base_extraction = _extraction()
    extraction = ExtractionValidatedResult(
        entities=base_extraction.entities,
        memories=[
            ExtractionMemoryCandidate(
                memory_type="fact",
                content="likes tea",
                subject_entity_id="user",
                predicate="likes",
                object_entity_id=None,
                object_value="tea",
                event_status=None,
                start_time=None,
                end_time=None,
                original_time_text=None,
                confidence=0.8,
                source_message_ids=["msg-2"],
                candidate_source_time=101,
                candidate_fingerprint="fp-2",
            ),
        ],
    )
    reconciliation = ReconciliationSuccess(
        user_id="user-1",
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-2",
                evidence_id="ev-2",
                action=ReconciliationAction.CREATE,
                target_memory_id=None,
                reason_code=ReasonCode.NEW_MEMORY,
                skip_reason=None,
                merged_content=None,
                recalled_memory_count=0,
                aligned_memory_key="key-2",
            ),
        ],
        existing_memory_update_plans=[],
        new_memory_create_plans=[
            PlannedMemoryCreate(
                create_kind="create",
                planned_memory_id="mem-new-2",
                aligned_memory_key="key-2",
                supersedes_target_memory_id=None,
                conflicts_with_target_memory_id=None,
                memory_type="fact",
                planned_content="likes tea",
                subject_entity_id="user:user-1",
                predicate="likes",
                object_entity_id=None,
                object_value="tea",
                event_status=None,
                start_time=None,
                end_time=None,
                original_time_text=None,
                planned_confidence=0.8,
                planned_importance=0.7,
                planned_latest_source_time=101,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-2"],
            ),
        ],
    )
    write_set = build_referenced_entity_write_set(reconciliation, alignment, extraction)
    entity_ids = {item.entity_id for item in write_set}
    assert entity_ids == {"user:user-1"}
