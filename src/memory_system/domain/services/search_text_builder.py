"""EXT-007 search_text builder with alias token budget (§2.2.3 rules 5–7)."""

from __future__ import annotations

from dataclasses import dataclass

from memory_system.domain.ports.tokenize_client import TokenizeClient
from memory_system.domain.services.core_search_text import (
    join_non_empty_with_single_space,
    normalize_search_text_fragment,
)


@dataclass(frozen=True, slots=True)
class SearchTextBuildResult:
    search_text: str
    token_count: int
    omitted_alias_count: int


def _sorted_aliases(aliases: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        fragment = normalize_search_text_fragment(alias)
        if not fragment or fragment in seen:
            continue
        seen.add(fragment)
        normalized.append(fragment)
    return sorted(normalized, key=lambda value: [ord(char) for char in value])


async def build_search_text_with_alias_budget(
    *,
    core_search_text: str,
    subject_aliases: list[str],
    object_aliases: list[str],
    user_id: str,
    subject_entity_id: str,
    object_entity_id: str | None,
    tokenize_client: TokenizeClient,
    max_tokens: int = 1024,
    core_token_count: int | None = None,
) -> SearchTextBuildResult:
    """Build final search_text by appending aliases that fit the token budget."""
    del user_id  # privacy enforced by caller-supplied alias lists
    del subject_entity_id, object_entity_id

    core = normalize_search_text_fragment(core_search_text)
    if not core:
        raise ValueError("core_search_text must be non-empty")

    token_count = (
        core_token_count
        if core_token_count is not None
        else await tokenize_client.count_tokens(core)
    )
    if token_count < 1 or token_count > max_tokens:
        raise ValueError("core_search_text token_count out of range")

    search_text = core
    omitted_alias_count = 0

    for alias in _sorted_aliases(subject_aliases) + _sorted_aliases(object_aliases):
        candidate = join_non_empty_with_single_space(search_text, alias)
        candidate_tokens = await tokenize_client.count_tokens(candidate)
        if candidate_tokens > max_tokens:
            omitted_alias_count += 1
            continue
        search_text = candidate
        token_count = candidate_tokens

    final_tokens = await tokenize_client.count_tokens(search_text)
    if final_tokens < 1 or final_tokens > max_tokens:
        raise ValueError("final search_text token_count out of range")

    return SearchTextBuildResult(
        search_text=search_text,
        token_count=final_tokens,
        omitted_alias_count=omitted_alias_count,
    )
