"""Deterministic, local content-only secret redaction for EXT-002."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

REDACTION_MARKER: Final[str] = "[REDACTED_SECRET]"


class RedactionFailure(RuntimeError):
    """Expected failure raised only by the authorized redaction operation."""

_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_BEARER = re.compile(
    r"\b(?:bearer|access[\s_-]*token)\s*(?:[:=]\s*|\s+)"
    r"[A-Za-z0-9._~+/=-]{12,}",
    re.IGNORECASE,
)
_LABELLED_CREDENTIAL = re.compile(
    r"\b(?:password|passwd|pwd|api[\s_-]*key|secret[\s_-]*key)\s*[:=]\s*"
    r"[^\s,;]+",
    re.IGNORECASE,
)
_OTP = re.compile(
    r"\b(?:otp|one[\s-]*time[\s-]*pass(?:word|code)?|verification[\s_-]*(?:code|number)|security[\s_-]*code)"
    r"\s*[:=]\s*\d{4,8}\b",
    re.IGNORECASE,
)
_CVV = re.compile(r"\b(?:cvv|cvc)\s*[:=]\s*\d{3,4}\b", re.IGNORECASE)
_API_PREFIX = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    r"sk-[A-Za-z0-9_-]{16,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"ghp_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{12,}"
    r")(?![A-Za-z0-9_])"
)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    precedence: int


def _luhn_valid(candidate: str) -> bool:
    digits = [int(char) for char in candidate if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _collect_spans(content: str) -> list[_Span]:
    spans: list[_Span] = []
    for pattern, precedence in (
        (_PRIVATE_KEY, 0),
        (_BEARER, 1),
        (_LABELLED_CREDENTIAL, 2),
        (_API_PREFIX, 2),
        (_OTP, 2),
        (_CVV, 2),
    ):
        spans.extend(
            _Span(match.start(), match.end(), precedence)
            for match in pattern.finditer(content)
        )
    for match in _CARD.finditer(content):
        if _luhn_valid(match.group()):
            spans.append(_Span(match.start(), match.end(), 3))
    return spans


def _merge_spans(spans: list[_Span]) -> list[tuple[int, int]]:
    if not spans:
        return []
    spans.sort(key=lambda item: (item.start, -(item.end - item.start), item.precedence))
    merged: list[tuple[int, int]] = []
    current_start, current_end = spans[0].start, spans[0].end
    for span in spans[1:]:
        if span.start <= current_end:
            current_end = max(current_end, span.end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = span.start, span.end
    merged.append((current_start, current_end))
    return merged


def redact_content(content: str) -> str:
    """Replace only authorized secret spans; no match is a successful result."""
    replacements = _merge_spans(_collect_spans(content))
    for start, end in reversed(replacements):
        content = content[:start] + REDACTION_MARKER + content[end:]
    return content


class ExtractionRedactionService:
    """Small injectable service boundary used by the preprocessing stage."""

    def redact(self, content: str) -> str:
        return redact_content(content)
