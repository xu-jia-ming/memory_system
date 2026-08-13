"""Helpers for EXT-009 extraction E2E scenarios."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx
from aiokafka import (  # type: ignore[import-untyped]
    AIOKafkaConsumer,
    AIOKafkaProducer,
    TopicPartition,
)
from elasticsearch import AsyncElasticsearch
from neo4j import AsyncDriver
from pymongo import AsyncMongoClient

from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.extraction_task import MemoryExtractionTask
from memory_system.domain.services.extraction_pipeline_port import ExtractionPipelinePort
from memory_system.domain.services.production_extraction_pipeline import (
    BeforeRetrievalSyncHook,
    create_production_extraction_pipeline,
)
from memory_system.infrastructure.kafka.archive_created_consumer import (
    create_archive_created_consumer,
    run_archive_created_consumer_loop,
)
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.mongodb import extraction_task_repository as task_repo
from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
    insert_context_archive,
)
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.settings.models import KafkaConsumerSettings
from tests.contract.helpers.extraction_llm_fake import valid_extraction_json
from tests.e2e.conftest import Ext009Runtime
from tests.support.fake_retrieval_index_embedding_client import FakeEmbeddingClient

TOPIC = "context.archive.created"
ADMIN_API_KEY = "dev-memory-admin-key-change-me"
FIXED_NOW = 1_700_000_000


def admin_headers() -> dict[str, str]:
    """Return the configured Admin API key using the existing HTTP contract."""
    return {"X-API-Key": ADMIN_API_KEY}


def new_ext009_ids(prefix: str) -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_user_{suffix}", str(uuid.uuid4()), str(uuid.uuid4())


def archive_document(
    *,
    user_id: str,
    session_id: str,
    archive_id: str,
    message_id: str = "msg_000001",
) -> dict[str, Any]:
    return {
        "archive_id": archive_id,
        "user_id": user_id,
        "session_id": session_id,
        "archive_batch_key": f"batch-{archive_id}",
        "base_compression_version": 0,
        "messages": [
            {
                "message_id": message_id,
                "role": "user",
                "content": "I am building the memory system",
                "timestamp": FIXED_NOW,
            }
        ],
        "created_time": FIXED_NOW,
    }


async def seed_archive(
    mongodb: AsyncMongoClient[Any],
    *,
    user_id: str,
    session_id: str,
    archive_id: str,
) -> None:
    await insert_context_archive(
        mongodb,
        archive_document(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        ),
    )


def archive_event(*, user_id: str, session_id: str, archive_id: str) -> ArchiveCreatedEvent:
    return ArchiveCreatedEvent(
        event_id=str(uuid.uuid4()),
        event_type=ARCHIVE_CREATED_EVENT_TYPE,
        archive_id=archive_id,
        user_id=user_id,
        session_id=session_id,
        created_time=FIXED_NOW,
    )


def user_only_extraction_json() -> str:
    """Return a valid extraction whose subject and object are both the reserved user."""
    return json.dumps(
        {
            "entities": [],
            "memories": [
                {
                    "memory_type": "fact",
                    "content": "用户与自己保持合作",
                    "subject_entity_id": "user",
                    "predicate": "collaborates_with",
                    "object_entity_id": "user",
                    "object_value": None,
                    "event_status": None,
                    "start_time": None,
                    "end_time": None,
                    "original_time_text": None,
                    "confidence": 0.91,
                    "source_message_ids": ["msg_000001"],
                }
            ],
        }
    )


def build_pipeline(
    mongodb: AsyncMongoClient[Any],
    runtime: Ext009Runtime,
    *,
    embedding_fail: bool = False,
    before_retrieval_sync_hook: BeforeRetrievalSyncHook | None = None,
    success_content: str | None = None,
) -> tuple[ExtractionPipelinePort, FakeLlmClient]:
    llm_client = FakeLlmClient(success_content=success_content or valid_extraction_json())
    pipeline = create_production_extraction_pipeline(
        mongodb,
        runtime.neo4j_driver,
        runtime.elasticsearch,
        runtime.http_client,
        runtime.settings,
        llm_client=llm_client,
        tokenize_client=FakeTokenizeClient(token_count=10),
        embedding_client=FakeEmbeddingClient(fail=embedding_fail),
        clock=lambda: FIXED_NOW,
        server_time_provider=lambda: FIXED_NOW + 10,
        before_retrieval_sync_hook=before_retrieval_sync_hook,
    )
    return pipeline, llm_client


async def publish_event(
    producer: AIOKafkaProducer,
    event: ArchiveCreatedEvent,
) -> tuple[int, int]:
    metadata = await producer.send_and_wait(
        TOPIC,
        key=event.user_id.encode("utf-8"),
        value=event.to_json_bytes(),
    )
    return metadata.partition, metadata.offset


async def wait_for_archive_event(
    *,
    bootstrap_servers: str,
    archive_id: str,
    user_id: str,
    group_id: str,
    after_partition: int | None = None,
    after_offset: int | None = None,
) -> tuple[int, int, ArchiveCreatedEvent]:
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            batch = await consumer.getmany(timeout_ms=1000, max_records=20)
            for records in batch.values():
                for record in records:
                    if (
                        after_partition is not None
                        and after_offset is not None
                        and record.partition == after_partition
                        and record.offset <= after_offset
                    ):
                        continue
                    event = ArchiveCreatedEvent.model_validate_json(record.value)
                    if event.archive_id == archive_id and event.user_id == user_id:
                        return record.partition, record.offset, event
        raise AssertionError(f"archive event not observed archive_id={archive_id}")
    finally:
        await consumer.stop()


async def run_worker_once(
    *,
    mongodb: AsyncMongoClient[Any],
    bootstrap_servers: str,
    pipeline: ExtractionPipelinePort,
    partition: int,
    offset: int,
    group_id: str | None = None,
) -> int:
    consumer = create_archive_created_consumer(
        bootstrap_servers=bootstrap_servers,
        topic=TOPIC,
        consumer_settings=KafkaConsumerSettings(),
        group_id=group_id or f"ext009-{uuid.uuid4().hex[:10]}",
    )
    await consumer.start()
    topic_partition = TopicPartition(TOPIC, partition)
    consumer.unsubscribe()
    consumer.assign([topic_partition])
    consumer.seek(topic_partition, offset)
    try:
        return await run_archive_created_consumer_loop(
            consumer=consumer,
            mongodb=mongodb,
            pipeline=pipeline,
            clock=lambda: FIXED_NOW,
            max_records=1,
            idle_deadline_monotonic=time.monotonic() + 30,
        )
    finally:
        await consumer.stop()


async def mark_task_failed_for_admin(
    mongodb: AsyncMongoClient[Any],
    *,
    user_id: str,
    archive_id: str,
) -> MemoryExtractionTask:
    from memory_system.domain.models.extraction_task import ExtractionLastError

    await task_repo.upsert_pending_extraction_task(
        mongodb,
        archive_id=archive_id,
        user_id=user_id,
        now=FIXED_NOW,
    )
    processing = await task_repo.mark_processing_from_pending(
        mongodb,
        archive_id=archive_id,
        now=FIXED_NOW,
    )
    assert processing is not None
    failed = await task_repo.mark_failed(
        mongodb,
        archive_id=archive_id,
        last_error=ExtractionLastError(
            error_code="reconciliation_plan_conflict",
            failed_stage="reconciliation",
            message="injected conflict",
        ),
        now=FIXED_NOW + 1,
    )
    return failed


async def count_user_graph_nodes(driver: AsyncDriver, label: str, user_id: str) -> int:
    async with driver.session() as session:
        result = await session.run(
            f"MATCH (node:{label} {{user_id: $user_id}}) RETURN count(node) AS count",
            user_id=user_id,
        )
        record = await result.single()
        assert record is not None
        return int(record["count"])


async def graph_memory_ids(driver: AsyncDriver, user_id: str) -> set[str]:
    async with driver.session() as session:
        result = await session.run(
            "MATCH (node:Memory {user_id: $user_id}) "
            "RETURN node.memory_id AS memory_id",
            user_id=user_id,
        )
        return {str(record["memory_id"]) async for record in result}


async def graph_evidence_ids(driver: AsyncDriver, user_id: str) -> set[str]:
    async with driver.session() as session:
        result = await session.run(
            "MATCH (node:Evidence {user_id: $user_id}) "
            "RETURN node.evidence_id AS evidence_id",
            user_id=user_id,
        )
        return {str(record["evidence_id"]) async for record in result}


async def graph_entity_ids(driver: AsyncDriver, user_id: str) -> set[str]:
    async with driver.session() as session:
        result = await session.run(
            "MATCH (node:Entity {user_id: $user_id}) "
            "RETURN node.entity_id AS entity_id",
            user_id=user_id,
        )
        return {str(record["entity_id"]) async for record in result}


async def graph_relationship_counts(driver: AsyncDriver, user_id: str) -> tuple[int, int]:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (ev:Evidence {user_id: $user_id})-[:SUPPORTS]->(memory:Memory)
            WHERE memory.user_id = $user_id
            WITH count(*) AS support_count
            MATCH (memory:Memory {user_id: $user_id})-[:SUBJECT|OBJECT]->(entity:Entity)
            WHERE entity.user_id = $user_id
            RETURN support_count, count(*) AS entity_link_count
            """,
            user_id=user_id,
        )
        record = await result.single()
        assert record is not None
        return int(record["support_count"]), int(record["entity_link_count"])


async def committed_offset(
    *,
    bootstrap_servers: str,
    group_id: str,
    partition: int,
) -> int | None:
    consumer = AIOKafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        return await consumer.committed(TopicPartition(TOPIC, partition))
    finally:
        await consumer.stop()


async def count_user_index_documents(
    elasticsearch: AsyncElasticsearch,
    *,
    index_name: str,
    user_id: str,
) -> int:
    response = await elasticsearch.count(
        index=index_name,
        query={"term": {"user_id": user_id}},
    )
    return int(response["count"])


async def cleanup_ext009_data(
    mongodb: AsyncMongoClient[Any],
    runtime: Ext009Runtime,
    *,
    user_id: str,
    archive_id: str,
) -> None:
    database = mongodb.get_default_database()
    assert database is not None
    await database[CONTEXT_ARCHIVE_COLLECTION].delete_many({"archive_id": archive_id})
    await database[task_repo.MEMORY_EXTRACTION_TASK_COLLECTION].delete_many(
        {"archive_id": archive_id}
    )
    async with runtime.neo4j_driver.session() as session:
        await session.run(
            "MATCH (node {user_id: $user_id}) DETACH DELETE node",
            user_id=user_id,
        )
    await runtime.elasticsearch.delete_by_query(
        index=runtime.settings.memory_retrieval.index_name,
        query={"term": {"user_id": user_id}},
        conflicts="proceed",
        refresh=True,
    )


async def get_admin_status(
    client: httpx.AsyncClient,
    user_id: str,
    archive_id: str,
) -> httpx.Response:
    return await client.get(
        f"/api/v1/memory/extraction/{user_id}/{archive_id}",
        headers=admin_headers(),
    )


async def post_admin_retry(
    client: httpx.AsyncClient,
    user_id: str,
    archive_id: str,
) -> httpx.Response:
    return await client.post(
        f"/api/v1/memory/extraction/{user_id}/{archive_id}/retry",
        headers=admin_headers(),
    )


async def post_admin_rebuild(
    client: httpx.AsyncClient,
    user_id: str,
    archive_id: str,
) -> httpx.Response:
    return await client.post(
        f"/api/v1/memory/extraction/{user_id}/{archive_id}/rebuild",
        headers=admin_headers(),
    )
