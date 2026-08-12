"""Unit tests for search_text_builder (EXT-007)."""

from __future__ import annotations

import pytest

from memory_system.domain.services.search_text_builder import build_search_text_with_alias_budget


class _WordCountTokenizeClient:
    async def count_tokens(self, text: str) -> int:
        return len(text.split())


@pytest.mark.asyncio
async def test_u1_alias_order_subject_before_object() -> None:
    client = _WordCountTokenizeClient()
    result = await build_search_text_with_alias_budget(
        core_search_text="core text here",
        subject_aliases=["zebra", "alpha"],
        object_aliases=["beta"],
        user_id="user-1",
        subject_entity_id="entity-subject",
        object_entity_id="entity-object",
        tokenize_client=client,
        max_tokens=20,
    )
    assert result.search_text == "core text here alpha zebra beta"


@pytest.mark.asyncio
async def test_u2_alias_budget_skips_overflow() -> None:
    client = _WordCountTokenizeClient()
    result = await build_search_text_with_alias_budget(
        core_search_text="one two three four",
        subject_aliases=["five six seven eight nine"],
        object_aliases=[],
        user_id="user-1",
        subject_entity_id="entity-subject",
        object_entity_id=None,
        tokenize_client=client,
        max_tokens=6,
    )
    assert result.omitted_alias_count == 1
    assert len(result.search_text.split()) <= 6


@pytest.mark.asyncio
async def test_u3_user_entity_aliases_not_passed_by_caller() -> None:
    client = _WordCountTokenizeClient()
    result = await build_search_text_with_alias_budget(
        core_search_text="likes tea",
        subject_aliases=[],
        object_aliases=[],
        user_id="user-1",
        subject_entity_id="user:user-1",
        object_entity_id=None,
        tokenize_client=client,
        max_tokens=10,
    )
    assert "current_user" not in result.search_text


@pytest.mark.asyncio
async def test_u4_core_not_truncated() -> None:
    client = _WordCountTokenizeClient()
    core = "alpha beta gamma delta"
    result = await build_search_text_with_alias_budget(
        core_search_text=core,
        subject_aliases=["extra"],
        object_aliases=[],
        user_id="user-1",
        subject_entity_id="entity-subject",
        object_entity_id=None,
        tokenize_client=client,
        max_tokens=20,
    )
    assert result.search_text.startswith(core)


@pytest.mark.asyncio
async def test_handoff_core_token_count_reuse() -> None:
    client = _WordCountTokenizeClient()
    result = await build_search_text_with_alias_budget(
        core_search_text="one two three",
        subject_aliases=["four"],
        object_aliases=[],
        user_id="user-1",
        subject_entity_id="entity-subject",
        object_entity_id=None,
        tokenize_client=client,
        max_tokens=10,
        core_token_count=3,
    )
    assert result.search_text == "one two three four"
    assert result.token_count == 4
