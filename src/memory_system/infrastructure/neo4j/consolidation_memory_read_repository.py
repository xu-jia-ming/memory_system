"""Read-only Neo4j repository for CON-002 consolidation candidate batch scan (§2.3.4)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from memory_system.domain.models.consolidation_batch import ConsolidationMemoryRow

Q_FETCH_CANDIDATE_BATCH = """
MATCH (m:Memory)
WHERE m.user_id = $user_id
  AND m.created_time <= $evaluation_time
  AND (m.last_consolidated_time IS NULL OR m.last_consolidated_time < $evaluation_time)
  AND ($cursor IS NULL OR m.memory_id > $cursor)
  AND m.status IN ["active", "conflicted", "superseded"]
OPTIONAL MATCH (e:Evidence)-[:SUPPORTS]->(m)
WHERE e.user_id = m.user_id
RETURN m,
       count(DISTINCT e.archive_id) AS independent_archive_count
ORDER BY m.memory_id ASC
LIMIT $batch_size
""".strip()


class ConsolidationMemoryGraphDataError(Exception):
    """Raised when Neo4j data cannot be mapped to a consolidation memory row."""


class ConsolidationReadError(Exception):
    """Raised when Neo4j consolidation read transport fails (consolidation_read_failed)."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def authorized_read_cypher_queries() -> tuple[str, ...]:
    return (Q_FETCH_CANDIDATE_BATCH,)


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ConsolidationMemoryGraphDataError(f"memory property {field} must be a string")
    return value


def _require_float(value: object, field: str) -> float:
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    raise ConsolidationMemoryGraphDataError(f"memory property {field} must be numeric")


def _require_int(value: object, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ConsolidationMemoryGraphDataError(f"memory property {field} must be an int")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ConsolidationMemoryGraphDataError("optional int property must be int or null")


def _require_archive_count(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise ConsolidationMemoryGraphDataError("independent_archive_count must be >= 0")
        return value
    raise ConsolidationMemoryGraphDataError("independent_archive_count must be an int")


def _memory_node_properties(node: object) -> Mapping[str, object]:
    if isinstance(node, Mapping):
        return node
    if hasattr(node, "items"):
        return dict(node.items())
    raise ConsolidationMemoryGraphDataError("memory node must be mapping-like")


def _try_extract_memory_id(record: Any) -> str | None:
    data = record.data() if hasattr(record, "data") else dict(record)
    node = data.get("m")
    if node is None:
        return None
    try:
        props = _memory_node_properties(node)
        memory_id = props.get("memory_id")
        if isinstance(memory_id, str):
            return memory_id
    except ConsolidationMemoryGraphDataError:
        return None
    return None


def memory_row_from_record(record: Any, request_user_id: str) -> ConsolidationMemoryRow:
    data = record.data() if hasattr(record, "data") else dict(record)
    if "m" not in data:
        raise ConsolidationMemoryGraphDataError("missing memory node in record")
    if "independent_archive_count" not in data:
        raise ConsolidationMemoryGraphDataError("missing independent_archive_count in record")

    props = _memory_node_properties(data["m"])
    memory_id = _require_str(props.get("memory_id"), "memory_id")
    node_user_id = props.get("user_id")
    if not isinstance(node_user_id, str) or node_user_id != request_user_id:
        raise ConsolidationMemoryGraphDataError("memory user_id does not match request user_id")

    archive_count = _require_archive_count(data["independent_archive_count"])

    return ConsolidationMemoryRow(
        memory_id=memory_id,
        memory_version=_optional_int(props.get("memory_version")),
        memory_type=_require_str(props.get("memory_type"), "memory_type"),
        confidence=_require_float(props.get("confidence"), "confidence"),
        status=_require_str(props.get("status"), "status"),
        created_time=_require_int(props.get("created_time"), "created_time"),
        latest_source_time=_optional_int(props.get("latest_source_time")),
        independent_archive_count=archive_count,
        mapping_valid=True,
    )


def _invalid_row_from_record(record: Any) -> ConsolidationMemoryRow:
    data = record.data() if hasattr(record, "data") else dict(record)
    memory_id = _try_extract_memory_id(record) or "unknown"
    archive_count = 0
    if "independent_archive_count" in data:
        try:
            archive_count = _require_archive_count(data["independent_archive_count"])
        except ConsolidationMemoryGraphDataError:
            archive_count = 0
    return ConsolidationMemoryRow(
        memory_id=memory_id,
        memory_version=None,
        memory_type=None,
        confidence=None,
        status=None,
        created_time=None,
        latest_source_time=None,
        independent_archive_count=archive_count,
        mapping_valid=False,
    )


class ConsolidationMemoryReadRepository:
    """Batch read-only consolidation candidate scan scoped to user_id."""

    def __init__(self, driver: AsyncDriver, *, neo4j_timeout_seconds: float) -> None:
        self._driver = driver
        self._neo4j_timeout_seconds = neo4j_timeout_seconds

    async def fetch_candidate_batch(
        self,
        user_id: str,
        evaluation_time: int,
        cursor: str | None,
        batch_size: int,
    ) -> list[ConsolidationMemoryRow]:
        async def _read(tx: AsyncManagedTransaction) -> list[ConsolidationMemoryRow]:
            result = await tx.run(
                Q_FETCH_CANDIDATE_BATCH,
                user_id=user_id,
                evaluation_time=evaluation_time,
                cursor=cursor,
                batch_size=batch_size,
            )
            rows: list[ConsolidationMemoryRow] = []
            async for record in result:
                record_data = record.data() if hasattr(record, "data") else dict(record)
                if "m" not in record_data or "independent_archive_count" not in record_data:
                    raise ConsolidationReadError(
                        "malformed consolidation batch record structure",
                        retryable=False,
                    )
                try:
                    rows.append(memory_row_from_record(record, user_id))
                except ConsolidationMemoryGraphDataError:
                    rows.append(_invalid_row_from_record(record))
            return rows

        try:
            async with self._driver.session() as session:
                return await asyncio.wait_for(
                    session.execute_read(_read),
                    timeout=self._neo4j_timeout_seconds,
                )
        except TimeoutError as exc:
            raise ConsolidationReadError(
                "neo4j consolidation candidate batch timed out",
                retryable=True,
            ) from exc
        except (ServiceUnavailable, Neo4jError) as exc:
            raise ConsolidationReadError(
                "neo4j consolidation candidate batch failed",
                retryable=True,
            ) from exc
