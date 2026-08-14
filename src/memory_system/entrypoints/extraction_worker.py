"""Entrypoint for the production memory-extraction-worker process."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
from typing import Any

import httpx
from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]
from elasticsearch import AsyncElasticsearch
from neo4j import AsyncDriver, AsyncGraphDatabase
from pymongo import AsyncMongoClient

from memory_system.domain.services.production_extraction_pipeline import (
    create_production_extraction_pipeline,
)
from memory_system.infrastructure.kafka.archive_created_consumer import (
    create_archive_created_consumer,
    run_archive_created_consumer_loop,
)
from memory_system.observability.logging import configure_logging
from memory_system.settings import get_settings
from memory_system.settings.models import Settings

_logger = logging.getLogger(__name__)


def remaining_shutdown_seconds(
    shutdown_started_monotonic: float | None,
    shutdown_timeout_seconds: int,
) -> float:
    if shutdown_started_monotonic is None:
        return float(shutdown_timeout_seconds)
    elapsed = time.monotonic() - shutdown_started_monotonic
    return max(0.0, float(shutdown_timeout_seconds) - elapsed)


async def _close_worker_resources(
    *,
    consumer: AIOKafkaConsumer | None,
    mongodb: AsyncMongoClient[Any],
    neo4j_driver: AsyncDriver,
    elasticsearch: AsyncElasticsearch,
    http_client: httpx.AsyncClient,
    timeout_seconds: int,
) -> None:
    async def close_all() -> None:
        if consumer is not None:
            await consumer.stop()
        await elasticsearch.close()
        await neo4j_driver.close()
        await mongodb.close()
        await http_client.aclose()

    try:
        await asyncio.wait_for(close_all(), timeout=timeout_seconds)
    except TimeoutError:
        _logger.error("memory-extraction-worker graceful shutdown timed out")


def _install_stop_handlers(
    stop_event: asyncio.Event,
    shutdown_started_monotonic: list[float | None],
) -> None:
    loop = asyncio.get_running_loop()

    def _handle_stop() -> None:
        shutdown_started_monotonic[0] = time.monotonic()
        stop_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, _handle_stop)
        except (NotImplementedError, RuntimeError):
            # Some embedding environments do not expose signal handlers.
            continue


async def _run_worker(settings: Settings) -> None:
    mongodb: AsyncMongoClient[Any] = AsyncMongoClient(
        settings.mongodb.uri.get_secret_value(),
        serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
        connectTimeoutMS=settings.mongodb.connect_timeout_ms,
        maxPoolSize=settings.mongodb.max_pool_size,
    )
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j.uri.get_secret_value(),
        connection_timeout=settings.neo4j.connection_timeout_seconds,
        connection_acquisition_timeout=settings.neo4j.connection_acquisition_timeout_seconds,
        max_connection_pool_size=settings.neo4j.max_connection_pool_size,
    )
    elasticsearch = AsyncElasticsearch(
        hosts=[settings.elasticsearch.url],
        request_timeout=settings.elasticsearch.request_timeout_seconds,
        max_retries=settings.elasticsearch.max_retries,
        retry_on_timeout=settings.elasticsearch.retry_on_timeout,
    )
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=settings.http_client.connect_timeout_seconds,
            read=settings.http_client.read_timeout_seconds,
            write=settings.http_client.write_timeout_seconds,
            pool=settings.http_client.pool_timeout_seconds,
        ),
        limits=httpx.Limits(
            max_connections=settings.http_client.max_connections,
            max_keepalive_connections=settings.http_client.max_keepalive_connections,
        ),
    )
    consumer: AIOKafkaConsumer | None = None
    shutdown_started_monotonic: list[float | None] = [None]
    try:
        await mongodb.admin.command("ping")
        async with neo4j_driver.session() as session:
            await session.run("RETURN 1")
        await elasticsearch.info()

        pipeline = create_production_extraction_pipeline(
            mongodb,
            neo4j_driver,
            elasticsearch,
            http_client,
            settings,
            clock=lambda: int(time.time()),
        )
        consumer = create_archive_created_consumer(
            bootstrap_servers=settings.kafka.bootstrap_servers,
            topic=settings.kafka.topic,
            consumer_settings=settings.kafka_consumer,
        )
        await consumer.start()
        stop_event = asyncio.Event()
        _install_stop_handlers(stop_event, shutdown_started_monotonic)
        await run_archive_created_consumer_loop(
            consumer=consumer,
            mongodb=mongodb,
            pipeline=pipeline,
            clock=lambda: int(time.time()),
            should_stop=stop_event.is_set,
            get_shutdown_started=lambda: shutdown_started_monotonic[0],
            shutdown_timeout_seconds=settings.shutdown.extraction_worker_timeout_seconds,
        )
    finally:
        close_timeout_seconds = int(
            remaining_shutdown_seconds(
                shutdown_started_monotonic[0],
                settings.shutdown.extraction_worker_timeout_seconds,
            )
        )
        await _close_worker_resources(
            consumer=consumer,
            mongodb=mongodb,
            neo4j_driver=neo4j_driver,
            elasticsearch=elasticsearch,
            http_client=http_client,
            timeout_seconds=close_timeout_seconds,
        )


def main() -> int:
    """Run the extraction consumer until a graceful shutdown is requested."""
    try:
        settings = get_settings()
    except Exception:
        print(
            "memory-extraction-worker is not ready: settings failed before the "
            "Kafka poll loop could start.",
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
            "memory-extraction-worker not ready: startup failed before normal shutdown: "
            f"{type(exc).__name__}; Kafka poll loop did not start.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
