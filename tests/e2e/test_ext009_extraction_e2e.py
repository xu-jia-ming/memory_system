"""EXT-009 E2E-1..4 using compose.test infrastructure and fake providers."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    find_extraction_task_by_archive_id,
)
from tests.e2e.conftest import Ext009Runtime, InfraStack
from tests.e2e.helpers.ext009_e2e_helpers import (
    admin_headers,
    archive_event,
    build_pipeline,
    cleanup_ext009_data,
    committed_offset,
    count_user_graph_nodes,
    count_user_index_documents,
    graph_entity_ids,
    graph_evidence_ids,
    graph_memory_ids,
    graph_relationship_counts,
    mark_task_failed_for_admin,
    new_ext009_ids,
    post_admin_rebuild,
    post_admin_retry,
    publish_event,
    run_worker_once,
    seed_archive,
    user_only_extraction_json,
    wait_for_archive_event,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e1_happy_path_commits_after_terminal(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("e2e1")
    group_id = f"ext009-e2e1-{uuid.uuid4().hex[:8]}"
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    pipeline, llm = build_pipeline(mongo_client, ext009_runtime)
    try:
        event = archive_event(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        )
        partition, offset = await publish_event(kafka_producer, event)
        assert (
            await run_worker_once(
                mongodb=mongo_client,
                bootstrap_servers=infra_stack.kafka_bootstrap,
                pipeline=pipeline,
                partition=partition,
                offset=offset,
                group_id=group_id,
            )
            == 1
        )
        task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert task is not None
        assert task.status == ExtractionTaskStatus.COMPLETED
        assert llm.call_count == 1
        assert await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Memory", user_id) == 1
        assert await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Evidence", user_id) == 1
        assert (
            await count_user_index_documents(
                ext009_runtime.elasticsearch,
                index_name=ext009_runtime.settings.memory_retrieval.index_name,
                user_id=user_id,
            )
            == 1
        )
        assert (
            await committed_offset(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                group_id=group_id,
                partition=partition,
            )
            == offset + 1
        )
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_convergence_reuses_extraction_and_graph_identities(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    hybrid_api_client: httpx.AsyncClient,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("retry")
    group_id = f"ext009-retry-{uuid.uuid4().hex[:8]}"
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    first_pipeline, first_llm = build_pipeline(
        mongo_client,
        ext009_runtime,
        embedding_fail=True,
    )
    try:
        first_event = archive_event(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        )
        first_partition, first_offset = await publish_event(kafka_producer, first_event)
        assert await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=first_pipeline,
            partition=first_partition,
            offset=first_offset,
            group_id=group_id,
        ) == 1
        failed_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert failed_task is not None
        assert failed_task.status == ExtractionTaskStatus.FAILED
        assert failed_task.last_error is not None
        assert failed_task.last_error.error_code == "retrieval_index_write_failed"
        assert first_llm.call_count == 1
        extraction_result = failed_task.extraction_result
        memory_ids_before = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
        evidence_ids_before = await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id)
        assert len(memory_ids_before) == 1
        assert len(evidence_ids_before) == 1
        assert await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        ) == 0
        assert (
            await committed_offset(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                group_id=group_id,
                partition=first_partition,
            )
            == first_offset + 1
        )

        retry_response = await post_admin_retry(hybrid_api_client, user_id, archive_id)
        assert retry_response.status_code == 200
        pending_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert pending_task is not None
        assert pending_task.status == ExtractionTaskStatus.PENDING
        assert pending_task.extraction_result == extraction_result

        retry_partition, retry_offset, retry_event = await wait_for_archive_event(
            bootstrap_servers=infra_stack.kafka_bootstrap,
            archive_id=archive_id,
            user_id=user_id,
            group_id=f"ext009-retry-capture-{uuid.uuid4().hex[:8]}",
            after_partition=first_partition,
            after_offset=first_offset,
        )
        second_pipeline, second_llm = build_pipeline(mongo_client, ext009_runtime)
        assert await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=second_pipeline,
            partition=retry_partition,
            offset=retry_offset,
            group_id=group_id,
        ) == 1
        assert retry_event.archive_id == archive_id
        completed_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert completed_task is not None
        assert completed_task.status == ExtractionTaskStatus.COMPLETED
        assert completed_task.extraction_result == extraction_result
        assert second_llm.call_count == 0
        assert await graph_memory_ids(ext009_runtime.neo4j_driver, user_id) == memory_ids_before
        assert await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id) == evidence_ids_before
        assert await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        ) == len(memory_ids_before) == 1
        for memory_id in memory_ids_before:
            assert await ext009_runtime.elasticsearch.exists(
                index=ext009_runtime.settings.memory_retrieval.index_name,
                id=memory_id,
            )
        assert (
            await committed_offset(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                group_id=group_id,
                partition=retry_partition,
            )
            == retry_offset + 1
        )
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f1_crash_after_graph_replay_preserves_graph_and_indexes(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("f1")
    group_id = f"ext009-f1-{uuid.uuid4().hex[:8]}"
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )

    async def crash_after_graph(_success: Any) -> None:
        raise RuntimeError("injected graph-to-index crash")

    first_pipeline, first_llm = build_pipeline(
        mongo_client,
        ext009_runtime,
        before_retrieval_sync_hook=crash_after_graph,
    )
    try:
        first_event = archive_event(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        )
        first_partition, first_offset = await publish_event(kafka_producer, first_event)
        with pytest.raises(RuntimeError, match="injected graph-to-index crash"):
            await run_worker_once(
                mongodb=mongo_client,
                bootstrap_servers=infra_stack.kafka_bootstrap,
                pipeline=first_pipeline,
                partition=first_partition,
                offset=first_offset,
                group_id=group_id,
            )
        crashed_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert crashed_task is not None
        assert crashed_task.status == ExtractionTaskStatus.PROCESSING
        assert crashed_task.completed_time is None
        assert first_llm.call_count == 1
        memory_ids_before = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
        evidence_ids_before = await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id)
        assert len(memory_ids_before) == 1
        assert len(evidence_ids_before) == 1
        support_count_before, entity_link_count_before = await graph_relationship_counts(
            ext009_runtime.neo4j_driver,
            user_id,
        )
        assert support_count_before == 1
        assert entity_link_count_before >= 1
        assert await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        ) == 0
        assert (
            await committed_offset(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                group_id=group_id,
                partition=first_partition,
            )
            is None
        )

        replay_event = first_event.model_copy(update={"event_id": str(uuid.uuid4())})
        replay_partition, replay_offset = await publish_event(kafka_producer, replay_event)
        replay_pipeline, replay_llm = build_pipeline(mongo_client, ext009_runtime)
        assert await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=replay_pipeline,
            partition=replay_partition,
            offset=replay_offset,
            group_id=group_id,
        ) == 1
        replay_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert replay_task is not None
        assert replay_task.status == ExtractionTaskStatus.COMPLETED
        assert replay_llm.call_count == 0
        assert await graph_memory_ids(ext009_runtime.neo4j_driver, user_id) == memory_ids_before
        assert await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id) == evidence_ids_before
        support_count_after, entity_link_count_after = await graph_relationship_counts(
            ext009_runtime.neo4j_driver,
            user_id,
        )
        assert (support_count_after, entity_link_count_after) == (
            support_count_before,
            entity_link_count_before,
        )
        assert await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        ) == len(memory_ids_before) == 1
        for memory_id in memory_ids_before:
            assert await ext009_runtime.elasticsearch.exists(
                index=ext009_runtime.settings.memory_retrieval.index_name,
                id=memory_id,
            )
        assert (
            await committed_offset(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                group_id=group_id,
                partition=replay_partition,
            )
            == replay_offset + 1
        )
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_p0_a_fresh_user_only_memory_reaches_retrieval_index(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("p0a")
    group_id = f"ext009-p0a-{uuid.uuid4().hex[:8]}"
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    pipeline, llm = build_pipeline(
        mongo_client,
        ext009_runtime,
        success_content=user_only_extraction_json(),
    )
    try:
        event = archive_event(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        )
        partition, offset = await publish_event(kafka_producer, event)
        assert (
            await run_worker_once(
                mongodb=mongo_client,
                bootstrap_servers=infra_stack.kafka_bootstrap,
                pipeline=pipeline,
                partition=partition,
                offset=offset,
                group_id=group_id,
            )
            == 1
        )
        task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert task is not None
        assert task.status == ExtractionTaskStatus.COMPLETED
        assert llm.call_count == 1

        memory_ids = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
        assert len(memory_ids) == 1
        assert await graph_entity_ids(ext009_runtime.neo4j_driver, user_id) == {
            f"user:{user_id}"
        }
        assert await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        ) == 1
        memory_id = next(iter(memory_ids))
        assert await ext009_runtime.elasticsearch.exists(
            index=ext009_runtime.settings.memory_retrieval.index_name,
            id=memory_id,
        )
        assert (
            await committed_offset(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                group_id=group_id,
                partition=partition,
            )
            == offset + 1
        )
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_p0_b_user_only_graph_replay_reindexes_missing_document(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    hybrid_api_client: httpx.AsyncClient,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("p0b")
    group_id = f"ext009-p0b-{uuid.uuid4().hex[:8]}"
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    first_pipeline, first_llm = build_pipeline(
        mongo_client,
        ext009_runtime,
        embedding_fail=True,
        success_content=user_only_extraction_json(),
    )
    try:
        first_event = archive_event(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        )
        first_partition, first_offset = await publish_event(kafka_producer, first_event)
        await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=first_pipeline,
            partition=first_partition,
            offset=first_offset,
            group_id=group_id,
        )
        first_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert first_task is not None
        assert first_task.status == ExtractionTaskStatus.FAILED
        assert first_task.last_error is not None
        assert first_task.last_error.error_code == "retrieval_index_write_failed"
        assert first_llm.call_count == 1
        memory_ids_before = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
        evidence_ids_before = await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id)
        assert len(memory_ids_before) == 1
        assert len(evidence_ids_before) == 1
        assert await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        ) == 0

        retry_response = await post_admin_retry(hybrid_api_client, user_id, archive_id)
        assert retry_response.status_code == 200
        pending_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert pending_task is not None
        assert pending_task.status == ExtractionTaskStatus.PENDING
        assert pending_task.extraction_result == first_task.extraction_result

        retry_partition, retry_offset, retry_event = await wait_for_archive_event(
            bootstrap_servers=infra_stack.kafka_bootstrap,
            archive_id=archive_id,
            user_id=user_id,
            group_id=f"ext009-p0b-capture-{uuid.uuid4().hex[:8]}",
            after_partition=first_partition,
            after_offset=first_offset,
        )
        replay_pipeline, replay_llm = build_pipeline(mongo_client, ext009_runtime)
        assert await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=replay_pipeline,
            partition=retry_partition,
            offset=retry_offset,
            group_id=group_id,
        ) == 1
        assert retry_event.archive_id == archive_id
        replay_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert replay_task is not None
        assert replay_task.status == ExtractionTaskStatus.COMPLETED
        assert replay_llm.call_count == 0
        assert await graph_memory_ids(ext009_runtime.neo4j_driver, user_id) == memory_ids_before
        assert await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id) == evidence_ids_before
        assert await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        ) == 1
        for memory_id in memory_ids_before:
            assert await ext009_runtime.elasticsearch.exists(
                index=ext009_runtime.settings.memory_retrieval.index_name,
                id=memory_id,
            )
        assert (
            await committed_offset(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                group_id=group_id,
                partition=retry_partition,
            )
            == retry_offset + 1
        )
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_p0_c_user_only_graph_replay_index_failure_never_completes(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    hybrid_api_client: httpx.AsyncClient,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("p0c")
    group_id = f"ext009-p0c-{uuid.uuid4().hex[:8]}"
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    first_pipeline, _ = build_pipeline(
        mongo_client,
        ext009_runtime,
        embedding_fail=True,
        success_content=user_only_extraction_json(),
    )
    try:
        first_event = archive_event(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        )
        first_partition, first_offset = await publish_event(kafka_producer, first_event)
        await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=first_pipeline,
            partition=first_partition,
            offset=first_offset,
            group_id=group_id,
        )
        first_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert first_task is not None
        assert first_task.status == ExtractionTaskStatus.FAILED
        memory_ids_before = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
        evidence_ids_before = await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id)

        retry_response = await post_admin_retry(hybrid_api_client, user_id, archive_id)
        assert retry_response.status_code == 200
        retry_partition, retry_offset, _ = await wait_for_archive_event(
            bootstrap_servers=infra_stack.kafka_bootstrap,
            archive_id=archive_id,
            user_id=user_id,
            group_id=f"ext009-p0c-capture-{uuid.uuid4().hex[:8]}",
            after_partition=first_partition,
            after_offset=first_offset,
        )
        replay_pipeline, replay_llm = build_pipeline(
            mongo_client,
            ext009_runtime,
            embedding_fail=True,
        )
        assert await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=replay_pipeline,
            partition=retry_partition,
            offset=retry_offset,
            group_id=group_id,
        ) == 1
        replay_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert replay_task is not None
        assert replay_task.status == ExtractionTaskStatus.FAILED
        assert replay_task.completed_time is None
        assert replay_task.last_error is not None
        assert replay_task.last_error.error_code == "retrieval_index_write_failed"
        assert replay_task.last_error.failed_stage == "retrieval_index"
        assert replay_llm.call_count == 0
        assert await graph_memory_ids(ext009_runtime.neo4j_driver, user_id) == memory_ids_before
        assert await graph_evidence_ids(ext009_runtime.neo4j_driver, user_id) == evidence_ids_before
        assert await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        ) == 0
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e2_graph_success_index_failure_is_retryable(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("e2e2")
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    pipeline, _ = build_pipeline(mongo_client, ext009_runtime, embedding_fail=True)
    try:
        event = archive_event(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        )
        partition, offset = await publish_event(kafka_producer, event)
        await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=pipeline,
            partition=partition,
            offset=offset,
        )
        task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert task is not None
        assert task.status == ExtractionTaskStatus.FAILED
        assert task.last_error is not None
        assert task.last_error.error_code == "retrieval_index_write_failed"
        assert await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Memory", user_id) == 1
        assert (
            await count_user_index_documents(
                ext009_runtime.elasticsearch,
                index_name=ext009_runtime.settings.memory_retrieval.index_name,
                user_id=user_id,
            )
            == 0
        )
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e3_completed_replay_skips_pipeline_and_is_idempotent(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("e2e3")
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    first_pipeline, first_llm = build_pipeline(mongo_client, ext009_runtime)
    try:
        event = archive_event(
            user_id=user_id,
            session_id=session_id,
            archive_id=archive_id,
        )
        partition, offset = await publish_event(kafka_producer, event)
        await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=first_pipeline,
            partition=partition,
            offset=offset,
        )
        memory_count = await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Memory", user_id)
        evidence_count = await count_user_graph_nodes(
            ext009_runtime.neo4j_driver,
            "Evidence",
            user_id,
        )
        index_count = await count_user_index_documents(
            ext009_runtime.elasticsearch,
            index_name=ext009_runtime.settings.memory_retrieval.index_name,
            user_id=user_id,
        )
        assert first_llm.call_count == 1

        replay_pipeline, replay_llm = build_pipeline(mongo_client, ext009_runtime)
        replay_event = event.model_copy(update={"event_id": str(uuid.uuid4())})
        replay_partition, replay_offset = await publish_event(kafka_producer, replay_event)
        await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=replay_pipeline,
            partition=replay_partition,
            offset=replay_offset,
        )
        assert replay_llm.call_count == 0
        assert (
            await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Memory", user_id)
            == memory_count
        )
        assert (
            await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Evidence", user_id)
            == evidence_count
        )
        assert (
            await count_user_index_documents(
                ext009_runtime.elasticsearch,
                index_name=ext009_runtime.settings.memory_retrieval.index_name,
                user_id=user_id,
            )
            == index_count
        )
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e4_admin_rebuild_uses_existing_asgi_auth_and_reprocesses(
    mongo_client: AsyncMongoClient[Any],
    hybrid_api_client: httpx.AsyncClient,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("e2e4")
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    await mark_task_failed_for_admin(
        mongo_client,
        user_id=user_id,
        archive_id=archive_id,
    )
    try:
        status_response = await hybrid_api_client.get(
            f"/api/v1/memory/extraction/{user_id}/{archive_id}",
            headers=admin_headers(),
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "failed"
        assert status_response.json()["last_error"]["error_code"] == "reconciliation_plan_conflict"
        retry_response = await post_admin_retry(hybrid_api_client, user_id, archive_id)
        assert retry_response.status_code == 409
        assert retry_response.json()["error"]["code"] == "retry_not_allowed"

        rebuild_response = await post_admin_rebuild(hybrid_api_client, user_id, archive_id)
        assert rebuild_response.status_code == 200
        assert rebuild_response.json()["status"] == "pending"
        reset_task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert reset_task is not None
        assert reset_task.status == ExtractionTaskStatus.PENDING
        assert reset_task.extraction_result is None

        partition, offset, event = await wait_for_archive_event(
            bootstrap_servers=infra_stack.kafka_bootstrap,
            archive_id=archive_id,
            user_id=user_id,
            group_id=f"ext009-e2e4-capture-{uuid.uuid4().hex[:8]}",
        )
        pipeline, llm = build_pipeline(mongo_client, ext009_runtime)
        await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=pipeline,
            partition=partition,
            offset=offset,
        )
        task = await find_extraction_task_by_archive_id(mongo_client, event.archive_id)
        assert task is not None
        assert task.status == ExtractionTaskStatus.COMPLETED
        assert llm.call_count == 1
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )
