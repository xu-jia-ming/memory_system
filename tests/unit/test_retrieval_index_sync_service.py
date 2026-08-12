"""Unit tests for retrieval_index_sync_service (EXT-007)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.support.fake_retrieval_index_embedding_client import FakeEmbeddingClient
from tests.support.fake_retrieval_index_read_repository import FakeRetrievalIndexReadRepository
from tests.support.fake_retrieval_index_write_repository import FakeRetrievalIndexWriteRepository

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.extraction_task import MemoryExtractionTask
from memory_system.domain.models.graph_write import GraphWriteSuccess, IndexSyncMemoryEntry
from memory_system.domain.models.retrieval_index_sync import (
    MemoryIndexRow,
    RetrievalIndexSyncAbort,
    RetrievalIndexSyncInput,
    RetrievalIndexSyncOutcomeKind,
)
from memory_system.domain.services.retrieval_index_sync_service import (
    EMBEDDING_BATCH_SIZE,
    RetrievalIndexSyncService,
)
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.settings import get_settings

NOW = 1_700_000_000


def _processing_task(**overrides: object) -> MemoryExtractionTask:
    payload: dict[str, Any] = {
        "task_id": "11111111-1111-4111-8111-111111111111",
        "archive_id": "archive-1",
        "user_id": "user-1",
        "status": ExtractionTaskStatus.PROCESSING,
        "attempt_count": 1,
        "extraction_result": {"entities": [], "memories": []},
        "last_error": None,
        "created_time": NOW,
        "updated_time": NOW,
        "completed_time": None,
    }
    payload.update(overrides)
    return MemoryExtractionTask.model_validate(payload)


def _alignment() -> EntityAlignmentSuccess:
    return EntityAlignmentSuccess(
        user_id="user-1",
        alignments=[
            AlignedEntity(
                local_entity_id="entity_1",
                entity_id="entity-project",
                match_kind=EntityMatchKind.PLANNED_CREATE,
                entity_type="project",
                canonical_name="Project",
                normalized_name="project",
                entity_key="key-1",
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


def _sync_input(*, handoff: list[IndexSyncMemoryEntry] | None = None) -> RetrievalIndexSyncInput:
    return RetrievalIndexSyncInput(
        task_id="11111111-1111-4111-8111-111111111111",
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        graph_write_success=GraphWriteSuccess(
            user_id="user-1",
            archive_id="archive-1",
            skipped_graph_write=False,
            index_sync_memory_set=(
                handoff
                if handoff is not None
                else [
                    IndexSyncMemoryEntry(
                        memory_id="mem-1",
                        core_search_text="content works_on project",
                        token_count=3,
                    ),
                ]
            ),
        ),
        entity_alignment=_alignment(),
    )


def _memory_row(memory_id: str = "mem-1") -> MemoryIndexRow:
    return MemoryIndexRow(
        memory_id=memory_id,
        user_id="user-1",
        memory_type="event",
        status="active",
        content="content",
        predicate="works_on",
        event_status="ongoing",
        latest_source_time=100,
        updated_time=NOW,
        subject_entity_id="user:user-1",
        object_entity_id="entity-project",
        object_value=None,
        subject_canonical_name="current_user",
        subject_aliases=[],
        object_canonical_name="Project",
        object_aliases=["alias-a"],
    )


def _service(
    *,
    read_repo: FakeRetrievalIndexReadRepository | None = None,
    write_repo: FakeRetrievalIndexWriteRepository | None = None,
    embedding: FakeEmbeddingClient | None = None,
) -> RetrievalIndexSyncService:
    return RetrievalIndexSyncService(
        read_repo or FakeRetrievalIndexReadRepository(rows=[_memory_row()]),
        write_repo or FakeRetrievalIndexWriteRepository(),
        tokenize_client=FakeTokenizeClient(),
        embedding_client=embedding or FakeEmbeddingClient(),
        settings=get_settings(),
        server_time_provider=lambda: NOW + 10,
    )


@pytest.mark.asyncio
async def test_u7_completed_skip_without_es_write() -> None:
    service = _service()
    write_repo = FakeRetrievalIndexWriteRepository()
    service._write_repository = write_repo
    completed = _processing_task(status=ExtractionTaskStatus.COMPLETED, completed_time=NOW)

    with patch(
        "memory_system.domain.services.retrieval_index_sync_service.task_repo.find_extraction_task_by_archive_id",
        AsyncMock(return_value=completed),
    ):
        outcome = await service.sync(_sync_input(), mongodb=MagicMock())

    assert isinstance(outcome, type(outcome))
    assert outcome.outcome == RetrievalIndexSyncOutcomeKind.SKIP_ALREADY_COMPLETED
    assert outcome.skip is not None
    assert write_repo.calls == []


@pytest.mark.asyncio
async def test_u6_embedding_error_maps_to_failure() -> None:
    service = _service(embedding=FakeEmbeddingClient(fail=True))
    processing = _processing_task()
    failed = _processing_task(status=ExtractionTaskStatus.FAILED)

    with (
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.find_extraction_task_by_archive_id",
            AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.mark_failed",
            AsyncMock(return_value=failed),
        ) as mark_failed,
    ):
        outcome = await service.sync(_sync_input(), mongodb=MagicMock())

    assert outcome.outcome == RetrievalIndexSyncOutcomeKind.FAILURE
    assert outcome.failure is not None
    assert outcome.failure.error_code == "retrieval_index_write_failed"
    assert outcome.failure.failed_stage == "retrieval_index"
    mark_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_success_marks_completed_after_es_write() -> None:
    write_repo = FakeRetrievalIndexWriteRepository()
    service = _service(write_repo=write_repo)
    processing = _processing_task()
    completed = _processing_task(status=ExtractionTaskStatus.COMPLETED, completed_time=NOW + 10)

    with (
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.find_extraction_task_by_archive_id",
            AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.mark_completed",
            AsyncMock(return_value=completed),
        ) as mark_completed,
    ):
        outcome = await service.sync(_sync_input(), mongodb=MagicMock())

    assert outcome.outcome == RetrievalIndexSyncOutcomeKind.SUCCESS
    assert outcome.success is not None
    assert outcome.success.synced_memory_count == 1
    assert len(write_repo.calls) == 1
    mark_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_sf2_empty_sync_set_marks_completed_without_es_bulk() -> None:
    write_repo = FakeRetrievalIndexWriteRepository()
    service = _service(
        read_repo=FakeRetrievalIndexReadRepository(rows=[]),
        write_repo=write_repo,
    )
    processing = _processing_task()
    completed = _processing_task(status=ExtractionTaskStatus.COMPLETED, completed_time=NOW + 10)
    sync_input = _sync_input(handoff=[])

    with (
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.find_extraction_task_by_archive_id",
            AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.mark_completed",
            AsyncMock(return_value=completed),
        ) as mark_completed,
    ):
        outcome = await service.sync(sync_input, mongodb=MagicMock())

    assert outcome.outcome == RetrievalIndexSyncOutcomeKind.SUCCESS
    assert outcome.success is not None
    assert outcome.success.synced_memory_count == 0
    assert write_repo.calls == []
    mark_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_sf3_embedding_batches_size_32() -> None:
    rows = [_memory_row(f"mem-{index}") for index in range(33)]
    embedding = FakeEmbeddingClient()
    service = _service(
        read_repo=FakeRetrievalIndexReadRepository(rows=rows),
        embedding=embedding,
    )
    handoff = [
        IndexSyncMemoryEntry(
            memory_id=row.memory_id,
            core_search_text="content works_on project",
            token_count=3,
        )
        for row in rows
    ]
    processing = _processing_task()

    with (
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.find_extraction_task_by_archive_id",
            AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.mark_completed",
            AsyncMock(
                return_value=_processing_task(
                    status=ExtractionTaskStatus.COMPLETED,
                    completed_time=NOW + 10,
                )
            ),
        ),
    ):
        await service.sync(_sync_input(handoff=handoff), mongodb=MagicMock())

    assert EMBEDDING_BATCH_SIZE == 32
    assert len(embedding.batch_calls) == 2
    assert len(embedding.batch_calls[0]) == 32
    assert len(embedding.batch_calls[1]) == 1


@pytest.mark.asyncio
async def test_non_processing_aborts_without_terminal() -> None:
    service = _service()
    pending = _processing_task(status=ExtractionTaskStatus.PENDING, attempt_count=0)

    with patch(
        "memory_system.domain.services.retrieval_index_sync_service.task_repo.find_extraction_task_by_archive_id",
        AsyncMock(return_value=pending),
    ):
        outcome = await service.sync(_sync_input(), mongodb=MagicMock())

    assert isinstance(outcome, RetrievalIndexSyncAbort)


@pytest.mark.asyncio
async def test_es_failure_before_mark_completed() -> None:
    write_repo = FakeRetrievalIndexWriteRepository(fail=True)
    service = _service(write_repo=write_repo)
    processing = _processing_task()
    failed = _processing_task(status=ExtractionTaskStatus.FAILED)

    with (
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.find_extraction_task_by_archive_id",
            AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.mark_completed",
            AsyncMock(),
        ) as mark_completed,
        patch(
            "memory_system.domain.services.retrieval_index_sync_service.task_repo.mark_failed",
            AsyncMock(return_value=failed),
        ) as mark_failed,
    ):
        outcome = await service.sync(_sync_input(), mongodb=MagicMock())

    assert outcome.outcome == RetrievalIndexSyncOutcomeKind.FAILURE
    mark_failed.assert_awaited_once()
    mark_completed.assert_not_awaited()
