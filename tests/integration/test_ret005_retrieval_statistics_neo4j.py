"""Integration tests for RET-005 Neo4j retrieval statistics writes."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from neo4j import AsyncDriver
from tests.support.ret005_neo4j_fixtures import (
    MEMORY_STATS_A,
    MEMORY_STATS_B,
    USER_RET005_A,
    seed_ret005_stats_memories,
)

from memory_system.infrastructure.neo4j.retrieval_statistics_repository import (
    RetrievalStatisticsRepository,
)
from memory_system.settings import get_settings

pytest_plugins = ("tests.integration.support.neo4j_fixtures",)

CURRENT_TIME = 1_700_000_300


@pytest.fixture
async def neo4j_driver(integration_neo4j_driver: AsyncDriver) -> AsyncIterator[AsyncDriver]:
    await seed_ret005_stats_memories(integration_neo4j_driver)
    yield integration_neo4j_driver


async def _read_stats(
    driver: AsyncDriver,
    *,
    memory_id: str,
    user_id: str,
) -> tuple[int, int | None]:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            RETURN m.retrieval_count AS retrieval_count,
                   m.last_retrieved_time AS last_retrieved_time
            """,
            memory_id=memory_id,
            user_id=user_id,
        )
        record = await result.single()
        assert record is not None
        return int(record["retrieval_count"]), record["last_retrieved_time"]


@pytest.mark.asyncio
async def test_i3_stats_increment_and_monotonic_time(neo4j_driver: AsyncDriver) -> None:
    settings = get_settings()
    repo = RetrievalStatisticsRepository(
        neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )

    before_a_count, before_a_time = await _read_stats(
        neo4j_driver,
        memory_id=MEMORY_STATS_A,
        user_id=USER_RET005_A,
    )
    before_b_count, before_b_time = await _read_stats(
        neo4j_driver,
        memory_id=MEMORY_STATS_B,
        user_id=USER_RET005_A,
    )

    await repo.increment_retrieval_stats(
        user_id=USER_RET005_A,
        memory_ids=[MEMORY_STATS_A, MEMORY_STATS_B, MEMORY_STATS_A],
        current_time=CURRENT_TIME,
    )

    after_a_count, after_a_time = await _read_stats(
        neo4j_driver,
        memory_id=MEMORY_STATS_A,
        user_id=USER_RET005_A,
    )
    after_b_count, after_b_time = await _read_stats(
        neo4j_driver,
        memory_id=MEMORY_STATS_B,
        user_id=USER_RET005_A,
    )

    assert before_a_count == 2
    assert after_a_count == before_a_count + 1
    assert after_b_count == before_b_count + 1
    assert after_a_time == CURRENT_TIME
    assert after_b_time == CURRENT_TIME
    assert before_a_time is not None
    assert after_a_time >= before_a_time
    assert before_b_time is None
