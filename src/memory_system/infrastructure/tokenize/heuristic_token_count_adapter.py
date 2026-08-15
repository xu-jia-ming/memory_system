"""Heuristic / character-ratio token-count adapter (not an exact tokenizer).

Wraps STM-001 ``estimate_tokens`` (§1.2.1). This is a character-ratio
approximation, not TEI ``/tokenize`` exact counts. MUST NOT be documented
or used as an exact model tokenizer.
"""

from __future__ import annotations

from memory_system.domain.services.token_estimator import estimate_tokens


class HeuristicTokenCountAdapter:
    """Async adapter over STM-001 ``estimate_tokens``; zero HTTP."""

    async def count_tokens(self, text: str) -> int:
        return estimate_tokens(text)
