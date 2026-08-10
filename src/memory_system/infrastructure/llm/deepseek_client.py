"""DeepSeek LLM client via openai.AsyncOpenAI (§3.9)."""

from __future__ import annotations

import logging
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from memory_system.infrastructure.llm.errors import LlmServiceError, _redact_for_display
from memory_system.settings.models import Settings

DEEPSEEK_PROVIDER = "deepseek"
SANITIZED_MESSAGE_MAX_LEN = 200


def _sanitize_message(raw: str) -> str:
    cleaned = _redact_for_display(raw.replace("\n", " ").strip())
    if len(cleaned) > SANITIZED_MESSAGE_MAX_LEN:
        return cleaned[:SANITIZED_MESSAGE_MAX_LEN] + "..."
    return cleaned


class DeepSeekLlmClient:
    """Single-call DeepSeek client; no transport-layer retry."""

    def __init__(
        self,
        settings: Settings,
        openai_client: AsyncOpenAI | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._logger = logger
        if openai_client is not None:
            self._client = openai_client
        else:
            self._client = AsyncOpenAI(
                api_key=settings.llm.api_key.get_secret_value(),
                base_url=settings.llm.base_url,
            )

    async def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> str:
        compression = self._settings.llm.compression
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=model,
                messages=messages,
                stream=False,
                temperature=float(compression.temperature),
                max_tokens=max_output_tokens,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": compression.thinking}},
                timeout=timeout_seconds,
            )
        except APITimeoutError as exc:
            raise LlmServiceError(
                code="llm_timeout",
                sanitized_message=_sanitize_message(str(exc)),
            ) from exc
        except APIConnectionError as exc:
            raise LlmServiceError(
                code="llm_request_failed",
                sanitized_message=_sanitize_message(str(exc)),
            ) from exc
        except APIStatusError as exc:
            status_code = exc.status_code
            raise LlmServiceError(
                code="llm_request_failed",
                sanitized_message=_sanitize_message(str(exc)),
                status_code=status_code,
            ) from exc
        except Exception as exc:
            raise LlmServiceError(
                code="llm_request_failed",
                sanitized_message=_sanitize_message(str(exc)),
            ) from exc

        content = self._extract_content(response)
        if content is None:
            raise LlmServiceError(
                code="llm_request_failed",
                sanitized_message="missing assistant message in response",
            )
        return content

    def _extract_content(self, response: Any) -> str | None:
        choices = getattr(response, "choices", None)
        if not choices:
            return None
        message = getattr(choices[0], "message", None)
        if message is None:
            return None
        content = getattr(message, "content", None)
        if content is None:
            return ""
        if not isinstance(content, str):
            return None
        return content
