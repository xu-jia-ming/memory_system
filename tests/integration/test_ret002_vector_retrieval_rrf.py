"""Integration tests for RET-002 Vector retrieval and RRF fusion."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
from elasticsearch import AsyncElasticsearch
from tests.support.fake_retrieval_index_embedding_client import FakeEmbeddingClient
from tests.support.ret002_es_fixtures import (
    RET002_KEYWORD,
    RET002_SEMANTIC_QUERY,
    USER_A,
    make_deterministic_embedding,
    seed_ret002_hybrid_fixtures,
)

from memory_system.domain.models.hybrid_retrieval import HybridRetrievalQuery
from memory_system.domain.models.vector_retrieval import VectorRetrievalQuery
from memory_system.domain.services.bm25_retrieval_service import create_bm25_retrieval_service
from memory_system.domain.services.hybrid_retrieval_service import HybridRetrievalService
from memory_system.domain.services.vector_retrieval_service import create_vector_retrieval_service
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)
from memory_system.infrastructure.embedding.types import EmbeddingResult
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
ELASTICSEARCH_CONTAINER = "memory-system-elasticsearch-test"
EMBEDDING_DIMENSION = 1024


class Ret002FakeEmbeddingClient:
    """Deterministic embedding keyed by normalized query text."""

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        vectors = [make_deterministic_embedding(text) for text in texts]
        return EmbeddingResult(
            model="ret002-fake-model",
            dimension=EMBEDDING_DIMENSION,
            vectors=vectors,
        )


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


def _compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env["PROXY__HTTP_URL"] = ""
    return env


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(COMPOSE_SH), "--stack=test", "--embedding=none", *args]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_compose_env(),
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"compose failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _ensure_dotenv() -> None:
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def _assert_test_isolation() -> None:
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT


def _container_ip(container: str) -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            container,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


@pytest.fixture(scope="module")
def test_infra() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run RET-002 integration")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "elasticsearch", check=False)
    if up.returncode != 0:
        pytest.skip(
            "Unable to start compose test infra "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 180
    while time.time() < deadline:
        if _container_ip(ELASTICSEARCH_CONTAINER):
            break
        time.sleep(2)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Elasticsearch container did not become ready in time")

    migrate = _compose("run", "--rm", "init-infra", check=False)
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra migration failed: "
            f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    es_ip = _container_ip(ELASTICSEARCH_CONTAINER)
    if not es_ip:
        _compose("down", "-v", check=False)
        pytest.skip("Could not resolve Elasticsearch container IP")

    yield f"http://{es_ip}:9200"
    _compose("down", "-v", check=False)


@pytest.fixture
async def es_client(test_infra: str) -> AsyncIterator[AsyncElasticsearch]:
    client = AsyncElasticsearch(hosts=[test_infra], request_timeout=30)
    try:
        await client.info()
    except Exception as exc:
        await client.close()
        pytest.skip(f"Elasticsearch ping failed: {exc}")
    yield client
    await client.close()


@pytest.fixture(autouse=True)
async def _clean_es(es_client: AsyncElasticsearch) -> AsyncIterator[None]:
    settings = get_settings()
    await es_client.delete_by_query(
        index=settings.memory_retrieval.index_name,
        body={"query": {"match_all": {}}},
        refresh=True,
        conflicts="proceed",
    )
    yield
    await es_client.delete_by_query(
        index=settings.memory_retrieval.index_name,
        body={"query": {"match_all": {}}},
        refresh=True,
        conflicts="proceed",
    )


def _vector_service(es_client: AsyncElasticsearch):
    return create_vector_retrieval_service(es_client, settings=get_settings())


def _hybrid_service(es_client: AsyncElasticsearch) -> HybridRetrievalService:
    return HybridRetrievalService(
        create_bm25_retrieval_service(es_client, settings=get_settings()),
        create_vector_retrieval_service(es_client, settings=get_settings()),
        Ret002FakeEmbeddingClient(),
        settings=get_settings(),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_vector_happy_path_semantic_ranking(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret002_hybrid_fixtures(write_repo, settings.memory_retrieval.index_name)

    query_vector = make_deterministic_embedding(RET002_SEMANTIC_QUERY)
    outcome = await _vector_service(es_client).search(
        VectorRetrievalQuery(user_id=USER_A, query_vector=query_vector),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.hits
    assert outcome.success.hits[0].memory_id == "mem-a-close-vector"
    assert outcome.success.hits[0].rank == 1
    assert outcome.success.hits[0].score > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_cross_user_isolation(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret002_hybrid_fixtures(write_repo, settings.memory_retrieval.index_name)

    query_vector = make_deterministic_embedding(RET002_SEMANTIC_QUERY)
    outcome = await _vector_service(es_client).search(
        VectorRetrievalQuery(user_id=USER_A, query_vector=query_vector),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    memory_ids = {hit.memory_id for hit in outcome.success.hits}
    assert "mem-b-active-fact" not in memory_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_memory_type_filter(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret002_hybrid_fixtures(write_repo, settings.memory_retrieval.index_name)

    query_vector = make_deterministic_embedding(RET002_SEMANTIC_QUERY)
    outcome = await _vector_service(es_client).search(
        VectorRetrievalQuery(
            user_id=USER_A,
            query_vector=query_vector,
            memory_types=["fact"],
        ),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    memory_ids = {hit.memory_id for hit in outcome.success.hits}
    assert "mem-a-vector-only" not in memory_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_default_status_active_only(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret002_hybrid_fixtures(write_repo, settings.memory_retrieval.index_name)

    query_vector = make_deterministic_embedding(RET002_SEMANTIC_QUERY)
    outcome = await _vector_service(es_client).search(
        VectorRetrievalQuery(user_id=USER_A, query_vector=query_vector),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    memory_ids = {hit.memory_id for hit in outcome.success.hits}
    assert "mem-a-conflicted-fact" not in memory_ids
    assert "mem-a-superseded-fact" not in memory_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_hybrid_rrf_dual_channel(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret002_hybrid_fixtures(write_repo, settings.memory_retrieval.index_name)

    outcome = await _hybrid_service(es_client).search(
        HybridRetrievalQuery(user_id=USER_A, query=RET002_SEMANTIC_QUERY),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "hybrid"
    assert outcome.success.candidates
    top = outcome.success.candidates[0]
    assert "bm25" in top.retrieval_source
    assert "vector" in top.retrieval_source
    assert top.rrf_score > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i7_fake_embed_failure_degrades_to_bm25_only(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret002_hybrid_fixtures(write_repo, settings.memory_retrieval.index_name)

    service = HybridRetrievalService(
        create_bm25_retrieval_service(es_client, settings=settings),
        create_vector_retrieval_service(es_client, settings=settings),
        FakeEmbeddingClient(fail=True),
        settings=settings,
    )

    outcome = await service.search(
        HybridRetrievalQuery(user_id=USER_A, query=RET002_KEYWORD),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "bm25_only"
    assert outcome.success.candidates


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i9_fused_top_n_truncation(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret002_hybrid_fixtures(
        write_repo,
        settings.memory_retrieval.index_name,
        include_fused_top_n_bulk=True,
    )

    outcome = await _hybrid_service(es_client).search(
        HybridRetrievalQuery(user_id=USER_A, query=RET002_KEYWORD),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.candidates) == settings.memory_retrieval.fused_top_n
