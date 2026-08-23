"""Rerank service error types with redacted string representations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from memory_system.infrastructure.embedding.errors import _redact_for_display

_QUERY_RE = re.compile(r"query=[^\s,]+", re.IGNORECASE)
_DOCUMENT_RE = re.compile(r"document[s]?=[^\s,]+", re.IGNORECASE)


def _redact_rerank_message(message: str) -> str:
    redacted = _redact_for_display(message)
    redacted = _QUERY_RE.sub("query=<redacted>", redacted)
    redacted = _DOCUMENT_RE.sub("document=<redacted>", redacted)
    return redacted


@dataclass
class RerankServiceError(Exception):
    """Fail-closed rerank error with sanitized observability fields."""

    code: str
    provider: str
    status_code: int | None
    trace_id: str | None
    sanitized_message: str
    retry_after: float | None = None

    def __str__(self) -> str:
        safe_message = _redact_rerank_message(self.sanitized_message)
        parts = [
            f"code={self.code}",
            f"provider={self.provider}",
        ]
        if self.status_code is not None:
            parts.append(f"status_code={self.status_code}")
        if self.trace_id is not None:
            parts.append(f"trace_id={self.trace_id}")
        parts.append(f"message={safe_message}")
        return "RerankServiceError(" + ", ".join(parts) + ")"

    def __repr__(self) -> str:
        return self.__str__()
