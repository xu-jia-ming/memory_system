"""Unit tests for TEI CPU memory probe helpers (DEV-003-002 + OI-011)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PROBE = REPO_ROOT / "scripts" / "preflight" / "lib_tei_probe.sh"
MEASURE_SH = REPO_ROOT / "scripts" / "diagnostics" / "measure_tei_memory.sh"
PREFLIGHT_SH = REPO_ROOT / "scripts" / "preflight" / "check_linux_host.sh"
LOCK_FILE = REPO_ROOT / "versions.lock.env"

LIMIT_BYTES = {
    "8g": "8589934592",
    "10g": "10737418240",
    "12g": "12884901888",
    "16g": "17179869184",
}
FORMAL_LIMIT = "12g"


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


@pytest.mark.parametrize("human", ["8g", "10g", "12g", "16g"])
def test_tei_probe_mem_limit_to_bytes(human: str) -> None:
    out = _bash_expr(f'tei_probe_mem_limit_to_bytes "{human}"')
    assert out == LIMIT_BYTES[human]


def test_tei_probe_mem_limit_rejects_illegal() -> None:
    result = subprocess.run(
        ["bash", "-c", f'source "{LIB_PROBE}"; tei_probe_mem_limit_to_bytes "20g"'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_tei_probe_spec_constants_formal_12g() -> None:
    expr = (
        'printf "%s|%s|%s|%s" "${TEI_SPEC_MEM_LIMIT_BYTES}" '
        '"${TEI_SPEC_MEM_LIMIT}" "${TEI_MODEL_ID}" "${TEI_DTYPE}"'
    )
    out = _bash_expr(expr)
    limit, human, model, dtype = out.split("|")
    assert limit == LIMIT_BYTES["12g"]
    assert human == "12g"
    assert model == "BAAI/bge-m3"
    assert dtype == "float32"


@pytest.mark.parametrize("human", ["10g", "12g", "16g"])
def test_tei_probe_build_compose_args_order_and_overlay(human: str) -> None:
    expr = (
        f'tei_probe_build_compose_args "{REPO_ROOT}" "{human}"; '
        'printf "%s\\n" "${TEI_PROBE_COMPOSE_ARGS[@]}"'
    )
    lines = _bash_expr(expr).splitlines()
    assert lines[0:6] == [
        "-f",
        str(REPO_ROOT / "compose.yaml"),
        "-f",
        str(REPO_ROOT / "compose.override.yaml"),
        "-f",
        str(REPO_ROOT / "compose.embedding.cpu.yaml"),
    ]
    joined = " ".join(lines)
    assert "scripts/compose.sh" not in joined
    assert str(REPO_ROOT / ".env") in joined
    if human == FORMAL_LIMIT:
        assert "mem10g" not in joined
        assert "mem16g" not in joined
    else:
        overlay = REPO_ROOT / f"compose.embedding.cpu.mem{human}.yaml"
        assert str(overlay) in joined
        assert overlay.is_file()


def test_tei_probe_build_compose_args_rejects_8g_after_12g_bake() -> None:
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{LIB_PROBE}"; tei_probe_build_compose_args "{REPO_ROOT}" "8g"',
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_measure_tei_memory_help_mentions_bans() -> None:
    result = subprocess.run(
        ["bash", str(MEASURE_SH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "measure_tei_memory.sh" in result.stdout
    assert "--mem-limit=" in result.stdout
    assert "compose.sh" in result.stdout
    assert "docker update" in result.stdout


def test_measure_tei_memory_rejects_illegal_mem_limit() -> None:
    result = subprocess.run(
        ["bash", str(MEASURE_SH), "--mem-limit=9g"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_check13a_and_check8_formula_constants() -> None:
    text = PREFLIGHT_SH.read_text(encoding="utf-8")
    assert "TEI_LIMIT_GIB=12" in text
    assert "REQUIRED_HOST_MEM_GIB=$((ES_LIMIT_GIB + TEI_LIMIT_GIB))" in text
    assert "CPU_MIN_GIB=$((12 + TEI_LIMIT_GIB - 8))" in text
    assert "CPU_REC_GIB=$((16 + TEI_LIMIT_GIB - 8))" in text
    out = subprocess.run(
        [
            "bash",
            "-c",
            (
                "TEI_LIMIT_GIB=12; ES_LIMIT_GIB=2; "
                "REQUIRED_HOST_MEM_GIB=$((ES_LIMIT_GIB + TEI_LIMIT_GIB)); "
                "CPU_MIN_GIB=$((12 + TEI_LIMIT_GIB - 8)); "
                "CPU_REC_GIB=$((16 + TEI_LIMIT_GIB - 8)); "
                'printf "%s|%s|%s" "$REQUIRED_HOST_MEM_GIB" "$CPU_MIN_GIB" "$CPU_REC_GIB"'
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "14|16|20"


def test_tei_probe_write_report_json_oom_fields(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    script = f'''
source "{LIB_PROBE}"
tei_probe_load_image_identity "{REPO_ROOT}" || true
tei_probe_set_requested_limit "8g"
TEI_PROBE_RUN_ID="unit-oom-8g"
tei_probe_write_report_json \\
  "{output}" "8589934592" "" "" "138" \\
  "false" "true" "137" "false" \\
  "embedding-service" "running" "starting" "8589934592" \\
  "${{TEI_PROBE_TEI_IMAGE:-}}" "${{TEI_PROBE_IMAGE_DIGEST:-}}" "300"
'''
    subprocess.run(["bash", "-c", script], cwd=REPO_ROOT, check=True)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1"
    assert report["spec_mem_limit_bytes"] == int(LIMIT_BYTES["12g"])
    assert report["requested_limit"] == "8g"
    assert report["requested_mem_limit_bytes"] == 8589934592
    assert report["rss_peak_warmup_bytes"] == 8589934592
    assert report["rss_steady_state_bytes"] is None
    assert report["health_ready"] is False
    assert report["oom_killed"] is True
    assert report["exit_code"] == 137
    assert report["runtime_contract_verdict"] == "SPEC_RUNTIME_CONTRACT_CONFLICT"
    assert report["time_to_ready_sec"] is None
    assert report["time_to_failure_sec"] == 138
    assert report["run_id"] == "unit-oom-8g"
    assert report["clean_create"] is True
    assert report["invalidation_reason"] is None
    if LOCK_FILE.exists():
        assert report.get("image_digest")


def test_tei_probe_write_report_json_pass_fields(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    script = f'''
source "{LIB_PROBE}"
tei_probe_set_requested_limit "12g"
TEI_PROBE_RUN_ID="unit-pass-12g"
tei_probe_write_report_json \\
  "{output}" "6000000000" "3000000000" "42" "" \\
  "true" "false" "0" "false" \\
  "embedding-service" "running" "healthy" "12884901888" \\
  "img@sha256:{'a' * 64}" "sha256:{'a' * 64}" "300"
'''
    subprocess.run(["bash", "-c", script], cwd=REPO_ROOT, check=True)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["runtime_contract_verdict"] == "PASS"
    assert report["requested_limit"] == "12g"
    assert report["spec_mem_limit_bytes"] == int(LIMIT_BYTES["12g"])
    assert report["requested_mem_limit_bytes"] == 12884901888
    assert report["container_mem_limit_bytes"] == 12884901888
    assert report["rss_steady_state_bytes"] == 3000000000
    assert report["time_to_ready_sec"] == 42
    assert report["time_to_failure_sec"] is None


@pytest.mark.parametrize(
    ("peak", "limit", "health", "oom", "exit_code", "steady", "ready", "expected"),
    [
        ("6000000000", "12884901888", "true", "false", "0", "3000000000", "30", "VIABLE"),
        ("12884901888", "12884901888", "true", "false", "0", "3000000000", "30", "NON_VIABLE"),
        ("7000000000", "8589934592", "false", "true", "137", "", "", "NON_VIABLE"),
        ("5000000000", "10737418240", "false", "false", "124", "", "", "NON_VIABLE"),
    ],
)
def test_tei_probe_classify_tier_run_sf3(
    peak: str,
    limit: str,
    health: str,
    oom: str,
    exit_code: str,
    steady: str,
    ready: str,
    expected: str,
) -> None:
    out = _bash_expr(
        "tei_probe_classify_tier_run "
        f'"{peak}" "{limit}" "{health}" "{oom}" "{exit_code}" "{steady}" "{ready}"'
    )
    assert out == expected
