"""Unit tests for shared retrieval filter builder."""

from __future__ import annotations

from memory_system.infrastructure.elasticsearch.retrieval_filter_builder import (
    build_retrieval_filters,
    build_retrieval_status_filter,
)


def test_u3_default_filters_active_only_no_memory_types() -> None:
    filters = build_retrieval_filters(
        user_id="user-1",
        memory_types=None,
        include_conflicted=False,
        include_history=False,
    )

    assert {"term": {"user_id": "user-1"}} in filters
    assert {"term": {"status": "active"}} in filters
    assert not any("memory_type" in str(filter_item) for filter_item in filters)


def test_u4_status_filter_matrix() -> None:
    cases = [
        (False, False, {"term": {"status": "active"}}),
        (True, False, {"terms": {"status": ["active", "conflicted"]}}),
        (False, True, {"terms": {"status": ["active", "superseded"]}}),
        (
            True,
            True,
            {"terms": {"status": ["active", "conflicted", "superseded"]}},
        ),
    ]
    for include_conflicted, include_history, expected in cases:
        assert (
            build_retrieval_status_filter(include_conflicted, include_history) == expected
        )
        filters = build_retrieval_filters(
            user_id="user-1",
            memory_types=None,
            include_conflicted=include_conflicted,
            include_history=include_history,
        )
        assert expected in filters


def test_memory_types_filter_included_when_present() -> None:
    filters = build_retrieval_filters(
        user_id="user-1",
        memory_types=["fact", "event"],
        include_conflicted=False,
        include_history=False,
    )
    assert {"terms": {"memory_type": ["fact", "event"]}} in filters
