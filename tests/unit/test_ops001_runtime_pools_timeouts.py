"""OPS-001 pool/timeout wiring audit tests (U1, U2, U10a–c, U11)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from memory_system.entrypoints import api, consolidation_worker, extraction_worker
from memory_system.infrastructure.runtime import create_app_state, shutdown_app_state
from memory_system.settings import Settings, get_settings

VALID_ENV: dict[str, str] = {
    "APP_ENV": "test",
    "REDIS__URI": "redis://redis:6379/0",
    "MONGODB__URI": "mongodb://mongodb:27017/memory_system",
    "KAFKA__BOOTSTRAP_SERVERS": "kafka:9092",
    "NEO4J__URI": "neo4j://neo4j:7687",
    "ELASTICSEARCH__URL": "http://elasticsearch:9200",
    "LLM__BASE_URL": "https://api.deepseek.com",
    "LLM__API_KEY": "sk-example-replace-me",
    "LLM__COMPRESSION__MODEL": "deepseek-v4-flash",
    "LLM__EXTRACTION__MODEL": "deepseek-v4-flash",
    "EMBEDDING__MODEL_ID": "BAAI/bge-m3",
    "EMBEDDING__BASE_URL": "http://embedding-service:80",
    "MEMORY_API_KEY": "dev-memory-api-key-change-me",
    "MEMORY_ADMIN_API_KEY": "dev-memory-admin-key-change-me",
    "EMBEDDING_EFFECTIVE_RUNTIME_MODE": "cpu",
    "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET": "4096",
    "SILICONFLOW_API_KEY": "sk-example-replace-me",
}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return get_settings()


@contextmanager
def _runtime_infra_patches() -> Iterator[dict[str, MagicMock]]:
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)

    mongo_client = MagicMock()
    mongo_client.admin.command = AsyncMock(return_value={"ok": 1})

    session = AsyncMock()
    session.run = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    neo4j_driver = MagicMock()
    neo4j_driver.session.return_value = session

    elasticsearch_client = MagicMock()
    elasticsearch_client.info = AsyncMock(return_value={})

    mock_producer = MagicMock()
    mock_producer.start = AsyncMock()
    mock_producer.client = MagicMock()

    captured: dict[str, MagicMock] = {
        "redis": redis_client,
        "mongo": mongo_client,
        "neo4j": neo4j_driver,
        "es": elasticsearch_client,
        "producer": mock_producer,
    }

    with (
        patch(
            "memory_system.infrastructure.runtime.redis.from_url",
            return_value=redis_client,
        ) as redis_from_url,
        patch(
            "memory_system.infrastructure.runtime.AsyncMongoClient",
            return_value=mongo_client,
        ) as mongo_ctor,
        patch(
            "memory_system.infrastructure.runtime.AsyncGraphDatabase.driver",
            return_value=neo4j_driver,
        ) as neo4j_ctor,
        patch(
            "memory_system.infrastructure.runtime.AsyncElasticsearch",
            return_value=elasticsearch_client,
        ) as es_ctor,
        patch("memory_system.infrastructure.runtime.httpx.AsyncClient") as http_ctor,
        patch(
            "memory_system.infrastructure.runtime.AIOKafkaProducer",
            return_value=mock_producer,
        ) as producer_ctor,
    ):
        captured["redis_from_url"] = redis_from_url
        captured["mongo_ctor"] = mongo_ctor
        captured["neo4j_ctor"] = neo4j_ctor
        captured["es_ctor"] = es_ctor
        captured["http_ctor"] = http_ctor
        captured["producer_ctor"] = producer_ctor
        yield captured


class TestU1ApiGracefulShutdown:
    def test_api_passes_uvicorn_timeout_from_settings(self, settings: Settings) -> None:
        with patch("memory_system.entrypoints.api.uvicorn.run") as uvicorn_run:
            api.main()
        assert uvicorn_run.call_args.kwargs["timeout_graceful_shutdown"] == (
            settings.shutdown.memory_api_timeout_seconds
        )


class TestU2ShutdownAppStateOrder:
    @pytest.mark.asyncio
    async def test_shutdown_app_state_closes_in_reverse_dependency_order(
        self,
        settings: Settings,
    ) -> None:
        order: list[str] = []

        state = MagicMock()
        state.settings = settings
        state.kafka_producer.stop = AsyncMock(side_effect=lambda: order.append("kafka"))
        state.elasticsearch.close = AsyncMock(side_effect=lambda: order.append("es"))
        state.neo4j.close = AsyncMock(side_effect=lambda: order.append("neo4j"))
        state.mongodb.close = AsyncMock(side_effect=lambda: order.append("mongo"))
        state.redis.aclose = AsyncMock(side_effect=lambda: order.append("redis"))
        state.http_client.aclose = AsyncMock(side_effect=lambda: order.append("httpx"))

        await shutdown_app_state(state)

        assert order == ["kafka", "es", "neo4j", "mongo", "redis", "httpx"]


class TestU10aRuntimePoolTimeoutWiring:
    @pytest.mark.asyncio
    async def test_create_app_state_wires_section_3_24_defaults(
        self,
        settings: Settings,
    ) -> None:
        with _runtime_infra_patches() as captured:
            await create_app_state(settings)

        captured["redis_from_url"].assert_called_once_with(
            settings.redis.uri.get_secret_value(),
            socket_connect_timeout=settings.redis.socket_connect_timeout_seconds,
            socket_timeout=settings.redis.socket_timeout_seconds,
            max_connections=settings.redis.max_connections,
            decode_responses=True,
        )
        captured["mongo_ctor"].assert_called_once_with(
            settings.mongodb.uri.get_secret_value(),
            serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
            connectTimeoutMS=settings.mongodb.connect_timeout_ms,
            maxPoolSize=settings.mongodb.max_pool_size,
        )
        captured["neo4j_ctor"].assert_called_once_with(
            settings.neo4j.uri.get_secret_value(),
            connection_timeout=settings.neo4j.connection_timeout_seconds,
            connection_acquisition_timeout=settings.neo4j.connection_acquisition_timeout_seconds,
            max_connection_pool_size=settings.neo4j.max_connection_pool_size,
        )
        captured["es_ctor"].assert_called_once_with(
            hosts=[settings.elasticsearch.url],
            request_timeout=settings.elasticsearch.request_timeout_seconds,
            max_retries=settings.elasticsearch.max_retries,
            retry_on_timeout=settings.elasticsearch.retry_on_timeout,
        )
        http_kwargs = captured["http_ctor"].call_args.kwargs
        assert http_kwargs["timeout"] == httpx.Timeout(
            connect=settings.http_client.connect_timeout_seconds,
            read=settings.http_client.read_timeout_seconds,
            write=settings.http_client.write_timeout_seconds,
            pool=settings.http_client.pool_timeout_seconds,
        )
        assert http_kwargs["limits"] == httpx.Limits(
            max_connections=settings.http_client.max_connections,
            max_keepalive_connections=settings.http_client.max_keepalive_connections,
        )
        captured["producer_ctor"].assert_called_once_with(
            bootstrap_servers=settings.kafka.bootstrap_servers,
            acks=settings.kafka_producer.acks,
            enable_idempotence=settings.kafka_producer.enable_idempotence,
            compression_type=settings.kafka_producer.compression_type,
            request_timeout_ms=settings.kafka_producer.request_timeout_ms,
            max_batch_size=settings.kafka_producer.max_batch_size,
            linger_ms=settings.kafka_producer.linger_ms,
        )


class TestU10bExtractionWorkerWiring:
    @pytest.mark.asyncio
    async def test_extraction_worker_client_ctor_kwargs(self, settings: Settings) -> None:
        mock_mongo = MagicMock()
        mock_mongo.admin.command = AsyncMock(return_value={"ok": 1})
        mock_neo4j = MagicMock()
        mock_session = MagicMock()
        mock_session.run = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_neo4j.session.return_value = mock_session
        mock_es = MagicMock()
        mock_es.info = AsyncMock(return_value={})
        mock_consumer = MagicMock()
        mock_consumer.start = AsyncMock()

        with (
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncMongoClient",
                return_value=mock_mongo,
            ) as mongo_ctor,
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncGraphDatabase.driver",
                return_value=mock_neo4j,
            ) as neo4j_ctor,
            patch(
                "memory_system.entrypoints.extraction_worker.AsyncElasticsearch",
                return_value=mock_es,
            ) as es_ctor,
            patch(
                "memory_system.entrypoints.extraction_worker.httpx.AsyncClient"
            ) as http_ctor,
            patch(
                "memory_system.entrypoints.extraction_worker.create_archive_created_consumer",
                return_value=mock_consumer,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.create_production_extraction_pipeline",
                return_value=MagicMock(),
            ),
            patch(
                "memory_system.entrypoints.extraction_worker.run_archive_created_consumer_loop",
                new_callable=AsyncMock,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker._close_worker_resources",
                new_callable=AsyncMock,
            ),
            patch(
                "memory_system.entrypoints.extraction_worker._install_stop_handlers",
                side_effect=lambda event, started: event.set(),
            ),
        ):
            await extraction_worker._run_worker(settings)

        mongo_ctor.assert_called_once_with(
            settings.mongodb.uri.get_secret_value(),
            serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
            connectTimeoutMS=settings.mongodb.connect_timeout_ms,
            maxPoolSize=settings.mongodb.max_pool_size,
        )
        neo4j_ctor.assert_called_once_with(
            settings.neo4j.uri.get_secret_value(),
            connection_timeout=settings.neo4j.connection_timeout_seconds,
            connection_acquisition_timeout=settings.neo4j.connection_acquisition_timeout_seconds,
            max_connection_pool_size=settings.neo4j.max_connection_pool_size,
        )
        es_ctor.assert_called_once_with(
            hosts=[settings.elasticsearch.url],
            request_timeout=settings.elasticsearch.request_timeout_seconds,
            max_retries=settings.elasticsearch.max_retries,
            retry_on_timeout=settings.elasticsearch.retry_on_timeout,
        )
        http_kwargs = http_ctor.call_args.kwargs
        assert http_kwargs["timeout"] == httpx.Timeout(
            connect=settings.http_client.connect_timeout_seconds,
            read=settings.http_client.read_timeout_seconds,
            write=settings.http_client.write_timeout_seconds,
            pool=settings.http_client.pool_timeout_seconds,
        )
        assert http_kwargs["limits"] == httpx.Limits(
            max_connections=settings.http_client.max_connections,
            max_keepalive_connections=settings.http_client.max_keepalive_connections,
        )


class TestU10cConsolidationWorkerWiring:
    @pytest.mark.asyncio
    async def test_consolidation_worker_neo4j_driver_kwargs(self, settings: Settings) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.run = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session.return_value = mock_session

        with (
            patch(
                "memory_system.entrypoints.consolidation_worker.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ) as neo4j_ctor,
            patch(
                "memory_system.entrypoints.consolidation_worker.create_consolidation_scheduler",
                return_value=None,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._close_neo4j",
                new_callable=AsyncMock,
            ),
            patch(
                "memory_system.entrypoints.consolidation_worker._install_stop_handlers",
                side_effect=lambda event, started: event.set(),
            ),
        ):
            await consolidation_worker._run_worker(settings)

        neo4j_ctor.assert_called_once_with(
            settings.neo4j.uri.get_secret_value(),
            connection_timeout=settings.neo4j.connection_timeout_seconds,
            connection_acquisition_timeout=settings.neo4j.connection_acquisition_timeout_seconds,
            max_connection_pool_size=settings.neo4j.max_connection_pool_size,
        )


class TestU11ElasticsearchRetries:
    @pytest.mark.asyncio
    async def test_create_app_state_passes_es_max_retries(self, settings: Settings) -> None:
        with _runtime_infra_patches() as captured:
            await create_app_state(settings)
        es_kwargs = captured["es_ctor"].call_args.kwargs
        assert es_kwargs["max_retries"] == 2
