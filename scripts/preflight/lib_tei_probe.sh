#!/usr/bin/env bash
# Shared TEI CPU runtime probe helpers (DEV-003-002 + OI-011).
# Characterization uses explicit multi -f (never compose.sh; never docker update).

TEI_PROBE_SCHEMA_VERSION="1"
# Formal contract (OI-011 MEMORY_LIMIT_DECISION=12g).
TEI_SPEC_MEM_LIMIT="12g"
TEI_SPEC_MEM_LIMIT_BYTES=12884901888
TEI_PROBE_TIMEOUT_SEC=300
TEI_MODEL_ID="BAAI/bge-m3"
TEI_MODEL_REVISION="57aacf8560157b7c1d4f771ce1a199877aeeec74"
TEI_DTYPE="float32"
TEI_RUNTIME="ONNX CPU"

# Active requested limit for the current probe run (may differ during characterization).
TEI_PROBE_REQUESTED_LIMIT="${TEI_SPEC_MEM_LIMIT}"
TEI_PROBE_REQUESTED_LIMIT_BYTES="${TEI_SPEC_MEM_LIMIT_BYTES}"
TEI_PROBE_RUN_ID=""
TEI_PROBE_CLEAN_CREATE="true"
TEI_PROBE_INVALIDATION_REASON=""

tei_probe_repo_root() {
  if [[ -n "${REPO_ROOT:-}" ]]; then
    printf '%s\n' "${REPO_ROOT}"
    return 0
  fi
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  printf '%s\n' "$(cd "${script_dir}/../.." && pwd)"
}

# Map 8g|10g|12g|16g → exact HostConfig.Memory bytes. Exit 1 on illegal value.
tei_probe_mem_limit_to_bytes() {
  local human="$1"
  case "${human}" in
    8g) printf '%s\n' "8589934592" ;;
    10g) printf '%s\n' "10737418240" ;;
    12g) printf '%s\n' "12884901888" ;;
    16g) printf '%s\n' "17179869184" ;;
    *)
      printf 'tei_probe: invalid mem_limit=%s (expected 8g|10g|12g|16g)\n' "${human}" >&2
      return 1
      ;;
  esac
}

# Set TEI_PROBE_REQUESTED_LIMIT / BYTES from human arg. Defaults to formal TEI_SPEC_MEM_LIMIT.
tei_probe_set_requested_limit() {
  local human="${1:-${TEI_SPEC_MEM_LIMIT}}"
  local bytes
  bytes="$(tei_probe_mem_limit_to_bytes "${human}")" || return 1
  TEI_PROBE_REQUESTED_LIMIT="${human}"
  TEI_PROBE_REQUESTED_LIMIT_BYTES="${bytes}"
}

# Overlay path when requested limit differs from formal baked TEI_SPEC_MEM_LIMIT.
# Formal 12g uses base compose.embedding.cpu.yaml only (no overlay).
# mem10g/mem16g remain characterization-only; not loaded by compose.sh.
tei_probe_mem_overlay_path() {
  local repo_root="$1"
  local human="$2"
  if [[ "${human}" == "${TEI_SPEC_MEM_LIMIT}" ]]; then
    printf '\n'
    return 0
  fi
  case "${human}" in
    10g) printf '%s\n' "${repo_root}/compose.embedding.cpu.mem10g.yaml" ;;
    16g) printf '%s\n' "${repo_root}/compose.embedding.cpu.mem16g.yaml" ;;
    8g|12g)
      echo "tei_probe: mem_limit=${human} requires a characterization overlay not shipped for formal ${TEI_SPEC_MEM_LIMIT}; use archived evidence or mem{10,16}g overlays" >&2
      return 1
      ;;
    *)
      return 1
      ;;
  esac
}

# Build docker compose argv for CPU characterization / probe (explicit -f; never compose.sh).
# Populates global array TEI_PROBE_COMPOSE_ARGS.
# Env-file: .env required; versions.env / versions.lock.env / .runtime/embedding.env only if present.
tei_probe_build_compose_args() {
  local repo_root="$1"
  local human="${2:-${TEI_PROBE_REQUESTED_LIMIT}}"
  local overlay=""

  if [[ ! -f "${repo_root}/.env" ]]; then
    echo "tei_probe: .env not found (required; aligned with compose.sh)" >&2
    return 1
  fi

  tei_probe_set_requested_limit "${human}" || return 1
  overlay="$(tei_probe_mem_overlay_path "${repo_root}" "${TEI_PROBE_REQUESTED_LIMIT}")" || return 1

  TEI_PROBE_COMPOSE_ARGS=(
    -f "${repo_root}/compose.yaml"
    -f "${repo_root}/compose.override.yaml"
    -f "${repo_root}/compose.embedding.cpu.yaml"
  )
  if [[ -n "${overlay}" ]]; then
    if [[ ! -f "${overlay}" ]]; then
      echo "tei_probe: missing mem overlay: ${overlay}" >&2
      return 1
    fi
    TEI_PROBE_COMPOSE_ARGS+=(-f "${overlay}")
  fi

  TEI_PROBE_COMPOSE_ARGS+=(--env-file "${repo_root}/.env")
  local ef
  for ef in \
    "${repo_root}/versions.env" \
    "${repo_root}/versions.lock.env" \
    "${repo_root}/.runtime/embedding.env"
  do
    if [[ -f "${ef}" ]]; then
      TEI_PROBE_COMPOSE_ARGS+=(--env-file "${ef}")
    fi
  done
}

tei_probe_compose_cpu() {
  local repo_root="$1"
  local human="$2"
  shift 2
  tei_probe_build_compose_args "${repo_root}" "${human}" || return 1
  tei_probe_with_embedding_env docker compose "${TEI_PROBE_COMPOSE_ARGS[@]}" "$@"
}

tei_probe_load_image_identity() {
  local repo_root="$1"
  local lock_file="${repo_root}/versions.lock.env"
  TEI_PROBE_TEI_IMAGE=""
  TEI_PROBE_IMAGE_DIGEST=""
  if [[ ! -f "${lock_file}" ]]; then
    return 1
  fi
  # shellcheck disable=SC1090
  source "${lock_file}"
  TEI_PROBE_TEI_IMAGE="${TEI_CPU_IMAGE:-}"
  if [[ "${TEI_PROBE_TEI_IMAGE}" =~ @sha256:([a-f0-9]{64})$ ]]; then
    TEI_PROBE_IMAGE_DIGEST="sha256:${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

tei_probe_with_embedding_env() {
  PROXY__HTTP_URL="" \
    EMBEDDING_EFFECTIVE_RUNTIME_MODE="${EMBEDDING_EFFECTIVE_RUNTIME_MODE:-cpu}" \
    EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET="${EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET:-4096}" \
    "$@"
}

tei_probe_find_container() {
  docker ps -a --filter "name=embedding-service" --format '{{.Names}}' 2>/dev/null | head -n 1
}

tei_probe_container_ip() {
  local name="$1"
  docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "${name}" 2>/dev/null
}

tei_probe_parse_mem_bytes() {
  local usage="$1"
  local used_part="${usage%%/*}"
  used_part="${used_part// /}"
  if [[ "${used_part}" =~ ^([0-9.]+)([KMGT]?i?B)$ ]]; then
    local value="${BASH_REMATCH[1]}"
    local unit="${BASH_REMATCH[2]}"
    awk -v v="${value}" -v u="${unit}" '
      BEGIN {
        mult["B"]=1; mult["KiB"]=1024; mult["MiB"]=1024^2; mult["GiB"]=1024^3;
        mult["KB"]=1000; mult["MB"]=1000^2; mult["GB"]=1000^3;
        if (u in mult) printf "%.0f", v * mult[u]; else printf "%.0f", v;
      }'
    return 0
  fi
  printf '0\n'
}

tei_probe_container_state() {
  local name="$1"
  docker inspect -f \
    '{{.State.Status}}|{{.State.OOMKilled}}|{{.State.ExitCode}}|{{.HostConfig.Memory}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
    "${name}" 2>/dev/null
}

tei_probe_health_ready() {
  local container_name="$1"
  local ip
  ip="$(tei_probe_container_ip "${container_name}")"
  if [[ -z "${ip}" ]]; then
    return 1
  fi
  curl -fsS --max-time 5 "http://${ip}/health" >/dev/null 2>&1
}

tei_probe_sample_memory_bytes() {
  local container_name="$1"
  local usage
  usage="$(docker stats --no-stream --format '{{.MemUsage}}' "${container_name}" 2>/dev/null | head -n 1)"
  tei_probe_parse_mem_bytes "${usage}"
}

# Assert HostConfig.Memory equals requested bytes. Prints reason on failure.
tei_probe_assert_hostconfig_memory() {
  local container_name="$1"
  local expected_bytes="$2"
  local actual
  actual="$(docker inspect -f '{{.HostConfig.Memory}}' "${container_name}" 2>/dev/null || true)"
  if [[ -z "${actual}" ]]; then
    echo "HostConfig.Memory inspect failed for ${container_name}"
    return 1
  fi
  if [[ "${actual}" != "${expected_bytes}" ]]; then
    echo "HostConfig.Memory mismatch actual=${actual} expected=${expected_bytes}"
    return 1
  fi
  return 0
}

# Decision helper (OI-011 SF-3): peak>=limit → NON_VIABLE even without explicit OOM.
# Args: peak_bytes limit_bytes health_ready oom_killed exit_code steady_state time_to_ready
# Prints VIABLE or NON_VIABLE.
tei_probe_classify_tier_run() {
  local peak_bytes="$1"
  local limit_bytes="$2"
  local health_ready="$3"
  local oom_killed="$4"
  local exit_code="$5"
  local steady_state="$6"
  local time_to_ready="$7"

  if [[ "${oom_killed}" == "true" ]]; then
    printf 'NON_VIABLE\n'
    return 0
  fi
  if [[ "${health_ready}" != "true" ]]; then
    printf 'NON_VIABLE\n'
    return 0
  fi
  if [[ "${exit_code}" == "137" ]]; then
    printf 'NON_VIABLE\n'
    return 0
  fi
  if [[ -z "${steady_state}" || "${steady_state}" == "null" ]]; then
    printf 'NON_VIABLE\n'
    return 0
  fi
  if [[ -z "${time_to_ready}" || "${time_to_ready}" == "null" ]]; then
    printf 'NON_VIABLE\n'
    return 0
  fi
  if [[ "${time_to_ready}" -gt 300 ]]; then
    printf 'NON_VIABLE\n'
    return 0
  fi
  if [[ "${peak_bytes}" -ge "${limit_bytes}" ]]; then
    printf 'NON_VIABLE\n'
    return 0
  fi
  printf 'VIABLE\n'
}

# Stop via §5.3 helper chain (same -f / env-file). Never compose.sh. Never docker update.
tei_probe_stop_cpu() {
  local repo_root="$1"
  local human="${2:-${TEI_PROBE_REQUESTED_LIMIT:-${TEI_SPEC_MEM_LIMIT}}}"
  if [[ -n "${TEI_PROBE_MOCK_STATE:-}" ]]; then
    return 0
  fi
  tei_probe_compose_cpu "${repo_root}" "${human}" down embedding-service 2>/dev/null || true
  local name
  while IFS= read -r name; do
    [[ -n "${name}" ]] && docker rm -f "${name}" 2>/dev/null || true
  done < <(docker ps -a --filter "name=embedding-service" --format '{{.Names}}' 2>/dev/null)
}

# Start via §5.3 helper: up -d --force-recreate. Never compose.sh. Never docker update.
tei_probe_start_cpu() {
  local repo_root="$1"
  local human="${2:-${TEI_PROBE_REQUESTED_LIMIT:-${TEI_SPEC_MEM_LIMIT}}}"
  if [[ -n "${TEI_PROBE_MOCK_STATE:-}" ]]; then
    return 0
  fi
  tei_probe_compose_cpu "${repo_root}" "${human}" up -d --force-recreate embedding-service
}

tei_probe_write_report_json() {
  local output_json="$1"
  local peak_bytes="$2"
  local steady_state="$3"
  local time_to_ready="$4"
  local time_to_failure="$5"
  local health_ready="$6"
  local oom_killed="$7"
  local exit_code="$8"
  local timed_out="$9"
  local container_name="${10}"
  local final_status="${11}"
  local final_health="${12}"
  local mem_limit_raw="${13}"
  local tei_image="${14}"
  local image_digest="${15}"
  local probe_timeout_sec="${16}"
  local requested_limit="${17:-${TEI_PROBE_REQUESTED_LIMIT}}"
  local requested_limit_bytes="${18:-${TEI_PROBE_REQUESTED_LIMIT_BYTES}}"
  local run_id="${19:-${TEI_PROBE_RUN_ID}}"
  local clean_create="${20:-${TEI_PROBE_CLEAN_CREATE}}"
  local invalidation_reason="${21:-${TEI_PROBE_INVALIDATION_REASON}}"

  local host_mem_total host_mem_avail
  host_mem_total="$(awk '/^MemTotal:/ { printf "%.0f", $2 * 1024 }' /proc/meminfo)"
  host_mem_avail="$(awk '/^MemAvailable:/ { printf "%.0f", $2 * 1024 }' /proc/meminfo)"

  mkdir -p "$(dirname "${output_json}")"
  python3 - "${output_json}" \
    "${TEI_PROBE_SCHEMA_VERSION}" \
    "${TEI_MODEL_ID}" "${TEI_MODEL_REVISION}" "${TEI_DTYPE}" "${TEI_RUNTIME}" \
    "${tei_image}" "${image_digest}" \
    "${TEI_SPEC_MEM_LIMIT_BYTES}" "${mem_limit_raw}" "${peak_bytes}" "${steady_state}" \
    "${time_to_ready}" "${time_to_failure}" \
    "${health_ready}" "${oom_killed}" "${exit_code}" "${timed_out}" \
    "${container_name}" "${final_status}" "${final_health}" \
    "${host_mem_total}" "${host_mem_avail}" "${probe_timeout_sec}" \
    "${requested_limit}" "${requested_limit_bytes}" "${run_id}" \
    "${clean_create}" "${invalidation_reason}" <<'PYEOF'
import json
import sys
from datetime import datetime, timezone

(
    output_json,
    schema_version,
    model_id,
    revision,
    dtype,
    runtime,
    tei_image,
    image_digest,
    spec_mem_limit,
    mem_limit_raw,
    peak_bytes,
    steady_raw,
    time_to_ready_raw,
    time_to_failure_raw,
    health_ready,
    oom_killed,
    exit_code,
    timed_out,
    container_name,
    final_status,
    final_health,
    host_mem_total,
    host_mem_avail,
    probe_timeout_sec,
    requested_limit,
    requested_limit_bytes,
    run_id,
    clean_create,
    invalidation_reason,
) = sys.argv[1:]

def as_bool(value: str) -> bool:
    return value == "true"

health = as_bool(health_ready)
oom = as_bool(oom_killed)
timeout = as_bool(timed_out)
exit_i = int(exit_code)
clean = as_bool(clean_create)

steady_val = int(steady_raw) if steady_raw else None
time_to_ready = int(time_to_ready_raw) if time_to_ready_raw else None
time_to_failure = int(time_to_failure_raw) if time_to_failure_raw else None
inv = invalidation_reason if invalidation_reason else None
req_bytes = int(requested_limit_bytes) if requested_limit_bytes else None
container_limit = int(mem_limit_raw) if mem_limit_raw else None
peak_i = int(peak_bytes) if peak_bytes else 0

if inv:
    verdict = "PROBE_EVIDENCE_INCOMPLETE"
elif not container_name:
    verdict = "PROBE_EVIDENCE_INCOMPLETE"
elif oom or exit_i == 137:
    verdict = "SPEC_RUNTIME_CONTRACT_CONFLICT"
    steady_val = None
    time_to_ready = None
elif container_limit is not None and peak_i >= container_limit:
    # Round 2 SF-3: peak at/over cgroup limit → conflict / non-viable input
    verdict = "SPEC_RUNTIME_CONTRACT_CONFLICT"
    if not health:
        steady_val = None
        time_to_ready = None
elif health:
    verdict = "PASS"
    time_to_failure = None
else:
    verdict = "SPEC_RUNTIME_CONTRACT_CONFLICT"
    steady_val = None
    time_to_ready = None
    if time_to_failure is None and time_to_ready_raw:
        time_to_failure = int(time_to_ready_raw)

report = {
    "schema_version": schema_version,
    "recorded_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "run_id": run_id or None,
    "model_id": model_id,
    "revision": revision,
    "dtype": dtype,
    "runtime": runtime,
    "tei_image": tei_image or None,
    "image_digest": image_digest or None,
    "spec_mem_limit_bytes": int(spec_mem_limit),
    "mem_limit_human": requested_limit,
    "requested_limit": requested_limit,
    "requested_mem_limit_bytes": req_bytes,
    "container_mem_limit_bytes": container_limit,
    "rss_peak_warmup_bytes": peak_i,
    "rss_steady_state_bytes": steady_val,
    "health_ready": health,
    "runtime_contract_verdict": verdict,
    "time_to_ready_sec": time_to_ready,
    "time_to_failure_sec": time_to_failure,
    "oom_killed": oom,
    "exit_code": exit_i,
    "timed_out": timeout,
    "probe_timeout_sec": int(probe_timeout_sec),
    "container_name": container_name,
    "container_status": final_status,
    "container_health": final_health,
    "host_mem_total_bytes": int(host_mem_total),
    "host_mem_available_bytes": int(host_mem_avail),
    "clean_create": clean,
    "invalidation_reason": inv,
}
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
    f.write("\n")
PYEOF
}

# Validate report JSON against Amendment 001 schema (exit 0=ok, 1=incomplete).
# New OI-011 audit fields are optional for historical fixtures.
tei_probe_validate_report_schema() {
  local report_json="$1"
  python3 - "${report_json}" <<'PYEOF'
import json
import sys

path = sys.argv[1]
required = {
    "schema_version", "recorded_at_utc", "model_id", "revision", "dtype", "runtime",
    "tei_image", "image_digest", "spec_mem_limit_bytes", "container_mem_limit_bytes",
    "rss_peak_warmup_bytes", "rss_steady_state_bytes", "health_ready",
    "runtime_contract_verdict", "time_to_ready_sec", "time_to_failure_sec",
    "oom_killed", "exit_code", "timed_out", "host_mem_total_bytes",
    "host_mem_available_bytes", "probe_timeout_sec",
}
with open(path, encoding="utf-8") as f:
    report = json.load(f)
missing = sorted(required - set(report))
if missing:
    print("missing fields:", ", ".join(missing))
    sys.exit(1)
if report.get("oom_killed") and report.get("rss_steady_state_bytes") is not None:
    print("OOM report must not set rss_steady_state_bytes")
    sys.exit(1)
if report.get("health_ready") and report.get("time_to_ready_sec") is None:
    print("healthy report requires time_to_ready_sec")
    sys.exit(1)
if not report.get("health_ready") and report.get("time_to_ready_sec") is not None:
    print("unhealthy report requires time_to_ready_sec=null")
    sys.exit(1)
verdict = report.get("runtime_contract_verdict")
if verdict not in {"PASS", "SPEC_RUNTIME_CONTRACT_CONFLICT", "PROBE_EVIDENCE_INCOMPLETE"}:
    print(f"invalid runtime_contract_verdict: {verdict}")
    sys.exit(1)
sys.exit(0)
PYEOF
}

# Test-only mock paths (Layer A). TEI_PROBE_MOCK_STATE: pass|oom|timeout|exited|incomplete|mem_mismatch
tei_probe_run_cpu_validation_mock() {
  local repo_root="$1"
  local output_json="${2:-}"
  local mock="${TEI_PROBE_MOCK_STATE}"
  local peak_bytes=7000000000 steady_state="" time_to_ready="" time_to_failure="42"
  local health_ready=false oom_killed=false exit_code=0 timed_out=false
  local container_name="embedding-service-mock" final_status="running" final_health="starting"
  local mem_limit_raw="${TEI_PROBE_REQUESTED_LIMIT_BYTES}"
  local invalidation_reason=""

  tei_probe_load_image_identity "${repo_root}" || true
  if [[ -z "${TEI_PROBE_RUN_ID}" ]]; then
    TEI_PROBE_RUN_ID="mock-${TEI_PROBE_REQUESTED_LIMIT}-${mock}"
  fi

  case "${mock}" in
    pass)
      health_ready=true
      steady_state=3000000000
      time_to_ready=30
      time_to_failure=""
      peak_bytes=6000000000
      final_health="healthy"
      ;;
    oom)
      oom_killed=true
      exit_code=137
      peak_bytes="${TEI_PROBE_REQUESTED_LIMIT_BYTES}"
      time_to_failure=138
      final_status="running"
      ;;
    timeout)
      timed_out=true
      exit_code=124
      time_to_failure=300
      peak_bytes=5000000000
      ;;
    exited)
      exit_code=1
      final_status="exited"
      time_to_failure=10
      ;;
    mem_mismatch)
      mem_limit_raw="1"
      invalidation_reason="HostConfig.Memory mismatch"
      TEI_PROBE_INVALIDATION_REASON="${invalidation_reason}"
      TEI_PROBE_CLEAN_CREATE="true"
      ;;
    peak_touch)
      # SF-3: peak >= limit → NON_VIABLE classification input
      health_ready=true
      steady_state=3000000000
      time_to_ready=40
      time_to_failure=""
      peak_bytes="${TEI_PROBE_REQUESTED_LIMIT_BYTES}"
      final_health="healthy"
      ;;
    incomplete)
      if [[ -n "${output_json}" ]]; then
        rm -f "${output_json}"
      fi
      return 1
      ;;
    *)
      return 1
      ;;
  esac

  if [[ "${mock}" != "incomplete" && -n "${output_json}" ]]; then
    tei_probe_write_report_json \
      "${output_json}" "${peak_bytes}" "${steady_state}" "${time_to_ready}" \
      "${time_to_failure}" "${health_ready}" "${oom_killed}" "${exit_code}" "${timed_out}" \
      "${container_name}" "${final_status}" "${final_health}" "${mem_limit_raw}" \
      "${TEI_PROBE_TEI_IMAGE:-}" "${TEI_PROBE_IMAGE_DIGEST:-}" "${TEI_PROBE_TIMEOUT_SEC}" \
      "${TEI_PROBE_REQUESTED_LIMIT}" "${TEI_PROBE_REQUESTED_LIMIT_BYTES}" \
      "${TEI_PROBE_RUN_ID}" "${TEI_PROBE_CLEAN_CREATE}" "${invalidation_reason}"
  fi

  if [[ "${mock}" == "mem_mismatch" ]]; then
    return 4
  fi
  if [[ "${oom_killed}" == "true" ]]; then
    return 2
  fi
  if [[ "${mock}" == "exited" ]]; then
    return 1
  fi
  if [[ "${mock}" == "peak_touch" ]]; then
    return 3
  fi
  if [[ "${timed_out}" == "true" || "${health_ready}" == "false" ]]; then
    return 3
  fi
  return 0
}

# Run CPU TEI validation under requested mem_limit (default formal TEI_SPEC_MEM_LIMIT).
# Args: repo_root [output_json_path] [mem_limit_human]
# Exit: 0 success; 2 OOM; 3 timeout/unhealthy/peak-touch; 4 invalid (Memory mismatch);
#       1 other failure
tei_probe_run_cpu_validation() {
  local repo_root="$1"
  local output_json="${2:-}"
  local mem_limit_human="${3:-${TEI_SPEC_MEM_LIMIT}}"
  local timeout_sec="${TEI_PROBE_TIMEOUT_SEC}"

  tei_probe_set_requested_limit "${mem_limit_human}" || return 1
  TEI_PROBE_CLEAN_CREATE="true"
  TEI_PROBE_INVALIDATION_REASON=""
  if [[ -z "${TEI_PROBE_RUN_ID}" ]]; then
    TEI_PROBE_RUN_ID="tei-${TEI_PROBE_REQUESTED_LIMIT}-$(date -u +%Y%m%dT%H%M%SZ)"
  fi

  if [[ -n "${TEI_PROBE_MOCK_STATE:-}" ]]; then
    tei_probe_run_cpu_validation_mock "${repo_root}" "${output_json}"
    return $?
  fi

  if ! tei_probe_load_image_identity "${repo_root}"; then
    return 1
  fi

  local started_at peak_bytes=0 steady_sum=0 steady_count=0
  local health_ready=false oom_killed=false exit_code=0 timed_out=false
  local container_name="" final_status="unknown" final_health="none" mem_limit_raw=""

  started_at="$(date +%s)"
  tei_probe_stop_cpu "${repo_root}" "${TEI_PROBE_REQUESTED_LIMIT}"

  if ! tei_probe_start_cpu "${repo_root}" "${TEI_PROBE_REQUESTED_LIMIT}"; then
    TEI_PROBE_INVALIDATION_REASON="compose up failed before probe"
    TEI_PROBE_CLEAN_CREATE="false"
    if [[ -n "${output_json}" ]]; then
      tei_probe_write_report_json \
        "${output_json}" "0" "" "" "" \
        "false" "false" "1" "false" \
        "" "unknown" "none" "" \
        "${TEI_PROBE_TEI_IMAGE:-}" "${TEI_PROBE_IMAGE_DIGEST:-}" "${timeout_sec}"
    fi
    return 1
  fi

  # Wait briefly for container to appear, then assert HostConfig.Memory.
  local appear_deadline=$((started_at + 60))
  while [[ "$(date +%s)" -lt "${appear_deadline}" ]]; do
    container_name="$(tei_probe_find_container)"
    if [[ -n "${container_name}" ]]; then
      break
    fi
    sleep 1
  done

  if [[ -z "${container_name}" ]]; then
    TEI_PROBE_INVALIDATION_REASON="compose up failed before probe"
    if [[ -n "${output_json}" ]]; then
      tei_probe_write_report_json \
        "${output_json}" "0" "" "" "" \
        "false" "false" "1" "false" \
        "" "unknown" "none" "" \
        "${TEI_PROBE_TEI_IMAGE:-}" "${TEI_PROBE_IMAGE_DIGEST:-}" "${timeout_sec}"
    fi
    tei_probe_stop_cpu "${repo_root}" "${TEI_PROBE_REQUESTED_LIMIT}"
    return 1
  fi

  local mem_assert_msg=""
  if ! mem_assert_msg="$(tei_probe_assert_hostconfig_memory "${container_name}" "${TEI_PROBE_REQUESTED_LIMIT_BYTES}")"; then
    TEI_PROBE_INVALIDATION_REASON="${mem_assert_msg:-HostConfig.Memory mismatch}"
    local state_line
    state_line="$(tei_probe_container_state "${container_name}")"
    IFS='|' read -r final_status oom_raw exit_code mem_limit_raw final_health <<<"${state_line}"
    if [[ -n "${output_json}" ]]; then
      tei_probe_write_report_json \
        "${output_json}" "0" "" "" "" \
        "false" "false" "${exit_code:-1}" "false" \
        "${container_name}" "${final_status}" "${final_health}" "${mem_limit_raw}" \
        "${TEI_PROBE_TEI_IMAGE:-}" "${TEI_PROBE_IMAGE_DIGEST:-}" "${timeout_sec}"
    fi
    tei_probe_stop_cpu "${repo_root}" "${TEI_PROBE_REQUESTED_LIMIT}"
    return 4
  fi

  local deadline=$((started_at + timeout_sec))
  local health_at=0

  while [[ "$(date +%s)" -lt "${deadline}" ]]; do
    container_name="$(tei_probe_find_container)"
    if [[ -z "${container_name}" ]]; then
      sleep 1
      continue
    fi

    local state_line
    state_line="$(tei_probe_container_state "${container_name}")"
    IFS='|' read -r final_status oom_raw exit_code mem_limit_raw final_health <<<"${state_line}"

    if [[ "${oom_raw}" == "true" ]]; then
      oom_killed=true
      exit_code=137
      break
    fi

    if [[ "${final_status}" == "exited" ]]; then
      [[ "${exit_code}" == "137" ]] && oom_killed=true
      break
    fi

    local sample
    sample="$(tei_probe_sample_memory_bytes "${container_name}")"
    if [[ "${sample}" -gt "${peak_bytes}" ]]; then
      peak_bytes="${sample}"
    fi

    if tei_probe_health_ready "${container_name}"; then
      if [[ "${health_ready}" == "false" ]]; then
        health_ready=true
        health_at="$(date +%s)"
      fi
      if [[ "${steady_count}" -lt 3 ]]; then
        steady_sum=$((steady_sum + sample))
        steady_count=$((steady_count + 1))
        sleep 5
        continue
      fi
      break
    fi

    sleep 1
  done

  if [[ "${health_ready}" == "false" && "${oom_killed}" == "false" ]]; then
    timed_out=true
    exit_code=124
  fi

  local time_to_ready="" time_to_failure=""
  local elapsed=$(( $(date +%s) - started_at ))
  if [[ "${health_ready}" == "true" && "${health_at}" -gt 0 ]]; then
    time_to_ready=$((health_at - started_at))
  else
    time_to_failure="${elapsed}"
  fi

  local steady_state=""
  if [[ "${health_ready}" == "true" && "${steady_count}" -gt 0 ]]; then
    steady_state=$((steady_sum / steady_count))
  fi

  if [[ -n "${output_json}" ]]; then
    tei_probe_write_report_json \
      "${output_json}" "${peak_bytes}" "${steady_state}" "${time_to_ready}" \
      "${time_to_failure}" "${health_ready}" "${oom_killed}" "${exit_code}" "${timed_out}" \
      "${container_name}" "${final_status}" "${final_health}" "${mem_limit_raw}" \
      "${TEI_PROBE_TEI_IMAGE:-}" "${TEI_PROBE_IMAGE_DIGEST:-}" "${timeout_sec}"
  fi

  tei_probe_stop_cpu "${repo_root}" "${TEI_PROBE_REQUESTED_LIMIT}"

  if [[ "${oom_killed}" == "true" ]]; then
    return 2
  fi
  if [[ "${timed_out}" == "true" || "${health_ready}" == "false" ]]; then
    return 3
  fi
  if [[ "${peak_bytes}" -ge "${TEI_PROBE_REQUESTED_LIMIT_BYTES}" ]]; then
    return 3
  fi
  if [[ "${mem_limit_raw}" != "${TEI_PROBE_REQUESTED_LIMIT_BYTES}" ]]; then
    return 4
  fi
  return 0
}

tei_probe_wait_for_cpu_ready() {
  local repo_root="$1"
  local timeout_sec="${2:-${TEI_PROBE_TIMEOUT_SEC}}"
  local container_name=""
  local started_at
  started_at="$(date +%s)"
  local deadline=$((started_at + timeout_sec))

  while [[ "$(date +%s)" -lt "${deadline}" ]]; do
    container_name="$(tei_probe_find_container)"
    if [[ -z "${container_name}" ]]; then
      sleep 2
      continue
    fi

    local state_line status oom_raw exit_code mem_limit_raw health
    state_line="$(tei_probe_container_state "${container_name}")"
    IFS='|' read -r status oom_raw exit_code mem_limit_raw health <<<"${state_line}"

    if [[ "${oom_raw}" == "true" || "${exit_code}" == "137" ]]; then
      printf 'OOMKilled container=%s exit=%s mem_limit=%s\n' "${container_name}" "${exit_code}" "${mem_limit_raw}" >&2
      return 2
    fi
    if [[ "${status}" == "exited" ]]; then
      printf 'container exited name=%s exit=%s\n' "${container_name}" "${exit_code}" >&2
      return 1
    fi
    if tei_probe_health_ready "${container_name}"; then
      if [[ "${mem_limit_raw}" != "${TEI_SPEC_MEM_LIMIT_BYTES}" ]]; then
        printf 'unexpected mem_limit=%s expected=%s\n' "${mem_limit_raw}" "${TEI_SPEC_MEM_LIMIT_BYTES}" >&2
        return 1
      fi
      return 0
    fi
    sleep 2
  done
  printf 'health timeout after %ss\n' "${timeout_sec}" >&2
  return 3
}
