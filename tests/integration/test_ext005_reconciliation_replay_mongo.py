"""Integration tests for EXT-005 reconciliation replay from persisted Mongo tasks."""

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
    AlignedEntity,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.reconciliation import (
    ReconciliationAbort,
    ReconciliationOutcomeKind,
)
from memory_system.domain.services.extraction_fingerprint import compute_candidate_fingerprint
from memory_system.domain.services.reconciliation_service import ReconciliationService
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


class _EmptyEvidenceRepository:
    async def find_processed_evidence_ids(
        self, user_id: str, evidence_ids: list[str]
    ) -> set[str]:
        return set()


class _EmptyRecallRepository:
    async def recall_memories_batch(
        self, user_id: str, recall_keys: list[Any]
    ) -> dict[int, list[Any]]:
        return {key.candidate_index: [] for key in recall_keys}


def _persisted_extraction_payload() -> dict[str, Any]:
    payload = valid_extraction_payload()
    memory = payload["memories"][0]
    memory["candidate_source_time"] = FIXED_NOW
    memory["candidate_fingerprint"] = compute_candidate_fingerprint(
        memory_type=memory["memory_type"],
        content=memory["content"],
        subject_entity_id=memory["subject_entity_id"],
        predicate=memory["predicate"],
        object_entity_id=memory["object_entity_id"],
        object_value=memory["object_value"],
        event_status=memory["event_status"],
        start_time=memory["start_time"],
        end_time=memory["end_time"],
        original_time_text=memory["original_time_text"],
        source_message_ids=memory["source_message_ids"],
    )
    return payload


def _alignment_success(user_id: str) -> EntityAlignmentSuccess:
    return EntityAlignmentSuccess(
        user_id=user_id,
        alignments=[
            AlignedEntity(
                local_entity_id="user",
                entity_id=f"user:{user_id}",
                match_kind=EntityMatchKind.RESERVED_USER_EXISTING,
                entity_type="person",
                canonical_name="current_user",
                normalized_name="current_user",
                entity_key="user-key",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=[],
                    planned_aliases=[],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=False,
            ),
            AlignedEntity(
                local_entity_id="entity_1",
                entity_id="entity:project-1",
                match_kind=EntityMatchKind.PLANNED_CREATE,
                entity_type="project",
                canonical_name="Agent Memory System",
                normalized_name="agent memory system",
                entity_key="entity-key",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=[],
                    planned_aliases=[],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=True,
            ),
        ],
    )


@pytest.fixture(scope="module")
def test_mongo() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run EXT-005 mongo integration")
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
        extraction_result=_persisted_extraction_payload(),
        now=FIXED_NOW + 2,
    )


def _service() -> ReconciliationService:
    return ReconciliationService(
        _EmptyEvidenceRepository(),  # type: ignore[arg-type]
        _EmptyRecallRepository(),  # type: ignore[arg-type]
        llm_client=FakeLlmClient(),
        settings=__import__("memory_system.settings", fromlist=["get_settings"]).get_settings(),
        memory_id_factory=lambda: "planned-memory-id",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m1_load_from_mongo_and_plan(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext005"
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id=user_id)
    service = _service()
    result = await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=_alignment_success(user_id),
    )
    assert not isinstance(result, ReconciliationAbort)
    assert result.outcome == ReconciliationOutcomeKind.SUCCESS


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m2_task_document_unchanged(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext005"
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id=user_id)
    before = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert before is not None
    before_doc = before.model_dump(mode="json")
    service = _service()
    await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=_alignment_success(user_id),
    )
    after = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert after is not None
    assert after.model_dump(mode="json") == before_doc


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m3_replay_twice_identical(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext005"
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id=user_id)
    service = _service()
    alignment = _alignment_success(user_id)
    first = await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=alignment,
    )
    second = await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=alignment,
    )
    assert first.model_dump() == second.model_dump()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m4_stays_processing(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext005"
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id=user_id)
    service = _service()
    await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=_alignment_success(user_id),
    )
    task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert task is not None
    assert task.status == ExtractionTaskStatus.PROCESSING


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m4_no_extraction_llm_calls(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext005"
    await _seed_processing_task(mongo_client, archive_id=archive_id, user_id=user_id)
    fake_llm = FakeLlmClient()
    service = ReconciliationService(
        _EmptyEvidenceRepository(),  # type: ignore[arg-type]
        _EmptyRecallRepository(),  # type: ignore[arg-type]
        llm_client=fake_llm,
        settings=__import__("memory_system.settings", fromlist=["get_settings"]).get_settings(),
    )
    await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=_alignment_success(user_id),
    )
    assert fake_llm.call_count == 0
