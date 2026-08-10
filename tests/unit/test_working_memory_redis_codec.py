"""Unit tests for Working Memory Redis Hash codec."""

from __future__ import annotations

import pytest

from memory_system.domain.enums.working_memory import SessionStatus
from memory_system.domain.models.working_memory import WorkingMemoryMeta
from memory_system.infrastructure.redis.working_memory_codec import (
    META_HASH_FIELD_NAMES,
    hash_fields_to_meta,
    meta_to_hash_fields,
)

USER_ID = "user_001"
SESSION_ID = "550e8400-e29b-41d4-a716-426614174000"
NOW = 1_700_000_000


def _sample_meta(**overrides: object) -> WorkingMemoryMeta:
    defaults: dict[str, object] = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "created_time": NOW,
        "updated_time": NOW,
    }
    defaults.update(overrides)
    return WorkingMemoryMeta(**defaults)  # type: ignore[arg-type]


def test_meta_to_hash_fields_covers_all_meta_fields() -> None:
    meta = _sample_meta()
    fields = meta_to_hash_fields(meta)
    assert set(fields) == set(META_HASH_FIELD_NAMES)


def test_codec_round_trip_defaults() -> None:
    meta = _sample_meta()
    restored = hash_fields_to_meta(meta_to_hash_fields(meta))
    assert restored == meta
    assert restored.status == SessionStatus.ACTIVE
    assert restored.compression_version == 0
    assert restored.compressed_context == ""
    assert restored.estimated_tokens == 0


def test_codec_pending_optional_none_encodes_as_empty_string() -> None:
    meta = _sample_meta()
    fields = meta_to_hash_fields(meta)
    assert fields["pending_archive_id"] == ""
    assert fields["pending_archive_batch_key"] == ""
    assert fields["pending_archive_message_count"] == "0"
    assert fields["pending_archive_estimated_tokens"] == "0"
    assert "null" not in fields.values()


def test_codec_pending_empty_string_decodes_as_none() -> None:
    meta = _sample_meta()
    fields = meta_to_hash_fields(meta)
    restored = hash_fields_to_meta(fields)
    assert restored.pending_archive_id is None
    assert restored.pending_archive_batch_key is None


def test_codec_pending_non_empty_round_trip() -> None:
    meta = _sample_meta(
        pending_archive_id="archive-1",
        pending_archive_batch_key="batch-1",
        pending_archive_message_count=3,
        pending_archive_estimated_tokens=42,
    )
    fields = meta_to_hash_fields(meta)
    assert fields["pending_archive_id"] == "archive-1"
    assert fields["pending_archive_batch_key"] == "batch-1"
    assert fields["pending_archive_message_count"] == "3"
    assert fields["pending_archive_estimated_tokens"] == "42"
    restored = hash_fields_to_meta(fields)
    assert restored.pending_archive_id == "archive-1"
    assert restored.pending_archive_batch_key == "batch-1"
    assert restored.pending_archive_message_count == 3
    assert restored.pending_archive_estimated_tokens == 42


def test_codec_status_stores_enum_literal() -> None:
    for status in (SessionStatus.ACTIVE, SessionStatus.CLOSING):
        meta = _sample_meta(status=status)
        fields = meta_to_hash_fields(meta)
        assert fields["status"] == status.value


def test_codec_integer_fields_are_decimal_strings() -> None:
    meta = _sample_meta(
        estimated_tokens=100,
        compression_version=2,
        created_time=123,
        updated_time=456,
    )
    fields = meta_to_hash_fields(meta)
    assert fields["estimated_tokens"] == "100"
    assert fields["compression_version"] == "2"
    assert fields["created_time"] == "123"
    assert fields["updated_time"] == "456"


@pytest.mark.parametrize("bad_value", ["null", "NULL"])
def test_codec_forbids_null_literal_in_pending_optional_fields(bad_value: str) -> None:
    fields = meta_to_hash_fields(_sample_meta())
    fields["pending_archive_id"] = bad_value
    restored = hash_fields_to_meta(fields)
    assert restored.pending_archive_id == bad_value
