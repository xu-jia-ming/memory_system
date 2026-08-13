"""CON-005 Neo4j seed helpers and consolidation readback utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import AsyncDriver

from memory_system.domain.models.consolidation_importance import (
    ConsolidationImportanceInput,
    ConsolidationImportanceSuccess,
)
from memory_system.domain.services.consolidation_importance import compute_consolidation_importance
from memory_system.settings import Settings, get_settings

CON005_USER_A = "user_con005_a"
CON005_USER_B = "user_con005_b"
CON005_EVALUATION_TIME = 1_700_100_000
CON005_EVALUATION_TIME_T2 = 1_700_200_000

DEFAULT_CREATED_TIME = 1_700_000_000
DEFAULT_LATEST_SOURCE_TIME = 1_699_500_000
DEFAULT_CONFIDENCE = 0.85
DEFAULT_IMPORTANCE = 0.25
DEFAULT_MEMORY_VERSION = 1


@dataclass(frozen=True, slots=True)
class MemorySeedParams:
    memory_id: str
    user_id: str
    memory_type: str = "fact"
    status: str = "active"
    content: str = "con005 seed content"
    confidence: float = DEFAULT_CONFIDENCE
    importance: float = DEFAULT_IMPORTANCE
    created_time: int = DEFAULT_CREATED_TIME
    latest_source_time: int = DEFAULT_LATEST_SOURCE_TIME
    memory_version: int = DEFAULT_MEMORY_VERSION
    last_consolidated_time: int | None = None
    updated_time: int = DEFAULT_CREATED_TIME


@dataclass(frozen=True, slots=True)
class MemoryConsolidationState:
    memory_id: str
    user_id: str
    importance: float
    last_consolidated_time: int | None
    memory_version: int
    content: str
    status: str
    memory_type: str
    confidence: float
    created_time: int
    latest_source_time: int | None
    updated_time: int
    retrieval_count: int


async def _create_memory(driver: AsyncDriver, params: MemorySeedParams) -> None:
    async with driver.session() as session:
        await session.run(
            """
            CREATE (m:Memory {
              memory_id: $memory_id,
              user_id: $user_id,
              memory_type: $memory_type,
              content: $content,
              subject_entity_id: $subject_entity_id,
              predicate: 'works_on',
              object_entity_id: null,
              object_value: 'con005-object',
              status: $status,
              event_status: null,
              start_time: null,
              end_time: null,
              original_time_text: null,
              confidence: $confidence,
              importance: $importance,
              latest_source_time: $latest_source_time,
              retrieval_count: 0,
              last_retrieved_time: null,
              updated_time: $updated_time,
              abstraction_level: 0,
              memory_version: $memory_version,
              created_time: $created_time,
              first_seen_time: $created_time,
              last_seen_time: $created_time,
              last_consolidated_time: $last_consolidated_time
            })
            """,
            memory_id=params.memory_id,
            user_id=params.user_id,
            memory_type=params.memory_type,
            content=params.content,
            subject_entity_id=f"user:{params.user_id}",
            status=params.status,
            confidence=params.confidence,
            importance=params.importance,
            latest_source_time=params.latest_source_time,
            updated_time=params.updated_time,
            memory_version=params.memory_version,
            created_time=params.created_time,
            last_consolidated_time=params.last_consolidated_time,
        )


async def _create_evidence(
    driver: AsyncDriver,
    *,
    evidence_id: str,
    user_id: str,
    memory_id: str,
    archive_id: str,
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            CREATE (ev:Evidence {
              evidence_id: $evidence_id,
              user_id: $user_id,
              archive_id: $archive_id
            })-[:SUPPORTS]->(m)
            """,
            evidence_id=evidence_id,
            user_id=user_id,
            memory_id=memory_id,
            archive_id=archive_id,
        )


async def seed_memory_with_evidence(
    driver: AsyncDriver,
    *,
    memory_id: str,
    user_id: str,
    archive_ids: list[str],
    params: MemorySeedParams | None = None,
) -> MemorySeedParams:
    """Seed one Memory node and Evidence rows with DISTINCT archive_id values."""
    seed = params or MemorySeedParams(memory_id=memory_id, user_id=user_id)
    if seed.memory_id != memory_id or seed.user_id != user_id:
        raise ValueError("params.memory_id and params.user_id must match arguments")
    await _create_memory(driver, seed)
    for index, archive_id in enumerate(archive_ids):
        await _create_evidence(
            driver,
            evidence_id=f"ev-{memory_id}-{index}",
            user_id=user_id,
            memory_id=memory_id,
            archive_id=archive_id,
        )
    return seed


async def seed_memory_no_evidence(
    driver: AsyncDriver,
    *,
    memory_id: str,
    user_id: str,
    params: MemorySeedParams | None = None,
) -> MemorySeedParams:
    """Seed Memory without qualifying Evidence (independent_archive_count=0)."""
    seed = params or MemorySeedParams(memory_id=memory_id, user_id=user_id)
    if seed.memory_id != memory_id or seed.user_id != user_id:
        raise ValueError("params.memory_id and params.user_id must match arguments")
    await _create_memory(driver, seed)
    return seed


async def read_memory_consolidation_state(
    driver: AsyncDriver,
    user_id: str,
    memory_id: str,
) -> MemoryConsolidationState:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            RETURN m
            """,
            memory_id=memory_id,
            user_id=user_id,
        )
        record = await result.single()
        if record is None:
            raise AssertionError(f"memory not found: {user_id}/{memory_id}")
        node = record["m"]
        props: dict[str, Any]
        if hasattr(node, "items"):
            props = dict(node.items())
        else:
            props = dict(node)

        return MemoryConsolidationState(
            memory_id=str(props["memory_id"]),
            user_id=str(props["user_id"]),
            importance=float(props["importance"]),
            last_consolidated_time=props.get("last_consolidated_time"),
            memory_version=int(props["memory_version"]),
            content=str(props["content"]),
            status=str(props["status"]),
            memory_type=str(props["memory_type"]),
            confidence=float(props["confidence"]),
            created_time=int(props["created_time"]),
            latest_source_time=props.get("latest_source_time"),
            updated_time=int(props["updated_time"]),
            retrieval_count=int(props.get("retrieval_count", 0)),
        )


def expected_importance_for_seed(
    seed: MemorySeedParams,
    *,
    evaluation_time: int,
    independent_archive_count: int,
    settings: Settings | None = None,
) -> float:
    """Compute CON-001 expected importance for seeded Memory fields."""
    active_settings = settings or get_settings()
    outcome = compute_consolidation_importance(
        ConsolidationImportanceInput(
            memory_type=seed.memory_type,  # type: ignore[arg-type]
            confidence=seed.confidence,
            status=seed.status,  # type: ignore[arg-type]
            created_time=seed.created_time,
            latest_source_time=seed.latest_source_time,
            independent_archive_count=independent_archive_count,
            evaluation_time=evaluation_time,
        ),
        active_settings.memory_consolidation,
    )
    if not isinstance(outcome, ConsolidationImportanceSuccess):
        raise AssertionError(f"expected scored outcome, got {outcome!r}")
    return outcome.new_importance


async def cleanup_con005_users(driver: AsyncDriver, user_ids: list[str]) -> None:
    async with driver.session() as session:
        await session.run(
            """
            MATCH (n)
            WHERE n.user_id IN $user_ids
            DETACH DELETE n
            """,
            user_ids=user_ids,
        )
