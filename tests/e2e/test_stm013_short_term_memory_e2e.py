"""STM-013 Short-Term Memory vertical slice E2E tests."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx
import pytest
import redis.asyncio as aioredis
from pymongo import AsyncMongoClient

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.enums.working_memory import SessionStatus
from memory_system.infrastructure.redis.keys import (
    compression_lock_key,
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from tests.e2e.conftest import FullContainerStack, InfraStack
from tests.e2e.helpers.stm_e2e_helpers import (
    assert_archive_event_schema,
    cleanup_session_data,
    consume_kafka_events,
    content_for_tokens,
    list_archives_for_session,
    new_test_ids,
    post_close,
    post_create_session,
    post_message,
    read_wm_meta,
    seed_messages_via_http,
    write_until_compression_trigger,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e1_happy_path_stm_vertical_slice(
    memory_api_client: httpx.AsyncClient,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    full_container_stack: FullContainerStack,
    authoritative_context_settings: int,
) -> None:
    user_id, session_id = new_test_ids("e1")
    trigger = authoritative_context_settings
    request_id = str(uuid.uuid4())

    try:
        create_resp = await post_create_session(
            memory_api_client,
            user_id=user_id,
            request_id=request_id,
        )
        assert create_resp.status_code == 200
        create_body = create_resp.json()
        assert create_resp.headers["X-Request-ID"] == request_id
        assert create_body["status"] == "created"
        session_id = create_body["session_id"]

        meta_after_create = await read_wm_meta(redis_client, user_id, session_id)
        assert meta_after_create is not None
        assert meta_after_create.status == SessionStatus.ACTIVE
        assert meta_after_create.compression_version == 0
        assert meta_after_create.estimated_tokens == 0

        trigger_resp = await write_until_compression_trigger(
            memory_api_client,
            redis_client,
            user_id=user_id,
            session_id=session_id,
            trigger=trigger,
        )
        trigger_body = trigger_resp.json()
        assert trigger_body["status"] == "success"
        assert trigger_body["compression_status"] in {
            CompressionStatus.COMPLETED,
            CompressionStatus.PARTIAL_COMPLETED,
        }

        meta_after_compression = await read_wm_meta(redis_client, user_id, session_id)
        assert meta_after_compression is not None
        assert meta_after_compression.compression_version == 1
        assert meta_after_compression.compressed_context.strip()
        assert meta_after_compression.pending_archive_id is None
        assert meta_after_compression.pending_archive_message_count == 0
        assert await redis_client.exists(compression_lock_key(user_id, session_id)) == 0
        assert await redis_client.llen(working_memory_messages_key(user_id, session_id)) > 0

        compression_archives = await list_archives_for_session(mongo_client, session_id)
        assert len(compression_archives) >= 1
        compression_archive = next(
            doc for doc in compression_archives if doc.base_compression_version == 0
        )
        assert compression_archive.user_id == user_id
        assert compression_archive.archive_batch_key

        kafka_events = await consume_kafka_events(
            full_container_stack.kafka_bootstrap,
            user_id=user_id,
            session_id=session_id,
            group_id=f"stm013-e1-{uuid.uuid4().hex[:8]}",
        )
        assert len(kafka_events) >= 1
        for event in kafka_events:
            assert_archive_event_schema(event)
            assert event["user_id"] == user_id
            assert event["session_id"] == session_id

        post_resp = await post_message(
            memory_api_client,
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            content="post-compression message",
        )
        assert post_resp.status_code == 200
        post_body = post_resp.json()
        assert post_body["status"] == "success"
        assert post_body["compression_status"] == CompressionStatus.NOT_TRIGGERED

        meta_after_post = await read_wm_meta(redis_client, user_id, session_id)
        assert meta_after_post is not None
        assert meta_after_post.compression_version == 1
        assert meta_after_post.estimated_tokens > meta_after_compression.estimated_tokens

        archive_count_before_close = len(await list_archives_for_session(mongo_client, session_id))

        close_resp = await post_close(
            memory_api_client,
            user_id=user_id,
            session_id=session_id,
        )
        assert close_resp.status_code == 200
        close_body = close_resp.json()
        assert close_body["status"] == "closed"
        assert close_body["archive_ids"]

        assert await redis_client.exists(working_memory_meta_key(user_id, session_id)) == 0
        assert await redis_client.exists(working_memory_messages_key(user_id, session_id)) == 0
        assert await redis_client.exists(working_memory_message_ids_key(user_id, session_id)) == 0
        assert await redis_client.exists(compression_lock_key(user_id, session_id)) == 0

        all_archives = await list_archives_for_session(mongo_client, session_id)
        assert len(all_archives) > archive_count_before_close
        close_suffix = next(
            (doc for doc in all_archives if doc.base_compression_version == 1),
            None,
        )
        assert close_suffix is not None
        assert close_suffix.archive_batch_key != compression_archive.archive_batch_key

        close_kafka = await consume_kafka_events(
            full_container_stack.kafka_bootstrap,
            user_id=user_id,
            session_id=session_id,
            archive_id=close_suffix.archive_id,
            group_id=f"stm013-e1-close-{uuid.uuid4().hex[:8]}",
        )
        if close_kafka:
            for event in close_kafka:
                assert_archive_event_schema(event)
    finally:
        await cleanup_session_data(redis_client, mongo_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2_duplicate_message_id_idempotent(
    memory_api_client: httpx.AsyncClient,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    full_container_stack: FullContainerStack,
) -> None:
    user_id, session_id = new_test_ids("e2")
    message_id = str(uuid.uuid4())

    try:
        create_resp = await post_create_session(memory_api_client, user_id=user_id)
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        events_before = await consume_kafka_events(
            full_container_stack.kafka_bootstrap,
            user_id=user_id,
            session_id=session_id,
            group_id=f"stm013-e2-before-{uuid.uuid4().hex[:8]}",
            deadline_seconds=3.0,
        )
        event_ids_before = {event["event_id"] for event in events_before}

        first_resp = await post_message(
            memory_api_client,
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            content="duplicate probe",
        )
        assert first_resp.status_code == 200
        assert first_resp.json()["status"] == "success"

        ids_after_first = await redis_client.scard(
            working_memory_message_ids_key(user_id, session_id)
        )
        messages_after_first = await redis_client.llen(
            working_memory_messages_key(user_id, session_id)
        )
        meta_first = await read_wm_meta(redis_client, user_id, session_id)
        assert meta_first is not None
        tokens_after_first = meta_first.estimated_tokens
        archive_count_after_first = len(await list_archives_for_session(mongo_client, session_id))

        second_resp = await post_message(
            memory_api_client,
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            content="duplicate probe",
        )
        assert second_resp.status_code == 200
        second_body = second_resp.json()
        assert second_body["status"] == "duplicate"
        assert second_body["compression_status"] == CompressionStatus.NOT_TRIGGERED

        assert await redis_client.scard(working_memory_message_ids_key(user_id, session_id)) == (
            ids_after_first
        )
        assert await redis_client.llen(working_memory_messages_key(user_id, session_id)) == (
            messages_after_first
        )
        meta_after_second = await read_wm_meta(redis_client, user_id, session_id)
        assert meta_after_second is not None
        assert meta_after_second.estimated_tokens == tokens_after_first
        assert len(await list_archives_for_session(mongo_client, session_id)) == (
            archive_count_after_first
        )

        events_after = await consume_kafka_events(
            full_container_stack.kafka_bootstrap,
            user_id=user_id,
            session_id=session_id,
            group_id=f"stm013-e2-after-{uuid.uuid4().hex[:8]}",
            deadline_seconds=3.0,
        )
        event_ids_after = {event["event_id"] for event in events_after}
        assert event_ids_after == event_ids_before
    finally:
        await cleanup_session_data(redis_client, mongo_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e3_concurrent_write_vs_close(
    memory_api_client: httpx.AsyncClient,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    full_container_stack: FullContainerStack,
) -> None:
    user_id, session_id = new_test_ids("e3")

    try:
        create_resp = await post_create_session(memory_api_client, user_id=user_id)
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        await post_message(
            memory_api_client,
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            content="seed message for race",
        )

        race_message_id = str(uuid.uuid4())

        async def do_write() -> httpx.Response:
            return await post_message(
                memory_api_client,
                user_id=user_id,
                session_id=session_id,
                message_id=race_message_id,
                content="race write",
            )

        async def do_close() -> httpx.Response:
            return await post_close(
                memory_api_client,
                user_id=user_id,
                session_id=session_id,
            )

        write_resp, close_resp = await asyncio.gather(do_write(), do_close())

        write_error_code = None
        if write_resp.status_code == 409:
            write_error_code = write_resp.json().get("error", {}).get("code")
        close_error_code = (
            close_resp.json().get("error", {}).get("code")
            if close_resp.status_code == 503
            else None
        )
        write_blocked = write_resp.status_code == 409 and write_error_code == "session_closing"
        close_ok_write_failed = (
            close_resp.status_code == 200
            and close_resp.json().get("status") == "closed"
            and write_resp.status_code != 200
        )
        close_incomplete = close_resp.status_code == 503 and close_error_code == "close_incomplete"
        assert write_blocked or close_ok_write_failed or close_incomplete

        assert not (
            write_resp.status_code == 200
            and write_resp.json().get("status") == "success"
            and close_resp.status_code == 200
            and close_resp.json().get("status") == "closed"
            and write_resp.json().get("message_id") == race_message_id
        )

        meta_exists = await redis_client.exists(working_memory_meta_key(user_id, session_id))
        if meta_exists:
            meta = await read_wm_meta(redis_client, user_id, session_id)
            assert meta is not None
            assert meta.status in {SessionStatus.ACTIVE, SessionStatus.CLOSING}
        else:
            assert await redis_client.exists(working_memory_messages_key(user_id, session_id)) == 0
            assert (
                await redis_client.exists(working_memory_message_ids_key(user_id, session_id))
            ) == 0

        if close_resp.status_code == 200 and close_resp.json().get("status") == "closed":
            archive_ids = close_resp.json().get("archive_ids", [])
            if archive_ids:
                suffix_id = archive_ids[-1]
                suffix_events = await consume_kafka_events(
                    full_container_stack.kafka_bootstrap,
                    user_id=user_id,
                    session_id=session_id,
                    archive_id=suffix_id,
                    group_id=f"stm013-e3-{uuid.uuid4().hex[:8]}",
                )
                for event in suffix_events:
                    assert_archive_event_schema(event)
    finally:
        await cleanup_session_data(redis_client, mongo_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e4_llm_failure_post_write_http_200_compression_failed(
    hybrid_api_client: httpx.AsyncClient,
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    infra_stack: InfraStack,
) -> None:
    user_id, session_id = new_test_ids("e4")

    try:
        create_resp = await post_create_session(hybrid_api_client, user_id=user_id)
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        meta_before = await read_wm_meta(redis_client, user_id, session_id)
        assert meta_before is not None
        version_before = meta_before.compression_version

        await seed_messages_via_http(
            hybrid_api_client,
            user_id=user_id,
            session_id=session_id,
            count=3,
            tokens_each=60,
        )
        messages_after_seed = await redis_client.llen(
            working_memory_messages_key(user_id, session_id)
        )
        assert messages_after_seed == 3

        fail_resp = await post_message(
            hybrid_api_client,
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            content=content_for_tokens(60),
        )
        assert fail_resp.status_code == 200
        fail_body = fail_resp.json()
        assert fail_body["status"] == "success"
        assert fail_body["compression_status"] == CompressionStatus.FAILED

        meta_after_fail = await read_wm_meta(redis_client, user_id, session_id)
        assert meta_after_fail is not None
        assert meta_after_fail.compression_version == version_before
        assert meta_after_fail.pending_archive_id
        assert meta_after_fail.pending_archive_message_count > 0
        messages_after_fail = await redis_client.llen(
            working_memory_messages_key(user_id, session_id)
        )
        assert messages_after_fail == messages_after_seed + 1

        pending_archive_id = meta_after_fail.pending_archive_id
        events = await consume_kafka_events(
            infra_stack.kafka_bootstrap,
            user_id=user_id,
            session_id=session_id,
            archive_id=pending_archive_id,
            group_id=f"stm013-e4-{uuid.uuid4().hex[:8]}",
        )
        assert len(events) <= 1
        for event in events:
            assert_archive_event_schema(event)
    finally:
        await cleanup_session_data(redis_client, mongo_client, user_id, session_id)
