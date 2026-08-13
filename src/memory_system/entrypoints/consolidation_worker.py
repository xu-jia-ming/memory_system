"""Entrypoint for the memory-consolidation-worker process (§3.25)."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from neo4j import AsyncDriver, AsyncGraphDatabase

from memory_system.domain.models.consolidation_write import (
    ConsolidationWriteBatchRequest,
    ConsolidationWriteBatchResult,
)
from memory_system.domain.services.consolidation_batch_service import ConsolidationBatchService
from memory_system.domain.services.consolidation_run_service import ConsolidationRunService
from memory_system.domain.services.consolidation_write_service import write_batch
from memory_system.infrastructure.consolidation_mutex import ConsolidationMutex
from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationMemoryReadRepository,
)
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    ConsolidationMemoryWriteRepository,
)
from memory_system.infrastructure.neo4j.consolidation_user_enumeration_repository import (
    ConsolidationUserEnumerationRepository,
)
from memory_system.infrastructure.scheduling.consolidation_scheduler import (
    create_consolidation_scheduler,
)
from memory_system.observability.logging import configure_logging
from memory_system.settings import get_settings
from memory_system.settings.models import Settings

_logger = logging.getLogger(__name__)


class _WriteBatchAdapter:
    def __init__(self, repository: ConsolidationMemoryWriteRepository) -> None:
        self._repository = repository

    async def write_batch(
        self,
        request: ConsolidationWriteBatchRequest,
    ) -> ConsolidationWriteBatchResult:
        return await write_batch(request, self._repository)


def _install_stop_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError):
            continue


async def _close_neo4j(driver: AsyncDriver, *, timeout_seconds: int) -> None:
    try:
        await asyncio.wait_for(driver.close(), timeout=timeout_seconds)
    except TimeoutError:
        _logger.error("memory-consolidation-worker graceful shutdown timed out closing Neo4j")


async def _run_worker(settings: Settings) -> None:
    neo4j_timeout_seconds = float(settings.memory_retrieval.neo4j_timeout_seconds)
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j.uri.get_secret_value(),
        connection_timeout=settings.neo4j.connection_timeout_seconds,
        connection_acquisition_timeout=settings.neo4j.connection_acquisition_timeout_seconds,
        max_connection_pool_size=settings.neo4j.max_connection_pool_size,
    )
    scheduler = None
    try:
        async with neo4j_driver.session() as session:
            await session.run("RETURN 1")

        read_repository = ConsolidationMemoryReadRepository(
            neo4j_driver,
            neo4j_timeout_seconds=neo4j_timeout_seconds,
        )
        write_repository = ConsolidationMemoryWriteRepository(
            neo4j_driver,
            neo4j_timeout_seconds=neo4j_timeout_seconds,
        )
        enumeration_repository = ConsolidationUserEnumerationRepository(
            neo4j_driver,
            neo4j_timeout_seconds=neo4j_timeout_seconds,
        )
        batch_service = ConsolidationBatchService(read_repository)
        write_service = _WriteBatchAdapter(write_repository)
        mutex = ConsolidationMutex()
        run_service = ConsolidationRunService(
            batch_service=batch_service,
            write_service=write_service,
            enumeration_repository=enumeration_repository,
            mutex=mutex,
            settings=settings,
        )

        async def run_callback(evaluation_time: int) -> None:
            await run_service.execute_run(evaluation_time)

        scheduler = create_consolidation_scheduler(settings, run_callback)
        if scheduler is not None:
            scheduler.start()

        stop_event = asyncio.Event()
        _install_stop_handlers(stop_event)
        await stop_event.wait()
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=True)
        await _close_neo4j(
            neo4j_driver,
            timeout_seconds=settings.shutdown.consolidation_worker_timeout_seconds,
        )


def main() -> int:
    """Run consolidation worker until graceful shutdown is requested."""
    try:
        settings = get_settings()
    except Exception:
        print(
            "memory-consolidation-worker is not ready: consolidation_invalid_config or "
            "settings failed before startup.",
            file=sys.stderr,
        )
        return 1

    configure_logging(settings)
    try:
        asyncio.run(_run_worker(settings))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(
            "memory-consolidation-worker not ready: startup failed before normal shutdown: "
            f"{type(exc).__name__}.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
