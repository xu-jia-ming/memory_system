"""Integration tests for memory_extraction_task Mongo upsert / unique index (EXT-001)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    MEMORY_EXTRACTION_TASK_COLLECTION,
    find_extraction_task_by_archive_id,
    mark_completed,
    mark_processing_from_pending,
    upsert_pending_extraction_task,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
MONGODB_CONTAINER = "memory-system-mongodb-test"
MONGODB_DATABASE = "memory_system"
FIXED_NOW = 1_700_000_000


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


def _mongodb_container_ip() -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            MONGODB_CONTAINER,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


def _run_init_infra() -> subprocess.CompletedProcess[str]:
    return _compose("run", "--rm", "init-infra", check=False)


@pytest.fixture(scope="module")
def test_mongo() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run extraction task mongo integration")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "mongodb", check=False)
    if up.returncode != 0:
        pytest.skip(
            "Unable to start compose test Mongo "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 120
    while time.time() < deadline:
        if _mongodb_container_ip():
            break
        time.sleep(2)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Test Mongo container did not become ready in time")

    migrate = _run_init_infra()
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra migration failed: "
            f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    ip = _mongodb_container_ip()
    if not ip:
        _compose("down", "-v", check=False)
        pytest.skip("Could not resolve test Mongo container IP")

    yield f"mongodb://{ip}:27017/{MONGODB_DATABASE}"

    _compose("down", "-v", check=False)


@pytest.fixture
async def mongo_client(test_mongo: str) -> AsyncIterator[AsyncMongoClient[Any]]:
    client: AsyncMongoClient[Any] = AsyncMongoClient(test_mongo)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        await client.close()
        pytest.skip(f"Mongo ping failed: {exc}")
    yield client
    await client.close()


@pytest.fixture(autouse=True)
async def _clean_tasks(mongo_client: AsyncMongoClient[Any]) -> AsyncIterator[None]:
    db = mongo_client.get_default_database()
    if db is not None:
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})
    yield
    if db is not None:
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_twice_same_archive_one_document(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    archive_id = str(uuid.uuid4())
    first = await upsert_pending_extraction_task(
        mongo_client, archive_id=archive_id, user_id="user-a", now=FIXED_NOW
    )
    second = await upsert_pending_extraction_task(
        mongo_client, archive_id=archive_id, user_id="user-b", now=FIXED_NOW + 10
    )
    assert first.task_id == second.task_id
    assert second.status == ExtractionTaskStatus.PENDING
    assert second.user_id == "user-a"  # $setOnInsert did not overwrite
    assert second.created_time == FIXED_NOW

    db = mongo_client.get_default_database()
    assert db is not None
    count = await db[MEMORY_EXTRACTION_TASK_COLLECTION].count_documents(
        {"archive_id": archive_id}
    )
    assert count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_indexes_present(mongo_client: AsyncMongoClient[Any]) -> None:
    db = mongo_client.get_default_database()
    assert db is not None
    indexes = await db[MEMORY_EXTRACTION_TASK_COLLECTION].index_information()
    assert "archive_id_unique" in indexes
    assert indexes["archive_id_unique"].get("unique") is True
    assert "status_updated_time" in indexes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_upsert_single_document(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    archive_id = str(uuid.uuid4())

    async def _once(user: str) -> str:
        task = await upsert_pending_extraction_task(
            mongo_client, archive_id=archive_id, user_id=user, now=FIXED_NOW
        )
        return task.task_id

    ids = await asyncio.gather(_once("u1"), _once("u2"), _once("u3"))
    assert len(set(ids)) == 1
    db = mongo_client.get_default_database()
    assert db is not None
    count = await db[MEMORY_EXTRACTION_TASK_COLLECTION].count_documents(
        {"archive_id": archive_id}
    )
    assert count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_completed_not_overwritten_by_upsert(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    archive_id = str(uuid.uuid4())
    await upsert_pending_extraction_task(
        mongo_client, archive_id=archive_id, user_id="user-a", now=FIXED_NOW
    )
    processing = await mark_processing_from_pending(
        mongo_client, archive_id=archive_id, now=FIXED_NOW + 1
    )
    assert processing is not None
    completed = await mark_completed(
        mongo_client, archive_id=archive_id, now=FIXED_NOW + 2
    )
    assert completed.status == ExtractionTaskStatus.COMPLETED

    again = await upsert_pending_extraction_task(
        mongo_client, archive_id=archive_id, user_id="user-a", now=FIXED_NOW + 99
    )
    assert again.status == ExtractionTaskStatus.COMPLETED
    assert again.task_id == completed.task_id
    loaded = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert loaded is not None
    assert loaded.status == ExtractionTaskStatus.COMPLETED
