"""Full-chain orchestration helpers for E2E-001 (HTTP → extract → retrieve → close)."""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import redis.asyncio as aioredis
from httpx import ASGITransport
from pymongo import AsyncMongoClient

from memory_system.api.app import create_app
from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.archive_event_republish import ArchiveEventRepublishInput
from memory_system.domain.models.context_archive import ContextArchive
from memory_system.domain.services.archive_event_republish_service import (
    republish_archive_created_event,
)
from memory_system.domain.services.production_extraction_pipeline import (
    BeforeRetrievalSyncHook,
    create_production_extraction_pipeline,
)
from memory_system.infrastructure.kafka.archive_created_consumer import (
    MEMORY_EXTRACTION_CONSUMER_GROUP,
)
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    find_extraction_task_by_archive_id,
)
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.runtime import AppState, create_app_state, shutdown_app_state
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.settings import get_settings
from tests.e2e.conftest import (
    COORDINATED_BUNDLE,
    KAFKA_CONTAINER,
    TEST_PROJECT,
    InfraStack,
    _compose,
    _patch_kafka_resolution,
)
from tests.e2e.helpers.con005_e2e_helpers import build_production_run_service
from tests.e2e.helpers.ext009_e2e_helpers import (
    FIXED_NOW,
    cleanup_ext009_data,
    run_worker_once,
    wait_for_archive_event,
)
from tests.e2e.helpers.stm_e2e_helpers import (
    API_KEY,
    TOPIC,
    cleanup_session_data,
    default_headers,
    list_archives_for_session,
    post_create_session,
    read_wm_meta,
    write_until_compression_trigger,
)
from tests.support.con005_neo4j_fixtures import read_memory_consolidation_state
from tests.support.fake_retrieval_index_embedding_client import FakeEmbeddingClient

KEYWORD = "e2e001fullchainkeyword"
E2E001_EVALUATION_TIME = FIXED_NOW + 100_000_000
EXTRACTION_WORKER_CONTAINER = "memory-system-extraction-worker-test"
SUCCESS_COMPRESSION_STATUSES = {
    CompressionStatus.COMPLETED,
    CompressionStatus.PARTIAL_COMPLETED,
}


@dataclass(frozen=True)
class E2E001AppRuntime:
    http_client: httpx.AsyncClient
    app_state: AppState
    settings: Any


def extraction_json_for_source(*, source_message_id: str, keyword: str = KEYWORD) -> str:
    """Fake extraction JSON with unique BM25 keyword; source id must exist in Archive."""
    return json.dumps(
        {
            "entities": [
                {
                    "local_entity_id": "entity_1",
                    "name": "E2E001 Full Chain Project",
                    "type": "project",
                    "aliases": [keyword],
                }
            ],
            "memories": [
                {
                    "memory_type": "fact",
                    "content": f"用户正在开发 {keyword} 记忆系统",
                    "subject_entity_id": "user",
                    "predicate": "works_on",
                    "object_entity_id": "entity_1",
                    "object_value": None,
                    "event_status": None,
                    "start_time": None,
                    "end_time": None,
                    "original_time_text": None,
                    "confidence": 0.95,
                    "source_message_ids": [source_message_id],
                }
            ],
        }
    )


def first_user_message_id(archive: ContextArchive) -> str:
    for message in archive.messages:
        if message.role == MessageRole.USER:
            return message.message_id
    raise AssertionError("archive has no user-role message")


def assert_request_id_echo(response: httpx.Response, request_id: str) -> None:
    assert response.headers["X-Request-ID"] == request_id


def _configure_e2e001_env(monkeypatch: Any, infra_stack: InfraStack) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("REDIS__URI", infra_stack.redis_url)
    monkeypatch.setenv("MONGODB__URI", infra_stack.mongo_url)
    monkeypatch.setenv("KAFKA__BOOTSTRAP_SERVERS", infra_stack.kafka_bootstrap)
    monkeypatch.setenv("NEO4J__URI", f"neo4j://{infra_stack.neo4j_ip}:7687")
    monkeypatch.setenv("ELASTICSEARCH__URL", infra_stack.elasticsearch_url)
    monkeypatch.setenv("MEMORY_API_KEY", API_KEY)
    monkeypatch.setenv("MEMORY_ADMIN_API_KEY", "dev-memory-admin-key-change-me")
    monkeypatch.setenv("LLM__BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM__API_KEY", "sk-example-replace-me")
    monkeypatch.setenv("LLM__COMPRESSION__MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM__EXTRACTION__MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("EMBEDDING__MODEL_ID", "BAAI/bge-m3")
    monkeypatch.setenv("EMBEDDING__BASE_URL", "http://embedding-service:80")
    monkeypatch.setenv("PROXY__HTTP_URL", "")
    monkeypatch.setenv("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    monkeypatch.setenv("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-example-replace-me")
    for key, value in COORDINATED_BUNDLE.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _install_fake_retrieval_clients(monkeypatch: Any) -> None:
    def fake_embedding_factory(_settings: Any, _http_client: Any) -> FakeEmbeddingClient:
        return FakeEmbeddingClient()

    def fake_tokenize_factory(_settings: Any, _http_client: Any) -> FakeTokenizeClient:
        return FakeTokenizeClient(token_count=10)

    monkeypatch.setattr(
        "memory_system.domain.services.retrieval_api_service.create_embedding_client",
        fake_embedding_factory,
    )
    monkeypatch.setattr(
        "memory_system.domain.services.retrieval_api_service.TeiTokenizeClient",
        fake_tokenize_factory,
    )


@asynccontextmanager
async def build_e2e001_app_client(
    infra_stack: InfraStack,
    monkeypatch: Any,
    *,
    llm_client: FakeLlmClient | None = None,
) -> AsyncIterator[E2E001AppRuntime]:
    """In-process FastAPI + Fake compression LLM + Fake retrieval embedding/tokenize."""
    _configure_e2e001_env(monkeypatch, infra_stack)
    _install_fake_retrieval_clients(monkeypatch)
    resolved_llm = llm_client or FakeLlmClient(
        success_content='{"compressed_context":"e2e001 compressed summary"}',
    )
    with _patch_kafka_resolution(infra_stack.kafka_ip):
        settings = get_settings()
        app_state = await create_app_state(settings)
        app = create_app(
            settings=settings,
            app_state=app_state,
            llm_client=resolved_llm,
        )
        app.state.app_state = app_state
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            timeout=60.0,
            headers=default_headers(),
        ) as client:
            try:
                yield E2E001AppRuntime(
                    http_client=client,
                    app_state=app_state,
                    settings=settings,
                )
            finally:
                await shutdown_app_state(app_state)


def build_e2e001_pipeline(
    mongodb: AsyncMongoClient[Any],
    runtime: Any,
    *,
    success_content: str | None = None,
    llm_client: FakeLlmClient | None = None,
    before_retrieval_sync_hook: BeforeRetrievalSyncHook | None = None,
    embedding_fail: bool = False,
) -> tuple[Any, FakeLlmClient]:
    resolved_llm = llm_client or FakeLlmClient(
        success_content=success_content or extraction_json_for_source(source_message_id="unused"),
    )
    pipeline = create_production_extraction_pipeline(
        mongodb,
        runtime.neo4j_driver,
        runtime.elasticsearch,
        runtime.http_client,
        runtime.settings,
        llm_client=resolved_llm,
        tokenize_client=FakeTokenizeClient(token_count=10),
        embedding_client=FakeEmbeddingClient(fail=embedding_fail),
        clock=lambda: FIXED_NOW,
        server_time_provider=lambda: FIXED_NOW + 10,
        before_retrieval_sync_hook=before_retrieval_sync_hook,
    )
    return pipeline, resolved_llm


async def create_session_via_http(
    client: httpx.AsyncClient,
    *,
    user_id: str,
    request_id: str,
) -> str:
    response = await post_create_session(client, user_id=user_id, request_id=request_id)
    assert response.status_code == 200, response.text
    assert_request_id_echo(response, request_id)
    body = response.json()
    assert body["status"] == "created"
    session_id = body["session_id"]
    assert isinstance(session_id, str) and session_id
    return session_id


async def assert_compression_succeeded(
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    *,
    user_id: str,
    session_id: str,
    trigger_response: httpx.Response,
) -> list[ContextArchive]:
    """MF-2: write_until_compression_trigger is drive-only; require compression success."""
    body = trigger_response.json()
    assert body["compression_status"] in SUCCESS_COMPRESSION_STATUSES
    meta = await read_wm_meta(redis_client, user_id, session_id)
    assert meta is not None
    assert meta.compressed_context.strip()
    assert meta.pending_archive_id is None
    archives = await list_archives_for_session(mongo_client, session_id)
    assert archives, "Mongo Archive missing after compression"
    for archive in archives:
        assert archive.messages, "archive.messages must be retained"
        assert archive.user_id == user_id
    return archives


async def drive_compression_succeeded(
    client: httpx.AsyncClient,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    *,
    user_id: str,
    session_id: str,
) -> tuple[httpx.Response, list[ContextArchive]]:
    trigger = get_settings().context.compression_trigger_tokens
    trigger_response = await write_until_compression_trigger(
        client,
        redis_client,
        user_id=user_id,
        session_id=session_id,
        trigger=trigger,
    )
    archives = await assert_compression_succeeded(
        redis_client,
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        trigger_response=trigger_response,
    )
    return trigger_response, archives


async def run_extraction_for_archive(
    *,
    mongodb: AsyncMongoClient[Any],
    infra_stack: InfraStack,
    ext009_runtime: Any,
    archive: ContextArchive,
    group_id: str,
    llm_client: FakeLlmClient | None = None,
    before_retrieval_sync_hook: BeforeRetrievalSyncHook | None = None,
    expect_completed: bool = True,
) -> tuple[Any, FakeLlmClient, int, int]:
    source_id = first_user_message_id(archive)
    pipeline, llm = build_e2e001_pipeline(
        mongodb,
        ext009_runtime,
        success_content=extraction_json_for_source(source_message_id=source_id),
        llm_client=llm_client,
        before_retrieval_sync_hook=before_retrieval_sync_hook,
    )
    partition, offset, _event = await wait_for_archive_event(
        bootstrap_servers=infra_stack.kafka_bootstrap,
        archive_id=archive.archive_id,
        user_id=archive.user_id,
        group_id=f"e2e001-wait-{uuid.uuid4().hex[:8]}",
    )
    processed = await run_worker_once(
        mongodb=mongodb,
        bootstrap_servers=infra_stack.kafka_bootstrap,
        pipeline=pipeline,
        partition=partition,
        offset=offset,
        group_id=group_id,
    )
    if expect_completed:
        assert processed == 1
        task = await find_extraction_task_by_archive_id(mongodb, archive.archive_id)
        assert task is not None
        assert task.status == ExtractionTaskStatus.COMPLETED
    return pipeline, llm, partition, offset


async def republish_archive(
    *,
    mongodb: AsyncMongoClient[Any],
    kafka_producer: Any,
    settings: Any,
    archive_id: str,
    user_id: str,
) -> str:
    result = await republish_archive_created_event(
        mongodb=mongodb,
        kafka_producer=kafka_producer,
        topic=settings.kafka.topic,
        input=ArchiveEventRepublishInput(
            archive_id=archive_id,
            expected_user_id=user_id,
        ),
    )
    assert result.status.value == "success", result
    assert result.event_id is not None
    return result.event_id


async def cleanup_e2e001_data(
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Any,
    *,
    user_id: str,
    session_id: str,
    extra_user_ids: list[str] | None = None,
) -> None:
    archives = await list_archives_for_session(mongo_client, session_id)
    await cleanup_session_data(redis_client, mongo_client, user_id, session_id)
    if archives:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archives[0].archive_id,
        )
        for archive in archives[1:]:
            await cleanup_ext009_data(
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                archive_id=archive.archive_id,
            )
    else:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id="missing",
        )
    for other in extra_user_ids or []:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=other,
            archive_id="missing",
        )


async def assert_redis_wm_gone(
    redis_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> None:
    assert await redis_client.exists(working_memory_meta_key(user_id, session_id)) == 0
    assert await redis_client.exists(working_memory_messages_key(user_id, session_id)) == 0
    assert await redis_client.exists(working_memory_message_ids_key(user_id, session_id)) == 0


def _kafka_exec(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", KAFKA_CONTAINER, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def describe_extraction_consumer_group() -> str:
    result = _kafka_exec(
        "/opt/kafka/bin/kafka-consumer-groups.sh",
        "--bootstrap-server",
        "localhost:9092",
        "--group",
        MEMORY_EXTRACTION_CONSUMER_GROUP,
        "--describe",
    )
    return f"{result.stdout}\n{result.stderr}"


def topic_has_records() -> bool:
    result = _kafka_exec(
        "/opt/kafka/bin/kafka-get-offsets.sh",
        "--bootstrap-server",
        "localhost:9092",
        "--topic",
        TOPIC,
    )
    text = f"{result.stdout}\n{result.stderr}"
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        parts = stripped.rsplit(":", 1)
        if len(parts) != 2:
            continue
        try:
            offset = int(parts[1])
        except ValueError:
            continue
        if offset > 0:
            return True
    return False


def parse_group_lag(describe_output: str) -> int | None:
    if "does not exist" in describe_output.lower():
        return None
    lags: list[int] = []
    for line in describe_output.splitlines():
        columns = line.split()
        if len(columns) < 6 or columns[0] in {"GROUP", "Consumer"}:
            continue
        if TOPIC not in columns:
            continue
        try:
            lags.append(int(columns[5]))
        except ValueError:
            continue
    if not lags:
        return None
    return sum(lags)


async def drain_production_extraction_group(bootstrap_servers: str) -> None:
    """Advance memory-extraction-group to log end without invoking the LLM pipeline."""
    from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id=MEMORY_EXTRACTION_CONSUMER_GROUP,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        max_poll_records=50,
    )
    await consumer.start()
    try:
        deadline = time.monotonic() + 20
        idle_rounds = 0
        while time.monotonic() < deadline:
            batch = await consumer.getmany(timeout_ms=1000, max_records=50)
            count = sum(len(records) for records in batch.values())
            if count == 0:
                idle_rounds += 1
                if idle_rounds >= 2:
                    break
                continue
            idle_rounds = 0
            await consumer.commit()
        await consumer.commit()
    finally:
        await consumer.stop()


async def assert_extraction_group_idle(bootstrap_servers: str) -> None:
    describe = describe_extraction_consumer_group()
    lag = parse_group_lag(describe)
    if lag is None:
        if topic_has_records():
            await drain_production_extraction_group(bootstrap_servers)
    elif lag > 0:
        await drain_production_extraction_group(bootstrap_servers)
    describe_after = describe_extraction_consumer_group()
    lag_after = parse_group_lag(describe_after)
    if lag_after is None:
        assert not topic_has_records(), (
            "leftover context.archive.created events exist; "
            "must not start memory-extraction-worker"
        )
        return
    assert lag_after == 0, f"extraction group lag={lag_after} describe={describe_after}"


def extraction_worker_running() -> bool:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{.State.Running}}",
            EXTRACTION_WORKER_CONTAINER,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def extraction_worker_logs() -> str:
    result = subprocess.run(
        ["docker", "logs", EXTRACTION_WORKER_CONTAINER],
        capture_output=True,
        text=True,
        check=False,
    )
    return f"{result.stdout}\n{result.stderr}"


def start_extraction_worker() -> None:
    config_result = _compose("config", "--format", "json")
    assert TEST_PROJECT in config_result.stdout
    _compose("up", "-d", "memory-extraction-worker")
    deadline = time.time() + 60
    while time.time() < deadline:
        if extraction_worker_running():
            return
        time.sleep(1)
    raise AssertionError("memory-extraction-worker did not start")


def stop_extraction_worker() -> None:
    subprocess.run(
        ["docker", "stop", EXTRACTION_WORKER_CONTAINER],
        capture_output=True,
        text=True,
        check=False,
    )


def assert_no_llm_http(logs: str) -> None:
    lowered = logs.lower()
    assert "/chat/completions" not in lowered
    assert "api.deepseek.com/v1" not in lowered
    assert "http request: post https://api.deepseek.com" not in lowered


def build_consolidation_run_service(ext009_runtime: Any) -> Any:
    return build_production_run_service(ext009_runtime.neo4j_driver, ext009_runtime.settings)


async def read_memory_version_and_consolidated(
    ext009_runtime: Any,
    *,
    user_id: str,
    memory_id: str,
) -> tuple[int | None, int]:
    state = await read_memory_consolidation_state(
        ext009_runtime.neo4j_driver,
        user_id,
        memory_id,
    )
    return state.last_consolidated_time, state.memory_version
