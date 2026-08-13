"""Unit tests for consolidation batch service (CON-002 U5b..U15, F1..F4)."""

from __future__ import annotations

import asyncio
from dataclasses import fields
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory_system.domain.models.consolidation_batch import (
    ConsolidationBatchRequest,
    ConsolidationMemoryRow,
    ConsolidationSkippedCandidate,
)
from memory_system.domain.models.consolidation_importance import ConsolidationImportanceInput
from memory_system.domain.services.consolidation_batch_service import ConsolidationBatchService
from memory_system.domain.services.consolidation_importance import compute_consolidation_importance
from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationMemoryReadRepository,
    ConsolidationReadError,
)
from memory_system.settings import get_settings

SETTINGS = get_settings()
EVALUATION_TIME = 1_700_000_000


def _valid_row(
    memory_id: str,
    archive_count: int = 3,
    *,
    memory_type: str = "fact",
    status: str = "active",
    created_time: int = 1_000_000,
    confidence: float = 0.85,
    memory_version: int = 2,
    latest_source_time: int | None = None,
    mapping_valid: bool = True,
) -> ConsolidationMemoryRow:
    return ConsolidationMemoryRow(
        memory_id=memory_id,
        memory_version=memory_version,
        memory_type=memory_type,
        confidence=confidence,
        status=status,
        created_time=created_time,
        latest_source_time=latest_source_time,
        independent_archive_count=archive_count,
        mapping_valid=mapping_valid,
    )


class FakeRepository:
    def __init__(self, rows: list[ConsolidationMemoryRow]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, int, str | None, int]] = []

    async def fetch_candidate_batch(
        self,
        user_id: str,
        evaluation_time: int,
        cursor: str | None,
        batch_size: int,
    ) -> list[ConsolidationMemoryRow]:
        self.calls.append((user_id, evaluation_time, cursor, batch_size))
        return list(self._rows)


def _service_with_rows(rows: list[ConsolidationMemoryRow]) -> ConsolidationBatchService:
    return ConsolidationBatchService(FakeRepository(rows))


class TestU9Con001Handoff:
    @pytest.mark.asyncio
    async def test_scored_with_precise_input_fields(self) -> None:
        row = _valid_row(
            "mem-1",
            5,
            memory_type="profile",
            status="conflicted",
            created_time=900_000,
            confidence=0.9,
            latest_source_time=950_000,
            memory_version=7,
        )
        service = _service_with_rows([row])
        result = await service.process_batch(
            ConsolidationBatchRequest(
                user_id="user-a",
                evaluation_time=EVALUATION_TIME,
                cursor=None,
                batch_size=10,
            ),
            SETTINGS,
        )
        assert len(result.scored) == 1
        scored = result.scored[0]
        assert scored.memory_id == "mem-1"
        assert scored.memory_version == 7
        assert isinstance(scored.new_importance, float)

        forbidden = {"importance", "retrieval_count", "last_retrieved_time", "user_id"}
        input_fields = {f.name for f in fields(ConsolidationImportanceInput)}
        assert forbidden.isdisjoint(input_fields)

        expected_input = ConsolidationImportanceInput(
            memory_type="profile",
            confidence=0.9,
            status="conflicted",
            created_time=900_000,
            latest_source_time=950_000,
            independent_archive_count=5,
            evaluation_time=EVALUATION_TIME,
        )
        outcome = compute_consolidation_importance(
            expected_input,
            SETTINGS.memory_consolidation,
        )
        assert scored.new_importance == outcome.new_importance


class TestU5bMissingEvidence:
    @pytest.mark.asyncio
    async def test_count_zero_skipped(self) -> None:
        service = _service_with_rows([_valid_row("mem-zero", 0)])
        result = await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10),
            SETTINGS,
        )
        assert result.scored == []
        assert len(result.skipped) == 1
        assert result.skipped[0] == ConsolidationSkippedCandidate(
            memory_id="mem-zero",
            reason="missing_evidence",
        )


class TestU6bInvalidMemoryState:
    @pytest.mark.asyncio
    async def test_invalid_enum_skipped(self) -> None:
        row = _valid_row("mem-bad", 3, status="deleted")
        service = _service_with_rows([row])
        result = await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10),
            SETTINGS,
        )
        assert result.scored == []
        assert result.skipped[0].reason == "invalid_memory_state"

    @pytest.mark.asyncio
    async def test_mapping_invalid_skipped(self) -> None:
        row = _valid_row("mem-bad", 3, mapping_valid=False)
        service = _service_with_rows([row])
        result = await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10),
            SETTINGS,
        )
        assert result.skipped[0].reason == "invalid_memory_state"


class TestU10Replay:
    @pytest.mark.asyncio
    async def test_identical_results_on_repeat(self) -> None:
        rows = [_valid_row("mem-1", 2), _valid_row("mem-2", 4)]
        service = _service_with_rows(rows)
        request = ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10)
        first = await service.process_batch(request, SETTINGS)
        second = await service.process_batch(request, SETTINGS)
        assert first == second


class TestU12BatchSizeResolution:
    @pytest.mark.asyncio
    async def test_none_uses_settings_default(self) -> None:
        repo = FakeRepository([])
        service = ConsolidationBatchService(repo)
        await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, None),
            SETTINGS,
        )
        assert repo.calls[0][3] == SETTINGS.memory_consolidation.batch_size

    @pytest.mark.asyncio
    async def test_explicit_batch_size(self) -> None:
        repo = FakeRepository([])
        service = ConsolidationBatchService(repo)
        await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 100),
            SETTINGS,
        )
        assert repo.calls[0][3] == 100


class TestPaginationMetadata:
    @pytest.mark.asyncio
    async def test_u13_empty_page(self) -> None:
        service = _service_with_rows([])
        result = await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10),
            SETTINGS,
        )
        assert result.memories_returned == 0
        assert result.next_cursor is None
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_u14_partial_page(self) -> None:
        rows = [_valid_row("mem-001", 2), _valid_row("mem-002", 2)]
        service = _service_with_rows(rows)
        result = await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 5),
            SETTINGS,
        )
        assert result.memories_returned == 2
        assert result.next_cursor == "mem-002"
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_u15_full_page(self) -> None:
        rows = [_valid_row("mem-001", 2), _valid_row("mem-002", 2)]
        service = _service_with_rows(rows)
        result = await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 2),
            SETTINGS,
        )
        assert result.memories_returned == 2
        assert result.next_cursor == "mem-002"
        assert result.has_more is True


class TestU11Validation:
    @pytest.mark.asyncio
    async def test_empty_cursor_raises(self) -> None:
        service = _service_with_rows([])
        with pytest.raises(ValueError, match="cursor"):
            await service.process_batch(
                ConsolidationBatchRequest("user-a", EVALUATION_TIME, "", 10),
                SETTINGS,
            )

    @pytest.mark.asyncio
    async def test_invalid_batch_size_raises(self) -> None:
        service = _service_with_rows([])
        with pytest.raises(ValueError, match="batch_size"):
            await service.process_batch(
                ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 0),
                SETTINGS,
            )

    @pytest.mark.asyncio
    async def test_negative_evaluation_time_raises(self) -> None:
        service = _service_with_rows([])
        with pytest.raises(ValueError, match="evaluation_time"):
            await service.process_batch(
                ConsolidationBatchRequest("user-a", -1, None, 10),
                SETTINGS,
            )


class TestFailureInjection:
    @pytest.mark.asyncio
    async def test_f1_zero_write_on_success(self) -> None:
        from tests.unit.test_consolidation_memory_read_repository import (
            _make_driver,
            _memory_record,
        )

        driver = _make_driver([_memory_record("mem-1", 2)])
        repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
        service = ConsolidationBatchService(repo)
        await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10),
            SETTINGS,
        )
        session = driver.session.return_value
        session.execute_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_f2_read_failure_no_partial_scored(self) -> None:
        repo = MagicMock(spec=ConsolidationMemoryReadRepository)
        repo.fetch_candidate_batch = AsyncMock(
            side_effect=ConsolidationReadError("neo4j down", retryable=True),
        )
        service = ConsolidationBatchService(repo)
        with pytest.raises(ConsolidationReadError):
            await service.process_batch(
                ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10),
                SETTINGS,
            )

    @pytest.mark.asyncio
    async def test_f3_mixed_valid_and_malformed(self) -> None:
        rows = [
            _valid_row("mem-good", 2),
            _valid_row("mem-bad", 2, mapping_valid=False),
        ]
        service = _service_with_rows(rows)
        result = await service.process_batch(
            ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10),
            SETTINGS,
        )
        assert len(result.scored) == 1
        assert result.scored[0].memory_id == "mem-good"
        assert len(result.skipped) == 1
        assert result.skipped[0].memory_id == "mem-bad"

    @pytest.mark.asyncio
    async def test_f4_concurrent_identical_batches(self) -> None:
        rows = [_valid_row("mem-1", 3)]
        service = _service_with_rows(rows)
        request = ConsolidationBatchRequest("user-a", EVALUATION_TIME, None, 10)

        async def _run() -> Any:
            return await service.process_batch(request, SETTINGS)

        results = await asyncio.gather(*[_run() for _ in range(10)])
        first = results[0]
        for result in results[1:]:
            assert result == first
