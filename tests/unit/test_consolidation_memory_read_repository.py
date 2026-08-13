"""Unit tests for consolidation memory read repository (CON-002 U1..U8)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from neo4j.exceptions import ServiceUnavailable

from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    Q_FETCH_CANDIDATE_BATCH,
    ConsolidationMemoryGraphDataError,
    ConsolidationMemoryReadRepository,
    ConsolidationReadError,
    authorized_read_cypher_queries,
    memory_row_from_record,
)


class FakeNode:
    def __init__(self, properties: dict[str, Any]) -> None:
        self._properties = properties

    def get(self, key: str, default: object = None) -> object:
        return self._properties.get(key, default)

    def items(self) -> Any:
        return self._properties.items()


class FakeRecord:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def data(self) -> dict[str, Any]:
        return self._data


class FakeResult:
    def __init__(self, records: list[FakeRecord]) -> None:
        self._records = records
        self._index = 0

    def __aiter__(self) -> FakeResult:
        return self

    async def __anext__(self) -> FakeRecord:
        if self._index >= len(self._records):
            raise StopAsyncIteration
        record = self._records[self._index]
        self._index += 1
        return record


def _valid_memory_props(
    memory_id: str,
    user_id: str = "user-a",
    *,
    memory_type: str = "fact",
    status: str = "active",
    created_time: int = 1_000_000,
    confidence: float = 0.85,
    memory_version: int = 1,
    latest_source_time: int | None = None,
) -> dict[str, Any]:
    return {
        "memory_id": memory_id,
        "user_id": user_id,
        "memory_type": memory_type,
        "status": status,
        "created_time": created_time,
        "confidence": confidence,
        "memory_version": memory_version,
        "latest_source_time": latest_source_time,
    }


def _memory_record(
    memory_id: str,
    archive_count: int,
    user_id: str = "user-a",
    **props: Any,
) -> FakeRecord:
    node_props = _valid_memory_props(memory_id, user_id, **props)
    return FakeRecord(
        {
            "m": FakeNode(node_props),
            "independent_archive_count": archive_count,
        },
    )


def _make_driver(records: list[FakeRecord]) -> MagicMock:
    async def fake_execute_read(callback: Any) -> Any:
        tx = MagicMock()
        tx.run = AsyncMock(return_value=FakeResult(records))
        return await callback(tx)

    session = MagicMock()
    session.execute_read = AsyncMock(side_effect=fake_execute_read)
    session.execute_write = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    driver = MagicMock()
    driver.session = MagicMock(return_value=session)
    return driver


class TestAuthorizedCypher:
    def test_c2_full_predicates_present(self) -> None:
        queries = authorized_read_cypher_queries()
        assert len(queries) == 1
        query = queries[0]
        assert query == Q_FETCH_CANDIDATE_BATCH
        normalized = " ".join(query.split()).upper()
        required_fragments = [
            "MATCH (M:MEMORY)",
            "WHERE M.USER_ID = $USER_ID",
            "M.CREATED_TIME <= $EVALUATION_TIME",
            "M.LAST_CONSOLIDATED_TIME IS NULL OR M.LAST_CONSOLIDATED_TIME < $EVALUATION_TIME",
            "$CURSOR IS NULL OR M.MEMORY_ID > $CURSOR",
            "M.STATUS IN [\"ACTIVE\", \"CONFLICTED\", \"SUPERSEDED\"]",
            "OPTIONAL MATCH (E:EVIDENCE)-[:SUPPORTS]->(M)",
            "WHERE E.USER_ID = M.USER_ID",
            "COUNT(DISTINCT E.ARCHIVE_ID) AS INDEPENDENT_ARCHIVE_COUNT",
            "ORDER BY M.MEMORY_ID ASC",
            "LIMIT $BATCH_SIZE",
        ]
        for fragment in required_fragments:
            assert fragment in normalized, f"missing fragment: {fragment}"


class TestMemoryRowFromRecord:
    def test_maps_valid_row(self) -> None:
        record = _memory_record("mem-1", 3)
        row = memory_row_from_record(record, "user-a")
        assert row.memory_id == "mem-1"
        assert row.independent_archive_count == 3
        assert row.mapping_valid is True
        assert row.memory_version == 1

    def test_u5_zero_evidence_count(self) -> None:
        record = _memory_record("mem-zero", 0)
        row = memory_row_from_record(record, "user-a")
        assert row.independent_archive_count == 0
        assert row.mapping_valid is True

    def test_user_id_mismatch_raises(self) -> None:
        record = _memory_record("mem-1", 1, user_id="user-b")
        with pytest.raises(ConsolidationMemoryGraphDataError):
            memory_row_from_record(record, "user-a")


@pytest.mark.asyncio
async def test_u1_cursor_pagination_three_batches() -> None:
    all_memories = [
        _memory_record("mem-001", 1),
        _memory_record("mem-002", 1),
        _memory_record("mem-003", 1),
    ]

    async def fake_execute_read(callback: Any) -> Any:
        tx = MagicMock()
        run_mock = AsyncMock()

        async def _run(query: str, **params: Any) -> FakeResult:
            cursor = params.get("cursor")
            batch_size = params["batch_size"]
            filtered = []
            for rec in all_memories:
                mem_id = rec.data()["m"].get("memory_id")
                if cursor is None or mem_id > cursor:
                    filtered.append(rec)
            filtered = sorted(filtered, key=lambda r: r.data()["m"].get("memory_id"))
            return FakeResult(filtered[:batch_size])

        run_mock.side_effect = _run
        tx.run = run_mock
        return await callback(tx)

    session = MagicMock()
    session.execute_read = AsyncMock(side_effect=fake_execute_read)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)

    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)

    batch1 = await repo.fetch_candidate_batch("user-a", 2_000_000, None, 2)
    assert [r.memory_id for r in batch1] == ["mem-001", "mem-002"]

    batch2 = await repo.fetch_candidate_batch("user-a", 2_000_000, "mem-002", 2)
    assert [r.memory_id for r in batch2] == ["mem-003"]

    batch3 = await repo.fetch_candidate_batch("user-a", 2_000_000, "mem-003", 2)
    assert batch3 == []


@pytest.mark.asyncio
async def test_u2_user_isolation_evidence_not_counted() -> None:
    """User A memory with count=0 even if user B evidence exists in graph (Neo4j returns 0)."""
    record = _memory_record("mem-a", 0, user_id="user-a")
    driver = _make_driver([record])
    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    rows = await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)
    assert len(rows) == 1
    assert rows[0].independent_archive_count == 0


@pytest.mark.asyncio
async def test_u3_three_distinct_archives() -> None:
    record = _memory_record("mem-1", 3)
    driver = _make_driver([record])
    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    rows = await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)
    assert rows[0].independent_archive_count == 3


@pytest.mark.asyncio
async def test_u4_dedup_same_archive() -> None:
    record = _memory_record("mem-1", 1)
    driver = _make_driver([record])
    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    rows = await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)
    assert rows[0].independent_archive_count == 1


@pytest.mark.asyncio
async def test_u5c_zero_evidence_with_other_user_evidence() -> None:
    record = _memory_record("mem-a", 0, user_id="user-a")
    driver = _make_driver([record])
    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    rows = await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)
    assert len(rows) == 1
    assert rows[0].independent_archive_count == 0


@pytest.mark.asyncio
async def test_u6_malformed_memory_returns_invalid_row() -> None:
    bad_props = _valid_memory_props("mem-bad", "user-a")
    del bad_props["memory_type"]
    record = FakeRecord(
        {
            "m": FakeNode(bad_props),
            "independent_archive_count": 2,
        },
    )
    driver = _make_driver([record])
    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    rows = await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)
    assert len(rows) == 1
    assert rows[0].memory_id == "mem-bad"
    assert rows[0].mapping_valid is False


@pytest.mark.asyncio
async def test_u6_user_id_mismatch_returns_invalid_row() -> None:
    record = _memory_record("mem-wrong", 1, user_id="user-b")
    driver = _make_driver([record])
    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    rows = await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)
    assert len(rows) == 1
    assert rows[0].mapping_valid is False


@pytest.mark.asyncio
async def test_u7_missing_archive_count_column_fails_batch() -> None:
    bad_record = FakeRecord({"m": FakeNode(_valid_memory_props("mem-1", "user-a"))})
    driver = _make_driver([bad_record])
    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    with pytest.raises(ConsolidationReadError, match="malformed"):
        await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)


@pytest.mark.asyncio
async def test_u8_service_unavailable_retryable() -> None:
    session = MagicMock()
    session.execute_read = AsyncMock(side_effect=ServiceUnavailable("down"))
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)

    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    with pytest.raises(ConsolidationReadError) as exc_info:
        await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_f1_zero_write_calls() -> None:
    driver = _make_driver([_memory_record("mem-1", 1)])
    repo = ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds=5.0)
    await repo.fetch_candidate_batch("user-a", 2_000_000, None, 10)
    session = driver.session.return_value
    session.execute_write.assert_not_called()
