"""CON-001 contract tests — scope boundaries (C1..C3)."""

from __future__ import annotations

import subprocess
from dataclasses import fields
from pathlib import Path

import pytest

from memory_system.domain.models.consolidation_importance import ConsolidationImportanceInput

pytestmark = pytest.mark.task_scope_boundary

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_COMMIT = "6f4a35ad28ad90946f74e39bfa567acc71120b12"

ALLOWED_SRC_FILES = frozenset(
    {
        "src/memory_system/domain/models/consolidation_importance.py",
        "src/memory_system/domain/services/consolidation_importance.py",
    }
)

FORBIDDEN_MODIFIED_PREFIXES = (
    "src/memory_system/domain/services/act_r_scoring.py",
    "src/memory_system/domain/services/reconciliation_plan_builder.py",
    "src/memory_system/domain/services/consolidation_worker.py",
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


class TestC1ProductionWhitelist:
    def test_only_whitelisted_src_files_changed(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        unexpected = [p for p in changed if p not in ALLOWED_SRC_FILES]
        assert unexpected == [], f"unexpected src changes: {unexpected}"


class TestC2InputContractFields:
    FORBIDDEN_FIELDS = frozenset(
        {"importance", "retrieval_count", "last_retrieved_time", "user_id"}
    )

    def test_input_has_no_forbidden_fields(self) -> None:
        field_names = {f.name for f in fields(ConsolidationImportanceInput)}
        overlap = self.FORBIDDEN_FIELDS & field_names
        assert overlap == set()

    def test_input_has_required_fields(self) -> None:
        field_names = {f.name for f in fields(ConsolidationImportanceInput)}
        required = {
            "memory_type",
            "confidence",
            "status",
            "created_time",
            "latest_source_time",
            "independent_archive_count",
            "evaluation_time",
        }
        assert required <= field_names


class TestC3ForbiddenFilesUnmodified:
    def test_forbidden_paths_not_in_src_diff(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/")
        for path in changed:
            for forbidden in FORBIDDEN_MODIFIED_PREFIXES:
                if forbidden.endswith("/"):
                    assert not path.startswith(forbidden), f"{path} modified under {forbidden}"
                else:
                    assert path != forbidden, f"{forbidden} was modified"

    def test_settings_directory_not_modified(self) -> None:
        changed = _git_diff_name_only(PLAN_COMMIT, "src/memory_system/settings/")
        assert changed == []
