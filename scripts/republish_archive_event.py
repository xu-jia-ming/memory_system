"""Republish context.archive.created for an existing Mongo archive (STM-011).

Run as: python -m scripts.republish_archive_event --archive-id <uuid> [--user-id <id>]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any

from aiokafka import AIOKafkaProducer  # type: ignore[import-untyped]
from pymongo import AsyncMongoClient

from memory_system.domain.enums.archive_event_republish import ArchiveEventRepublishStatus
from memory_system.domain.models.archive_event_republish import ArchiveEventRepublishInput
from memory_system.domain.services.archive_event_republish_service import (
    republish_archive_created_event,
)
from memory_system.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Republish context.archive.created for an existing Mongo archive. "
            "Run as: python -m scripts.republish_archive_event"
        ),
    )
    parser.add_argument(
        "--archive-id",
        required=True,
        help="Archive UUID to republish (required)",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="Optional ownership check; must match Mongo document user_id",
    )
    return parser


def _exit_code_for_status(status: ArchiveEventRepublishStatus) -> int:
    if status == ArchiveEventRepublishStatus.SUCCESS:
        return 0
    if status == ArchiveEventRepublishStatus.INVALID_INPUT:
        return 2
    return 1


def _kafka_producer_from_settings(settings: Settings) -> AIOKafkaProducer:
    return AIOKafkaProducer(
        bootstrap_servers=settings.kafka.bootstrap_servers,
        acks=settings.kafka_producer.acks,
        enable_idempotence=settings.kafka_producer.enable_idempotence,
        compression_type=settings.kafka_producer.compression_type,
        request_timeout_ms=settings.kafka_producer.request_timeout_ms,
        max_batch_size=settings.kafka_producer.max_batch_size,
        linger_ms=settings.kafka_producer.linger_ms,
    )


async def _async_main(
    *,
    archive_id: str,
    expected_user_id: str | None,
    settings: Settings,
) -> int:
    mongodb: AsyncMongoClient[Any] | None = None
    producer: AIOKafkaProducer | None = None
    try:
        mongodb = AsyncMongoClient(
            settings.mongodb.uri.get_secret_value(),
            serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
            connectTimeoutMS=settings.mongodb.connect_timeout_ms,
            maxPoolSize=settings.mongodb.max_pool_size,
        )
        producer = _kafka_producer_from_settings(settings)
        await producer.start()

        result = await republish_archive_created_event(
            mongodb=mongodb,
            kafka_producer=producer,
            topic=settings.kafka.topic,
            input=ArchiveEventRepublishInput(
                archive_id=archive_id,
                expected_user_id=expected_user_id,
            ),
            logger=logger,
        )

        if result.status == ArchiveEventRepublishStatus.SUCCESS:
            assert result.event_id is not None
            logger.info(
                "republish succeeded archive_id=%s event_id=%s",
                archive_id,
                result.event_id,
            )
            return _exit_code_for_status(result.status)

        if result.status == ArchiveEventRepublishStatus.ARCHIVE_NOT_FOUND:
            logger.error("republish failed archive_id=%s status=archive_not_found", archive_id)
        elif result.status == ArchiveEventRepublishStatus.ARCHIVE_OWNERSHIP_MISMATCH:
            logger.error(
                "republish failed archive_id=%s status=archive_ownership_mismatch",
                archive_id,
            )
        elif result.status == ArchiveEventRepublishStatus.INVALID_ARCHIVE:
            logger.error("republish failed archive_id=%s status=invalid_archive", archive_id)
        elif result.status == ArchiveEventRepublishStatus.KAFKA_PUBLISH_FAILED:
            logger.error(
                "republish failed archive_id=%s status=kafka_publish_failed",
                archive_id,
            )
        elif result.status == ArchiveEventRepublishStatus.INVALID_INPUT:
            logger.error("republish failed archive_id=%s status=invalid_input", archive_id)
        else:
            logger.error(
                "republish failed archive_id=%s status=%s",
                archive_id,
                result.status.value,
            )

        return _exit_code_for_status(result.status)
    except Exception:
        logger.exception("republish failed archive_id=%s unexpected error", archive_id)
        return 1
    finally:
        if producer is not None:
            await producer.stop()
        if mongodb is not None:
            await mongodb.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 2
        return int(code) if isinstance(code, int) else 2

    archive_id = (args.archive_id or "").strip()
    if not archive_id:
        logger.error("republish failed archive_id= status=invalid_input (--archive-id empty)")
        return 2

    expected_user_id = args.user_id
    if expected_user_id is not None:
        expected_user_id = expected_user_id.strip() or None

    settings = get_settings()
    return asyncio.run(
        _async_main(
            archive_id=archive_id,
            expected_user_id=expected_user_id,
            settings=settings,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
