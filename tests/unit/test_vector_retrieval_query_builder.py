"""Unit tests for Vector retrieval ES kNN query builder."""

from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from elasticsearch import ConnectionError

from memory_system.domain.models.vector_retrieval import VectorRetrievalQuery
from memory_system.infrastructure.elasticsearch.vector_retrieval_repository import (
    EMBEDDING_DIMENSION,
    VectorRetrievalError,
    VectorRetrievalRepository,
    _parse_hits,
)

VECTOR_TOP_N = 30
VECTOR_NUM_CANDIDATES = 100


def _repo() -> VectorRetrievalRepository:
    return VectorRetrievalRepository(client=None)  # type: ignore[arg-type]


def _vector(dim: float = 0.5) -> list[float]:
    return [dim] * EMBEDDING_DIMENSION


def _base_query(**overrides: object) -> VectorRetrievalQuery:
    payload = {
        "user_id": "user-1",
        "query_vector": _vector(),
    }
    payload.update(overrides)
    return VectorRetrievalQuery.model_validate(payload)


def test_u5_knn_body_structure_and_settings() -> None:
    body = _repo().build_knn_search_body(
        _base_query(),
        k=VECTOR_TOP_N,
        num_candidates=VECTOR_NUM_CANDIDATES,
        size=VECTOR_TOP_N,
    )

    assert body["size"] == VECTOR_TOP_N
    assert body["_source"] is False
    knn = body["knn"]
    assert knn["field"] == "embedding"
    assert knn["k"] == VECTOR_TOP_N
    assert knn["num_candidates"] == VECTOR_NUM_CANDIDATES
    assert len(knn["query_vector"]) == EMBEDDING_DIMENSION
    assert {"term": {"user_id": "user-1"}} in knn["filter"]["bool"]["filter"]


def test_u6_query_vector_wrong_length_raises_value_error() -> None:
    with pytest.raises(ValueError, match="query_vector"):
        _repo().build_knn_search_body(
            _base_query(query_vector=[0.1, 0.2]),
            k=VECTOR_TOP_N,
            num_candidates=VECTOR_NUM_CANDIDATES,
            size=VECTOR_TOP_N,
        )


def test_c1_knn_search_body_keys() -> None:
    body = _repo().build_knn_search_body(
        _base_query(),
        k=VECTOR_TOP_N,
        num_candidates=VECTOR_NUM_CANDIDATES,
        size=VECTOR_TOP_N,
    )
    assert set(body.keys()) == {"size", "_source", "knn"}


def test_c3_no_hardcoded_index_in_production_files() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    prod_files = [
        repo_root / "src/memory_system/domain/models/vector_retrieval.py",
        repo_root / "src/memory_system/domain/services/vector_retrieval_service.py",
        repo_root / "src/memory_system/infrastructure/elasticsearch/vector_retrieval_repository.py",
    ]
    for path in prod_files:
        text = path.read_text()
        assert "memory_retrieval_v1" not in text
        assert "memory_retrieval_current" not in text


def test_u7_parse_hits_rank_and_score() -> None:
    response = {
        "hits": {
            "hits": [
                {"_id": "mem-1", "_score": 2.5},
                {"_id": "mem-2", "_score": 1.2},
            ]
        }
    }
    hits = _parse_hits(response)
    assert len(hits) == 2
    assert hits[0].memory_id == "mem-1"
    assert hits[0].rank == 1
    assert hits[0].score == 2.5
    assert hits[1].rank == 2


def test_u7_duplicate_memory_id_fail_closed() -> None:
    response = {
        "hits": {
            "hits": [
                {"_id": "mem-1", "_score": 1.0},
                {"_id": "mem-1", "_score": 0.5},
            ]
        }
    }
    with pytest.raises(VectorRetrievalError, match="duplicate"):
        _parse_hits(response)


@pytest.mark.asyncio
async def test_u8_repository_connection_error_retryable() -> None:
    scoped_client = MagicMock()
    scoped_client.search = AsyncMock(side_effect=ConnectionError("connection failed"))
    client = MagicMock()
    client.options.return_value = scoped_client
    repo = VectorRetrievalRepository(client)
    with pytest.raises(VectorRetrievalError, match="transport failed") as exc_info:
        await repo.search(
            _base_query(),
            index_name="alias",
            k=VECTOR_TOP_N,
            num_candidates=VECTOR_NUM_CANDIDATES,
            size=VECTOR_TOP_N,
            request_timeout=5.0,
        )
    assert exc_info.value.retryable is True
