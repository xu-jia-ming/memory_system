"""Entrypoint for the memory-consolidation-worker process.

Safe to import. Runtime startup is not available until later Phase 0/4 tasks
provide configuration and scheduler wiring.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Run consolidation worker. Returns a non-zero exit code while not ready."""
    print(
        "memory-consolidation-worker is not ready: configuration (DEV-002) and "
        "consolidation scheduler wiring are not yet implemented; refusing to start.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
