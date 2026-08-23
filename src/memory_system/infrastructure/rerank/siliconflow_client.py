"""SiliconFlow hosted rerank client (BAAI/bge-reranker-v2-m3 via POST /v1/rerank)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from memory_system.infrastructure.embedding.errors import _redact_for_display
from memory_system.infrastructure.rerank.errors import RerankServiceError
from memory_system.infrastructure.rerank.retry import MAX_HTTP_ATTEMPTS, compute_backoff_delay
from memory_system.infrastructure.rerank.types import RerankResult, RerankScoredDocument
from memory_system.settings.models import Settings

SILICONFLOW_PROVIDER = "siliconflow"
TRACE_ID_HEADER = "x-siliconcloud-trace-id"
SANITIZED_MESSAGE_MAX_LEN = 200
_RETRY_AFTER_RE = re.compile(r"^\d+(\.\d+)?$")


def _sanitize_message(raw: str) -> str:
    cleaned = _redact_for_display(raw.replace("\n", " ").strip())
    if len(cleaned) > SANITIZED_MESSAGE_MAX_LEN:
        return cleaned[:SANITIZED_MESSAGE_MAX_LEN] + "..."
    return cleaned


def _parse_retry_after(header_value: str | None) -> float | None:
    if header_value is None:
        return None
    stripped = header_value.strip()
    if _RETRY_AFTER_RE.match(stripped):
        return float(stripped)
    return None


class SiliconFlowRerankClient:
    """RerankClient implementation for SiliconFlow hosted BAAI/bge-reranker-v2-m3."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._logger = logger

    async def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> RerankResult:
        if not documents:
            return RerankResult(results=[])

        last_error: RerankServiceError | None = None

        for attempt in range(MAX_HTTP_ATTEMPTS):
            try:
                response = await self._post_rerank(query, documents, top_n)
                return self._parse_success_response(response, len(documents))
            except RerankServiceError as exc:
                if not self._is_retryable(exc):
                    raise
                last_error = exc
                self._log_error(exc)
            except (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.WriteError,
                httpx.PoolTimeout,
            ) as exc:
                last_error = RerankServiceError(
                    code="rerank_failed",
                    provider=SILICONFLOW_PROVIDER,
                    status_code=None,
                    trace_id=None,
                    sanitized_message=_sanitize_message(str(exc)),
                )
                self._log_error(last_error)

            if attempt < MAX_HTTP_ATTEMPTS - 1:
                retry_after = last_error.retry_after if last_error is not None else None
                await asyncio.sleep(compute_backoff_delay(attempt, retry_after))

        if last_error is not None:
            raise last_error
        raise RerankServiceError(
            code="rerank_failed",
            provider=SILICONFLOW_PROVIDER,
            status_code=None,
            trace_id=None,
            sanitized_message="rerank request failed after retries",
        )

    async def _post_rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> httpx.Response:
        retrieval = self._settings.memory_retrieval
        base_url = retrieval.siliconflow_base_url.rstrip("/")
        url = f"{base_url}/v1/rerank"
        api_key = self._settings.siliconflow_api_key
        if api_key is None:
            raise RerankServiceError(
                code="rerank_auth_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=None,
                trace_id=None,
                sanitized_message="siliconflow api key is not configured",
            )

        headers = {
            "Authorization": f"Bearer {api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": retrieval.rerank_model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        if retrieval.rerank_max_chunks_per_doc is not None:
            body["max_chunks_per_doc"] = retrieval.rerank_max_chunks_per_doc
        if retrieval.rerank_overlap_tokens is not None:
            body["overlap_tokens"] = retrieval.rerank_overlap_tokens

        timeout = httpx.Timeout(retrieval.rerank_timeout_seconds)
        response = await self._http_client.post(url, headers=headers, json=body, timeout=timeout)
        if response.is_success:
            return response

        trace_id = response.headers.get(TRACE_ID_HEADER)
        sanitized_message = _sanitize_message(self._extract_error_message(response))
        status_code = response.status_code

        if status_code in (401, 403):
            raise RerankServiceError(
                code="rerank_auth_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=status_code,
                trace_id=trace_id,
                sanitized_message=sanitized_message,
            )

        if status_code == 400:
            raise RerankServiceError(
                code="rerank_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=status_code,
                trace_id=trace_id,
                sanitized_message=sanitized_message,
            )

        if status_code == 429 or 500 <= status_code <= 599:
            raise RerankServiceError(
                code="rerank_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=status_code,
                trace_id=trace_id,
                sanitized_message=sanitized_message,
                retry_after=_parse_retry_after(response.headers.get("Retry-After")),
            )

        raise RerankServiceError(
            code="rerank_failed",
            provider=SILICONFLOW_PROVIDER,
            status_code=status_code,
            trace_id=trace_id,
            sanitized_message=sanitized_message,
        )

    def _parse_success_response(
        self,
        response: httpx.Response,
        document_count: int,
    ) -> RerankResult:
        try:
            payload: Any = response.json()
        except json.JSONDecodeError:
            raise RerankServiceError(
                code="rerank_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=response.status_code,
                trace_id=response.headers.get(TRACE_ID_HEADER),
                sanitized_message="invalid json response",
            ) from None

        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise RerankServiceError(
                code="rerank_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=response.status_code,
                trace_id=response.headers.get(TRACE_ID_HEADER),
                sanitized_message="missing results field in response",
            )

        scored: list[RerankScoredDocument] = []
        seen_indices: set[int] = set()
        for item in raw_results:
            if not isinstance(item, dict):
                raise RerankServiceError(
                    code="rerank_failed",
                    provider=SILICONFLOW_PROVIDER,
                    status_code=response.status_code,
                    trace_id=response.headers.get(TRACE_ID_HEADER),
                    sanitized_message="invalid result item",
                )
            index = item.get("index")
            score = item.get("relevance_score")
            if not isinstance(index, int) or not isinstance(score, (int, float)):
                raise RerankServiceError(
                    code="rerank_failed",
                    provider=SILICONFLOW_PROVIDER,
                    status_code=response.status_code,
                    trace_id=response.headers.get(TRACE_ID_HEADER),
                    sanitized_message="missing index or relevance_score",
                )
            if index < 0 or index >= document_count:
                raise RerankServiceError(
                    code="rerank_failed",
                    provider=SILICONFLOW_PROVIDER,
                    status_code=response.status_code,
                    trace_id=response.headers.get(TRACE_ID_HEADER),
                    sanitized_message="result index out of range",
                )
            if index in seen_indices:
                raise RerankServiceError(
                    code="rerank_failed",
                    provider=SILICONFLOW_PROVIDER,
                    status_code=response.status_code,
                    trace_id=response.headers.get(TRACE_ID_HEADER),
                    sanitized_message="duplicate result index",
                )
            seen_indices.add(index)
            scored.append(RerankScoredDocument(index=index, relevance_score=float(score)))

        return RerankResult(results=scored)

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            payload: Any = response.json()
            if isinstance(payload, dict):
                for key in ("message", "error"):
                    value = payload.get(key)
                    if isinstance(value, str):
                        return value
                    if isinstance(value, dict) and isinstance(value.get("message"), str):
                        return str(value["message"])
        except json.JSONDecodeError:
            pass
        return f"http {response.status_code}"

    def _is_retryable(self, error: RerankServiceError) -> bool:
        if error.status_code is None:
            return True
        return error.status_code == 429 or 500 <= error.status_code <= 599

    def _log_error(self, error: RerankServiceError) -> None:
        if self._logger is None:
            return
        self._logger.warning(
            "siliconflow rerank error provider=%s status_code=%s trace_id=%s message=%s",
            error.provider,
            error.status_code,
            error.trace_id,
            error.sanitized_message,
        )
