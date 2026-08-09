"""Contract tests for Preflight Check 13b TEI CPU runtime probe (DEV-003-002)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_SH = REPO_ROOT / "scripts" / "preflight" / "check_linux_host.sh"


def test_preflight_script_documents_check_13b() -> None:
    text = PREFLIGHT_SH.read_text(encoding="utf-8")
    assert "Check 13b" in text
    assert "TEI CPU runtime probe" in text
    assert "Check 13a" in text


def test_preflight_skip_tei_probe_env_skips_check_13b() -> None:
    result = subprocess.run(
        ["bash", str(PREFLIGHT_SH), "--mode=cpu"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={
            **__import__("os").environ,
            "PREFLIGHT_SKIP_TEI_PROBE": "1",
        },
    )
    output = result.stdout + result.stderr
    assert "Check 13b" in output
    assert "PREFLIGHT_SKIP_TEI_PROBE=1" in output


def test_preflight_gpu_mode_skips_check_13b() -> None:
    if not Path("/usr/bin/nvidia-smi").exists():
        pytest.skip("nvidia-smi not present")
    result = subprocess.run(
        ["bash", str(PREFLIGHT_SH), "--mode=gpu"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if "Check 13b" in output:
        assert "deferred" in output.lower() or "SKIP" in output
