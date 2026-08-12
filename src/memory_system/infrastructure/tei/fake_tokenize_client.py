"""Fake tokenize client for EXT-006 tests."""

from __future__ import annotations


class FakeTokenizeClient:
    """Deterministic token counter for unit and integration tests."""

    def __init__(self, *, token_count: int | None = None, fail: bool = False) -> None:
        self._token_count = token_count
        self._fail = fail
        self.calls: list[str] = []

    async def count_tokens(self, text: str) -> int:
        self.calls.append(text)
        if self._fail:
            raise RuntimeError("tokenize unavailable")
        if self._token_count is not None:
            return self._token_count
        return max(1, len(text.split()))
