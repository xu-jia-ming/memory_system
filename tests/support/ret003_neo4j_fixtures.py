"""RET-003 integration test Neo4j fixture helpers."""

from __future__ import annotations

from neo4j import AsyncDriver

USER_A = "user_ret003_a"
USER_B = "user_ret003_b"
ENTITY_SHARED_OBJECT = "entity-shared-object"
ENTITY_SUBJECT = "entity-subject-a"
FIXED_NOW = 1_700_000_200


async def _create_entity(
    driver: AsyncDriver,
    *,
    entity_id: str,
    user_id: str,
    entity_type: str = "concept",
    canonical_name: str,
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            MERGE (e:Entity {entity_id: $entity_id})
            SET e.user_id = $user_id,
                e.entity_type = $entity_type,
                e.canonical_name = $canonical_name,
                e.normalized_name = $normalized_name,
                e.aliases = $aliases,
                e.entity_key = $entity_key
            """,
            entity_id=entity_id,
            user_id=user_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            normalized_name=canonical_name.lower(),
            aliases=[],
            entity_key=f"key-{entity_id}",
        )


async def _create_memory(
    driver: AsyncDriver,
    *,
    memory_id: str,
    user_id: str,
    memory_type: str = "fact",
    status: str = "active",
    content: str,
    subject_entity_id: str,
    object_entity_id: str | None,
    importance: float = 0.8,
    latest_source_time: int = 150,
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            CREATE (m:Memory {
              memory_id: $memory_id,
              user_id: $user_id,
              memory_type: $memory_type,
              content: $content,
              subject_entity_id: $subject_entity_id,
              predicate: 'works_on',
              object_entity_id: $object_entity_id,
              object_value: null,
              status: $status,
              event_status: null,
              start_time: null,
              end_time: null,
              original_time_text: null,
              confidence: 0.9,
              importance: $importance,
              latest_source_time: $latest_source_time,
              retrieval_count: 0,
              last_retrieved_time: null,
              updated_time: $updated_time,
              abstraction_level: 0,
              memory_version: 1,
              created_time: $updated_time,
              first_seen_time: $updated_time,
              last_seen_time: $updated_time
            })
            """,
            memory_id=memory_id,
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            subject_entity_id=subject_entity_id,
            object_entity_id=object_entity_id,
            status=status,
            importance=importance,
            latest_source_time=latest_source_time,
            updated_time=FIXED_NOW,
        )


async def _link_subject(
    driver: AsyncDriver,
    *,
    memory_id: str,
    entity_id: str,
    user_id: str,
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            MATCH (e:Entity {entity_id: $entity_id, user_id: $user_id})
            MERGE (m)-[:SUBJECT]->(e)
            """,
            memory_id=memory_id,
            entity_id=entity_id,
            user_id=user_id,
        )


async def _link_object(
    driver: AsyncDriver,
    *,
    memory_id: str,
    entity_id: str,
    user_id: str,
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            MATCH (e:Entity {entity_id: $entity_id, user_id: $user_id})
            MERGE (m)-[:OBJECT]->(e)
            """,
            memory_id=memory_id,
            entity_id=entity_id,
            user_id=user_id,
        )


async def _link_supersedes(
    driver: AsyncDriver,
    *,
    from_memory_id: str,
    to_memory_id: str,
    user_id: str,
) -> None:
    async with driver.session() as session:
        await session.run(
            """
            MATCH (a:Memory {memory_id: $from_id, user_id: $user_id})
            MATCH (b:Memory {memory_id: $to_id, user_id: $user_id})
            MERGE (a)-[:SUPERSEDES]->(b)
            """,
            from_id=from_memory_id,
            to_id=to_memory_id,
            user_id=user_id,
        )


async def seed_ret003_graph(driver: AsyncDriver) -> dict[str, str]:
    """Seed user A/B memories, entities, and one-hop relationships for RET-003."""
    user_entity_a = f"user:{USER_A}"
    user_entity_b = f"user:{USER_B}"

    for entity_id, user_id, name in (
        (user_entity_a, USER_A, "Current User A"),
        (user_entity_b, USER_B, "Current User B"),
        (ENTITY_SUBJECT, USER_A, "Shared Subject"),
        (ENTITY_SHARED_OBJECT, USER_A, "Shared Object"),
        (ENTITY_SHARED_OBJECT, USER_B, "Shared Object B"),
    ):
        await _create_entity(
            driver,
            entity_id=entity_id,
            user_id=user_id,
            canonical_name=name,
        )

    await _create_memory(
        driver,
        memory_id="mem-a-seed",
        user_id=USER_A,
        content="seed memory",
        subject_entity_id=ENTITY_SUBJECT,
        object_entity_id=ENTITY_SHARED_OBJECT,
        importance=0.9,
    )
    await _create_memory(
        driver,
        memory_id="mem-a-expanded-object",
        user_id=USER_A,
        content="object shared expansion",
        subject_entity_id=ENTITY_SUBJECT,
        object_entity_id=ENTITY_SHARED_OBJECT,
        importance=0.7,
        latest_source_time=120,
    )
    await _create_memory(
        driver,
        memory_id="mem-a-expanded-supersedes",
        user_id=USER_A,
        content="supersedes expansion",
        subject_entity_id=ENTITY_SUBJECT,
        object_entity_id=None,
        importance=0.95,
        latest_source_time=200,
    )
    await _create_memory(
        driver,
        memory_id="mem-b-cross-user",
        user_id=USER_B,
        content="user b only",
        subject_entity_id=ENTITY_SHARED_OBJECT,
        object_entity_id=None,
    )
    await _create_memory(
        driver,
        memory_id="mem-neo4j-only",
        user_id=USER_A,
        content="neo4j only expanded",
        subject_entity_id=ENTITY_SUBJECT,
        object_entity_id=None,
        importance=0.5,
    )

    await _link_subject(driver, memory_id="mem-a-seed", entity_id=ENTITY_SUBJECT, user_id=USER_A)
    await _link_object(
        driver,
        memory_id="mem-a-seed",
        entity_id=ENTITY_SHARED_OBJECT,
        user_id=USER_A,
    )
    await _link_subject(
        driver,
        memory_id="mem-a-expanded-object",
        entity_id=ENTITY_SUBJECT,
        user_id=USER_A,
    )
    await _link_object(
        driver,
        memory_id="mem-a-expanded-object",
        entity_id=ENTITY_SHARED_OBJECT,
        user_id=USER_A,
    )
    await _link_subject(
        driver,
        memory_id="mem-a-expanded-supersedes",
        entity_id=ENTITY_SUBJECT,
        user_id=USER_A,
    )
    await _link_subject(
        driver,
        memory_id="mem-neo4j-only",
        entity_id=ENTITY_SUBJECT,
        user_id=USER_A,
    )
    await _link_subject(
        driver,
        memory_id="mem-b-cross-user",
        entity_id=ENTITY_SHARED_OBJECT,
        user_id=USER_B,
    )
    await _link_supersedes(
        driver,
        from_memory_id="mem-a-seed",
        to_memory_id="mem-a-expanded-supersedes",
        user_id=USER_A,
    )

    return {
        "seed": "mem-a-seed",
        "expanded_object": "mem-a-expanded-object",
        "expanded_supersedes": "mem-a-expanded-supersedes",
        "neo4j_only": "mem-neo4j-only",
        "cross_user": "mem-b-cross-user",
    }
