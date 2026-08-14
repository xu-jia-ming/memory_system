"""OPS-004 contract: CI workflow and merge-gate inventory (C-OPS4-01..04)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
MERGE_GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "run_merge_gate.sh"
README_PATH = REPO_ROOT / "README.md"

STATIC_INVENTORY = (
    "uv sync --locked",
    "uv run ruff check",
    "uv run mypy src",
    "uv run python scripts/check_env_example.py",
)

UNIT_CONTRACT_INVENTORY = (
    "uv run pytest tests/unit tests/contract",
    "not runtime_contract_gate and not task_scope_boundary",
    "--cov=memory_system.domain",
    "--cov=memory_system.application",
    "--cov-fail-under=80",
)

INTEGRATION_INVENTORY = (
    "cp .env.example .env",
    "uv run pytest tests/integration",
    "not runtime_contract_gate",
)

GHA_BOOTSTRAP_INVENTORY = (
    "actions/setup-python@v5",
    'python-version: "3.12"',
    "astral-sh/setup-uv@v4",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"missing required path: {path}"
    return path.read_text(encoding="utf-8")


def test_ci_workflow_file_exists() -> None:
    assert WORKFLOW_PATH.is_file()


def test_ci_workflow_jobs_inventory() -> None:
    workflow = _read(WORKFLOW_PATH)
    for job in ("static", "unit-contract-coverage", "integration"):
        assert f"{job}:" in workflow


def test_ci_workflow_gha_bootstrap_inventory() -> None:
    workflow = _read(WORKFLOW_PATH)
    for fragment in GHA_BOOTSTRAP_INVENTORY:
        assert fragment in workflow, f"workflow missing bootstrap fragment: {fragment!r}"


def test_ci_workflow_static_job_inventory() -> None:
    workflow = _read(WORKFLOW_PATH)
    for fragment in STATIC_INVENTORY:
        assert fragment in workflow, f"workflow missing static fragment: {fragment!r}"


def test_ci_workflow_unit_contract_coverage_inventory() -> None:
    workflow = _read(WORKFLOW_PATH)
    for fragment in UNIT_CONTRACT_INVENTORY:
        assert fragment in workflow, f"workflow missing unit/contract fragment: {fragment!r}"


def test_ci_workflow_integration_job_inventory() -> None:
    workflow = _read(WORKFLOW_PATH)
    for fragment in INTEGRATION_INVENTORY:
        assert fragment in workflow, f"workflow missing integration fragment: {fragment!r}"


def test_ci_workflow_excludes_e2e_and_scope_markers() -> None:
    workflow = _read(WORKFLOW_PATH)
    assert "task_scope_boundary" in workflow
    assert "runtime_contract_gate" in workflow
    assert "tests/e2e" not in workflow


def test_merge_gate_script_aligns_with_workflow() -> None:
    """C-OPS4-03: run_merge_gate.sh mirrors workflow static/unit/integration commands."""
    script = _read(MERGE_GATE_SCRIPT)
    assert "set -euo pipefail" in script
    for fragment in STATIC_INVENTORY + UNIT_CONTRACT_INVENTORY + INTEGRATION_INVENTORY:
        assert fragment in script, f"merge-gate script missing fragment: {fragment!r}"


def test_readme_default_merge_gate_command_inventory() -> None:
    """C-OPS4-04: README Default merge-gate tests section inventory."""
    readme = _read(README_PATH)
    section_match = re.search(
        r"\*\*Default merge-gate tests\*\*.*?(?=\n\*\*|\n### |\Z)",
        readme,
        re.DOTALL,
    )
    assert section_match is not None, "README missing Default merge-gate tests section"
    section = section_match.group(0)
    assert "uv run pytest tests/unit tests/contract tests/integration" in section
    assert "runtime_contract_gate" in section
    assert "scripts/ci/run_merge_gate.sh" in section
    assert "task_scope_boundary" in section
    assert "--cov-fail-under=80" in section or "fail_under=80" in section
