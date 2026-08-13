"""CON-005 integration tests for CON-002 read repo and CON-004 user enumeration."""

from __future__ import annotations

import pytest
from neo4j import AsyncDriver
from tests.support.con005_neo4j_fixtures import (
    CON005_EVALUATION_TIME,
    CON005_USER_A,
    CON005_USER_B,
    DEFAULT_CREATED_TIME,
    seed_memory_no_evidence,
    seed_memory_with_evidence,
)

from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationMemoryReadRepository,
)
from memory_system.infrastructure.neo4j.consolidation_user_enumeration_repository import (
    ConsolidationUserEnumerationRepository,
)
from memory_system.settings import get_settings

pytest_plugins = ("tests.integration.conftest_con005_neo4j",)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_int1_read_repo_cursor_archive_count_and_user_isolation(
    con005_neo4j_driver: AsyncDriver,
) -> None:
    settings = get_settings()
    repo = ConsolidationMemoryReadRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )
    batch_size = 2

    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-a-001",
        user_id=CON005_USER_A,
        archive_ids=["arch-a-1", "arch-a-1", "arch-a-2"],
    )
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-a-002",
        user_id=CON005_USER_A,
        archive_ids=["arch-a-3"],
    )
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-a-003",
        user_id=CON005_USER_A,
        archive_ids=["arch-a-4"],
    )
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-b-cross",
        user_id=CON005_USER_B,
        archive_ids=["arch-b-only"],
    )

    page1 = await repo.fetch_candidate_batch(
        CON005_USER_A,
        CON005_EVALUATION_TIME,
        cursor=None,
        batch_size=batch_size,
    )
    assert [row.memory_id for row in page1] == ["mem-a-001", "mem-a-002"]
    assert page1[0].independent_archive_count == 2
    assert page1[1].independent_archive_count == 1

    page2 = await repo.fetch_candidate_batch(
        CON005_USER_A,
        CON005_EVALUATION_TIME,
        cursor="mem-a-002",
        batch_size=batch_size,
    )
    assert [row.memory_id for row in page2] == ["mem-a-003"]
    assert page2[0].independent_archive_count == 1

    page3 = await repo.fetch_candidate_batch(
        CON005_USER_A,
        CON005_EVALUATION_TIME,
        cursor="mem-a-003",
        batch_size=batch_size,
    )
    assert page3 == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_int2_read_repo_zero_evidence_returns_memory_with_count_zero(
    con005_neo4j_driver: AsyncDriver,
) -> None:
    settings = get_settings()
    repo = ConsolidationMemoryReadRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )
    await seed_memory_no_evidence(
        con005_neo4j_driver,
        memory_id="mem-no-evidence",
        user_id=CON005_USER_A,
    )

    rows = await repo.fetch_candidate_batch(
        CON005_USER_A,
        CON005_EVALUATION_TIME,
        cursor=None,
        batch_size=10,
    )
    assert len(rows) == 1
    assert rows[0].memory_id == "mem-no-evidence"
    assert rows[0].independent_archive_count == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_int5_user_enumeration_distinct_asc_and_candidate_predicate(
    con005_neo4j_driver: AsyncDriver,
) -> None:
    settings = get_settings()
    repo = ConsolidationUserEnumerationRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-b-001",
        user_id=CON005_USER_B,
        archive_ids=["arch-b-1"],
    )
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-a-001",
        user_id=CON005_USER_A,
        archive_ids=["arch-a-1"],
    )
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-a-old",
        user_id=CON005_USER_A,
        archive_ids=["arch-a-old"],
    )
    async with con005_neo4j_driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            SET m.last_consolidated_time = $last_consolidated_time
            """,
            memory_id="mem-a-old",
            user_id=CON005_USER_A,
            last_consolidated_time=CON005_EVALUATION_TIME,
        )

    user_ids = await repo.list_user_ids(CON005_EVALUATION_TIME)
    assert user_ids == [CON005_USER_A, CON005_USER_B]

    future_only = await repo.list_user_ids(DEFAULT_CREATED_TIME - 1)
    assert future_only == []
