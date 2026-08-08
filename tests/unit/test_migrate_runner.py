"""Unit tests for Migration Runner checksum / order / skip / conflict / precheck."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from scripts.migrate import (
    MigrationError,
    MigrationFile,
    apply_migrations,
    bootstrap_migrations_collection,
    compute_checksum,
    discover_migrations,
    verify_dependency_versions,
)
from scripts.migrations import MigrationCtx


def test_compute_checksum_format(tmp_path: Path) -> None:
    path = tmp_path / "001_sample.py"
    path.write_text("print('x')\n", encoding="utf-8")
    checksum = compute_checksum(path)
    assert checksum.startswith("sha256:")
    assert len(checksum) == len("sha256:") + 64
    assert all(c in "0123456789abcdef" for c in checksum.removeprefix("sha256:"))


def test_discover_migrations_order() -> None:
    repo_migrations = Path(__file__).resolve().parents[2] / "scripts" / "migrations"
    found = discover_migrations(repo_migrations)
    ids = [m.migration_id for m in found]
    assert ids == [
        "001_initial_mongodb",
        "002_initial_neo4j",
        "003_elasticsearch_memory_v1",
        "004_initial_kafka_topics",
    ]


def test_bootstrap_creates_unique_index() -> None:
    collection = MagicMock()
    db = MagicMock()
    db.__getitem__.return_value = collection
    bootstrap_migrations_collection(db)
    collection.create_index.assert_called_once()
    args, kwargs = collection.create_index.call_args
    assert args[0] == [("migration_id", 1)] or args[0][0][0] == "migration_id"
    assert kwargs.get("unique") is True


def _fake_ctx_with_collection(collection: MagicMock) -> MigrationCtx:
    db = MagicMock()
    db.__getitem__.return_value = collection
    mongo = MagicMock()
    mongo.get_default_database.return_value = db
    settings = MagicMock()
    return MigrationCtx(
        settings=settings,
        mongo_client=mongo,
        neo4j_driver=MagicMock(),
        es_client=MagicMock(),
    )


def test_skip_when_checksum_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mig = tmp_path / "001_demo.py"
    mig.write_text("def upgrade(ctx):\n    raise AssertionError('should skip')\n", encoding="utf-8")
    checksum = compute_checksum(mig)
    collection = MagicMock()
    collection.find_one.return_value = {
        "migration_id": "001_demo",
        "checksum": checksum,
    }
    ctx = _fake_ctx_with_collection(collection)
    upgrade_calls: list[str] = []

    def fake_load(migration: MigrationFile) -> Any:
        def upgrade(_ctx: object) -> None:
            upgrade_calls.append(migration.migration_id)

        return upgrade

    monkeypatch.setattr("scripts.migrate.load_upgrade", fake_load)
    monkeypatch.setattr("scripts.migrate.bootstrap_migrations_collection", lambda _db: None)
    monkeypatch.setattr("scripts.migrate.app_version", lambda: "0.1.0")

    apply_migrations(
        ctx,
        [MigrationFile(migration_id="001_demo", path=mig)],
        skip_version_precheck=True,
    )
    assert upgrade_calls == []
    collection.insert_one.assert_not_called()


def test_checksum_conflict_fails_without_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mig = tmp_path / "001_demo.py"
    mig.write_text("def upgrade(ctx):\n    pass\n", encoding="utf-8")
    collection = MagicMock()
    collection.find_one.return_value = {
        "migration_id": "001_demo",
        "checksum": "sha256:" + ("0" * 64),
    }
    ctx = _fake_ctx_with_collection(collection)
    called = {"n": 0}

    def fake_load(_migration: MigrationFile) -> Any:
        def upgrade(_ctx: object) -> None:
            called["n"] += 1

        return upgrade

    monkeypatch.setattr("scripts.migrate.load_upgrade", fake_load)
    monkeypatch.setattr("scripts.migrate.bootstrap_migrations_collection", lambda _db: None)

    with pytest.raises(MigrationError, match="Checksum conflict"):
        apply_migrations(
            ctx,
            [MigrationFile(migration_id="001_demo", path=mig)],
            skip_version_precheck=True,
        )
    assert called["n"] == 0
    collection.insert_one.assert_not_called()


def test_version_precheck_failure_does_not_write_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Amendment 001 / SHOULD_FIX 3: version precheck fail → no migration Record."""
    collection = MagicMock()
    collection.find_one.return_value = None
    ctx = _fake_ctx_with_collection(collection)

    def boom(_ctx: object) -> None:
        raise MigrationError("Elasticsearch version mismatch")

    monkeypatch.setattr("scripts.migrate.verify_dependency_versions", boom)

    with pytest.raises(MigrationError, match="Elasticsearch version mismatch"):
        apply_migrations(ctx, migrations=[], skip_version_precheck=False)

    collection.insert_one.assert_not_called()
    collection.find_one.assert_not_called()


def test_verify_dependency_versions_es_mismatch() -> None:
    settings = MagicMock()
    settings.memory_retrieval.elasticsearch_version = "9.4.4"
    settings.kafka.bootstrap_servers = "kafka:9092"
    es = MagicMock()
    es.info.return_value = {"version": {"number": "8.0.0"}}
    mongo = MagicMock()
    mongo.server_info.return_value = {"version": "8.0.28"}
    neo4j = MagicMock()
    session = MagicMock()
    session.run.return_value.single.return_value = {
        "versions": ["5.26.28"],
        "edition": "community",
    }
    neo4j.session.return_value.__enter__.return_value = session
    neo4j.session.return_value.__exit__.return_value = False
    ctx = MigrationCtx(
        settings=settings,
        mongo_client=mongo,
        neo4j_driver=neo4j,
        es_client=es,
    )
    with pytest.raises(MigrationError, match="Elasticsearch version"):
        verify_dependency_versions(ctx)


def test_broker_configs_accepts_config_names_field() -> None:
    from scripts.migrate import _KAFKA_V4_CONFIG_MARKERS, _broker_configs_from_responses

    class _Resp:
        resources = None

        def to_object(self) -> dict[str, object]:
            return {
                "resources": [
                    {
                        "config_entries": [
                            {
                                "config_names": "share.coordinator.state.topic.num.partitions",
                                "config_value": "50",
                            }
                        ]
                    }
                ]
            }

    configs = _broker_configs_from_responses([_Resp()])
    assert configs["share.coordinator.state.topic.num.partitions"] == "50"
    assert any(marker in configs for marker in _KAFKA_V4_CONFIG_MARKERS)
