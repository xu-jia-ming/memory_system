"""RET-002 Hybrid retrieval orchestration: parallel BM25 + Vector with RRF fusion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

import httpx
import structlog
from elasticsearch import AsyncElasticsearch

from memory_system.domain.models.bm25_retrieval import Bm25RetrievalOutcome, Bm25RetrievalQuery
from memory_system.domain.models.hybrid_retrieval import (
    HybridRetrievalOutcome,
    HybridRetrievalQuery,
)
from memory_system.domain.models.vector_retrieval import (
    VectorRetrievalFailure,
    VectorRetrievalOutcome,
    VectorRetrievalQuery,
)
from memory_system.domain.services.bm25_retrieval_service import create_bm25_retrieval_service
from memory_system.domain.services.retrieval_query_normalizer import normalize_retrieval_query
from memory_system.domain.services.rrf_fusion import fuse_rrf
from memory_system.domain.services.vector_retrieval_service import create_vector_retrieval_service
from memory_system.infrastructure.embedding.errors import EmbeddingServiceError
from memory_system.infrastructure.embedding.factory import create_embedding_client
from memory_system.infrastructure.embedding.types import EmbeddingClient
from memory_system.settings.models import Settings

_logger = structlog.get_logger(__name__)

VALID_MEMORY_TYPES = frozenset({"fact", "preference", "event", "profile"})


@dataclass(frozen=True)
class _RetrievalFilterFields:
    user_id: str
    memory_types: list[str] | None
    include_conflicted: bool
    include_history: bool


class Bm25RetrievalSearchPort(Protocol):
    async def search(self, query: Bm25RetrievalQuery) -> Bm25RetrievalOutcome: ...


class VectorRetrievalSearchPort(Protocol):
    async def search(self, query: VectorRetrievalQuery) -> VectorRetrievalOutcome: ...


class HybridRetrievalService:
    """Parallel BM25 + Embedding + Vector retrieval with RRF fusion."""

    def __init__(
        self,
        bm25_service: Bm25RetrievalSearchPort,
        vector_service: VectorRetrievalSearchPort,
        embedding_client: EmbeddingClient,
        *,
        settings: Settings,
    ) -> None:
        self._bm25_service = bm25_service
        self._vector_service = vector_service
        self._embedding_client = embedding_client
        self._settings = settings

    async def search(self, query: HybridRetrievalQuery) -> HybridRetrievalOutcome:
        normalized_query, filter_fields = self._validate_and_prepare(query)

        bm25_task = asyncio.create_task(
            self._bm25_service.search(
                Bm25RetrievalQuery(
                    user_id=filter_fields.user_id,
                    query=normalized_query,
                    memory_types=filter_fields.memory_types,
                    include_conflicted=filter_fields.include_conflicted,
                    include_history=filter_fields.include_history,
                ),
            ),
        )
        vector_task = asyncio.create_task(
            self._embed_and_vector_search(
                user_id=filter_fields.user_id,
                normalized_query=normalized_query,
                memory_types=filter_fields.memory_types,
                include_conflicted=filter_fields.include_conflicted,
                include_history=filter_fields.include_history,
            ),
        )

        bm25_outcome, vector_outcome = await asyncio.gather(bm25_task, vector_task)

        retrieval_settings = self._settings.memory_retrieval
        return fuse_rrf(
            bm25_outcome,
            vector_outcome,
            rrf_k=retrieval_settings.rrf_k,
            fused_top_n=retrieval_settings.fused_top_n,
            user_id=filter_fields.user_id,
        )

    async def _embed_and_vector_search(
        self,
        *,
        user_id: str,
        normalized_query: str,
        memory_types: list[str] | None,
        include_conflicted: bool,
        include_history: bool,
    ) -> VectorRetrievalOutcome:
        expected_dimension = self._settings.memory_retrieval.embedding_dimension

        try:
            result = await self._embedding_client.embed(texts=[normalized_query])
        except EmbeddingServiceError as exc:
            retryable = exc.status_code is None or exc.status_code >= 500
            _logger.warning(
                "hybrid_retrieval_embedding_failure",
                user_id=user_id,
                retryable=retryable,
            )
            return VectorRetrievalOutcome(
                outcome="failure",
                failure=VectorRetrievalFailure(
                    kind="channel_failure",
                    message=str(exc),
                    retryable=retryable,
                ),
            )

        if result.dimension != expected_dimension:
            return VectorRetrievalOutcome(
                outcome="failure",
                failure=VectorRetrievalFailure(
                    kind="channel_failure",
                    message=(
                        "embedding dimension mismatch: "
                        f"expected {expected_dimension}, got {result.dimension}"
                    ),
                    retryable=False,
                ),
            )

        if len(result.vectors) != 1:
            return VectorRetrievalOutcome(
                outcome="failure",
                failure=VectorRetrievalFailure(
                    kind="channel_failure",
                    message=f"embedding returned {len(result.vectors)} vectors, expected 1",
                    retryable=False,
                ),
            )

        query_vector = result.vectors[0]
        if len(query_vector) != expected_dimension:
            return VectorRetrievalOutcome(
                outcome="failure",
                failure=VectorRetrievalFailure(
                    kind="channel_failure",
                    message=(
                        f"embedding vector length mismatch: expected {expected_dimension}, "
                        f"got {len(query_vector)}"
                    ),
                    retryable=False,
                ),
            )

        return await self._vector_service.search(
            VectorRetrievalQuery(
                user_id=user_id,
                query_vector=query_vector,
                memory_types=memory_types,
                include_conflicted=include_conflicted,
                include_history=include_history,
            ),
        )

    def _validate_and_prepare(
        self,
        query: HybridRetrievalQuery,
    ) -> tuple[str, _RetrievalFilterFields]:
        user_id = query.user_id.strip()
        if not user_id:
            raise ValueError("user_id must not be empty")

        normalized_query = normalize_retrieval_query(query.query)
        if not normalized_query:
            raise ValueError("query must not be empty after normalization")

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

        filter_fields = _RetrievalFilterFields(
            user_id=user_id,
            memory_types=memory_types,
            include_conflicted=query.include_conflicted,
            include_history=query.include_history,
        )
        return normalized_query, filter_fields


def create_hybrid_retrieval_service(
    elasticsearch: AsyncElasticsearch,
    http_client: httpx.AsyncClient,
    *,
    settings: Settings,
) -> HybridRetrievalService:
    bm25_service = create_bm25_retrieval_service(elasticsearch, settings=settings)
    vector_service = create_vector_retrieval_service(elasticsearch, settings=settings)
    embedding_client = create_embedding_client(settings, http_client)
    return HybridRetrievalService(
        bm25_service,
        vector_service,
        embedding_client,
        settings=settings,
    )
