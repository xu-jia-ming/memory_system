"""Contract tests for STM-011 archive event republish."""

from __future__ import annotations

import json

from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_FIELD_NAMES,
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)


def test_ct1_archive_event_republish_status_literals_stable() -> None:
    expected = {
        "success",
        "archive_not_found",
        "archive_ownership_mismatch",
        "invalid_archive",
        "kafka_publish_failed",
        "invalid_input",
    }
    assert {m.value for m in ArchiveEventRepublishStatus} == expected


def test_ct2_republish_payload_keys_match_archive_created_contract() -> None:
    event = ArchiveCreatedEvent(
        event_id="evt-001",
        archive_id="arch-001",
        user_id="user-001",
        session_id="session-001",
        created_time=1_700_000_000,
    )
    payload = json.loads(event.to_json_bytes().decode("utf-8"))
    assert set(payload.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)
    assert "archive_batch_key" not in payload
    assert "base_compression_version" not in payload


def test_ct3_event_type_constant() -> None:
    assert ARCHIVE_CREATED_EVENT_TYPE == "context.archive.created"
