"""Contract tests for API shell auth, health, metrics, and error envelopes."""

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
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, generate_latest

from memory_system.api.app import create_app
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
        return_value={
            "memory_retrieval_v1": {
                "mappings": MEMORY_RETRIEVAL_V1_MAPPINGS,
            }
        }
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

    @app.get("/_contract/validate")
    async def validate_query(required_int: int) -> dict[str, int]:
        return {"required_int": required_int}

    with TestClient(app) as test_client:
        yield test_client


def test_health_live_without_api_key(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_health_ready_without_api_key_all_ready(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["embedding"] == "ready"


def test_metrics_without_api_key(client: TestClient) -> None:
    response = client.get("/internal/metrics")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "invalid_api_key"


def test_metrics_with_wrong_api_key(client: TestClient) -> None:
    response = client.get(
        "/internal/metrics",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_metrics_with_memory_key_forbidden(client: TestClient) -> None:
    response = client.get(
        "/internal/metrics",
        headers={"X-API-Key": VALID_ENV["MEMORY_API_KEY"]},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_metrics_with_admin_key(client: TestClient) -> None:
    response = client.get(
        "/internal/metrics",
        headers={"X-API-Key": VALID_ENV["MEMORY_ADMIN_API_KEY"]},
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "http_requests_total" in response.text


def test_validation_error_envelope(client: TestClient) -> None:
    response = client.get("/_contract/validate")
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert "request_id" in body
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_request_id_header_matches_body_on_error(client: TestClient) -> None:
    request_id = "123e4567-e89b-42d3-a456-426614174000"
    response = client.get(
        "/internal/metrics",
        headers={"X-Request-ID": request_id, "X-API-Key": "wrong"},
    )
    assert response.headers["X-Request-ID"] == request_id
    assert response.json()["request_id"] == request_id


def test_auth_failure_logs_do_not_leak_api_key(
    monkeypatch: pytest.MonkeyPatch,
    fake_app_state: AppState,
) -> None:
    captured = io.StringIO()

    def _capture_logger_factory(*_args: Any, **_kwargs: Any) -> logging.Logger:
        handler = logging.StreamHandler(captured)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("memory_system.auth_capture")
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

    output = captured.getvalue()
    assert secret not in output


def test_registered_metric_names_exist() -> None:
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
    assert metrics_module.KAFKA_CONSUMER_LAG in metrics_module.ALL_METRICS


def test_http_metrics_label_dimensions(client: TestClient) -> None:
    client.get("/health/live")
    samples = REGISTRY.get_sample_value(
        "http_requests_total",
        labels={
            "method": "GET",
            "path_template": "/health/live",
            "status": "200",
        },
    )
    assert samples is not None and samples >= 1


def test_structlog_minimum_fields(
    monkeypatch: pytest.MonkeyPatch,
    fake_app_state: AppState,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        metrics_module,
        "observe_http_request",
        lambda **_kwargs: None,
    )

    app: FastAPI = create_app(app_state=fake_app_state)
    with TestClient(app) as test_client:
        test_client.get("/health/live")

    captured = capsys.readouterr().out
    lines = [line for line in captured.splitlines() if line.strip()]
    assert lines
    payload = json.loads(lines[-1])
    for field in ("timestamp", "level", "service_name", "environment", "request_id"):
        assert field in payload
