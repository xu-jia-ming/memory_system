"""Fake rerank client for unit and contract tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from memory_system.infrastructure.rerank.errors import RerankServiceError
from memory_system.infrastructure.rerank.types import RerankResult, RerankScoredDocument


@dataclass
class FakeRerankClient:
    """Configurable fake rerank client for tests."""

    results: list[RerankScoredDocument] | None = None
    error: RerankServiceError | None = None
    calls: list[dict[str, object]] = field(default_factory=list)

    async def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> RerankResult:
        self.calls.append(
            {
                "query": query,
                "documents": list(documents),
                "top_n": top_n,
            },
        )
        if self.error is not None:
            raise self.error
        if self.results is None:
            return RerankResult(
                results=[
                    RerankScoredDocument(index=index, relevance_score=1.0 - index * 0.1)
                    for index in range(len(documents))
                ],
            )
        return RerankResult(results=list(self.results))
