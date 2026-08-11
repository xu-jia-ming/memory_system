"""STM-012: CLI republish → Kafka → EXT-001 consumer → Mongo integration."""

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
from typing import Any, cast

import pytest
from aiokafka import (  # type: ignore[import-untyped]
    AIOKafkaConsumer,
    TopicPartition,
)
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_FIELD_NAMES,
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.context_archive import ContextArchiveCreateInput
from memory_system.domain.models.extraction_task import MemoryExtractionTask
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.context_archive_service import build_archive_batch_key
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.infrastructure.kafka.archive_created_consumer import (
    create_archive_created_consumer,
    run_archive_created_consumer_loop,
)
from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
    insert_context_archive,
)
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    MEMORY_EXTRACTION_TASK_COLLECTION,
    find_extraction_task_by_archive_id,
)
from memory_system.settings.models import KafkaConsumerSettings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
MONGODB_CONTAINER = "memory-system-mongodb-test"
KAFKA_CONTAINER = "memory-system-kafka-test"
MONGODB_DATABASE = "memory_system"
TOPIC = "context.archive.created"
FIXED_NOW = 1_700_000_000
CLI_TIMEOUT_S = 60.0
_CLI_SITE_DIR: Path | None = None


def _ensure_cli_sitecustomize_dir() -> Path:
    """Test-only sitecustomize so CLI subprocess resolves kafka hostname to bootstrap IP."""
    global _CLI_SITE_DIR
    if _CLI_SITE_DIR is None:
        import tempfile

        site_dir = Path(tempfile.mkdtemp(prefix="stm012-site-"))
        sitecustomize = '''\
import os
import socket

_bootstrap = os.environ.get("KAFKA__BOOTSTRAP_SERVERS", "")
_kafka_ip = _bootstrap.rsplit(":", 1)[0] if _bootstrap else ""
if _kafka_ip:
    _real_getaddrinfo = socket.getaddrinfo

    def _patched_getaddrinfo(host, port, *args, **kwargs):
        if host in ("kafka", b"kafka"):
            host = _kafka_ip
        return _real_getaddrinfo(host, port, *args, **kwargs)

    socket.getaddrinfo = _patched_getaddrinfo
'''
        (site_dir / "sitecustomize.py").write_text(sitecustomize, encoding="utf-8")
        _CLI_SITE_DIR = site_dir
    return _CLI_SITE_DIR


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
        raise AssertionError(f"topic create failed: {created.stderr or created.stdout}")


def _run_init_infra() -> subprocess.CompletedProcess[str]:
    return _compose("run", "--rm", "init-infra", check=False)


def _cli_subprocess_env(*, mongo_ip: str, kafka_ip: str) -> dict[str, str]:
    """Explicit allowlist for STM-011 CLI subprocess (Amendment 002)."""
    site_dir = _ensure_cli_sitecustomize_dir()
    pythonpath = os.pathsep.join([str(REPO_ROOT / "src"), str(site_dir)])
    return {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": pythonpath,
        "APP_ENV": "test",
        "REDIS__URI": "redis://redis:6379/0",
        "MONGODB__URI": f"mongodb://{mongo_ip}:27017/{MONGODB_DATABASE}",
        "KAFKA__BOOTSTRAP_SERVERS": f"{kafka_ip}:9092",
        "KAFKA__TOPIC": TOPIC,
        "NEO4J__URI": "neo4j://neo4j:7687",
        "ELASTICSEARCH__URL": "http://elasticsearch:9200",
        "LLM__BASE_URL": "https://api.deepseek.com",
        "LLM__API_KEY": "sk-example-replace-me",
        "LLM__COMPRESSION__MODEL": "deepseek-v4-flash",
        "LLM__EXTRACTION__MODEL": "deepseek-v4-flash",
        "EMBEDDING__MODEL_ID": "BAAI/bge-m3",
        "EMBEDDING__BASE_URL": "http://embedding-service:80",
        "MEMORY_API_KEY": "dev-memory-api-key-change-me",
        "MEMORY_ADMIN_API_KEY": "dev-memory-admin-key-change-me",
        "PROXY__HTTP_URL": "",
        "EMBEDDING_EFFECTIVE_RUNTIME_MODE": "cpu",
        "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET": "4096",
    }


def _run_republish_cli(
    *,
    archive_id: str,
    user_id: str,
    mongo_ip: str,
    kafka_ip: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python",
            "scripts/republish_archive_event.py",
            "--archive-id",
            archive_id,
            "--user-id",
            user_id,
        ],
        cwd=REPO_ROOT,
        env=_cli_subprocess_env(mongo_ip=mongo_ip, kafka_ip=kafka_ip),
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_S,
        check=False,
    )


class FakeCompletePipeline:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_task_archive_ids: list[str] = []
        self.seen_event_archive_ids: list[str] = []

    async def run(
        self, task: MemoryExtractionTask, event: ArchiveCreatedEvent
    ) -> PipelineTerminalDecision:
        self.calls += 1
        self.seen_task_archive_ids.append(task.archive_id)
        self.seen_event_archive_ids.append(event.archive_id)
        return PipelineTerminalDecision.complete()


@pytest.fixture(scope="module")
def mongo_kafka_stack() -> Iterator[tuple[str, str, str, str]]:
    """Start test Mongo + Kafka; yield (mongo_uri, kafka_bootstrap, mongo_ip, kafka_ip)."""
    if not _docker_available():
        pytest.skip("Docker not available")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "mongodb", "kafka", check=False)
    if up.returncode != 0:
        pytest.skip(f"Unable to start mongo/kafka: {up.stderr[-800:] or up.stdout[-800:]}")

    deadline = time.time() + 180
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
        time.sleep(3)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Test Mongo/Kafka did not become ready in time")

    migrate = _run_init_infra()
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra failed: " f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    try:
        _ensure_topic()
    except AssertionError as exc:
        _compose("down", "-v", check=False)
        pytest.skip(f"Unable to ensure Kafka topic: {exc}")

    assert mongo_ip and kafka_ip
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
            f"mongodb://{mongo_ip}:27017/{MONGODB_DATABASE}",
            f"{kafka_ip}:9092",
            mongo_ip,
            kafka_ip,
        )
    finally:
        socket.getaddrinfo = real_getaddrinfo
        _compose("down", "-v", check=False)


@pytest.fixture
async def mongo_client(
    mongo_kafka_stack: tuple[str, str, str, str],
) -> AsyncIterator[AsyncMongoClient[Any]]:
    mongo_uri, _, _, _ = mongo_kafka_stack
    client: AsyncMongoClient[Any] = AsyncMongoClient(mongo_uri)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        await client.close()
        pytest.skip(f"Mongo ping failed: {exc}")
    yield client
    await client.close()


@pytest.fixture(autouse=True)
async def _clean_collections(mongo_client: AsyncMongoClient[Any]) -> AsyncIterator[None]:
    db = mongo_client.get_default_database()
    if db is not None:
        await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})
    yield
    if db is not None:
        await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})


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


async def _find_kafka_record(
    bootstrap: str,
    *,
    archive_id: str,
    user_id: str,
    group_id: str,
    event_id: str | None = None,
    exclude_event_ids: set[str] | None = None,
    timeout_s: float = 30.0,
) -> tuple[int, int, bytes, dict[str, Any]]:
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            batch = await consumer.getmany(timeout_ms=1000, max_records=20)
            for _tp, messages in batch.items():
                for msg in messages:
                    payload = json.loads(msg.value.decode("utf-8"))
                    if payload.get("archive_id") != archive_id:
                        continue
                    if payload.get("user_id") != user_id:
                        continue
                    record_event_id = payload.get("event_id")
                    if event_id is not None and record_event_id != event_id:
                        continue
                    if (
                        exclude_event_ids is not None
                        and record_event_id in exclude_event_ids
                    ):
                        continue
                    return msg.partition, msg.offset, msg.key or b"", payload
            await asyncio.sleep(0.2)
        raise AssertionError(
            f"Kafka record not found for archive_id={archive_id} user_id={user_id} "
            f"event_id={event_id} exclude={exclude_event_ids}"
        )
    finally:
        await consumer.stop()


async def _committed_offset(
    bootstrap: str,
    *,
    group_id: str,
    topic: str,
    partition: int,
) -> int | None:
    consumer = AIOKafkaConsumer(
        bootstrap_servers=bootstrap,
        group_id=group_id,
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        tp = TopicPartition(topic, partition)
        consumer.assign([tp])
        committed = await consumer.committed(tp)
        return cast(int | None, committed)
    finally:
        await consumer.stop()


async def _run_consumer_at_offset(
    *,
    bootstrap: str,
    mongo_client: AsyncMongoClient[Any],
    pipeline: FakeCompletePipeline,
    group_id: str,
    partition: int,
    start_offset: int,
    timeout_s: float = 30.0,
) -> int:
    settings = KafkaConsumerSettings()
    assert settings.enable_auto_commit is False
    consumer = create_archive_created_consumer(
        bootstrap_servers=bootstrap,
        topic=TOPIC,
        consumer_settings=settings,
        group_id=group_id,
    )
    await consumer.start()
    try:
        tp = TopicPartition(TOPIC, partition)
        consumer.unsubscribe()
        consumer.assign([tp])
        consumer.seek(tp, start_offset)
        return await run_archive_created_consumer_loop(
            consumer=consumer,
            mongodb=mongo_client,
            pipeline=pipeline,
            clock=lambda: FIXED_NOW,
            max_records=1,
            idle_deadline_monotonic=time.monotonic() + timeout_s,
        )
    finally:
        await consumer.stop()


def _assert_six_field_payload(
    *,
    key: bytes,
    payload: dict[str, Any],
    archive_id: str,
    user_id: str,
    session_id: str,
) -> str:
    assert key == user_id.encode("utf-8")
    assert set(payload.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert payload["event_type"] == ARCHIVE_CREATED_EVENT_TYPE
    assert payload["archive_id"] == archive_id
    assert payload["user_id"] == user_id
    assert payload["session_id"] == session_id
    assert payload["created_time"] == FIXED_NOW
    event_id = payload["event_id"]
    assert isinstance(event_id, str) and event_id
    assert uuid.UUID(event_id).version == 4
    return event_id


async def _task_document_snapshot(
    mongo_client: AsyncMongoClient[Any],
    archive_id: str,
) -> dict[str, Any]:
    db = mongo_client.get_default_database()
    assert db is not None
    document = await db[MEMORY_EXTRACTION_TASK_COLLECTION].find_one({"archive_id": archive_id})
    assert document is not None
    snapshot = cast(dict[str, Any], dict(document))
    snapshot.pop("_id", None)
    return snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stm012_cli_republish_extraction_consumer_idempotency(
    mongo_client: AsyncMongoClient[Any],
    mongo_kafka_stack: tuple[str, str, str, str],
) -> None:
    _, bootstrap, mongo_ip, kafka_ip = mongo_kafka_stack
    archive_id = str(uuid.uuid4())
    user_id = f"stm012_user_{uuid.uuid4().hex[:8]}"
    session_id = str(uuid.uuid4())
    consumer_group = f"memory-extraction-group-stm012-{uuid.uuid4().hex}"

    await _insert_archive(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )

    first_cli = _run_republish_cli(
        archive_id=archive_id,
        user_id=user_id,
        mongo_ip=mongo_ip,
        kafka_ip=kafka_ip,
    )
    assert first_cli.returncode == 0, (
        f"first republish failed (exit {first_cli.returncode}): "
        f"stdout={first_cli.stdout[-500:]!r} stderr={first_cli.stderr[-500:]!r}"
    )

    raw_group_1 = f"stm012-raw-{uuid.uuid4().hex[:10]}"
    partition1, offset1, key1, payload1 = await _find_kafka_record(
        bootstrap,
        archive_id=archive_id,
        user_id=user_id,
        group_id=raw_group_1,
    )
    first_event_id = _assert_six_field_payload(
        key=key1,
        payload=payload1,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )

    pipeline1 = FakeCompletePipeline()
    processed1 = await _run_consumer_at_offset(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline1,
        group_id=consumer_group,
        partition=partition1,
        start_offset=offset1,
    )
    assert processed1 == 1
    assert pipeline1.calls == 1
    assert pipeline1.seen_task_archive_ids == [archive_id]
    assert pipeline1.seen_event_archive_ids == [archive_id]

    task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert task is not None
    assert task.archive_id == archive_id
    assert task.user_id == user_id
    assert task.status == ExtractionTaskStatus.COMPLETED
    assert task.attempt_count == 1
    assert uuid.UUID(task.task_id).version == 4
    assert task.created_time == FIXED_NOW
    assert task.updated_time == FIXED_NOW
    assert task.completed_time == FIXED_NOW
    assert task.last_error is None
    assert task.extraction_result is None
    task_snapshot = await _task_document_snapshot(mongo_client, archive_id)
    assert {"session_id", "event_id"}.isdisjoint(task_snapshot.keys())
    forbidden = {"session_id", "event_id"}
    assert forbidden.isdisjoint(task_snapshot.keys())

    committed1 = await _committed_offset(
        bootstrap,
        group_id=consumer_group,
        topic=TOPIC,
        partition=partition1,
    )
    assert committed1 == offset1 + 1

    second_cli = _run_republish_cli(
        archive_id=archive_id,
        user_id=user_id,
        mongo_ip=mongo_ip,
        kafka_ip=kafka_ip,
    )
    assert second_cli.returncode == 0, (
        f"second republish failed (exit {second_cli.returncode}): "
        f"stdout={second_cli.stdout[-500:]!r} stderr={second_cli.stderr[-500:]!r}"
    )

    raw_group_2 = f"stm012-raw-{uuid.uuid4().hex[:10]}"
    partition2, offset2, key2, payload2 = await _find_kafka_record(
        bootstrap,
        archive_id=archive_id,
        user_id=user_id,
        group_id=raw_group_2,
        exclude_event_ids={first_event_id},
    )

    second_event_id = _assert_six_field_payload(
        key=key2,
        payload=payload2,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )
    assert second_event_id != first_event_id

    pipeline2 = FakeCompletePipeline()
    processed2 = await _run_consumer_at_offset(
        bootstrap=bootstrap,
        mongo_client=mongo_client,
        pipeline=pipeline2,
        group_id=consumer_group,
        partition=partition2,
        start_offset=offset2,
    )
    assert processed2 == 1
    assert pipeline2.calls == 0
    assert pipeline1.calls + pipeline2.calls == 1

    db = mongo_client.get_default_database()
    assert db is not None
    count = await db[MEMORY_EXTRACTION_TASK_COLLECTION].count_documents(
        {"archive_id": archive_id}
    )
    assert count == 1

    task_after = await _task_document_snapshot(mongo_client, archive_id)
    assert task_after == task_snapshot

    committed2 = await _committed_offset(
        bootstrap,
        group_id=consumer_group,
        topic=TOPIC,
        partition=partition2,
    )
    assert committed2 == offset2 + 1
