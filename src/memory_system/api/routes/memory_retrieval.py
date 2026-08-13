"""Memory retrieval API routes (§2.2.5)."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from memory_system.api.dependencies import require_memory_api_key
from memory_system.api.errors import AppError
from memory_system.api.schemas.memory_retrieval import (
    RetrievalMemoryItem,
    RetrievalObject,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalSubject,
)
from memory_system.domain.services.retrieval_api_service import (
    RetrievalApiFatalError,
    RetrievalApiInput,
    RetrievalApiValidationError,
    create_retrieval_api_service_from_app_state,
    resolve_top_k,
)
from memory_system.domain.services.retrieval_response_mapper import MappedRetrievalMemoryItem
from memory_system.infrastructure.security.api_key import ApiKeyRole

router = APIRouter(prefix="/api/v1/memory", tags=["memory-retrieval"])


def _to_response_item(item: MappedRetrievalMemoryItem) -> RetrievalMemoryItem:
    return RetrievalMemoryItem(
        memory_id=item.memory_id,
        memory_type=item.memory_type,
        content=item.content,
        subject=RetrievalSubject(
            entity_id=item.subject.entity_id,
            name=item.subject.name,
        ),
        predicate=item.predicate,
        object=RetrievalObject(
            entity_id=item.object.entity_id,
            name=item.object.name,
            value=item.object.value,
        ),
        status=item.status,
        event_status=item.event_status,
        start_time=item.start_time,
        end_time=item.end_time,
        confidence=item.confidence,
        importance=item.importance,
        latest_source_time=item.latest_source_time,
        score=item.score,
        retrieval_source=item.retrieval_source,
        source_message_ids=item.source_message_ids,
        evidence_count=item.evidence_count,
    )


@router.post(
    "/retrieval",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
)
async def retrieve_memories(
    request: Request,
    body: RetrievalRequest,
    _role: Annotated[ApiKeyRole, Depends(require_memory_api_key)],
) -> RetrievalResponse:
    app_state = request.app.state.app_state
    settings = app_state.settings
    loop = asyncio.get_event_loop()
    deadline = loop.time() + float(settings.memory_retrieval.retrieval_total_timeout_seconds)

    try:
        top_k = resolve_top_k(body.top_k, settings)
    except RetrievalApiValidationError as exc:
        raise AppError(
            code=exc.code,
            message=exc.message,
            status_code=400,
            details={},
        ) from exc

    service = create_retrieval_api_service_from_app_state(
        elasticsearch=app_state.elasticsearch,
        neo4j_driver=app_state.neo4j,
        http_client=app_state.http_client,
        settings=settings,
    )

    try:
        result = await service.retrieve(
            RetrievalApiInput(
                user_id=body.user_id,
                query=body.query,
                memory_types=body.memory_types,
                top_k=top_k,
                include_conflicted=body.include_conflicted,
                include_history=body.include_history,
                graph_expand=body.graph_expand,
            ),
            deadline=deadline,
        )
    except RetrievalApiValidationError as exc:
        raise AppError(
            code=exc.code,
            message=exc.message,
            status_code=400,
            details={},
        ) from exc
    except RetrievalApiFatalError as exc:
        raise AppError(
            code=exc.code,
            message=exc.message,
            status_code=503,
            details={},
        ) from exc
    except Exception as exc:
        raise AppError(
            code="internal_error",
            message="Internal error",
            status_code=503,
            details={},
        ) from exc

    return RetrievalResponse(
        retrieval_mode=result.retrieval_mode,
        warnings=result.warnings,
        memories=[_to_response_item(item) for item in result.memories],
    )
