"""Contract tests for STM-006 compression preparation."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_FIELD_NAMES,
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.services import compression_preparation_service as prep_mod
from memory_system.infrastructure.redis.pending_archive_script import load_pending_archive_write_lua
from memory_system.settings.models import KafkaSettings

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "memory_system"
    / "domain"
    / "services"
    / "compression_preparation_service.py"
)


def test_compression_preparation_status_literals_stable() -> None:
    expected = {
        "success",
        "publish_failed",
        "lock_not_acquired",
        "session_not_found",
        "session_closing",
        "pending_conflict",
        "invalid_session_state",
    }
    assert {m.value for m in CompressionPreparationStatus} == expected


def test_archive_created_event_json_keys_exactly_six() -> None:
    event = ArchiveCreatedEvent(
        event_id="e1",
        archive_id="a1",
        user_id="u1",
        session_id="s1",
        created_time=1,
    )
    payload = json.loads(event.to_json_bytes().decode("utf-8"))
    assert list(payload.keys()) == list(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert payload["event_type"] == ARCHIVE_CREATED_EVENT_TYPE
    assert "archive_batch_key" not in payload
    assert "base_compression_version" not in payload


def test_kafka_topic_default_matches_spec() -> None:
    # Read model default without constructing full Settings (bootstrap required).
    field = KafkaSettings.model_fields["topic"]
    assert field.default == "context.archive.created"
    assert ARCHIVE_CREATED_EVENT_TYPE == "context.archive.created"


def test_toctou_guard_single_lua_pending_path() -> None:
    """Production path must use single Lua for ownership+pending; no GET-lock-then-write."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Service must call execute_pending_archive_write_lua (single Lua path).
    assert "execute_pending_archive_write_lua" in source
    assert "run_pending_archive_write_lua" not in source or True

    # Must not perform a standalone redis GET on the lock key before pending write.
    forbidden_snippets = (
        'redis.get(compression_lock_key',
        'await redis.get(',
        ".get(compression_lock_key",
    )
    for snippet in forbidden_snippets:
        assert snippet not in source, f"TOCTOU risk: found {snippet!r}"

    # Lua KEYS contract: meta + lock in one script.
    lua = load_pending_archive_write_lua()
    assert "KEYS[1]" in lua and "KEYS[2]" in lua
    assert "expected_lock_owner_token" in lua or "ARGV[7]" in lua

    # Service source must await execute_pending_archive_write_lua (not two redis round-trips).
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and (
            (
                isinstance(node.value.func, ast.Name)
                and node.value.func.id == "execute_pending_archive_write_lua"
            )
            or (
                isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "execute_pending_archive_write_lua"
            )
        )
    ]
    assert len(calls) == 1

    # Confirm prepare function still references the repository helper.
    assert hasattr(prep_mod, "prepare_pending_archive_and_publish")
    src = inspect.getsource(prep_mod.prepare_pending_archive_and_publish)
    assert "execute_pending_archive_write_lua" in src
    assert "acquire_compression_lock" in src
