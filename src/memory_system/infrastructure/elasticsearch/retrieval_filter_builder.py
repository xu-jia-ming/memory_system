"""Shared Elasticsearch retrieval filters for BM25 and Vector channels."""

from __future__ import annotations

from typing import Any


def build_retrieval_status_filter(
    include_conflicted: bool,
    include_history: bool,
) -> dict[str, Any]:
    if not include_conflicted and not include_history:
        return {"term": {"status": "active"}}
    if include_conflicted and not include_history:
        return {"terms": {"status": ["active", "conflicted"]}}
    if not include_conflicted and include_history:
        return {"terms": {"status": ["active", "superseded"]}}
    return {"terms": {"status": ["active", "conflicted", "superseded"]}}


def build_retrieval_filters(
    *,
    user_id: str,
    memory_types: list[str] | None,
    include_conflicted: bool,
    include_history: bool,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [{"term": {"user_id": user_id}}]

    if memory_types:
        filters.append({"terms": {"memory_type": memory_types}})

    filters.append(
        build_retrieval_status_filter(include_conflicted, include_history),
    )
    return filters
