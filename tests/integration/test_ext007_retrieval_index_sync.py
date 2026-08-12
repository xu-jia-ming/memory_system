"""Integration tests for EXT-007 retrieval index sync."""

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
from elasticsearch import AsyncElasticsearch
from neo4j import AsyncDriver, AsyncGraphDatabase
from pymongo import AsyncMongoClient
from tests.support.fake_retrieval_index_embedding_client import FakeEmbeddingClient
from tests.support.fake_retrieval_index_write_repository import FakeRetrievalIndexWriteRepository

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.graph_write import GraphWriteSuccess, IndexSyncMemoryEntry
from memory_system.domain.models.retrieval_index_sync import RetrievalIndexSyncInput
from memory_system.domain.services.core_search_text import build_core_search_text
from memory_system.domain.services.retrieval_index_sync_service import (
    RetrievalIndexSyncService,
    create_retrieval_index_sync_service,
)
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    MEMORY_EXTRACTION_TASK_COLLECTION,
    find_extraction_task_by_archive_id,
    mark_processing_from_pending,
    upsert_pending_extraction_task,
)
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
MONGODB_CONTAINER = "memory-system-mongodb-test"
NEO4J_CONTAINER = "memory-system-neo4j-test"
ELASTICSEARCH_CONTAINER = "memory-system-elasticsearch-test"
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
def test_infra() -> Iterator[tuple[str, str, str]]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run EXT-007 integration")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "mongodb", "neo4j", "elasticsearch", check=False)
    if up.returncode != 0:
        pytest.skip(
            "Unable to start compose test infra "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 180
    while time.time() < deadline:
        if (
            _container_ip(MONGODB_CONTAINER)
            and _container_ip(NEO4J_CONTAINER)
            and _container_ip(ELASTICSEARCH_CONTAINER)
        ):
            break
        time.sleep(2)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Test infra containers did not become ready in time")

    migrate = _compose("run", "--rm", "init-infra", check=False)
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra migration failed: "
            f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    mongo_ip = _container_ip(MONGODB_CONTAINER)
    neo4j_ip = _container_ip(NEO4J_CONTAINER)
    es_ip = _container_ip(ELASTICSEARCH_CONTAINER)
    if not mongo_ip or not neo4j_ip or not es_ip:
        _compose("down", "-v", check=False)
        pytest.skip("Could not resolve test infra container IPs")

    yield (
        f"mongodb://{mongo_ip}:27017/{MONGODB_DATABASE}",
        f"neo4j://{neo4j_ip}:7687",
        f"http://{es_ip}:9200",
    )
    _compose("down", "-v", check=False)


@pytest.fixture
async def mongo_client(test_infra: tuple[str, str, str]) -> AsyncIterator[AsyncMongoClient[Any]]:
    mongo_uri, _, _ = test_infra
    client: AsyncMongoClient[Any] = AsyncMongoClient(mongo_uri)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        await client.close()
        pytest.skip(f"Mongo ping failed: {exc}")
    yield client
    await client.close()


@pytest.fixture
async def neo4j_driver(test_infra: tuple[str, str, str]) -> AsyncIterator[AsyncDriver]:
    _, neo4j_uri, _ = test_infra
    driver = AsyncGraphDatabase.driver(neo4j_uri)
    try:
        await driver.verify_connectivity()
    except Exception as exc:
        await driver.close()
        pytest.skip(f"Neo4j ping failed: {exc}")
    yield driver
    await driver.close()


@pytest.fixture
async def es_client(test_infra: tuple[str, str, str]) -> AsyncIterator[AsyncElasticsearch]:
    _, _, es_url = test_infra
    client = AsyncElasticsearch(hosts=[es_url], request_timeout=30)
    try:
        await client.info()
    except Exception as exc:
        await client.close()
        pytest.skip(f"Elasticsearch ping failed: {exc}")
    yield client
    await client.close()


@pytest.fixture(autouse=True)
async def _clean_stores(
    mongo_client: AsyncMongoClient[Any],
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> AsyncIterator[None]:
    db = mongo_client.get_default_database()
    if db is not None:
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    settings = get_settings()
    await es_client.delete_by_query(
        index=settings.memory_retrieval.index_name,
        body={"query": {"match_all": {}}},
        refresh=True,
        conflicts="proceed",
    )
    yield
    if db is not None:
        await db[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many({})
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    await es_client.delete_by_query(
        index=settings.memory_retrieval.index_name,
        body={"query": {"match_all": {}}},
        refresh=True,
        conflicts="proceed",
    )


def _alignment(user_id: str, *, include_project: bool = True) -> EntityAlignmentSuccess:
    alignments = [
        AlignedEntity(
            local_entity_id="user",
            entity_id=f"user:{user_id}",
            match_kind=EntityMatchKind.RESERVED_USER_EXISTING,
            entity_type="person",
            canonical_name="current_user",
            normalized_name="current_user",
            entity_key=f"user-key-{user_id}",
            planned_alias_merge=PlannedEntityAliasMerge(
                normalized_candidate_aliases=[],
                existing_aliases=[],
                planned_aliases=[],
                omitted_alias_count=0,
            ),
            existing_entity=None,
            planned_create=False,
        ),
    ]
    if include_project:
        alignments.append(
            AlignedEntity(
                local_entity_id="entity_1",
                entity_id="entity-project",
                match_kind=EntityMatchKind.PLANNED_CREATE,
                entity_type="project",
                canonical_name="Project",
                normalized_name="project",
                entity_key="entity-key-1",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=["Alias A"],
                    planned_aliases=["Alias A"],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=True,
            ),
        )
    return EntityAlignmentSuccess(user_id=user_id, alignments=alignments)


async def _seed_memory_graph(
    driver: AsyncDriver,
    *,
    user_id: str,
    memory_id: str,
    content: str = "integration content",
    related_memory_id: str | None = None,
    link_entity: bool = True,
) -> str:
    core = build_core_search_text(
        user_id=user_id,
        content=content,
        subject_entity_id=f"user:{user_id}",
        subject_canonical_name="current_user",
        predicate="works_on",
        object_entity_id="entity-project" if link_entity else None,
        object_canonical_name="Project" if link_entity else None,
        object_value=None,
    )
    async with driver.session() as session:
        await session.run(
            """
            MERGE (u:Entity {entity_id: $user_entity_id})
            SET u.user_id = $user_id,
                u.canonical_name = 'current_user',
                u.aliases = []
            MERGE (p:Entity {entity_id: 'entity-project'})
            SET p.user_id = $user_id,
                p.canonical_name = 'Project',
                p.aliases = ['Alias A']
            MERGE (m:Memory {memory_id: $memory_id})
            SET m.user_id = $user_id,
                m.memory_type = 'event',
                m.content = $content,
                m.subject_entity_id = $user_entity_id,
                m.predicate = 'works_on',
                m.object_entity_id = CASE WHEN $link_entity THEN 'entity-project' ELSE null END,
                m.object_value = null,
                m.status = 'active',
                m.event_status = 'ongoing',
                m.latest_source_time = 150,
                m.updated_time = $updated_time
            MERGE (m)-[:SUBJECT]->(u)
            FOREACH (_ IN CASE WHEN $link_entity THEN [1] ELSE [] END |
              MERGE (m)-[:OBJECT]->(p)
            )
            """,
            user_id=user_id,
            user_entity_id=f"user:{user_id}",
            memory_id=memory_id,
            content=content,
            link_entity=link_entity,
            updated_time=FIXED_NOW,
        )
        if related_memory_id is not None:
            await session.run(
                """
                MERGE (old:Memory {memory_id: $related_memory_id})
                SET old.user_id = $user_id,
                    old.memory_type = 'event',
                    old.content = 'older content',
                    old.subject_entity_id = $user_entity_id,
                    old.predicate = 'works_on',
                    old.object_entity_id = 'entity-project',
                    old.object_value = null,
                    old.status = 'superseded',
                    old.event_status = null,
                    old.latest_source_time = 100,
                    old.updated_time = $updated_time
                MERGE (m:Memory {memory_id: $memory_id})
                MERGE (m)-[:SUPERSEDES]->(old)
                """,
                user_id=user_id,
                user_entity_id=f"user:{user_id}",
                memory_id=memory_id,
                related_memory_id=related_memory_id,
                updated_time=FIXED_NOW,
            )
    return core


async def _processing_task(
    mongo_client: AsyncMongoClient[Any],
    *,
    user_id: str,
    archive_id: str,
) -> None:
    await upsert_pending_extraction_task(
        mongo_client,
        archive_id=archive_id,
        user_id=user_id,
        now=FIXED_NOW,
    )
    task = await mark_processing_from_pending(
        mongo_client,
        archive_id=archive_id,
        now=FIXED_NOW + 1,
    )
    assert task is not None


def _sync_service(
    driver: AsyncDriver,
    es_client: AsyncElasticsearch,
    *,
    write_repo: FakeRetrievalIndexWriteRepository | None = None,
) -> RetrievalIndexSyncService:
    settings = get_settings()
    service = create_retrieval_index_sync_service(
        driver,
        es_client,
        tokenize_client=FakeTokenizeClient(token_count=10),
        embedding_client=FakeEmbeddingClient(),
        settings=settings,
        server_time_provider=lambda: FIXED_NOW + 10,
    )
    if write_repo is not None:
        service._write_repository = write_repo
    return service


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_happy_path(
    mongo_client: AsyncMongoClient[Any],
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    user_id = "user-ext007"
    archive_id = str(uuid.uuid4())
    memory_id = "mem-happy-1"
    core = await _seed_memory_graph(neo4j_driver, user_id=user_id, memory_id=memory_id)
    await _processing_task(mongo_client, user_id=user_id, archive_id=archive_id)

    service = _sync_service(neo4j_driver, es_client)
    outcome = await service.sync(
        RetrievalIndexSyncInput(
            task_id=str(uuid.uuid4()),
            archive_id=archive_id,
            user_id=user_id,
            session_id="session-1",
            graph_write_success=GraphWriteSuccess(
                user_id=user_id,
                archive_id=archive_id,
                skipped_graph_write=False,
                index_sync_memory_set=[
                    IndexSyncMemoryEntry(
                        memory_id=memory_id,
                        core_search_text=core,
                        token_count=10,
                    ),
                ],
            ),
            entity_alignment=_alignment(user_id),
        ),
        mongodb=mongo_client,
    )

    assert outcome.outcome.value == "success"
    settings = get_settings()
    doc = await es_client.get(index=settings.memory_retrieval.index_name, id=memory_id)
    assert doc["_source"]["memory_id"] == memory_id
    task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert task is not None
    assert task.status == ExtractionTaskStatus.COMPLETED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_supersedes_neighbor_synced(
    mongo_client: AsyncMongoClient[Any],
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    user_id = "user-ext007-sup"
    archive_id = str(uuid.uuid4())
    memory_id = "mem-new"
    related_id = "mem-old"
    core = await _seed_memory_graph(
        neo4j_driver,
        user_id=user_id,
        memory_id=memory_id,
        related_memory_id=related_id,
    )
    await _processing_task(mongo_client, user_id=user_id, archive_id=archive_id)

    service = _sync_service(neo4j_driver, es_client)
    outcome = await service.sync(
        RetrievalIndexSyncInput(
            task_id=str(uuid.uuid4()),
            archive_id=archive_id,
            user_id=user_id,
            session_id=None,
            graph_write_success=GraphWriteSuccess(
                user_id=user_id,
                archive_id=archive_id,
                skipped_graph_write=False,
                index_sync_memory_set=[
                    IndexSyncMemoryEntry(
                        memory_id=memory_id,
                        core_search_text=core,
                        token_count=10,
                    ),
                ],
            ),
            entity_alignment=_alignment(user_id),
        ),
        mongodb=mongo_client,
    )

    assert outcome.outcome.value == "success"
    settings = get_settings()
    assert await es_client.exists(index=settings.memory_retrieval.index_name, id=memory_id)
    assert await es_client.exists(index=settings.memory_retrieval.index_name, id=related_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_bulk_failure_marks_failed(
    mongo_client: AsyncMongoClient[Any],
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    user_id = "user-ext007-fail"
    archive_id = str(uuid.uuid4())
    memory_id = "mem-fail"
    core = await _seed_memory_graph(neo4j_driver, user_id=user_id, memory_id=memory_id)
    await _processing_task(mongo_client, user_id=user_id, archive_id=archive_id)

    service = _sync_service(
        neo4j_driver,
        es_client,
        write_repo=FakeRetrievalIndexWriteRepository(fail=True),
    )
    outcome = await service.sync(
        RetrievalIndexSyncInput(
            task_id=str(uuid.uuid4()),
            archive_id=archive_id,
            user_id=user_id,
            session_id=None,
            graph_write_success=GraphWriteSuccess(
                user_id=user_id,
                archive_id=archive_id,
                skipped_graph_write=False,
                index_sync_memory_set=[
                    IndexSyncMemoryEntry(
                        memory_id=memory_id,
                        core_search_text=core,
                        token_count=10,
                    ),
                ],
            ),
            entity_alignment=_alignment(user_id),
        ),
        mongodb=mongo_client,
    )

    assert outcome.outcome.value == "failure"
    task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
    assert task is not None
    assert task.status == ExtractionTaskStatus.FAILED
    assert task.last_error is not None
    assert task.last_error.error_code == "retrieval_index_write_failed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_replay_upsert_updates_without_duplicate(
    mongo_client: AsyncMongoClient[Any],
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    user_id = "user-ext007-replay"
    archive_id = str(uuid.uuid4())
    memory_id = "mem-replay"
    core = await _seed_memory_graph(neo4j_driver, user_id=user_id, memory_id=memory_id)
    await _processing_task(mongo_client, user_id=user_id, archive_id=archive_id)

    sync_input = RetrievalIndexSyncInput(
        task_id=str(uuid.uuid4()),
        archive_id=archive_id,
        user_id=user_id,
        session_id=None,
        graph_write_success=GraphWriteSuccess(
            user_id=user_id,
            archive_id=archive_id,
            skipped_graph_write=False,
            index_sync_memory_set=[
                IndexSyncMemoryEntry(
                    memory_id=memory_id,
                    core_search_text=core,
                    token_count=10,
                ),
            ],
        ),
        entity_alignment=_alignment(user_id),
    )
    service = _sync_service(neo4j_driver, es_client)
    first = await service.sync(sync_input, mongodb=mongo_client)
    assert first.outcome.value == "success"

    db = mongo_client.get_default_database()
    assert db is not None
    await db[MEMORY_EXTRACTION_TASK_COLLECTION].update_one(
        {"archive_id": archive_id},
        {
            "$set": {
                "status": ExtractionTaskStatus.PROCESSING.value,
                "completed_time": None,
            }
        },
    )
    second = await service.sync(sync_input, mongodb=mongo_client)
    assert second.outcome.value == "success"

    settings = get_settings()
    count = await es_client.count(index=settings.memory_retrieval.index_name)
    assert count["count"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_user_entity_only_no_entity_expansion(
    mongo_client: AsyncMongoClient[Any],
    neo4j_driver: AsyncDriver,
    es_client: AsyncElasticsearch,
) -> None:
    user_id = "user-ext007-user-only"
    archive_id = str(uuid.uuid4())
    seed_id = "mem-seed"
    linked_id = "mem-linked"
    await _seed_memory_graph(
        neo4j_driver,
        user_id=user_id,
        memory_id=seed_id,
        link_entity=False,
    )
    await _seed_memory_graph(
        neo4j_driver,
        user_id=user_id,
        memory_id=linked_id,
        link_entity=True,
    )
    await _processing_task(mongo_client, user_id=user_id, archive_id=archive_id)

    core = build_core_search_text(
        user_id=user_id,
        content="integration content",
        subject_entity_id=f"user:{user_id}",
        subject_canonical_name="current_user",
        predicate="works_on",
        object_entity_id=None,
        object_canonical_name=None,
        object_value=None,
    )
    service = _sync_service(neo4j_driver, es_client)
    outcome = await service.sync(
        RetrievalIndexSyncInput(
            task_id=str(uuid.uuid4()),
            archive_id=archive_id,
            user_id=user_id,
            session_id=None,
            graph_write_success=GraphWriteSuccess(
                user_id=user_id,
                archive_id=archive_id,
                skipped_graph_write=False,
                index_sync_memory_set=[
                    IndexSyncMemoryEntry(
                        memory_id=seed_id,
                        core_search_text=core,
                        token_count=10,
                    ),
                ],
            ),
            entity_alignment=_alignment(user_id, include_project=False),
        ),
        mongodb=mongo_client,
    )

    assert outcome.outcome.value == "success"
    settings = get_settings()
    assert await es_client.exists(index=settings.memory_retrieval.index_name, id=seed_id)
    assert not await es_client.exists(index=settings.memory_retrieval.index_name, id=linked_id)
