"""Unit tests for constant-time API key verification."""

from __future__ import annotations

import hashlib
import secrets
from unittest.mock import patch

from pydantic import SecretStr

from memory_system.infrastructure.security.api_key import verify_api_key


def test_verify_api_key_equal_keys() -> None:
    expected = SecretStr("dev-memory-api-key-change-me")
    assert verify_api_key("dev-memory-api-key-change-me", expected) is True


def test_verify_api_key_unequal_keys() -> None:
    expected = SecretStr("dev-memory-api-key-change-me")
    assert verify_api_key("wrong-key", expected) is False


def test_verify_api_key_missing_key() -> None:
    expected = SecretStr("dev-memory-api-key-change-me")
    assert verify_api_key(None, expected) is False


def test_verify_api_key_uses_compare_digest() -> None:
    expected = SecretStr("short")
    with patch("memory_system.infrastructure.security.api_key.secrets.compare_digest") as compare:
        compare.return_value = False
        assert verify_api_key("different-length-value", expected) is False
        compare.assert_called_once()
        provided_digest, expected_digest = compare.call_args.args
        assert len(provided_digest) == len(expected_digest) == 64


def test_verify_api_key_different_lengths_use_fixed_length_digests() -> None:
    expected = SecretStr("a")
    provided = "much-longer-provided-value"
    assert (
        hashlib.sha256(provided.encode()).hexdigest()
        != hashlib.sha256(b"a").hexdigest()
    )
    assert verify_api_key(provided, expected) is False
    assert secrets.compare_digest(
        hashlib.sha256(provided.encode()).hexdigest(),
        hashlib.sha256(b"a").hexdigest(),
    ) is False
