"""Unit tests for core_search_text (EXT-006)."""

from __future__ import annotations

from memory_system.domain.services.core_search_text import (
    build_core_search_text,
    join_non_empty_with_single_space,
    normalize_search_text_fragment,
)


def test_t1_formula_order() -> None:
    text = build_core_search_text(
        user_id="user-1",
        content="用户正在开发",
        subject_entity_id="entity-uuid-1",
        subject_canonical_name="Agent Memory System",
        predicate="works_on",
        object_entity_id="entity-uuid-2",
        object_canonical_name="Memory Project",
        object_value=None,
    )
    assert text == "用户正在开发 agent memory system works_on memory project"


def test_t2_user_entity_omits_current_user() -> None:
    text = build_core_search_text(
        user_id="user-1",
        content="likes tea",
        subject_entity_id="user:user-1",
        subject_canonical_name="current_user",
        predicate="likes",
        object_entity_id=None,
        object_canonical_name=None,
        object_value="tea",
    )
    assert "current_user" not in text
    assert text == "likes tea likes tea"


def test_t3_nfkc_and_whitespace_normalization() -> None:
    fragment = normalize_search_text_fragment("  Agent\u3000Memory   System  ")
    assert fragment == "Agent Memory System"
    joined = join_non_empty_with_single_space("alpha", "alpha", "  beta  ")
    assert joined == "alpha beta"
