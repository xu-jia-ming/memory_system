"""RET-001 BM25 keyword retrieval orchestration service."""

from __future__ import annotations

from typing import Protocol

import structlog
from elasticsearch import AsyncElasticsearch

from memory_system.domain.models.bm25_retrieval import (
    Bm25RetrievalFailure,
    Bm25RetrievalHit,
    Bm25RetrievalOutcome,
    Bm25RetrievalQuery,
    Bm25RetrievalSuccess,
)
from memory_system.infrastructure.elasticsearch.bm25_retrieval_repository import (
    Bm25RetrievalError,
    Bm25RetrievalRepository,
)
from memory_system.settings.models import Settings

_logger = structlog.get_logger(__name__)

VALID_MEMORY_TYPES = frozenset({"fact", "preference", "event", "profile"})


class Bm25RetrievalReadPort(Protocol):
    async def search(
        self,
        query: Bm25RetrievalQuery,
        *,
        index_name: str,
        size: int,
        request_timeout: float,
    ) -> list[Bm25RetrievalHit]: ...


class Bm25RetrievalService:
    """Internal BM25 keyword retrieval channel (§2.2.7)."""

    def __init__(
        self,
        repository: Bm25RetrievalReadPort,
        *,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._settings = settings

    async def search(self, query: Bm25RetrievalQuery) -> Bm25RetrievalOutcome:
        normalized = self._validate_and_normalize(query)
        retrieval_settings = self._settings.memory_retrieval

        try:
            hits = await self._repository.search(
                normalized,
                index_name=retrieval_settings.index_name,
                size=retrieval_settings.bm25_top_n,
                request_timeout=float(retrieval_settings.elasticsearch_timeout_seconds),
            )
        except Bm25RetrievalError as exc:
            _logger.warning(
                "bm25_retrieval_channel_failure",
                user_id=normalized.user_id,
                retryable=exc.retryable,
            )
            return Bm25RetrievalOutcome(
                outcome="failure",
                failure=Bm25RetrievalFailure(
                    message=str(exc),
                    retryable=exc.retryable,
                ),
            )

        success = Bm25RetrievalSuccess(
            user_id=normalized.user_id,
            hits=hits,
            total_hits=len(hits),
        )
        _logger.info(
            "bm25_retrieval_success",
            user_id=normalized.user_id,
            hit_count=len(hits),
        )
        return Bm25RetrievalOutcome(outcome="success", success=success)

    def _validate_and_normalize(self, query: Bm25RetrievalQuery) -> Bm25RetrievalQuery:
        user_id = query.user_id.strip()
        if not user_id:
            raise ValueError("user_id must not be empty")

        search_query = query.query.strip()
        if not search_query:
            raise ValueError("query must not be empty")

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

        return Bm25RetrievalQuery(
            user_id=user_id,
            query=search_query,
            memory_types=memory_types,
            include_conflicted=query.include_conflicted,
            include_history=query.include_history,
        )


def create_bm25_retrieval_service(
    elasticsearch: AsyncElasticsearch,
    *,
    settings: Settings,
) -> Bm25RetrievalService:
    repository = Bm25RetrievalRepository(elasticsearch)
    return Bm25RetrievalService(repository, settings=settings)
