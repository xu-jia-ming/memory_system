"""CON-005 production wiring helpers, metrics reset, and run assertions."""

from __future__ import annotations

from neo4j import AsyncDriver

from memory_system.domain.models.consolidation_run import (
    ConsolidationRunResult,
    ConsolidationRunStatus,
)
from memory_system.domain.models.consolidation_write import (
    ConsolidationWriteBatchRequest,
    ConsolidationWriteBatchResult,
)
from memory_system.domain.services.consolidation_batch_service import ConsolidationBatchService
from memory_system.domain.services.consolidation_run_service import ConsolidationRunService
from memory_system.domain.services.consolidation_write_service import write_batch
from memory_system.infrastructure.consolidation_mutex import ConsolidationMutex
from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationMemoryReadRepository,
)
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    ConsolidationMemoryWriteRepository,
)
from memory_system.infrastructure.neo4j.consolidation_user_enumeration_repository import (
    ConsolidationUserEnumerationRepository,
)
from memory_system.observability.metrics import CONSOLIDATION_RUNS_TOTAL
from memory_system.settings import Settings


class _WriteBatchAdapter:
    def __init__(self, repository: ConsolidationMemoryWriteRepository) -> None:
        self._repository = repository

    async def write_batch(
        self,
        request: ConsolidationWriteBatchRequest,
    ) -> ConsolidationWriteBatchResult:
        return await write_batch(request, self._repository)


def build_production_run_service(
    driver: AsyncDriver,
    settings: Settings,
    *,
    read_repo: ConsolidationMemoryReadRepository | None = None,
    write_repo: ConsolidationMemoryWriteRepository | None = None,
) -> ConsolidationRunService:
    """Mirror consolidation_worker.py wiring with optional repository injection."""
    neo4j_timeout_seconds = float(settings.memory_retrieval.neo4j_timeout_seconds)
    read_repository = read_repo or ConsolidationMemoryReadRepository(
        driver,
        neo4j_timeout_seconds=neo4j_timeout_seconds,
    )
    write_repository = write_repo or ConsolidationMemoryWriteRepository(
        driver,
        neo4j_timeout_seconds=neo4j_timeout_seconds,
    )
    enumeration_repository = ConsolidationUserEnumerationRepository(
        driver,
        neo4j_timeout_seconds=neo4j_timeout_seconds,
    )
    batch_service = ConsolidationBatchService(read_repository)
    write_service = _WriteBatchAdapter(write_repository)
    mutex = ConsolidationMutex()
    return ConsolidationRunService(
        batch_service=batch_service,
        write_service=write_service,
        enumeration_repository=enumeration_repository,
        mutex=mutex,
        settings=settings,
    )


def reset_consolidation_metrics() -> None:
    collected = list(CONSOLIDATION_RUNS_TOTAL.collect())
    if not collected:
        return
    for metric in collected[0].samples:
        if metric.name.endswith("_created"):
            continue
        CONSOLIDATION_RUNS_TOTAL.labels(status=metric.labels["status"])._value.set(0)


def metric_value(status: str) -> float:
    counter = CONSOLIDATION_RUNS_TOTAL.labels(status=status)
    return float(counter._value.get())


def assert_run_success(
    result: ConsolidationRunResult,
    *,
    expected_updated: int | None = None,
    expected_scanned: int | None = None,
    expected_version_conflicts: int | None = None,
    expected_missing_evidence: int | None = None,
) -> None:
    assert result.status == ConsolidationRunStatus.SUCCESS
    assert result.run_id is not None
    if expected_updated is not None:
        assert result.metrics.updated_count == expected_updated
    if expected_scanned is not None:
        assert result.metrics.scanned_count == expected_scanned
    if expected_version_conflicts is not None:
        assert result.metrics.version_conflict_count == expected_version_conflicts
    if expected_missing_evidence is not None:
        assert result.metrics.missing_evidence_count == expected_missing_evidence
