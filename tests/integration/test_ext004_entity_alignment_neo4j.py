"""Integration tests for EXT-004 entity alignment against real Neo4j."""

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
from neo4j import AsyncDriver, AsyncGraphDatabase

from memory_system.domain.models.entity_alignment import EntityAlignmentInput, EntityMatchKind
from memory_system.domain.models.extraction_llm import (
    RESERVED_USER_ENTITY_ID,
    ExtractionEntityCandidate,
    ExtractionMemoryCandidate,
)
from memory_system.domain.services.entity_alignment_service import EntityAlignmentService
from memory_system.domain.services.entity_key import (
    compute_entity_key,
    normalize_entity_name,
    planned_user_entity_fields,
)
from memory_system.infrastructure.neo4j.entity_alignment_repository import EntityAlignmentRepository

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
def test_neo4j_uri() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run EXT-004 Neo4j integration")
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
async def neo4j_driver(test_neo4j_uri: str) -> AsyncIterator[AsyncDriver]:
    driver = AsyncGraphDatabase.driver(test_neo4j_uri)
    try:
        await driver.verify_connectivity()
    except Exception as exc:
        await driver.close()
        pytest.skip(f"Neo4j ping failed: {exc}")
    yield driver
    await driver.close()


@pytest.fixture(autouse=True)
async def _clean_entities(neo4j_driver: AsyncDriver) -> AsyncIterator[None]:
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")


async def _count_entities(driver: AsyncDriver) -> int:
    async with driver.session() as session:
        result = await session.run("MATCH (e:Entity) RETURN count(e) AS count")
        record = await result.single()
        assert record is not None
        return int(record["count"])


async def _create_entity(
    driver: AsyncDriver,
    *,
    entity_id: str,
    user_id: str,
    entity_type: str,
    canonical_name: str,
    normalized_name: str,
    aliases: list[str] | None = None,
) -> None:
    entity_key = compute_entity_key(
        user_id=user_id,
        entity_type=entity_type,
        normalized_name=normalized_name,
    )
    async with driver.session() as session:
        await session.run(
            """
            CREATE (e:Entity {
              entity_id: $entity_id,
              user_id: $user_id,
              entity_key: $entity_key,
              entity_type: $entity_type,
              canonical_name: $canonical_name,
              normalized_name: $normalized_name,
              aliases: $aliases
            })
            """,
            entity_id=entity_id,
            user_id=user_id,
            entity_key=entity_key,
            entity_type=entity_type,
            canonical_name=canonical_name,
            normalized_name=normalized_name,
            aliases=aliases or [],
        )


def _alignment_input(
    *,
    user_id: str,
    entities: list[ExtractionEntityCandidate],
    include_user_reference: bool = False,
) -> EntityAlignmentInput:
    memories: list[ExtractionMemoryCandidate] = []
    if include_user_reference:
        memories.append(
            ExtractionMemoryCandidate(
                memory_type="fact",
                content="integration",
                subject_entity_id=RESERVED_USER_ENTITY_ID,
                predicate="works_on",
                object_entity_id=entities[0].local_entity_id if entities else None,
                object_value=None,
                event_status=None,
                start_time=None,
                end_time=None,
                original_time_text=None,
                confidence=0.9,
                source_message_ids=["msg_000001"],
                candidate_source_time=1,
                candidate_fingerprint="fp",
            )
        )
    elif entities:
        memories.append(
            ExtractionMemoryCandidate(
                memory_type="fact",
                content="integration",
                subject_entity_id=entities[0].local_entity_id,
                predicate="knows",
                object_entity_id=None,
                object_value=None,
                event_status=None,
                start_time=None,
                end_time=None,
                original_time_text=None,
                confidence=0.9,
                source_message_ids=["msg_000001"],
                candidate_source_time=1,
                candidate_fingerprint="fp",
            )
        )
    referenced = {memory.subject_entity_id for memory in memories}
    for memory in memories:
        if memory.object_entity_id is not None:
            referenced.add(memory.object_entity_id)
    return EntityAlignmentInput(
        task_id=str(uuid.uuid4()),
        archive_id=str(uuid.uuid4()),
        user_id=user_id,
        entities=entities,
        referenced_local_entity_ids=referenced,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_entity_key_exact_hit(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-a"
    await _create_entity(
        neo4j_driver,
        entity_id="entity-existing",
        user_id=user_id,
        entity_type="project",
        canonical_name="Memory System",
        normalized_name=normalize_entity_name("Memory System"),
    )
    before = await _count_entities(neo4j_driver)
    service = EntityAlignmentService(EntityAlignmentRepository(neo4j_driver))
    outcome = await service.align(
        _alignment_input(
            user_id=user_id,
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="Memory System",
                    type="project",
                    aliases=[],
                )
            ],
        )
    )
    assert outcome.success is not None
    assert outcome.success.alignments[0].entity_id == "entity-existing"
    assert await _count_entities(neo4j_driver) == before


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_planned_create_zero_writes(neo4j_driver: AsyncDriver) -> None:
    before = await _count_entities(neo4j_driver)
    service = EntityAlignmentService(
        EntityAlignmentRepository(neo4j_driver),
        entity_id_factory=lambda: "planned-entity",
    )
    outcome = await service.align(
        _alignment_input(
            user_id="user-a",
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="New Concept",
                    type="concept",
                    aliases=[],
                )
            ],
        )
    )
    assert outcome.success.alignments[0].planned_create is True  # type: ignore[union-attr]
    assert await _count_entities(neo4j_driver) == before


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_reserved_user_existing_and_planned(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-a"
    fields = planned_user_entity_fields(user_id)
    service = EntityAlignmentService(
        EntityAlignmentRepository(neo4j_driver),
        entity_id_factory=lambda: "planned-user",
    )
    planned = await service.align(
        _alignment_input(user_id=user_id, entities=[], include_user_reference=True)
    )
    assert planned.success.alignments[0].match_kind == EntityMatchKind.RESERVED_USER_PLANNED_CREATE  # type: ignore[union-attr]

    await _create_entity(
        neo4j_driver,
        entity_id=fields["entity_id"],
        user_id=user_id,
        entity_type="person",
        canonical_name="current_user",
        normalized_name="current_user",
    )
    existing = await service.align(
        _alignment_input(user_id=user_id, entities=[], include_user_reference=True)
    )
    assert existing.success.alignments[0].match_kind == EntityMatchKind.RESERVED_USER_EXISTING  # type: ignore[union-attr]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_secondary_match_and_multi_hit(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-a"
    await _create_entity(
        neo4j_driver,
        entity_id="z-entity",
        user_id=user_id,
        entity_type="person",
        canonical_name="Sam",
        normalized_name="sam",
    )
    await _create_entity(
        neo4j_driver,
        entity_id="a-entity",
        user_id=user_id,
        entity_type="person",
        canonical_name="Sam",
        normalized_name="sam",
    )
    service = EntityAlignmentService(EntityAlignmentRepository(neo4j_driver))
    outcome = await service.align(
        _alignment_input(
            user_id=user_id,
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="Sam",
                    type="person",
                    aliases=[],
                )
            ],
        )
    )
    assert outcome.success.alignments[0].entity_id == "a-entity"  # type: ignore[union-attr]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4b_same_batch_entity_key_collision(neo4j_driver: AsyncDriver) -> None:
    before = await _count_entities(neo4j_driver)
    factory_calls = 0

    def factory() -> str:
        nonlocal factory_calls
        factory_calls += 1
        return f"planned-{factory_calls}"

    service = EntityAlignmentService(
        EntityAlignmentRepository(neo4j_driver),
        entity_id_factory=factory,
    )
    outcome = await service.align(
        _alignment_input(
            user_id="user-a",
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="Same",
                    type="person",
                    aliases=[],
                ),
                ExtractionEntityCandidate(
                    local_entity_id="entity_2",
                    name="Same",
                    type="person",
                    aliases=[],
                ),
            ],
        )
    )
    mapping = outcome.success.local_entity_id_map()  # type: ignore[union-attr]
    assert mapping["entity_1"] == mapping["entity_2"]
    assert factory_calls == 1
    assert await _count_entities(neo4j_driver) == before


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_cross_user_isolation(neo4j_driver: AsyncDriver) -> None:
    await _create_entity(
        neo4j_driver,
        entity_id="entity-b",
        user_id="user-b",
        entity_type="person",
        canonical_name="Alice",
        normalized_name="alice",
    )
    service = EntityAlignmentService(
        EntityAlignmentRepository(neo4j_driver),
        entity_id_factory=lambda: "planned-a",
    )
    outcome = await service.align(
        _alignment_input(
            user_id="user-a",
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="Alice",
                    type="person",
                    aliases=[],
                )
            ],
        )
    )
    assert outcome.success.alignments[0].planned_create is True  # type: ignore[union-attr]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_zero_writes_properties_unchanged(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-a"
    await _create_entity(
        neo4j_driver,
        entity_id="entity-1",
        user_id=user_id,
        entity_type="person",
        canonical_name="Alice",
        normalized_name="alice",
        aliases=["Beta"],
    )
    async with neo4j_driver.session() as session:
        result = await session.run("MATCH (e:Entity) RETURN properties(e) AS props")
        before = [record.data() async for record in result]
    service = EntityAlignmentService(EntityAlignmentRepository(neo4j_driver))
    await service.align(
        _alignment_input(
            user_id=user_id,
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="Alice",
                    type="person",
                    aliases=["Gamma"],
                )
            ],
        )
    )
    async with neo4j_driver.session() as session:
        result = await session.run("MATCH (e:Entity) RETURN properties(e) AS props")
        after = [record.data() async for record in result]
    assert before == after


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i7_query_failure_maps_to_entity_alignment_failed() -> None:
    class BrokenDriver:
        def session(self) -> Any:
            raise RuntimeError("neo4j down")

    service = EntityAlignmentService(EntityAlignmentRepository(BrokenDriver()))  # type: ignore[arg-type]
    outcome = await service.align(
        _alignment_input(
            user_id="user-a",
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="Alice",
                    type="person",
                    aliases=[],
                )
            ],
        )
    )
    assert outcome.failure is not None
    assert outcome.failure.error_code == "entity_alignment_failed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i8_batch_100_candidates(neo4j_driver: AsyncDriver) -> None:
    entities = [
        ExtractionEntityCandidate(
            local_entity_id=f"entity_{index}",
            name=f"Name {index}",
            type="person",
            aliases=[],
        )
        for index in range(100)
    ]
    service = EntityAlignmentService(
        EntityAlignmentRepository(neo4j_driver),
        entity_id_factory=lambda: "planned",
    )
    outcome = await service.align(_alignment_input(user_id="user-a", entities=entities))
    assert outcome.success is not None
    assert len(outcome.success.alignments) == 100
