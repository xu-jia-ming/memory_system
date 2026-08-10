"""Unit tests for heuristic token estimation (§1.2.1)."""

from __future__ import annotations

import inspect

import pytest

from memory_system.domain.services.token_estimator import estimate_tokens


def test_empty_string_returns_zero() -> None:
    assert estimate_tokens("") == 0


def test_pure_ascii_uses_other_ratio() -> None:
    assert estimate_tokens("abcd") == 1


def test_pure_digits_and_spaces() -> None:
    assert estimate_tokens("1234") == 1
    assert estimate_tokens("    ") == 1


def test_single_chinese_character_ceil() -> None:
    assert estimate_tokens("中") == 2


def test_four_chinese_characters() -> None:
    assert estimate_tokens("中文测试") == 5


def test_mixed_chinese_and_ascii() -> None:
    assert estimate_tokens("中a") == 2


def test_ceil_not_trunc() -> None:
    assert estimate_tokens("中中") == 3


def test_deterministic_on_repeated_calls() -> None:
    text = "Hello 世界"
    assert estimate_tokens(text) == estimate_tokens(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", 0),
        ("a", 1),
        ("aaaa", 1),
        ("aaaaa", 2),
        ("中", 2),
        ("中文", 3),
        ("中文测试", 5),
        ("Hello 世界", 4),
        ("user message 用户", 6),
    ],
)
def test_estimate_tokens_parametrized(text: str, expected: int) -> None:
    assert estimate_tokens(text) == expected


def test_module_docstring_states_heuristic_not_exact_tokenizer() -> None:
    from memory_system.domain import services

    module = services.token_estimator
    doc = inspect.getdoc(module) or ""
    lowered = doc.lower()
    assert "heuristic" in lowered or "approximation" in lowered
    assert "exact" not in lowered or "not an exact" in lowered
