"""EXT-005 reconciliation orchestration service (read-only, transient plan)."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

import structlog
from pydantic import ValidationError
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.entity_alignment import EntityAlignmentSuccess
from memory_system.domain.models.extraction_llm import (
    ExtractionMemoryCandidate,
    ExtractionValidatedResult,
)
from memory_system.domain.models.memory_recall import MemoryNodeSnapshot
from memory_system.domain.models.reconciliation import (
    AlignedMemoryCandidateView,
    ReasonCode,
    ReconciliationAbort,
    ReconciliationAction,
    ReconciliationErrorCode,
    ReconciliationFailure,
    ReconciliationInput,
    ReconciliationOutcome,
    ReconciliationOutcomeKind,
)
from memory_system.domain.services.aligned_memory_key import compute_aligned_memory_key
from memory_system.domain.services.evidence_identity import compute_evidence_id
from memory_system.domain.services.reconciliation_llm_service import run_reconciliation_llm
from memory_system.domain.services.reconciliation_plan_builder import (
    CandidatePlanInput,
    MemoryIdFactory,
    build_reconciliation_plan,
    compute_create_aligned_memory_key,
)
from memory_system.infrastructure.llm.protocol import LLMClient
from memory_system.infrastructure.mongodb import extraction_task_repository as task_repo
from memory_system.infrastructure.neo4j.evidence_lookup_repository import EvidenceGraphDataError
from memory_system.infrastructure.neo4j.memory_recall_repository import (
    MemoryGraphDataError,
    MemoryRecallKey,
)
from memory_system.settings.models import Settings

_logger = structlog.get_logger(__name__)


class EvidenceLookupReadRepository(Protocol):
    async def find_processed_evidence_ids(
        self, user_id: str, evidence_ids: list[str]
    ) -> set[str]: ...


class MemoryRecallReadRepository(Protocol):
    async def recall_memories_batch(
        self,
        user_id: str,
        recall_keys: list[MemoryRecallKey],
    ) -> dict[int, list[MemoryNodeSnapshot]]: ...


def build_aligned_candidate_views(
    *,
    memories: list[ExtractionMemoryCandidate],
    archive_id: str,
    local_entity_id_map: dict[str, str],
) -> list[AlignedMemoryCandidateView]:
    views: list[AlignedMemoryCandidateView] = []
    for index, memory in enumerate(memories):
        subject_entity_id = local_entity_id_map.get(memory.subject_entity_id)
        if subject_entity_id is None:
            raise KeyError(f"missing aligned subject entity for {memory.subject_entity_id}")
        object_entity_id: str | None
        if memory.object_entity_id is None:
            object_entity_id = None
        else:
            mapped_object = local_entity_id_map.get(memory.object_entity_id)
            if mapped_object is None:
                raise KeyError(f"missing aligned object entity for {memory.object_entity_id}")
            object_entity_id = mapped_object
        views.append(
            AlignedMemoryCandidateView(
                candidate_index=index,
                memory_type=memory.memory_type,
                content=memory.content,
                predicate=memory.predicate,
                object_value=memory.object_value,
                event_status=memory.event_status,
                start_time=memory.start_time,
                end_time=memory.end_time,
                original_time_text=memory.original_time_text,
                confidence=memory.confidence,
                source_message_ids=list(memory.source_message_ids),
                candidate_source_time=memory.candidate_source_time,
                candidate_fingerprint=memory.candidate_fingerprint,
                subject_entity_id=subject_entity_id,
                object_entity_id=object_entity_id,
                evidence_id=compute_evidence_id(archive_id, memory.candidate_fingerprint),
            )
        )
    return views


class ReconciliationService:
    """Build transient reconciliation plan from persisted extraction + alignment."""

    def __init__(
        self,
        evidence_repository: EvidenceLookupReadRepository,
        memory_recall_repository: MemoryRecallReadRepository,
        *,
        llm_client: LLMClient,
        settings: Settings,
        memory_id_factory: MemoryIdFactory | None = None,
    ) -> None:
        self._evidence_repository = evidence_repository
        self._memory_recall_repository = memory_recall_repository
        self._llm_client = llm_client
        self._settings = settings
        self._memory_id_factory = memory_id_factory or (lambda: str(uuid.uuid4()))

    async def reconcile(
        self,
        reconciliation_input: ReconciliationInput,
        *,
        attempt_count: int | None = None,
    ) -> ReconciliationOutcome | ReconciliationAbort:
        try:
            aligned_views = build_aligned_candidate_views(
                memories=reconciliation_input.extraction_result.memories,
                archive_id=reconciliation_input.archive_id,
                local_entity_id_map=reconciliation_input.entity_alignment.local_entity_id_map(),
            )
        except KeyError:
            return ReconciliationAbort()

        evidence_ids = [view.evidence_id for view in aligned_views]
        try:
            processed_evidence_ids = await self._evidence_repository.find_processed_evidence_ids(
                reconciliation_input.user_id,
                evidence_ids,
            )
        except (EvidenceGraphDataError, Exception):
            return self._graph_query_failure(reconciliation_input, attempt_count=attempt_count)

        recall_keys = [
            MemoryRecallKey(
                candidate_index=view.candidate_index,
                memory_type=view.memory_type,
                subject_entity_id=view.subject_entity_id,
                predicate=view.predicate,
            )
            for view in aligned_views
            if view.evidence_id not in processed_evidence_ids
        ]
        recalled_by_index: dict[int, list[MemoryNodeSnapshot]] = {}
        if recall_keys:
            try:
                recalled_by_index = await self._memory_recall_repository.recall_memories_batch(
                    reconciliation_input.user_id,
                    recall_keys,
                )
            except (MemoryGraphDataError, Exception):
                return self._graph_query_failure(reconciliation_input, attempt_count=attempt_count)

        plan_inputs: list[CandidatePlanInput] = []
        for view in aligned_views:
            if view.evidence_id in processed_evidence_ids:
                plan_inputs.append(
                    CandidatePlanInput(
                        candidate_index=view.candidate_index,
                        candidate_fingerprint=view.candidate_fingerprint,
                        evidence_id=view.evidence_id,
                        action=ReconciliationAction.SKIP,
                        target_memory_id=None,
                        reason_code=None,
                        skip_reason="evidence_already_processed",
                        merged_content=None,
                        recalled_memory_count=0,
                        aligned_memory_key=None,
                        memory_type=view.memory_type,
                        content=view.content,
                        subject_entity_id=view.subject_entity_id,
                        predicate=view.predicate,
                        object_entity_id=view.object_entity_id,
                        object_value=view.object_value,
                        event_status=view.event_status,
                        start_time=view.start_time,
                        end_time=view.end_time,
                        original_time_text=view.original_time_text,
                        confidence=view.confidence,
                        candidate_source_time=view.candidate_source_time,
                        recalled_memories=[],
                    )
                )
                continue

            recalled = recalled_by_index.get(view.candidate_index, [])
            if not recalled:
                create_aligned_key = compute_aligned_memory_key(
                    memory_type=view.memory_type,
                    final_subject_entity_id=view.subject_entity_id,
                    predicate=view.predicate,
                    final_object_entity_id=view.object_entity_id,
                    object_value=view.object_value,
                    event_status=view.event_status,
                    start_time=view.start_time,
                    end_time=view.end_time,
                )
                plan_inputs.append(
                    CandidatePlanInput(
                        candidate_index=view.candidate_index,
                        candidate_fingerprint=view.candidate_fingerprint,
                        evidence_id=view.evidence_id,
                        action=ReconciliationAction.CREATE,
                        target_memory_id=None,
                        reason_code=ReasonCode.NEW_MEMORY,
                        skip_reason=None,
                        merged_content=None,
                        recalled_memory_count=0,
                        aligned_memory_key=create_aligned_key,
                        memory_type=view.memory_type,
                        content=view.content,
                        subject_entity_id=view.subject_entity_id,
                        predicate=view.predicate,
                        object_entity_id=view.object_entity_id,
                        object_value=view.object_value,
                        event_status=view.event_status,
                        start_time=view.start_time,
                        end_time=view.end_time,
                        original_time_text=view.original_time_text,
                        confidence=view.confidence,
                        candidate_source_time=view.candidate_source_time,
                        recalled_memories=[],
                    )
                )
                continue

            llm_result = await run_reconciliation_llm(
                task_id=reconciliation_input.task_id,
                archive_id=reconciliation_input.archive_id,
                user_id=reconciliation_input.user_id,
                candidate=view,
                existing_memories=recalled,
                llm_client=self._llm_client,
                settings=self._settings,
                attempt_count=attempt_count,
            )
            if isinstance(llm_result, ReconciliationOutcome):
                return llm_result

            aligned_key: str | None = None
            if llm_result.action == ReconciliationAction.CREATE:
                candidate_input = CandidatePlanInput(
                    candidate_index=view.candidate_index,
                    candidate_fingerprint=view.candidate_fingerprint,
                    evidence_id=view.evidence_id,
                    action=llm_result.action,
                    target_memory_id=llm_result.target_memory_id,
                    reason_code=llm_result.reason_code,
                    skip_reason=None,
                    merged_content=llm_result.merged_content,
                    recalled_memory_count=len(recalled),
                    aligned_memory_key=None,
                    memory_type=view.memory_type,
                    content=view.content,
                    subject_entity_id=view.subject_entity_id,
                    predicate=view.predicate,
                    object_entity_id=view.object_entity_id,
                    object_value=view.object_value,
                    event_status=view.event_status,
                    start_time=view.start_time,
                    end_time=view.end_time,
                    original_time_text=view.original_time_text,
                    confidence=view.confidence,
                    candidate_source_time=view.candidate_source_time,
                    recalled_memories=recalled,
                )
                aligned_key = compute_create_aligned_memory_key(candidate_input)

            plan_inputs.append(
                CandidatePlanInput(
                    candidate_index=view.candidate_index,
                    candidate_fingerprint=view.candidate_fingerprint,
                    evidence_id=view.evidence_id,
                    action=llm_result.action,
                    target_memory_id=llm_result.target_memory_id,
                    reason_code=llm_result.reason_code,
                    skip_reason=None,
                    merged_content=llm_result.merged_content,
                    recalled_memory_count=len(recalled),
                    aligned_memory_key=aligned_key,
                    memory_type=view.memory_type,
                    content=view.content,
                    subject_entity_id=view.subject_entity_id,
                    predicate=view.predicate,
                    object_entity_id=view.object_entity_id,
                    object_value=view.object_value,
                    event_status=view.event_status,
                    start_time=view.start_time,
                    end_time=view.end_time,
                    original_time_text=view.original_time_text,
                    confidence=view.confidence,
                    candidate_source_time=view.candidate_source_time,
                    recalled_memories=recalled,
                )
            )

        return build_reconciliation_plan(
            user_id=reconciliation_input.user_id,
            archive_id=reconciliation_input.archive_id,
            candidates=plan_inputs,
            memory_id_factory=self._memory_id_factory,
        )

    async def load_from_persisted_task(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        *,
        entity_alignment_success: EntityAlignmentSuccess,
    ) -> ReconciliationOutcome | ReconciliationAbort:
        task = await task_repo.find_extraction_task_by_archive_id(mongodb, archive_id)
        if task is None:
            return ReconciliationAbort()
        if task.status != ExtractionTaskStatus.PROCESSING or task.extraction_result is None:
            return ReconciliationAbort()
        try:
            validated = ExtractionValidatedResult.model_validate(task.extraction_result)
        except ValidationError:
            return ReconciliationAbort()

        reconciliation_input = ReconciliationInput(
            task_id=task.task_id,
            archive_id=task.archive_id,
            user_id=task.user_id,
            session_id=None,
            extraction_result=validated,
            entity_alignment=entity_alignment_success,
        )
        result = await self.reconcile(reconciliation_input, attempt_count=task.attempt_count)
        if isinstance(result, ReconciliationAbort):
            return result
        return result

    def _graph_query_failure(
        self,
        reconciliation_input: ReconciliationInput,
        *,
        attempt_count: int | None,
    ) -> ReconciliationOutcome:
        log_kwargs: dict[str, str | int] = {
            "task_id": reconciliation_input.task_id,
            "archive_id": reconciliation_input.archive_id,
            "user_id": reconciliation_input.user_id,
            "failed_stage": "reconciliation",
        }
        if attempt_count is not None:
            log_kwargs["attempt_count"] = attempt_count
        _logger.warning(
            "reconciliation graph query failed",
            error_code=ReconciliationErrorCode.GRAPH_QUERY_FAILED.value,
            **log_kwargs,
        )
        return ReconciliationOutcome(
            outcome=ReconciliationOutcomeKind.FAILURE,
            success=None,
            failure=ReconciliationFailure(error_code=ReconciliationErrorCode.GRAPH_QUERY_FAILED),
        )


def create_reconciliation_service(
    driver: Any,
    *,
    llm_client: LLMClient,
    settings: Settings,
    memory_id_factory: MemoryIdFactory | None = None,
) -> ReconciliationService:
    from memory_system.infrastructure.neo4j.evidence_lookup_repository import (
        EvidenceLookupRepository,
    )
    from memory_system.infrastructure.neo4j.memory_recall_repository import MemoryRecallRepository

    return ReconciliationService(
        EvidenceLookupRepository(driver),
        MemoryRecallRepository(driver),
        llm_client=llm_client,
        settings=settings,
        memory_id_factory=memory_id_factory,
    )
