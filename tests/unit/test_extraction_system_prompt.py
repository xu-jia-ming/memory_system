"""Unit tests for EXTRACTION_SYSTEM_PROMPT (EXT-010 + EXT-011)."""

from __future__ import annotations

from memory_system.domain.models.extraction_llm import ENTITY_TYPES, EVENT_STATUSES
from memory_system.domain.services.extraction_llm_service import EXTRACTION_SYSTEM_PROMPT


def test_extraction_system_prompt_contains_memory_types() -> None:
    for memory_type in ("fact", "preference", "event", "profile"):
        assert memory_type in EXTRACTION_SYSTEM_PROMPT


def test_extraction_system_prompt_classification_order() -> None:
    preference_pos = EXTRACTION_SYSTEM_PROMPT.index("preference")
    event_pos = EXTRACTION_SYSTEM_PROMPT.index("- event:")
    profile_pos = EXTRACTION_SYSTEM_PROMPT.index("- profile:")
    fact_pos = EXTRACTION_SYSTEM_PROMPT.index("- fact:")
    assert preference_pos < event_pos < profile_pos < fact_pos

    order_section = EXTRACTION_SYSTEM_PROMPT.split("Classification order:", 1)[1]
    assert order_section.index("preference") < order_section.index("event")
    assert order_section.index("event") < order_section.index("profile")
    assert order_section.index("profile") < order_section.index("fact")


def test_extraction_system_prompt_examples_present() -> None:
    assert "prefers replies in Chinese" in EXTRACTION_SYSTEM_PROMPT
    assert "plans to submit a paper next week" in EXTRACTION_SYSTEM_PROMPT
    assert "backend developer" in EXTRACTION_SYSTEM_PROMPT
    assert "uses Java for backend development" in EXTRACTION_SYSTEM_PROMPT


def test_extraction_system_prompt_preserves_core_requirements() -> None:
    assert "Extract only memories supported by the provided messages." in (
        EXTRACTION_SYSTEM_PROMPT
    )
    assert "at least one source message whose role is user" in EXTRACTION_SYSTEM_PROMPT
    assert "must never be the only evidence" in EXTRACTION_SYSTEM_PROMPT
    assert (
        "Do not extract greetings, temporary formatting requests, unsupported assistant"
        in EXTRACTION_SYSTEM_PROMPT
    )
    assert "Return only valid JSON matching the Output schema below." in (
        EXTRACTION_SYSTEM_PROMPT
    )


def test_extraction_system_prompt_event_and_fact_coexistence_rule() -> None:
    assert "both an event and a resulting fact" in EXTRACTION_SYSTEM_PROMPT
    assert "semantically duplicate" in EXTRACTION_SYSTEM_PROMPT


def test_extraction_system_prompt_contains_output_schema_keys() -> None:
    assert "Output schema:" in EXTRACTION_SYSTEM_PROMPT
    assert '"entities"' in EXTRACTION_SYSTEM_PROMPT
    assert '"memories"' in EXTRACTION_SYSTEM_PROMPT
    for field in (
        "local_entity_id",
        "name",
        "type",
        "aliases",
        "memory_type",
        "content",
        "subject_entity_id",
        "predicate",
        "object_entity_id",
        "object_value",
        "event_status",
        "start_time",
        "end_time",
        "original_time_text",
        "confidence",
        "source_message_ids",
    ):
        assert field in EXTRACTION_SYSTEM_PROMPT


def test_extraction_system_prompt_xor_rule() -> None:
    assert "object_entity_id" in EXTRACTION_SYSTEM_PROMPT
    assert "object_value" in EXTRACTION_SYSTEM_PROMPT
    assert "exactly one non-null value (XOR)" in EXTRACTION_SYSTEM_PROMPT


def test_extraction_system_prompt_non_event_null_rule() -> None:
    assert "For non-event memories" in EXTRACTION_SYSTEM_PROMPT
    for field in ("event_status", "start_time", "end_time", "original_time_text"):
        assert field in EXTRACTION_SYSTEM_PROMPT
    assert "must all be null" in EXTRACTION_SYSTEM_PROMPT


def test_extraction_system_prompt_entity_and_event_enums() -> None:
    for entity_type in ENTITY_TYPES:
        assert entity_type in EXTRACTION_SYSTEM_PROMPT
    for event_status in EVENT_STATUSES:
        assert event_status in EXTRACTION_SYSTEM_PROMPT


def test_extraction_system_prompt_preserves_ext010_content() -> None:
    assert "Memory type definitions" in EXTRACTION_SYSTEM_PROMPT
    assert "Classification order:" in EXTRACTION_SYSTEM_PROMPT
    test_extraction_system_prompt_contains_memory_types()
    test_extraction_system_prompt_classification_order()
    test_extraction_system_prompt_examples_present()
