"""Entrypoint for the memory-api process."""

from __future__ import annotations

import sys

import uvicorn

from memory_system.api import create_app
from memory_system.settings import get_settings


def main() -> int:
    """Run memory-api with Uvicorn."""
    try:
        settings = get_settings()
    except Exception as exc:
        print(f"memory-api failed to load settings: {exc}", file=sys.stderr)
        return 1

    app = create_app(settings=settings)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        timeout_graceful_shutdown=settings.shutdown.memory_api_timeout_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
