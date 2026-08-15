"""Unit tests for create_tokenize_client provider routing."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from memory_system.domain.services.production_extraction_pipeline import (
    create_production_extraction_pipeline,
)
from memory_system.domain.services.retrieval_api_service import (
    create_retrieval_api_service_from_app_state,
)
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.infrastructure.tei.tei_tokenize_client import TeiTokenizeClient
from memory_system.infrastructure.tokenize.factory import create_tokenize_client
from memory_system.infrastructure.tokenize.heuristic_token_count_adapter import (
    HeuristicTokenCountAdapter,
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


@pytest.mark.asyncio
async def test_factory_siliconflow_returns_heuristic_adapter(valid_env: None) -> None:
    settings = get_settings()
    async with httpx.AsyncClient() as http_client:
        client = create_tokenize_client(settings, http_client)
    assert isinstance(client, HeuristicTokenCountAdapter)
    assert await client.count_tokens("Hello 世界") == estimate_tokens("Hello 世界")


def test_factory_local_tei_returns_tei_client(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "")
    monkeypatch.setenv("MEMORY_RETRIEVAL__EMBEDDING_PROVIDER", "local_tei")
    settings = get_settings()
    http_client = httpx.AsyncClient()
    client = create_tokenize_client(settings, http_client)
    assert isinstance(client, TeiTokenizeClient)


def test_factory_unknown_provider_fail_closed() -> None:
    settings = SimpleNamespace(memory_retrieval=SimpleNamespace(embedding_provider="openai"))
    with pytest.raises(ValueError, match="unsupported embedding_provider: 'openai'") as exc_info:
        create_tokenize_client(settings, httpx.AsyncClient())  # type: ignore[arg-type]
    assert "siliconflow" not in str(exc_info.value).lower() or "openai" in str(exc_info.value)


def test_factory_siliconflow_does_not_construct_tei(
    valid_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[object] = []
    original_init = TeiTokenizeClient.__init__

    def wrapped_init(self: TeiTokenizeClient, *args: object, **kwargs: object) -> None:
        constructed.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(TeiTokenizeClient, "__init__", wrapped_init)
    settings = get_settings()
    client = create_tokenize_client(settings, httpx.AsyncClient())
    assert constructed == []
    assert not isinstance(client, TeiTokenizeClient)
    assert isinstance(client, HeuristicTokenCountAdapter)


def test_production_pipeline_siliconflow_resolves_heuristic(
    valid_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[object] = []
    original_init = TeiTokenizeClient.__init__

    def wrapped_init(self: TeiTokenizeClient, *args: object, **kwargs: object) -> None:
        constructed.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(TeiTokenizeClient, "__init__", wrapped_init)
    settings = get_settings()
    pipeline = create_production_extraction_pipeline(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        httpx.AsyncClient(),
        settings,
        llm_client=MagicMock(),
        tokenize_client=None,
        embedding_client=MagicMock(),
    )
    resolved = pipeline._graph_write_service._tokenize_client
    assert constructed == []
    assert isinstance(resolved, HeuristicTokenCountAdapter)
    assert not isinstance(resolved, TeiTokenizeClient)


def test_explicit_tokenize_client_injection_wins(
    valid_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory_calls: list[object] = []

    def exploding_factory(*args: object, **kwargs: object) -> Any:
        factory_calls.append((args, kwargs))
        raise AssertionError("create_tokenize_client must not override explicit fake")

    monkeypatch.setattr(
        "memory_system.domain.services.production_extraction_pipeline.create_tokenize_client",
        exploding_factory,
    )
    fake = FakeTokenizeClient(token_count=7)
    settings = get_settings()
    pipeline = create_production_extraction_pipeline(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        httpx.AsyncClient(),
        settings,
        llm_client=MagicMock(),
        tokenize_client=fake,
        embedding_client=MagicMock(),
    )
    assert factory_calls == []
    assert pipeline._graph_write_service._tokenize_client is fake


def test_retrieval_assembly_siliconflow_resolves_heuristic(
    valid_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[object] = []
    original_init = TeiTokenizeClient.__init__

    def wrapped_init(self: TeiTokenizeClient, *args: object, **kwargs: object) -> None:
        constructed.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(TeiTokenizeClient, "__init__", wrapped_init)
    settings = get_settings()
    service = create_retrieval_api_service_from_app_state(
        elasticsearch=MagicMock(),
        neo4j_driver=MagicMock(),
        http_client=httpx.AsyncClient(),
        settings=settings,
    )
    resolved = service._tokenize_client
    assert constructed == []
    assert isinstance(resolved, HeuristicTokenCountAdapter)
    assert not isinstance(resolved, TeiTokenizeClient)
