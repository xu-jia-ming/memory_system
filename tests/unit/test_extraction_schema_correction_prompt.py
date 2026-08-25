"""Unit tests for SCHEMA_CORRECTION_INSTRUCTION retry guidance (EXT-011)."""

from __future__ import annotations

from memory_system.domain.services.extraction_llm_service import SCHEMA_CORRECTION_INSTRUCTION


def test_schema_correction_instruction_required_keys() -> None:
    assert "previous response was invalid" in SCHEMA_CORRECTION_INSTRUCTION.lower()
    assert "entities" in SCHEMA_CORRECTION_INSTRUCTION
    assert "memories" in SCHEMA_CORRECTION_INSTRUCTION
    assert "memory_type" in SCHEMA_CORRECTION_INSTRUCTION
    assert "not category" in SCHEMA_CORRECTION_INSTRUCTION
    assert "may be empty" in SCHEMA_CORRECTION_INSTRUCTION
    assert "object_entity_id XOR object_value" in SCHEMA_CORRECTION_INSTRUCTION
    assert "source_message_ids" in SCHEMA_CORRECTION_INSTRUCTION
    assert "Return JSON only." in SCHEMA_CORRECTION_INSTRUCTION
