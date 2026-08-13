"""Unit tests for consolidation user enumeration repository (CON-004 U2b, U9b)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from neo4j.exceptions import ServiceUnavailable

from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationReadError,
)
from memory_system.infrastructure.neo4j.consolidation_user_enumeration_repository import (
    Q_LIST_USER_IDS,
    ConsolidationUserEnumerationRepository,
    authorized_enumeration_cypher_queries,
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


def _make_driver(records: list[FakeRecord]) -> MagicMock:
    async def fake_execute_read(callback: Any) -> Any:
        tx = MagicMock()
        tx.run = AsyncMock(return_value=FakeResult(records))
        return await callback(tx)

    session = MagicMock()
    session.execute_read = AsyncMock(side_effect=fake_execute_read)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    driver = MagicMock()
    driver.session.return_value = session
    return driver


class TestU2bDistinctOrdering:
    @pytest.mark.asyncio
    async def test_returns_sorted_distinct_user_ids(self) -> None:
        records = [
            FakeRecord({"user_id": "user-a"}),
            FakeRecord({"user_id": "user-b"}),
        ]
        repo = ConsolidationUserEnumerationRepository(
            _make_driver(records),
            neo4j_timeout_seconds=5.0,
        )
        assert await repo.list_user_ids(1_700_000_000) == ["user-a", "user-b"]

    def test_authorized_cypher_has_candidate_predicates(self) -> None:
        queries = authorized_enumeration_cypher_queries()
        assert len(queries) == 1
        query = queries[0]
        assert query == Q_LIST_USER_IDS
        normalized = " ".join(query.split()).upper()
        assert "RETURN DISTINCT M.USER_ID AS USER_ID" in normalized
        assert "ORDER BY M.USER_ID ASC" in normalized
        assert "M.CREATED_TIME <= $EVALUATION_TIME" in normalized
        assert "M.LAST_CONSOLIDATED_TIME IS NULL" in normalized
        assert 'M.STATUS IN ["ACTIVE", "CONFLICTED", "SUPERSEDED"]' in normalized


class TestU9bReadFailure:
    @pytest.mark.asyncio
    async def test_neo4j_failure_raises_consolidation_read_error(self) -> None:
        session = MagicMock()
        session.execute_read = AsyncMock(side_effect=ServiceUnavailable("down"))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        driver = MagicMock()
        driver.session.return_value = session

        repo = ConsolidationUserEnumerationRepository(driver, neo4j_timeout_seconds=5.0)
        with pytest.raises(ConsolidationReadError):
            await repo.list_user_ids(1_700_000_000)
