"""EXT-005 aligned_memory_key and content normalization (§2.1.11 B.1 / SF-001)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata


def normalize_memory_content_for_aggregation(content: str) -> str:
    """NFKC, compress whitespace, strip (§2.1.11 A/B aggregation)."""
    normalized = unicodedata.normalize("NFKC", content)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def compute_aligned_memory_key(
    *,
    memory_type: str,
    final_subject_entity_id: str,
    predicate: str,
    final_object_entity_id: str | None,
    object_value: str | None,
    event_status: str | None,
    start_time: str | None,
    end_time: str | None,
) -> str:
    """Return lowercase hex SHA-256 of canonical JSON structural key (§2.1.11 B.1)."""
    payload = {
        "memory_type": memory_type,
        "final_subject_entity_id": final_subject_entity_id,
        "predicate": predicate,
        "final_object_entity_id": final_object_entity_id,
        "object_value": object_value,
        "event_status": event_status,
        "start_time": start_time,
        "end_time": end_time,
    }
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
