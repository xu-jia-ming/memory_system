"""Provider-aware token-count port (TEI /tokenize exact vs STM-001 heuristic)."""

from __future__ import annotations

from typing import Protocol


class TokenizeClient(Protocol):
    async def count_tokens(self, text: str) -> int: ...
