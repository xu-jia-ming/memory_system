"""Integration test session hooks (shared compose stack + CI skip policy)."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from typing import Any

import pytest
from tests.integration.support.compose_stack import (
    docker_available,
    run_init_infra_once,
    shared_stack_enabled,
    teardown_session_stack,
)

# Opt-in / environment-specific skips allowed in CI integration job.
_ALLOWED_SKIP_SUBSTRINGS: tuple[str, ...] = (
    "EXT002_MONGO_TEST_URI is not configured",
    "EXT002_MONGO_TEST_URI must include a database",
    "Set RUN_SILICONFLOW_EMBEDDING_INTEGRATION=1",
    "Set RUN_COMPRESSION_LLM_INTEGRATION=1",
    "Preflight integration requires Linux",
    "Preflight cpu mode hard-failed",
    "NVIDIA GPU present",
    "Host passed cpu preflight despite gpu runtime env",
    "memory-api not published on host:8000",
    "memory-api endpoint unavailable",
)

_FORBIDDEN_SKIP_SUBSTRINGS_WHEN_DOCKER: tuple[str, ...] = (
    "Docker not available",
    "did not become ready in time",
    "Could not resolve",
    "Unable to start",
    "init-infra migration failed",
    "ping failed",
    "Elasticsearch ping failed",
    "connectivity failed",
    "Test stack isolation not confirmed",
    "Unable to ensure Kafka topic",
    "Stack not ready",
    "Redis/Mongo not ready",
    "Test stack did not become ready",
)


def _skip_reason(report: pytest.TestReport) -> str:
    longrepr = report.longrepr
    if longrepr is None:
        return ""
    return str(longrepr)


def _is_allowed_skip(reason: str) -> bool:
    return any(fragment in reason for fragment in _ALLOWED_SKIP_SUBSTRINGS)


def _is_forbidden_infra_skip(reason: str) -> bool:
    if _is_allowed_skip(reason):
        return False
    return any(fragment in reason for fragment in _FORBIDDEN_SKIP_SUBSTRINGS_WHEN_DOCKER)


@pytest.fixture(scope="session", autouse=True)
def _integration_shared_compose_stack() -> Iterator[None]:
    if not shared_stack_enabled():
        yield
        return

    real_run = subprocess.run

    def guarded_run(
        cmd: Any,
        *args: Any,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[Any]:
        argv = cmd if isinstance(cmd, list) else []
        joined = " ".join(str(part) for part in argv)
        if "compose.sh" in joined:
            if (
                "down" in argv
                and "-v" in argv
                and os.environ.get("INTEGRATION_ALLOW_DESTROY") != "1"
            ):
                return subprocess.CompletedProcess(argv, 0, "", "")
            if "run" in argv and "init-infra" in joined:
                run_init_infra_once()
                return subprocess.CompletedProcess(argv, 0, "", "")
        return real_run(cmd, *args, **kwargs)

    subprocess.run = guarded_run  # type: ignore[assignment]
    try:
        yield
    finally:
        subprocess.run = real_run  # type: ignore[assignment]
        if os.environ.get("INTEGRATION_ALLOW_DESTROY") != "1":
            teardown_session_stack()


@pytest.fixture
def integration_allow_stack_destroy() -> Iterator[None]:
    """Allow isolated modules (OPS-003 / migrate) to tear down shared volumes."""
    os.environ["INTEGRATION_ALLOW_DESTROY"] = "1"
    try:
        yield
    finally:
        os.environ.pop("INTEGRATION_ALLOW_DESTROY", None)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run stack-destructive isolated modules after the shared-stack suite."""
    destructive: list[pytest.Item] = []
    normal: list[pytest.Item] = []
    for item in items:
        nodeid = item.nodeid
        if "test_ops003_blank_environment_bootstrap" in nodeid or "test_migrate_infra" in nodeid:
            destructive.append(item)
        else:
            normal.append(item)
    items[:] = normal + destructive


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Any:
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.skipped:
        return
    if os.environ.get("PYTEST_INTEGRATION_STRICT_SKIPS", "").strip() != "1":
        return
    if not docker_available():
        return
    reason = _skip_reason(report)
    if _is_forbidden_infra_skip(reason):
        pytest.fail(
            "Integration test skipped due to infra/setup failure in CI "
            f"(forbidden skip): {reason}",
            pytrace=False,
        )
