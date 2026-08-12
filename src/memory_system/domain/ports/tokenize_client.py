"""Tokenize client port for TEI /tokenize exact counts (EXT-006)."""

from __future__ import annotations

from typing import Protocol


class TokenizeClient(Protocol):
    async def count_tokens(self, text: str) -> int: ...
