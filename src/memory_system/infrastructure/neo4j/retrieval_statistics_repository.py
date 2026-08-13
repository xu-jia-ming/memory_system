"""Neo4j batch write for retrieval_count and last_retrieved_time (§2.2.13)."""

from __future__ import annotations

import asyncio

from neo4j import AsyncDriver, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable

Q_INCREMENT_RETRIEVAL_STATS = """
UNWIND $memory_ids AS memory_id
MATCH (m:Memory {memory_id: memory_id, user_id: $user_id})
SET m.retrieval_count = coalesce(m.retrieval_count, 0) + 1,
    m.last_retrieved_time =
        CASE
            WHEN m.last_retrieved_time IS NULL
              OR m.last_retrieved_time < $current_time
            THEN $current_time
            ELSE m.last_retrieved_time
        END
""".strip()


class RetrievalStatisticsWriteError(Exception):
    """Raised when Neo4j retrieval statistics write fails."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def authorized_write_cypher_queries() -> tuple[str, ...]:
    return (Q_INCREMENT_RETRIEVAL_STATS,)


class RetrievalStatisticsRepository:
    """Batch update retrieval_count and last_retrieved_time for Top-K memories."""

    def __init__(self, driver: AsyncDriver, *, neo4j_timeout_seconds: float) -> None:
        self._driver = driver
        self._neo4j_timeout_seconds = neo4j_timeout_seconds

    async def increment_retrieval_stats(
        self,
        *,
        user_id: str,
        memory_ids: list[str],
        current_time: int,
    ) -> None:
        if not memory_ids:
            return

        sorted_ids = sorted(dict.fromkeys(memory_ids))

        async def _write(tx: AsyncManagedTransaction) -> None:
            await tx.run(
                Q_INCREMENT_RETRIEVAL_STATS,
                memory_ids=sorted_ids,
                user_id=user_id,
                current_time=current_time,
            )

        try:
            async with self._driver.session() as session:
                await asyncio.wait_for(
                    session.execute_write(_write),
                    timeout=self._neo4j_timeout_seconds,
                )
        except TimeoutError as exc:
            raise RetrievalStatisticsWriteError(
                "neo4j retrieval statistics write timed out",
                retryable=True,
            ) from exc
        except (ServiceUnavailable, Neo4jError) as exc:
            raise RetrievalStatisticsWriteError(
                "neo4j retrieval statistics write failed",
                retryable=True,
            ) from exc
