"""OPS-004 contract: CI workflow and merge-gate inventory (C-OPS4-01..04)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
MERGE_GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "run_merge_gate.sh"
README_PATH = REPO_ROOT / "README.md"
OPERATIONS_PATH = REPO_ROOT / "docs" / "operations.md"

STATIC_INVENTORY = (
    "uv sync --locked",
    "uv run ruff check",
    "uv run mypy src",
    "uv run python scripts/check_env_example.py",
)

UNIT_CONTRACT_INVENTORY = (
    "cp .env.example .env",
    "uv run pytest tests/unit tests/contract",
    "not runtime_contract_gate and not task_scope_boundary",
    "--cov=memory_system.domain",
    "--cov=memory_system.application",
    "--cov-fail-under=80",
)

INTEGRATION_INVENTORY = (
    "cp .env.example .env",
    "prewarm_integration_stack.sh",
    "INTEGRATION_SHARED_STACK",
    "PYTEST_INTEGRATION_STRICT_SKIPS",
    "uv run pytest tests/integration",
    "not runtime_contract_gate and not preflight_integration",
    "--timeout=300",
    "--durations=15",
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


_PYTEST_PLUGINS_RE = re.compile(r"^pytest_plugins\s*=\s*(.+)$", re.MULTILINE)
_TEST_MODULE_PLUGIN_RE = re.compile(
    r"tests\.(?:integration|e2e|unit|contract)\.test_[A-Za-z0-9_]+"
)


def test_pytest_plugins_do_not_load_test_modules() -> None:
    """Loading a test_*.py via pytest_plugins registers its autouse fixtures session-wide.

    That leaked mongo_client pings after isolated compose down -v (migrate / OPS-003).
    """
    violations: list[str] = []
    for path in (REPO_ROOT / "tests").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _PYTEST_PLUGINS_RE.finditer(text):
            assignment = match.group(1)
            if assignment.startswith("("):
                end = text.find(")", match.end() - len(assignment))
                assignment = text[match.start() : end + 1] if end >= 0 else assignment
            for plugin in _TEST_MODULE_PLUGIN_RE.findall(assignment):
                violations.append(f"{path.relative_to(REPO_ROOT)}: {plugin}")
    assert not violations, (
        "pytest_plugins must not point at test modules (session-global autouse leak): "
        f"{violations}"
    )


def test_integration_support_plugins_have_no_autouse() -> None:
    """Support plugins are session-global; autouse there leaks into isolated modules."""
    support = REPO_ROOT / "tests" / "integration" / "support"
    violations: list[str] = []
    for path in sorted(support.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"autouse\s*=\s*True", text):
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, f"integration support plugins must not use autouse: {violations}"


def test_operations_default_merge_gate_command_inventory() -> None:
    """C-OPS4-04: docs/operations.md CI / merge-gate inventory."""
    readme = _read(README_PATH)
    operations = _read(OPERATIONS_PATH)
    docs_surface = readme + "\n" + operations
    section_match = re.search(
        r"(## CI / Quality Gate|\*\*Default merge-gate tests\*\*).*?(?=\n## |\Z)",
        docs_surface,
        re.DOTALL,
    )
    assert section_match is not None, "docs missing CI / merge-gate section"
    section = section_match.group(0)
    assert "uv run pytest tests/unit tests/contract tests/integration" in section
    assert "runtime_contract_gate" in section
    assert "scripts/ci/run_merge_gate.sh" in section
    assert "task_scope_boundary" in section
    assert "--cov-fail-under=80" in section or "fail_under=80" in section
