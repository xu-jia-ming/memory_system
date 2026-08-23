"""Rerank client protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RerankScoredDocument:
    """Single reranked document with relevance score."""

    index: int
    relevance_score: float


@dataclass(frozen=True)
class RerankResult:
    """Ordered rerank results (descending relevance)."""

    results: list[RerankScoredDocument]


class RerankClient(Protocol):
    """Protocol for cross-encoder rerank providers."""

    async def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> RerankResult:
        """Rerank documents for query and return scored results."""
        ...
