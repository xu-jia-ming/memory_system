"""Unit tests for retrieval statistics repository (RET-005 C4 / U11)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory_system.infrastructure.neo4j.retrieval_statistics_repository import (
    Q_INCREMENT_RETRIEVAL_STATS,
    RetrievalStatisticsRepository,
    RetrievalStatisticsWriteError,
    authorized_write_cypher_queries,
)


def test_authorized_write_cypher_contains_user_id() -> None:
    queries = authorized_write_cypher_queries()
    assert Q_INCREMENT_RETRIEVAL_STATS in queries
    assert "user_id: $user_id" in Q_INCREMENT_RETRIEVAL_STATS
    assert "retrieval_count" in Q_INCREMENT_RETRIEVAL_STATS
    assert "last_retrieved_time" in Q_INCREMENT_RETRIEVAL_STATS


@pytest.mark.asyncio
async def test_increment_retrieval_stats_executes_cypher() -> None:
    tx = MagicMock()
    tx.run = AsyncMock()

    async def _execute_write(fn: Any) -> None:
        await fn(tx)

    session = MagicMock()
    session.execute_write = AsyncMock(side_effect=_execute_write)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)

    repo = RetrievalStatisticsRepository(driver, neo4j_timeout_seconds=5.0)
    await repo.increment_retrieval_stats(
        user_id="user-a",
        memory_ids=["mem-2", "mem-1", "mem-2"],
        current_time=1_700_000_000,
    )

    tx.run.assert_awaited_once()
    kwargs = tx.run.await_args.kwargs
    assert kwargs["user_id"] == "user-a"
    assert kwargs["memory_ids"] == ["mem-1", "mem-2"]
    assert kwargs["current_time"] == 1_700_000_000


@pytest.mark.asyncio
async def test_increment_retrieval_stats_empty_noop() -> None:
    driver = MagicMock()
    repo = RetrievalStatisticsRepository(driver, neo4j_timeout_seconds=5.0)
    await repo.increment_retrieval_stats(
        user_id="user-a",
        memory_ids=[],
        current_time=1,
    )
    driver.session.assert_not_called()


@pytest.mark.asyncio
async def test_increment_retrieval_stats_timeout_raises() -> None:
    session = MagicMock()
    session.execute_write = AsyncMock(side_effect=TimeoutError())
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    driver = MagicMock()
    driver.session = MagicMock(return_value=session)

    repo = RetrievalStatisticsRepository(driver, neo4j_timeout_seconds=0.001)
    with pytest.raises(RetrievalStatisticsWriteError):
        await repo.increment_retrieval_stats(
            user_id="user-a",
            memory_ids=["mem-1"],
            current_time=1,
        )
