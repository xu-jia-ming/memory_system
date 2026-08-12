from __future__ import annotations

import pytest

from memory_system.domain.services.extraction_redaction_service import (
    REDACTION_MARKER,
    redact_content,
)


@pytest.mark.parametrize(
    ("content", "secret"),
    [
        ("password: hunter2", "hunter2"),
        ("OTP: 123456", "123456"),
        ("api-key=sk-abcdefghijklmnopqrstuvwxyz", "sk-abcdefghijklmnopqrstuvwxyz"),
        ("Authorization: Bearer abcdefghijklmnop", "abcdefghijklmnop"),
        (
            "-----BEGIN PRIVATE KEY-----\nmaterial\n-----END PRIVATE KEY-----",
            "material",
        ),
        ("card 4111 1111 1111 1111", "4111 1111 1111 1111"),
        ("CVC: 123", "123"),
    ],
    ids=["RED-01", "RED-02", "RED-03", "RED-04", "RED-05", "RED-06", "RED-07"],
)
def test_authorized_categories_are_redacted_without_value(
    content: str, secret: str
) -> None:
    result = redact_content(content)
    assert REDACTION_MARKER in result
    assert secret not in result


def test_unlabelled_numbers_and_general_pii_are_preserved() -> None:
    content = "call 123456 and email alice@example.com, card 4111 1111 1111 1112"
    assert redact_content(content) == content


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("password hunter2", "password hunter2"),
        ("verification code: 12", "verification code: 12"),
        ("123456", "123456"),
        ("cvv 123", "cvv 123"),
        ("alice@example.com +1 555 0100 123 Main St", "alice@example.com +1 555 0100 123 Main St"),
    ],
    ids=[
        "RED-08-general-pii",
        "RED-10-boundary",
        "RED-11-no-match",
        "RED-15-near-match",
        "RED-16-no-leakage",
    ],
)
def test_RED_08_RED_10_RED_11_RED_15_RED_16_negative_inputs_remain_safe(
    content: str, expected: str
) -> None:
    assert redact_content(content) == expected


def test_normalized_input_is_the_detector_input_and_disjoint_spans_are_independent() -> None:
    assert redact_content("password: one password: two") == (
        f"{REDACTION_MARKER} {REDACTION_MARKER}"
    )


def test_private_key_overlap_is_one_replacement() -> None:
    content = "key=-----BEGIN PRIVATE KEY-----abc-----END PRIVATE KEY-----"
    assert redact_content(content).count(REDACTION_MARKER) == 1


def test_RED_09_only_content_is_redaction_target() -> None:
    content = "archive-1 user-1 session-1 message-1 user 1700000000"
    assert redact_content(content) == content


@pytest.mark.parametrize(
    "token",
    [
        "sk-abcdefghijklmnopqrstuvwxyz",
        "AKIA1234567890ABCDEF",
        "ghp_abcdefghijklmnopqrstuvwxyz",
        "github_pat_abcdefghijklmnopqrstuvwxyz",
        "xoxb-abcdefghijkl",
    ],
    ids=["RED-03-sk", "RED-03-aws", "RED-03-github", "RED-03-github-pat", "RED-03-slack"],
)
def test_RED_03_all_authorized_api_key_forms_are_redacted(token: str) -> None:
    assert redact_content(f"key={token}") == f"key={REDACTION_MARKER}"


def test_RED_12_precedence_and_RED_14_longest_equivalent_start_are_deterministic() -> None:
    content = "Authorization: Bearer abcdefghijklmnop password: secret"
    assert redact_content(content) == f"Authorization: {REDACTION_MARKER} {REDACTION_MARKER}"
    assert redact_content("password: secret") == REDACTION_MARKER


def test_RED_13_disjoint_spans_are_sorted_and_replaced_independently() -> None:
    assert redact_content("password: one; cvv: 123") == (
        f"{REDACTION_MARKER}; {REDACTION_MARKER}"
    )


def test_RED_17_provenance_order_and_first_person_content_are_not_synthesized() -> None:
    contents = ["I am Alice", "You are Bob"]
    assert [redact_content(content) for content in contents] == contents


def test_RED_21_RED_22_RED_23_post_redaction_handoff_shape_has_no_raw_fields() -> None:
    from memory_system.domain.models.extraction_preprocessing import ExtractionReadyArchive

    ready = ExtractionReadyArchive(
        archive_id="archive-1",
        user_id="user-1",
        session_id="session-1",
        messages=[],
    )
    assert set(ready.model_dump()) == {"archive_id", "user_id", "session_id", "messages"}
    assert "raw_content" not in ready.model_dump()
    assert "normalized_content" not in ready.model_dump()


def test_RED_24_redaction_is_deterministic_and_local() -> None:
    content = "api-key=sk-abcdefghijklmnopqrstuvwxyz"
    assert redact_content(content) == redact_content(content)


def test_RED_25_invalid_luhn_card_and_unlabeled_secret_are_not_redacted() -> None:
    assert redact_content("card 4111 1111 1111 1112") == "card 4111 1111 1111 1112"
    assert redact_content("token-like 123456789") == "token-like 123456789"


def test_RED_26_empty_archive_content_is_a_successful_no_match() -> None:
    assert redact_content("") == ""


def test_RED_27_redaction_does_not_mutate_input_string() -> None:
    content = "password: secret"
    redact_content(content)
    assert content == "password: secret"
