"""Shared Redis+Mongo integration fixtures backed by compose_stack."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import redis
import redis.asyncio as aioredis
from pymongo import AsyncMongoClient
from tests.integration.support.compose_stack import (
    module_services,
    mongo_uri_from_container,
    redis_uri_from_container,
    require_docker_or_skip,
    skip_on_startup_error,
)

from memory_system.infrastructure.mongodb.context_archive_repository import (
    CONTEXT_ARCHIVE_COLLECTION,
)


@pytest.fixture(scope="module")
def redis_mongo_stack() -> Iterator[tuple[str, str]]:
    require_docker_or_skip()
    try:
        with module_services(("redis", "mongodb"), migrate=True):
            yield (
                redis_uri_from_container(),
                mongo_uri_from_container(),
            )
    except (AssertionError, TimeoutError) as exc:
        skip_on_startup_error(str(exc))


@pytest.fixture
async def async_redis(redis_mongo_stack: tuple[str, str]) -> AsyncIterator[aioredis.Redis]:
    client = aioredis.from_url(redis_mongo_stack[0], decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def sync_redis(redis_mongo_stack: tuple[str, str]) -> Iterator[redis.Redis]:
    client = redis.from_url(redis_mongo_stack[0], decode_responses=True)
    yield client
    client.close()


@pytest.fixture
async def mongo_client(redis_mongo_stack: tuple[str, str]) -> AsyncIterator[AsyncMongoClient[Any]]:
    client: AsyncMongoClient[Any] = AsyncMongoClient(redis_mongo_stack[1])
    try:
        await client.admin.command("ping")
        db = client.get_default_database()
        if db is not None:
            await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
        yield client
        if db is not None:
            await db[CONTEXT_ARCHIVE_COLLECTION].delete_many({})
    finally:
        await client.close()
