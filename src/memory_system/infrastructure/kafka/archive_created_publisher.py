"""Kafka publisher adapter for ``context.archive.created`` (§1.2.4)."""

from __future__ import annotations

from typing import Protocol

from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent


class KafkaProducerLike(Protocol):
    """Minimal producer surface used by the archive-created publisher."""

    async def send_and_wait(
        self,
        topic: str,
        *,
        key: bytes | None = None,
        value: bytes | None = None,
    ) -> object: ...


async def publish_archive_created_event(
    producer: KafkaProducerLike,
    topic: str,
    event: ArchiveCreatedEvent,
) -> None:
    """Publish the six-field event; Message Key is user_id (UTF-8 bytes)."""
    await producer.send_and_wait(
        topic,
        key=event.user_id.encode("utf-8"),
        value=event.to_json_bytes(),
    )
