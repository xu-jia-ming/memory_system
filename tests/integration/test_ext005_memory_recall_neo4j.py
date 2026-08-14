"""Integration tests for EXT-005 Memory recall against real Neo4j."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from neo4j import AsyncDriver

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
from memory_system.domain.models.reconciliation import (
    ReconciliationAction,
    ReconciliationErrorCode,
    ReconciliationInput,
    ReconciliationOutcomeKind,
)
from memory_system.domain.services.evidence_identity import compute_evidence_id
from memory_system.domain.services.reconciliation_service import ReconciliationService
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.neo4j.evidence_lookup_repository import EvidenceLookupRepository
from memory_system.infrastructure.neo4j.memory_recall_repository import (
    MemoryRecallKey,
    MemoryRecallRepository,
)
from memory_system.settings import get_settings

pytest_plugins = ("tests.integration.support.neo4j_fixtures",)


@pytest.fixture(autouse=True)
async def _clean_graph(neo4j_driver: AsyncDriver) -> AsyncIterator[None]:
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")


async def _count_nodes(driver: AsyncDriver, label: str) -> int:
    async with driver.session() as session:
        result = await session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
        record = await result.single()
        assert record is not None
        return int(record["count"])


async def _create_memory(
    driver: AsyncDriver,
    *,
    memory_id: str,
    user_id: str,
    status: str,
    latest_source_time: int,
    predicate: str = "likes",
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            CREATE (m:Memory {
              memory_id: $memory_id,
              user_id: $user_id,
              memory_type: 'fact',
              content: $content,
              subject_entity_id: $subject_entity_id,
              predicate: $predicate,
              object_entity_id: null,
              object_value: 'tea',
              status: $status,
              event_status: null,
              start_time: null,
              end_time: null,
              original_time_text: null,
              confidence: 0.8,
              latest_source_time: $latest_source_time
            })
            """,
            memory_id=memory_id,
            user_id=user_id,
            content=f"content-{memory_id}",
            subject_entity_id=f"user:{user_id}",
            predicate=predicate,
            status=status,
            latest_source_time=latest_source_time,
        )


async def _create_evidence_supports(
    driver: AsyncDriver,
    *,
    evidence_id: str,
    user_id: str,
    memory_id: str,
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id})
            CREATE (ev:Evidence {
              evidence_id: $evidence_id,
              user_id: $user_id
            })-[:SUPPORTS]->(m)
            """,
            evidence_id=evidence_id,
            user_id=user_id,
            memory_id=memory_id,
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
                entity_key="user-key",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=[],
                    planned_aliases=[],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=False,
            )
        ],
    )


def _reconciliation_input(user_id: str, fingerprint: str = "fp-1") -> ReconciliationInput:
    return ReconciliationInput(
        task_id="task-1",
        archive_id="archive-1",
        user_id=user_id,
        session_id=None,
        extraction_result=ExtractionValidatedResult(
            entities=[
                ExtractionEntityCandidate(
                    local_entity_id="user",
                    name="current_user",
                    type="person",
                    aliases=[],
                )
            ],
            memories=[
                ExtractionMemoryCandidate(
                    memory_type="fact",
                    content="candidate content",
                    subject_entity_id="user",
                    predicate="likes",
                    object_entity_id=None,
                    object_value="tea",
                    event_status=None,
                    start_time=None,
                    end_time=None,
                    original_time_text=None,
                    confidence=0.9,
                    source_message_ids=["msg_1"],
                    candidate_source_time=300,
                    candidate_fingerprint=fingerprint,
                )
            ],
        ),
        entity_alignment=_alignment(user_id),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_recall_ordering(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-a"
    await _create_memory(
        neo4j_driver,
        memory_id="conflicted",
        user_id=user_id,
        status="conflicted",
        latest_source_time=500,
    )
    await _create_memory(
        neo4j_driver,
        memory_id="active-newer",
        user_id=user_id,
        status="active",
        latest_source_time=400,
    )
    await _create_memory(
        neo4j_driver,
        memory_id="active-older",
        user_id=user_id,
        status="active",
        latest_source_time=100,
    )
    repo = MemoryRecallRepository(neo4j_driver)
    recalls = await repo.recall_memories_batch(
        user_id,
        [
            MemoryRecallKey(
                candidate_index=0,
                memory_type="fact",
                subject_entity_id=f"user:{user_id}",
                predicate="likes",
            )
        ],
    )
    ids = [item.memory_id for item in recalls[0]]
    assert ids.index("active-newer") < ids.index("active-older")
    assert ids.index("active-newer") < ids.index("conflicted")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_limit_twenty(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-limit"
    for index in range(25):
        await _create_memory(
            neo4j_driver,
            memory_id=f"mem-{index:02d}",
            user_id=user_id,
            status="active",
            latest_source_time=index,
        )
    repo = MemoryRecallRepository(neo4j_driver)
    recalls = await repo.recall_memories_batch(
        user_id,
        [
            MemoryRecallKey(
                candidate_index=0,
                memory_type="fact",
                subject_entity_id=f"user:{user_id}",
                predicate="likes",
            )
        ],
    )
    assert len(recalls[0]) == 20


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_cross_user_isolation(neo4j_driver: AsyncDriver) -> None:
    await _create_memory(
        neo4j_driver,
        memory_id="user-b-memory",
        user_id="user-b",
        status="active",
        latest_source_time=10,
    )
    repo = MemoryRecallRepository(neo4j_driver)
    recalls = await repo.recall_memories_batch(
        "user-a",
        [
            MemoryRecallKey(
                candidate_index=0,
                memory_type="fact",
                subject_entity_id="user:user-a",
                predicate="likes",
            )
        ],
    )
    assert recalls.get(0, []) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_evidence_exists_skip(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-evidence"
    await _create_memory(
        neo4j_driver,
        memory_id="mem-evidence",
        user_id=user_id,
        status="active",
        latest_source_time=10,
    )
    evidence_id = compute_evidence_id("archive-1", "fp-evidence")
    await _create_evidence_supports(
        neo4j_driver,
        evidence_id=evidence_id,
        user_id=user_id,
        memory_id="mem-evidence",
    )
    service = ReconciliationService(
        EvidenceLookupRepository(neo4j_driver),
        MemoryRecallRepository(neo4j_driver),
        llm_client=FakeLlmClient(),
        settings=get_settings(),
    )
    result = await service.reconcile(_reconciliation_input(user_id, fingerprint="fp-evidence"))
    assert result.success is not None
    assert result.success.per_candidate_decisions[0].action == ReconciliationAction.SKIP
    assert result.success.per_candidate_decisions[0].skip_reason == "evidence_already_processed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_zero_writes(neo4j_driver: AsyncDriver) -> None:
    user_id = "user-zero-write"
    await _create_memory(
        neo4j_driver,
        memory_id="mem-1",
        user_id=user_id,
        status="active",
        latest_source_time=10,
    )
    before_memory = await _count_nodes(neo4j_driver, "Memory")
    before_evidence = await _count_nodes(neo4j_driver, "Evidence")
    service = ReconciliationService(
        EvidenceLookupRepository(neo4j_driver),
        MemoryRecallRepository(neo4j_driver),
        llm_client=FakeLlmClient(),
        settings=get_settings(),
    )
    await service.reconcile(_reconciliation_input(user_id))
    assert await _count_nodes(neo4j_driver, "Memory") == before_memory
    assert await _count_nodes(neo4j_driver, "Evidence") == before_evidence


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_query_failure_maps_graph_query_failed(neo4j_driver: AsyncDriver) -> None:
    class _BrokenRecallRepository:
        async def recall_memories_batch(
            self, user_id: str, recall_keys: list[MemoryRecallKey]
        ) -> dict[int, list[Any]]:
            raise RuntimeError("injected failure")

    service = ReconciliationService(
        EvidenceLookupRepository(neo4j_driver),
        _BrokenRecallRepository(),  # type: ignore[arg-type]
        llm_client=FakeLlmClient(),
        settings=get_settings(),
    )
    result = await service.reconcile(_reconciliation_input("user-fail"))
    assert result.outcome == ReconciliationOutcomeKind.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == ReconciliationErrorCode.GRAPH_QUERY_FAILED
