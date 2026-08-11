"""Memory session API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from memory_system.api.dependencies import require_memory_api_key
from memory_system.api.errors import AppError
from memory_system.api.schemas.memory_session import (
    CloseSessionResponse,
    CreateSessionRequest,
    CreateSessionResponse,
)
from memory_system.domain.services.session_close_service import (
    BaseCompressionVersionMismatchError,
    MalformedCompressionVersionError,
    MessageBoundaryMismatchError,
    SessionCloseIncompleteError,
    SessionCloseLockNotAcquiredError,
    SessionNotFoundCloseError,
    close_session,
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


@router.post(
    "/session/{user_id}/{session_id}/close",
    response_model=CloseSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def close_memory_session(
    request: Request,
    user_id: Annotated[str, Path(min_length=1, pattern=r"^\S+$")],
    session_id: Annotated[str, Path(min_length=1, pattern=r"^\S+$")],
    _role: Annotated[ApiKeyRole, Depends(require_memory_api_key)],
) -> CloseSessionResponse:
    app_state = request.app.state.app_state
    request_id = getattr(request.state, "request_id", None)

    try:
        result = await close_session(
            redis=app_state.redis,
            mongodb=app_state.mongodb,
            kafka_producer=app_state.kafka_producer,
            settings=app_state.settings,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id if isinstance(request_id, str) else None,
        )
    except SessionNotFoundCloseError as exc:
        raise AppError(
            code="session_not_found",
            message="Working memory session not found",
            status_code=404,
            details={},
        ) from exc
    except SessionCloseIncompleteError as exc:
        raise AppError(
            code="close_incomplete",
            message="Session close incomplete; Redis terminal delete failed",
            status_code=503,
            details={},
        ) from exc
    except (
        SessionCloseLockNotAcquiredError,
        MalformedCompressionVersionError,
        BaseCompressionVersionMismatchError,
        MessageBoundaryMismatchError,
    ) as exc:
        raise AppError(
            code="internal_error",
            message=str(exc),
            status_code=503,
            details={},
        ) from exc

    return CloseSessionResponse(
        session_id=result.session_id,
        archive_ids=result.archive_ids,
        status=result.status,
    )
