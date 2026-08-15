"""Unit tests for retrieval API service orchestration (RET-005 U1-U18, F1-F3)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from memory_system.domain.models.authoritative_recall import (
    AuthoritativeRecallFailure,
    AuthoritativeRecallOutcome,
    AuthoritativeRecallSuccess,
)
from memory_system.domain.models.bm25_retrieval import (
    Bm25RetrievalFailure,
    Bm25RetrievalHit,
    Bm25RetrievalOutcome,
    Bm25RetrievalQuery,
    Bm25RetrievalSuccess,
)
from memory_system.domain.models.hybrid_retrieval import (
    FusedRetrievalCandidate,
    HybridRetrievalSuccess,
)
from memory_system.domain.models.retrieval_scoring import (
    ActRScoreComponents,
    RetrievalScoringFailure,
    RetrievalScoringOutcome,
    RetrievalScoringSuccess,
    ScoredRetrievalMemory,
)
from memory_system.domain.models.vector_retrieval import (
    VectorRetrievalFailure,
    VectorRetrievalHit,
    VectorRetrievalOutcome,
    VectorRetrievalQuery,
    VectorRetrievalSuccess,
)
from memory_system.domain.services.retrieval_api_service import (
    RetrievalApiFatalError,
    RetrievalApiInput,
    RetrievalApiService,
    RetrievalApiValidationError,
    resolve_top_k,
    validate_retrieval_input,
)
from memory_system.infrastructure.embedding.errors import EmbeddingServiceError
from memory_system.infrastructure.embedding.types import EmbeddingResult
from memory_system.infrastructure.neo4j.retrieval_statistics_repository import (
    RetrievalStatisticsWriteError,
)
from memory_system.infrastructure.tei.tei_tokenize_client import TokenizeServiceError
from memory_system.settings import get_settings

SETTINGS = get_settings()
USER_ID = "user-a"
EMBEDDING_DIMENSION = 1024


def make_hybrid_success() -> HybridRetrievalSuccess:
    return HybridRetrievalSuccess(
        user_id=USER_ID,
        retrieval_mode="hybrid",
        candidates=[
            FusedRetrievalCandidate(
                memory_id="mem-1",
                bm25_rank=1,
                vector_rank=1,
                bm25_score=1.0,
                vector_score=0.9,
                retrieval_source=["bm25", "vector"],
                rrf_score=0.5,
                min_available_rank=1,
                normalized_retrieval_score=0.8,
            )
        ],
        effective_channel_count=2,
    )


def make_authoritative_success() -> AuthoritativeRecallSuccess:
    from tests.unit.test_retrieval_scoring_service import (
        make_authoritative_success as _make_auth,
    )
    from tests.unit.test_retrieval_scoring_service import (
        make_validated,
    )

    return _make_auth(direct=[make_validated(memory_id="mem-1")])


def make_scored_memory(memory_id: str = "mem-1") -> ScoredRetrievalMemory:
    from tests.unit.test_retrieval_scoring_service import make_memory_snapshot

    memory = make_memory_snapshot(memory_id=memory_id)
    return ScoredRetrievalMemory(
        memory_id=memory_id,
        memory_type=memory.memory_type,
        status=memory.status,
        content=memory.content,
        subject_entity=memory.subject_entity,
        object_entity=memory.object_entity,
        predicate=memory.predicate,
        object_value=memory.object_value,
        event_status=memory.event_status,
        start_time=memory.start_time,
        end_time=memory.end_time,
        confidence=memory.confidence,
        importance=memory.importance,
        latest_source_time=memory.latest_source_time,
        retrieval_source=["bm25"],
        bm25_rank=1,
        vector_rank=None,
        bm25_score=1.0,
        vector_score=None,
        rrf_score=0.5,
        min_available_rank=1,
        candidate_origin="direct",
        act_r_components=ActRScoreComponents(
            retrieval_score=0.8,
            importance_score=0.7,
            confidence_score=0.6,
            frequency_score=0.5,
            recency_score=0.4,
        ),
        final_score=0.75,
        evidence_count=1,
        source_message_ids=["msg-1"],
    )


class FakeBm25Service:
    def __init__(
        self,
        *,
        fail: bool = False,
        hits: list[Bm25RetrievalHit] | None = None,
    ) -> None:
        self.fail = fail
        self.hits = hits or [Bm25RetrievalHit(memory_id="mem-1", rank=1, score=1.0)]
        self.calls: list[Bm25RetrievalQuery] = []

    async def search(self, query: Bm25RetrievalQuery) -> Bm25RetrievalOutcome:
        self.calls.append(query)
        if self.fail:
            return Bm25RetrievalOutcome(
                outcome="failure",
                failure=Bm25RetrievalFailure(message="bm25 failed", retryable=True),
            )
        return Bm25RetrievalOutcome(
            outcome="success",
            success=Bm25RetrievalSuccess(
                user_id=query.user_id,
                hits=self.hits,
                total_hits=len(self.hits),
            ),
        )


class FakeVectorService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[VectorRetrievalQuery] = []

    async def search(self, query: VectorRetrievalQuery) -> VectorRetrievalOutcome:
        self.calls.append(query)
        if self.fail:
            return VectorRetrievalOutcome(
                outcome="failure",
                failure=VectorRetrievalFailure(
                    kind="channel_failure",
                    message="vector failed",
                    retryable=True,
                ),
            )
        return VectorRetrievalOutcome(
            outcome="success",
            success=VectorRetrievalSuccess(
                user_id=query.user_id,
                hits=[VectorRetrievalHit(memory_id="mem-1", rank=1, score=0.9)],
                total_hits=1,
            ),
        )


class FakeEmbeddingClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.embed_calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self.embed_calls.append(list(texts))
        if self.fail:
            raise EmbeddingServiceError(
                code="provider_unavailable",
                provider="fake",
                status_code=503,
                trace_id=None,
                sanitized_message="embed failed",
            )
        vectors = [[0.1] * EMBEDDING_DIMENSION for _ in texts]
        return EmbeddingResult(
            model="fake",
            dimension=EMBEDDING_DIMENSION,
            vectors=vectors,
        )


class FakeTokenizeClient:
    def __init__(self, *, token_count: int = 10, fail: bool = False) -> None:
        self.token_count = token_count
        self.fail = fail
        self.calls: list[str] = []

    async def count_tokens(self, text: str) -> int:
        self.calls.append(text)
        if self.fail:
            raise TokenizeServiceError("tokenize failed")
        return self.token_count


class FakeAuthoritativeService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def recall(self, query: Any) -> AuthoritativeRecallOutcome:
        if self.fail:
            return AuthoritativeRecallOutcome(
                outcome="failure",
                failure=AuthoritativeRecallFailure(message="neo4j read failed"),
            )
        return AuthoritativeRecallOutcome(
            outcome="success",
            success=make_authoritative_success(),
        )


class FakeScoringService:
    def __init__(
        self,
        *,
        fail_kind: str | None = None,
        scored: list[ScoredRetrievalMemory] | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.fail_kind = fail_kind
        self.scored = [make_scored_memory()] if scored is None else scored
        self.delay_seconds = delay_seconds

    async def score(self, query: Any) -> RetrievalScoringOutcome:
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.fail_kind == "neo4j_read_failure":
            return RetrievalScoringOutcome(
                outcome="failure",
                failure=RetrievalScoringFailure(
                    kind="neo4j_read_failure",
                    message="neo4j read failed",
                ),
            )
        if self.fail_kind == "graph_load_failed":
            return RetrievalScoringOutcome(
                outcome="failure",
                failure=RetrievalScoringFailure(
                    kind="graph_load_failed",
                    message="graph load failed",
                ),
            )
        return RetrievalScoringOutcome(
            outcome="success",
            success=RetrievalScoringSuccess(
                user_id=USER_ID,
                retrieval_mode="hybrid",
                effective_channel_count=2,
                scored_memories=self.scored,
                warnings=[],
            ),
        )


class FakeStatisticsRepository:
    def __init__(self, *, fail: bool = False, delay_seconds: float = 0.0) -> None:
        self.fail = fail
        self.delay_seconds = delay_seconds
        self.calls: list[tuple[str, list[str], int]] = []

    async def increment_retrieval_stats(
        self,
        *,
        user_id: str,
        memory_ids: list[str],
        current_time: int,
    ) -> None:
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        self.calls.append((user_id, memory_ids, current_time))
        if self.fail:
            raise RetrievalStatisticsWriteError("stats failed", retryable=True)


def make_service(
    *,
    bm25: FakeBm25Service | None = None,
    vector: FakeVectorService | None = None,
    embedding: FakeEmbeddingClient | None = None,
    tokenize: FakeTokenizeClient | None = None,
    authoritative: FakeAuthoritativeService | None = None,
    scoring: FakeScoringService | None = None,
    stats: FakeStatisticsRepository | None = None,
) -> RetrievalApiService:
    return RetrievalApiService(
        bm25_service=bm25 if bm25 is not None else FakeBm25Service(),
        vector_service=vector if vector is not None else FakeVectorService(),
        embedding_client=embedding if embedding is not None else FakeEmbeddingClient(),
        tokenize_client=tokenize if tokenize is not None else FakeTokenizeClient(),
        authoritative_service=(
            authoritative if authoritative is not None else FakeAuthoritativeService()
        ),
        scoring_service=scoring if scoring is not None else FakeScoringService(),
        statistics_repository=stats if stats is not None else FakeStatisticsRepository(),
        settings=SETTINGS,
    )


def make_input(**overrides: Any) -> RetrievalApiInput:
    defaults = {
        "user_id": USER_ID,
        "query": "hello world",
        "memory_types": None,
        "top_k": 10,
        "include_conflicted": False,
        "include_history": False,
        "graph_expand": True,
    }
    defaults.update(overrides)
    return RetrievalApiInput(**defaults)


def deadline_far() -> float:
    return asyncio.get_event_loop().time() + 60.0


@pytest.mark.asyncio
async def test_u1_happy_path() -> None:
    stats = FakeStatisticsRepository()
    service = make_service(stats=stats)
    result = await service.retrieve(make_input(), deadline=deadline_far())
    assert result.retrieval_mode == "hybrid"
    assert len(result.memories) == 1
    assert result.memories[0].memory_id == "mem-1"
    assert stats.calls[0][0] == USER_ID


def test_u2_top_k_default_and_invalid() -> None:
    assert resolve_top_k(None, SETTINGS) == SETTINGS.memory_retrieval.default_top_k
    with pytest.raises(RetrievalApiValidationError) as exc_info:
        resolve_top_k(0, SETTINGS)
    assert exc_info.value.code == "invalid_top_k"
    with pytest.raises(RetrievalApiValidationError) as exc_info2:
        resolve_top_k(21, SETTINGS)
    assert exc_info2.value.code == "invalid_top_k"


def test_u3_memory_types_dedup_and_invalid() -> None:
    user_id, normalized, memory_types = validate_retrieval_input(
        make_input(memory_types=["fact", "event", "fact"])
    )
    assert user_id == USER_ID
    assert memory_types == ["fact", "event"]
    with pytest.raises(RetrievalApiValidationError) as exc_info:
        validate_retrieval_input(make_input(memory_types=["invalid"]))
    assert exc_info.value.code == "invalid_memory_type"


def test_u4_query_too_long() -> None:
    with pytest.raises(RetrievalApiValidationError) as exc_info:
        validate_retrieval_input(make_input(query="x" * 2001))
    assert exc_info.value.code == "query_too_long"


@pytest.mark.asyncio
async def test_u5_tokenize_over_1024_skips_embed() -> None:
    embedding = FakeEmbeddingClient()
    service = make_service(tokenize=FakeTokenizeClient(token_count=1025), embedding=embedding)
    result = await service.retrieve(make_input(), deadline=deadline_far())
    assert embedding.embed_calls == []
    assert "vector_skipped_query_too_long" in result.warnings


@pytest.mark.asyncio
async def test_u6_tokenize_within_limit_embeds() -> None:
    embedding = FakeEmbeddingClient()
    service = make_service(tokenize=FakeTokenizeClient(token_count=1024), embedding=embedding)
    await service.retrieve(make_input(), deadline=deadline_far())
    assert len(embedding.embed_calls) == 1


@pytest.mark.asyncio
async def test_u7_embedding_failure_warning() -> None:
    service = make_service(embedding=FakeEmbeddingClient(fail=True))
    result = await service.retrieve(make_input(), deadline=deadline_far())
    assert "embedding_failed" in result.warnings


@pytest.mark.asyncio
async def test_u8_bm25_failure_only() -> None:
    service = make_service(bm25=FakeBm25Service(fail=True))
    result = await service.retrieve(make_input(), deadline=deadline_far())
    assert "bm25_retrieval_failed" in result.warnings


@pytest.mark.asyncio
async def test_u9_vector_search_failure_only() -> None:
    service = make_service(vector=FakeVectorService(fail=True))
    result = await service.retrieve(make_input(), deadline=deadline_far())
    assert "vector_retrieval_failed" in result.warnings


@pytest.mark.asyncio
async def test_u10_dual_channel_failure() -> None:
    service = make_service(
        bm25=FakeBm25Service(fail=True),
        vector=FakeVectorService(fail=True),
        embedding=FakeEmbeddingClient(fail=True),
    )
    with pytest.raises(RetrievalApiFatalError) as exc_info:
        await service.retrieve(make_input(), deadline=deadline_far())
    assert exc_info.value.code == "retrieval_unavailable"


@pytest.mark.asyncio
async def test_u11_stats_failure_warning() -> None:
    service = make_service(stats=FakeStatisticsRepository(fail=True))
    result = await service.retrieve(make_input(), deadline=deadline_far())
    assert "retrieval_stat_update_failed" in result.warnings


@pytest.mark.asyncio
async def test_u12_post_dto_timeout_degraded() -> None:
    loop = asyncio.get_event_loop()
    stats = FakeStatisticsRepository(delay_seconds=2.0)
    service = make_service(stats=stats)
    deadline = loop.time() + 0.05
    result = await service.retrieve(make_input(), deadline=deadline)
    assert "retrieval_timeout_degraded" in result.warnings
    assert len(result.memories) == 1


@pytest.mark.asyncio
async def test_u13_pre_dto_timeout_fatal() -> None:
    loop = asyncio.get_event_loop()
    service = make_service(scoring=FakeScoringService(delay_seconds=2.0))
    deadline = loop.time() + 0.05
    with pytest.raises(RetrievalApiFatalError) as exc_info:
        await service.retrieve(make_input(), deadline=deadline)
    assert exc_info.value.code == "retrieval_timeout"


@pytest.mark.asyncio
async def test_u14_neo4j_read_failure() -> None:
    service = make_service(authoritative=FakeAuthoritativeService(fail=True))
    with pytest.raises(RetrievalApiFatalError) as exc_info:
        await service.retrieve(make_input(), deadline=deadline_far())
    assert exc_info.value.code == "graph_load_failed"


@pytest.mark.asyncio
async def test_u15_graph_load_failed() -> None:
    service = make_service(scoring=FakeScoringService(fail_kind="graph_load_failed"))
    with pytest.raises(RetrievalApiFatalError) as exc_info:
        await service.retrieve(make_input(), deadline=deadline_far())
    assert exc_info.value.code == "graph_load_failed"


@pytest.mark.asyncio
async def test_u17_empty_top_k_no_stats() -> None:
    stats = FakeStatisticsRepository()
    service = make_service(scoring=FakeScoringService(scored=[]))
    result = await service.retrieve(make_input(), deadline=deadline_far())
    assert result.memories == []
    assert stats.calls == []


@pytest.mark.asyncio
async def test_u18_stats_memory_ids_deduped() -> None:
    stats = FakeStatisticsRepository()
    service = make_service(
        scoring=FakeScoringService(
            scored=[make_scored_memory("mem-dup"), make_scored_memory("mem-dup")]
        ),
        stats=stats,
    )
    await service.retrieve(make_input(top_k=10), deadline=deadline_far())
    assert stats.calls[0][1] == ["mem-dup"]


@pytest.mark.asyncio
async def test_f1_concurrent_retrieve_no_errors() -> None:
    stats = FakeStatisticsRepository()
    service = make_service(stats=stats)

    async def run_once() -> None:
        await service.retrieve(make_input(), deadline=deadline_far())

    await asyncio.gather(*[run_once() for _ in range(10)])
    assert len(stats.calls) == 10


@pytest.mark.asyncio
async def test_f2_pre_response_timeout_skips_stats() -> None:
    loop = asyncio.get_event_loop()
    stats = FakeStatisticsRepository()
    service = make_service(scoring=FakeScoringService(delay_seconds=2.0), stats=stats)
    deadline = loop.time() + 0.05
    with pytest.raises(RetrievalApiFatalError) as exc_info:
        await service.retrieve(make_input(), deadline=deadline)
    assert exc_info.value.code == "retrieval_timeout"
    assert stats.calls == []


@pytest.mark.asyncio
async def test_f3_post_dto_slow_stats_degraded() -> None:
    loop = asyncio.get_event_loop()
    stats = FakeStatisticsRepository(delay_seconds=2.0)
    service = make_service(stats=stats)
    deadline = loop.time() + 0.05
    result = await service.retrieve(make_input(), deadline=deadline)
    assert result.retrieval_mode == "hybrid"
    assert "retrieval_timeout_degraded" in result.warnings
