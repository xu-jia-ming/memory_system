"""Fake embedding client for EXT-007 tests."""

from __future__ import annotations

from memory_system.infrastructure.embedding.errors import EmbeddingServiceError
from memory_system.infrastructure.embedding.types import EmbeddingResult


class FakeEmbeddingClient:
    def __init__(
        self,
        *,
        dimension: int = 1024,
        fail: bool = False,
        batch_calls: list[list[str]] | None = None,
    ) -> None:
        self.dimension = dimension
        self.fail = fail
        self.batch_calls = batch_calls if batch_calls is not None else []
        self.embed_calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self.embed_calls.append(list(texts))
        self.batch_calls.append(list(texts))
        if self.fail:
            raise EmbeddingServiceError(
                code="provider_unavailable",
                provider="fake",
                status_code=503,
                trace_id=None,
                sanitized_message="embedding unavailable",
            )
        vectors = [[0.1] * self.dimension for _ in texts]
        return EmbeddingResult(model="fake-model", dimension=self.dimension, vectors=vectors)
