"""Heuristic token estimation for Working Memory (§1.2.1).

This module provides a **character-ratio approximation**, not an exact model
tokenizer. Do not use for billing or model context limits that require
tokenizer-accurate counts.
"""

from __future__ import annotations

import math
import re

_CHINESE_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using the MVP heuristic formula.

    ``estimated_tokens = ceil(chinese * 1.25 + other * 0.25)``

    Chinese characters match ``\\u4e00-\\u9fff``; all other characters count
    toward ``other``. Empty input returns ``0``.
    """
    if not text:
        return 0

    chinese_count = len(_CHINESE_CHAR_PATTERN.findall(text))
    other_count = len(text) - chinese_count
    return math.ceil(chinese_count * 1.25 + other_count * 0.25)
