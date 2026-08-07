#!/usr/bin/env bash
# Select CPU/GPU embedding mode, write .runtime/embedding.env, start embedding-service only (§3.10.5).
#
# Usage: ./scripts/start_embedding.sh [cpu|gpu|auto]
# Default mode: auto

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNTIME_DIR="${REPO_ROOT}/.runtime"
RUNTIME_ENV="${RUNTIME_DIR}/embedding.env"
LOCK_FILE="${REPO_ROOT}/versions.lock.env"

MODE="${1:-auto}"
MIN_GPU_FREE_MIB=8192

usage() {
  cat <<'EOF'
Usage: ./scripts/start_embedding.sh [cpu|gpu|auto]

Modes:
  cpu   — unconditional CPU override (budget 4096)
  gpu   — require NVIDIA + RTX A5000 + free VRAM >= 8192 MiB (budget 16384); no auto-fallback
  auto  — GPU-first; fall back to CPU on GPU path failure (default)

Writes .runtime/embedding.env and runs:
  ./scripts/compose.sh --embedding=<resolved> up -d embedding-service
EOF
}

log() { printf '%s\n' "$*"; }
fail() { printf 'start_embedding.sh: %s\n' "$*" >&2; exit 1; }

validate_lock_file() {
  if [[ ! -f "${LOCK_FILE}" ]]; then
    fail "versions.lock.env missing. Run ./scripts/lock_tei_images.sh --update first."
  fi
  # shellcheck disable=SC1090
  source "${LOCK_FILE}"
  for var in TEI_CPU_IMAGE TEI_GPU_IMAGE; do
    local value="${!var:-}"
    if [[ -z "${value}" || "${value}" != *@sha256:* ]]; then
      fail "${var} must contain @sha256: digest in versions.lock.env. Run ./scripts/lock_tei_images.sh --update."
    fi
    if [[ "${value}" =~ @sha256:0{64}$ ]]; then
      fail "${var} has placeholder digest. Run ./scripts/lock_tei_images.sh --update."
    fi
  done
}

write_runtime_env() {
  local resolved_mode="$1"
  local resolved_budget="$2"
  mkdir -p "${RUNTIME_DIR}"
  local tmp
  tmp="$(mktemp "${RUNTIME_DIR}/embedding.env.XXXXXX")"
  cat >"${tmp}" <<EOF
EMBEDDING_EFFECTIVE_RUNTIME_MODE=${resolved_mode}
EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET=${resolved_budget}
EOF
  mv "${tmp}" "${RUNTIME_ENV}"
}

gpu_path_healthy() {
  command -v nvidia-smi >/dev/null 2>&1 || return 1
  docker info 2>/dev/null | grep -qi nvidia || return 1
  nvidia-smi --query-gpu=name,memory.free --format=csv,noheader,nounits 2>/dev/null \
    | awk -F',' -v min="${MIN_GPU_FREE_MIB}" '
      {
        gsub(/^[ \t]+|[ \t]+$/, "", $1);
        gsub(/^[ \t]+|[ \t]+$/, "", $2);
        if ($1 ~ /A5000/ && $2 + 0 >= min) { found=1 }
      }
      END { exit(found ? 0 : 1) }'
}

mem_available_gib() {
  awk '/^MemAvailable:/ { printf "%.2f\n", $2 / 1024 / 1024 }' /proc/meminfo
}

mem_available_at_least() {
  local threshold_gib="$1"
  awk -v t="${threshold_gib}" '/^MemAvailable:/ { exit ($2 / 1024 / 1024 >= t) ? 0 : 1 }' /proc/meminfo
}

cleanup_failed_embedding() {
  "${SCRIPT_DIR}/compose.sh" --embedding="${1}" down embedding-service 2>/dev/null || true
  docker rm -f memory-system-embedding-service-1 memory-system-embedding-test 2>/dev/null || true
}

start_embedding_service() {
  local resolved="$1"
  if ! "${SCRIPT_DIR}/compose.sh" --embedding="${resolved}" up -d embedding-service; then
    return 1
  fi
  return 0
}

resolve_auto_mode() {
  if gpu_path_healthy && mem_available_at_least 8; then
    echo "gpu"
    return 0
  fi
  if mem_available_at_least 12; then
    echo "cpu"
    return 0
  fi
  fail "auto mode: neither GPU path nor CPU path (>=12 GiB MemAvailable) satisfied"
}

case "${MODE}" in
  -h|--help)
    usage
    exit 0
    ;;
  cpu|gpu|auto) ;;
  *)
    fail "invalid mode '${MODE}'. Expected cpu|gpu|auto."
    ;;
esac

validate_lock_file

RESOLVED_MODE=""
RESOLVED_BUDGET=""

case "${MODE}" in
  cpu)
    if ! mem_available_at_least 12; then
      fail "cpu mode: MemAvailable below 12 GiB minimum"
    fi
    RESOLVED_MODE="cpu"
    RESOLVED_BUDGET="4096"
    ;;
  gpu)
    if ! gpu_path_healthy; then
      fail "gpu mode: NVIDIA driver, Container Toolkit, RTX A5000, or free VRAM >= ${MIN_GPU_FREE_MIB} MiB not satisfied"
    fi
    if ! mem_available_at_least 8; then
      fail "gpu mode: MemAvailable below 8 GiB minimum"
    fi
    RESOLVED_MODE="gpu"
    RESOLVED_BUDGET="16384"
    ;;
  auto)
    RESOLVED_MODE="$(resolve_auto_mode)"
    if [[ "${RESOLVED_MODE}" == "gpu" ]]; then
      RESOLVED_BUDGET="16384"
    else
      RESOLVED_BUDGET="4096"
    fi
    ;;
esac

write_runtime_env "${RESOLVED_MODE}" "${RESOLVED_BUDGET}"
log "Wrote ${RUNTIME_ENV}: mode=${RESOLVED_MODE} budget=${RESOLVED_BUDGET}"

if [[ "${MODE}" == "auto" && "${RESOLVED_MODE}" == "gpu" ]]; then
  if ! start_embedding_service gpu; then
    log "GPU embedding-service start failed; cleaning up and falling back to CPU"
    cleanup_failed_embedding gpu
    RESOLVED_MODE="cpu"
    RESOLVED_BUDGET="4096"
    write_runtime_env "${RESOLVED_MODE}" "${RESOLVED_BUDGET}"
    start_embedding_service cpu
  fi
else
  start_embedding_service "${RESOLVED_MODE}"
fi

log "embedding-service started with mode=${RESOLVED_MODE}"
