"""Embedding client errors."""

from __future__ import annotations


class EmbeddingError(Exception):
    """Base class for embedding client failures."""

    code: str = "embedding_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class EmbeddingInputTooLongError(EmbeddingError):
    code = "embedding_input_too_long"


class EmbeddingServiceError(EmbeddingError):
    code = "embedding_service_error"


class EmbeddingValidationError(EmbeddingError):
    code = "embedding_validation_error"
