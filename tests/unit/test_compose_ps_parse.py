"""Unit tests for compose ps JSON parsing used by isolated integration modules."""

from __future__ import annotations

from tests.integration.support.compose_stack import parse_compose_ps_rows


def test_parse_compose_ps_array() -> None:
    rows = parse_compose_ps_rows('[{"Service":"redis","State":"running","Health":"healthy"}]')
    assert rows[0]["Service"] == "redis"


def test_parse_compose_ps_ndjson_ignores_warning_prefix() -> None:
    stdout = (
        "time=2026-08-14T13:07:45Z level=warning msg=noise\n"
        '{"Service":"neo4j","State":"running","Health":""}\n'
        '{"Service":"mongodb","State":"running","Health":"healthy"}\n'
    )
    rows = parse_compose_ps_rows(stdout)
    assert [row["Service"] for row in rows] == ["neo4j", "mongodb"]


def test_parse_compose_ps_empty_and_invalid() -> None:
    assert parse_compose_ps_rows("") == []
    assert parse_compose_ps_rows("not json") == []
    assert parse_compose_ps_rows("{not-json\n") == []
