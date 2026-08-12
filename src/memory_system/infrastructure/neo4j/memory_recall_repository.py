"""Read-only Neo4j repository for EXT-005 Memory recall (Q-M1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction

from memory_system.domain.models.memory_recall import MemoryNodeSnapshot

Q_M1_RECALL_CYPHER = """
MATCH (m:Memory)
WHERE m.user_id = $user_id
  AND m.memory_type = $memory_type
  AND m.subject_entity_id = $subject_entity_id
  AND m.predicate = $predicate
  AND m.status IN ['active', 'conflicted']
RETURN m.memory_id AS memory_id,
       m.user_id AS user_id,
       m.memory_type AS memory_type,
       m.content AS content,
       m.subject_entity_id AS subject_entity_id,
       m.predicate AS predicate,
       m.object_entity_id AS object_entity_id,
       m.object_value AS object_value,
       m.status AS status,
       m.event_status AS event_status,
       m.start_time AS start_time,
       m.end_time AS end_time,
       m.original_time_text AS original_time_text,
       m.confidence AS confidence,
       m.latest_source_time AS latest_source_time
ORDER BY CASE m.status
           WHEN 'active' THEN 0
           WHEN 'conflicted' THEN 1
           ELSE 2
         END ASC,
         coalesce(m.latest_source_time, 0) DESC,
         m.memory_id ASC
LIMIT 20
""".strip()

Q_M1_BATCH_RECALL_CYPHER = """
WITH $user_id AS user_id
UNWIND $recall_keys AS k
CALL (k, user_id) {
  WITH k, user_id
  MATCH (m:Memory)
  WHERE m.user_id = user_id
    AND m.memory_type = k.memory_type
    AND m.subject_entity_id = k.subject_entity_id
    AND m.predicate = k.predicate
    AND m.status IN ['active', 'conflicted']
  RETURN m
  ORDER BY CASE m.status
             WHEN 'active' THEN 0
             WHEN 'conflicted' THEN 1
             ELSE 2
           END ASC,
           coalesce(m.latest_source_time, 0) DESC,
           m.memory_id ASC
  LIMIT 20
}
RETURN k.candidate_index AS candidate_index,
       m.memory_id AS memory_id,
       m.user_id AS user_id,
       m.memory_type AS memory_type,
       m.content AS content,
       m.subject_entity_id AS subject_entity_id,
       m.predicate AS predicate,
       m.object_entity_id AS object_entity_id,
       m.object_value AS object_value,
       m.status AS status,
       m.event_status AS event_status,
       m.start_time AS start_time,
       m.end_time AS end_time,
       m.original_time_text AS original_time_text,
       m.confidence AS confidence,
       m.latest_source_time AS latest_source_time
ORDER BY candidate_index ASC,
         CASE m.status
           WHEN 'active' THEN 0
           WHEN 'conflicted' THEN 1
           ELSE 2
         END ASC,
         coalesce(m.latest_source_time, 0) DESC,
         m.memory_id ASC
""".strip()


class MemoryGraphDataError(Exception):
    """Raised when a Memory node cannot be mapped to the authorized snapshot."""


@dataclass(frozen=True, slots=True)
class MemoryRecallKey:
    candidate_index: int
    memory_type: str
    subject_entity_id: str
    predicate: str


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise MemoryGraphDataError(f"memory property {field} must be a string")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MemoryGraphDataError("memory optional string property must be string or null")
    return value


def _require_float(value: object, field: str) -> float:
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    raise MemoryGraphDataError(f"memory property {field} must be numeric")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise MemoryGraphDataError("memory property latest_source_time must be int or null")


def snapshot_from_record(record: Any) -> MemoryNodeSnapshot:
    data = record.data() if hasattr(record, "data") else dict(record)
    required = (
        "memory_id",
        "user_id",
        "memory_type",
        "content",
        "subject_entity_id",
        "predicate",
        "status",
        "confidence",
    )
    for field in required:
        if field not in data:
            raise MemoryGraphDataError(f"missing memory property {field}")
    return MemoryNodeSnapshot(
        memory_id=_require_str(data["memory_id"], "memory_id"),
        user_id=_require_str(data["user_id"], "user_id"),
        memory_type=_require_str(data["memory_type"], "memory_type"),
        content=_require_str(data["content"], "content"),
        subject_entity_id=_require_str(data["subject_entity_id"], "subject_entity_id"),
        predicate=_require_str(data["predicate"], "predicate"),
        object_entity_id=_optional_str(data.get("object_entity_id")),
        object_value=_optional_str(data.get("object_value")),
        status=_require_str(data["status"], "status"),
        event_status=_optional_str(data.get("event_status")),
        start_time=_optional_str(data.get("start_time")),
        end_time=_optional_str(data.get("end_time")),
        original_time_text=_optional_str(data.get("original_time_text")),
        confidence=_require_float(data["confidence"], "confidence"),
        latest_source_time=_optional_int(data.get("latest_source_time")),
    )


class MemoryRecallRepository:
    """Batch read-only Memory recall scoped to a single user_id."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def recall_memories_batch(
        self,
        user_id: str,
        recall_keys: list[MemoryRecallKey],
    ) -> dict[int, list[MemoryNodeSnapshot]]:
        if not recall_keys:
            return {}

        payload = [
            {
                "candidate_index": key.candidate_index,
                "memory_type": key.memory_type,
                "subject_entity_id": key.subject_entity_id,
                "predicate": key.predicate,
            }
            for key in recall_keys
        ]

        async def _read(tx: AsyncManagedTransaction) -> dict[int, list[MemoryNodeSnapshot]]:
            result = await tx.run(
                Q_M1_BATCH_RECALL_CYPHER,
                recall_keys=payload,
                user_id=user_id,
            )
            grouped: dict[int, list[MemoryNodeSnapshot]] = {}
            async for record in result:
                data = record.data()
                candidate_index = data.get("candidate_index")
                if not isinstance(candidate_index, int):
                    raise MemoryGraphDataError("missing candidate_index in recall batch row")
                snapshot = snapshot_from_record(record)
                grouped.setdefault(candidate_index, []).append(snapshot)
            return grouped

        async with self._driver.session() as session:
            return await session.execute_read(_read)
