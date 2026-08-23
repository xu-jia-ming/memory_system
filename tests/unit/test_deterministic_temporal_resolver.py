"""Unit tests for deterministic temporal resolver (SAFE rule set)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "locomo_eval"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from deterministic_temporal_resolver import (  # noqa: E402
    ResolutionStatus,
    resolve_temporal_expression,
)
from memory_evidence_context import (  # noqa: E402
    SourceMessageIndex,
    SourceMessageRecord,
    format_memories,
    select_source_message_ids,
)

JAN_20_TS = int(datetime(2023, 1, 20, 12, 0, 0).timestamp())
MAR_01_TS = int(datetime(2023, 3, 1, 12, 0, 0).timestamp())
JAN_01_TS = int(datetime(2023, 1, 1, 12, 0, 0).timestamp())
LEAP_MAR_01_TS = int(datetime(2024, 3, 1, 12, 0, 0).timestamp())
JUL_TS = int(datetime(2023, 7, 9, 12, 0, 0).timestamp())


def test_case_a_yesterday() -> None:
    r = resolve_temporal_expression("I lost my job yesterday.", JAN_20_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-01-19"
    assert r.rule_id == "yesterday"


def test_case_b_today() -> None:
    r = resolve_temporal_expression("We met today.", JAN_20_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-01-20"


def test_case_c_tomorrow() -> None:
    r = resolve_temporal_expression("I will call tomorrow.", JAN_20_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-01-21"


def test_case_d_three_days_ago() -> None:
    r = resolve_temporal_expression("That happened 3 days ago.", JAN_20_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-01-17"


def test_case_e_in_three_days() -> None:
    r = resolve_temporal_expression("The meeting is in 3 days.", JAN_20_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-01-23"


def test_case_f_month_boundary() -> None:
    r = resolve_temporal_expression("yesterday", MAR_01_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-02-28"


def test_case_g_year_boundary() -> None:
    r = resolve_temporal_expression("yesterday", JAN_01_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2022-12-31"


def test_case_h_leap_year() -> None:
    r = resolve_temporal_expression("yesterday", LEAP_MAR_01_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2024-02-29"


def test_case_i_vague_few_years() -> None:
    r = resolve_temporal_expression("I moved here a few years ago.", JAN_20_TS)
    assert r.status == ResolutionStatus.AMBIGUOUS
    assert r.resolved_event_start is None


def test_case_j_recently() -> None:
    r = resolve_temporal_expression("I saw him recently.", JAN_20_TS)
    assert r.status == ResolutionStatus.AMBIGUOUS


def test_case_k_no_expression() -> None:
    r = resolve_temporal_expression("I lost my job as a banker.", JAN_20_TS)
    assert r.status == ResolutionStatus.NO_MATCH


def test_case_l_multiple_expressions() -> None:
    r = resolve_temporal_expression(
        "Yesterday I called her, and today we met again.",
        JAN_20_TS,
    )
    assert r.status == ResolutionStatus.AMBIGUOUS_MULTIPLE_EXPRESSIONS
    assert r.resolved_event_start is None


def test_case_m_merge_regression_jan_anchor() -> None:
    index = SourceMessageIndex(
        {
            "msg_jan": SourceMessageRecord(
                message_id="msg_jan",
                content="[Jon] Lost my job as a banker yesterday.",
                timestamp=JAN_20_TS,
                role="user",
            ),
            "msg_jul": SourceMessageRecord(
                message_id="msg_jul",
                content="[Jon] Losing my job earlier this year pushed me to start a business.",
                timestamp=JUL_TS,
                role="user",
            ),
        },
        "user_a",
    )
    ids = select_source_message_ids(
        "When did Jon lose his job?",
        "Jon lost his job yesterday",
        ["msg_jan", "msg_jul"],
        index,
        1,
        memory_id="m1",
    )
    assert ids == ["msg_jan"]
    record = index.get("msg_jan")
    assert record is not None
    r = resolve_temporal_expression(
        "Lost my job as a banker yesterday.",
        record.timestamp,
    )
    assert r.resolved_event_start == "2023-01-19"


def test_case_n_memory_only_relative_not_in_evidence() -> None:
    index = SourceMessageIndex(
        {
            "msg_jan": SourceMessageRecord(
                message_id="msg_jan",
                content="[Jon] I started a business after leaving banking.",
                timestamp=JAN_20_TS,
                role="user",
            ),
        },
        "user_a",
    )
    text = format_memories(
        {
            "memories": [
                {
                    "memory_type": "event",
                    "content": "Jon lost his job yesterday",
                    "source_message_ids": ["msg_jan"],
                    "memory_id": "m1",
                }
            ]
        },
        index,
        question="When?",
        max_evidence_per_memory=1,
        enable_deterministic_temporal_resolver=True,
    )
    assert "Resolved event date" not in text


def test_case_o_serialization_includes_resolved_metadata() -> None:
    index = SourceMessageIndex(
        {
            "msg_jan": SourceMessageRecord(
                message_id="msg_jan",
                content="[Jon] Lost my job yesterday.",
                timestamp=JAN_20_TS,
                role="user",
            ),
        },
        "user_a",
    )
    text = format_memories(
        {
            "memories": [
                {
                    "memory_type": "event",
                    "content": "Jon lost his job yesterday",
                    "source_message_ids": ["msg_jan"],
                    "memory_id": "m1",
                }
            ]
        },
        index,
        question="When?",
        max_evidence_per_memory=1,
        enable_deterministic_temporal_resolver=True,
    )
    assert "Resolved event date: 2023-01-19" in text
    assert "Temporal basis:" in text
    assert "yesterday" in text
    assert "2023-01-20" in text


def test_word_number_two_days_ago() -> None:
    r = resolve_temporal_expression("two days ago", JAN_20_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-01-18"


def test_last_week_resolves_to_safe_range() -> None:
    r = resolve_temporal_expression("I went last week.", JAN_20_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.granularity == "range"
    assert r.resolved_event_start == "2023-01-09"
    assert r.resolved_event_end == "2023-01-15"
    assert r.rule_id == "last_week_range"


def test_next_month_safe_range() -> None:
    r = resolve_temporal_expression(
        "Finishing choreography to perform at a nearby festival next month.",
        JAN_20_TS,
    )
    assert r.status == ResolutionStatus.SAFE
    assert r.granularity == "range"
    assert r.resolved_event_start == "2023-02-01"
    assert r.resolved_event_end == "2023-02-28"
    assert r.rule_id == "next_month_range"


def test_last_month_cross_month() -> None:
    r = resolve_temporal_expression("I opened my store last month.", MAR_01_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-02-01"
    assert r.resolved_event_end == "2023-02-28"


def test_next_month_cross_year() -> None:
    dec_ts = int(datetime(2023, 12, 15, 12, 0, 0).timestamp())
    r = resolve_temporal_expression("We are planning an event next month.", dec_ts)
    assert r.resolved_event_start == "2024-01-01"
    assert r.resolved_event_end == "2024-01-31"


def test_next_week_iso_range() -> None:
    # 2023-01-20 is Friday; next week Mon-Sun = 2023-01-23 .. 2023-01-29
    r = resolve_temporal_expression("Meeting next week.", JAN_20_TS)
    assert r.status == ResolutionStatus.SAFE
    assert r.resolved_event_start == "2023-01-23"
    assert r.resolved_event_end == "2023-01-29"


def test_soon_stays_ambiguous() -> None:
    r = resolve_temporal_expression("I will travel soon.", JAN_20_TS)
    assert r.status == ResolutionStatus.AMBIGUOUS
    assert r.resolved_event_start is None


def test_last_year_stays_ambiguous() -> None:
    r = resolve_temporal_expression("I moved here last year.", JAN_20_TS)
    assert r.status == ResolutionStatus.AMBIGUOUS


def test_format_memories_includes_month_range_metadata() -> None:
    index = SourceMessageIndex(
        {
            "msg_jan": SourceMessageRecord(
                message_id="msg_jan",
                content="[Jon] Finishing choreography for a festival next month.",
                timestamp=JAN_20_TS,
                role="user",
            ),
        },
        "user_a",
    )
    text = format_memories(
        {
            "memories": [
                {
                    "memory_type": "event",
                    "content": "Jon performs at a festival next month",
                    "source_message_ids": ["msg_jan"],
                    "memory_id": "m1",
                }
            ]
        },
        index,
        question="When is Jon performing?",
        max_evidence_per_memory=1,
        enable_deterministic_temporal_resolver=True,
    )
    assert "Resolved event date range: 2023-02-01 ~ 2023-02-28" in text
