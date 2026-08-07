#!/usr/bin/env python3
"""Validate that ``.env.example`` contains all required settings keys without real secrets."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from memory_system.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

DENY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*[^\s#]{32,}"),
)


def parse_env_example(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=value format")
        key, value = line.split("=", 1)
        entries[key.strip()] = value.strip()
    return entries


def find_secret_violations(path: Path) -> list[str]:
    violations: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for pattern in DENY_PATTERNS:
            if pattern.search(stripped):
                if "example" in stripped.lower() or "change-me" in stripped.lower():
                    continue
                violations.append(f"{path}:{line_number}: suspicious secret-like value")
    return violations


def main() -> int:
    if not ENV_EXAMPLE_PATH.exists():
        print(f"Missing required file: {ENV_EXAMPLE_PATH}", file=sys.stderr)
        return 1

    try:
        env_example = parse_env_example(ENV_EXAMPLE_PATH)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    required_keys = Settings.required_env_keys()
    missing_keys = [key for key in required_keys if key not in env_example]
    if missing_keys:
        print("Missing required keys in .env.example:", file=sys.stderr)
        for key in missing_keys:
            print(f"  - {key}", file=sys.stderr)
        return 1

    violations = find_secret_violations(ENV_EXAMPLE_PATH)
    if violations:
        print("Potential secrets detected in .env.example:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1

    print(f".env.example validation passed ({len(required_keys)} required keys).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
