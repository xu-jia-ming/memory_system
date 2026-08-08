"""Unit tests for request ID resolution."""

from __future__ import annotations

import uuid

from memory_system.api.middleware import resolve_request_id


def test_request_id_passthrough_valid_uuid4() -> None:
    value = "123e4567-e89b-42d3-a456-426614174000"
    assert resolve_request_id(value) == value


def test_request_id_generated_when_missing() -> None:
    generated = resolve_request_id(None)
    parsed = uuid.UUID(generated)
    assert parsed.version == 4


def test_request_id_invalid_string_regenerates() -> None:
    generated = resolve_request_id("not-a-uuid")
    parsed = uuid.UUID(generated)
    assert parsed.version == 4


def test_request_id_non_uuid4_version_regenerates() -> None:
    value = str(uuid.uuid1())
    generated = resolve_request_id(value)
    parsed = uuid.UUID(generated)
    assert parsed.version == 4
    assert generated != value
