"""Embedding client infrastructure."""

from memory_system.infrastructure.embedding.errors import EmbeddingServiceError
from memory_system.infrastructure.embedding.factory import create_embedding_client
from memory_system.infrastructure.embedding.siliconflow_client import SiliconFlowEmbeddingClient
from memory_system.infrastructure.embedding.types import EmbeddingClient, EmbeddingResult

__all__ = [
    "EmbeddingClient",
    "EmbeddingResult",
    "EmbeddingServiceError",
    "SiliconFlowEmbeddingClient",
    "create_embedding_client",
]
