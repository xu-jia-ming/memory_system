"""EXT-005 reconciliation LLM orchestration (§2.1.11 / LD-3)."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import TYPE_CHECKING, Literal

import structlog

from memory_system.domain.models.memory_recall import MemoryNodeSnapshot
from memory_system.domain.models.reconciliation import (
    AlignedMemoryCandidateView,
    ReasonCode,
    ReconciliationAction,
    ReconciliationErrorCode,
    ReconciliationFailure,
    ReconciliationLlmOutput,
    ReconciliationOutcome,
    ReconciliationOutcomeKind,
)
from memory_system.domain.services.aligned_memory_key import (
    normalize_memory_content_for_aggregation,
)
from memory_system.infrastructure.llm.deepseek_client import DeepSeekLlmClient
from memory_system.infrastructure.llm.errors import LlmServiceError
from memory_system.settings.models import Settings

if TYPE_CHECKING:
    from memory_system.infrastructure.llm.protocol import LLMClient

MAX_SCHEMA_ATTEMPTS = 2
FAILED_STAGE = "reconciliation"
RECONCILIATION_PROMPT_VERSION = "memory_reconciliation_v1"

RECONCILIATION_SYSTEM_PROMPT = (
    "You are a memory reconciliation engine.\n"
    "\n"
    "Compare one new memory candidate against existing memories and decide the action.\n"
    "\n"
    "Requirements:\n"
    "1. Return only valid JSON matching the required schema.\n"
    "2. action must be one of CREATE, MERGE, SUPERSEDE, CONFLICT, or SKIP.\n"
    "3. target_memory_id must reference an existing_memories memory_id when required.\n"
    "4. merged_content may only combine candidate content and target memory content.\n"
    "5. Use candidate_source_time versus latest_source_time to judge recency.\n"
    "6. Do not output free-form reasoning."
)

SCHEMA_CORRECTION_INSTRUCTION = (
    "The previous response was invalid.\n"
    "Return exactly one valid JSON object matching the required reconciliation schema.\n"
    "Return JSON only."
)

_logger = structlog.get_logger(__name__)
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _is_blank_content(content: str) -> bool:
    return content.strip() == ""


def _build_llm_user_prompt(
    candidate: AlignedMemoryCandidateView,
    existing_memories: list[MemoryNodeSnapshot],
) -> str:
    payload = {
        "candidate": {
            "memory_type": candidate.memory_type,
            "content": candidate.content,
            "subject_entity_id": candidate.subject_entity_id,
            "predicate": candidate.predicate,
            "object_entity_id": candidate.object_entity_id,
            "object_value": candidate.object_value,
            "event_status": candidate.event_status,
            "start_time": candidate.start_time,
            "end_time": candidate.end_time,
            "original_time_text": candidate.original_time_text,
            "candidate_source_time": candidate.candidate_source_time,
        },
        "existing_memories": [
            {
                "memory_id": memory.memory_id,
                "memory_type": memory.memory_type,
                "content": memory.content,
                "subject_entity_id": memory.subject_entity_id,
                "predicate": memory.predicate,
                "object_entity_id": memory.object_entity_id,
                "object_value": memory.object_value,
                "event_status": memory.event_status,
                "start_time": memory.start_time,
                "end_time": memory.end_time,
                "original_time_text": memory.original_time_text,
                "status": memory.status,
                "confidence": memory.confidence,
                "latest_source_time": memory.latest_source_time,
            }
            for memory in existing_memories
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _merged_content_uses_only_sources(
    merged_content: str,
    candidate_content: str,
    target_content: str,
) -> bool:
    normalized_merged = normalize_memory_content_for_aggregation(merged_content)
    normalized_candidate = normalize_memory_content_for_aggregation(candidate_content)
    normalized_target = normalize_memory_content_for_aggregation(target_content)

    if not normalized_merged:
        return False
    if normalized_merged in {normalized_candidate, normalized_target}:
        return True

    merged_chars = Counter(_WHITESPACE_PATTERN.sub("", normalized_merged))
    source_chars = Counter(
        _WHITESPACE_PATTERN.sub("", normalized_candidate + normalized_target)
    )
    return all(merged_chars[char] <= source_chars[char] for char in merged_chars)


def _validate_llm_output(
    output: ReconciliationLlmOutput,
    *,
    candidate: AlignedMemoryCandidateView,
    existing_memories: list[MemoryNodeSnapshot],
) -> bool:
    existing_ids = {memory.memory_id for memory in existing_memories}
    target_id = output.target_memory_id

    if output.action in {ReconciliationAction.CREATE, ReconciliationAction.SKIP}:
        if target_id is not None:
            return False
    elif target_id is None or target_id not in existing_ids:
        return False

    target_memory: MemoryNodeSnapshot | None = None
    if target_id is not None:
        target_memory = next(
            (memory for memory in existing_memories if memory.memory_id == target_id),
            None,
        )
        if target_memory is None:
            return False

    if output.reason_code == ReasonCode.ADDITIONAL_EVIDENCE and target_memory is not None:
        candidate_norm = normalize_memory_content_for_aggregation(candidate.content)
        target_norm = normalize_memory_content_for_aggregation(target_memory.content)
        has_new_info = candidate_norm != target_norm
        if has_new_info and output.merged_content is None:
            return False
        if not has_new_info and output.merged_content is not None:
            return False

    if output.merged_content is not None:
        if target_memory is None:
            return False
        if not _merged_content_uses_only_sources(
            output.merged_content,
            candidate.content,
            target_memory.content,
        ):
            return False

    return True


def _parse_llm_output(raw: dict[str, object]) -> ReconciliationLlmOutput | None:
    try:
        return ReconciliationLlmOutput.model_validate(raw, strict=False)
    except Exception:
        return None


def _failure_outcome(
    error_code: ReconciliationErrorCode,
) -> ReconciliationOutcome:
    return ReconciliationOutcome(
        outcome=ReconciliationOutcomeKind.FAILURE,
        success=None,
        failure=ReconciliationFailure(error_code=error_code),
    )


async def run_reconciliation_llm(
    *,
    task_id: str,
    archive_id: str,
    user_id: str,
    candidate: AlignedMemoryCandidateView,
    existing_memories: list[MemoryNodeSnapshot],
    llm_client: LLMClient,
    settings: Settings,
    attempt_count: int | None = None,
) -> ReconciliationOutcome | ReconciliationLlmOutput:
    """Run reconciliation LLM with schema correction retry and validation."""
    extraction_llm = settings.llm.extraction
    memory_extraction = settings.memory_extraction
    model = extraction_llm.model
    timeout_seconds = float(memory_extraction.llm_timeout_seconds)
    max_output_tokens = extraction_llm.max_output_tokens

    system_prompt = RECONCILIATION_SYSTEM_PROMPT
    user_prompt = _build_llm_user_prompt(candidate, existing_memories)
    correction_user_prompt = f"{user_prompt}\n\n{SCHEMA_CORRECTION_INSTRUCTION}"

    for attempt in range(MAX_SCHEMA_ATTEMPTS):
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
            mapped: Literal[
                ReconciliationErrorCode.LLM_TIMEOUT,
                ReconciliationErrorCode.LLM_REQUEST_FAILED,
            ]
            if exc.code == "llm_timeout":
                mapped = ReconciliationErrorCode.LLM_TIMEOUT
            else:
                mapped = ReconciliationErrorCode.LLM_REQUEST_FAILED
            log_kwargs: dict[str, str | int] = {
                "task_id": task_id,
                "archive_id": archive_id,
                "user_id": user_id,
                "failed_stage": FAILED_STAGE,
            }
            if attempt_count is not None:
                log_kwargs["attempt_count"] = attempt_count
            _logger.warning("reconciliation llm failed", error_code=mapped.value, **log_kwargs)
            return _failure_outcome(mapped)

        if _is_blank_content(raw_content):
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            return _failure_outcome(ReconciliationErrorCode.LLM_INVALID_OUTPUT)

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            return _failure_outcome(ReconciliationErrorCode.LLM_INVALID_OUTPUT)

        if not isinstance(parsed, dict):
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            return _failure_outcome(ReconciliationErrorCode.LLM_INVALID_OUTPUT)

        output = _parse_llm_output(parsed)
        if output is None:
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            return _failure_outcome(ReconciliationErrorCode.LLM_INVALID_OUTPUT)

        if not _validate_llm_output(
            output,
            candidate=candidate,
            existing_memories=existing_memories,
        ):
            if attempt < MAX_SCHEMA_ATTEMPTS - 1:
                continue
            return _failure_outcome(ReconciliationErrorCode.LLM_INVALID_OUTPUT)

        return output

    return _failure_outcome(ReconciliationErrorCode.LLM_INVALID_OUTPUT)
