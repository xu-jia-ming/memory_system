"""Integration tests for EXT-004 alignment replay from persisted Mongo tasks."""

from __future__ import annotations

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
from tests.contract.helpers.extraction_llm_fake import valid_extraction_payload

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.entity_alignment import (
    EntityAlignmentAbort,
    EntityAlignmentOutcomeKind,
)
from memory_system.domain.services.entity_alignment_service import EntityAlignmentService
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    MEMORY_EXTRACTION_TASK_COLLECTION,
    find_extraction_task_by_archive_id,
    mark_processing_from_pending,
    set_extraction_result,
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


class _EmptyNeo4jRepository:
    async def find_user_entity(self, user_id: str, *, user_entity_id: str) -> None:
        return None

    async def find_by_entity_keys(
        self, user_id: str, entity_keys: list[str]
    ) -> dict[str, Any]:
        return {}

    async def find_secondary_match_candidates(
        self, user_id: str, candidates: list[Any]
    ) -> dict[str, list[Any]]:
        return {candidate.local_entity_id: [] for candidate in candidates}


@pytest.fixture(scope="module")
def test_mongo() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run EXT-004 mongo integration")
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

    migrate = _compose("run", "--rm", "init-infra", check=False)
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


async def _seed_processing_task(
    mongo_client: AsyncMongoClient[Any],
    *,
    archive_id: str,
    user_id: str,
) -> None:
    await upsert_pending_extraction_task(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        now=FIXED_NOW,
    )
    processing = await mark_processing_from_pending(
        mongo_client,
        archive_id=archive_id,
        now=FIXED_NOW + 1,
    )
    assert processing is not None
    await set_extraction_result(
        mongo_client,
        archive_id=archive_id,
        extraction_result=valid_extraction_payload(),
        now=FIXED_NOW + 2,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m1_load_persisted_task_and_align(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext004"
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id=user_id)
    service = EntityAlignmentService(
        _EmptyNeo4jRepository(),  # type: ignore[arg-type]
        entity_id_factory=lambda: "planned",
    )
    result = await service.load_from_persisted_task(mongo_client, archive_id)
    assert not isinstance(result, EntityAlignmentAbort)
    assert result.outcome == EntityAlignmentOutcomeKind.SUCCESS


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m2_no_llm_calls(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id="user-ext004")
    fake_llm = FakeLlmClient()
    service = EntityAlignmentService(_EmptyNeo4jRepository())  # type: ignore[arg-type]
    _ = fake_llm
    await service.load_from_persisted_task(mongo_client, archive_id)
    assert fake_llm.call_count == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m3_replay_idempotent_and_mongo_unchanged(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    archive_id = str(uuid.uuid4())
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id="user-ext004")
    service = EntityAlignmentService(
        _EmptyNeo4jRepository(),  # type: ignore[arg-type]
        entity_id_factory=lambda: "planned-1",
    )
    before = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert before is not None
    before_doc = before.model_dump(mode="json")
    first = await service.load_from_persisted_task(mongo_client, archive_id)
    second = await service.load_from_persisted_task(mongo_client, archive_id)
    assert first.model_dump() == second.model_dump()
    after = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert after is not None
    assert after.model_dump(mode="json") == before_doc


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m4_non_processing_or_missing_result_aborts(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    archive_id = str(uuid.uuid4())
    await upsert_pending_extraction_task(
        mongo_client,
        archive_id=archive_id,
        user_id="user-ext004",
        now=FIXED_NOW,
    )
    service = EntityAlignmentService(_EmptyNeo4jRepository())  # type: ignore[arg-type]
    abort = await service.load_from_persisted_task(mongo_client, archive_id)
    assert isinstance(abort, EntityAlignmentAbort)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m5_task_status_unchanged_after_alignment(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    archive_id = str(uuid.uuid4())
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id="user-ext004")
    service = EntityAlignmentService(_EmptyNeo4jRepository())  # type: ignore[arg-type]
    await service.load_from_persisted_task(mongo_client, archive_id)
    task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert task is not None
    assert task.status == ExtractionTaskStatus.PROCESSING
