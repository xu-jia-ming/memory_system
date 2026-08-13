"""RET-004 ACT-R scoring pure functions (§2.2.11)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from memory_system.domain.models.authoritative_recall import ValidatedRetrievalCandidate
from memory_system.domain.models.retrieval_scoring import ActRScoreComponents
from memory_system.settings.models import MemoryRetrievalSettings

_LN_2 = math.log(2)
_LN_21 = math.log(21)
_SECONDS_PER_DAY = 86400


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def select_retrieval_score(candidate: ValidatedRetrievalCandidate) -> float | None:
    """Select retrieval score by candidate_origin; None means skip candidate."""
    if candidate.candidate_origin == "direct":
        if candidate.normalized_retrieval_score is None:
            return None
        return candidate.normalized_retrieval_score
    if candidate.graph_retrieval_score is None:
        return None
    return candidate.graph_retrieval_score


def compute_frequency_score(retrieval_count: int) -> float:
    """§4.1 #4 — saturates at retrieval_count >= 20."""
    if retrieval_count >= 20:
        return 1.0
    return min(1.0, math.log(1 + retrieval_count) / _LN_21)


def compute_recency_score(
    last_retrieved_time: int | None,
    latest_source_time: int | None,
    current_time: int,
    half_life_days: int,
) -> float:
    """§4.1 #5 — reference_time uses null→0 for both inputs (LD-1)."""
    reference_time = max(last_retrieved_time or 0, latest_source_time or 0)
    age_days = max(0, current_time - reference_time) / _SECONDS_PER_DAY
    if half_life_days <= 0:
        return 0.0
    return math.exp(-_LN_2 * age_days / half_life_days)


def compute_act_r_components(
    candidate: ValidatedRetrievalCandidate,
    current_time: int,
    settings: MemoryRetrievalSettings,
) -> ActRScoreComponents | None:
    """Compute all ACT-R components; None if required retrieval score is missing."""
    retrieval_score = select_retrieval_score(candidate)
    if retrieval_score is None:
        return None

    memory = candidate.memory
    return ActRScoreComponents(
        retrieval_score=_clamp01(retrieval_score),
        importance_score=_clamp01(memory.importance),
        confidence_score=_clamp01(memory.confidence),
        frequency_score=_clamp01(compute_frequency_score(memory.retrieval_count)),
        recency_score=_clamp01(
            compute_recency_score(
                memory.last_retrieved_time,
                memory.latest_source_time,
                current_time,
                settings.recency_half_life_days,
            )
        ),
    )


def compute_final_score(
    components: ActRScoreComponents,
    status: str,
    settings: MemoryRetrievalSettings,
) -> float:
    """Weighted sum, status penalty, clamp, round to 6 decimals."""
    weighted = (
        settings.retrieval_score_weight * components.retrieval_score
        + settings.importance_weight * components.importance_score
        + settings.confidence_weight * components.confidence_score
        + settings.frequency_weight * components.frequency_score
        + settings.recency_weight * components.recency_score
    )
    status_penalty = 1.0
    if status == "conflicted":
        status_penalty = settings.conflicted_penalty
    elif status == "superseded":
        status_penalty = settings.superseded_penalty
    return round(_clamp01(weighted * status_penalty), 6)


@dataclass(frozen=True, slots=True)
class ScoredCandidateIntermediate:
    """Intermediate scored candidate before Top-K truncation and Evidence load."""

    candidate: ValidatedRetrievalCandidate
    act_r_components: ActRScoreComponents
    final_score: float


def _sort_key(item: ScoredCandidateIntermediate) -> tuple[float, int, float, str]:
    memory = item.candidate.memory
    latest_source_time = memory.latest_source_time or 0
    return (
        -item.final_score,
        -latest_source_time,
        -memory.importance,
        item.candidate.memory_id,
    )


def sort_scored_candidates(
    candidates: list[ScoredCandidateIntermediate],
) -> list[ScoredCandidateIntermediate]:
    """§7.1 ordering: final_score DESC, latest_source_time DESC, importance DESC, memory_id ASC."""
    return sorted(candidates, key=_sort_key)
