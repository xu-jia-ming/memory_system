"""CON-004 consolidation run orchestration models (§2.3.4, §2.3.13)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConsolidationRunStatus(StrEnum):
    SUCCESS = "success"
    READ_FAILED = "read_failed"
    WRITE_FAILED = "write_failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ConsolidationRunMetrics:
    scanned_count: int
    updated_count: int
    version_conflict_count: int
    invalid_memory_count: int
    missing_evidence_count: int
    batch_count: int
    run_duration_ms: int


@dataclass(frozen=True, slots=True)
class ConsolidationRunResult:
    run_id: str | None
    evaluation_time: int
    status: ConsolidationRunStatus
    metrics: ConsolidationRunMetrics
    error_code: str | None = None
