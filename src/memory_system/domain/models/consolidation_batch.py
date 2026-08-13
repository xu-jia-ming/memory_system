"""CON-002 consolidation batch read models (§2.3.4 cursor pagination + evidence count)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BatchSkipReason = Literal["missing_evidence", "invalid_memory_state"]


@dataclass(frozen=True, slots=True)
class ConsolidationBatchRequest:
    user_id: str
    evaluation_time: int
    cursor: str | None
    batch_size: int | None = None


@dataclass(frozen=True, slots=True)
class ConsolidationScoredCandidate:
    memory_id: str
    new_importance: float
    memory_version: int


@dataclass(frozen=True, slots=True)
class ConsolidationSkippedCandidate:
    memory_id: str
    reason: BatchSkipReason


@dataclass(frozen=True, slots=True)
class ConsolidationBatchResult:
    user_id: str
    evaluation_time: int
    cursor_in: str | None
    batch_size: int
    memories_returned: int
    next_cursor: str | None
    scored: list[ConsolidationScoredCandidate]
    skipped: list[ConsolidationSkippedCandidate]
    has_more: bool


@dataclass(frozen=True, slots=True)
class ConsolidationMemoryRow:
    """Repository → service intermediate row before CON-001 handoff."""

    memory_id: str
    memory_version: int | None
    memory_type: str | None
    confidence: float | None
    status: str | None
    created_time: int | None
    latest_source_time: int | None
    independent_archive_count: int
    mapping_valid: bool
