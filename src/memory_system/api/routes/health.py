"""Liveness and readiness health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from memory_system.infrastructure.runtime import (
    aggregate_readiness_status,
    collect_readiness_checks,
)

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready(request: Request) -> JSONResponse:
    state = request.app.state.app_state
    checks = await collect_readiness_checks(state)
    status = aggregate_readiness_status(checks)
    status_code = 200 if status == "ready" else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "checks": checks},
    )
