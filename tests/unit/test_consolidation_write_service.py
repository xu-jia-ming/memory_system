"""Unit tests for consolidation write service (CON-003 U10..U20, F2..F4)."""

from __future__ import annotations

import asyncio
from dataclasses import fields

import pytest

from memory_system.domain.models.consolidation_batch import ConsolidationScoredCandidate
from memory_system.domain.models.consolidation_write import (
    ConsolidationInvalidWriteCandidate,
    ConsolidationWriteBatchRequest,
    ConsolidationWriteRow,
)
from memory_system.domain.services.consolidation_write_service import (
    scored_candidates_to_write_rows,
    write_batch,
)
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    ConsolidationWriteError,
)

EVALUATION_TIME = 1_700_000_000


def _row(
    memory_id: str,
    importance: float = 0.5,
    version: int = 1,
) -> ConsolidationWriteRow:
    return ConsolidationWriteRow(
        memory_id=memory_id,
        new_importance=importance,
        expected_memory_version=version,
    )


class FakeWriteRepository:
    def __init__(self, updated_count: int = 0, *, fail: bool = False) -> None:
        self.updated_count = updated_count
        self.fail = fail
        self.calls: list[tuple[str, int, list[ConsolidationWriteRow]]] = []

    async def write_importance_batch(
        self,
        user_id: str,
        evaluation_time: int,
        rows: list[ConsolidationWriteRow],
    ) -> int:
        self.calls.append((user_id, evaluation_time, list(rows)))
        if self.fail:
            raise ConsolidationWriteError("neo4j consolidation write failed", retryable=True)
        return self.updated_count


class TestU10Handoff:
    def test_scored_candidates_to_write_rows_mapping(self) -> None:
        scored = [
            ConsolidationScoredCandidate(
                memory_id="mem-1",
                new_importance=0.77,
                memory_version=5,
            ),
            ConsolidationScoredCandidate(
                memory_id="mem-2",
                new_importance=0.33,
                memory_version=2,
            ),
        ]
        rows = scored_candidates_to_write_rows(scored)
        assert len(rows) == 2
        assert rows[0] == _row("mem-1", 0.77, 5)
        assert rows[1] == _row("mem-2", 0.33, 2)


class TestU11EvaluationTime:
    @pytest.mark.asyncio
    async def test_negative_evaluation_time_raises(self) -> None:
        repo = FakeWriteRepository()
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=-1,
            rows=[_row("mem-1")],
        )
        with pytest.raises(ValueError, match="evaluation_time"):
            await write_batch(request, repo)
        assert repo.calls == []


class TestU12DuplicateMemoryId:
    @pytest.mark.asyncio
    async def test_duplicate_memory_id_first_wins(self) -> None:
        repo = FakeWriteRepository(updated_count=1)
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[
                _row("mem-dup", 0.5, 1),
                _row("mem-dup", 0.6, 2),
            ],
        )
        result = await write_batch(request, repo)
        assert result.valid_count == 1
        assert result.updated_count == 1
        assert len(result.invalid_candidates) == 1
        assert result.invalid_candidates[0] == ConsolidationInvalidWriteCandidate(
            memory_id="mem-dup",
            reason="invalid_candidate",
        )
        assert len(repo.calls[0][2]) == 1
        assert repo.calls[0][2][0].new_importance == 0.5


class TestU13InvalidImportance:
    @pytest.mark.asyncio
    async def test_importance_above_one_invalid(self) -> None:
        repo = FakeWriteRepository()
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[_row("mem-1", 1.5)],
        )
        result = await write_batch(request, repo)
        assert result.valid_count == 0
        assert result.write_executed is False
        assert len(result.invalid_candidates) == 1
        assert repo.calls == []


class TestU14EmptyRows:
    @pytest.mark.asyncio
    async def test_empty_rows_no_write(self) -> None:
        repo = FakeWriteRepository()
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[],
        )
        result = await write_batch(request, repo)
        assert result.input_count == 0
        assert result.valid_count == 0
        assert result.updated_count == 0
        assert result.version_conflict_count == 0
        assert result.write_executed is False
        assert repo.calls == []


class TestU15AllInvalid:
    @pytest.mark.asyncio
    async def test_all_invalid_no_write(self) -> None:
        repo = FakeWriteRepository()
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[
                _row("", 0.5),
                _row("mem-bad", 2.0),
            ],
        )
        result = await write_batch(request, repo)
        assert result.valid_count == 0
        assert result.write_executed is False
        assert len(result.invalid_candidates) == 2
        assert repo.calls == []


class TestU16VersionConflictCount:
    @pytest.mark.asyncio
    async def test_version_conflict_count_aggregation(self) -> None:
        repo = FakeWriteRepository(updated_count=2)
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[
                _row("mem-1"),
                _row("mem-2"),
                _row("mem-3"),
            ],
        )
        result = await write_batch(request, repo)
        assert result.valid_count == 3
        assert result.updated_count == 2
        assert result.version_conflict_count == 1


class TestU17SkippedNeverWritten:
    def test_scored_candidates_to_write_rows_has_no_skipped_path(self) -> None:
        scored_fields = {f.name for f in fields(ConsolidationScoredCandidate)}
        assert "reason" not in scored_fields
        rows = scored_candidates_to_write_rows(
            [
                ConsolidationScoredCandidate(
                    memory_id="mem-1",
                    new_importance=0.5,
                    memory_version=1,
                ),
            ],
        )
        assert len(rows) == 1
        assert rows[0].memory_id == "mem-1"


class TestU18EmptyUserId:
    @pytest.mark.asyncio
    async def test_empty_user_id_raises_no_neo4j(self) -> None:
        repo = FakeWriteRepository()
        request = ConsolidationWriteBatchRequest(
            user_id="",
            evaluation_time=EVALUATION_TIME,
            rows=[_row("mem-1")],
        )
        with pytest.raises(ValueError, match="user_id"):
            await write_batch(request, repo)
        assert repo.calls == []


class TestU19InvalidVersionZero:
    @pytest.mark.asyncio
    async def test_version_zero_invalid_candidate(self) -> None:
        repo = FakeWriteRepository()
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[_row("mem-1", version=0)],
        )
        result = await write_batch(request, repo)
        assert result.valid_count == 0
        assert result.write_executed is False
        assert len(result.invalid_candidates) == 1
        assert repo.calls == []


class TestU20InvalidVersionNegativeOrBool:
    @pytest.mark.asyncio
    async def test_negative_version_invalid_candidate(self) -> None:
        repo = FakeWriteRepository()
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[_row("mem-1", version=-1)],
        )
        result = await write_batch(request, repo)
        assert result.valid_count == 0
        assert result.write_executed is False
        assert len(result.invalid_candidates) == 1
        assert repo.calls == []

    @pytest.mark.asyncio
    async def test_bool_version_invalid_candidate(self) -> None:
        repo = FakeWriteRepository()
        bad_row = ConsolidationWriteRow(
            memory_id="mem-1",
            new_importance=0.5,
            expected_memory_version=True,  # type: ignore[arg-type]
        )
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[bad_row],
        )
        result = await write_batch(request, repo)
        assert result.valid_count == 0
        assert result.write_executed is False
        assert len(result.invalid_candidates) == 1
        assert repo.calls == []


class TestF2RepositoryErrorPropagates:
    @pytest.mark.asyncio
    async def test_write_error_propagates(self) -> None:
        repo = FakeWriteRepository(fail=True)
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[_row("mem-1")],
        )
        with pytest.raises(ConsolidationWriteError):
            await write_batch(request, repo)


class TestF3PartialInvalidPartialValid:
    @pytest.mark.asyncio
    async def test_valid_rows_written_invalid_listed(self) -> None:
        repo = FakeWriteRepository(updated_count=1)
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[
                _row("mem-valid"),
                _row("mem-bad", 1.5),
            ],
        )
        result = await write_batch(request, repo)
        assert result.valid_count == 1
        assert result.updated_count == 1
        assert len(result.invalid_candidates) == 1
        assert result.invalid_candidates[0].memory_id == "mem-bad"
        assert len(repo.calls) == 1


class TestF4NoEsMongoKafka:
    @pytest.mark.asyncio
    async def test_success_no_external_durable_stores(self) -> None:
        repo = FakeWriteRepository(updated_count=1)
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[_row("mem-1")],
        )
        result = await write_batch(request, repo)
        assert result.write_executed is True
        assert len(repo.calls) == 1


class TestF4ConcurrentWrites:
    @pytest.mark.asyncio
    async def test_concurrent_identical_requests_consistent(self) -> None:
        repo = FakeWriteRepository(updated_count=1)
        request = ConsolidationWriteBatchRequest(
            user_id="user-a",
            evaluation_time=EVALUATION_TIME,
            rows=[_row("mem-1")],
        )
        results = await asyncio.gather(
            *[write_batch(request, repo) for _ in range(10)],
        )
        for result in results:
            assert result.updated_count == 1
            assert result.version_conflict_count == 0
        assert len(repo.calls) == 10
