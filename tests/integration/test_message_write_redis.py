"""Integration tests for message write against compose test Redis."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import redis
import redis.asyncio as aioredis

from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.enums.working_memory import MessageRole, SessionStatus
from memory_system.domain.models.message_write import MessageWriteInput
from memory_system.domain.services.message_write_service import write_message
from memory_system.domain.services.token_estimator import estimate_tokens
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

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
REDIS_CONTAINER = "memory-system-redis-test"

FIXED_NOW = 1_700_000_000


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


def _compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env["PROXY__HTTP_URL"] = ""
    return env


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(COMPOSE_SH), "--stack=test", "--embedding=none", *args]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_compose_env(),
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"compose failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _ensure_dotenv() -> None:
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def _assert_test_isolation() -> None:
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT


def _redis_container_ip() -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            REDIS_CONTAINER,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


def _ascii_content_for_tokens(token_count: int) -> str:
    return "a" * (4 * token_count)


def _new_ids() -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    user_id = f"msg_write_user_{suffix}"
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    return user_id, session_id, message_id


@pytest.fixture(scope="module")
def test_redis() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available")
    _ensure_dotenv()
    _assert_test_isolation()
    _compose("up", "-d", "redis")
    deadline = time.time() + 60
    while time.time() < deadline:
        ip = _redis_container_ip()
        if ip:
            break
        time.sleep(2)
    else:
        pytest.skip("Test Redis container did not become ready in time")
    ip = _redis_container_ip()
    if not ip:
        pytest.skip("Could not resolve test Redis container IP")
    yield f"redis://{ip}:6379/0"
    _compose("down", check=False)


@pytest.fixture
def async_redis_client(test_redis: str) -> Iterator[aioredis.Redis]:
    client = aioredis.from_url(test_redis, decode_responses=True)
    yield client


@pytest.fixture
def redis_client(test_redis: str) -> Iterator[redis.Redis]:
    client = redis.from_url(test_redis, decode_responses=True)
    yield client
    client.close()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def context_settings() -> Any:
    return get_settings().context


async def _create_active_session(
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


async def _write(
    async_client: aioredis.Redis,
    context_settings: Any,
    user_id: str,
    session_id: str,
    message_id: str,
    content: str = "hello",
    role: MessageRole = MessageRole.USER,
) -> Any:
    return await write_message(
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
async def test_message_write_success_and_redis_state(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    context_settings: Any,
) -> None:
    user_id, session_id, message_id = _new_ids()
    content = "integration hello"
    message_tokens = estimate_tokens(content)
    await _create_active_session(async_redis_client, user_id, session_id)

    # scenario 1: success
    result = await _write(
        async_redis_client,
        context_settings,
        user_id,
        session_id,
        message_id,
        content=content,
    )
    assert result.status == MessageWriteStatus.SUCCESS

    # scenario 2: messages list
    messages_key = working_memory_messages_key(user_id, session_id)
    assert redis_client.llen(messages_key) == 1
    stored_json = redis_client.lindex(messages_key, 0)
    assert stored_json is not None
    stored_message = json_to_message(str(stored_json))
    assert stored_message.message_id == message_id
    assert stored_message.content == content
    assert stored_message.estimated_tokens == message_tokens

    # scenario 3: message_ids set
    message_ids_key = working_memory_message_ids_key(user_id, session_id)
    assert redis_client.sismember(message_ids_key, message_id) == 1

    # scenario 4: meta updated
    meta_key = working_memory_meta_key(user_id, session_id)
    fields = cast(dict[str, str], redis_client.hgetall(meta_key))
    meta = hash_fields_to_meta(fields)
    assert meta.estimated_tokens == message_tokens
    assert meta.updated_time == FIXED_NOW
    assert result.estimated_tokens == message_tokens
    assert result.message_estimated_tokens == message_tokens

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_message_write_duplicate_zero_side_effect(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    context_settings: Any,
) -> None:
    user_id, session_id, message_id = _new_ids()
    await _create_active_session(async_redis_client, user_id, session_id)
    first = await _write(async_redis_client, context_settings, user_id, session_id, message_id)
    assert first.status == MessageWriteStatus.SUCCESS

    messages_key = working_memory_messages_key(user_id, session_id)
    message_ids_key = working_memory_message_ids_key(user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)
    list_len = redis_client.llen(messages_key)
    set_size = redis_client.scard(message_ids_key)
    tokens_before = redis_client.hget(meta_key, "estimated_tokens")
    updated_before = redis_client.hget(meta_key, "updated_time")

    # scenario 5: duplicate
    second = await _write(async_redis_client, context_settings, user_id, session_id, message_id)
    assert second.status == MessageWriteStatus.DUPLICATE

    # scenario 6: zero side effect
    assert redis_client.llen(messages_key) == list_len
    assert redis_client.scard(message_ids_key) == set_size
    assert redis_client.hget(meta_key, "estimated_tokens") == tokens_before
    assert redis_client.hget(meta_key, "updated_time") == updated_before

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_message_too_large_no_redis_growth(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, message_id = _new_ids()
    await _create_active_session(async_redis_client, user_id, session_id)
    context = get_settings().context.model_copy(update={"max_message_estimated_tokens": 5})
    content = _ascii_content_for_tokens(6)

    # scenario 7
    result = await write_message(
        redis=async_redis_client,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=content,
        ),
        context=context,
        clock=lambda: FIXED_NOW,
    )
    assert result.status == MessageWriteStatus.MESSAGE_TOO_LARGE
    messages_key = working_memory_messages_key(user_id, session_id)
    message_ids_key = working_memory_message_ids_key(user_id, session_id)
    assert redis_client.exists(messages_key) == 0
    assert redis_client.exists(message_ids_key) == 0

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_capacity_exceeded_no_partial_write(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, message_id = _new_ids()
    await _create_active_session(async_redis_client, user_id, session_id)
    max_wm = 100
    context = get_settings().context.model_copy(
        update={"max_working_memory_estimated_tokens": max_wm}
    )
    meta_key = working_memory_meta_key(user_id, session_id)
    redis_client.hset(meta_key, "estimated_tokens", str(max_wm - 1))

    # scenario 8
    result = await write_message(
        redis=async_redis_client,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=_ascii_content_for_tokens(2),
        ),
        context=context,
        clock=lambda: FIXED_NOW,
    )
    assert result.status == MessageWriteStatus.CAPACITY_EXCEEDED
    messages_key = working_memory_messages_key(user_id, session_id)
    assert redis_client.llen(messages_key) == 0
    assert redis_client.hget(meta_key, "estimated_tokens") == str(max_wm - 1)

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_not_found_and_closing(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    context_settings: Any,
) -> None:
    user_id, session_id, message_id = _new_ids()

    # scenario 9: meta missing
    missing = await _write(async_redis_client, context_settings, user_id, session_id, message_id)
    assert missing.status == MessageWriteStatus.SESSION_NOT_FOUND

    await _create_active_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)
    redis_client.hset(meta_key, "status", SessionStatus.CLOSING.value)

    # scenario 10: closing
    closing = await _write(
        async_redis_client,
        context_settings,
        user_id,
        session_id,
        str(uuid.uuid4()),
    )
    assert closing.status == MessageWriteStatus.SESSION_CLOSING
    messages_key = working_memory_messages_key(user_id, session_id)
    assert redis_client.llen(messages_key) == 0

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_isolation_session_not_found(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    context_settings: Any,
) -> None:
    user_a, session_id, _ = _new_ids()
    user_b = f"other_user_{uuid.uuid4().hex[:8]}"
    await _create_active_session(async_redis_client, user_a, session_id)

    # scenario 11
    result = await _write(
        async_redis_client,
        context_settings,
        user_b,
        session_id,
        str(uuid.uuid4()),
    )
    assert result.status == MessageWriteStatus.SESSION_NOT_FOUND
    meta_key = working_memory_meta_key(user_a, session_id)
    assert redis_client.hget(meta_key, "estimated_tokens") == "0"

    _cleanup_keys(redis_client, user_a, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_same_message_id_one_success(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    context_settings: Any,
) -> None:
    user_id, session_id, message_id = _new_ids()
    await _create_active_session(async_redis_client, user_id, session_id)

    # scenario 12
    results = await asyncio.gather(
        _write(async_redis_client, context_settings, user_id, session_id, message_id),
        _write(async_redis_client, context_settings, user_id, session_id, message_id),
        _write(async_redis_client, context_settings, user_id, session_id, message_id),
        _write(async_redis_client, context_settings, user_id, session_id, message_id),
    )
    statuses = [r.status for r in results]
    assert statuses.count(MessageWriteStatus.SUCCESS) == 1
    assert statuses.count(MessageWriteStatus.DUPLICATE) == 3
    messages_key = working_memory_messages_key(user_id, session_id)
    assert redis_client.llen(messages_key) == 1

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_atomic_failure_preserves_state(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, message_id = _new_ids()
    await _create_active_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)
    message_ids_key = working_memory_message_ids_key(user_id, session_id)

    list_len = redis_client.llen(messages_key)
    set_size = redis_client.scard(message_ids_key)
    updated = redis_client.hget(meta_key, "updated_time")

    context = get_settings().context.model_copy(update={"max_working_memory_estimated_tokens": 1})
    redis_client.hset(meta_key, "estimated_tokens", "1")
    tokens_after_prefill = redis_client.hget(meta_key, "estimated_tokens")

    # scenario 13: capacity failure
    cap_result = await write_message(
        redis=async_redis_client,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content="hello",
        ),
        context=context,
        clock=lambda: FIXED_NOW,
    )
    assert cap_result.status == MessageWriteStatus.CAPACITY_EXCEEDED
    assert redis_client.llen(messages_key) == list_len
    assert redis_client.scard(message_ids_key) == set_size
    assert redis_client.hget(meta_key, "estimated_tokens") == tokens_after_prefill
    assert redis_client.hget(meta_key, "updated_time") == updated

    redis_client.hset(meta_key, "status", SessionStatus.CLOSING.value)
    closing_result = await write_message(
        redis=async_redis_client,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content="hello",
        ),
        context=context,
        clock=lambda: FIXED_NOW,
    )
    assert closing_result.status == MessageWriteStatus.SESSION_CLOSING
    assert redis_client.llen(messages_key) == list_len

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exact_boundary_max_message_and_max_wm(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    max_message = 50
    max_wm = 200
    context = get_settings().context.model_copy(
        update={
            "max_message_estimated_tokens": max_message,
            "max_working_memory_estimated_tokens": max_wm,
        }
    )
    user_id, session_id, message_id = _new_ids()
    await _create_active_session(async_redis_client, user_id, session_id)

    # scenario 14: tokens == max_message
    boundary_content = _ascii_content_for_tokens(max_message)
    boundary_result = await write_message(
        redis=async_redis_client,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            role=MessageRole.USER,
            content=boundary_content,
        ),
        context=context,
        clock=lambda: FIXED_NOW,
    )
    assert boundary_result.status == MessageWriteStatus.SUCCESS

    meta_key = working_memory_meta_key(user_id, session_id)
    redis_client.hset(meta_key, "estimated_tokens", str(max_wm - max_message))

    # scenario 15: new_total == max_wm
    second_id = str(uuid.uuid4())
    second_result = await write_message(
        redis=async_redis_client,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=second_id,
            role=MessageRole.USER,
            content=boundary_content,
        ),
        context=context,
        clock=lambda: FIXED_NOW,
    )
    assert second_result.status == MessageWriteStatus.SUCCESS
    assert redis_client.hget(meta_key, "estimated_tokens") == str(max_wm)

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_malformed_estimated_tokens_fail_closed(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
    context_settings: Any,
) -> None:
    user_id, session_id, message_id = _new_ids()
    await _create_active_session(async_redis_client, user_id, session_id)
    meta_key = working_memory_meta_key(user_id, session_id)

    # scenario 16: malformed field
    redis_client.hset(meta_key, "estimated_tokens", "not-a-number")
    malformed = await _write(
        async_redis_client,
        context_settings,
        user_id,
        session_id,
        message_id,
    )
    assert malformed.status == MessageWriteStatus.INVALID_SESSION_STATE
    messages_key = working_memory_messages_key(user_id, session_id)
    assert redis_client.llen(messages_key) == 0

    redis_client.hdel(meta_key, "estimated_tokens")
    missing = await _write(
        async_redis_client,
        context_settings,
        user_id,
        session_id,
        str(uuid.uuid4()),
    )
    assert missing.status == MessageWriteStatus.INVALID_SESSION_STATE

    _cleanup_keys(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_argv_message_id_mismatch_skips_evalsha(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    from unittest.mock import AsyncMock, patch

    from memory_system.domain.services.message_write_service import MessageWriteIdMismatchError

    user_id, session_id, message_id = _new_ids()
    await _create_active_session(async_redis_client, user_id, session_id)
    mismatched_json = (
        '{"message_id":"00000000-0000-4000-8000-000000000001",'
        '"role":"user","content":"x","estimated_tokens":1,"timestamp":1}'
    )
    messages_key = working_memory_messages_key(user_id, session_id)
    message_ids_key = working_memory_message_ids_key(user_id, session_id)

    # scenario 17: service verifies serialized id before Lua
    with patch(
        "memory_system.domain.services.message_write_service.message_to_json",
        return_value=mismatched_json,
    ):
        with patch(
            "memory_system.domain.services.message_write_service.execute_message_write_lua",
            new_callable=AsyncMock,
        ) as mock_lua:
            with pytest.raises(MessageWriteIdMismatchError):
                await write_message(
                    redis=async_redis_client,
                    input=MessageWriteInput(
                        user_id=user_id,
                        session_id=session_id,
                        message_id=message_id,
                        role=MessageRole.USER,
                        content="x",
                    ),
                    context=get_settings().context,
                    clock=lambda: FIXED_NOW,
                )
            mock_lua.assert_not_awaited()

    assert redis_client.llen(messages_key) == 0
    assert redis_client.scard(message_ids_key) == 0

    _cleanup_keys(redis_client, user_id, session_id)
