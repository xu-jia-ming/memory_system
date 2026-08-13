"""Read-only Neo4j repository for RET-003 authoritative memory load and one-hop expansion."""

from __future__ import annotations

import asyncio
from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from memory_system.domain.models.retrieval_memory_snapshot import (
    RetrievalEntitySnapshot,
    RetrievalMemorySnapshot,
)
from memory_system.domain.services.graph_expansion_ranker import ExpansionEdge

Q_LOAD_RETRIEVAL_MEMORIES = """
UNWIND $memory_ids AS memory_id
MATCH (m:Memory {memory_id: memory_id})
WHERE m.user_id = $user_id
OPTIONAL MATCH (m)-[:SUBJECT]->(sub:Entity)
WHERE sub.user_id = $user_id
OPTIONAL MATCH (m)-[:OBJECT]->(obj:Entity)
WHERE obj.user_id = $user_id
RETURN m.memory_id AS memory_id,
       m.user_id AS user_id,
       m.memory_type AS memory_type,
       m.status AS status,
       m.content AS content,
       m.subject_entity_id AS subject_entity_id,
       m.predicate AS predicate,
       m.object_entity_id AS object_entity_id,
       m.object_value AS object_value,
       m.event_status AS event_status,
       m.start_time AS start_time,
       m.end_time AS end_time,
       m.original_time_text AS original_time_text,
       m.importance AS importance,
       m.confidence AS confidence,
       m.retrieval_count AS retrieval_count,
       m.last_retrieved_time AS last_retrieved_time,
       m.latest_source_time AS latest_source_time,
       m.updated_time AS updated_time,
       sub.entity_id AS subject_entity_node_id,
       sub.canonical_name AS subject_canonical_name,
       sub.aliases AS subject_aliases,
       sub.entity_type AS subject_entity_type,
       sub.normalized_name AS subject_normalized_name,
       obj.entity_id AS object_entity_node_id,
       obj.canonical_name AS object_canonical_name,
       obj.aliases AS object_aliases,
       obj.entity_type AS object_entity_type,
       obj.normalized_name AS object_normalized_name
""".strip()

Q_ONE_HOP_EXPANSION_PATH_B = """
UNWIND $seed_ids AS seed_id
MATCH (seed:Memory {memory_id: seed_id})
WHERE seed.user_id = $user_id
MATCH (seed)-[:SUPERSEDES|CONFLICTS_WITH]-(related:Memory)
WHERE related.user_id = $user_id
  AND related.memory_id <> seed.memory_id
RETURN seed.memory_id AS seed_id,
       related.memory_id AS related_id,
       0 AS expansion_tier,
       related.importance AS importance,
       related.latest_source_time AS latest_source_time,
       related.memory_type AS memory_type,
       related.status AS status
""".strip()

Q_ONE_HOP_EXPANSION_PATH_A = """
UNWIND $seed_ids AS seed_id
MATCH (seed:Memory {memory_id: seed_id})
WHERE seed.user_id = $user_id
MATCH (seed)-[:SUBJECT|OBJECT]->(entity:Entity)<-[:SUBJECT|OBJECT]-(related:Memory)
WHERE entity.user_id = $user_id
  AND related.user_id = $user_id
  AND related.memory_id <> seed.memory_id
  AND entity.entity_id <> 'user:' + $user_id
WITH seed,
     related,
     entity,
     CASE
       WHEN EXISTS { MATCH (seed)-[:OBJECT]->(entity) }
         OR EXISTS { MATCH (related)-[:OBJECT]->(entity) }
       THEN 1
       ELSE 2
     END AS expansion_tier
RETURN seed.memory_id AS seed_id,
       related.memory_id AS related_id,
       expansion_tier,
       related.importance AS importance,
       related.latest_source_time AS latest_source_time,
       related.memory_type AS memory_type,
       related.status AS status
""".strip()


class RetrievalMemoryGraphDataError(Exception):
    """Raised when Neo4j data cannot be mapped to authorized retrieval snapshots."""


class RetrievalMemoryReadError(Exception):
    """Raised when Neo4j retrieval read transport fails."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def authorized_read_cypher_queries() -> tuple[str, ...]:
    return (
        Q_LOAD_RETRIEVAL_MEMORIES,
        Q_ONE_HOP_EXPANSION_PATH_A,
        Q_ONE_HOP_EXPANSION_PATH_B,
    )


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise RetrievalMemoryGraphDataError(f"memory property {field} must be a string")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RetrievalMemoryGraphDataError("optional string property must be string or null")
    return value


def _require_float(value: object, field: str) -> float:
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    raise RetrievalMemoryGraphDataError(f"memory property {field} must be numeric")


def _require_int(value: object, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise RetrievalMemoryGraphDataError(f"memory property {field} must be an int")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise RetrievalMemoryGraphDataError("optional int property must be int or null")


def _optional_entity(data: dict[str, Any], prefix: str) -> RetrievalEntitySnapshot | None:
    entity_id = data.get(f"{prefix}_entity_node_id")
    if entity_id is None:
        return None
    return RetrievalEntitySnapshot(
        entity_id=_require_str(entity_id, f"{prefix}.entity_id"),
        canonical_name=_require_str(
            data.get(f"{prefix}_canonical_name"),
            f"{prefix}.canonical_name",
        ),
        aliases=_require_aliases(data.get(f"{prefix}_aliases")),
        entity_type=_require_str(data.get(f"{prefix}_entity_type"), f"{prefix}.entity_type"),
        normalized_name=_require_str(
            data.get(f"{prefix}_normalized_name"),
            f"{prefix}.normalized_name",
        ),
    )


def _require_aliases(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RetrievalMemoryGraphDataError("entity aliases must be a list")
    aliases: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise RetrievalMemoryGraphDataError("entity alias must be a string")
        aliases.append(item)
    return aliases


def snapshot_from_record(record: Any) -> RetrievalMemorySnapshot:
    data = record.data() if hasattr(record, "data") else dict(record)
    required = (
        "memory_id",
        "user_id",
        "memory_type",
        "status",
        "content",
        "subject_entity_id",
        "predicate",
        "importance",
        "confidence",
        "retrieval_count",
        "updated_time",
    )
    for field in required:
        if field not in data:
            raise RetrievalMemoryGraphDataError(f"missing memory property {field}")

    return RetrievalMemorySnapshot(
        memory_id=_require_str(data["memory_id"], "memory_id"),
        user_id=_require_str(data["user_id"], "user_id"),
        memory_type=_require_str(data["memory_type"], "memory_type"),
        status=_require_str(data["status"], "status"),
        content=_require_str(data["content"], "content"),
        subject_entity_id=_require_str(data["subject_entity_id"], "subject_entity_id"),
        predicate=_require_str(data["predicate"], "predicate"),
        object_entity_id=_optional_str(data.get("object_entity_id")),
        object_value=_optional_str(data.get("object_value")),
        event_status=_optional_str(data.get("event_status")),
        start_time=_optional_int(data.get("start_time")),
        end_time=_optional_int(data.get("end_time")),
        original_time_text=_optional_str(data.get("original_time_text")),
        importance=_require_float(data["importance"], "importance"),
        confidence=_require_float(data["confidence"], "confidence"),
        retrieval_count=_require_int(data["retrieval_count"], "retrieval_count"),
        last_retrieved_time=_optional_int(data.get("last_retrieved_time")),
        latest_source_time=_optional_int(data.get("latest_source_time")),
        updated_time=_require_int(data["updated_time"], "updated_time"),
        subject_entity=_optional_entity(data, "subject"),
        object_entity=_optional_entity(data, "object"),
    )


def expansion_edge_from_record(record: Any) -> ExpansionEdge:
    data = record.data() if hasattr(record, "data") else dict(record)
    required = (
        "seed_id",
        "related_id",
        "expansion_tier",
        "importance",
        "memory_type",
        "status",
    )
    for field in required:
        if field not in data:
            raise RetrievalMemoryGraphDataError(f"missing expansion property {field}")
    tier = data["expansion_tier"]
    if not isinstance(tier, int) or isinstance(tier, bool):
        raise RetrievalMemoryGraphDataError("expansion_tier must be an int")
    return ExpansionEdge(
        seed_id=_require_str(data["seed_id"], "seed_id"),
        related_id=_require_str(data["related_id"], "related_id"),
        expansion_tier=tier,
        importance=_require_float(data["importance"], "importance"),
        latest_source_time=_optional_int(data.get("latest_source_time")),
        memory_type=_require_str(data["memory_type"], "memory_type"),
        status=_require_str(data["status"], "status"),
    )


def _merge_expansion_edges(edges: list[ExpansionEdge]) -> list[ExpansionEdge]:
    best: dict[tuple[str, str], ExpansionEdge] = {}
    for edge in edges:
        key = (edge.seed_id, edge.related_id)
        existing = best.get(key)
        if existing is None or edge.expansion_tier < existing.expansion_tier:
            best[key] = edge
    return list(best.values())


class RetrievalMemoryReadRepository:
    """Batch read-only Memory load and one-hop graph expansion scoped to user_id."""

    def __init__(self, driver: AsyncDriver, *, neo4j_timeout_seconds: float) -> None:
        self._driver = driver
        self._neo4j_timeout_seconds = neo4j_timeout_seconds

    async def load_memories(
        self,
        user_id: str,
        memory_ids: list[str],
    ) -> dict[str, RetrievalMemorySnapshot]:
        if not memory_ids:
            return {}

        sorted_ids = sorted(memory_ids)

        async def _read(tx: AsyncManagedTransaction) -> dict[str, RetrievalMemorySnapshot]:
            result = await tx.run(
                Q_LOAD_RETRIEVAL_MEMORIES,
                memory_ids=sorted_ids,
                user_id=user_id,
            )
            loaded: dict[str, RetrievalMemorySnapshot] = {}
            async for record in result:
                try:
                    snapshot = snapshot_from_record(record)
                except RetrievalMemoryGraphDataError:
                    continue
                loaded[snapshot.memory_id] = snapshot
            return loaded

        try:
            async with self._driver.session() as session:
                return await asyncio.wait_for(
                    session.execute_read(_read),
                    timeout=self._neo4j_timeout_seconds,
                )
        except TimeoutError as exc:
            raise RetrievalMemoryReadError(
                "neo4j retrieval memory load timed out",
                retryable=True,
            ) from exc
        except (ServiceUnavailable, Neo4jError) as exc:
            raise RetrievalMemoryReadError(
                "neo4j retrieval memory load failed",
                retryable=True,
            ) from exc

    async def expand_one_hop(
        self,
        user_id: str,
        seed_ids: list[str],
    ) -> list[ExpansionEdge]:
        if not seed_ids:
            return []

        sorted_seed_ids = sorted(seed_ids)

        async def _read(tx: AsyncManagedTransaction) -> list[ExpansionEdge]:
            path_b = await tx.run(
                Q_ONE_HOP_EXPANSION_PATH_B,
                seed_ids=sorted_seed_ids,
                user_id=user_id,
            )
            path_a = await tx.run(
                Q_ONE_HOP_EXPANSION_PATH_A,
                seed_ids=sorted_seed_ids,
                user_id=user_id,
            )
            edges: list[ExpansionEdge] = []
            for result in (path_b, path_a):
                async for record in result:
                    try:
                        edges.append(expansion_edge_from_record(record))
                    except RetrievalMemoryGraphDataError:
                        continue
            return _merge_expansion_edges(edges)

        try:
            async with self._driver.session() as session:
                return await asyncio.wait_for(
                    session.execute_read(_read),
                    timeout=self._neo4j_timeout_seconds,
                )
        except TimeoutError as exc:
            raise RetrievalMemoryReadError(
                "neo4j one-hop expansion timed out",
                retryable=True,
            ) from exc
        except (ServiceUnavailable, Neo4jError) as exc:
            raise RetrievalMemoryReadError(
                "neo4j one-hop expansion failed",
                retryable=True,
            ) from exc
