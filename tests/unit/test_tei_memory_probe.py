"""Unit tests for TEI CPU memory probe helpers (DEV-003-002)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PROBE = REPO_ROOT / "scripts" / "preflight" / "lib_tei_probe.sh"
MEASURE_SH = REPO_ROOT / "scripts" / "diagnostics" / "measure_tei_memory.sh"
LOCK_FILE = REPO_ROOT / "versions.lock.env"


def _bash_expr(expr: str) -> str:
    result = subprocess.run(
        ["bash", "-c", f'source "{LIB_PROBE}"; {expr}'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ("512MiB / 8GiB", "536870912"),
        ("1.5GiB / 8GiB", "1610612736"),
        ("100MB / 8GB", "100000000"),
    ],
)
def test_tei_probe_parse_mem_bytes(usage: str, expected: str) -> None:
    out = _bash_expr(f'tei_probe_parse_mem_bytes "{usage}"')
    assert out == expected


def test_tei_probe_spec_constants() -> None:
    expr = (
        'printf "%s|%s|%s" "${TEI_SPEC_MEM_LIMIT_BYTES}" '
        '"${TEI_MODEL_ID}" "${TEI_DTYPE}"'
    )
    out = _bash_expr(expr)
    limit, model, dtype = out.split("|")
    assert limit == "8589934592"
    assert model == "BAAI/bge-m3"
    assert dtype == "float32"


def test_measure_tei_memory_help_exits_zero() -> None:
    result = subprocess.run(
        ["bash", str(MEASURE_SH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "measure_tei_memory.sh" in result.stdout


def test_tei_probe_write_report_json_oom_fields(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    script = f'''
source "{LIB_PROBE}"
tei_probe_load_image_identity "{REPO_ROOT}" || true
tei_probe_write_report_json \\
  "{output}" "8589934592" "" "" "138" \\
  "false" "true" "137" "false" \\
  "embedding-service" "running" "starting" "8589934592" \\
  "${{TEI_PROBE_TEI_IMAGE:-}}" "${{TEI_PROBE_IMAGE_DIGEST:-}}" "300"
'''
    subprocess.run(["bash", "-c", script], cwd=REPO_ROOT, check=True)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1"
    assert report["spec_mem_limit_bytes"] == 8589934592
    assert report["rss_peak_warmup_bytes"] == 8589934592
    assert report["rss_steady_state_bytes"] is None
    assert report["health_ready"] is False
    assert report["oom_killed"] is True
    assert report["exit_code"] == 137
    assert report["runtime_contract_verdict"] == "SPEC_RUNTIME_CONTRACT_CONFLICT"
    assert report["time_to_ready_sec"] is None
    assert report["time_to_failure_sec"] == 138
    if LOCK_FILE.exists():
        assert report.get("image_digest")


def test_tei_probe_write_report_json_pass_fields(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    script = f'''
source "{LIB_PROBE}"
tei_probe_write_report_json \\
  "{output}" "6000000000" "3000000000" "42" "" \\
  "true" "false" "0" "false" \\
  "embedding-service" "running" "healthy" "8589934592" \\
  "img@sha256:{'a' * 64}" "sha256:{'a' * 64}" "300"
'''
    subprocess.run(["bash", "-c", script], cwd=REPO_ROOT, check=True)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["runtime_contract_verdict"] == "PASS"
    assert report["rss_steady_state_bytes"] == 3000000000
    assert report["time_to_ready_sec"] == 42
    assert report["time_to_failure_sec"] is None
