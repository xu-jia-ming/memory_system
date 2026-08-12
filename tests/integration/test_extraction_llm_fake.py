"""Integration tests for extraction LLM with FakeLlmClient (EXT-003)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from tests.contract.helpers.extraction_llm_fake import empty_extraction_json, valid_extraction_json

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus, PipelineTerminalKind
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_llm import ExtractionLlmInput, ExtractionLlmOutcome
from memory_system.domain.models.extraction_preprocessing import (
    ExtractionArchiveMessage,
    ExtractionReadyArchive,
)
from memory_system.domain.models.extraction_task import MemoryExtractionTask
from memory_system.domain.services.extraction_llm_service import (
    ExtractionLlmService,
    run_extraction_llm,
)
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.settings import get_settings

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

NOW = 1_700_000_000


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


def _archive() -> ExtractionReadyArchive:
    return ExtractionReadyArchive(
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        messages=[
            ExtractionArchiveMessage(
                message_id="msg_000001",
                role="user",
                content="integration content",
                timestamp=NOW,
            )
        ],
    )


def _input() -> ExtractionLlmInput:
    return ExtractionLlmInput(
        archive=_archive(),
        task_id="11111111-1111-4111-8111-111111111111",
        archive_id="archive-1",
        user_id="user-1",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i1_end_to_end_success(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=valid_extraction_json())
    result = await run_extraction_llm(_input(), client, settings)
    assert result.outcome == ExtractionLlmOutcome.SUCCESS
    assert result.success is not None
    assert result.success.result.memories[0].candidate_fingerprint


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i2_fake_timeout_mapping(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(mode="timeout")
    result = await run_extraction_llm(_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_timeout"
    assert client.call_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i3_fake_retry_sequence(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(responses=["not-json", valid_extraction_json()])
    result = await run_extraction_llm(_input(), client, settings)
    assert result.outcome == ExtractionLlmOutcome.SUCCESS
    assert client.call_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i4_fake_legal_empty_pipeline(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=empty_extraction_json())
    preprocessing = AsyncMock()
    preprocessing.prepare = AsyncMock(
        return_value=(PipelineTerminalDecision.complete(), _archive())
    )
    task = MemoryExtractionTask(
        task_id="11111111-1111-4111-8111-111111111111",
        archive_id="archive-1",
        user_id="user-1",
        status=ExtractionTaskStatus.PROCESSING,
        attempt_count=1,
        created_time=NOW,
        updated_time=NOW,
    )
    event = ArchiveCreatedEvent(
        event_id="event-1",
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        created_time=NOW,
    )
    empty_result = {"entities": [], "memories": []}
    with patch(
        "memory_system.domain.services.extraction_llm_service.task_repo.set_extraction_result",
        new_callable=AsyncMock,
        return_value=task.model_copy(update={"extraction_result": empty_result}),
    ):
        service = ExtractionLlmService(
            AsyncMock(),
            client,
            settings,
            preprocessing=preprocessing,
        )
        decision = await service.run(task, event)
    assert decision.kind == PipelineTerminalKind.COMPLETE


@pytest.mark.integration
@pytest.mark.asyncio
async def test_i6_replay_zero_llm_calls(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=valid_extraction_json())
    persisted_entities = [
        {"local_entity_id": "e", "name": "n", "type": "other", "aliases": []},
    ]
    task = MemoryExtractionTask(
        task_id="11111111-1111-4111-8111-111111111111",
        archive_id="archive-1",
        user_id="user-1",
        status=ExtractionTaskStatus.PROCESSING,
        attempt_count=2,
        extraction_result={"entities": persisted_entities, "memories": []},
        created_time=NOW,
        updated_time=NOW,
    )
    service = ExtractionLlmService(AsyncMock(), client, settings, preprocessing=AsyncMock())
    decision = await service.run(
        task,
        ArchiveCreatedEvent(
            event_id="event-1",
            archive_id="archive-1",
            user_id="user-1",
            session_id="session-1",
            created_time=NOW,
        ),
    )
    assert client.call_count == 0
    assert decision.kind == PipelineTerminalKind.ABORT_WITHOUT_TERMINAL
