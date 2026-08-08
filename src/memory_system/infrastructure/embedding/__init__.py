"""TEI embedding infrastructure."""

from memory_system.infrastructure.embedding.errors import (
    EmbeddingError,
    EmbeddingInputTooLongError,
    EmbeddingServiceError,
    EmbeddingValidationError,
)
from memory_system.infrastructure.embedding.factory import create_embedding_client
from memory_system.infrastructure.embedding.types import (
    EMBEDDING_DIMENSION,
    EmbeddingClient,
    EmbeddingResult,
)

__all__ = [
    "EMBEDDING_DIMENSION",
    "EmbeddingClient",
    "EmbeddingError",
    "EmbeddingInputTooLongError",
    "EmbeddingResult",
    "EmbeddingServiceError",
    "EmbeddingValidationError",
    "create_embedding_client",
]
