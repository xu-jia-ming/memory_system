"""Integration tests for session creation against compose test Redis."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
import redis
import redis.asyncio as aioredis
from fastapi.testclient import TestClient

from memory_system.api.app import create_app
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_codec import hash_fields_to_meta
from memory_system.infrastructure.runtime import AppState
from memory_system.settings import get_settings

VALID_ENV: dict[str, str] = {
    "APP_ENV": "test",
    "REDIS__URI": "redis://redis:6379/0",
    "MONGODB__URI": "mongodb://mongodb:27017/memory_system",
    "KAFKA__BOOTSTRAP_SERVERS": "kafka:9092",
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
    "SILICONFLOW_API_KEY": "sk-example-replace-me",
}

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
REDIS_CONTAINER = "memory-system-redis-test"

UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

SESSION_PATH = "/api/v1/memory/session"


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


def _redis_container_ip() -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            REDIS_CONTAINER,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


@pytest.fixture(scope="module")
def test_redis() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available")
    _ensure_dotenv()
    _assert_test_isolation()
    _compose("up", "-d", "redis")
    deadline = time.time() + 60
    while time.time() < deadline:
        ip = _redis_container_ip()
        if ip:
            break
        time.sleep(2)
    else:
        pytest.skip("Test Redis container did not become ready in time")
    ip = _redis_container_ip()
    if not ip:
        pytest.skip("Could not resolve test Redis container IP")
    yield f"redis://{ip}:6379/0"
    _compose("down", check=False)


@pytest.fixture
def async_redis_client(test_redis: str) -> Iterator[aioredis.Redis]:
    client = aioredis.from_url(test_redis, decode_responses=True)
    yield client


@pytest.fixture
def redis_client(test_redis: str) -> Iterator[redis.Redis]:
    """Sync Redis client for post-request assertions (avoids event-loop conflicts)."""
    client = redis.from_url(test_redis, decode_responses=True)
    yield client
    client.close()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


def _minimal_app_state(redis_client: aioredis.Redis) -> AppState:
    settings = get_settings()
    return AppState(
        settings=settings,
        redis=redis_client,
        mongodb=MagicMock(),
        neo4j=MagicMock(),
        elasticsearch=MagicMock(),
        http_client=MagicMock(),
        kafka_producer=MagicMock(),
        kafka_producer_ready=True,
    )


@pytest.mark.integration
def test_session_create_writes_meta_hash_to_redis(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    valid_env: None,
) -> None:
    app_state = _minimal_app_state(async_redis_client)
    app = create_app(app_state=app_state)
    user_id = f"integration_user_{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        response = client.post(
            SESSION_PATH,
            json={"user_id": user_id},
            headers={"X-API-Key": VALID_ENV["MEMORY_API_KEY"]},
        )

    assert response.status_code == 200
    body = response.json()
    session_id = body["session_id"]
    assert body["status"] == "created"
    assert UUID_V4_PATTERN.match(session_id)
    uuid.UUID(session_id, version=4)

    meta_key = working_memory_meta_key(user_id, session_id)
    assert meta_key == f"memory:working:{user_id}:{session_id}"

    fields = cast(dict[str, str], redis_client.hgetall(meta_key))
    meta = hash_fields_to_meta(fields)
    assert meta.status.value == "active"
    assert meta.compression_version == 0
    assert meta.user_id == user_id
    assert meta.session_id == session_id
    assert fields["pending_archive_id"] == ""
    assert fields["pending_archive_batch_key"] == ""
    assert fields["pending_archive_message_count"] == "0"
    assert fields["pending_archive_estimated_tokens"] == "0"
    assert "null" not in fields.values()

    messages_key = working_memory_messages_key(user_id, session_id)
    message_ids_key = working_memory_message_ids_key(user_id, session_id)
    assert redis_client.exists(messages_key) == 0
    assert redis_client.exists(message_ids_key) == 0
    assert redis_client.ttl(meta_key) == -1

    redis_client.delete(meta_key)


@pytest.mark.integration
def test_session_create_user_isolation_and_duplicate_posts(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    valid_env: None,
) -> None:
    app_state = _minimal_app_state(async_redis_client)
    app = create_app(app_state=app_state)
    user_a = f"user_a_{uuid.uuid4().hex[:8]}"
    user_b = f"user_b_{uuid.uuid4().hex[:8]}"
    created_keys: list[str] = []

    with TestClient(app) as client:
        resp_a1 = client.post(
            SESSION_PATH,
            json={"user_id": user_a},
            headers={"X-API-Key": VALID_ENV["MEMORY_API_KEY"]},
        )
        resp_a2 = client.post(
            SESSION_PATH,
            json={"user_id": user_a},
            headers={"X-API-Key": VALID_ENV["MEMORY_API_KEY"]},
        )
        resp_b = client.post(
            SESSION_PATH,
            json={"user_id": user_b},
            headers={"X-API-Key": VALID_ENV["MEMORY_API_KEY"]},
        )

    assert resp_a1.status_code == 200
    assert resp_a2.status_code == 200
    assert resp_b.status_code == 200

    session_a1 = resp_a1.json()["session_id"]
    session_a2 = resp_a2.json()["session_id"]
    session_b = resp_b.json()["session_id"]
    assert session_a1 != session_a2

    key_a1 = working_memory_meta_key(user_a, session_a1)
    key_a2 = working_memory_meta_key(user_a, session_a2)
    key_b = working_memory_meta_key(user_b, session_b)
    created_keys.extend([key_a1, key_a2, key_b])

    assert redis_client.exists(key_a1) == 1
    assert redis_client.exists(key_a2) == 1
    assert redis_client.exists(key_b) == 1

    fields_b = cast(dict[str, str], redis_client.hgetall(key_b))
    assert fields_b["user_id"] == user_b
    assert fields_b["session_id"] == session_b

    redis_client.delete(*created_keys)


@pytest.mark.integration
def test_session_create_empty_user_id_returns_422(
    async_redis_client: aioredis.Redis,
    valid_env: None,
) -> None:
    app_state = _minimal_app_state(async_redis_client)
    app = create_app(app_state=app_state)
    with TestClient(app) as client:
        response = client.post(
            SESSION_PATH,
            json={"user_id": ""},
            headers={"X-API-Key": VALID_ENV["MEMORY_API_KEY"]},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
