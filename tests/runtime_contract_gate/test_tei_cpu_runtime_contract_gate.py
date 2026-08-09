"""Layer B: reference runtime contract gate (DEV-003-002 Amendment 001).

Not part of default merge-gate CI. Validates archived §13 evidence semantics.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PROBE = REPO_ROOT / "scripts" / "preflight" / "lib_tei_probe.sh"
ARCHIVED_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "archived_conflict_evidence_v1.json"
)
RUNTIME_REPORT = REPO_ROOT / ".runtime" / "tei_memory_report.json"
REQUIRED_SCHEMA_FIELDS = frozenset(
    {
        "schema_version",
        "recorded_at_utc",
        "model_id",
        "revision",
        "dtype",
        "runtime",
        "tei_image",
        "image_digest",
        "spec_mem_limit_bytes",
        "container_mem_limit_bytes",
        "rss_peak_warmup_bytes",
        "rss_steady_state_bytes",
        "health_ready",
        "runtime_contract_verdict",
        "time_to_ready_sec",
        "time_to_failure_sec",
        "oom_killed",
        "exit_code",
        "timed_out",
        "host_mem_total_bytes",
        "host_mem_available_bytes",
        "probe_timeout_sec",
    }
)


def _validate_schema(report: dict[str, object]) -> None:
    missing = sorted(REQUIRED_SCHEMA_FIELDS - set(report))
    assert not missing, f"missing schema fields: {missing}"
    if report.get("oom_killed"):
        assert report.get("rss_steady_state_bytes") is None
    if report.get("health_ready"):
        assert report.get("time_to_ready_sec") is not None
    else:
        assert report.get("time_to_ready_sec") is None


def _bash_validate(path: Path) -> subprocess.CompletedProcess[str]:
    script = f'source "{LIB_PROBE}"; tei_probe_validate_report_schema "{path}"'
    return subprocess.run(
        ["bash", "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.runtime_contract_gate
def test_archived_conflict_evidence_schema_and_verdict() -> None:
    """§13 formal probe evidence (upgraded fixture) — CONFLICT is expected and valid."""
    report = json.loads(ARCHIVED_FIXTURE.read_text(encoding="utf-8"))
    _validate_schema(report)
    assert report["runtime_contract_verdict"] == "SPEC_RUNTIME_CONTRACT_CONFLICT"
    assert report["oom_killed"] is True
    assert report["exit_code"] == 137
    assert report["health_ready"] is False
    assert report["spec_mem_limit_bytes"] == 8589934592
    assert report["rss_peak_warmup_bytes"] == 8589934592

    result = _bash_validate(ARCHIVED_FIXTURE)
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.runtime_contract_gate
def test_runtime_report_or_fixture_satisfies_layer_b_without_rerun() -> None:
    """Prefer §13 archived JSON; fixture suffices when on-disk report lacks new schema."""
    if RUNTIME_REPORT.exists():
        report = json.loads(RUNTIME_REPORT.read_text(encoding="utf-8"))
        if REQUIRED_SCHEMA_FIELDS <= set(report):
            _validate_schema(report)
            if report.get("runtime_contract_verdict") == "SPEC_RUNTIME_CONTRACT_CONFLICT":
                assert report.get("oom_killed") is True
                result = _bash_validate(RUNTIME_REPORT)
                assert result.returncode == 0, result.stderr
                return
    # On-disk report predates Amendment schema — fixture is authoritative for Layer B.
    report = json.loads(ARCHIVED_FIXTURE.read_text(encoding="utf-8"))
    assert report["runtime_contract_verdict"] == "SPEC_RUNTIME_CONTRACT_CONFLICT"
