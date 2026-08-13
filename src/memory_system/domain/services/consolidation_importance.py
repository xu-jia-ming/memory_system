"""CON-001 consolidation importance pure functions (§2.3.5–§2.3.7).

§2.3.8 reinforcement and soft-forget rules are documentation-only in this module;
no soft-forget side effects (ES delete, status change, or content clearing) are
implemented here — importance reduction is expressed solely through these formulas.
"""

from __future__ import annotations

import math

from memory_system.domain.models.consolidation_importance import (
    VALID_MEMORY_STATUSES,
    VALID_MEMORY_TYPES,
    ConsolidationImportanceComponents,
    ConsolidationImportanceInput,
    ConsolidationImportanceOutcome,
    ConsolidationImportanceSkip,
    ConsolidationImportanceSuccess,
)
from memory_system.domain.services.reconciliation_plan_builder import IMPORTANCE_BY_TYPE
from memory_system.settings.models import MemoryConsolidationSettings

_LN_2 = math.log(2)
_SECONDS_PER_DAY = 86400


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)


def _validate_input(input: ConsolidationImportanceInput) -> None:
    if input.memory_type not in VALID_MEMORY_TYPES:
        raise ValueError(f"invalid memory_type: {input.memory_type}")
    if input.status not in VALID_MEMORY_STATUSES:
        raise ValueError(f"invalid status: {input.status}")
    if input.created_time < 0:
        raise ValueError("created_time must be >= 0")
    if input.evaluation_time < 0:
        raise ValueError("evaluation_time must be >= 0")
    if input.independent_archive_count < 0:
        raise ValueError("independent_archive_count must be >= 0")


def base_importance_for_type(memory_type: str) -> float:
    """§2.3.5 #1 — lookup from IMPORTANCE_BY_TYPE."""
    return IMPORTANCE_BY_TYPE[memory_type]


def compute_confidence_score(confidence: float) -> float:
    """Clamp confidence to [0, 1]."""
    return _clamp01(confidence)


def compute_evidence_score(count: int, saturation_count: int) -> float:
    """§2.3.5 #3 — count must be > 0."""
    if count <= 0:
        raise ValueError("independent_archive_count must be > 0 to compute evidence_score")
    return min(
        1.0,
        math.log(1 + count) / math.log(1 + saturation_count),
    )


def compute_reference_time(latest_source_time: int | None, created_time: int) -> int:
    """§2.3.5 #4 — latest_source_time null treated as 0."""
    return max(latest_source_time or 0, created_time)


def compute_inactive_days(reference_time: int, evaluation_time: int) -> float:
    """§2.3.5 #4 — non-negative days since reference."""
    return max(0.0, (evaluation_time - reference_time) / _SECONDS_PER_DAY)


def half_life_days_for(
    memory_type: str,
    status: str,
    settings: MemoryConsolidationSettings,
) -> int:
    """§2.3.6 — type half-life; superseded uses shorter effective half-life."""
    type_half_life_map = {
        "profile": settings.profile_half_life_days,
        "fact": settings.fact_half_life_days,
        "preference": settings.preference_half_life_days,
        "event": settings.event_half_life_days,
    }
    half_life_days = type_half_life_map[memory_type]
    if status == "superseded":
        half_life_days = min(half_life_days, settings.superseded_half_life_days)
    return half_life_days


def compute_recency_score(inactive_days: float, half_life_days: int) -> float:
    """§2.3.6 — exponential decay with half-life."""
    if half_life_days <= 0:
        return 0.0
    return math.exp(-_LN_2 * inactive_days / half_life_days)


def compute_reinforcement_score(
    confidence_score: float,
    evidence_score: float,
    settings: MemoryConsolidationSettings,
) -> float:
    """§2.3.7 — weighted confidence and evidence."""
    return (
        settings.confidence_weight * confidence_score
        + settings.evidence_weight * evidence_score
    )


def compute_effective_min_importance(
    status: str,
    settings: MemoryConsolidationSettings,
) -> float:
    """§2.3.7 — conflicted uses higher floor."""
    if status == "conflicted":
        return settings.conflicted_min_importance
    return settings.min_importance


def compute_raw_importance(
    base_importance: float,
    recency_score: float,
    reinforcement_score: float,
    settings: MemoryConsolidationSettings,
) -> float:
    """§2.3.7 — base decay plus reinforcement bonus."""
    return (
        base_importance * recency_score
        + settings.reinforcement_bonus_weight * reinforcement_score
    )


def compute_new_importance(
    raw_importance: float,
    status: str,
    settings: MemoryConsolidationSettings,
) -> float:
    """Clamp raw importance and round to 4 decimal places."""
    effective_min = compute_effective_min_importance(status, settings)
    clamped = _clamp(raw_importance, effective_min, settings.max_importance)
    return round(clamped, 4)


def compute_consolidation_importance_components(
    input: ConsolidationImportanceInput,
    settings: MemoryConsolidationSettings,
) -> ConsolidationImportanceComponents:
    """Compute intermediate components; caller must ensure count > 0."""
    _validate_input(input)
    if input.independent_archive_count == 0:
        raise ValueError("independent_archive_count must be > 0 to compute components")

    base = base_importance_for_type(input.memory_type)
    confidence_score = compute_confidence_score(input.confidence)
    evidence_score = compute_evidence_score(
        input.independent_archive_count,
        settings.evidence_saturation_count,
    )
    reference_time = compute_reference_time(input.latest_source_time, input.created_time)
    inactive_days = compute_inactive_days(reference_time, input.evaluation_time)
    half_life = half_life_days_for(input.memory_type, input.status, settings)
    recency_score = compute_recency_score(inactive_days, half_life)
    reinforcement_score = compute_reinforcement_score(
        confidence_score,
        evidence_score,
        settings,
    )
    raw_importance = compute_raw_importance(
        base,
        recency_score,
        reinforcement_score,
        settings,
    )
    return ConsolidationImportanceComponents(
        base_importance=base,
        confidence_score=confidence_score,
        evidence_score=evidence_score,
        inactive_days=inactive_days,
        recency_score=recency_score,
        reinforcement_score=reinforcement_score,
        raw_importance=raw_importance,
    )


def compute_consolidation_importance(
    input: ConsolidationImportanceInput,
    settings: MemoryConsolidationSettings,
) -> ConsolidationImportanceOutcome:
    """Main entry — new_importance or missing_evidence skip."""
    _validate_input(input)
    if input.independent_archive_count == 0:
        return ConsolidationImportanceSkip(reason="missing_evidence")

    components = compute_consolidation_importance_components(input, settings)
    new_importance = compute_new_importance(
        components.raw_importance,
        input.status,
        settings,
    )
    return ConsolidationImportanceSuccess(new_importance=new_importance)
