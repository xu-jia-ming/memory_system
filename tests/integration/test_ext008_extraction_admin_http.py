"""HTTP integration tests for EXT-008 extraction admin API (TestClient + fakes)."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from memory_system.api.app import create_app
from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_event_republish import ArchiveEventRepublishResult
from memory_system.infrastructure.runtime import AppState
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

NOW = 1_700_000_200
TASK_ID = "11111111-1111-4111-8111-111111111111"
USER_ID = "user_001"
OTHER_USER = "user_002"
ARCHIVE_ID = "archive_000001"
EXTRACTION_RESULT = {"candidates": [{"memory_id": "m1"}]}


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)


class _FakeExtractionStore:
    def __init__(self) -> None:
        self.tasks: dict[tuple[str, str], dict[str, Any]] = {}

    def seed_failed(
        self,
        *,
        user_id: str,
        archive_id: str,
        error_code: str,
        extraction_result: dict[str, Any] | None = EXTRACTION_RESULT,
    ) -> None:
        self.tasks[(user_id, archive_id)] = {
            "task_id": TASK_ID,
            "archive_id": archive_id,
            "user_id": user_id,
            "status": ExtractionTaskStatus.FAILED.value,
            "attempt_count": 2,
            "extraction_result": extraction_result,
            "last_error": {
                "error_code": error_code,
                "failed_stage": "llm_extraction",
                "message": "synthetic failure",
            },
            "created_time": NOW - 100,
            "updated_time": NOW - 50,
            "completed_time": None,
        }

    def seed_completed(self, *, user_id: str, archive_id: str) -> None:
        self.tasks[(user_id, archive_id)] = {
            "task_id": TASK_ID,
            "archive_id": archive_id,
            "user_id": user_id,
            "status": ExtractionTaskStatus.COMPLETED.value,
            "attempt_count": 1,
            "extraction_result": EXTRACTION_RESULT,
            "last_error": None,
            "created_time": NOW - 100,
            "updated_time": NOW,
            "completed_time": NOW,
        }


def _build_fake_mongodb(store: _FakeExtractionStore) -> MagicMock:
    collection = MagicMock()

    async def find_one(query: dict[str, Any]) -> dict[str, Any] | None:
        if "user_id" in query and "archive_id" in query:
            return store.tasks.get((query["user_id"], query["archive_id"]))
        if "archive_id" in query:
            doc = store.tasks.get((USER_ID, query["archive_id"]))
            if doc is None:
                for key, value in store.tasks.items():
                    if key[1] == query["archive_id"]:
                        return value
            return doc
        return None

    async def find_one_and_update(
        filt: dict[str, Any],
        update: dict[str, Any],
        return_document: Any = None,
    ) -> dict[str, Any] | None:
        user_id = filt.get("user_id")
        archive_id = filt.get("archive_id")
        if user_id is None or archive_id is None:
            return None
        key = (user_id, archive_id)
        doc = store.tasks.get(key)
        if doc is None:
            return None
        status_filter = filt.get("status")
        if isinstance(status_filter, str):
            if doc["status"] != status_filter:
                return None
        elif isinstance(status_filter, dict):
            allowed = status_filter.get("$in", [])
            if doc["status"] not in allowed:
                return None
        set_fields = update.get("$set", {})
        doc.update(set_fields)
        store.tasks[key] = doc
        return dict(doc)

    collection.find_one = AsyncMock(side_effect=find_one)
    collection.find_one_and_update = AsyncMock(side_effect=find_one_and_update)

    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection)
    client = MagicMock()
    client.get_default_database.return_value = db
    return client


@pytest.fixture
def extraction_store() -> _FakeExtractionStore:
    return _FakeExtractionStore()


@pytest.fixture
def app_state(valid_env: None, extraction_store: _FakeExtractionStore) -> AppState:
    settings = get_settings()
    redis_client = MagicMock()
    redis_client.ping = AsyncMock(return_value=True)

    mongodb_client = _build_fake_mongodb(extraction_store)

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
def client(app_state: AppState) -> Iterator[TestClient]:
    app = create_app(app_state=app_state)
    with TestClient(app) as test_client:
        yield test_client


def _admin_headers() -> dict[str, str]:
    return {"X-API-Key": VALID_ENV["MEMORY_ADMIN_API_KEY"]}


def _memory_headers() -> dict[str, str]:
    return {"X-API-Key": VALID_ENV["MEMORY_API_KEY"]}


def _status_path(user_id: str = USER_ID, archive_id: str = ARCHIVE_ID) -> str:
    return f"/api/v1/memory/extraction/{user_id}/{archive_id}"


def _retry_path(user_id: str = USER_ID, archive_id: str = ARCHIVE_ID) -> str:
    return f"/api/v1/memory/extraction/{user_id}/{archive_id}/retry"


def _rebuild_path(user_id: str = USER_ID, archive_id: str = ARCHIVE_ID) -> str:
    return f"/api/v1/memory/extraction/{user_id}/{archive_id}/rebuild"


@pytest.fixture(autouse=True)
def _mock_republish_success() -> Iterator[None]:
    with patch(
        "memory_system.domain.services.extraction_admin_service.republish_archive_created_event",
        AsyncMock(
            return_value=ArchiveEventRepublishResult(
                status=ArchiveEventRepublishStatus.SUCCESS,
                event_id="22222222-2222-4222-8222-222222222222",
            )
        ),
    ):
        yield


def test_i1_get_happy(client: TestClient, extraction_store: _FakeExtractionStore) -> None:
    extraction_store.seed_completed(user_id=USER_ID, archive_id=ARCHIVE_ID)
    response = client.get(_status_path(), headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == USER_ID
    assert body["archive_id"] == ARCHIVE_ID
    assert body["status"] == "completed"
    assert body["attempt_count"] == 1
    assert body["completed_time"] == NOW
    assert "extraction_result" not in body


def test_i2_retry_happy(
    client: TestClient,
    extraction_store: _FakeExtractionStore,
) -> None:
    extraction_store.seed_failed(user_id=USER_ID, archive_id=ARCHIVE_ID, error_code="llm_timeout")
    response = client.post(_retry_path(), headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "user_id": USER_ID,
        "archive_id": ARCHIVE_ID,
        "status": "pending",
    }
    stored = extraction_store.tasks[(USER_ID, ARCHIVE_ID)]
    assert stored["status"] == "pending"
    assert stored["last_error"] is None
    assert stored["extraction_result"] == EXTRACTION_RESULT


def test_i3_rebuild_happy(
    client: TestClient,
    extraction_store: _FakeExtractionStore,
) -> None:
    extraction_store.seed_failed(
        user_id=USER_ID,
        archive_id=ARCHIVE_ID,
        error_code="reconciliation_plan_conflict",
    )
    response = client.post(_rebuild_path(), headers=_admin_headers())
    assert response.status_code == 200
    stored = extraction_store.tasks[(USER_ID, ARCHIVE_ID)]
    assert stored["status"] == "pending"
    assert stored["extraction_result"] is None


def test_i4_cross_user_get_404(
    client: TestClient,
    extraction_store: _FakeExtractionStore,
) -> None:
    extraction_store.seed_completed(user_id=OTHER_USER, archive_id=ARCHIVE_ID)
    response = client.get(_status_path(user_id=USER_ID), headers=_admin_headers())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "extraction_task_not_found"


def test_i5_retry_completed_409(
    client: TestClient,
    extraction_store: _FakeExtractionStore,
) -> None:
    extraction_store.seed_completed(user_id=USER_ID, archive_id=ARCHIVE_ID)
    response = client.post(_retry_path(), headers=_admin_headers())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "retry_not_allowed"


def test_no_api_key_401(client: TestClient) -> None:
    response = client.get(_status_path())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_memory_key_403(client: TestClient) -> None:
    response = client.get(_status_path(), headers=_memory_headers())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
