"""Integration tests for RET-005 Neo4j retrieval statistics writes."""

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
from tests.support.ret005_neo4j_fixtures import (
    MEMORY_STATS_A,
    MEMORY_STATS_B,
    USER_RET005_A,
    seed_ret005_stats_memories,
)

from memory_system.infrastructure.neo4j.retrieval_statistics_repository import (
    RetrievalStatisticsRepository,
)
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
NEO4J_CONTAINER = "memory-system-neo4j-test"
CURRENT_TIME = 1_700_000_300


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


@pytest.fixture(scope="module")
def neo4j_stack() -> Iterator[None]:
    if not _docker_available():
        pytest.skip("docker not available")
    _ensure_dotenv()
    _compose("up", "-d", "neo4j")
    _assert_test_isolation()
    deadline = time.time() + 120
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", NEO4J_CONTAINER],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip() == "healthy":
            break
        time.sleep(2)
    else:
        pytest.fail("neo4j test container did not become healthy")
    yield
    _compose("down", check=False)


@pytest.fixture
async def neo4j_driver(neo4j_stack: None) -> AsyncIterator[AsyncDriver]:
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(settings.neo4j.uri.get_secret_value())
    try:
        await seed_ret005_stats_memories(driver)
        yield driver
    finally:
        await driver.close()


async def _read_stats(
    driver: AsyncDriver,
    *,
    memory_id: str,
    user_id: str,
) -> tuple[int, int | None]:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            RETURN m.retrieval_count AS retrieval_count,
                   m.last_retrieved_time AS last_retrieved_time
            """,
            memory_id=memory_id,
            user_id=user_id,
        )
        record = await result.single()
        assert record is not None
        return int(record["retrieval_count"]), record["last_retrieved_time"]


@pytest.mark.asyncio
async def test_i3_stats_increment_and_monotonic_time(neo4j_driver: AsyncDriver) -> None:
    settings = get_settings()
    repo = RetrievalStatisticsRepository(
        neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )

    before_a_count, before_a_time = await _read_stats(
        neo4j_driver,
        memory_id=MEMORY_STATS_A,
        user_id=USER_RET005_A,
    )
    before_b_count, before_b_time = await _read_stats(
        neo4j_driver,
        memory_id=MEMORY_STATS_B,
        user_id=USER_RET005_A,
    )

    await repo.increment_retrieval_stats(
        user_id=USER_RET005_A,
        memory_ids=[MEMORY_STATS_A, MEMORY_STATS_B, MEMORY_STATS_A],
        current_time=CURRENT_TIME,
    )

    after_a_count, after_a_time = await _read_stats(
        neo4j_driver,
        memory_id=MEMORY_STATS_A,
        user_id=USER_RET005_A,
    )
    after_b_count, after_b_time = await _read_stats(
        neo4j_driver,
        memory_id=MEMORY_STATS_B,
        user_id=USER_RET005_A,
    )

    assert before_a_count == 2
    assert after_a_count == before_a_count + 1
    assert after_b_count == before_b_count + 1
    assert after_a_time == CURRENT_TIME
    assert after_b_time == CURRENT_TIME
    assert before_a_time is not None
    assert after_a_time >= before_a_time
    assert before_b_time is None
