"""OPS-002 unit tests for Prometheus metrics wiring."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import REGISTRY

from memory_system.domain.enums.compression_coordinator import CompressionStatus
from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.compression_coordinator_service import (
    run_compression_coordination,
)
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.extraction_task_consumer_service import (
    process_archive_created_event,
)
from memory_system.observability.metrics import record_retrieval
from memory_system.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]

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


def _sample_value(metric_name: str, labels: dict[str, str]) -> float | None:
    return REGISTRY.get_sample_value(metric_name, labels=labels)


@pytest.mark.asyncio
async def test_u_ops2_10_compression_total_incremented(valid_env: None) -> None:
    settings = get_settings()
    before = _sample_value("compression_total", {"status": "not_triggered"}) or 0.0
    with patch(
        "memory_system.domain.services.compression_coordinator_service.get_working_memory_meta",
        new=AsyncMock(return_value=MagicMock(estimated_tokens=0)),
    ):
        result = await run_compression_coordination(
            redis=MagicMock(),
            mongodb=MagicMock(),
            kafka_producer=MagicMock(),
            llm_client=MagicMock(),
            settings=settings,
            user_id="user-1",
            session_id="sess-1",
        )
    assert result.status == CompressionStatus.NOT_TRIGGERED
    after = _sample_value("compression_total", {"status": "not_triggered"})
    assert after is not None and after > before


@pytest.mark.asyncio
async def test_u_ops2_11_extraction_terminal_metrics(valid_env: None) -> None:
    before_total = _sample_value("extraction_tasks_total", {"status": "failed"}) or 0.0
    before_duration = (
        REGISTRY.get_sample_value("extraction_task_duration_seconds_count") or 0.0
    )
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
            new=AsyncMock(
                return_value=task.model_copy(update={"status": ExtractionTaskStatus.FAILED}),
            ),
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

    after_total = _sample_value("extraction_tasks_total", {"status": "failed"})
    after_duration = REGISTRY.get_sample_value("extraction_task_duration_seconds_count")
    assert after_total is not None and after_total > before_total
    assert after_duration is not None and after_duration > before_duration


@pytest.mark.asyncio
async def test_u_ops2_12_retrieval_metrics(valid_env: None) -> None:
    before_requests = (
        REGISTRY.get_sample_value(
            "retrieval_requests_total",
            labels={"mode": "hybrid", "status": "success"},
        )
        or 0.0
    )
    before_duration = (
        REGISTRY.get_sample_value(
            "retrieval_duration_seconds_count",
            labels={"mode": "hybrid"},
        )
        or 0.0
    )
    record_retrieval(mode="hybrid", status="success", duration_seconds=0.05)
    after_requests = REGISTRY.get_sample_value(
        "retrieval_requests_total",
        labels={"mode": "hybrid", "status": "success"},
    )
    after_duration = REGISTRY.get_sample_value(
        "retrieval_duration_seconds_count",
        labels={"mode": "hybrid"},
    )
    assert after_requests is not None and after_requests > before_requests
    assert after_duration is not None and after_duration > before_duration

    service_source = (
        REPO_ROOT / "src/memory_system/domain/services/retrieval_api_service.py"
    ).read_text(encoding="utf-8")
    assert "record_retrieval(" in service_source
