"""Unit tests for Hybrid retrieval service orchestration."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from memory_system.domain.models.bm25_retrieval import (
    Bm25RetrievalHit,
    Bm25RetrievalOutcome,
    Bm25RetrievalQuery,
    Bm25RetrievalSuccess,
)
from memory_system.domain.models.hybrid_retrieval import HybridRetrievalQuery
from memory_system.domain.models.vector_retrieval import (
    VectorRetrievalHit,
    VectorRetrievalOutcome,
    VectorRetrievalQuery,
    VectorRetrievalSuccess,
)
from memory_system.domain.services.hybrid_retrieval_service import HybridRetrievalService
from memory_system.infrastructure.embedding.errors import EmbeddingServiceError
from memory_system.infrastructure.embedding.types import EmbeddingResult
from memory_system.settings import get_settings

EMBEDDING_DIMENSION = 1024


class FakeBm25Service:
    def __init__(
        self,
        *,
        hits: list[Bm25RetrievalHit] | None = None,
        delay_seconds: float = 0.0,
        on_search: Any = None,
    ) -> None:
        if hits is None:
            hits = [Bm25RetrievalHit(memory_id="mem-1", rank=1, score=1.5)]
        self.hits = hits
        self.delay_seconds = delay_seconds
        self.on_search = on_search
        self.calls: list[Bm25RetrievalQuery] = []

    async def search(self, query: Bm25RetrievalQuery) -> Bm25RetrievalOutcome:
        self.calls.append(query)
        if self.on_search is not None:
            await self.on_search()
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return Bm25RetrievalOutcome(
            outcome="success",
            success=Bm25RetrievalSuccess(
                user_id=query.user_id,
                hits=self.hits,
                total_hits=len(self.hits),
            ),
        )


class FakeVectorService:
    def __init__(
        self,
        *,
        hits: list[VectorRetrievalHit] | None = None,
        fail: bool = False,
    ) -> None:
        if hits is None:
            hits = [VectorRetrievalHit(memory_id="mem-2", rank=1, score=1.2)]
        self.hits = hits
        self.fail = fail
        self.calls: list[VectorRetrievalQuery] = []

    async def search(self, query: VectorRetrievalQuery) -> VectorRetrievalOutcome:
        from memory_system.domain.models.vector_retrieval import VectorRetrievalFailure

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
                hits=self.hits,
                total_hits=len(self.hits),
            ),
        )


class FakeEmbeddingClient:
    def __init__(
        self,
        *,
        fail: bool = False,
        delay_seconds: float = 0.0,
        on_embed: Any = None,
    ) -> None:
        self.fail = fail
        self.delay_seconds = delay_seconds
        self.on_embed = on_embed
        self.embed_calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self.embed_calls.append(list(texts))
        if self.on_embed is not None:
            await self.on_embed()
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.fail:
            raise EmbeddingServiceError(
                code="provider_unavailable",
                provider="fake",
                status_code=503,
                trace_id=None,
                sanitized_message="embedding unavailable",
            )
        return EmbeddingResult(
            model="fake-model",
            dimension=EMBEDDING_DIMENSION,
            vectors=[[0.1] * EMBEDDING_DIMENSION for _ in texts],
        )


def _service(
    bm25: FakeBm25Service | None = None,
    vector: FakeVectorService | None = None,
    embedding: FakeEmbeddingClient | None = None,
) -> HybridRetrievalService:
    return HybridRetrievalService(
        bm25 or FakeBm25Service(),
        vector or FakeVectorService(),
        embedding or FakeEmbeddingClient(),
        settings=get_settings(),
    )


@pytest.mark.asyncio
async def test_u15_embedding_failure_bm25_only() -> None:
    outcome = await _service(
        bm25=FakeBm25Service(),
        vector=FakeVectorService(),
        embedding=FakeEmbeddingClient(fail=True),
    ).search(HybridRetrievalQuery(user_id="user-1", query="keyword"))

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "bm25_only"


@pytest.mark.asyncio
async def test_u17_bm25_does_not_wait_for_embedding() -> None:
    bm25_started = asyncio.Event()
    embed_started = asyncio.Event()
    release_embed = asyncio.Event()

    async def on_bm25() -> None:
        bm25_started.set()

    async def on_embed() -> None:
        embed_started.set()
        await release_embed.wait()

    service = _service(
        bm25=FakeBm25Service(delay_seconds=0.05, on_search=on_bm25),
        vector=FakeVectorService(),
        embedding=FakeEmbeddingClient(on_embed=on_embed),
    )

    search_task = asyncio.create_task(
        service.search(HybridRetrievalQuery(user_id="user-1", query="keyword")),
    )

    await asyncio.wait_for(bm25_started.wait(), timeout=1.0)
    assert embed_started.is_set()
    assert not search_task.done()

    release_embed.set()
    outcome = await asyncio.wait_for(search_task, timeout=1.0)
    assert outcome.outcome == "success"


@pytest.mark.asyncio
async def test_parallel_timing_bm25_not_blocked_by_embed_delay() -> None:
    service = _service(
        bm25=FakeBm25Service(delay_seconds=0.05),
        vector=FakeVectorService(),
        embedding=FakeEmbeddingClient(delay_seconds=0.15),
    )

    started = time.monotonic()
    await service.search(HybridRetrievalQuery(user_id="user-1", query="keyword"))
    elapsed = time.monotonic() - started

    assert elapsed < 0.19


@pytest.mark.asyncio
async def test_normalized_query_passed_to_bm25_and_embed() -> None:
    bm25 = FakeBm25Service()
    embedding = FakeEmbeddingClient()
    await _service(bm25=bm25, embedding=embedding).search(
        HybridRetrievalQuery(user_id="user-1", query="  ＡＢＣ  hello  "),
    )

    assert bm25.calls[0].query == "ABC hello"
    assert embedding.embed_calls[0] == ["ABC hello"]


@pytest.mark.asyncio
async def test_u2_empty_query_after_normalization_raises_value_error() -> None:
    service = _service()
    with pytest.raises(ValueError, match="query"):
        await service.search(HybridRetrievalQuery(user_id="user-1", query="   "))


@pytest.mark.asyncio
async def test_u19_hybrid_one_failure_other_empty_success() -> None:
    outcome = await _service(
        bm25=FakeBm25Service(hits=[]),
        vector=FakeVectorService(fail=True),
        embedding=FakeEmbeddingClient(),
    ).search(HybridRetrievalQuery(user_id="user-1", query="keyword"))

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.retrieval_mode == "none"
    assert outcome.success.candidates == []


@pytest.mark.asyncio
async def test_dual_channel_failure_retrieval_unavailable() -> None:
    class FailingBm25:
        async def search(self, query: Bm25RetrievalQuery) -> Bm25RetrievalOutcome:
            from memory_system.domain.models.bm25_retrieval import Bm25RetrievalFailure

            return Bm25RetrievalOutcome(
                outcome="failure",
                failure=Bm25RetrievalFailure(message="bm25 failed", retryable=True),
            )

    outcome = await HybridRetrievalService(
        FailingBm25(),
        FakeVectorService(fail=True),
        FakeEmbeddingClient(),
        settings=get_settings(),
    ).search(HybridRetrievalQuery(user_id="user-1", query="keyword"))

    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.kind == "retrieval_unavailable"
