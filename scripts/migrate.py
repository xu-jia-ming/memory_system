"""Migration Runner — unique infra init entrypoint (`python -m scripts.migrate`).

Performs dependency version precheck, bootstraps ``infra_schema_migrations``,
then applies ``scripts/migrations/0*.py`` in filename order with checksum records.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import logging
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from memory_system.settings import Settings, get_settings
from scripts.migrations import MigrationContext, MigrationCtx

logger = logging.getLogger(__name__)

MIGRATIONS_COLLECTION = "infra_schema_migrations"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Kafka 4 KRaft brokers expose Share Group coordinator configs and no longer
# publish inter.broker.protocol.version. Do NOT infer broker major from the
# client's negotiated ApiVersions map (aiokafka may max out below Share APIs).
_KAFKA_V4_CONFIG_MARKERS: tuple[str, ...] = (
    "share.coordinator.state.topic.num.partitions",
    "share.coordinator.state.topic.replication.factor",
    "group.share.max.size",
)


class MigrationError(RuntimeError):
    """Fatal migration / precheck failure."""


@dataclass(frozen=True, slots=True)
class MigrationFile:
    migration_id: str
    path: Path


def compute_checksum(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def discover_migrations(migrations_dir: Path | None = None) -> list[MigrationFile]:
    directory = migrations_dir if migrations_dir is not None else MIGRATIONS_DIR
    files = sorted(
        p
        for p in directory.glob("0*.py")
        if p.is_file() and p.name != "__init__.py"
    )
    return [MigrationFile(migration_id=p.stem, path=p) for p in files]


def app_version() -> str:
    try:
        return metadata.version("memory-system")
    except metadata.PackageNotFoundError:
        return "0.1.0"


def bootstrap_migrations_collection(db: Database[Any]) -> None:
    """Ensure infra_schema_migrations exists with unique migration_id (§3.20)."""
    collection = db[MIGRATIONS_COLLECTION]
    collection.create_index(
        [("migration_id", ASCENDING)],
        unique=True,
        name="migration_id_unique",
    )


def _mongo_db(client: MongoClient[Any]) -> Database[Any]:
    db = client.get_default_database()
    if db is None:
        raise MigrationError(
            "MongoDB URI must include a default database path "
            "(e.g. mongodb://host:27017/memory_system)"
        )
    return db


def _connect_clients(settings: Settings) -> MigrationCtx:
    mongo_client: MongoClient[Any] = MongoClient(
        settings.mongodb.uri.get_secret_value(),
        serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
        connectTimeoutMS=settings.mongodb.connect_timeout_ms,
        maxPoolSize=settings.mongodb.max_pool_size,
    )
    neo4j_driver = GraphDatabase.driver(
        settings.neo4j.uri.get_secret_value(),
        auth=None,
        connection_timeout=settings.neo4j.connection_timeout_seconds,
        max_connection_pool_size=settings.neo4j.max_connection_pool_size,
        connection_acquisition_timeout=(
            settings.neo4j.connection_acquisition_timeout_seconds
        ),
    )
    es_client = Elasticsearch(
        settings.elasticsearch.url,
        request_timeout=settings.elasticsearch.request_timeout_seconds,
        max_retries=settings.elasticsearch.max_retries,
        retry_on_timeout=settings.elasticsearch.retry_on_timeout,
    )
    return MigrationCtx(
        settings=settings,
        mongo_client=mongo_client,
        neo4j_driver=neo4j_driver,
        es_client=es_client,
    )


def _close_clients(ctx: MigrationCtx) -> None:
    ctx.mongo_client.close()
    ctx.neo4j_driver.close()
    ctx.es_client.close()


def _major_version(version: str) -> int:
    cleaned = version.strip().lstrip("vV").split("+", 1)[0]
    major_token = cleaned.split(".", 1)[0].split("-", 1)[0]
    if not major_token.isdigit():
        raise MigrationError(f"Cannot parse major version from {version!r}")
    return int(major_token)


def verify_dependency_versions(ctx: MigrationContext) -> None:
    """Precheck Mongo/Neo4j/ES/Kafka versions before any migration Record write."""
    settings = ctx.settings

    es_info = ctx.es_client.info()
    es_version = str(es_info["version"]["number"])
    expected_es = settings.memory_retrieval.elasticsearch_version
    if es_version != expected_es:
        raise MigrationError(
            f"Elasticsearch version {es_version!r} != expected {expected_es!r}"
        )

    mongo_info = ctx.mongo_client.server_info()
    mongo_version = str(mongo_info.get("version", ""))
    if _major_version(mongo_version) != 8:
        raise MigrationError(f"MongoDB major version must be 8, got {mongo_version!r}")

    with ctx.neo4j_driver.session() as session:
        record = session.run(
            "CALL dbms.components() YIELD name, versions, edition "
            "WHERE name = 'Neo4j Kernel' RETURN versions, edition"
        ).single()
    if record is None or not record["versions"]:
        raise MigrationError("Could not determine Neo4j server version")
    neo4j_version = str(record["versions"][0])
    if _major_version(neo4j_version) != 5:
        raise MigrationError(f"Neo4j major version must be 5, got {neo4j_version!r}")

    kafka_major = _detect_kafka_major(settings.kafka.bootstrap_servers)
    if kafka_major != 4:
        raise MigrationError(f"Kafka major version must be 4, got {kafka_major}")

    logger.info(
        "version precheck ok: es=%s mongo=%s neo4j=%s kafka_major=%s",
        es_version,
        mongo_version,
        neo4j_version,
        kafka_major,
    )


def _detect_kafka_major(bootstrap_servers: str) -> int:
    import asyncio

    from aiokafka.admin import AIOKafkaAdminClient  # type: ignore[import-untyped]
    from aiokafka.admin.config_resource import (  # type: ignore[import-untyped]
        ConfigResource,
        ConfigResourceType,
    )

    async def _run() -> int:
        admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
        await admin.start()
        try:
            cluster = await admin.describe_cluster()
            if hasattr(cluster, "to_object"):
                cluster_obj = cluster.to_object()
            elif isinstance(cluster, dict):
                cluster_obj = cluster
            else:
                cluster_obj = {
                    "brokers": getattr(cluster, "brokers", []),
                    "controller_id": getattr(cluster, "controller_id", None),
                }
            brokers = cluster_obj.get("brokers") or []
            if not brokers:
                raise MigrationError("Kafka cluster reported no brokers")
            first = brokers[0]
            if isinstance(first, dict):
                broker_id = str(first.get("node_id", first.get("id")))
            else:
                broker_id = str(first)
            responses = await admin.describe_configs(
                [ConfigResource(ConfigResourceType.BROKER, broker_id)]
            )
            configs = _broker_configs_from_responses(responses)
            for key in (
                "inter.broker.protocol.version",
                "log.message.format.version",
            ):
                if key in configs and configs[key] not in ("", "None", "null"):
                    return _major_version(configs[key])
            # Kafka 4+ (KRaft): protocol version keys removed; Share Group
            # coordinator configs are present on apache/kafka:4.x.
            if any(marker in configs for marker in _KAFKA_V4_CONFIG_MARKERS):
                return 4
            raise MigrationError(
                "Unable to determine Kafka broker major version "
                "(no protocol version keys and no Kafka-4 share coordinator markers)"
            )
        finally:
            await admin.close()

    return asyncio.run(_run())


def _broker_configs_from_responses(responses: list[Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for response in responses:
        resources = getattr(response, "resources", None)
        if resources:
            for resource in resources:
                if not isinstance(resource, (list, tuple)) or len(resource) < 4:
                    continue
                entries = resource[-1]
                for entry in entries:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        result[str(entry[0])] = str(entry[1])
            if result:
                continue
        if hasattr(response, "to_object"):
            obj = response.to_object()
            if isinstance(obj, dict):
                for resource in obj.get("resources") or []:
                    if not isinstance(resource, dict):
                        continue
                    for cfg in resource.get("config_entries") or []:
                        if isinstance(cfg, dict):
                            name = (
                                cfg.get("name")
                                or cfg.get("config_name")
                                or cfg.get("config_names")
                            )
                            value = cfg.get("value") or cfg.get("config_value")
                            if isinstance(name, str) and value is not None:
                                result[name] = str(value)
    return result


def load_upgrade(migration: MigrationFile) -> Callable[[MigrationContext], None]:
    module_name = f"scripts.migrations.{migration.migration_id}"
    # Temp dirs used by unit tests: load from path when not under package dir.
    if migration.path.parent.resolve() != MIGRATIONS_DIR.resolve():
        spec = importlib.util.spec_from_file_location(
            f"scripts.migrations._tmp_{migration.migration_id}",
            migration.path,
        )
        if spec is None or spec.loader is None:
            raise MigrationError(f"unable to load migration from {migration.path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(module_name)
    upgrade = getattr(module, "upgrade", None)
    if not callable(upgrade):
        raise MigrationError(f"{module_name} missing callable upgrade(ctx)")
    return upgrade  # type: ignore[no-any-return]


def apply_migrations(
    ctx: MigrationContext,
    migrations: Sequence[MigrationFile] | None = None,
    *,
    skip_version_precheck: bool = False,
) -> list[str]:
    """Run version precheck, bootstrap, then migrations with checksum records."""
    if not skip_version_precheck:
        verify_dependency_versions(ctx)

    db = _mongo_db(ctx.mongo_client)
    bootstrap_migrations_collection(db)
    collection = db[MIGRATIONS_COLLECTION]

    items = list(migrations) if migrations is not None else discover_migrations()
    version = app_version()
    applied: list[str] = []

    for item in items:
        checksum = compute_checksum(item.path)
        existing = collection.find_one({"migration_id": item.migration_id})
        if existing is not None:
            recorded = existing.get("checksum")
            if recorded == checksum:
                logger.info("skip %s (checksum match)", item.migration_id)
                continue
            raise MigrationError(
                f"Checksum conflict for {item.migration_id}: "
                f"recorded={recorded!r} current={checksum!r}"
            )

        upgrade = load_upgrade(item)
        logger.info("applying %s", item.migration_id)
        try:
            upgrade(ctx)
        except Exception as exc:
            raise MigrationError(
                f"Migration {item.migration_id} failed: {exc}"
            ) from exc

        collection.insert_one(
            {
                "migration_id": item.migration_id,
                "checksum": checksum,
                "applied_at": int(time.time()),
                "app_version": version,
            }
        )
        applied.append(item.migration_id)
        logger.info("recorded %s", item.migration_id)
    return applied


def main(argv: list[str] | None = None) -> int:
    _ = argv  # MVP: no CLI flags
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    settings = get_settings()
    ctx = _connect_clients(settings)
    try:
        applied = apply_migrations(ctx)
        logger.info("all migrations applied successfully applied=%s", applied)
        return 0
    except (MigrationError, PyMongoError) as exc:
        logger.error("migration failed: %s", exc)
        return 1
    except Exception:
        logger.exception("migration failed with unexpected error")
        return 1
    finally:
        _close_clients(ctx)


if __name__ == "__main__":
    sys.exit(main())
