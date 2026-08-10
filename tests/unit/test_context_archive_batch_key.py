"""Unit tests for archive_batch_key helper."""

from __future__ import annotations

from memory_system.domain.services.context_archive_service import build_archive_batch_key

SESSION_ID = "session_001"
FIRST_ID = "msg_000001"
LAST_ID = "msg_000002"


def test_build_archive_batch_key_format() -> None:
    key = build_archive_batch_key(SESSION_ID, FIRST_ID, LAST_ID)
    assert key == f"{SESSION_ID}:{FIRST_ID}:{LAST_ID}"
    assert key == "session_001:msg_000001:msg_000002"


def test_build_archive_batch_key_deterministic() -> None:
    first = build_archive_batch_key(SESSION_ID, FIRST_ID, LAST_ID)
    second = build_archive_batch_key(SESSION_ID, FIRST_ID, LAST_ID)
    assert first == second


def test_build_archive_batch_key_different_sessions() -> None:
    key_a = build_archive_batch_key("session_a", FIRST_ID, LAST_ID)
    key_b = build_archive_batch_key("session_b", FIRST_ID, LAST_ID)
    assert key_a != key_b


def test_build_archive_batch_key_different_message_bounds() -> None:
    key_a = build_archive_batch_key(SESSION_ID, "msg_a", LAST_ID)
    key_b = build_archive_batch_key(SESSION_ID, FIRST_ID, "msg_z")
    assert key_a != key_b
