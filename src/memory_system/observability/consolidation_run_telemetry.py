"""Structured logging and Prometheus helpers for consolidation runs (§2.3.13)."""

from __future__ import annotations

from typing import Literal

import structlog

from memory_system.domain.models.consolidation_run import ConsolidationRunMetrics
from memory_system.observability.metrics import CONSOLIDATION_RUNS_TOTAL

_logger = structlog.get_logger(__name__)

RunPrometheusStatus = Literal["success", "read_failed", "write_failed"]


def record_run_status(status: RunPrometheusStatus) -> None:
    CONSOLIDATION_RUNS_TOTAL.labels(status=status).inc()


def log_run_completed(
    *,
    run_id: str,
    evaluation_time: int,
    metrics: ConsolidationRunMetrics,
    status: RunPrometheusStatus,
    user_id: str | None = None,
    cursor: str | None = None,
    batch_size: int | None = None,
    error_code: str | None = None,
) -> None:
    _logger.info(
        "consolidation run completed",
        run_id=run_id,
        evaluation_time=evaluation_time,
        status=status,
        scanned_count=metrics.scanned_count,
        updated_count=metrics.updated_count,
        version_conflict_count=metrics.version_conflict_count,
        invalid_memory_count=metrics.invalid_memory_count,
        missing_evidence_count=metrics.missing_evidence_count,
        batch_count=metrics.batch_count,
        run_duration_ms=metrics.run_duration_ms,
        user_id=user_id,
        cursor=cursor,
        batch_size=batch_size,
        error_code=error_code,
    )


def log_run_failed(
    *,
    run_id: str,
    evaluation_time: int,
    metrics: ConsolidationRunMetrics,
    status: RunPrometheusStatus,
    error_code: str,
    user_id: str | None = None,
    cursor: str | None = None,
    batch_size: int | None = None,
) -> None:
    log_run_completed(
        run_id=run_id,
        evaluation_time=evaluation_time,
        metrics=metrics,
        status=status,
        user_id=user_id,
        cursor=cursor,
        batch_size=batch_size,
        error_code=error_code,
    )


def log_mutex_skipped(*, evaluation_time: int, skipped_trigger_count: int) -> None:
    _logger.info(
        "consolidation run skipped: mutex already held",
        evaluation_time=evaluation_time,
        error_code="consolidation_already_running",
        skipped_trigger_count=skipped_trigger_count,
    )


def log_unhandled_run_error(
    *,
    run_id: str,
    evaluation_time: int,
    exc: BaseException,
) -> None:
    _logger.error(
        "consolidation run unhandled error",
        run_id=run_id,
        evaluation_time=evaluation_time,
        error_type=type(exc).__name__,
        exc_info=exc,
    )
