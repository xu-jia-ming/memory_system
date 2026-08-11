"""Contract tests for STM-009 message write API."""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from memory_system.api.app import create_app
from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.models.compression_coordinator import WriteMessageCoordinatorResult
from memory_system.domain.services.compression_coordinator_service import (
    SessionClosingCoordinatorError,
    SessionNotFoundCoordinatorError,
    WorkingMemoryFullCoordinatorError,
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

MESSAGE_PATH = "/api/v1/memory/working/message"


def _valid_body(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "message_id": str(uuid.uuid4()),
        "user_id": "user_001",
        "session_id": str(uuid.uuid4()),
        "role": "user",
        "content": "hello integration",
    }
    data.update(overrides)
    return data


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


def test_c1_endpoint_exists(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_message.write_working_message_with_coordination",
        new_callable=AsyncMock,
        return_value=WriteMessageCoordinatorResult(
            message_id="m1",
            status="success",
            compression_status=CompressionStatus.NOT_TRIGGERED,
        ),
    ):
        response = client.post(MESSAGE_PATH, json=_valid_body(), headers=_auth_headers())
    assert response.status_code == 200


def test_c2_no_api_key(client: TestClient) -> None:
    response = client.post(MESSAGE_PATH, json=_valid_body())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_c3_invalid_body(client: TestClient) -> None:
    response = client.post(
        MESSAGE_PATH,
        json={"message_id": "m1"},
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_c4_request_id_passthrough(client: TestClient) -> None:
    request_id = "123e4567-e89b-42d3-a456-426614174000"
    with patch(
        "memory_system.api.routes.memory_message.write_working_message_with_coordination",
        new_callable=AsyncMock,
        return_value=WriteMessageCoordinatorResult(
            message_id="m1",
            status="success",
            compression_status=CompressionStatus.NOT_TRIGGERED,
        ),
    ):
        response = client.post(
            MESSAGE_PATH,
            json=_valid_body(),
            headers=_auth_headers(**{"X-Request-ID": request_id}),
        )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_c5_success_envelope_three_fields_only(client: TestClient) -> None:
    message_id = str(uuid.uuid4())
    with patch(
        "memory_system.api.routes.memory_message.write_working_message_with_coordination",
        new_callable=AsyncMock,
        return_value=WriteMessageCoordinatorResult(
            message_id=message_id,
            status="success",
            compression_status=CompressionStatus.COMPLETED,
        ),
    ):
        response = client.post(
            MESSAGE_PATH,
            json=_valid_body(message_id=message_id),
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"message_id", "status", "compression_status"}
    assert body["message_id"] == message_id
    assert body["status"] == "success"
    assert body["compression_status"] == "completed"


def test_c6_duplicate_not_triggered(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_message.write_working_message_with_coordination",
        new_callable=AsyncMock,
        return_value=WriteMessageCoordinatorResult(
            message_id="dup-1",
            status="duplicate",
            compression_status=CompressionStatus.NOT_TRIGGERED,
        ),
    ):
        response = client.post(MESSAGE_PATH, json=_valid_body(), headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "duplicate"
    assert body["compression_status"] == "not_triggered"


def test_c7_working_memory_full(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_message.write_working_message_with_coordination",
        new_callable=AsyncMock,
        side_effect=WorkingMemoryFullCoordinatorError(),
    ):
        response = client.post(MESSAGE_PATH, json=_valid_body(), headers=_auth_headers())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "working_memory_full"


def test_c8_compression_fail_still_200(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_message.write_working_message_with_coordination",
        new_callable=AsyncMock,
        return_value=WriteMessageCoordinatorResult(
            message_id="m1",
            status="success",
            compression_status=CompressionStatus.FAILED,
        ),
    ):
        response = client.post(MESSAGE_PATH, json=_valid_body(), headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["compression_status"] == "failed"


def test_c9_session_not_found(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_message.write_working_message_with_coordination",
        new_callable=AsyncMock,
        side_effect=SessionNotFoundCoordinatorError(),
    ):
        response = client.post(MESSAGE_PATH, json=_valid_body(), headers=_auth_headers())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_c10_session_closing(client: TestClient) -> None:
    with patch(
        "memory_system.api.routes.memory_message.write_working_message_with_coordination",
        new_callable=AsyncMock,
        side_effect=SessionClosingCoordinatorError(),
    ):
        response = client.post(MESSAGE_PATH, json=_valid_body(), headers=_auth_headers())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_closing"
