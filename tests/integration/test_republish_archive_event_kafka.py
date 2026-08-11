"""Kafka integration tests for archive event republish (STM-011; Mongo + Kafka only)."""

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
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore[import-untyped]
from pymongo import AsyncMongoClient

from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.archive_created_event import ARCHIVE_CREATED_EVENT_FIELD_NAMES
from memory_system.domain.models.archive_event_republish import ArchiveEventRepublishInput
from memory_system.domain.models.context_archive import ContextArchiveCreateInput
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.archive_event_republish_service import (
    republish_archive_created_event,
)
from memory_system.domain.services.context_archive_service import build_archive_batch_key
from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
    insert_context_archive,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
MONGODB_CONTAINER = "memory-system-mongodb-test"
KAFKA_CONTAINER = "memory-system-kafka-test"
MONGODB_DATABASE = "memory_system"
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


def _run_init_infra() -> subprocess.CompletedProcess[str]:
    return _compose("run", "--rm", "init-infra", check=False)


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
        raise AssertionError(f"topic create failed: {created.stderr or created.stdout}")


@pytest.fixture(scope="module")
def mongo_kafka_stack() -> Iterator[tuple[str, str]]:
    """Start test Mongo + Kafka; yield (mongo_uri, kafka_bootstrap)."""
    if not _docker_available():
        pytest.skip("Docker not available; cannot run republish integration safely")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "mongodb", "kafka", check=False)
    if up.returncode != 0:
        pytest.skip(
            "Unable to start compose test Mongo/Kafka "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 120
    mongo_ip: str | None = None
    kafka_ip: str | None = None
    while time.time() < deadline:
        mongo_ip = _container_ip(MONGODB_CONTAINER)
        kafka_ip = _container_ip(KAFKA_CONTAINER)
        if mongo_ip and kafka_ip:
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
        time.sleep(2)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Test Mongo/Kafka did not become ready in time")

    migrate = _run_init_infra()
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra migration failed: "
            f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    assert mongo_ip and kafka_ip
    mongo_uri = f"mongodb://{mongo_ip}:27017/{MONGODB_DATABASE}"

    try:
        _ensure_topic()
    except AssertionError as exc:
        _compose("down", "-v", check=False)
        pytest.skip(f"Unable to ensure Kafka topic: {exc}")

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
        yield mongo_uri, f"{kafka_ip}:9092"
    finally:
        socket.getaddrinfo = real_getaddrinfo
        _compose("down", "-v", check=False)


@pytest.fixture
async def mongo_client(mongo_kafka_stack: tuple[str, str]) -> AsyncIterator[AsyncMongoClient[Any]]:
    mongo_uri, _ = mongo_kafka_stack
    client: AsyncMongoClient[Any] = AsyncMongoClient(mongo_uri)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        await client.close()
        pytest.skip(f"Mongo ping failed: {exc}")
    yield client
    await client.close()


@pytest.fixture
async def kafka_producer(
    mongo_kafka_stack: tuple[str, str],
) -> AsyncIterator[AIOKafkaProducer]:
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


@pytest.fixture(autouse=True)
async def _clean_context_archive(mongo_client: AsyncMongoClient[Any]) -> AsyncIterator[None]:
    db = mongo_client.get_default_database()
    if db is not None:
        await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
    yield
    if db is not None:
        await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})


def _seed_input(user_id: str, session_id: str) -> ContextArchiveCreateInput:
    messages = [
        WorkingMemoryMessage(
            message_id="msg_m1",
            role=MessageRole.USER,
            content="first",
            estimated_tokens=10,
            timestamp=FIXED_NOW,
        ),
        WorkingMemoryMessage(
            message_id="msg_m2",
            role=MessageRole.ASSISTANT,
            content="second",
            estimated_tokens=12,
            timestamp=FIXED_NOW + 1,
        ),
    ]
    batch_key = build_archive_batch_key(session_id, "msg_m1", "msg_m2")
    return ContextArchiveCreateInput(
        user_id=user_id,
        session_id=session_id,
        archive_batch_key=batch_key,
        base_compression_version=0,
        messages=messages,
    )


async def _insert_archive(
    mongo_client: AsyncMongoClient[Any],
    *,
    archive_id: str,
    user_id: str,
    session_id: str,
) -> None:
    from memory_system.domain.models.context_archive import archive_document_from_input

    input_data = _seed_input(user_id, session_id)
    document = archive_document_from_input(
        input=input_data,
        archive_id=archive_id,
        created_time=FIXED_NOW,
    )
    await insert_context_archive(mongo_client, document)


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
async def test_i1_mongo_seed_and_republish_publishes_six_field_event(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    archive_id = str(uuid.uuid4())
    user_id = f"stm011_user_{uuid.uuid4().hex[:8]}"
    session_id = str(uuid.uuid4())
    await _insert_archive(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )

    result = await republish_archive_created_event(
        mongodb=mongo_client,
        kafka_producer=kafka_producer,
        topic=TOPIC,
        input=ArchiveEventRepublishInput(archive_id=archive_id),
    )
    assert result.status == ArchiveEventRepublishStatus.SUCCESS
    assert result.event_id is not None

    key, payload = await _consume_one(
        bootstrap,
        group_id=f"stm011-i1-{uuid.uuid4().hex[:8]}",
    )
    assert key == user_id.encode("utf-8")
    assert set(payload.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert payload["archive_id"] == archive_id
    assert payload["user_id"] == user_id
    assert payload["session_id"] == session_id
    assert payload["created_time"] == FIXED_NOW
    assert payload["event_id"] == result.event_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_archive_not_found_no_publish(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
) -> None:
    missing_id = str(uuid.uuid4())
    send_spy = AsyncMock(wraps=kafka_producer.send_and_wait)

    with patch.object(kafka_producer, "send_and_wait", send_spy):
        result = await republish_archive_created_event(
            mongodb=mongo_client,
            kafka_producer=kafka_producer,
            topic=TOPIC,
            input=ArchiveEventRepublishInput(archive_id=missing_id),
        )

    assert result.status == ArchiveEventRepublishStatus.ARCHIVE_NOT_FOUND
    send_spy.assert_not_awaited()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_ownership_mismatch_no_publish(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
) -> None:
    archive_id = str(uuid.uuid4())
    user_id = f"stm011_owner_{uuid.uuid4().hex[:8]}"
    session_id = str(uuid.uuid4())
    await _insert_archive(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )
    send_spy = AsyncMock(wraps=kafka_producer.send_and_wait)

    with patch.object(kafka_producer, "send_and_wait", send_spy):
        result = await republish_archive_created_event(
            mongodb=mongo_client,
            kafka_producer=kafka_producer,
            topic=TOPIC,
            input=ArchiveEventRepublishInput(
                archive_id=archive_id,
                expected_user_id="wrong_user",
            ),
        )

    assert result.status == ArchiveEventRepublishStatus.ARCHIVE_OWNERSHIP_MISMATCH
    send_spy.assert_not_awaited()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_injected_publish_failure_mongo_unchanged(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
) -> None:
    archive_id = str(uuid.uuid4())
    user_id = f"stm011_fail_{uuid.uuid4().hex[:8]}"
    session_id = str(uuid.uuid4())
    await _insert_archive(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )

    db = mongo_client.get_default_database()
    assert db is not None
    before = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"archive_id": archive_id})

    with patch.object(
        kafka_producer,
        "send_and_wait",
        new=AsyncMock(side_effect=RuntimeError("injected broker failure")),
    ):
        result = await republish_archive_created_event(
            mongodb=mongo_client,
            kafka_producer=kafka_producer,
            topic=TOPIC,
            input=ArchiveEventRepublishInput(archive_id=archive_id),
        )

    assert result.status == ArchiveEventRepublishStatus.KAFKA_PUBLISH_FAILED
    after = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"archive_id": archive_id})
    assert before == after


async def _consume_for_archive(
    bootstrap: str,
    *,
    archive_id: str,
    group_id: str,
    expected_count: int,
    timeout_s: float = 20.0,
) -> set[str]:
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=int(timeout_s * 1000),
    )
    await consumer.start()
    event_ids: set[str] = set()
    try:
        deadline = time.time() + timeout_s
        while time.time() < deadline and len(event_ids) < expected_count:
            batch = await consumer.getmany(timeout_ms=1000, max_records=20)
            for _tp, messages in batch.items():
                for msg in messages:
                    payload = json.loads(msg.value.decode("utf-8"))
                    if payload.get("archive_id") == archive_id:
                        event_ids.add(payload["event_id"])
            await asyncio.sleep(0.2)
        return event_ids
    finally:
        await consumer.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f2_concurrent_republish_distinct_event_ids(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    mongo_kafka_stack: tuple[str, str],
) -> None:
    _, bootstrap = mongo_kafka_stack
    archive_id = str(uuid.uuid4())
    user_id = f"stm011_conc_{uuid.uuid4().hex[:8]}"
    session_id = str(uuid.uuid4())
    await _insert_archive(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )

    results = await asyncio.gather(
        republish_archive_created_event(
            mongodb=mongo_client,
            kafka_producer=kafka_producer,
            topic=TOPIC,
            input=ArchiveEventRepublishInput(archive_id=archive_id),
        ),
        republish_archive_created_event(
            mongodb=mongo_client,
            kafka_producer=kafka_producer,
            topic=TOPIC,
            input=ArchiveEventRepublishInput(archive_id=archive_id),
        ),
    )
    assert all(r.status == ArchiveEventRepublishStatus.SUCCESS for r in results)
    event_ids = {r.event_id for r in results}
    assert len(event_ids) == 2

    consumed_ids = await _consume_for_archive(
        bootstrap,
        archive_id=archive_id,
        group_id=f"stm011-f2-{uuid.uuid4().hex[:8]}",
        expected_count=2,
    )
    assert event_ids == consumed_ids
