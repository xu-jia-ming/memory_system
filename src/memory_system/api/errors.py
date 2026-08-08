"""Application error types."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Domain-agnostic HTTP error with stable API code."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def build_error_body(
    *,
    code: str,
    message: str,
    details: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "request_id": request_id,
    }
