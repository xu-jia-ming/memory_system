"""Unit tests for extraction fingerprint helper (EXT-003)."""

from __future__ import annotations

import hashlib

from memory_system.domain.services.extraction_fingerprint import (
    canonical_fingerprint_bytes,
    compute_candidate_fingerprint,
)


def test_u22_same_candidate_same_digest() -> None:
    kwargs = {
        "memory_type": "fact",
        "content": "stable content",
        "subject_entity_id": "user",
        "predicate": "likes",
        "object_entity_id": None,
        "object_value": "tea",
        "event_status": None,
        "start_time": None,
        "end_time": None,
        "original_time_text": None,
        "source_message_ids": ["msg_a", "msg_b"],
    }
    first = compute_candidate_fingerprint(**kwargs)
    second = compute_candidate_fingerprint(**kwargs)
    assert first == second
    assert len(first) == 64


def test_u23_source_ids_sorted_for_fingerprint() -> None:
    base = {
        "memory_type": "fact",
        "content": "stable content",
        "subject_entity_id": "user",
        "predicate": "likes",
        "object_entity_id": None,
        "object_value": "tea",
        "event_status": None,
        "start_time": None,
        "end_time": None,
        "original_time_text": None,
    }
    forward = compute_candidate_fingerprint(**base, source_message_ids=["msg_b", "msg_a"])
    reverse = compute_candidate_fingerprint(**base, source_message_ids=["msg_a", "msg_b"])
    assert forward == reverse


def test_u24_unicode_ensure_ascii_false() -> None:
    canonical = canonical_fingerprint_bytes(
        memory_type="fact",
        content="中文内容",
        subject_entity_id="user",
        predicate="likes",
        object_entity_id=None,
        object_value="🙂",
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text="昨天",
        source_message_ids=["msg_1"],
    )
    assert "中文内容" in canonical.decode("utf-8")
    assert "\\u" not in canonical.decode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    assert digest == compute_candidate_fingerprint(
        memory_type="fact",
        content="中文内容",
        subject_entity_id="user",
        predicate="likes",
        object_entity_id=None,
        object_value="🙂",
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text="昨天",
        source_message_ids=["msg_1"],
    )


def test_candidate_source_time_excluded_from_fingerprint() -> None:
    kwargs = {
        "memory_type": "fact",
        "content": "content",
        "subject_entity_id": "user",
        "predicate": "likes",
        "object_entity_id": None,
        "object_value": "tea",
        "event_status": None,
        "start_time": None,
        "end_time": None,
        "original_time_text": None,
        "source_message_ids": ["msg_1"],
    }
    digest = compute_candidate_fingerprint(**kwargs)
    canonical = canonical_fingerprint_bytes(**kwargs).decode("utf-8")
    assert "candidate_source_time" not in canonical
    assert "candidate_fingerprint" not in canonical
    assert digest == compute_candidate_fingerprint(**kwargs)
