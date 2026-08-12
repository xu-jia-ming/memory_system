"""§2.1.15 manual retry / rebuild error-code policy for extraction admin API."""

from __future__ import annotations

MANUAL_RETRY_ALLOWED_ERROR_CODES: frozenset[str] = frozenset(
    {
        "llm_timeout",
        "llm_request_failed",
        "llm_invalid_output",
        "entity_alignment_failed",
        "graph_query_failed",
        "graph_write_failed",
        "retrieval_index_write_failed",
        "kafka_publish_failed",
    }
)

MANUAL_RETRY_FORBIDDEN_ERROR_CODES: frozenset[str] = frozenset(
    {
        "archive_not_found",
        "archive_ownership_mismatch",
        "invalid_archive",
        "archive_too_large",
        "reconciliation_plan_conflict",
        "memory_search_text_too_long",
    }
)

REBUILD_ALLOWED_ERROR_CODES: frozenset[str] = frozenset({"reconciliation_plan_conflict"})
