"""Neo4j atomic graph write repository for EXT-006."""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncManagedTransaction

from memory_system.domain.models.graph_write import (
    EntityWriteRow,
    ImmutableGraphWritePlan,
    MemoryCreateRow,
)

ENTITY_MERGE_CYPHER = """
UNWIND $rows AS row
MERGE (e:Entity {entity_key: row.entity_key})
ON CREATE SET
  e.entity_id = row.entity_id,
  e.user_id = row.user_id,
  e.entity_type = row.entity_type,
  e.canonical_name = row.canonical_name,
  e.normalized_name = row.normalized_name,
  e.aliases = row.aliases,
  e.created_time = row.created_time,
  e.updated_time = row.updated_time
ON MATCH SET
  e.aliases = row.aliases,
  e.updated_time = row.updated_time
RETURN e.entity_key AS entity_key, e.entity_id AS entity_id
""".strip()

ENTITY_RESOLVE_CYPHER = """
UNWIND $entity_keys AS entity_key
MATCH (e:Entity {entity_key: entity_key})
WHERE e.user_id = $user_id
RETURN e.entity_key AS entity_key, e.entity_id AS entity_id
""".strip()

MEMORY_CREATE_CYPHER = """
UNWIND $rows AS row
MERGE (m:Memory {memory_id: row.memory_id})
ON CREATE SET
  m.user_id = row.user_id,
  m.memory_type = row.memory_type,
  m.content = row.content,
  m.subject_entity_id = row.subject_entity_id,
  m.predicate = row.predicate,
  m.object_entity_id = row.object_entity_id,
  m.object_value = row.object_value,
  m.status = row.status,
  m.abstraction_level = row.abstraction_level,
  m.event_status = row.event_status,
  m.start_time = row.start_time,
  m.end_time = row.end_time,
  m.original_time_text = row.original_time_text,
  m.confidence = row.confidence,
  m.importance = row.importance,
  m.latest_source_time = row.latest_source_time,
  m.first_seen_time = row.first_seen_time,
  m.last_seen_time = row.last_seen_time,
  m.retrieval_count = row.retrieval_count,
  m.last_retrieved_time = row.last_retrieved_time,
  m.last_consolidated_time = row.last_consolidated_time,
  m.memory_version = row.memory_version,
  m.created_time = row.created_time,
  m.updated_time = row.updated_time
""".strip()

MEMORY_UPDATE_CYPHER = """
UNWIND $rows AS row
MATCH (m:Memory {memory_id: row.target_memory_id})
WHERE m.user_id = row.user_id
SET m.updated_time = row.updated_time,
    m.last_seen_time = row.last_seen_time,
    m.content = CASE
      WHEN row.planned_merged_content IS NOT NULL THEN row.planned_merged_content
      ELSE m.content
    END,
    m.confidence = CASE
      WHEN row.planned_merged_confidence IS NOT NULL THEN row.planned_merged_confidence
      ELSE m.confidence
    END,
    m.latest_source_time = CASE
      WHEN row.planned_latest_source_time IS NOT NULL THEN row.planned_latest_source_time
      ELSE m.latest_source_time
    END,
    m.status = CASE
      WHEN row.status IS NOT NULL THEN row.status
      ELSE m.status
    END,
    m.memory_version = m.memory_version + CASE
      WHEN row.increment_memory_version THEN 1
      ELSE 0
    END
""".strip()

SUBJECT_REL_CYPHER = """
UNWIND $rows AS row
MATCH (m:Memory {memory_id: row.memory_id})
WHERE m.user_id = row.user_id
MATCH (e:Entity {entity_id: row.subject_entity_id})
WHERE e.user_id = row.user_id
MERGE (m)-[:SUBJECT]->(e)
""".strip()

OBJECT_REL_CYPHER = """
UNWIND $rows AS row
MATCH (m:Memory {memory_id: row.memory_id})
WHERE m.user_id = row.user_id
MATCH (e:Entity {entity_id: row.object_entity_id})
WHERE e.user_id = row.user_id
MERGE (m)-[:OBJECT]->(e)
""".strip()

SUPERSEDES_REL_CYPHER = """
UNWIND $rows AS row
MATCH (new:Memory {memory_id: row.new_memory_id})
WHERE new.user_id = row.user_id
MATCH (old:Memory {memory_id: row.old_memory_id})
WHERE old.user_id = row.user_id
MERGE (new)-[:SUPERSEDES]->(old)
""".strip()

CONFLICTS_REL_CYPHER = """
UNWIND $rows AS row
MATCH (new:Memory {memory_id: row.new_memory_id})
WHERE new.user_id = row.user_id
MATCH (old:Memory {memory_id: row.old_memory_id})
WHERE old.user_id = row.user_id
MERGE (new)-[:CONFLICTS_WITH]->(old)
""".strip()

EVIDENCE_MERGE_CYPHER = """
UNWIND $rows AS row
MATCH (m:Memory {memory_id: row.memory_id})
WHERE m.user_id = row.user_id
MERGE (ev:Evidence {evidence_id: row.evidence_id})
ON CREATE SET
  ev.user_id = row.user_id,
  ev.archive_id = row.archive_id,
  ev.session_id = row.session_id,
  ev.source_message_ids = row.source_message_ids,
  ev.source_time_start = row.source_time_start,
  ev.source_time_end = row.source_time_end,
  ev.extracted_content = row.extracted_content,
  ev.prompt_version = row.prompt_version,
  ev.created_time = row.created_time
MERGE (ev)-[:SUPPORTS]->(m)
""".strip()


def _entity_id_resolution_map(
    entity_rows: list[EntityWriteRow],
    entity_key_to_id: dict[str, str],
) -> dict[str, str]:
    """Map planned entity_id to authoritative entity_id after entity_key MERGE."""
    resolution: dict[str, str] = {}
    for row in entity_rows:
        authoritative_id = entity_key_to_id.get(row.entity_key, row.entity_id)
        resolution[row.entity_id] = authoritative_id
    return resolution


def _resolve_entity_id(entity_id: str, resolution_map: dict[str, str]) -> str:
    return resolution_map.get(entity_id, entity_id)


def _resolved_memory_create_row(
    row: MemoryCreateRow,
    entity_id_resolution: dict[str, str],
) -> dict[str, object]:
    resolved = row.model_dump(mode="json")
    resolved["subject_entity_id"] = _resolve_entity_id(
        row.subject_entity_id,
        entity_id_resolution,
    )
    if row.object_entity_id is not None:
        resolved["object_entity_id"] = _resolve_entity_id(
            row.object_entity_id,
            entity_id_resolution,
        )
    return resolved


async def _load_entity_key_to_id(
    tx: AsyncManagedTransaction,
    *,
    user_id: str,
    entity_keys: list[str],
) -> dict[str, str]:
    if not entity_keys:
        return {}
    result = await tx.run(
        ENTITY_RESOLVE_CYPHER,
        entity_keys=entity_keys,
        user_id=user_id,
    )
    records = [record async for record in result]
    return {str(record["entity_key"]): str(record["entity_id"]) for record in records}


class GraphWriteRepository:
    """Execute one atomic Neo4j write transaction per archive write plan."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def write(self, plan: ImmutableGraphWritePlan) -> None:
        async def _write(tx: AsyncManagedTransaction) -> None:
            entity_id_resolution: dict[str, str] = {}
            if plan.entity_rows:
                merge_result = await tx.run(
                    ENTITY_MERGE_CYPHER,
                    rows=[row.model_dump(mode="json") for row in plan.entity_rows],
                )
                entity_key_to_id = {
                    str(record["entity_key"]): str(record["entity_id"])
                    async for record in merge_result
                }
                missing_keys = [
                    row.entity_key
                    for row in plan.entity_rows
                    if row.entity_key not in entity_key_to_id
                ]
                if missing_keys:
                    entity_key_to_id.update(
                        await _load_entity_key_to_id(
                            tx,
                            user_id=plan.user_id,
                            entity_keys=missing_keys,
                        )
                    )
                entity_id_resolution = _entity_id_resolution_map(
                    plan.entity_rows,
                    entity_key_to_id,
                )

            resolved_memory_create_rows = [
                _resolved_memory_create_row(row, entity_id_resolution)
                for row in plan.memory_create_rows
            ]
            if resolved_memory_create_rows:
                await tx.run(MEMORY_CREATE_CYPHER, rows=resolved_memory_create_rows)
            if plan.memory_update_rows:
                await tx.run(
                    MEMORY_UPDATE_CYPHER,
                    rows=[row.model_dump(mode="json") for row in plan.memory_update_rows],
                )

            subject_rows = [
                {
                    "memory_id": row["memory_id"],
                    "user_id": row["user_id"],
                    "subject_entity_id": row["subject_entity_id"],
                }
                for row in resolved_memory_create_rows
            ]
            if subject_rows:
                await tx.run(SUBJECT_REL_CYPHER, rows=subject_rows)

            object_rows = [
                {
                    "memory_id": row["memory_id"],
                    "user_id": row["user_id"],
                    "object_entity_id": row["object_entity_id"],
                }
                for row in resolved_memory_create_rows
                if row.get("object_entity_id") is not None
            ]
            if object_rows:
                await tx.run(OBJECT_REL_CYPHER, rows=object_rows)

            supersedes_rows = [
                {
                    "user_id": row.user_id,
                    "new_memory_id": row.memory_id,
                    "old_memory_id": row.supersedes_target_memory_id,
                }
                for row in plan.memory_create_rows
                if row.supersedes_target_memory_id is not None
            ]
            if supersedes_rows:
                await tx.run(SUPERSEDES_REL_CYPHER, rows=supersedes_rows)

            conflicts_rows = [
                {
                    "user_id": row.user_id,
                    "new_memory_id": row.memory_id,
                    "old_memory_id": row.conflicts_with_target_memory_id,
                }
                for row in plan.memory_create_rows
                if row.conflicts_with_target_memory_id is not None
            ]
            if conflicts_rows:
                await tx.run(CONFLICTS_REL_CYPHER, rows=conflicts_rows)

            if plan.evidence_rows:
                await tx.run(
                    EVIDENCE_MERGE_CYPHER,
                    rows=[row.model_dump(mode="json") for row in plan.evidence_rows],
                )

        async with self._driver.session() as session:
            await session.execute_write(_write)


def authorized_write_cypher_queries() -> tuple[str, ...]:
    """Return authorized write Cypher bodies for contract tests."""
    return (
        ENTITY_MERGE_CYPHER,
        MEMORY_CREATE_CYPHER,
        MEMORY_UPDATE_CYPHER,
        SUBJECT_REL_CYPHER,
        OBJECT_REL_CYPHER,
        SUPERSEDES_REL_CYPHER,
        CONFLICTS_REL_CYPHER,
        EVIDENCE_MERGE_CYPHER,
    )
