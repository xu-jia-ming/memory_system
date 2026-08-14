"""Unit tests for extraction_task_consumer_service C5/C6 matrix (EXT-001)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.extraction_task_consumer_service import (
    TerminalPersistError,
    process_archive_created_event,
)
from memory_system.entrypoints.extraction_worker import main as extraction_main
from memory_system.infrastructure.kafka.archive_created_consumer import (
    ArchiveCreatedKeyMismatchError,
    assert_message_key_matches_user_id,
    process_consumer_record,
)

NOW = 1_700_000_000


def _event(**overrides: object) -> ArchiveCreatedEvent:
    payload: dict[str, object] = {
        "event_id": "evt-1",
        "event_type": ARCHIVE_CREATED_EVENT_TYPE,
        "archive_id": "arch-1",
        "user_id": "user-1",
        "session_id": "sess-1",
        "created_time": NOW,
    }
    payload.update(overrides)
    return ArchiveCreatedEvent.model_validate(payload)


def _task(**overrides: object) -> MemoryExtractionTask:
    payload: dict[str, object] = {
        "task_id": "11111111-1111-4111-8111-111111111111",
        "archive_id": "arch-1",
        "user_id": "user-1",
        "status": ExtractionTaskStatus.PENDING,
        "attempt_count": 0,
        "extraction_result": None,
        "last_error": None,
        "created_time": NOW,
        "updated_time": NOW,
        "completed_time": None,
    }
    payload.update(overrides)
    return MemoryExtractionTask.model_validate(payload)


class RecordingPipeline:
    def __init__(self, decision: PipelineTerminalDecision) -> None:
        self.decision = decision
        self.calls: list[MemoryExtractionTask] = []

    async def run(
        self, task: MemoryExtractionTask, event: ArchiveCreatedEvent
    ) -> PipelineTerminalDecision:
        self.calls.append(task)
        if task.extraction_result is not None:
            # Contract: non-null extraction_result ⇒ skip LLM (Fake asserts).
            self.skipped_llm = True
        else:
            self.skipped_llm = False
        return self.decision


@pytest.mark.asyncio
async def test_completed_early_exit_no_pipeline() -> None:
    pipeline = RecordingPipeline(PipelineTerminalDecision.complete())
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new_callable=AsyncMock,
            return_value=_task(status=ExtractionTaskStatus.COMPLETED, attempt_count=1),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_processing_from_pending",
            new_callable=AsyncMock,
        ) as mark_proc,
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=pipeline,
            clock=lambda: NOW,
        )
    assert result.should_commit_offset is True
    assert pipeline.calls == []
    mark_proc.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_early_exit_no_pipeline() -> None:
    pipeline = RecordingPipeline(PipelineTerminalDecision.complete())
    with patch(
        "memory_system.domain.services.extraction_task_consumer_service.repo."
        "upsert_pending_extraction_task",
        new_callable=AsyncMock,
        return_value=_task(
            status=ExtractionTaskStatus.FAILED,
            attempt_count=1,
            last_error=ExtractionLastError(
                error_code="x", failed_stage="y", message="z"
            ),
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=pipeline,
            clock=lambda: NOW,
        )
    assert result.should_commit_offset is True
    assert pipeline.calls == []


@pytest.mark.asyncio
async def test_pending_transitions_and_port_complete() -> None:
    pipeline = RecordingPipeline(PipelineTerminalDecision.complete())
    processing = _task(status=ExtractionTaskStatus.PROCESSING, attempt_count=1)
    completed = _task(
        status=ExtractionTaskStatus.COMPLETED,
        attempt_count=1,
        completed_time=NOW + 1,
    )
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new_callable=AsyncMock,
            return_value=_task(),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_processing_from_pending",
            new_callable=AsyncMock,
            return_value=processing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_completed",
            new_callable=AsyncMock,
            return_value=completed,
        ) as mark_done,
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=pipeline,
            clock=lambda: NOW,
        )
    assert result.should_commit_offset is True
    assert len(pipeline.calls) == 1
    assert pipeline.calls[0].attempt_count == 1
    mark_done.assert_awaited_once()


@pytest.mark.asyncio
async def test_processing_recovery_bumps_attempt_skips_llm_when_result() -> None:
    pipeline = RecordingPipeline(PipelineTerminalDecision.complete())
    existing = _task(
        status=ExtractionTaskStatus.PROCESSING,
        attempt_count=1,
        extraction_result={"candidates": []},
    )
    bumped = _task(
        status=ExtractionTaskStatus.PROCESSING,
        attempt_count=2,
        extraction_result={"candidates": []},
    )
    completed = _task(
        status=ExtractionTaskStatus.COMPLETED,
        attempt_count=2,
        extraction_result={"candidates": []},
        completed_time=NOW,
    )
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new_callable=AsyncMock,
            return_value=existing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "bump_processing_attempt",
            new_callable=AsyncMock,
            return_value=bumped,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_completed",
            new_callable=AsyncMock,
            return_value=completed,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(event_id="evt-replay"),
            pipeline=pipeline,
            clock=lambda: NOW,
        )
    assert result.should_commit_offset is True
    assert pipeline.skipped_llm is True
    assert pipeline.calls[0].attempt_count == 2


@pytest.mark.asyncio
async def test_port_fail_commits_and_logs_sf004(
    capsys: pytest.CaptureFixture[str],
) -> None:
    err = ExtractionLastError(
        error_code="graph_write_failed",
        failed_stage="graph_write",
        message="boom",
    )
    pipeline = RecordingPipeline(PipelineTerminalDecision.fail(err))
    processing = _task(status=ExtractionTaskStatus.PROCESSING, attempt_count=1)
    failed = _task(
        status=ExtractionTaskStatus.FAILED,
        attempt_count=1,
        last_error=err,
        extraction_result={"keep": True},
    )
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new_callable=AsyncMock,
            return_value=_task(),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_processing_from_pending",
            new_callable=AsyncMock,
            return_value=processing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_failed",
            new_callable=AsyncMock,
            return_value=failed,
        ) as mark_failed,
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "find_extraction_task_by_archive_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=pipeline,
            clock=lambda: NOW,
        )
    assert result.should_commit_offset is True
    mark_failed.assert_awaited_once()
    # SF-004 five fields present in log message
    captured = capsys.readouterr().out
    assert failed.task_id in captured
    assert "arch-1" in captured
    assert "user-1" in captured
    assert "graph_write" in captured
    assert "attempt_count=1" in captured


@pytest.mark.asyncio
async def test_terminal_write_failure_no_commit() -> None:
    pipeline = RecordingPipeline(PipelineTerminalDecision.complete())
    processing = _task(status=ExtractionTaskStatus.PROCESSING, attempt_count=1)
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new_callable=AsyncMock,
            return_value=_task(),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_processing_from_pending",
            new_callable=AsyncMock,
            return_value=processing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_completed",
            new_callable=AsyncMock,
            side_effect=RuntimeError("mongo down"),
        ),
    ):
        with pytest.raises(TerminalPersistError):
            await process_archive_created_event(
                mongodb=AsyncMock(),
                event=_event(),
                pipeline=pipeline,
                clock=lambda: NOW,
            )


@pytest.mark.asyncio
async def test_abort_without_terminal_no_commit() -> None:
    pipeline = RecordingPipeline(PipelineTerminalDecision.abort_without_terminal())
    processing = _task(status=ExtractionTaskStatus.PROCESSING, attempt_count=1)
    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "upsert_pending_extraction_task",
            new_callable=AsyncMock,
            return_value=_task(),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_processing_from_pending",
            new_callable=AsyncMock,
            return_value=processing,
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo."
            "mark_completed",
            new_callable=AsyncMock,
        ) as mark_done,
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(),
            pipeline=pipeline,
            clock=lambda: NOW,
        )
    assert result.should_commit_offset is False
    mark_done.assert_not_awaited()


@pytest.mark.asyncio
async def test_c6_2_new_event_id_same_archive_completed_commits() -> None:
    """C6.2: new event_id, same archive_id → still one task; completed early commit."""
    pipeline = RecordingPipeline(PipelineTerminalDecision.complete())
    with patch(
        "memory_system.domain.services.extraction_task_consumer_service.repo."
        "upsert_pending_extraction_task",
        new_callable=AsyncMock,
        return_value=_task(status=ExtractionTaskStatus.COMPLETED, attempt_count=1),
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(event_id="brand-new-event"),
            pipeline=pipeline,
            clock=lambda: NOW,
        )
    assert result.should_commit_offset is True
    assert pipeline.calls == []


def test_key_mismatch_raises() -> None:
    with pytest.raises(ArchiveCreatedKeyMismatchError):
        assert_message_key_matches_user_id(b"other-user", _event())
    with pytest.raises(ArchiveCreatedKeyMismatchError):
        assert_message_key_matches_user_id(None, _event())


@pytest.mark.asyncio
async def test_process_consumer_record_key_mismatch_no_upsert() -> None:
    record = MagicRecord(key=b"wrong", value=_event().to_json_bytes())
    with patch(
        "memory_system.infrastructure.kafka.archive_created_consumer.process_archive_created_event",
        new_callable=AsyncMock,
    ) as process:
        with pytest.raises(ArchiveCreatedKeyMismatchError):
            await process_consumer_record(
                record=record,  # type: ignore[arg-type]
                mongodb=AsyncMock(),
                pipeline=RecordingPipeline(PipelineTerminalDecision.complete()),
                clock=lambda: NOW,
            )
    process.assert_not_awaited()


@pytest.mark.asyncio
async def test_c10_user_id_mismatch_keeps_existing_and_branches() -> None:
    pipeline = RecordingPipeline(PipelineTerminalDecision.complete())
    existing = _task(status=ExtractionTaskStatus.COMPLETED, user_id="original-user")
    with patch(
        "memory_system.domain.services.extraction_task_consumer_service.repo."
        "upsert_pending_extraction_task",
        new_callable=AsyncMock,
        return_value=existing,
    ):
        result = await process_archive_created_event(
            mongodb=AsyncMock(),
            event=_event(user_id="different-user"),
            pipeline=pipeline,
            clock=lambda: NOW,
        )
    assert result.should_commit_offset is True
    assert result.task is not None
    assert result.task.user_id == "original-user"


def test_extraction_worker_main_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = extraction_main()
    assert code != 0
    err = capsys.readouterr().err
    assert "EXT-002" in err or "not ready" in err
    assert "poll" in err.lower() or "refuses" in err.lower()


class MagicRecord:
    def __init__(self, *, key: bytes | None, value: bytes) -> None:
        self.key = key
        self.value = value
        self.topic = "context.archive.created"
        self.partition = 0
        self.offset = 0
