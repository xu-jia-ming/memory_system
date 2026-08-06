"""Entrypoint for the memory-api process.

Safe to import. Runtime startup is not available until later Phase 0 tasks
wire settings (DEV-002) and the API shell (DEV-005).
"""

from __future__ import annotations

import sys


def main() -> int:
    """Run memory-api. Returns a non-zero exit code while the process is not ready."""
    print(
        "memory-api is not ready: configuration (DEV-002) and API wiring "
        "(DEV-005) are not yet implemented; refusing to start.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
