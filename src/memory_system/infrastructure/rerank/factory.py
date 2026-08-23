"""Factory for rerank client dispatch by configured settings."""

from __future__ import annotations

import httpx

from memory_system.infrastructure.rerank.siliconflow_client import SiliconFlowRerankClient
from memory_system.infrastructure.rerank.types import (
    RerankClient,
    RerankResult,
    RerankScoredDocument,
)
from memory_system.settings.models import Settings


class NoOpRerankClient:
    """Pass-through rerank client used when rerank is disabled."""

    async def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> RerankResult:
        del query, top_n
        return RerankResult(
            results=[
                RerankScoredDocument(index=index, relevance_score=0.0)
                for index in range(len(documents))
            ]
        )


def create_rerank_client(
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> RerankClient:
    """Return the rerank client for the configured settings."""
    retrieval = settings.memory_retrieval
    if not retrieval.rerank_enabled:
        return NoOpRerankClient()
    if retrieval.embedding_provider == "siliconflow":
        return SiliconFlowRerankClient(settings, http_client)
    raise ValueError(
        "rerank_enabled requires memory_retrieval.embedding_provider=siliconflow in MVP"
    )
