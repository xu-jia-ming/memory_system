"""Unit tests for consolidation run service (CON-004 U1..U13, U18, F2, F3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from memory_system.domain.models.consolidation_batch import (
    ConsolidationBatchRequest,
    ConsolidationBatchResult,
    ConsolidationScoredCandidate,
    ConsolidationSkippedCandidate,
)
from memory_system.domain.models.consolidation_run import ConsolidationRunStatus
from memory_system.domain.models.consolidation_write import (
    ConsolidationWriteBatchRequest,
    ConsolidationWriteBatchResult,
)
from memory_system.domain.services.consolidation_run_service import ConsolidationRunService
from memory_system.infrastructure.consolidation_mutex import ConsolidationMutex
from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationReadError,
)
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    ConsolidationWriteError,
)
from memory_system.observability.metrics import CONSOLIDATION_RUNS_TOTAL
from memory_system.settings import get_settings

SETTINGS = get_settings()
EVAL_A = 1_700_000_000
EVAL_B = 1_700_086_400
BATCH_SIZE = SETTINGS.memory_consolidation.batch_size


@dataclass
class FakeEnumerationRepository:
    user_ids: list[str]
    fail: bool = False
    calls: list[int] = field(default_factory=list)

    async def list_user_ids(self, evaluation_time: int) -> list[str]:
        self.calls.append(evaluation_time)
        if self.fail:
            raise ConsolidationReadError("enumeration failed", retryable=True)
        return list(self.user_ids)


@dataclass
class PlannedBatch:
    memories_returned: int
    scored: list[ConsolidationScoredCandidate]
    skipped: list[ConsolidationSkippedCandidate]
    has_more: bool
    next_cursor: str | None = None


@dataclass
class FakeBatchService:
    plans: dict[str, list[PlannedBatch]]
    calls: list[ConsolidationBatchRequest] = field(default_factory=list)
    fail_on_call: int | None = None
    call_count: int = 0

    async def process_batch(
        self,
        request: ConsolidationBatchRequest,
        settings: Any,
    ) -> ConsolidationBatchResult:
        self.call_count += 1
        if self.fail_on_call == self.call_count:
            raise ConsolidationReadError("batch read failed", retryable=True)
        self.calls.append(request)
        user_plan = self.plans[request.user_id]
        if not user_plan:
            raise AssertionError(f"unexpected batch for user {request.user_id}")
        planned = user_plan.pop(0)
        cursor_in = request.cursor
        next_cursor = planned.next_cursor
        if planned.has_more and next_cursor is None and planned.memories_returned > 0:
            next_cursor = f"cursor-{planned.memories_returned}"
        return ConsolidationBatchResult(
            user_id=request.user_id,
            evaluation_time=request.evaluation_time,
            cursor_in=cursor_in,
            batch_size=settings.memory_consolidation.batch_size,
            memories_returned=planned.memories_returned,
            next_cursor=next_cursor,
            scored=list(planned.scored),
            skipped=list(planned.skipped),
            has_more=planned.has_more,
        )


@dataclass
class FakeWriteService:
    updated_count: int = 1
    version_conflict_count: int = 0
    fail_on_call: int | None = None
    calls: list[ConsolidationWriteBatchRequest] = field(default_factory=list)
    call_count: int = 0
    committed_batches: list[ConsolidationWriteBatchRequest] = field(default_factory=list)

    async def write_batch(
        self,
        request: ConsolidationWriteBatchRequest,
    ) -> ConsolidationWriteBatchResult:
        self.call_count += 1
        if self.fail_on_call == self.call_count:
            raise ConsolidationWriteError("batch write failed", retryable=True)
        self.calls.append(request)
        self.committed_batches.append(request)
        return ConsolidationWriteBatchResult(
            user_id=request.user_id,
            evaluation_time=request.evaluation_time,
            input_count=len(request.rows),
            valid_count=len(request.rows),
            updated_count=self.updated_count,
            version_conflict_count=self.version_conflict_count,
            invalid_candidates=[],
            write_executed=True,
        )


def _scored(
    memory_id: str, importance: float = 0.5, version: int = 1
) -> ConsolidationScoredCandidate:
    return ConsolidationScoredCandidate(
        memory_id=memory_id,
        new_importance=importance,
        memory_version=version,
    )


def _full_page(scored: list[ConsolidationScoredCandidate], cursor: str) -> PlannedBatch:
    return PlannedBatch(
        memories_returned=BATCH_SIZE,
        scored=scored,
        skipped=[],
        has_more=True,
        next_cursor=cursor,
    )


def _terminal_page(
    scored: list[ConsolidationScoredCandidate],
    *,
    memories_returned: int | None = None,
    skipped: list[ConsolidationSkippedCandidate] | None = None,
) -> PlannedBatch:
    return PlannedBatch(
        memories_returned=memories_returned if memories_returned is not None else len(scored),
        scored=scored,
        skipped=skipped or [],
        has_more=False,
    )


def _service(
    *,
    enum_repo: FakeEnumerationRepository,
    batch_service: FakeBatchService,
    write_service: FakeWriteService,
    mutex: ConsolidationMutex | None = None,
) -> ConsolidationRunService:
    return ConsolidationRunService(
        batch_service=batch_service,  # type: ignore[arg-type]
        write_service=write_service,
        enumeration_repository=enum_repo,  # type: ignore[arg-type]
        mutex=mutex or ConsolidationMutex(),
        settings=SETTINGS,
        clock=lambda: 0.0,
    )


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    for metric in CONSOLIDATION_RUNS_TOTAL.collect()[0].samples:
        if metric.name.endswith("_created"):
            continue
        CONSOLIDATION_RUNS_TOTAL.labels(status=metric.labels["status"])._value.set(0)  # type: ignore[attr-defined]


class TestU1SingleUserPagination:
    @pytest.mark.asyncio
    async def test_multi_page_happy_path(self) -> None:
        batch_service = FakeBatchService(
            plans={
                "user-a": [
                    _full_page([_scored("mem-1")], "mem-full-1"),
                    _full_page([_scored("mem-2")], "mem-full-2"),
                    _terminal_page([_scored("mem-3")], memories_returned=1),
                ],
            },
        )
        write_service = FakeWriteService()
        service = _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=write_service,
        )
        result = await service.execute_run(EVAL_A)
        assert result.status == ConsolidationRunStatus.SUCCESS
        assert result.metrics.batch_count == 3
        assert len(batch_service.calls) == 3
        assert batch_service.calls[0].cursor is None
        assert batch_service.calls[1].cursor == "mem-full-1"
        assert batch_service.calls[2].cursor == "mem-full-2"
        assert len(write_service.calls) == 3


class TestU2MultiUser:
    @pytest.mark.asyncio
    async def test_users_processed_in_order_with_independent_cursors(self) -> None:
        batch_service = FakeBatchService(
            plans={
                "user-a": [_terminal_page([_scored("a-1")], memories_returned=1)],
                "user-b": [_terminal_page([_scored("b-1")], memories_returned=1)],
            },
        )
        write_service = FakeWriteService()
        service = _service(
            enum_repo=FakeEnumerationRepository(["user-a", "user-b"]),
            batch_service=batch_service,
            write_service=write_service,
        )
        result = await service.execute_run(EVAL_A)
        assert result.status == ConsolidationRunStatus.SUCCESS
        assert [call.user_id for call in batch_service.calls] == ["user-a", "user-b"]
        assert batch_service.calls[0].cursor is None
        assert batch_service.calls[1].cursor is None


class TestU3CursorAdvancement:
    @pytest.mark.asyncio
    async def test_has_more_advances_next_cursor(self) -> None:
        batch_service = FakeBatchService(
            plans={
                "user-a": [
                    _full_page([], "cursor-1"),
                    _terminal_page([], memories_returned=0),
                ],
            },
        )
        service = _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=FakeWriteService(),
        )
        await service.execute_run(EVAL_A)
        assert batch_service.calls[1].cursor == "cursor-1"


class TestU4EmptyEnumeration:
    @pytest.mark.asyncio
    async def test_empty_users_success_zero_scanned(self) -> None:
        service = _service(
            enum_repo=FakeEnumerationRepository([]),
            batch_service=FakeBatchService(plans={}),
            write_service=FakeWriteService(),
        )
        result = await service.execute_run(EVAL_A)
        assert result.status == ConsolidationRunStatus.SUCCESS
        assert result.metrics.scanned_count == 0
        assert result.metrics.batch_count == 0


class TestU7VersionConflictContinues:
    @pytest.mark.asyncio
    async def test_version_conflict_does_not_fail_run(self) -> None:
        batch_service = FakeBatchService(
            plans={"user-a": [_terminal_page([_scored("mem-1")], memories_returned=1)]},
        )
        write_service = FakeWriteService(updated_count=0, version_conflict_count=1)
        result = await _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=write_service,
        ).execute_run(EVAL_A)
        assert result.status == ConsolidationRunStatus.SUCCESS
        assert result.metrics.version_conflict_count == 1


class TestU8EvaluationTimePropagation:
    @pytest.mark.asyncio
    async def test_same_evaluation_time_for_all_calls(self) -> None:
        batch_service = FakeBatchService(
            plans={"user-a": [_terminal_page([_scored("mem-1")], memories_returned=1)]},
        )
        write_service = FakeWriteService()
        enum_repo = FakeEnumerationRepository(["user-a"])
        await _service(
            enum_repo=enum_repo,
            batch_service=batch_service,
            write_service=write_service,
        ).execute_run(EVAL_A)
        assert enum_repo.calls == [EVAL_A]
        assert all(call.evaluation_time == EVAL_A for call in batch_service.calls)
        assert all(call.evaluation_time == EVAL_A for call in write_service.calls)


class TestU9ReadFailure:
    @pytest.mark.asyncio
    async def test_batch_read_failure_terminates_run(self) -> None:
        batch_service = FakeBatchService(
            plans={"user-a": [_terminal_page([_scored("mem-1")], memories_returned=1)]},
            fail_on_call=1,
        )
        result = await _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=FakeWriteService(),
        ).execute_run(EVAL_A)
        assert result.status == ConsolidationRunStatus.READ_FAILED
        assert result.error_code == "consolidation_read_failed"


class TestU10WriteFailure:
    @pytest.mark.asyncio
    async def test_write_failure_preserves_prior_batches(self) -> None:
        batch_service = FakeBatchService(
            plans={
                "user-a": [
                    _full_page([_scored("mem-1")], "cursor-1"),
                    _terminal_page([_scored("mem-2")], memories_returned=1),
                ],
            },
        )
        write_service = FakeWriteService(fail_on_call=2)
        result = await _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=write_service,
        ).execute_run(EVAL_A)
        assert result.status == ConsolidationRunStatus.WRITE_FAILED
        assert len(write_service.committed_batches) == 1
        assert write_service.committed_batches[0].rows[0].memory_id == "mem-1"


class TestU11MetricsAggregation:
    @pytest.mark.asyncio
    async def test_metrics_aggregate_counts(self) -> None:
        batch_service = FakeBatchService(
            plans={
                "user-a": [
                    PlannedBatch(
                        memories_returned=2,
                        scored=[_scored("mem-1")],
                        skipped=[
                            ConsolidationSkippedCandidate("mem-x", "missing_evidence"),
                            ConsolidationSkippedCandidate("mem-y", "invalid_memory_state"),
                        ],
                        has_more=False,
                    ),
                ],
            },
        )
        write_service = FakeWriteService(updated_count=1, version_conflict_count=2)
        result = await _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=write_service,
        ).execute_run(EVAL_A)
        assert result.metrics.scanned_count == 2
        assert result.metrics.updated_count == 1
        assert result.metrics.version_conflict_count == 2
        assert result.metrics.missing_evidence_count == 1
        assert result.metrics.invalid_memory_count == 1
        assert result.metrics.batch_count == 1


class TestU12UnhandledExceptionReleasesMutex:
    @pytest.mark.asyncio
    async def test_exception_releases_mutex_for_next_run(self) -> None:
        mutex = ConsolidationMutex()

        class ExplodingEnumeration(FakeEnumerationRepository):
            async def list_user_ids(self, evaluation_time: int) -> list[str]:
                raise RuntimeError("boom")

        service = _service(
            enum_repo=ExplodingEnumeration(["user-a"]),
            batch_service=FakeBatchService(plans={}),
            write_service=FakeWriteService(),
            mutex=mutex,
        )
        await service.execute_run(EVAL_A)
        assert mutex.is_held() is False
        assert await mutex.try_acquire() is True
        await mutex.release()


class TestU13NextRunNewEvaluationTime:
    @pytest.mark.asyncio
    async def test_second_run_uses_new_evaluation_time(self) -> None:
        enum_repo = FakeEnumerationRepository(["user-a"])
        batch_service = FakeBatchService(
            plans={"user-a": [_terminal_page([_scored("mem-1")], memories_returned=1)]},
        )
        service = _service(
            enum_repo=enum_repo,
            batch_service=batch_service,
            write_service=FakeWriteService(),
        )
        await service.execute_run(EVAL_A)
        await service.execute_run(EVAL_B)
        assert enum_repo.calls == [EVAL_A, EVAL_B]


class TestU18SkippedNeverWritten:
    @pytest.mark.asyncio
    async def test_all_skip_page_does_not_call_write(self) -> None:
        batch_service = FakeBatchService(
            plans={
                "user-a": [
                    PlannedBatch(
                        memories_returned=1,
                        scored=[],
                        skipped=[
                            ConsolidationSkippedCandidate("mem-1", "missing_evidence"),
                        ],
                        has_more=False,
                    ),
                ],
            },
        )
        write_service = FakeWriteService()
        await _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=write_service,
        ).execute_run(EVAL_A)
        assert write_service.calls == []


class TestU5MutexSkipFromRunService:
    @pytest.mark.asyncio
    async def test_overlap_skips_without_run_id(self) -> None:
        mutex = ConsolidationMutex()
        await mutex.try_acquire()
        service = _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=FakeBatchService(plans={}),
            write_service=FakeWriteService(),
            mutex=mutex,
        )
        result = await service.execute_run(EVAL_A)
        assert result.run_id is None
        assert result.error_code == "consolidation_already_running"
        await mutex.release()


class TestF2ReadFailureMutexRecoverable:
    @pytest.mark.asyncio
    async def test_read_failure_then_mutex_available(self) -> None:
        mutex = ConsolidationMutex()
        batch_service = FakeBatchService(
            plans={"user-a": [_terminal_page([_scored("mem-1")], memories_returned=1)]},
            fail_on_call=1,
        )
        service = _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=FakeWriteService(),
            mutex=mutex,
        )
        await service.execute_run(EVAL_A)
        assert mutex.is_held() is False
        assert await mutex.try_acquire() is True
        await mutex.release()


class TestF3WriteFailureNoRollback:
    @pytest.mark.asyncio
    async def test_prior_write_batches_remain_committed(self) -> None:
        write_service = FakeWriteService(fail_on_call=2)
        batch_service = FakeBatchService(
            plans={
                "user-a": [
                    _full_page([_scored("mem-1")], "cursor-1"),
                    _terminal_page([_scored("mem-2")], memories_returned=1),
                ],
            },
        )
        await _service(
            enum_repo=FakeEnumerationRepository(["user-a"]),
            batch_service=batch_service,
            write_service=write_service,
        ).execute_run(EVAL_A)
        assert len(write_service.committed_batches) == 1
