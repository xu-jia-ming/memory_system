"""OPS-002 sensitive log and validation redaction guards."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from memory_system.api.error_handlers import _sanitize_validation_errors, register_error_handlers
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


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_u_ops2_07_validation_error_redacts_api_key_field() -> None:
    errors = _sanitize_validation_errors(
        [
            {
                "type": "missing",
                "loc": ("body", "api_key"),
                "msg": "Field required",
                "input": {"api_key": "super-secret-key"},
                "ctx": {"api_key": "super-secret-key", "secret_token": "hidden"},
            }
        ]
    )
    assert errors[0]["loc"] == ["body", "<redacted>"]
    assert errors[0]["ctx"]["api_key"] == "<redacted>"
    assert errors[0]["ctx"]["secret_token"] == "<redacted>"


def test_sanitize_validation_errors_redacts_input_values_in_ctx() -> None:
    errors = _sanitize_validation_errors(
        [
            {
                "type": "value_error",
                "loc": ("body", "secret_field"),
                "msg": "invalid",
                "ctx": {"error": "contains sk-live-abc"},
            }
        ]
    )
    assert errors[0]["loc"] == ["body", "<redacted>"]


def test_register_error_handlers_validation_sanitized() -> None:
    class _Payload(BaseModel):
        api_key: str

    app = FastAPI()
    register_error_handlers(app)

    @app.post("/probe")
    async def probe(_payload: _Payload) -> dict[str, str]:
        return {"ok": "true"}

    client = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(app)
    response = client.post("/probe", json={})
    assert response.status_code == 422
    details = response.json()["error"]["details"]["errors"]
    assert details
    assert "super-secret" not in json.dumps(details)
