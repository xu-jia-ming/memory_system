"""Contract tests for DEV-010 provider-aware tokenize count-source routing."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from memory_system.infrastructure.embedding.factory import create_embedding_client
from memory_system.infrastructure.tei.tei_tokenize_client import TeiTokenizeClient
from memory_system.infrastructure.tokenize.factory import create_tokenize_client
from memory_system.infrastructure.tokenize.heuristic_token_count_adapter import (
    HeuristicTokenCountAdapter,
)
from memory_system.settings import get_settings

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_PATH = ROOT / "src/memory_system/domain/services/production_extraction_pipeline.py"
RETRIEVAL_PATH = ROOT / "src/memory_system/domain/services/retrieval_api_service.py"
SPEC_PATH = ROOT / "01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md"
PYPROJECT_PATH = ROOT / "pyproject.toml"

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


def test_production_sources_use_factory_not_tei_default() -> None:
    pipeline_src = PIPELINE_PATH.read_text(encoding="utf-8")
    retrieval_src = RETRIEVAL_PATH.read_text(encoding="utf-8")
    for source, path in (
        (pipeline_src, PIPELINE_PATH),
        (retrieval_src, RETRIEVAL_PATH),
    ):
        assert "create_tokenize_client(settings, http_client)" in source, path
        assert "TeiTokenizeClient(settings, http_client)" not in source, path
        assert "import TeiTokenizeClient" not in source, path
        assert "TeiTokenizeClient," not in source, path
        assert "TeiTokenizeClient\n" not in source, path
        assert "TeiTokenizeClient" not in source, path
    assert "TokenizeServiceError" in retrieval_src
    assert "from memory_system.infrastructure.tei.tei_tokenize_client import" in retrieval_src


@pytest.mark.asyncio
async def test_siliconflow_path_posts_zero_tokenize(valid_env: None) -> None:
    settings = get_settings()
    posts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posts.append(request)
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = create_tokenize_client(settings, http_client)
        assert isinstance(client, HeuristicTokenCountAdapter)
        await client.count_tokens("Hello 世界 mixed 中文")
    assert posts == []


def test_spec_and_code_provider_aware_invariants() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")
    assert "provider-aware token-count source" in spec
    assert "estimate_tokens" in spec
    assert "embedding_provider=siliconflow" in spec
    pipeline_src = PIPELINE_PATH.read_text(encoding="utf-8")
    retrieval_src = RETRIEVAL_PATH.read_text(encoding="utf-8")
    assert "create_tokenize_client(settings, http_client)" in pipeline_src
    assert "create_tokenize_client(settings, http_client)" in retrieval_src
    assert "TeiTokenizeClient(settings, http_client)" not in pipeline_src
    assert "TeiTokenizeClient(settings, http_client)" not in retrieval_src


def test_local_tei_factory_binds_tei_client(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "")
    monkeypatch.setenv("MEMORY_RETRIEVAL__EMBEDDING_PROVIDER", "local_tei")
    settings = get_settings()
    client = create_tokenize_client(settings, httpx.AsyncClient())
    assert isinstance(client, TeiTokenizeClient)


def test_non_goals_no_new_tokenizer_or_tei_embedding_client(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
    assert "transformers" not in pyproject
    assert "tiktoken" not in pyproject
    src_root = ROOT / "src"
    tei_embedding_hits = list(src_root.rglob("*tei_embedding*"))
    assert tei_embedding_hits == []
    production_hits: list[Path] = []
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "class TEIEmbeddingClient" in text:
            production_hits.append(path)
    assert production_hits == []
    monkeypatch.setenv("SILICONFLOW_API_KEY", "")
    monkeypatch.setenv("MEMORY_RETRIEVAL__EMBEDDING_PROVIDER", "local_tei")
    settings = get_settings()
    with pytest.raises(NotImplementedError):
        create_embedding_client(settings, httpx.AsyncClient())
