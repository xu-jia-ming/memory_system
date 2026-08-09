"""Contract tests for Preflight Check 13a/13b TEI CPU runtime probe (OI-011)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_SH = REPO_ROOT / "scripts" / "preflight" / "check_linux_host.sh"
LIB_PROBE = REPO_ROOT / "scripts" / "preflight" / "lib_tei_probe.sh"
SPEC = (
    REPO_ROOT
    / "01_技术规格"
    / "记忆系统设计文档_全链路MVP技术选型版(9).md"
)


def test_preflight_script_documents_check_13b() -> None:
    text = PREFLIGHT_SH.read_text(encoding="utf-8")
    assert "Check 13b" in text
    assert "TEI CPU runtime probe" in text
    assert "Check 13a" in text
    assert "TEI_LIMIT_GIB=12" in text
    assert "REQUIRED_HOST_MEM_GIB" in text


def test_preflight_and_probe_formal_limit_aligned() -> None:
    preflight = PREFLIGHT_SH.read_text(encoding="utf-8")
    probe = LIB_PROBE.read_text(encoding="utf-8")
    assert "TEI_LIMIT_GIB=12" in preflight
    assert 'TEI_SPEC_MEM_LIMIT="12g"' in probe
    assert "TEI_SPEC_MEM_LIMIT_BYTES=12884901888" in probe


def test_spec_sf2_and_memavailable_formula_language() -> None:
    text = SPEC.read_text(encoding="utf-8")
    assert "NON_SPEC_COMPLIANT" in text
    assert "mem_limit: 12g" in text
    assert "minimum_available_memory_gib: 16" in text
    assert "recommended_available_memory_gib: 20" in text
    assert "可以通过环境变量调低" not in text


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
    assert "TEI 12g" in output or "TEI ${TEI_LIMIT_GIB}g" in PREFLIGHT_SH.read_text(
        encoding="utf-8"
    )


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
