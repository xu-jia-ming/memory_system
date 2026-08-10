"""LLM client protocol aligned with §3.9 (transport layer only)."""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Provider client that performs a single structured-output HTTP call.

    Returns raw assistant ``content`` string. JSON parse, schema validation,
    blank detection, and bounded schema retry are owned by the domain service.
    """

    async def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> str:
        """Perform one provider call and return raw assistant content."""
        ...
