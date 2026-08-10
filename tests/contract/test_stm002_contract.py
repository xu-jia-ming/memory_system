"""Contract tests for STM-002 session creation API."""

from __future__ import annotations

import importlib
import re
import uuid
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from memory_system.api.app import create_app
from memory_system.infrastructure.runtime import AppState
from memory_system.settings import get_settings

_es_mod = importlib.import_module("scripts.migrations.003_elasticsearch_memory_v1")
MEMORY_RETRIEVAL_V1_MAPPINGS = _es_mod.MEMORY_RETRIEVAL_V1_MAPPINGS

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

UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

SESSION_PATH = "/api/v1/memory/session"


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


class _InMemoryRedis:
    """Minimal async Redis mock with Hash storage for contract tests."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}

    async def ping(self) -> bool:
        return True

    async def hset(self, key: str, mapping: dict[str, str] | None = None, **kwargs: Any) -> int:
        if mapping is None:
            return 0
        self._hashes[key] = dict(mapping)
        return len(mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    async def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if key in self._hashes)


@pytest.fixture
def session_app_state(valid_env: None) -> AppState:
    settings = get_settings()
    redis_client = _InMemoryRedis()

    collection = MagicMock()
    collection.find_one = AsyncMock(
        side_effect=lambda query: {"migration_id": query["migration_id"]}
    )
    database = MagicMock()
    database.__getitem__ = MagicMock(return_value=collection)
    mongodb_client = MagicMock()
    mongodb_client.admin = MagicMock()
    mongodb_client.admin.command = AsyncMock(return_value={"ok": 1})
    mongodb_client.__getitem__ = MagicMock(return_value=database)

    neo4j_session = MagicMock()
    neo4j_session.run = AsyncMock()
    neo4j_session.__aenter__ = AsyncMock(return_value=neo4j_session)
    neo4j_session.__aexit__ = AsyncMock(return_value=None)
    neo4j_driver = MagicMock()
    neo4j_driver.session = MagicMock(return_value=neo4j_session)

    elasticsearch_client = MagicMock()
    elasticsearch_client.info = AsyncMock(
        return_value={"version": {"number": settings.memory_retrieval.elasticsearch_version}}
    )
    elasticsearch_client.indices = MagicMock()
    elasticsearch_client.indices.exists_alias = AsyncMock(return_value=True)
    alias_name = settings.memory_retrieval.index_name
    elasticsearch_client.indices.get_alias = AsyncMock(
        return_value={"memory_retrieval_v1": {"aliases": {alias_name: {}}}}
    )
    elasticsearch_client.indices.get_mapping = AsyncMock(
        return_value={
            "memory_retrieval_v1": {
                "mappings": MEMORY_RETRIEVAL_V1_MAPPINGS,
            }
        }
    )

    http_client = MagicMock()
    http_response = MagicMock()
    http_response.status_code = 200
    http_client.get = AsyncMock(return_value=http_response)

    kafka_producer = MagicMock()
    kafka_producer._closed = False
    kafka_producer.client = MagicMock()
    kafka_producer.client.bootstrap_connected = MagicMock(return_value=True)

    return AppState(
        settings=settings,
        redis=redis_client,  # type: ignore[arg-type]
        mongodb=mongodb_client,
        neo4j=neo4j_driver,
        elasticsearch=elasticsearch_client,
        http_client=http_client,
        kafka_producer=kafka_producer,
        kafka_producer_ready=True,
    )


@pytest.fixture
def client(session_app_state: AppState) -> Iterator[TestClient]:
    app = create_app(app_state=session_app_state)
    with TestClient(app) as test_client:
        yield test_client


def _auth_headers(**extra: str) -> dict[str, str]:
    headers = {"X-API-Key": VALID_ENV["MEMORY_API_KEY"]}
    headers.update(extra)
    return headers


def test_create_session_without_api_key(client: TestClient) -> None:
    response = client.post(SESSION_PATH, json={"user_id": "user_001"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_create_session_with_wrong_api_key(client: TestClient) -> None:
    response = client.post(
        SESSION_PATH,
        json={"user_id": "user_001"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_create_session_success_with_memory_key(client: TestClient) -> None:
    response = client.post(
        SESSION_PATH,
        json={"user_id": "user_001"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert UUID_V4_PATTERN.match(body["session_id"])
    uuid.UUID(body["session_id"], version=4)
    assert body["status"] == "created"
    assert "compression_version" not in body
    assert "request_id" not in body
    assert response.headers.get("X-Request-ID")


def test_create_session_success_with_admin_key(client: TestClient) -> None:
    response = client.post(
        SESSION_PATH,
        json={"user_id": "user_001"},
        headers={"X-API-Key": VALID_ENV["MEMORY_ADMIN_API_KEY"]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "created"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_id": ""},
    ],
)
def test_create_session_validation_error(client: TestClient, payload: dict[str, str]) -> None:
    response = client.post(SESSION_PATH, json=payload, headers=_auth_headers())
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert "request_id" in body
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_create_session_missing_user_id_field(client: TestClient) -> None:
    response = client.post(SESSION_PATH, json={}, headers=_auth_headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_session_same_user_two_posts_distinct_sessions(client: TestClient) -> None:
    first = client.post(
        SESSION_PATH,
        json={"user_id": "user_001"},
        headers=_auth_headers(),
    )
    second = client.post(
        SESSION_PATH,
        json={"user_id": "user_001"},
        headers=_auth_headers(),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["session_id"] != second.json()["session_id"]


def test_create_session_request_id_passthrough(client: TestClient) -> None:
    request_id = "123e4567-e89b-42d3-a456-426614174000"
    response = client.post(
        SESSION_PATH,
        json={"user_id": "user_001"},
        headers=_auth_headers(**{"X-Request-ID": request_id}),
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_create_session_redis_failure_returns_error(
    valid_env: None,
    session_app_state: AppState,
) -> None:
    failing_redis = MagicMock()
    failing_redis.ping = AsyncMock(return_value=True)
    failing_redis.hset = AsyncMock(side_effect=ConnectionError("redis down"))
    session_app_state.redis = failing_redis

    app = create_app(app_state=session_app_state)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            SESSION_PATH,
            json={"user_id": "user_001"},
            headers=_auth_headers(),
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "internal_error"
