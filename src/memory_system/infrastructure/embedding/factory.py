"""Embedding client factory."""

from __future__ import annotations

import httpx

from memory_system.infrastructure.embedding.tei_client import TEIEmbeddingClient
from memory_system.infrastructure.embedding.types import EmbeddingClient
from memory_system.settings.models import Settings


def create_embedding_client(
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> EmbeddingClient:
    return TEIEmbeddingClient(settings, http_client)
