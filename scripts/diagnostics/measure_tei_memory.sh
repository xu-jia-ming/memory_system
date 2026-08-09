#!/usr/bin/env bash
# Measure TEI CPU warm-up peak and steady-state RSS under spec 8g mem_limit (DEV-003-002).
#
# Usage: ./scripts/diagnostics/measure_tei_memory.sh [--timeout=300] [--output=PATH]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/preflight/lib_tei_probe.sh"

TIMEOUT_SEC="${TEI_PROBE_TIMEOUT_SEC}"
OUTPUT_JSON="${REPO_ROOT}/.runtime/tei_memory_report.json"

usage() {
  cat <<'EOF'
Usage: ./scripts/diagnostics/measure_tei_memory.sh [--timeout=SECONDS] [--output=PATH]

Runs spec-compliant CPU TEI (mem_limit=8g) and writes JSON memory evidence.
Exit codes: 0=success; 1=compose/other; 2=OOM; 3=timeout/unhealthy
EOF
}

for arg in "$@"; do
  case "${arg}" in
    --timeout=*) TIMEOUT_SEC="${arg#--timeout=}" ;;
    --output=*) OUTPUT_JSON="${arg#--output=}" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "measure_tei_memory.sh: unknown argument: ${arg}" >&2; usage >&2; exit 1 ;;
  esac
done

TEI_PROBE_TIMEOUT_SEC="${TIMEOUT_SEC}"
rc=0
tei_probe_run_cpu_validation "${REPO_ROOT}" "${OUTPUT_JSON}" || rc=$?

if [[ -f "${OUTPUT_JSON}" ]]; then
  python3 - "${OUTPUT_JSON}" <<PY
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    r = json.load(f)
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
    f"exit_code={r['exit_code']}"
)
PY
  exit "${rc}"
else
  echo "measure_tei_memory.sh: probe evidence incomplete (no JSON written)" >&2
  exit 1
fi
