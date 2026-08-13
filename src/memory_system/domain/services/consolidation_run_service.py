"""CON-004 consolidation run orchestration (§2.3.11)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from memory_system.domain.models.consolidation_batch import ConsolidationBatchRequest
from memory_system.domain.models.consolidation_run import (
    ConsolidationRunMetrics,
    ConsolidationRunResult,
    ConsolidationRunStatus,
)
from memory_system.domain.models.consolidation_write import (
    ConsolidationWriteBatchRequest,
    ConsolidationWriteBatchResult,
)
from memory_system.domain.services.consolidation_batch_service import ConsolidationBatchService
from memory_system.domain.services.consolidation_write_service import (
    scored_candidates_to_write_rows,
)
from memory_system.infrastructure.consolidation_mutex import ConsolidationMutex
from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationReadError,
)
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    ConsolidationWriteError,
)
from memory_system.infrastructure.neo4j.consolidation_user_enumeration_repository import (
    ConsolidationUserEnumerationRepository,
)
from memory_system.observability.consolidation_run_telemetry import (
    RunPrometheusStatus,
    log_mutex_skipped,
    log_run_completed,
    log_run_failed,
    log_unhandled_run_error,
    record_run_status,
)
from memory_system.settings import Settings

Clock = Callable[[], float]


class WriteBatchService(Protocol):
    async def write_batch(
        self,
        request: ConsolidationWriteBatchRequest,
    ) -> ConsolidationWriteBatchResult:
        ...


def _empty_metrics() -> ConsolidationRunMetrics:
    return ConsolidationRunMetrics(
        scanned_count=0,
        updated_count=0,
        version_conflict_count=0,
        invalid_memory_count=0,
        missing_evidence_count=0,
        batch_count=0,
        run_duration_ms=0,
    )


class ConsolidationRunService:
    """Orchestrates mutex, user enumeration, per-user pagination, and CON-002/003 calls."""

    def __init__(
        self,
        *,
        batch_service: ConsolidationBatchService,
        write_service: WriteBatchService,
        enumeration_repository: ConsolidationUserEnumerationRepository,
        mutex: ConsolidationMutex,
        settings: Settings,
        clock: Clock | None = None,
    ) -> None:
        self._batch_service = batch_service
        self._write_service = write_service
        self._enumeration_repository = enumeration_repository
        self._mutex = mutex
        self._settings = settings
        self._clock = clock or time.monotonic

    async def execute_run(self, evaluation_time: int) -> ConsolidationRunResult:
        if not await self._mutex.try_acquire():
            log_mutex_skipped(
                evaluation_time=evaluation_time,
                skipped_trigger_count=self._mutex.skipped_trigger_count,
            )
            return ConsolidationRunResult(
                run_id=None,
                evaluation_time=evaluation_time,
                status=ConsolidationRunStatus.SKIPPED,
                metrics=_empty_metrics(),
                error_code="consolidation_already_running",
            )

        run_id = str(uuid4())
        start = self._clock()
        metrics = _empty_metrics()
        scanned_count = 0
        updated_count = 0
        version_conflict_count = 0
        invalid_memory_count = 0
        missing_evidence_count = 0
        batch_count = 0
        last_user_id: str | None = None
        last_cursor: str | None = None
        last_batch_size: int | None = None
        in_write_phase = False

        try:
            user_ids = await self._enumeration_repository.list_user_ids(evaluation_time)

            for user_id in user_ids:
                cursor: str | None = None
                while True:
                    batch_result = await self._batch_service.process_batch(
                        ConsolidationBatchRequest(
                            user_id=user_id,
                            evaluation_time=evaluation_time,
                            cursor=cursor,
                            batch_size=None,
                        ),
                        self._settings,
                    )
                    batch_count += 1
                    scanned_count += batch_result.memories_returned
                    invalid_memory_count += sum(
                        1 for item in batch_result.skipped if item.reason == "invalid_memory_state"
                    )
                    missing_evidence_count += sum(
                        1 for item in batch_result.skipped if item.reason == "missing_evidence"
                    )
                    last_user_id = user_id
                    last_cursor = batch_result.cursor_in
                    last_batch_size = batch_result.batch_size

                    if batch_result.scored:
                        write_result = await self._write_service.write_batch(
                            ConsolidationWriteBatchRequest(
                                user_id=user_id,
                                evaluation_time=evaluation_time,
                                rows=scored_candidates_to_write_rows(batch_result.scored),
                            ),
                        )
                        in_write_phase = True
                        updated_count += write_result.updated_count
                        version_conflict_count += write_result.version_conflict_count

                    if not batch_result.has_more:
                        break
                    cursor = batch_result.next_cursor

            run_duration_ms = int((self._clock() - start) * 1000)
            metrics = ConsolidationRunMetrics(
                scanned_count=scanned_count,
                updated_count=updated_count,
                version_conflict_count=version_conflict_count,
                invalid_memory_count=invalid_memory_count,
                missing_evidence_count=missing_evidence_count,
                batch_count=batch_count,
                run_duration_ms=run_duration_ms,
            )
            record_run_status("success")
            log_run_completed(
                run_id=run_id,
                evaluation_time=evaluation_time,
                metrics=metrics,
                status="success",
                user_id=last_user_id,
                cursor=last_cursor,
                batch_size=last_batch_size,
            )
            return ConsolidationRunResult(
                run_id=run_id,
                evaluation_time=evaluation_time,
                status=ConsolidationRunStatus.SUCCESS,
                metrics=metrics,
            )
        except ConsolidationReadError:
            return self._fail_run(
                run_id=run_id,
                evaluation_time=evaluation_time,
                status="read_failed",
                error_code="consolidation_read_failed",
                scanned_count=scanned_count,
                updated_count=updated_count,
                version_conflict_count=version_conflict_count,
                invalid_memory_count=invalid_memory_count,
                missing_evidence_count=missing_evidence_count,
                batch_count=batch_count,
                start=start,
                user_id=last_user_id,
                cursor=last_cursor,
                batch_size=last_batch_size,
            )
        except ConsolidationWriteError:
            return self._fail_run(
                run_id=run_id,
                evaluation_time=evaluation_time,
                status="write_failed",
                error_code="consolidation_write_failed",
                scanned_count=scanned_count,
                updated_count=updated_count,
                version_conflict_count=version_conflict_count,
                invalid_memory_count=invalid_memory_count,
                missing_evidence_count=missing_evidence_count,
                batch_count=batch_count,
                start=start,
                user_id=last_user_id,
                cursor=last_cursor,
                batch_size=last_batch_size,
            )
        except Exception as exc:
            log_unhandled_run_error(
                run_id=run_id,
                evaluation_time=evaluation_time,
                exc=exc,
            )
            fail_status: RunPrometheusStatus = (
                "write_failed" if in_write_phase else "read_failed"
            )
            error_code = (
                "consolidation_write_failed"
                if fail_status == "write_failed"
                else "consolidation_read_failed"
            )
            return self._fail_run(
                run_id=run_id,
                evaluation_time=evaluation_time,
                status=fail_status,
                error_code=error_code,
                scanned_count=scanned_count,
                updated_count=updated_count,
                version_conflict_count=version_conflict_count,
                invalid_memory_count=invalid_memory_count,
                missing_evidence_count=missing_evidence_count,
                batch_count=batch_count,
                start=start,
                user_id=last_user_id,
                cursor=last_cursor,
                batch_size=last_batch_size,
            )
        finally:
            await self._mutex.release()

    def _fail_run(
        self,
        *,
        run_id: str,
        evaluation_time: int,
        status: RunPrometheusStatus,
        error_code: str,
        scanned_count: int,
        updated_count: int,
        version_conflict_count: int,
        invalid_memory_count: int,
        missing_evidence_count: int,
        batch_count: int,
        start: float,
        user_id: str | None,
        cursor: str | None,
        batch_size: int | None,
    ) -> ConsolidationRunResult:
        run_duration_ms = int((self._clock() - start) * 1000)
        metrics = ConsolidationRunMetrics(
            scanned_count=scanned_count,
            updated_count=updated_count,
            version_conflict_count=version_conflict_count,
            invalid_memory_count=invalid_memory_count,
            missing_evidence_count=missing_evidence_count,
            batch_count=batch_count,
            run_duration_ms=run_duration_ms,
        )
        record_run_status(status)
        log_run_failed(
            run_id=run_id,
            evaluation_time=evaluation_time,
            metrics=metrics,
            status=status,
            error_code=error_code,
            user_id=user_id,
            cursor=cursor,
            batch_size=batch_size,
        )
        run_status = (
            ConsolidationRunStatus.READ_FAILED
            if status == "read_failed"
            else ConsolidationRunStatus.WRITE_FAILED
        )
        return ConsolidationRunResult(
            run_id=run_id,
            evaluation_time=evaluation_time,
            status=run_status,
            metrics=metrics,
            error_code=error_code,
        )
