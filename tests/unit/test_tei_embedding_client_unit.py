"""Unit tests for TEIEmbeddingClient with mock transport."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from tests.contract.helpers.tei_fake import FakeTEIState, build_fake_tei_client

from memory_system.infrastructure.embedding.errors import (
    EmbeddingInputTooLongError,
    EmbeddingServiceError,
    EmbeddingValidationError,
)
from memory_system.infrastructure.embedding.tei_client import TEIEmbeddingClient
from memory_system.infrastructure.embedding.types import EMBEDDING_DIMENSION
from memory_system.settings import get_settings
from memory_system.settings.models import Settings

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
    "EMBEDDING__BASE_URL": "http://fake-tei",
    "MEMORY_API_KEY": "dev-memory-api-key-change-me",
    "MEMORY_ADMIN_API_KEY": "dev-memory-admin-key-change-me",
    "EMBEDDING_EFFECTIVE_RUNTIME_MODE": "cpu",
    "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET": "4096",
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


@pytest.fixture
def settings(valid_env: None) -> Settings:
    return get_settings()


@pytest.fixture
def fake_state() -> FakeTEIState:
    return FakeTEIState()


@pytest.fixture
async def fake_http_client(fake_state: FakeTEIState) -> AsyncIterator[httpx.AsyncClient]:
    client = build_fake_tei_client(fake_state)
    yield client
    await client.aclose()


@pytest.fixture
def client(settings: Settings, fake_http_client: httpx.AsyncClient) -> TEIEmbeddingClient:
    return TEIEmbeddingClient(settings, fake_http_client)


async def test_embed_single_short_text(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    result = await client.embed(["hello world"])
    assert result.model == "BAAI/bge-m3"
    assert result.dimension == EMBEDDING_DIMENSION
    assert len(result.vectors) == 1
    assert len(result.vectors[0]) == EMBEDDING_DIMENSION
    assert len(fake_state.tokenize_calls) == 1
    assert len(fake_state.embeddings_calls) == 1


async def test_embed_rejects_empty_list(client: TEIEmbeddingClient) -> None:
    with pytest.raises(EmbeddingValidationError):
        await client.embed([])


async def test_embed_rejects_empty_string(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    with pytest.raises(EmbeddingValidationError):
        await client.embed([""])
    assert fake_state.tokenize_calls == []
    assert fake_state.embeddings_calls == []


async def test_embed_rejects_more_than_64_inputs(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    with pytest.raises(EmbeddingValidationError):
        await client.embed([f"text-{index}" for index in range(65)])
    assert fake_state.tokenize_calls == []
    assert fake_state.embeddings_calls == []


async def test_embed_rejects_token_count_over_limit(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    text = "too-long"
    fake_state.token_counts[text] = 1025
    with pytest.raises(EmbeddingInputTooLongError):
        await client.embed([text])
    assert len(fake_state.tokenize_calls) == 1
    assert fake_state.embeddings_calls == []


async def test_embed_rejects_wrong_dimension(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    fake_state.embeddings_vector_kind_by_call[0] = "wrong_dim"
    with pytest.raises(EmbeddingValidationError):
        await client.embed(["bad-dimension"])


async def test_embed_rejects_nan_vector(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    fake_state.embeddings_vector_kind_by_call[0] = "nan"
    with pytest.raises(EmbeddingValidationError):
        await client.embed(["nan-vector"])


async def test_embed_sub_batch_failure_raises_service_error(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    fake_state.token_counts = {f"text-{index}": 1024 for index in range(5)}
    fake_state.embeddings_status_by_call[1] = 500
    texts = [f"text-{index}" for index in range(5)]
    with pytest.raises(EmbeddingServiceError):
        await client.embed(texts)
    assert len(fake_state.embeddings_calls) == 2


async def test_concurrent_embed_calls_are_safe(
    settings: Settings,
    fake_state: FakeTEIState,
) -> None:
    import asyncio

    async with build_fake_tei_client(fake_state) as http_client:
        client = TEIEmbeddingClient(settings, http_client)
        results = await asyncio.gather(
            *[client.embed([f"concurrent-{index}"]) for index in range(8)]
        )
    assert len(results) == 8
    assert all(len(result.vectors[0]) == EMBEDDING_DIMENSION for result in results)


async def test_embed_uses_post_timeout_from_settings(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_client = MagicMock()
    http_client.post = AsyncMock(
        side_effect=httpx.TimeoutException("timed out"),
    )
    client = TEIEmbeddingClient(settings, http_client)
    with pytest.raises(EmbeddingServiceError):
        await client.embed(["timeout"])
    http_client.post.assert_awaited_once()
    assert (
        http_client.post.await_args.kwargs["timeout"]
        == settings.embedding_http_client.read_timeout_seconds
    )
