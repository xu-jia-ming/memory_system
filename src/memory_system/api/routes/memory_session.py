"""Memory session API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from memory_system.api.dependencies import require_memory_api_key
from memory_system.api.schemas.memory_session import (
    CreateSessionRequest,
    CreateSessionResponse,
)
from memory_system.domain.services.session_service import create_session
from memory_system.infrastructure.security.api_key import ApiKeyRole

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.post(
    "/session",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def create_memory_session(
    request: Request,
    body: CreateSessionRequest,
    _role: Annotated[ApiKeyRole, Depends(require_memory_api_key)],
) -> CreateSessionResponse:
    app_state = request.app.state.app_state
    session_id, created_status = await create_session(
        redis=app_state.redis,
        user_id=body.user_id,
    )
    return CreateSessionResponse(session_id=session_id, status=created_status)
