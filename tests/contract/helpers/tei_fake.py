"""Fake TEI HTTP transport for contract tests."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

import httpx

from memory_system.infrastructure.embedding.types import EMBEDDING_DIMENSION

MODEL_ID = "BAAI/bge-m3"


def make_finite_vector(seed: float, *, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    values = [
        math.sin(seed + index) + math.cos(seed * 0.5 + index * 0.01)
        for index in range(dimension)
    ]
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        values[0] = 1.0
        norm = 1.0
    return [value / norm for value in values]


@dataclass
class FakeTEIState:
    token_counts: dict[str, int] = field(default_factory=dict)
    default_token_count: int = 8
    embeddings_status_by_call: dict[int, int] = field(default_factory=dict)
    embeddings_vector_kind_by_call: dict[int, str] = field(default_factory=dict)
    reject_direct_long_embeddings: bool = True
    direct_long_token_threshold: int = 1024
    tokenize_calls: list[list[str]] = field(default_factory=list)
    embeddings_calls: list[list[str]] = field(default_factory=list)

    def reset_calls(self) -> None:
        self.tokenize_calls.clear()
        self.embeddings_calls.clear()


class FakeTEITransport(httpx.AsyncBaseTransport):
    def __init__(self, state: FakeTEIState) -> None:
        self._state = state

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/tokenize"):
            return self._handle_tokenize(request)
        if path.endswith("/v1/embeddings"):
            return self._handle_embeddings(request)
        if path.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(404, json={"error": "not found"})

    def _handle_tokenize(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        inputs = payload.get("inputs")
        if isinstance(inputs, str):
            texts = [inputs]
        elif isinstance(inputs, list) and all(isinstance(item, str) for item in inputs):
            texts = inputs
        else:
            return httpx.Response(422, json={"error": "invalid inputs"})

        self._state.tokenize_calls.append(list(texts))
        response_payload = []
        for text in texts:
            token_count = self._state.token_counts.get(text, self._state.default_token_count)
            response_payload.append(
                [
                    {"id": index, "text": f"t{index}", "special": False}
                    for index in range(token_count)
                ]
            )
        return httpx.Response(200, json=response_payload)

    def _handle_embeddings(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        inputs = payload.get("input")
        if isinstance(inputs, str):
            texts = [inputs]
        elif isinstance(inputs, list) and all(isinstance(item, str) for item in inputs):
            texts = inputs
        else:
            return httpx.Response(422, json={"error": "invalid input"})

        call_index = len(self._state.embeddings_calls)
        self._state.embeddings_calls.append(list(texts))

        if self._state.reject_direct_long_embeddings:
            for text in texts:
                token_count = self._state.token_counts.get(text, self._state.default_token_count)
                if token_count > self._state.direct_long_token_threshold:
                    return httpx.Response(
                        400,
                        json={"error": "input too long for model"},
                    )

        status_code = self._state.embeddings_status_by_call.get(call_index, 200)
        if status_code != 200:
            return httpx.Response(status_code, json={"error": "embeddings failed"})

        vector_kind = self._state.embeddings_vector_kind_by_call.get(call_index, "valid")
        data: list[dict[str, Any]] = []
        for index, text in enumerate(texts):
            embedding = self._build_vector(vector_kind, seed=float(index + len(text)))
            data.append({"object": "embedding", "index": index, "embedding": embedding})

        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "object": "list",
                    "model": MODEL_ID,
                    "data": data,
                },
                allow_nan=vector_kind == "nan",
            ),
            headers={"Content-Type": "application/json"},
        )

    def _build_vector(self, vector_kind: str, *, seed: float) -> list[float]:
        if vector_kind == "wrong_dim":
            return [0.1] * (EMBEDDING_DIMENSION - 1)
        if vector_kind == "nan":
            vector = make_finite_vector(seed)
            vector[0] = float("nan")
            return vector
        if vector_kind == "zero":
            return [0.0] * EMBEDDING_DIMENSION
        return make_finite_vector(seed)


def build_fake_tei_client(state: FakeTEIState) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=FakeTEITransport(state),
        base_url="http://fake-tei",
    )
