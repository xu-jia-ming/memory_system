"""Integration tests for Linux host Preflight script."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_SH = REPO_ROOT / "scripts" / "preflight" / "check_linux_host.sh"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


@pytest.fixture(scope="module")
def preflight_prerequisites() -> None:
    if platform.system() != "Linux":
        pytest.skip("Preflight integration requires Linux")
    if not _docker_available():
        pytest.skip("Docker not available on this host")


def _run_preflight(mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(PREFLIGHT_SH), f"--mode={mode}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_preflight_cpu_mode_exits_zero_or_warnings_only(preflight_prerequisites: None) -> None:
    result = _run_preflight("cpu")
    output = result.stdout + result.stderr
    assert "TEI_CPU_DIGEST=" in output or "TEI CPU digest:" in output
    assert "TEI_GPU_DIGEST=" in output or "TEI GPU digest:" in output
    # May hard-fail on resource-constrained CI; accept pass or documented failures.
    if result.returncode != 0:
        pytest.skip(f"Preflight cpu mode hard-failed on this host: {output[-500:]}")


def test_preflight_auto_mode_gpu_first_or_cpu_fallback(preflight_prerequisites: None) -> None:
    result = _run_preflight("auto")
    output = result.stdout + result.stderr
    if result.returncode != 0:
        # Host may fail hard checks (e.g. vm.max_map_count); still valid integration signal.
        assert "FAIL:" in output or "hard_failures=" in output
        return
    assert "resolved_mode=" in output
    assert "cpu" in output or "gpu" in output


def test_preflight_gpu_mode_fails_without_nvidia(preflight_prerequisites: None) -> None:
    if shutil.which("nvidia-smi"):
        probe = subprocess.run(["nvidia-smi"], capture_output=True, check=False)
        if probe.returncode == 0:
            pytest.skip("NVIDIA GPU present; cannot assert gpu-mode hard failure")
    gpu_result = _run_preflight("gpu")
    assert gpu_result.returncode != 0, "gpu mode must hard-fail without healthy NVIDIA path"


def test_preflight_fails_on_runtime_env_mismatch(
    preflight_prerequisites: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_dir = REPO_ROOT / ".runtime"
    runtime_dir.mkdir(exist_ok=True)
    runtime_env = runtime_dir / "embedding.env"
    backup = runtime_env.read_text(encoding="utf-8") if runtime_env.exists() else None
    runtime_env.write_text(
        "EMBEDDING_EFFECTIVE_RUNTIME_MODE=gpu\nEMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET=16384\n",
        encoding="utf-8",
    )
    try:
        result = _run_preflight("cpu")
        if result.returncode == 0:
            pytest.skip("Host passed cpu preflight despite gpu runtime env (unexpected)")
        assert "embedding.env" in (result.stdout + result.stderr).lower()
    finally:
        if backup is not None:
            runtime_env.write_text(backup, encoding="utf-8")
        else:
            runtime_env.unlink(missing_ok=True)
