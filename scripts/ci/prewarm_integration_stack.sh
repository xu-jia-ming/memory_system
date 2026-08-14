#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

cp .env.example .env

./scripts/compose.sh --stack=test --embedding=none up -d \
  redis mongodb kafka neo4j elasticsearch

./scripts/compose.sh --stack=test --embedding=none run --rm init-infra
