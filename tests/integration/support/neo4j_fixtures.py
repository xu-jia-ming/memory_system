"""Shared Neo4j integration fixtures backed by compose_stack."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase
from tests.integration.support.compose_stack import (
    elasticsearch_url_from_container,
    module_services,
    mongo_uri_from_container,
    neo4j_uri_from_container,
    require_docker_or_skip,
    skip_on_startup_error,
)


async def _purge_neo4j(uri: str) -> None:
    driver = AsyncGraphDatabase.driver(uri)
    try:
        async with driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
    finally:
        await driver.close()


@pytest.fixture(scope="module")
def integration_neo4j_uri() -> Iterator[str]:
    require_docker_or_skip()
    try:
        with module_services(("neo4j",), migrate=True):
            uri = neo4j_uri_from_container()
            asyncio.run(_purge_neo4j(uri))
            yield uri
    except (AssertionError, TimeoutError) as exc:
        skip_on_startup_error(str(exc))


@pytest.fixture
async def integration_neo4j_driver(
    integration_neo4j_uri: str,
) -> AsyncIterator[AsyncDriver]:
    driver = AsyncGraphDatabase.driver(integration_neo4j_uri)
    try:
        await driver.verify_connectivity()
        async with driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
    except Exception as exc:
        await driver.close()
        pytest.fail(f"Neo4j ping failed: {exc}")
    try:
        yield driver
    finally:
        async with driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
        await driver.close()


@pytest.fixture(scope="module")
def integration_mongo_neo4j_es_uris() -> Iterator[tuple[str, str, str]]:
    require_docker_or_skip()
    try:
        with module_services(("mongodb", "neo4j", "elasticsearch"), migrate=True):
            yield (
                mongo_uri_from_container(),
                neo4j_uri_from_container(),
                elasticsearch_url_from_container(),
            )
    except (AssertionError, TimeoutError) as exc:
        skip_on_startup_error(str(exc))


# Aliases used by legacy integration modules.
test_neo4j_uri = integration_neo4j_uri
neo4j_driver = integration_neo4j_driver
test_infra = integration_mongo_neo4j_es_uris
