"""Unit tests: pyproject.toml dependency and build-system contract (§3.5)."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

EXPECTED_REQUIRES_PYTHON = ">=3.12,<3.13"

EXPECTED_DEPENDENCIES = [
    "fastapi>=0.139,<0.140",
    "pydantic>=2.13,<2.14",
    "pydantic-settings>=2.14,<2.15",
    "pyyaml>=6.0,<7",
    "uvicorn[standard]>=0.47,<0.48",
    "httpx>=0.28,<0.29",
    "openai>=2.46,<3",
    "redis>=8.0,<8.1",
    "pymongo>=4.17,<4.18",
    "aiokafka>=0.13,<0.14",
    "neo4j>=5.28,<6",
    "elasticsearch[async]>=9.4,<9.5",
    "apscheduler>=3.11,<4",
    "structlog>=26.1,<27",
    "prometheus-client>=0.25,<0.26",
]

EXPECTED_QUALITY = [
    "ruff>=0.15,<0.16",
    "mypy>=2.1,<2.2",
]

EXPECTED_TEST = [
    "pytest>=9.1,<9.2",
    "pytest-asyncio>=1.4,<1.5",
    "pytest-cov>=7.1,<7.2",
]

EXPECTED_BUILD_REQUIRES = ["uv_build>=0.11.32,<0.13"]
EXPECTED_BUILD_BACKEND = "uv_build"

FORBIDDEN_PARALLEL_DEP_FILES = (
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "environment.yml",
    "conda-lock.yml",
)


def _load_pyproject() -> dict[str, object]:
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    assert isinstance(data, dict)
    return data


def test_requires_python_matches_spec() -> None:
    data = _load_pyproject()
    project = data["project"]
    assert isinstance(project, dict)
    assert project["requires-python"] == EXPECTED_REQUIRES_PYTHON


def test_runtime_dependencies_match_spec_exactly() -> None:
    data = _load_pyproject()
    project = data["project"]
    assert isinstance(project, dict)
    dependencies = project["dependencies"]
    assert isinstance(dependencies, list)
    assert dependencies == EXPECTED_DEPENDENCIES
    assert set(dependencies) == set(EXPECTED_DEPENDENCIES)
    assert all("uv_build" not in item for item in dependencies)


def test_quality_and_test_groups_match_spec_exactly() -> None:
    data = _load_pyproject()
    groups = data["dependency-groups"]
    assert isinstance(groups, dict)
    quality = groups["quality"]
    test = groups["test"]
    assert isinstance(quality, list)
    assert isinstance(test, list)
    assert quality == EXPECTED_QUALITY
    assert test == EXPECTED_TEST
    assert set(quality) == set(EXPECTED_QUALITY)
    assert set(test) == set(EXPECTED_TEST)
    assert all("uv_build" not in item for item in quality)
    assert all("uv_build" not in item for item in test)


def test_build_system_matches_spec() -> None:
    data = _load_pyproject()
    build_system = data["build-system"]
    assert isinstance(build_system, dict)
    assert build_system["requires"] == EXPECTED_BUILD_REQUIRES
    assert build_system["build-backend"] == EXPECTED_BUILD_BACKEND


def test_no_parallel_dependency_manager_files() -> None:
    for name in FORBIDDEN_PARALLEL_DEP_FILES:
        assert not (REPO_ROOT / name).exists(), f"unexpected file present: {name}"
