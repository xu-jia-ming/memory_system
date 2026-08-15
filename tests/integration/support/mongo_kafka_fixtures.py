"""Shared Mongo+Kafka integration fixtures backed by compose_stack.

This module must not define autouse fixtures. Test modules load it via
pytest_plugins; autouse here would leak into unrelated files (migrate/OPS-003).
"""

from __future__ import annotations

import socket
import subprocess
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from pymongo import AsyncMongoClient
from tests.integration.support.compose_stack import (
    CONTAINER_NAMES,
    kafka_bootstrap_from_container,
    module_services,
    mongo_uri_from_container,
    require_docker_or_skip,
    skip_on_startup_error,
)

TOPIC = "context.archive.created"
KAFKA_CONTAINER = CONTAINER_NAMES["kafka"]


def _ensure_archive_topic() -> None:
    created = subprocess.run(
        [
            "docker",
            "exec",
            KAFKA_CONTAINER,
            "/opt/kafka/bin/kafka-topics.sh",
            "--bootstrap-server",
            "localhost:9092",
            "--create",
            "--if-not-exists",
            "--topic",
            TOPIC,
            "--partitions",
            "3",
            "--replication-factor",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if created.returncode != 0:
        raise AssertionError(f"topic create failed: {created.stderr or created.stdout}")


@pytest.fixture(scope="module")
def mongo_kafka_stack() -> Iterator[tuple[str, str]]:
    require_docker_or_skip()
    try:
        with module_services(("mongodb", "kafka"), migrate=True):
            mongo_uri = mongo_uri_from_container()
            bootstrap = kafka_bootstrap_from_container()
            kafka_ip = bootstrap.rsplit(":", 1)[0]
            _ensure_archive_topic()
            real_getaddrinfo = socket.getaddrinfo

            def _patched_getaddrinfo(
                host: str | bytes | None,
                port: Any,
                *args: Any,
                **kwargs: Any,
            ) -> list[Any]:
                if host in ("kafka", b"kafka"):
                    host = kafka_ip
                return real_getaddrinfo(host, port, *args, **kwargs)

            socket.getaddrinfo = _patched_getaddrinfo
            try:
                yield mongo_uri, bootstrap
            finally:
                socket.getaddrinfo = real_getaddrinfo
    except (AssertionError, TimeoutError) as exc:
        skip_on_startup_error(str(exc))


@pytest.fixture
async def mongo_client(mongo_kafka_stack: tuple[str, str]) -> AsyncIterator[AsyncMongoClient[Any]]:
    client: AsyncMongoClient[Any] = AsyncMongoClient(mongo_kafka_stack[0])
    try:
        await client.admin.command("ping")
    except Exception as exc:
        await client.close()
        pytest.fail(f"Mongo ping failed: {exc}")
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
async def kafka_producer(mongo_kafka_stack: tuple[str, str]) -> AsyncIterator[AIOKafkaProducer]:
    _, bootstrap = mongo_kafka_stack
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        acks="all",
        enable_idempotence=True,
    )
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()
