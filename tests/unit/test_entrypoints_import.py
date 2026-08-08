"""Unit tests: entrypoint modules are import-safe and refuse unready startup."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

ENTRYPOINT_MODULES: tuple[str, ...] = (
    "memory_system.entrypoints.api",
    "memory_system.entrypoints.extraction_worker",
    "memory_system.entrypoints.consolidation_worker",
)

NOT_READY_ENTRYPOINT_MODULES: tuple[str, ...] = (
    "memory_system.entrypoints.extraction_worker",
    "memory_system.entrypoints.consolidation_worker",
)


@pytest.mark.parametrize("module_name", ENTRYPOINT_MODULES)
def test_entrypoint_import_succeeds(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None


@pytest.mark.parametrize("module_name", NOT_READY_ENTRYPOINT_MODULES)
def test_entrypoint_module_run_exits_nonzero_when_not_ready(module_name: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", module_name],
        check=False,
        capture_output=True,
        text=True,
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "not ready" in combined.lower()
    assert "success" not in combined.lower()


def test_api_entrypoint_exits_nonzero_without_env(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "memory_system.entrypoints.api"],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={
            "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    assert result.returncode != 0
    assert "settings" in f"{result.stdout}\n{result.stderr}".lower()


def test_entrypoint_module_list_matches_spec() -> None:
    expected: Sequence[str] = ENTRYPOINT_MODULES
    assert len(expected) == 3
