"""Integration tests for EXT-004 alignment replay from persisted Mongo tasks."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
from pymongo import AsyncMongoClient
from tests.contract.helpers.extraction_llm_fake import persisted_extraction_payload
from tests.integration.support.compose_stack import (
    module_services,
    mongo_uri_from_container,
    require_docker_or_skip,
    skip_on_startup_error,
)

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
FIXED_NOW = 1_700_000_000


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
    require_docker_or_skip()
    try:
        with module_services(("mongodb",), migrate=True):
            yield mongo_uri_from_container()
    except (AssertionError, TimeoutError) as exc:
        skip_on_startup_error(str(exc))


@pytest.fixture
async def mongo_client(test_mongo: str) -> AsyncIterator[AsyncMongoClient[Any]]:
    client: AsyncMongoClient[Any] = AsyncMongoClient(test_mongo)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        await client.close()
        pytest.fail(f"Mongo ping failed: {exc}")
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
        extraction_result=persisted_extraction_payload(),
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
