"""Entrypoint for the memory-extraction-worker process.

Safe to import. Runtime startup is not available until later Phase 0/2 tasks
provide configuration and worker wiring.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Run extraction worker. Returns a non-zero exit code while not ready."""
    print(
        "memory-extraction-worker is not ready: configuration (DEV-002) and "
        "extraction worker wiring are not yet implemented; refusing to start.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
