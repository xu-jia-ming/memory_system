"""Redis/Mongo integration tests for session close (STM-010 A–R + OI4)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis
import redis.asyncio as aioredis
from pymongo import AsyncMongoClient

from memory_system.domain.enums.message_write import MessageWriteStatus
from memory_system.domain.enums.session_close import SessionCloseTerminalStatus
from memory_system.domain.enums.working_memory import MessageRole, SessionStatus
from memory_system.domain.models.context_archive import ContextArchiveCreateInput
from memory_system.domain.models.message_write import MessageWriteInput
from memory_system.domain.models.working_memory import WorkingMemoryMessage, WorkingMemoryMeta
from memory_system.domain.services.compression_coordinator_service import (
    SessionClosingCoordinatorError,
    write_working_message_with_coordination,
)
from memory_system.domain.services.context_archive_service import (
    build_archive_batch_key,
    create_or_reuse_context_archive,
)
from memory_system.domain.services.message_write_service import write_message
from memory_system.domain.services.session_close_service import (
    SessionCloseIncompleteError,
    close_session,
)
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
MONGODB_CONTAINER = "memory-system-mongodb-test"
MONGODB_DATABASE = "memory_system"
FIXED_NOW = 1_700_000_000
TOPIC = "context.archive.created"


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


def _container_ip(name: str) -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def _run_init_infra() -> subprocess.CompletedProcess[str]:
    return _compose("run", "--rm", "init-infra", check=False)


@pytest.fixture(scope="module")
def redis_mongo_stack() -> Iterator[tuple[str, str]]:
    if not _docker_available():
        pytest.skip("Docker not available")
    _ensure_dotenv()
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT

    _compose("up", "-d", "redis", "mongodb")
    deadline = time.time() + 120
    redis_ip: str | None = None
    mongo_ip: str | None = None
    while time.time() < deadline:
        redis_ip = _container_ip(REDIS_CONTAINER)
        mongo_ip = _container_ip(MONGODB_CONTAINER)
        if redis_ip and mongo_ip:
            break
        time.sleep(2)
    else:
        pytest.skip("Redis/Mongo not ready")

    migrate = _run_init_infra()
    if migrate.returncode != 0:
        pytest.skip(f"init-infra failed: {migrate.stderr[-500:]}")

    assert redis_ip and mongo_ip
    yield f"redis://{redis_ip}:6379/0", f"mongodb://{mongo_ip}:27017/{MONGODB_DATABASE}"
    _compose("down", check=False)


@pytest.fixture
async def async_redis(redis_mongo_stack: tuple[str, str]) -> AsyncIterator[aioredis.Redis]:
    client = aioredis.from_url(redis_mongo_stack[0], decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def mongo_client(redis_mongo_stack: tuple[str, str]) -> AsyncIterator[AsyncMongoClient[Any]]:
    client: AsyncMongoClient[Any] = AsyncMongoClient(redis_mongo_stack[1])
    try:
        await client.admin.command("ping")
        db = client.get_default_database()
        if db is not None:
            await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
        yield client
        if db is not None:
            await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
    finally:
        await client.close()


@pytest.fixture
def sync_redis(redis_mongo_stack: tuple[str, str]) -> Iterator[redis.Redis]:
    client = redis.from_url(redis_mongo_stack[0], decode_responses=True)
    yield client
    client.close()


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
                    "max_archive_estimated_tokens": 100,
                    "compression_trigger_tokens": 500,
                    "compression_target_tokens": 80,
                    "preferred_recent_messages": 2,
                    "absolute_min_recent_messages": 2,
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
    return f"stm010_user_{suffix}", str(uuid.uuid4())


def _content_for_tokens(tokens: int) -> str:
    return "a" * max(tokens * 4, 4)


def _clock_at(offset: int) -> Callable[[], int]:
    return lambda: FIXED_NOW + offset


async def _read_meta(
    redis_client: aioredis.Redis,
    user_id: str,
    session_id: str,
) -> WorkingMemoryMeta | None:
    fields = await redis_client.hgetall(working_memory_meta_key(user_id, session_id))
    if not fields:
        return None
    return hash_fields_to_meta(cast(dict[str, str], fields))


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


async def _seed_session_with_messages(
    redis_client: aioredis.Redis,
    settings: Any,
    user_id: str,
    session_id: str,
    token_list: list[int],
    *,
    compression_version: int = 0,
) -> list[str]:
    await create_working_memory_session(
        redis=redis_client,
        user_id=user_id,
        session_id=session_id,
        now=FIXED_NOW,
    )
    if compression_version != 0:
        await redis_client.hset(
            working_memory_meta_key(user_id, session_id),
            "compression_version",
            str(compression_version),
        )
    message_ids: list[str] = []
    for index, tokens in enumerate(token_list):
        message_id = f"msg-{index}"
        message_ids.append(message_id)
        result = await write_message(
            redis=redis_client,
            input=MessageWriteInput(
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                role=MessageRole.USER,
                content=_content_for_tokens(tokens),
            ),
            context=settings.context,
            clock=_clock_at(index),
        )
        assert result.status == MessageWriteStatus.SUCCESS
    return message_ids


async def _close(
    redis_client: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: MagicMock,
    settings: Any,
    user_id: str,
    session_id: str,
) -> Any:
    return await close_session(
        redis=redis_client,
        mongodb=mongo_client,
        kafka_producer=kafka_producer,
        settings=settings,
        user_id=user_id,
        session_id=session_id,
        clock=lambda: FIXED_NOW + 1000,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_a_full_close_path(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [30, 40])
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    assert result.status == "closed"
    assert await async_redis.exists(working_memory_meta_key(user_id, session_id)) == 0
    assert await async_redis.exists(working_memory_messages_key(user_id, session_id)) == 0
    assert await async_redis.exists(working_memory_message_ids_key(user_id, session_id)) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_b_close_then_write_rejected(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [20])
    meta_key = working_memory_meta_key(user_id, session_id)
    await async_redis.hset(meta_key, "status", SessionStatus.CLOSING.value)
    write_result = await write_message(
        redis=async_redis,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id="late-msg",
            role=MessageRole.USER,
            content="late",
        ),
        context=test_settings.context,
        clock=lambda: FIXED_NOW + 2000,
    )
    assert write_result.status == MessageWriteStatus.SESSION_CLOSING
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_c_mongo_messages_four_fields(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [25, 35])
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    archive_id = result.archive_ids[0]
    db = mongo_client.get_default_database()
    doc = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"archive_id": archive_id})
    assert doc is not None
    for msg in doc["messages"]:
        assert set(msg.keys()) == {"message_id", "role", "content", "timestamp"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_d_token_sum_exact(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    tokens = [30, 45, 25]
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, tokens)
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    db = mongo_client.get_default_database()
    total_archived = 0
    for archive_id in result.archive_ids:
        doc = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"archive_id": archive_id})
        assert doc is not None
        for msg in doc["messages"]:
            index = int(str(msg["message_id"]).split("-")[1])
            total_archived += tokens[index]
    assert total_archived == sum(tokens)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_e_pending_batch_uses_meta_tokens(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    message_ids = await _seed_session_with_messages(
        async_redis, test_settings, user_id, session_id, [40, 50]
    )
    batch_key = build_archive_batch_key(session_id, message_ids[0], message_ids[0])
    archive_result = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=ContextArchiveCreateInput(
            user_id=user_id,
            session_id=session_id,
            archive_batch_key=batch_key,
            base_compression_version=0,
            messages=[
                WorkingMemoryMessage(
                    message_id=message_ids[0],
                    role=MessageRole.USER,
                    content=_content_for_tokens(40),
                    estimated_tokens=40,
                    timestamp=FIXED_NOW,
                )
            ],
        ),
        clock=lambda: FIXED_NOW,
    )
    meta_key = working_memory_meta_key(user_id, session_id)
    await async_redis.hset(
        meta_key,
        mapping={
            "pending_archive_id": archive_result.archive_id,
            "pending_archive_batch_key": batch_key,
            "pending_archive_message_count": "1",
            "pending_archive_estimated_tokens": "40",
        },
    )
    await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_f_pending_cleared_after_terminal(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [20])
    await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    assert await async_redis.exists(working_memory_meta_key(user_id, session_id)) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_g_lock_released(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [20])
    await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    assert await async_redis.exists(compression_lock_key(user_id, session_id)) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_h_all_wm_keys_deleted(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [20])
    await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    for key_fn in (
        working_memory_meta_key,
        working_memory_messages_key,
        working_memory_message_ids_key,
    ):
        assert await async_redis.exists(key_fn(user_id, session_id)) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_i_empty_session(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await create_working_memory_session(
        redis=async_redis, user_id=user_id, session_id=session_id, now=FIXED_NOW
    )
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    assert result.archive_ids == []
    assert result.status == "closed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_j_closing_retry_no_duplicate_archive(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [30])
    with patch(
        "memory_system.domain.services.session_close_service.execute_terminal_delete_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseTerminalStatus.INVALID_SESSION_STATE,
    ):
        with pytest.raises(SessionCloseIncompleteError):
            await _close(
                async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
            )
    db = mongo_client.get_default_database()
    count_before = await db[CONTEXT_ARCHIVE_COLLECTION].count_documents({})
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    count_after = await db[CONTEXT_ARCHIVE_COLLECTION].count_documents({})
    assert count_after == count_before
    assert result.status == "closed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_k_concurrent_write_vs_close(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [20, 20])

    async def do_close() -> Any:
        return await _close(
            async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
        )

    async def do_write() -> MessageWriteStatus:
        result = await write_message(
            redis=async_redis,
            input=MessageWriteInput(
                user_id=user_id,
                session_id=session_id,
                message_id="race-msg",
                role=MessageRole.USER,
                content="race",
            ),
            context=test_settings.context,
            clock=lambda: FIXED_NOW + 500,
        )
        return result.status

    close_result, write_status = await asyncio.gather(do_close(), do_write())
    assert close_result.status == "closed"
    assert write_status in {
        MessageWriteStatus.SUCCESS,
        MessageWriteStatus.SESSION_CLOSING,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_l_llm_fail_pending_close_succeeds(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(
        async_redis, test_settings, user_id, session_id, [40, 50, 60, 70]
    )
    await write_working_message_with_coordination(
        redis=async_redis,
        mongodb=mongo_client,
        kafka_producer=kafka_producer_mock,
        llm_client=FakeLlmClient(mode="provider_error"),
        settings=test_settings,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=_content_for_tokens(60),
        ),
        clock=lambda: FIXED_NOW + 50,
    )
    meta = await _read_meta(async_redis, user_id, session_id)
    assert meta is not None
    if meta.pending_archive_id:
        result = await _close(
            async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
        )
        assert result.status == "closed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_m_kafka_fail_still_closed(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [25])
    kafka_producer = MagicMock()
    kafka_producer.send_and_wait = AsyncMock(side_effect=RuntimeError("kafka down"))
    result = await _close(
        async_redis, mongo_client, kafka_producer, test_settings, user_id, session_id
    )
    assert result.status == "closed"
    assert await async_redis.exists(working_memory_meta_key(user_id, session_id)) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_n_crash_retry_recovery(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [30])
    with patch(
        "memory_system.domain.services.session_close_service.execute_terminal_delete_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseTerminalStatus.INVALID_SESSION_STATE,
    ):
        with pytest.raises(SessionCloseIncompleteError):
            await _close(
                async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
            )
    meta = await _read_meta(async_redis, user_id, session_id)
    assert meta is not None
    assert meta.status == SessionStatus.CLOSING
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    assert result.status == "closed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_o_base_compression_version_exact(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    version = 7
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(
        async_redis,
        test_settings,
        user_id,
        session_id,
        [30, 40],
        compression_version=version,
    )
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    db = mongo_client.get_default_database()
    for archive_id in result.archive_ids:
        doc = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"archive_id": archive_id})
        assert doc is not None
        assert doc["base_compression_version"] == version


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_p_suffix_retry_reused_version_stable(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    version = 5
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(
        async_redis,
        test_settings,
        user_id,
        session_id,
        [30],
        compression_version=version,
    )
    with patch(
        "memory_system.domain.services.session_close_service.execute_terminal_delete_lua",
        new_callable=AsyncMock,
        return_value=SessionCloseTerminalStatus.INVALID_SESSION_STATE,
    ):
        with pytest.raises(SessionCloseIncompleteError):
            await _close(
                async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
            )
    db = mongo_client.get_default_database()
    first_doc = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"session_id": session_id})
    assert first_doc is not None
    first_version = first_doc["base_compression_version"]
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    second_doc = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"session_id": session_id})
    assert second_doc is not None
    assert second_doc["base_compression_version"] == first_version == version
    assert result.status == "closed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_q_closing_blocks_ordinary_compression(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(
        async_redis, test_settings, user_id, session_id, [60, 60, 60, 60]
    )
    meta_key = working_memory_meta_key(user_id, session_id)
    await async_redis.hset(meta_key, "status", SessionStatus.CLOSING.value)
    with pytest.raises(SessionClosingCoordinatorError):
        await write_working_message_with_coordination(
            redis=async_redis,
            mongodb=mongo_client,
            kafka_producer=kafka_producer_mock,
            llm_client=FakeLlmClient(),
            settings=test_settings,
            input=MessageWriteInput(
                user_id=user_id,
                session_id=session_id,
                message_id=str(uuid.uuid4()),
                role=MessageRole.USER,
                content=_content_for_tokens(60),
            ),
            clock=lambda: FIXED_NOW + 300,
        )
    write_result = await write_message(
        redis=async_redis,
        input=MessageWriteInput(
            user_id=user_id,
            session_id=session_id,
            message_id="blocked-write",
            role=MessageRole.USER,
            content="blocked",
        ),
        context=test_settings.context,
        clock=lambda: FIXED_NOW + 400,
    )
    assert write_result.status == MessageWriteStatus.SESSION_CLOSING
    await _cleanup(async_redis, user_id, session_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i_r_close_recovery_not_409(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    user_id, session_id = _new_ids()
    await _seed_session_with_messages(async_redis, test_settings, user_id, session_id, [25])
    meta_key = working_memory_meta_key(user_id, session_id)
    await async_redis.hset(meta_key, "status", SessionStatus.CLOSING.value)
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    assert result.status == "closed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oi4_token_boundary_closure(
    async_redis: aioredis.Redis,
    mongo_client: AsyncMongoClient[Any],
    test_settings: Any,
    kafka_producer_mock: MagicMock,
) -> None:
    tokens = [15, 25, 35, 45, 20]
    user_id, session_id = _new_ids()
    message_ids = await _seed_session_with_messages(
        async_redis, test_settings, user_id, session_id, tokens
    )
    raw_before = await async_redis.lrange(
        working_memory_messages_key(user_id, session_id), 0, -1
    )
    redis_messages = [json_to_message(str(raw)) for raw in raw_before]
    result = await _close(
        async_redis, mongo_client, kafka_producer_mock, test_settings, user_id, session_id
    )
    db = mongo_client.get_default_database()
    archived_ids: list[str] = []
    for archive_id in result.archive_ids:
        doc = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"archive_id": archive_id})
        assert doc is not None
        for msg in doc["messages"]:
            archived_ids.append(msg["message_id"])
            redis_msg = next(m for m in redis_messages if m.message_id == msg["message_id"])
            assert msg["content"] == redis_msg.content
            assert int(msg["timestamp"]) == redis_msg.timestamp
    assert archived_ids == message_ids
    for archive_id in result.archive_ids:
        doc = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"archive_id": archive_id})
        assert doc is not None
        batch_sum = sum(
            m.estimated_tokens
            for m in redis_messages
            if m.message_id in {x["message_id"] for x in doc["messages"]}
        )
        assert batch_sum == sum(
            tokens[int(m["message_id"].split("-")[1])] for m in doc["messages"]
        )
