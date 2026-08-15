"""E2E-001 §3.32 #5 idempotency: duplicate message, Kafka replay, worker restart, admin retry."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import redis.asyncio as aioredis
from pymongo import AsyncMongoClient

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    find_extraction_task_by_archive_id,
)
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
)
from tests.e2e.conftest import Ext009Runtime, InfraStack
from tests.e2e.helpers.e2e001_helpers import (
    build_e2e001_app_client,
    build_e2e001_pipeline,
    cleanup_e2e001_data,
    create_session_via_http,
    drive_compression_succeeded,
    extraction_json_for_source,
    first_user_message_id,
    run_extraction_for_archive,
)
from tests.e2e.helpers.ext009_e2e_helpers import (
    archive_event,
    count_user_graph_nodes,
    count_user_index_documents,
    graph_evidence_ids,
    graph_memory_ids,
    post_admin_retry,
    publish_event,
    run_worker_once,
    wait_for_archive_event,
)
from tests.e2e.helpers.stm_e2e_helpers import (
    list_archives_for_session,
    new_test_ids,
    post_message,
)

pytestmark = pytest.mark.integration


async def _compress_and_extract(
    *,
    runtime: Any,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
    user_id: str,
    session_id: str,
    group_id: str,
) -> Any:
    _resp, archives = await drive_compression_succeeded(
        runtime.http_client,
        redis_client,
        mongo_client,
        user_id=user_id,
        session_id=session_id,
    )
    compression_archive = next(
        archive for archive in archives if archive.base_compression_version == 0
    )
    await run_extraction_for_archive(
        mongodb=mongo_client,
        infra_stack=infra_stack,
        ext009_runtime=ext009_runtime,
        archive=compression_archive,
        group_id=group_id,
    )
    return compression_archive


@pytest.mark.asyncio
async def test_idem_1_duplicate_message_id_then_single_extraction(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001idem1")
    session_id = ""
    duplicate_id = str(uuid.uuid4())
    async with build_e2e001_app_client(infra_stack, monkeypatch) as runtime:
        try:
            session_id = await create_session_via_http(
                runtime.http_client,
                user_id=user_id,
                request_id=str(uuid.uuid4()),
            )
            first = await post_message(
                runtime.http_client,
                user_id=user_id,
                session_id=session_id,
                message_id=duplicate_id,
                content="duplicate probe",
            )
            assert first.status_code == 200, first.text
            assert first.json()["status"] == "success"
            ids_after_first = await redis_client.scard(
                working_memory_message_ids_key(user_id, session_id)
            )
            messages_after_first = await redis_client.llen(
                working_memory_messages_key(user_id, session_id)
            )
            archives_after_first = len(await list_archives_for_session(mongo_client, session_id))

            second = await post_message(
                runtime.http_client,
                user_id=user_id,
                session_id=session_id,
                message_id=duplicate_id,
                content="duplicate probe",
            )
            assert second.status_code == 200, second.text
            assert second.json()["status"] == "duplicate"
            assert second.json()["compression_status"] == CompressionStatus.NOT_TRIGGERED
            assert (
                await redis_client.scard(working_memory_message_ids_key(user_id, session_id))
                == ids_after_first
            )
            assert (
                await redis_client.llen(working_memory_messages_key(user_id, session_id))
                == messages_after_first
            )
            assert len(await list_archives_for_session(mongo_client, session_id)) == (
                archives_after_first
            )

            await _compress_and_extract(
                runtime=runtime,
                redis_client=redis_client,
                mongo_client=mongo_client,
                infra_stack=infra_stack,
                ext009_runtime=ext009_runtime,
                user_id=user_id,
                session_id=session_id,
                group_id=f"e2e001-idem1-{uuid.uuid4().hex[:8]}",
            )
            assert (
                await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Memory", user_id) == 1
            )
            assert (
                await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Evidence", user_id)
                == 1
            )
            assert (
                await count_user_index_documents(
                    ext009_runtime.elasticsearch,
                    index_name=ext009_runtime.settings.memory_retrieval.index_name,
                    user_id=user_id,
                )
                == 1
            )
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
            )


@pytest.mark.asyncio
async def test_idem_2_replay_same_archive_event_no_duplicate_entities(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    kafka_producer: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001idem2")
    session_id = ""
    async with build_e2e001_app_client(infra_stack, monkeypatch) as runtime:
        try:
            session_id = await create_session_via_http(
                runtime.http_client,
                user_id=user_id,
                request_id=str(uuid.uuid4()),
            )
            archive = await _compress_and_extract(
                runtime=runtime,
                redis_client=redis_client,
                mongo_client=mongo_client,
                infra_stack=infra_stack,
                ext009_runtime=ext009_runtime,
                user_id=user_id,
                session_id=session_id,
                group_id=f"e2e001-idem2-{uuid.uuid4().hex[:8]}",
            )
            memory_ids = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
            evidence_ids = await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id)
            index_count = await count_user_index_documents(
                ext009_runtime.elasticsearch,
                index_name=ext009_runtime.settings.memory_retrieval.index_name,
                user_id=user_id,
            )
            replay = archive_event(
                user_id=user_id,
                session_id=session_id,
                archive_id=archive.archive_id,
            )
            partition, offset = await publish_event(kafka_producer, replay)
            source_id = first_user_message_id(archive)
            pipeline, llm = build_e2e001_pipeline(
                mongo_client,
                ext009_runtime,
                success_content=extraction_json_for_source(source_message_id=source_id),
            )
            await run_worker_once(
                mongodb=mongo_client,
                bootstrap_servers=infra_stack.kafka_bootstrap,
                pipeline=pipeline,
                partition=partition,
                offset=offset,
                group_id=f"e2e001-idem2-replay-{uuid.uuid4().hex[:8]}",
            )
            assert llm.call_count == 0
            assert await graph_memory_ids(ext009_runtime.neo4j_driver, user_id) == memory_ids
            assert await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id) == evidence_ids
            assert (
                await count_user_index_documents(
                    ext009_runtime.elasticsearch,
                    index_name=ext009_runtime.settings.memory_retrieval.index_name,
                    user_id=user_id,
                )
                == index_count
                == 1
            )
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
            )


@pytest.mark.asyncio
async def test_idem_3_crash_after_graph_second_worker_stable_identity(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    kafka_producer: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001idem3")
    session_id = ""
    group_id = f"e2e001-idem3-{uuid.uuid4().hex[:8]}"
    async with build_e2e001_app_client(infra_stack, monkeypatch) as runtime:
        try:
            session_id = await create_session_via_http(
                runtime.http_client,
                user_id=user_id,
                request_id=str(uuid.uuid4()),
            )
            _resp, archives = await drive_compression_succeeded(
                runtime.http_client,
                redis_client,
                mongo_client,
                user_id=user_id,
                session_id=session_id,
            )
            archive = next(item for item in archives if item.base_compression_version == 0)

            async def crash_after_graph(_success: Any) -> None:
                raise RuntimeError("injected graph-to-index crash")

            source_id = first_user_message_id(archive)
            first_pipeline, _ = build_e2e001_pipeline(
                mongo_client,
                ext009_runtime,
                success_content=extraction_json_for_source(source_message_id=source_id),
                before_retrieval_sync_hook=crash_after_graph,
            )
            partition, offset, first_event = await wait_for_archive_event(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                archive_id=archive.archive_id,
                user_id=user_id,
                group_id=f"e2e001-idem3-wait-{uuid.uuid4().hex[:8]}",
            )
            with pytest.raises(RuntimeError, match="injected graph-to-index crash"):
                await run_worker_once(
                    mongodb=mongo_client,
                    bootstrap_servers=infra_stack.kafka_bootstrap,
                    pipeline=first_pipeline,
                    partition=partition,
                    offset=offset,
                    group_id=group_id,
                )
            memory_ids = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
            evidence_ids = await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id)
            assert len(memory_ids) == 1
            replay_event = first_event.model_copy(update={"event_id": str(uuid.uuid4())})
            replay_partition, replay_offset = await publish_event(kafka_producer, replay_event)
            replay_pipeline, replay_llm = build_e2e001_pipeline(
                mongo_client,
                ext009_runtime,
                success_content=extraction_json_for_source(source_message_id=source_id),
            )
            assert (
                await run_worker_once(
                    mongodb=mongo_client,
                    bootstrap_servers=infra_stack.kafka_bootstrap,
                    pipeline=replay_pipeline,
                    partition=replay_partition,
                    offset=replay_offset,
                    group_id=group_id,
                )
                == 1
            )
            assert replay_llm.call_count == 0
            assert await graph_memory_ids(ext009_runtime.neo4j_driver, user_id) == memory_ids
            assert await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id) == evidence_ids
            assert (
                await count_user_index_documents(
                    ext009_runtime.elasticsearch,
                    index_name=ext009_runtime.settings.memory_retrieval.index_name,
                    user_id=user_id,
                )
                == 1
            )
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
            )


@pytest.mark.asyncio
async def test_idem_4_admin_retry_completed_does_not_duplicate(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001idem4")
    session_id = ""
    async with build_e2e001_app_client(infra_stack, monkeypatch) as runtime:
        try:
            session_id = await create_session_via_http(
                runtime.http_client,
                user_id=user_id,
                request_id=str(uuid.uuid4()),
            )
            archive = await _compress_and_extract(
                runtime=runtime,
                redis_client=redis_client,
                mongo_client=mongo_client,
                infra_stack=infra_stack,
                ext009_runtime=ext009_runtime,
                user_id=user_id,
                session_id=session_id,
                group_id=f"e2e001-idem4-{uuid.uuid4().hex[:8]}",
            )
            task = await find_extraction_task_by_archive_id(mongo_client, archive.archive_id)
            assert task is not None
            assert task.status == ExtractionTaskStatus.COMPLETED
            memory_ids = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
            retry_response = await post_admin_retry(
                runtime.http_client,
                user_id,
                archive.archive_id,
            )
            assert retry_response.status_code == 409, retry_response.text
            assert retry_response.json()["error"]["code"] == "retry_not_allowed"
            assert await graph_memory_ids(ext009_runtime.neo4j_driver, user_id) == memory_ids
            assert (
                await count_user_index_documents(
                    ext009_runtime.elasticsearch,
                    index_name=ext009_runtime.settings.memory_retrieval.index_name,
                    user_id=user_id,
                )
                == 1
            )
            still = await find_extraction_task_by_archive_id(mongo_client, archive.archive_id)
            assert still is not None
            assert still.status == ExtractionTaskStatus.COMPLETED
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
            )
