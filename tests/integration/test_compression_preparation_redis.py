"""Redis integration tests for compression preparation (no Kafka broker dependency)."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from typing import cast
from unittest.mock import AsyncMock

import pytest
import redis
import redis.asyncio as aioredis

from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.domain.enums.working_memory import SessionStatus
from memory_system.domain.models.compression_preparation import CompressionPreparationInput
from memory_system.domain.models.working_memory import WorkingMemoryMeta
from memory_system.domain.services.compression_preparation_service import (
    prepare_pending_archive_and_publish,
)
from memory_system.infrastructure.redis.compression_lock_repository import (
    acquire_compression_lock,
    release_compression_lock,
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

pytest_plugins = ("tests.integration.support.redis_fixtures",)

FIXED_NOW = 1_700_000_000
TOPIC = "context.archive.created"
TTL = 420


def _new_ids() -> tuple[str, str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    user_id = f"stm006_user_{suffix}"
    session_id = str(uuid.uuid4())
    archive_id = str(uuid.uuid4())
    batch_key = f"{session_id}:msg-a:msg-b"
    return user_id, session_id, archive_id, batch_key


def _input(
    user_id: str,
    session_id: str,
    archive_id: str,
    batch_key: str,
    *,
    count: int = 2,
    tokens: int = 50,
    lock_owner_token: str | None = None,
) -> CompressionPreparationInput:
    return CompressionPreparationInput(
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
        archive_batch_key=batch_key,
        pending_archive_message_count=count,
        pending_archive_estimated_tokens=tokens,
        lock_owner_token=lock_owner_token,
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _cleanup(
    sync_client: redis.Redis,
    user_id: str,
    session_id: str,
) -> None:
    sync_client.delete(
        working_memory_meta_key(user_id, session_id),
        working_memory_messages_key(user_id, session_id),
        working_memory_message_ids_key(user_id, session_id),
        compression_lock_key(user_id, session_id),
    )


async def _seed_session(
    async_client: aioredis.Redis,
    user_id: str,
    session_id: str,
    *,
    status: SessionStatus = SessionStatus.ACTIVE,
    compression_version: int = 7,
    message_count: int = 2,
) -> None:
    await create_working_memory_session(
        redis=async_client,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )
    meta_key = working_memory_meta_key(user_id, session_id)
    await async_client.hset(meta_key, mapping={"compression_version": str(compression_version)})
    if status != SessionStatus.ACTIVE:
        await async_client.hset(meta_key, mapping={"status": status.value})
    messages_key = working_memory_messages_key(user_id, session_id)
    for i in range(message_count):
        await async_client.rpush(messages_key, json.dumps({"message_id": f"m{i}"}))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_fresh_lock_pending_success(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )

    assert result.status == CompressionPreparationStatus.SUCCESS
    assert result.lock_owner_token is not None
    assert await async_redis_client.get(compression_lock_key(user_id, session_id)) == (
        result.lock_owner_token
    )
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    meta: WorkingMemoryMeta = hash_fields_to_meta(cast(dict[str, str], fields))
    assert meta.pending_archive_id == archive_id
    assert meta.pending_archive_batch_key == batch_key
    assert meta.pending_archive_message_count == 2
    assert meta.pending_archive_estimated_tokens == 50
    mock_producer.send_and_wait.assert_awaited_once()
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_missing_session(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
    )

    assert result.status == CompressionPreparationStatus.SESSION_NOT_FOUND
    assert await async_redis_client.get(compression_lock_key(user_id, session_id)) is None
    mock_producer.send_and_wait.assert_not_awaited()
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_session_closing(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(
        async_redis_client, user_id, session_id, status=SessionStatus.CLOSING
    )
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
    )

    assert result.status == CompressionPreparationStatus.SESSION_CLOSING
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_id"] == ""
    mock_producer.send_and_wait.assert_not_awaited()
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_lock_contention(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    mock_a = AsyncMock()
    mock_a.send_and_wait = AsyncMock(return_value=None)
    mock_b = AsyncMock()
    mock_b.send_and_wait = AsyncMock()

    first = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_a,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    second = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_b,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )

    assert first.status == CompressionPreparationStatus.SUCCESS
    assert second.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED
    mock_b.send_and_wait.assert_not_awaited()
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_same_archive_idempotent_with_accounting(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    first = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key, count=2, tokens=50),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert first.status == CompressionPreparationStatus.SUCCESS
    assert first.lock_owner_token is not None

    second = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(
            user_id,
            session_id,
            archive_id,
            batch_key,
            count=2,
            tokens=50,
            lock_owner_token=first.lock_owner_token,
        ),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert second.status == CompressionPreparationStatus.SUCCESS
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_id"] == archive_id
    assert fields["pending_archive_message_count"] == "2"
    assert fields["pending_archive_estimated_tokens"] == "50"
    assert mock_producer.send_and_wait.await_count == 2
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5b_same_identity_inconsistent_accounting_fail_closed(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    first = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key, count=2, tokens=50),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert first.lock_owner_token is not None

    conflict = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(
            user_id,
            session_id,
            archive_id,
            batch_key,
            count=2,
            tokens=99,
            lock_owner_token=first.lock_owner_token,
        ),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert conflict.status == CompressionPreparationStatus.PENDING_CONFLICT
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_estimated_tokens"] == "50"
    assert mock_producer.send_and_wait.await_count == 1
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_conflicting_pending(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    other_archive = str(uuid.uuid4())
    await _seed_session(async_redis_client, user_id, session_id)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    first = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert first.lock_owner_token is not None

    conflict = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(
            user_id,
            session_id,
            other_archive,
            f"{session_id}:x:y",
            lock_owner_token=first.lock_owner_token,
        ),
        lock_ttl_seconds=TTL,
    )
    assert conflict.status == CompressionPreparationStatus.PENDING_CONFLICT
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_id"] == archive_id
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i7_malformed_pending(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)
    await async_redis_client.hset(
        meta_key,
        mapping={
            "pending_archive_id": "half-filled",
            "pending_archive_batch_key": "",
            "pending_archive_message_count": "0",
            "pending_archive_estimated_tokens": "0",
        },
    )
    token = await acquire_compression_lock(
        async_redis_client,
        user_id=user_id,
        session_id=session_id,
        ttl_seconds=TTL,
    )
    assert token is not None
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key, lock_owner_token=token),
        lock_ttl_seconds=TTL,
    )
    assert result.status == CompressionPreparationStatus.INVALID_SESSION_STATE
    mock_producer.send_and_wait.assert_not_awaited()
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i9_no_compression_version_bump(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id, compression_version=42)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert result.status == CompressionPreparationStatus.SUCCESS
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["compression_version"] == "42"
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i10_no_message_trim(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id, message_count=5)
    before = await async_redis_client.llen(working_memory_messages_key(user_id, session_id))
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert result.status == CompressionPreparationStatus.SUCCESS
    after = await async_redis_client.llen(working_memory_messages_key(user_id, session_id))
    assert after == before == 5
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i12_concurrent_contenders(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)

    async def _run() -> CompressionPreparationStatus:
        producer = AsyncMock()
        producer.send_and_wait = AsyncMock(return_value=None)
        result = await prepare_pending_archive_and_publish(
            redis=async_redis_client,
            kafka_producer=producer,
            topic=TOPIC,
            input=_input(user_id, session_id, archive_id, batch_key),
            lock_ttl_seconds=TTL,
            clock=lambda: FIXED_NOW,
        )
        return result.status

    statuses = await asyncio.gather(_run(), _run(), _run())
    assert statuses.count(CompressionPreparationStatus.SUCCESS) == 1
    assert statuses.count(CompressionPreparationStatus.LOCK_NOT_ACQUIRED) == 2
    lock_val = await async_redis_client.get(compression_lock_key(user_id, session_id))
    assert lock_val is not None
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i13_stale_preheld_zero_side_effect(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    token_a = "token-owner-a"
    token_b = "token-owner-b"
    lock_key = compression_lock_key(user_id, session_id)
    await async_redis_client.set(lock_key, token_a, ex=TTL)
    # Replace with owner B
    await async_redis_client.set(lock_key, token_b, ex=TTL)
    # Pre-seed pending under B's successful write path
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)
    ok = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(
            user_id, session_id, archive_id, batch_key, lock_owner_token=token_b
        ),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert ok.status == CompressionPreparationStatus.SUCCESS
    publish_count = mock_producer.send_and_wait.await_count

    stale = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(
            user_id, session_id, archive_id, batch_key, lock_owner_token=token_a
        ),
        lock_ttl_seconds=TTL,
    )
    assert stale.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED
    assert mock_producer.send_and_wait.await_count == publish_count
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_id"] == archive_id
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i14_expired_preheld_zero_side_effect(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(
            user_id, session_id, archive_id, batch_key, lock_owner_token="old-expired"
        ),
        lock_ttl_seconds=TTL,
    )
    assert result.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_id"] == ""
    mock_producer.send_and_wait.assert_not_awaited()
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i15_valid_preheld(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    token = await acquire_compression_lock(
        async_redis_client,
        user_id=user_id,
        session_id=session_id,
        ttl_seconds=TTL,
    )
    assert token is not None
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(
            user_id, session_id, archive_id, batch_key, lock_owner_token=token
        ),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert result.status == CompressionPreparationStatus.SUCCESS
    mock_producer.send_and_wait.assert_awaited_once()
    await release_compression_lock(
        async_redis_client, user_id=user_id, session_id=session_id, token=token
    )
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_r1_publish_failed_pending_survives(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(side_effect=RuntimeError("inject fail"))

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=TTL,
        clock=lambda: FIXED_NOW,
    )
    assert result.status == CompressionPreparationStatus.PUBLISH_FAILED
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_id"] == archive_id
    assert fields["pending_archive_batch_key"] == batch_key
    assert result.lock_owner_token is not None
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_r4_pending_readable_after_lock_expiry(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id, batch_key = _new_ids()
    await _seed_session(async_redis_client, user_id, session_id)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock(return_value=None)

    result = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(user_id, session_id, archive_id, batch_key),
        lock_ttl_seconds=2,
        clock=lambda: FIXED_NOW,
    )
    assert result.status == CompressionPreparationStatus.SUCCESS
    await async_redis_client.delete(compression_lock_key(user_id, session_id))
    fields = await async_redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    assert fields["pending_archive_id"] == archive_id
    assert fields["pending_archive_batch_key"] == batch_key
    # STM-006 must not allow unlocked republish
    blocked = await prepare_pending_archive_and_publish(
        redis=async_redis_client,
        kafka_producer=mock_producer,
        topic=TOPIC,
        input=_input(
            user_id,
            session_id,
            archive_id,
            batch_key,
            lock_owner_token=result.lock_owner_token,
        ),
        lock_ttl_seconds=TTL,
    )
    assert blocked.status == CompressionPreparationStatus.LOCK_NOT_ACQUIRED
    _cleanup(redis_client, user_id, session_id)
