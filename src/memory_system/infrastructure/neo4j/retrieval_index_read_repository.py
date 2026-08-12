"""Read-only Neo4j repository for EXT-007 retrieval index sync."""

from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction

from memory_system.domain.models.retrieval_index_sync import MemoryIndexRow

Q_RI1_RELATED_MEMORY_IDS = """
UNWIND $seed_memory_ids AS seed_id
MATCH (seed:Memory {memory_id: seed_id})
WHERE seed.user_id = $user_id
OPTIONAL MATCH (seed)-[:SUPERSEDES|CONFLICTS_WITH]-(related:Memory)
WHERE related.user_id = $user_id
RETURN DISTINCT related.memory_id AS memory_id
""".strip()

Q_RI2_ENTITY_LINKED_MEMORY_IDS = """
UNWIND $entity_ids AS entity_id
MATCH (e:Entity {entity_id: entity_id})
WHERE e.user_id = $user_id
MATCH (m:Memory)-[:SUBJECT|OBJECT]->(e)
WHERE m.user_id = $user_id
RETURN DISTINCT m.memory_id AS memory_id
""".strip()

Q_RI3_LOAD_MEMORY_INDEX_ROWS = """
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
       m.predicate AS predicate,
       m.event_status AS event_status,
       m.latest_source_time AS latest_source_time,
       m.updated_time AS updated_time,
       m.subject_entity_id AS subject_entity_id,
       m.object_entity_id AS object_entity_id,
       m.object_value AS object_value,
       sub.canonical_name AS subject_canonical_name,
       sub.aliases AS subject_aliases,
       obj.canonical_name AS object_canonical_name,
       obj.aliases AS object_aliases
""".strip()


class RetrievalIndexGraphDataError(Exception):
    """Raised when Neo4j data cannot be mapped to authorized index rows."""


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise RetrievalIndexGraphDataError(f"memory property {field} must be a string")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RetrievalIndexGraphDataError("optional string property must be string or null")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise RetrievalIndexGraphDataError("latest_source_time must be int or null")


def _require_int(value: object, field: str) -> int:
    if isinstance(value, int):
        return value
    raise RetrievalIndexGraphDataError(f"memory property {field} must be int")


def _aliases(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RetrievalIndexGraphDataError(f"{field} must be a list")
    aliases: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise RetrievalIndexGraphDataError(f"{field} entries must be strings")
        aliases.append(item)
    return aliases


def _row_from_record(record: Any) -> MemoryIndexRow:
    data = record.data() if hasattr(record, "data") else dict(record)
    required = (
        "memory_id",
        "user_id",
        "memory_type",
        "status",
        "content",
        "predicate",
        "updated_time",
        "subject_entity_id",
    )
    for field in required:
        if field not in data:
            raise RetrievalIndexGraphDataError(f"missing memory property {field}")

    return MemoryIndexRow(
        memory_id=_require_str(data["memory_id"], "memory_id"),
        user_id=_require_str(data["user_id"], "user_id"),
        memory_type=_require_str(data["memory_type"], "memory_type"),
        status=_require_str(data["status"], "status"),
        content=_require_str(data["content"], "content"),
        predicate=_require_str(data["predicate"], "predicate"),
        event_status=_optional_str(data.get("event_status")),
        latest_source_time=_optional_int(data.get("latest_source_time")),
        updated_time=_require_int(data["updated_time"], "updated_time"),
        subject_entity_id=_require_str(data["subject_entity_id"], "subject_entity_id"),
        object_entity_id=_optional_str(data.get("object_entity_id")),
        object_value=_optional_str(data.get("object_value")),
        subject_canonical_name=_optional_str(data.get("subject_canonical_name")),
        subject_aliases=_aliases(data.get("subject_aliases"), "subject_aliases"),
        object_canonical_name=_optional_str(data.get("object_canonical_name")),
        object_aliases=_aliases(data.get("object_aliases"), "object_aliases"),
    )


class RetrievalIndexReadRepository:
    """Read-only Neo4j access for index sync set expansion and document loading."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def expand_related_memory_ids(
        self,
        user_id: str,
        seed_memory_ids: set[str],
    ) -> set[str]:
        if not seed_memory_ids:
            return set()

        async def _read(tx: AsyncManagedTransaction) -> set[str]:
            result = await tx.run(
                Q_RI1_RELATED_MEMORY_IDS,
                user_id=user_id,
                seed_memory_ids=sorted(seed_memory_ids),
            )
            memory_ids: set[str] = set()
            async for record in result:
                memory_id = record.get("memory_id")
                if memory_id is None:
                    continue
                if not isinstance(memory_id, str):
                    raise RetrievalIndexGraphDataError("related memory_id must be string")
                memory_ids.add(memory_id)
            return memory_ids

        async with self._driver.session() as session:
            return await session.execute_read(_read)

    async def expand_entity_linked_memory_ids(
        self,
        user_id: str,
        entity_ids: list[str],
    ) -> set[str]:
        if not entity_ids:
            return set()

        async def _read(tx: AsyncManagedTransaction) -> set[str]:
            result = await tx.run(
                Q_RI2_ENTITY_LINKED_MEMORY_IDS,
                user_id=user_id,
                entity_ids=entity_ids,
            )
            memory_ids: set[str] = set()
            async for record in result:
                memory_id = record.get("memory_id")
                if memory_id is None:
                    continue
                if not isinstance(memory_id, str):
                    raise RetrievalIndexGraphDataError("entity-linked memory_id must be string")
                memory_ids.add(memory_id)
            return memory_ids

        async with self._driver.session() as session:
            return await session.execute_read(_read)

    async def load_memory_index_rows(
        self,
        user_id: str,
        memory_ids: set[str],
    ) -> list[MemoryIndexRow]:
        if not memory_ids:
            return []

        async def _read(tx: AsyncManagedTransaction) -> list[MemoryIndexRow]:
            result = await tx.run(
                Q_RI3_LOAD_MEMORY_INDEX_ROWS,
                user_id=user_id,
                memory_ids=sorted(memory_ids),
            )
            rows: list[MemoryIndexRow] = []
            async for record in result:
                row = _row_from_record(record)
                if row.user_id != user_id:
                    raise RetrievalIndexGraphDataError("memory user_id mismatch")
                rows.append(row)
            return rows

        async with self._driver.session() as session:
            return await session.execute_read(_read)


def authorized_read_cypher_queries() -> tuple[str, ...]:
    """Authorized read-only Cypher for contract tests."""
    return (
        Q_RI1_RELATED_MEMORY_IDS,
        Q_RI2_ENTITY_LINKED_MEMORY_IDS,
        Q_RI3_LOAD_MEMORY_INDEX_ROWS,
    )
