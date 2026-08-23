"""RET-005 HTTP retrieval orchestration: hybrid recall, scoring, stats, degradation."""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
import structlog
from elasticsearch import AsyncElasticsearch
from neo4j import AsyncDriver

from memory_system.domain.models.authoritative_recall import (
    AuthoritativeRecallOutcome,
    AuthoritativeRecallQuery,
)
from memory_system.domain.models.bm25_retrieval import Bm25RetrievalOutcome, Bm25RetrievalQuery
from memory_system.domain.models.hybrid_retrieval import HybridRetrievalOutcome
from memory_system.domain.models.retrieval_scoring import (
    RetrievalScoringOutcome,
    RetrievalScoringQuery,
)
from memory_system.domain.models.vector_retrieval import (
    VectorRetrievalFailure,
    VectorRetrievalOutcome,
    VectorRetrievalQuery,
)
from memory_system.domain.services.authoritative_recall_service import (
    create_authoritative_recall_service,
)
from memory_system.domain.services.bm25_retrieval_service import (
    create_bm25_retrieval_service,
)
from memory_system.domain.services.retrieval_query_normalizer import normalize_retrieval_query
from memory_system.domain.services.retrieval_response_mapper import (
    MappedRetrievalMemoryItem,
    MissingSubjectEntityError,
    map_scored_memories_to_response_items,
)
from memory_system.domain.services.retrieval_scoring_service import (
    create_retrieval_scoring_service,
)
from memory_system.domain.services.retrieval_warning_mapper import (
    WarningEntry,
    collect_and_order_warnings,
    warning_from_bm25,
    warning_from_vector,
    warnings_from_internal,
)
from memory_system.domain.services.rrf_fusion import fuse_rrf
from memory_system.domain.services.vector_retrieval_service import (
    create_vector_retrieval_service,
)
from memory_system.infrastructure.embedding.errors import EmbeddingServiceError
from memory_system.infrastructure.embedding.factory import create_embedding_client
from memory_system.infrastructure.embedding.types import EmbeddingClient
from memory_system.infrastructure.neo4j.retrieval_statistics_repository import (
    RetrievalStatisticsRepository,
    RetrievalStatisticsWriteError,
)
from memory_system.infrastructure.tei.tei_tokenize_client import TokenizeServiceError
from memory_system.infrastructure.tokenize.factory import create_tokenize_client
from memory_system.observability.metrics import record_retrieval
from memory_system.settings.models import Settings

_logger = structlog.get_logger(__name__)

VALID_MEMORY_TYPES = frozenset({"fact", "preference", "event", "profile"})
_USER_ID_PATTERN = re.compile(r"^\S+$")
_MAX_QUERY_LENGTH = 2000


class RetrievalApiValidationError(Exception):
    """Business validation failure mapped to HTTP 400."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class RetrievalApiFatalError(Exception):
    """Fatal retrieval failure mapped to HTTP 503."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class RetrievalApiInput:
    user_id: str
    query: str
    memory_types: list[str] | None
    top_k: int
    include_conflicted: bool
    include_history: bool
    graph_expand: bool


@dataclass(frozen=True)
class RetrievalApiSuccess:
    retrieval_mode: Literal["hybrid", "bm25_only", "vector_only", "none"]
    warnings: list[str]
    memories: list[MappedRetrievalMemoryItem]


class Bm25RetrievalSearchPort(Protocol):
    async def search(self, query: Bm25RetrievalQuery) -> Bm25RetrievalOutcome: ...


class VectorRetrievalSearchPort(Protocol):
    async def search(self, query: VectorRetrievalQuery) -> VectorRetrievalOutcome: ...


class TokenizeCountPort(Protocol):
    async def count_tokens(self, text: str) -> int: ...


class AuthoritativeRecallPort(Protocol):
    async def recall(self, query: AuthoritativeRecallQuery) -> AuthoritativeRecallOutcome: ...


class RetrievalScoringPort(Protocol):
    async def score(self, query: RetrievalScoringQuery) -> RetrievalScoringOutcome: ...


class RetrievalStatisticsPort(Protocol):
    async def increment_retrieval_stats(
        self,
        *,
        user_id: str,
        memory_ids: list[str],
        current_time: int,
    ) -> None: ...


class RetrievalApiService:
    """HTTP retrieval orchestration owner (§4)."""

    def __init__(
        self,
        bm25_service: Bm25RetrievalSearchPort,
        vector_service: VectorRetrievalSearchPort,
        embedding_client: EmbeddingClient,
        tokenize_client: TokenizeCountPort,
        authoritative_service: AuthoritativeRecallPort,
        scoring_service: RetrievalScoringPort,
        statistics_repository: RetrievalStatisticsPort,
        *,
        settings: Settings,
    ) -> None:
        self._bm25_service = bm25_service
        self._vector_service = vector_service
        self._embedding_client = embedding_client
        self._tokenize_client = tokenize_client
        self._authoritative_service = authoritative_service
        self._scoring_service = scoring_service
        self._statistics_repository = statistics_repository
        self._settings = settings

    async def retrieve(
        self,
        input_data: RetrievalApiInput,
        *,
        deadline: float,
    ) -> RetrievalApiSuccess:
        loop = asyncio.get_event_loop()
        started = time.perf_counter()
        metric_mode_holder = {"mode": "hybrid"}
        try:
            return await self._retrieve_impl(
                input_data,
                deadline=deadline,
                loop=loop,
                started=started,
                metric_mode_holder=metric_mode_holder,
            )
        except RetrievalApiFatalError:
            record_retrieval(
                mode=metric_mode_holder["mode"],
                status="error",
                duration_seconds=time.perf_counter() - started,
            )
            raise

    async def _retrieve_impl(
        self,
        input_data: RetrievalApiInput,
        *,
        deadline: float,
        loop: asyncio.AbstractEventLoop,
        started: float,
        metric_mode_holder: dict[str, str],
    ) -> RetrievalApiSuccess:
        current_time = int(time.time())
        user_id, normalized_query, memory_types = validate_retrieval_input(input_data)
        query_hash = hashlib.sha256(normalized_query.encode()).hexdigest()

        warning_entries: list[WarningEntry] = []

        self._ensure_before_deadline(deadline, loop)
        hybrid_outcome, hybrid_warnings = await self._run_hybrid_recall(
            user_id=user_id,
            normalized_query=normalized_query,
            memory_types=memory_types,
            include_conflicted=input_data.include_conflicted,
            include_history=input_data.include_history,
            deadline=deadline,
            loop=loop,
            query_hash=query_hash,
        )
        warning_entries.extend(hybrid_warnings)

        if hybrid_outcome.outcome == "failure":
            raise RetrievalApiFatalError(
                "retrieval_unavailable",
                "Both retrieval channels are unavailable",
            )
        hybrid_success = hybrid_outcome.success
        if hybrid_success is None:
            raise RetrievalApiFatalError(
                "internal_error",
                "Hybrid retrieval returned success without payload",
            )

        self._ensure_before_deadline(deadline, loop)
        auth_outcome = await self._await_with_deadline(
            self._authoritative_service.recall(
                AuthoritativeRecallQuery(
                    hybrid_success=hybrid_success,
                    memory_types=memory_types,
                    include_conflicted=input_data.include_conflicted,
                    include_history=input_data.include_history,
                    graph_expand=input_data.graph_expand,
                    normalized_query=normalized_query,
                ),
            ),
            deadline=deadline,
            loop=loop,
        )
        if auth_outcome.outcome == "failure":
            _logger.error(
                "retrieval_authoritative_failure",
                user_id=user_id,
                query_hash=query_hash,
                stage="authoritative",
                error_code="graph_load_failed",
            )
            raise RetrievalApiFatalError(
                "graph_load_failed",
                "Failed to load authoritative memory graph",
            )
        auth_success = auth_outcome.success
        if auth_success is None:
            raise RetrievalApiFatalError(
                "internal_error",
                "Authoritative recall returned success without payload",
            )
        warning_entries.extend(warnings_from_internal(auth_success.warnings))

        self._ensure_before_deadline(deadline, loop)
        scoring_outcome = await self._await_with_deadline(
            self._scoring_service.score(
                RetrievalScoringQuery(
                    authoritative_success=auth_success,
                    top_k=input_data.top_k,
                    current_time=current_time,
                ),
            ),
            deadline=deadline,
            loop=loop,
        )
        if scoring_outcome.outcome == "failure":
            failure = scoring_outcome.failure
            code = "graph_load_failed"
            if failure is not None and failure.kind == "neo4j_read_failure":
                code = "graph_load_failed"
            _logger.error(
                "retrieval_scoring_failure",
                user_id=user_id,
                query_hash=query_hash,
                stage="scoring",
                error_code=code,
            )
            raise RetrievalApiFatalError(
                code,
                "Failed to load evidence for retrieval scoring",
            )
        scoring_success = scoring_outcome.success
        if scoring_success is None:
            raise RetrievalApiFatalError(
                "internal_error",
                "Scoring returned success without payload",
            )
        warning_entries.extend(warnings_from_internal(scoring_success.warnings))

        try:
            memories = map_scored_memories_to_response_items(scoring_success.scored_memories)
        except MissingSubjectEntityError as exc:
            _logger.error(
                "retrieval_response_mapping_failure",
                user_id=user_id,
                query_hash=query_hash,
                stage="dto",
                error_code="graph_load_failed",
            )
            raise RetrievalApiFatalError(
                "graph_load_failed",
                "Memory graph data incomplete for response",
            ) from exc

        memory_ids = list(dict.fromkeys(item.memory_id for item in memories))

        if not self._has_remaining_time(deadline, loop):
            warning_entries.append(WarningEntry("retrieval_timeout_degraded"))
            metric_mode_holder["mode"] = scoring_success.retrieval_mode
            record_retrieval(
                mode=scoring_success.retrieval_mode,
                status="degraded",
                duration_seconds=time.perf_counter() - started,
            )
            return RetrievalApiSuccess(
                retrieval_mode=scoring_success.retrieval_mode,
                warnings=collect_and_order_warnings(warning_entries),
                memories=memories,
            )

        if memory_ids:
            if not self._has_remaining_time(deadline, loop):
                warning_entries.append(WarningEntry("retrieval_timeout_degraded"))
            else:
                try:
                    await self._await_with_deadline(
                        self._statistics_repository.increment_retrieval_stats(
                            user_id=user_id,
                            memory_ids=memory_ids,
                            current_time=current_time,
                        ),
                        deadline=deadline,
                        loop=loop,
                    )
                except (RetrievalStatisticsWriteError, TimeoutError):
                    _logger.warning(
                        "retrieval_stat_update_failed",
                        user_id=user_id,
                        query_hash=query_hash,
                        stage="stats",
                        error_code="retrieval_stat_update_failed",
                    )
                    warning_entries.append(WarningEntry("retrieval_stat_update_failed"))
                except RetrievalApiFatalError as exc:
                    if exc.code == "retrieval_timeout":
                        warning_entries.append(WarningEntry("retrieval_timeout_degraded"))
                    else:
                        raise

        metric_mode_holder["mode"] = scoring_success.retrieval_mode
        status = (
            "degraded"
            if any(entry.kind == "retrieval_timeout_degraded" for entry in warning_entries)
            else "success"
        )
        record_retrieval(
            mode=scoring_success.retrieval_mode,
            status=status,
            duration_seconds=time.perf_counter() - started,
        )
        return RetrievalApiSuccess(
            retrieval_mode=scoring_success.retrieval_mode,
            warnings=collect_and_order_warnings(warning_entries),
            memories=memories,
        )

    async def _run_hybrid_recall(
        self,
        *,
        user_id: str,
        normalized_query: str,
        memory_types: list[str] | None,
        include_conflicted: bool,
        include_history: bool,
        deadline: float,
        loop: asyncio.AbstractEventLoop,
        query_hash: str,
    ) -> tuple[HybridRetrievalOutcome, list[WarningEntry]]:
        bm25_task = asyncio.create_task(
            self._bm25_service.search(
                Bm25RetrievalQuery(
                    user_id=user_id,
                    query=normalized_query,
                    memory_types=memory_types,
                    include_conflicted=include_conflicted,
                    include_history=include_history,
                ),
            ),
        )
        vector_task = asyncio.create_task(
            self._embed_and_vector_search(
                user_id=user_id,
                normalized_query=normalized_query,
                memory_types=memory_types,
                include_conflicted=include_conflicted,
                include_history=include_history,
                deadline=deadline,
                loop=loop,
            ),
        )

        try:
            bm25_outcome, vector_result = await asyncio.gather(bm25_task, vector_task)
        except RetrievalApiFatalError:
            bm25_task.cancel()
            vector_task.cancel()
            raise
        except Exception:
            bm25_task.cancel()
            vector_task.cancel()
            raise

        if isinstance(vector_result, tuple):
            vector_outcome, vector_warnings = vector_result
        else:
            vector_outcome = vector_result
            vector_warnings = []

        warnings: list[WarningEntry] = list(vector_warnings)
        bm25_warning = warning_from_bm25(bm25_outcome)
        if bm25_warning is not None:
            warnings.append(bm25_warning)
        vector_warning = warning_from_vector(
            vector_outcome,
            embedding_failed=any(
                entry.kind == "embedding_failed" for entry in vector_warnings
            ),
        )
        if vector_warning is not None:
            warnings.append(vector_warning)

        retrieval_settings = self._settings.memory_retrieval
        hybrid = fuse_rrf(
            bm25_outcome,
            vector_outcome,
            rrf_k=retrieval_settings.rrf_k,
            fused_top_n=retrieval_settings.fused_top_n,
            user_id=user_id,
        )
        return hybrid, warnings

    async def _embed_and_vector_search(
        self,
        *,
        user_id: str,
        normalized_query: str,
        memory_types: list[str] | None,
        include_conflicted: bool,
        include_history: bool,
        deadline: float,
        loop: asyncio.AbstractEventLoop,
    ) -> tuple[VectorRetrievalOutcome, list[WarningEntry]]:
        warnings: list[WarningEntry] = []
        self._ensure_before_deadline(deadline, loop)

        try:
            token_count = await self._tokenize_client.count_tokens(normalized_query)
        except TokenizeServiceError as exc:
            _logger.warning(
                "retrieval_tokenize_failure",
                user_id=user_id,
                retryable=True,
            )
            warnings.append(WarningEntry("embedding_failed"))
            return (
                VectorRetrievalOutcome(
                    outcome="failure",
                    failure=VectorRetrievalFailure(
                        kind="channel_failure",
                        message=str(exc),
                        retryable=True,
                    ),
                ),
                warnings,
            )

        if token_count > 1024:
            warnings.append(WarningEntry("vector_skipped_query_too_long"))
            return (
                VectorRetrievalOutcome(
                    outcome="failure",
                    failure=VectorRetrievalFailure(
                        kind="skipped_query_too_long",
                        message="query exceeds embedding token limit",
                        retryable=False,
                    ),
                ),
                warnings,
            )

        if token_count == 0:
            raise RetrievalApiValidationError("invalid_request", "Query must not be empty")

        self._ensure_before_deadline(deadline, loop)
        embedding_timeout = float(self._settings.memory_retrieval.embedding_timeout_seconds)
        expected_dimension = self._settings.memory_retrieval.embedding_dimension

        try:
            result = await asyncio.wait_for(
                self._embedding_client.embed(texts=[normalized_query]),
                timeout=embedding_timeout,
            )
        except TimeoutError:
            warnings.append(WarningEntry("embedding_failed"))
            return (
                VectorRetrievalOutcome(
                    outcome="failure",
                    failure=VectorRetrievalFailure(
                        kind="channel_failure",
                        message="embedding timed out",
                        retryable=True,
                    ),
                ),
                warnings,
            )
        except EmbeddingServiceError as exc:
            retryable = exc.status_code is None or exc.status_code >= 500
            warnings.append(WarningEntry("embedding_failed"))
            return (
                VectorRetrievalOutcome(
                    outcome="failure",
                    failure=VectorRetrievalFailure(
                        kind="channel_failure",
                        message=str(exc),
                        retryable=retryable,
                    ),
                ),
                warnings,
            )

        if result.dimension != expected_dimension:
            warnings.append(WarningEntry("embedding_failed"))
            return (
                VectorRetrievalOutcome(
                    outcome="failure",
                    failure=VectorRetrievalFailure(
                        kind="channel_failure",
                        message=(
                            f"embedding dimension mismatch: expected {expected_dimension}, "
                            f"got {result.dimension}"
                        ),
                        retryable=False,
                    ),
                ),
                warnings,
            )

        if len(result.vectors) != 1:
            warnings.append(WarningEntry("embedding_failed"))
            return (
                VectorRetrievalOutcome(
                    outcome="failure",
                    failure=VectorRetrievalFailure(
                        kind="channel_failure",
                        message=f"embedding returned {len(result.vectors)} vectors, expected 1",
                        retryable=False,
                    ),
                ),
                warnings,
            )

        query_vector = result.vectors[0]
        if len(query_vector) != expected_dimension:
            warnings.append(WarningEntry("embedding_failed"))
            return (
                VectorRetrievalOutcome(
                    outcome="failure",
                    failure=VectorRetrievalFailure(
                        kind="channel_failure",
                        message=(
                            f"embedding vector length mismatch: expected {expected_dimension}, "
                            f"got {len(query_vector)}"
                        ),
                        retryable=False,
                    ),
                ),
                warnings,
            )

        vector_outcome = await self._await_with_deadline(
            self._vector_service.search(
                VectorRetrievalQuery(
                    user_id=user_id,
                    query_vector=query_vector,
                    memory_types=memory_types,
                    include_conflicted=include_conflicted,
                    include_history=include_history,
                ),
            ),
            deadline=deadline,
            loop=loop,
        )
        return vector_outcome, warnings

    def _ensure_before_deadline(
        self,
        deadline: float,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        if not self._has_remaining_time(deadline, loop):
            raise RetrievalApiFatalError(
                "retrieval_timeout",
                "Retrieval request timed out before response was complete",
            )

    async def _await_with_deadline(
        self,
        awaitable: Any,
        *,
        deadline: float,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        self._ensure_before_deadline(deadline, loop)
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise RetrievalApiFatalError(
                "retrieval_timeout",
                "Retrieval request timed out before response was complete",
            )
        try:
            return await asyncio.wait_for(awaitable, timeout=remaining)
        except TimeoutError as exc:
            raise RetrievalApiFatalError(
                "retrieval_timeout",
                "Retrieval request timed out before response was complete",
            ) from exc

    @staticmethod
    def _has_remaining_time(deadline: float, loop: asyncio.AbstractEventLoop) -> bool:
        return loop.time() < deadline


def validate_retrieval_input(
    input_data: RetrievalApiInput,
) -> tuple[str, str, list[str] | None]:
    user_id = input_data.user_id.strip()
    if not user_id or not _USER_ID_PATTERN.fullmatch(user_id):
        raise RetrievalApiValidationError("invalid_request", "user_id must be non-empty")

    if not input_data.query or not input_data.query.strip():
        raise RetrievalApiValidationError("invalid_request", "query must not be empty")

    normalized_query = normalize_retrieval_query(input_data.query)
    if not normalized_query:
        raise RetrievalApiValidationError(
            "invalid_request",
            "query must not be empty after normalization",
        )
    if len(normalized_query) > _MAX_QUERY_LENGTH:
        raise RetrievalApiValidationError(
            "query_too_long",
            f"query exceeds maximum length of {_MAX_QUERY_LENGTH} characters",
        )

    memory_types = input_data.memory_types
    if memory_types is not None:
        deduped = list(dict.fromkeys(memory_types))
        if deduped:
            invalid = [value for value in deduped if value not in VALID_MEMORY_TYPES]
            if invalid:
                raise RetrievalApiValidationError(
                    "invalid_memory_type",
                    "memory_types contains invalid values",
                )
            memory_types = deduped
        else:
            memory_types = None

    return user_id, normalized_query, memory_types


def validate_retrieval_top_k(top_k: int, settings: Settings) -> None:
    retrieval_settings = settings.memory_retrieval
    if top_k < 1 or top_k > retrieval_settings.max_top_k:
        raise RetrievalApiValidationError(
            "invalid_top_k",
            f"top_k must be between 1 and {retrieval_settings.max_top_k} inclusive",
        )


def resolve_top_k(request_top_k: int | None, settings: Settings) -> int:
    if request_top_k is None:
        return settings.memory_retrieval.default_top_k
    validate_retrieval_top_k(request_top_k, settings)
    return request_top_k


def create_retrieval_api_service(
    settings: Settings,
    bm25_service: Bm25RetrievalSearchPort,
    vector_service: VectorRetrievalSearchPort,
    embedding_client: EmbeddingClient,
    tokenize_client: TokenizeCountPort,
    authoritative_service: AuthoritativeRecallPort,
    scoring_service: RetrievalScoringPort,
    statistics_repository: RetrievalStatisticsPort,
) -> RetrievalApiService:
    return RetrievalApiService(
        bm25_service=bm25_service,
        vector_service=vector_service,
        embedding_client=embedding_client,
        tokenize_client=tokenize_client,
        authoritative_service=authoritative_service,
        scoring_service=scoring_service,
        statistics_repository=statistics_repository,
        settings=settings,
    )


def create_retrieval_api_service_from_app_state(
    *,
    elasticsearch: AsyncElasticsearch,
    neo4j_driver: AsyncDriver,
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> RetrievalApiService:
    bm25_service = create_bm25_retrieval_service(elasticsearch, settings=settings)
    vector_service = create_vector_retrieval_service(elasticsearch, settings=settings)
    embedding_client = create_embedding_client(settings, http_client)
    tokenize_client = create_tokenize_client(settings, http_client)
    authoritative_service = create_authoritative_recall_service(
        neo4j_driver=neo4j_driver,
        es_client=elasticsearch,
        settings=settings,
        http_client=http_client,
    )
    scoring_service = create_retrieval_scoring_service(
        neo4j_driver=neo4j_driver,
        settings=settings,
    )
    statistics_repository = RetrievalStatisticsRepository(
        neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )
    return create_retrieval_api_service(
        settings,
        bm25_service,
        vector_service,
        embedding_client,
        tokenize_client,
        authoritative_service,
        scoring_service,
        statistics_repository,
    )
