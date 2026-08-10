"""Kafka infrastructure adapters."""

from memory_system.infrastructure.kafka.archive_created_publisher import (
    publish_archive_created_event,
)

__all__ = ["publish_archive_created_event"]
