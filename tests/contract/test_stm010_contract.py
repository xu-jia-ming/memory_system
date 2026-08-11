"""Contract tests for STM-010 session close API."""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from memory_system.api.app import create_app
from memory_system.domain.models.session_close import SessionCloseResult
from memory_system.domain.services.session_close_service import (
    SessionCloseIncompleteError,
    SessionNotFoundCloseError,
)
from memory_system.infrastructure.llm import FakeLlmClient
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

USER_ID = "user_001"
SESSION_ID = str(uuid.uuid4())


def _close_path(user_id: str = USER_ID, session_id: str = SESSION_ID) -> str:
    return f"/api/v1/memory/session/{user_id}/{session_id}/close"


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def app_state(valid_env: None) -> AppState:
    settings = get_settings()
    redis_client = MagicMock()
    redis_client.ping = AsyncMock(return_value=True)

    mongodb_client = MagicMock()
    mongodb_client.admin = MagicMock()
    mongodb_client.admin.command = AsyncMock(return_value={"ok": 1})

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
        redis=redis_client,
        mongodb=mongodb_client,
        neo4j=neo4j_driver,
        elasticsearch=elasticsearch_client,
        http_client=http_client,
        kafka_producer=kafka_producer,
        kafka_producer_ready=True,
    )


@pytest.fixture
def client(app_state: AppState) -> Iterator[TestClient]:
    app = create_app(app_state=app_state, llm_client=FakeLlmClient())
    with TestClient(app) as test_client:
        yield test_client


def _auth_headers(**extra: str) -> dict[str, str]:
    headers = {"X-API-Key": VALID_ENV["MEMORY_API_KEY"]}
    headers.update(extra)
    return headers


def test_c1_close_endpoint_exists(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        return_value=SessionCloseResult(
            session_id=SESSION_ID,
            archive_ids=[],
            status="closed",
        ),
    ):
        response = client.post(_close_path(), headers=_auth_headers())
    assert response.status_code == 200


def test_c2_no_api_key(client: TestClient) -> None:
    response = client.post(_close_path())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_c3_invalid_path_params(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/memory/session/{' '}/{SESSION_ID}/close",
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_c4_request_id(client: TestClient) -> None:
    request_id = "123e4567-e89b-42d3-a456-426614174000"
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        return_value=SessionCloseResult(
            session_id=SESSION_ID,
            archive_ids=[],
            status="closed",
        ),
    ):
        response = client.post(
            _close_path(),
            headers=_auth_headers(**{"X-Request-ID": request_id}),
        )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_c5_success_envelope(client: TestClient) -> None:
    archive_ids = [str(uuid.uuid4())]
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        return_value=SessionCloseResult(
            session_id=SESSION_ID,
            archive_ids=archive_ids,
            status="closed",
        ),
    ):
        response = client.post(_close_path(), headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"session_id", "archive_ids", "status"}
    assert body["session_id"] == SESSION_ID
    assert body["archive_ids"] == archive_ids
    assert body["status"] == "closed"


def test_c6_session_not_found(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        side_effect=SessionNotFoundCloseError(),
    ):
        response = client.post(_close_path(), headers=_auth_headers())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_c7_closing_retry_not_409(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        return_value=SessionCloseResult(
            session_id=SESSION_ID,
            archive_ids=[],
            status="closed",
        ),
    ):
        response = client.post(_close_path(), headers=_auth_headers())
    assert response.status_code == 200
    assert response.status_code != 409


def test_c7_closing_retry_close_incomplete(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        side_effect=SessionCloseIncompleteError("terminal failed"),
    ):
        response = client.post(_close_path(), headers=_auth_headers())
    assert response.status_code == 503
    assert response.status_code != 409


def test_c8_terminal_repeat_not_found(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        side_effect=SessionNotFoundCloseError(),
    ):
        response = client.post(_close_path(), headers=_auth_headers())
    assert response.status_code == 404


def test_c9_close_incomplete(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        side_effect=SessionCloseIncompleteError("terminal failed"),
    ):
        response = client.post(_close_path(), headers=_auth_headers())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "close_incomplete"


def test_c10_identity_mismatch_zero_side_effect(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_session.close_session",
        new_callable=AsyncMock,
        side_effect=SessionNotFoundCloseError(),
    ) as mock_close:
        response = client.post(
            _close_path(user_id="user_B", session_id=SESSION_ID),
            headers=_auth_headers(),
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"
    mock_close.assert_awaited_once()
