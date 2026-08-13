"""CON-005 consolidation vertical slice E2E tests on real Neo4j."""

from __future__ import annotations

import asyncio

import pytest
from neo4j import AsyncDriver

from memory_system.domain.models.consolidation_run import ConsolidationRunStatus
from memory_system.domain.services.consolidation_run_service import ConsolidationRunService
from memory_system.settings import Settings, get_settings
from tests.e2e.helpers.con005_e2e_helpers import (
    assert_run_success,
    build_production_run_service,
    metric_value,
    reset_consolidation_metrics,
)
from tests.support.con005_failure_doubles import (
    BlockingConsolidationMemoryReadRepository,
    FailingConsolidationMemoryReadRepository,
    FailingConsolidationMemoryWriteRepository,
    VersionBumpBeforeWriteRepository,
)
from tests.support.con005_neo4j_fixtures import (
    CON005_EVALUATION_TIME,
    CON005_EVALUATION_TIME_T2,
    CON005_USER_A,
    CON005_USER_B,
    MemorySeedParams,
    expected_importance_for_seed,
    read_memory_consolidation_state,
    seed_memory_no_evidence,
    seed_memory_with_evidence,
)

pytest_plugins = ("tests.integration.conftest_con005_neo4j",)
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_e2e1_happy_path_formula_and_durable_readback(
    con005_neo4j_driver: AsyncDriver,
    con005_run_service: ConsolidationRunService,
) -> None:
    reset_consolidation_metrics()
    success_before = metric_value("success")
    seed = await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-e2e1",
        user_id=CON005_USER_A,
        archive_ids=["arch-e2e1-a", "arch-e2e1-a", "arch-e2e1-b"],
    )
    before = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-e2e1",
    )
    expected = expected_importance_for_seed(
        seed,
        evaluation_time=CON005_EVALUATION_TIME,
        independent_archive_count=2,
    )
    assert before.importance != pytest.approx(expected, abs=1e-6)

    result = await con005_run_service.execute_run(CON005_EVALUATION_TIME)
    assert_run_success(
        result,
        expected_updated=1,
        expected_scanned=1,
        expected_version_conflicts=0,
        expected_missing_evidence=0,
    )
    assert metric_value("success") == success_before + 1

    after = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-e2e1",
    )
    assert after.importance == pytest.approx(expected, abs=1e-6)
    assert after.last_consolidated_time == CON005_EVALUATION_TIME
    assert after.memory_version == before.memory_version
    assert after.content == before.content
    assert after.status == before.status
    assert after.user_id == before.user_id
    assert after.memory_type == before.memory_type
    assert after.confidence == before.confidence
    assert after.created_time == before.created_time
    assert after.latest_source_time == before.latest_source_time
    assert after.updated_time == before.updated_time
    assert after.retrieval_count == before.retrieval_count


@pytest.mark.asyncio
async def test_e2e2_multi_page_batch_size_two_and_multi_user_isolation(
    con005_neo4j_driver: AsyncDriver,
    con005_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_CONSOLIDATION__BATCH_SIZE", "2")
    get_settings.cache_clear()
    settings = get_settings()
    service = build_production_run_service(con005_neo4j_driver, settings)

    for index in range(6):
        await seed_memory_with_evidence(
            con005_neo4j_driver,
            memory_id=f"mem-a-{index:02d}",
            user_id=CON005_USER_A,
            archive_ids=[f"arch-a-{index}"],
        )
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-b-only",
        user_id=CON005_USER_B,
        archive_ids=["arch-b-only"],
    )

    result = await service.execute_run(CON005_EVALUATION_TIME)
    assert_run_success(result, expected_updated=7, expected_scanned=7)
    assert result.metrics.batch_count >= 4

    for index in range(6):
        state = await read_memory_consolidation_state(
            con005_neo4j_driver,
            CON005_USER_A,
            f"mem-a-{index:02d}",
        )
        assert state.last_consolidated_time == CON005_EVALUATION_TIME

    user_b = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_B,
        "mem-b-only",
    )
    assert user_b.last_consolidated_time == CON005_EVALUATION_TIME


@pytest.mark.asyncio
async def test_e2e3_missing_evidence_skips_write(
    con005_neo4j_driver: AsyncDriver,
    con005_run_service: ConsolidationRunService,
) -> None:
    seed = await seed_memory_no_evidence(
        con005_neo4j_driver,
        memory_id="mem-missing-evidence",
        user_id=CON005_USER_A,
    )
    before = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-missing-evidence",
    )

    result = await con005_run_service.execute_run(CON005_EVALUATION_TIME)
    assert_run_success(
        result,
        expected_updated=0,
        expected_scanned=1,
        expected_missing_evidence=1,
    )

    after = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-missing-evidence",
    )
    assert after.importance == seed.importance
    assert after.last_consolidated_time is None
    assert after.memory_version == before.memory_version


@pytest.mark.asyncio
async def test_e2e4_version_conflict_partial_success(
    con005_neo4j_driver: AsyncDriver,
    con005_settings: Settings,
) -> None:
    settings = con005_settings
    timeout = float(settings.memory_retrieval.neo4j_timeout_seconds)
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-conflict-a",
        user_id=CON005_USER_A,
        archive_ids=["arch-conf-a"],
    )
    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-conflict-b",
        user_id=CON005_USER_A,
        archive_ids=["arch-conf-b"],
    )
    service = build_production_run_service(
        con005_neo4j_driver,
        settings,
        write_repo=VersionBumpBeforeWriteRepository(
            con005_neo4j_driver,
            neo4j_timeout_seconds=timeout,
            bump_memory_ids={"mem-conflict-a"},
        ),
    )

    result = await service.execute_run(CON005_EVALUATION_TIME)
    assert_run_success(
        result,
        expected_updated=1,
        expected_scanned=2,
        expected_version_conflicts=1,
    )

    conflict = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-conflict-a",
    )
    assert conflict.last_consolidated_time is None

    committed = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-conflict-b",
    )
    assert committed.last_consolidated_time == CON005_EVALUATION_TIME


@pytest.mark.asyncio
async def test_e2e5_write_read_failure_mutex_overlap_and_release(
    con005_neo4j_driver: AsyncDriver,
    con005_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_consolidation_metrics()
    settings = con005_settings
    timeout = float(settings.memory_retrieval.neo4j_timeout_seconds)

    monkeypatch.setenv("MEMORY_CONSOLIDATION__BATCH_SIZE", "1")
    get_settings.cache_clear()
    settings = get_settings()
    mutex_service = build_production_run_service(con005_neo4j_driver, settings)

    for index in range(3):
        await seed_memory_with_evidence(
            con005_neo4j_driver,
            memory_id=f"mem-write-fail-{index}",
            user_id=CON005_USER_A,
            archive_ids=[f"arch-write-{index}"],
        )

    write_fail_repo = FailingConsolidationMemoryWriteRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=timeout,
        fail_on_call=2,
    )
    write_fail_service = build_production_run_service(
        con005_neo4j_driver,
        settings,
        write_repo=write_fail_repo,
    )
    write_before = metric_value("write_failed")
    write_result = await write_fail_service.execute_run(CON005_EVALUATION_TIME)
    assert write_result.status == ConsolidationRunStatus.WRITE_FAILED
    assert metric_value("write_failed") == write_before + 1
    first = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-write-fail-0",
    )
    assert first.last_consolidated_time == CON005_EVALUATION_TIME
    second = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_A,
        "mem-write-fail-1",
    )
    assert second.last_consolidated_time is None

    write_recovery_result = await mutex_service.execute_run(CON005_EVALUATION_TIME)
    assert write_recovery_result.status == ConsolidationRunStatus.SUCCESS

    for index in range(3):
        await seed_memory_with_evidence(
            con005_neo4j_driver,
            memory_id=f"mem-read-fail-{index}",
            user_id=CON005_USER_B,
            archive_ids=[f"arch-read-{index}"],
        )
    read_fail_repo = FailingConsolidationMemoryReadRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=timeout,
        fail_on_call=2,
    )
    read_fail_service = build_production_run_service(
        con005_neo4j_driver,
        settings,
        read_repo=read_fail_repo,
    )
    read_before = metric_value("read_failed")
    read_result = await read_fail_service.execute_run(CON005_EVALUATION_TIME)
    assert read_result.status == ConsolidationRunStatus.READ_FAILED
    assert metric_value("read_failed") == read_before + 1
    assert read_result.metrics.updated_count == 1

    read_fail_first = await read_memory_consolidation_state(
        con005_neo4j_driver,
        CON005_USER_B,
        "mem-read-fail-0",
    )
    assert read_fail_first.last_consolidated_time == CON005_EVALUATION_TIME
    for index in (1, 2):
        pending = await read_memory_consolidation_state(
            con005_neo4j_driver,
            CON005_USER_B,
            f"mem-read-fail-{index}",
        )
        assert pending.last_consolidated_time is None

    read_recovery_result = await mutex_service.execute_run(CON005_EVALUATION_TIME)
    assert read_recovery_result.status == ConsolidationRunStatus.SUCCESS

    await seed_memory_with_evidence(
        con005_neo4j_driver,
        memory_id="mem-mutex-only",
        user_id=CON005_USER_A,
        archive_ids=["arch-mutex"],
    )
    entered_event = asyncio.Event()
    release_event = asyncio.Event()
    blocking_repo = BlockingConsolidationMemoryReadRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=timeout,
        entered_event=entered_event,
        release_event=release_event,
    )
    mutex_service = build_production_run_service(
        con005_neo4j_driver,
        settings,
        read_repo=blocking_repo,
    )  # fresh service with blocking read for overlap sub-scenario
    success_before_overlap = metric_value("success")

    async def blocked_run() -> None:
        await mutex_service.execute_run(CON005_EVALUATION_TIME)

    first_task = asyncio.create_task(blocked_run())
    await asyncio.wait_for(entered_event.wait(), timeout=5.0)
    overlap = await mutex_service.execute_run(CON005_EVALUATION_TIME)
    release_event.set()
    await first_task
    assert overlap.status == ConsolidationRunStatus.SKIPPED
    assert overlap.error_code == "consolidation_already_running"
    assert metric_value("success") == success_before_overlap + 1


@pytest.mark.asyncio
async def test_e2e6_partial_progress_next_run_at_t2_rescans_t1_rows(
    con005_neo4j_driver: AsyncDriver,
    con005_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Distinguish same-T retry (T1 rows with last_consolidated_time=T1 are skipped)
    from new scheduled run at T2>T1 (T1 rows are re-eligible and recomputed at T2).
    """
    monkeypatch.setenv("MEMORY_CONSOLIDATION__BATCH_SIZE", "2")
    get_settings.cache_clear()
    settings = get_settings()
    timeout = float(settings.memory_retrieval.neo4j_timeout_seconds)

    memory_ids = [f"mem-e2e6-{index}" for index in range(4)]
    seeds: dict[str, MemorySeedParams] = {}
    for memory_id in memory_ids:
        seeds[memory_id] = await seed_memory_with_evidence(
            con005_neo4j_driver,
            memory_id=memory_id,
            user_id=CON005_USER_A,
            archive_ids=[f"arch-{memory_id}"],
        )

    read_fail_repo = FailingConsolidationMemoryReadRepository(
        con005_neo4j_driver,
        neo4j_timeout_seconds=timeout,
        fail_on_call=2,
    )
    run_a_service = build_production_run_service(
        con005_neo4j_driver,
        settings,
        read_repo=read_fail_repo,
    )
    run_a = await run_a_service.execute_run(CON005_EVALUATION_TIME)
    assert run_a.status == ConsolidationRunStatus.READ_FAILED
    assert run_a.run_id is not None

    committed_ids = memory_ids[:2]
    pending_ids = memory_ids[2:]
    for memory_id in committed_ids:
        state = await read_memory_consolidation_state(
            con005_neo4j_driver,
            CON005_USER_A,
            memory_id,
        )
        assert state.last_consolidated_time == CON005_EVALUATION_TIME

    for memory_id in pending_ids:
        state = await read_memory_consolidation_state(
            con005_neo4j_driver,
            CON005_USER_A,
            memory_id,
        )
        assert state.last_consolidated_time is None

    # §6.3 #7: Run B enumerates all users with cursor=None — no persistent checkpoint.
    run_b_service = build_production_run_service(con005_neo4j_driver, settings)
    run_b = await run_b_service.execute_run(CON005_EVALUATION_TIME_T2)
    assert run_b.status == ConsolidationRunStatus.SUCCESS
    assert run_b.run_id is not None
    assert run_b.run_id != run_a.run_id
    assert run_b.metrics.scanned_count == len(memory_ids)
    assert run_b.metrics.updated_count == len(memory_ids)
    assert run_b.metrics.batch_count >= 2  # full rescan from cursor=None, not resumed checkpoint

    for memory_id in memory_ids:
        expected = expected_importance_for_seed(
            seeds[memory_id],
            evaluation_time=CON005_EVALUATION_TIME_T2,
            independent_archive_count=1,
            settings=settings,
        )
        state = await read_memory_consolidation_state(
            con005_neo4j_driver,
            CON005_USER_A,
            memory_id,
        )
        assert state.last_consolidated_time == CON005_EVALUATION_TIME_T2
        assert state.importance == pytest.approx(expected, abs=1e-6)

    assert CON005_EVALUATION_TIME_T2 > CON005_EVALUATION_TIME
