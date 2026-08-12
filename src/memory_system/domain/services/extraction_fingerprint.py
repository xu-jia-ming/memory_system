"""EXT-003 candidate fingerprint helper (Appendix B §B.7)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _dedupe_lex_sort_source_ids(source_message_ids: list[str]) -> list[str]:
    return sorted(set(source_message_ids))


def fingerprint_payload_from_memory_fields(
    *,
    memory_type: str,
    content: str,
    subject_entity_id: str,
    predicate: str,
    object_entity_id: str | None,
    object_value: str | None,
    event_status: str | None,
    start_time: str | None,
    end_time: str | None,
    original_time_text: str | None,
    source_message_ids: list[str],
) -> list[Any]:
    """Build the fixed-order JSON array payload (before serialization)."""
    return [
        memory_type,
        content,
        subject_entity_id,
        predicate,
        object_entity_id,
        object_value,
        event_status,
        start_time,
        end_time,
        original_time_text,
        _dedupe_lex_sort_source_ids(source_message_ids),
    ]


def compute_candidate_fingerprint(
    *,
    memory_type: str,
    content: str,
    subject_entity_id: str,
    predicate: str,
    object_entity_id: str | None,
    object_value: str | None,
    event_status: str | None,
    start_time: str | None,
    end_time: str | None,
    original_time_text: str | None,
    source_message_ids: list[str],
) -> str:
    """Return SHA-256 hex digest of the canonical fingerprint bytes."""
    payload = fingerprint_payload_from_memory_fields(
        memory_type=memory_type,
        content=content,
        subject_entity_id=subject_entity_id,
        predicate=predicate,
        object_entity_id=object_entity_id,
        object_value=object_value,
        event_status=event_status,
        start_time=start_time,
        end_time=end_time,
        original_time_text=original_time_text,
        source_message_ids=source_message_ids,
    )
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_fingerprint_bytes(
    *,
    memory_type: str,
    content: str,
    subject_entity_id: str,
    predicate: str,
    object_entity_id: str | None,
    object_value: str | None,
    event_status: str | None,
    start_time: str | None,
    end_time: str | None,
    original_time_text: str | None,
    source_message_ids: list[str],
) -> bytes:
    """Return UTF-8 bytes of the compact JSON array (for contract tests)."""
    payload = fingerprint_payload_from_memory_fields(
        memory_type=memory_type,
        content=content,
        subject_entity_id=subject_entity_id,
        predicate=predicate,
        object_entity_id=object_entity_id,
        object_value=object_value,
        event_status=event_status,
        start_time=start_time,
        end_time=end_time,
        original_time_text=original_time_text,
        source_message_ids=source_message_ids,
    )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
