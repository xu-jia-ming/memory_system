"""Factory for tokenize client dispatch by configured embedding provider."""

from __future__ import annotations

import httpx

from memory_system.domain.ports.tokenize_client import TokenizeClient
from memory_system.infrastructure.tei.tei_tokenize_client import TeiTokenizeClient
from memory_system.infrastructure.tokenize.heuristic_token_count_adapter import (
    HeuristicTokenCountAdapter,
)
from memory_system.settings.models import Settings


def create_tokenize_client(
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> TokenizeClient:
    """Return the token-count client for the configured embedding provider."""
    provider = settings.memory_retrieval.embedding_provider
    if provider == "siliconflow":
        return HeuristicTokenCountAdapter()
    if provider == "local_tei":
        return TeiTokenizeClient(settings, http_client)
    raise ValueError(f"unsupported embedding_provider: {provider!r}")
