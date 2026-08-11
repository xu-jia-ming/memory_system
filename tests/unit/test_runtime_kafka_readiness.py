"""Unit tests for kafka producer readiness in create_app_state (DEV-OPS-008 C1)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_system.infrastructure.runtime import AppState, check_kafka_producer, create_app_state
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
def _infra_patches(mock_producer: MagicMock) -> Iterator[None]:
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

    mock_producer.start = AsyncMock()

    with (
        patch(
            "memory_system.infrastructure.runtime.redis.from_url",
            return_value=redis_client,
        ),
        patch(
            "memory_system.infrastructure.runtime.AsyncMongoClient",
            return_value=mongo_client,
        ),
        patch(
            "memory_system.infrastructure.runtime.AsyncGraphDatabase.driver",
            return_value=neo4j_driver,
        ),
        patch(
            "memory_system.infrastructure.runtime.AsyncElasticsearch",
            return_value=elasticsearch_client,
        ),
        patch("memory_system.infrastructure.runtime.httpx.AsyncClient"),
        patch(
            "memory_system.infrastructure.runtime.AIOKafkaProducer",
            return_value=mock_producer,
        ),
    ):
        yield


async def _app_state_with_kafka_client(
    settings: Settings,
    *,
    client: object | None,
) -> AppState:
    mock_producer = MagicMock()
    mock_producer.client = client

    with _infra_patches(mock_producer):
        return await create_app_state(settings)


@pytest.mark.asyncio
async def test_c1_u1_no_bootstrap_connected_valid_client_start_success(
    settings: Settings,
) -> None:
    class ClientWithoutBootstrap:
        pass

    state = await _app_state_with_kafka_client(
        settings,
        client=ClientWithoutBootstrap(),
    )
    assert state.kafka_producer_ready is True


@pytest.mark.asyncio
async def test_c1_u2_bootstrap_connected_false(settings: Settings) -> None:
    class ClientWithBootstrap:
        def bootstrap_connected(self) -> bool:
            return False

    state = await _app_state_with_kafka_client(
        settings,
        client=ClientWithBootstrap(),
    )
    assert state.kafka_producer_ready is False


@pytest.mark.asyncio
async def test_c1_u3_bootstrap_connected_true(settings: Settings) -> None:
    class ClientWithBootstrap:
        def bootstrap_connected(self) -> bool:
            return True

    state = await _app_state_with_kafka_client(
        settings,
        client=ClientWithBootstrap(),
    )
    assert state.kafka_producer_ready is True


@pytest.mark.asyncio
async def test_c1_u5_client_none_fail_closed(settings: Settings) -> None:
    state = await _app_state_with_kafka_client(settings, client=None)
    assert state.kafka_producer_ready is False


@pytest.mark.asyncio
async def test_c1_u4_check_kafka_producer_closed_not_ready(settings: Settings) -> None:
    kafka_producer = MagicMock()
    kafka_producer._closed = True
    state = AppState(
        settings=settings,
        redis=MagicMock(),
        mongodb=MagicMock(),
        neo4j=MagicMock(),
        elasticsearch=MagicMock(),
        http_client=MagicMock(),
        kafka_producer=kafka_producer,
        kafka_producer_ready=True,
    )
    assert await check_kafka_producer(state) == "not_ready"
