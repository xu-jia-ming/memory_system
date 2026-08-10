"""Unit tests for pending archive Lua result mapping."""

from __future__ import annotations

import pytest

from memory_system.domain.enums.compression_preparation import CompressionPreparationStatus
from memory_system.infrastructure.redis.pending_archive_repository import (
    PendingArchiveLuaError,
    parse_pending_archive_lua_result,
)
from memory_system.infrastructure.redis.pending_archive_script import load_pending_archive_write_lua


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("success", CompressionPreparationStatus.SUCCESS),
        ("lock_not_acquired", CompressionPreparationStatus.LOCK_NOT_ACQUIRED),
        ("session_not_found", CompressionPreparationStatus.SESSION_NOT_FOUND),
        ("session_closing", CompressionPreparationStatus.SESSION_CLOSING),
        ("pending_conflict", CompressionPreparationStatus.PENDING_CONFLICT),
        ("invalid_session_state", CompressionPreparationStatus.INVALID_SESSION_STATE),
    ],
)
def test_parse_pending_archive_lua_result(
    raw: str,
    expected: CompressionPreparationStatus,
) -> None:
    assert parse_pending_archive_lua_result(raw) == expected


def test_parse_unknown_lua_result_raises() -> None:
    with pytest.raises(PendingArchiveLuaError):
        parse_pending_archive_lua_result("not_a_real_status")


def test_parse_publish_failed_is_not_lua_result() -> None:
    with pytest.raises(PendingArchiveLuaError):
        parse_pending_archive_lua_result("publish_failed")


def test_lua_source_contains_ownership_and_keys_contract() -> None:
    source = load_pending_archive_write_lua()
    assert "KEYS[1]" in source
    assert "KEYS[2]" in source
    assert "lock_not_acquired" in source
    assert "pending_conflict" in source
    assert "invalid_session_state" in source
    assert "redis.call('GET', lock_key)" in source
    assert "HSET" in source
    assert "LTRIM" not in source
    assert "compression_version" not in source
    assert "compressed_context" not in source
