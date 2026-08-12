"""Read-only Neo4j repository for EXT-004 entity alignment (Q1/Q2/Q3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction

from memory_system.domain.models.entity_alignment import EntityNodeSnapshot

Q1_USER_ENTITY_CYPHER = """
MATCH (e:Entity {entity_id: $user_entity_id})
WHERE e.user_id = $user_id
RETURN e.entity_id AS entity_id,
       e.entity_key AS entity_key,
       e.user_id AS user_id,
       e.entity_type AS entity_type,
       e.canonical_name AS canonical_name,
       e.normalized_name AS normalized_name,
       e.aliases AS aliases
""".strip()

Q2_ENTITY_KEY_BATCH_CYPHER = """
UNWIND $entity_keys AS k
MATCH (e:Entity {entity_key: k})
WHERE e.user_id = $user_id
RETURN e.entity_id AS entity_id,
       e.entity_key AS entity_key,
       e.user_id AS user_id,
       e.entity_type AS entity_type,
       e.canonical_name AS canonical_name,
       e.normalized_name AS normalized_name,
       e.aliases AS aliases
""".strip()

Q3_SECONDARY_MATCH_CYPHER = """
UNWIND $candidates AS c
MATCH (e:Entity)
WHERE e.user_id = $user_id
  AND e.entity_type = c.entity_type
RETURN c.local_entity_id AS local_entity_id,
       e.entity_id AS entity_id,
       e.entity_key AS entity_key,
       e.user_id AS user_id,
       e.entity_type AS entity_type,
       e.canonical_name AS canonical_name,
       e.normalized_name AS normalized_name,
       e.aliases AS aliases
ORDER BY c.local_entity_id ASC, e.entity_id ASC
""".strip()


class EntityGraphDataError(Exception):
    """Raised when an Entity node cannot be mapped to the authorized snapshot."""


@dataclass(frozen=True, slots=True)
class SecondaryMatchCandidate:
    local_entity_id: str
    entity_type: str
    normalized_name: str


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise EntityGraphDataError(f"entity property {field} must be a string")
    return value


def _require_aliases(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EntityGraphDataError("entity property aliases must be a list of strings")
    aliases: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise EntityGraphDataError("entity property aliases must be a list of strings")
        aliases.append(item)
    return aliases


def snapshot_from_record(record: Any) -> EntityNodeSnapshot:
    """Map a Neo4j record row to a strict EntityNodeSnapshot."""
    data = record.data() if hasattr(record, "data") else dict(record)
    required = (
        "entity_id",
        "entity_key",
        "user_id",
        "entity_type",
        "canonical_name",
        "normalized_name",
    )
    for field in required:
        if field not in data:
            raise EntityGraphDataError(f"missing entity property {field}")
    return EntityNodeSnapshot(
        entity_id=_require_str(data["entity_id"], "entity_id"),
        entity_key=_require_str(data["entity_key"], "entity_key"),
        user_id=_require_str(data["user_id"], "user_id"),
        entity_type=_require_str(data["entity_type"], "entity_type"),
        canonical_name=_require_str(data["canonical_name"], "canonical_name"),
        normalized_name=_require_str(data["normalized_name"], "normalized_name"),
        aliases=_require_aliases(data.get("aliases")),
    )


class EntityAlignmentRepository:
    """Batch read-only Entity lookups scoped to a single user_id."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def find_user_entity(
        self, user_id: str, *, user_entity_id: str
    ) -> EntityNodeSnapshot | None:
        async def _read(tx: AsyncManagedTransaction) -> EntityNodeSnapshot | None:
            result = await tx.run(
                Q1_USER_ENTITY_CYPHER,
                user_entity_id=user_entity_id,
                user_id=user_id,
            )
            record = await result.single()
            if record is None:
                return None
            return snapshot_from_record(record)

        async with self._driver.session() as session:
            return await session.execute_read(_read)

    async def find_by_entity_keys(
        self,
        user_id: str,
        entity_keys: list[str],
    ) -> dict[str, EntityNodeSnapshot]:
        if not entity_keys:
            return {}

        async def _read(tx: AsyncManagedTransaction) -> dict[str, EntityNodeSnapshot]:
            result = await tx.run(
                Q2_ENTITY_KEY_BATCH_CYPHER,
                entity_keys=entity_keys,
                user_id=user_id,
            )
            hits: dict[str, EntityNodeSnapshot] = {}
            async for record in result:
                snapshot = snapshot_from_record(record)
                hits[snapshot.entity_key] = snapshot
            return hits

        async with self._driver.session() as session:
            return await session.execute_read(_read)

    async def find_secondary_match_candidates(
        self,
        user_id: str,
        candidates: list[SecondaryMatchCandidate],
    ) -> dict[str, list[EntityNodeSnapshot]]:
        if not candidates:
            return {}

        payload = [
            {
                "local_entity_id": candidate.local_entity_id,
                "entity_type": candidate.entity_type,
                "normalized_name": candidate.normalized_name,
            }
            for candidate in candidates
        ]

        async def _read(tx: AsyncManagedTransaction) -> dict[str, list[EntityNodeSnapshot]]:
            result = await tx.run(
                Q3_SECONDARY_MATCH_CYPHER,
                candidates=payload,
                user_id=user_id,
            )
            grouped: dict[str, list[EntityNodeSnapshot]] = {}
            async for record in result:
                data = record.data()
                local_entity_id = _require_str(data["local_entity_id"], "local_entity_id")
                snapshot = snapshot_from_record(record)
                grouped.setdefault(local_entity_id, []).append(snapshot)
            return grouped

        async with self._driver.session() as session:
            return await session.execute_read(_read)
