"""Embedding client contract types."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

EMBEDDING_DIMENSION = 1024


class EmbeddingResult(BaseModel):
    model: str
    dimension: int = Field(default=EMBEDDING_DIMENSION)
    vectors: list[list[float]]


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> EmbeddingResult: ...
