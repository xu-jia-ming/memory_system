"""Unit tests for compression finalize Lua result mapping."""

from __future__ import annotations

import pytest

from memory_system.domain.enums.compression_finalize import CompressionFinalizeStatus
from memory_system.infrastructure.redis.compression_finalize_repository import (
    CompressionFinalizeLuaError,
    parse_compression_finalize_lua_result,
)
from memory_system.infrastructure.redis.compression_finalize_script import (
    load_compression_finalize_lua,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("session_not_found", CompressionFinalizeStatus.SESSION_NOT_FOUND),
        ("session_closing", CompressionFinalizeStatus.SESSION_CLOSING),
        ("lock_not_acquired", CompressionFinalizeStatus.LOCK_NOT_ACQUIRED),
        ("version_conflict", CompressionFinalizeStatus.VERSION_CONFLICT),
        ("pending_conflict", CompressionFinalizeStatus.PENDING_CONFLICT),
        ("invalid_session_state", CompressionFinalizeStatus.INVALID_SESSION_STATE),
        ("message_boundary_mismatch", CompressionFinalizeStatus.MESSAGE_BOUNDARY_MISMATCH),
    ],
)
def test_parse_failure_status(raw: str, expected: CompressionFinalizeStatus) -> None:
    outcome = parse_compression_finalize_lua_result(raw)
    assert outcome.status == expected
    assert outcome.new_compression_version is None
    assert outcome.new_estimated_tokens is None


def test_parse_success_tuple() -> None:
    outcome = parse_compression_finalize_lua_result(["success", "1", "500"])
    assert outcome.status == CompressionFinalizeStatus.SUCCESS
    assert outcome.new_compression_version == 1
    assert outcome.new_estimated_tokens == 500


def test_parse_unknown_raises() -> None:
    with pytest.raises(CompressionFinalizeLuaError):
        parse_compression_finalize_lua_result("not_a_real_status")


def test_lua_source_contract() -> None:
    source = load_compression_finalize_lua()
    assert "KEYS[1]" in source
    assert "KEYS[2]" in source
    assert "KEYS[3]" in source
    assert "LTRIM" in source
    assert "SREM" not in source
    assert "message_ids" not in source
    assert "lock_not_acquired" in source
    assert "pending_conflict" in source
    assert "message_boundary_mismatch" in source
    assert "redis.call('GET', lock_key)" in source
    assert "redis.call('DEL', lock_key)" in source
    assert "ARGV[11] ~= ARGV[7]" in source
