"""Unit tests for compression finalize input models and STM-007 payload handoff."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from memory_system.domain.models.compression_finalize import CompressionFinalizeInput
from memory_system.domain.models.compression_llm import CompressionFinalizeLlmPayload

USER_ID = "user_001"
SESSION_ID = "session_001"
ARCHIVE_ID = "arch-001"
BATCH_KEY = "session_001:m1:m2"
LOCK_TOKEN = "lock-token-001"


def _payload(**overrides: object) -> CompressionFinalizeLlmPayload:
    data: dict[str, object] = {
        "compressed_context": "summary text",
        "new_compressed_context_tokens": 80,
    }
    data.update(overrides)
    return CompressionFinalizeLlmPayload.model_validate(data)


def _input(**overrides: object) -> CompressionFinalizeInput:
    data: dict[str, object] = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "expected_compression_version": 0,
        "pending_archive_id": ARCHIVE_ID,
        "pending_archive_batch_key": BATCH_KEY,
        "pending_archive_message_count": 2,
        "pending_archive_estimated_tokens": 300,
        "expected_first_message_id": "m1",
        "expected_last_message_id": "m2",
        "archived_message_tokens": 300,
        "old_compressed_context_tokens": 50,
        "lock_owner_token": LOCK_TOKEN,
        "llm_payload": _payload(),
    }
    data.update(overrides)
    return CompressionFinalizeInput.model_validate(data)


def test_archived_tokens_must_match_pending() -> None:
    with pytest.raises(ValidationError, match="archived_message_tokens"):
        _input(archived_message_tokens=100)


def test_empty_compressed_context_is_valid() -> None:
    inp = _input(llm_payload=_payload(compressed_context="", new_compressed_context_tokens=0))
    assert inp.llm_payload.compressed_context == ""
    assert inp.llm_payload.new_compressed_context_tokens == 0


def test_stm007_payload_embedded_in_input() -> None:
    payload = _payload(compressed_context="ctx", new_compressed_context_tokens=42)
    inp = _input(llm_payload=payload)
    assert inp.llm_payload is payload
    assert inp.llm_payload.new_compressed_context_tokens == 42


def test_empty_lock_owner_token_rejected() -> None:
    with pytest.raises(ValidationError):
        _input(lock_owner_token="")


def test_zero_message_count_rejected() -> None:
    with pytest.raises(ValidationError):
        _input(pending_archive_message_count=0)
