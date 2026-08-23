"""HTTP adapter from LoCoMo ingest/QA onto Memory System MVP APIs."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MemoryApiError(RuntimeError):
    def __init__(self, status: int, body: Any) -> None:
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


class MemorySystemAdapter:
    """Thin client for session, message, close, extraction wait, and retrieval."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        admin_key: str,
        timeout_seconds: int = 180,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._admin_key = admin_key
        self._timeout = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        *,
        key: str,
        body: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self._base + path,
            data=data,
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout or self._timeout) as response:
                raw = response.read().decode("utf-8")
                parsed: Any = json.loads(raw) if raw else None
                return response.status, parsed
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw[:500]}
            return exc.code, parsed
        except URLError as exc:
            raise MemoryApiError(0, {"error": str(exc)}) from exc

    def create_session(self, user_id: str) -> str:
        status, body = self._request(
            "POST",
            "/api/v1/memory/session",
            key=self._api_key,
            body={"user_id": user_id},
        )
        if status != 200 or not isinstance(body, dict) or "session_id" not in body:
            raise MemoryApiError(status, body)
        return str(body["session_id"])

    def write_message(
        self,
        *,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        timestamp: int,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "message_id": message_id or str(uuid.uuid4()),
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
        }
        for attempt in range(3):
            status, body = self._request(
                "POST",
                "/api/v1/memory/working/message",
                key=self._api_key,
                body=payload,
            )
            if status == 200 and isinstance(body, dict):
                return body
            if status == 503 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise MemoryApiError(status, body)
        raise MemoryApiError(503, body)

    def close_session(self, user_id: str, session_id: str) -> list[str]:
        status, body = self._request(
            "POST",
            f"/api/v1/memory/session/{user_id}/{session_id}/close",
            key=self._api_key,
            timeout=180,
        )
        if status != 200 or not isinstance(body, dict):
            raise MemoryApiError(status, body)
        archive_ids = body.get("archive_ids") or []
        return [str(item) for item in archive_ids]

    def get_extraction(self, user_id: str, archive_id: str) -> tuple[int, dict[str, Any]]:
        status, body = self._request(
            "GET",
            f"/api/v1/memory/extraction/{user_id}/{archive_id}",
            key=self._admin_key,
            timeout=30,
        )
        if not isinstance(body, dict):
            body = {"raw": body}
        return status, body

    def retry_extraction(self, user_id: str, archive_id: str) -> dict[str, Any]:
        status, body = self._request(
            "POST",
            f"/api/v1/memory/extraction/{user_id}/{archive_id}/retry",
            key=self._admin_key,
            timeout=30,
        )
        if status != 200 or not isinstance(body, dict):
            raise MemoryApiError(status, body)
        return body

    def wait_for_extraction(
        self,
        user_id: str,
        archive_id: str,
        *,
        poll_seconds: float = 4.0,
        max_polls: int = 90,
        retry_on_invalid: bool = True,
    ) -> dict[str, Any]:
        retried = False
        last: dict[str, Any] = {}
        for _ in range(max_polls):
            status, body = self.get_extraction(user_id, archive_id)
            last = body
            ext_status = body.get("status") if status == 200 else None
            if status == 200 and ext_status == "completed":
                return body
            if status == 200 and ext_status == "failed":
                error = (body.get("last_error") or {}).get("error_code")
                if retry_on_invalid and not retried and error == "llm_invalid_output":
                    self.retry_extraction(user_id, archive_id)
                    retried = True
                    time.sleep(poll_seconds)
                    continue
                return body
            time.sleep(poll_seconds)
        last["status"] = last.get("status") or "timeout"
        return last

    def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        top_k: int = 10,
    ) -> dict[str, Any]:
        status, body = self._request(
            "POST",
            "/api/v1/memory/retrieval",
            key=self._api_key,
            body={"user_id": user_id, "query": query, "top_k": top_k},
            timeout=60,
        )
        if status != 200 or not isinstance(body, dict):
            raise MemoryApiError(status, body)
        return body
