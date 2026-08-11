"""Application runtime state and infrastructure client lifecycle."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import redis.asyncio as redis
from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from elasticsearch import AsyncElasticsearch
from neo4j import AsyncDriver, AsyncGraphDatabase
from pymongo import AsyncMongoClient

from memory_system.settings.models import Settings

_es_mapping_mod = importlib.import_module("scripts.migrations.003_elasticsearch_memory_v1")
assert_mapping_compatible: Any = _es_mapping_mod.assert_mapping_compatible

REQUIRED_MIGRATION_IDS: tuple[str, ...] = (
    "001_initial_mongodb",
    "002_initial_neo4j",
    "003_elasticsearch_memory_v1",
    "004_initial_kafka_topics",
)

BLOCKING_READINESS_CHECKS: tuple[str, ...] = (
    "redis",
    "mongodb",
    "neo4j",
    "elasticsearch",
    "kafka_producer",
    "migrations",
)


@dataclass
class AppState:
    settings: Settings
    redis: redis.Redis
    mongodb: AsyncMongoClient[Any]
    neo4j: AsyncDriver
    elasticsearch: AsyncElasticsearch
    http_client: httpx.AsyncClient
    kafka_producer: AIOKafkaProducer
    kafka_producer_ready: bool = False


def _mongodb_database_name(uri: str) -> str:
    parsed = urlparse(uri)
    path = parsed.path.lstrip("/")
    if not path:
        raise ValueError("MongoDB URI must include a database name")
    return path.split("/", 1)[0]


async def create_app_state(settings: Settings) -> AppState:
    redis_client = redis.from_url(
        settings.redis.uri.get_secret_value(),
        socket_connect_timeout=settings.redis.socket_connect_timeout_seconds,
        socket_timeout=settings.redis.socket_timeout_seconds,
        max_connections=settings.redis.max_connections,
        decode_responses=True,
    )
    mongodb_client: AsyncMongoClient[Any] = AsyncMongoClient(
        settings.mongodb.uri.get_secret_value(),
        serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
        connectTimeoutMS=settings.mongodb.connect_timeout_ms,
        maxPoolSize=settings.mongodb.max_pool_size,
    )
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j.uri.get_secret_value(),
        connection_timeout=settings.neo4j.connection_timeout_seconds,
        connection_acquisition_timeout=settings.neo4j.connection_acquisition_timeout_seconds,
        max_connection_pool_size=settings.neo4j.max_connection_pool_size,
    )
    elasticsearch_client = AsyncElasticsearch(
        hosts=[settings.elasticsearch.url],
        request_timeout=settings.elasticsearch.request_timeout_seconds,
        max_retries=settings.elasticsearch.max_retries,
        retry_on_timeout=settings.elasticsearch.retry_on_timeout,
    )
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=settings.http_client.connect_timeout_seconds,
            read=settings.http_client.read_timeout_seconds,
            write=settings.http_client.write_timeout_seconds,
            pool=settings.http_client.pool_timeout_seconds,
        ),
        limits=httpx.Limits(
            max_connections=settings.http_client.max_connections,
            max_keepalive_connections=settings.http_client.max_keepalive_connections,
        ),
    )
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka.bootstrap_servers,
        acks=settings.kafka_producer.acks,
        enable_idempotence=settings.kafka_producer.enable_idempotence,
        compression_type=settings.kafka_producer.compression_type,
        request_timeout_ms=settings.kafka_producer.request_timeout_ms,
        max_batch_size=settings.kafka_producer.max_batch_size,
        linger_ms=settings.kafka_producer.linger_ms,
    )

    await redis_client.ping()
    await mongodb_client.admin.command("ping")
    async with neo4j_driver.session() as session:
        await session.run("RETURN 1")
    await elasticsearch_client.info()
    await kafka_producer.start()

    kafka_client = kafka_producer.client
    if kafka_client is None:
        kafka_ready = False  # fail-closed
    elif hasattr(kafka_client, "bootstrap_connected"):
        kafka_ready = kafka_client.bootstrap_connected()
    else:
        # aiokafka >=0.13 removed bootstrap_connected; start() success is sufficient.
        kafka_ready = True

    return AppState(
        settings=settings,
        redis=redis_client,
        mongodb=mongodb_client,
        neo4j=neo4j_driver,
        elasticsearch=elasticsearch_client,
        http_client=http_client,
        kafka_producer=kafka_producer,
        kafka_producer_ready=kafka_ready,
    )


async def shutdown_app_state(state: AppState) -> None:
    await state.kafka_producer.stop()
    await state.elasticsearch.close()
    await state.neo4j.close()
    await state.mongodb.close()
    await state.redis.aclose()
    await state.http_client.aclose()


async def check_redis(state: AppState) -> str:
    try:
        if await state.redis.ping():
            return "ready"
    except Exception:
        return "not_ready"
    return "not_ready"


async def check_mongodb(state: AppState) -> str:
    try:
        await state.mongodb.admin.command("ping")
        return "ready"
    except Exception:
        return "not_ready"


async def check_neo4j(state: AppState) -> str:
    try:
        async with state.neo4j.session() as session:
            await session.run("RETURN 1")
        return "ready"
    except Exception:
        return "not_ready"


async def check_elasticsearch(state: AppState) -> str:
    try:
        info = await state.elasticsearch.info()
        version = info.get("version", {}).get("number")
        expected_version = state.settings.memory_retrieval.elasticsearch_version
        if version != expected_version:
            return "not_ready"

        alias_name = state.settings.memory_retrieval.index_name
        alias_exists = await state.elasticsearch.indices.exists_alias(name=alias_name)
        if not alias_exists:
            return "not_ready"

        alias_info = await state.elasticsearch.indices.get_alias(name=alias_name)
        index_name = next(iter(alias_info.keys()))
        mapping_response = await state.elasticsearch.indices.get_mapping(index=index_name)
        index_mapping = mapping_response.get(index_name, {}).get("mappings", {})
        assert_mapping_compatible(index_mapping)
        return "ready"
    except Exception:
        return "not_ready"


async def check_kafka_producer(state: AppState) -> str:
    if state.kafka_producer_ready and not state.kafka_producer._closed:  # noqa: SLF001
        return "ready"
    return "not_ready"


async def check_migrations(state: AppState) -> str:
    try:
        db_name = _mongodb_database_name(state.settings.mongodb.uri.get_secret_value())
        collection = state.mongodb[db_name]["infra_schema_migrations"]
        for migration_id in REQUIRED_MIGRATION_IDS:
            doc = await collection.find_one({"migration_id": migration_id})
            if doc is None:
                return "not_ready"
        return "ready"
    except Exception:
        return "not_ready"


async def check_embedding(state: AppState) -> str:
    try:
        base_url = state.settings.embedding.base_url.rstrip("/")
        response = await state.http_client.get(
            f"{base_url}/health",
            timeout=state.settings.embedding_http_client.read_timeout_seconds,
        )
        if response.status_code == 200:
            return "ready"
    except Exception:
        return "not_ready"
    return "not_ready"


async def collect_readiness_checks(state: AppState) -> dict[str, str]:
    return {
        "redis": await check_redis(state),
        "mongodb": await check_mongodb(state),
        "neo4j": await check_neo4j(state),
        "elasticsearch": await check_elasticsearch(state),
        "kafka_producer": await check_kafka_producer(state),
        "migrations": await check_migrations(state),
        "embedding": await check_embedding(state),
    }


def aggregate_readiness_status(checks: dict[str, str]) -> str:
    blocking_not_ready = any(checks[name] == "not_ready" for name in BLOCKING_READINESS_CHECKS)
    return "not_ready" if blocking_not_ready else "ready"
