"""CON-003 consolidation optimistic-lock batch write orchestration (§2.3.9)."""

from __future__ import annotations

import math

from memory_system.domain.models.consolidation_batch import ConsolidationScoredCandidate
from memory_system.domain.models.consolidation_write import (
    ConsolidationInvalidWriteCandidate,
    ConsolidationWriteBatchRequest,
    ConsolidationWriteBatchResult,
    ConsolidationWriteRow,
)
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    ConsolidationMemoryWriteRepository,
)


def scored_candidates_to_write_rows(
    scored: list[ConsolidationScoredCandidate],
) -> list[ConsolidationWriteRow]:
    """Map CON-002 scored candidates to write rows. Skipped candidates must not be passed."""
    return [
        ConsolidationWriteRow(
            memory_id=candidate.memory_id,
            new_importance=candidate.new_importance,
            expected_memory_version=candidate.memory_version,
        )
        for candidate in scored
    ]


def _validate_request(request: ConsolidationWriteBatchRequest) -> None:
    if not request.user_id:
        raise ValueError("user_id must be a non-empty string")
    if request.evaluation_time < 0:
        raise ValueError("evaluation_time must be >= 0")


def _is_valid_version(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _is_valid_importance(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if not math.isfinite(float(value)):
        return False
    return 0.0 <= float(value) <= 1.0


def _partition_rows(
    rows: list[ConsolidationWriteRow],
) -> tuple[list[ConsolidationWriteRow], list[ConsolidationInvalidWriteCandidate]]:
    valid_rows: list[ConsolidationWriteRow] = []
    invalid_candidates: list[ConsolidationInvalidWriteCandidate] = []
    seen_memory_ids: set[str] = set()

    for row in rows:
        if not row.memory_id:
            invalid_candidates.append(
                ConsolidationInvalidWriteCandidate(
                    memory_id=row.memory_id,
                    reason="invalid_candidate",
                ),
            )
            continue
        if not _is_valid_version(row.expected_memory_version):
            invalid_candidates.append(
                ConsolidationInvalidWriteCandidate(
                    memory_id=row.memory_id,
                    reason="invalid_candidate",
                ),
            )
            continue
        if not _is_valid_importance(row.new_importance):
            invalid_candidates.append(
                ConsolidationInvalidWriteCandidate(
                    memory_id=row.memory_id,
                    reason="invalid_candidate",
                ),
            )
            continue
        if row.memory_id in seen_memory_ids:
            invalid_candidates.append(
                ConsolidationInvalidWriteCandidate(
                    memory_id=row.memory_id,
                    reason="invalid_candidate",
                ),
            )
            continue
        seen_memory_ids.add(row.memory_id)
        valid_rows.append(row)

    return valid_rows, invalid_candidates


async def write_batch(
    request: ConsolidationWriteBatchRequest,
    repository: ConsolidationMemoryWriteRepository,
) -> ConsolidationWriteBatchResult:
    _validate_request(request)

    input_count = len(request.rows)
    valid_rows, invalid_candidates = _partition_rows(request.rows)
    valid_count = len(valid_rows)

    if valid_count == 0:
        return ConsolidationWriteBatchResult(
            user_id=request.user_id,
            evaluation_time=request.evaluation_time,
            input_count=input_count,
            valid_count=0,
            updated_count=0,
            version_conflict_count=0,
            invalid_candidates=invalid_candidates,
            write_executed=False,
        )

    updated_count = await repository.write_importance_batch(
        user_id=request.user_id,
        evaluation_time=request.evaluation_time,
        rows=valid_rows,
    )
    version_conflict_count = valid_count - updated_count

    return ConsolidationWriteBatchResult(
        user_id=request.user_id,
        evaluation_time=request.evaluation_time,
        input_count=input_count,
        valid_count=valid_count,
        updated_count=updated_count,
        version_conflict_count=version_conflict_count,
        invalid_candidates=invalid_candidates,
        write_executed=True,
    )
