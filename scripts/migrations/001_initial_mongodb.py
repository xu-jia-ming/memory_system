"""001 — MongoDB Collection indexes (§1.2.2, §2.1.3)."""

from __future__ import annotations

import logging

from pymongo import ASCENDING
from pymongo.errors import OperationFailure

from scripts.migrations import MigrationContext

logger = logging.getLogger(__name__)


def upgrade(ctx: MigrationContext) -> None:
    """Create context_archive and memory_extraction_task indexes (idempotent)."""
    db = ctx.mongo_client.get_default_database()
    if db is None:
        raise RuntimeError(
            "MongoDB URI must include a default database path "
            "(e.g. mongodb://host:27017/memory_system)"
        )

    try:
        archive = db["context_archive"]
        archive.create_index([("archive_id", ASCENDING)], unique=True, name="archive_id_unique")
        archive.create_index(
            [
                ("user_id", ASCENDING),
                ("session_id", ASCENDING),
                ("created_time", ASCENDING),
            ],
            name="user_session_created_time",
        )
        archive.create_index(
            [("archive_batch_key", ASCENDING)],
            unique=True,
            name="archive_batch_key_unique",
        )

        tasks = db["memory_extraction_task"]
        tasks.create_index([("archive_id", ASCENDING)], unique=True, name="archive_id_unique")
        tasks.create_index(
            [("status", ASCENDING), ("updated_time", ASCENDING)],
            name="status_updated_time",
        )
        logger.info("mongodb indexes ensured for context_archive and memory_extraction_task")
    except OperationFailure:
        logger.exception("mongodb index creation failed (possible incompatible existing index)")
        raise
