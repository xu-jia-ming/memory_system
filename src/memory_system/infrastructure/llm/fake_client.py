"""Deterministic fake LLM client for tests and CI."""

from __future__ import annotations

from collections.abc import Sequence

from memory_system.infrastructure.llm.errors import LlmServiceError


class FakeLlmClient:
    """Fake LLMClient with injectable per-call responses or fixed modes."""

    def __init__(
        self,
        *,
        mode: str = "success",
        success_content: str | None = None,
        responses: Sequence[str | BaseException] | None = None,
    ) -> None:
        self._mode = mode
        self._success_content = success_content
        self._responses: list[str | BaseException] = list(responses) if responses else []
        self.call_count = 0
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None
        self.prompt_history: list[tuple[str, str]] = []

    async def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
        max_output_tokens: int,
        **kwargs: object,
    ) -> str:
        del kwargs
        del model, timeout_seconds, max_output_tokens
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        self.prompt_history.append((system_prompt, user_prompt))
        self.call_count += 1

        if self._responses:
            index = min(self.call_count - 1, len(self._responses) - 1)
            item = self._responses[index]
            if isinstance(item, BaseException):
                raise item
            return item

        if self._mode == "success":
            if self._success_content is not None:
                return self._success_content
            return '{"compressed_context":"compressed summary"}'

        if self._mode == "timeout":
            raise LlmServiceError(
                code="llm_timeout",
                sanitized_message="simulated read timeout",
            )

        if self._mode == "provider_error":
            raise LlmServiceError(
                code="llm_request_failed",
                sanitized_message="simulated provider error",
                status_code=503,
            )

        if self._mode == "invalid_json":
            return "not-json"

        if self._mode == "schema_invalid":
            return '{"wrong_field":"value"}'

        if self._mode == "empty_content":
            return ""

        if self._mode == "whitespace_content":
            return "   \n\t  "

        raise ValueError(f"unknown fake llm mode: {self._mode}")
