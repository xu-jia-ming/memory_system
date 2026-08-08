"""Integration tests against a real CPU TEI embedding service."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest

from memory_system.infrastructure.embedding.factory import create_embedding_client
from memory_system.infrastructure.embedding.types import EMBEDDING_DIMENSION
from memory_system.settings import get_settings
from memory_system.settings.models import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
START_EMBEDDING_SH = REPO_ROOT / "scripts" / "start_embedding.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
LOCK_FILE = REPO_ROOT / "versions.lock.env"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "embedding_consistency_texts.json"

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
    "MEMORY_API_KEY": "dev-memory-api-key-change-me",
    "MEMORY_ADMIN_API_KEY": "dev-memory-admin-key-change-me",
    "EMBEDDING_EFFECTIVE_RUNTIME_MODE": "cpu",
    "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET": "4096",
}


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


def _lock_file_valid() -> bool:
    if not LOCK_FILE.is_file():
        return False
    content = LOCK_FILE.read_text(encoding="utf-8")
    placeholder = "@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    return "@sha256:" in content and placeholder not in content


def _ensure_dotenv() -> None:
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def _discover_embedding_base_url() -> str | None:
    override = os.environ.get("TEI_INTEGRATION_BASE_URL")
    if override:
        return override.rstrip("/")

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=embedding-service", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not names:
        return None

    inspect = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            names[0],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip_address = inspect.stdout.strip()
    if not ip_address:
        return None
    return f"http://{ip_address}:80"


def _wait_for_embedding_health(base_url: str, timeout_seconds: int = 300) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health", timeout=5.0)
            if response.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(5)
    return False


@pytest.fixture(scope="module")
def tei_cpu_base_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available")
    if not _lock_file_valid():
        pytest.skip("versions.lock.env missing or has placeholder digests")
    _ensure_dotenv()

    start = subprocess.run(
        [str(START_EMBEDDING_SH), "cpu"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if start.returncode != 0:
        pytest.skip(f"start_embedding.sh cpu failed: {start.stderr}")

    base_url = _discover_embedding_base_url()
    if base_url is None:
        pytest.skip("embedding-service container not discoverable on docker network")
    if not _wait_for_embedding_health(base_url):
        pytest.skip("embedding-service did not become healthy in time")

    yield base_url


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def integration_env(monkeypatch: pytest.MonkeyPatch, tei_cpu_base_url: str) -> None:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("EMBEDDING__BASE_URL", tei_cpu_base_url)


@pytest.fixture
def settings(integration_env: None) -> Settings:
    return get_settings()


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0),
    ) as client:
        yield client


def _l2_norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))



async def test_cpu_embed_short_text(
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> None:
    client = create_embedding_client(settings, http_client)
    result = await client.embed(["integration short text"])
    assert result.model == settings.embedding.model_id
    assert len(result.vectors) == 1
    assert len(result.vectors[0]) == EMBEDDING_DIMENSION
    assert all(math.isfinite(value) for value in result.vectors[0])
    assert abs(_l2_norm(result.vectors[0]) - 1.0) < 0.05



async def test_cpu_embed_splits_when_total_tokens_exceed_budget(
    settings: Settings,
    http_client: httpx.AsyncClient,
    tei_cpu_base_url: str,
) -> None:
    texts = [f"记忆系统检索测试文本片段 {index}。" * 40 for index in range(12)]
    tokenize_response = await http_client.post(
        f"{tei_cpu_base_url}/tokenize",
        json={"inputs": texts},
        timeout=60.0,
    )
    tokenize_response.raise_for_status()
    token_payload = tokenize_response.json()
    total_tokens = sum(len(item) for item in token_payload)
    assert total_tokens > settings.embedding_client_total_token_budget

    client = create_embedding_client(settings, http_client)
    result = await client.embed(texts)
    assert len(result.vectors) == len(texts)
    assert all(len(vector) == EMBEDDING_DIMENSION for vector in result.vectors)



async def test_cpu_consistency_fixture_vectors(
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> None:
    texts = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(texts) >= 20

    client = create_embedding_client(settings, http_client)
    result = await client.embed(texts)
    assert len(result.vectors) == len(texts)
    for vector in result.vectors:
        assert len(vector) == EMBEDDING_DIMENSION
        assert all(math.isfinite(value) for value in vector)
        assert abs(_l2_norm(vector) - 1.0) < 0.05



async def test_gpu_consistency_optional(
    settings: Settings,
    http_client: httpx.AsyncClient,
    tei_cpu_base_url: str,
) -> None:
    gpu_check = subprocess.run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        check=False,
    )
    if gpu_check.returncode != 0 or "A5000" not in gpu_check.stdout:
        pytest.skip("RTX A5000 GPU not available for optional GPU consistency test")

    gpu_start = subprocess.run(
        [str(START_EMBEDDING_SH), "gpu"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if gpu_start.returncode != 0:
        pytest.skip("start_embedding.sh gpu failed")

    gpu_base_url = _discover_embedding_base_url()
    if gpu_base_url is None or not _wait_for_embedding_health(gpu_base_url):
        pytest.skip("GPU embedding-service did not become healthy")

    texts = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[:5]
    cpu_client = create_embedding_client(settings, http_client)
    cpu_vectors = (await cpu_client.embed(texts)).vectors

    gpu_settings = settings.model_copy(
        update={
            "embedding_effective_runtime_mode": "gpu",
            "embedding_client_total_token_budget": settings.embedding.gpu.client_total_token_budget,
            "embedding": settings.embedding.model_copy(update={"base_url": gpu_base_url}),
        }
    )
    gpu_client = create_embedding_client(gpu_settings, http_client)
    gpu_vectors = (await gpu_client.embed(texts)).vectors

    minimum_similarity = settings.embedding.consistency.minimum_cosine_similarity
    for cpu_vector, gpu_vector in zip(cpu_vectors, gpu_vectors, strict=True):
        dot = sum(left * right for left, right in zip(cpu_vector, gpu_vector, strict=True))
        assert dot >= minimum_similarity

    # Restore CPU embedding for subsequent tests in the same session.
    subprocess.run([str(START_EMBEDDING_SH), "cpu"], cwd=REPO_ROOT, check=False)
