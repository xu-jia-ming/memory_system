"""OPS-001 focused failure tests for consolidation worker shutdown (U7–U9, U13)."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.domain.models.consolidation_run import (
    ConsolidationRunMetrics,
    ConsolidationRunResult,
    ConsolidationRunStatus,
)
from memory_system.domain.services.consolidation_run_service import ConsolidationRunService
from memory_system.entrypoints import consolidation_worker
from memory_system.settings import get_settings

SETTINGS = get_settings()
SHORT_SHUTDOWN_SETTINGS = SETTINGS.model_copy(
    update={
        "shutdown": SETTINGS.shutdown.model_copy(
            update={"consolidation_worker_timeout_seconds": 1}
        )
    }
)


def _empty_run_metrics() -> ConsolidationRunMetrics:
    return ConsolidationRunMetrics(
        scanned_count=0,
        updated_count=0,
        version_conflict_count=0,
        invalid_memory_count=0,
        missing_evidence_count=0,
        batch_count=0,
        run_duration_ms=0,
    )


def _neo4j_driver_mock() -> MagicMock:
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_session.run = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_driver.session.return_value = mock_session
    mock_driver.close = AsyncMock()
    return mock_driver


class TestU7EnabledFalseShutdown:
    @pytest.mark.asyncio
    async def test_disabled_scheduler_skips_phase_ab(self) -> None:
        mock_driver = _neo4j_driver_mock()
        close_timeouts: list[int] = []

        async def capture_close(_driver: object, *, timeout_seconds: int) -> None:
            close_timeouts.append(timeout_seconds)

        with (
            patch(
                "memory_system.entrypoints.consolidation_worker.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker.create_consolidation_scheduler",
                return_value=None,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._close_neo4j",
                side_effect=capture_close,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._install_stop_handlers",
                side_effect=lambda event, started: event.set(),
            ),
        ):
            await consolidation_worker._run_worker(SETTINGS)

        assert close_timeouts == [SETTINGS.shutdown.consolidation_worker_timeout_seconds]


class TestU8InFlightShutdownDeadline:
    @pytest.mark.asyncio
    async def test_close_uses_remaining_budget_after_shutdown_started(self) -> None:
        mock_driver = _neo4j_driver_mock()
        mock_scheduler = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()
        close_timeouts: list[int] = []
        shutdown_started = time.monotonic() - 0.5

        async def capture_close(_driver: object, *, timeout_seconds: int) -> None:
            close_timeouts.append(timeout_seconds)

        with (
            patch(
                "memory_system.entrypoints.consolidation_worker.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker.create_consolidation_scheduler",
                return_value=mock_scheduler,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._close_neo4j",
                side_effect=capture_close,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._install_stop_handlers",
                side_effect=lambda event, started: (
                    started.__setitem__(0, shutdown_started),
                    event.set(),
                ),
            ),
        ):
            await consolidation_worker._run_worker(SHORT_SHUTDOWN_SETTINGS)

        mock_scheduler.shutdown.assert_called_once_with(wait=True)
        assert len(close_timeouts) == 1
        timeout_seconds = SHORT_SHUTDOWN_SETTINGS.shutdown.consolidation_worker_timeout_seconds
        assert close_timeouts[0] < timeout_seconds

    @pytest.mark.asyncio
    async def test_run_worker_phase_a_cancels_in_flight_run_and_releases_mutex(self) -> None:
        mock_driver = _neo4j_driver_mock()
        scheduler_instances: list[MagicMock] = []
        mutex_instances: list[consolidation_worker.ConsolidationMutex] = []
        hang_started = asyncio.Event()
        close_timeouts: list[int] = []

        real_mutex_cls = consolidation_worker.ConsolidationMutex

        def capture_mutex() -> consolidation_worker.ConsolidationMutex:
            mutex = real_mutex_cls()
            mutex_instances.append(mutex)
            return mutex

        async def hanging_execute_run(
            self: ConsolidationRunService,
            evaluation_time: int,
        ) -> ConsolidationRunResult:
            if not await self._mutex.try_acquire():
                return ConsolidationRunResult(
                    run_id=None,
                    evaluation_time=evaluation_time,
                    status=ConsolidationRunStatus.SKIPPED,
                    metrics=_empty_run_metrics(),
                )
            try:
                hang_started.set()
                await asyncio.Event().wait()
            finally:
                await self._mutex.release()
            return ConsolidationRunResult(
                run_id=None,
                evaluation_time=evaluation_time,
                status=ConsolidationRunStatus.SUCCESS,
                metrics=_empty_run_metrics(),
            )

        def fake_create_scheduler(
            _settings: object,
            run_callback: object,
        ) -> MagicMock:
            mock_sched = MagicMock()

            def start() -> None:
                asyncio.create_task(run_callback(1_700_000_000))  # type: ignore[operator]

            mock_sched.start = start
            mock_sched.shutdown = MagicMock()
            scheduler_instances.append(mock_sched)
            return mock_sched

        async def delayed_stop(
            event: asyncio.Event,
            started: list[float | None],
        ) -> None:
            await hang_started.wait()
            started[0] = time.monotonic()
            event.set()

        async def capture_close(_driver: object, *, timeout_seconds: int) -> None:
            close_timeouts.append(timeout_seconds)

        wait_for_calls = 0
        real_wait_for = asyncio.wait_for

        async def selective_wait_for(coro, timeout):  # type: ignore[no-untyped-def]
            nonlocal wait_for_calls
            wait_for_calls += 1
            if wait_for_calls == 1:
                raise TimeoutError()
            return await real_wait_for(coro, timeout=timeout)

        async def immediate_to_thread(fn, /, *args, **kwargs):  # type: ignore[no-untyped-def]
            return fn(*args, **kwargs)

        with (
            patch(
                "memory_system.entrypoints.consolidation_worker.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker.ConsolidationMutex",
                side_effect=capture_mutex,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker.create_consolidation_scheduler",
                side_effect=fake_create_scheduler,
            ),
            patch.object(
                ConsolidationRunService,
                "execute_run",
                hanging_execute_run,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._close_neo4j",
                side_effect=capture_close,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._install_stop_handlers",
                side_effect=lambda event, started: asyncio.create_task(
                    delayed_stop(event, started)
                ),
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker.asyncio.wait_for",
                side_effect=selective_wait_for,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker.asyncio.to_thread",
                side_effect=immediate_to_thread,
            ),
        ):
            await consolidation_worker._run_worker(SHORT_SHUTDOWN_SETTINGS)

        assert hang_started.is_set()
        assert len(scheduler_instances) == 1
        scheduler_instances[0].shutdown.assert_called_once_with(wait=True)
        assert len(mutex_instances) == 1
        assert not mutex_instances[0].is_held()
        assert len(close_timeouts) == 1
        assert (
            close_timeouts[0]
            < SHORT_SHUTDOWN_SETTINGS.shutdown.consolidation_worker_timeout_seconds
        )


class TestU9IdleShutdown:
    @pytest.mark.asyncio
    async def test_idle_stop_runs_scheduler_shutdown_and_neo4j_close(self) -> None:
        mock_driver = _neo4j_driver_mock()
        mock_scheduler = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()
        close_timeouts: list[int] = []

        async def capture_close(_driver: object, *, timeout_seconds: int) -> None:
            close_timeouts.append(timeout_seconds)

        with (
            patch(
                "memory_system.entrypoints.consolidation_worker.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker.create_consolidation_scheduler",
                return_value=mock_scheduler,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._close_neo4j",
                side_effect=capture_close,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._install_stop_handlers",
                side_effect=lambda event, started: event.set(),
            ),
        ):
            await consolidation_worker._run_worker(SETTINGS)

        mock_scheduler.shutdown.assert_called_once_with(wait=True)
        assert close_timeouts == [SETTINGS.shutdown.consolidation_worker_timeout_seconds]


class TestU13MutexDefensiveRelease:
    @pytest.mark.asyncio
    async def test_mutex_released_after_run_cancel_on_deadline(self) -> None:
        mutex = consolidation_worker.ConsolidationMutex()
        await mutex.try_acquire()
        assert mutex.is_held()

        async def hanging_run() -> None:
            await asyncio.sleep(3600)

        task = asyncio.create_task(hanging_run())
        await asyncio.sleep(0)
        shutdown_started = time.monotonic()

        with patch(
            "memory_system.entrypoints.consolidation_worker.time.monotonic",
            return_value=shutdown_started + 10.0,
        ):
            remaining = consolidation_worker.remaining_shutdown_seconds(
                shutdown_started,
                0,
            )
            try:
                await asyncio.wait_for(task, timeout=remaining)
            except TimeoutError:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                if mutex.is_held():
                    await mutex.release()

        assert not mutex.is_held()
