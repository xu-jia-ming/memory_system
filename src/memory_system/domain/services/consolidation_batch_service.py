"""CON-002 consolidation batch orchestration and CON-001 handoff (§2.3.4)."""

from __future__ import annotations

from typing import cast

from memory_system.domain.models.consolidation_batch import (
    ConsolidationBatchRequest,
    ConsolidationBatchResult,
    ConsolidationMemoryRow,
    ConsolidationScoredCandidate,
    ConsolidationSkippedCandidate,
)
from memory_system.domain.models.consolidation_importance import (
    ConsolidationImportanceInput,
    ConsolidationImportanceSkip,
    ConsolidationImportanceSuccess,
    MemoryStatus,
    MemoryType,
)
from memory_system.domain.services.consolidation_importance import compute_consolidation_importance
from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationMemoryReadRepository,
)
from memory_system.settings import Settings


def _validate_request(request: ConsolidationBatchRequest, settings: Settings) -> int:
    if request.evaluation_time < 0:
        raise ValueError("evaluation_time must be >= 0")
    if request.cursor is not None and request.cursor == "":
        raise ValueError("cursor must be null or a non-empty string")
    if request.batch_size is None:
        return settings.memory_consolidation.batch_size
    if request.batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    return request.batch_size


def _build_importance_input(
    row: ConsolidationMemoryRow,
    evaluation_time: int,
) -> ConsolidationImportanceInput:
    if (
        row.memory_type is None
        or row.confidence is None
        or row.status is None
        or row.created_time is None
    ):
        raise ValueError("incomplete memory row cannot build ConsolidationImportanceInput")
    return ConsolidationImportanceInput(
        memory_type=cast(MemoryType, row.memory_type),
        confidence=row.confidence,
        status=cast(MemoryStatus, row.status),
        created_time=row.created_time,
        latest_source_time=row.latest_source_time,
        independent_archive_count=row.independent_archive_count,
        evaluation_time=evaluation_time,
    )


def _process_row(
    row: ConsolidationMemoryRow,
    evaluation_time: int,
    consolidation_settings: Settings,
) -> ConsolidationScoredCandidate | ConsolidationSkippedCandidate:
    if not row.mapping_valid:
        return ConsolidationSkippedCandidate(
            memory_id=row.memory_id,
            reason="invalid_memory_state",
        )

    try:
        importance_input = _build_importance_input(row, evaluation_time)
        outcome = compute_consolidation_importance(
            importance_input,
            consolidation_settings.memory_consolidation,
        )
    except ValueError:
        return ConsolidationSkippedCandidate(
            memory_id=row.memory_id,
            reason="invalid_memory_state",
        )

    if isinstance(outcome, ConsolidationImportanceSkip):
        return ConsolidationSkippedCandidate(
            memory_id=row.memory_id,
            reason="missing_evidence",
        )

    if isinstance(outcome, ConsolidationImportanceSuccess):
        if row.memory_version is None:
            return ConsolidationSkippedCandidate(
                memory_id=row.memory_id,
                reason="invalid_memory_state",
            )
        return ConsolidationScoredCandidate(
            memory_id=row.memory_id,
            new_importance=outcome.new_importance,
            memory_version=row.memory_version,
        )

    raise ValueError(f"unexpected consolidation importance outcome: {outcome!r}")


class ConsolidationBatchService:
    """Orchestrates consolidation candidate batch read and CON-001 importance scoring."""

    def __init__(self, repository: ConsolidationMemoryReadRepository) -> None:
        self._repository = repository

    async def process_batch(
        self,
        request: ConsolidationBatchRequest,
        settings: Settings,
    ) -> ConsolidationBatchResult:
        batch_size = _validate_request(request, settings)
        rows = await self._repository.fetch_candidate_batch(
            user_id=request.user_id,
            evaluation_time=request.evaluation_time,
            cursor=request.cursor,
            batch_size=batch_size,
        )

        scored: list[ConsolidationScoredCandidate] = []
        skipped: list[ConsolidationSkippedCandidate] = []
        for row in rows:
            outcome = _process_row(row, request.evaluation_time, settings)
            if isinstance(outcome, ConsolidationScoredCandidate):
                scored.append(outcome)
            else:
                skipped.append(outcome)

        memories_returned = len(rows)
        next_cursor = rows[-1].memory_id if memories_returned > 0 else None
        has_more = memories_returned == batch_size

        return ConsolidationBatchResult(
            user_id=request.user_id,
            evaluation_time=request.evaluation_time,
            cursor_in=request.cursor,
            batch_size=batch_size,
            memories_returned=memories_returned,
            next_cursor=next_cursor,
            scored=scored,
            skipped=skipped,
            has_more=has_more,
        )
