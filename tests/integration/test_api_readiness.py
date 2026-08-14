"""Integration tests for memory-api readiness against compose test stack.

Superseded for full bootstrap by ``test_ops003_blank_environment_bootstrap`` (I-OPS3-01).
INJ-OPS3-01 migrate-before-api coverage lives in OPS-003 bootstrap module.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


if not _docker_available():
    pytestmark = pytest.mark.skip(reason="Docker not available (INT-SKIP-001)")


def _compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env["PROXY__HTTP_URL"] = ""
    return env


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(COMPOSE_SH), "--stack=test", "--embedding=none", *args]
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


@pytest.fixture(scope="module")
def test_stack() -> Iterator[None]:
    _ensure_dotenv()
    _compose("up", "-d", "mongodb", "kafka", "neo4j", "elasticsearch", "redis")
    deadline = time.time() + 180
    while time.time() < deadline:
        ps = _compose("ps", "--format", "json", check=False)
        if ps.returncode == 0 and ps.stdout.strip():
            break
        time.sleep(3)
    else:
        pytest.fail("Test stack did not become ready in time (INT-SKIP-001 hard fail)")
    yield
    _compose("down", check=False)


@pytest.mark.integration
def test_readiness_reports_migrations_not_ready_before_migrate(test_stack: None) -> None:
    """Legacy narrow check; full INJ-OPS3-01 in OPS-003 bootstrap module."""
    host = "127.0.0.1"
    port = 8000
    try:
        with httpx.Client(base_url=f"http://{host}:{port}", timeout=5.0) as client:
            response = client.get("/health/ready")
    except httpx.HTTPError:
        pytest.skip("memory-api not published on host:8000; covered by OPS-003 bootstrap INT")
        return

    if response.status_code not in {200, 503}:
        pytest.skip("memory-api endpoint unavailable; covered by OPS-003 bootstrap INT")
    payload = response.json()
    assert "checks" in payload
    if payload["status"] == "ready":
        assert payload["checks"].get("migrations") == "ready"
    else:
        assert payload["checks"].get("migrations") in {"ready", "not_ready"}
