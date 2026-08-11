"""Contract tests for EXT-001 extraction task + consumer boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from memory_system.domain.enums.extraction_task import ExtractionTaskStatus
from memory_system.domain.models.archive_created_event import (
    ARCHIVE_CREATED_EVENT_FIELD_NAMES,
    ArchiveCreatedEvent,
)
from memory_system.domain.models.extraction_task import MemoryExtractionTask
from memory_system.infrastructure.kafka.archive_created_consumer import (
    MEMORY_EXTRACTION_CONSUMER_GROUP,
)
from memory_system.settings.models import KafkaConsumerSettings

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_001 = REPO_ROOT / "scripts" / "migrations" / "001_initial_mongodb.py"
ARCHIVE_EVENT_SRC = (
    REPO_ROOT / "src" / "memory_system" / "domain" / "models" / "archive_created_event.py"
)

C1_FIELDS = {
    "task_id",
    "archive_id",
    "user_id",
    "status",
    "attempt_count",
    "extraction_result",
    "last_error",
    "created_time",
    "updated_time",
    "completed_time",
}


def test_task_json_field_set_equals_c1() -> None:
    task = MemoryExtractionTask(
        task_id="11111111-1111-4111-8111-111111111111",
        archive_id="a",
        user_id="u",
        status=ExtractionTaskStatus.PENDING,
        attempt_count=0,
        extraction_result=None,
        last_error=None,
        created_time=1,
        updated_time=1,
        completed_time=None,
    )
    assert set(task.model_dump().keys()) == C1_FIELDS
    assert "session_id" not in task.model_dump()
    assert "event_id" not in task.model_dump()
    assert "event_type" not in task.model_dump()


def test_status_enum_exact_four() -> None:
    assert {s.value for s in ExtractionTaskStatus} == {
        "pending",
        "processing",
        "completed",
        "failed",
    }


def test_consumer_group_literal() -> None:
    assert MEMORY_EXTRACTION_CONSUMER_GROUP == "memory-extraction-group"


def test_kafka_consumer_settings_defaults() -> None:
    settings = KafkaConsumerSettings()
    assert settings.enable_auto_commit is False
    assert settings.max_poll_records == 1
    assert settings.auto_offset_reset == "earliest"


def test_migration_001_contains_extraction_task_index_names() -> None:
    source = MIGRATION_001.read_text(encoding="utf-8")
    assert 'db["memory_extraction_task"]' in source or "memory_extraction_task" in source
    assert 'name="archive_id_unique"' in source
    assert 'name="status_updated_time"' in source
    # Both indexes appear in the extraction-task block
    assert source.index("memory_extraction_task") < source.index('name="status_updated_time"')


def test_archive_created_event_still_no_extra_forbid() -> None:
    source = ARCHIVE_EVENT_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ArchiveCreatedEvent"
    )
    config_assign = None
    for stmt in class_node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "model_config":
                    config_assign = stmt
    assert config_assign is not None
    dumped = ast.dump(config_assign)
    assert "extra" not in dumped or "forbid" not in dumped
    # Runtime: model_config must not forbid extras
    assert ArchiveCreatedEvent.model_config.get("extra") != "forbid"


def test_archive_created_field_names_six_tuple() -> None:
    assert ARCHIVE_CREATED_EVENT_FIELD_NAMES == (
        "event_id",
        "event_type",
        "archive_id",
        "user_id",
        "session_id",
        "created_time",
    )
    assert len(ARCHIVE_CREATED_EVENT_FIELD_NAMES) == 6
