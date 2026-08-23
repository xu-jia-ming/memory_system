"""Integration tests for RET-003 authoritative recall with Neo4j and Elasticsearch."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from elasticsearch import AsyncElasticsearch
from neo4j import AsyncDriver, AsyncGraphDatabase
from tests.support.ret003_es_fixtures import seed_ret003_es_documents
from tests.support.ret003_neo4j_fixtures import USER_A, USER_B, seed_ret003_graph

from memory_system.domain.models.authoritative_recall import AuthoritativeRecallQuery
from memory_system.domain.models.hybrid_retrieval import (
    FusedRetrievalCandidate,
    HybridRetrievalSuccess,
)
from memory_system.domain.services.authoritative_recall_service import (
    AuthoritativeRecallService,
    create_authoritative_recall_service,
)
from memory_system.infrastructure.elasticsearch.mget_retrieval_repository import MgetRetrievalError
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
NEO4J_CONTAINER = "memory-system-neo4j-test"
ELASTICSEARCH_CONTAINER = "memory-system-elasticsearch-test"


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
def test_infra_uris() -> Iterator[tuple[str, str]]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run RET-003 integration")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "neo4j", "elasticsearch", check=False)
    if up.returncode != 0:
        pytest.skip(
            "Unable to start compose test stack "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 180
    while time.time() < deadline:
        if _container_ip(NEO4J_CONTAINER) and _container_ip(ELASTICSEARCH_CONTAINER):
            break
        time.sleep(2)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Test stack did not become ready in time")

    migrate = _compose("run", "--rm", "init-infra", check=False)
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra migration failed: "
            f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    neo4j_ip = _container_ip(NEO4J_CONTAINER)
    es_ip = _container_ip(ELASTICSEARCH_CONTAINER)
    if not neo4j_ip or not es_ip:
        _compose("down", "-v", check=False)
        pytest.skip("Could not resolve test container IPs")

    yield (f"bolt://{neo4j_ip}:7687", f"http://{es_ip}:9200")
    _compose("down", "-v", check=False)


@pytest.fixture
async def neo4j_driver(test_infra_uris: tuple[str, str]) -> AsyncIterator[AsyncDriver]:
    neo4j_uri, _ = test_infra_uris
    driver = AsyncGraphDatabase.driver(neo4j_uri)
    try:
        await driver.verify_connectivity()
    except Exception as exc:
        await driver.close()
        pytest.skip(f"Neo4j connectivity failed: {exc}")
    yield driver
    await driver.close()


@pytest.fixture
async def es_client(test_infra_uris: tuple[str, str]) -> AsyncIterator[AsyncElasticsearch]:
    _, es_uri = test_infra_uris
    client = AsyncElasticsearch(hosts=[es_uri], request_timeout=30)
    try:
        await client.info()
    except Exception as exc:
        await client.close()
        pytest.skip(f"Elasticsearch ping failed: {exc}")
    yield client
    await client.close()


@pytest.fixture(autouse=True)
async def _clean_graph(neo4j_driver: AsyncDriver) -> AsyncIterator[None]:
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")


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


def _hybrid_success_for_seed(seed_id: str) -> HybridRetrievalSuccess:
    return HybridRetrievalSuccess(
        user_id=USER_A,
        retrieval_mode="hybrid",
        effective_channel_count=2,
        candidates=[
            FusedRetrievalCandidate(
                memory_id=seed_id,
                bm25_rank=1,
                vector_rank=None,
                bm25_score=1.5,
                vector_score=None,
                retrieval_source=["bm25"],
                rrf_score=0.5,
                min_available_rank=1,
                normalized_retrieval_score=0.8,
            ),
        ],
    )


def _service(
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> AuthoritativeRecallService:
    settings = get_settings().model_copy(
        update={
            "memory_retrieval": get_settings().memory_retrieval.model_copy(
                update={"rerank_enabled": False},
            ),
        },
    )
    return create_authoritative_recall_service(
        neo4j_driver=neo4j_driver,
        es_client=es_client,
        settings=settings,
        http_client=httpx.AsyncClient(),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_direct_seed_neo4j_es_consistent(
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    ids = await seed_ret003_graph(neo4j_driver)
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret003_es_documents(
        write_repo,
        settings.memory_retrieval.index_name,
        memory_ids=[ids["seed"]],
    )

    outcome = await _service(neo4j_driver, es_client).recall(
        AuthoritativeRecallQuery(
            hybrid_success=_hybrid_success_for_seed(ids["seed"]),
            graph_expand=False,
        ),
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.direct_candidates) == 1
    assert outcome.success.direct_candidates[0].memory_id == ids["seed"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_cross_user_related_not_visible(
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    ids = await seed_ret003_graph(neo4j_driver)
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret003_es_documents(
        write_repo,
        settings.memory_retrieval.index_name,
        memory_ids=[ids["seed"], ids["cross_user"]],
        user_id=USER_B,
    )

    outcome = await _service(neo4j_driver, es_client).recall(
        AuthoritativeRecallQuery(hybrid_success=_hybrid_success_for_seed(ids["seed"])),
    )
    assert outcome.success is not None
    expanded_ids = {item.memory_id for item in outcome.success.expanded_candidates}
    assert ids["cross_user"] not in expanded_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_supersedes_tier_zero_priority(
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    ids = await seed_ret003_graph(neo4j_driver)
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret003_es_documents(
        write_repo,
        settings.memory_retrieval.index_name,
        memory_ids=[
            ids["seed"],
            ids["expanded_supersedes"],
            ids["expanded_object"],
        ],
    )

    outcome = await _service(neo4j_driver, es_client).recall(
        AuthoritativeRecallQuery(hybrid_success=_hybrid_success_for_seed(ids["seed"])),
    )
    assert outcome.success is not None
    assert outcome.success.expanded_candidates
    assert outcome.success.expanded_candidates[0].memory_id == ids["expanded_supersedes"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_dirty_index_with_neo4j_driver(
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret003_es_documents(
        write_repo,
        settings.memory_retrieval.index_name,
        memory_ids=["mem-es-only"],
    )

    outcome = await _service(neo4j_driver, es_client).recall(
        AuthoritativeRecallQuery(hybrid_success=_hybrid_success_for_seed("mem-es-only")),
    )
    assert outcome.success is not None
    assert outcome.success.direct_candidates == []
    assert any(w.kind == "dirty_index_document" for w in outcome.success.warnings)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_neo4j_expanded_without_es_discarded(
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    ids = await seed_ret003_graph(neo4j_driver)
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret003_es_documents(
        write_repo,
        settings.memory_retrieval.index_name,
        memory_ids=[ids["seed"]],
    )

    outcome = await _service(neo4j_driver, es_client).recall(
        AuthoritativeRecallQuery(hybrid_success=_hybrid_success_for_seed(ids["seed"])),
    )
    assert outcome.success is not None
    expanded_ids = {item.memory_id for item in outcome.success.expanded_candidates}
    assert ids["neo4j_only"] not in expanded_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i7_graph_expand_end_to_end(
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    ids = await seed_ret003_graph(neo4j_driver)
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret003_es_documents(
        write_repo,
        settings.memory_retrieval.index_name,
        memory_ids=[
            ids["seed"],
            ids["expanded_supersedes"],
            ids["expanded_object"],
        ],
    )

    outcome = await _service(neo4j_driver, es_client).recall(
        AuthoritativeRecallQuery(hybrid_success=_hybrid_success_for_seed(ids["seed"])),
    )
    assert outcome.success is not None
    assert len(outcome.success.direct_candidates) == 1
    assert len(outcome.success.expanded_candidates) >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i8_mget_failure_degrades_to_direct(
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    ids = await seed_ret003_graph(neo4j_driver)
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret003_es_documents(
        write_repo,
        settings.memory_retrieval.index_name,
        memory_ids=[ids["seed"], ids["expanded_supersedes"]],
    )

    service = _service(neo4j_driver, es_client)

    async def _fail_mget(**kwargs: Any) -> set[str]:
        raise MgetRetrievalError("injected mget failure", retryable=True)

    with patch.object(service._mget_repo, "exists_many", side_effect=_fail_mget):
        outcome = await service.recall(
            AuthoritativeRecallQuery(hybrid_success=_hybrid_success_for_seed(ids["seed"])),
        )

    assert outcome.success is not None
    assert len(outcome.success.direct_candidates) == 1
    assert outcome.success.expanded_candidates == []
    assert any(w.kind == "graph_expansion_failed" for w in outcome.success.warnings)
