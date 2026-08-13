"""Unit coverage for the EXT-009 production extraction continuation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus, PipelineTerminalKind
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentFailure,
    EntityAlignmentOutcome,
    EntityAlignmentOutcomeKind,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.models.graph_write import (
    GraphWriteFailure,
    GraphWriteOutcome,
    GraphWriteOutcomeKind,
    GraphWriteSuccess,
    IndexSyncMemoryEntry,
)
from memory_system.domain.models.reconciliation import (
    ReconciliationErrorCode,
    ReconciliationFailure,
    ReconciliationOutcome,
    ReconciliationOutcomeKind,
    ReconciliationSuccess,
)
from memory_system.domain.models.retrieval_index_sync import (
    RetrievalIndexSyncFailure,
    RetrievalIndexSyncOutcome,
    RetrievalIndexSyncOutcomeKind,
)
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.production_extraction_pipeline import (
    ProductionExtractionPipeline,
)

NOW = 1_700_000_000


def _event() -> ArchiveCreatedEvent:
    return ArchiveCreatedEvent(
        event_id="event-1",
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        created_time=NOW,
    )


def _task(**overrides: Any) -> MemoryExtractionTask:
    payload: dict[str, Any] = {
        "task_id": "11111111-1111-4111-8111-111111111111",
        "archive_id": "archive-1",
        "user_id": "user-1",
        "status": ExtractionTaskStatus.PROCESSING,
        "attempt_count": 1,
        "extraction_result": {"entities": [{"local_entity_id": "entity-1"}], "memories": []},
        "last_error": None,
        "created_time": NOW,
        "updated_time": NOW,
        "completed_time": None,
    }
    payload.update(overrides)
    return MemoryExtractionTask.model_validate(payload)


def _alignment_success() -> EntityAlignmentSuccess:
    return EntityAlignmentSuccess(
        user_id="user-1",
        alignments=[
            AlignedEntity(
                local_entity_id="entity-1",
                entity_id="entity-1",
                match_kind=EntityMatchKind.PLANNED_CREATE,
                entity_type="project",
                canonical_name="Project",
                normalized_name="project",
                entity_key="project-key",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=[],
                    planned_aliases=[],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=True,
            )
        ],
    )


def _reconciliation_success() -> ReconciliationSuccess:
    return ReconciliationSuccess(
        user_id="user-1",
        archive_id="archive-1",
        per_candidate_decisions=[],
        existing_memory_update_plans=[],
        new_memory_create_plans=[],
    )


def _graph_success() -> GraphWriteSuccess:
    return GraphWriteSuccess(
        user_id="user-1",
        archive_id="archive-1",
        skipped_graph_write=False,
        index_sync_memory_set=[],
    )


def _pipeline(
    *,
    llm: AsyncMock | None = None,
    alignment: AsyncMock | None = None,
    reconciliation: AsyncMock | None = None,
    graph: AsyncMock | None = None,
    retrieval: AsyncMock | None = None,
    before_retrieval_sync_hook: Any = None,
    replay_index_sync_memory_set_loader: Any = None,
) -> tuple[ProductionExtractionPipeline, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    llm_service = AsyncMock()
    llm_service.run = llm or AsyncMock(
        return_value=PipelineTerminalDecision.abort_without_terminal()
    )
    alignment_service = AsyncMock()
    alignment_service.load_from_persisted_task = alignment or AsyncMock(
        return_value=EntityAlignmentOutcome(
            outcome=EntityAlignmentOutcomeKind.SUCCESS,
            success=_alignment_success(),
            failure=None,
        )
    )
    reconciliation_service = AsyncMock()
    reconciliation_service.load_from_persisted_task = reconciliation or AsyncMock(
        return_value=ReconciliationOutcome(
            outcome=ReconciliationOutcomeKind.SUCCESS,
            success=_reconciliation_success(),
            failure=None,
        )
    )
    graph_service = AsyncMock()
    graph_service.load_from_persisted_task = graph or AsyncMock(
        return_value=GraphWriteOutcome(
            outcome=GraphWriteOutcomeKind.SUCCESS,
            success=_graph_success(),
            failure=None,
        )
    )
    retrieval_service = AsyncMock()
    retrieval_service.sync = retrieval or AsyncMock(
        return_value=RetrievalIndexSyncOutcome(
            outcome=RetrievalIndexSyncOutcomeKind.SUCCESS,
        )
    )
    pipeline = ProductionExtractionPipeline(
        AsyncMock(),
        llm_service,
        alignment_service,
        reconciliation_service,
        graph_service,
        retrieval_service,
        before_retrieval_sync_hook=before_retrieval_sync_hook,
        replay_index_sync_memory_set_loader=replay_index_sync_memory_set_loader,
    )
    return (
        pipeline,
        llm_service,
        alignment_service,
        reconciliation_service,
        graph_service,
        retrieval_service,
    )


@pytest.mark.asyncio
async def test_happy_path_preserves_stage_order_and_retrieval_metadata() -> None:
    calls: list[str] = []
    alignment = AsyncMock(
        return_value=EntityAlignmentOutcome(
            outcome=EntityAlignmentOutcomeKind.SUCCESS,
            success=_alignment_success(),
            failure=None,
        )
    )
    reconciliation = AsyncMock(
        return_value=ReconciliationOutcome(
            outcome=ReconciliationOutcomeKind.SUCCESS,
            success=_reconciliation_success(),
            failure=None,
        )
    )
    graph = AsyncMock(
        return_value=GraphWriteOutcome(
            outcome=GraphWriteOutcomeKind.SUCCESS,
            success=_graph_success(),
            failure=None,
        )
    )
    retrieval = AsyncMock(
        return_value=RetrievalIndexSyncOutcome(
            outcome=RetrievalIndexSyncOutcomeKind.SUCCESS,
        )
    )
    for mock, name in (
        (alignment, "alignment"),
        (reconciliation, "reconciliation"),
        (graph, "graph"),
        (retrieval, "retrieval"),
    ):
        mock.side_effect = lambda *args, _mock=mock, _name=name, **kwargs: (
            calls.append(_name) or _mock.return_value
        )

    pipeline, llm, _, _, _, retrieval_service = _pipeline(
        alignment=alignment,
        reconciliation=reconciliation,
        graph=graph,
        retrieval=retrieval,
    )
    decision = await pipeline.run(_task(), _event())

    assert decision.kind == PipelineTerminalKind.COMPLETE
    assert calls == ["alignment", "reconciliation", "graph", "retrieval"]
    llm.run.assert_not_awaited()
    retrieval_call = retrieval_service.sync.await_args
    assert retrieval_call is not None
    sync_input = retrieval_call.args[0]
    assert sync_input.session_id == "session-1"
    assert sync_input.graph_write_success == _graph_success()


@pytest.mark.asyncio
async def test_both_empty_llm_result_completes_without_downstream_stages() -> None:
    llm = AsyncMock(return_value=PipelineTerminalDecision.complete())
    pipeline, llm_service, alignment, reconciliation, graph, retrieval = _pipeline(llm=llm)

    decision = await pipeline.run(_task(extraction_result=None), _event())

    assert decision.kind == PipelineTerminalKind.COMPLETE
    llm_service.run.assert_awaited_once()
    alignment.load_from_persisted_task.assert_not_awaited()
    reconciliation.load_from_persisted_task.assert_not_awaited()
    graph.load_from_persisted_task.assert_not_awaited()
    retrieval.sync.assert_not_awaited()


@pytest.mark.asyncio
async def test_newly_persisted_extraction_result_falls_through_to_alignment() -> None:
    llm = AsyncMock(return_value=PipelineTerminalDecision.abort_without_terminal())
    pipeline, llm_service, alignment, reconciliation, graph, retrieval = _pipeline(llm=llm)
    reloaded = _task(
        extraction_result={"entities": [{"local_entity_id": "entity-1"}], "memories": []}
    )

    with patch(
        "memory_system.domain.services.production_extraction_pipeline.task_repo."
        "find_extraction_task_by_archive_id",
        new=AsyncMock(return_value=reloaded),
    ):
        decision = await pipeline.run(_task(extraction_result=None), _event())

    assert decision.kind == PipelineTerminalKind.COMPLETE
    llm_service.run.assert_awaited_once()
    alignment.load_from_persisted_task.assert_awaited_once()
    reconciliation.load_from_persisted_task.assert_awaited_once()
    graph.load_from_persisted_task.assert_awaited_once()
    retrieval.sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_failure_returns_without_downstream_calls() -> None:
    error = ExtractionLastError(
        error_code="llm_invalid_output",
        failed_stage="llm_extraction",
        message="extraction llm failed",
    )
    llm = AsyncMock(return_value=PipelineTerminalDecision.fail(error))
    pipeline, _, alignment, reconciliation, graph, retrieval = _pipeline(llm=llm)

    decision = await pipeline.run(_task(extraction_result=None), _event())

    assert decision == PipelineTerminalDecision.fail(error)
    alignment.load_from_persisted_task.assert_not_awaited()
    reconciliation.load_from_persisted_task.assert_not_awaited()
    graph.load_from_persisted_task.assert_not_awaited()
    retrieval.sync.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stage", "outcome", "error_code", "failed_stage"),
    [
        (
            "alignment",
            EntityAlignmentOutcome(
                outcome=EntityAlignmentOutcomeKind.FAILURE,
                success=None,
                failure=EntityAlignmentFailure(),
            ),
            "entity_alignment_failed",
            "entity_alignment",
        ),
        (
            "reconciliation",
            ReconciliationOutcome(
                outcome=ReconciliationOutcomeKind.FAILURE,
                success=None,
                failure=ReconciliationFailure(
                    error_code=ReconciliationErrorCode.RECONCILIATION_PLAN_CONFLICT
                ),
            ),
            "reconciliation_plan_conflict",
            "reconciliation",
        ),
        (
            "graph",
            GraphWriteOutcome(
                outcome=GraphWriteOutcomeKind.FAILURE,
                success=None,
                failure=GraphWriteFailure(error_code="memory_search_text_too_long"),
            ),
            "memory_search_text_too_long",
            "graph_write",
        ),
    ],
)
async def test_stage_failure_maps_to_existing_terminal_error(
    stage: str,
    outcome: Any,
    error_code: str,
    failed_stage: str,
) -> None:
    kwargs: dict[str, AsyncMock] = {}
    if stage == "alignment":
        kwargs["alignment"] = AsyncMock(return_value=outcome)
    elif stage == "reconciliation":
        kwargs["reconciliation"] = AsyncMock(return_value=outcome)
    else:
        kwargs["graph"] = AsyncMock(return_value=outcome)
    pipeline, _, _, _, _, _ = _pipeline(**kwargs)

    decision = await pipeline.run(_task(), _event())

    assert decision.kind == PipelineTerminalKind.FAIL
    assert decision.last_error is not None
    assert decision.last_error.error_code == error_code
    assert decision.last_error.failed_stage == failed_stage


@pytest.mark.asyncio
async def test_retrieval_failure_is_mapped_without_second_terminal_write() -> None:
    retrieval = AsyncMock(
        return_value=RetrievalIndexSyncOutcome(
            outcome=RetrievalIndexSyncOutcomeKind.FAILURE,
            failure=RetrievalIndexSyncFailure(message="EmbeddingServiceError"),
        )
    )
    pipeline, _, _, _, _, retrieval_service = _pipeline(retrieval=retrieval)

    decision = await pipeline.run(_task(), _event())

    assert decision.kind == PipelineTerminalKind.FAIL
    assert decision.last_error == ExtractionLastError(
        error_code="retrieval_index_write_failed",
        failed_stage="retrieval_index",
        message="EmbeddingServiceError",
    )
    retrieval_service.sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_f1_hook_crashes_after_graph_before_retrieval() -> None:
    async def crash_after_graph(_success: GraphWriteSuccess) -> None:
        raise RuntimeError("injected graph-to-index crash")

    pipeline, _, _, _, graph, retrieval = _pipeline(
        before_retrieval_sync_hook=crash_after_graph,
    )

    with pytest.raises(RuntimeError, match="injected graph-to-index crash"):
        await pipeline.run(_task(), _event())

    graph.load_from_persisted_task.assert_awaited_once()
    retrieval.sync.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_replay_index_set_is_repaired_from_durable_memory_set() -> None:
    replay_loader = AsyncMock(
        return_value=[
            IndexSyncMemoryEntry(
                memory_id="memory-replayed",
                core_search_text="replayed core",
                token_count=10,
            )
        ]
    )
    pipeline, _, _, _, _, retrieval_service = _pipeline(
        replay_index_sync_memory_set_loader=replay_loader,
    )

    decision = await pipeline.run(
        _task(
            extraction_result={
                "entities": [],
                "memories": [{"candidate_fingerprint": "fingerprint-1"}],
            }
        ),
        _event(),
    )

    assert decision.kind == PipelineTerminalKind.COMPLETE
    replay_loader.assert_awaited_once_with("user-1", "archive-1")
    retrieval_call = retrieval_service.sync.await_args
    assert retrieval_call is not None
    repaired_graph_success = retrieval_call.args[0].graph_write_success
    assert repaired_graph_success.index_sync_memory_set == [
        IndexSyncMemoryEntry(
            memory_id="memory-replayed",
            core_search_text="replayed core",
            token_count=10,
        )
    ]
    assert repaired_graph_success.skipped_graph_write is False
