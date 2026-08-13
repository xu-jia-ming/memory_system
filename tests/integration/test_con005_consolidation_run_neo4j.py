"""CON-005 integration smoke for ConsolidationRunService on real Neo4j (INT-6)."""

from __future__ import annotations

import pytest
from neo4j import AsyncDriver
from tests.e2e.helpers.con005_e2e_helpers import assert_run_success, reset_consolidation_metrics
from tests.support.con005_neo4j_fixtures import (
    CON005_EVALUATION_TIME,
    CON005_USER_A,
    expected_importance_for_seed,
    read_memory_consolidation_state,
    seed_memory_with_evidence,
)

from memory_system.domain.models.consolidation_run import ConsolidationRunStatus
from memory_system.domain.services.consolidation_run_service import ConsolidationRunService

pytest_plugins = ("tests.integration.conftest_con005_neo4j",)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_int6_run_service_single_user_happy_path(
    con005_neo4j_driver: AsyncDriver,
    con005_run_service: ConsolidationRunService,
) -> None:
    reset_consolidation_metrics()
    seed = await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-int6",
        user_id=CON005_USER_A,
        archive_ids=["arch-int6-a", "arch-int6-b"],
    )
    before = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-int6",
    )
    expected = expected_importance_for_seed(
        seed,
        evaluation_time=CON005_EVALUATION_TIME,
        independent_archive_count=2,
    )

    result = await con005_run_service.execute_run(CON005_EVALUATION_TIME)
    assert result.status == ConsolidationRunStatus.SUCCESS
    assert_run_success(result, expected_updated=1, expected_scanned=1)

    after = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-int6",
    )
    assert after.importance == pytest.approx(expected, abs=1e-6)
    assert after.last_consolidated_time == CON005_EVALUATION_TIME
    assert after.memory_version == before.memory_version
    assert after.content == before.content
