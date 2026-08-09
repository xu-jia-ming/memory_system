"""Contract tests for SiliconFlow embedding client mocked HTTP matrix."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from memory_system.infrastructure.embedding import (
    EmbeddingServiceError,
    SiliconFlowEmbeddingClient,
    create_embedding_client,
)
from memory_system.settings import get_settings

_HELPER_PATH = Path(__file__).resolve().parent / "helpers" / "siliconflow_fake.py"
_HELPER_SPEC = importlib.util.spec_from_file_location(
    "siliconflow_fake_helper",
    _HELPER_PATH,
)
assert _HELPER_SPEC is not None and _HELPER_SPEC.loader is not None
_siliconflow_fake = importlib.util.module_from_spec(_HELPER_SPEC)
_HELPER_SPEC.loader.exec_module(_siliconflow_fake)
EMBEDDING_DIMENSION = cast(int, _siliconflow_fake.EMBEDDING_DIMENSION)
json_response = cast(
    Callable[..., httpx.Response],
    _siliconflow_fake.json_response,
)
make_embeddings_response = cast(
    Callable[..., dict[str, Any]],
    _siliconflow_fake.make_embeddings_response,
)
make_mock_transport = cast(
    Callable[[Callable[[httpx.Request], httpx.Response]], httpx.MockTransport],
    _siliconflow_fake.make_mock_transport,
)
parse_request_input = cast(
    Callable[[httpx.Request], list[str]],
    _siliconflow_fake.parse_request_input,
)

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


async def _make_client(
    handler: httpx.MockTransport | None = None,
    *,
    transport: httpx.MockTransport | None = None,
) -> tuple[SiliconFlowEmbeddingClient, httpx.AsyncClient]:
    settings = get_settings()
    selected_transport = transport if transport is not None else handler
    if selected_transport is None:
        raise ValueError("handler or transport required")
    http_client = httpx.AsyncClient(transport=selected_transport)
    return SiliconFlowEmbeddingClient(settings, http_client), http_client


@pytest.mark.asyncio
async def test_factory_returns_siliconflow_client(valid_env: None) -> None:
    settings = get_settings()
    async with httpx.AsyncClient() as http_client:
        client = create_embedding_client(settings, http_client)
        assert isinstance(client, SiliconFlowEmbeddingClient)


@pytest.mark.asyncio
async def test_single_input_success(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        texts = parse_request_input(request)
        return json_response(200, make_embeddings_response(texts))

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    result = await client.embed(["hello"])
    await http_client.aclose()

    assert len(result.vectors) == 1
    assert len(result.vectors[0]) == EMBEDDING_DIMENSION
    assert result.dimension == EMBEDDING_DIMENSION


@pytest.mark.asyncio
async def test_multi_input_single_batch_success(valid_env: None) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        texts = parse_request_input(request)
        return json_response(200, make_embeddings_response(texts))

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    texts = [f"text-{index}" for index in range(5)]
    result = await client.embed(texts)
    await http_client.aclose()

    assert call_count == 1
    assert len(result.vectors) == 5
    assert all(len(vector) == EMBEDDING_DIMENSION for vector in result.vectors)


@pytest.mark.asyncio
async def test_thirty_three_inputs_use_two_batches(valid_env: None) -> None:
    call_count = 0
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        texts = parse_request_input(request)
        batch_sizes.append(len(texts))
        return json_response(200, make_embeddings_response(texts))

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    texts = [f"text-{index}" for index in range(33)]
    result = await client.embed(texts)
    await http_client.aclose()

    assert call_count == 2
    assert batch_sizes == [32, 1]
    assert len(result.vectors) == 33


@pytest.mark.asyncio
async def test_response_index_reordering(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        texts = parse_request_input(request)
        return json_response(200, make_embeddings_response(texts, shuffle_indices=True))

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    result = await client.embed(["first", "second"])
    await http_client.aclose()

    assert len(result.vectors[0]) == EMBEDDING_DIMENSION
    assert result.vectors[0][0] != result.vectors[1][0]


@pytest.mark.asyncio
async def test_response_count_mismatch_fails_fast(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = make_embeddings_response(["only-one"])
        return json_response(200, payload)

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError) as exc_info:
        await client.embed(["one", "two"])
    await http_client.aclose()
    assert exc_info.value.code == "embedding_failed"


@pytest.mark.asyncio
async def test_malformed_json_fails_fast(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError):
        await client.embed(["hello"])
    await http_client.aclose()


@pytest.mark.asyncio
async def test_missing_embedding_field_fails_fast(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            200,
            {
                "object": "list",
                "model": "BAAI/bge-m3",
                "data": [{"index": 0, "object": "embedding"}],
            },
        )

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError):
        await client.embed(["hello"])
    await http_client.aclose()


@pytest.mark.asyncio
async def test_wrong_dimension_fails_fast(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            200,
            {
                "object": "list",
                "model": "BAAI/bge-m3",
                "data": [{"index": 0, "object": "embedding", "embedding": [0.1, 0.2]}],
            },
        )

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError):
        await client.embed(["hello"])
    await http_client.aclose()


@pytest.mark.asyncio
async def test_http_400_fails_fast_without_retry(valid_env: None) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return json_response(400, {"message": "bad request"})

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError) as exc_info:
        await client.embed(["hello"])
    await http_client.aclose()
    assert exc_info.value.code == "embedding_failed"
    assert call_count == 1


@pytest.mark.asyncio
async def test_http_401_fails_fast_auth_failed(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(401, {"message": "unauthorized"})

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError) as exc_info:
        await client.embed(["hello"])
    await http_client.aclose()
    assert exc_info.value.code == "embedding_auth_failed"


@pytest.mark.asyncio
async def test_http_403_fails_fast_auth_failed(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(403, {"message": "forbidden"})

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError) as exc_info:
        await client.embed(["hello"])
    await http_client.aclose()
    assert exc_info.value.code == "embedding_auth_failed"


@pytest.mark.asyncio
async def test_http_429_retries_then_succeeds(valid_env: None) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return json_response(429, {"message": "rate limit"}, headers={"Retry-After": "0"})
        texts = parse_request_input(request)
        return json_response(200, make_embeddings_response(texts))

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    result = await client.embed(["hello"])
    await http_client.aclose()
    assert attempts == 2
    assert len(result.vectors) == 1


@pytest.mark.asyncio
async def test_http_500_retries_then_succeeds(valid_env: None) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return json_response(500, {"message": "server error"})
        texts = parse_request_input(request)
        return json_response(200, make_embeddings_response(texts))

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    result = await client.embed(["hello"])
    await http_client.aclose()
    assert attempts == 2
    assert len(result.vectors) == 1


@pytest.mark.asyncio
async def test_timeout_retries_then_succeeds(valid_env: None) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise httpx.ReadTimeout("read timeout")
        texts = parse_request_input(request)
        return json_response(200, make_embeddings_response(texts))

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    result = await client.embed(["hello"])
    await http_client.aclose()
    assert attempts == 2
    assert len(result.vectors) == 1


@pytest.mark.asyncio
async def test_http_429_exhausted_after_three_attempts(valid_env: None) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return json_response(429, {"message": "rate limit"}, headers={"Retry-After": "0"})

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError) as exc_info:
        await client.embed(["hello"])
    await http_client.aclose()
    assert exc_info.value.code == "embedding_failed"
    assert attempts == 3


@pytest.mark.asyncio
async def test_authorization_not_leaked_in_error(valid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        auth_header = request.headers.get("Authorization", "")
        return json_response(401, {"message": f"failed auth header was {auth_header}"})

    transport = make_mock_transport(handler)
    client, http_client = await _make_client(transport=transport)
    with pytest.raises(EmbeddingServiceError) as exc_info:
        await client.embed(["hello"])
    await http_client.aclose()
    rendered = str(exc_info.value)
    assert "Bearer" not in rendered
    assert "sk-example-replace-me" not in rendered


def test_local_tei_factory_raises_not_implemented(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
) -> None:
    monkeypatch.setenv("SILICONFLOW_API_KEY", "")
    monkeypatch.setenv("MEMORY_RETRIEVAL__EMBEDDING_PROVIDER", "local_tei")
    settings = get_settings()
    with pytest.raises(NotImplementedError):
        create_embedding_client(settings, httpx.AsyncClient())
