"""Unit tests for evidence aggregation pure functions (RET-004 NC-8)."""

from __future__ import annotations

from memory_system.domain.services.evidence_aggregation import (
    EvidenceRow,
    aggregate_evidence_for_memory,
)


def test_nc8_evidence_aggregation_order_dedup_and_cap() -> None:
    rows = [
        EvidenceRow("e2", "mem-1", 200, ["m2", "m1"]),
        EvidenceRow("e1", "mem-1", 200, ["m3"]),
        EvidenceRow("e3", "mem-1", 100, ["m1", "m4"]),
    ]
    result = aggregate_evidence_for_memory(rows, max_source_message_ids=20)
    assert result.evidence_count == 3
    assert result.source_message_ids == ["m3", "m2", "m1", "m4"]


def test_nc8_cap_source_message_ids() -> None:
    rows = [
        EvidenceRow("e2", "mem-1", 200, ["m2", "m1"]),
        EvidenceRow("e1", "mem-1", 200, ["m3"]),
        EvidenceRow("e3", "mem-1", 100, ["m1", "m4"]),
    ]
    result = aggregate_evidence_for_memory(rows, max_source_message_ids=2)
    assert result.evidence_count == 3
    assert result.source_message_ids == ["m3", "m2"]


def test_null_source_time_end_sorted_last() -> None:
    rows = [
        EvidenceRow("e1", "mem-1", None, ["m-null"]),
        EvidenceRow("e2", "mem-1", 100, ["m-known"]),
    ]
    result = aggregate_evidence_for_memory(rows, max_source_message_ids=20)
    assert result.source_message_ids == ["m-known", "m-null"]


def test_empty_evidence_rows() -> None:
    result = aggregate_evidence_for_memory([], max_source_message_ids=20)
    assert result.evidence_count == 0
    assert result.source_message_ids == []
