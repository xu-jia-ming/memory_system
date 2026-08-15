"""Integration: Migration Runner against isolated compose test stack.

Isolation strategy (fail-closed if violated)
--------------------------------------------
This module uses ONLY ``./scripts/compose.sh --stack=test`` which loads
``compose.yaml`` + ``compose.test.yaml``. That override sets:

* Compose project name ``memory-system-test``
* Independent volumes ``*-data-test`` (never the development ``*-data`` volumes)
* Distinct container names ``memory-system-*-test``

Tests must not invoke the bare Compose CLI, must not use ``--stack=dev``,
and must not write to development project data. If Docker / the test stack
cannot be brought up safely, tests skip or hard-fail with an explicit reason
rather than falling back to the development stack.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tests.integration.support.compose_stack import parse_compose_ps_rows

pytestmark = [pytest.mark.usefixtures("isolated_compose_stack")]

_neo4j_mod = importlib.import_module("scripts.migrations.002_initial_neo4j")
NEO4J_SCHEMA_NAMES: tuple[str, ...] = _neo4j_mod.NEO4J_SCHEMA_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

TEST_PROJECT = "memory-system-test"
INFRA_SERVICES = ("mongodb", "kafka", "neo4j", "elasticsearch")
TEST_VOLUME_MARKERS = (
    "mongodb-data-test",
    "kafka-data-test",
    "neo4j-data-test",
    "elasticsearch-data-test",
)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


def _compose_env() -> dict[str, str]:
    """Env for compose.sh subprocesses during Integration.

    PROXY__HTTP_URL must NOT be invented as ``host.docker.internal:7890`` and
    treated as a Mihomo fallback: on the approved DEV host, port 7890 is an
    SSH/sshd forwarding listener; Mihomo listens on ``127.0.0.1:17890``.
    We also must NOT assume ``host.docker.internal:17890`` is reachable from
    containers (Mihomo binds localhost only). Spec / ``.env.example`` may still
    keep the 7890 *contract literal*; this test overrides the process env with
    an empty value so Compose interpolates empty ``HTTP_PROXY``/``HTTPS_PROXY``
    for init-infra. Image pulls continue to use the Docker *daemon* proxy
    (already configured to Mihomo 17890). Migrate traffic targets internal
    services listed in ``NO_PROXY``.
    """
    env = os.environ.copy()
    env.setdefault("EMBEDDING_EFFECTIVE_RUNTIME_MODE", "cpu")
    env.setdefault("EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET", "4096")
    env["PROXY__HTTP_URL"] = ""
    return env


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(COMPOSE_SH), "--stack=test", "--embedding=none", *args]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=_compose_env(),
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"compose failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _ensure_dotenv() -> None:
    dotenv = REPO_ROOT / ".env"
    if not dotenv.exists():
        shutil.copy(ENV_EXAMPLE, dotenv)


def _assert_test_isolation() -> None:
    config_result = _compose("config", "--format", "json")
    config: dict[str, Any] = json.loads(config_result.stdout)
    assert config.get("name") == TEST_PROJECT, (
        f"fail-closed: expected project {TEST_PROJECT!r}, got {config.get('name')!r}; "
        "refusing to run against a non-test stack"
    )
    volumes = config.get("volumes") or {}
    for marker in TEST_VOLUME_MARKERS:
        assert marker in volumes, (
            f"fail-closed: missing isolated volume {marker!r}; "
            "refusing to risk development volumes"
        )
    # Development volume names must not be the only bindings.
    for bad in ("mongodb-data", "elasticsearch-data", "kafka-data", "neo4j-data"):
        if bad in volumes and f"{bad}-test" not in volumes:
            raise AssertionError(f"fail-closed: development volume {bad!r} without test twin")


@pytest.fixture(scope="module")
def test_stack() -> Iterator[None]:
    if not _docker_available():
        pytest.skip("Docker not available; cannot run migrate integration safely")
    _ensure_dotenv()
    try:
        _assert_test_isolation()
    except AssertionError as exc:
        pytest.skip(f"Test stack isolation not confirmed: {exc}")

    # Fresh volumes for deterministic first-run.
    _compose("down", "-v", check=False)
    time.sleep(2)
    up = _compose("up", "-d", *INFRA_SERVICES, check=False)
    if up.returncode != 0:
        pytest.fail(
            "Unable to start compose test infra "
            f"(exit {up.returncode}): {up.stderr[-800:] or up.stdout[-800:]}"
        )

    deadline = time.time() + 180
    while time.time() < deadline:
        ps = _compose("ps", "--format", "json", check=False)
        if ps.returncode != 0:
            time.sleep(3)
            continue
        healthy_services: set[str] = set()
        for row in parse_compose_ps_rows(ps.stdout):
            svc = row.get("Service")
            health = str(row.get("Health", "")).lower()
            state = str(row.get("State", "")).lower()
            ok = health == "healthy" or (not health and state == "running")
            if svc in INFRA_SERVICES and ok:
                healthy_services.add(str(svc))
        if set(INFRA_SERVICES).issubset(healthy_services):
            break
        time.sleep(3)
    else:
        _compose("down", "-v", check=False)
        pytest.fail("Test infra did not become healthy within timeout")

    yield

    _compose("down", "-v", check=False)


def _run_init_infra() -> subprocess.CompletedProcess[str]:
    return _compose("run", "--rm", "init-infra", check=False)


def _docker_exec(container: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", container, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_migrate_first_run_idempotent_checksum_and_stores(test_stack: None) -> None:
    first = _run_init_infra()
    assert first.returncode == 0, first.stderr or first.stdout

    # Records
    mongo = _docker_exec(
        "memory-system-mongodb-test",
        "mongosh",
        "--quiet",
        "memory_system",
        "--eval",
        (
            "JSON.stringify(db.infra_schema_migrations"
            ".find({}, {_id:0,migration_id:1,checksum:1}).toArray())"
        ),
    )
    assert mongo.returncode == 0, mongo.stderr
    records = json.loads(mongo.stdout)
    ids = sorted(r["migration_id"] for r in records)
    assert ids == [
        "001_initial_mongodb",
        "002_initial_neo4j",
        "003_elasticsearch_memory_v1",
        "004_initial_kafka_topics",
    ]
    assert all(str(r["checksum"]).startswith("sha256:") for r in records)
    first_count = len(records)

    # Idempotent second run
    second = _run_init_infra()
    assert second.returncode == 0, second.stderr or second.stdout
    mongo2 = _docker_exec(
        "memory-system-mongodb-test",
        "mongosh",
        "--quiet",
        "memory_system",
        "--eval",
        "db.infra_schema_migrations.countDocuments({})",
    )
    assert mongo2.returncode == 0
    assert int(mongo2.stdout.strip()) == first_count

    # Checksum conflict: tamper recorded checksum
    tamper = _docker_exec(
        "memory-system-mongodb-test",
        "mongosh",
        "--quiet",
        "memory_system",
        "--eval",
        'db.infra_schema_migrations.updateOne('
        '{migration_id:"001_initial_mongodb"},'
        '{$set:{checksum:"sha256:' + ("a" * 64) + '"}})',
    )
    assert tamper.returncode == 0, tamper.stderr
    conflict = _run_init_infra()
    assert conflict.returncode != 0
    # Restore checksum path for subsequent assertions by re-down? Keep failing state ok.

    # Re-fix for store assertions: wipe migration record conflict by fixing checksum
    # via full remigrate after restoring from file — simplest: down -v and re-up is heavy;
    # instead set checksum back by re-running after deleting the bad record and... actually
    # the file checksum is fine; just restore the correct checksum from the first payload.
    good_checksum = next(
        r["checksum"] for r in records if r["migration_id"] == "001_initial_mongodb"
    )
    restore = _docker_exec(
        "memory-system-mongodb-test",
        "mongosh",
        "--quiet",
        "memory_system",
        "--eval",
        f'db.infra_schema_migrations.updateOne('
        f'{{migration_id:"001_initial_mongodb"}},'
        f'{{$set:{{checksum:"{good_checksum}"}}}})',
    )
    assert restore.returncode == 0

    # ES alias + mapping
    es_alias = _docker_exec(
        "memory-system-elasticsearch-test",
        "curl",
        "-fsS",
        "http://localhost:9200/memory_retrieval_current/_alias",
    )
    assert es_alias.returncode == 0, es_alias.stderr
    alias_body = json.loads(es_alias.stdout)
    assert "memory_retrieval_v1" in alias_body
    assert "memory_retrieval_current" in alias_body["memory_retrieval_v1"]["aliases"]

    es_mapping = _docker_exec(
        "memory-system-elasticsearch-test",
        "curl",
        "-fsS",
        "http://localhost:9200/memory_retrieval_v1/_mapping",
    )
    assert es_mapping.returncode == 0, es_mapping.stderr
    mapping = json.loads(es_mapping.stdout)
    props = mapping["memory_retrieval_v1"]["mappings"]["properties"]
    assert props["embedding"]["dims"] == 1024
    assert props["embedding"]["similarity"] == "cosine"
    assert props["embedding"]["index_options"]["type"] == "int8_hnsw"
    assert props["content"]["analyzer"] == "cjk"

    # Mongo indexes
    idx = _docker_exec(
        "memory-system-mongodb-test",
        "mongosh",
        "--quiet",
        "memory_system",
        "--eval",
        "JSON.stringify(db.context_archive.getIndexes().map(i => i.name))",
    )
    assert idx.returncode == 0
    index_names = json.loads(idx.stdout)
    assert "archive_id_unique" in index_names
    assert "archive_batch_key_unique" in index_names

    task_idx = _docker_exec(
        "memory-system-mongodb-test",
        "mongosh",
        "--quiet",
        "memory_system",
        "--eval",
        "JSON.stringify(db.memory_extraction_task.getIndexes().map(i => i.name))",
    )
    assert task_idx.returncode == 0
    task_index_names = json.loads(task_idx.stdout)
    assert "archive_id_unique" in task_index_names
    assert "status_updated_time" in task_index_names

    # Neo4j constraints / indexes — exact §2.1.9 names
    neo4j = _docker_exec(
        "memory-system-neo4j-test",
        "cypher-shell",
        "-u",
        "neo4j",
        "--format",
        "plain",
        "SHOW CONSTRAINTS YIELD name RETURN collect(name) AS names",
    )
    # AUTH none — cypher-shell may not need password
    if neo4j.returncode != 0:
        neo4j = _docker_exec(
            "memory-system-neo4j-test",
            "cypher-shell",
            "--format",
            "plain",
            "SHOW CONSTRAINTS YIELD name RETURN collect(name) AS names",
        )
    assert neo4j.returncode == 0, neo4j.stderr or neo4j.stdout
    constraint_out = neo4j.stdout
    for name in (
        "entity_id_unique",
        "entity_key_unique",
        "memory_id_unique",
        "evidence_id_unique",
    ):
        assert name in constraint_out, f"missing constraint {name}"

    neo4j_idx = _docker_exec(
        "memory-system-neo4j-test",
        "cypher-shell",
        "--format",
        "plain",
        "SHOW INDEXES YIELD name RETURN collect(name) AS names",
    )
    assert neo4j_idx.returncode == 0, neo4j_idx.stderr
    for name in ("memory_user_type_status", "memory_subject_predicate"):
        assert name in neo4j_idx.stdout, f"missing index {name}"
    for name in NEO4J_SCHEMA_NAMES:
        assert name in constraint_out or name in neo4j_idx.stdout

    # Kafka topic
    kafka = _docker_exec(
        "memory-system-kafka-test",
        "/opt/kafka/bin/kafka-topics.sh",
        "--bootstrap-server",
        "localhost:9092",
        "--describe",
        "--topic",
        "context.archive.created",
    )
    assert kafka.returncode == 0, kafka.stderr
    assert "context.archive.created" in kafka.stdout
    assert "PartitionCount: 3" in kafka.stdout or "PartitionCount:3" in kafka.stdout.replace(
        " ", ""
    )
