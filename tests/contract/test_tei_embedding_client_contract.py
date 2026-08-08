"""Contract tests for TEIEmbeddingClient against Fake TEI."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from memory_system.infrastructure.embedding.errors import (
    EmbeddingInputTooLongError,
    EmbeddingServiceError,
    EmbeddingValidationError,
)
from memory_system.infrastructure.embedding.tei_client import TEIEmbeddingClient
from memory_system.infrastructure.embedding.types import EMBEDDING_DIMENSION
from memory_system.settings import get_settings
from memory_system.settings.models import Settings
from tests.contract.helpers.tei_fake import FakeTEIState, build_fake_tei_client

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


async def test_contract_normal_single_short_text(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    result = await client.embed(["short text"])
    assert result.model == "BAAI/bge-m3"
    assert len(result.vectors) == 1
    assert len(result.vectors[0]) == EMBEDDING_DIMENSION
    assert len(fake_state.tokenize_calls) == 1
    assert len(fake_state.embeddings_calls) == 1


async def test_contract_rejects_65_inputs_without_tei_calls(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    with pytest.raises(EmbeddingValidationError):
        await client.embed([f"item-{index}" for index in range(65)])
    assert fake_state.tokenize_calls == []
    assert fake_state.embeddings_calls == []


async def test_contract_rejects_empty_string_without_tei_calls(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    with pytest.raises(EmbeddingValidationError):
        await client.embed(["valid", ""])
    assert fake_state.tokenize_calls == []
    assert fake_state.embeddings_calls == []


async def test_contract_tokenize_1025_raises_without_embeddings(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    text = "over-limit"
    fake_state.token_counts[text] = 1025
    with pytest.raises(EmbeddingInputTooLongError) as exc_info:
        await client.embed([text])
    assert exc_info.value.code == "embedding_input_too_long"
    assert len(fake_state.tokenize_calls) == 1
    assert fake_state.embeddings_calls == []


async def test_contract_multi_batch_preserves_order_and_call_count(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    texts = [f"batch-{index}" for index in range(5)]
    for text in texts:
        fake_state.token_counts[text] = 1024

    result = await client.embed(texts)
    assert len(result.vectors) == 5
    assert len(fake_state.embeddings_calls) == 2
    assert fake_state.embeddings_calls[0] == texts[:4]
    assert fake_state.embeddings_calls[1] == texts[4:]


async def test_contract_sub_batch_500_fails_entire_embed(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    texts = [f"fail-{index}" for index in range(5)]
    for text in texts:
        fake_state.token_counts[text] = 1024
    fake_state.embeddings_status_by_call[1] = 500

    with pytest.raises(EmbeddingServiceError):
        await client.embed(texts)
    assert len(fake_state.embeddings_calls) == 2


async def test_contract_wrong_dimension_vector(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    fake_state.embeddings_vector_kind_by_call[0] = "wrong_dim"
    with pytest.raises(EmbeddingValidationError):
        await client.embed(["wrong-dim"])


async def test_contract_nan_vector(
    client: TEIEmbeddingClient,
    fake_state: FakeTEIState,
) -> None:
    fake_state.embeddings_vector_kind_by_call[0] = "nan"
    with pytest.raises(EmbeddingValidationError):
        await client.embed(["nan-vector"])


async def test_contract_direct_long_embeddings_return_error(
    fake_state: FakeTEIState,
) -> None:
    fake_state.token_counts["long-input"] = 2000
    async with build_fake_tei_client(fake_state) as http_client:
        response = await http_client.post(
            "http://fake-tei/v1/embeddings",
            json={
                "model": "BAAI/bge-m3",
                "input": ["long-input"],
                "encoding_format": "float",
            },
        )
    assert response.status_code == 400
