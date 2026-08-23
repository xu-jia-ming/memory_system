"""Deterministic relative-time resolution for Supporting Evidence (answer-time only)."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

# Word number map one–thirty.
_WORD_NUMBERS: dict[str, int] = {}
_ONES = [
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
for i, word in enumerate(_ONES, start=1):
    _WORD_NUMBERS[word] = i
for tens, start in [("twenty", 20), ("thirty", 30)]:
    _WORD_NUMBERS[tens] = start
    for i, word in enumerate(_ONES[:9], start=1):
        _WORD_NUMBERS[f"{tens}-{word}"] = start + i
        _WORD_NUMBERS[f"{tens} {word}"] = start + i

_WORD_ALT = "|".join(sorted(_WORD_NUMBERS.keys(), key=len, reverse=True))

# Word-boundary relative expressions (detection only; resolution is rule-gated).
_UNSUPPORTED_VAGUE_RE = re.compile(
    r"\b("
    r"recently|a while ago|some time ago|a few years ago|several years ago|"
    r"around then|sometime last year|earlier this year|lately|not long ago|soon"
    r")\b",
    re.IGNORECASE,
)
_UNSUPPORTED_YEAR_PERIOD_RE = re.compile(
    r"\b(last year|next year|this year)\b",
    re.IGNORECASE,
)
_SAFE_MONTH_WEEK_RE = re.compile(
    r"\b("
    r"last week|next week|this week|"
    r"last month|next month|this month"
    r")\b",
    re.IGNORECASE,
)
_SAFE_TODAY_RE = re.compile(r"\btoday\b", re.IGNORECASE)
_SAFE_YESTERDAY_RE = re.compile(r"\byesterday\b", re.IGNORECASE)
_SAFE_TOMORROW_RE = re.compile(r"\btomorrow\b", re.IGNORECASE)
_SAFE_N_DAYS_AGO_RE = re.compile(r"\b(\d+)\s+days?\s+ago\b", re.IGNORECASE)
_SAFE_IN_N_DAYS_RE = re.compile(r"\bin\s+(\d+)\s+days?\b", re.IGNORECASE)
_SAFE_WORD_DAYS_AGO_RE = re.compile(
    rf"\b({_WORD_ALT})\s+days?\s+ago\b",
    re.IGNORECASE,
)
_SAFE_IN_WORD_DAYS_RE = re.compile(
    rf"\bin\s+({_WORD_ALT})\s+days?\b",
    re.IGNORECASE,
)


class ResolutionStatus(StrEnum):
    SAFE = "SAFE"
    AMBIGUOUS = "AMBIGUOUS"
    AMBIGUOUS_MULTIPLE_EXPRESSIONS = "AMBIGUOUS_MULTIPLE_EXPRESSIONS"
    NO_MATCH = "NO_MATCH"


@dataclass(frozen=True, slots=True)
class TemporalResolution:
    mention_time: str  # YYYY-MM-DD from evidence source timestamp
    relative_expression: str | None
    resolved_event_start: str | None  # YYYY-MM-DD when SAFE
    resolved_event_end: str | None
    granularity: str  # day | none
    status: ResolutionStatus
    rule_id: str | None
    reason: str
    detected_expressions: tuple[str, ...] = ()

    def to_metadata_lines(self) -> list[str]:
        if self.status != ResolutionStatus.SAFE or not self.resolved_event_start:
            return []
        basis = (
            f'"{self.relative_expression}" relative to evidence date {self.mention_time}'
        )
        if (
            self.granularity == "range"
            and self.resolved_event_end
            and self.resolved_event_end != self.resolved_event_start
        ):
            return [
                (
                    f"  Resolved event date range: {self.resolved_event_start} ~ "
                    f"{self.resolved_event_end}"
                ),
                f"  Temporal basis: {basis}",
            ]
        return [
            f"  Resolved event date: {self.resolved_event_start}",
            f"  Temporal basis: {basis}",
        ]


def mention_date_from_timestamp(timestamp: int) -> date:
    """Local calendar date — matches format_source_date / fromtimestamp semantics."""
    return datetime.fromtimestamp(timestamp).date()


def format_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _shift_month(anchor: date, delta_months: int) -> tuple[int, int]:
    month_index = anchor.month - 1 + delta_months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    return year, month


def _iso_week_bounds(anchor: date) -> tuple[date, date]:
    monday = anchor - timedelta(days=anchor.weekday())
    return monday, monday + timedelta(days=6)


def _this_month_range(anchor: date) -> tuple[date, date]:
    return _month_bounds(anchor.year, anchor.month)


def _next_month_range(anchor: date) -> tuple[date, date]:
    year, month = _shift_month(anchor, 1)
    return _month_bounds(year, month)


def _last_month_range(anchor: date) -> tuple[date, date]:
    year, month = _shift_month(anchor, -1)
    return _month_bounds(year, month)


def _this_week_range(anchor: date) -> tuple[date, date]:
    return _iso_week_bounds(anchor)


def _next_week_range(anchor: date) -> tuple[date, date]:
    monday, _ = _iso_week_bounds(anchor)
    next_monday = monday + timedelta(days=7)
    return next_monday, next_monday + timedelta(days=6)


def _last_week_range(anchor: date) -> tuple[date, date]:
    monday, _ = _iso_week_bounds(anchor)
    last_monday = monday - timedelta(days=7)
    return last_monday, last_monday + timedelta(days=6)


def _range_resolution(
    mention: date,
    expression: str,
    *,
    rule_id: str,
    start: date,
    end: date,
    reason: str,
) -> TemporalResolution:
    mention_str = format_date(mention)
    return TemporalResolution(
        mention_time=mention_str,
        relative_expression=expression,
        resolved_event_start=format_date(start),
        resolved_event_end=format_date(end),
        granularity="range",
        status=ResolutionStatus.SAFE,
        rule_id=rule_id,
        reason=reason,
        detected_expressions=(expression,),
    )


def _detect_all_expressions(text: str) -> list[str]:
    found: list[str] = []
    for pattern in (
        _UNSUPPORTED_VAGUE_RE,
        _UNSUPPORTED_YEAR_PERIOD_RE,
        _SAFE_MONTH_WEEK_RE,
        _SAFE_TODAY_RE,
        _SAFE_YESTERDAY_RE,
        _SAFE_TOMORROW_RE,
        _SAFE_N_DAYS_AGO_RE,
        _SAFE_IN_N_DAYS_RE,
        _SAFE_WORD_DAYS_AGO_RE,
        _SAFE_IN_WORD_DAYS_RE,
    ):
        for match in pattern.finditer(text):
            found.append(match.group(0).strip())
    return found


def _is_safe_expression(expr: str) -> bool:
    low = expr.lower()
    if _UNSUPPORTED_VAGUE_RE.search(low) or _UNSUPPORTED_YEAR_PERIOD_RE.search(low):
        return False
    if _SAFE_MONTH_WEEK_RE.search(low):
        return True
    if _SAFE_TODAY_RE.search(low):
        return True
    if _SAFE_YESTERDAY_RE.search(low):
        return True
    if _SAFE_TOMORROW_RE.search(low):
        return True
    if _SAFE_N_DAYS_AGO_RE.search(low) or _SAFE_WORD_DAYS_AGO_RE.search(low):
        return True
    if _SAFE_IN_N_DAYS_RE.search(low) or _SAFE_IN_WORD_DAYS_RE.search(low):
        return True
    return False


def _parse_word_or_digit(num_str: str) -> int | None:
    low = num_str.lower().strip()
    if low.isdigit():
        return int(low)
    return _WORD_NUMBERS.get(low)


def _resolve_safe_single(
    mention: date,
    text: str,
    expression: str,
) -> TemporalResolution | None:
    low = text.lower()
    expr_low = expression.lower()
    mention_str = format_date(mention)

    if _SAFE_TODAY_RE.search(expr_low) and _SAFE_TODAY_RE.search(low):
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression="today",
            resolved_event_start=mention_str,
            resolved_event_end=mention_str,
            granularity="day",
            status=ResolutionStatus.SAFE,
            rule_id="today",
            reason="today maps to mention date",
            detected_expressions=(expression,),
        )

    if _SAFE_YESTERDAY_RE.search(expr_low) and _SAFE_YESTERDAY_RE.search(low):
        resolved = mention - timedelta(days=1)
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression="yesterday",
            resolved_event_start=format_date(resolved),
            resolved_event_end=format_date(resolved),
            granularity="day",
            status=ResolutionStatus.SAFE,
            rule_id="yesterday",
            reason="yesterday is one day before mention date",
            detected_expressions=(expression,),
        )

    if _SAFE_TOMORROW_RE.search(expr_low) and _SAFE_TOMORROW_RE.search(low):
        resolved = mention + timedelta(days=1)
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression="tomorrow",
            resolved_event_start=format_date(resolved),
            resolved_event_end=format_date(resolved),
            granularity="day",
            status=ResolutionStatus.SAFE,
            rule_id="tomorrow",
            reason="tomorrow is one day after mention date",
            detected_expressions=(expression,),
        )

    m = _SAFE_N_DAYS_AGO_RE.search(low)
    if m and _SAFE_N_DAYS_AGO_RE.search(expr_low):
        n = int(m.group(1))
        resolved = mention - timedelta(days=n)
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression=m.group(0).strip(),
            resolved_event_start=format_date(resolved),
            resolved_event_end=format_date(resolved),
            granularity="day",
            status=ResolutionStatus.SAFE,
            rule_id="n_days_ago",
            reason=f"{n} days before mention date",
            detected_expressions=(expression,),
        )

    m = _SAFE_WORD_DAYS_AGO_RE.search(low)
    if m and _SAFE_WORD_DAYS_AGO_RE.search(expr_low):
        n = _parse_word_or_digit(m.group(1))
        if n is None:
            return None
        resolved = mention - timedelta(days=n)
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression=m.group(0).strip(),
            resolved_event_start=format_date(resolved),
            resolved_event_end=format_date(resolved),
            granularity="day",
            status=ResolutionStatus.SAFE,
            rule_id="n_days_ago",
            reason=f"{n} days before mention date",
            detected_expressions=(expression,),
        )

    m = _SAFE_IN_N_DAYS_RE.search(low)
    if m and _SAFE_IN_N_DAYS_RE.search(expr_low):
        n = int(m.group(1))
        resolved = mention + timedelta(days=n)
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression=m.group(0).strip(),
            resolved_event_start=format_date(resolved),
            resolved_event_end=format_date(resolved),
            granularity="day",
            status=ResolutionStatus.SAFE,
            rule_id="in_n_days",
            reason=f"{n} days after mention date",
            detected_expressions=(expression,),
        )

    m = _SAFE_IN_WORD_DAYS_RE.search(low)
    if m and _SAFE_IN_WORD_DAYS_RE.search(expr_low):
        n = _parse_word_or_digit(m.group(1))
        if n is None:
            return None
        resolved = mention + timedelta(days=n)
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression=m.group(0).strip(),
            resolved_event_start=format_date(resolved),
            resolved_event_end=format_date(resolved),
            granularity="day",
            status=ResolutionStatus.SAFE,
            rule_id="in_n_days",
            reason=f"{n} days after mention date",
            detected_expressions=(expression,),
        )

    expr_normalized = expression.lower().strip()
    range_map: dict[str, tuple[str, Any]] = {
        "this month": ("this_month_range", _this_month_range),
        "next month": ("next_month_range", _next_month_range),
        "last month": ("last_month_range", _last_month_range),
        "this week": ("this_week_range", _this_week_range),
        "next week": ("next_week_range", _next_week_range),
        "last week": ("last_week_range", _last_week_range),
    }
    if expr_normalized in range_map:
        rule_id, range_fn = range_map[expr_normalized]
        if expr_normalized in low:
            start, end = range_fn(mention)
            return _range_resolution(
                mention,
                expression,
                rule_id=rule_id,
                start=start,
                end=end,
                reason=f"{expr_normalized} calendar range relative to mention date",
            )

    return None


def resolve_temporal_expression(
    evidence_text: str,
    source_timestamp: int,
) -> TemporalResolution:
    """Resolve relative time in evidence text against its source message timestamp."""
    text = (evidence_text or "").strip()
    if not text or source_timestamp <= 0:
        return TemporalResolution(
            mention_time="",
            relative_expression=None,
            resolved_event_start=None,
            resolved_event_end=None,
            granularity="none",
            status=ResolutionStatus.NO_MATCH,
            rule_id=None,
            reason="missing text or timestamp",
        )

    mention = mention_date_from_timestamp(source_timestamp)
    mention_str = format_date(mention)
    detected = _detect_all_expressions(text)

    if not detected:
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression=None,
            resolved_event_start=None,
            resolved_event_end=None,
            granularity="none",
            status=ResolutionStatus.NO_MATCH,
            rule_id=None,
            reason="no relative expression in evidence text",
        )

    if len(detected) > 1:
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression=None,
            resolved_event_start=None,
            resolved_event_end=None,
            granularity="none",
            status=ResolutionStatus.AMBIGUOUS_MULTIPLE_EXPRESSIONS,
            rule_id=None,
            reason="multiple relative expressions in evidence",
            detected_expressions=tuple(detected),
        )

    expression = detected[0]
    if not _is_safe_expression(expression):
        return TemporalResolution(
            mention_time=mention_str,
            relative_expression=expression,
            resolved_event_start=None,
            resolved_event_end=None,
            granularity="none",
            status=ResolutionStatus.AMBIGUOUS,
            rule_id=None,
            reason="expression not in SAFE rule set",
            detected_expressions=(expression,),
        )

    resolved = _resolve_safe_single(mention, text, expression)
    if resolved is not None:
        return resolved

    return TemporalResolution(
        mention_time=mention_str,
        relative_expression=expression,
        resolved_event_start=None,
        resolved_event_end=None,
        granularity="none",
        status=ResolutionStatus.AMBIGUOUS,
        rule_id=None,
        reason="could not resolve expression safely",
        detected_expressions=(expression,),
    )


@dataclass
class TemporalResolutionTelemetry:
    attempted: int = 0
    safe: int = 0
    ambiguous: int = 0
    no_match: int = 0
    rule_counts: dict[str, int] = field(default_factory=dict)

    def record(self, resolution: TemporalResolution) -> None:
        self.attempted += 1
        if resolution.status == ResolutionStatus.SAFE:
            self.safe += 1
            if resolution.rule_id:
                self.rule_counts[resolution.rule_id] = (
                    self.rule_counts.get(resolution.rule_id, 0) + 1
                )
        elif resolution.status == ResolutionStatus.NO_MATCH:
            self.no_match += 1
        else:
            self.ambiguous += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "temporal_resolution_attempted": self.attempted,
            "temporal_resolution_safe": self.safe,
            "temporal_resolution_ambiguous": self.ambiguous,
            "temporal_resolution_no_match": self.no_match,
            "rule_id_distribution": dict(self.rule_counts),
        }

