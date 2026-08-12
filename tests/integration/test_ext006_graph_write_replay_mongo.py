"""Integration tests for EXT-006 graph write replay from persisted Mongo tasks."""

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
from memory_system.domain.models.graph_write import GraphWriteAbort, GraphWriteOutcomeKind
from memory_system.domain.models.reconciliation import (
    PerCandidateDecision,
    PlannedMemoryCreate,
    ReasonCode,
    ReconciliationAction,
    ReconciliationSuccess,
)
from memory_system.domain.services.extraction_fingerprint import compute_candidate_fingerprint
from memory_system.domain.services.graph_write_service import GraphWriteService
from memory_system.infrastructure.mongodb.context_archive_repository import insert_context_archive
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    MEMORY_EXTRACTION_TASK_COLLECTION,
    find_extraction_task_by_archive_id,
    mark_processing_from_pending,
    set_extraction_result,
    upsert_pending_extraction_task,
)
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.settings import get_settings

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


class _FakeEvidenceRepository:
    async def find_processed_evidence_ids(
        self, user_id: str, evidence_ids: list[str]
    ) -> set[str]:
        return set()


class _RecordingWriteRepository:
    def __init__(self) -> None:
        self.called = False

    async def write(self, plan: Any) -> None:
        self.called = True


class _FakeArchiveTimestampRepository:
    async def resolve_source_time_range(
        self,
        mongodb: AsyncMongoClient[Any],
        archive_id: str,
        source_message_ids: list[str],
        candidate_source_time: int,
    ) -> tuple[int, int]:
        return candidate_source_time, candidate_source_time


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


def _reconciliation_success(user_id: str, archive_id: str) -> ReconciliationSuccess:
    return ReconciliationSuccess(
        user_id=user_id,
        archive_id=archive_id,
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint=_persisted_extraction_payload()["memories"][0][
                    "candidate_fingerprint"
                ],
                evidence_id="ev-1",
                action=ReconciliationAction.CREATE,
                target_memory_id=None,
                reason_code=ReasonCode.NEW_MEMORY,
                skip_reason=None,
                merged_content=None,
                recalled_memory_count=0,
                aligned_memory_key="key-1",
            ),
        ],
        existing_memory_update_plans=[],
        new_memory_create_plans=[
            PlannedMemoryCreate(
                create_kind="create",
                planned_memory_id="planned-memory-id",
                aligned_memory_key="key-1",
                supersedes_target_memory_id=None,
                conflicts_with_target_memory_id=None,
                memory_type="event",
                planned_content="用户正在开发 Agent Memory System",
                subject_entity_id=f"user:{user_id}",
                predicate="works_on",
                object_entity_id="entity:project-1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text="正在",
                planned_confidence=0.95,
                planned_importance=0.55,
                planned_latest_source_time=FIXED_NOW,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
            ),
        ],
    )


@pytest.fixture(scope="module")
def test_mongo() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run EXT-006 mongo integration")
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
async def _clean_collections(mongo_client: AsyncMongoClient[Any]) -> AsyncIterator[None]:
    db = mongo_client.get_default_database()
    if db is not None:
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})
        await db["context_archive"].delete_many({})
    yield
    if db is not None:
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})
        await db["context_archive"].delete_many({})


async def _seed_processing_task(
    mongo_client: AsyncMongoClient[Any],
    *,
    archive_id: str,
    user_id: str,
    session_id: str,
) -> None:
    await insert_context_archive(
        mongo_client,
        {
            "archive_id": archive_id,
            "user_id": user_id,
            "session_id": session_id,
            "archive_batch_key": f"{session_id}:msg:start:end",
            "base_compression_version": 0,
            "messages": [
                {
                    "message_id": "msg_000001",
                    "role": "user",
                    "content": "archive message",
                    "timestamp": FIXED_NOW,
                }
            ],
            "created_time": FIXED_NOW,
        },
    )
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


def _service(write_repo: _RecordingWriteRepository) -> GraphWriteService:
    return GraphWriteService(
        _FakeEvidenceRepository(),
        write_repo,
        tokenize_client=FakeTokenizeClient(token_count=10),
        settings=get_settings(),
        archive_timestamp_repository=_FakeArchiveTimestampRepository(),
        server_time_provider=lambda: FIXED_NOW,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m1_load_metadata_and_injected_plan_writes(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext006"
    session_id = str(uuid.uuid4())
    await _seed_processing_task(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )
    write_repo = _RecordingWriteRepository()
    service = _service(write_repo)
    result = await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=_alignment_success(user_id),
        reconciliation_success=_reconciliation_success(user_id, archive_id),
    )
    assert not isinstance(result, GraphWriteAbort)
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    assert write_repo.called is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m2_task_document_unchanged(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext006"
    session_id = str(uuid.uuid4())
    await _seed_processing_task(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )
    before = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert before is not None
    before_doc = before.model_dump(mode="json")
    write_repo = _RecordingWriteRepository()
    service = _service(write_repo)
    await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=_alignment_success(user_id),
        reconciliation_success=_reconciliation_success(user_id, archive_id),
    )
    after = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert after is not None
    assert after.model_dump(mode="json") == before_doc


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m3_task_remains_processing(mongo_client: AsyncMongoClient[Any]) -> None:
    archive_id = str(uuid.uuid4())
    user_id = "user-ext006"
    session_id = str(uuid.uuid4())
    await _seed_processing_task(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
    )
    write_repo = _RecordingWriteRepository()
    service = _service(write_repo)
    await service.load_from_persisted_task(
        mongo_client,
        archive_id,
        entity_alignment_success=_alignment_success(user_id),
        reconciliation_success=_reconciliation_success(user_id, archive_id),
    )
    task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert task is not None
    assert task.status == ExtractionTaskStatus.PROCESSING
    assert task.completed_time is None
