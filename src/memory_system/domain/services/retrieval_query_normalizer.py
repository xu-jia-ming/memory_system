"""RET-002 retrieval-path query normalization (§2.2.6)."""

from __future__ import annotations

from memory_system.domain.services.core_search_text import normalize_search_text_fragment


def normalize_retrieval_query(raw: str) -> str:
    """Normalize a retrieval query via NFKC, trim, and whitespace compression."""
    return normalize_search_text_fragment(raw)
