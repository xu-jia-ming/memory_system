"""Shared fake helpers for compression LLM contract tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

DEFAULT_SUCCESS_JSON = '{"compressed_context":"compressed summary"}'


def make_chat_completion(
    content: str | None,
    *,
    model: str = "deepseek-v4-flash",
) -> ChatCompletion:
    message = ChatCompletionMessage(role="assistant", content=content)
    choice = Choice(finish_reason="stop", index=0, message=message)
    return ChatCompletion(
        id="chatcmpl-test",
        choices=[choice],
        created=0,
        model=model,
        object="chat.completion",
    )


def make_success_response(
    compressed_context: str = "compressed summary",
    *,
    model: str = "deepseek-v4-flash",
) -> ChatCompletion:
    payload = json.dumps({"compressed_context": compressed_context})
    return make_chat_completion(payload, model=model)


def make_mock_create(
    handler: Callable[..., Any],
) -> Callable[..., Any]:
    return handler
