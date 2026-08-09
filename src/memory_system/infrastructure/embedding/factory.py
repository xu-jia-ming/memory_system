"""Factory for embedding client dispatch by configured provider."""

from __future__ import annotations

import httpx

from memory_system.infrastructure.embedding.siliconflow_client import SiliconFlowEmbeddingClient
from memory_system.infrastructure.embedding.types import EmbeddingClient
from memory_system.settings.models import Settings


def create_embedding_client(
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> EmbeddingClient:
    """Return the embedding client for the configured provider."""
    provider = settings.memory_retrieval.embedding_provider
    if provider == "siliconflow":
        return SiliconFlowEmbeddingClient(settings, http_client)
    if provider == "local_tei":
        raise NotImplementedError(
            "local_tei embedding client is not implemented in DEV-007 MVP; "
            "use embedding_provider=siliconflow or defer to future TEI task"
        )
    raise ValueError(f"unsupported embedding_provider: {provider!r}")
