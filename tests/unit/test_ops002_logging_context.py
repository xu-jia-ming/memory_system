"""OPS-002 unit tests for logging context and structlog JSON fields."""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.consolidation_run import ConsolidationRunMetrics
from memory_system.domain.models.extraction_task import MemoryExtractionTask
from memory_system.domain.services.compression_llm_service import run_compression_llm
from memory_system.domain.services.extraction_llm_service import run_extraction_llm
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.extraction_task_consumer_service import (
    process_archive_created_event,
)
from memory_system.entrypoints.consolidation_worker import main as consolidation_main
from memory_system.entrypoints.extraction_worker import main as extraction_main
from memory_system.infrastructure.kafka.archive_created_consumer import process_consumer_record
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.observability.consolidation_run_telemetry import log_run_completed
from memory_system.observability.logging import configure_logging
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


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def settings(valid_env: None) -> Settings:
    return get_settings()


def _capture_json_logs() -> tuple[io.StringIO, None]:
    captured = io.StringIO()

    def _factory(*_args: object, **_kwargs: object) -> logging.Logger:
        handler = logging.StreamHandler(captured)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger(f"ops002.capture.{id(captured)}")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        return logger

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=_factory,
        cache_logger_on_first_use=False,
    )
    return captured, None


@pytest.mark.parametrize(
    ("service_name", "entrypoint_main"),
    [
        ("memory-api", None),
        ("memory-extraction-worker", extraction_main),
        ("memory-consolidation-worker", consolidation_main),
    ],
)
def test_u_ops2_01_configure_logging_service_name(
    settings: Settings,
    service_name: str,
    entrypoint_main: object | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(settings, service_name=service_name)
    structlog.get_logger("ops002.service_name").info("probe")
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["service_name"] == service_name


@pytest.mark.asyncio
async def test_u_ops2_02_extraction_record_includes_task_run_id(settings: Settings) -> None:
    captured, _ = _capture_json_logs()
    configure_logging(settings, service_name="memory-extraction-worker")

    event = ArchiveCreatedEvent.model_validate(
        {
            "event_id": "evt-1",
            "event_type": ARCHIVE_CREATED_EVENT_TYPE,
            "archive_id": "arch-1",
            "user_id": "user-1",
            "session_id": "sess-1",
            "created_time": 1_700_000_000,
        }
    )
    task = MemoryExtractionTask.model_validate(
        {
            "task_id": "11111111-1111-4111-8111-111111111111",
            "archive_id": "arch-1",
            "user_id": "user-1",
            "status": ExtractionTaskStatus.COMPLETED,
            "attempt_count": 0,
            "extraction_result": None,
            "last_error": None,
            "created_time": 1_700_000_000,
            "updated_time": 1_700_000_000,
            "completed_time": None,
        }
    )

    class _Pipeline:
        async def run(self, *_args: object, **_kwargs: object) -> PipelineTerminalDecision:
            structlog.get_logger("ops002.worker").info(
                "processing archive",
                archive_id=event.archive_id,
                user_id=event.user_id,
            )
            return PipelineTerminalDecision.complete()

    record = MagicMock()
    record.value = json.dumps(event.model_dump()).encode()
    record.key = event.user_id.encode()
    record.topic = "context.archive.created"
    record.partition = 0
    record.offset = 1

    with (
        patch(
            "memory_system.infrastructure.kafka.archive_created_consumer.process_archive_created_event",
            new=AsyncMock(
                return_value=MagicMock(should_commit_offset=True, task=task),
            ),
        ),
        patch(
            "memory_system.infrastructure.kafka.archive_created_consumer.bind_log_context",
            wraps=__import__(
                "memory_system.observability.request_context",
                fromlist=["bind_log_context"],
            ).bind_log_context,
        ) as bind_mock,
    ):
        await process_consumer_record(
            record=record,
            mongodb=MagicMock(),
            pipeline=_Pipeline(),
            clock=lambda: 1_700_000_000,
        )

    bind_mock.assert_called_once()
    assert bind_mock.call_args.kwargs["task_run_id"]
    assert bind_mock.call_args.kwargs["user_id"] == "user-1"
    assert bind_mock.call_args.kwargs["archive_id"] == "arch-1"


@pytest.mark.asyncio
async def test_u_ops2_03_compression_llm_json_without_content(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(settings, service_name="memory-api")
    secret_content = "TOP_SECRET_USER_MESSAGE_BODY"
    from memory_system.domain.enums.working_memory import MessageRole
    from memory_system.domain.models.compression_llm import CompressionLlmInput
    from memory_system.domain.models.context_archive import ContextArchiveMessage

    client = FakeLlmClient(
        success_content=json.dumps({"compressed_context": "summary only"}),
    )
    await run_compression_llm(
        CompressionLlmInput.model_validate(
            {
                "existing_compressed_context": "",
                "archived_messages": [
                    ContextArchiveMessage(
                        message_id="m1",
                        role=MessageRole.USER,
                        content=secret_content,
                        timestamp=1,
                    )
                ],
                "max_compressed_context_estimated_tokens": 1000,
            }
        ),
        client,
        settings,
    )
    output = capsys.readouterr().out
    assert secret_content not in output
    payload = json.loads(output.strip().splitlines()[-1])
    assert payload["event"] == "compression_llm"
    assert "compressed_context" not in output


@pytest.mark.asyncio
async def test_u_ops2_03b_extraction_llm_json_without_prompt_content(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(settings, service_name="memory-extraction-worker")
    secret = "PRIVATE_ARCHIVE_MESSAGE_CONTENT"
    from memory_system.domain.models.extraction_llm import ExtractionLlmInput
    from memory_system.domain.models.extraction_preprocessing import ExtractionReadyArchive
    from memory_system.domain.enums.working_memory import MessageRole

    archive = ExtractionReadyArchive.model_validate(
        {
            "archive_id": "arch-1",
            "user_id": "user-1",
            "session_id": "sess-1",
            "messages": [
                {
                    "message_id": "m1",
                    "role": MessageRole.USER,
                    "content": secret,
                    "timestamp": 1,
                }
            ],
        }
    )
    client = FakeLlmClient(
        success_content=json.dumps({"entities": [], "memories": []}),
    )
    await run_extraction_llm(
        ExtractionLlmInput(
            task_id="task-1",
            archive_id="arch-1",
            user_id="user-1",
            archive=archive,
        ),
        client,
        settings,
    )
    output = capsys.readouterr().out
    assert secret not in output


@pytest.mark.asyncio
async def test_u_ops2_04_extraction_consumer_failed_log_fields(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(settings, service_name="memory-extraction-worker")
    from memory_system.domain.models.extraction_task import ExtractionLastError

    event = ArchiveCreatedEvent.model_validate(
        {
            "event_id": "evt-1",
            "event_type": ARCHIVE_CREATED_EVENT_TYPE,
            "archive_id": "arch-1",
            "user_id": "user-1",
            "session_id": "sess-1",
            "created_time": 1_700_000_000,
        }
    )
    task = MemoryExtractionTask.model_validate(
        {
            "task_id": "11111111-1111-4111-8111-111111111111",
            "archive_id": "arch-1",
            "user_id": "user-1",
            "status": ExtractionTaskStatus.PENDING,
            "attempt_count": 0,
            "extraction_result": None,
            "last_error": None,
            "created_time": 1_700_000_000,
            "updated_time": 1_700_000_000,
            "completed_time": None,
        }
    )
    decision = PipelineTerminalDecision.fail(
        ExtractionLastError(
            failed_stage="graph_write",
            error_code="graph_write_failed",
            message="failed",
        )
    )

    class _Pipeline:
        async def run(self, *_args: object, **_kwargs: object) -> PipelineTerminalDecision:
            return decision

    with (
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.upsert_pending_extraction_task",
            new=AsyncMock(return_value=task),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_processing_from_pending",
            new=AsyncMock(
                return_value=task.model_copy(
                    update={
                        "status": ExtractionTaskStatus.PROCESSING,
                        "attempt_count": 1,
                    }
                )
            ),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            new=AsyncMock(return_value=task.model_copy(update={"status": ExtractionTaskStatus.FAILED})),
        ),
        patch(
            "memory_system.domain.services.extraction_task_consumer_service.repo.find_extraction_task_by_archive_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        await process_archive_created_event(
            mongodb=MagicMock(),
            event=event,
            pipeline=_Pipeline(),
            clock=lambda: 1_700_000_000,
        )

    output = capsys.readouterr().out
    payload = json.loads(output.strip().splitlines()[-1])
    for field in ("task_id", "archive_id", "user_id", "failed_stage", "attempt_count"):
        assert field in payload


def test_u_ops2_05_consolidation_telemetry_json(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(settings, service_name="memory-consolidation-worker")
    metrics = ConsolidationRunMetrics(
        scanned_count=1,
        updated_count=1,
        version_conflict_count=0,
        invalid_memory_count=0,
        missing_evidence_count=0,
        batch_count=1,
        run_duration_ms=42,
    )
    log_run_completed(
        run_id="run-1",
        evaluation_time=1_700_000_000,
        metrics=metrics,
        status="success",
        user_id="user-1",
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["event"] == "consolidation run completed"
    assert payload["run_duration_ms"] == 42
