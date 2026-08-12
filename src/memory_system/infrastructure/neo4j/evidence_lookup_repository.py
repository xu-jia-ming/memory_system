"""Read-only Neo4j repository for EXT-005 Evidence existence checks (Q-E1)."""

from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction

Q_E1_EVIDENCE_EXISTS_CYPHER = """
UNWIND $evidence_ids AS eid
MATCH (ev:Evidence {evidence_id: eid})-[:SUPPORTS]->(m:Memory)
WHERE ev.user_id = $user_id
RETURN ev.evidence_id AS evidence_id
""".strip()


class EvidenceGraphDataError(Exception):
    """Raised when Evidence existence query returns unexpected data."""


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise EvidenceGraphDataError(f"evidence property {field} must be a string")
    return value


class EvidenceLookupRepository:
    """Batch read-only Evidence processed checks scoped to a single user_id."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def find_processed_evidence_ids(
        self,
        user_id: str,
        evidence_ids: list[str],
    ) -> set[str]:
        if not evidence_ids:
            return set()

        async def _read(tx: AsyncManagedTransaction) -> set[str]:
            result = await tx.run(
                Q_E1_EVIDENCE_EXISTS_CYPHER,
                evidence_ids=evidence_ids,
                user_id=user_id,
            )
            processed: set[str] = set()
            async for record in result:
                data: dict[str, Any] = record.data()
                processed.add(_require_str(data["evidence_id"], "evidence_id"))
            return processed

        async with self._driver.session() as session:
            return await session.execute_read(_read)
