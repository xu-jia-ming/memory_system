"""TEI HTTP embedding client."""

from __future__ import annotations

import math
from typing import Any

import httpx

from memory_system.infrastructure.embedding.batching import split_into_batches
from memory_system.infrastructure.embedding.errors import (
    EmbeddingInputTooLongError,
    EmbeddingServiceError,
    EmbeddingValidationError,
)
from memory_system.infrastructure.embedding.types import EMBEDDING_DIMENSION, EmbeddingResult
from memory_system.settings.models import Settings

_ZERO_VECTOR_TOLERANCE = 0.0


class TEIEmbeddingClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client
        self._base_url = settings.embedding.base_url.rstrip("/")
        self._model_id = settings.embedding.model_id
        self._max_batch_size = settings.embedding.max_client_batch_size
        self._per_input_token_limit = settings.embedding.per_input_token_limit
        self._max_batch_tokens = settings.embedding_client_total_token_budget
        self._timeout = settings.embedding_http_client.read_timeout_seconds

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self._validate_inputs(texts)

        token_counts = await self._tokenize(texts)
        self._validate_token_counts(token_counts)

        index_batches = split_into_batches(
            token_counts,
            max_batch_size=self._max_batch_size,
            max_batch_tokens=self._max_batch_tokens,
        )

        vectors: list[list[float] | None] = [None] * len(texts)
        response_model: str | None = None

        for index_batch in index_batches:
            batch_texts = [texts[index] for index in index_batch]
            batch_model, batch_vectors = await self._embed_batch(batch_texts)
            if response_model is None:
                response_model = batch_model
            elif batch_model != response_model:
                raise EmbeddingValidationError(
                    f"inconsistent embedding model in response: {batch_model!r}"
                )

            if len(batch_vectors) != len(index_batch):
                raise EmbeddingValidationError(
                    "embedding response count does not match sub-batch size"
                )

            for original_index, vector in zip(index_batch, batch_vectors, strict=True):
                self._validate_vector(vector)
                vectors[original_index] = vector

        resolved_model = response_model or self._model_id
        if resolved_model != self._model_id:
            raise EmbeddingValidationError(
                f"unexpected embedding model: {resolved_model!r}, expected {self._model_id!r}"
            )

        final_vectors: list[list[float]] = []
        for index in range(len(texts)):
            merged_vector = vectors[index]
            if merged_vector is None:
                raise EmbeddingValidationError("missing vectors after batch merge")
            final_vectors.append(merged_vector)

        return EmbeddingResult(
            model=resolved_model,
            dimension=EMBEDDING_DIMENSION,
            vectors=final_vectors,
        )

    def _validate_inputs(self, texts: list[str]) -> None:
        if not texts:
            raise EmbeddingValidationError("embed requires at least one text")
        if len(texts) > self._max_batch_size:
            raise EmbeddingValidationError(
                f"embed accepts at most {self._max_batch_size} texts per call"
            )
        if any(text == "" for text in texts):
            raise EmbeddingValidationError("empty string inputs are not allowed")

    def _validate_token_counts(self, token_counts: list[int]) -> None:
        for token_count in token_counts:
            if token_count == 0:
                raise EmbeddingValidationError("tokenize returned zero tokens for input")
            if token_count > self._per_input_token_limit:
                raise EmbeddingInputTooLongError(
                    f"input exceeds per-input token limit of {self._per_input_token_limit}"
                )

    async def _tokenize(self, texts: list[str]) -> list[int]:
        url = f"{self._base_url}/tokenize"
        try:
            response = await self._http_client.post(
                url,
                json={"inputs": texts},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingServiceError("tokenize request failed") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise EmbeddingServiceError(
                f"tokenize returned HTTP {response.status_code}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbeddingServiceError("tokenize response is not valid JSON") from exc

        return self._parse_tokenize_response(payload, expected_count=len(texts))

    def _parse_tokenize_response(self, payload: Any, *, expected_count: int) -> list[int]:
        if not isinstance(payload, list) or len(payload) != expected_count:
            raise EmbeddingServiceError("tokenize response shape is invalid")

        token_counts: list[int] = []
        for item in payload:
            if not isinstance(item, list):
                raise EmbeddingServiceError("tokenize response item is not a token list")
            token_counts.append(len(item))
        return token_counts

    async def _embed_batch(self, texts: list[str]) -> tuple[str, list[list[float]]]:
        url = f"{self._base_url}/v1/embeddings"
        try:
            response = await self._http_client.post(
                url,
                json={
                    "model": self._model_id,
                    "input": texts,
                    "encoding_format": "float",
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingServiceError("embeddings request failed") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise EmbeddingServiceError(
                f"embeddings returned HTTP {response.status_code}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbeddingServiceError("embeddings response is not valid JSON") from exc

        return self._parse_embeddings_response(payload, expected_count=len(texts))

    def _parse_embeddings_response(
        self,
        payload: Any,
        *,
        expected_count: int,
    ) -> tuple[str, list[list[float]]]:
        if not isinstance(payload, dict):
            raise EmbeddingServiceError("embeddings response is not an object")

        model = payload.get("model")
        if not isinstance(model, str):
            raise EmbeddingServiceError("embeddings response missing model")

        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise EmbeddingServiceError("embeddings response data count mismatch")

        vectors: list[list[float] | None] = [None] * expected_count
        for item in data:
            if not isinstance(item, dict):
                raise EmbeddingServiceError("embeddings response item is invalid")
            index = item.get("index")
            embedding = item.get("embedding")
            if not isinstance(index, int) or not (0 <= index < expected_count):
                raise EmbeddingServiceError("embeddings response index is invalid")
            if not isinstance(embedding, list):
                raise EmbeddingServiceError("embeddings response embedding is invalid")
            if vectors[index] is not None:
                raise EmbeddingServiceError("duplicate embedding index in response")
            vectors[index] = [float(value) for value in embedding]

        if any(vector is None for vector in vectors):
            raise EmbeddingServiceError("embeddings response missing vector indices")

        return model, [vector for vector in vectors if vector is not None]

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != EMBEDDING_DIMENSION:
            raise EmbeddingValidationError(
                f"embedding dimension must be {EMBEDDING_DIMENSION}, got {len(vector)}"
            )
        if not all(math.isfinite(value) for value in vector):
            raise EmbeddingValidationError("embedding vector contains NaN or Inf")
        if all(abs(value) <= _ZERO_VECTOR_TOLERANCE for value in vector):
            raise EmbeddingValidationError("embedding vector must not be all zeros")
