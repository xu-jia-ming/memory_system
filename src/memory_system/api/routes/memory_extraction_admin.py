"""Extraction admin API routes (§2.1.14 GET / retry / rebuild)."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from memory_system.api.dependencies import require_admin_api_key
from memory_system.api.errors import AppError
from memory_system.api.schemas.memory_extraction_admin import (
    ExtractionLastErrorResponse,
    ExtractionMutationResponse,
    ExtractionStatusResponse,
)
from memory_system.domain.services.extraction_admin_service import (
    ExtractionAdminInfrastructureError,
    ExtractionTaskNotFoundError,
    RetryNotAllowedError,
    get_status,
    rebuild_task,
    retry_task,
)
from memory_system.infrastructure.security.api_key import ApiKeyRole

router = APIRouter(prefix="/api/v1/memory", tags=["memory-extraction-admin"])


def _status_path(
    user_id: Annotated[str, Path(min_length=1, pattern=r"^\S+$")],
    archive_id: Annotated[str, Path(min_length=1, pattern=r"^\S+$")],
) -> tuple[str, str]:
    return user_id, archive_id


@router.get(
    "/extraction/{user_id}/{archive_id}",
    response_model=ExtractionStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_extraction_status(
    request: Request,
    path: Annotated[tuple[str, str], Depends(_status_path)],
    _role: Annotated[ApiKeyRole, Depends(require_admin_api_key)],
) -> ExtractionStatusResponse:
    user_id, archive_id = path
    app_state = request.app.state.app_state

    try:
        result = await get_status(
            mongodb=app_state.mongodb,
            user_id=user_id,
            archive_id=archive_id,
        )
    except ExtractionTaskNotFoundError as exc:
        raise AppError(
            code="extraction_task_not_found",
            message="Extraction task not found",
            status_code=404,
        ) from exc
    except ExtractionAdminInfrastructureError as exc:
        raise AppError(
            code="internal_error",
            message="Internal error",
            status_code=503,
        ) from exc

    last_error: ExtractionLastErrorResponse | None = None
    if result.last_error is not None:
        last_error = ExtractionLastErrorResponse(
            error_code=result.last_error.error_code,
            failed_stage=result.last_error.failed_stage,
            message=result.last_error.message,
        )

    return ExtractionStatusResponse(
        user_id=result.user_id,
        archive_id=result.archive_id,
        status=result.status.value,
        attempt_count=result.attempt_count,
        last_error=last_error,
        completed_time=result.completed_time,
    )


@router.post(
    "/extraction/{user_id}/{archive_id}/retry",
    response_model=ExtractionMutationResponse,
    status_code=status.HTTP_200_OK,
)
async def retry_extraction_task(
    request: Request,
    path: Annotated[tuple[str, str], Depends(_status_path)],
    _role: Annotated[ApiKeyRole, Depends(require_admin_api_key)],
) -> ExtractionMutationResponse:
    user_id, archive_id = path
    app_state = request.app.state.app_state

    try:
        result = await retry_task(
            mongodb=app_state.mongodb,
            kafka_producer=app_state.kafka_producer,
            settings=app_state.settings,
            user_id=user_id,
            archive_id=archive_id,
            now=int(time.time()),
        )
    except ExtractionTaskNotFoundError as exc:
        raise AppError(
            code="extraction_task_not_found",
            message="Extraction task not found",
            status_code=404,
        ) from exc
    except RetryNotAllowedError as exc:
        raise AppError(
            code="retry_not_allowed",
            message="Retry not allowed for this extraction task",
            status_code=409,
        ) from exc
    except ExtractionAdminInfrastructureError as exc:
        raise AppError(
            code="internal_error",
            message="Internal error",
            status_code=503,
        ) from exc

    return ExtractionMutationResponse(
        user_id=result.user_id,
        archive_id=result.archive_id,
        status="pending",
    )


@router.post(
    "/extraction/{user_id}/{archive_id}/rebuild",
    response_model=ExtractionMutationResponse,
    status_code=status.HTTP_200_OK,
)
async def rebuild_extraction_task(
    request: Request,
    path: Annotated[tuple[str, str], Depends(_status_path)],
    _role: Annotated[ApiKeyRole, Depends(require_admin_api_key)],
) -> ExtractionMutationResponse:
    user_id, archive_id = path
    app_state = request.app.state.app_state

    try:
        result = await rebuild_task(
            mongodb=app_state.mongodb,
            kafka_producer=app_state.kafka_producer,
            settings=app_state.settings,
            user_id=user_id,
            archive_id=archive_id,
            now=int(time.time()),
        )
    except ExtractionTaskNotFoundError as exc:
        raise AppError(
            code="extraction_task_not_found",
            message="Extraction task not found",
            status_code=404,
        ) from exc
    except RetryNotAllowedError as exc:
        raise AppError(
            code="retry_not_allowed",
            message="Retry not allowed for this extraction task",
            status_code=409,
        ) from exc
    except ExtractionAdminInfrastructureError as exc:
        raise AppError(
            code="internal_error",
            message="Internal error",
            status_code=503,
        ) from exc

    return ExtractionMutationResponse(
        user_id=result.user_id,
        archive_id=result.archive_id,
        status="pending",
    )
