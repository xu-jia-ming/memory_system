"""Contract: §3.4 migration paths and unique init entrypoint."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_MIGRATIONS = (
    "001_initial_mongodb.py",
    "002_initial_neo4j.py",
    "003_elasticsearch_memory_v1.py",
    "004_initial_kafka_topics.py",
)


def test_migrate_runner_and_migration_files_exist() -> None:
    assert (REPO_ROOT / "scripts" / "migrate.py").is_file()
    migrations_dir = REPO_ROOT / "scripts" / "migrations"
    for name in EXPECTED_MIGRATIONS:
        assert (migrations_dir / name).is_file(), name
    assert (migrations_dir / "__init__.py").is_file()


def test_migration_id_stems_match_filenames() -> None:
    migrations_dir = REPO_ROOT / "scripts" / "migrations"
    stems = sorted(p.stem for p in migrations_dir.glob("0*.py"))
    assert stems == [name.removesuffix(".py") for name in EXPECTED_MIGRATIONS]


def test_unique_documented_migrate_entrypoint() -> None:
    """Only python -m scripts.migrate / init-infra; no second init script."""
    scripts_dir = REPO_ROOT / "scripts"
    init_like = [
        p.name
        for p in scripts_dir.glob("*.py")
        if p.name != "__init__.py"
        and re.search(r"(^|_)(init|bootstrap|setup_infra)", p.name, re.I)
    ]
    assert init_like == [], f"unexpected init scripts: {init_like}"
    assert (scripts_dir / "migrate.py").is_file()

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "python -m scripts.migrate" in readme
    assert "compose.sh" in readme
    assert "禁止" in readme


def test_upgrade_protocol_exported() -> None:
    from scripts.migrations import MigrationContext, MigrationCtx, MigrationModule

    assert MigrationContext is not None
    assert MigrationModule is not None
    assert frozenset(MigrationCtx.__dataclass_fields__) == frozenset(
        {"settings", "mongo_client", "neo4j_driver", "es_client"}
    )
