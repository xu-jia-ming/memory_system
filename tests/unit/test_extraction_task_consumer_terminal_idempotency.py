"""EXT-009 consumer terminal reload and offset-gate tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.extraction_task_consumer_service import (
    TerminalPersistError,
    process_archive_created_event,
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
        "extraction_result": {"entities": [], "memories": []},
        "last_error": None,
        "created_time": NOW,
        "updated_time": NOW,
        "completed_time": None,
    }
    payload.update(overrides)
    return MemoryExtractionTask.model_validate(payload)


class _Pipeline:
    def __init__(self, decision: PipelineTerminalDecision) -> None:
        self.decision = decision

    async def run(
        self,
        task: MemoryExtractionTask,
        event: ArchiveCreatedEvent,
    ) -> PipelineTerminalDecision:
        del task, event
        return self.decision


@pytest.mark.asyncio
async def test_complete_skips_duplicate_mark_completed_after_ext007() -> None:
    processing = _task()
    durable_completed = _task(
        status=ExtractionTaskStatus.COMPLETED,
        completed_time=NOW + 1,
    )
    mark_completed = AsyncMock()

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(return_value=durable_completed),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_completed",
            new=mark_completed,
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=_Pipeline(PipelineTerminalDecision.complete()),
            clock=lambda: NOW,
        )

    assert result.should_commit_offset is True
    assert result.task == durable_completed
    mark_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_fail_skips_duplicate_mark_failed_after_ext007() -> None:
    processing = _task()
    error = ExtractionLastError(
        error_code="retrieval_index_write_failed",
        failed_stage="retrieval_index",
        message="EmbeddingServiceError",
    )
    durable_failed = _task(
        status=ExtractionTaskStatus.FAILED,
        last_error=error,
    )
    mark_failed = AsyncMock()

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(return_value=durable_failed),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            new=mark_failed,
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=_Pipeline(PipelineTerminalDecision.fail(error)),
            clock=lambda: NOW,
        )

    assert result.should_commit_offset is True
    assert result.task == durable_failed
    mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_non_terminal_reload_marks_completed_once() -> None:
    processing = _task()
    completed = _task(
        status=ExtractionTaskStatus.COMPLETED,
        completed_time=NOW + 1,
    )
    mark_completed = AsyncMock(return_value=completed)

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_completed",
            new=mark_completed,
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=_Pipeline(PipelineTerminalDecision.complete()),
            clock=lambda: NOW,
        )

    assert result.should_commit_offset is True
    assert result.task == completed
    mark_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_fail_non_terminal_reload_marks_failed_once() -> None:
    processing = _task()
    error = ExtractionLastError(
        error_code="entity_alignment_failed",
        failed_stage="entity_alignment",
        message="alignment failed",
    )
    failed = _task(
        status=ExtractionTaskStatus.FAILED,
        last_error=error,
    )
    mark_failed = AsyncMock(return_value=failed)

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            new=mark_failed,
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=_Pipeline(PipelineTerminalDecision.fail(error)),
            clock=lambda: NOW,
        )

    assert result.should_commit_offset is True
    assert result.task == failed
    mark_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_reload_type_error_fails_closed() -> None:
    processing = _task()
    reload_error = TypeError("invalid repository result")
    mark_completed = AsyncMock()
    mark_failed = AsyncMock()

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(side_effect=reload_error),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_completed",
            new=mark_completed,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            new=mark_failed,
        ),
    ):
        with pytest.raises(TerminalPersistError) as raised:
            await process_archive_created_event(
                mongodb=AsyncMock(),
                event=_event(),
                pipeline=_Pipeline(PipelineTerminalDecision.complete()),
                clock=lambda: NOW,
            )

    assert isinstance(raised.value.__cause__, TypeError)
    mark_completed.assert_not_awaited()
    mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_fail_reload_type_error_fails_closed() -> None:
    processing = _task()
    error = ExtractionLastError(
        error_code="retrieval_index_write_failed",
        failed_stage="retrieval_index",
        message="index failed",
    )
    reload_error = TypeError("invalid repository result")
    mark_completed = AsyncMock()
    mark_failed = AsyncMock()

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(side_effect=reload_error),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_completed",
            new=mark_completed,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            new=mark_failed,
        ),
    ):
        with pytest.raises(TerminalPersistError) as raised:
            await process_archive_created_event(
                mongodb=AsyncMock(),
                event=_event(),
                pipeline=_Pipeline(PipelineTerminalDecision.fail(error)),
                clock=lambda: NOW,
            )

    assert isinstance(raised.value.__cause__, TypeError)
    mark_completed.assert_not_awaited()
    mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_reload_repository_error_fails_closed() -> None:
    processing = _task()
    reload_error = RuntimeError("repository unavailable")
    mark_completed = AsyncMock()
    mark_failed = AsyncMock()

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(side_effect=reload_error),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_completed",
            new=mark_completed,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            new=mark_failed,
        ),
    ):
        with pytest.raises(TerminalPersistError) as raised:
            await process_archive_created_event(
                mongodb=AsyncMock(),
                event=_event(),
                pipeline=_Pipeline(PipelineTerminalDecision.complete()),
                clock=lambda: NOW,
            )

    assert isinstance(raised.value.__cause__, RuntimeError)
    mark_completed.assert_not_awaited()
    mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_fail_reload_repository_error_fails_closed() -> None:
    processing = _task()
    error = ExtractionLastError(
        error_code="retrieval_index_write_failed",
        failed_stage="retrieval_index",
        message="index failed",
    )
    reload_error = RuntimeError("repository unavailable")
    mark_completed = AsyncMock()
    mark_failed = AsyncMock()

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(side_effect=reload_error),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_completed",
            new=mark_completed,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            new=mark_failed,
        ),
    ):
        with pytest.raises(TerminalPersistError) as raised:
            await process_archive_created_event(
                mongodb=AsyncMock(),
                event=_event(),
                pipeline=_Pipeline(PipelineTerminalDecision.fail(error)),
                clock=lambda: NOW,
            )

    assert isinstance(raised.value.__cause__, RuntimeError)
    mark_completed.assert_not_awaited()
    mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_abort_does_not_reload_terminal_or_commit_offset() -> None:
    processing = _task()
    reload_task = AsyncMock()

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=reload_task,
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=_Pipeline(PipelineTerminalDecision.abort_without_terminal()),
            clock=lambda: NOW,
        )

    assert result.should_commit_offset is False
    reload_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_terminal_persistence_failure_raises_without_commit() -> None:
    processing = _task()
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new=AsyncMock(return_value=processing),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_completed",
            new=AsyncMock(side_effect=RuntimeError("mongo down")),
        ),
    ):
        with pytest.raises(TerminalPersistError):
            await process_archive_created_event(
                mongodb=AsyncMock(),
                event=_event(),
                pipeline=_Pipeline(PipelineTerminalDecision.complete()),
                clock=lambda: NOW,
            )
