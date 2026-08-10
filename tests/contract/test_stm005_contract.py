"""STM-005 contract tests (no network, no Mongo I/O)."""

from __future__ import annotations

from memory_system.domain.enums.context_archive import ContextArchiveOutcome

OUTCOME_VALUES = frozenset(
    {
        ContextArchiveOutcome.CREATED,
        ContextArchiveOutcome.REUSED,
    }
)


def test_context_archive_outcome_literals_stable() -> None:
    assert ContextArchiveOutcome.CREATED.value == "created"
    assert ContextArchiveOutcome.REUSED.value == "reused"


def test_outcome_enum_values_match_members() -> None:
    for outcome in OUTCOME_VALUES:
        assert outcome.value == outcome


def test_outcome_set_has_exactly_two_values() -> None:
    assert len(OUTCOME_VALUES) == 2
