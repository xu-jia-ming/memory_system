"""E2E-001 contract tests — zero src diff and test-file whitelist."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.task_scope_boundary

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_COMMIT = "c2afaaa576107329ca6153a846fcb071c9383445"

ALLOWED_TEST_FILES = frozenset(
    {
        "tests/e2e/helpers/e2e001_helpers.py",
        "tests/support/e2e001_failure_doubles.py",
        "tests/e2e/test_e2e001_full_chain.py",
        "tests/e2e/test_e2e001_idempotency.py",
        "tests/e2e/test_e2e001_failure_injection.py",
        "tests/e2e/conftest.py",
        "tests/contract/test_e2e001_scope_boundaries.py",
    }
)


def _git_diff_name_only(rev: str, pathspec: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", rev, "--", pathspec],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class TestC1ZeroProductionDiff:
    def test_no_src_changes_since_plan_commit(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        assert changed == [], f"unexpected src changes: {changed}"


class TestC2TestFileWhitelist:
    def test_only_whitelisted_test_files_changed(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "tests/")
        unexpected = [path for path in changed if path not in ALLOWED_TEST_FILES]
        assert unexpected == [], f"unexpected test changes: {unexpected}"

    def test_whitelist_files_exist(self) -> None:
        missing = [path for path in ALLOWED_TEST_FILES if not (REPO_ROOT / path).is_file()]
        assert missing == [], f"missing whitelisted files: {missing}"
