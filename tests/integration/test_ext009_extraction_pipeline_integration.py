"""Compose-backed EXT-009 integration coverage."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from pymongo import AsyncMongoClient
from tests.e2e import conftest as ext009_fixtures
from tests.e2e.conftest import Ext009Runtime, InfraStack
from tests.e2e.helpers.ext009_e2e_helpers import (
    archive_event,
    build_pipeline,
    cleanup_ext009_data,
    count_user_graph_nodes,
    count_user_index_documents,
    new_ext009_ids,
    publish_event,
    run_worker_once,
    seed_archive,
)

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.infrastructure.mongodb.extraction_task_repository import (
    find_extraction_task_by_archive_id,
)


@pytest.fixture(scope="module")
def e2e_dotenv() -> Iterator[ext009_fixtures.DotenvBackup]:
    yield from ext009_fixtures.e2e_dotenv.__wrapped__()


@pytest.fixture(scope="module")
def infra_stack(e2e_dotenv: ext009_fixtures.DotenvBackup) -> Iterator[InfraStack]:
    yield from ext009_fixtures.infra_stack.__wrapped__(e2e_dotenv)


@pytest.fixture
async def mongo_client(
    infra_stack: InfraStack,
) -> AsyncIterator[AsyncMongoClient[Any]]:
    async for client in ext009_fixtures.mongo_client.__wrapped__(infra_stack):
        yield client


@pytest.fixture
async def ext009_runtime(
    infra_stack: InfraStack,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Ext009Runtime]:
    async for runtime in ext009_fixtures.ext009_runtime.__wrapped__(
        infra_stack,
        monkeypatch,
    ):
        yield runtime


@pytest.fixture
async def kafka_producer(infra_stack: InfraStack) -> AsyncIterator[AIOKafkaProducer]:
    async for producer in ext009_fixtures.kafka_producer.__wrapped__(infra_stack):
        yield producer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_compose_happy_path_uses_real_stage_repositories(
    mongo_client: AsyncMongoClient[Any],
    kafka_producer: AIOKafkaProducer,
    infra_stack: InfraStack,
    ext009_runtime: Ext009Runtime,
) -> None:
    user_id, session_id, archive_id = new_ext009_ids("i1")
    await seed_archive(
        mongo_client,
        user_id=user_id,
        session_id=session_id,
        archive_id=archive_id,
    )
    pipeline, llm = build_pipeline(mongo_client, ext009_runtime)
    try:
        partition, offset = await publish_event(
            kafka_producer,
            archive_event(
                user_id=user_id,
                session_id=session_id,
                archive_id=archive_id,
            ),
        )
        processed = await run_worker_once(
            mongodb=mongo_client,
            bootstrap_servers=infra_stack.kafka_bootstrap,
            pipeline=pipeline,
            partition=partition,
            offset=offset,
        )
        task = await find_extraction_task_by_archive_id(mongo_client, archive_id)
        assert processed == 1
        assert task is not None
        assert task.status == ExtractionTaskStatus.COMPLETED
        assert llm.call_count == 1
        assert await count_user_graph_nodes(ext009_runtime.neo4j_driver, "Memory", user_id) == 1
        assert (
            await count_user_index_documents(
                ext009_runtime.elasticsearch,
                index_name=ext009_runtime.settings.memory_retrieval.index_name,
                user_id=user_id,
            )
            == 1
        )
    finally:
        await cleanup_ext009_data(
            mongo_client,
            ext009_runtime,
            user_id=user_id,
            archive_id=archive_id,
        )
