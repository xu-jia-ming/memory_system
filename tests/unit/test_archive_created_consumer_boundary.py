"""Unit tests for archive-created consumer-boundary validation (EXT-001 C4/MF-001)."""

from __future__ import annotations

import json

import pytest

from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_FIELD_NAMES,
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.infrastructure.kafka.archive_created_consumer import (
    MalformedArchiveCreatedEventError,
    parse_archive_created_event_value,
    reject_empty_string_ids,
    validate_archive_created_payload_keys,
)

VALID = {
    "event_id": "evt-1",
    "event_type": ARCHIVE_CREATED_EVENT_TYPE,
    "archive_id": "arch-1",
    "user_id": "user-1",
    "session_id": "sess-1",
    "created_time": 1_700_000_000,
}


def test_exact_six_keys_ok() -> None:
    validate_archive_created_payload_keys(VALID)
    event = parse_archive_created_event_value(
        json.dumps(VALID, separators=(",", ":")).encode("utf-8")
    )
    assert event.archive_id == "arch-1"
    assert event.user_id == "user-1"


def test_extra_unknown_key_malformed() -> None:
    payload = {**VALID, "extra_field": "nope"}
    with pytest.raises(MalformedArchiveCreatedEventError, match="extra"):
        parse_archive_created_event_value(json.dumps(payload).encode("utf-8"))


def test_missing_key_malformed() -> None:
    payload = {k: v for k, v in VALID.items() if k != "session_id"}
    with pytest.raises(MalformedArchiveCreatedEventError, match="missing"):
        parse_archive_created_event_value(json.dumps(payload).encode("utf-8"))


@pytest.mark.parametrize("field", ["archive_id", "user_id", "event_id", "session_id"])
def test_empty_string_id_malformed(field: str) -> None:
    payload = {**VALID, field: ""}
    with pytest.raises(MalformedArchiveCreatedEventError, match="empty-string"):
        parse_archive_created_event_value(json.dumps(payload).encode("utf-8"))


def test_reject_empty_string_ids_helper() -> None:
    with pytest.raises(MalformedArchiveCreatedEventError):
        reject_empty_string_ids({**VALID, "archive_id": ""})


def test_invalid_json_malformed() -> None:
    with pytest.raises(MalformedArchiveCreatedEventError, match="JSON"):
        parse_archive_created_event_value(b"{not-json")


def test_non_object_json_malformed() -> None:
    with pytest.raises(MalformedArchiveCreatedEventError, match="object"):
        parse_archive_created_event_value(b"[1,2]")


def test_invalid_event_type_malformed() -> None:
    payload = {**VALID, "event_type": "other.event"}
    with pytest.raises(MalformedArchiveCreatedEventError, match="event_type"):
        parse_archive_created_event_value(json.dumps(payload).encode("utf-8"))


def test_archive_created_event_model_still_accepts_extra_keys() -> None:
    """MF-001: model itself is unchanged (no extra=forbid); reject only at boundary."""
    payload = {**VALID, "rogue": 1}
    # Direct model_validate must NOT fail solely because of extra keys.
    event = ArchiveCreatedEvent.model_validate(payload)
    assert event.archive_id == "arch-1"
    assert set(ARCHIVE_CREATED_EVENT_FIELD_NAMES) == {
        "event_id",
        "event_type",
        "archive_id",
        "user_id",
        "session_id",
        "created_time",
    }
    # Boundary still rejects.
    with pytest.raises(MalformedArchiveCreatedEventError):
        parse_archive_created_event_value(json.dumps(payload).encode("utf-8"))


def test_type_error_malformed() -> None:
    payload = {**VALID, "created_time": "not-int"}
    with pytest.raises(MalformedArchiveCreatedEventError, match="validation"):
        parse_archive_created_event_value(json.dumps(payload).encode("utf-8"))
