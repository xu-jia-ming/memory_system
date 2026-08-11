"""Entrypoint for the memory-extraction-worker process.

Library-level Kafka consumer APIs exist for tests and EXT-002+ wiring.
Production ``main()`` refuses to start the poll loop until the real extraction
pipeline stages (EXT-002+) are ready (EXT-001 C7 / SF-001).
"""

from __future__ import annotations

import sys


def main() -> int:
    """Refuse to start; production pipeline stages are not ready (exit ≠ 0)."""
    print(
        "memory-extraction-worker is not ready: production extraction pipeline "
        "stages (EXT-002+) are not implemented; library-level archive-created "
        "consumer exists but main() refuses to start the Kafka poll loop.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
