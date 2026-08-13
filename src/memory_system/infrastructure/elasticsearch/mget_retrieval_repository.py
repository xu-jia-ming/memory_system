"""Elasticsearch read repository for RET-003 MGET existence checks."""

from __future__ import annotations

from typing import Any

from elasticsearch import ApiError, AsyncElasticsearch, ConnectionError, TransportError


class MgetRetrievalError(Exception):
    """Raised when Elasticsearch MGET fails or returns a malformed response."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class MgetRetrievalRepository:
    """Read-only Elasticsearch repository for retrieval document existence via _mget."""

    def __init__(self, client: AsyncElasticsearch) -> None:
        self._client = client

    def build_mget_body(self, memory_ids: list[str]) -> dict[str, list[str]]:
        return {"ids": sorted(memory_ids)}

    async def exists_many(
        self,
        *,
        index_name: str,
        memory_ids: list[str],
        request_timeout: float,
    ) -> set[str]:
        if not memory_ids:
            return set()

        body = self.build_mget_body(memory_ids)
        try:
            client = self._client.options(request_timeout=request_timeout)
            response = await client.mget(index=index_name, body=body, source=False)
        except (ConnectionError, TransportError) as exc:
            raise MgetRetrievalError(
                "elasticsearch mget transport failed",
                retryable=True,
            ) from exc
        except ApiError as exc:
            status = exc.status_code
            retryable = isinstance(status, int) and status >= 500
            raise MgetRetrievalError(
                "elasticsearch mget request failed",
                retryable=retryable,
            ) from exc

        return _parse_found_ids(response)


def _coerce_mget_response_body(response: Any) -> dict[str, Any]:
    body = getattr(response, "body", response)
    if not isinstance(body, dict):
        raise MgetRetrievalError("elasticsearch mget response must be an object", retryable=False)
    return body


def _parse_found_ids(response: Any) -> set[str]:
    body = _coerce_mget_response_body(response)
    docs = body.get("docs")
    if not isinstance(docs, list):
        raise MgetRetrievalError("elasticsearch mget response missing docs", retryable=False)

    found: set[str] = set()
    for doc in docs:
        if not isinstance(doc, dict):
            raise MgetRetrievalError("elasticsearch mget doc must be an object", retryable=False)
        if doc.get("found") is True:
            doc_id = doc.get("_id")
            if not isinstance(doc_id, str) or not doc_id:
                raise MgetRetrievalError(
                    "elasticsearch mget found doc missing _id",
                    retryable=False,
                )
            found.add(doc_id)
    return found
