"""Redis+Mongo integration tests for message write coordinator (STM-009 A–G, J–L)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis
from pymongo import AsyncMongoClient

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.message_write import MessageWriteInput
from memory_system.domain.models.working_memory import WorkingMemoryMeta
from memory_system.domain.services.compression_coordinator_service import (
    write_working_message_with_coordination,
)
from memory_system.domain.services.message_write_service import write_message
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
)
from memory_system.infrastructure.redis.keys import (
    compression_lock_key,
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_codec import hash_fields_to_meta
from memory_system.infrastructure.redis.working_memory_repository import (
    create_working_memory_session,
)
from memory_system.settings import get_settings

pytest_plugins = ("tests.integration.support.redis_mongo_fixtures",)

FIXED_NOW = 1_700_000_000
TOPIC = "context.archive.created"


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_settings() -> Any:
    settings = get_settings()
    return settings.model_copy(
        update={
            "context": settings.context.model_copy(
                update={
                    "compression_trigger_tokens": 200,
                    "compression_target_tokens": 80,
                    "preferred_recent_messages": 2,
                    "absolute_min_recent_messages": 2,
                    "max_archive_estimated_tokens": 5000,
                    "max_compression_rounds_per_request": 3,
                }
            )
        }
    )


@pytest.fixture
def kafka_producer_mock() -> MagicMock:
    producer = MagicMock()
    producer.send_and_wait = AsyncMock(return_value=None)
    return producer


def _new_ids() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return f"stm009_user_{suffix}", str(uuid.uuid4())


def _content_for_tokens(tokens: int) -> str:
    return "a" * max(tokens * 4, 4)


def _clock_at(offset: int) -> Callable[[], int]:
    return lambda: FIXED_NOW + offset


async def _read_meta(
    redis_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> WorkingMemoryMeta:
    fields = cast(
        dict[str, str],
        await redis_client.hgetall(working_memory_meta_key(user_id, session_id)),
    )
    return hash_fields_to_meta(fields)


async def _cleanup(
    redis_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> None:
    await redis_client.delete(
        working_memory_meta_key(user_id, session_id),
        working_memory_messages_key(user_id, session_id),
        working_memory_message_ids_key(user_id, session_id),
        compression_lock_key(user_id, session_id),
    )


async def _seed_messages(
    redis_client: aioredis.Redis,
    settings: Any,
    user_id: str,
    session_id: str,
    count: int,
    *,
    tokens_each: int = 60,
) -> list[str]:
    await create_working_memory_session(
        redis=redis_client,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )
    ids: list[str] = []
    for index in range(count):
        message_id = str(uuid.uuid4())
        ids.append(message_id)
        result = await write_message(
            redis=redis_client,
            input=MessageWriteInput(
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                role=MessageRole.USER,
                content=_content_for_tokens(tokens_each),
            ),
            context=settings.context,
            clock=_clock_at(index),
        )
        assert result.status == MessageWriteStatus.SUCCESS
    return ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_a_below_trigger_no_pending_lock(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await create_working_memory_session(
        redis=async_redis, user_id=user_id, session_id=session_id, now=FIXED_NOW
    )
    message_id = str(uuid.uuid4())
    result = await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content="small message",
        ),
        clock=lambda: FIXED_NOW,
    )
    assert result.compression_status == CompressionStatus.NOT_TRIGGERED
    meta = await _read_meta(async_redis, user_id, session_id)
    assert meta.pending_archive_id is None
    assert await async_redis.exists(compression_lock_key(user_id, session_id)) == 0
    kafka_producer_mock.send_and_wait.assert_not_awaited()
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_b_full_compression_path(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 4, tokens_each=60)
    message_id = str(uuid.uuid4())
    result = await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(
            success_content='{"compressed_context":"compressed summary"}'
        ),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 10,
    )
    assert result.status == "success"
    assert result.compression_status == CompressionStatus.COMPLETED
    kafka_producer_mock.send_and_wait.assert_awaited()
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_c_finalize_trims_head_messages(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 5, tokens_each=60)
    before_len = await async_redis.llen(working_memory_messages_key(user_id, session_id))
    message_id = str(uuid.uuid4())
    await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 20,
    )
    after_len = await async_redis.llen(working_memory_messages_key(user_id, session_id))
    assert after_len < before_len
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_d_token_accounting(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 4, tokens_each=60)
    message_id = str(uuid.uuid4())
    await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(
            success_content='{"compressed_context":"summary text here"}'
        ),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 30,
    )
    meta = await _read_meta(async_redis, user_id, session_id)
    compressed_tokens = estimate_tokens(meta.compressed_context)
    list_tokens = 0
    raw_messages = await async_redis.lrange(
        working_memory_messages_key(user_id, session_id), 0, -1
    )
    for raw in raw_messages:
        parsed = json.loads(raw)
        list_tokens += int(parsed["estimated_tokens"])
    assert meta.estimated_tokens == compressed_tokens + list_tokens
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_e_mongo_archive_document_exists(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 4, tokens_each=60)
    message_id = str(uuid.uuid4())
    await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 40,
    )
    meta = await _read_meta(async_redis, user_id, session_id)
    assert meta.pending_archive_id is None
    db = mongo_client.get_default_database()
    assert db is not None
    count = await db[CONTEXT_ARCHIVE_COLLECTION].count_documents({"session_id": session_id})
    assert count >= 1
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_f_pending_cleared_after_finalize(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 4, tokens_each=60)
    message_id = str(uuid.uuid4())
    await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 50,
    )
    meta = await _read_meta(async_redis, user_id, session_id)
    assert meta.pending_archive_id is None
    assert meta.pending_archive_message_count == 0
    assert meta.pending_archive_estimated_tokens == 0
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_g_lock_released_after_finalize(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 4, tokens_each=60)
    message_id = str(uuid.uuid4())
    await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 60,
    )
    assert await async_redis.exists(compression_lock_key(user_id, session_id)) == 0
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_j_llm_failure_pending_preserved(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 4, tokens_each=60)
    message_id = str(uuid.uuid4())
    result = await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(mode="timeout"),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 70,
    )
    assert result.compression_status == CompressionStatus.FAILED
    meta = await _read_meta(async_redis, user_id, session_id)
    assert meta.pending_archive_id
    assert meta.pending_archive_message_count > 0
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_k_concurrent_lock_one_skipped(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 4, tokens_each=60)
    await async_redis.set(compression_lock_key(user_id, session_id), "held", ex=420)
    message_id = str(uuid.uuid4())
    result = await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 80,
    )
    assert result.status == "success"
    assert result.compression_status == CompressionStatus.SKIPPED_LOCK
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_l_duplicate_no_double_finalize(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_messages(async_redis, test_settings, user_id, session_id, 4, tokens_each=60)
    message_id = str(uuid.uuid4())
    first = await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 90,
    )
    meta_after_first = await _read_meta(async_redis, user_id, session_id)
    version_after_first = meta_after_first.compression_version

    second = await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 91,
    )
    meta_after_second = await _read_meta(async_redis, user_id, session_id)
    assert first.status == "success"
    assert second.status == "duplicate"
    assert second.compression_status == CompressionStatus.NOT_TRIGGERED
    assert meta_after_second.compression_version == version_after_first
    await _cleanup(async_redis, user_id, session_id)
