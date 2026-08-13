"""Unit tests for BM25 retrieval service orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from memory_system.domain.models.bm25_retrieval import (
    Bm25RetrievalHit,
    Bm25RetrievalQuery,
)
from memory_system.domain.services.bm25_retrieval_service import Bm25RetrievalService
from memory_system.infrastructure.elasticsearch.bm25_retrieval_repository import Bm25RetrievalError
from memory_system.settings import get_settings


class FakeBm25RetrievalRepository:
    def __init__(self, *, fail_on_search: bool = False, retryable: bool = True) -> None:
        self.fail_on_search = fail_on_search
        self.retryable = retryable
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        query: Bm25RetrievalQuery,
        *,
        index_name: str,
        size: int,
        request_timeout: float,
    ) -> list[Bm25RetrievalHit]:
        self.calls.append(
            {
                "query": query,
                "index_name": index_name,
                "size": size,
                "request_timeout": request_timeout,
            }
        )
        if self.fail_on_search:
            raise Bm25RetrievalError("synthetic bm25 failure", retryable=self.retryable)
        return [
            Bm25RetrievalHit(memory_id="mem-1", rank=1, score=1.5),
            Bm25RetrievalHit(memory_id="mem-2", rank=2, score=1.0),
        ]


def _service(repo: FakeBm25RetrievalRepository | None = None) -> Bm25RetrievalService:
    return Bm25RetrievalService(
        repo or FakeBm25RetrievalRepository(),
        settings=get_settings(),
    )


@pytest.mark.asyncio
async def test_u9_service_success_outcome() -> None:
    repo = FakeBm25RetrievalRepository()
    service = _service(repo)
    outcome = await service.search(
        Bm25RetrievalQuery(user_id="user-1", query="keyword"),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.failure is None
    assert outcome.success.user_id == "user-1"
    assert len(outcome.success.hits) == 2
    assert outcome.success.total_hits == 2

    settings = get_settings()
    assert repo.calls[0]["index_name"] == settings.memory_retrieval.index_name
    assert repo.calls[0]["size"] == settings.memory_retrieval.bm25_top_n
    assert repo.calls[0]["request_timeout"] == float(
        settings.memory_retrieval.elasticsearch_timeout_seconds
    )


@pytest.mark.asyncio
async def test_u9_service_empty_success() -> None:
    repo = FakeBm25RetrievalRepository()
    repo.search = _empty_search  # type: ignore[method-assign]
    service = _service(repo)
    outcome = await service.search(
        Bm25RetrievalQuery(user_id="user-1", query="keyword"),
    )
    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert outcome.success.hits == []
    assert outcome.success.total_hits == 0


async def _empty_search(
    query: Bm25RetrievalQuery,
    *,
    index_name: str,
    size: int,
    request_timeout: float,
) -> list[Bm25RetrievalHit]:
    return []


@pytest.mark.asyncio
async def test_u9_service_channel_failure_retryable() -> None:
    service = _service(FakeBm25RetrievalRepository(fail_on_search=True, retryable=True))
    outcome = await service.search(
        Bm25RetrievalQuery(user_id="user-1", query="keyword"),
    )
    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.kind == "channel_failure"
    assert outcome.failure.retryable is True


@pytest.mark.asyncio
async def test_service_channel_failure_not_retryable() -> None:
    service = _service(FakeBm25RetrievalRepository(fail_on_search=True, retryable=False))
    outcome = await service.search(
        Bm25RetrievalQuery(user_id="user-1", query="keyword"),
    )
    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.retryable is False


@pytest.mark.asyncio
async def test_u10_empty_user_id_raises_value_error() -> None:
    service = _service()
    with pytest.raises(ValueError, match="user_id"):
        await service.search(Bm25RetrievalQuery(user_id="  ", query="keyword"))


@pytest.mark.asyncio
async def test_u10_empty_query_raises_value_error() -> None:
    service = _service()
    with pytest.raises(ValueError, match="query"):
        await service.search(Bm25RetrievalQuery(user_id="user-1", query="  "))


@pytest.mark.asyncio
async def test_u10_invalid_memory_type_raises_value_error() -> None:
    service = _service()
    with pytest.raises(ValueError, match="memory_types"):
        await service.search(
            Bm25RetrievalQuery(user_id="user-1", query="keyword", memory_types=["invalid"]),
        )


@pytest.mark.asyncio
async def test_memory_types_empty_list_normalized_to_none() -> None:
    repo = FakeBm25RetrievalRepository()
    service = _service(repo)
    await service.search(
        Bm25RetrievalQuery(user_id="user-1", query="keyword", memory_types=[]),
    )
    assert repo.calls[0]["query"].memory_types is None


@pytest.mark.asyncio
async def test_f1_fake_repository_fail_on_search() -> None:
    service = _service(FakeBm25RetrievalRepository(fail_on_search=True))
    outcome = await service.search(
        Bm25RetrievalQuery(user_id="user-1", query="keyword"),
    )
    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.kind == "channel_failure"


@pytest.mark.asyncio
async def test_f2_concurrent_identical_queries_consistent() -> None:
    service = _service(FakeBm25RetrievalRepository())
    query = Bm25RetrievalQuery(user_id="user-1", query="keyword")
    outcomes = await asyncio.gather(*[service.search(query) for _ in range(10)])
    for outcome in outcomes:
        assert outcome.outcome == "success"
        assert outcome.success is not None
        assert len(outcome.success.hits) == 2
