"""HTTP middleware for request ID, access logging, and metrics."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from memory_system.observability.metrics import observe_http_request
from memory_system.observability.request_context import clear_request_context, set_request_id

logger = structlog.get_logger(__name__)


def _is_valid_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4


def resolve_request_id(header_value: str | None) -> str:
    if header_value and _is_valid_uuid4(header_value):
        return header_value
    return str(uuid.uuid4())


def _path_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return str(route.path)
    return request.url.path


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = resolve_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers["X-Request-ID"] = request_id
        return response


class AccessLogMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        duration_seconds = time.perf_counter() - started
        duration_ms = int(duration_seconds * 1000)
        path_template = _path_template(request)
        status = str(response.status_code)
        observe_http_request(
            method=request.method,
            path_template=path_template,
            status=status,
            duration_seconds=duration_seconds,
        )
        logger.info(
            "http_request",
            method=request.method,
            path_template=path_template,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=getattr(request.state, "request_id", None),
        )
        return response
