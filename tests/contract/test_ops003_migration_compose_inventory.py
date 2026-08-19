"""OPS-003 contract: migration/compose inventory and §3.17 README alignment (C-OPS3-01/02).

MVP checklist A mapping (§10):
- Migration first run / idempotent / checksum tamper → test_migrate_infra + I-OPS3-01
- Three entrypoints + readiness → I-OPS3-01
- Docker unavailable → module-level skip in integration (INT-SKIP-001)
- CPU embedding / preflight → DEFERRED (manual or OPS-004)
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.contract.test_migrate_paths_contract import EXPECTED_MIGRATIONS

REPO_ROOT = Path(__file__).resolve().parents[2]

# §3.17 standard startup substrings (C-OPS3-01)
README_SECTION317_SUBSTRINGS = (
    "cp .env.example .env",
    "./scripts/compose.sh --embedding=none pull",
    "./scripts/compose.sh --embedding=none build",
    "./scripts/compose.sh --embedding=none",
    "up -d redis mongodb kafka neo4j elasticsearch",
    "./scripts/start_embedding.sh auto",
    "./scripts/compose.sh --embedding=current run --rm init-infra",
    "python -m scripts.migrate",
    "./scripts/compose.sh --embedding=current up -d",
    "memory-api memory-extraction-worker memory-consolidation-worker",
    "./scripts/compose.sh --embedding=current down -v",
    "./scripts/compose.sh",
    "禁止",
)

# §6 migration/compose component paths (C-OPS3-02)
MIGRATION_COMPONENTS = (
    "scripts/migrate.py",
    "scripts/migrations/__init__.py",
    *(f"scripts/migrations/{name}" for name in EXPECTED_MIGRATIONS),
)

COMPOSE_COMPONENTS = (
    "compose.yaml",
    "compose.test.yaml",
    "scripts/compose.sh",
)

APP_SERVICES = (
    "memory-api",
    "memory-extraction-worker",
    "memory-consolidation-worker",
)

INFRA_SERVICES = (
    "redis",
    "mongodb",
    "kafka",
    "neo4j",
    "elasticsearch",
    "init-infra",
)


def test_migration_component_inventory_exists() -> None:
    for rel in MIGRATION_COMPONENTS:
        path = REPO_ROOT / rel
        assert path.is_file(), f"missing migration component: {rel}"


def test_compose_component_inventory_exists() -> None:
    for rel in COMPOSE_COMPONENTS:
        path = REPO_ROOT / rel
        assert path.is_file(), f"missing compose component: {rel}"


def test_init_infra_command_is_migrate_runner() -> None:
    compose_text = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "scripts.migrate" in compose_text
    init_block = re.search(
        r"init-infra:.*?(?=\n  [a-z]|\n  #|\Z)",
        compose_text,
        re.DOTALL,
    )
    assert init_block is not None
    assert "scripts.migrate" in init_block.group(0)


def test_compose_test_stack_isolation_keys() -> None:
    test_yaml = (REPO_ROOT / "compose.test.yaml").read_text(encoding="utf-8")
    assert "name: memory-system-test" in test_yaml
    for marker in (
        "mongodb-data-test",
        "kafka-data-test",
        "neo4j-data-test",
        "elasticsearch-data-test",
        "redis-data-test",
    ):
        assert marker in test_yaml


def test_deployment_section317_command_inventory() -> None:
    deployment = (REPO_ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
    for fragment in README_SECTION317_SUBSTRINGS:
        assert fragment in deployment, f"docs/deployment.md missing §3.17 fragment: {fragment!r}"


def test_compose_yaml_lists_app_and_infra_services() -> None:
    compose_text = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    for svc in APP_SERVICES + INFRA_SERVICES:
        assert f"  {svc}:" in compose_text or f"{svc}:" in compose_text


def test_start_embedding_writes_runtime_env_keys() -> None:
    """C-OPS3-03: static structure for embedding.env atomic write."""
    script = (REPO_ROOT / "scripts" / "start_embedding.sh").read_text(encoding="utf-8")
    assert "EMBEDDING_EFFECTIVE_RUNTIME_MODE" in script
    assert "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET" in script
    assert ".runtime/embedding.env" in script
    assert "mktemp" in script
    assert "mv " in script
    assert "cleanup_failed_embedding" in script
