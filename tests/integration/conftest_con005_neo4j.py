"""Shared Neo4j-only fixtures for CON-005 integration and E2E tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from neo4j import AsyncDriver
from tests.e2e.helpers.con005_e2e_helpers import build_production_run_service

from memory_system.domain.services.consolidation_run_service import ConsolidationRunService
from memory_system.settings import Settings, get_settings

pytest_plugins = ("tests.integration.support.neo4j_fixtures",)


@pytest.fixture
async def con005_neo4j_driver(integration_neo4j_driver: AsyncDriver) -> AsyncIterator[AsyncDriver]:
    yield integration_neo4j_driver


@pytest.fixture(autouse=True)
async def _clean_graph(con005_neo4j_driver: AsyncDriver) -> AsyncIterator[None]:
    async with con005_neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield
    async with con005_neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")


@pytest.fixture
def con005_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("NEO4J__URI", "neo4j://127.0.0.1:7687")
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def con005_run_service(
    con005_neo4j_driver: AsyncDriver,
    con005_settings: Settings,
) -> ConsolidationRunService:
    return build_production_run_service(con005_neo4j_driver, con005_settings)
