"""EXT-006 core_search_text builder (§2.2.3, no aliases)."""

from __future__ import annotations

import re
import unicodedata

from memory_system.domain.services.entity_key import build_user_entity_id, normalize_entity_name

_WHITESPACE = re.compile(r"\s+", re.UNICODE)


def normalize_search_text_fragment(value: str) -> str:
    """NFKC, strip, compress whitespace (§2.2.3 rule 1)."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _WHITESPACE.sub(" ", normalized)
    return normalized.strip()


def join_non_empty_with_single_space(*parts: str | None) -> str:
    """Join non-empty unique fragments with a single space."""
    fragments: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part is None:
            continue
        normalized = normalize_search_text_fragment(part)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        fragments.append(normalized)
    return " ".join(fragments)


def build_core_search_text(
    *,
    user_id: str,
    content: str,
    subject_entity_id: str,
    subject_canonical_name: str,
    predicate: str,
    object_entity_id: str | None,
    object_canonical_name: str | None,
    object_value: str | None,
) -> str:
    """Build core_search_text without entity aliases."""
    user_entity_id = build_user_entity_id(user_id)
    subject_name: str | None = None
    if subject_entity_id != user_entity_id:
        subject_name = normalize_entity_name(subject_canonical_name)

    object_part: str | None = None
    if object_entity_id is not None:
        if object_entity_id != user_entity_id:
            object_part = normalize_entity_name(object_canonical_name or "")
    else:
        object_part = object_value

    return join_non_empty_with_single_space(
        content,
        subject_name,
        predicate,
        object_part,
    )
