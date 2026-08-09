"""Embedding service error types with redacted string representations."""

from __future__ import annotations

import re
from dataclasses import dataclass

_BEARER_RE = re.compile(r"Bearer\s+[^\s]+", re.IGNORECASE)
_SECRET_KEY_RE = re.compile(r"sk-[a-zA-Z0-9_-]+")
_VECTOR_RE = re.compile(r"vector=\[[^\]]*\]")


def _redact_for_display(message: str) -> str:
    redacted = _BEARER_RE.sub("<redacted>", message)
    redacted = _SECRET_KEY_RE.sub("<redacted>", redacted)
    redacted = _VECTOR_RE.sub("vector=<redacted>", redacted)
    return redacted


@dataclass
class EmbeddingServiceError(Exception):
    """Fail-closed embedding error with sanitized observability fields."""

    code: str
    provider: str
    status_code: int | None
    trace_id: str | None
    sanitized_message: str
    retry_after: float | None = None

    def __str__(self) -> str:
        safe_message = _redact_for_display(self.sanitized_message)
        parts = [
            f"code={self.code}",
            f"provider={self.provider}",
        ]
        if self.status_code is not None:
            parts.append(f"status_code={self.status_code}")
        if self.trace_id is not None:
            parts.append(f"trace_id={self.trace_id}")
        parts.append(f"message={safe_message}")
        return "EmbeddingServiceError(" + ", ".join(parts) + ")"

    def __repr__(self) -> str:
        return self.__str__()
