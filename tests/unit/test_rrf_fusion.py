"""Unit tests for RRF fusion."""

from __future__ import annotations

from memory_system.domain.models.bm25_retrieval import (
    Bm25RetrievalFailure,
    Bm25RetrievalHit,
    Bm25RetrievalOutcome,
    Bm25RetrievalSuccess,
)
from memory_system.domain.models.vector_retrieval import (
    VectorRetrievalFailure,
    VectorRetrievalHit,
    VectorRetrievalOutcome,
    VectorRetrievalSuccess,
)
from memory_system.domain.services.rrf_fusion import fuse_rrf

RRF_K = 60
FUSED_TOP_N = 30
USER_ID = "user-1"


def _bm25_success(hits: list[Bm25RetrievalHit]) -> Bm25RetrievalOutcome:
    return Bm25RetrievalOutcome(
        outcome="success",
        success=Bm25RetrievalSuccess(user_id=USER_ID, hits=hits, total_hits=len(hits)),
    )


def _vector_success(hits: list[VectorRetrievalHit]) -> VectorRetrievalOutcome:
    return VectorRetrievalOutcome(
        outcome="success",
        success=VectorRetrievalSuccess(user_id=USER_ID, hits=hits, total_hits=len(hits)),
    )


def _bm25_failure(*, retryable: bool = True) -> Bm25RetrievalOutcome:
    return Bm25RetrievalOutcome(
        outcome="failure",
        failure=Bm25RetrievalFailure(message="bm25 failed", retryable=retryable),
    )


def _vector_failure(*, retryable: bool = True) -> VectorRetrievalOutcome:
    return VectorRetrievalOutcome(
        outcome="failure",
        failure=VectorRetrievalFailure(
            kind="channel_failure",
            message="vector failed",
            retryable=retryable,
        ),
    )


def test_u9_rrf_example_scores_and_normalization() -> None:
    bm25 = _bm25_success(
        [
            Bm25RetrievalHit(memory_id="mem_a", rank=1, score=2.0),
            Bm25RetrievalHit(memory_id="mem_b", rank=2, score=1.5),
        ]
    )
    vector = _vector_success(
        [
            VectorRetrievalHit(memory_id="mem_a", rank=1, score=2.0),
            VectorRetrievalHit(memory_id="mem_c", rank=2, score=1.5),
        ]
    )

    outcome = fuse_rrf(bm25, vector, rrf_k=RRF_K, fused_top_n=FUSED_TOP_N, user_id=USER_ID)

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "hybrid"
    assert outcome.success.effective_channel_count == 2

    by_id = {candidate.memory_id: candidate for candidate in outcome.success.candidates}
    expected_a = 1 / 61 + 1 / 61
    expected_b = 1 / 62
    expected_c = 1 / 62
    assert by_id["mem_a"].rrf_score == expected_a
    assert by_id["mem_b"].rrf_score == expected_b
    assert by_id["mem_c"].rrf_score == expected_c
    assert by_id["mem_a"].normalized_retrieval_score == 1.0
    assert by_id["mem_b"].min_available_rank == 2
    assert by_id["mem_c"].min_available_rank == 2

    ordered_ids = [candidate.memory_id for candidate in outcome.success.candidates]
    assert ordered_ids.index("mem_b") < ordered_ids.index("mem_c")


def test_u10_duplicate_memory_id_across_channels_single_candidate() -> None:
    bm25 = _bm25_success([Bm25RetrievalHit(memory_id="mem_x", rank=1, score=1.0)])
    vector = _vector_success([VectorRetrievalHit(memory_id="mem_x", rank=1, score=1.0)])

    outcome = fuse_rrf(bm25, vector, rrf_k=RRF_K, fused_top_n=FUSED_TOP_N, user_id=USER_ID)

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.candidates) == 1
    candidate = outcome.success.candidates[0]
    assert candidate.memory_id == "mem_x"
    assert candidate.retrieval_source == ["bm25", "vector"]


def test_u11_bm25_only_mode() -> None:
    bm25 = _bm25_success([Bm25RetrievalHit(memory_id="mem_b", rank=2, score=1.0)])
    vector = _vector_failure()

    outcome = fuse_rrf(bm25, vector, rrf_k=RRF_K, fused_top_n=FUSED_TOP_N, user_id=USER_ID)

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "bm25_only"
    candidate = outcome.success.candidates[0]
    assert candidate.vector_rank is None
    assert candidate.bm25_rank == 2
    rrf_max = 1 / 61
    assert candidate.normalized_retrieval_score == min(1.0, candidate.rrf_score / rrf_max)


def test_u12_vector_only_mode() -> None:
    bm25 = _bm25_failure()
    vector = _vector_success([VectorRetrievalHit(memory_id="mem_c", rank=2, score=1.0)])

    outcome = fuse_rrf(bm25, vector, rrf_k=RRF_K, fused_top_n=FUSED_TOP_N, user_id=USER_ID)

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "vector_only"
    assert outcome.success.candidates[0].bm25_rank is None


def test_u13_both_channels_empty_success() -> None:
    outcome = fuse_rrf(
        _bm25_success([]),
        _vector_success([]),
        rrf_k=RRF_K,
        fused_top_n=FUSED_TOP_N,
        user_id=USER_ID,
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "none"
    assert outcome.success.candidates == []


def test_u14_both_channels_failure() -> None:
    outcome = fuse_rrf(
        _bm25_failure(),
        _vector_failure(),
        rrf_k=RRF_K,
        fused_top_n=FUSED_TOP_N,
        user_id=USER_ID,
    )

    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.kind == "retrieval_unavailable"


def test_u16_fused_top_n_truncation() -> None:
    bm25_hits = [
        Bm25RetrievalHit(memory_id=f"mem-{index}", rank=index + 1, score=1.0)
        for index in range(40)
    ]
    outcome = fuse_rrf(
        _bm25_success(bm25_hits),
        _vector_success([]),
        rrf_k=RRF_K,
        fused_top_n=5,
        user_id=USER_ID,
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.candidates) == 5


def test_u19_one_channel_failure_other_empty_success() -> None:
    outcome = fuse_rrf(
        _bm25_failure(),
        _vector_success([]),
        rrf_k=RRF_K,
        fused_top_n=FUSED_TOP_N,
        user_id=USER_ID,
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "none"
    assert outcome.success.candidates == []


def test_duplicate_within_channel_treated_as_invalid() -> None:
    bm25 = _bm25_success(
        [
            Bm25RetrievalHit(memory_id="mem_dup", rank=1, score=1.0),
            Bm25RetrievalHit(memory_id="mem_dup", rank=2, score=0.5),
        ]
    )
    vector = _vector_success([VectorRetrievalHit(memory_id="mem_x", rank=1, score=1.0)])

    outcome = fuse_rrf(bm25, vector, rrf_k=RRF_K, fused_top_n=FUSED_TOP_N, user_id=USER_ID)

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "vector_only"
    assert len(outcome.success.candidates) == 1
    assert outcome.success.candidates[0].memory_id == "mem_x"
