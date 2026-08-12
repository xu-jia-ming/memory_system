"""Unit tests for aligned_memory_key helper (EXT-005)."""

from __future__ import annotations

import hashlib
import json

from memory_system.domain.services.aligned_memory_key import (
    compute_aligned_memory_key,
    normalize_memory_content_for_aggregation,
)


def test_k1_field_order_and_no_content() -> None:
    payload = {
        "memory_type": "fact",
        "final_subject_entity_id": "user:user-1",
        "predicate": "likes",
        "final_object_entity_id": None,
        "object_value": "tea",
        "event_status": None,
        "start_time": None,
        "end_time": None,
    }
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert (
        compute_aligned_memory_key(
            memory_type="fact",
            final_subject_entity_id="user:user-1",
            predicate="likes",
            final_object_entity_id=None,
            object_value="tea",
            event_status=None,
            start_time=None,
            end_time=None,
        )
        == expected
    )
    assert "content" not in canonical


def test_k2_aligned_entity_ids_participate() -> None:
    local_key = compute_aligned_memory_key(
        memory_type="fact",
        final_subject_entity_id="user:user-1",
        predicate="knows",
        final_object_entity_id="entity-local",
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
    )
    aligned_key = compute_aligned_memory_key(
        memory_type="fact",
        final_subject_entity_id="user:user-1",
        predicate="knows",
        final_object_entity_id="entity:final-db-id",
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
    )
    assert local_key != aligned_key


def test_k3_object_mutual_exclusion_reflected_in_key() -> None:
    entity_key = compute_aligned_memory_key(
        memory_type="fact",
        final_subject_entity_id="user:user-1",
        predicate="knows",
        final_object_entity_id="entity:1",
        object_value=None,
        event_status=None,
        start_time=None,
        end_time=None,
    )
    value_key = compute_aligned_memory_key(
        memory_type="fact",
        final_subject_entity_id="user:user-1",
        predicate="knows",
        final_object_entity_id=None,
        object_value="Alice",
        event_status=None,
        start_time=None,
        end_time=None,
    )
    assert entity_key != value_key


def test_normalize_nfkc_and_whitespace() -> None:
    assert normalize_memory_content_for_aggregation("  hello   world  ") == "hello world"
