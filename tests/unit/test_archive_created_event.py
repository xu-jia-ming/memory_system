"""Unit tests for ArchiveCreatedEvent serialization (six fields only)."""

from __future__ import annotations

import json

from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_FIELD_NAMES,
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)


def test_event_serializes_exactly_six_fields() -> None:
    event = ArchiveCreatedEvent(
        event_id="evt-1",
        archive_id="arch-1",
        user_id="user_001",
        session_id="session_001",
        created_time=1_700_000_000,
    )
    payload = json.loads(event.to_json_bytes().decode("utf-8"))
    assert set(payload.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert payload["event_type"] == ARCHIVE_CREATED_EVENT_TYPE
    assert payload["event_id"] == "evt-1"
    assert payload["archive_id"] == "arch-1"
    assert payload["user_id"] == "user_001"
    assert payload["session_id"] == "session_001"
    assert payload["created_time"] == 1_700_000_000
    assert "archive_batch_key" not in payload
    assert "base_compression_version" not in payload
