"""Kafka integration tests for message write coordinator (STM-009 I-H, I-I mandatory)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore[import-untyped]
from pymongo import AsyncMongoClient

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.archive_created_event import ARCHIVE_CREATED_EVENT_FIELD_NAMES
from memory_system.domain.models.message_write import MessageWriteInput
from memory_system.domain.models.working_memory import WorkingMemoryMeta
from memory_system.domain.services.compression_coordinator_service import (
    write_working_message_with_coordination,
)
from memory_system.domain.services.message_write_service import write_message
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
)
from memory_system.infrastructure.redis.keys import (
    compression_lock_key,
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_codec import hash_fields_to_meta
from memory_system.infrastructure.redis.working_memory_repository import (
    create_working_memory_session,
)
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
REDIS_CONTAINER = "memory-system-redis-test"
KAFKA_CONTAINER = "memory-system-kafka-test"
MONGODB_CONTAINER = "memory-system-mongodb-test"
TOPIC = "context.archive.created"
FIXED_NOW = 1_700_000_000


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


def _ensure_topic() -> None:
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
def full_stack() -> Iterator[tuple[str, str, str]]:
    if not _docker_available():
        pytest.skip("Docker not available")
    _ensure_dotenv()
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT

    _compose("up", "-d", "redis", "kafka", "mongodb")
    deadline = time.time() + 120
    redis_ip = kafka_ip = mongo_ip = None
    while time.time() < deadline:
        redis_ip = _container_ip(REDIS_CONTAINER)
        kafka_ip = _container_ip(KAFKA_CONTAINER)
        mongo_ip = _container_ip(MONGODB_CONTAINER)
        if redis_ip and kafka_ip and mongo_ip:
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
        pytest.skip("Stack not ready")

    assert redis_ip and kafka_ip and mongo_ip
    _ensure_topic()

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
        yield (
            f"redis://{redis_ip}:6379/0",
            f"{kafka_ip}:9092",
            f"mongodb://{mongo_ip}:27017/memory_system",
        )
    finally:
        socket.getaddrinfo = real_getaddrinfo
        _compose("down", check=False)


@pytest.fixture
async def async_redis(full_stack: tuple[str, str, str]) -> AsyncIterator[aioredis.Redis]:
    redis_url, _, _ = full_stack
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def mongo_client(full_stack: tuple[str, str, str]) -> AsyncIterator[AsyncMongoClient[Any]]:
    _, _, mongo_url = full_stack
    client: AsyncMongoClient[Any] = AsyncMongoClient(mongo_url)
    try:
        await client.admin.command("ping")
        db = client.get_default_database()
        if db is not None:
            await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
        yield client
        if db is not None:
            await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
    finally:
        await client.close()


@pytest.fixture
async def kafka_producer(
    full_stack: tuple[str, str, str],
) -> AsyncIterator[AIOKafkaProducer]:
    _, bootstrap, _ = full_stack
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


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_settings() -> Any:
    settings = get_settings()
    return settings.model_copy(
        update={
            "context": settings.context.model_copy(
                update={
                    "compression_trigger_tokens": 200,
                    "compression_target_tokens": 80,
                    "preferred_recent_messages": 2,
                    "absolute_min_recent_messages": 2,
                }
            )
        }
    )


def _content_for_tokens(tokens: int) -> str:
    return "b" * max(tokens * 4, 4)


def _new_ids() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return f"stm009_k_user_{suffix}", str(uuid.uuid4())


def _clock_at(offset: int) -> Callable[[], int]:
    return lambda: FIXED_NOW + offset


async def _read_meta(
    redis_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> WorkingMemoryMeta:
    fields = cast(
        dict[str, str],
        await redis_client.hgetall(working_memory_meta_key(user_id, session_id)),
    )
    return hash_fields_to_meta(fields)


async def _cleanup(redis_client: aioredis.Redis, user_id: str, session_id: str) -> None:
    await redis_client.delete(
        working_memory_meta_key(user_id, session_id),
        working_memory_messages_key(user_id, session_id),
        working_memory_message_ids_key(user_id, session_id),
        compression_lock_key(user_id, session_id),
    )


async def _seed_for_trigger(
    redis_client: aioredis.Redis,
    settings: Any,
    user_id: str,
    session_id: str,
) -> None:
    await create_working_memory_session(
        redis=redis_client, user_id=user_id, session_id=session_id, now=FIXED_NOW
    )
    for index in range(4):
        result = await write_message(
            redis=redis_client,
            input=MessageWriteInput(
                user_id=user_id,
                session_id=session_id,
                message_id=str(uuid.uuid4()),
                role=MessageRole.USER,
                content=_content_for_tokens(60),
            ),
            context=settings.context,
            clock=_clock_at(index),
        )
        assert result.status == MessageWriteStatus.SUCCESS


async def _consume_one(
    bootstrap: str,
    *,
    group_id: str,
    user_id: str,
    session_id: str,
) -> dict[str, Any]:
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=20_000,
    )
    await consumer.start()
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            batch = await consumer.getmany(timeout_ms=1000, max_records=20)
            for messages in batch.values():
                for msg in messages:
                    payload: dict[str, Any] = json.loads(msg.value.decode("utf-8"))
                    if (
                        payload.get("user_id") == user_id
                        and payload.get("session_id") == session_id
                    ):
                        return payload
            await asyncio.sleep(0.2)
        return {}
    finally:
        await consumer.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_h_kafka_event_emitted(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    full_stack: tuple[str, str, str],
    test_settings: Any,
) -> None:
    _, bootstrap, _ = full_stack
    user_id, session_id = _new_ids()
    await _seed_for_trigger(async_redis, test_settings, user_id, session_id)
    message_id = str(uuid.uuid4())
    await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 10,
    )
    payload = await _consume_one(
        bootstrap,
        group_id=f"stm009-h-{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        session_id=session_id,
    )
    assert set(payload.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert payload["event_type"] == TOPIC
    assert payload["user_id"] == user_id
    assert payload["session_id"] == session_id
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_i_kafka_publish_failed_pending_preserved_continues(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    test_settings: Any,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_for_trigger(async_redis, test_settings, user_id, session_id)
    message_id = str(uuid.uuid4())

    with patch.object(
        kafka_producer,
        "send_and_wait",
        new=AsyncMock(side_effect=RuntimeError("injected kafka failure")),
    ):
        result = await write_working_message_with_coordination(
            redis=async_redis,
            mongodb=mongo_client,
            kafka_producer=kafka_producer,
            llm_client=FakeLlmClient(
                success_content='{"compressed_context":"kafka fail recovery"}'
            ),
            settings=test_settings,
            input=MessageWriteInput(
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                role=MessageRole.USER,
                content=_content_for_tokens(60),
            ),
            clock=lambda: FIXED_NOW + 20,
        )

    assert result.status == "success"
    assert result.compression_status == CompressionStatus.COMPLETED
    meta_before_finalize_check = await _read_meta(async_redis, user_id, session_id)
    assert meta_before_finalize_check.pending_archive_id is None
    await _cleanup(async_redis, user_id, session_id)
