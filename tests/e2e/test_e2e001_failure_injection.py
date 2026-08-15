"""E2E-001 §3.28 failure injection and recovery (INJ-1..5 + INJ-SIGTERM)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import redis.asyncio as aioredis
from pymongo import AsyncMongoClient

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.enums.working_memory import SessionStatus
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    find_extraction_task_by_archive_id,
)
from tests.e2e.conftest import Ext009Runtime, InfraStack
from tests.e2e.helpers.e2e001_helpers import (
    assert_extraction_group_idle,
    assert_no_llm_http,
    assert_redis_wm_gone,
    build_e2e001_app_client,
    build_e2e001_pipeline,
    cleanup_e2e001_data,
    create_session_via_http,
    drive_compression_succeeded,
    extraction_json_for_source,
    extraction_worker_logs,
    extraction_worker_running,
    first_user_message_id,
    republish_archive,
    start_extraction_worker,
    stop_extraction_worker,
)
from tests.e2e.helpers.ext009_e2e_helpers import (
    committed_offset,
    count_user_graph_nodes,
    count_user_index_documents,
    graph_memory_ids,
    post_admin_retry,
    publish_event,
    run_worker_once,
    wait_for_archive_event,
)
from tests.e2e.helpers.stm_e2e_helpers import (
    consume_kafka_events,
    list_archives_for_session,
    new_test_ids,
    post_close,
    read_wm_meta,
)
from tests.support.e2e001_failure_doubles import (
    close_terminal_delete_fail,
    install_one_shot_production_es_bulk_failure,
    kafka_send_and_wait_fail,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_inj_1_kafka_publish_fail_then_stm011_republish(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001inj1")
    session_id = ""
    async with build_e2e001_app_client(infra_stack, monkeypatch) as runtime:
        try:
            session_id = await create_session_via_http(
                runtime.http_client,
                user_id=user_id,
                request_id=str(uuid.uuid4()),
            )
            with kafka_send_and_wait_fail(runtime.app_state.kafka_producer):
                _resp, archives = await drive_compression_succeeded(
                    runtime.http_client,
                    redis_client,
                    mongo_client,
                    user_id=user_id,
                    session_id=session_id,
                )
            archive = next(item for item in archives if item.base_compression_version == 0)
            assert archive.messages
            kafka_events = await consume_kafka_events(
                infra_stack.kafka_bootstrap,
                user_id=user_id,
                session_id=session_id,
                archive_id=archive.archive_id,
                group_id=f"e2e001-inj1-absent-{uuid.uuid4().hex[:8]}",
                deadline_seconds=3.0,
            )
            assert kafka_events == []

            event_id = await republish_archive(
                mongodb=mongo_client,
                kafka_producer=runtime.app_state.kafka_producer,
                settings=runtime.settings,
                archive_id=archive.archive_id,
                user_id=user_id,
            )
            del event_id
            source_id = first_user_message_id(archive)
            pipeline, _llm = build_e2e001_pipeline(
                mongo_client,
                ext009_runtime,
                success_content=extraction_json_for_source(source_message_id=source_id),
            )
            partition, offset, _event = await wait_for_archive_event(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                archive_id=archive.archive_id,
                user_id=user_id,
                group_id=f"e2e001-inj1-wait-{uuid.uuid4().hex[:8]}",
            )
            assert (
                await run_worker_once(
                    mongodb=mongo_client,
                    bootstrap_servers=infra_stack.kafka_bootstrap,
                    pipeline=pipeline,
                    partition=partition,
                    offset=offset,
                    group_id=f"e2e001-inj1-worker-{uuid.uuid4().hex[:8]}",
                )
                == 1
            )
            task = await find_extraction_task_by_archive_id(mongo_client, archive.archive_id)
            assert task is not None
            assert task.status == ExtractionTaskStatus.COMPLETED
            retained = await list_archives_for_session(mongo_client, session_id)
            matching = next(item for item in retained if item.archive_id == archive.archive_id)
            assert matching.messages
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
            )


@pytest.mark.asyncio
async def test_inj_2_extraction_llm_timeout_then_admin_retry(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001inj2")
    session_id = ""
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
            timeout_pipeline, _ = build_e2e001_pipeline(
                mongo_client,
                ext009_runtime,
                llm_client=FakeLlmClient(mode="timeout"),
            )
            partition, offset, first_event = await wait_for_archive_event(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                archive_id=archive.archive_id,
                user_id=user_id,
                group_id=f"e2e001-inj2-wait-{uuid.uuid4().hex[:8]}",
            )
            await run_worker_once(
                mongodb=mongo_client,
                bootstrap_servers=infra_stack.kafka_bootstrap,
                pipeline=timeout_pipeline,
                partition=partition,
                offset=offset,
                group_id=f"e2e001-inj2-timeout-{uuid.uuid4().hex[:8]}",
            )
            failed = await find_extraction_task_by_archive_id(mongo_client, archive.archive_id)
            assert failed is not None
            assert failed.status == ExtractionTaskStatus.FAILED
            assert failed.last_error is not None
            assert failed.last_error.error_code == "llm_timeout"
            retained = next(
                item
                for item in await list_archives_for_session(mongo_client, session_id)
                if item.archive_id == archive.archive_id
            )
            assert retained.messages

            retry_response = await post_admin_retry(
                runtime.http_client,
                user_id,
                archive.archive_id,
            )
            assert retry_response.status_code == 200, retry_response.text
            source_id = first_user_message_id(archive)
            success_pipeline, _ = build_e2e001_pipeline(
                mongo_client,
                ext009_runtime,
                success_content=extraction_json_for_source(source_message_id=source_id),
            )
            retry_partition, retry_offset, _retry_event = await wait_for_archive_event(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                archive_id=archive.archive_id,
                user_id=user_id,
                group_id=f"e2e001-inj2-retry-wait-{uuid.uuid4().hex[:8]}",
                after_partition=partition,
                after_offset=offset,
            )
            del first_event
            assert (
                await run_worker_once(
                    mongodb=mongo_client,
                    bootstrap_servers=infra_stack.kafka_bootstrap,
                    pipeline=success_pipeline,
                    partition=retry_partition,
                    offset=retry_offset,
                    group_id=f"e2e001-inj2-retry-{uuid.uuid4().hex[:8]}",
                )
                == 1
            )
            completed = await find_extraction_task_by_archive_id(
                mongo_client, archive.archive_id
            )
            assert completed is not None
            assert completed.status == ExtractionTaskStatus.COMPLETED
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
            )


@pytest.mark.asyncio
async def test_inj_3_production_es_bulk_fail_then_admin_retry(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001inj3")
    session_id = ""
    install_one_shot_production_es_bulk_failure(monkeypatch)
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
            source_id = first_user_message_id(archive)
            fail_pipeline, _ = build_e2e001_pipeline(
                mongo_client,
                ext009_runtime,
                success_content=extraction_json_for_source(source_message_id=source_id),
            )
            partition, offset, _event = await wait_for_archive_event(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                archive_id=archive.archive_id,
                user_id=user_id,
                group_id=f"e2e001-inj3-wait-{uuid.uuid4().hex[:8]}",
            )
            await run_worker_once(
                mongodb=mongo_client,
                bootstrap_servers=infra_stack.kafka_bootstrap,
                pipeline=fail_pipeline,
                partition=partition,
                offset=offset,
                group_id=f"e2e001-inj3-fail-{uuid.uuid4().hex[:8]}",
            )
            failed = await find_extraction_task_by_archive_id(mongo_client, archive.archive_id)
            assert failed is not None
            assert failed.status == ExtractionTaskStatus.FAILED
            assert failed.last_error is not None
            assert failed.last_error.error_code == "retrieval_index_write_failed"
            memory_ids = await graph_memory_ids(ext009_runtime.neo4j_driver, user_id)
            assert len(memory_ids) == 1
            memory_id = next(iter(memory_ids))
            assert (
                await count_user_index_documents(
                    ext009_runtime.elasticsearch,
                    index_name=ext009_runtime.settings.memory_retrieval.index_name,
                    user_id=user_id,
                )
                == 0
            )

            retry_response = await post_admin_retry(
                runtime.http_client,
                user_id,
                archive.archive_id,
            )
            assert retry_response.status_code == 200, retry_response.text
            retry_pipeline, _ = build_e2e001_pipeline(
                mongo_client,
                ext009_runtime,
                success_content=extraction_json_for_source(source_message_id=source_id),
            )
            retry_partition, retry_offset, _retry_event = await wait_for_archive_event(
                bootstrap_servers=infra_stack.kafka_bootstrap,
                archive_id=archive.archive_id,
                user_id=user_id,
                group_id=f"e2e001-inj3-retry-wait-{uuid.uuid4().hex[:8]}",
                after_partition=partition,
                after_offset=offset,
            )
            assert (
                await run_worker_once(
                    mongodb=mongo_client,
                    bootstrap_servers=infra_stack.kafka_bootstrap,
                    pipeline=retry_pipeline,
                    partition=retry_partition,
                    offset=retry_offset,
                    group_id=f"e2e001-inj3-retry-{uuid.uuid4().hex[:8]}",
                )
                == 1
            )
            completed = await find_extraction_task_by_archive_id(
                mongo_client, archive.archive_id
            )
            assert completed is not None
            assert completed.status == ExtractionTaskStatus.COMPLETED
            assert await ext009_runtime.elasticsearch.exists(
                index=ext009_runtime.settings.memory_retrieval.index_name,
                id=memory_id,
            )
            assert await graph_memory_ids(ext009_runtime.neo4j_driver, user_id) == memory_ids
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
            )


@pytest.mark.asyncio
async def test_inj_4_neo4j_commit_then_exit_second_worker_converges(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    kafka_producer: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001inj4")
    session_id = ""
    group_id = f"e2e001-inj4-{uuid.uuid4().hex[:8]}"
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
                group_id=f"e2e001-inj4-wait-{uuid.uuid4().hex[:8]}",
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
            crashed = await find_extraction_task_by_archive_id(mongo_client, archive.archive_id)
            assert crashed is not None
            assert crashed.status == ExtractionTaskStatus.PROCESSING
            assert crashed.completed_time is None
            assert await count_user_graph_nodes(
                ext009_runtime.neo4j_driver, "Memory", user_id
            ) == 1
            assert (
                await count_user_index_documents(
                    ext009_runtime.elasticsearch,
                    index_name=ext009_runtime.settings.memory_retrieval.index_name,
                    user_id=user_id,
                )
                == 0
            )
            assert (
                await committed_offset(
                    bootstrap_servers=infra_stack.kafka_bootstrap,
                    group_id=group_id,
                    partition=partition,
                )
                is None
            )

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
            completed = await find_extraction_task_by_archive_id(
                mongo_client, archive.archive_id
            )
            assert completed is not None
            assert completed.status == ExtractionTaskStatus.COMPLETED
            assert (
                await count_user_index_documents(
                    ext009_runtime.elasticsearch,
                    index_name=ext009_runtime.settings.memory_retrieval.index_name,
                    user_id=user_id,
                )
                == 1
            )
            for memory_id in await graph_memory_ids(ext009_runtime.neo4j_driver, user_id):
                assert await ext009_runtime.elasticsearch.exists(
                    index=ext009_runtime.settings.memory_retrieval.index_name,
                    id=memory_id,
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
async def test_inj_5_close_incomplete_then_retry_without_injection(
    infra_stack: InfraStack,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    ext009_runtime: Ext009Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, _ = new_test_ids("e2e001inj5")
    session_id = ""
    async with build_e2e001_app_client(infra_stack, monkeypatch) as runtime:
        try:
            session_id = await create_session_via_http(
                runtime.http_client,
                user_id=user_id,
                request_id=str(uuid.uuid4()),
            )
            _resp, compression_archives = await drive_compression_succeeded(
                runtime.http_client,
                redis_client,
                mongo_client,
                user_id=user_id,
                session_id=session_id,
            )
            compression_ids = {item.archive_id for item in compression_archives}
            with close_terminal_delete_fail():
                first_close = await post_close(
                    runtime.http_client,
                    user_id=user_id,
                    session_id=session_id,
                    request_id=str(uuid.uuid4()),
                )
            assert first_close.status_code == 503, first_close.text
            assert first_close.json()["error"]["code"] == "close_incomplete"
            meta_closing = await read_wm_meta(redis_client, user_id, session_id)
            assert meta_closing is not None
            assert meta_closing.status == SessionStatus.CLOSING
            after_first = await list_archives_for_session(mongo_client, session_id)
            close_archives = [
                item for item in after_first if item.archive_id not in compression_ids
            ]
            assert close_archives, "close must persist at least one Archive before terminal fail"
            close_ids = {item.archive_id for item in close_archives}
            close_keys = {item.archive_batch_key for item in close_archives}

            second_close = await post_close(
                runtime.http_client,
                user_id=user_id,
                session_id=session_id,
                request_id=str(uuid.uuid4()),
            )
            assert second_close.status_code == 200, second_close.text
            assert second_close.json()["status"] == "closed"
            after_second = await list_archives_for_session(mongo_client, session_id)
            close_after = [
                item for item in after_second if item.archive_id not in compression_ids
            ]
            assert {item.archive_id for item in close_after} == close_ids
            assert {item.archive_batch_key for item in close_after} == close_keys
            await assert_redis_wm_gone(redis_client, user_id, session_id)
        finally:
            await cleanup_e2e001_data(
                redis_client,
                mongo_client,
                ext009_runtime,
                user_id=user_id,
                session_id=session_id or "missing",
            )


@pytest.mark.asyncio
async def test_inj_sigterm_idle_extraction_worker(
    infra_stack: InfraStack,
) -> None:
    await assert_extraction_group_idle(infra_stack.kafka_bootstrap)
    if extraction_worker_running():
        stop_extraction_worker()
        assert not extraction_worker_running()
    try:
        start_extraction_worker()
        assert extraction_worker_running()
        stop_extraction_worker()
        assert not extraction_worker_running()
        assert_no_llm_http(extraction_worker_logs())
    finally:
        if extraction_worker_running():
            stop_extraction_worker()
        assert not extraction_worker_running()
