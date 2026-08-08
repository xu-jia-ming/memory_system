"""Contract tests: compose.sh config output (§3.3, §7.6)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from memory_system.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

APP_SERVICES = (
    "memory-api",
    "memory-extraction-worker",
    "memory-consolidation-worker",
)

INFRA_SERVICES_NONE = (
    "redis",
    "mongodb",
    "kafka",
    "neo4j",
    "elasticsearch",
    "init-infra",
)

REQUIRED_ENV_EXPLICIT = frozenset(
    {
        "EMBEDDING_EFFECTIVE_RUNTIME_MODE",
        "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    }
)

NO_PROXY_LITERAL = (
    "localhost,127.0.0.1,redis,mongodb,kafka,neo4j,elasticsearch,"
    "embedding-service,memory-api,memory-extraction-worker,memory-consolidation-worker"
)


@pytest.fixture(scope="module", autouse=True)
def ensure_dotenv() -> None:
    """Contract tests need .env for env_file references and variable interpolation."""
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def _run_compose_config(*args: str) -> dict[str, Any]:
    cmd = [str(COMPOSE_SH), *args, "config", "--format", "json"]
    env = os.environ.copy()
    # Provide embedding interpolation when not using --embedding=current runtime file.
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env.setdefault("PROXY__HTTP_URL", "http://host.docker.internal:7890")
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    parsed: dict[str, Any] = json.loads(result.stdout)
    return parsed


def _service_env_union(service: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    env_block = service.get("environment")
    if isinstance(env_block, dict):
        keys.update(env_block.keys())
    elif isinstance(env_block, list):
        for entry in env_block:
            if isinstance(entry, str) and "=" in entry:
                keys.add(entry.split("=", 1)[0])
    return keys


def _grace_period_seconds(value: str | None) -> int | None:
    if value is None:
        return None
    if value.endswith("s") and value[:-1].isdigit():
        return int(value[:-1])
    if value.endswith("m0s"):
        return int(value[:-3]) * 60
    if value.endswith("m"):
        return int(value[:-1]) * 60
    return None


def _assert_app_env_injection(service_name: str, service: dict[str, Any]) -> None:
    env_files = service.get("env_file") or []
    # compose config --format json resolves env_file into environment; either is valid.
    if ".env" not in env_files:
        env_block_preview = service.get("environment") or {}
        if isinstance(env_block_preview, dict):
            assert "APP_ENV" in env_block_preview, (
                f"{service_name}: .env keys not resolved (missing APP_ENV in environment)"
            )

    env_block = service.get("environment") or {}
    if isinstance(env_block, list):
        env_dict = {}
        for item in env_block:
            if isinstance(item, str) and "=" in item:
                k, v = item.split("=", 1)
                env_dict[k] = v
        env_block = env_dict

    for key in REQUIRED_ENV_EXPLICIT:
        assert key in env_block, f"{service_name}: missing environment.{key}"

    assert env_block.get("NO_PROXY") == NO_PROXY_LITERAL

    covered = _service_env_union(service)
    required = set(Settings.required_env_keys())
    missing = required - covered
    assert not missing, f"{service_name}: missing required env keys: {sorted(missing)}"


def test_compose_none_config_includes_core_services() -> None:
    config = _run_compose_config("--embedding=none")
    services = config.get("services", {})
    expected = set(APP_SERVICES) | set(INFRA_SERVICES_NONE)
    for name in expected:
        assert name in services, f"missing service {name} in --embedding=none config"
    assert "embedding-service" not in services


def test_compose_cpu_config_includes_embedding_service() -> None:
    config = _run_compose_config("--embedding=cpu")
    services = config.get("services", {})
    assert "embedding-service" in services
    emb = services["embedding-service"]
    image = emb.get("image", "")
    assert "TEI_CPU_IMAGE" in image or "text-embeddings-inference" in image
    env = emb.get("environment") or {}
    if isinstance(env, list):
        env = {k: v for item in env if "=" in item for k, v in [item.split("=", 1)]}
    assert env.get("AUTO_TRUNCATE") == "false"


def test_compose_gpu_config_has_gpu_reservation_and_batch_tokens() -> None:
    config = _run_compose_config("--embedding=gpu")
    emb = config["services"]["embedding-service"]
    deploy = emb.get("deploy", {})
    devices = deploy.get("resources", {}).get("reservations", {}).get("devices", [])
    assert any(d.get("capabilities") == ["gpu"] for d in devices)
    command = emb.get("command") or []
    assert "16384" in command


def test_app_services_stop_grace_periods() -> None:
    config = _run_compose_config("--embedding=none")
    services = config["services"]
    api_grace = _grace_period_seconds(services["memory-api"].get("stop_grace_period"))
    ext_grace = _grace_period_seconds(
        services["memory-extraction-worker"].get("stop_grace_period")
    )
    con_grace = _grace_period_seconds(
        services["memory-consolidation-worker"].get("stop_grace_period")
    )
    assert api_grace == 480
    assert ext_grace == 300
    assert con_grace == 300


def test_app_services_required_env_keys_coverage() -> None:
    config = _run_compose_config("--embedding=cpu")
    services = config["services"]
    for name in APP_SERVICES:
        _assert_app_env_injection(name, services[name])


def test_init_infra_command_and_one_shot() -> None:
    config = _run_compose_config("--embedding=none")
    init_infra = config["services"]["init-infra"]
    command = init_infra.get("command")
    if isinstance(command, str):
        assert "scripts.migrate" in command
    else:
        joined = " ".join(command) if isinstance(command, list) else str(command)
        assert "scripts.migrate" in joined
    assert init_infra.get("restart") == "no"


def test_init_infra_app_env_injection_aligned_with_apps() -> None:
    """DEV-004: init-infra must receive the same x-app-env as application services."""
    config = _run_compose_config("--embedding=cpu")
    services = config["services"]
    _assert_app_env_injection("init-infra", services["init-infra"])
    for name in APP_SERVICES:
        _assert_app_env_injection(name, services[name])


def test_test_stack_project_name_and_volume_isolation() -> None:
    config = _run_compose_config("--stack=test", "--embedding=none")
    assert config.get("name") == "memory-system-test"
    volumes = config.get("volumes", {})
    assert "redis-data-test" in volumes
    assert "redis-data" not in volumes or "redis-data-test" in volumes


def test_test_stack_file_order_with_cpu_embedding() -> None:
    """compose.sh must load test override (not dev override) plus embedding last."""
    result = subprocess.run(
        [str(COMPOSE_SH), "--stack=test", "--embedding=cpu", "config", "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "EMBEDDING_EFFECTIVE_RUNTIME_MODE": "cpu",
            "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET": "4096",
            "PROXY__HTTP_URL": "http://host.docker.internal:7890",
        },
        check=False,
    )
    assert result.returncode == 0, result.stderr
    config: dict[str, Any] = json.loads(result.stdout)
    assert config["name"] == "memory-system-test"
    assert "embedding-service" in config["services"]
    redis = config["services"]["redis"]
    vol_entries = redis.get("volumes", [])
    vol_sources = []
    for v in vol_entries:
        if isinstance(v, str):
            vol_sources.append(v.split(":")[0])
        elif isinstance(v, dict):
            vol_sources.append(str(v.get("source", "")))
    assert any("redis-data-test" in s for s in vol_sources)
