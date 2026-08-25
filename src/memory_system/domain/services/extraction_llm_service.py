"""EXT-003 extraction LLM orchestration, validation, fingerprint, and pipeline handoff."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import structlog
from pydantic import ValidationError
from pymongo import AsyncMongoClient

from memory_system.domain.models.archive_created_event import ArchiveCreatedEvent
from memory_system.domain.models.extraction_llm import (
    AUTHORIZED_ENTITY_FIELDS,
    AUTHORIZED_MEMORY_FIELDS,
    ENTITY_TYPES,
    EVENT_STATUSES,
    MEMORY_TYPES,
    RESERVED_USER_ENTITY_ID,
    ExtractionEntityCandidate,
    ExtractionLlmFailure,
    ExtractionLlmInput,
    ExtractionLlmOutcome,
    ExtractionLlmResult,
    ExtractionLlmSuccess,
    ExtractionMemoryCandidate,
    ExtractionValidatedResult,
)
from memory_system.domain.models.extraction_preprocessing import ExtractionReadyArchive
from memory_system.domain.models.extraction_task import ExtractionLastError, MemoryExtractionTask
from memory_system.domain.services.extraction_archive_preprocessing_service import (
    ExtractionArchivePreprocessingService,
)
from memory_system.domain.services.extraction_fingerprint import compute_candidate_fingerprint
from memory_system.domain.services.extraction_pipeline_port import (
    ExtractionPipelinePort,
    PipelineTerminalDecision,
)
from memory_system.domain.services.extraction_redaction_service import REDACTION_MARKER
from memory_system.infrastructure.llm.deepseek_client import DeepSeekLlmClient
from memory_system.infrastructure.llm.errors import LlmServiceError
from memory_system.infrastructure.mongodb import extraction_task_repository as task_repo
from memory_system.settings.models import MemoryExtractionSettings, Settings

if TYPE_CHECKING:
    from memory_system.infrastructure.llm.protocol import LLMClient

MAX_SCHEMA_ATTEMPTS = 2
FAILED_STAGE = "llm_extraction"

EXTRACTION_SYSTEM_PROMPT = (
    "You are a long-term memory extraction engine.\n"
    "\n"
    "Your task is to extract only durable and reusable memories from archived "
    "conversation messages.\n"
    "\n"
    "Requirements:\n"
    "1. Extract only memories supported by the provided messages.\n"
    "2. Every memory must include at least one source message whose role is user.\n"
    "3. Assistant messages may provide context, but must never be the only evidence.\n"
    "4. Classify each memory as fact, preference, event, or profile.\n"
    "\n"
    "Memory type definitions (apply the classification order below when multiple "
    "types could apply):\n"
    "- preference: an explicit like, dislike, style, or choice tendency.\n"
    "  Example: the user prefers replies in Chinese.\n"
    "- event: an action, change, or experience anchored to a specific time "
    "(past, ongoing, or planned).\n"
    "  Example: the user plans to submit a paper next week.\n"
    "- profile: a relatively long-term identity, role, occupation, ability, or "
    "long-term goal.\n"
    "  Example: the user is a backend developer.\n"
    "- fact: any other currently true objective state, attribute, or relation "
    "without emphasizing the change process.\n"
    "  Example: the user currently uses Java for backend development.\n"
    "\n"
    "Classification order:\n"
    "1. Classify explicit preferences, dislikes, or style as preference.\n"
    "2. Classify time-anchored actions, changes, or experiences as event.\n"
    "3. Classify long-term identity, occupation, ability, or long-term goals as "
    "profile.\n"
    "4. Classify all remaining current objective states, attributes, or relations "
    "as fact.\n"
    "\n"
    "One utterance may produce both an event and a resulting fact. Express the "
    "change process and the resulting current state as separate memories. Do not "
    "create semantically duplicate memories.\n"
    "\n"
    "5. Each memory must express one atomic meaning. Split unrelated information "
    "into separate memories.\n"
    '6. Resolve first-person references such as "I" and "my" to the current user entity.\n'
    "7. Preserve explicit corrections, negations, temporal order, event status and "
    "unresolved conflicts.\n"
    "8. Preserve the original time expression. Resolve relative time only when the source "
    "timestamp and timezone are both available.\n"
    "9. For non-event memories, set all event-related fields to null.\n"
    "10. Do not infer hidden attributes, intentions, diagnoses or relationships.\n"
    "11. Do not extract greetings, temporary formatting requests, unsupported assistant "
    "suggestions, secrets or authentication credentials.\n"
    "12. Use lower_snake_case for predicate.\n"
    "13. Return only valid JSON matching the required schema."
)

EXTRACTION_USER_PROMPT_TEMPLATE = """Current user ID:
{user_id}

Archived conversation messages:
{messages}

Extract durable long-term memory candidates."""

SCHEMA_CORRECTION_INSTRUCTION = (
    "The previous response was invalid.\n"
    "Return exactly one valid JSON object matching the required extraction schema, "
    "using only source_message_ids from the provided archive.\n"
    "Return JSON only."
)

_PREDICATE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
_ISO_UTC_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
)
_YEAR_PATTERN = re.compile(r"^\d{4}$")
_YEAR_MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
_YEAR_MONTH_DAY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_logger = structlog.get_logger(__name__)
Clock = Callable[[], int]


def _code_point_len(value: str) -> int:
    return len(value)


def _is_blank_content(content: str) -> bool:
    return content.strip() == ""


def _is_valid_time_value(value: str) -> bool:
    return bool(
        _ISO_UTC_PATTERN.match(value)
        or _YEAR_PATTERN.match(value)
        or _YEAR_MONTH_PATTERN.match(value)
        or _YEAR_MONTH_DAY_PATTERN.match(value)
    )


def render_extraction_user_prompt(archive: ExtractionReadyArchive) -> str:
    messages_payload = [
        {
            "message_id": message.message_id,
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp,
        }
        for message in archive.messages
    ]
    messages_json = json.dumps(messages_payload, ensure_ascii=False, separators=(",", ":"))
    return EXTRACTION_USER_PROMPT_TEMPLATE.format(
        user_id=archive.user_id,
        messages=messages_json,
    )


def _strip_unknown_fields(raw: dict[str, Any]) -> dict[str, Any]:
    entities_raw = raw.get("entities")
    memories_raw = raw.get("memories")
    if not isinstance(entities_raw, list) or not isinstance(memories_raw, list):
        raise ValueError("top-level arrays invalid")
    entities: list[dict[str, Any]] = []
    for item in entities_raw:
        if not isinstance(item, dict):
            raise ValueError("entity must be object")
        entities.append({key: item[key] for key in AUTHORIZED_ENTITY_FIELDS if key in item})
    memories: list[dict[str, Any]] = []
    for item in memories_raw:
        if not isinstance(item, dict):
            raise ValueError("memory must be object")
        memories.append({key: item[key] for key in AUTHORIZED_MEMORY_FIELDS if key in item})
    return {"entities": entities, "memories": memories}


def _validate_entity(
    raw: dict[str, Any],
    *,
    limits: MemoryExtractionSettings,
    seen_ids: set[str],
) -> ExtractionEntityCandidate:
    local_entity_id = raw.get("local_entity_id")
    name = raw.get("name")
    entity_type = raw.get("type")
    aliases = raw.get("aliases")
    if not isinstance(local_entity_id, str) or not local_entity_id:
        raise ValueError("local_entity_id invalid")
    if local_entity_id in seen_ids:
        raise ValueError("duplicate local_entity_id")
    if not isinstance(name, str) or not name:
        raise ValueError("entity name invalid")
    if _code_point_len(name) > limits.max_entity_name_characters:
        raise ValueError("entity name too long")
    if not isinstance(entity_type, str) or entity_type not in ENTITY_TYPES:
        raise ValueError("entity type invalid")
    if not isinstance(aliases, list):
        raise ValueError("aliases invalid")
    if len(aliases) > limits.max_entity_alias_count_per_candidate:
        raise ValueError("too many aliases")
    normalized_aliases: list[str] = []
    for alias in aliases:
        if not isinstance(alias, str):
            raise ValueError("alias invalid")
        if _code_point_len(alias) > limits.max_entity_alias_characters:
            raise ValueError("alias too long")
        normalized_aliases.append(alias)
    seen_ids.add(local_entity_id)
    return ExtractionEntityCandidate(
        local_entity_id=local_entity_id,
        name=name,
        type=entity_type,  # type: ignore[arg-type]
        aliases=normalized_aliases,
    )


def _validate_memory(
    raw: dict[str, Any],
    *,
    limits: MemoryExtractionSettings,
    local_entity_ids: set[str],
    archive: ExtractionReadyArchive,
) -> ExtractionMemoryCandidate:
    for forbidden in ("candidate_source_time", "candidate_fingerprint"):
        if forbidden in raw:
            raise ValueError("application-owned field present")

    memory_type = raw.get("memory_type")
    content = raw.get("content")
    subject_entity_id = raw.get("subject_entity_id")
    predicate = raw.get("predicate")
    object_entity_id = raw.get("object_entity_id")
    object_value = raw.get("object_value")
    event_status = raw.get("event_status")
    start_time = raw.get("start_time")
    end_time = raw.get("end_time")
    original_time_text = raw.get("original_time_text")
    confidence = raw.get("confidence")
    source_message_ids = raw.get("source_message_ids")

    if not isinstance(memory_type, str) or memory_type not in MEMORY_TYPES:
        raise ValueError("memory_type invalid")
    if not isinstance(content, str) or not content:
        raise ValueError("content invalid")
    if REDACTION_MARKER in content:
        raise ValueError("redaction marker in content")
    if _code_point_len(content) > limits.max_memory_content_characters:
        raise ValueError("content too long")
    if not isinstance(subject_entity_id, str):
        raise ValueError("subject_entity_id invalid")
    if subject_entity_id != RESERVED_USER_ENTITY_ID and subject_entity_id not in local_entity_ids:
        raise ValueError("subject_entity_id reference invalid")
    if not isinstance(predicate, str) or not predicate:
        raise ValueError("predicate invalid")
    if not _PREDICATE_PATTERN.match(predicate):
        raise ValueError("predicate not lower_snake_case")
    if _code_point_len(predicate) > limits.max_predicate_characters:
        raise ValueError("predicate too long")

    object_entity_present = object_entity_id is not None
    object_value_present = object_value is not None
    if object_entity_present == object_value_present:
        raise ValueError("object xor invalid")
    if object_entity_id is not None:
        if not isinstance(object_entity_id, str):
            raise ValueError("object_entity_id invalid")
        if (
            object_entity_id != RESERVED_USER_ENTITY_ID
            and object_entity_id not in local_entity_ids
        ):
            raise ValueError("object_entity_id reference invalid")
    if object_value is not None:
        if not isinstance(object_value, str):
            raise ValueError("object_value invalid")
        if REDACTION_MARKER in object_value:
            raise ValueError("redaction marker in object_value")
        if _code_point_len(object_value) > limits.max_object_value_characters:
            raise ValueError("object_value too long")

    if memory_type == "event":
        if not isinstance(event_status, str) or event_status not in EVENT_STATUSES:
            raise ValueError("event_status invalid for event")
    else:
        if event_status is not None:
            raise ValueError("event_status must be null for non-event")
        if start_time is not None:
            raise ValueError("start_time must be null for non-event")
        if end_time is not None:
            raise ValueError("end_time must be null for non-event")
        if original_time_text is not None:
            raise ValueError("original_time_text must be null for non-event")

    for time_field, time_value in (("start_time", start_time), ("end_time", end_time)):
        if time_value is not None:
            if not isinstance(time_value, str) or not _is_valid_time_value(time_value):
                raise ValueError(f"{time_field} invalid")

    if original_time_text is not None:
        if not isinstance(original_time_text, str):
            raise ValueError("original_time_text invalid")
        if _code_point_len(original_time_text) > limits.max_original_time_text_characters:
            raise ValueError("original_time_text too long")

    if not isinstance(confidence, (int, float)):
        raise ValueError("confidence invalid")
    confidence_value = float(confidence)
    if confidence_value < 0.0 or confidence_value > 1.0:
        raise ValueError("confidence out of range")

    if not isinstance(source_message_ids, list) or not source_message_ids:
        raise ValueError("source_message_ids invalid")
    normalized_source_ids: list[str] = []
    message_by_id = {message.message_id: message for message in archive.messages}
    has_user_source = False
    for source_id in source_message_ids:
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_message_id invalid")
        message = message_by_id.get(source_id)
        if message is None:
            raise ValueError("source_message_id not in archive")
        if message.role == "user":
            has_user_source = True
        normalized_source_ids.append(source_id)
    if not has_user_source:
        raise ValueError("missing user source")

    user_timestamps = [
        message_by_id[source_id].timestamp
        for source_id in normalized_source_ids
        if message_by_id[source_id].role == "user"
    ]
    candidate_source_time = max(user_timestamps)
    deduped_sorted_sources = sorted(set(normalized_source_ids))
    fingerprint = compute_candidate_fingerprint(
        memory_type=memory_type,
        content=content,
        subject_entity_id=subject_entity_id,
        predicate=predicate,
        object_entity_id=object_entity_id,
        object_value=object_value,
        event_status=event_status,
        start_time=start_time,
        end_time=end_time,
        original_time_text=original_time_text,
        source_message_ids=deduped_sorted_sources,
    )
    return ExtractionMemoryCandidate(
        memory_type=memory_type,  # type: ignore[arg-type]
        content=content,
        subject_entity_id=subject_entity_id,
        predicate=predicate,
        object_entity_id=object_entity_id,
        object_value=object_value,
        event_status=event_status,  # type: ignore[arg-type]
        start_time=start_time,
        end_time=end_time,
        original_time_text=original_time_text,
        confidence=confidence_value,
        source_message_ids=deduped_sorted_sources,
        candidate_source_time=candidate_source_time,
        candidate_fingerprint=fingerprint,
    )


def _memory_equivalence_key(memory: ExtractionMemoryCandidate) -> tuple[Any, ...]:
    return (
        memory.memory_type,
        memory.content,
        memory.subject_entity_id,
        memory.predicate,
        memory.object_entity_id,
        memory.object_value,
        memory.event_status,
        memory.start_time,
        memory.end_time,
        memory.original_time_text,
        memory.confidence,
    )


def _merge_duplicate_memories(
    memories: list[ExtractionMemoryCandidate],
) -> list[ExtractionMemoryCandidate]:
    merged: list[ExtractionMemoryCandidate] = []
    index_by_key: dict[tuple[Any, ...], int] = {}
    for memory in memories:
        key = _memory_equivalence_key(memory)
        if key not in index_by_key:
            index_by_key[key] = len(merged)
            merged.append(memory)
            continue
        existing = merged[index_by_key[key]]
        combined_sources = sorted(set(existing.source_message_ids) | set(memory.source_message_ids))
        merged[index_by_key[key]] = existing.model_copy(
            update={
                "source_message_ids": combined_sources,
                "candidate_source_time": max(
                    existing.candidate_source_time, memory.candidate_source_time
                ),
                "candidate_fingerprint": compute_candidate_fingerprint(
                    memory_type=existing.memory_type,
                    content=existing.content,
                    subject_entity_id=existing.subject_entity_id,
                    predicate=existing.predicate,
                    object_entity_id=existing.object_entity_id,
                    object_value=existing.object_value,
                    event_status=existing.event_status,
                    start_time=existing.start_time,
                    end_time=existing.end_time,
                    original_time_text=existing.original_time_text,
                    source_message_ids=combined_sources,
                ),
            }
        )
    return merged


def validate_extraction_payload(
    parsed: dict[str, Any],
    *,
    archive: ExtractionReadyArchive,
    limits: MemoryExtractionSettings,
) -> ExtractionValidatedResult:
    stripped = _strip_unknown_fields(parsed)
    entities: list[ExtractionEntityCandidate] = []
    seen_ids: set[str] = set()
    for raw_entity in stripped["entities"]:
        entities.append(_validate_entity(raw_entity, limits=limits, seen_ids=seen_ids))
    if len(entities) > limits.max_entity_candidates_per_archive:
        raise ValueError("too many entities")
    local_entity_ids = {entity.local_entity_id for entity in entities}
    memories: list[ExtractionMemoryCandidate] = []
    for raw_memory in stripped["memories"]:
        memories.append(
            _validate_memory(
                raw_memory,
                limits=limits,
                local_entity_ids=local_entity_ids,
                archive=archive,
            )
        )
    if len(memories) > limits.max_memory_candidates_per_archive:
        raise ValueError("too many memories")
    merged_memories = _merge_duplicate_memories(memories)
    return ExtractionValidatedResult(entities=entities, memories=merged_memories)


def is_both_empty_extraction_result(result: dict[str, Any]) -> bool:
    entities = result.get("entities")
    memories = result.get("memories")
    return entities == [] and memories == []


def _log_failure(
    *,
    task_id: str,
    archive_id: str,
    user_id: str,
    failed_stage: str,
    attempt_count: int,
    error_code: str,
) -> None:
    _logger.error(
        "extraction llm failed",
        task_id=task_id,
        archive_id=archive_id,
        user_id=user_id,
        failed_stage=failed_stage,
        attempt_count=attempt_count,
        error_code=error_code,
    )


def _failure_result(
    *,
    error_code: Literal["llm_timeout", "llm_request_failed", "llm_invalid_output"],
    attempt_count: int,
) -> ExtractionLlmResult:
    return ExtractionLlmResult(
        outcome=ExtractionLlmOutcome.FAILURE,
        failure=ExtractionLlmFailure(error_code=error_code, attempt_count=attempt_count),
    )


async def run_extraction_llm(
    input: ExtractionLlmInput,
    llm_client: LLMClient,
    settings: Settings,
) -> ExtractionLlmResult:
    """Run extraction LLM with schema correction retry and validation."""
    extraction_llm = settings.llm.extraction
    memory_extraction = settings.memory_extraction
    model = extraction_llm.model
    timeout_seconds = float(memory_extraction.llm_timeout_seconds)
    max_output_tokens = extraction_llm.max_output_tokens

    system_prompt = EXTRACTION_SYSTEM_PROMPT
    user_prompt = render_extraction_user_prompt(input.archive)
    correction_user_prompt = f"{user_prompt}\n\n{SCHEMA_CORRECTION_INSTRUCTION}"

    start = time.perf_counter()

    for attempt in range(MAX_SCHEMA_ATTEMPTS):
        attempt_number = attempt + 1
        current_user_prompt = user_prompt if attempt == 0 else correction_user_prompt
        try:
            if isinstance(llm_client, DeepSeekLlmClient):
                raw_content = await llm_client.generate_structured(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=current_user_prompt,
                    timeout_seconds=timeout_seconds,
                    max_output_tokens=max_output_tokens,
                    settings_profile="extraction",
                )
            else:
                raw_content = await llm_client.generate_structured(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=current_user_prompt,
                    timeout_seconds=timeout_seconds,
                    max_output_tokens=max_output_tokens,
                )
        except LlmServiceError as exc:
            mapped: Literal["llm_timeout", "llm_request_failed"]
            if exc.code == "llm_timeout":
                mapped = "llm_timeout"
            else:
                mapped = "llm_request_failed"
            _log_failure(
                task_id=input.task_id,
                archive_id=input.archive_id,
                user_id=input.user_id,
                failed_stage=FAILED_STAGE,
                attempt_count=attempt_number,
                error_code=mapped,
            )
            return _failure_result(error_code=mapped, attempt_count=attempt_number)

        if _is_blank_content(raw_content):
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            _log_failure(
                task_id=input.task_id,
                archive_id=input.archive_id,
                user_id=input.user_id,
                failed_stage=FAILED_STAGE,
                attempt_count=MAX_SCHEMA_ATTEMPTS,
                error_code="llm_invalid_output",
            )
            return _failure_result(
                error_code="llm_invalid_output",
                attempt_count=MAX_SCHEMA_ATTEMPTS,
            )

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            _log_failure(
                task_id=input.task_id,
                archive_id=input.archive_id,
                user_id=input.user_id,
                failed_stage=FAILED_STAGE,
                attempt_count=MAX_SCHEMA_ATTEMPTS,
                error_code="llm_invalid_output",
            )
            return _failure_result(
                error_code="llm_invalid_output",
                attempt_count=MAX_SCHEMA_ATTEMPTS,
            )

        if not isinstance(parsed, dict):
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            _log_failure(
                task_id=input.task_id,
                archive_id=input.archive_id,
                user_id=input.user_id,
                failed_stage=FAILED_STAGE,
                attempt_count=MAX_SCHEMA_ATTEMPTS,
                error_code="llm_invalid_output",
            )
            return _failure_result(
                error_code="llm_invalid_output",
                attempt_count=MAX_SCHEMA_ATTEMPTS,
            )

        try:
            validated = validate_extraction_payload(
                parsed,
                archive=input.archive,
                limits=memory_extraction,
            )
        except (ValueError, ValidationError):
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            _log_failure(
                task_id=input.task_id,
                archive_id=input.archive_id,
                user_id=input.user_id,
                failed_stage=FAILED_STAGE,
                attempt_count=MAX_SCHEMA_ATTEMPTS,
                error_code="llm_invalid_output",
            )
            return _failure_result(
                error_code="llm_invalid_output",
                attempt_count=MAX_SCHEMA_ATTEMPTS,
            )

        del start  # duration observability reserved without content logging
        return ExtractionLlmResult(
            outcome=ExtractionLlmOutcome.SUCCESS,
            success=ExtractionLlmSuccess(result=validated, attempt_count=attempt_number),
        )

    raise RuntimeError("extraction LLM attempt loop exhausted without result")


class ExtractionLlmService(ExtractionPipelinePort):
    """Single orchestration owner for EXT-003 pipeline handoff."""

    def __init__(
        self,
        mongodb: AsyncMongoClient[Any],
        llm_client: LLMClient,
        settings: Settings,
        *,
        preprocessing: ExtractionArchivePreprocessingService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._mongodb = mongodb
        self._llm_client = llm_client
        self._settings = settings
        self._preprocessing = preprocessing or ExtractionArchivePreprocessingService(
            mongodb,
            max_archive_estimated_tokens=settings.memory_extraction.max_archive_estimated_tokens,
        )
        self._clock = clock or (lambda: int(time.time()))

    async def run(
        self,
        task: MemoryExtractionTask,
        event: ArchiveCreatedEvent,
    ) -> PipelineTerminalDecision:
        if task.extraction_result is not None:
            if is_both_empty_extraction_result(task.extraction_result):
                return PipelineTerminalDecision.complete()
            return PipelineTerminalDecision.abort_without_terminal()

        prepare_decision, ready = await self._preprocessing.prepare(task, event)
        if prepare_decision.kind.value != "complete":
            return prepare_decision
        if ready is None:
            return PipelineTerminalDecision.abort_without_terminal()
        if not ready.messages:
            return PipelineTerminalDecision.complete()

        llm_result = await run_extraction_llm(
            ExtractionLlmInput(
                archive=ready,
                task_id=task.task_id,
                archive_id=task.archive_id,
                user_id=task.user_id,
            ),
            self._llm_client,
            self._settings,
        )
        if llm_result.outcome == ExtractionLlmOutcome.FAILURE:
            assert llm_result.failure is not None
            return PipelineTerminalDecision.fail(
                ExtractionLastError(
                    error_code=llm_result.failure.error_code,
                    failed_stage=llm_result.failure.failed_stage,
                    message="extraction llm failed",
                )
            )

        assert llm_result.success is not None
        validated = llm_result.success.result
        now = self._clock()
        try:
            persisted = await task_repo.set_extraction_result(
                self._mongodb,
                archive_id=task.archive_id,
                extraction_result=validated.to_durable_dict(),
                now=now,
            )
        except Exception:
            return PipelineTerminalDecision.abort_without_terminal()
        if persisted is None:
            return PipelineTerminalDecision.abort_without_terminal()

        if validated.is_both_empty():
            return PipelineTerminalDecision.complete()
        return PipelineTerminalDecision.abort_without_terminal()
