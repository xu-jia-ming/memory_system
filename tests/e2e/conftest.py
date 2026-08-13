"""Compose fixtures and backend clients for STM-013 E2E tests."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
import redis.asyncio as aioredis
from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from elasticsearch import AsyncElasticsearch
from httpx import ASGITransport
from neo4j import AsyncDriver, AsyncGraphDatabase
from pymongo import AsyncMongoClient

from memory_system.api.app import create_app
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.runtime import create_app_state, shutdown_app_state
from memory_system.settings import get_settings
from tests.e2e.helpers.stm_e2e_helpers import API_KEY, TOPIC, default_headers

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
DOTENV_PATH = REPO_ROOT / ".env"

TEST_PROJECT = "memory-system-test"
REDIS_CONTAINER = "memory-system-redis-test"
KAFKA_CONTAINER = "memory-system-kafka-test"
MONGODB_CONTAINER = "memory-system-mongodb-test"
NEO4J_CONTAINER = "memory-system-neo4j-test"
ELASTICSEARCH_CONTAINER = "memory-system-elasticsearch-test"
API_CONTAINER = "memory-system-api-test"

COORDINATED_BUNDLE: dict[str, str] = {
    "CONTEXT__COMPRESSION_TRIGGER_TOKENS": "200",
    "CONTEXT__COMPRESSION_TARGET_TOKENS": "80",
    "CONTEXT__MAX_COMPRESSED_CONTEXT_ESTIMATED_TOKENS": "100",
    "CONTEXT__PREFERRED_RECENT_MESSAGES": "2",
    "CONTEXT__ABSOLUTE_MIN_RECENT_MESSAGES": "2",
}


@dataclass(frozen=True)
class DotenvBackup:
    existed: bool
    content: str | None


@dataclass(frozen=True)
class InfraStack:
    redis_url: str
    kafka_bootstrap: str
    mongo_url: str
    kafka_ip: str
    redis_ip: str
    mongo_ip: str
    neo4j_ip: str
    elasticsearch_url: str


@dataclass(frozen=True)
class FullContainerStack(InfraStack):
    api_base_url: str
    compression_trigger_tokens: int


@dataclass(frozen=True)
class Ext009Runtime:
    settings: Any
    neo4j_driver: AsyncDriver
    elasticsearch: AsyncElasticsearch
    http_client: httpx.AsyncClient


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


def _backup_dotenv() -> DotenvBackup:
    if DOTENV_PATH.exists():
        return DotenvBackup(existed=True, content=DOTENV_PATH.read_text(encoding="utf-8"))
    return DotenvBackup(existed=False, content=None)


def _restore_dotenv(backup: DotenvBackup) -> None:
    if backup.existed:
        assert backup.content is not None
        DOTENV_PATH.write_text(backup.content, encoding="utf-8")
    elif DOTENV_PATH.exists():
        DOTENV_PATH.unlink()


def _write_coordinated_bundle() -> None:
    if not DOTENV_PATH.exists():
        shutil.copy(ENV_EXAMPLE, DOTENV_PATH)
    lines = DOTENV_PATH.read_text(encoding="utf-8").splitlines()
    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in COORDINATED_BUNDLE:
                new_lines.append(f"{key}={COORDINATED_BUNDLE[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)
    for key, value in COORDINATED_BUNDLE.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")
    DOTENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


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


def _read_container_compression_trigger() -> int:
    result = subprocess.run(
        [
            "docker",
            "exec",
            API_CONTAINER,
            "python",
            "-c",
            (
                "from memory_system.settings import get_settings; "
                "print(get_settings().context.compression_trigger_tokens)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"failed to read container ContextSettings: {result.stderr or result.stdout}"
        )
    return int(result.stdout.strip())


def _assert_config_parity(container_trigger: int) -> None:
    get_settings.cache_clear()
    host_trigger = get_settings().context.compression_trigger_tokens
    assert host_trigger == container_trigger, (
        f"host/container ContextSettings mismatch: host={host_trigger} "
        f"container={container_trigger}"
    )


async def _poll_api_ready(base_url: str, *, deadline_seconds: float = 180.0) -> None:
    deadline = time.time() + deadline_seconds
    last_status: str | None = None
    last_body: str | None = None
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        while time.time() < deadline:
            try:
                response = await client.get("/health/ready")
                last_status = str(response.status_code)
                last_body = response.text[:500]
                if response.status_code == 200:
                    payload = response.json()
                    checks = payload.get("checks", {})
                    if payload.get("status") == "ready" and checks.get("migrations") == "ready":
                        return
            except httpx.HTTPError as exc:
                last_status = "http_error"
                last_body = str(exc)
            await asyncio.sleep(2)
    logs = subprocess.run(
        ["docker", "logs", API_CONTAINER],
        capture_output=True,
        text=True,
        check=False,
    )
    log_tail = (logs.stdout + logs.stderr)[-1500:]
    raise AssertionError(
        f"memory-api not ready at {base_url} within {deadline_seconds}s; "
        f"last_status={last_status!r} last_body={last_body!r}; "
        f"container_logs_tail={log_tail!r}"
    )


def _wait_containers_exist(
    container_names: tuple[str, ...],
    *,
    deadline_seconds: float = 120,
) -> None:
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        if all(
            subprocess.run(["docker", "inspect", name], capture_output=True, check=False).returncode
            == 0
            for name in container_names
        ):
            return
        time.sleep(2)
    missing = [
        name
        for name in container_names
        if subprocess.run(["docker", "inspect", name], capture_output=True, check=False).returncode
        != 0
    ]
    raise AssertionError(f"containers not created within {deadline_seconds}s: {missing}")


def _wait_containers_healthy(
    container_names: tuple[str, ...],
    *,
    deadline_seconds: float = 180,
) -> None:
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        all_healthy = True
        for name in container_names:
            inspect = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Health.Status}}", name],
                capture_output=True,
                text=True,
                check=False,
            )
            if inspect.returncode != 0 or inspect.stdout.strip() != "healthy":
                all_healthy = False
                break
        if all_healthy:
            return
        time.sleep(3)
    statuses: list[str] = []
    for name in container_names:
        inspect = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}} health={{.State.Health.Status}}", name],
            capture_output=True,
            text=True,
            check=False,
        )
        statuses.append(f"{name}={inspect.stdout.strip() or 'missing'}")
    raise AssertionError(
        f"containers not healthy within {deadline_seconds}s: " + ", ".join(statuses)
    )


def _wait_container_running(name: str, *, deadline_seconds: float = 120) -> None:
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                name,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip() == "true":
            return
        time.sleep(2)
    raise AssertionError(f"container {name} not running within {deadline_seconds}s")


def _poll_infra_ips() -> tuple[str, str, str, str, str]:
    deadline = time.time() + 120
    redis_ip = kafka_ip = mongo_ip = neo4j_ip = es_ip = None
    while time.time() < deadline:
        redis_ip = _container_ip(REDIS_CONTAINER)
        kafka_ip = _container_ip(KAFKA_CONTAINER)
        mongo_ip = _container_ip(MONGODB_CONTAINER)
        neo4j_ip = _container_ip(NEO4J_CONTAINER)
        es_ip = _container_ip(ELASTICSEARCH_CONTAINER)
        if redis_ip and kafka_ip and mongo_ip and neo4j_ip and es_ip:
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
        raise AssertionError("infra stack not ready")
    assert redis_ip and kafka_ip and mongo_ip and neo4j_ip and es_ip
    return redis_ip, kafka_ip, mongo_ip, neo4j_ip, es_ip


@contextmanager
def _patch_kafka_resolution(kafka_ip: str) -> Iterator[None]:
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
        yield
    finally:
        socket.getaddrinfo = real_getaddrinfo


def _start_infra() -> InfraStack:
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT

    _compose("up", "-d", "redis", "mongodb", "kafka", "neo4j", "elasticsearch")
    infra_containers = (
        REDIS_CONTAINER,
        MONGODB_CONTAINER,
        KAFKA_CONTAINER,
        NEO4J_CONTAINER,
        ELASTICSEARCH_CONTAINER,
    )
    _wait_containers_exist(infra_containers)
    _wait_containers_healthy(infra_containers)
    redis_ip, kafka_ip, mongo_ip, neo4j_ip, es_ip = _poll_infra_ips()
    migrate = _compose("run", "--rm", "init-infra", check=False)
    if migrate.returncode != 0:
        raise AssertionError(f"init-infra failed: {migrate.stderr[-500:]}")
    _ensure_topic()
    return InfraStack(
        redis_url=f"redis://{redis_ip}:6379/0",
        kafka_bootstrap=f"{kafka_ip}:9092",
        mongo_url=f"mongodb://{mongo_ip}:27017/memory_system",
        kafka_ip=kafka_ip,
        redis_ip=redis_ip,
        mongo_ip=mongo_ip,
        neo4j_ip=neo4j_ip,
        elasticsearch_url=f"http://{es_ip}:9200",
    )


@pytest.fixture(scope="module")
def e2e_dotenv() -> Iterator[DotenvBackup]:
    if not _docker_available():
        pytest.skip("Docker not available")
    backup = _backup_dotenv()
    _write_coordinated_bundle()
    try:
        yield backup
    finally:
        _restore_dotenv(backup)


@pytest.fixture(scope="module")
def infra_stack(e2e_dotenv: DotenvBackup) -> Iterator[InfraStack]:
    del e2e_dotenv
    _compose("down", "--remove-orphans", check=False)
    stack = _start_infra()
    with _patch_kafka_resolution(stack.kafka_ip):
        yield stack
    _compose("down", "--remove-orphans", check=False)


@pytest.fixture(scope="module")
def full_container_stack(infra_stack: InfraStack) -> Iterator[FullContainerStack]:
    _compose("up", "-d", "memory-api")
    _wait_container_running(API_CONTAINER)
    api_ip = None
    deadline = time.time() + 120
    while time.time() < deadline:
        api_ip = _container_ip(API_CONTAINER)
        if api_ip:
            break
        time.sleep(2)
    if not api_ip:
        pytest.skip("memory-api container IP not available")

    api_base_url = f"http://{api_ip}:8000"
    asyncio.run(_poll_api_ready(api_base_url))
    container_trigger = _read_container_compression_trigger()
    _assert_config_parity(container_trigger)
    yield FullContainerStack(
        redis_url=infra_stack.redis_url,
        kafka_bootstrap=infra_stack.kafka_bootstrap,
        mongo_url=infra_stack.mongo_url,
        kafka_ip=infra_stack.kafka_ip,
        redis_ip=infra_stack.redis_ip,
        mongo_ip=infra_stack.mongo_ip,
        neo4j_ip=infra_stack.neo4j_ip,
        elasticsearch_url=infra_stack.elasticsearch_url,
        api_base_url=api_base_url,
        compression_trigger_tokens=container_trigger,
    )


@pytest.fixture(scope="module")
def authoritative_context_settings(e2e_dotenv: DotenvBackup) -> int:
    del e2e_dotenv
    get_settings.cache_clear()
    return get_settings().context.compression_trigger_tokens


@pytest.fixture
async def memory_api_client(
    full_container_stack: FullContainerStack,
) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        base_url=full_container_stack.api_base_url,
        timeout=60.0,
        headers=default_headers(),
    ) as client:
        yield client


@pytest.fixture
async def redis_client(infra_stack: InfraStack) -> AsyncIterator[aioredis.Redis]:
    client = aioredis.from_url(infra_stack.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def mongo_client(infra_stack: InfraStack) -> AsyncIterator[AsyncMongoClient[Any]]:
    client: AsyncMongoClient[Any] = AsyncMongoClient(infra_stack.mongo_url)
    try:
        await client.admin.command("ping")
        yield client
    finally:
        await client.close()


@pytest.fixture
async def kafka_producer(infra_stack: InfraStack) -> AsyncIterator[AIOKafkaProducer]:
    producer = AIOKafkaProducer(
        bootstrap_servers=infra_stack.kafka_bootstrap,
        acks="all",
        enable_idempotence=True,
    )
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()


@pytest.fixture
async def ext009_runtime(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Ext009Runtime]:
    """EXT-009 in-process stage clients; provider calls remain fake in tests."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MONGODB__URI", infra_stack.mongo_url)
    monkeypatch.setenv("KAFKA__BOOTSTRAP_SERVERS", infra_stack.kafka_bootstrap)
    monkeypatch.setenv("NEO4J__URI", f"neo4j://{infra_stack.neo4j_ip}:7687")
    monkeypatch.setenv("ELASTICSEARCH__URL", infra_stack.elasticsearch_url)
    monkeypatch.setenv("LLM__BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM__API_KEY", "sk-example-replace-me")
    monkeypatch.setenv("LLM__COMPRESSION__MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM__EXTRACTION__MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("EMBEDDING__MODEL_ID", "BAAI/bge-m3")
    monkeypatch.setenv("EMBEDDING__BASE_URL", "http://embedding-service:80")
    monkeypatch.setenv("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    monkeypatch.setenv("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-example-replace-me")
    get_settings.cache_clear()
    settings = get_settings()
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
    http_client = httpx.AsyncClient()
    try:
        await elasticsearch.info()
        async with neo4j_driver.session() as session:
            await session.run("RETURN 1")
        yield Ext009Runtime(
            settings=settings,
            neo4j_driver=neo4j_driver,
            elasticsearch=elasticsearch,
            http_client=http_client,
        )
    finally:
        await elasticsearch.close()
        await neo4j_driver.close()
        await http_client.aclose()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def hybrid_api_client(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
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
    with _patch_kafka_resolution(infra_stack.kafka_ip):
        settings = get_settings()
        app_state = await create_app_state(settings)
        app = create_app(
            settings=settings,
            app_state=app_state,
            llm_client=FakeLlmClient(mode="timeout"),
        )
        # ASGITransport does not run FastAPI lifespan; routes read request.app.state.app_state.
        app.state.app_state = app_state
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            timeout=60.0,
            headers=default_headers(),
        ) as client:
            try:
                yield client
            finally:
                await shutdown_app_state(app_state)
