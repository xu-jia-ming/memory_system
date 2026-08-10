"""Unit tests for context archive Mongo repository."""

from __future__ import annotations

import pytest
from pymongo.errors import DuplicateKeyError

from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.context_archive import ContextArchive, ContextArchiveMessage
from memory_system.infrastructure.mongodb.context_archive_repository import (
    context_archive_from_document,
    is_archive_batch_key_duplicate_error,
)

FIXED_NOW = 1_700_000_000


def _sample_document() -> dict[str, object]:
    return {
        "archive_id": "00000000-0000-4000-8000-000000000001",
        "user_id": "user_001",
        "session_id": "session_001",
        "archive_batch_key": "session_001:msg_001:msg_002",
        "base_compression_version": 0,
        "messages": [
            {
                "message_id": "msg_001",
                "role": "user",
                "content": "hello",
                "timestamp": FIXED_NOW,
            },
            {
                "message_id": "msg_002",
                "role": "assistant",
                "content": "world",
                "timestamp": FIXED_NOW + 1,
            },
        ],
        "created_time": FIXED_NOW,
    }


def test_context_archive_from_document_round_trip() -> None:
    archive = context_archive_from_document(_sample_document())
    assert isinstance(archive, ContextArchive)
    assert archive.archive_id == "00000000-0000-4000-8000-000000000001"
    assert archive.user_id == "user_001"
    assert archive.session_id == "session_001"
    assert archive.archive_batch_key == "session_001:msg_001:msg_002"
    assert archive.base_compression_version == 0
    assert archive.created_time == FIXED_NOW
    assert len(archive.messages) == 2
    assert archive.messages[0] == ContextArchiveMessage(
        message_id="msg_001",
        role=MessageRole.USER,
        content="hello",
        timestamp=FIXED_NOW,
    )
    assert archive.messages[1].role == MessageRole.ASSISTANT


def test_context_archive_from_document_missing_field_fail_closed() -> None:
    document = _sample_document()
    del document["archive_id"]
    with pytest.raises(ValueError, match="archive_id"):
        context_archive_from_document(document)


def test_is_archive_batch_key_duplicate_error_by_key_pattern() -> None:
    exc = DuplicateKeyError("dup", 11000, {"keyPattern": {"archive_batch_key": 1}})
    assert is_archive_batch_key_duplicate_error(exc) is True


def test_is_archive_batch_key_duplicate_error_by_index_name() -> None:
    exc = DuplicateKeyError("dup", 11000, {"errmsg": "index: archive_batch_key_unique dup key"})
    assert is_archive_batch_key_duplicate_error(exc) is True


def test_is_archive_batch_key_duplicate_error_false_for_archive_id() -> None:
    exc = DuplicateKeyError("dup", 11000, {"keyPattern": {"archive_id": 1}})
    assert is_archive_batch_key_duplicate_error(exc) is False
