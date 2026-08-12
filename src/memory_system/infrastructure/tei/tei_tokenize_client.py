"""TEI POST /tokenize client for EXT-006 core_search_text gate."""

from __future__ import annotations

import httpx

from memory_system.settings.models import Settings


class TokenizeServiceError(Exception):
    """Raised when TEI /tokenize is unavailable or returns invalid data."""


class TeiTokenizeClient:
    """Count tokens via embedding service TEI /tokenize endpoint."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client
        self._base_url = settings.embedding.base_url.rstrip("/")

    async def count_tokens(self, text: str) -> int:
        url = f"{self._base_url}/tokenize"
        timeout = httpx.Timeout(
            connect=self._settings.embedding_http_client.connect_timeout_seconds,
            read=self._settings.embedding_http_client.read_timeout_seconds,
            write=self._settings.embedding_http_client.read_timeout_seconds,
            pool=self._settings.embedding_http_client.connect_timeout_seconds,
        )
        try:
            response = await self._http_client.post(
                url,
                json={"inputs": text},
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise TokenizeServiceError(str(exc)) from exc

        if response.status_code != 200:
            raise TokenizeServiceError(f"tokenize status {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise TokenizeServiceError("tokenize response is not json") from exc

        if not isinstance(payload, dict):
            raise TokenizeServiceError("tokenize response must be an object")

        token_count = payload.get("token_count")
        if not isinstance(token_count, int) or token_count < 0:
            raise TokenizeServiceError("tokenize response missing token_count")
        return token_count
