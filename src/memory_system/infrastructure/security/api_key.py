"""Constant-time API key verification."""

from __future__ import annotations

import hashlib
import secrets
from enum import StrEnum

from pydantic import SecretStr


class ApiKeyRole(StrEnum):
    MEMORY = "memory"
    ADMIN = "admin"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_api_key(provided: str | None, expected: SecretStr) -> bool:
    """Compare API keys in constant time without logging secrets."""
    provided_value = provided or ""
    expected_value = expected.get_secret_value()
    return secrets.compare_digest(_digest(provided_value), _digest(expected_value))
