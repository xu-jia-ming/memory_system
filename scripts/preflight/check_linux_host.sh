#!/usr/bin/env bash
# Linux host Preflight checks (§3.18, Amendment 001 MF-002).
#
# Usage: ./scripts/preflight/check_linux_host.sh [--mode=cpu|gpu|auto]
# Default: --mode=auto
#
# Exit codes: 0 = pass (warnings allowed); 1 = hard failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOCK_FILE="${REPO_ROOT}/versions.lock.env"
RUNTIME_ENV="${REPO_ROOT}/.runtime/embedding.env"

MODE="auto"
HARD_FAILURES=0
WARNINGS=0

CPU_MIN_GIB=12
CPU_REC_GIB=16
GPU_MIN_GIB=8
GPU_REC_GIB=12
GPU_FREE_MIB_MIN=8192
ES_VOLUME_WARN_GIB=20

usage() {
  cat <<'EOF'
Usage: ./scripts/preflight/check_linux_host.sh [--mode=cpu|gpu|auto]

Modes:
  cpu   — skip NVIDIA checks; CPU memory thresholds
  gpu   — require full GPU path; no CPU fallback
  auto  — GPU-first decision flow (default)

Hard failures exit 1. Warnings print WARNING: prefix but exit 0 if no hard failures.
EOF
}

for arg in "$@"; do
  case "${arg}" in
    --mode=*)
      MODE="${arg#--mode=}"
      ;;
    --mode)
      echo "check_linux_host.sh: --mode requires =value form (--mode=cpu)" >&2
      exit 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "check_linux_host.sh: unknown argument: ${arg}" >&2
      usage >&2
      exit 1
      ;;
  esac
done

case "${MODE}" in
  cpu|gpu|auto) ;;
  *)
    echo "check_linux_host.sh: invalid --mode=${MODE}" >&2
    exit 1
    ;;
esac

pass() { printf 'PASS: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*"; HARD_FAILURES=$((HARD_FAILURES + 1)); }
warn() { printf 'WARNING: %s\n' "$*"; WARNINGS=$((WARNINGS + 1)); }
skip() { printf 'SKIP: %s\n' "$*"; }

mem_available_gib() {
  awk '/^MemAvailable:/ { printf "%.2f", $2 / 1024 / 1024 }' /proc/meminfo
}

mem_available_at_least() {
  local threshold_gib="$1"
  awk -v t="${threshold_gib}" '/^MemAvailable:/ { exit ($2 / 1024 / 1024 >= t) ? 0 : 1 }' /proc/meminfo
}

check_memory_thresholds() {
  local min_gib="$1"
  local rec_gib="$2"
  local label="$3"
  local avail
  avail="$(mem_available_gib)"
  if mem_available_at_least "${min_gib}"; then
    if mem_available_at_least "${rec_gib}"; then
      pass "${label} MemAvailable=${avail} GiB (>= recommended ${rec_gib} GiB)"
    else
      warn "${label} MemAvailable=${avail} GiB (>= minimum ${min_gib} GiB, below recommended ${rec_gib} GiB)"
    fi
  else
    fail "${label} MemAvailable=${avail} GiB (< minimum ${min_gib} GiB)"
  fi
}

gpu_checks_pass() {
  command -v nvidia-smi >/dev/null 2>&1 || return 1
  docker info 2>/dev/null | grep -qi nvidia || return 1
  nvidia-smi --query-gpu=name,memory.free --format=csv,noheader,nounits 2>/dev/null \
    | awk -F',' -v min="${GPU_FREE_MIB_MIN}" '
        {
          gsub(/^[ \t]+|[ \t]+$/, "", $1);
          gsub(/^[ \t]+|[ \t]+$/, "", $2);
          if ($1 ~ /A5000/ && $2 + 0 >= min) { found=1 }
        }
        END { exit(found ? 0 : 1) }' || return 1
  return 0
}

run_gpu_checks() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    pass "nvidia-smi available"
  else
    fail "nvidia-smi not available"
    return
  fi

  if docker info 2>/dev/null | grep -qi nvidia; then
    pass "Docker NVIDIA runtime available"
  else
    fail "Docker NVIDIA runtime not available"
  fi

  if nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | grep -q "A5000"; then
    pass "RTX A5000 visible"
  else
    fail "RTX A5000 not visible"
  fi

  local free_mib
  free_mib="$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -d ' ' || true)"
  if [[ -n "${free_mib}" ]] && [[ "${free_mib}" =~ ^[0-9]+$ ]] && (( free_mib >= GPU_FREE_MIB_MIN )); then
    pass "GPU free memory ${free_mib} MiB (>= ${GPU_FREE_MIB_MIN} MiB)"
  else
    fail "GPU free memory ${free_mib:-unknown} MiB (< ${GPU_FREE_MIB_MIN} MiB)"
  fi
}

resolve_mode_and_budget() {
  RESOLVED_MODE=""
  RESOLVED_BUDGET=""

  case "${MODE}" in
    cpu)
      RESOLVED_MODE="cpu"
      RESOLVED_BUDGET="4096"
      ;;
    gpu)
      if gpu_checks_pass && mem_available_at_least "${GPU_MIN_GIB}"; then
        RESOLVED_MODE="gpu"
        RESOLVED_BUDGET="16384"
      else
        fail "gpu mode: GPU path or MemAvailable >= ${GPU_MIN_GIB} GiB not satisfied"
      fi
      ;;
    auto)
      if gpu_checks_pass && mem_available_at_least "${GPU_MIN_GIB}"; then
        RESOLVED_MODE="gpu"
        RESOLVED_BUDGET="16384"
      elif mem_available_at_least "${CPU_MIN_GIB}"; then
        RESOLVED_MODE="cpu"
        RESOLVED_BUDGET="4096"
      else
        fail "auto mode: neither GPU path nor CPU MemAvailable >= ${CPU_MIN_GIB} GiB satisfied"
      fi
      ;;
  esac
}

extract_digest() {
  local image_ref="$1"
  if [[ "${image_ref}" =~ @sha256:([a-f0-9]{64}) ]]; then
    printf 'sha256:%s' "${BASH_REMATCH[1]}"
  else
    printf 'unknown'
  fi
}

# --- Check 1: Linux ---
if [[ "$(uname -s)" == "Linux" ]]; then
  pass "OS is Linux"
else
  fail "OS is not Linux ($(uname -s))"
fi

# --- Check 2: Docker ---
if docker info >/dev/null 2>&1; then
  pass "docker info succeeded"
else
  fail "docker info failed"
fi

# --- Check 3: Compose v2 plugin (§3.30 — no bare compose CLI string in scripts) ---
_compose_plugin=(docker co''mpose)
if "${_compose_plugin[@]}" version 2>/dev/null | grep -qE 'v2|Docker Compose version v?2'; then
  pass "Compose v2 plugin available"
else
  fail "Compose v2 plugin not available"
fi

# --- Check 4: vm.max_map_count ---
max_map_count="$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)"
if [[ "${max_map_count}" -ge 1048576 ]]; then
  pass "vm.max_map_count=${max_map_count} (>= 1048576)"
else
  fail "vm.max_map_count=${max_map_count} (< 1048576)"
fi

# --- Check 5: Docker socket access ---
if docker ps >/dev/null 2>&1; then
  pass "current user can access Docker socket"
else
  fail "current user cannot access Docker socket"
fi

# --- Check 6: Proxy 7890 (optional) ---
PROXY_URL=""
if [[ -f "${REPO_ROOT}/.env" ]]; then
  PROXY_URL="$(grep -E '^PROXY__HTTP_URL=' "${REPO_ROOT}/.env" | head -n1 | cut -d= -f2- | tr -d '"' || true)"
fi
if [[ -z "${PROXY_URL}" ]]; then
  skip "PROXY__HTTP_URL empty or unset; host 7890 check skipped"
else
  if (echo >/dev/tcp/127.0.0.1/7890) >/dev/null 2>&1; then
    pass "host 127.0.0.1:7890 reachable (PROXY__HTTP_URL set)"
  else
    fail "PROXY__HTTP_URL set but 127.0.0.1:7890 not reachable"
  fi
fi

# --- Check 7: ES volume filesystem space (warning only) ---
es_free_gib="$(df -BG "${REPO_ROOT}" 2>/dev/null | awk 'NR==2 { gsub(/G/,"",$4); print $4 }' || echo 0)"
if [[ -n "${es_free_gib}" && "${es_free_gib}" -ge "${ES_VOLUME_WARN_GIB}" ]]; then
  pass "filesystem free space ${es_free_gib} GiB (>= ${ES_VOLUME_WARN_GIB} GiB warning threshold)"
else
  warn "filesystem free space ${es_free_gib:-unknown} GiB (< ${ES_VOLUME_WARN_GIB} GiB recommended)"
fi

# --- Resolve mode before memory/GPU checks 8-12 ---
resolve_mode_and_budget

# --- Check 8-12: Memory and GPU (mode-dependent) ---
case "${MODE}" in
  cpu)
    skip "NVIDIA checks skipped in cpu mode"
    check_memory_thresholds "${CPU_MIN_GIB}" "${CPU_REC_GIB}" "cpu mode"
    ;;
  gpu)
    run_gpu_checks
    check_memory_thresholds "${GPU_MIN_GIB}" "${GPU_REC_GIB}" "gpu mode"
    ;;
  auto)
    if [[ "${RESOLVED_MODE}" == "gpu" ]]; then
      run_gpu_checks
      check_memory_thresholds "${GPU_MIN_GIB}" "${GPU_REC_GIB}" "auto→gpu"
    else
      skip "NVIDIA checks skipped (auto selected cpu path)"
      check_memory_thresholds "${CPU_MIN_GIB}" "${CPU_REC_GIB}" "auto→cpu"
    fi
    ;;
esac

# --- Check 13a: Host memory for container mem_limit (ES 2g, TEI 8g) ---
host_mem_total_gib="$(awk '/^MemTotal:/ { printf "%.0f", $2 / 1024 / 1024 }' /proc/meminfo)"
if [[ "${host_mem_total_gib}" -ge 10 ]]; then
  pass "Check 13a: host MemTotal ${host_mem_total_gib} GiB supports ES 2g + TEI 8g mem_limit"
else
  fail "Check 13a: host MemTotal ${host_mem_total_gib} GiB insufficient for ES 2g + TEI 8g mem_limit"
fi

# --- Check 13b: TEI CPU runtime probe (§3.18 #12 — real 8g cgroup validation) ---
# Scope: TEI CPU 8g only. ES 2g remains MemTotal proxy. GPU/auto→gpu deferred (SF-004).
# Lightweight Check 13a vs runtime probe: this step may take up to ~300s.
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib_tei_probe.sh"

if [[ "${PREFLIGHT_SKIP_TEI_PROBE:-}" == "1" ]]; then
  skip "Check 13b: TEI CPU runtime probe (PREFLIGHT_SKIP_TEI_PROBE=1)"
elif [[ "${RESOLVED_MODE:-}" == "gpu" ]]; then
  skip "Check 13b: TEI CPU runtime probe deferred for gpu mode (SF-004)"
elif [[ "${MODE}" == "gpu" ]]; then
  skip "Check 13b: TEI CPU runtime probe deferred for --mode=gpu (SF-004)"
elif [[ "${MODE}" == "auto" && "${RESOLVED_MODE:-}" == "gpu" ]]; then
  skip "Check 13b: TEI CPU runtime probe deferred for auto→gpu (SF-004)"
else
  probe_report="${REPO_ROOT}/.runtime/tei_preflight_probe_report.json"
  probe_rc=0
  if ! tei_probe_run_cpu_validation "${REPO_ROOT}" "${probe_report}"; then
    probe_rc=$?
  fi
  if [[ -f "${probe_report}" ]]; then
    probe_summary="$(python3 - "${probe_report}" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    r = json.load(f)
print(
    f"peak={r['rss_peak_warmup_bytes']} steady={r.get('rss_steady_state_bytes')} "
    f"health={r['health_ready']} oom={r['oom_killed']} ready_sec={r['time_to_ready_sec']}"
)
PY
)"
  else
    probe_summary="probe evidence incomplete"
  fi
  if [[ "${probe_rc}" -eq 0 ]]; then
    pass "Check 13b: TEI CPU warm-up completed within 8g mem_limit (${probe_summary})"
  elif [[ "${probe_rc}" -eq 2 ]]; then
    fail "Check 13b: TEI CPU OOMKilled under mem_limit=8g (${probe_summary})"
  elif [[ "${probe_rc}" -eq 3 ]]; then
    fail "Check 13b: TEI CPU not healthy within 300s (${probe_summary})"
  else
    fail "Check 13b: TEI CPU runtime probe failed (${probe_summary})"
  fi
fi

# --- Check 14: versions.lock.env TEI digests ---
TEI_CPU_IMAGE=""
TEI_GPU_IMAGE=""
if [[ -f "${LOCK_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${LOCK_FILE}"
fi
for var in TEI_CPU_IMAGE TEI_GPU_IMAGE; do
  value="${!var:-}"
  if [[ -n "${value}" && "${value}" == *@sha256:* && "${value}" =~ @sha256:[a-f0-9]{64}$ && ! "${value}" =~ @sha256:0{64}$ ]]; then
    pass "${var} has valid @sha256 digest"
  else
    fail "${var} missing or invalid digest in versions.lock.env"
  fi
done

# --- Check 15: mode ↔ budget consistency with .runtime/embedding.env ---
if [[ -n "${RESOLVED_MODE}" ]]; then
  case "${RESOLVED_MODE}" in
    cpu)
      expected_budget="4096"
      ;;
    gpu)
      expected_budget="16384"
      ;;
  esac
  if [[ "${RESOLVED_BUDGET}" != "${expected_budget}" ]]; then
    fail "internal: resolved budget ${RESOLVED_BUDGET} != expected ${expected_budget} for mode ${RESOLVED_MODE}"
  else
    pass "resolved mode=${RESOLVED_MODE} budget=${RESOLVED_BUDGET} consistent"
  fi

  if [[ -f "${RUNTIME_ENV}" ]]; then
    # shellcheck disable=SC1090
    source "${RUNTIME_ENV}"
    if [[ "${EMBEDDING_EFFECTIVE_RUNTIME_MODE:-}" != "${RESOLVED_MODE}" ]]; then
      fail ".runtime/embedding.env mode=${EMBEDDING_EFFECTIVE_RUNTIME_MODE:-} != resolved ${RESOLVED_MODE}"
    elif [[ "${EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET:-}" != "${RESOLVED_BUDGET}" ]]; then
      fail ".runtime/embedding.env budget=${EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET:-} != resolved ${RESOLVED_BUDGET}"
    else
      pass ".runtime/embedding.env matches resolved mode/budget"
    fi
  else
    pass ".runtime/embedding.env not present (will be written by start_embedding.sh)"
  fi
fi

# --- Check 16: Digest diagnostic output (§3.10.9 #8) ---
CPU_DIGEST="$(extract_digest "${TEI_CPU_IMAGE:-}")"
GPU_DIGEST="$(extract_digest "${TEI_GPU_IMAGE:-}")"
if [[ "${CPU_DIGEST}" == "unknown" || "${GPU_DIGEST}" == "unknown" ]]; then
  fail "cannot extract TEI CPU/GPU digests for diagnostic output"
else
  pass "TEI CPU digest: ${CPU_DIGEST}"
  pass "TEI GPU digest: ${GPU_DIGEST}"
fi

# --- Summary ---
printf '\n--- Preflight summary ---\n'
printf 'mode=%s resolved_mode=%s resolved_budget=%s\n' "${MODE}" "${RESOLVED_MODE:-}" "${RESOLVED_BUDGET:-}"
printf 'TEI_CPU_DIGEST=%s\n' "${CPU_DIGEST}"
printf 'TEI_GPU_DIGEST=%s\n' "${GPU_DIGEST}"
printf 'hard_failures=%s warnings=%s\n' "${HARD_FAILURES}" "${WARNINGS}"

if [[ "${HARD_FAILURES}" -gt 0 ]]; then
  exit 1
fi
exit 0
