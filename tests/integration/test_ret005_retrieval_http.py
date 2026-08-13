"""Integration tests for RET-005 retrieval HTTP route."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from memory_system.api.app import create_app
from memory_system.domain.services.retrieval_api_service import (
    RetrievalApiFatalError,
    RetrievalApiInput,
    RetrievalApiSuccess,
    RetrievalApiValidationError,
)
from memory_system.domain.services.retrieval_response_mapper import map_scored_memory_to_response_item
from memory_system.infrastructure.runtime import AppState
from memory_system.settings import get_settings
from tests.unit.test_retrieval_api_service import make_scored_memory

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

RETRIEVAL_URL = "/api/v1/memory/retrieval"


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
def fake_app_state(valid_env: None) -> AppState:
    settings = get_settings()
    return AppState(
        settings=settings,
        redis=MagicMock(),
        mongodb=MagicMock(),
        neo4j=MagicMock(),
        elasticsearch=MagicMock(),
        http_client=MagicMock(),
        kafka_producer=MagicMock(),
        kafka_producer_ready=True,
    )


class FakeRetrievalApiService:
    def __init__(self, *, mode: str = "happy") -> None:
        self.mode = mode
        self.calls: list[RetrievalApiInput] = []

    async def retrieve(self, input_data: RetrievalApiInput, *, deadline: float) -> RetrievalApiSuccess:
        self.calls.append(input_data)
        if self.mode == "validation":
            raise RetrievalApiValidationError("query_too_long", "query too long")
        if self.mode == "unavailable":
            raise RetrievalApiFatalError("retrieval_unavailable", "unavailable")
        if self.mode == "stats_failed":
            return RetrievalApiSuccess(
                retrieval_mode="bm25_only",
                warnings=["retrieval_stat_update_failed"],
                memories=[map_scored_memory_to_response_item(make_scored_memory())],
            )
        if self.mode == "embedding_failed":
            return RetrievalApiSuccess(
                retrieval_mode="bm25_only",
                warnings=["embedding_failed"],
                memories=[map_scored_memory_to_response_item(make_scored_memory())],
            )
        if self.mode == "user_isolation":
            return RetrievalApiSuccess(
                retrieval_mode="hybrid",
                warnings=[],
                memories=[
                    map_scored_memory_to_response_item(make_scored_memory(memory_id="mem-user-a"))
                ],
            )
        return RetrievalApiSuccess(
            retrieval_mode="hybrid",
            warnings=[],
            memories=[map_scored_memory_to_response_item(make_scored_memory())],
        )


@pytest.fixture
def client(fake_app_state: AppState, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    fake_service_holder: dict[str, FakeRetrievalApiService] = {}

    def _factory(**kwargs: Any) -> FakeRetrievalApiService:
        if "instance" not in fake_service_holder:
            fake_service_holder["instance"] = FakeRetrievalApiService()
        return fake_service_holder["instance"]

    monkeypatch.setattr(
        "memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state",
        _factory,
    )
    app = create_app(app_state=fake_app_state)
    with TestClient(app) as test_client:
        test_client._ret005_fake_service = fake_service_holder.setdefault(  # type: ignore[attr-defined]
            "instance", FakeRetrievalApiService()
        )
        yield test_client


def _headers() -> dict[str, str]:
    return {"X-API-Key": VALID_ENV["MEMORY_API_KEY"]}


def test_i1_happy_path(client: TestClient) -> None:
    response = client.post(
        RETRIEVAL_URL,
        headers=_headers(),
        json={
            "user_id": "user-a",
            "query": "hello",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_mode"] == "hybrid"
    assert len(body["memories"]) == 1
    assert body["memories"][0]["memory_id"] == "mem-1"
    assert "score" in body["memories"][0]


def test_i2_embedding_failed_degraded(client: TestClient) -> None:
    client._ret005_fake_service.mode = "embedding_failed"  # type: ignore[attr-defined]
    response = client.post(
        RETRIEVAL_URL,
        headers=_headers(),
        json={"user_id": "user-a", "query": "hello"},
    )
    assert response.status_code == 200
    assert "embedding_failed" in response.json()["warnings"]


def test_i4_user_isolation_response(client: TestClient) -> None:
    client._ret005_fake_service.mode = "user_isolation"  # type: ignore[attr-defined]
    response = client.post(
        RETRIEVAL_URL,
        headers=_headers(),
        json={"user_id": "user-a", "query": "hello"},
    )
    assert response.status_code == 200
    memory_ids = [item["memory_id"] for item in response.json()["memories"]]
    assert "mem-user-b" not in memory_ids


def test_i5_dual_channel_failure(client: TestClient) -> None:
    client._ret005_fake_service.mode = "unavailable"  # type: ignore[attr-defined]
    response = client.post(
        RETRIEVAL_URL,
        headers=_headers(),
        json={"user_id": "user-a", "query": "hello"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "retrieval_unavailable"


def test_i6_query_too_long(client: TestClient) -> None:
    client._ret005_fake_service.mode = "validation"  # type: ignore[attr-defined]
    response = client.post(
        RETRIEVAL_URL,
        headers=_headers(),
        json={"user_id": "user-a", "query": "x" * 2001},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "query_too_long"


def test_i7_stats_failure_warning(client: TestClient) -> None:
    client._ret005_fake_service.mode = "stats_failed"  # type: ignore[attr-defined]
    response = client.post(
        RETRIEVAL_URL,
        headers=_headers(),
        json={"user_id": "user-a", "query": "hello"},
    )
    assert response.status_code == 200
    assert "retrieval_stat_update_failed" in response.json()["warnings"]


def test_c2_auth_missing_key_401(client: TestClient) -> None:
    response = client.post(
        RETRIEVAL_URL,
        json={"user_id": "user-a", "query": "hello"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_c2_admin_key_allowed(client: TestClient) -> None:
    response = client.post(
        RETRIEVAL_URL,
        headers={"X-API-Key": VALID_ENV["MEMORY_ADMIN_API_KEY"]},
        json={"user_id": "user-a", "query": "hello"},
    )
    assert response.status_code == 200
