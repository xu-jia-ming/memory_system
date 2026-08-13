"""CON-005 integration tests for CON-003 optimistic-lock write repository."""

from __future__ import annotations

import pytest
from neo4j import AsyncDriver
from tests.support.con005_failure_doubles import bump_memory_version
from tests.support.con005_neo4j_fixtures import (
    CON005_EVALUATION_TIME,
    CON005_USER_A,
    expected_importance_for_seed,
    read_memory_consolidation_state,
    seed_memory_with_evidence,
)

from memory_system.domain.models.consolidation_write import (
    ConsolidationWriteBatchRequest,
    ConsolidationWriteRow,
)
from memory_system.domain.services.consolidation_write_service import write_batch
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    ConsolidationMemoryWriteRepository,
)
from memory_system.settings import get_settings

pytest_plugins = ("tests.integration.conftest_con005_neo4j",)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_int3_optimistic_write_updates_importance_and_last_consolidated_time_only(
    con005_neo4j_driver: AsyncDriver,
) -> None:
    settings = get_settings()
    repo = ConsolidationMemoryWriteRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )
    seed = await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-write-ok",
        user_id=CON005_USER_A,
        archive_ids=["arch-1", "arch-2"],
    )
    before = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-write-ok",
    )
    expected = expected_importance_for_seed(
        seed,
        evaluation_time=CON005_EVALUATION_TIME,
        independent_archive_count=2,
        settings=settings,
    )

    result = await write_batch(
        ConsolidationWriteBatchRequest(
            user_id=CON005_USER_A,
            evaluation_time=CON005_EVALUATION_TIME,
            rows=[
                ConsolidationWriteRow(
                    memory_id="mem-write-ok",
                    new_importance=expected,
                    expected_memory_version=seed.memory_version,
                )
            ],
        ),
        repo,
    )
    assert result.updated_count == 1
    assert result.version_conflict_count == 0

    after = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-write-ok",
    )
    assert after.importance == pytest.approx(expected, abs=1e-6)
    assert after.last_consolidated_time == CON005_EVALUATION_TIME
    assert after.memory_version == before.memory_version
    assert after.updated_time == before.updated_time
    assert after.content == before.content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_int4_version_conflict_leaves_row_unmodified(
    con005_neo4j_driver: AsyncDriver,
) -> None:
    settings = get_settings()
    repo = ConsolidationMemoryWriteRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )
    seed = await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-conflict",
        user_id=CON005_USER_A,
        archive_ids=["arch-conflict"],
    )
    before = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-conflict",
    )
    await bump_memory_version(
        con005_neo4j_driver,
        user_id=CON005_USER_A,
        memory_id="mem-conflict",
    )

    result = await write_batch(
        ConsolidationWriteBatchRequest(
            user_id=CON005_USER_A,
            evaluation_time=CON005_EVALUATION_TIME,
            rows=[
                ConsolidationWriteRow(
                    memory_id="mem-conflict",
                    new_importance=0.99,
                    expected_memory_version=seed.memory_version,
                )
            ],
        ),
        repo,
    )
    assert result.updated_count == 0
    assert result.version_conflict_count == 1

    after = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-conflict",
    )
    assert after.importance == before.importance
    assert after.last_consolidated_time == before.last_consolidated_time
    assert after.memory_version == before.memory_version + 1
