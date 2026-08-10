"""Contract tests for STM-008 compression finalize."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.domain.models.compression_llm import CompressionFinalizeLlmPayload
from memory_system.domain.services import compression_finalize_service as finalize_mod
from memory_system.infrastructure.redis.compression_finalize_script import (
    load_compression_finalize_lua,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "memory_system"
    / "domain"
    / "services"
    / "compression_finalize_service.py"
)


def test_compression_finalize_status_literals_stable() -> None:
    expected = {
        "success",
        "session_not_found",
        "session_closing",
        "lock_not_acquired",
        "version_conflict",
        "pending_conflict",
        "invalid_session_state",
        "message_boundary_mismatch",
    }
    assert {m.value for m in CompressionFinalizeStatus} == expected


def test_stm007_payload_handoff_two_fields_only() -> None:
    CompressionFinalizeLlmPayload(
        compressed_context="",
        new_compressed_context_tokens=0,
    )
    assert set(CompressionFinalizeLlmPayload.model_fields.keys()) == {
        "compressed_context",
        "new_compressed_context_tokens",
    }


def test_toctou_guard_single_lua_finalize_path() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "finalize_compression_in_redis" in source
    forbidden_snippets = (
        'redis.get(compression_lock_key',
        "await redis.get(",
        ".get(compression_lock_key",
        "release_compression_lock",
    )
    for snippet in forbidden_snippets:
        assert snippet not in source, f"TOCTOU risk: found {snippet!r}"

    lua = load_compression_finalize_lua()
    assert "KEYS[1]" in lua and "KEYS[2]" in lua and "KEYS[3]" in lua
    assert "ARGV[8]" in lua

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and (
            (
                isinstance(node.value.func, ast.Name)
                and node.value.func.id == "finalize_compression_in_redis"
            )
            or (
                isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "finalize_compression_in_redis"
            )
        )
    ]
    assert len(calls) == 1

    assert hasattr(finalize_mod, "finalize_compression")
    src = inspect.getsource(finalize_mod.finalize_compression)
    assert "finalize_compression_in_redis" in src


def test_lua_source_sentinels() -> None:
    lua = load_compression_finalize_lua()
    assert "LTRIM" in lua
    assert "SREM" not in lua
    assert "message_ids" not in lua
    assert "redis.call('DEL', lock_key)" in lua
