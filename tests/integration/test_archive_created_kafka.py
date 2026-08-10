"""Kafka integration tests for context.archive.created publish (STM-006)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore[import-untyped]

from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.domain.models.archive_created_event import ARCHIVE_CREATED_EVENT_FIELD_NAMES
from memory_system.domain.models.compression_preparation import CompressionPreparationInput
from memory_system.domain.services.compression_preparation_service import (
    prepare_pending_archive_and_publish,
)
from memory_system.infrastructure.redis.keys import (
    compression_lock_key,
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_repository import (
    create_working_memory_session,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
REDIS_CONTAINER = "memory-system-redis-test"
KAFKA_CONTAINER = "memory-system-kafka-test"
TOPIC = "context.archive.created"
FIXED_NOW = 1_700_000_000
TTL = 420


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


def _ensure_topic(bootstrap_inside: str = "localhost:9092") -> None:
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
        raise AssertionError(
            f"topic create failed: {created.stderr or created.stdout}"
        )


@pytest.fixture(scope="module")
def kafka_redis_stack() -> Iterator[tuple[str, str]]:
    """Start test Redis + Kafka; yield (redis_url, kafka_bootstrap)."""
    if not _docker_available():
        pytest.skip("Docker not available")
    _ensure_dotenv()
    _assert_test_isolation()
    _compose("up", "-d", "redis", "kafka")
    deadline = time.time() + 120
    redis_ip: str | None = None
    kafka_ip: str | None = None
    while time.time() < deadline:
        redis_ip = _container_ip(REDIS_CONTAINER)
        kafka_ip = _container_ip(KAFKA_CONTAINER)
        if redis_ip and kafka_ip:
            # Wait until kafka broker responds inside container
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
        pytest.skip("Test Redis/Kafka did not become ready in time")

    assert redis_ip and kafka_ip
    try:
        _ensure_topic()
    except AssertionError as exc:
        pytest.skip(f"Unable to ensure Kafka topic: {exc}")

    # Host clients connect to PLAINTEXT (9092) but metadata returns hostname "kafka".
    # Patch getaddrinfo so "kafka" resolves to the container IP for this process.
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
        yield f"redis://{redis_ip}:6379/0", f"{kafka_ip}:9092"
    finally:
        socket.getaddrinfo = real_getaddrinfo
        _compose("down", check=False)


@pytest.fixture
async def async_redis(kafka_redis_stack: tuple[str, str]) -> AsyncIterator[aioredis.Redis]:
    redis_url, _ = kafka_redis_stack
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def kafka_producer(
    kafka_redis_stack: tuple[str, str],
) -> AsyncIterator[AIOKafkaProducer]:
    _, bootstrap = kafka_redis_stack
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


def _new_ids() -> tuple[str, str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    user_id = f"stm006_k_user_{suffix}"
    session_id = str(uuid.uuid4())
    archive_id = str(uuid.uuid4())
    batch_key = f"{session_id}:ka:kb"
    return user_id, session_id, archive_id, batch_key


async def _cleanup(redis_client: aioredis.Redis, user_id: str, session_id: str) -> None:
    await redis_client.delete(
        working_memory_meta_key(user_id, session_id),
        working_memory_messages_key(user_id, session_id),
        working_memory_message_ids_key(user_id, session_id),
        compression_lock_key(user_id, session_id),
    )


async def _consume_one(
    bootstrap: str,
    *,
    group_id: str,
    timeout_s: float = 20.0,
) -> tuple[bytes | None, dict[str, Any]]:
    consumer = AIOKafkaConsumer(
        TOPIC,
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
                    payload = json.loads(msg.value.decode("utf-8"))
                    return msg.key, payload
            await asyncio.sleep(0.2)
        return None, {}
    finally:
        await consumer.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_k1_k5_exact_topic_schema_key_success(
    async_redis: aioredis.Redis,
    kafka_producer: AIOKafkaProducer,
    kafka_redis_stack: tuple[str, str],
) -> None:
    _, bootstrap = kafka_redis_stack
    user_id, session_id, archive_id, batch_key = _new_ids()
    await create_working_memory_session(
        redis=async_redis,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )

    result = await prepare_pending_archive_and_publish(
        redis=async_redis,
        kafka_producer=kafka_producer,
        topic=TOPIC,
        input=CompressionPreparationInput(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
            archive_batch_key=batch_key,
            pending_archive_message_count=2,
            pending_archive_estimated_tokens=40,
        ),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert result.status == CompressionPreparationStatus.SUCCESS
    assert result.event_id is not None

    key, payload = await _consume_one(
        bootstrap,
        group_id=f"stm006-k-{uuid.uuid4().hex[:8]}",
    )
    assert key == user_id.encode("utf-8")
    assert set(payload.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert payload["event_type"] == TOPIC
    assert payload["archive_id"] == archive_id
    assert payload["user_id"] == user_id
    assert payload["session_id"] == session_id
    assert payload["created_time"] == FIXED_NOW
    assert payload["event_id"] == result.event_id
    assert "archive_batch_key" not in payload
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_k6_injected_publish_failure_pending_survives(
    async_redis: aioredis.Redis,
    kafka_producer: AIOKafkaProducer,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await create_working_memory_session(
        redis=async_redis,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )

    with patch.object(
        kafka_producer,
        "send_and_wait",
        new=AsyncMock(side_effect=RuntimeError("injected publish failure")),
    ):
        result = await prepare_pending_archive_and_publish(
            redis=async_redis,
            kafka_producer=kafka_producer,
            topic=TOPIC,
            input=CompressionPreparationInput(
                user_id=user_id,
                session_id=session_id,
                archive_id=archive_id,
                archive_batch_key=batch_key,
                pending_archive_message_count=2,
                pending_archive_estimated_tokens=40,
            ),
            lock_ttl_seconds=TTL,
            clock=lambda: FIXED_NOW,
        )

    assert result.status == CompressionPreparationStatus.PUBLISH_FAILED
    fields = await async_redis.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_id"] == archive_id
    assert fields["pending_archive_batch_key"] == batch_key
    assert result.lock_owner_token is not None
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_k7_duplicate_retry_allowed(
    async_redis: aioredis.Redis,
    kafka_producer: AIOKafkaProducer,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await create_working_memory_session(
        redis=async_redis,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )
    first = await prepare_pending_archive_and_publish(
        redis=async_redis,
        kafka_producer=kafka_producer,
        topic=TOPIC,
        input=CompressionPreparationInput(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
            archive_batch_key=batch_key,
            pending_archive_message_count=2,
            pending_archive_estimated_tokens=40,
        ),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert first.status == CompressionPreparationStatus.SUCCESS
    assert first.lock_owner_token is not None

    second = await prepare_pending_archive_and_publish(
        redis=async_redis,
        kafka_producer=kafka_producer,
        topic=TOPIC,
        input=CompressionPreparationInput(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
            archive_batch_key=batch_key,
            pending_archive_message_count=2,
            pending_archive_estimated_tokens=40,
            lock_owner_token=first.lock_owner_token,
        ),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert second.status == CompressionPreparationStatus.SUCCESS
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_k8_k9_no_unrelated_topic_and_zero_kafka_on_lock_fail(
    async_redis: aioredis.Redis,
    kafka_producer: AIOKafkaProducer,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await create_working_memory_session(
        redis=async_redis,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )
    # Hold lock so fresh acquire fails — must not publish to any topic.
    await async_redis.set(compression_lock_key(user_id, session_id), "other", ex=TTL)
    send = AsyncMock(return_value=None)
    with patch.object(kafka_producer, "send_and_wait", new=send):
        result = await prepare_pending_archive_and_publish(
            redis=async_redis,
            kafka_producer=kafka_producer,
            topic=TOPIC,
            input=CompressionPreparationInput(
                user_id=user_id,
                session_id=session_id,
                archive_id=archive_id,
                archive_batch_key=batch_key,
                pending_archive_message_count=2,
                pending_archive_estimated_tokens=40,
            ),
            lock_ttl_seconds=TTL,
        )
    assert result.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED
    send.assert_not_awaited()

    # Success path must only use the approved topic name.
    await async_redis.delete(compression_lock_key(user_id, session_id))
    captured: list[str] = []

    async def _capture_send(topic: str, **kwargs: Any) -> None:
        captured.append(topic)

    with patch.object(kafka_producer, "send_and_wait", new=_capture_send):
        ok = await prepare_pending_archive_and_publish(
            redis=async_redis,
            kafka_producer=kafka_producer,
            topic=TOPIC,
            input=CompressionPreparationInput(
                user_id=user_id,
                session_id=session_id,
                archive_id=archive_id,
                archive_batch_key=batch_key,
                pending_archive_message_count=2,
                pending_archive_estimated_tokens=40,
            ),
            lock_ttl_seconds=TTL,
            clock=lambda: FIXED_NOW,
        )
    assert ok.status == CompressionPreparationStatus.SUCCESS
    assert captured == [TOPIC]
    await _cleanup(async_redis, user_id, session_id)
