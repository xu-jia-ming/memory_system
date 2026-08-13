"""Unit tests for retrieval query normalization."""

from __future__ import annotations

from memory_system.domain.services.retrieval_query_normalizer import normalize_retrieval_query


def test_u1_nfkc_whitespace_and_punctuation_preserved() -> None:
    assert normalize_retrieval_query("  ＡＢＣ　１２３  hello   world  ") == "ABC 123 hello world"
    assert normalize_retrieval_query("你好，世界！") == "你好,世界!"


def test_u2_whitespace_only_normalizes_to_empty_string() -> None:
    assert normalize_retrieval_query("   ") == ""
    assert normalize_retrieval_query("\u3000\u3000") == ""
