"""OPS-002 static user isolation inventory contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "memory_system"

EXPECTED_HTTP_ISOLATION = {
    "memory_session.py": "user_id",
    "memory_message.py": "user_id",
    "memory_retrieval.py": "user_id",
    "memory_extraction_admin.py": "require_admin_api_key",
}


def test_http_routes_declare_user_isolation_enforcement() -> None:
    routes_dir = SRC / "api" / "routes"
    for route_file, marker in EXPECTED_HTTP_ISOLATION.items():
        content = (routes_dir / route_file).read_text(encoding="utf-8")
        assert marker in content, f"{route_file} missing isolation marker {marker!r}"


def test_admin_extraction_uses_user_scoped_lookup() -> None:
    admin_service = (SRC / "domain" / "services" / "extraction_admin_service.py").read_text(
        encoding="utf-8"
    )
    assert "find_extraction_task_by_user_and_archive_id" in admin_service


def test_context_read_redis_expected_user_guard_present() -> None:
    redis_repo = (SRC / "infrastructure" / "redis" / "context_read_repository.py").read_text(
        encoding="utf-8"
    )
    assert "expected_user_id" in redis_repo
