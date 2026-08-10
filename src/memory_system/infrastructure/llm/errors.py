"""LLM service error types with redacted string representations."""

from __future__ import annotations

import re
from dataclasses import dataclass

_BEARER_RE = re.compile(r"Bearer\s+[^\s]+", re.IGNORECASE)
_SECRET_KEY_RE = re.compile(r"sk-[a-zA-Z0-9_-]+")


def _redact_for_display(message: str) -> str:
    redacted = _BEARER_RE.sub("<redacted>", message)
    return _SECRET_KEY_RE.sub("<redacted>", redacted)


@dataclass
class LlmServiceError(Exception):
    """Fail-closed LLM transport error with sanitized observability fields."""

    code: str
    sanitized_message: str
    status_code: int | None = None

    def __str__(self) -> str:
        safe_message = _redact_for_display(self.sanitized_message)
        parts = [f"code={self.code}"]
        if self.status_code is not None:
            parts.append(f"status_code={self.status_code}")
        parts.append(f"message={safe_message}")
        return "LlmServiceError(" + ", ".join(parts) + ")"

    def __repr__(self) -> str:
        return self.__str__()
