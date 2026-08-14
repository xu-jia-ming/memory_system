"""Contract guards for EXT-009 boundaries and upstream zero-diff invariants."""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from memory_system.domain.enums.extraction_task import PipelineTerminalKind
from memory_system.domain.services.extraction_pipeline_port import ExtractionPipelinePort
from memory_system.domain.services.production_extraction_pipeline import (
    ProductionExtractionPipeline,
    create_production_extraction_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_COMMIT = "53480405f1b7e916c40f39f7845c569858952c7f"

UPSTREAM_PRODUCTION_PATHS = (
    "src/memory_system/domain/services/extraction_archive_preprocessing_service.py",
    "src/memory_system/domain/services/extraction_llm_service.py",
    "src/memory_system/domain/services/extraction_pipeline_port.py",
    "src/memory_system/domain/services/entity_alignment_service.py",
    "src/memory_system/domain/services/reconciliation_service.py",
    "src/memory_system/domain/services/graph_write_service.py",
    "src/memory_system/domain/services/retrieval_index_sync_service.py",
)


def test_pipeline_implements_existing_port_without_contract_replacement() -> None:
    assert ExtractionPipelinePort in ProductionExtractionPipeline.__mro__
    assert inspect.iscoroutinefunction(ProductionExtractionPipeline.run)
    assert callable(create_production_extraction_pipeline)
    assert set(kind.value for kind in PipelineTerminalKind) == {
        "complete",
        "fail",
        "abort_without_terminal",
    }


@pytest.mark.task_scope_boundary
def test_ext002_to_ext007_services_and_terminal_port_have_zero_diff() -> None:
    result = subprocess.run(
        ["git", "diff", "--exit-code", PLAN_COMMIT, "--", *UPSTREAM_PRODUCTION_PATHS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_worker_is_wired_to_production_pipeline_and_consumer_loop() -> None:
    source = (REPO_ROOT / "src/memory_system/entrypoints/extraction_worker.py").read_text(
        encoding="utf-8"
    )
    assert "create_production_extraction_pipeline" in source
    assert "run_archive_created_consumer_loop" in source
    assert "create_archive_created_consumer" in source
    assert "refuses to start the Kafka poll loop" not in source
    assert "asyncio.run(_run_worker(settings))" in source
