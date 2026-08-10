"""Redis integration tests for compression finalize (27 scenarios; no Kafka/Mongo/LLM)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
import redis
import redis.asyncio as aioredis

from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.domain.enums.working_memory import MessageRole, SessionStatus
from memory_system.domain.models.compression_finalize import CompressionFinalizeInput
from memory_system.domain.models.compression_llm import CompressionFinalizeLlmPayload
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.compression_finalize_service import finalize_compression
from memory_system.domain.services.context_archive_service import build_archive_batch_key
from memory_system.domain.services.token_estimator import estimate_tokens
from memory_system.infrastructure.redis.compression_lock_repository import (
    acquire_compression_lock,
)
from memory_system.infrastructure.redis.keys import (
    compression_lock_key,
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)
from memory_system.infrastructure.redis.working_memory_message_codec import message_to_json
from memory_system.infrastructure.redis.working_memory_repository import (
    create_working_memory_session,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
REDIS_CONTAINER = "memory-system-redis-test"

FIXED_NOW = 1_700_000_000
TTL = 420


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


def _new_ids() -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    user_id = f"stm008_user_{suffix}"
    session_id = str(uuid.uuid4())
    archive_id = str(uuid.uuid4())
    return user_id, session_id, archive_id


def _msg(message_id: str, *, tokens: int = 10) -> str:
    message = WorkingMemoryMessage(
        message_id=message_id,
        role=MessageRole.USER,
        content="x" * max(tokens * 4, 1),
        estimated_tokens=tokens,
        timestamp=FIXED_NOW,
    )
    return message_to_json(message)


@dataclass
class FinalizeSeed:
    user_id: str
    session_id: str
    archive_id: str
    first_message_id: str
    last_message_id: str
    batch_key: str
    pending_count: int
    pending_tokens: int
    lock_token: str
    compression_version: int
    old_compressed_context: str
    old_compressed_tokens: int
    estimated_tokens: int
    message_ids: list[str]


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


def _cleanup(sync_client: redis.Redis, user_id: str, session_id: str) -> None:
    sync_client.delete(
        working_memory_meta_key(user_id, session_id),
        working_memory_messages_key(user_id, session_id),
        working_memory_message_ids_key(user_id, session_id),
        compression_lock_key(user_id, session_id),
    )


async def _seed_finalize_state(
    async_client: aioredis.Redis,
    *,
    pending_count: int = 2,
    pending_tokens: int = 300,
    remaining_count: int = 3,
    compression_version: int = 0,
    old_compressed_context: str = "old compressed context text here",
    estimated_tokens: int = 770,
    status: SessionStatus = SessionStatus.ACTIVE,
    lock_token: str | None = None,
    message_overrides: dict[int, str] | None = None,
) -> FinalizeSeed:
    user_id, session_id, archive_id = _new_ids()
    await create_working_memory_session(
        redis=async_client,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )
    meta_key = working_memory_meta_key(user_id, session_id)
    messages_key = working_memory_messages_key(user_id, session_id)
    ids_key = working_memory_message_ids_key(user_id, session_id)

    message_ids: list[str] = []
    for i in range(pending_count + remaining_count):
        mid = f"m{i}"
        message_ids.append(mid)
        payload = _msg(mid)
        if message_overrides and i in message_overrides:
            payload = message_overrides[i]
        await async_client.rpush(messages_key, payload)
        await async_client.sadd(ids_key, mid)

    first_id = message_ids[0]
    last_pending_id = message_ids[pending_count - 1]
    batch_key = build_archive_batch_key(session_id, first_id, last_pending_id)
    old_tokens = estimate_tokens(old_compressed_context)

    token = lock_token
    if token is None:
        acquired = await acquire_compression_lock(
            async_client,
            user_id=user_id,
            session_id=session_id,
            ttl_seconds=TTL,
            token_factory=lambda: f"lock-{uuid.uuid4().hex}",
        )
        assert acquired is not None
        token = acquired

    mapping: dict[str, str] = {
        "compression_version": str(compression_version),
        "compressed_context": old_compressed_context,
        "estimated_tokens": str(estimated_tokens),
        "pending_archive_id": archive_id,
        "pending_archive_batch_key": batch_key,
        "pending_archive_message_count": str(pending_count),
        "pending_archive_estimated_tokens": str(pending_tokens),
    }
    if status != SessionStatus.ACTIVE:
        mapping["status"] = status.value
    await async_client.hset(meta_key, mapping=cast(dict[Any, Any], mapping))

    return FinalizeSeed(
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
        first_message_id=first_id,
        last_message_id=last_pending_id,
        batch_key=batch_key,
        pending_count=pending_count,
        pending_tokens=pending_tokens,
        lock_token=token,
        compression_version=compression_version,
        old_compressed_context=old_compressed_context,
        old_compressed_tokens=old_tokens,
        estimated_tokens=estimated_tokens,
        message_ids=message_ids,
    )


def _finalize_input(
    seed: FinalizeSeed,
    *,
    version: int | None = None,
    new_compressed_context: str = "new compressed summary",
    new_tokens: int = 80,
    lock_token: str | None = None,
    archive_id: str | None = None,
    batch_key: str | None = None,
    pending_count: int | None = None,
    pending_tokens: int | None = None,
    first_id: str | None = None,
    last_id: str | None = None,
    archived_tokens: int | None = None,
    old_compressed_tokens: int | None = None,
) -> CompressionFinalizeInput:
    pt = pending_tokens if pending_tokens is not None else seed.pending_tokens
    at = archived_tokens if archived_tokens is not None else pt
    return CompressionFinalizeInput(
        user_id=seed.user_id,
        session_id=seed.session_id,
        expected_compression_version=version
        if version is not None
        else seed.compression_version,
        pending_archive_id=archive_id if archive_id is not None else seed.archive_id,
        pending_archive_batch_key=batch_key if batch_key is not None else seed.batch_key,
        pending_archive_message_count=pending_count
        if pending_count is not None
        else seed.pending_count,
        pending_archive_estimated_tokens=pt,
        expected_first_message_id=first_id if first_id is not None else seed.first_message_id,
        expected_last_message_id=last_id if last_id is not None else seed.last_message_id,
        archived_message_tokens=at,
        old_compressed_context_tokens=old_compressed_tokens
        if old_compressed_tokens is not None
        else seed.old_compressed_tokens,
        lock_owner_token=lock_token if lock_token is not None else seed.lock_token,
        llm_payload=CompressionFinalizeLlmPayload(
            compressed_context=new_compressed_context,
            new_compressed_context_tokens=new_tokens,
        ),
        updated_time=FIXED_NOW,
    )


async def _snapshot(
    async_client: aioredis.Redis,
    seed: FinalizeSeed,
) -> dict[str, Any]:
    meta_key = working_memory_meta_key(seed.user_id, seed.session_id)
    messages_key = working_memory_messages_key(seed.user_id, seed.session_id)
    ids_key = working_memory_message_ids_key(seed.user_id, seed.session_id)
    fields = await async_client.hgetall(meta_key)
    return {
        "fields": dict(cast(dict[str, str], fields)),
        "msg_len": await async_client.llen(messages_key),
        "lock": await async_client.get(compression_lock_key(seed.user_id, seed.session_id)),
        "ids": sorted(await async_client.smembers(ids_key)),
    }


def _assert_zero_mutation(before: dict[str, Any], after: dict[str, Any]) -> None:
    assert after["fields"] == before["fields"]
    assert after["msg_len"] == before["msg_len"]
    assert after["lock"] == before["lock"]
    assert after["ids"] == before["ids"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_success_full_path(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed),
        clock=lambda: FIXED_NOW,
    )
    assert result.status == CompressionFinalizeStatus.SUCCESS
    assert result.new_compression_version == 1
    meta_key = working_memory_meta_key(seed.user_id, seed.session_id)
    fields = await async_redis_client.hgetall(meta_key)
    assert fields["compression_version"] == "1"
    assert fields["compressed_context"] == "new compressed summary"
    assert fields["pending_archive_id"] == ""
    assert fields["pending_archive_message_count"] == "0"
    assert await async_redis_client.get(
        compression_lock_key(seed.user_id, seed.session_id)
    ) is None
    assert await async_redis_client.llen(
        working_memory_messages_key(seed.user_id, seed.session_id)
    ) == len(seed.message_ids) - seed.pending_count
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_session_not_found(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    user_id, session_id, archive_id = _new_ids()
    token = await acquire_compression_lock(
        async_redis_client, user_id=user_id, session_id=session_id, ttl_seconds=TTL
    )
    assert token is not None
    inp = CompressionFinalizeInput(
        user_id=user_id,
        session_id=session_id,
        expected_compression_version=0,
        pending_archive_id=archive_id,
        pending_archive_batch_key=f"{session_id}:a:b",
        pending_archive_message_count=2,
        pending_archive_estimated_tokens=10,
        expected_first_message_id="a",
        expected_last_message_id="b",
        archived_message_tokens=10,
        old_compressed_context_tokens=0,
        lock_owner_token=token,
        llm_payload=CompressionFinalizeLlmPayload(
            compressed_context="x", new_compressed_context_tokens=1
        ),
    )
    result = await finalize_compression(redis=async_redis_client, input=inp)
    assert result.status == CompressionFinalizeStatus.SESSION_NOT_FOUND
    _cleanup(redis_client, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_session_closing_no_pending(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client, status=SessionStatus.CLOSING)
    meta_key = working_memory_meta_key(seed.user_id, seed.session_id)
    await async_redis_client.hset(
        meta_key,
        mapping={
            "pending_archive_id": "",
            "pending_archive_batch_key": "",
            "pending_archive_message_count": "0",
            "pending_archive_estimated_tokens": "0",
        },
    )
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.SESSION_CLOSING
    after = await _snapshot(async_redis_client, seed)
    _assert_zero_mutation(before, after)
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_closing_in_flight_success(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client, status=SessionStatus.CLOSING)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.SUCCESS
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_lock_not_acquired_wrong_token(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, lock_token="wrong-token"),
    )
    assert result.status == CompressionFinalizeStatus.LOCK_NOT_ACQUIRED
    after = await _snapshot(async_redis_client, seed)
    _assert_zero_mutation(before, after)
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_lock_not_acquired_missing(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    await async_redis_client.delete(
        compression_lock_key(seed.user_id, seed.session_id)
    )
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.LOCK_NOT_ACQUIRED
    after = await _snapshot(async_redis_client, seed)
    _assert_zero_mutation(before, after)
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i7_version_conflict(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client, compression_version=5)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, version=3),
    )
    assert result.status == CompressionFinalizeStatus.VERSION_CONFLICT
    after = await _snapshot(async_redis_client, seed)
    _assert_zero_mutation(before, after)
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i8_retry_old_version_after_success(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    first = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert first.status == CompressionFinalizeStatus.SUCCESS
    msg_len_after_first = await async_redis_client.llen(
        working_memory_messages_key(seed.user_id, seed.session_id)
    )
    retry_token = await acquire_compression_lock(
        async_redis_client,
        user_id=seed.user_id,
        session_id=seed.session_id,
        ttl_seconds=TTL,
    )
    assert retry_token is not None
    retry = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, version=0, lock_token=retry_token),
    )
    assert retry.status == CompressionFinalizeStatus.VERSION_CONFLICT
    assert await async_redis_client.llen(
        working_memory_messages_key(seed.user_id, seed.session_id)
    ) == msg_len_after_first
    fields = await async_redis_client.hgetall(
        working_memory_meta_key(seed.user_id, seed.session_id)
    )
    assert fields["compression_version"] == "1"
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i9_pending_conflict_archive_id(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, archive_id=str(uuid.uuid4())),
    )
    assert result.status == CompressionFinalizeStatus.PENDING_CONFLICT
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i10_pending_conflict_batch_key(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, batch_key=f"{seed.session_id}:x:y"),
    )
    assert result.status == CompressionFinalizeStatus.PENDING_CONFLICT
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i11_pending_conflict_message_count(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, pending_count=99),
    )
    assert result.status == CompressionFinalizeStatus.PENDING_CONFLICT
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i12_pending_conflict_estimated_tokens(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, pending_tokens=999, archived_tokens=999),
    )
    assert result.status == CompressionFinalizeStatus.PENDING_CONFLICT
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i13_invalid_session_state_half_pending(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    meta_key = working_memory_meta_key(seed.user_id, seed.session_id)
    await async_redis_client.hset(
        meta_key,
        mapping={
            "pending_archive_id": "half",
            "pending_archive_batch_key": "",
            "pending_archive_message_count": "0",
            "pending_archive_estimated_tokens": "0",
        },
    )
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.INVALID_SESSION_STATE
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i14_message_boundary_first_id_wrong(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, first_id="wrong-first"),
    )
    assert result.status == CompressionFinalizeStatus.MESSAGE_BOUNDARY_MISMATCH
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i15_message_boundary_last_id_wrong(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, last_id="wrong-last"),
    )
    assert result.status == CompressionFinalizeStatus.MESSAGE_BOUNDARY_MISMATCH
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i16_message_boundary_list_too_short(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client, pending_count=2, remaining_count=0)
    meta_key = working_memory_meta_key(seed.user_id, seed.session_id)
    await async_redis_client.hset(meta_key, "pending_archive_message_count", "5")
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, pending_count=5),
    )
    assert result.status == CompressionFinalizeStatus.MESSAGE_BOUNDARY_MISMATCH
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i17_message_boundary_batch_key_mismatch(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    meta_key = working_memory_meta_key(seed.user_id, seed.session_id)
    await async_redis_client.hset(
        meta_key,
        "pending_archive_batch_key",
        f"{seed.session_id}:m0:wrong",
    )
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.PENDING_CONFLICT
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i18_token_formula_case_a(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    old_ctx = "x" * 200
    seed = await _seed_finalize_state(
        async_redis_client,
        pending_count=2,
        pending_tokens=300,
        remaining_count=3,
        old_compressed_context=old_ctx,
        estimated_tokens=770,
    )
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(
            seed,
            old_compressed_tokens=50,
            new_tokens=80,
        ),
    )
    assert result.status == CompressionFinalizeStatus.SUCCESS
    assert result.new_estimated_tokens == 500
    fields = await async_redis_client.hgetall(
        working_memory_meta_key(seed.user_id, seed.session_id)
    )
    assert fields["estimated_tokens"] == "500"
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i19_empty_compressed_context(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(
        async_redis_client,
        estimated_tokens=100,
        pending_tokens=40,
        old_compressed_context="",
    )
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(
            seed,
            new_compressed_context="",
            new_tokens=0,
            old_compressed_tokens=0,
            pending_tokens=40,
            archived_tokens=40,
        ),
    )
    assert result.status == CompressionFinalizeStatus.SUCCESS
    fields = await async_redis_client.hgetall(
        working_memory_meta_key(seed.user_id, seed.session_id)
    )
    assert fields["compressed_context"] == ""
    expected = max(0, 100 - 40 - 0 + 0)
    assert fields["estimated_tokens"] == str(expected)
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i20_failure_zero_side_effect_version_fail(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client, compression_version=2)
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, version=1),
    )
    assert result.status == CompressionFinalizeStatus.VERSION_CONFLICT
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i21_retry_outcome_unknown(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    first = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert first.status == CompressionFinalizeStatus.SUCCESS
    fields = await async_redis_client.hgetall(
        working_memory_meta_key(seed.user_id, seed.session_id)
    )
    assert fields["pending_archive_id"] == ""
    assert fields["compression_version"] == "1"
    retry_token = await acquire_compression_lock(
        async_redis_client,
        user_id=seed.user_id,
        session_id=seed.session_id,
        ttl_seconds=TTL,
    )
    assert retry_token is not None
    retry = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(seed, version=0, lock_token=retry_token),
    )
    assert retry.status == CompressionFinalizeStatus.VERSION_CONFLICT
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i22_concurrent_duplicate_finalize(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client, compression_version=0)

    async def _run() -> CompressionFinalizeStatus:
        return (
            await finalize_compression(
                redis=async_redis_client, input=_finalize_input(seed)
            )
        ).status

    statuses = await asyncio.gather(_run(), _run(), _run())
    assert statuses.count(CompressionFinalizeStatus.SUCCESS) == 1
    non_success = [
        s
        for s in statuses
        if s != CompressionFinalizeStatus.SUCCESS
    ]
    assert len(non_success) == 2
    assert all(
        s in (
            CompressionFinalizeStatus.VERSION_CONFLICT,
            CompressionFinalizeStatus.LOCK_NOT_ACQUIRED,
        )
        for s in non_success
    )
    fields = await async_redis_client.hgetall(
        working_memory_meta_key(seed.user_id, seed.session_id)
    )
    assert fields["compression_version"] == "1"
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i23_message_ids_set_unchanged(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    ids_key = working_memory_message_ids_key(seed.user_id, seed.session_id)
    before_ids = await async_redis_client.smembers(ids_key)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.SUCCESS
    after_ids = await async_redis_client.smembers(ids_key)
    assert before_ids == after_ids
    assert len(after_ids) == len(seed.message_ids)
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i24_malformed_compression_version(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    meta_key = working_memory_meta_key(seed.user_id, seed.session_id)
    await async_redis_client.hset(meta_key, "compression_version", "abc")
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.INVALID_SESSION_STATE
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i25_malformed_estimated_tokens(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(async_redis_client)
    meta_key = working_memory_meta_key(seed.user_id, seed.session_id)
    await async_redis_client.hset(meta_key, "estimated_tokens", "12.5")
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.INVALID_SESSION_STATE
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i26_malformed_message_json(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(
        async_redis_client,
        message_overrides={0: "{not valid json"},
    )
    before = await _snapshot(async_redis_client, seed)
    result = await finalize_compression(
        redis=async_redis_client, input=_finalize_input(seed)
    )
    assert result.status == CompressionFinalizeStatus.MESSAGE_BOUNDARY_MISMATCH
    _assert_zero_mutation(before, await _snapshot(async_redis_client, seed))
    _cleanup(redis_client, seed.user_id, seed.session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i27_token_clamp_case_b(
    async_redis_client: aioredis.Redis,
    redis_client: redis.Redis,
) -> None:
    seed = await _seed_finalize_state(
        async_redis_client,
        estimated_tokens=100,
        pending_tokens=80,
        old_compressed_context="x" * 200,
    )
    result = await finalize_compression(
        redis=async_redis_client,
        input=_finalize_input(
            seed,
            old_compressed_tokens=50,
            new_tokens=10,
            pending_tokens=80,
            archived_tokens=80,
        ),
    )
    assert result.status == CompressionFinalizeStatus.SUCCESS
    assert result.new_estimated_tokens == 0
    fields = await async_redis_client.hgetall(
        working_memory_meta_key(seed.user_id, seed.session_id)
    )
    assert fields["estimated_tokens"] == "0"
    _cleanup(redis_client, seed.user_id, seed.session_id)
