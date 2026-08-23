"""Unit tests for NO_INFO evidence expand retry pipeline."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "locomo_eval"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from answer_pipeline import answer_with_no_info_expand_retry  # noqa: E402
from memory_evidence_context import (  # noqa: E402
    SourceMessageIndex,
    SourceMessageRecord,
    append_expanded_evidence_context,
    collect_shown_source_message_ids,
    expandable_source_message_ids,
    has_expandable_evidence,
)
from prompts import is_no_info  # noqa: E402

JAN_TS = int(datetime(2023, 1, 20, 12, 0, 0).timestamp())
FEB_TS = int(datetime(2023, 2, 4, 12, 0, 0).timestamp())


class _FakeLlm:
    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self.calls: list[str] = []

    async def complete(self, *, system: str, user: str, json_object: bool = False) -> str:
        del system, json_object
        self.calls.append(user)
        if not self._answers:
            raise AssertionError("no canned answers left")
        return self._answers.pop(0)


def _index() -> SourceMessageIndex:
    return SourceMessageIndex(
        {
            "msg_a": SourceMessageRecord(
                message_id="msg_a",
                content="[Jon] The studio has Marley flooring and great natural light.",
                timestamp=JAN_TS,
                role="user",
            ),
            "msg_b": SourceMessageRecord(
                message_id="msg_b",
                content="[Jon] It should be by the water with plenty of windows.",
                timestamp=FEB_TS,
                role="user",
            ),
        },
        "user_a",
    )


def _retrieval() -> dict:
    return {
        "memories": [
            {
                "memory_id": "m1",
                "memory_type": "fact",
                "content": "Jon wants a dance studio near water",
                "source_message_ids": ["msg_a", "msg_b"],
            }
        ]
    }


def test_is_no_info_exact_phrase() -> None:
    assert is_no_info("No information available")
    assert not is_no_info("February, 2023")


def test_expandable_ids_excludes_shown() -> None:
    retrieval = _retrieval()
    shown = collect_shown_source_message_ids(
        retrieval,
        question="studio look",
        source_index=_index(),
        max_evidence_per_memory=1,
    )
    assert shown == {"msg_a"}
    assert expandable_source_message_ids(retrieval, shown) == ["msg_b"]
    assert has_expandable_evidence(retrieval, shown)


def test_append_expanded_evidence_dedupes_section() -> None:
    merged = append_expanded_evidence_context("Memory block", "- Date: x")
    assert "Additional supporting evidence" in merged
    assert "Memory block" in merged


@pytest.mark.asyncio
async def test_normal_answer_no_retry() -> None:
    llm = _FakeLlm(["February, 2023"])
    outcome = await answer_with_no_info_expand_retry(
        llm,
        system_prompt="sys",
        question="When?",
        reference_date="July 2023",
        retrieval=_retrieval(),
        source_index=_index(),
        max_evidence_per_memory=1,
    )
    assert outcome.generated == "February, 2023"
    assert outcome.retry_attempted is False
    assert outcome.expand_applied is False
    assert outcome.answer_llm_calls == 1
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_no_info_expands_and_retries_once() -> None:
    llm = _FakeLlm(["No information available", "by the water with natural light"])
    outcome = await answer_with_no_info_expand_retry(
        llm,
        system_prompt="sys",
        question="What should the studio look like?",
        reference_date="July 2023",
        retrieval=_retrieval(),
        source_index=_index(),
        max_evidence_per_memory=1,
    )
    assert outcome.retry_attempted is True
    assert outcome.expand_applied is True
    assert outcome.expanded_message_ids == ("msg_b",)
    assert outcome.answer_llm_calls == 2
    assert "Additional supporting evidence" in outcome.memories_text
    assert "msg_b" not in outcome.memories_text or "by the water" in outcome.memories_text


@pytest.mark.asyncio
async def test_no_info_without_expandable_stays_single_call() -> None:
    retrieval = {
        "memories": [
            {
                "memory_id": "m1",
                "memory_type": "fact",
                "content": "only one source",
                "source_message_ids": ["msg_a"],
            }
        ]
    }
    llm = _FakeLlm(["No information available"])
    outcome = await answer_with_no_info_expand_retry(
        llm,
        system_prompt="sys",
        question="?",
        reference_date="2023",
        retrieval=retrieval,
        source_index=_index(),
        max_evidence_per_memory=1,
    )
    assert outcome.retry_attempted is False
    assert outcome.answer_llm_calls == 1


@pytest.mark.asyncio
async def test_retry_still_no_info_stops_after_one_retry() -> None:
    llm = _FakeLlm(["No information available", "No information available"])
    outcome = await answer_with_no_info_expand_retry(
        llm,
        system_prompt="sys",
        question="What should the studio look like?",
        reference_date="July 2023",
        retrieval=_retrieval(),
        source_index=_index(),
        max_evidence_per_memory=1,
    )
    assert is_no_info(outcome.generated)
    assert outcome.answer_llm_calls == 2
    assert len(llm.calls) == 2
