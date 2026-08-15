"""Integration tests for context read against compose test Redis."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import redis
import redis.asyncio as aioredis

from memory_system.domain.enums.context_read import ContextReadStatus
from memory_system.domain.enums.working_memory import MessageRole, SessionStatus
from memory_system.domain.models.context_read import ContextReadInput
from memory_system.domain.models.message_write import MessageWriteInput
from memory_system.domain.services.context_read_service import (
    ContextReadFailure,
    read_working_memory_context,
)
from memory_system.domain.services.message_write_service import write_message
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_codec import hash_fields_to_meta
from memory_system.infrastructure.redis.working_memory_message_codec import json_to_message
from memory_system.infrastructure.redis.working_memory_repository import (
    create_working_memory_session,
)
from memory_system.settings import get_settings

_HELPER_PATH = Path(__file__).resolve().parent / "context_read_torn_read_helpers.py"
_HELPER_SPEC = importlib.util.spec_from_file_location(
    "context_read_torn_read_helpers",
    _HELPER_PATH,
)
assert _HELPER_SPEC is not None and _HELPER_SPEC.loader is not None
_torn_read_helpers = importlib.util.module_from_spec(_HELPER_SPEC)
sys.modules[_HELPER_SPEC.name] = _torn_read_helpers
_HELPER_SPEC.loader.exec_module(_torn_read_helpers)

FORBIDDEN_HYBRID = _torn_read_helpers.FORBIDDEN_HYBRID
NEW_STATE = _torn_read_helpers.NEW_STATE
OLD_STATE = _torn_read_helpers.OLD_STATE
apply_canonical_state = _torn_read_helpers.apply_canonical_state
broken_split_read_with_barrier = _torn_read_helpers.broken_split_read_with_barrier
snapshot_matches = _torn_read_helpers.snapshot_matches
toggle_canonical_state = _torn_read_helpers.toggle_canonical_state

pytest_plugins = ("tests.integration.support.redis_fixtures",)

FIXED_NOW = 1_700_000_000
I12_TOGGLE_ITERATIONS = 100


def _new_ids() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    user_id = f"ctx_read_user_{suffix}"
    session_id = str(uuid.uuid4())
    return user_id, session_id


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def context_settings() -> Any:
    return get_settings().context


def _cleanup_keys(
    sync_client: redis.Redis,
    user_id: str,
    session_id: str,
) -> None:
    keys = [
        working_memory_meta_key(user_id, session_id),
        working_memory_messages_key(user_id, session_id),
        working_memory_message_ids_key(user_id, session_id),
    ]
    sync_client.delete(*keys)


async def _create_session(
    async_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> None:
    await create_working_memory_session(
        redis=async_client,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )


async def _read(
    async_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> Any:
    return await read_working_memory_context(
        redis=async_client,
        input=ContextReadInput(user_id=user_id, session_id=session_id),
    )


async def _write_message(
    async_client: aioredis.Redis,
    context_settings: Any,
    user_id: str,
    session_id: str,
    message_id: str,
    content: str,
    role: MessageRole = MessageRole.USER,
) -> None:
    await write_message(
        redis=async_client,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=role,
            content=content,
        ),
        context=context_settings,
        clock=lambda: FIXED_NOW,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_empty_session(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I1: new session empty WM."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)

    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.SUCCESS
    assert result.snapshot is not None
    assert result.snapshot.compression_version == 0
    assert result.snapshot.compressed_context == ""
    assert result.snapshot.messages == []

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_after_message_writes(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    context_settings: Any,
) -> None:
    """I2: messages order matches List after STM-003 writes."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)

    contents = ["first message", "second message", "third message"]
    message_ids = [str(uuid.uuid4()) for _ in contents]
    for message_id, content in zip(message_ids, contents, strict=True):
        await _write_message(
            async_redis_client,
            context_settings,
            user_id,
            session_id,
            message_id,
            content,
        )

    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.SUCCESS
    assert result.snapshot is not None
    assert len(result.snapshot.messages) == 3
    for index, message in enumerate(result.snapshot.messages):
        assert message.message_id == message_ids[index]
        assert message.content == contents[index]

    messages_key = working_memory_messages_key(user_id, session_id)
    stored = cast(list[str], redis_client.lrange(messages_key, 0, -1))
    assert [m.message_id for m in result.snapshot.messages] == [
        json_to_message(item).message_id for item in stored
    ]

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_with_seeded_compression_fields(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I3: seeded compressed_context and compression_version."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)
    redis_client.hset(meta_key, "compression_version", "3")
    redis_client.hset(meta_key, "compressed_context", "seeded summary")

    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.SUCCESS
    assert result.snapshot is not None
    assert result.snapshot.compression_version == 3
    assert result.snapshot.compressed_context == "seeded summary"

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_session_not_found(
    async_redis_client: aioredis.Redis,
) -> None:
    """I4: meta key missing."""
    user_id, session_id = _new_ids()
    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.SESSION_NOT_FOUND
    assert result.snapshot is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_wrong_user_id(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I5: wrong user_id."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)

    result = await _read(async_redis_client, f"wrong_{user_id}", session_id)
    assert result.status == ContextReadStatus.SESSION_NOT_FOUND
    assert result.snapshot is None

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_wrong_session_id(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I6: wrong session_id."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)

    result = await _read(async_redis_client, user_id, str(uuid.uuid4()))
    assert result.status == ContextReadStatus.SESSION_NOT_FOUND
    assert result.snapshot is None

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_closing_status_allowed(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I7: status=closing still readable."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)
    redis_client.hset(meta_key, "status", SessionStatus.CLOSING.value)

    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.SUCCESS
    assert result.snapshot is not None

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_empty_compressed_context_string(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I8: Redis empty string compressed_context."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)
    redis_client.hset(meta_key, "compressed_context", "")

    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.SUCCESS
    assert result.snapshot is not None
    assert result.snapshot.compressed_context == ""

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_invalid_compression_version(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I9: malformed or missing compression_version."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)

    redis_client.hset(meta_key, "compression_version", "not-an-int")
    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.INVALID_SESSION_STATE

    redis_client.hdel(meta_key, "compression_version")
    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.INVALID_SESSION_STATE

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_missing_compressed_context_field(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I10: missing compressed_context field."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)
    redis_client.hdel(meta_key, "compressed_context")

    result = await _read(async_redis_client, user_id, session_id)
    assert result.status == ContextReadStatus.INVALID_SESSION_STATE
    assert result.snapshot is None

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_malformed_message_json(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I11: malformed message JSON raises ContextReadFailure."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)
    redis_client.rpush(messages_key, "not-valid-json")

    with pytest.raises(ContextReadFailure):
        await _read(async_redis_client, user_id, session_id)

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i12_part2_broken_split_reader_negative_control(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I12 Part 2: broken split-reader constructs forbidden V0+C1+M1 hybrid."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    await apply_canonical_state(
        async_redis_client,
        user_id=user_id,
        session_id=session_id,
        state=OLD_STATE,
    )

    version_read_event = asyncio.Event()
    mutator_done_event = asyncio.Event()

    async def run_mutator() -> None:
        await version_read_event.wait()
        await apply_canonical_state(
            async_redis_client,
            user_id=user_id,
            session_id=session_id,
            state=NEW_STATE,
        )
        mutator_done_event.set()

    mutator_task = asyncio.create_task(run_mutator())
    split_snapshot = await broken_split_read_with_barrier(
        async_redis_client,
        user_id=user_id,
        session_id=session_id,
        version_read_event=version_read_event,
        mutator_done_event=mutator_done_event,
    )
    await mutator_task

    assert split_snapshot.compression_version == str(OLD_STATE.compression_version)
    assert snapshot_matches(
        compression_version=split_snapshot.compression_version or "",
        compressed_context=split_snapshot.compressed_context or "",
        messages=split_snapshot.messages,
        canonical=FORBIDDEN_HYBRID,
    )
    assert not (
        snapshot_matches(
            compression_version=split_snapshot.compression_version or "",
            compressed_context=split_snapshot.compressed_context or "",
            messages=split_snapshot.messages,
            canonical=OLD_STATE,
        )
        or snapshot_matches(
            compression_version=split_snapshot.compression_version or "",
            compressed_context=split_snapshot.compressed_context or "",
            messages=split_snapshot.messages,
            canonical=NEW_STATE,
        )
    )

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i12_part3_production_lua_positive_control(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    """I12 Part 3: production Lua reader only returns OLD_STATE or NEW_STATE."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    await apply_canonical_state(
        async_redis_client,
        user_id=user_id,
        session_id=session_id,
        state=OLD_STATE,
    )

    stop_event = asyncio.Event()
    current_state = OLD_STATE

    async def toggle_loop() -> None:
        nonlocal current_state
        while not stop_event.is_set():
            current_state = await toggle_canonical_state(
                async_redis_client,
                user_id=user_id,
                session_id=session_id,
                current=current_state,
            )
            await asyncio.sleep(0)

    toggle_task = asyncio.create_task(toggle_loop())
    try:
        for _ in range(I12_TOGGLE_ITERATIONS):
            result = await _read(async_redis_client, user_id, session_id)
            if result.status == ContextReadStatus.SUCCESS:
                assert result.snapshot is not None
                assert snapshot_matches(
                    compression_version=result.snapshot.compression_version,
                    compressed_context=result.snapshot.compressed_context,
                    messages=result.snapshot.messages,
                    canonical=OLD_STATE,
                ) or snapshot_matches(
                    compression_version=result.snapshot.compression_version,
                    compressed_context=result.snapshot.compressed_context,
                    messages=result.snapshot.messages,
                    canonical=NEW_STATE,
                )
    finally:
        stop_event.set()
        await toggle_task

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_read_zero_write_side_effects(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    context_settings: Any,
) -> None:
    """I13: read path makes no Redis writes; deterministic repeated reads."""
    user_id, session_id = _new_ids()
    await _create_session(async_redis_client, user_id, session_id)
    message_id = str(uuid.uuid4())
    await _write_message(
        async_redis_client,
        context_settings,
        user_id,
        session_id,
        message_id,
        "read-only check",
    )

    meta_key = working_memory_meta_key(user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)
    message_ids_key = working_memory_message_ids_key(user_id, session_id)

    before_meta = cast(dict[str, str], redis_client.hgetall(meta_key))
    before_messages = cast(list[str], redis_client.lrange(messages_key, 0, -1))
    before_message_ids_size = redis_client.scard(message_ids_key)
    before_ttl_meta = redis_client.ttl(meta_key)
    before_ttl_messages = redis_client.ttl(messages_key)

    first = await _read(async_redis_client, user_id, session_id)
    second = await _read(async_redis_client, user_id, session_id)
    assert first.status == ContextReadStatus.SUCCESS
    assert second.status == ContextReadStatus.SUCCESS
    assert first.snapshot == second.snapshot

    after_meta = cast(dict[str, str], redis_client.hgetall(meta_key))
    after_messages = cast(list[str], redis_client.lrange(messages_key, 0, -1))
    after_message_ids_size = redis_client.scard(message_ids_key)

    assert after_meta == before_meta
    assert after_messages == before_messages
    assert after_message_ids_size == before_message_ids_size
    assert before_meta["updated_time"] == after_meta["updated_time"]
    assert before_meta["compression_version"] == after_meta["compression_version"]
    assert redis_client.ttl(meta_key) == before_ttl_meta == -1
    assert redis_client.ttl(messages_key) == before_ttl_messages == -1

    meta = hash_fields_to_meta(after_meta)
    assert meta.estimated_tokens == int(before_meta["estimated_tokens"])

    _cleanup_keys(redis_client, user_id, session_id)
