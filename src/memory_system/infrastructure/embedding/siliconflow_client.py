"""SiliconFlow hosted embedding client (BAAI/bge-m3 via POST /v1/embeddings)."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import Any

import httpx

from memory_system.infrastructure.embedding.errors import EmbeddingServiceError, _redact_for_display
from memory_system.infrastructure.embedding.retry import MAX_HTTP_ATTEMPTS, compute_backoff_delay
from memory_system.infrastructure.embedding.types import EmbeddingResult
from memory_system.settings.models import Settings

SILICONFLOW_MAX_BATCH_SIZE = 32
SILICONFLOW_PROVIDER = "siliconflow"
TRACE_ID_HEADER = "x-siliconcloud-trace-id"
SANITIZED_MESSAGE_MAX_LEN = 200
_RETRY_AFTER_RE = re.compile(r"^\d+(\.\d+)?$")


def _split_batches(texts: list[str], batch_size: int) -> list[list[str]]:
    return [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]


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


class SiliconFlowEmbeddingClient:
    """EmbeddingClient implementation for SiliconFlow hosted BAAI/bge-m3."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._logger = logger

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        retrieval = self._settings.memory_retrieval
        model = retrieval.embedding_model
        dimension = retrieval.embedding_dimension

        if not texts:
            return EmbeddingResult(model=model, dimension=dimension, vectors=[])

        for text in texts:
            if text == "":
                raise EmbeddingServiceError(
                    code="embedding_input_too_long",
                    provider=SILICONFLOW_PROVIDER,
                    status_code=None,
                    trace_id=None,
                    sanitized_message="empty input string is not allowed",
                )

        all_vectors: list[list[float]] = []
        for batch in _split_batches(texts, SILICONFLOW_MAX_BATCH_SIZE):
            batch_vectors = await self._embed_batch(batch)
            all_vectors.extend(batch_vectors)

        return EmbeddingResult(model=model, dimension=dimension, vectors=all_vectors)

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        last_error: EmbeddingServiceError | None = None

        for attempt in range(MAX_HTTP_ATTEMPTS):
            try:
                response = await self._post_embeddings(batch)
                return self._parse_success_response(response, len(batch))
            except EmbeddingServiceError as exc:
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
                last_error = EmbeddingServiceError(
                    code="embedding_failed",
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
        raise EmbeddingServiceError(
            code="embedding_failed",
            provider=SILICONFLOW_PROVIDER,
            status_code=None,
            trace_id=None,
            sanitized_message="embedding request failed after retries",
        )

    async def _post_embeddings(self, batch: list[str]) -> httpx.Response:
        retrieval = self._settings.memory_retrieval
        base_url = retrieval.siliconflow_base_url.rstrip("/")
        url = f"{base_url}/v1/embeddings"
        api_key = self._settings.siliconflow_api_key
        if api_key is None:
            raise EmbeddingServiceError(
                code="embedding_auth_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=None,
                trace_id=None,
                sanitized_message="siliconflow api key is not configured",
            )

        headers = {
            "Authorization": f"Bearer {api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        body = {
            "model": retrieval.embedding_model,
            "input": batch,
            "encoding_format": "float",
        }
        # Per-request timeout uses embedding_timeout_seconds.
        timeout = httpx.Timeout(retrieval.embedding_timeout_seconds)

        response = await self._http_client.post(url, headers=headers, json=body, timeout=timeout)
        if response.is_success:
            return response

        trace_id = response.headers.get(TRACE_ID_HEADER)
        sanitized_message = _sanitize_message(self._extract_error_message(response))
        status_code = response.status_code

        if status_code in (401, 403):
            raise EmbeddingServiceError(
                code="embedding_auth_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=status_code,
                trace_id=trace_id,
                sanitized_message=sanitized_message,
            )

        if status_code == 400:
            raise EmbeddingServiceError(
                code="embedding_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=status_code,
                trace_id=trace_id,
                sanitized_message=sanitized_message,
            )

        if status_code == 429 or 500 <= status_code <= 599:
            raise EmbeddingServiceError(
                code="embedding_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=status_code,
                trace_id=trace_id,
                sanitized_message=sanitized_message,
                retry_after=_parse_retry_after(response.headers.get("Retry-After")),
            )

        raise EmbeddingServiceError(
            code="embedding_failed",
            provider=SILICONFLOW_PROVIDER,
            status_code=status_code,
            trace_id=trace_id,
            sanitized_message=sanitized_message,
        )

    def _parse_success_response(
        self,
        response: httpx.Response,
        expected_count: int,
    ) -> list[list[float]]:
        try:
            payload: Any = response.json()
        except json.JSONDecodeError:
            raise EmbeddingServiceError(
                code="embedding_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=response.status_code,
                trace_id=response.headers.get(TRACE_ID_HEADER),
                sanitized_message="invalid json response",
            ) from None

        data = payload.get("data")
        if not isinstance(data, list):
            raise EmbeddingServiceError(
                code="embedding_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=response.status_code,
                trace_id=response.headers.get(TRACE_ID_HEADER),
                sanitized_message="missing data field in response",
            )

        if len(data) != expected_count:
            raise EmbeddingServiceError(
                code="embedding_failed",
                provider=SILICONFLOW_PROVIDER,
                status_code=response.status_code,
                trace_id=response.headers.get(TRACE_ID_HEADER),
                sanitized_message="response count mismatch",
            )

        dimension = self._settings.memory_retrieval.embedding_dimension
        sorted_items = sorted(data, key=lambda item: item.get("index", 0))
        vectors: list[list[float]] = []

        for item in sorted_items:
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise EmbeddingServiceError(
                    code="embedding_failed",
                    provider=SILICONFLOW_PROVIDER,
                    status_code=response.status_code,
                    trace_id=response.headers.get(TRACE_ID_HEADER),
                    sanitized_message="missing embedding field",
                )
            if len(embedding) != dimension:
                raise EmbeddingServiceError(
                    code="embedding_failed",
                    provider=SILICONFLOW_PROVIDER,
                    status_code=response.status_code,
                    trace_id=response.headers.get(TRACE_ID_HEADER),
                    sanitized_message="embedding dimension mismatch",
                )
            for value in embedding:
                if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    raise EmbeddingServiceError(
                        code="embedding_failed",
                        provider=SILICONFLOW_PROVIDER,
                        status_code=response.status_code,
                        trace_id=response.headers.get(TRACE_ID_HEADER),
                        sanitized_message="non-finite embedding value",
                    )
            vectors.append([float(v) for v in embedding])

        return vectors

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

    def _is_retryable(self, error: EmbeddingServiceError) -> bool:
        if error.status_code is None:
            return True
        return error.status_code == 429 or 500 <= error.status_code <= 599

    def _log_error(self, error: EmbeddingServiceError) -> None:
        if self._logger is None:
            return
        self._logger.warning(
            "siliconflow embedding error provider=%s status_code=%s trace_id=%s message=%s",
            error.provider,
            error.status_code,
            error.trace_id,
            error.sanitized_message,
        )
