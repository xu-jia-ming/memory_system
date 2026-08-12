"""Integration tests for EXT-006 graph write against real Neo4j."""

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

from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.extraction_llm import (
    ExtractionEntityCandidate,
    ExtractionMemoryCandidate,
    ExtractionValidatedResult,
)
from memory_system.domain.models.graph_write import GraphWriteOutcomeKind
from memory_system.domain.models.reconciliation import (
    PerCandidateDecision,
    PlannedExistingMemoryUpdate,
    PlannedMemoryCreate,
    ReasonCode,
    ReconciliationAction,
    ReconciliationSuccess,
)
from memory_system.domain.services.graph_write_service import GraphWriteService
from memory_system.infrastructure.neo4j.evidence_lookup_repository import EvidenceLookupRepository
from memory_system.infrastructure.neo4j.graph_write_repository import GraphWriteRepository
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
NEO4J_CONTAINER = "memory-system-neo4j-test"
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
        pytest.skip("Docker not available; cannot run EXT-006 Neo4j integration")
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
async def _clean_graph(neo4j_driver: AsyncDriver) -> AsyncIterator[None]:
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")


class _FakeArchiveTimestampRepository:
    async def resolve_source_time_range(
        self,
        mongodb: Any,
        archive_id: str,
        source_message_ids: list[str],
        candidate_source_time: int,
    ) -> tuple[int, int]:
        return candidate_source_time, candidate_source_time


async def _count_nodes(driver: AsyncDriver, label: str) -> int:
    async with driver.session() as session:
        result = await session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
        record = await result.single()
        assert record is not None
        return int(record["count"])


def _graph_write_service(driver: AsyncDriver) -> GraphWriteService:
    return GraphWriteService(
        EvidenceLookupRepository(driver),
        GraphWriteRepository(driver),
        tokenize_client=FakeTokenizeClient(token_count=10),
        settings=get_settings(),
        archive_timestamp_repository=_FakeArchiveTimestampRepository(),
        server_time_provider=lambda: FIXED_NOW,
    )


def _alignment(user_id: str) -> EntityAlignmentSuccess:
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
            AlignedEntity(
                local_entity_id="entity_1",
                entity_id="entity-uuid-1",
                match_kind=EntityMatchKind.PLANNED_CREATE,
                entity_type="project",
                canonical_name="Agent Memory System",
                normalized_name="agent memory system",
                entity_key="entity-key-1",
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


def _create_reconciliation(user_id: str) -> ReconciliationSuccess:
    return ReconciliationSuccess(
        user_id=user_id,
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-1",
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
                planned_memory_id="mem-new-1",
                aligned_memory_key="key-1",
                supersedes_target_memory_id=None,
                conflicts_with_target_memory_id=None,
                memory_type="event",
                planned_content="integration content",
                subject_entity_id=f"user:{user_id}",
                predicate="works_on",
                object_entity_id="entity-uuid-1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                planned_confidence=0.9,
                planned_importance=0.55,
                planned_latest_source_time=150,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
            ),
        ],
    )


def _graph_input(user_id: str) -> Any:
    from memory_system.domain.models.graph_write import GraphWriteInput

    return GraphWriteInput(
        task_id="task-1",
        archive_id="archive-1",
        user_id=user_id,
        session_id="session-1",
        extraction_result=ExtractionValidatedResult(
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="entity_1",
                    name="Agent Memory System",
                    type="project",
                    aliases=[],
                ),
            ],
            memories=[
                ExtractionMemoryCandidate(
                    memory_type="event",
                    content="integration content",
                    subject_entity_id="user",
                    predicate="works_on",
                    object_entity_id="entity_1",
                    object_value=None,
                    event_status="ongoing",
                    start_time=None,
                    end_time=None,
                    original_time_text=None,
                    confidence=0.9,
                    source_message_ids=["msg-1"],
                    candidate_source_time=150,
                    candidate_fingerprint="fp-1",
                ),
            ],
        ),
        entity_alignment=_alignment(user_id),
        reconciliation=_create_reconciliation(user_id),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_create_memory_evidence_entity(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-i1"
    service = _graph_write_service(neo4j_driver)
    from pymongo import AsyncMongoClient

    result = await service.write(
        _graph_input(user_id),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    assert await _count_nodes(neo4j_driver, "Memory") == 1
    assert await _count_nodes(neo4j_driver, "Evidence") == 1
    assert await _count_nodes(neo4j_driver, "Entity") == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_update_existing_memory(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-i2"
    async with neo4j_driver.session() as session:
        await session.run(
            """
            CREATE (m:Memory {
              memory_id: 'mem-existing-1',
              user_id: $user_id,
              memory_type: 'event',
              content: 'old content',
              subject_entity_id: $subject,
              predicate: 'works_on',
              object_entity_id: 'entity-uuid-1',
              object_value: null,
              status: 'active',
              event_status: 'ongoing',
              start_time: null,
              end_time: null,
              original_time_text: null,
              confidence: 0.7,
              importance: 0.55,
              latest_source_time: 100,
              abstraction_level: 0,
              retrieval_count: 0,
              memory_version: 2,
              first_seen_time: $now,
              last_seen_time: $now,
              created_time: $now,
              updated_time: $now,
              last_retrieved_time: null,
              last_consolidated_time: null
            })
            """,
            user_id=user_id,
            subject=f"user:{user_id}",
            now=FIXED_NOW,
        )
    reconciliation = ReconciliationSuccess(
        user_id=user_id,
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-1",
                evidence_id="ev-1",
                action=ReconciliationAction.MERGE,
                target_memory_id="mem-existing-1",
                reason_code=ReasonCode.SAME_SEMANTIC_MEMORY,
                skip_reason=None,
                merged_content="merged integration content",
                recalled_memory_count=1,
                aligned_memory_key=None,
            ),
        ],
        existing_memory_update_plans=[
            PlannedExistingMemoryUpdate(
                target_memory_id="mem-existing-1",
                aggregated_action="MERGE",
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
                planned_merged_content="merged integration content",
                planned_merged_confidence=0.85,
                planned_latest_source_time=150,
                increment_memory_version=True,
                planned_new_memory_id=None,
            ),
        ],
        new_memory_create_plans=[],
    )
    graph_input = _graph_input(user_id)
    graph_input.reconciliation = reconciliation
    service = _graph_write_service(neo4j_driver)
    from pymongo import AsyncMongoClient

    result = await service.write(
        graph_input,
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    async with neo4j_driver.session() as session:
        record = await (
            await session.run(
                "MATCH (m:Memory {memory_id: 'mem-existing-1'}) RETURN m.memory_version AS v",
            )
        ).single()
        assert record is not None
        assert int(record["v"]) == 3
    assert await _count_nodes(neo4j_driver, "Evidence") == 1


async def _seed_existing_memory(
    driver: AsyncDriver,
    *,
    user_id: str,
    memory_id: str,
    status: str = "active",
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            CREATE (m:Memory {
              memory_id: $memory_id,
              user_id: $user_id,
              memory_type: 'event',
              content: 'old content',
              subject_entity_id: $subject,
              predicate: 'works_on',
              object_entity_id: 'entity-uuid-1',
              object_value: null,
              status: $status,
              event_status: 'ongoing',
              start_time: null,
              end_time: null,
              original_time_text: null,
              confidence: 0.7,
              importance: 0.55,
              latest_source_time: 100,
              abstraction_level: 0,
              retrieval_count: 0,
              memory_version: 2,
              first_seen_time: $now,
              last_seen_time: $now,
              created_time: $now,
              updated_time: $now,
              last_retrieved_time: null,
              last_consolidated_time: null
            })
            """,
            user_id=user_id,
            memory_id=memory_id,
            subject=f"user:{user_id}",
            status=status,
            now=FIXED_NOW,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_supersede_path(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-i3-sup"
    await _seed_existing_memory(neo4j_driver, user_id=user_id, memory_id="mem-old-1")
    reconciliation = ReconciliationSuccess(
        user_id=user_id,
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-1",
                evidence_id="ev-1",
                action=ReconciliationAction.SUPERSEDE,
                target_memory_id="mem-old-1",
                reason_code=ReasonCode.EXPLICIT_CORRECTION,
                skip_reason=None,
                merged_content=None,
                recalled_memory_count=1,
                aligned_memory_key=None,
            ),
        ],
        existing_memory_update_plans=[
            PlannedExistingMemoryUpdate(
                target_memory_id="mem-old-1",
                aggregated_action="SUPERSEDE",
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
                planned_merged_content=None,
                planned_merged_confidence=None,
                planned_latest_source_time=150,
                increment_memory_version=True,
                planned_new_memory_id="mem-new-sup",
            ),
        ],
        new_memory_create_plans=[
            PlannedMemoryCreate(
                create_kind="supersede_new",
                planned_memory_id="mem-new-sup",
                aligned_memory_key=None,
                supersedes_target_memory_id="mem-old-1",
                conflicts_with_target_memory_id=None,
                memory_type="event",
                planned_content="superseding content",
                subject_entity_id=f"user:{user_id}",
                predicate="works_on",
                object_entity_id="entity-uuid-1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                planned_confidence=0.9,
                planned_importance=0.55,
                planned_latest_source_time=150,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
            ),
        ],
    )
    graph_input = _graph_input(user_id)
    graph_input.reconciliation = reconciliation
    service = _graph_write_service(neo4j_driver)
    from pymongo import AsyncMongoClient

    result = await service.write(
        graph_input,
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    async with neo4j_driver.session() as session:
        old_record = await (
            await session.run(
                "MATCH (m:Memory {memory_id: 'mem-old-1'}) RETURN m.status AS status",
            )
        ).single()
        assert old_record is not None
        assert old_record["status"] == "superseded"
        new_record = await (
            await session.run(
                "MATCH (m:Memory {memory_id: 'mem-new-sup'}) RETURN m.status AS status",
            )
        ).single()
        assert new_record is not None
        assert new_record["status"] == "active"
        rel = await (
            await session.run(
                """
                MATCH (new:Memory {memory_id: 'mem-new-sup'})-[:SUPERSEDES]->
                      (old:Memory {memory_id: 'mem-old-1'})
                RETURN count(*) AS count
                """,
            )
        ).single()
        assert rel is not None
        assert int(rel["count"]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_conflict_path(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-i3-conf"
    await _seed_existing_memory(neo4j_driver, user_id=user_id, memory_id="mem-old-1")
    reconciliation = ReconciliationSuccess(
        user_id=user_id,
        archive_id="archive-1",
        per_candidate_decisions=[
            PerCandidateDecision(
                candidate_index=0,
                candidate_fingerprint="fp-1",
                evidence_id="ev-1",
                action=ReconciliationAction.CONFLICT,
                target_memory_id="mem-old-1",
                reason_code=ReasonCode.UNRESOLVED_CONTRADICTION,
                skip_reason=None,
                merged_content=None,
                recalled_memory_count=1,
                aligned_memory_key=None,
            ),
        ],
        existing_memory_update_plans=[
            PlannedExistingMemoryUpdate(
                target_memory_id="mem-old-1",
                aggregated_action="CONFLICT",
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
                planned_merged_content=None,
                planned_merged_confidence=None,
                planned_latest_source_time=150,
                increment_memory_version=True,
                planned_new_memory_id="mem-new-conf",
            ),
        ],
        new_memory_create_plans=[
            PlannedMemoryCreate(
                create_kind="conflict_new",
                planned_memory_id="mem-new-conf",
                aligned_memory_key=None,
                supersedes_target_memory_id=None,
                conflicts_with_target_memory_id="mem-old-1",
                memory_type="event",
                planned_content="conflicting content",
                subject_entity_id=f"user:{user_id}",
                predicate="works_on",
                object_entity_id="entity-uuid-1",
                object_value=None,
                event_status="ongoing",
                start_time=None,
                end_time=None,
                original_time_text=None,
                planned_confidence=0.9,
                planned_importance=0.55,
                planned_latest_source_time=150,
                contributing_candidate_indices=[0],
                contributing_evidence_ids=["ev-1"],
            ),
        ],
    )
    graph_input = _graph_input(user_id)
    graph_input.reconciliation = reconciliation
    service = _graph_write_service(neo4j_driver)
    from pymongo import AsyncMongoClient

    result = await service.write(
        graph_input,
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    async with neo4j_driver.session() as session:
        old_record = await (
            await session.run(
                "MATCH (m:Memory {memory_id: 'mem-old-1'}) RETURN m.status AS status",
            )
        ).single()
        assert old_record is not None
        assert old_record["status"] == "conflicted"
        new_record = await (
            await session.run(
                "MATCH (m:Memory {memory_id: 'mem-new-conf'}) RETURN m.status AS status",
            )
        ).single()
        assert new_record is not None
        assert new_record["status"] == "conflicted"
        rel = await (
            await session.run(
                """
                MATCH (new:Memory {memory_id: 'mem-new-conf'})-[:CONFLICTS_WITH]->
                      (old:Memory {memory_id: 'mem-old-1'})
                RETURN count(*) AS count
                """,
            )
        ).single()
        assert rel is not None
        assert int(rel["count"]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_evidence_replay_idempotency(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-i4"
    service = _graph_write_service(neo4j_driver)
    from pymongo import AsyncMongoClient

    mongodb = AsyncMongoClient("mongodb://localhost:27017/memory_system")
    graph_input = _graph_input(user_id)
    first = await service.write(graph_input, mongodb=mongodb)
    assert first.success is not None
    before_evidence = await _count_nodes(neo4j_driver, "Evidence")
    second = await service.write(graph_input, mongodb=mongodb)
    assert second.success is not None
    assert second.success.skipped_graph_write is True
    assert await _count_nodes(neo4j_driver, "Evidence") == before_evidence


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_transaction_rollback_on_failure(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-i5"
    before = await _count_nodes(neo4j_driver, "Memory")

    class _FailRepository(GraphWriteRepository):
        async def write(self, plan: Any) -> None:
            async def _write(tx: Any) -> None:
                await tx.run("CREATE (m:Memory {memory_id: 'partial'})")
                raise RuntimeError("injected failure")

            async with self._driver.session() as session:
                await session.execute_write(_write)

    service = GraphWriteService(
        EvidenceLookupRepository(neo4j_driver),
        _FailRepository(neo4j_driver),
        tokenize_client=FakeTokenizeClient(token_count=10),
        settings=get_settings(),
        archive_timestamp_repository=_FakeArchiveTimestampRepository(),
        server_time_provider=lambda: FIXED_NOW,
    )
    from pymongo import AsyncMongoClient

    result = await service.write(
        _graph_input(user_id),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.FAILURE
    assert await _count_nodes(neo4j_driver, "Memory") == before


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_cross_user_isolation(neo4j_driver: AsyncDriver) -> None:
    user_b = "user-b"
    async with neo4j_driver.session() as session:
        await session.run(
            """
            CREATE (m:Memory {
              memory_id: 'mem-b-only',
              user_id: $user_id,
              memory_type: 'fact',
              content: 'secret',
              subject_entity_id: $subject,
              predicate: 'likes',
              object_entity_id: null,
              object_value: 'tea',
              status: 'active',
              confidence: 0.8,
              latest_source_time: 10,
              memory_version: 1
            })
            """,
            user_id=user_b,
            subject=f"user:{user_b}",
        )
    service = _graph_write_service(neo4j_driver)
    from pymongo import AsyncMongoClient

    result = await service.write(
        _graph_input("user-a"),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert result.outcome == GraphWriteOutcomeKind.SUCCESS
    async with neo4j_driver.session() as session:
        record = await (
            await session.run(
                "MATCH (m:Memory {memory_id: 'mem-b-only'}) RETURN m.content AS content",
            )
        ).single()
        assert record is not None
        assert record["content"] == "secret"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i7_entity_key_merge_convergence(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-i7"
    async with neo4j_driver.session() as session:
        await session.run(
            """
            CREATE (e:Entity {
              entity_id: 'existing-entity-id',
              user_id: $user_id,
              entity_key: 'entity-key-1',
              entity_type: 'project',
              canonical_name: 'Agent Memory System',
              normalized_name: 'agent memory system',
              aliases: [],
              created_time: $now,
              updated_time: $now
            })
            """,
            user_id=user_id,
            now=FIXED_NOW,
        )
    service = _graph_write_service(neo4j_driver)
    from pymongo import AsyncMongoClient

    await service.write(
        _graph_input(user_id),
        mongodb=AsyncMongoClient("mongodb://localhost:27017/memory_system"),
    )
    assert await _count_nodes(neo4j_driver, "Entity") == 2
    async with neo4j_driver.session() as session:
        entity_record = await (
            await session.run(
                """
                MATCH (e:Entity {entity_key: 'entity-key-1'})
                RETURN e.entity_id AS entity_id
                """,
            )
        ).single()
        assert entity_record is not None
        assert entity_record["entity_id"] == "existing-entity-id"

        memory_record = await (
            await session.run(
                """
                MATCH (m:Memory {memory_id: 'mem-new-1'})
                RETURN m.object_entity_id AS object_entity_id
                """,
            )
        ).single()
        assert memory_record is not None
        assert memory_record["object_entity_id"] == "existing-entity-id"

        object_rel = await (
            await session.run(
                """
                MATCH (m:Memory {memory_id: 'mem-new-1'})-[:OBJECT]->(e:Entity)
                RETURN e.entity_id AS entity_id, e.entity_key AS entity_key
                """,
            )
        ).single()
        assert object_rel is not None
        assert object_rel["entity_id"] == "existing-entity-id"
        assert object_rel["entity_key"] == "entity-key-1"

        subject_rel = await (
            await session.run(
                """
                MATCH (m:Memory {memory_id: 'mem-new-1'})-[:SUBJECT]->(e:Entity)
                RETURN e.entity_id AS entity_id
                """,
            )
        ).single()
        assert subject_rel is not None
        assert subject_rel["entity_id"] == f"user:{user_id}"
