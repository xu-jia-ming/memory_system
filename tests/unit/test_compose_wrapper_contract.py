"""Unit tests: compose wrapper, bare docker compose ban, and script contracts."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_SH = REPO_ROOT / "scripts" / "compose.sh"
START_EMBEDDING_SH = REPO_ROOT / "scripts" / "start_embedding.sh"
LOCK_TEI_SH = REPO_ROOT / "scripts" / "lock_tei_images.sh"
PREFLIGHT_SH = REPO_ROOT / "scripts" / "preflight" / "check_linux_host.sh"

BARE_DOCKER_COMPOSE_RE = re.compile(r"(?<![\w./-])docker\s+compose\b")

SCAN_ROOTS = (
    REPO_ROOT / "scripts",
    REPO_ROOT / "tests",
)
SCAN_EXTRA = (REPO_ROOT / "Makefile",)

ALLOWED_BARE_COMPOSE_FILES = {
    REPO_ROOT / "scripts" / "compose.sh",
    # This file intentionally references the banned pattern for static scanning.
    Path(__file__).resolve(),
}


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".sh", ".py", ".md", ""}:
                files.append(path)
    for extra in SCAN_EXTRA:
        if extra.exists():
            files.append(extra)
    return files


def test_no_bare_docker_compose_outside_wrapper() -> None:
    violations: list[str] = []
    for path in _iter_scan_files():
        if path.resolve() in {p.resolve() for p in ALLOWED_BARE_COMPOSE_FILES}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if BARE_DOCKER_COMPOSE_RE.search(text):
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, f"bare 'docker compose' found outside compose.sh: {violations}"


def test_compose_sh_exists_and_executable() -> None:
    assert COMPOSE_SH.is_file()
    assert COMPOSE_SH.stat().st_mode & 0o111


def test_compose_sh_contains_embedding_and_exec() -> None:
    text = COMPOSE_SH.read_text(encoding="utf-8")
    assert "--embedding=" in text
    assert "exec docker compose" in text
    assert "--stack=" in text
    assert "compose.override.yaml" in text
    assert "compose.test.yaml" in text
    assert "compose.embedding.cpu.yaml" in text
    assert "compose.embedding.gpu.yaml" in text


def test_start_embedding_sh_contract() -> None:
    assert START_EMBEDDING_SH.is_file()
    text = START_EMBEDDING_SH.read_text(encoding="utf-8")
    assert "cpu" in text
    assert "gpu" in text
    assert "auto" in text
    assert ".runtime/embedding.env" in text
    assert "embedding-service" in text


def test_lock_tei_images_sh_contract() -> None:
    assert LOCK_TEI_SH.is_file()
    text = LOCK_TEI_SH.read_text(encoding="utf-8")
    assert "--update" in text
    assert "text-embeddings-router" in text
    assert "versions.lock.env" in text


def test_lock_tei_images_sh_gpu_validation_requests_nvidia_runtime() -> None:
    """GPU TEI images must be version-checked with --gpus all (libcuda.so.1)."""
    text = LOCK_TEI_SH.read_text(encoding="utf-8")
    assert "is_gpu_tei_image" in text
    assert "--gpus all" in text
    assert "TEI_GPU_IMAGE" in text


def test_lock_tei_images_sh_fail_closed_version_diagnostics() -> None:
    """GPU runtime failures must not be masked as empty semantic-version parse errors."""
    text = LOCK_TEI_SH.read_text(encoding="utf-8")
    assert "version command failed" in text
    assert "stderr_file" in text
    assert "produced empty version output" in text


def test_preflight_script_exists() -> None:
    assert PREFLIGHT_SH.is_file()
    assert PREFLIGHT_SH.stat().st_mode & 0o111


def test_compose_sh_current_fails_without_runtime_env(tmp_path: Path) -> None:
    """--embedding=current must fail when .runtime/embedding.env is absent."""
    env_file = tmp_path / ".env"
    env_file.write_text((REPO_ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    # Run from repo root; if .runtime/embedding.env exists locally, skip destructive test.
    runtime_env = REPO_ROOT / ".runtime" / "embedding.env"
    if runtime_env.exists():
        return
    result = subprocess.run(
        [str(COMPOSE_SH), "--embedding=current", "config"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert ".runtime/embedding.env" in (result.stderr + result.stdout)
