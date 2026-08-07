#!/usr/bin/env bash
# Unified Docker Compose wrapper (§3.10.2). The ONLY entry point for docker compose.
#
# Compose file order (--stack):
#   dev (default):  compose.yaml → compose.override.yaml → compose.embedding.{cpu|gpu}.yaml
#   test:           compose.yaml → compose.test.yaml → compose.embedding.{cpu|gpu}.yaml
#   none embedding: compose.yaml → compose.override.yaml|compose.test.yaml (no embedding override)
#
# Env file load order (each --env-file, later wins):
#   .env → versions.env → versions.lock.env → .runtime/embedding.env (if exists)
#
# Usage:
#   ./scripts/compose.sh [--embedding=none|cpu|gpu|current] [--stack=dev|test] <docker compose args...>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

EMBEDDING_MODE="current"
STACK="dev"

usage() {
  cat <<'EOF'
Usage: ./scripts/compose.sh [--embedding=none|cpu|gpu|current] [--stack=dev|test] <docker compose subcommand> [args...]

Defaults: --embedding=current --stack=dev

Compose -f order:
  dev:  compose.yaml → compose.override.yaml → [compose.embedding.{cpu|gpu}.yaml]
  test: compose.yaml → compose.test.yaml → [compose.embedding.{cpu|gpu}.yaml]

Env --env-file order:
  .env → versions.env → versions.lock.env → .runtime/embedding.env (if present)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --embedding=*)
      EMBEDDING_MODE="${1#--embedding=}"
      shift
      ;;
    --embedding)
      EMBEDDING_MODE="${2:?--embedding requires a value}"
      shift 2
      ;;
    --stack=*)
      STACK="${1#--stack=}"
      shift
      ;;
    --stack)
      STACK="${2:?--stack requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "compose.sh: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  echo "compose.sh: missing docker compose subcommand" >&2
  usage >&2
  exit 1
fi

case "${EMBEDDING_MODE}" in
  none|cpu|gpu|current) ;;
  *)
    echo "compose.sh: invalid --embedding=${EMBEDDING_MODE} (expected none|cpu|gpu|current)" >&2
    exit 1
    ;;
esac

case "${STACK}" in
  dev|test) ;;
  *)
    echo "compose.sh: invalid --stack=${STACK} (expected dev|test)" >&2
    exit 1
    ;;
esac

cd "${REPO_ROOT}"

RUNTIME_ENV="${REPO_ROOT}/.runtime/embedding.env"
RESOLVED_EMBEDDING="${EMBEDDING_MODE}"

if [[ "${EMBEDDING_MODE}" == "current" ]]; then
  if [[ ! -f "${RUNTIME_ENV}" ]]; then
    echo "compose.sh: .runtime/embedding.env not found." >&2
    echo "Run ./scripts/start_embedding.sh {cpu|gpu|auto} first, or pass --embedding=none|cpu|gpu explicitly." >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "${RUNTIME_ENV}"
  if [[ "${EMBEDDING_EFFECTIVE_RUNTIME_MODE:-}" != "cpu" && "${EMBEDDING_EFFECTIVE_RUNTIME_MODE:-}" != "gpu" ]]; then
    echo "compose.sh: EMBEDDING_EFFECTIVE_RUNTIME_MODE must be cpu or gpu in ${RUNTIME_ENV}" >&2
    exit 1
  fi
  case "${EMBEDDING_EFFECTIVE_RUNTIME_MODE}" in
    cpu)
      expected_budget="4096"
      ;;
    gpu)
      expected_budget="16384"
      ;;
  esac
  if [[ "${EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET:-}" != "${expected_budget}" ]]; then
    echo "compose.sh: EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET=${EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET:-} does not match mode ${EMBEDDING_EFFECTIVE_RUNTIME_MODE} (expected ${expected_budget})" >&2
    exit 1
  fi
  RESOLVED_EMBEDDING="${EMBEDDING_EFFECTIVE_RUNTIME_MODE}"
elif [[ "${EMBEDDING_MODE}" == "cpu" ]]; then
  export EMBEDDING_EFFECTIVE_RUNTIME_MODE="cpu"
  export EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET="4096"
elif [[ "${EMBEDDING_MODE}" == "gpu" ]]; then
  export EMBEDDING_EFFECTIVE_RUNTIME_MODE="gpu"
  export EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET="16384"
fi

compose_files=("${REPO_ROOT}/compose.yaml")
if [[ "${STACK}" == "dev" ]]; then
  compose_files+=("${REPO_ROOT}/compose.override.yaml")
else
  compose_files+=("${REPO_ROOT}/compose.test.yaml")
fi

if [[ "${RESOLVED_EMBEDDING}" == "cpu" ]]; then
  compose_files+=("${REPO_ROOT}/compose.embedding.cpu.yaml")
elif [[ "${RESOLVED_EMBEDDING}" == "gpu" ]]; then
  compose_files+=("${REPO_ROOT}/compose.embedding.gpu.yaml")
fi

env_files=(
  "${REPO_ROOT}/.env"
  "${REPO_ROOT}/versions.env"
  "${REPO_ROOT}/versions.lock.env"
)
if [[ -f "${RUNTIME_ENV}" ]]; then
  env_files+=("${RUNTIME_ENV}")
fi

compose_args=()
for f in "${compose_files[@]}"; do
  compose_args+=(-f "${f}")
done
for ef in "${env_files[@]}"; do
  if [[ -f "${ef}" ]]; then
    compose_args+=(--env-file "${ef}")
  fi
done

# .env is required for app container env_file references and PROXY__HTTP_URL interpolation.
if [[ ! -f "${REPO_ROOT}/.env" ]]; then
  echo "compose.sh: .env not found. Copy .env.example to .env first." >&2
  exit 1
fi

exec docker compose "${compose_args[@]}" "$@"
