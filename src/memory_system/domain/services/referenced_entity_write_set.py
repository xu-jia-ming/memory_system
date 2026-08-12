"""EXT-006 referenced entity write set (§2.1.13 step 8)."""

from __future__ import annotations

from memory_system.domain.models.entity_alignment import AlignedEntity, EntityAlignmentSuccess
from memory_system.domain.models.extraction_llm import ExtractionValidatedResult
from memory_system.domain.models.graph_write import ReferencedEntityWritePlan
from memory_system.domain.models.reconciliation import ReconciliationAction, ReconciliationSuccess


def collect_referenced_entity_ids(
    reconciliation: ReconciliationSuccess,
    extraction_result: ExtractionValidatedResult,
    local_entity_id_map: dict[str, str],
) -> set[str]:
    """Collect aligned entity_ids referenced by non-SKIP reconciliation plans."""
    referenced: set[str] = set()
    for plan in reconciliation.new_memory_create_plans:
        referenced.add(plan.subject_entity_id)
        if plan.object_entity_id is not None:
            referenced.add(plan.object_entity_id)

    for decision in reconciliation.per_candidate_decisions:
        if decision.action == ReconciliationAction.SKIP:
            continue
        memory = extraction_result.memories[decision.candidate_index]
        subject_entity_id = local_entity_id_map.get(memory.subject_entity_id)
        if subject_entity_id is not None:
            referenced.add(subject_entity_id)
        if memory.object_entity_id is not None:
            object_entity_id = local_entity_id_map.get(memory.object_entity_id)
            if object_entity_id is not None:
                referenced.add(object_entity_id)
    return referenced


def build_referenced_entity_write_set(
    reconciliation: ReconciliationSuccess,
    entity_alignment: EntityAlignmentSuccess,
    extraction_result: ExtractionValidatedResult,
) -> list[ReferencedEntityWritePlan]:
    """Filter alignment rows to entities referenced by non-SKIP reconciliation plans."""
    local_entity_id_map = entity_alignment.local_entity_id_map()
    referenced_ids = collect_referenced_entity_ids(
        reconciliation,
        extraction_result,
        local_entity_id_map,
    )
    entity_by_id: dict[str, AlignedEntity] = {
        alignment.entity_id: alignment for alignment in entity_alignment.alignments
    }

    plans: list[ReferencedEntityWritePlan] = []
    for entity_id in sorted(referenced_ids):
        alignment = entity_by_id.get(entity_id)
        if alignment is None:
            continue
        plans.append(
            ReferencedEntityWritePlan(
                entity_key=alignment.entity_key,
                entity_id=alignment.entity_id,
                user_id=entity_alignment.user_id,
                entity_type=alignment.entity_type,
                canonical_name=alignment.canonical_name,
                normalized_name=alignment.normalized_name,
                aliases=list(alignment.planned_alias_merge.planned_aliases),
                planned_create=alignment.planned_create,
            )
        )
    return plans
