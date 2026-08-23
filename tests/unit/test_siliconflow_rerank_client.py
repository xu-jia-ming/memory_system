"""Unit tests for SiliconFlow rerank client and settings integration."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from memory_system.infrastructure.rerank import (
    RerankServiceError,
    SiliconFlowRerankClient,
    create_rerank_client,
)
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
    "EMBEDDING_EFFECTIVE_RUNTIME_MODE": "cpu",
    "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET": "4096",
    "SILICONFLOW_API_KEY": "sk-example-replace-me",
}


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


def _success_payload(indices: list[int], scores: list[float]) -> dict[str, object]:
    return {
        "results": [
            {"index": index, "relevance_score": score}
            for index, score in zip(indices, scores, strict=True)
        ],
    }


@pytest.mark.asyncio
async def test_rerank_success_parses_results(valid_env: None) -> None:
    settings = get_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["model"] == "BAAI/bge-reranker-v2-m3"
        assert body["query"] == "When did Gina get her tattoo?"
        assert body["documents"] == ["doc-a", "doc-b", "doc-c"]
        assert body["top_n"] == 3
        return httpx.Response(200, json=_success_payload([1, 0, 2], [0.9, 0.8, 0.1]))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SiliconFlowRerankClient(settings, http_client)
        result = await client.rerank(
            query="When did Gina get her tattoo?",
            documents=["doc-a", "doc-b", "doc-c"],
            top_n=3,
        )

    assert [(item.index, item.relevance_score) for item in result.results] == [
        (1, 0.9),
        (0, 0.8),
        (2, 0.1),
    ]


@pytest.mark.asyncio
async def test_rerank_401_maps_auth_error(valid_env: None) -> None:
    settings = get_settings()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid api key"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SiliconFlowRerankClient(settings, http_client)
        with pytest.raises(RerankServiceError) as exc_info:
            await client.rerank(query="q", documents=["doc"], top_n=1)
        assert exc_info.value.code == "rerank_auth_failed"


@pytest.mark.asyncio
async def test_rerank_429_retries_before_success(
    valid_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    attempts = 0
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "memory_system.infrastructure.rerank.siliconflow_client.asyncio.sleep",
        fake_sleep,
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json=_success_payload([0], [0.99]))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SiliconFlowRerankClient(settings, http_client)
        result = await client.rerank(query="q", documents=["doc"], top_n=1)

    assert attempts == 3
    assert len(sleep_calls) == 2
    assert result.results[0].relevance_score == 0.99


@pytest.mark.asyncio
async def test_rerank_500_exhausts_retries(
    valid_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    attempts = 0

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        "memory_system.infrastructure.rerank.siliconflow_client.asyncio.sleep",
        fake_sleep,
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={"message": "server error"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SiliconFlowRerankClient(settings, http_client)
        with pytest.raises(RerankServiceError) as exc_info:
            await client.rerank(query="q", documents=["doc"], top_n=1)

    assert attempts == 3
    assert exc_info.value.code == "rerank_failed"


def test_rerank_service_error_redacts_query_and_documents() -> None:
    secret = "sk-live-secret-key-value"
    error = RerankServiceError(
        code="rerank_failed",
        provider="siliconflow",
        status_code=500,
        trace_id="trace-123",
        sanitized_message=f"query={secret} documents=['private doc text'] Bearer {secret}",
    )
    rendered = str(error)
    assert secret not in rendered
    assert "private doc text" not in rendered
    assert "Bearer" not in rendered


def test_factory_selects_siliconflow_client(valid_env: None) -> None:
    settings = get_settings()
    http_client = httpx.AsyncClient()
    client = create_rerank_client(settings, http_client)
    assert isinstance(client, SiliconFlowRerankClient)


def test_factory_returns_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("MEMORY_RETRIEVAL__RERANK_ENABLED", "false")
    settings = get_settings()
    from memory_system.infrastructure.rerank import NoOpRerankClient

    client = create_rerank_client(settings, httpx.AsyncClient())
    assert isinstance(client, NoOpRerankClient)
