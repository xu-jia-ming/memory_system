"""Shared Redis integration fixtures backed by compose_stack."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import redis
import redis.asyncio as aioredis
from tests.integration.support.compose_stack import (
    module_services,
    redis_uri_from_container,
    require_docker_or_skip,
    skip_on_startup_error,
)


@pytest.fixture(scope="module")
def integration_redis_uri() -> Iterator[str]:
    require_docker_or_skip()
    try:
        with module_services(("redis",), migrate=False):
            yield redis_uri_from_container()
    except (AssertionError, TimeoutError) as exc:
        skip_on_startup_error(str(exc))


@pytest.fixture
def async_redis_client(integration_redis_uri: str) -> Iterator[aioredis.Redis]:
    client = aioredis.from_url(integration_redis_uri, decode_responses=True)
    yield client


@pytest.fixture
def redis_client(integration_redis_uri: str) -> Iterator[redis.Redis]:
    client = redis.from_url(integration_redis_uri, decode_responses=True)
    yield client
    client.close()


# Aliases used by legacy integration modules.
test_redis = integration_redis_uri
