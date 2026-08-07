"""Unit tests: versions.env and versions.lock.env contracts (§7.1, §7.2)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_ENV = REPO_ROOT / "versions.env"
VERSIONS_LOCK_ENV = REPO_ROOT / "versions.lock.env"

EXPECTED_VERSIONS_ENV_KEYS = {
    "PYTHON_IMAGE": "python:3.12.13-slim-bookworm",
    "REDIS_IMAGE": "redis:8.6.5",
    "MONGODB_IMAGE": "mongo:8.0.28",
    "KAFKA_IMAGE": "apache/kafka:4.3.1",
    "NEO4J_IMAGE": "neo4j:5.26.28-community",
    "ELASTICSEARCH_IMAGE": "docker.elastic.co/elasticsearch/elasticsearch:9.4.4",
    "TEI_EXPECTED_VERSION": "1.9.3",
    "TEI_CPU_IMAGE_SOURCE": "ghcr.io/huggingface/text-embeddings-inference:cpu-1.9",
    "TEI_GPU_IMAGE_SOURCE": "ghcr.io/huggingface/text-embeddings-inference:86-1.9",
    "EMBEDDING_MODEL_ID": "BAAI/bge-m3",
    "EMBEDDING_MODEL_REVISION": "57aacf8560157b7c1d4f771ce1a199877aeeec74",
}

SHA256_DIGEST_RE = re.compile(
    r"^ghcr\.io/huggingface/text-embeddings-inference:(cpu-1\.9|86-1\.9)@sha256:[a-f0-9]{64}$"
)


def _parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def test_versions_env_contains_all_required_keys_and_tags() -> None:
    assert VERSIONS_ENV.is_file(), "versions.env must exist"
    parsed = _parse_env_file(VERSIONS_ENV)
    for key, expected in EXPECTED_VERSIONS_ENV_KEYS.items():
        assert key in parsed, f"missing key {key}"
        assert parsed[key] == expected, f"{key}: expected {expected!r}, got {parsed[key]!r}"


def test_versions_lock_env_tei_images_have_sha256_digest() -> None:
    assert VERSIONS_LOCK_ENV.is_file(), "versions.lock.env must exist"
    parsed = _parse_env_file(VERSIONS_LOCK_ENV)
    for var in ("TEI_CPU_IMAGE", "TEI_GPU_IMAGE"):
        assert var in parsed, f"missing {var}"
        value = parsed[var]
        assert SHA256_DIGEST_RE.match(value), f"{var} invalid digest format: {value!r}"
        assert not value.endswith("@sha256:" + "0" * 64), f"{var} has placeholder digest"


def test_versions_env_does_not_contain_runtime_embedding_keys() -> None:
    parsed = _parse_env_file(VERSIONS_ENV)
    forbidden = {"EMBEDDING_EFFECTIVE_RUNTIME_MODE", "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET"}
    assert not (forbidden & set(parsed)), "versions.env must not define runtime embedding keys"
