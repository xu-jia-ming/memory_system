"""CON-005 failure injection repository wrappers and Neo4j test helpers."""

from __future__ import annotations

import asyncio

from neo4j import AsyncDriver

from memory_system.domain.models.consolidation_batch import ConsolidationMemoryRow
from memory_system.domain.models.consolidation_write import ConsolidationWriteRow
from memory_system.infrastructure.neo4j.consolidation_memory_read_repository import (
    ConsolidationMemoryReadRepository,
    ConsolidationReadError,
)
from memory_system.infrastructure.neo4j.consolidation_memory_write_repository import (
    ConsolidationMemoryWriteRepository,
    ConsolidationWriteError,
)


class FailingConsolidationMemoryReadRepository(ConsolidationMemoryReadRepository):
    """Fail on the Nth fetch_candidate_batch call (1-based)."""

    def __init__(
        self,
        driver: AsyncDriver,
        *,
        neo4j_timeout_seconds: float,
        fail_on_call: int,
    ) -> None:
        super().__init__(driver, neo4j_timeout_seconds=neo4j_timeout_seconds)
        self._fail_on_call = fail_on_call
        self._call_count = 0

    async def fetch_candidate_batch(
        self,
        user_id: str,
        evaluation_time: int,
        cursor: str | None,
        batch_size: int,
    ) -> list[ConsolidationMemoryRow]:
        self._call_count += 1
        if self._call_count == self._fail_on_call:
            raise ConsolidationReadError("injected consolidation read failure", retryable=True)
        return await super().fetch_candidate_batch(
            user_id=user_id,
            evaluation_time=evaluation_time,
            cursor=cursor,
            batch_size=batch_size,
        )


class FailingConsolidationMemoryWriteRepository(ConsolidationMemoryWriteRepository):
    """Fail on the Nth write_importance_batch call (1-based)."""

    def __init__(
        self,
        driver: AsyncDriver,
        *,
        neo4j_timeout_seconds: float,
        fail_on_call: int,
    ) -> None:
        super().__init__(driver, neo4j_timeout_seconds=neo4j_timeout_seconds)
        self._fail_on_call = fail_on_call
        self._call_count = 0

    async def write_importance_batch(
        self,
        user_id: str,
        evaluation_time: int,
        rows: list[ConsolidationWriteRow],
    ) -> int:
        self._call_count += 1
        if self._call_count == self._fail_on_call:
            raise ConsolidationWriteError("injected consolidation write failure", retryable=True)
        return await super().write_importance_batch(
            user_id=user_id,
            evaluation_time=evaluation_time,
            rows=rows,
        )


class BlockingConsolidationMemoryReadRepository(ConsolidationMemoryReadRepository):
    """Block the first fetch until release_event is set (mutex overlap testing)."""

    def __init__(
        self,
        driver: AsyncDriver,
        *,
        neo4j_timeout_seconds: float,
        entered_event: asyncio.Event,
        release_event: asyncio.Event,
    ) -> None:
        super().__init__(driver, neo4j_timeout_seconds=neo4j_timeout_seconds)
        self._entered_event = entered_event
        self._release_event = release_event
        self._blocked_once = False

    async def fetch_candidate_batch(
        self,
        user_id: str,
        evaluation_time: int,
        cursor: str | None,
        batch_size: int,
    ) -> list[ConsolidationMemoryRow]:
        if not self._blocked_once and cursor is None:
            self._blocked_once = True
            self._entered_event.set()
            await self._release_event.wait()
        return await super().fetch_candidate_batch(
            user_id=user_id,
            evaluation_time=evaluation_time,
            cursor=cursor,
            batch_size=batch_size,
        )


async def bump_memory_version(
    driver: AsyncDriver,
    *,
    user_id: str,
    memory_id: str,
    increment: int = 1,
) -> int:
    """Simulate extraction race by bumping memory_version outside consolidation write."""
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            SET m.memory_version = m.memory_version + $increment
            RETURN m.memory_version AS memory_version
            """,
            memory_id=memory_id,
            user_id=user_id,
            increment=increment,
        )
        record = await result.single()
        if record is None:
            raise AssertionError(f"memory not found for version bump: {user_id}/{memory_id}")
        return int(record["memory_version"])


class VersionBumpBeforeWriteRepository(ConsolidationMemoryWriteRepository):
    """Bump selected memories immediately before write to simulate extraction race."""

    def __init__(
        self,
        driver: AsyncDriver,
        *,
        neo4j_timeout_seconds: float,
        bump_memory_ids: set[str],
    ) -> None:
        super().__init__(driver, neo4j_timeout_seconds=neo4j_timeout_seconds)
        self._bump_memory_ids = bump_memory_ids

    async def write_importance_batch(
        self,
        user_id: str,
        evaluation_time: int,
        rows: list[ConsolidationWriteRow],
    ) -> int:
        for row in rows:
            if row.memory_id in self._bump_memory_ids:
                await bump_memory_version(
                    self._driver,
                    user_id=user_id,
                    memory_id=row.memory_id,
                )
        return await super().write_importance_batch(
            user_id=user_id,
            evaluation_time=evaluation_time,
            rows=rows,
        )
