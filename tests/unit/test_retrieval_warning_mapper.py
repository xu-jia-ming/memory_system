"""Unit tests for retrieval warning mapper (RET-005 U16)."""

from __future__ import annotations

from memory_system.domain.models.authoritative_recall import InternalRetrievalWarning
from memory_system.domain.models.bm25_retrieval import (
    Bm25RetrievalFailure,
    Bm25RetrievalOutcome,
)
from memory_system.domain.models.vector_retrieval import (
    VectorRetrievalFailure,
    VectorRetrievalOutcome,
)
from memory_system.domain.services.retrieval_warning_mapper import (
    WarningEntry,
    collect_and_order_warnings,
    warning_from_bm25,
    warning_from_vector,
    warnings_from_internal,
)


def test_u16_warning_order_and_dedupe() -> None:
    entries = [
        WarningEntry("retrieval_stat_update_failed"),
        WarningEntry("embedding_failed"),
        WarningEntry("bm25_retrieval_failed"),
        WarningEntry("embedding_failed"),
        WarningEntry("dirty_index_document", memory_id="mem-b"),
        WarningEntry("dirty_index_document", memory_id="mem-a"),
        WarningEntry("dirty_index_document", memory_id="mem-a"),
        WarningEntry("vector_retrieval_failed"),
        WarningEntry("graph_expansion_failed"),
        WarningEntry("stale_index_document", memory_id="mem-z"),
    ]
    ordered = collect_and_order_warnings(entries)
    assert ordered == [
        "embedding_failed",
        "bm25_retrieval_failed",
        "vector_retrieval_failed",
        "graph_expansion_failed",
        "dirty_index_document",
        "dirty_index_document",
        "stale_index_document",
        "retrieval_stat_update_failed",
    ]


def test_warning_from_bm25_channel_failure() -> None:
    outcome = Bm25RetrievalOutcome(
        outcome="failure",
        failure=Bm25RetrievalFailure(message="es down", retryable=True),
    )
    assert warning_from_bm25(outcome) == WarningEntry("bm25_retrieval_failed")


def test_warning_from_vector_skipped() -> None:
    outcome = VectorRetrievalOutcome(
        outcome="failure",
        failure=VectorRetrievalFailure(
            kind="skipped_query_too_long",
            message="too long",
            retryable=False,
        ),
    )
    assert warning_from_vector(outcome, embedding_failed=False) == WarningEntry(
        "vector_skipped_query_too_long"
    )


def test_warning_from_vector_embedding_vs_search() -> None:
    outcome = VectorRetrievalOutcome(
        outcome="failure",
        failure=VectorRetrievalFailure(
            kind="channel_failure",
            message="failed",
            retryable=True,
        ),
    )
    assert warning_from_vector(outcome, embedding_failed=True) == WarningEntry("embedding_failed")
    assert warning_from_vector(outcome, embedding_failed=False) == WarningEntry(
        "vector_retrieval_failed"
    )


def test_warnings_from_internal_maps_kinds() -> None:
    warnings = warnings_from_internal(
        [
            InternalRetrievalWarning(kind="dirty_index_document", memory_id="mem-1"),
            InternalRetrievalWarning(kind="graph_expansion_failed"),
        ]
    )
    assert warnings == [
        WarningEntry("dirty_index_document", memory_id="mem-1"),
        WarningEntry("graph_expansion_failed"),
    ]
