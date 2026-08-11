"""Integration tests: Kafka LZ4 producer send_and_wait with real test broker."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
KAFKA_CONTAINER = "memory-system-kafka-test"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


def _compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env["PROXY__HTTP_URL"] = ""
    return env


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(COMPOSE_SH), "--stack=test", "--embedding=none", *args]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_compose_env(),
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"compose failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _ensure_dotenv() -> None:
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def _assert_test_isolation() -> None:
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT


def _container_ip(name: str) -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


def _ensure_topic(topic: str, bootstrap_inside: str = "localhost:9092") -> None:
    created = subprocess.run(
        [
            "docker",
            "exec",
            KAFKA_CONTAINER,
            "/opt/kafka/bin/kafka-topics.sh",
            "--bootstrap-server",
            bootstrap_inside,
            "--create",
            "--if-not-exists",
            "--topic",
            topic,
            "--partitions",
            "1",
            "--replication-factor",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if created.returncode != 0:
        raise AssertionError(
            f"topic create failed: {created.stderr or created.stdout}"
        )


@pytest.fixture(scope="module")
def kafka_stack() -> Iterator[str]:
    """Start test Kafka; yield bootstrap address for host clients."""
    if not _docker_available():
        pytest.skip("Docker not available")
    _ensure_dotenv()
    _assert_test_isolation()
    _compose("up", "-d", "kafka")
    deadline = time.time() + 120
    kafka_ip: str | None = None
    while time.time() < deadline:
        kafka_ip = _container_ip(KAFKA_CONTAINER)
        if kafka_ip:
            probe = subprocess.run(
                [
                    "docker",
                    "exec",
                    KAFKA_CONTAINER,
                    "/opt/kafka/bin/kafka-broker-api-versions.sh",
                    "--bootstrap-server",
                    "localhost:9092",
                ],
                capture_output=True,
                check=False,
            )
            if probe.returncode == 0:
                break
        time.sleep(3)
    else:
        pytest.skip("Test Kafka did not become ready in time")

    assert kafka_ip
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
        yield f"{kafka_ip}:9092"
    finally:
        socket.getaddrinfo = real_getaddrinfo
        _compose("down", check=False)


async def _consume_one(
    bootstrap: str,
    topic: str,
    *,
    group_id: str,
    timeout_s: float = 20.0,
) -> tuple[bytes | None, bytes | None]:
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=int(timeout_s * 1000),
    )
    await consumer.start()
    try:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            batch = await consumer.getmany(timeout_ms=1000, max_records=10)
            for _tp, messages in batch.items():
                for msg in messages:
                    return msg.key, msg.value
            await asyncio.sleep(0.2)
        return None, None
    finally:
        await consumer.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_lz4_producer_send_and_wait_consumer_readback(
    kafka_stack: str,
) -> None:
    topic = f"devops009.lz4.{uuid.uuid4().hex[:12]}"
    _ensure_topic(topic)
    bootstrap = kafka_stack
    payload = json.dumps({"probe": "lz4", "id": uuid.uuid4().hex}).encode("utf-8")
    message_key = b"devops009-lz4-key"

    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        acks="all",
        enable_idempotence=True,
        compression_type="lz4",
    )
    assert producer._compression_type == "lz4"  # noqa: SLF001 — explicit lz4 wire contract
    await producer.start()
    try:
        record_metadata = await producer.send_and_wait(topic, value=payload, key=message_key)
        assert record_metadata.topic == topic
    finally:
        await producer.stop()

    key, value = await _consume_one(
        bootstrap,
        topic,
        group_id=f"devops009-lz4-{uuid.uuid4().hex[:8]}",
    )
    assert key == message_key
    assert value == payload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_lz4_producer_compression_type_not_gzip_fallback(
    kafka_stack: str,
) -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=kafka_stack,
        compression_type="lz4",
    )
    assert producer._compression_type == "lz4"  # noqa: SLF001
    assert producer._compression_type != "gzip"  # noqa: SLF001
