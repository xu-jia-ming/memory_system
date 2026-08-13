"""Neo4j optimistic-lock batch write for CON-003 consolidation (§2.3.9)."""

from __future__ import annotations

import asyncio
from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from memory_system.domain.models.consolidation_write import ConsolidationWriteRow

Q_WRITE_IMPORTANCE_BATCH = """
UNWIND $rows AS row
MATCH (m:Memory {memory_id: row.memory_id})
WHERE m.user_id = row.user_id
  AND m.memory_version = row.expected_memory_version
SET m.importance = row.importance,
    m.last_consolidated_time = $evaluation_time
RETURN count(m) AS updated_count
""".strip()


class ConsolidationWriteError(Exception):
    """Raised when Neo4j consolidation write transport fails (consolidation_write_failed)."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def authorized_write_cypher_queries() -> tuple[str, ...]:
    return (Q_WRITE_IMPORTANCE_BATCH,)


def _row_to_cypher_param(row: ConsolidationWriteRow, user_id: str) -> dict[str, Any]:
    return {
        "memory_id": row.memory_id,
        "user_id": user_id,
        "expected_memory_version": row.expected_memory_version,
        "importance": row.new_importance,
    }


def _extract_updated_count(record: Any) -> int:
    data = record.data() if hasattr(record, "data") else dict(record)
    if "updated_count" not in data:
        raise ConsolidationWriteError(
            "malformed consolidation write record structure",
            retryable=False,
        )
    value = data["updated_count"]
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ConsolidationWriteError(
        "malformed consolidation write updated_count",
        retryable=False,
    )


class ConsolidationMemoryWriteRepository:
    """Batch optimistic-lock write for importance and last_consolidated_time."""

    def __init__(self, driver: AsyncDriver, *, neo4j_timeout_seconds: float) -> None:
        self._driver = driver
        self._neo4j_timeout_seconds = neo4j_timeout_seconds

    async def write_importance_batch(
        self,
        user_id: str,
        evaluation_time: int,
        rows: list[ConsolidationWriteRow],
    ) -> int:
        if not rows:
            raise ValueError("rows must be non-empty for write_importance_batch")

        cypher_rows = [_row_to_cypher_param(row, user_id) for row in rows]

        async def _write(tx: AsyncManagedTransaction) -> int:
            result = await tx.run(
                Q_WRITE_IMPORTANCE_BATCH,
                rows=cypher_rows,
                evaluation_time=evaluation_time,
            )
            record = await result.single()
            if record is None:
                raise ConsolidationWriteError(
                    "consolidation write returned no record",
                    retryable=False,
                )
            return _extract_updated_count(record)

        try:
            async with self._driver.session() as session:
                return await asyncio.wait_for(
                    session.execute_write(_write),
                    timeout=self._neo4j_timeout_seconds,
                )
        except TimeoutError as exc:
            raise ConsolidationWriteError(
                "neo4j consolidation write timed out",
                retryable=True,
            ) from exc
        except (ServiceUnavailable, Neo4jError) as exc:
            raise ConsolidationWriteError(
                "neo4j consolidation write failed",
                retryable=True,
            ) from exc
