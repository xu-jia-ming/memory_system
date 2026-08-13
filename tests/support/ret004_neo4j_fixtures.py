"""RET-004 integration test Neo4j fixture helpers for Evidence SUPPORTS."""

from __future__ import annotations

from neo4j import AsyncDriver
from tests.support.ret003_neo4j_fixtures import (
    FIXED_NOW,
    USER_A,
    USER_B,
    _create_memory,
    _link_subject,
    seed_ret003_graph,
)

USER_RET004_A = USER_A
USER_RET004_B = USER_B
MEMORY_WITH_EVIDENCE = "mem-ret004-evidence"
MEMORY_NO_EVIDENCE = "mem-ret004-no-evidence"
MEMORY_USER_B = "mem-b-evidence"


async def _create_evidence_supports(
    driver: AsyncDriver,
    *,
    evidence_id: str,
    user_id: str,
    memory_id: str,
    source_time_end: int | None,
    source_message_ids: list[str],
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            CREATE (ev:Evidence {
              evidence_id: $evidence_id,
              user_id: $user_id,
              source_time_end: $source_time_end,
              source_message_ids: $source_message_ids
            })-[:SUPPORTS]->(m)
            """,
            evidence_id=evidence_id,
            user_id=user_id,
            memory_id=memory_id,
            source_time_end=source_time_end,
            source_message_ids=source_message_ids,
        )


async def seed_ret004_evidence_graph(driver: AsyncDriver) -> dict[str, str]:
    """Seed RET-003 base graph plus RET-004 Evidence SUPPORTS fixtures."""
    base = await seed_ret003_graph(driver)

    await _create_memory(
        driver,
        memory_id=MEMORY_WITH_EVIDENCE,
        user_id=USER_A,
        content="memory with evidence",
        subject_entity_id="entity-subject-a",
        object_entity_id=None,
        importance=0.95,
        latest_source_time=300,
    )
    await _link_subject(
        driver,
        memory_id=MEMORY_WITH_EVIDENCE,
        entity_id="entity-subject-a",
        user_id=USER_A,
    )

    await _create_memory(
        driver,
        memory_id=MEMORY_NO_EVIDENCE,
        user_id=USER_A,
        content="memory without evidence",
        subject_entity_id="entity-subject-a",
        object_entity_id=None,
        importance=0.5,
        latest_source_time=50,
    )
    await _link_subject(
        driver,
        memory_id=MEMORY_NO_EVIDENCE,
        entity_id="entity-subject-a",
        user_id=USER_A,
    )

    await _create_memory(
        driver,
        memory_id=MEMORY_USER_B,
        user_id=USER_B,
        content="user b evidence memory",
        subject_entity_id="entity-shared-object",
        object_entity_id=None,
        importance=0.8,
        latest_source_time=400,
    )
    await _link_subject(
        driver,
        memory_id=MEMORY_USER_B,
        entity_id="entity-shared-object",
        user_id=USER_B,
    )

    await _create_evidence_supports(
        driver,
        evidence_id="ev-a-e2",
        user_id=USER_A,
        memory_id=MEMORY_WITH_EVIDENCE,
        source_time_end=200,
        source_message_ids=["m2", "m1"],
    )
    await _create_evidence_supports(
        driver,
        evidence_id="ev-a-e1",
        user_id=USER_A,
        memory_id=MEMORY_WITH_EVIDENCE,
        source_time_end=200,
        source_message_ids=["m3"],
    )
    await _create_evidence_supports(
        driver,
        evidence_id="ev-a-e3",
        user_id=USER_A,
        memory_id=MEMORY_WITH_EVIDENCE,
        source_time_end=100,
        source_message_ids=["m1", "m4"],
    )
    await _create_evidence_supports(
        driver,
        evidence_id="ev-b-only",
        user_id=USER_B,
        memory_id=MEMORY_USER_B,
        source_time_end=500,
        source_message_ids=["user-b-msg"],
    )

    return {
        **base,
        "with_evidence": MEMORY_WITH_EVIDENCE,
        "no_evidence": MEMORY_NO_EVIDENCE,
        "user_b_memory": MEMORY_USER_B,
        "fixed_now": str(FIXED_NOW),
    }
