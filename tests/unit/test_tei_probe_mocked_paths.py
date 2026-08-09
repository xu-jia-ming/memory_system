"""Layer A: mocked TEI probe classification paths (DEV-003-002 Amendment 001)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PROBE = REPO_ROOT / "scripts" / "preflight" / "lib_tei_probe.sh"


def _run_mock(mock_state: str, output: Path) -> tuple[int, dict[str, object]]:
    script = f'''
source "{LIB_PROBE}"
export TEI_PROBE_MOCK_STATE="{mock_state}"
tei_probe_run_cpu_validation "{REPO_ROOT}" "{output}"
echo RC=$?
'''
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    rc_line = [line for line in result.stdout.splitlines() if line.startswith("RC=")]
    rc = int(rc_line[-1].split("=", 1)[1]) if rc_line else result.returncode
    report: dict[str, object] = {}
    if output.exists():
        report = json.loads(output.read_text(encoding="utf-8"))
    return rc, report


@pytest.mark.parametrize(
    ("mock_state", "expected_rc", "verdict", "health_ready"),
    [
        ("pass", 0, "PASS", True),
        ("oom", 2, "SPEC_RUNTIME_CONTRACT_CONFLICT", False),
        ("timeout", 3, "SPEC_RUNTIME_CONTRACT_CONFLICT", False),
        ("exited", 1, "SPEC_RUNTIME_CONTRACT_CONFLICT", False),
    ],
)
def test_mock_probe_exit_codes_and_verdicts(
    tmp_path: Path,
    mock_state: str,
    expected_rc: int,
    verdict: str,
    health_ready: bool,
) -> None:
    output = tmp_path / f"{mock_state}.json"
    rc, report = _run_mock(mock_state, output)
    assert rc == expected_rc
    if mock_state == "exited":
        assert report["exit_code"] == 1
        return
    assert report["runtime_contract_verdict"] == verdict
    assert report["health_ready"] is health_ready
    if mock_state == "oom":
        assert report["oom_killed"] is True
        assert report["exit_code"] == 137
        assert report["rss_steady_state_bytes"] is None
        assert report["time_to_ready_sec"] is None
        assert report["time_to_failure_sec"] is not None
    if mock_state == "pass":
        assert report["rss_steady_state_bytes"] is not None
        assert report["time_to_ready_sec"] is not None
        assert report["time_to_failure_sec"] is None


def test_mock_incomplete_evidence_no_json(tmp_path: Path) -> None:
    output = tmp_path / "incomplete.json"
    rc, _ = _run_mock("incomplete", output)
    assert rc == 1
    assert not output.exists()


def test_validate_report_schema_rejects_oom_with_steady(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "recorded_at_utc": "2026-01-01T00:00:00Z",
                "model_id": "BAAI/bge-m3",
                "revision": "57aacf8560157b7c1d4f771ce1a199877aeeec74",
                "dtype": "float32",
                "runtime": "ONNX CPU",
                "tei_image": "img",
                "image_digest": "sha256:" + "a" * 64,
                "spec_mem_limit_bytes": 8589934592,
                "container_mem_limit_bytes": 8589934592,
                "rss_peak_warmup_bytes": 1,
                "rss_steady_state_bytes": 1,
                "health_ready": False,
                "runtime_contract_verdict": "SPEC_RUNTIME_CONTRACT_CONFLICT",
                "time_to_ready_sec": None,
                "time_to_failure_sec": 1,
                "oom_killed": True,
                "exit_code": 137,
                "timed_out": False,
                "probe_timeout_sec": 300,
                "host_mem_total_bytes": 1,
                "host_mem_available_bytes": 1,
            }
        ),
        encoding="utf-8",
    )
    script = f'source "{LIB_PROBE}"; tei_probe_validate_report_schema "{bad}"'
    result = subprocess.run(["bash", "-c", script], cwd=REPO_ROOT, check=False)
    assert result.returncode != 0
