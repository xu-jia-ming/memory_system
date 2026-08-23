"""Shared LoCoMo answer flow: optional NO_INFO evidence expand with single retry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from deterministic_temporal_resolver import TemporalResolutionTelemetry
from memory_evidence_context import (
    SourceMessageIndex,
    append_expanded_evidence_context,
    collect_shown_source_message_ids,
    expandable_source_message_ids,
    format_additional_evidence,
    format_memories,
)
from prompts import ANSWER_USER_PROMPT, is_no_info


class AnswerLlmClient(Protocol):
    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_object: bool = False,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class AnswerOutcome:
    generated: str
    initial_generated: str
    memories_text: str
    retry_attempted: bool
    expand_applied: bool
    expanded_message_ids: tuple[str, ...]
    answer_llm_calls: int


def normalize_generated_answer(raw: str) -> str:
    text = str(raw or "").strip()
    if text.upper().startswith("ANSWER:"):
        return text.split(":", 1)[1].strip()
    return text


async def answer_with_no_info_expand_retry(
    llm: AnswerLlmClient,
    *,
    system_prompt: str,
    question: str,
    reference_date: str,
    retrieval: dict[str, Any],
    source_index: SourceMessageIndex | None,
    max_evidence_per_memory: int | None,
    enable_no_info_evidence_expand: bool = True,
    enable_deterministic_temporal_resolver: bool = True,
    temporal_telemetry: TemporalResolutionTelemetry | None = None,
) -> AnswerOutcome:
    """Answer once; on NO_INFO optionally expand provenance and retry at most once."""
    memories_text = format_memories(
        retrieval,
        source_index,
        question=question,
        max_evidence_per_memory=max_evidence_per_memory,
        enable_deterministic_temporal_resolver=enable_deterministic_temporal_resolver,
        temporal_telemetry=temporal_telemetry,
    )
    generated = normalize_generated_answer(
        await llm.complete(
            system=system_prompt,
            user=ANSWER_USER_PROMPT.format(
                reference_date=reference_date,
                memories=memories_text,
                question=question,
            ),
            json_object=False,
        )
    )
    answer_calls = 1
    retry_attempted = False
    expand_applied = False
    expanded_ids: tuple[str, ...] = ()
    initial_generated = generated

    if (
        enable_no_info_evidence_expand
        and is_no_info(generated)
        and source_index is not None
    ):
        shown_ids = collect_shown_source_message_ids(
            retrieval,
            question=question,
            source_index=source_index,
            max_evidence_per_memory=max_evidence_per_memory,
        )
        extra_ids = expandable_source_message_ids(retrieval, shown_ids)
        if extra_ids:
            additional = format_additional_evidence(
                extra_ids,
                source_index,
                enable_deterministic_temporal_resolver=enable_deterministic_temporal_resolver,
                temporal_telemetry=temporal_telemetry,
            )
            if additional.strip():
                retry_attempted = True
                expand_applied = True
                expanded_ids = tuple(extra_ids)
                memories_text = append_expanded_evidence_context(memories_text, additional)
                generated = normalize_generated_answer(
                    await llm.complete(
                        system=system_prompt,
                        user=ANSWER_USER_PROMPT.format(
                            reference_date=reference_date,
                            memories=memories_text,
                            question=question,
                        ),
                        json_object=False,
                    )
                )
                answer_calls = 2

    return AnswerOutcome(
        generated=generated,
        initial_generated=initial_generated,
        memories_text=memories_text,
        retry_attempted=retry_attempted,
        expand_applied=expand_applied,
        expanded_message_ids=expanded_ids,
        answer_llm_calls=answer_calls,
    )
