"""OPS-001 focused failure tests for extraction worker shutdown (U3, U5, U6)."""

from __future__ import annotations

import asyncio
import signal
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.entrypoints import extraction_worker
from memory_system.settings import get_settings

SETTINGS = get_settings()


class TestU3StopHandlers:
    def test_install_stop_handlers_sets_event_and_monotonic(self) -> None:
        stop_event = asyncio.Event()
        shutdown_started: list[float | None] = [None]
        loop = MagicMock()
        handlers: dict[int, object] = {}

        def add_signal_handler(signum: int, callback: object) -> None:
            handlers[signum] = callback

        loop.add_signal_handler = add_signal_handler

        with patch(
            "memory_system.entrypoints.extraction_worker.asyncio.get_running_loop",
            return_value=loop,
        ):
            extraction_worker._install_stop_handlers(stop_event, shutdown_started)

        assert signal.SIGTERM in handlers
        assert signal.SIGINT in handlers
        before = time.monotonic()
        handlers[signal.SIGTERM]()  # type: ignore[operator]
        assert stop_event.is_set()
        assert shutdown_started[0] is not None
        assert shutdown_started[0] >= before


class TestU5InFlightShutdownDeadline:
    @pytest.mark.asyncio
    async def test_close_uses_remaining_budget_after_in_flight_timeout(self) -> None:
        mock_consumer = MagicMock()
        mock_consumer.start = AsyncMock()
        mock_consumer.stop = AsyncMock()

        mock_mongo = MagicMock()
        mock_mongo.admin.command = AsyncMock(return_value={"ok": 1})
        mock_mongo.close = AsyncMock()

        mock_session = MagicMock()
        mock_session.run = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_neo4j = MagicMock()
        mock_neo4j.session.return_value = mock_session
        mock_neo4j.close = AsyncMock()

        mock_es = MagicMock()
        mock_es.info = AsyncMock(return_value={})
        mock_es.close = AsyncMock()

        mock_http = MagicMock()
        mock_http.aclose = AsyncMock()

        close_timeouts: list[int] = []
        shutdown_started = time.monotonic() - 5.0

        async def fake_consumer_loop(**kwargs: object) -> int:
            assert kwargs.get("get_shutdown_started") is not None
            assert kwargs.get("shutdown_timeout_seconds") == (
                SETTINGS.shutdown.extraction_worker_timeout_seconds
            )
            return 0

        async def capture_close(**kwargs: object) -> None:
            close_timeouts.append(kwargs["timeout_seconds"])  # type: ignore[index]

        with (
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncMongoClient",
                return_value=mock_mongo,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncGraphDatabase.driver",
                return_value=mock_neo4j,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncElasticsearch",
                return_value=mock_es,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.httpx.AsyncClient",
                return_value=mock_http,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.create_archive_created_consumer",
                return_value=mock_consumer,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.create_production_extraction_pipeline",
                return_value=MagicMock(),
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.run_archive_created_consumer_loop",
                side_effect=fake_consumer_loop,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker._close_worker_resources",
                side_effect=capture_close,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker._install_stop_handlers",
                side_effect=lambda event, started: (
                    started.__setitem__(0, shutdown_started),
                    event.set(),
                ),
            ),
        ):
            await extraction_worker._run_worker(SETTINGS)

        assert len(close_timeouts) == 1
        assert close_timeouts[0] < SETTINGS.shutdown.extraction_worker_timeout_seconds
        assert close_timeouts[0] <= 266


class TestU6IdleShutdown:
    @pytest.mark.asyncio
    async def test_idle_stop_close_uses_full_budget(self) -> None:
        close_timeouts: list[int] = []

        async def capture_close(**kwargs: object) -> None:
            close_timeouts.append(kwargs["timeout_seconds"])  # type: ignore[index]

        mock_consumer = MagicMock()
        mock_consumer.start = AsyncMock()

        mock_mongo = MagicMock()
        mock_mongo.admin.command = AsyncMock(return_value={"ok": 1})

        mock_session = MagicMock()
        mock_session.run = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_neo4j = MagicMock()
        mock_neo4j.session.return_value = mock_session

        mock_es = MagicMock()
        mock_es.info = AsyncMock(return_value={})

        with (
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncMongoClient",
                return_value=mock_mongo,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncGraphDatabase.driver",
                return_value=mock_neo4j,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncElasticsearch",
                return_value=mock_es,
            ),
            patch("memory_system.entrypoints.extraction_worker.httpx.AsyncClient"),
            patch(
                "memory_system.entrypoints.extraction_worker.create_archive_created_consumer",
                return_value=mock_consumer,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.create_production_extraction_pipeline",
                return_value=MagicMock(),
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.run_archive_created_consumer_loop",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker._close_worker_resources",
                side_effect=capture_close,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker._install_stop_handlers",
                side_effect=lambda event, started: event.set(),
            ),
        ):
            await extraction_worker._run_worker(SETTINGS)

        assert close_timeouts == [SETTINGS.shutdown.extraction_worker_timeout_seconds]
