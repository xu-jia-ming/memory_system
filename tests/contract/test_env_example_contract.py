"""Contract tests for ``.env.example`` completeness and safety."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from memory_system.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_env_example.py"


def _parse_env_example(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _ = line.split("=", 1)
        keys.add(key.strip())
    return keys


def test_check_env_example_script_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_env_example_contains_all_required_keys() -> None:
    required = set(Settings.required_env_keys())
    present = _parse_env_example(ENV_EXAMPLE_PATH)
    missing = required - present
    assert not missing, f"Missing keys in .env.example: {sorted(missing)}"


def test_env_example_includes_embedding_runtime_keys() -> None:
    present = _parse_env_example(ENV_EXAMPLE_PATH)
    assert "EMBEDDING_EFFECTIVE_RUNTIME_MODE" in present
    assert "EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET" in present


def test_check_env_example_fails_when_required_key_missing(tmp_path: Path) -> None:
    incomplete = "\n".join(
        f"{key}=example"
        for key in Settings.required_env_keys()
        if key != "MEMORY_API_KEY"
    )
    env_file = tmp_path / ".env.example"
    env_file.write_text(incomplete + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-c", CHECK_INLINE_SCRIPT, str(env_file)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "MEMORY_API_KEY" in result.stderr


CHECK_INLINE_SCRIPT = """
import sys
from pathlib import Path

from memory_system.settings import Settings

path = Path(sys.argv[1])
keys = set()
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _ = line.split("=", 1)
    keys.add(key.strip())

missing = [key for key in Settings.required_env_keys() if key not in keys]
if missing:
    for key in missing:
        print(f"  - {key}", file=sys.stderr)
    raise SystemExit(1)
raise SystemExit(0)
"""
