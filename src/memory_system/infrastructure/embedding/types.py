"""Embedding client protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingResult:
    """Ordered embedding vectors returned from an embed call."""

    model: str
    dimension: int
    vectors: list[list[float]]


class EmbeddingClient(Protocol):
    """Protocol for text embedding providers."""

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Embed texts and return vectors in input order."""
        ...
