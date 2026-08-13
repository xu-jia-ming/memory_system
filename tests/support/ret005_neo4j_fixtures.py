"""RET-005 integration Neo4j fixtures for retrieval statistics."""

from __future__ import annotations

from neo4j import AsyncDriver
from tests.support.ret003_neo4j_fixtures import (
    ENTITY_SUBJECT,
    FIXED_NOW,
    USER_A,
    _create_entity,
    _create_memory,
    _link_subject,
)

USER_RET005_A = USER_A
MEMORY_STATS_A = "mem-ret005-stats-a"
MEMORY_STATS_B = "mem-ret005-stats-b"


async def seed_ret005_stats_memories(driver: AsyncDriver) -> dict[str, int]:
    """Seed memories with known retrieval_count and last_retrieved_time."""
    await _create_entity(
        driver,
        entity_id=ENTITY_SUBJECT,
        user_id=USER_RET005_A,
        canonical_name="Subject",
    )
    await _create_memory(
        driver,
        memory_id=MEMORY_STATS_A,
        user_id=USER_RET005_A,
        content="stats memory a",
        subject_entity_id=ENTITY_SUBJECT,
        object_entity_id=None,
    )
    await _link_subject(
        driver,
        memory_id=MEMORY_STATS_A,
        entity_id=ENTITY_SUBJECT,
        user_id=USER_RET005_A,
    )
    await _create_memory(
        driver,
        memory_id=MEMORY_STATS_B,
        user_id=USER_RET005_A,
        content="stats memory b",
        subject_entity_id=ENTITY_SUBJECT,
        object_entity_id=None,
    )
    await _link_subject(
        driver,
        memory_id=MEMORY_STATS_B,
        entity_id=ENTITY_SUBJECT,
        user_id=USER_RET005_A,
    )

    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            SET m.retrieval_count = $retrieval_count,
                m.last_retrieved_time = $last_retrieved_time
            """,
            memory_id=MEMORY_STATS_A,
            user_id=USER_RET005_A,
            retrieval_count=2,
            last_retrieved_time=FIXED_NOW - 100,
        )

    return {
        MEMORY_STATS_A: 2,
        MEMORY_STATS_B: 0,
    }
