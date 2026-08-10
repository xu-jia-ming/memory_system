"""Integration tests for context archive create/reuse against compose test Mongo."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from pymongo import AsyncMongoClient

from memory_system.domain.enums.context_archive import ContextArchiveOutcome
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.context_archive import ContextArchiveCreateInput
from memory_system.domain.models.working_memory import WorkingMemoryMessage
from memory_system.domain.services.context_archive_service import (
    ContextArchiveValidationError,
    build_archive_batch_key,
    create_or_reuse_context_archive,
)
from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
    count_by_batch_key,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"
MONGODB_CONTAINER = "memory-system-mongodb-test"
MONGODB_DATABASE = "memory_system"
FIXED_NOW = 1_700_000_000

UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


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


def _mongodb_container_ip() -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            MONGODB_CONTAINER,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


def _run_init_infra() -> subprocess.CompletedProcess[str]:
    return _compose("run", "--rm", "init-infra", check=False)


def _docker_exec(container: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", container, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _clock_at(offset: int) -> Callable[[], int]:
    return lambda: FIXED_NOW + offset


@pytest.fixture(scope="module")
def test_mongo() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run context archive integration safely")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "mongodb", check=False)
    if up.returncode != 0:
        pytest.skip(
            "Unable to start compose test Mongo "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 120
    while time.time() < deadline:
        ip = _mongodb_container_ip()
        if ip:
            break
        time.sleep(2)
    else:
        _compose("down", "-v", check=False)
        pytest.skip("Test Mongo container did not become ready in time")

    migrate = _run_init_infra()
    if migrate.returncode != 0:
        _compose("down", "-v", check=False)
        pytest.skip(
            "init-infra migration failed: "
            f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
        )

    ip = _mongodb_container_ip()
    if not ip:
        _compose("down", "-v", check=False)
        pytest.skip("Could not resolve test Mongo container IP")

    yield f"mongodb://{ip}:27017/{MONGODB_DATABASE}"

    _compose("down", "-v", check=False)


@pytest.fixture
async def mongo_client(test_mongo: str) -> AsyncIterator[AsyncMongoClient[Any]]:
    client: AsyncMongoClient[Any] = AsyncMongoClient(test_mongo)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        await client.close()
        pytest.skip(f"Mongo ping failed: {exc}")
    yield client
    await client.close()


@pytest.fixture(autouse=True)
async def _clean_context_archive(mongo_client: AsyncMongoClient[Any]) -> AsyncIterator[None]:
    db = mongo_client.get_default_database()
    if db is not None:
        await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
    yield
    if db is not None:
        await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})


def _unique_session() -> str:
    return f"session_{uuid.uuid4().hex[:12]}"


def _messages_ordered() -> list[WorkingMemoryMessage]:
    return [
        WorkingMemoryMessage(
            message_id="msg_m1",
            role=MessageRole.USER,
            content="first",
            estimated_tokens=10,
            timestamp=FIXED_NOW,
        ),
        WorkingMemoryMessage(
            message_id="msg_m2",
            role=MessageRole.ASSISTANT,
            content="second",
            estimated_tokens=12,
            timestamp=FIXED_NOW + 1,
        ),
        WorkingMemoryMessage(
            message_id="msg_m3",
            role=MessageRole.USER,
            content="third",
            estimated_tokens=8,
            timestamp=FIXED_NOW + 2,
        ),
    ]


def _input_for_session(
    session_id: str,
    messages: list[WorkingMemoryMessage] | None = None,
    *,
    user_id: str = "user_integration",
    base_compression_version: int = 0,
    archive_batch_key: str | None = None,
) -> ContextArchiveCreateInput:
    msgs = messages if messages is not None else _messages_ordered()
    batch_key = archive_batch_key or build_archive_batch_key(
        session_id,
        msgs[0].message_id,
        msgs[-1].message_id,
    )
    return ContextArchiveCreateInput(
        user_id=user_id,
        session_id=session_id,
        archive_batch_key=batch_key,
        base_compression_version=base_compression_version,
        messages=msgs,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_first_create_returns_created(mongo_client: AsyncMongoClient[Any]) -> None:
    session_id = _unique_session()
    input_data = _input_for_session(session_id)

    result = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW,
    )

    assert result.outcome == ContextArchiveOutcome.CREATED
    assert UUID_V4_PATTERN.match(result.archive_id)
    assert await count_by_batch_key(mongo_client, input_data.archive_batch_key) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_same_key_returns_reused(mongo_client: AsyncMongoClient[Any]) -> None:
    session_id = _unique_session()
    input_data = _input_for_session(session_id)

    first = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW,
    )
    second = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW + 999,
    )

    assert first.outcome == ContextArchiveOutcome.CREATED
    assert second.outcome == ContextArchiveOutcome.REUSED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_same_key_same_archive_id(mongo_client: AsyncMongoClient[Any]) -> None:
    session_id = _unique_session()
    input_data = _input_for_session(session_id)

    first = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW,
    )
    second = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW + 1,
    )

    assert first.archive_id == second.archive_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_same_key_single_physical_document(mongo_client: AsyncMongoClient[Any]) -> None:
    session_id = _unique_session()
    input_data = _input_for_session(session_id)

    await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW,
    )
    await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW + 1,
    )

    assert await count_by_batch_key(mongo_client, input_data.archive_batch_key) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i5_concurrent_same_key_one_document(mongo_client: AsyncMongoClient[Any]) -> None:
    session_id = _unique_session()
    input_data = _input_for_session(session_id)
    concurrency = 12

    results = await asyncio.gather(
        *[
            create_or_reuse_context_archive(
                mongodb=mongo_client,
                input=input_data,
                clock=_clock_at(offset),
            )
            for offset in range(concurrency)
        ]
    )

    archive_ids = {result.archive_id for result in results}
    assert len(archive_ids) == 1
    assert await count_by_batch_key(mongo_client, input_data.archive_batch_key) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_concurrent_callers_same_archive_identity(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    session_id = _unique_session()
    input_data = _input_for_session(session_id)

    results = await asyncio.gather(
        *[
            create_or_reuse_context_archive(
                mongodb=mongo_client,
                input=input_data,
                clock=lambda: FIXED_NOW,
            )
            for _ in range(10)
        ]
    )

    outcomes = {result.outcome for result in results}
    assert ContextArchiveOutcome.CREATED in outcomes
    assert outcomes.issubset({ContextArchiveOutcome.CREATED, ContextArchiveOutcome.REUSED})
    assert len({result.archive_id for result in results}) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i7_different_keys_different_archives(mongo_client: AsyncMongoClient[Any]) -> None:
    session_a = _unique_session()
    session_b = _unique_session()
    input_a = _input_for_session(session_a)
    input_b = _input_for_session(session_b)

    result_a = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_a,
        clock=lambda: FIXED_NOW,
    )
    result_b = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_b,
        clock=lambda: FIXED_NOW,
    )

    assert result_a.archive_id != result_b.archive_id
    assert await count_by_batch_key(mongo_client, input_a.archive_batch_key) == 1
    assert await count_by_batch_key(mongo_client, input_b.archive_batch_key) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i8_required_fields_persisted(mongo_client: AsyncMongoClient[Any]) -> None:
    session_id = _unique_session()
    messages = _messages_ordered()
    input_data = _input_for_session(session_id, messages, base_compression_version=3)

    result = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW,
    )

    db = mongo_client.get_default_database()
    assert db is not None
    stored = await db[CONTEXT_ARCHIVE_COLLECTION].find_one({"archive_id": result.archive_id})
    assert stored is not None
    assert stored["user_id"] == input_data.user_id
    assert stored["session_id"] == session_id
    assert stored["archive_batch_key"] == input_data.archive_batch_key
    assert stored["base_compression_version"] == 3
    assert stored["created_time"] == FIXED_NOW
    assert len(stored["messages"]) == 3
    for stored_msg, source_msg in zip(stored["messages"], messages, strict=True):
        assert set(stored_msg.keys()) == {"message_id", "role", "content", "timestamp"}
        assert "estimated_tokens" not in stored_msg
        assert stored_msg["message_id"] == source_msg.message_id
        assert stored_msg["role"] == source_msg.role.value
        assert stored_msg["content"] == source_msg.content
        assert stored_msg["timestamp"] == source_msg.timestamp


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i9_messages_preserve_order(mongo_client: AsyncMongoClient[Any]) -> None:
    session_id = _unique_session()
    messages = _messages_ordered()
    input_data = _input_for_session(session_id, messages)

    result = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW,
    )

    persisted_ids = [msg.message_id for msg in result.archive.messages]
    assert persisted_ids == ["msg_m1", "msg_m2", "msg_m3"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i10_reuse_does_not_overwrite_existing_archive(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    session_id = _unique_session()
    original_messages = _messages_ordered()
    input_data = _input_for_session(session_id, original_messages, base_compression_version=1)

    first = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=input_data,
        clock=lambda: FIXED_NOW,
    )

    tampered_messages = [
        WorkingMemoryMessage(
            message_id="msg_m1",
            role=MessageRole.USER,
            content="tampered",
            estimated_tokens=99,
            timestamp=FIXED_NOW,
        ),
        WorkingMemoryMessage(
            message_id="msg_m2",
            role=MessageRole.ASSISTANT,
            content="tampered",
            estimated_tokens=99,
            timestamp=FIXED_NOW + 1,
        ),
        WorkingMemoryMessage(
            message_id="msg_m3",
            role=MessageRole.USER,
            content="tampered",
            estimated_tokens=99,
            timestamp=FIXED_NOW + 2,
        ),
    ]
    tampered_input = _input_for_session(
        session_id,
        tampered_messages,
        base_compression_version=99,
    )
    assert tampered_input.archive_batch_key == input_data.archive_batch_key

    second = await create_or_reuse_context_archive(
        mongodb=mongo_client,
        input=tampered_input,
        clock=lambda: FIXED_NOW + 5000,
    )

    assert second.outcome == ContextArchiveOutcome.REUSED
    assert second.archive_id == first.archive_id
    assert second.archive.created_time == FIXED_NOW
    assert second.archive.base_compression_version == 1
    assert [msg.content for msg in second.archive.messages] == ["first", "second", "third"]


@pytest.mark.integration
def test_i11_archive_batch_key_unique_index_exists(test_mongo: str) -> None:
    idx = _docker_exec(
        MONGODB_CONTAINER,
        "mongosh",
        "--quiet",
        MONGODB_DATABASE,
        "--eval",
        "JSON.stringify(db.context_archive.getIndexes().map(i => i.name))",
    )
    assert idx.returncode == 0, idx.stderr
    index_names = json.loads(idx.stdout)
    assert "archive_batch_key_unique" in index_names
    assert "archive_id_unique" in index_names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i12_invalid_batch_key_consistency_zero_writes(
    mongo_client: AsyncMongoClient[Any],
) -> None:
    session_id = _unique_session()
    messages = _messages_ordered()
    bad_key = f"{session_id}:wrong:first"
    input_data = _input_for_session(session_id, messages, archive_batch_key=bad_key)

    with pytest.raises(ContextArchiveValidationError):
        await create_or_reuse_context_archive(
            mongodb=mongo_client,
            input=input_data,
            clock=lambda: FIXED_NOW,
        )

    assert await count_by_batch_key(mongo_client, bad_key) == 0
    db = mongo_client.get_default_database()
    assert db is not None
    assert await db[CONTEXT_ARCHIVE_COLLECTION].count_documents({}) == 0
