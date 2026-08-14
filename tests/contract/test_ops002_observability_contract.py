"""OPS-002 observability contract tests."""

from __future__ import annotations

import importlib
import io
import json
import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, generate_latest

from memory_system.api.app import create_app
from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_TYPE,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.extraction_pipeline_port import PipelineTerminalDecision
from memory_system.domain.services.extraction_task_consumer_service import (
    process_archive_created_event,
)
from memory_system.infrastructure.runtime import AppState
from memory_system.observability import metrics as metrics_module
from memory_system.settings import get_settings

_es_mod = importlib.import_module("scripts.migrations.003_elasticsearch_memory_v1")
MEMORY_RETRIEVAL_V1_MAPPINGS = _es_mod.MEMORY_RETRIEVAL_V1_MAPPINGS

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
    "PROXY__HTTP_URL": "",
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
def fake_app_state(valid_env: None) -> AppState:
    settings = get_settings()
    redis_client = MagicMock()
    redis_client.ping = AsyncMock(return_value=True)
    collection = MagicMock()
    collection.find_one = AsyncMock(
        side_effect=lambda query: {"migration_id": query["migration_id"]}
    )
    database = MagicMock()
    database.__getitem__ = MagicMock(return_value=collection)
    mongodb_client = MagicMock()
    mongodb_client.admin = MagicMock()
    mongodb_client.admin.command = AsyncMock(return_value={"ok": 1})
    mongodb_client.__getitem__ = MagicMock(return_value=database)
    neo4j_session = MagicMock()
    neo4j_session.run = AsyncMock()
    neo4j_session.__aenter__ = AsyncMock(return_value=neo4j_session)
    neo4j_session.__aexit__ = AsyncMock(return_value=None)
    neo4j_driver = MagicMock()
    neo4j_driver.session = MagicMock(return_value=neo4j_session)
    elasticsearch_client = MagicMock()
    elasticsearch_client.info = AsyncMock(
        return_value={"version": {"number": settings.memory_retrieval.elasticsearch_version}}
    )
    elasticsearch_client.indices = MagicMock()
    elasticsearch_client.indices.exists_alias = AsyncMock(return_value=True)
    alias_name = settings.memory_retrieval.index_name
    elasticsearch_client.indices.get_alias = AsyncMock(
        return_value={"memory_retrieval_v1": {"aliases": {alias_name: {}}}}
    )
    elasticsearch_client.indices.get_mapping = AsyncMock(
        return_value={"memory_retrieval_v1": {"mappings": MEMORY_RETRIEVAL_V1_MAPPINGS}}
    )
    http_client = MagicMock()
    http_response = MagicMock()
    http_response.status_code = 200
    http_client.get = AsyncMock(return_value=http_response)
    kafka_producer = MagicMock()
    kafka_producer._closed = False
    kafka_producer.client = MagicMock()
    kafka_producer.client.bootstrap_connected = MagicMock(return_value=True)
    return AppState(
        settings=settings,
        redis=redis_client,
        mongodb=mongodb_client,
        neo4j=neo4j_driver,
        elasticsearch=elasticsearch_client,
        http_client=http_client,
        kafka_producer=kafka_producer,
        kafka_producer_ready=True,
    )


@pytest.fixture
def client(fake_app_state: AppState) -> Iterator[TestClient]:
    app = create_app(app_state=fake_app_state)
    with TestClient(app) as test_client:
        yield test_client


def test_c_ops2_01_health_live_json_minimum_fields(
    monkeypatch: pytest.MonkeyPatch,
    fake_app_state: AppState,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(metrics_module, "observe_http_request", lambda **_kwargs: None)
    app = create_app(app_state=fake_app_state)
    with TestClient(app) as test_client:
        test_client.get("/health/live")
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    for field in ("timestamp", "level", "service_name", "environment", "request_id"):
        assert field in payload
    assert payload["service_name"] == "memory-api"


def test_c_ops2_02_api_scrape_boundary_and_worker_unit_sample(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    client.get("/health/live")
    scrape = generate_latest(REGISTRY).decode()
    assert "http_requests_total" in scrape
    assert "consolidation_runs_total" in scrape
    # MET-AUDIT-001: production api/worker registries are separate processes.
    # Unit tests share one REGISTRY; worker non-zero sample is asserted below.

    before = REGISTRY.get_sample_value("extraction_tasks_total", labels={"status": "failed"}) or 0.0
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
        monkeypatch.context() as mp,
    ):
        mp.setattr(
            "memory_system.domain.services.extraction_task_consumer_service.repo.upsert_pending_extraction_task",
            AsyncMock(return_value=task),
        )
        mp.setattr(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_processing_from_pending",
            AsyncMock(
                return_value=task.model_copy(
                    update={
                        "status": ExtractionTaskStatus.PROCESSING,
                        "attempt_count": 1,
                    }
                )
            ),
        )
        mp.setattr(
            "memory_system.domain.services.extraction_task_consumer_service.repo.mark_failed",
            AsyncMock(return_value=task.model_copy(update={"status": ExtractionTaskStatus.FAILED})),
        )
        mp.setattr(
            "memory_system.domain.services.extraction_task_consumer_service.repo.find_extraction_task_by_archive_id",
            AsyncMock(return_value=None),
        )
        import asyncio

        asyncio.run(
            process_archive_created_event(
                mongodb=MagicMock(),
                event=event,
                pipeline=_Pipeline(),
                clock=lambda: 1_700_000_000,
            )
        )
    after = REGISTRY.get_sample_value("extraction_tasks_total", labels={"status": "failed"})
    assert after is not None and after > before


def test_c_ops2_03_auth_failure_logs_do_not_leak_api_key(fake_app_state: AppState) -> None:
    captured = io.StringIO()

    def _capture_logger_factory(*_args: Any, **_kwargs: Any) -> logging.Logger:
        handler = logging.StreamHandler(captured)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("memory_system.ops002.auth_capture")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        return logger

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=_capture_logger_factory,
        cache_logger_on_first_use=False,
    )
    app = create_app(app_state=fake_app_state)
    with TestClient(app) as test_client:
        secret = VALID_ENV["MEMORY_API_KEY"]
        test_client.get("/internal/metrics", headers={"X-API-Key": secret})
    assert secret not in captured.getvalue()


def test_c_ops2_04_registered_metric_names_exist() -> None:
    payload = generate_latest().decode()
    for expected in (
        "http_requests_total",
        "http_request_duration_seconds",
        "compression_total",
        "extraction_tasks_total",
        "extraction_task_duration_seconds",
        "retrieval_requests_total",
        "retrieval_duration_seconds",
        "consolidation_runs_total",
    ):
        assert expected in payload
