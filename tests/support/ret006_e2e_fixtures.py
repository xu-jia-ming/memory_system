"""RET-006 E2E aligned ES + Neo4j seeds and EXT-007 sync handoff fixtures."""

from __future__ import annotations

import uuid
from typing import Any

from elasticsearch import AsyncElasticsearch
from neo4j import AsyncDriver
from pymongo import AsyncMongoClient
from tests.support.ret002_es_fixtures import (
    FIXED_NOW as RET002_FIXED_NOW,
)
from tests.support.ret002_es_fixtures import (
    make_deterministic_embedding,
    make_memory_index_document,
)
from tests.support.ret003_neo4j_fixtures import (
    _create_entity,
    _create_memory,
    _link_object,
    _link_subject,
)

from memory_system.domain.models.entity_alignment import (
    AlignedEntity,
    EntityAlignmentSuccess,
    EntityMatchKind,
    PlannedEntityAliasMerge,
)
from memory_system.domain.models.graph_write import GraphWriteSuccess, IndexSyncMemoryEntry
from memory_system.domain.models.retrieval_index_sync import RetrievalIndexSyncInput
from memory_system.domain.services.core_search_text import build_core_search_text
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    mark_processing_from_pending,
    upsert_pending_extraction_task,
)

RET006_KEYWORD = "ret006e2ekeyword"
RET006_SEMANTIC_QUERY = f"{RET006_KEYWORD} semantic anchor"
USER_RET006_A = "user_ret006_a"
USER_RET006_B = "user_ret006_b"
MEMORY_A_PRIMARY = "mem-ret006-a-primary"
MEMORY_B_ISOLATION = "mem-ret006-b-isolation"
ENTITY_SUBJECT_A = "entity-ret006-subject-a"
ENTITY_OBJECT_A = "entity-ret006-object-a"
ENTITY_SUBJECT_B = "entity-ret006-subject-b"
FIXED_NOW = RET002_FIXED_NOW + 600


async def _create_evidence_supports(
    driver: AsyncDriver,
    *,
    evidence_id: str,
    user_id: str,
    memory_id: str,
    source_time_end: int,
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


async def seed_ret006_aligned_graph(driver: AsyncDriver) -> dict[str, str]:
    """Seed aligned Neo4j memories, entities, and Evidence for RET-006 E2E."""
    user_entity_a = f"user:{USER_RET006_A}"
    user_entity_b = f"user:{USER_RET006_B}"

    for entity_id, user_id, name in (
        (user_entity_a, USER_RET006_A, "Current User A"),
        (user_entity_b, USER_RET006_B, "Current User B"),
        (ENTITY_SUBJECT_A, USER_RET006_A, "Ret006 Subject"),
        (ENTITY_OBJECT_A, USER_RET006_A, "Ret006 Object"),
        (ENTITY_SUBJECT_B, USER_RET006_B, "Ret006 Subject B"),
    ):
        await _create_entity(
            driver,
            entity_id=entity_id,
            user_id=user_id,
            canonical_name=name,
        )

    await _create_memory(
        driver,
        memory_id=MEMORY_A_PRIMARY,
        user_id=USER_RET006_A,
        content=f"{RET006_KEYWORD} primary memory content",
        subject_entity_id=ENTITY_SUBJECT_A,
        object_entity_id=ENTITY_OBJECT_A,
        importance=0.95,
        latest_source_time=300,
    )
    await _link_subject(
        driver,
        memory_id=MEMORY_A_PRIMARY,
        entity_id=ENTITY_SUBJECT_A,
        user_id=USER_RET006_A,
    )
    await _link_object(
        driver,
        memory_id=MEMORY_A_PRIMARY,
        entity_id=ENTITY_OBJECT_A,
        user_id=USER_RET006_A,
    )

    await _create_evidence_supports(
        driver,
        evidence_id="ev-ret006-a-2",
        user_id=USER_RET006_A,
        memory_id=MEMORY_A_PRIMARY,
        source_time_end=200,
        source_message_ids=["m2", "m1"],
    )
    await _create_evidence_supports(
        driver,
        evidence_id="ev-ret006-a-1",
        user_id=USER_RET006_A,
        memory_id=MEMORY_A_PRIMARY,
        source_time_end=200,
        source_message_ids=["m3"],
    )
    await _create_evidence_supports(
        driver,
        evidence_id="ev-ret006-a-3",
        user_id=USER_RET006_A,
        memory_id=MEMORY_A_PRIMARY,
        source_time_end=100,
        source_message_ids=["m1", "m4"],
    )

    await _create_memory(
        driver,
        memory_id=MEMORY_B_ISOLATION,
        user_id=USER_RET006_B,
        content=f"{RET006_KEYWORD} {RET006_KEYWORD} isolation memory",
        subject_entity_id=ENTITY_SUBJECT_B,
        object_entity_id=None,
        importance=0.99,
        latest_source_time=500,
    )
    await _link_subject(
        driver,
        memory_id=MEMORY_B_ISOLATION,
        entity_id=ENTITY_SUBJECT_B,
        user_id=USER_RET006_B,
    )

    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            SET m.retrieval_count = 0,
                m.last_retrieved_time = null,
                m.updated_time = $updated_time
            """,
            memory_id=MEMORY_A_PRIMARY,
            user_id=USER_RET006_A,
            updated_time=FIXED_NOW,
        )
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            SET m.retrieval_count = 3,
                m.last_retrieved_time = $last_retrieved_time,
                m.updated_time = $updated_time
            """,
            memory_id=MEMORY_B_ISOLATION,
            user_id=USER_RET006_B,
            last_retrieved_time=FIXED_NOW - 500,
            updated_time=FIXED_NOW,
        )

    return {
        "primary": MEMORY_A_PRIMARY,
        "isolation": MEMORY_B_ISOLATION,
    }


async def seed_ret006_aligned_es(
    write_repo: RetrievalIndexWriteRepository,
    index_alias: str,
) -> dict[str, str]:
    """Seed ES documents aligned with Neo4j memory_id values."""
    semantic_key = RET006_SEMANTIC_QUERY
    documents = [
        make_memory_index_document(
            memory_id=MEMORY_A_PRIMARY,
            user_id=USER_RET006_A,
            memory_type="fact",
            status="active",
            search_text=f"{RET006_KEYWORD} primary indexed fact",
            embedding_key=semantic_key,
            content=f"{RET006_KEYWORD} primary memory content",
        ),
        make_memory_index_document(
            memory_id=MEMORY_B_ISOLATION,
            user_id=USER_RET006_B,
            memory_type="fact",
            status="active",
            search_text=f"{RET006_KEYWORD} {RET006_KEYWORD} isolation indexed",
            embedding_key=semantic_key,
            content=f"{RET006_KEYWORD} isolation memory",
        ),
    ]
    await write_repo.bulk_upsert(index_alias, documents)
    return {"primary": MEMORY_A_PRIMARY, "isolation": MEMORY_B_ISOLATION}


def build_ext007_entity_alignment(user_id: str) -> EntityAlignmentSuccess:
    return EntityAlignmentSuccess(
        user_id=user_id,
        alignments=[
            AlignedEntity(
                local_entity_id="user",
                entity_id=f"user:{user_id}",
                match_kind=EntityMatchKind.RESERVED_USER_EXISTING,
                entity_type="person",
                canonical_name="current_user",
                normalized_name="current_user",
                entity_key=f"user-key-{user_id}",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=[],
                    planned_aliases=[],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=False,
            ),
            AlignedEntity(
                local_entity_id="entity_1",
                entity_id="entity-ret006-project",
                match_kind=EntityMatchKind.PLANNED_CREATE,
                entity_type="project",
                canonical_name="Project",
                normalized_name="project",
                entity_key="entity-key-ret006",
                planned_alias_merge=PlannedEntityAliasMerge(
                    normalized_candidate_aliases=[],
                    existing_aliases=["Alias A"],
                    planned_aliases=["Alias A"],
                    omitted_alias_count=0,
                ),
                existing_entity=None,
                planned_create=True,
            ),
        ],
    )


async def seed_ret006_ext007_graph(
    driver: AsyncDriver,
    *,
    user_id: str,
    memory_id: str,
    content: str,
) -> str:
    """Seed Neo4j graph for EXT-007 write→retrieve (E2E-2)."""
    user_entity_id = f"user:{user_id}"
    project_entity_id = "entity-ret006-project"
    core = build_core_search_text(
        user_id=user_id,
        content=content,
        subject_entity_id=user_entity_id,
        subject_canonical_name="current_user",
        predicate="works_on",
        object_entity_id=project_entity_id,
        object_canonical_name="Project",
        object_value=None,
    )
    await _create_entity(
        driver,
        entity_id=user_entity_id,
        user_id=user_id,
        entity_type="person",
        canonical_name="current_user",
    )
    await _create_entity(
        driver,
        entity_id=project_entity_id,
        user_id=user_id,
        entity_type="project",
        canonical_name="Project",
    )
    async with driver.session() as session:
        await session.run(
            """
            MATCH (p:Entity {entity_id: $project_entity_id, user_id: $user_id})
            SET p.aliases = ['Alias A']
            """,
            user_id=user_id,
            project_entity_id=project_entity_id,
        )
    await _create_memory(
        driver,
        memory_id=memory_id,
        user_id=user_id,
        memory_type="event",
        status="active",
        content=content,
        subject_entity_id=user_entity_id,
        object_entity_id=project_entity_id,
        importance=0.8,
        latest_source_time=150,
    )
    await _link_subject(
        driver,
        memory_id=memory_id,
        entity_id=user_entity_id,
        user_id=user_id,
    )
    await _link_object(
        driver,
        memory_id=memory_id,
        entity_id=project_entity_id,
        user_id=user_id,
    )
    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            SET m.event_status = 'ongoing',
                m.retrieval_count = 0,
                m.last_retrieved_time = null,
                m.updated_time = $updated_time
            """,
            memory_id=memory_id,
            user_id=user_id,
            updated_time=FIXED_NOW,
        )
    return core


async def seed_ret006_ext007_task(
    mongo: AsyncMongoClient[Any],
    *,
    user_id: str,
    archive_id: str,
) -> None:
    await upsert_pending_extraction_task(
        mongo,
        archive_id=archive_id,
        user_id=user_id,
        now=FIXED_NOW,
    )
    task = await mark_processing_from_pending(
        mongo,
        archive_id=archive_id,
        now=FIXED_NOW + 1,
    )
    assert task is not None


def build_ext007_sync_input(
    *,
    user_id: str,
    archive_id: str,
    memory_id: str,
    core_search_text: str,
) -> RetrievalIndexSyncInput:
    return RetrievalIndexSyncInput(
        task_id=str(uuid.uuid4()),
        archive_id=archive_id,
        user_id=user_id,
        session_id="session-ret006-e2e2",
        graph_write_success=GraphWriteSuccess(
            user_id=user_id,
            archive_id=archive_id,
            skipped_graph_write=False,
            index_sync_memory_set=[
                IndexSyncMemoryEntry(
                    memory_id=memory_id,
                    core_search_text=core_search_text,
                    token_count=10,
                ),
            ],
        ),
        entity_alignment=build_ext007_entity_alignment(user_id),
    )


async def refresh_es_index(elasticsearch: AsyncElasticsearch, index_name: str) -> None:
    await elasticsearch.indices.refresh(index=index_name)


def make_ret006_query_embedding(text: str) -> list[float]:
    return make_deterministic_embedding(text)
