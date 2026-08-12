"""EXT-005 evidence identity helpers (§2.1.13 step 1)."""

from __future__ import annotations

import hashlib


def compute_evidence_id(archive_id: str, candidate_fingerprint: str) -> str:
    """Return lowercase hex SHA-256 of archive_id:candidate_fingerprint (UTF-8)."""
    payload = f"{archive_id}:{candidate_fingerprint}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
