"""Read-only Neo4j repository for RET-004 Top-K Evidence batch load (§2.2.12)."""

from __future__ import annotations

import asyncio
from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from memory_system.domain.services.evidence_aggregation import EvidenceRow

Q_LOAD_EVIDENCE_FOR_MEMORIES = """
UNWIND $memory_ids AS memory_id
MATCH (ev:Evidence)-[:SUPPORTS]->(m:Memory {memory_id: memory_id})
WHERE m.user_id = $user_id
  AND ev.user_id = $user_id
RETURN ev.evidence_id AS evidence_id,
       m.memory_id AS memory_id,
       ev.source_time_end AS source_time_end,
       ev.source_message_ids AS source_message_ids
""".strip()


class RetrievalEvidenceGraphDataError(Exception):
    """Raised when Evidence query returns unexpected data."""


class RetrievalEvidenceReadError(Exception):
    """Raised when Neo4j Evidence read transport fails."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def authorized_read_cypher_queries() -> tuple[str, ...]:
    return (Q_LOAD_EVIDENCE_FOR_MEMORIES,)


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise RetrievalEvidenceGraphDataError(f"evidence property {field} must be a string")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise RetrievalEvidenceGraphDataError("optional int property must be int or null")


def _require_message_ids(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RetrievalEvidenceGraphDataError("source_message_ids must be a list")
    message_ids: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise RetrievalEvidenceGraphDataError("source_message_ids item must be a string")
        message_ids.append(item)
    return message_ids


def evidence_row_from_record(record: Any) -> EvidenceRow:
    data = record.data() if hasattr(record, "data") else dict(record)
    required = ("evidence_id", "memory_id")
    for field in required:
        if field not in data:
            raise RetrievalEvidenceGraphDataError(f"missing evidence property {field}")
    return EvidenceRow(
        evidence_id=_require_str(data["evidence_id"], "evidence_id"),
        memory_id=_require_str(data["memory_id"], "memory_id"),
        source_time_end=_optional_int(data.get("source_time_end")),
        source_message_ids=_require_message_ids(data.get("source_message_ids")),
    )


class RetrievalEvidenceReadRepository:
    """Batch read-only Evidence load for Top-K memories scoped to user_id."""

    def __init__(self, driver: AsyncDriver, *, neo4j_timeout_seconds: float) -> None:
        self._driver = driver
        self._neo4j_timeout_seconds = neo4j_timeout_seconds

    async def load_evidence_for_memories(
        self,
        user_id: str,
        memory_ids: list[str],
    ) -> list[EvidenceRow]:
        if not memory_ids:
            return []

        sorted_ids = sorted(memory_ids)

        async def _read(tx: AsyncManagedTransaction) -> list[EvidenceRow]:
            result = await tx.run(
                Q_LOAD_EVIDENCE_FOR_MEMORIES,
                memory_ids=sorted_ids,
                user_id=user_id,
            )
            rows: list[EvidenceRow] = []
            async for record in result:
                try:
                    row = evidence_row_from_record(record)
                except RetrievalEvidenceGraphDataError as exc:
                    raise RetrievalEvidenceReadError(
                        f"malformed evidence row: {exc}",
                        retryable=False,
                    ) from exc
                if row.memory_id not in sorted_ids:
                    raise RetrievalEvidenceReadError(
                        f"evidence row memory_id {row.memory_id!r} outside requested batch",
                        retryable=False,
                    )
                rows.append(row)
            return rows

        try:
            async with self._driver.session() as session:
                return await asyncio.wait_for(
                    session.execute_read(_read),
                    timeout=self._neo4j_timeout_seconds,
                )
        except RetrievalEvidenceReadError:
            raise
        except TimeoutError as exc:
            raise RetrievalEvidenceReadError(
                "neo4j evidence load timed out",
                retryable=True,
            ) from exc
        except (ServiceUnavailable, Neo4jError) as exc:
            raise RetrievalEvidenceReadError(
                "neo4j evidence load failed",
                retryable=True,
            ) from exc
