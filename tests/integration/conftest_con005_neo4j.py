"""Shared Neo4j-only fixtures for CON-005 integration and E2E tests."""

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
from neo4j import AsyncDriver, AsyncGraphDatabase
from tests.e2e.helpers.con005_e2e_helpers import build_production_run_service

from memory_system.domain.services.consolidation_run_service import ConsolidationRunService
from memory_system.settings import Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
NEO4J_CONTAINER = "memory-system-neo4j-test"


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


def _neo4j_container_ip() -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            NEO4J_CONTAINER,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


@pytest.fixture(scope="module")
def con005_neo4j_uri() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run CON-005 Neo4j integration")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "neo4j", check=False)
    if up.returncode != 0:
        pytest.skip(
            "Unable to start compose test Neo4j "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 120
    while time.time() < deadline:
        if _neo4j_container_ip():
            break
        time.sleep(2)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Test Neo4j container did not become ready in time")

    migrate = _compose("run", "--rm", "init-infra", check=False)
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra migration failed: "
            f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    ip = _neo4j_container_ip()
    if not ip:
        _compose("down", "-v", check=False)
        pytest.skip("Could not resolve test Neo4j container IP")

    yield f"neo4j://{ip}:7687"
    _compose("down", "-v", check=False)


@pytest.fixture
async def con005_neo4j_driver(con005_neo4j_uri: str) -> AsyncIterator[AsyncDriver]:
    driver = AsyncGraphDatabase.driver(con005_neo4j_uri)
    try:
        await driver.verify_connectivity()
    except Exception as exc:
        await driver.close()
        pytest.skip(f"Neo4j ping failed: {exc}")
    yield driver
    await driver.close()


@pytest.fixture(autouse=True)
async def _clean_graph(con005_neo4j_driver: AsyncDriver) -> AsyncIterator[None]:
    async with con005_neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield
    async with con005_neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")


@pytest.fixture
def con005_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("NEO4J__URI", "neo4j://127.0.0.1:7687")
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def con005_run_service(
    con005_neo4j_driver: AsyncDriver,
    con005_settings: Settings,
) -> ConsolidationRunService:
    return build_production_run_service(con005_neo4j_driver, con005_settings)
