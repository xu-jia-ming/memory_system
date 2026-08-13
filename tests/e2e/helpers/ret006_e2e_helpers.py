"""Helpers for RET-006 retrieval E2E scenarios."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from elasticsearch import AsyncElasticsearch
from httpx import ASGITransport
from neo4j import AsyncDriver, AsyncGraphDatabase
from pymongo import AsyncMongoClient

from memory_system.api.app import create_app
from memory_system.domain.models.bm25_retrieval import (
    Bm25RetrievalFailure,
    Bm25RetrievalOutcome,
    Bm25RetrievalQuery,
)
from memory_system.domain.models.retrieval_index_sync import RetrievalIndexSyncOutcome
from memory_system.domain.models.retrieval_scoring import (
    RetrievalScoringOutcome,
    RetrievalScoringQuery,
)
from memory_system.domain.models.vector_retrieval import (
    VectorRetrievalFailure,
    VectorRetrievalOutcome,
    VectorRetrievalQuery,
)
from memory_system.domain.services.retrieval_api_service import (
    AuthoritativeRecallPort,
    RetrievalApiService,
    RetrievalScoringPort,
    RetrievalStatisticsPort,
    TokenizeCountPort,
    create_retrieval_api_service,
    create_retrieval_api_service_from_app_state,
)
from memory_system.domain.services.retrieval_api_service import (
    Bm25RetrievalSearchPort as Bm25RetrievalSearchPortProtocol,
)
from memory_system.domain.services.retrieval_api_service import (
    VectorRetrievalSearchPort as VectorRetrievalSearchPortProtocol,
)
from memory_system.domain.services.retrieval_index_sync_service import (
    create_retrieval_index_sync_service,
)
from memory_system.domain.services.retrieval_scoring_service import create_retrieval_scoring_service
from memory_system.infrastructure.elasticsearch.retrieval_index_write_repository import (
    RetrievalIndexWriteRepository,
)
from memory_system.infrastructure.embedding.errors import EmbeddingServiceError
from memory_system.infrastructure.embedding.types import EmbeddingClient, EmbeddingResult
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    MEMORY_EXTRACTION_TASK_COLLECTION,
)
from memory_system.infrastructure.neo4j.retrieval_statistics_repository import (
    RetrievalStatisticsRepository,
)
from memory_system.infrastructure.runtime import create_app_state, shutdown_app_state
from memory_system.infrastructure.tei.fake_tokenize_client import FakeTokenizeClient
from memory_system.settings import Settings, get_settings
from tests.e2e.conftest import COORDINATED_BUNDLE, InfraStack, _patch_kafka_resolution
from tests.e2e.helpers.stm_e2e_helpers import API_KEY, default_headers
from tests.support.fake_retrieval_index_embedding_client import FakeEmbeddingClient
from tests.support.ret002_es_fixtures import make_deterministic_embedding
from tests.support.ret006_e2e_fixtures import (
    MEMORY_A_PRIMARY,
    MEMORY_B_ISOLATION,
    RET006_KEYWORD,
    RET006_SEMANTIC_QUERY,
    USER_RET006_A,
    USER_RET006_B,
    build_ext007_sync_input,
    refresh_es_index,
    seed_ret006_aligned_es,
    seed_ret006_aligned_graph,
    seed_ret006_ext007_graph,
    seed_ret006_ext007_task,
)

RETRIEVAL_URL = "/api/v1/memory/retrieval"
EMBEDDING_DIMENSION = 1024
TIGHT_TIMEOUT_ENV = {
    "MEMORY_RETRIEVAL__RETRIEVAL_TOTAL_TIMEOUT_SECONDS": "2",
    "MEMORY_RETRIEVAL__EMBEDDING_TIMEOUT_SECONDS": "2",
    "MEMORY_RETRIEVAL__ELASTICSEARCH_TIMEOUT_SECONDS": "2",
    "MEMORY_RETRIEVAL__NEO4J_TIMEOUT_SECONDS": "2",
}
FATAL_TIMEOUT_ENV = {
    "MEMORY_RETRIEVAL__RETRIEVAL_TOTAL_TIMEOUT_SECONDS": "1",
    "MEMORY_RETRIEVAL__EMBEDDING_TIMEOUT_SECONDS": "1",
    "MEMORY_RETRIEVAL__ELASTICSEARCH_TIMEOUT_SECONDS": "1",
    "MEMORY_RETRIEVAL__NEO4J_TIMEOUT_SECONDS": "1",
}


@dataclass
class MemoryStats:
    retrieval_count: int
    last_retrieved_time: int | None


@dataclass
class Ret006ServiceOverrides:
    embedding_client: EmbeddingClient | None = None
    tokenize_client: TokenizeCountPort | None = None
    bm25_service: Bm25RetrievalSearchPortProtocol | None = None
    vector_service: VectorRetrievalSearchPortProtocol | None = None
    authoritative_service: AuthoritativeRecallPort | None = None
    scoring_service: RetrievalScoringPort | None = None
    statistics_repository: RetrievalStatisticsPort | None = None


@dataclass
class Ret006Runtime:
    settings: Settings
    neo4j_driver: AsyncDriver
    elasticsearch: AsyncElasticsearch
    mongo: AsyncMongoClient[Any] | None
    http_client: httpx.AsyncClient
    app_state: Any


class Ret006AlignedEmbeddingClient:
    """Deterministic query embeddings aligned with ret006 ES fixture keys."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.embed_calls: list[list[str]] = []
        self.dimension = EMBEDDING_DIMENSION

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self.embed_calls.append(list(texts))
        if self.fail:
            raise EmbeddingServiceError(
                code="provider_unavailable",
                provider="fake",
                status_code=503,
                trace_id=None,
                sanitized_message="embedding unavailable",
            )
        vectors = [make_deterministic_embedding(text) for text in texts]
        return EmbeddingResult(
            model="ret006-aligned-fake",
            dimension=self.dimension,
            vectors=vectors,
        )


class Bm25RetrievalSearchPort:
    """Stub BM25 port returning channel_failure for failure injection."""

    async def search(self, query: Bm25RetrievalQuery) -> Bm25RetrievalOutcome:
        del query
        return Bm25RetrievalOutcome(
            outcome="failure",
            failure=Bm25RetrievalFailure(message="injected bm25 channel failure", retryable=True),
        )


class VectorRetrievalSearchPort:
    """Stub Vector port returning channel_failure for failure injection."""

    async def search(self, query: VectorRetrievalQuery) -> VectorRetrievalOutcome:
        del query
        return VectorRetrievalOutcome(
            outcome="failure",
            failure=VectorRetrievalFailure(
                kind="channel_failure",
                message="injected vector channel failure",
                retryable=True,
            ),
        )


class SlowRetrievalScoringPort:
    """Wrap a real scoring port with an injected delay (E2E-5a)."""

    def __init__(self, inner: RetrievalScoringPort, *, delay_seconds: float) -> None:
        self._inner = inner
        self._delay_seconds = delay_seconds

    async def score(self, query: RetrievalScoringQuery) -> RetrievalScoringOutcome:
        await asyncio.sleep(self._delay_seconds)
        return await self._inner.score(query)


class SlowRetrievalStatisticsPort:
    """Wrap stats repository with delay to trigger retrieval_timeout_degraded (E2E-5b)."""

    def __init__(self, inner: RetrievalStatisticsPort, *, delay_seconds: float) -> None:
        self._inner = inner
        self._delay_seconds = delay_seconds

    async def increment_retrieval_stats(
        self,
        *,
        user_id: str,
        memory_ids: list[str],
        current_time: int,
    ) -> None:
        await asyncio.sleep(self._delay_seconds)
        await self._inner.increment_retrieval_stats(
            user_id=user_id,
            memory_ids=memory_ids,
            current_time=current_time,
        )


def _configure_ret006_env(
    monkeypatch: Any,
    infra_stack: InfraStack,
    *,
    extra_env: dict[str, str] | None = None,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("REDIS__URI", infra_stack.redis_url)
    monkeypatch.setenv("MONGODB__URI", infra_stack.mongo_url)
    monkeypatch.setenv("KAFKA__BOOTSTRAP_SERVERS", infra_stack.kafka_bootstrap)
    monkeypatch.setenv("NEO4J__URI", f"neo4j://{infra_stack.neo4j_ip}:7687")
    monkeypatch.setenv("ELASTICSEARCH__URL", infra_stack.elasticsearch_url)
    monkeypatch.setenv("MEMORY_API_KEY", API_KEY)
    monkeypatch.setenv("MEMORY_ADMIN_API_KEY", "dev-memory-admin-key-change-me")
    monkeypatch.setenv("LLM__BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM__API_KEY", "sk-example-replace-me")
    monkeypatch.setenv("LLM__COMPRESSION__MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM__EXTRACTION__MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("EMBEDDING__MODEL_ID", "BAAI/bge-m3")
    monkeypatch.setenv("EMBEDDING__BASE_URL", "http://embedding-service:80")
    monkeypatch.setenv("PROXY__HTTP_URL", "")
    monkeypatch.setenv("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    monkeypatch.setenv("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-example-replace-me")
    for key, value in COORDINATED_BUNDLE.items():
        monkeypatch.setenv(key, value)
    if extra_env:
        for key, value in extra_env.items():
            monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _build_patched_factory(
    overrides: Ret006ServiceOverrides,
) -> Callable[..., RetrievalApiService]:
    def factory(
        *,
        elasticsearch: AsyncElasticsearch,
        neo4j_driver: AsyncDriver,
        http_client: httpx.AsyncClient,
        settings: Settings,
    ) -> RetrievalApiService:
        default_service = create_retrieval_api_service_from_app_state(
            elasticsearch=elasticsearch,
            neo4j_driver=neo4j_driver,
            http_client=http_client,
            settings=settings,
        )
        statistics_repository = overrides.statistics_repository
        if statistics_repository is None:
            statistics_repository = RetrievalStatisticsRepository(
                neo4j_driver,
                neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
            )
        scoring_service = overrides.scoring_service
        if scoring_service is None:
            scoring_service = default_service._scoring_service  # noqa: SLF001
        return create_retrieval_api_service(
            settings,
            bm25_service=overrides.bm25_service or default_service._bm25_service,  # noqa: SLF001
            vector_service=overrides.vector_service or default_service._vector_service,  # noqa: SLF001
            embedding_client=overrides.embedding_client or default_service._embedding_client,  # noqa: SLF001
            tokenize_client=overrides.tokenize_client or default_service._tokenize_client,  # noqa: SLF001
            authoritative_service=(
                overrides.authoritative_service or default_service._authoritative_service  # noqa: SLF001
            ),
            scoring_service=scoring_service,
            statistics_repository=statistics_repository,
        )

    return factory


@asynccontextmanager
async def build_retrieval_client(
    infra_stack: InfraStack,
    monkeypatch: Any,
    *,
    embedding: EmbeddingClient | None = None,
    tokenize: TokenizeCountPort | None = None,
    service_overrides: Ret006ServiceOverrides | None = None,
    scoring_delay_seconds: float | None = None,
    stats_delay_seconds: float | None = None,
    extra_env: dict[str, str] | None = None,
    request_id: str | None = None,
) -> AsyncIterator[Ret006Runtime]:
    """Build in-process retrieval HTTP client with optional factory injection."""
    _configure_ret006_env(monkeypatch, infra_stack, extra_env=extra_env)
    overrides = service_overrides or Ret006ServiceOverrides()
    if embedding is not None:
        overrides.embedding_client = embedding
    if tokenize is not None:
        overrides.tokenize_client = tokenize

    settings = get_settings()
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j.uri.get_secret_value(),
        connection_timeout=settings.neo4j.connection_timeout_seconds,
        connection_acquisition_timeout=settings.neo4j.connection_acquisition_timeout_seconds,
        max_connection_pool_size=settings.neo4j.max_connection_pool_size,
    )
    if scoring_delay_seconds is not None:
        overrides.scoring_service = SlowRetrievalScoringPort(
            create_retrieval_scoring_service(
                neo4j_driver=neo4j_driver,
                settings=settings,
            ),
            delay_seconds=scoring_delay_seconds,
        )
    if stats_delay_seconds is not None:
        overrides.statistics_repository = SlowRetrievalStatisticsPort(
            RetrievalStatisticsRepository(
                neo4j_driver,
                neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
            ),
            delay_seconds=stats_delay_seconds,
        )
    elasticsearch = AsyncElasticsearch(
        hosts=[settings.elasticsearch.url],
        request_timeout=settings.elasticsearch.request_timeout_seconds,
        max_retries=settings.elasticsearch.max_retries,
        retry_on_timeout=settings.elasticsearch.retry_on_timeout,
    )
    mongo: AsyncMongoClient[Any] | None = AsyncMongoClient(infra_stack.mongo_url)

    monkeypatch.setattr(
        "memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state",
        _build_patched_factory(overrides),
    )

    with _patch_kafka_resolution(infra_stack.kafka_ip):
        app_state = await create_app_state(settings)
        app = create_app(
            settings=settings,
            app_state=app_state,
            llm_client=FakeLlmClient(mode="timeout"),
        )
        app.state.app_state = app_state
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            timeout=60.0,
            headers=default_headers(request_id=request_id),
        ) as http_client:
            try:
                yield Ret006Runtime(
                    settings=settings,
                    neo4j_driver=neo4j_driver,
                    elasticsearch=elasticsearch,
                    mongo=mongo,
                    http_client=http_client,
                    app_state=app_state,
                )
            finally:
                await shutdown_app_state(app_state)
                if mongo is not None:
                    await mongo.close()
                await elasticsearch.close()
                await neo4j_driver.close()


async def read_memory_stats(
    driver: AsyncDriver,
    *,
    user_id: str,
    memory_id: str,
) -> MemoryStats | None:
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:Memory {memory_id: $memory_id, user_id: $user_id})
            RETURN m.retrieval_count AS retrieval_count,
                   m.last_retrieved_time AS last_retrieved_time
            """,
            memory_id=memory_id,
            user_id=user_id,
        )
        record = await result.single()
        if record is None:
            return None
        last_retrieved = record["last_retrieved_time"]
        return MemoryStats(
            retrieval_count=int(record["retrieval_count"]),
            last_retrieved_time=int(last_retrieved) if last_retrieved is not None else None,
        )


async def seed_ret006_aligned(
    runtime: Ret006Runtime,
) -> dict[str, str]:
    write_repo = RetrievalIndexWriteRepository(runtime.elasticsearch)
    index_alias = runtime.settings.memory_retrieval.index_name
    memory_ids = await seed_ret006_aligned_graph(runtime.neo4j_driver)
    await seed_ret006_aligned_es(write_repo, index_alias)
    await refresh_es_index(runtime.elasticsearch, index_alias)
    return memory_ids


async def seed_ret006_ext007_synced(
    runtime: Ret006Runtime,
) -> dict[str, str]:
    user_id = "user_ret006_ext007"
    memory_id = "mem-ret006-ext007"
    archive_id = str(uuid.uuid4())
    content = f"{RET006_KEYWORD} synced memory via ext007"
    core_search_text = await seed_ret006_ext007_graph(
        runtime.neo4j_driver,
        user_id=user_id,
        memory_id=memory_id,
        content=content,
    )
    assert runtime.mongo is not None
    await seed_ret006_ext007_task(
        runtime.mongo,
        user_id=user_id,
        archive_id=archive_id,
    )
    sync_service = create_retrieval_index_sync_service(
        runtime.neo4j_driver,
        runtime.elasticsearch,
        tokenize_client=FakeTokenizeClient(token_count=10),
        embedding_client=FakeEmbeddingClient(),
        settings=runtime.settings,
        server_time_provider=lambda: int(time.time()) + 10,
    )
    outcome = await sync_service.sync(
        build_ext007_sync_input(
            user_id=user_id,
            archive_id=archive_id,
            memory_id=memory_id,
            core_search_text=core_search_text,
        ),
        mongodb=runtime.mongo,
    )
    assert isinstance(outcome, RetrievalIndexSyncOutcome)
    assert outcome.outcome.value == "success"
    await refresh_es_index(runtime.elasticsearch, runtime.settings.memory_retrieval.index_name)
    return {
        "user_id": user_id,
        "memory_id": memory_id,
        "archive_id": archive_id,
        "content": content,
    }


async def cleanup_ret006_data(
    runtime: Ret006Runtime,
    *,
    user_ids: list[str],
    archive_ids: list[str] | None = None,
) -> None:
    index_name = runtime.settings.memory_retrieval.index_name
    for user_id in user_ids:
        async with runtime.neo4j_driver.session() as session:
            await session.run(
                "MATCH (node {user_id: $user_id}) DETACH DELETE node",
                user_id=user_id,
            )
        await runtime.elasticsearch.delete_by_query(
            index=index_name,
            query={"term": {"user_id": user_id}},
            conflicts="proceed",
            refresh=True,
        )
    if runtime.mongo is not None and archive_ids:
        database = runtime.mongo.get_default_database()
        if database is not None:
            for archive_id in archive_ids:
                await database[MEMORY_EXTRACTION_TASK_COLLECTION].delete_many(
                    {"archive_id": archive_id}
                )


async def post_retrieval(
    client: httpx.AsyncClient,
    *,
    user_id: str,
    query: str,
    top_k: int = 10,
    request_id: str | None = None,
) -> httpx.Response:
    headers = default_headers(request_id=request_id)
    return await client.post(
        RETRIEVAL_URL,
        headers=headers,
        json={
            "user_id": user_id,
            "query": query,
            "top_k": top_k,
        },
    )


def assert_retrieval_response_contract(payload: dict[str, Any]) -> None:
    assert payload["retrieval_mode"] in {"hybrid", "bm25_only", "vector_only", "none"}
    assert isinstance(payload.get("warnings", []), list)
    memories = payload["memories"]
    assert isinstance(memories, list)
    allowed_top_keys = {"retrieval_mode", "warnings", "memories"}
    assert set(payload.keys()).issubset(allowed_top_keys)
    for item in memories:
        assert "memory_id" in item
        assert "score" in item
        assert "final_score" not in item
        assert "retrieval_source" in item
        assert "evidence_count" in item
        assert "source_message_ids" in item


def build_slow_scoring_override(
    *,
    settings: Settings,
    neo4j_driver: AsyncDriver,
    delay_seconds: float,
) -> Ret006ServiceOverrides:
    scoring_service = create_retrieval_scoring_service(
        neo4j_driver=neo4j_driver,
        settings=settings,
    )
    return Ret006ServiceOverrides(
        scoring_service=SlowRetrievalScoringPort(
            scoring_service,
            delay_seconds=delay_seconds,
        ),
    )


def build_slow_stats_override(
    *,
    settings: Settings,
    neo4j_driver: AsyncDriver,
    delay_seconds: float,
) -> Ret006ServiceOverrides:
    stats_repo = RetrievalStatisticsRepository(
        neo4j_driver,
        neo4j_timeout_seconds=float(settings.memory_retrieval.neo4j_timeout_seconds),
    )
    return Ret006ServiceOverrides(
        statistics_repository=SlowRetrievalStatisticsPort(
            stats_repo,
            delay_seconds=delay_seconds,
        ),
    )


def build_channel_failure_overrides(
    *,
    bm25: bool = False,
    vector: bool = False,
) -> Ret006ServiceOverrides:
    return Ret006ServiceOverrides(
        bm25_service=Bm25RetrievalSearchPort() if bm25 else None,
        vector_service=VectorRetrievalSearchPort() if vector else None,
    )


__all__ = [
    "Bm25RetrievalSearchPort",
    "MEMORY_A_PRIMARY",
    "MEMORY_B_ISOLATION",
    "RET006_KEYWORD",
    "RET006_SEMANTIC_QUERY",
    "Ret006AlignedEmbeddingClient",
    "Ret006Runtime",
    "Ret006ServiceOverrides",
    "TIGHT_TIMEOUT_ENV",
    "USER_RET006_A",
    "USER_RET006_B",
    "VectorRetrievalSearchPort",
    "assert_retrieval_response_contract",
    "build_channel_failure_overrides",
    "build_retrieval_client",
    "build_slow_scoring_override",
    "build_slow_stats_override",
    "cleanup_ret006_data",
    "FATAL_TIMEOUT_ENV",
    "post_retrieval",
    "read_memory_stats",
    "seed_ret006_aligned",
    "seed_ret006_ext007_synced",
]
