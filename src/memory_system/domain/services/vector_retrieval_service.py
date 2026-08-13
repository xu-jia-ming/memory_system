"""RET-002 Vector semantic retrieval orchestration service."""

from __future__ import annotations

from typing import Protocol

import structlog
from elasticsearch import AsyncElasticsearch

from memory_system.domain.models.vector_retrieval import (
    VectorRetrievalFailure,
    VectorRetrievalHit,
    VectorRetrievalOutcome,
    VectorRetrievalQuery,
    VectorRetrievalSuccess,
)
from memory_system.infrastructure.elasticsearch.vector_retrieval_repository import (
    EMBEDDING_DIMENSION,
    VectorRetrievalError,
    VectorRetrievalRepository,
)
from memory_system.settings.models import Settings

_logger = structlog.get_logger(__name__)

VALID_MEMORY_TYPES = frozenset({"fact", "preference", "event", "profile"})


class VectorRetrievalReadPort(Protocol):
    async def search(
        self,
        query: VectorRetrievalQuery,
        *,
        index_name: str,
        k: int,
        num_candidates: int,
        size: int,
        request_timeout: float,
    ) -> list[VectorRetrievalHit]: ...


class VectorRetrievalService:
    """Internal Vector kNN retrieval channel (§2.2.8). Does not perform embedding."""

    def __init__(
        self,
        repository: VectorRetrievalReadPort,
        *,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._settings = settings

    async def search(self, query: VectorRetrievalQuery) -> VectorRetrievalOutcome:
        try:
            normalized = self._validate_and_normalize(query)
        except ValueError as exc:
            return VectorRetrievalOutcome(
                outcome="failure",
                failure=VectorRetrievalFailure(
                    kind="channel_failure",
                    message=str(exc),
                    retryable=False,
                ),
            )

        retrieval_settings = self._settings.memory_retrieval

        try:
            hits = await self._repository.search(
                normalized,
                index_name=retrieval_settings.index_name,
                k=retrieval_settings.vector_top_n,
                num_candidates=retrieval_settings.vector_num_candidates,
                size=retrieval_settings.vector_top_n,
                request_timeout=float(retrieval_settings.elasticsearch_timeout_seconds),
            )
        except ValueError as exc:
            _logger.warning(
                "vector_retrieval_invalid_query",
                user_id=normalized.user_id,
            )
            return VectorRetrievalOutcome(
                outcome="failure",
                failure=VectorRetrievalFailure(
                    kind="channel_failure",
                    message=str(exc),
                    retryable=False,
                ),
            )
        except VectorRetrievalError as exc:
            _logger.warning(
                "vector_retrieval_channel_failure",
                user_id=normalized.user_id,
                retryable=exc.retryable,
            )
            return VectorRetrievalOutcome(
                outcome="failure",
                failure=VectorRetrievalFailure(
                    kind="channel_failure",
                    message=str(exc),
                    retryable=exc.retryable,
                ),
            )

        success = VectorRetrievalSuccess(
            user_id=normalized.user_id,
            hits=hits,
            total_hits=len(hits),
        )
        _logger.info(
            "vector_retrieval_success",
            user_id=normalized.user_id,
            hit_count=len(hits),
        )
        return VectorRetrievalOutcome(outcome="success", success=success)

    def _validate_and_normalize(self, query: VectorRetrievalQuery) -> VectorRetrievalQuery:
        user_id = query.user_id.strip()
        if not user_id:
            raise ValueError("user_id must not be empty")

        if len(query.query_vector) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"query_vector must have length {EMBEDDING_DIMENSION}, "
                f"got {len(query.query_vector)}",
            )

        memory_types = query.memory_types
        if memory_types is not None:
            deduped = list(dict.fromkeys(memory_types))
            if deduped:
                invalid = [value for value in deduped if value not in VALID_MEMORY_TYPES]
                if invalid:
                    raise ValueError("memory_types contains invalid values")
                memory_types = deduped
            else:
                memory_types = None

        return VectorRetrievalQuery(
            user_id=user_id,
            query_vector=list(query.query_vector),
            memory_types=memory_types,
            include_conflicted=query.include_conflicted,
            include_history=query.include_history,
        )


def create_vector_retrieval_service(
    elasticsearch: AsyncElasticsearch,
    *,
    settings: Settings,
) -> VectorRetrievalService:
    repository = VectorRetrievalRepository(elasticsearch)
    return VectorRetrievalService(repository, settings=settings)
