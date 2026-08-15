"""CON-005 contract tests — scope boundaries (C1..C3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.task_scope_boundary

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_COMMIT = "2862b7a"

ALLOWED_TEST_FILES = frozenset(
    {
        "tests/support/con005_neo4j_fixtures.py",
        "tests/support/con005_failure_doubles.py",
        "tests/integration/conftest_con005_neo4j.py",
        "tests/integration/test_con005_consolidation_read_neo4j.py",
        "tests/integration/test_con005_consolidation_write_neo4j.py",
        "tests/integration/test_con005_consolidation_run_neo4j.py",
        "tests/e2e/helpers/con005_e2e_helpers.py",
        "tests/e2e/test_con005_consolidation_e2e.py",
        "tests/contract/test_con005_scope_boundaries.py",
    }
)

FORBIDDEN_MODIFIED_FILES = (
    "src/memory_system/domain/services/consolidation_importance.py",
    "src/memory_system/domain/models/consolidation_importance.py",
    "src/memory_system/domain/services/consolidation_batch_service.py",
    "src/memory_system/infrastructure/neo4j/consolidation_memory_read_repository.py",
    "src/memory_system/domain/models/consolidation_batch.py",
    "src/memory_system/domain/services/consolidation_write_service.py",
    "src/memory_system/infrastructure/neo4j/consolidation_memory_write_repository.py",
    "src/memory_system/domain/models/consolidation_write.py",
    "src/memory_system/domain/services/consolidation_run_service.py",
    "src/memory_system/infrastructure/consolidation_mutex.py",
    "src/memory_system/infrastructure/scheduling/consolidation_scheduler.py",
    "src/memory_system/infrastructure/neo4j/consolidation_user_enumeration_repository.py",
    "src/memory_system/observability/consolidation_run_telemetry.py",
    "src/memory_system/entrypoints/consolidation_worker.py",
    "src/memory_system/settings/",
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


class TestC2Con001ThroughCon004ProductionUnmodified:
    def test_forbidden_service_files_not_in_src_diff(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        for path in changed:
            for forbidden in FORBIDDEN_MODIFIED_FILES:
                if forbidden.endswith("/"):
                    assert not path.startswith(forbidden), f"{path} modified under {forbidden}"
                else:
                    assert path != forbidden, f"{forbidden} was modified"


class TestC3TestFileWhitelistComplete:
    def test_only_whitelisted_test_files_changed(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "tests/")
        con005_changes = [path for path in changed if "con005" in path.lower()]
        unexpected = [path for path in con005_changes if path not in ALLOWED_TEST_FILES]
        assert unexpected == [], f"unexpected CON-005 test changes: {unexpected}"

    def test_whitelist_files_exist(self) -> None:
        missing = [path for path in ALLOWED_TEST_FILES if not (REPO_ROOT / path).is_file()]
        assert missing == [], f"missing whitelisted files: {missing}"
