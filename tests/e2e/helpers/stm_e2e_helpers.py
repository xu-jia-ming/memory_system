"""HTTP wrappers and cross-layer assertion helpers for STM-013 E2E."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, cast

import httpx
import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer  # type: ignore[import-untyped]
from pymongo import AsyncMongoClient

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.models.archive_created_event import ARCHIVE_CREATED_EVENT_FIELD_NAMES
from memory_system.domain.models.working_memory import WorkingMemoryMeta
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
    context_archive_from_document,
)
from memory_system.infrastructure.redis.keys import (
    compression_lock_key,
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_codec import hash_fields_to_meta
from memory_system.infrastructure.redis.working_memory_message_codec import json_to_message

TOPIC = "context.archive.created"
API_KEY = "dev-memory-api-key-change-me"
SESSION_PATH = "/api/v1/memory/session"
MESSAGE_PATH = "/api/v1/memory/working/message"


def content_for_tokens(n: int) -> str:
    """ASCII-only content where ``estimate_tokens(result) >= n``."""
    return "b" * max(n * 4, 4)


def new_test_ids(prefix: str = "stm013") -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_user_{suffix}", str(uuid.uuid4())


def default_headers(*, request_id: str | None = None) -> dict[str, str]:
    headers = {"X-API-Key": API_KEY}
    if request_id is not None:
        headers["X-Request-ID"] = request_id
    return headers


def close_path(user_id: str, session_id: str) -> str:
    return f"/api/v1/memory/session/{user_id}/{session_id}/close"


async def post_create_session(
    client: httpx.AsyncClient,
    *,
    user_id: str,
    request_id: str | None = None,
) -> httpx.Response:
    return await client.post(
        SESSION_PATH,
        json={"user_id": user_id},
        headers=default_headers(request_id=request_id),
    )


async def post_message(
    client: httpx.AsyncClient,
    *,
    user_id: str,
    session_id: str,
    message_id: str,
    content: str,
    role: str = "user",
    request_id: str | None = None,
) -> httpx.Response:
    return await client.post(
        MESSAGE_PATH,
        json={
            "message_id": message_id,
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "content": content,
        },
        headers=default_headers(request_id=request_id),
    )


async def post_close(
    client: httpx.AsyncClient,
    *,
    user_id: str,
    session_id: str,
    request_id: str | None = None,
) -> httpx.Response:
    return await client.post(
        close_path(user_id, session_id),
        headers=default_headers(request_id=request_id),
    )


async def read_wm_meta(
    redis_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> WorkingMemoryMeta | None:
    fields = await redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    if not fields:
        return None
    return hash_fields_to_meta(cast(dict[str, str], fields))


async def sum_message_tokens(
    redis_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> int:
    raw_messages = await redis_client.lrange(
        working_memory_messages_key(user_id, session_id),
        0,
        -1,
    )
    total = 0
    for raw in raw_messages:
        total += json_to_message(str(raw)).estimated_tokens
    return total


async def list_archives_for_session(
    mongo_client: AsyncMongoClient[Any],
    session_id: str,
) -> list[Any]:
    db = mongo_client.get_default_database()
    assert db is not None
    cursor = db[CONTEXT_ARCHIVE_COLLECTION].find({"session_id": session_id})
    docs: list[Any] = []
    async for doc in cursor:
        docs.append(context_archive_from_document(doc))
    return docs


async def consume_kafka_events(
    bootstrap: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    archive_id: str | None = None,
    group_id: str,
    deadline_seconds: float = 20.0,
) -> list[dict[str, Any]]:
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=int(deadline_seconds * 1000),
    )
    await consumer.start()
    matched: list[dict[str, Any]] = []
    try:
        deadline = time.time() + deadline_seconds
        while time.time() < deadline:
            batch = await consumer.getmany(timeout_ms=1000, max_records=50)
            for messages in batch.values():
                for msg in messages:
                    payload: dict[str, Any] = json.loads(msg.value.decode("utf-8"))
                    if user_id is not None and payload.get("user_id") != user_id:
                        continue
                    if session_id is not None and payload.get("session_id") != session_id:
                        continue
                    if archive_id is not None and payload.get("archive_id") != archive_id:
                        continue
                    matched.append(payload)
            if matched:
                break
            await asyncio.sleep(0.2)
        return matched
    finally:
        await consumer.stop()


def assert_archive_event_schema(event: dict[str, Any]) -> None:
    assert set(event.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert event["event_type"] == TOPIC


async def cleanup_session_data(
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    user_id: str,
    session_id: str,
) -> None:
    await redis_client.delete(
        working_memory_meta_key(user_id, session_id),
        working_memory_messages_key(user_id, session_id),
        working_memory_message_ids_key(user_id, session_id),
        compression_lock_key(user_id, session_id),
    )
    db = mongo_client.get_default_database()
    if db is not None:
        await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({"session_id": session_id})


async def seed_messages_via_http(
    client: httpx.AsyncClient,
    *,
    user_id: str,
    session_id: str,
    count: int,
    tokens_each: int = 60,
) -> None:
    """POST ``count`` moderate messages without expecting compression."""
    for _ in range(count):
        response = await post_message(
            client,
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            content=content_for_tokens(tokens_each),
        )
        assert response.status_code == 200, response.text
        assert response.json()["compression_status"] == CompressionStatus.NOT_TRIGGERED


async def write_until_compression_trigger(
    client: httpx.AsyncClient,
    redis_client: aioredis.Redis,
    *,
    user_id: str,
    session_id: str,
    trigger: int,
) -> httpx.Response:
    """POST moderate chunks until coordinator compression runs; return triggering response."""
    triggered_statuses = {
        CompressionStatus.COMPLETED,
        CompressionStatus.PARTIAL_COMPLETED,
        CompressionStatus.FAILED,
    }
    last_response: httpx.Response | None = None
    while True:
        meta = await read_wm_meta(redis_client, user_id, session_id)
        current_tokens = meta.estimated_tokens if meta is not None else 0
        chunk_tokens = min(60, max(trigger - current_tokens, 60))
        last_response = await post_message(
            client,
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            content=content_for_tokens(chunk_tokens),
        )
        assert last_response.status_code == 200, last_response.text
        compression_status = last_response.json().get("compression_status")
        if compression_status in triggered_statuses:
            return last_response
        meta_after = await read_wm_meta(redis_client, user_id, session_id)
        assert meta_after is not None
        if (
            meta_after.estimated_tokens >= trigger
            and compression_status == CompressionStatus.NOT_TRIGGERED
        ):
            continue
    assert last_response is not None
    return last_response


__all__ = [
    "API_KEY",
    "MESSAGE_PATH",
    "SESSION_PATH",
    "TOPIC",
    "assert_archive_event_schema",
    "cleanup_session_data",
    "close_path",
    "consume_kafka_events",
    "content_for_tokens",
    "default_headers",
    "estimate_tokens",
    "list_archives_for_session",
    "new_test_ids",
    "post_close",
    "post_create_session",
    "post_message",
    "read_wm_meta",
    "seed_messages_via_http",
    "sum_message_tokens",
    "write_until_compression_trigger",
]
