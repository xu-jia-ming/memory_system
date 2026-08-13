"""Unit tests for Vector retrieval service orchestration."""

from __future__ import annotations

from typing import Any

import pytest

from memory_system.domain.models.vector_retrieval import VectorRetrievalQuery
from memory_system.domain.services.vector_retrieval_service import VectorRetrievalService
from memory_system.infrastructure.elasticsearch.vector_retrieval_repository import (
    EMBEDDING_DIMENSION,
    VectorRetrievalError,
)
from memory_system.settings import get_settings


class FakeVectorRetrievalRepository:
    def __init__(self, *, fail_on_search: bool = False, retryable: bool = True) -> None:
        self.fail_on_search = fail_on_search
        self.retryable = retryable
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        query: VectorRetrievalQuery,
        *,
        index_name: str,
        k: int,
        num_candidates: int,
        size: int,
        request_timeout: float,
    ):
        from memory_system.domain.models.vector_retrieval import VectorRetrievalHit

        self.calls.append(
            {
                "query": query,
                "index_name": index_name,
                "k": k,
                "num_candidates": num_candidates,
                "size": size,
                "request_timeout": request_timeout,
            }
        )
        if self.fail_on_search:
            raise VectorRetrievalError("synthetic vector failure", retryable=self.retryable)
        return [
            VectorRetrievalHit(memory_id="mem-1", rank=1, score=1.5),
            VectorRetrievalHit(memory_id="mem-2", rank=2, score=1.0),
        ]


def _vector() -> list[float]:
    return [0.1] * EMBEDDING_DIMENSION


def _service(repo: FakeVectorRetrievalRepository | None = None) -> VectorRetrievalService:
    return VectorRetrievalService(
        repo or FakeVectorRetrievalRepository(),
        settings=get_settings(),
    )


@pytest.mark.asyncio
async def test_u7_service_success_outcome() -> None:
    repo = FakeVectorRetrievalRepository()
    service = _service(repo)
    outcome = await service.search(
        VectorRetrievalQuery(user_id="user-1", query_vector=_vector()),
    )

    assert outcome.outcome == "success"
    assert outcome.success is not None
    assert len(outcome.success.hits) == 2
    settings = get_settings()
    assert repo.calls[0]["index_name"] == settings.memory_retrieval.index_name
    assert repo.calls[0]["k"] == settings.memory_retrieval.vector_top_n


@pytest.mark.asyncio
async def test_u6_wrong_vector_length_channel_failure() -> None:
    service = _service()
    outcome = await service.search(
        VectorRetrievalQuery(user_id="user-1", query_vector=[0.1, 0.2]),
    )
    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.kind == "channel_failure"
    assert outcome.failure.retryable is False


@pytest.mark.asyncio
async def test_u8_service_channel_failure_retryable() -> None:
    service = _service(FakeVectorRetrievalRepository(fail_on_search=True, retryable=True))
    outcome = await service.search(
        VectorRetrievalQuery(user_id="user-1", query_vector=_vector()),
    )
    assert outcome.outcome == "failure"
    assert outcome.failure is not None
    assert outcome.failure.retryable is True
