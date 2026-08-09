#!/usr/bin/env bash
# Measure TEI CPU warm-up peak and steady-state RSS (DEV-003-002 + OI-011).
#
# Characterization (OI-011 §5.3):
#   - Uses lib_tei_probe.sh explicit multi -f helper for ALL limits including 8g
#   - NEVER uses scripts/compose.sh
#   - NEVER uses docker update
#
# Usage:
#   ./scripts/diagnostics/measure_tei_memory.sh \
#     [--mem-limit=8g|10g|12g|16g] [--timeout=300] [--output=PATH] [--run-id=ID]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/preflight/lib_tei_probe.sh"

TIMEOUT_SEC="${TEI_PROBE_TIMEOUT_SEC}"
OUTPUT_JSON="${REPO_ROOT}/.runtime/tei_memory_report.json"
MEM_LIMIT="${TEI_SPEC_MEM_LIMIT}"
RUN_ID=""

usage() {
  cat <<'EOF'
Usage: ./scripts/diagnostics/measure_tei_memory.sh [options]

Options:
  --mem-limit=8g|10g|12g|16g   Container cgroup mem_limit (default: formal TEI_SPEC_MEM_LIMIT)
  --timeout=SECONDS            Warm-up/ready observation window (default: 300)
  --output=PATH                JSON evidence path
  --run-id=ID                  Optional audit run_id

Behavior (OI-011):
  - Starts/stops via lib_tei_probe.sh explicit docker compose -f chain
    (compose.yaml → compose.override.yaml → compose.embedding.cpu.yaml
     → optional compose.embedding.cpu.mem{N}g.yaml for N≠8)
  - Does NOT use scripts/compose.sh
  - Does NOT use docker update
  - Asserts HostConfig.Memory bytes equal the requested limit

Exit codes: 0=success; 1=compose/other; 2=OOM; 3=timeout/unhealthy/peak-touch;
            4=invalidated (e.g. HostConfig.Memory mismatch)
EOF
}

for arg in "$@"; do
  case "${arg}" in
    --timeout=*) TIMEOUT_SEC="${arg#--timeout=}" ;;
    --output=*) OUTPUT_JSON="${arg#--output=}" ;;
    --mem-limit=*) MEM_LIMIT="${arg#--mem-limit=}" ;;
    --run-id=*) RUN_ID="${arg#--run-id=}" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "measure_tei_memory.sh: unknown argument: ${arg}" >&2; usage >&2; exit 1 ;;
  esac
done

if ! tei_probe_set_requested_limit "${MEM_LIMIT}"; then
  usage >&2
  exit 1
fi

TEI_PROBE_TIMEOUT_SEC="${TIMEOUT_SEC}"
if [[ -n "${RUN_ID}" ]]; then
  TEI_PROBE_RUN_ID="${RUN_ID}"
fi

rc=0
tei_probe_run_cpu_validation "${REPO_ROOT}" "${OUTPUT_JSON}" "${MEM_LIMIT}" || rc=$?

if [[ -f "${OUTPUT_JSON}" ]]; then
  python3 - "${OUTPUT_JSON}" <<PY
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    r = json.load(f)
print(
    f"run_id={r.get('run_id')} requested_limit={r.get('requested_limit')} "
    f"container_mem_limit_bytes={r.get('container_mem_limit_bytes')} "
    f"invalidation_reason={r.get('invalidation_reason')}"
)
print(
    f"model={r['model_id']} revision={r['revision']} dtype={r['dtype']} runtime={r['runtime']}"
)
print(
    f"spec_mem_limit_bytes={r['spec_mem_limit_bytes']} "
    f"rss_peak_warmup_bytes={r['rss_peak_warmup_bytes']} "
    f"rss_steady_state_bytes={r.get('rss_steady_state_bytes')} "
    f"runtime_contract_verdict={r.get('runtime_contract_verdict')} "
    f"health_ready={r['health_ready']} oom_killed={r['oom_killed']} "
    f"time_to_ready_sec={r.get('time_to_ready_sec')} "
    f"time_to_failure_sec={r.get('time_to_failure_sec')} "
    f"exit_code={r['exit_code']} "
    f"host_mem_total_bytes={r.get('host_mem_total_bytes')} "
    f"host_mem_available_bytes={r.get('host_mem_available_bytes')}"
)
PY
  exit "${rc}"
else
  echo "measure_tei_memory.sh: probe evidence incomplete (no JSON written)" >&2
  exit 1
fi
