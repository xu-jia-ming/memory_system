"""Archive-created consumption service: §2.1.4 branches + Offset gate (EXT-001 C5)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import structlog
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import (
    ExtractionTaskStatus,
    PipelineTerminalKind,
)
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_task import (
    MemoryExtractionTask,
    ProcessArchiveCreatedResult,
)
from memory_system.domain.services.extraction_pipeline_port import (
    ExtractionPipelinePort,
    PipelineTerminalDecision,
)
from memory_system.infrastructure.mongodb import extraction_task_repository as repo
from memory_system.observability.metrics import record_extraction_terminal

Clock = Callable[[], int]
_logger = structlog.get_logger(__name__)


class TerminalPersistError(RuntimeError):
    """Raised when terminal Mongo persistence fails; callers must not commit offset."""


def _log_failed_task(
    log: structlog.stdlib.BoundLogger,
    *,
    task: MemoryExtractionTask,
    failed_stage: str,
    session_id: str | None = None,
) -> None:
    """SF-004: failed-path logs must include the five required fields."""
    log.error(
        "extraction task failed",
        task_id=task.task_id,
        archive_id=task.archive_id,
        user_id=task.user_id,
        failed_stage=failed_stage,
        attempt_count=task.attempt_count,
        session_id=session_id,
    )


async def process_archive_created_event(
    *,
    mongodb: AsyncMongoClient[Any],
    event: ArchiveCreatedEvent,
    pipeline: ExtractionPipelinePort,
    clock: Clock,
    logger: structlog.stdlib.BoundLogger | None = None,
) -> ProcessArchiveCreatedResult:
    """Apply C5 status branches; commit offset only after terminal Mongo success.

    Preconditions: caller already validated consumer-boundary (C4) and key (C3.1).
    """
    log = logger or _logger
    now = clock()
    processing_started = time.perf_counter()

    task = await repo.upsert_pending_extraction_task(
        mongodb,
        archive_id=event.archive_id,
        user_id=event.user_id,
        now=now,
    )

    if task.user_id != event.user_id:
        # OI-EXT-001-003 / C10: do not overwrite user_id; continue by existing status.
        log.warning(
            "extraction task user_id mismatch",
            archive_id=task.archive_id,
            task_user_id=task.user_id,
            event_user_id=event.user_id,
        )

    if task.status == ExtractionTaskStatus.COMPLETED:
        return ProcessArchiveCreatedResult(should_commit_offset=True, task=task)

    if task.status == ExtractionTaskStatus.FAILED:
        return ProcessArchiveCreatedResult(should_commit_offset=True, task=task)

    if task.status == ExtractionTaskStatus.PENDING:
        transitioned = await repo.mark_processing_from_pending(
            mongodb,
            archive_id=task.archive_id,
            now=clock(),
        )
        if transitioned is None:
            # Concurrent status change — reload and re-branch without inventing paths.
            reloaded = await repo.find_extraction_task_by_archive_id(mongodb, task.archive_id)
            if reloaded is None:
                raise RuntimeError(f"task vanished archive_id={task.archive_id}")
            if reloaded.status == ExtractionTaskStatus.COMPLETED:
                return ProcessArchiveCreatedResult(should_commit_offset=True, task=reloaded)
            if reloaded.status == ExtractionTaskStatus.FAILED:
                return ProcessArchiveCreatedResult(should_commit_offset=True, task=reloaded)
            if reloaded.status == ExtractionTaskStatus.PROCESSING:
                bumped = await repo.bump_processing_attempt(
                    mongodb,
                    archive_id=reloaded.archive_id,
                    now=clock(),
                )
                task = bumped or reloaded
            else:
                raise RuntimeError(
                    f"unexpected status after pending race archive_id={task.archive_id} "
                    f"status={reloaded.status}"
                )
        else:
            task = transitioned
    elif task.status == ExtractionTaskStatus.PROCESSING:
        bumped = await repo.bump_processing_attempt(
            mongodb,
            archive_id=task.archive_id,
            now=clock(),
        )
        if bumped is None:
            reloaded = await repo.find_extraction_task_by_archive_id(mongodb, task.archive_id)
            if reloaded is None:
                raise RuntimeError(f"task vanished archive_id={task.archive_id}")
            if reloaded.status == ExtractionTaskStatus.COMPLETED:
                return ProcessArchiveCreatedResult(should_commit_offset=True, task=reloaded)
            if reloaded.status == ExtractionTaskStatus.FAILED:
                return ProcessArchiveCreatedResult(should_commit_offset=True, task=reloaded)
            task = reloaded
        else:
            task = bumped
    else:
        raise RuntimeError(f"unknown extraction task status={task.status}")

    decision: PipelineTerminalDecision = await pipeline.run(task, event)

    if decision.kind == PipelineTerminalKind.ABORT_WITHOUT_TERMINAL:
        return ProcessArchiveCreatedResult(should_commit_offset=False, task=task)

    duration_seconds = time.perf_counter() - processing_started

    if decision.kind == PipelineTerminalKind.COMPLETE:
        try:
            reloaded = await repo.find_extraction_task_by_archive_id(
                mongodb,
                task.archive_id,
            )
        except Exception as exc:
            raise TerminalPersistError(
                f"terminal completed reload failed archive_id={task.archive_id}"
            ) from exc
        if reloaded is not None and reloaded.status == ExtractionTaskStatus.COMPLETED:
            record_extraction_terminal(status="completed", duration_seconds=duration_seconds)
            return ProcessArchiveCreatedResult(should_commit_offset=True, task=reloaded)
        try:
            completed = await repo.mark_completed(
                mongodb,
                archive_id=task.archive_id,
                now=clock(),
            )
        except Exception as exc:
            raise TerminalPersistError(
                f"terminal completed write failed archive_id={task.archive_id}"
            ) from exc
        record_extraction_terminal(status="completed", duration_seconds=duration_seconds)
        return ProcessArchiveCreatedResult(should_commit_offset=True, task=completed)

    if decision.kind == PipelineTerminalKind.FAIL:
        assert decision.last_error is not None
        try:
            reloaded = await repo.find_extraction_task_by_archive_id(
                mongodb,
                task.archive_id,
            )
        except Exception as exc:
            raise TerminalPersistError(
                f"terminal failed reload failed archive_id={task.archive_id}"
            ) from exc
        if reloaded is not None and reloaded.status == ExtractionTaskStatus.FAILED:
            record_extraction_terminal(status="failed", duration_seconds=duration_seconds)
            return ProcessArchiveCreatedResult(should_commit_offset=True, task=reloaded)
        try:
            failed = await repo.mark_failed(
                mongodb,
                archive_id=task.archive_id,
                last_error=decision.last_error,
                now=clock(),
            )
        except Exception as exc:
            raise TerminalPersistError(
                f"terminal failed write failed archive_id={task.archive_id}"
            ) from exc
        _log_failed_task(
            log,
            task=failed,
            failed_stage=decision.last_error.failed_stage,
            session_id=event.session_id,
        )
        record_extraction_terminal(status="failed", duration_seconds=duration_seconds)
        return ProcessArchiveCreatedResult(should_commit_offset=True, task=failed)

    raise RuntimeError(f"unknown pipeline decision kind={decision.kind}")
