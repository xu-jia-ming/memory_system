"""EXT-006 immutable graph write plan builder (§2.1.13 steps 8–10)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pymongo import AsyncMongoClient

from memory_system.domain.models.entity_alignment import AlignedEntity, EntityAlignmentSuccess
from memory_system.domain.models.extraction_llm import ExtractionValidatedResult
from memory_system.domain.models.graph_write import (
    EntityWriteRow,
    EvidenceWriteRow,
    GraphWriteFailure,
    GraphWriteInput,
    GraphWriteOutcome,
    GraphWriteOutcomeKind,
    ImmutableGraphWritePlan,
    IndexSyncMemoryEntry,
    MemoryCreateRow,
    MemoryUpdateRow,
    ReferencedEntityWritePlan,
)
from memory_system.domain.models.reconciliation import (
    PlannedExistingMemoryUpdate,
    PlannedMemoryCreate,
    ReconciliationSuccess,
)
from memory_system.domain.ports.tokenize_client import TokenizeClient
from memory_system.domain.services.core_search_text import build_core_search_text
from memory_system.domain.services.referenced_entity_write_set import (
    build_referenced_entity_write_set,
)
from memory_system.infrastructure.mongodb.context_archive_message_timestamp_repository import (
    ContextArchiveMessageTimestampRepository,
)

ServerTimeProvider = Callable[[], int]


@dataclass(frozen=True, slots=True)
class MemorySearchTextView:
    memory_id: str
    content: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None
    object_value: str | None


def _event_fields(
    memory_type: str,
    event_status: str | None,
    start_time: str | None,
    end_time: str | None,
    original_time_text: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    if memory_type != "event":
        return None, None, None, None
    return event_status, start_time, end_time, original_time_text


def _canonical_name_for_entity(
    entity_id: str,
    entity_by_id: dict[str, AlignedEntity],
) -> str:
    alignment = entity_by_id.get(entity_id)
    if alignment is None:
        return ""
    return alignment.canonical_name


def _memory_search_views(
    reconciliation: ReconciliationSuccess,
    extraction_result: ExtractionValidatedResult,
    entity_alignment: EntityAlignmentSuccess,
) -> dict[str, MemorySearchTextView]:
    views: dict[str, MemorySearchTextView] = {}

    for plan in reconciliation.new_memory_create_plans:
        views[plan.planned_memory_id] = MemorySearchTextView(
            memory_id=plan.planned_memory_id,
            content=plan.planned_content,
            subject_entity_id=plan.subject_entity_id,
            predicate=plan.predicate,
            object_entity_id=plan.object_entity_id,
            object_value=plan.object_value,
        )

    local_entity_id_map = entity_alignment.local_entity_id_map()

    for update_plan in reconciliation.existing_memory_update_plans:
        representative_index = update_plan.contributing_candidate_indices[0]
        candidate = extraction_result.memories[representative_index]
        content = update_plan.planned_merged_content or candidate.content
        subject_entity_id = local_entity_id_map.get(
            candidate.subject_entity_id,
            candidate.subject_entity_id,
        )
        object_entity_id: str | None = None
        if candidate.object_entity_id is not None:
            object_entity_id = local_entity_id_map.get(
                candidate.object_entity_id,
                candidate.object_entity_id,
            )
        views[update_plan.target_memory_id] = MemorySearchTextView(
            memory_id=update_plan.target_memory_id,
            content=content,
            subject_entity_id=subject_entity_id,
            predicate=candidate.predicate,
            object_entity_id=object_entity_id,
            object_value=candidate.object_value,
        )

    return views


def _index_sync_memory_ids(reconciliation: ReconciliationSuccess) -> list[str]:
    memory_ids: list[str] = []
    for create_plan in reconciliation.new_memory_create_plans:
        memory_ids.append(create_plan.planned_memory_id)
    for update_plan in reconciliation.existing_memory_update_plans:
        memory_ids.append(update_plan.target_memory_id)
    return memory_ids


async def build_graph_write_plan(
    graph_input: GraphWriteInput,
    *,
    mongodb: AsyncMongoClient[Any],
    tokenize_client: TokenizeClient,
    archive_timestamp_repository: ContextArchiveMessageTimestampRepository,
    prompt_version: str,
    max_search_text_tokens: int,
    server_time_provider: ServerTimeProvider,
) -> GraphWriteOutcome | ImmutableGraphWritePlan:
    reconciliation = graph_input.reconciliation
    entity_alignment = graph_input.entity_alignment
    extraction_result = graph_input.extraction_result
    user_id = graph_input.user_id
    archive_id = graph_input.archive_id

    referenced_entities = build_referenced_entity_write_set(
        reconciliation,
        entity_alignment,
        extraction_result,
    )
    entity_by_id = {item.entity_id: item for item in entity_alignment.alignments}
    local_entity_id_map = entity_alignment.local_entity_id_map()

    search_views = _memory_search_views(reconciliation, extraction_result, entity_alignment)
    index_entries: list[IndexSyncMemoryEntry] = []

    for memory_id in _index_sync_memory_ids(reconciliation):
        view = search_views.get(memory_id)
        if view is None:
            continue
        subject_entity_id = local_entity_id_map.get(view.subject_entity_id, view.subject_entity_id)
        object_entity_id: str | None = None
        if view.object_entity_id is not None:
            object_entity_id = local_entity_id_map.get(
                view.object_entity_id,
                view.object_entity_id,
            )
        core_search_text = build_core_search_text(
            user_id=user_id,
            content=view.content,
            subject_entity_id=subject_entity_id,
            subject_canonical_name=_canonical_name_for_entity(subject_entity_id, entity_by_id),
            predicate=view.predicate,
            object_entity_id=object_entity_id,
            object_canonical_name=(
                _canonical_name_for_entity(object_entity_id, entity_by_id)
                if object_entity_id is not None
                else None
            ),
            object_value=view.object_value,
        )
        try:
            token_count = await tokenize_client.count_tokens(core_search_text)
        except Exception:
            return GraphWriteOutcome(
                outcome=GraphWriteOutcomeKind.FAILURE,
                success=None,
                failure=GraphWriteFailure(error_code="graph_write_failed"),
            )
        if token_count > max_search_text_tokens:
            return GraphWriteOutcome(
                outcome=GraphWriteOutcomeKind.FAILURE,
                success=None,
                failure=GraphWriteFailure(error_code="memory_search_text_too_long"),
            )
        index_entries.append(
            IndexSyncMemoryEntry(
                memory_id=memory_id,
                core_search_text=core_search_text,
                token_count=token_count,
            )
        )

    server_now = server_time_provider()
    entity_rows = [
        EntityWriteRow(
            entity_key=item.entity_key,
            entity_id=item.entity_id,
            user_id=item.user_id,
            entity_type=item.entity_type,
            canonical_name=item.canonical_name,
            normalized_name=item.normalized_name,
            aliases=list(item.aliases),
            created_time=server_now,
            updated_time=server_now,
        )
        for item in referenced_entities
    ]

    memory_create_rows = [
        _memory_create_row(plan, user_id=user_id, server_now=server_now)
        for plan in reconciliation.new_memory_create_plans
    ]
    memory_update_rows = [
        _memory_update_row(plan, user_id=user_id, server_now=server_now)
        for plan in reconciliation.existing_memory_update_plans
    ]

    evidence_rows = await _build_evidence_rows(
        reconciliation=reconciliation,
        extraction_result=extraction_result,
        mongodb=mongodb,
        archive_timestamp_repository=archive_timestamp_repository,
        archive_id=archive_id,
        user_id=user_id,
        session_id=graph_input.session_id or "",
        prompt_version=prompt_version,
        server_now=server_now,
    )

    return ImmutableGraphWritePlan(
        user_id=user_id,
        archive_id=archive_id,
        entity_rows=entity_rows,
        memory_create_rows=memory_create_rows,
        memory_update_rows=memory_update_rows,
        evidence_rows=evidence_rows,
        index_sync_memory_set=index_entries,
    )


def _memory_create_row(
    plan: PlannedMemoryCreate,
    *,
    user_id: str,
    server_now: int,
) -> MemoryCreateRow:
    status: Literal["active", "conflicted"] = (
        "conflicted" if plan.create_kind == "conflict_new" else "active"
    )
    event_status, start_time, end_time, original_time_text = _event_fields(
        plan.memory_type,
        plan.event_status,
        plan.start_time,
        plan.end_time,
        plan.original_time_text,
    )
    return MemoryCreateRow(
        memory_id=plan.planned_memory_id,
        user_id=user_id,
        memory_type=plan.memory_type,
        content=plan.planned_content,
        subject_entity_id=plan.subject_entity_id,
        predicate=plan.predicate,
        object_entity_id=plan.object_entity_id,
        object_value=plan.object_value,
        status=status,
        event_status=event_status,
        start_time=start_time,
        end_time=end_time,
        original_time_text=original_time_text,
        confidence=plan.planned_confidence,
        importance=plan.planned_importance,
        latest_source_time=plan.planned_latest_source_time,
        first_seen_time=server_now,
        last_seen_time=server_now,
        created_time=server_now,
        updated_time=server_now,
        supersedes_target_memory_id=plan.supersedes_target_memory_id,
        conflicts_with_target_memory_id=plan.conflicts_with_target_memory_id,
    )


def _memory_update_row(
    plan: PlannedExistingMemoryUpdate,
    *,
    user_id: str,
    server_now: int,
) -> MemoryUpdateRow:
    status: str | None = None
    if plan.aggregated_action == "SUPERSEDE":
        status = "superseded"
    elif plan.aggregated_action == "CONFLICT":
        status = "conflicted"
    return MemoryUpdateRow(
        target_memory_id=plan.target_memory_id,
        user_id=user_id,
        planned_merged_content=plan.planned_merged_content,
        planned_merged_confidence=plan.planned_merged_confidence,
        planned_latest_source_time=plan.planned_latest_source_time,
        increment_memory_version=plan.increment_memory_version,
        aggregated_action=plan.aggregated_action,
        updated_time=server_now,
        last_seen_time=server_now,
        status=status,
    )


async def _build_evidence_rows(
    *,
    reconciliation: ReconciliationSuccess,
    extraction_result: ExtractionValidatedResult,
    mongodb: AsyncMongoClient[Any],
    archive_timestamp_repository: ContextArchiveMessageTimestampRepository,
    archive_id: str,
    user_id: str,
    session_id: str,
    prompt_version: str,
    server_now: int,
) -> list[EvidenceWriteRow]:
    rows: list[EvidenceWriteRow] = []
    seen_evidence_ids: set[str] = set()

    async def append_rows(
        memory_id: str,
        evidence_ids: list[str],
        candidate_indices: list[int],
    ) -> None:
        for evidence_id, candidate_index in zip(evidence_ids, candidate_indices, strict=True):
            if evidence_id in seen_evidence_ids:
                continue
            seen_evidence_ids.add(evidence_id)
            candidate = extraction_result.memories[candidate_index]
            source_time_start, source_time_end = (
                await archive_timestamp_repository.resolve_source_time_range(
                    mongodb,
                    archive_id,
                    list(candidate.source_message_ids),
                    candidate.candidate_source_time,
                )
            )
            rows.append(
                EvidenceWriteRow(
                    evidence_id=evidence_id,
                    user_id=user_id,
                    archive_id=archive_id,
                    session_id=session_id,
                    memory_id=memory_id,
                    source_message_ids=list(candidate.source_message_ids),
                    source_time_start=source_time_start,
                    source_time_end=source_time_end,
                    extracted_content=candidate.content,
                    prompt_version=prompt_version,
                    created_time=server_now,
                )
            )

    for create_plan in reconciliation.new_memory_create_plans:
        await append_rows(
            create_plan.planned_memory_id,
            create_plan.contributing_evidence_ids,
            create_plan.contributing_candidate_indices,
        )

    for update_plan in reconciliation.existing_memory_update_plans:
        await append_rows(
            update_plan.target_memory_id,
            update_plan.contributing_evidence_ids,
            update_plan.contributing_candidate_indices,
        )

    return rows


def referenced_entity_write_plans(
    graph_input: GraphWriteInput,
) -> list[ReferencedEntityWritePlan]:
    return build_referenced_entity_write_set(
        graph_input.reconciliation,
        graph_input.entity_alignment,
        graph_input.extraction_result,
    )
