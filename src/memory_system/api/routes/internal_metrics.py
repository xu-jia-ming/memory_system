"""Internal Prometheus metrics endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from memory_system.api.dependencies import require_admin_api_key
from memory_system.infrastructure.security.api_key import ApiKeyRole

router = APIRouter(tags=["internal"])


@router.get("/internal/metrics")
async def internal_metrics(
    _role: Annotated[ApiKeyRole, Depends(require_admin_api_key)],
) -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
