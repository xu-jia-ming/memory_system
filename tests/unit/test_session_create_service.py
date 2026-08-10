"""Unit tests for session creation service and repository."""

from __future__ import annotations

import re
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory_system.domain.enums.working_memory import SessionStatus
from memory_system.domain.services.session_service import create_session
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_codec import (
    META_HASH_FIELD_NAMES,
    hash_fields_to_meta,
)
from memory_system.infrastructure.redis.working_memory_repository import (
    create_working_memory_session,
)

UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

USER_ID = "user_001"
FIXED_NOW = 1_700_000_000


@pytest.fixture
def mock_redis() -> tuple[MagicMock, dict[str, dict[str, str]]]:
    store: dict[str, dict[str, str]] = {}

    async def hset(key: str, mapping: dict[str, str] | None = None, **kwargs: object) -> int:
        if mapping is None:
            return 0
        store[key] = dict(mapping)
        return len(mapping)

    async def hgetall(key: str) -> dict[str, str]:
        return dict(store.get(key, {}))

    client = MagicMock()
    client.hset = AsyncMock(side_effect=hset)
    client.hgetall = AsyncMock(side_effect=hgetall)
    return client, store


@pytest.mark.asyncio
async def test_create_session_generates_uuid_v4(
    mock_redis: tuple[MagicMock, dict[str, dict[str, str]]],
) -> None:
    client, _ = mock_redis
    session_id, status = await create_session(
        redis=client,
        user_id=USER_ID,
        clock=lambda: FIXED_NOW,
    )
    assert status == "created"
    assert UUID_V4_PATTERN.match(session_id)
    uuid.UUID(session_id, version=4)


@pytest.mark.asyncio
async def test_create_session_writes_meta_hash_once(
    mock_redis: tuple[MagicMock, dict[str, dict[str, str]]],
) -> None:
    client, _ = mock_redis
    session_id, _ = await create_session(
        redis=client,
        user_id=USER_ID,
        clock=lambda: FIXED_NOW,
    )
    expected_key = working_memory_meta_key(USER_ID, session_id)
    client.hset.assert_awaited_once()
    call_args = client.hset.await_args
    assert call_args is not None
    assert call_args.args[0] == expected_key
    assert call_args.kwargs["mapping"] is not None


@pytest.mark.asyncio
async def test_create_session_initial_meta_fields(
    mock_redis: tuple[MagicMock, dict[str, dict[str, str]]],
) -> None:
    client, store = mock_redis
    session_id, _ = await create_session(
        redis=client,
        user_id=USER_ID,
        clock=lambda: FIXED_NOW,
    )
    key = working_memory_meta_key(USER_ID, session_id)
    fields = store[key]
    meta = hash_fields_to_meta(fields)
    assert meta.user_id == USER_ID
    assert meta.session_id == session_id
    assert meta.status == SessionStatus.ACTIVE
    assert meta.compression_version == 0
    assert meta.compressed_context == ""
    assert meta.estimated_tokens == 0
    assert meta.pending_archive_id is None
    assert meta.pending_archive_batch_key is None
    assert meta.pending_archive_message_count == 0
    assert meta.pending_archive_estimated_tokens == 0
    assert meta.created_time == FIXED_NOW
    assert meta.updated_time == FIXED_NOW
    assert set(fields) == set(META_HASH_FIELD_NAMES)


@pytest.mark.asyncio
async def test_create_session_no_message_side_effects(
    mock_redis: tuple[MagicMock, dict[str, dict[str, str]]],
) -> None:
    client, store = mock_redis
    session_id, _ = await create_session(
        redis=client,
        user_id=USER_ID,
        clock=lambda: FIXED_NOW,
    )
    messages_key = working_memory_messages_key(USER_ID, session_id)
    message_ids_key = working_memory_message_ids_key(USER_ID, session_id)
    assert messages_key not in store
    assert message_ids_key not in store


@pytest.mark.asyncio
async def test_create_working_memory_session_propagates_redis_error() -> None:
    failing_redis = MagicMock()
    failing_redis.hset = AsyncMock(side_effect=ConnectionError("redis down"))
    with pytest.raises(ConnectionError, match="redis down"):
        await create_working_memory_session(
            redis=failing_redis,
            user_id=USER_ID,
            session_id=str(uuid.uuid4()),
            now=FIXED_NOW,
        )


@pytest.mark.asyncio
async def test_same_user_two_calls_produce_different_session_ids(
    mock_redis: tuple[MagicMock, dict[str, dict[str, str]]],
) -> None:
    client, _ = mock_redis
    session_id_a, _ = await create_session(
        redis=client,
        user_id=USER_ID,
        clock=lambda: FIXED_NOW,
    )
    session_id_b, _ = await create_session(
        redis=client,
        user_id=USER_ID,
        clock=lambda: FIXED_NOW,
    )
    assert session_id_a != session_id_b
