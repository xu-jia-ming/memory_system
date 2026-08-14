"""OPS-003 blank-environment bootstrap integration (I-OPS3-01 / INJ-OPS3-01).

BLANK-ENV-001: ONLY ``./scripts/compose.sh --stack=test --embedding=none``.
Embedding mode locked to ``none`` (no TEI pull; embedding readiness is non-blocking).
NEVER ``--stack=dev``; NEVER read production secrets; NEVER call ``start_embedding.sh``.

INT-SKIP-001: Docker daemon unavailable → module-level skip at collection.
Stack up but infra health or readiness poll timeout → hard fail (no per-test skip).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

TEST_PROJECT = "memory-system-test"
API_CONTAINER = "memory-system-api-test"
EMBEDDING_MODE = "none"

INFRA_SERVICES = ("redis", "mongodb", "kafka", "neo4j", "elasticsearch")
TEST_VOLUME_MARKERS = (
    "redis-data-test",
    "mongodb-data-test",
    "kafka-data-test",
    "neo4j-data-test",
    "elasticsearch-data-test",
)

SENSITIVE_URI_MARKERS = (
    "mongodb://",
    "redis://",
    "neo4j://",
    "neo4j+s://",
    "sk-",
    "password",
    "api_key",
)

HEALTH_POLL_SECONDS = 180.0
READY_POLL_SECONDS = 180.0


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


if not _docker_available():
    pytestmark = [
        pytest.mark.skip(reason="Docker not available (INT-SKIP-001)"),
    ]
else:
    pytestmark = [pytest.mark.usefixtures("integration_allow_stack_destroy")]


def _compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env["PROXY__HTTP_URL"] = ""
    return env


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [
        str(COMPOSE_SH),
        "--stack=test",
        f"--embedding={EMBEDDING_MODE}",
        *args,
    ]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_compose_env(),
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"compose failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _ensure_dotenv() -> None:
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def _assert_test_isolation() -> None:
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT, (
        f"fail-closed: expected project {TEST_PROJECT!r}, got {config.get('name')!r}"
    )
    volumes = config.get("volumes") or {}
    for marker in TEST_VOLUME_MARKERS:
        assert marker in volumes, f"fail-closed: missing isolated volume {marker!r}"
    for bad in ("mongodb-data", "elasticsearch-data", "kafka-data", "neo4j-data", "redis-data"):
        if bad in volumes and f"{bad}-test" not in volumes:
            raise AssertionError(f"fail-closed: development volume {bad!r} without test twin")


def _parse_compose_ps_rows(stdout: str) -> list[dict[str, Any]]:
    text = stdout.strip()
    if not text:
        return []
    if text.startswith("["):
        rows: list[dict[str, Any]] = json.loads(text)
        return rows
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _wait_infra_healthy(deadline_seconds: float = HEALTH_POLL_SECONDS) -> None:
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        ps = _compose("ps", "--format", "json", check=False)
        if ps.returncode != 0:
            time.sleep(3)
            continue
        healthy_services: set[str] = set()
        for row in _parse_compose_ps_rows(ps.stdout):
            svc = row.get("Service")
            health = str(row.get("Health", "")).lower()
            state = str(row.get("State", "")).lower()
            ok = health == "healthy" or (not health and state == "running")
            if svc in INFRA_SERVICES and ok:
                healthy_services.add(str(svc))
        if set(INFRA_SERVICES).issubset(healthy_services):
            return
        time.sleep(3)
    ps_tail = _compose("ps", check=False)
    pytest.fail(
        f"Test infra did not become healthy within {deadline_seconds}s; "
        f"ps:\n{ps_tail.stdout}\n{ps_tail.stderr}"
    )


def _container_ip(name: str) -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


def _memory_api_base_url() -> str:
    config: dict[str, Any] = json.loads(_compose("config", "--format", "json").stdout)
    service = config.get("services", {}).get("memory-api", {})
    ports = service.get("ports") or []
    for entry in ports:
        if isinstance(entry, str):
            # 127.0.0.1:8000:8000 or 8000:8000
            host_port = entry.rsplit(":", 2)[0] if entry.count(":") >= 2 else entry.split(":")[0]
            if host_port.rsplit(":", 1)[-1].isdigit():
                port = host_port.rsplit(":", 1)[-1]
            elif entry.split(":")[0].isdigit():
                port = entry.split(":")[0]
            else:
                continue
            return f"http://127.0.0.1:{port}"
        if isinstance(entry, dict):
            published = entry.get("published")
            if published:
                return f"http://127.0.0.1:{published}"
    api_ip = _container_ip(API_CONTAINER)
    if api_ip:
        return f"http://{api_ip}:8000"
    pytest.fail("memory-api has no published port and container IP unavailable")


def _run_init_infra() -> subprocess.CompletedProcess[str]:
    return _compose("run", "--rm", "init-infra", check=False)


def _docker_exec(container: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", container, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _poll_readiness(
    base_url: str,
    *,
    expect_ready: bool,
    deadline_seconds: float = READY_POLL_SECONDS,
) -> dict[str, Any]:
    deadline = time.time() + deadline_seconds
    last_status: int | None = None
    last_payload: dict[str, Any] | None = None
    last_error: str | None = None
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        while time.time() < deadline:
            try:
                response = client.get("/health/ready")
                last_status = response.status_code
                if response.status_code in {200, 503}:
                    last_payload = response.json()
                    status = last_payload.get("status")
                    migrations = last_payload.get("checks", {}).get("migrations")
                    if expect_ready:
                        if (
                            response.status_code == 200
                            and status == "ready"
                            and migrations == "ready"
                        ):
                            return last_payload
                    else:
                        not_ready = migrations == "not_ready"
                        status_bad = status != "ready"
                        http_503 = response.status_code == 503
                        if not_ready or status_bad or http_503:
                            return last_payload
                else:
                    last_error = response.text[:500]
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(2)
    logs = subprocess.run(
        ["docker", "logs", API_CONTAINER],
        capture_output=True,
        text=True,
        check=False,
    )
    log_tail = (logs.stdout + logs.stderr)[-1500:]
    pytest.fail(
        f"readiness poll failed at {base_url} within {deadline_seconds}s "
        f"(expect_ready={expect_ready}); last_status={last_status!r} "
        f"last_payload={last_payload!r} last_error={last_error!r}; "
        f"container_logs_tail={log_tail!r}"
    )


def _assert_readiness_payload_safe(payload: dict[str, Any]) -> None:
    checks = payload.get("checks", {})
    assert isinstance(checks, dict)
    for name, value in checks.items():
        assert value in {"ready", "not_ready"}, f"unexpected check value for {name}: {value!r}"
    serialized = json.dumps(payload).lower()
    for marker in SENSITIVE_URI_MARKERS:
        assert marker not in serialized, f"readiness payload leaks sensitive marker {marker!r}"


@pytest.fixture(scope="module")
def blank_bootstrap_stack() -> Iterator[str]:
    _ensure_dotenv()
    _assert_test_isolation()
    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "--build", *INFRA_SERVICES, check=False)
    if up.returncode != 0:
        pytest.fail(
            f"Unable to start compose test infra (exit {up.returncode}): "
            f"{up.stderr[-800:] or up.stdout[-800:]}"
        )
    _wait_infra_healthy()

    first = _run_init_infra()
    assert first.returncode == 0, first.stderr or first.stdout

    second = _run_init_infra()
    assert second.returncode == 0, second.stderr or second.stdout

    mongo = _docker_exec(
        "memory-system-mongodb-test",
        "mongosh",
        "--quiet",
        "memory_system",
        "--eval",
        "db.infra_schema_migrations.countDocuments({})",
    )
    assert mongo.returncode == 0, mongo.stderr
    record_count = int(mongo.stdout.strip())
    assert record_count == 4

    third = _run_init_infra()
    assert third.returncode == 0, third.stderr or third.stdout
    mongo2 = _docker_exec(
        "memory-system-mongodb-test",
        "mongosh",
        "--quiet",
        "memory_system",
        "--eval",
        "db.infra_schema_migrations.countDocuments({})",
    )
    assert mongo2.returncode == 0
    assert int(mongo2.stdout.strip()) == record_count

    apps_up = _compose(
        "up",
        "-d",
        "memory-api",
        "memory-extraction-worker",
        "memory-consolidation-worker",
        check=False,
    )
    assert apps_up.returncode == 0, apps_up.stderr or apps_up.stdout

    deadline = time.time() + 120
    while time.time() < deadline:
        if _container_ip(API_CONTAINER):
            break
        time.sleep(2)
    else:
        pytest.fail("memory-api container did not appear within 120s")

    base_url = _memory_api_base_url()
    payload = _poll_readiness(base_url, expect_ready=True)
    _assert_readiness_payload_safe(payload)

    yield base_url

    _compose("down", "-v", check=False)


def test_blank_environment_full_bootstrap_readiness(blank_bootstrap_stack: str) -> None:
    """I-OPS3-01: infra → migrate×2 → three apps → /health/ready ready."""
    payload = _poll_readiness(blank_bootstrap_stack, expect_ready=True, deadline_seconds=30)
    assert payload["status"] == "ready"
    assert payload["checks"]["migrations"] == "ready"
    for blocking in ("redis", "mongodb", "neo4j", "elasticsearch", "kafka_producer"):
        assert payload["checks"].get(blocking) == "ready"


def test_readiness_payload_contains_no_sensitive_uris(blank_bootstrap_stack: str) -> None:
    """I-OPS3-02: OPS-002 regression — checks values only ready/not_ready, no URI leaks."""
    with httpx.Client(base_url=blank_bootstrap_stack, timeout=10.0) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    _assert_readiness_payload_safe(response.json())


@pytest.fixture(scope="module")
def migrate_not_ready_stack() -> Iterator[None]:
    _ensure_dotenv()
    _assert_test_isolation()
    _compose("down", "-v", check=False)
    up = _compose("up", "-d", "--build", *INFRA_SERVICES, check=False)
    if up.returncode != 0:
        pytest.fail(f"infra up failed: {up.stderr[-500:]}")
    _wait_infra_healthy()

    api_up = _compose("up", "-d", "memory-api", check=False)
    assert api_up.returncode == 0, api_up.stderr or api_up.stdout

    deadline = time.time() + 120
    while time.time() < deadline:
        if _container_ip(API_CONTAINER):
            break
        time.sleep(2)
    else:
        pytest.fail("memory-api container did not appear within 120s")

    yield

    _compose("down", "-v", check=False)


def test_readiness_migrations_not_ready_before_init_infra(migrate_not_ready_stack: None) -> None:
    """INJ-OPS3-01: memory-api before migrate → migrations not_ready or HTTP 503."""
    base_url = _memory_api_base_url()
    payload = _poll_readiness(base_url, expect_ready=False)
    assert payload["checks"].get("migrations") == "not_ready" or payload.get("status") != "ready"
    _assert_readiness_payload_safe(payload)
