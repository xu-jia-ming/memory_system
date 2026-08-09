"""Layer A: mocked TEI probe classification paths (DEV-003-002 + OI-011)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PROBE = REPO_ROOT / "scripts" / "preflight" / "lib_tei_probe.sh"

LIMIT_BYTES = {
    "8g": 8589934592,
    "10g": 10737418240,
    "12g": 12884901888,
    "16g": 17179869184,
}


def _run_mock(
    mock_state: str,
    output: Path,
    mem_limit: str = "8g",
) -> tuple[int, dict[str, object]]:
    script = f'''
source "{LIB_PROBE}"
export TEI_PROBE_MOCK_STATE="{mock_state}"
tei_probe_run_cpu_validation "{REPO_ROOT}" "{output}" "{mem_limit}"
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
    assert report["requested_limit"] == "8g"
    assert report["requested_mem_limit_bytes"] == LIMIT_BYTES["8g"]
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
        assert report["invalidation_reason"] is None


@pytest.mark.parametrize("mem_limit", ["8g", "10g", "12g", "16g"])
def test_mock_pass_across_mem_limits(tmp_path: Path, mem_limit: str) -> None:
    output = tmp_path / f"pass-{mem_limit}.json"
    rc, report = _run_mock("pass", output, mem_limit=mem_limit)
    assert rc == 0
    assert report["runtime_contract_verdict"] == "PASS"
    assert report["requested_limit"] == mem_limit
    assert report["requested_mem_limit_bytes"] == LIMIT_BYTES[mem_limit]
    assert report["container_mem_limit_bytes"] == LIMIT_BYTES[mem_limit]
    assert report["clean_create"] is True


def test_mock_mem_mismatch_invalidates(tmp_path: Path) -> None:
    output = tmp_path / "mismatch.json"
    rc, report = _run_mock("mem_mismatch", output, mem_limit="10g")
    assert rc == 4
    assert report["runtime_contract_verdict"] == "PROBE_EVIDENCE_INCOMPLETE"
    assert report["invalidation_reason"] == "HostConfig.Memory mismatch"
    assert report["requested_limit"] == "10g"
    assert report["requested_mem_limit_bytes"] == LIMIT_BYTES["10g"]


def test_mock_peak_touch_sf3_conflict(tmp_path: Path) -> None:
    output = tmp_path / "peak_touch.json"
    rc, report = _run_mock("peak_touch", output, mem_limit="8g")
    assert rc == 3
    assert report["rss_peak_warmup_bytes"] == LIMIT_BYTES["8g"]
    assert report["runtime_contract_verdict"] == "SPEC_RUNTIME_CONTRACT_CONFLICT"
    classify = subprocess.run(
        [
            "bash",
            "-c",
            (
                f'source "{LIB_PROBE}"; '
                'tei_probe_classify_tier_run '
                f'"{report["rss_peak_warmup_bytes"]}" '
                f'"{report["requested_mem_limit_bytes"]}" '
                f'"true" "false" "0" '
                f'"{report["rss_steady_state_bytes"]}" '
                f'"{report["time_to_ready_sec"]}"'
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert classify.stdout.strip() == "NON_VIABLE"


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


def test_start_stop_helpers_do_not_invoke_compose_sh() -> None:
    text = LIB_PROBE.read_text(encoding="utf-8")
    # Must not shell-invoke compose.sh; comments mentioning the ban are OK.
    assert "scripts/compose.sh" not in text
    assert 'compose.sh"' not in text
    assert "${repo_root}/scripts/compose.sh" not in text
    assert "tei_probe_build_compose_args" in text
    assert "force-recreate" in text
    # No docker-update invocation; ban may appear only in comments.
    assert "docker update --" not in text
    assert "docker update -" not in text
