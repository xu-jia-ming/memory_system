"""Unit tests for graph_write_service (EXT-006)."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from pymongo import AsyncMongoClient

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
from memory_system.domain.models.graph_write import (
    GraphWriteAbort,
    GraphWriteInput,
    GraphWriteOutcomeKind,
    ImmutableGraphWritePlan,
)
from memory_system.domain.models.reconciliation import (
    PerCandidateDecision,
    PlannedExistingMemoryUpdate,
    PlannedMemoryCreate,
    ReasonCode,
    ReconciliationAction,
    ReconciliationSuccess,
)
from memory_system.domain.services.graph_write_service import GraphWriteService
from memory_system.infrastructure.mongodb.context_archive_message_timestamp_repository import (
    GraphWriteAbortError,
)
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.settings import get_settings


class _FakeEvidenceRepository:
    def __init__(self, processed: set[str] | None = None) -> None:
        self._processed = processed or set()

    async def find_processed_evidence_ids(
        self, user_id: str, evidence_ids: list[str]
    ) -> set[str]:
        return {evidence_id for evidence_id in evidence_ids if evidence_id in self._processed}


class _FakeWriteRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[ImmutableGraphWritePlan] = []

    async def write(self, plan: ImmutableGraphWritePlan) -> None:
        if self.fail:
            raise RuntimeError("neo4j write failed")
        self.calls.append(plan)


class _UnresolvableMessageIdArchiveRepository:
    async def resolve_source_time_range(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        source_message_ids: list[str],
        candidate_source_time: int,
    ) -> tuple[int, int]:
        if "missing-msg-id" in source_message_ids:
            raise GraphWriteAbortError(GraphWriteAbort())
        if len(source_message_ids) == 1:
            return candidate_source_time, candidate_source_time
        return 100, 200


class _AbortArchiveTimestampRepository:
    async def resolve_source_time_range(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        source_message_ids: list[str],
        candidate_source_time: int,
    ) -> tuple[int, int]:
        raise GraphWriteAbortError(GraphWriteAbort())


def _base_input(
    *,
    reconciliation: ReconciliationSuccess | None = None,
    extraction: ExtractionValidatedResult | None = None,
) -> GraphWriteInput:
    user_id = "user-1"
    extraction_result = extraction or ExtractionValidatedResult(
        entities=[
            ExtractionEntityCandidate(
                local_entity_id="entity_1",
                name="Agent Memory System",
                type="project",
                aliases=[],
            ),
        ],
        memories=[
            ExtractionMemoryCandidate(
                memory_type="event",
                content="secret-content-value",
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
                candidate_source_time=150,
                candidate_fingerprint="fp-1",
            ),
        ],
    )
    reconciliation_result = reconciliation or ReconciliationSuccess(
        user_id=user_id,
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
                planned_content="secret-content-value",
                subject_entity_id=f"user:{user_id}",
                predicate="works_on",
                object_entity_id="entity-uuid-1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                planned_confidence=0.9,
                planned_importance=0.55,
                planned_latest_source_time=150,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
            ),
        ],
    )
    return GraphWriteInput(
        task_id="task-1",
        archive_id="archive-1",
        user_id=user_id,
        session_id="session-1",
        extraction_result=extraction_result,
        entity_alignment=EntityAlignmentSuccess(
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
            ],
        ),
        reconciliation=reconciliation_result,
    )


def _service(
    *,
    processed: set[str] | None = None,
    write_fail: bool = False,
    tokenize_client: FakeTokenizeClient | None = None,
    archive_repo: Any = None,
) -> tuple[GraphWriteService, _FakeWriteRepository]:
    write_repo = _FakeWriteRepository(fail=write_fail)
    service = GraphWriteService(
        _FakeEvidenceRepository(processed),
        write_repo,
        tokenize_client=tokenize_client or FakeTokenizeClient(token_count=10),
        settings=get_settings(),
        archive_timestamp_repository=archive_repo or _FakeArchiveTimestampRepository(),
        server_time_provider=lambda: 1_700_000_000,
    )
    return service, write_repo


class _FakeArchiveTimestampRepository:
    async def resolve_source_time_range(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        source_message_ids: list[str],
        candidate_source_time: int,
    ) -> tuple[int, int]:
        if len(source_message_ids) == 1:
            return candidate_source_time, candidate_source_time
        return 100, 200


@pytest.mark.asyncio
async def test_s1_create_memory_and_evidence_success() -> None:
    service, write_repo = _service()
    result = await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert not isinstance(result, GraphWriteAbort)
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    assert result.success is not None
    assert result.success.skipped_graph_write is False
    assert len(write_repo.calls) == 1


@pytest.mark.asyncio
async def test_s2_merge_update_plan_in_write_transaction() -> None:
    user_id = "user-1"
    reconciliation = ReconciliationSuccess(
        user_id=user_id,
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-1",
                evidence_id="ev-1",
                action=ReconciliationAction.MERGE,
                target_memory_id="mem-existing-1",
                reason_code=ReasonCode.SAME_SEMANTIC_MEMORY,
                skip_reason=None,
                merged_content=None,
                recalled_memory_count=1,
                aligned_memory_key=None,
            ),
        ],
        existing_memory_update_plans=[
            PlannedExistingMemoryUpdate(
                target_memory_id="mem-existing-1",
                aggregated_action="MERGE",
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
                planned_merged_content="merged content",
                planned_merged_confidence=0.85,
                planned_latest_source_time=150,
                increment_memory_version=True,
                planned_new_memory_id=None,
            ),
        ],
        new_memory_create_plans=[],
    )
    service, write_repo = _service()
    result = await service.write(
        _base_input(reconciliation=reconciliation),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    plan = write_repo.calls[0]
    assert len(plan.memory_update_rows) == 1
    assert plan.memory_update_rows[0].increment_memory_version is True


@pytest.mark.asyncio
async def test_s3_supersede_path() -> None:
    user_id = "user-1"
    reconciliation = ReconciliationSuccess(
        user_id=user_id,
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-1",
                evidence_id="ev-1",
                action=ReconciliationAction.SUPERSEDE,
                target_memory_id="mem-old-1",
                reason_code=ReasonCode.EXPLICIT_CORRECTION,
                skip_reason=None,
                merged_content=None,
                recalled_memory_count=1,
                aligned_memory_key=None,
            ),
        ],
        existing_memory_update_plans=[
            PlannedExistingMemoryUpdate(
                target_memory_id="mem-old-1",
                aggregated_action="SUPERSEDE",
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
                planned_merged_content=None,
                planned_merged_confidence=None,
                planned_latest_source_time=150,
                increment_memory_version=True,
                planned_new_memory_id="mem-new-sup",
            ),
        ],
        new_memory_create_plans=[
            PlannedMemoryCreate(
                create_kind="supersede_new",
                planned_memory_id="mem-new-sup",
                aligned_memory_key=None,
                supersedes_target_memory_id="mem-old-1",
                conflicts_with_target_memory_id=None,
                memory_type="event",
                planned_content="secret-content-value",
                subject_entity_id=f"user:{user_id}",
                predicate="works_on",
                object_entity_id="entity-uuid-1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                planned_confidence=0.9,
                planned_importance=0.55,
                planned_latest_source_time=150,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
            ),
        ],
    )
    service, write_repo = _service()
    result = await service.write(
        _base_input(reconciliation=reconciliation),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    plan = write_repo.calls[0]
    assert plan.memory_create_rows[0].supersedes_target_memory_id == "mem-old-1"
    assert plan.memory_update_rows[0].status == "superseded"


@pytest.mark.asyncio
async def test_s4_conflict_path() -> None:
    user_id = "user-1"
    reconciliation = ReconciliationSuccess(
        user_id=user_id,
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-1",
                evidence_id="ev-1",
                action=ReconciliationAction.CONFLICT,
                target_memory_id="mem-old-1",
                reason_code=ReasonCode.UNRESOLVED_CONTRADICTION,
                skip_reason=None,
                merged_content=None,
                recalled_memory_count=1,
                aligned_memory_key=None,
            ),
        ],
        existing_memory_update_plans=[
            PlannedExistingMemoryUpdate(
                target_memory_id="mem-old-1",
                aggregated_action="CONFLICT",
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
                planned_merged_content=None,
                planned_merged_confidence=None,
                planned_latest_source_time=150,
                increment_memory_version=True,
                planned_new_memory_id="mem-new-conf",
            ),
        ],
        new_memory_create_plans=[
            PlannedMemoryCreate(
                create_kind="conflict_new",
                planned_memory_id="mem-new-conf",
                aligned_memory_key=None,
                supersedes_target_memory_id=None,
                conflicts_with_target_memory_id="mem-old-1",
                memory_type="event",
                planned_content="secret-content-value",
                subject_entity_id=f"user:{user_id}",
                predicate="works_on",
                object_entity_id="entity-uuid-1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                planned_confidence=0.9,
                planned_importance=0.55,
                planned_latest_source_time=150,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
            ),
        ],
    )
    service, write_repo = _service()
    result = await service.write(
        _base_input(reconciliation=reconciliation),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    plan = write_repo.calls[0]
    assert plan.memory_create_rows[0].status == "conflicted"
    assert plan.memory_update_rows[0].status == "conflicted"


@pytest.mark.asyncio
async def test_s5_all_evidence_processed_skips_write() -> None:
    service, write_repo = _service(processed={"ev-1"})
    result = await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    assert result.success is not None
    assert result.success.skipped_graph_write is True
    assert write_repo.calls == []


@pytest.mark.asyncio
async def test_s6_replay_second_call_skips_write() -> None:
    service, write_repo = _service()
    mongodb = AsyncMongoClient("mongodb://localhost:27017/memory_system")
    graph_input = _base_input()
    first = await service.write(graph_input, mongodb=mongodb)
    assert first.success is not None and not first.success.skipped_graph_write
    service_replay, write_repo_replay = _service(processed={"ev-1"})
    second = await service_replay.write(graph_input, mongodb=mongodb)
    assert second.success is not None
    assert second.success.skipped_graph_write is True
    assert write_repo_replay.calls == []


@pytest.mark.asyncio
async def test_s7_write_failure_maps_graph_write_failed() -> None:
    service, _ = _service(write_fail=True)
    result = await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "graph_write_failed"
    assert result.failure.failed_stage == "graph_write"


@pytest.mark.asyncio
async def test_s8_write_plan_includes_user_id_for_isolation() -> None:
    service, write_repo = _service()
    await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    plan = write_repo.calls[0]
    assert all(row.user_id == "user-1" for row in plan.entity_rows)
    assert all(row.user_id == "user-1" for row in plan.memory_create_rows)
    assert all(row.user_id == "user-1" for row in plan.evidence_rows)


@pytest.mark.asyncio
async def test_s9_no_upstream_llm_invocation() -> None:
    service, _ = _service()
    await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )


@pytest.mark.asyncio
async def test_s10_privacy_no_sensitive_fields_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    service, _ = _service(write_fail=True)
    await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    combined = caplog.text
    assert "secret-content-value" not in combined
    assert "Agent Memory System" not in combined


@pytest.mark.asyncio
async def test_s11_precondition_abort_without_terminal() -> None:
    service, write_repo = _service()
    graph_input = _base_input()
    graph_input.extraction_result = ExtractionValidatedResult(entities=[], memories=[])
    result = await service.write(
        graph_input,
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert isinstance(result, GraphWriteAbort)
    assert write_repo.calls == []


@pytest.mark.asyncio
async def test_s12_forbidden_error_codes_not_emitted() -> None:
    service, _ = _service(write_fail=True)
    result = await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.failure is not None
    assert result.failure.error_code not in {
        "graph_query_failed",
        "llm_timeout",
        "entity_alignment_failed",
    }


@pytest.mark.asyncio
async def test_s13_evidence_source_time_single_message() -> None:
    service, write_repo = _service()
    await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    evidence = write_repo.calls[0].evidence_rows[0]
    assert evidence.source_time_start == 150
    assert evidence.source_time_end == 150


@pytest.mark.asyncio
async def test_s14_archive_missing_aborts_without_write() -> None:
    service, write_repo = _service(archive_repo=_AbortArchiveTimestampRepository())
    result = await service.write(
        _base_input(),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert isinstance(result, GraphWriteAbort)
    assert write_repo.calls == []


@pytest.mark.asyncio
async def test_s14b_unresolvable_message_id_aborts_without_write() -> None:
    extraction = ExtractionValidatedResult(
        entities=[
            ExtractionEntityCandidate(
                local_entity_id="entity_1",
                name="Agent Memory System",
                type="project",
                aliases=[],
            ),
        ],
        memories=[
            ExtractionMemoryCandidate(
                memory_type="event",
                content="secret-content-value",
                subject_entity_id="user",
                predicate="works_on",
                object_entity_id="entity_1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                confidence=0.9,
                source_message_ids=["missing-msg-id"],
                candidate_source_time=150,
                candidate_fingerprint="fp-1",
            ),
        ],
    )
    service, write_repo = _service(archive_repo=_UnresolvableMessageIdArchiveRepository())
    result = await service.write(
        _base_input(extraction=extraction),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert isinstance(result, GraphWriteAbort)
    assert write_repo.calls == []
