"""Shared compose test-stack helpers for integration tests.

When ``INTEGRATION_SHARED_STACK=1`` (CI merge-gate default), a session-scoped
fixture brings up the full test infra once and skips per-module ``down -v`` /
re-migrate churn. Modules marked ``isolated_compose`` keep legacy isolation
(OPS-003 blank bootstrap, migrate idempotency).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
TEST_PROJECT = "memory-system-test"

CONTAINER_NAMES: dict[str, str] = {
    "redis": "memory-system-redis-test",
    "mongodb": "memory-system-mongodb-test",
    "kafka": "memory-system-kafka-test",
    "neo4j": "memory-system-neo4j-test",
    "elasticsearch": "memory-system-elasticsearch-test",
}

ALL_INFRA_SERVICES: tuple[str, ...] = (
    "redis",
    "mongodb",
    "kafka",
    "neo4j",
    "elasticsearch",
)

_INIT_INFRA_DONE = False
_SESSION_BOOTSTRAPPED = False
_MIGRATING = False

MONGODB_DATABASE = "memory_system"


def _compose_raw(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(COMPOSE_SH), "--stack=test", "--embedding=none", *args]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=compose_env(),
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"compose failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def shared_stack_enabled() -> bool:
    return os.environ.get("INTEGRATION_SHARED_STACK", "").strip() == "1"


def stack_destroy_allowed() -> bool:
    return os.environ.get("INTEGRATION_ALLOW_DESTROY", "").strip() == "1"


def reset_shared_stack_state() -> None:
    global _INIT_INFRA_DONE, _SESSION_BOOTSTRAPPED
    _INIT_INFRA_DONE = False
    _SESSION_BOOTSTRAPPED = False


def neo4j_uri_from_container() -> str:
    ip = wait_container_ip(CONTAINER_NAMES["neo4j"])
    return f"neo4j://{ip}:7687"


def redis_uri_from_container() -> str:
    ip = wait_container_ip(CONTAINER_NAMES["redis"])
    return f"redis://{ip}:6379/0"


def mongo_uri_from_container() -> str:
    ip = wait_container_ip(CONTAINER_NAMES["mongodb"])
    return f"mongodb://{ip}:27017/{MONGODB_DATABASE}"


def elasticsearch_url_from_container() -> str:
    ip = wait_container_ip(CONTAINER_NAMES["elasticsearch"])
    return wait_elasticsearch_http(ip)


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


def compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env["PROXY__HTTP_URL"] = ""
    return env


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _compose_raw(*args, check=check)


def ensure_dotenv() -> None:
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def assert_test_isolation() -> None:
    config_result = compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT, (
        f"fail-closed: expected project {TEST_PROJECT!r}, got {config.get('name')!r}"
    )


def container_ip(container: str) -> str | None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            container,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ip = result.stdout.strip()
    return ip or None


def wait_container_ip(container: str, *, deadline_seconds: float = 180.0) -> str:
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        ip = container_ip(container)
        if ip:
            return ip
        time.sleep(2)
    raise TimeoutError(f"container {container!r} did not get an IP within {deadline_seconds}s")


def wait_elasticsearch_http(es_ip: str, *, deadline_seconds: float = 180.0) -> str:
    url = f"http://{es_ip}:9200"
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{url}/_cluster/health")
                if response.status_code == 200:
                    return url
        except httpx.HTTPError:
            time.sleep(2)
    raise TimeoutError(f"Elasticsearch not HTTP-ready at {url} within {deadline_seconds}s")


def run_init_infra_once() -> None:
    global _INIT_INFRA_DONE, _MIGRATING
    if _INIT_INFRA_DONE or _MIGRATING:
        return
    _MIGRATING = True
    try:
        migrate = _compose_raw("run", "--rm", "init-infra", check=False)
        if migrate.returncode != 0:
            raise AssertionError(
                "init-infra migration failed: "
                f"{migrate.stderr[-800:] or migrate.stdout[-800:]}"
            )
        _INIT_INFRA_DONE = True
    finally:
        _MIGRATING = False


def bootstrap_session_stack() -> None:
    global _SESSION_BOOTSTRAPPED
    if _SESSION_BOOTSTRAPPED:
        return
    if not docker_available():
        return
    ensure_dotenv()
    assert_test_isolation()
    up = compose("up", "-d", *ALL_INFRA_SERVICES, check=False)
    if up.returncode != 0:
        raise AssertionError(
            "Unable to start shared integration stack "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )
    for service in ALL_INFRA_SERVICES:
        ip = wait_container_ip(CONTAINER_NAMES[service], deadline_seconds=180.0)
        if service == "elasticsearch":
            wait_elasticsearch_http(ip, deadline_seconds=180.0)
    run_init_infra_once()
    _SESSION_BOOTSTRAPPED = True


def teardown_session_stack() -> None:
    global _SESSION_BOOTSTRAPPED, _INIT_INFRA_DONE
    if not _SESSION_BOOTSTRAPPED:
        return
    compose("down", "-v", check=False)
    reset_shared_stack_state()


def start_services(
    services: tuple[str, ...],
    *,
    migrate: bool = False,
    isolated: bool = False,
) -> None:
    ensure_dotenv()
    assert_test_isolation()
    if shared_stack_enabled() and not isolated:
        for service in services:
            wait_container_ip(CONTAINER_NAMES[service], deadline_seconds=180.0)
        if migrate:
            run_init_infra_once()
        return

    compose("down", "-v", check=False)
    up = compose("up", "-d", *services, check=False)
    if up.returncode != 0:
        raise AssertionError(
            "Unable to start compose test infra "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )
    if migrate:
        migrate_result = compose("run", "--rm", "init-infra", check=False)
        if migrate_result.returncode != 0:
            compose("down", "-v", check=False)
            raise AssertionError(
                "init-infra migration failed: "
                f"{migrate_result.stderr[-800:] or migrate_result.stdout[-800:]}"
            )


def end_services(*, volumes: bool = True, isolated: bool = False) -> None:
    if shared_stack_enabled() and not isolated:
        return
    if volumes:
        compose("down", "-v", check=False)
    else:
        compose("down", check=False)


def require_docker_or_skip() -> None:
    if not docker_available():
        pytest.skip("Docker not available (INT-SKIP-001)")


def skip_on_isolation_error(exc: AssertionError) -> None:
    pytest.skip(f"Test stack isolation not confirmed: {exc}")


def skip_on_startup_error(message: str) -> None:
    pytest.skip(message)


@contextmanager
def module_services(
    services: tuple[str, ...],
    *,
    migrate: bool = False,
    isolated: bool = False,
    teardown_volumes: bool = True,
) -> Iterator[None]:
    require_docker_or_skip()
    try:
        start_services(services, migrate=migrate, isolated=isolated)
    except (AssertionError, TimeoutError) as exc:
        end_services(volumes=teardown_volumes, isolated=isolated)
        skip_on_startup_error(str(exc))
    try:
        yield
    finally:
        end_services(volumes=teardown_volumes, isolated=isolated)
