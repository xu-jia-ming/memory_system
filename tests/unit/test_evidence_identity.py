"""Unit tests for evidence_id helper (EXT-005)."""

from __future__ import annotations

import hashlib

from memory_system.domain.services.evidence_identity import compute_evidence_id
from memory_system.domain.services.extraction_fingerprint import compute_candidate_fingerprint


def test_e1_evidence_id_formula() -> None:
    archive_id = "archive-123"
    fingerprint = "abc123fingerprint"
    expected = hashlib.sha256(f"{archive_id}:{fingerprint}".encode()).hexdigest()
    assert compute_evidence_id(archive_id, fingerprint) == expected
    assert compute_evidence_id(archive_id, fingerprint) == expected.lower()


def test_e2_matches_persisted_candidate_fingerprint() -> None:
    archive_id = "archive-456"
    fingerprint = compute_candidate_fingerprint(
        memory_type="fact",
        content="用户喜欢咖啡",
        subject_entity_id="user",
        predicate="likes",
        object_entity_id=None,
        object_value="coffee",
        event_status=None,
        start_time=None,
        end_time=None,
        original_time_text=None,
        source_message_ids=["msg_000001"],
    )
    assert compute_evidence_id(archive_id, fingerprint) == compute_evidence_id(
        archive_id, fingerprint
    )
