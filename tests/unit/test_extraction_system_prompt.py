"""Unit tests for EXTRACTION_SYSTEM_PROMPT memory type guidance (EXT-010)."""

from __future__ import annotations

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
    assert "Return only valid JSON matching the required schema." in (
        EXTRACTION_SYSTEM_PROMPT
    )


def test_extraction_system_prompt_event_and_fact_coexistence_rule() -> None:
    assert "both an event and a resulting fact" in EXTRACTION_SYSTEM_PROMPT
    assert "semantically duplicate" in EXTRACTION_SYSTEM_PROMPT
