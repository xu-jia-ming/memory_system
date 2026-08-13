"""Unit tests for BM25 retrieval ES query builder."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from elasticsearch import ApiError, ConnectionError

from memory_system.domain.models.bm25_retrieval import Bm25RetrievalQuery
from memory_system.infrastructure.elasticsearch.bm25_retrieval_repository import (
    Bm25RetrievalError,
    Bm25RetrievalRepository,
    _parse_hits,
)

BM25_TOP_N = 30


def _repo() -> Bm25RetrievalRepository:
    return Bm25RetrievalRepository(client=None)  # type: ignore[arg-type]


def _base_query(**overrides: object) -> Bm25RetrievalQuery:
    payload = {
        "user_id": "user-1",
        "query": "integration keyword",
    }
    payload.update(overrides)
    return Bm25RetrievalQuery.model_validate(payload)


def _filters(body: dict[str, object]) -> list[dict[str, object]]:
    query = body["query"]
    assert isinstance(query, dict)
    bool_query = query["bool"]
    assert isinstance(bool_query, dict)
    filters = bool_query["filter"]
    assert isinstance(filters, list)
    return filters


def test_u1_default_filters_active_only_no_memory_types() -> None:
    body = _repo().build_search_body(_base_query(), size=BM25_TOP_N)
    filters = _filters(body)

    assert {"term": {"user_id": "user-1"}} in filters
    assert {"term": {"status": "active"}} in filters
    assert not any("memory_type" in str(filter_item) for filter_item in filters)
    assert body["size"] == BM25_TOP_N
    assert body["_source"] is False


def test_u2_memory_types_fact_event() -> None:
    body = _repo().build_search_body(
        _base_query(memory_types=["fact", "event"]),
        size=BM25_TOP_N,
    )
    filters = _filters(body)
    assert {"terms": {"memory_type": ["fact", "event"]}} in filters


def test_u3_memory_types_none_and_empty_omit_terms() -> None:
    for memory_types in (None, []):
        body = _repo().build_search_body(
            _base_query(memory_types=memory_types),
            size=BM25_TOP_N,
        )
        filters = _filters(body)
        assert not any("memory_type" in str(filter_item) for filter_item in filters)


def test_u4_status_filter_matrix() -> None:
    cases = [
        (False, False, {"term": {"status": "active"}}),
        (True, False, {"terms": {"status": ["active", "conflicted"]}}),
        (False, True, {"terms": {"status": ["active", "superseded"]}}),
        (
            True,
            True,
            {"terms": {"status": ["active", "conflicted", "superseded"]}},
        ),
    ]
    for include_conflicted, include_history, expected in cases:
        body = _repo().build_search_body(
            _base_query(
                include_conflicted=include_conflicted,
                include_history=include_history,
            ),
            size=BM25_TOP_N,
        )
        filters = _filters(body)
        assert expected in filters


def test_u5_multi_match_field_weights() -> None:
    body = _repo().build_search_body(_base_query(), size=BM25_TOP_N)
    query = body["query"]
    assert isinstance(query, dict)
    bool_query = query["bool"]
    assert isinstance(bool_query, dict)
    must = bool_query["must"]
    assert isinstance(must, dict)
    multi_match = must["multi_match"]
    assert isinstance(multi_match, dict)
    assert multi_match["query"] == "integration keyword"
    assert multi_match["fields"] == ["search_text^2.0", "content^1.0", "predicate^0.5"]


def test_u6_size_from_settings() -> None:
    body = _repo().build_search_body(_base_query(), size=17)
    assert body["size"] == 17


def test_u7_parse_object_api_response_body() -> None:
    class FakeObjectApiResponse:
        def __init__(self, body: dict[str, object]) -> None:
            self.body = body

    response = FakeObjectApiResponse(
        {
            "hits": {
                "hits": [
                    {"_id": "mem-1", "_score": 1.0},
                ]
            }
        }
    )
    hits = _parse_hits(response)
    assert len(hits) == 1
    assert hits[0].memory_id == "mem-1"
    assert hits[0].score == 1.0


def test_u7_parse_three_hits_rank_memory_id_score() -> None:
    response = {
        "hits": {
            "hits": [
                {"_id": "mem-1", "_score": 2.5},
                {"_id": "mem-2", "_score": 1.2},
                {"_id": "mem-3", "_score": 0.8},
            ]
        }
    }
    hits = _parse_hits(response)
    assert len(hits) == 3
    assert hits[0].memory_id == "mem-1"
    assert hits[0].rank == 1
    assert hits[0].score == 2.5
    assert hits[2].rank == 3
    assert hits[2].score == 0.8


def test_u8_malformed_score_fail_closed_not_zero() -> None:
    for bad_score in (None, "bad", {}, False, True):
        response = {"hits": {"hits": [{"_id": "mem-1", "_score": bad_score}]}}
        with pytest.raises(Bm25RetrievalError, match="_score"):
            _parse_hits(response)


def test_u8_missing_score_fail_closed() -> None:
    response = {"hits": {"hits": [{"_id": "mem-1"}]}}
    with pytest.raises(Bm25RetrievalError, match="_score"):
        _parse_hits(response)


def test_c1_search_body_structure() -> None:
    body = _repo().build_search_body(_base_query(), size=BM25_TOP_N)
    assert set(body.keys()) == {"size", "_source", "query"}
    query = body["query"]
    assert isinstance(query, dict)
    bool_query = query["bool"]
    assert isinstance(bool_query, dict)
    assert "filter" in bool_query
    assert "must" in bool_query


def test_c3_no_hardcoded_index_in_production_files() -> None:
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    prod_files = [
        repo_root / "src/memory_system/domain/models/bm25_retrieval.py",
        repo_root / "src/memory_system/domain/services/bm25_retrieval_service.py",
        repo_root / "src/memory_system/infrastructure/elasticsearch/bm25_retrieval_repository.py",
    ]
    for path in prod_files:
        text = path.read_text()
        assert "memory_retrieval_v1" not in text
        assert "memory_retrieval_current" not in text


@pytest.mark.asyncio
async def test_u8_repository_connection_error_retryable() -> None:
    scoped_client = MagicMock()
    scoped_client.search = AsyncMock(side_effect=ConnectionError("connection failed"))
    client = MagicMock()
    client.options.return_value = scoped_client
    repo = Bm25RetrievalRepository(client)
    with pytest.raises(Bm25RetrievalError, match="transport failed") as exc_info:
        await repo.search(
            _base_query(),
            index_name="alias",
            size=BM25_TOP_N,
            request_timeout=5.0,
        )
    assert exc_info.value.retryable is True
    client.options.assert_called_once_with(request_timeout=5.0)


@pytest.mark.asyncio
async def test_u8_repository_api_error_4xx_not_retryable() -> None:
    scoped_client = MagicMock()
    meta = MagicMock()
    meta.status = 400
    api_error = ApiError("bad request", meta=meta, body={"error": "bad"})
    scoped_client.search = AsyncMock(side_effect=api_error)
    client = MagicMock()
    client.options.return_value = scoped_client
    repo = Bm25RetrievalRepository(client)
    with pytest.raises(Bm25RetrievalError, match="request failed") as exc_info:
        await repo.search(
            _base_query(),
            index_name="alias",
            size=BM25_TOP_N,
            request_timeout=5.0,
        )
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_u8_repository_api_error_5xx_retryable() -> None:
    scoped_client = MagicMock()
    meta = MagicMock()
    meta.status = 503
    api_error = ApiError("service unavailable", meta=meta, body={"error": "unavailable"})
    scoped_client.search = AsyncMock(side_effect=api_error)
    client = MagicMock()
    client.options.return_value = scoped_client
    repo = Bm25RetrievalRepository(client)
    with pytest.raises(Bm25RetrievalError, match="request failed") as exc_info:
        await repo.search(
            _base_query(),
            index_name="alias",
            size=BM25_TOP_N,
            request_timeout=5.0,
        )
    assert exc_info.value.retryable is True
