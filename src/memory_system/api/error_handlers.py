"""Global exception handlers for unified API error envelopes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from memory_system.api.errors import AppError, build_error_body

logger = structlog.get_logger(__name__)


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    return "unknown"


def build_error_response(
    *,
    code: str,
    message: str,
    details: dict[str, Any],
    request_id: str,
    status_code: int,
) -> JSONResponse:
    body = build_error_body(
        code=code,
        message=message,
        details=details,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"X-Request-ID": request_id},
    )


def _should_redact_validation_key(key: str) -> bool:
    lower = key.lower()
    return "secret" in lower or "api_key" in lower or "authorization" in lower


def _sanitize_validation_errors(errors: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in list(errors):
        entry = dict(item)
        location = entry.get("loc")
        if isinstance(location, tuple | list):
            entry["loc"] = [
                (
                    "<redacted>"
                    if isinstance(part, str) and _should_redact_validation_key(part)
                    else part
                )
                for part in location
            ]
        if "ctx" in entry:
            ctx = entry.get("ctx")
            if isinstance(ctx, dict):
                entry["ctx"] = {
                    key: "<redacted>" if _should_redact_validation_key(key) else value
                    for key, value in ctx.items()
                }
        sanitized.append(entry)
    return sanitized


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id(request)
        if exc.status_code >= 500:
            logger.error(
                "app_error",
                error_code=exc.code,
                status_code=exc.status_code,
                request_id=request_id,
            )
        return build_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = _request_id(request)
        return build_error_response(
            code="validation_error",
            message="Request validation failed",
            details={"errors": _sanitize_validation_errors(exc.errors())},
            request_id=request_id,
            status_code=422,
        )

    @app.exception_handler(ValidationError)
    async def handle_validation_error(
        request: Request,
        exc: ValidationError,
    ) -> JSONResponse:
        request_id = _request_id(request)
        return build_error_response(
            code="validation_error",
            message="Request validation failed",
            details={"errors": _sanitize_validation_errors(exc.errors())},
            request_id=request_id,
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = _request_id(request)
        details: dict[str, Any] = {}
        if isinstance(exc.detail, dict):
            details = exc.detail
        elif isinstance(exc.detail, str):
            details = {"detail": exc.detail}
        return build_error_response(
            code="http_error",
            message="HTTP error",
            details=details,
            request_id=request_id,
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.exception(
            "internal_error",
            error_code="internal_error",
            request_id=request_id,
        )
        return build_error_response(
            code="internal_error",
            message="Internal server error",
            details={},
            request_id=request_id,
            status_code=503,
        )
