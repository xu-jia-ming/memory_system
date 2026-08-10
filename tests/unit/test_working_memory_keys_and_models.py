"""Unit tests for Working Memory key templates and field models (§1.2.1)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from memory_system.domain.enums.working_memory import MessageRole, SessionStatus
from memory_system.domain.models.working_memory import WorkingMemoryMessage, WorkingMemoryMeta
from memory_system.infrastructure.redis.keys import (
    working_memory_message_ids_key,
    working_memory_messages_key,
    working_memory_meta_key,
)

USER_ID = "user_001"
SESSION_ID = "session_001"


def test_meta_key_template() -> None:
    assert working_memory_meta_key(USER_ID, SESSION_ID) == (
        f"memory:working:{USER_ID}:{SESSION_ID}"
    )


def test_messages_key_template() -> None:
    assert working_memory_messages_key(USER_ID, SESSION_ID) == (
        f"memory:working:{USER_ID}:{SESSION_ID}:messages"
    )


def test_message_ids_key_template() -> None:
    assert working_memory_message_ids_key(USER_ID, SESSION_ID) == (
        f"memory:working:{USER_ID}:{SESSION_ID}:message_ids"
    )


def test_working_memory_meta_defaults() -> None:
    meta = WorkingMemoryMeta(
        user_id=USER_ID,
        session_id=SESSION_ID,
        created_time=1,
        updated_time=2,
    )
    assert meta.compressed_context == ""
    assert meta.pending_archive_id is None
    assert meta.pending_archive_batch_key is None
    assert meta.pending_archive_message_count == 0
    assert meta.pending_archive_estimated_tokens == 0
    assert meta.status == SessionStatus.ACTIVE


def test_compressed_context_allows_empty_string() -> None:
    meta = WorkingMemoryMeta(
        user_id=USER_ID,
        session_id=SESSION_ID,
        compressed_context="",
        created_time=1,
        updated_time=2,
    )
    assert meta.compressed_context == ""


def test_compressed_context_rejects_null() -> None:
    with pytest.raises(ValidationError):
        WorkingMemoryMeta(
            user_id=USER_ID,
            session_id=SESSION_ID,
            compressed_context=None,  # type: ignore[arg-type]
            created_time=1,
            updated_time=2,
        )


@pytest.mark.parametrize("status", [SessionStatus.ACTIVE, SessionStatus.CLOSING])
def test_valid_session_status(status: SessionStatus) -> None:
    meta = WorkingMemoryMeta(
        user_id=USER_ID,
        session_id=SESSION_ID,
        status=status,
        created_time=1,
        updated_time=2,
    )
    assert meta.status == status


def test_invalid_session_status_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkingMemoryMeta(
            user_id=USER_ID,
            session_id=SESSION_ID,
            status="archived",  # type: ignore[arg-type]
            created_time=1,
            updated_time=2,
        )


@pytest.mark.parametrize("role", [MessageRole.USER, MessageRole.ASSISTANT])
def test_valid_message_role(role: MessageRole) -> None:
    message = WorkingMemoryMessage(
        message_id="msg_001",
        role=role,
        content="hello",
        estimated_tokens=1,
        timestamp=1720000000,
    )
    assert message.role == role


def test_invalid_message_role_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkingMemoryMessage(
            message_id="msg_001",
            role="system",  # type: ignore[arg-type]
            content="hello",
            estimated_tokens=1,
            timestamp=1720000000,
        )


def test_whitelist_source_files_do_not_import_redis() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    whitelist_paths = [
        repo_root / "src/memory_system/domain/services/token_estimator.py",
        repo_root / "src/memory_system/domain/models/working_memory.py",
        repo_root / "src/memory_system/domain/enums/working_memory.py",
        repo_root / "src/memory_system/infrastructure/redis/keys.py",
    ]
    for path in whitelist_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.names[0].name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        import_froms = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert "redis" not in imports
        assert not any(module.startswith("redis") for module in import_froms)
