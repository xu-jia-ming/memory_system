#!/usr/bin/env bash
# Shared TEI CPU 8g runtime probe helpers (DEV-003-002).
# Source from preflight, start_embedding, and diagnostics scripts.

TEI_PROBE_SCHEMA_VERSION="1"
TEI_SPEC_MEM_LIMIT_BYTES=8589934592
TEI_PROBE_TIMEOUT_SEC=300
TEI_MODEL_ID="BAAI/bge-m3"
TEI_MODEL_REVISION="57aacf8560157b7c1d4f771ce1a199877aeeec74"
TEI_DTYPE="float32"
TEI_RUNTIME="ONNX CPU"

tei_probe_repo_root() {
  if [[ -n "${REPO_ROOT:-}" ]]; then
    printf '%s\n' "${REPO_ROOT}"
    return 0
  fi
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  printf '%s\n' "$(cd "${script_dir}/../.." && pwd)"
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

tei_probe_stop_cpu() {
  local repo_root="$1"
  if [[ -n "${TEI_PROBE_MOCK_STATE:-}" ]]; then
    return 0
  fi
  tei_probe_with_embedding_env "${repo_root}/scripts/compose.sh" --embedding=cpu down embedding-service 2>/dev/null || true
  local name
  while IFS= read -r name; do
    [[ -n "${name}" ]] && docker rm -f "${name}" 2>/dev/null || true
  done < <(docker ps -a --filter "name=embedding-service" --format '{{.Names}}' 2>/dev/null)
}

tei_probe_start_cpu() {
  local repo_root="$1"
  if [[ -n "${TEI_PROBE_MOCK_STATE:-}" ]]; then
    return 0
  fi
  tei_probe_with_embedding_env "${repo_root}/scripts/compose.sh" --embedding=cpu up -d embedding-service
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
    "${host_mem_total}" "${host_mem_avail}" "${probe_timeout_sec}" <<'PYEOF'
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
) = sys.argv[1:]

def as_bool(value: str) -> bool:
    return value == "true"

health = as_bool(health_ready)
oom = as_bool(oom_killed)
timeout = as_bool(timed_out)
exit_i = int(exit_code)

steady_val = int(steady_raw) if steady_raw else None
time_to_ready = int(time_to_ready_raw) if time_to_ready_raw else None
time_to_failure = int(time_to_failure_raw) if time_to_failure_raw else None

if not container_name:
    verdict = "PROBE_EVIDENCE_INCOMPLETE"
elif oom or exit_i == 137:
    verdict = "SPEC_RUNTIME_CONTRACT_CONFLICT"
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
    "model_id": model_id,
    "revision": revision,
    "dtype": dtype,
    "runtime": runtime,
    "tei_image": tei_image or None,
    "image_digest": image_digest or None,
    "spec_mem_limit_bytes": int(spec_mem_limit),
    "mem_limit_human": "8g",
    "container_mem_limit_bytes": int(mem_limit_raw) if mem_limit_raw else None,
    "rss_peak_warmup_bytes": int(peak_bytes),
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
}
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
    f.write("\n")
PYEOF
}

# Validate report JSON against Amendment 001 schema (exit 0=ok, 1=incomplete).
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

# Test-only mock paths (Layer A). TEI_PROBE_MOCK_STATE: pass|oom|timeout|exited|incomplete
tei_probe_run_cpu_validation_mock() {
  local repo_root="$1"
  local output_json="${2:-}"
  local mock="${TEI_PROBE_MOCK_STATE}"
  local peak_bytes=7000000000 steady_state="" time_to_ready="" time_to_failure="42"
  local health_ready=false oom_killed=false exit_code=0 timed_out=false
  local container_name="embedding-service-mock" final_status="running" final_health="starting"
  local mem_limit_raw="${TEI_SPEC_MEM_LIMIT_BYTES}"

  tei_probe_load_image_identity "${repo_root}" || true

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
      peak_bytes="${TEI_SPEC_MEM_LIMIT_BYTES}"
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
      "${TEI_PROBE_TEI_IMAGE:-}" "${TEI_PROBE_IMAGE_DIGEST:-}" "${TEI_PROBE_TIMEOUT_SEC}"
  fi

  if [[ "${oom_killed}" == "true" ]]; then
    return 2
  fi
  if [[ "${mock}" == "exited" ]]; then
    return 1
  fi
  if [[ "${timed_out}" == "true" || "${health_ready}" == "false" ]]; then
    return 3
  fi
  return 0
}

# Run CPU TEI validation under spec 8g mem_limit.
# Args: repo_root [output_json_path]
# Exit: 0 success; 2 OOM; 3 timeout/unhealthy; 1 other failure
tei_probe_run_cpu_validation() {
  local repo_root="$1"
  local output_json="${2:-}"
  local timeout_sec="${TEI_PROBE_TIMEOUT_SEC}"

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
  tei_probe_stop_cpu "${repo_root}"

  if ! tei_probe_start_cpu "${repo_root}"; then
    return 1
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

  tei_probe_stop_cpu "${repo_root}"

  if [[ "${oom_killed}" == "true" ]]; then
    return 2
  fi
  if [[ "${timed_out}" == "true" || "${health_ready}" == "false" ]]; then
    return 3
  fi
  if [[ "${mem_limit_raw}" != "${TEI_SPEC_MEM_LIMIT_BYTES}" ]]; then
    return 1
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
