"""Fake SiliconFlow embedding HTTP responses for contract tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

EMBEDDING_DIMENSION = 1024


def make_vector(seed: float = 0.1) -> list[float]:
    return [seed + (index % 10) / 1000.0 for index in range(EMBEDDING_DIMENSION)]


def make_embeddings_response(
    texts: list[str],
    *,
    shuffle_indices: bool = False,
    model: str = "BAAI/bge-m3",
) -> dict[str, Any]:
    indices = list(range(len(texts)))
    if shuffle_indices:
        indices = list(reversed(indices))
    data = [
        {
            "index": index,
            "object": "embedding",
            "embedding": make_vector(0.1 + index * 0.01),
        }
        for index in indices
    ]
    return {
        "object": "list",
        "model": model,
        "data": data,
        "usage": {
            "prompt_tokens": len(texts),
            "completion_tokens": 0,
            "total_tokens": len(texts),
        },
    }


def make_mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def json_response(
    status_code: int,
    payload: dict[str, Any] | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    content = json.dumps(payload or {}).encode("utf-8")
    response_headers = {"Content-Type": "application/json"}
    if headers:
        response_headers.update(headers)
    return httpx.Response(status_code, content=content, headers=response_headers)


def parse_request_input(request: httpx.Request) -> list[str]:
    body = json.loads(request.content.decode("utf-8"))
    raw_input = body["input"]
    if isinstance(raw_input, str):
        return [raw_input]
    return list(raw_input)
