"""Elasticsearch read repository for RET-001 BM25 keyword retrieval."""

from __future__ import annotations

from numbers import Real
from typing import Any

from elasticsearch import ApiError, AsyncElasticsearch, ConnectionError, TransportError

from memory_system.domain.models.bm25_retrieval import Bm25RetrievalHit, Bm25RetrievalQuery
from memory_system.infrastructure.elasticsearch.retrieval_filter_builder import (
    build_retrieval_filters,
)

MULTI_MATCH_FIELDS = ["search_text^2.0", "content^1.0", "predicate^0.5"]


class Bm25RetrievalError(Exception):
    """Raised when Elasticsearch BM25 search fails or returns a malformed response."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class Bm25RetrievalRepository:
    """Read-only Elasticsearch repository for BM25 keyword retrieval."""

    def __init__(self, client: AsyncElasticsearch) -> None:
        self._client = client

    def build_search_body(self, query: Bm25RetrievalQuery, *, size: int) -> dict[str, Any]:
        filters = build_retrieval_filters(
            user_id=query.user_id,
            memory_types=query.memory_types,
            include_conflicted=query.include_conflicted,
            include_history=query.include_history,
        )

        return {
            "size": size,
            "_source": False,
            "query": {
                "bool": {
                    "filter": filters,
                    "must": {
                        "multi_match": {
                            "query": query.query,
                            "fields": MULTI_MATCH_FIELDS,
                        }
                    },
                }
            },
        }

    async def search(
        self,
        query: Bm25RetrievalQuery,
        *,
        index_name: str,
        size: int,
        request_timeout: float,
    ) -> list[Bm25RetrievalHit]:
        body = self.build_search_body(query, size=size)
        try:
            client = self._client.options(request_timeout=request_timeout)
            response = await client.search(
                index=index_name,
                size=body["size"],
                source=body["_source"],
                query=body["query"],
            )
        except (ConnectionError, TransportError) as exc:
            raise Bm25RetrievalError(
                "elasticsearch bm25 search transport failed",
                retryable=True,
            ) from exc
        except ApiError as exc:
            status = exc.status_code
            retryable = isinstance(status, int) and status >= 500
            raise Bm25RetrievalError(
                "elasticsearch bm25 search request failed",
                retryable=retryable,
            ) from exc

        return _parse_hits(response)


def _coerce_search_response_body(response: Any) -> dict[str, Any]:
    body = getattr(response, "body", response)
    if not isinstance(body, dict):
        raise Bm25RetrievalError("elasticsearch bm25 response must be an object", retryable=False)
    return body


def _parse_hits(response: Any) -> list[Bm25RetrievalHit]:
    body = _coerce_search_response_body(response)

    hits_wrapper = body.get("hits")
    if not isinstance(hits_wrapper, dict):
        raise Bm25RetrievalError("elasticsearch bm25 response missing hits", retryable=False)

    raw_hits = hits_wrapper.get("hits")
    if not isinstance(raw_hits, list):
        raise Bm25RetrievalError("elasticsearch bm25 response hits must be a list", retryable=False)

    parsed: list[Bm25RetrievalHit] = []
    for index, hit in enumerate(raw_hits):
        if not isinstance(hit, dict):
            raise Bm25RetrievalError("elasticsearch bm25 hit must be an object", retryable=False)

        memory_id = hit.get("_id")
        if not isinstance(memory_id, str) or not memory_id:
            raise Bm25RetrievalError("elasticsearch bm25 hit missing _id", retryable=False)

        score = hit.get("_score")
        if not isinstance(score, Real) or isinstance(score, bool):
            raise Bm25RetrievalError("elasticsearch bm25 hit missing valid _score", retryable=False)

        parsed.append(
            Bm25RetrievalHit(
                memory_id=memory_id,
                rank=index + 1,
                score=float(score),
            )
        )

    return parsed
