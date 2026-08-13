"""Unit tests for consolidation memory write repository (CON-003 U1..U9, F1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from neo4j.exceptions import ServiceUnavailable

from memory_system.domain.models.consolidation_write import ConsolidationWriteRow
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    Q_WRITE_IMPORTANCE_BATCH,
    ConsolidationMemoryWriteRepository,
    ConsolidationWriteError,
    authorized_write_cypher_queries,
)


class FakeRecord:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def data(self) -> dict[str, Any]:
        return self._data


class FakeResult:
    def __init__(self, record: FakeRecord | None) -> None:
        self._record = record

    async def single(self) -> FakeRecord | None:
        return self._record


def _write_row(
    memory_id: str,
    importance: float = 0.5,
    version: int = 1,
) -> ConsolidationWriteRow:
    return ConsolidationWriteRow(
        memory_id=memory_id,
        new_importance=importance,
        expected_memory_version=version,
    )


def _make_driver(
    updated_count: int,
    *,
    raise_on_write: Exception | None = None,
) -> MagicMock:
    captured_params: list[dict[str, Any]] = []

    async def fake_execute_write(callback: Any) -> Any:
        if raise_on_write is not None:
            raise raise_on_write
        tx = MagicMock()
        tx.run = AsyncMock(
            side_effect=lambda query, **params: _capture_and_return(
                captured_params,
                query,
                params,
                updated_count,
            ),
        )
        return await callback(tx)

    session = MagicMock()
    session.execute_write = AsyncMock(side_effect=fake_execute_write)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    driver = MagicMock()
    driver.session = MagicMock(return_value=session)
    driver.captured_params = captured_params
    return driver


def _capture_and_return(
    captured: list[dict[str, Any]],
    query: str,
    params: dict[str, Any],
    updated_count: int,
) -> FakeResult:
    captured.append({"query": query, **params})
    return FakeResult(FakeRecord({"updated_count": updated_count}))


class TestAuthorizedCypher:
    def test_c2_full_predicates_present(self) -> None:
        queries = authorized_write_cypher_queries()
        assert len(queries) == 1
        assert queries[0] == Q_WRITE_IMPORTANCE_BATCH
        normalized = " ".join(queries[0].split()).upper()
        required_fragments = [
            "UNWIND $ROWS AS ROW",
            "MATCH (M:MEMORY {MEMORY_ID: ROW.MEMORY_ID})",
            "WHERE M.USER_ID = ROW.USER_ID",
            "AND M.MEMORY_VERSION = ROW.EXPECTED_MEMORY_VERSION",
            "SET M.IMPORTANCE = ROW.IMPORTANCE",
            "M.LAST_CONSOLIDATED_TIME = $EVALUATION_TIME",
            "RETURN COUNT(M) AS UPDATED_COUNT",
        ]
        for fragment in required_fragments:
            assert fragment in normalized, f"missing fragment: {fragment}"

    def test_c3_no_memory_version_or_updated_time_set(self) -> None:
        upper = Q_WRITE_IMPORTANCE_BATCH.upper()
        assert "SET M.MEMORY_VERSION" not in upper
        assert "SET M.UPDATED_TIME" not in upper
        assert "UPDATED_TIME" not in upper.replace("LAST_CONSOLIDATED_TIME", "")


@pytest.mark.asyncio
async def test_u1_single_valid_write() -> None:
    driver = _make_driver(updated_count=1)
    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    row = _write_row("mem-1", 0.42, 3)
    count = await repo.write_importance_batch("user-a", 1_700_000_000, [row])
    assert count == 1
    params = driver.captured_params[0]
    assert params["evaluation_time"] == 1_700_000_000
    assert params["rows"] == [
        {
            "memory_id": "mem-1",
            "user_id": "user-a",
            "expected_memory_version": 3,
            "importance": 0.42,
        },
    ]


@pytest.mark.asyncio
async def test_u2_user_isolation_user_id_injected() -> None:
    driver = _make_driver(updated_count=0)
    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    row = _write_row("mem-1")
    count = await repo.write_importance_batch("user-a", 1_700_000_000, [row])
    assert count == 0
    params = driver.captured_params[0]
    assert params["rows"][0]["user_id"] == "user-a"


@pytest.mark.asyncio
async def test_u3_version_mismatch_updated_count_zero() -> None:
    driver = _make_driver(updated_count=0)
    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    row = _write_row("mem-1", version=99)
    count = await repo.write_importance_batch("user-a", 1_700_000_000, [row])
    assert count == 0


@pytest.mark.asyncio
async def test_u4_mixed_batch_partial_success() -> None:
    driver = _make_driver(updated_count=2)
    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    rows = [
        _write_row("mem-1", version=1),
        _write_row("mem-2", version=1),
        _write_row("mem-3", version=99),
    ]
    count = await repo.write_importance_batch("user-a", 1_700_000_000, rows)
    assert count == 2
    session = driver.session.return_value
    session.execute_write.assert_awaited_once()


@pytest.mark.asyncio
async def test_u6_only_importance_and_last_consolidated_time_set() -> None:
    driver = _make_driver(updated_count=1)
    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    await repo.write_importance_batch("user-a", 1_700_000_000, [_write_row("mem-1")])
    query = driver.captured_params[0]["query"]
    upper = query.upper()
    assert "SET M.IMPORTANCE" in upper
    assert "LAST_CONSOLIDATED_TIME" in upper
    assert "SET M.MEMORY_VERSION" not in upper
    assert "SET M.UPDATED_TIME" not in upper


@pytest.mark.asyncio
async def test_u7_missing_updated_count_raises() -> None:
    async def fake_execute_write(callback: Any) -> Any:
        tx = MagicMock()
        tx.run = AsyncMock(return_value=FakeResult(FakeRecord({"other": 1})))
        return await callback(tx)

    session = MagicMock()
    session.execute_write = AsyncMock(side_effect=fake_execute_write)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)

    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    with pytest.raises(ConsolidationWriteError, match="malformed"):
        await repo.write_importance_batch("user-a", 1_700_000_000, [_write_row("mem-1")])


@pytest.mark.asyncio
async def test_u8_service_unavailable_retryable() -> None:
    driver = _make_driver(updated_count=0, raise_on_write=ServiceUnavailable("down"))
    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    with pytest.raises(ConsolidationWriteError) as exc_info:
        await repo.write_importance_batch("user-a", 1_700_000_000, [_write_row("mem-1")])
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_u9_replay_same_version_twice() -> None:
    driver = _make_driver(updated_count=1)
    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    row = _write_row("mem-1", 0.6, 2)
    count1 = await repo.write_importance_batch("user-a", 1_700_000_000, [row])
    count2 = await repo.write_importance_batch("user-a", 1_700_000_000, [row])
    assert count1 == 1
    assert count2 == 1


@pytest.mark.asyncio
async def test_f1_execute_write_once_per_batch() -> None:
    driver = _make_driver(updated_count=3)
    repo = ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds=5.0)
    rows = [_write_row(f"mem-{i}") for i in range(3)]
    await repo.write_importance_batch("user-a", 1_700_000_000, rows)
    session = driver.session.return_value
    session.execute_write.assert_awaited_once()
