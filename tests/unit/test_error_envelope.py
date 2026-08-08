"""Unit tests for unified API error envelopes."""

from __future__ import annotations

import json

from memory_system.api.error_handlers import build_error_response
from memory_system.api.errors import build_error_body


def test_build_error_body_shape() -> None:
    body = build_error_body(
        code="invalid_api_key",
        message="Invalid API key",
        details={},
        request_id="11111111-1111-4111-8111-111111111111",
    )
    assert body["success"] is False
    assert body["error"]["code"] == "invalid_api_key"
    assert body["error"]["message"] == "Invalid API key"
    assert body["error"]["details"] == {}
    assert body["request_id"] == "11111111-1111-4111-8111-111111111111"


def test_build_error_response_includes_request_id_header() -> None:
    request_id = "22222222-2222-4222-8222-222222222222"
    response = build_error_response(
        code="validation_error",
        message="Request validation failed",
        details={"errors": []},
        request_id=request_id,
        status_code=422,
    )
    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == request_id
    payload = json.loads(bytes(response.body).decode())
    assert payload["request_id"] == request_id
    assert payload["error"]["code"] == "validation_error"
