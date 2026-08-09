"""Bounded retry backoff helpers for embedding HTTP requests."""

from __future__ import annotations

import random

MAX_HTTP_ATTEMPTS = 3
MAX_BACKOFF_SECONDS = 8.0
BASE_BACKOFF_SECONDS = 0.5


def compute_backoff_delay(attempt: int, retry_after: float | None = None) -> float:
    """Return bounded exponential backoff with optional jitter."""
    if retry_after is not None:
        return min(retry_after, MAX_BACKOFF_SECONDS)
    delay = min(BASE_BACKOFF_SECONDS * (2**attempt), MAX_BACKOFF_SECONDS)
    return float(delay + random.uniform(0, 0.1))
