"""Elasticsearch read repository for RET-002 Vector kNN retrieval."""

from __future__ import annotations

from numbers import Real
from typing import Any

from elasticsearch import ApiError, AsyncElasticsearch, ConnectionError, TransportError

from memory_system.domain.models.vector_retrieval import VectorRetrievalHit, VectorRetrievalQuery
from memory_system.infrastructure.elasticsearch.retrieval_filter_builder import (
    build_retrieval_filters,
)

EMBEDDING_DIMENSION = 1024


class VectorRetrievalError(Exception):
    """Raised when Elasticsearch Vector kNN search fails or returns a malformed response."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class VectorRetrievalRepository:
    """Read-only Elasticsearch repository for Vector kNN retrieval."""

    def __init__(self, client: AsyncElasticsearch) -> None:
        self._client = client

    def build_knn_search_body(
        self,
        query: VectorRetrievalQuery,
        *,
        k: int,
        num_candidates: int,
        size: int,
    ) -> dict[str, Any]:
        if len(query.query_vector) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"query_vector must have length {EMBEDDING_DIMENSION}, "
                f"got {len(query.query_vector)}",
            )

        filters = build_retrieval_filters(
            user_id=query.user_id,
            memory_types=query.memory_types,
            include_conflicted=query.include_conflicted,
            include_history=query.include_history,
        )

        return {
            "size": size,
            "_source": False,
            "knn": {
                "field": "embedding",
                "query_vector": query.query_vector,
                "k": k,
                "num_candidates": num_candidates,
                "filter": {
                    "bool": {
                        "filter": filters,
                    }
                },
            },
        }

    async def search(
        self,
        query: VectorRetrievalQuery,
        *,
        index_name: str,
        k: int,
        num_candidates: int,
        size: int,
        request_timeout: float,
    ) -> list[VectorRetrievalHit]:
        body = self.build_knn_search_body(
            query,
            k=k,
            num_candidates=num_candidates,
            size=size,
        )
        try:
            client = self._client.options(request_timeout=request_timeout)
            response = await client.search(
                index=index_name,
                size=body["size"],
                source=body["_source"],
                knn=body["knn"],
            )
        except (ConnectionError, TransportError) as exc:
            raise VectorRetrievalError(
                "elasticsearch vector search transport failed",
                retryable=True,
            ) from exc
        except ApiError as exc:
            status = exc.status_code
            retryable = isinstance(status, int) and status >= 500
            raise VectorRetrievalError(
                "elasticsearch vector search request failed",
                retryable=retryable,
            ) from exc

        return _parse_hits(response)


def _coerce_search_response_body(response: Any) -> dict[str, Any]:
    body = getattr(response, "body", response)
    if not isinstance(body, dict):
        raise VectorRetrievalError(
            "elasticsearch vector response must be an object",
            retryable=False,
        )
    return body


def _parse_hits(response: Any) -> list[VectorRetrievalHit]:
    body = _coerce_search_response_body(response)

    hits_wrapper = body.get("hits")
    if not isinstance(hits_wrapper, dict):
        raise VectorRetrievalError("elasticsearch vector response missing hits", retryable=False)

    raw_hits = hits_wrapper.get("hits")
    if not isinstance(raw_hits, list):
        raise VectorRetrievalError(
            "elasticsearch vector response hits must be a list",
            retryable=False,
        )

    parsed: list[VectorRetrievalHit] = []
    seen_ids: set[str] = set()
    for index, hit in enumerate(raw_hits):
        if not isinstance(hit, dict):
            raise VectorRetrievalError(
                "elasticsearch vector hit must be an object",
                retryable=False,
            )

        memory_id = hit.get("_id")
        if not isinstance(memory_id, str) or not memory_id:
            raise VectorRetrievalError("elasticsearch vector hit missing _id", retryable=False)

        if memory_id in seen_ids:
            raise VectorRetrievalError(
                "elasticsearch vector response contains duplicate _id",
                retryable=False,
            )
        seen_ids.add(memory_id)

        score = hit.get("_score")
        if not isinstance(score, Real) or isinstance(score, bool):
            raise VectorRetrievalError(
                "elasticsearch vector hit missing valid _score",
                retryable=False,
            )

        parsed.append(
            VectorRetrievalHit(
                memory_id=memory_id,
                rank=index + 1,
                score=float(score),
            )
        )

    return parsed
