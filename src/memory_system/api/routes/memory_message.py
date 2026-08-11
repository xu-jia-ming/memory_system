"""Memory working message API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from memory_system.api.dependencies import require_memory_api_key
from memory_system.api.errors import AppError
from memory_system.api.schemas.memory_message import WriteMessageRequest, WriteMessageResponse
from memory_system.domain.enums.working_memory import MessageRole
from memory_system.domain.models.message_write import MessageWriteInput
from memory_system.domain.services.compression_coordinator_service import (
    InvalidMessageTimestampError,
    MessageTooLargeCoordinatorError,
    SessionClosingCoordinatorError,
    SessionNotFoundCoordinatorError,
    WorkingMemoryFullCoordinatorError,
    write_working_message_with_coordination,
)
from memory_system.domain.services.message_write_service import MessageWriteValidationError
from memory_system.infrastructure.security.api_key import ApiKeyRole

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.post(
    "/working/message",
    response_model=WriteMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def write_working_message(
    request: Request,
    body: WriteMessageRequest,
    _role: Annotated[ApiKeyRole, Depends(require_memory_api_key)],
) -> WriteMessageResponse:
    app_state = request.app.state.app_state
    llm_client = request.app.state.llm_client
    request_id = getattr(request.state, "request_id", None)

    try:
        result = await write_working_message_with_coordination(
            redis=app_state.redis,
            mongodb=app_state.mongodb,
            kafka_producer=app_state.kafka_producer,
            llm_client=llm_client,
            settings=app_state.settings,
            input=MessageWriteInput(
                user_id=body.user_id,
                session_id=body.session_id,
                message_id=body.message_id,
                role=MessageRole(body.role),
                content=body.content,
                timestamp=body.timestamp,
            ),
            request_id=request_id if isinstance(request_id, str) else None,
        )
    except MessageWriteValidationError as exc:
        raise AppError(
            code="validation_error",
            message=str(exc),
            status_code=422,
            details={},
        ) from exc
    except InvalidMessageTimestampError as exc:
        raise AppError(
            code="invalid_message_timestamp",
            message="Message timestamp exceeds allowed future skew",
            status_code=400,
            details={},
        ) from exc
    except MessageTooLargeCoordinatorError as exc:
        raise AppError(
            code="message_too_large",
            message="Message exceeds maximum estimated tokens",
            status_code=400,
            details={},
        ) from exc
    except SessionNotFoundCoordinatorError as exc:
        raise AppError(
            code="session_not_found",
            message="Working memory session not found",
            status_code=404,
            details={},
        ) from exc
    except SessionClosingCoordinatorError as exc:
        raise AppError(
            code="session_closing",
            message="Session is closing; new writes are rejected",
            status_code=409,
            details={},
        ) from exc
    except WorkingMemoryFullCoordinatorError as exc:
        raise AppError(
            code="working_memory_full",
            message="Working memory capacity exceeded after compression",
            status_code=503,
            details={},
        ) from exc

    return WriteMessageResponse(
        message_id=result.message_id,
        status=result.status,
        compression_status=result.compression_status,
    )
