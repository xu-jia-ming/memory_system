"""RET-004 Evidence aggregation pure functions (§2.2.12)."""

from __future__ import annotations

from dataclasses import dataclass

from memory_system.domain.models.retrieval_scoring import EvidenceAggregationResult


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    """Single Evidence row from Neo4j batch read."""

    evidence_id: str
    memory_id: str
    source_time_end: int | None
    source_message_ids: list[str]


def _evidence_sort_key(row: EvidenceRow) -> tuple[int, str]:
    """source_time_end DESC (null→0), evidence_id ASC (LD-2)."""
    return (-(row.source_time_end or 0), row.evidence_id)


def aggregate_evidence_for_memory(
    evidence_rows: list[EvidenceRow],
    max_source_message_ids: int,
) -> EvidenceAggregationResult:
    """Deterministic source_message_ids merge for one memory (§5.3)."""
    sorted_rows = sorted(evidence_rows, key=_evidence_sort_key)
    evidence_count = len(sorted_rows)

    seen: set[str] = set()
    merged: list[str] = []
    for row in sorted_rows:
        for message_id in row.source_message_ids:
            if message_id in seen:
                continue
            seen.add(message_id)
            merged.append(message_id)
            if len(merged) >= max_source_message_ids:
                break
        if len(merged) >= max_source_message_ids:
            break

    return EvidenceAggregationResult(
        evidence_count=evidence_count,
        source_message_ids=merged,
    )


def group_evidence_rows_by_memory(
    rows: list[EvidenceRow],
) -> dict[str, list[EvidenceRow]]:
    """Group evidence rows by memory_id preserving insertion order of keys."""
    grouped: dict[str, list[EvidenceRow]] = {}
    for row in rows:
        grouped.setdefault(row.memory_id, []).append(row)
    return grouped
