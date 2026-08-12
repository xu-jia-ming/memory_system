"""Unit tests for extraction LLM service (EXT-003)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from tests.contract.helpers.extraction_llm_fake import (
    empty_extraction_json,
    valid_extraction_json,
    valid_extraction_payload,
)

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus, PipelineTerminalKind
from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_llm import ExtractionLlmInput, ExtractionLlmOutcome
from memory_system.domain.models.extraction_preprocessing import (
    ExtractionArchiveMessage,
    ExtractionReadyArchive,
)
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.extraction_llm_service import (
    EXTRACTION_SYSTEM_PROMPT,
    SCHEMA_CORRECTION_INSTRUCTION,
    ExtractionLlmService,
    render_extraction_user_prompt,
    run_extraction_llm,
    validate_extraction_payload,
)
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.extraction_redaction_service import REDACTION_MARKER
from memory_system.infrastructure.llm import FakeLlmClient, LlmServiceError
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


def _ready_archive(**message_overrides: Any) -> ExtractionReadyArchive:
    message = {
        "message_id": "msg_000001",
        "role": "user",
        "content": "I am building the memory system",
        "timestamp": NOW,
    }
    message.update(message_overrides)
    return ExtractionReadyArchive(
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        messages=[ExtractionArchiveMessage.model_validate(message)],
    )


def _task(**overrides: Any) -> MemoryExtractionTask:
    payload: dict[str, Any] = {
        "task_id": "11111111-1111-4111-8111-111111111111",
        "archive_id": "archive-1",
        "user_id": "user-1",
        "status": ExtractionTaskStatus.PROCESSING,
        "attempt_count": 1,
        "extraction_result": None,
        "last_error": None,
        "created_time": NOW,
        "updated_time": NOW,
        "completed_time": None,
    }
    payload.update(overrides)
    return MemoryExtractionTask.model_validate(payload)


def _event() -> ArchiveCreatedEvent:
    return ArchiveCreatedEvent(
        event_id="event-1",
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        created_time=NOW,
    )


def _llm_input(archive: ExtractionReadyArchive | None = None) -> ExtractionLlmInput:
    return ExtractionLlmInput(
        archive=archive or _ready_archive(),
        task_id="11111111-1111-4111-8111-111111111111",
        archive_id="archive-1",
        user_id="user-1",
    )


@pytest.mark.asyncio
async def test_u1_valid_output_adds_source_time_and_fingerprint(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=valid_extraction_json())
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.outcome == ExtractionLlmOutcome.SUCCESS
    assert result.success is not None
    memory = result.success.result.memories[0]
    assert memory.candidate_source_time == NOW
    assert len(memory.candidate_fingerprint) == 64
    assert result.success.result.entities[0].name == "Agent Memory System"


@pytest.mark.asyncio
async def test_u3_legal_empty_output(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=empty_extraction_json())
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.outcome == ExtractionLlmOutcome.SUCCESS
    assert result.success is not None
    assert result.success.result.is_both_empty()


@pytest.mark.asyncio
async def test_u5_prompt_preserves_message_order(valid_env: None) -> None:
    archive = ExtractionReadyArchive(
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        messages=[
            ExtractionArchiveMessage(
                message_id="msg_a",
                role="user",
                content="first",
                timestamp=NOW,
            ),
            ExtractionArchiveMessage(
                message_id="msg_b",
                role="assistant",
                content="second",
                timestamp=NOW,
            ),
        ],
    )
    prompt = render_extraction_user_prompt(archive)
    assert prompt.index("msg_a") < prompt.index("msg_b")
    assert '"timestamp":1700000000' in prompt.replace(" ", "")


@pytest.mark.asyncio
async def test_u7_duplicate_local_entity_ids_fail(valid_env: None) -> None:
    settings = get_settings()
    payload = valid_extraction_payload(
        entities=[
            {
                "local_entity_id": "entity_1",
                "name": "A",
                "type": "project",
                "aliases": [],
            },
            {
                "local_entity_id": "entity_1",
                "name": "B",
                "type": "project",
                "aliases": [],
            },
        ]
    )
    client = FakeLlmClient(responses=[json.dumps(payload), json.dumps(payload)])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.outcome == ExtractionLlmOutcome.FAILURE
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u8_invalid_source_reference_fails(valid_env: None) -> None:
    settings = get_settings()
    payload = valid_extraction_payload()
    payload["memories"][0]["source_message_ids"] = ["missing"]
    client = FakeLlmClient(responses=[json.dumps(payload), json.dumps(payload)])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u9_object_xor_violation_fails(valid_env: None) -> None:
    settings = get_settings()
    payload = valid_extraction_payload()
    payload["memories"][0]["object_entity_id"] = None
    payload["memories"][0]["object_value"] = None
    client = FakeLlmClient(responses=[json.dumps(payload), json.dumps(payload)])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("memory_overrides",),
    [
        ({"memory_type": "fact", "event_status": "ongoing"},),
        ({"memory_type": "fact", "event_status": None, "start_time": "2024-01-01"},),
        ({"memory_type": "fact", "event_status": None, "end_time": "2024-01-01"},),
        (
            {
                "memory_type": "fact",
                "event_status": None,
                "original_time_text": "yesterday",
            },
        ),
        ({"memory_type": "event", "event_status": "invalid_status"},),
    ],
)
async def test_u10_event_non_event_nullability_violations(
    valid_env: None,
    memory_overrides: dict[str, Any],
) -> None:
    settings = get_settings()
    payload = valid_extraction_payload()
    payload["memories"][0].update(memory_overrides)
    client = FakeLlmClient(responses=[json.dumps(payload), json.dumps(payload)])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u11_confidence_out_of_range_fails(valid_env: None) -> None:
    settings = get_settings()
    payload = valid_extraction_payload()
    payload["memories"][0]["confidence"] = 1.5
    client = FakeLlmClient(responses=[json.dumps(payload), json.dumps(payload)])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"


@pytest.mark.asyncio
async def test_u13_redaction_marker_rejected(valid_env: None) -> None:
    settings = get_settings()
    payload = valid_extraction_payload()
    payload["memories"][0]["content"] = f"secret {REDACTION_MARKER}"
    client = FakeLlmClient(responses=[json.dumps(payload), json.dumps(payload)])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"


@pytest.mark.asyncio
async def test_u14_malformed_then_valid_succeeds(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(responses=["not-json", valid_extraction_json()])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.outcome == ExtractionLlmOutcome.SUCCESS
    assert client.call_count == 2
    assert client.last_user_prompt is not None
    assert SCHEMA_CORRECTION_INSTRUCTION in client.prompt_history[1][1]
    assert "not-json" not in client.prompt_history[1][1]


@pytest.mark.asyncio
async def test_u16_both_attempts_invalid(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(responses=["not-json", "still-not-json"])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_invalid_output"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u17_timeout_no_retry(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(
        responses=[
            LlmServiceError(code="llm_timeout", sanitized_message="timeout"),
        ]
    )
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_timeout"
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_u18_provider_failure_no_retry(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(
        responses=[
            LlmServiceError(code="llm_request_failed", sanitized_message="503"),
        ]
    )
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.failure is not None
    assert result.failure.error_code == "llm_request_failed"
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_u19_blank_output_maps_to_invalid_output(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(responses=["", valid_extraction_json()])
    result = await run_extraction_llm(_llm_input(), client, settings)
    assert result.outcome == ExtractionLlmOutcome.SUCCESS
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_u20_exact_prompt_literals(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=valid_extraction_json())
    await run_extraction_llm(_llm_input(), client, settings)
    assert client.last_system_prompt == EXTRACTION_SYSTEM_PROMPT
    assert client.last_user_prompt is not None
    assert "Current user ID:\nuser-1" in client.last_user_prompt
    assert "Archived conversation messages:" in client.last_user_prompt
    assert "Extract durable long-term memory candidates." in client.last_user_prompt
    assert "event_id" not in client.last_user_prompt
    assert "archive_batch_key" not in client.last_user_prompt


def test_u21_duplicate_memories_merge_source_ids(valid_env: None) -> None:
    settings = get_settings()
    payload = valid_extraction_payload(
        memories=[
            {
                "memory_type": "fact",
                "content": "same",
                "subject_entity_id": "user",
                "predicate": "likes",
                "object_entity_id": None,
                "object_value": "tea",
                "event_status": None,
                "start_time": None,
                "end_time": None,
                "original_time_text": None,
                "confidence": 0.8,
                "source_message_ids": ["msg_b"],
            },
            {
                "memory_type": "fact",
                "content": "same",
                "subject_entity_id": "user",
                "predicate": "likes",
                "object_entity_id": None,
                "object_value": "tea",
                "event_status": None,
                "start_time": None,
                "end_time": None,
                "original_time_text": None,
                "confidence": 0.8,
                "source_message_ids": ["msg_000001"],
            },
        ]
    )
    archive = _ready_archive()
    archive = archive.model_copy(
        update={
            "messages": archive.messages
            + [
                ExtractionArchiveMessage(
                    message_id="msg_b",
                    role="user",
                    content="more",
                    timestamp=NOW + 1,
                )
            ]
        }
    )
    validated = validate_extraction_payload(
        payload,
        archive=archive,
        limits=settings.memory_extraction,
    )
    assert len(validated.memories) == 1
    assert validated.memories[0].source_message_ids == ["msg_000001", "msg_b"]


@pytest.mark.asyncio
async def test_u25_failure_logs_required_metadata(
    valid_env: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = get_settings()
    client = FakeLlmClient(responses=["not-json", "still-not-json"])
    with caplog.at_level(logging.ERROR):
        await run_extraction_llm(_llm_input(), client, settings)
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "task_id=" in joined
    assert "archive_id=" in joined
    assert "user_id=" in joined
    assert "failed_stage=" in joined
    assert "attempt_count=" in joined
    assert "not-json" not in joined


@pytest.mark.asyncio
async def test_u2_empty_archive_zero_llm_calls(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=valid_extraction_json())
    preprocessing = AsyncMock()
    preprocessing.prepare = AsyncMock(
        return_value=(
            PipelineTerminalDecision.complete(),
            ExtractionReadyArchive(
                archive_id="archive-1",
                user_id="user-1",
                session_id="session-1",
                messages=[],
            ),
        )
    )
    service = ExtractionLlmService(
        AsyncMock(),
        client,
        settings,
        preprocessing=preprocessing,
    )
    decision = await service.run(_task(), _event())
    assert decision.kind == PipelineTerminalKind.COMPLETE
    assert client.call_count == 0


@pytest.mark.asyncio
async def test_pipeline_non_empty_result_aborts_without_terminal(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=valid_extraction_json())
    preprocessing = AsyncMock()
    preprocessing.prepare = AsyncMock(
        return_value=(PipelineTerminalDecision.complete(), _ready_archive())
    )
    with patch(
        "memory_system.domain.services.extraction_llm_service.task_repo.set_extraction_result",
        new_callable=AsyncMock,
        return_value=_task(extraction_result=valid_extraction_payload()),
    ):
        service = ExtractionLlmService(
            AsyncMock(),
            client,
            settings,
            preprocessing=preprocessing,
        )
        decision = await service.run(_task(), _event())
    assert decision.kind == PipelineTerminalKind.ABORT_WITHOUT_TERMINAL
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_pipeline_both_empty_completes(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=empty_extraction_json())
    preprocessing = AsyncMock()
    preprocessing.prepare = AsyncMock(
        return_value=(PipelineTerminalDecision.complete(), _ready_archive())
    )
    with patch(
        "memory_system.domain.services.extraction_llm_service.task_repo.set_extraction_result",
        new_callable=AsyncMock,
        return_value=_task(extraction_result={"entities": [], "memories": []}),
    ):
        service = ExtractionLlmService(
            AsyncMock(),
            client,
            settings,
            preprocessing=preprocessing,
        )
        decision = await service.run(_task(), _event())
    assert decision.kind == PipelineTerminalKind.COMPLETE


@pytest.mark.asyncio
async def test_replay_skips_llm_with_persisted_result(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(success_content=valid_extraction_json())
    service = ExtractionLlmService(AsyncMock(), client, settings, preprocessing=AsyncMock())
    decision = await service.run(
        _task(extraction_result=valid_extraction_payload()),
        _event(),
    )
    assert decision.kind == PipelineTerminalKind.ABORT_WITHOUT_TERMINAL
    assert client.call_count == 0


@pytest.mark.asyncio
async def test_pipeline_llm_failure_returns_fail_decision(valid_env: None) -> None:
    settings = get_settings()
    client = FakeLlmClient(responses=["not-json", "still-not-json"])
    preprocessing = AsyncMock()
    preprocessing.prepare = AsyncMock(
        return_value=(PipelineTerminalDecision.complete(), _ready_archive())
    )
    service = ExtractionLlmService(
        AsyncMock(),
        client,
        settings,
        preprocessing=preprocessing,
    )
    decision = await service.run(_task(), _event())
    assert decision.kind == PipelineTerminalKind.FAIL
    assert decision.last_error == ExtractionLastError(
        error_code="llm_invalid_output",
        failed_stage="llm_extraction",
        message="extraction llm failed",
    )
