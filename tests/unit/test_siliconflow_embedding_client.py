"""Unit tests for SiliconFlow embedding client and settings integration."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from pydantic import ValidationError

from memory_system.infrastructure.embedding import (
    EmbeddingServiceError,
    SiliconFlowEmbeddingClient,
    create_embedding_client,
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


def test_default_settings_use_siliconflow_provider(valid_env: None) -> None:
    settings = get_settings()
    assert settings.memory_retrieval.embedding_provider == "siliconflow"


def test_siliconflow_provider_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "")
    with pytest.raises(ValidationError):
        get_settings()


def test_local_tei_provider_allows_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "")
    monkeypatch.setenv("MEMORY_RETRIEVAL__EMBEDDING_PROVIDER", "local_tei")
    settings = get_settings()
    assert settings.memory_retrieval.embedding_provider == "local_tei"


def test_invalid_embedding_provider_rejected(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("MEMORY_RETRIEVAL__EMBEDDING_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        get_settings()


def test_embedding_service_error_str_repr_redacts_sensitive_fields() -> None:
    secret_key = "sk-live-secret-key-value"
    long_vector = [0.1] * 1024
    error = EmbeddingServiceError(
        code="embedding_failed",
        provider="siliconflow",
        status_code=500,
        trace_id="trace-123",
        sanitized_message=f"Bearer {secret_key} vector={long_vector}",
    )
    rendered = str(error)
    assert secret_key not in rendered
    assert "Bearer" not in rendered
    assert "0.1" not in rendered
    assert error.__repr__() == rendered


@pytest.mark.asyncio
async def test_empty_string_embed_fails_without_http(valid_env: None) -> None:
    settings = get_settings()
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SiliconFlowEmbeddingClient(settings, http_client)
        with pytest.raises(EmbeddingServiceError) as exc_info:
            await client.embed(["hello", ""])
        assert exc_info.value.code == "embedding_input_too_long"

    assert call_count == 0


@pytest.mark.asyncio
async def test_empty_input_list_returns_empty_result_without_http(valid_env: None) -> None:
    settings = get_settings()
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SiliconFlowEmbeddingClient(settings, http_client)
        result = await client.embed([])
        assert result.vectors == []
        assert result.dimension == 1024

    assert call_count == 0


def test_factory_selects_siliconflow_client(valid_env: None) -> None:
    settings = get_settings()
    http_client = httpx.AsyncClient()
    client = create_embedding_client(settings, http_client)
    assert isinstance(client, SiliconFlowEmbeddingClient)
