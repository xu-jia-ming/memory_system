"""004 — Kafka topic initialization and config validation (§3.19)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiokafka.admin import AIOKafkaAdminClient, NewTopic  # type: ignore[import-untyped]
from aiokafka.admin.config_resource import (  # type: ignore[import-untyped]
    ConfigResource,
    ConfigResourceType,
)
from aiokafka.errors import TopicAlreadyExistsError  # type: ignore[import-untyped]

from scripts.migrations import MigrationContext

logger = logging.getLogger(__name__)


def _topic_config_map(describe_response: Any) -> dict[str, str]:
    """Extract topic config name→value from a DescribeConfigs response."""
    obj = describe_response.to_object()
    resources = obj.get("resources") or []
    result: dict[str, str] = {}
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        error_code = resource.get("error_code", 0)
        if error_code not in (0, None):
            raise RuntimeError(
                f"describe_configs error_code={error_code} "
                f"message={resource.get('error_message')!r}"
            )
        for entry in resource.get("config_entries") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("config_names") or entry.get("name") or entry.get("config_name")
            # aiokafka field naming varies by version; try common keys
            if name is None:
                # positional fallback via raw tuple already handled by to_object keys
                for key in entry:
                    if "name" in key and key != "config_names":
                        name = entry[key]
                        break
            value = entry.get("config_value") or entry.get("value")
            if isinstance(name, str) and value is not None:
                result[name] = str(value)
    return result


def _config_entries_from_raw(response: Any) -> dict[str, str]:
    """Fallback parser when to_object field names differ across protocol versions."""
    result: dict[str, str] = {}
    resources = getattr(response, "resources", ())
    for resource in resources:
        # Typical: (error_code, error_message?, resource_type, resource_name, config_entries)
        if not isinstance(resource, (list, tuple)) or len(resource) < 4:
            continue
        error_code = resource[0]
        if error_code not in (0, None):
            raise RuntimeError(f"describe_configs error_code={error_code}")
        config_entries = resource[-1]
        for entry in config_entries:
            if isinstance(entry, dict):
                name = entry.get("config_name") or entry.get("name")
                value = entry.get("config_value") or entry.get("value")
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                name, value = entry[0], entry[1]
            else:
                continue
            if isinstance(name, str) and value is not None:
                result[name] = str(value)
    return result


async def _upgrade_async(ctx: MigrationContext) -> None:
    kafka = ctx.settings.kafka
    admin = AIOKafkaAdminClient(bootstrap_servers=kafka.bootstrap_servers)
    await admin.start()
    try:
        existing = await admin.list_topics()
        if kafka.topic not in existing:
            topic = NewTopic(
                name=kafka.topic,
                num_partitions=kafka.partitions,
                replication_factor=kafka.replication_factor,
                topic_configs={
                    "retention.ms": str(kafka.retention_ms),
                    "cleanup.policy": kafka.cleanup_policy,
                    "max.message.bytes": str(kafka.max_message_bytes),
                },
            )
            try:
                await admin.create_topics([topic])
                logger.info("kafka topic %s created", kafka.topic)
            except TopicAlreadyExistsError:
                logger.info("kafka topic %s created concurrently; validating", kafka.topic)
        else:
            logger.info("kafka topic %s already exists; validating", kafka.topic)

        described = await admin.describe_topics([kafka.topic])
        if not described:
            raise RuntimeError(f"describe_topics returned empty for {kafka.topic}")
        topic_meta = described[0]
        if not isinstance(topic_meta, dict):
            raise RuntimeError(f"unexpected topic metadata type: {type(topic_meta)!r}")
        if topic_meta.get("error_code", 0) not in (0, None):
            raise RuntimeError(
                f"describe_topics error for {kafka.topic}: {topic_meta.get('error_code')}"
            )
        partitions = topic_meta.get("partitions") or []
        if len(partitions) != kafka.partitions:
            raise RuntimeError(
                f"kafka topic {kafka.topic} partitions={len(partitions)} "
                f"!= configured {kafka.partitions}"
            )
        first = partitions[0]
        replicas = first.get("replicas") if isinstance(first, dict) else None
        if replicas is None:
            raise RuntimeError(f"kafka topic {kafka.topic} partition missing replicas")
        if len(replicas) != kafka.replication_factor:
            raise RuntimeError(
                f"kafka topic {kafka.topic} replication_factor={len(replicas)} "
                f"!= configured {kafka.replication_factor}"
            )

        resources = [ConfigResource(ConfigResourceType.TOPIC, kafka.topic)]
        responses = await admin.describe_configs(resources)
        if not responses:
            raise RuntimeError("describe_configs returned no response for topic")
        try:
            config_map = _topic_config_map(responses[0])
        except Exception:
            config_map = _config_entries_from_raw(responses[0])
        if not config_map:
            config_map = _config_entries_from_raw(responses[0])
        expected = {
            "retention.ms": str(kafka.retention_ms),
            "cleanup.policy": kafka.cleanup_policy,
            "max.message.bytes": str(kafka.max_message_bytes),
        }
        for key, expected_value in expected.items():
            actual = config_map.get(key)
            if actual is None:
                raise RuntimeError(f"kafka topic {kafka.topic} missing config {key}")
            if actual != expected_value:
                raise RuntimeError(
                    f"kafka topic {kafka.topic} config {key}={actual!r} "
                    f"!= configured {expected_value!r}"
                )
        logger.info("kafka topic %s configuration validated", kafka.topic)
    finally:
        await admin.close()


def upgrade(ctx: MigrationContext) -> None:
    """Create or validate Kafka topic from Settings (§3.19)."""
    asyncio.run(_upgrade_async(ctx))
