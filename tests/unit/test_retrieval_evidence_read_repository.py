"""Unit tests for retrieval evidence read repository (RET-004 C2/C3/C4)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory_system.infrastructure.neo4j.retrieval_evidence_read_repository import (
    RetrievalEvidenceGraphDataError,
    RetrievalEvidenceReadError,
    RetrievalEvidenceReadRepository,
    authorized_read_cypher_queries,
    evidence_row_from_record,
)


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


def test_c2_authorized_cypher_queries_bind_dual_user_id() -> None:
    queries = authorized_read_cypher_queries()
    assert len(queries) == 1
    query = queries[0].upper()
    assert "$USER_ID" in query or "USER_ID" in query
    assert query.count("USER_ID") >= 2
    assert "SUPPORTS" in query
    assert "MATCH" in query
    assert "CREATE" not in query
    assert "MERGE" not in query
    assert "DELETE" not in query
    assert "SET " not in query


def test_evidence_row_from_record() -> None:
    record = FakeRecord(
        {
            "evidence_id": "ev-1",
            "memory_id": "mem-1",
            "source_time_end": 200,
            "source_message_ids": ["m1", "m2"],
        },
    )
    row = evidence_row_from_record(record)
    assert row.evidence_id == "ev-1"
    assert row.memory_id == "mem-1"
    assert row.source_time_end == 200
    assert row.source_message_ids == ["m1", "m2"]


def test_evidence_row_from_record_rejects_malformed_message_ids() -> None:
    record = FakeRecord(
        {
            "evidence_id": "ev-1",
            "memory_id": "mem-1",
            "source_time_end": 200,
            "source_message_ids": [123],
        },
    )
    with pytest.raises(RetrievalEvidenceGraphDataError):
        evidence_row_from_record(record)


@pytest.mark.asyncio
async def test_load_evidence_for_memories_fails_closed_on_malformed_row() -> None:
    malformed = FakeRecord(
        {
            "evidence_id": "ev-bad",
            "memory_id": "mem-1",
            "source_time_end": "not-an-int",
            "source_message_ids": ["m1"],
        },
    )

    async def fake_execute_read(callback: Any) -> Any:
        tx = MagicMock()
        tx.run = AsyncMock(return_value=FakeResult([malformed]))
        return await callback(tx)

    session = MagicMock()
    session.execute_read = AsyncMock(side_effect=fake_execute_read)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    driver = MagicMock()
    driver.session = MagicMock(return_value=session)

    repo = RetrievalEvidenceReadRepository(driver, neo4j_timeout_seconds=5.0)

    with pytest.raises(RetrievalEvidenceReadError, match="malformed evidence row"):
        await repo.load_evidence_for_memories("user-a", ["mem-1"])
