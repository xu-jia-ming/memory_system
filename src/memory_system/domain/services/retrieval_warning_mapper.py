"""Collect, dedupe, and order HTTP retrieval warnings (§2.2.15 / §7.4)."""

from __future__ import annotations

from dataclasses import dataclass

from memory_system.domain.models.authoritative_recall import InternalRetrievalWarning
from memory_system.domain.models.bm25_retrieval import Bm25RetrievalOutcome
from memory_system.domain.models.vector_retrieval import VectorRetrievalOutcome

WARNING_ORDER: tuple[str, ...] = (
    "embedding_failed",
    "vector_skipped_query_too_long",
    "bm25_retrieval_failed",
    "vector_retrieval_failed",
    "rerank_failed",
    "graph_expansion_failed",
    "dirty_index_document",
    "stale_index_document",
    "retrieval_stat_update_failed",
    "retrieval_timeout_degraded",
)

_CHANNEL_KINDS = frozenset(
    {
        "embedding_failed",
        "vector_skipped_query_too_long",
        "bm25_retrieval_failed",
        "vector_retrieval_failed",
        "rerank_failed",
        "graph_expansion_failed",
        "retrieval_stat_update_failed",
        "retrieval_timeout_degraded",
    }
)

_PER_MEMORY_KINDS = frozenset({"dirty_index_document", "stale_index_document"})

_ORDER_INDEX = {kind: index for index, kind in enumerate(WARNING_ORDER)}


@dataclass(frozen=True)
class WarningEntry:
    kind: str
    memory_id: str | None = None


def warning_from_bm25(outcome: Bm25RetrievalOutcome) -> WarningEntry | None:
    if outcome.outcome == "failure" and outcome.failure is not None:
        if outcome.failure.kind == "channel_failure":
            return WarningEntry("bm25_retrieval_failed")
    return None


def warning_from_vector(
    outcome: VectorRetrievalOutcome,
    *,
    embedding_failed: bool,
) -> WarningEntry | None:
    if outcome.outcome != "failure" or outcome.failure is None:
        return None
    if outcome.failure.kind == "skipped_query_too_long":
        return WarningEntry("vector_skipped_query_too_long")
    if embedding_failed:
        return WarningEntry("embedding_failed")
    return WarningEntry("vector_retrieval_failed")


def warnings_from_internal(
    warnings: list[InternalRetrievalWarning],
) -> list[WarningEntry]:
    entries: list[WarningEntry] = []
    for warning in warnings:
        if warning.kind in _PER_MEMORY_KINDS:
            entries.append(WarningEntry(warning.kind, memory_id=warning.memory_id))
        elif warning.kind == "graph_expansion_failed":
            entries.append(WarningEntry("graph_expansion_failed"))
        elif warning.kind == "rerank_failed":
            entries.append(WarningEntry("rerank_failed"))
    return entries


def collect_and_order_warnings(entries: list[WarningEntry]) -> list[str]:
    seen_channel: set[str] = set()
    seen_per_memory: set[tuple[str, str]] = set()
    ordered_items: list[tuple[int, str, str]] = []

    for entry in entries:
        if entry.kind in _CHANNEL_KINDS:
            if entry.kind not in seen_channel:
                seen_channel.add(entry.kind)
                ordered_items.append((_ORDER_INDEX[entry.kind], "", entry.kind))
        elif entry.kind in _PER_MEMORY_KINDS:
            memory_id = entry.memory_id or ""
            key = (entry.kind, memory_id)
            if key not in seen_per_memory:
                seen_per_memory.add(key)
                ordered_items.append((_ORDER_INDEX[entry.kind], memory_id, entry.kind))

    ordered_items.sort(key=lambda item: (item[0], item[1]))
    return [kind for _, _, kind in ordered_items]
