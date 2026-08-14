#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

uv sync --locked

cp .env.example .env

echo "=== Static checks ==="
uv run ruff check src tests scripts
uv run mypy src
uv run python scripts/check_env_example.py

echo "=== Unit + Contract + Coverage ==="
uv run pytest tests/unit tests/contract \
  -m "not runtime_contract_gate and not task_scope_boundary" \
  --cov=memory_system.domain \
  --cov=memory_system.application \
  --cov-report=term-missing \
  --cov-fail-under=80 \
  -q

echo "=== Integration ==="
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  bash scripts/ci/prewarm_integration_stack.sh
  export INTEGRATION_SHARED_STACK=1
  export PYTEST_INTEGRATION_STRICT_SKIPS=1
  uv run pytest tests/integration \
    -m "not runtime_contract_gate" \
    -q
else
  echo "Docker not available — skipping integration (INT-SKIP-001)"
fi
