"""CON-001 consolidation importance input/output models (§2.3.5–§2.3.7).

§2.3.8 reinforcement and soft-forget rules are documentation-only in this module;
no soft-forget side effects (ES delete, status change, or content clearing) are
implemented here — importance reduction is expressed solely through these formulas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MemoryType = Literal["profile", "fact", "preference", "event"]
MemoryStatus = Literal["active", "conflicted", "superseded"]
SkipReason = Literal["missing_evidence"]

VALID_MEMORY_TYPES: frozenset[str] = frozenset({"profile", "fact", "preference", "event"})
VALID_MEMORY_STATUSES: frozenset[str] = frozenset({"active", "conflicted", "superseded"})


@dataclass(frozen=True, slots=True)
class ConsolidationImportanceInput:
    memory_type: MemoryType
    confidence: float
    status: MemoryStatus
    created_time: int
    latest_source_time: int | None
    independent_archive_count: int
    evaluation_time: int


@dataclass(frozen=True, slots=True)
class ConsolidationImportanceSuccess:
    new_importance: float


@dataclass(frozen=True, slots=True)
class ConsolidationImportanceSkip:
    reason: SkipReason


ConsolidationImportanceOutcome = ConsolidationImportanceSuccess | ConsolidationImportanceSkip


@dataclass(frozen=True, slots=True)
class ConsolidationImportanceComponents:
    base_importance: float
    confidence_score: float
    evidence_score: float
    inactive_days: float
    recency_score: float
    reinforcement_score: float
    raw_importance: float
