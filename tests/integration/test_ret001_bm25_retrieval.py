"""Integration tests for RET-001 BM25 keyword retrieval."""

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
from tests.support.ret001_es_fixtures import (
    RET001_KEYWORD,
    USER_A,
    seed_ret001_bm25_fixtures,
)

from memory_system.domain.models.bm25_retrieval import Bm25RetrievalQuery
from memory_system.domain.services.bm25_retrieval_service import create_bm25_retrieval_service
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
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
def test_infra() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run RET-001 integration")
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

    try:
        yield f"http://{es_ip}:9200"
    finally:
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


def _service(es_client: AsyncElasticsearch):
    return create_bm25_retrieval_service(es_client, settings=get_settings())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_happy_path_keyword_ranking(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret001_bm25_fixtures(write_repo, settings.memory_retrieval.index_name)

    outcome = await _service(es_client).search(
        Bm25RetrievalQuery(user_id=USER_A, query=RET001_KEYWORD),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.hits) >= 1
    ranks = [hit.rank for hit in outcome.success.hits]
    assert ranks == list(range(1, len(ranks) + 1))
    assert all(hit.score > 0 for hit in outcome.success.hits)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_cross_user_isolation(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret001_bm25_fixtures(write_repo, settings.memory_retrieval.index_name)

    outcome = await _service(es_client).search(
        Bm25RetrievalQuery(user_id=USER_A, query=RET001_KEYWORD),
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
    await seed_ret001_bm25_fixtures(write_repo, settings.memory_retrieval.index_name)

    outcome = await _service(es_client).search(
        Bm25RetrievalQuery(
            user_id=USER_A,
            query=RET001_KEYWORD,
            memory_types=["fact"],
        ),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.hits
    memory_ids = {hit.memory_id for hit in outcome.success.hits}
    assert "mem-a-active-event" not in memory_ids
    assert "mem-a-active-profile" not in memory_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_default_status_active_only(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret001_bm25_fixtures(write_repo, settings.memory_retrieval.index_name)

    outcome = await _service(es_client).search(
        Bm25RetrievalQuery(user_id=USER_A, query=RET001_KEYWORD),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    memory_ids = {hit.memory_id for hit in outcome.success.hits}
    assert "mem-a-conflicted-fact" not in memory_ids
    assert "mem-a-superseded-fact" not in memory_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_include_conflicted(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret001_bm25_fixtures(write_repo, settings.memory_retrieval.index_name)

    outcome = await _service(es_client).search(
        Bm25RetrievalQuery(
            user_id=USER_A,
            query=RET001_KEYWORD,
            include_conflicted=True,
        ),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    memory_ids = {hit.memory_id for hit in outcome.success.hits}
    assert "mem-a-conflicted-fact" in memory_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_include_history(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret001_bm25_fixtures(write_repo, settings.memory_retrieval.index_name)

    outcome = await _service(es_client).search(
        Bm25RetrievalQuery(
            user_id=USER_A,
            query=RET001_KEYWORD,
            include_history=True,
        ),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    memory_ids = {hit.memory_id for hit in outcome.success.hits}
    assert "mem-a-superseded-fact" in memory_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i7_empty_result(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret001_bm25_fixtures(write_repo, settings.memory_retrieval.index_name)

    outcome = await _service(es_client).search(
        Bm25RetrievalQuery(user_id=USER_A, query="zzznomatchquery999"),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.hits == []
    assert outcome.success.total_hits == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i8_bm25_top_n_limit(es_client: AsyncElasticsearch) -> None:
    settings = get_settings()
    write_repo = RetrievalIndexWriteRepository(es_client)
    await seed_ret001_bm25_fixtures(
        write_repo,
        settings.memory_retrieval.index_name,
        include_top_n_bulk=True,
    )

    outcome = await _service(es_client).search(
        Bm25RetrievalQuery(user_id=USER_A, query=RET001_KEYWORD),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.hits) == settings.memory_retrieval.bm25_top_n
    assert outcome.success.total_hits == settings.memory_retrieval.bm25_top_n
