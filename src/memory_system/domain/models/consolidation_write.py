"""CON-003 consolidation optimistic-lock batch write models (§2.3.9)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

InvalidWriteReason = Literal["invalid_candidate"]


@dataclass(frozen=True, slots=True)
class ConsolidationWriteRow:
    memory_id: str
    new_importance: float
    expected_memory_version: int


@dataclass(frozen=True, slots=True)
class ConsolidationWriteBatchRequest:
    user_id: str
    evaluation_time: int
    rows: list[ConsolidationWriteRow]


@dataclass(frozen=True, slots=True)
class ConsolidationInvalidWriteCandidate:
    memory_id: str
    reason: InvalidWriteReason


@dataclass(frozen=True, slots=True)
class ConsolidationWriteBatchResult:
    user_id: str
    evaluation_time: int
    input_count: int
    valid_count: int
    updated_count: int
    version_conflict_count: int
    invalid_candidates: list[ConsolidationInvalidWriteCandidate]
    write_executed: bool
