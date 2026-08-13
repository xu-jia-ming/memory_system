"""Neo4j DISTINCT user_id enumeration for CON-004 consolidation runs (§2.3.4)."""

from __future__ import annotations

import asyncio

from neo4j import AsyncDriver, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationReadError,
)

Q_LIST_USER_IDS = """
MATCH (m:Memory)
WHERE m.created_time <= $evaluation_time
  AND (m.last_consolidated_time IS NULL OR m.last_consolidated_time < $evaluation_time)
  AND m.status IN ["active", "conflicted", "superseded"]
RETURN DISTINCT m.user_id AS user_id
ORDER BY m.user_id ASC
""".strip()


def authorized_enumeration_cypher_queries() -> tuple[str, ...]:
    return (Q_LIST_USER_IDS,)


def _require_user_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ConsolidationReadError(
            "malformed consolidation user enumeration user_id",
            retryable=False,
        )
    return value


class ConsolidationUserEnumerationRepository:
    """Read-only DISTINCT user_id enumeration for consolidation candidate scan."""

    def __init__(self, driver: AsyncDriver, *, neo4j_timeout_seconds: float) -> None:
        self._driver = driver
        self._neo4j_timeout_seconds = neo4j_timeout_seconds

    async def list_user_ids(self, evaluation_time: int) -> list[str]:
        async def _read(tx: AsyncManagedTransaction) -> list[str]:
            result = await tx.run(Q_LIST_USER_IDS, evaluation_time=evaluation_time)
            user_ids: list[str] = []
            async for record in result:
                data = record.data() if hasattr(record, "data") else dict(record)
                if "user_id" not in data:
                    raise ConsolidationReadError(
                        "malformed consolidation user enumeration record structure",
                        retryable=False,
                    )
                user_ids.append(_require_user_id(data["user_id"]))
            return user_ids

        try:
            async with self._driver.session() as session:
                return await asyncio.wait_for(
                    session.execute_read(_read),
                    timeout=self._neo4j_timeout_seconds,
                )
        except TimeoutError as exc:
            raise ConsolidationReadError(
                "neo4j consolidation user enumeration timed out",
                retryable=True,
            ) from exc
        except (ServiceUnavailable, Neo4jError) as exc:
            raise ConsolidationReadError(
                "neo4j consolidation user enumeration failed",
                retryable=True,
            ) from exc
