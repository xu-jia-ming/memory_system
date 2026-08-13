"""Unit tests for retrieval memory validator (RET-003 U1/U2)."""

from __future__ import annotations

import pytest
from tests.unit.test_authoritative_recall_service import make_memory_snapshot

from memory_system.domain.services.retrieval_memory_validator import (
    memory_status_allowed,
    memory_type_allowed,
    normalize_memory_types,
    validate_memory_for_request,
)
from memory_system.infrastructure.elasticsearch.retrieval_filter_builder import (
    build_retrieval_status_filter,
)


@pytest.mark.parametrize(
    ("include_conflicted", "include_history", "allowed_statuses"),
    [
        (False, False, {"active"}),
        (True, False, {"active", "conflicted"}),
        (False, True, {"active", "superseded"}),
        (True, True, {"active", "conflicted", "superseded"}),
    ],
)
def test_u1_status_matrix_matches_es_filter(
    include_conflicted: bool,
    include_history: bool,
    allowed_statuses: set[str],
) -> None:
    es_filter = build_retrieval_status_filter(include_conflicted, include_history)
    if "term" in es_filter:
        es_allowed = {es_filter["term"]["status"]}
    else:
        es_allowed = set(es_filter["terms"]["status"])

    assert es_allowed == allowed_statuses
    for status in ("active", "conflicted", "superseded", "deleted"):
        assert memory_status_allowed(
            status,
            include_conflicted=include_conflicted,
            include_history=include_history,
        ) == (status in allowed_statuses)


def test_u2_memory_types_filter() -> None:
    snapshot = make_memory_snapshot(memory_type="event")
    assert memory_type_allowed("event", None) is True
    assert memory_type_allowed("event", ["fact", "event"]) is True
    assert memory_type_allowed("profile", ["fact"]) is False
    assert validate_memory_for_request(
        snapshot,
        snapshot.user_id,
        ["fact"],
        include_conflicted=False,
        include_history=False,
    ).valid is False


def test_normalize_memory_types_dedupes_and_rejects_invalid() -> None:
    assert normalize_memory_types(["fact", "fact", "event"]) == ["event", "fact"]
    assert normalize_memory_types([]) is None
    with pytest.raises(ValueError, match="invalid memory_types"):
        normalize_memory_types(["invalid"])
