# DEV-003-002 TEI CPU Memory Contract Validation（Preflight Hardening）

## 1. 任务信息

```yaml
task_id: DEV-003-002
task_name: TEI CPU Memory Contract Validation（Preflight Hardening）
status: approved
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§3.10.3 CPU 默认模式（mem_limit: 8g；float32；bge-m3）"
  - "§3.10.8 Embedding Health Check / Readiness 诊断"
  - "§3.10.9 TEI 镜像 Digest 锁定"
  - "§3.18 Preflight（尤其 #12 Docker 8g TEI mem_limit；#13 lock/budget）"
prerequisites:
  - "DEV-003 completed（Compose、start_embedding.sh、preflight、lock_tei_images.sh）"
  - "versions.lock.env 含有效 TEI CPU @sha256 Digest"
  - "embedding-model-cache Volume 已缓存 BAAI/bge-m3 rev 57aacf...（避免 HF 下载干扰内存测量）"
insertion_reason: "DEV-006 §8.8 Integration 发布阻塞：spec-compliant CPU TEI（mem_limit=8g）warm-up OOMKilled exit=137"
blocks:
  - "DEV-003-002 completion 仅满足 DEV-006 R1（tooling merged）"
  - "DEV-006 R2–R4 仍由后续 Spec-OI / 新 runtime contract validation 阻塞"
  - "DEV-006 PR #13 NOT_READY_FOR_PR_MERGE"
branch: "feat/DEV-003-002-tei-cpu-memory-contract-validation"
created_at: "2026-08-08 14:52 UTC"
updated_at: "2026-08-09 01:02 UTC"
completion_model: MODEL_2
tooling_status: pending_validation
runtime_contract_status: SPEC_RUNTIME_CONTRACT_CONFLICT
dev006_dependency_status: BLOCKED
```

## 2. 任务目标

> **Amendment 001（MODEL 2）**：本任务交付 **runtime contract validation tooling** 与可审计 conflict evidence；**不要求**当前 spec 8g CPU TEI runtime 必须 PASS。见 §12 Amendment 001。

闭合 **DEV-003 P2-001 Verdict A** 暴露的残余风险：Preflight Check 13 仅以宿主机 `MemTotal ≥ 10 GiB` 代理 §3.18 #12，**未验证** TEI 在 `mem_limit: 8g` 下 warm-up 峰值 RSS 与 healthy 可达性。本任务通过 **真实 runtime probe + fail-closed 报告** 闭合该验证缺口；若 probe 准确检出 conflict，则 tooling 目标达成，**runtime contract 状态另记为 CONFLICT**。

完成后应具备：

1. **可复现的内存证据采集**：区分 warm-up 峰值 RSS 与 steady-state RSS；记录 OOMKilled、time-to-ready/time-to-failure、TEI image digest、模型 Revision、dtype、runtime；输出机器可读报告（JSON + 人类摘要）；OOM 时 `rss_steady_state_bytes=null`。
2. **Preflight 硬化**：在 `resolved_mode=cpu`（含 `auto→cpu`）路径上，以 **spec-compliant** `compose.embedding.cpu.yaml`（`mem_limit: 8g` 不变）执行 TEI 启动探针；OOM 或 300s 内未 healthy → **硬失败**并输出诊断（**operational fail-closed 保持不变**）。
3. **`start_embedding.sh` OOM 可观测性**：CPU 路径启动后检测容器 `OOMKilled` / exit 137；失败时清理并给出明确错误（禁止静默重试或掩盖）。
4. **分层测试**：A) tooling correctness（mock/受控，验证 PASS/OOM/timeout/malformed evidence 分类）；B) reference runtime contract gate（真实 8g probe，**独立执行**，结果可为 PASS 或 `SPEC_RUNTIME_CONTRACT_CONFLICT`，**不得**进入默认 CI 红灯）。
5. **状态语义清晰**：`TOOLING_STATUS=VALID` 与 `RUNTIME_CONTRACT_STATUS=CONFLICT` 可并存；DEV-006 恢复依赖 **后续 Spec-OI 新 contract**（见 §15 Amendment 001）。

**规格边界**：本任务 **不得** 将 `compose.embedding.cpu.yaml` 的 `mem_limit` 改为 `16g` 或任何非 `8g` 值，不得执行 Spec-OI characterization matrix；memory limit 决策 = `MEMORY_LIMIT_DECISION_NOT_YET_SUPPORTED`。

## 3. 非目标

- 修改 `src/memory_system/**`（含 `TEIEmbeddingClient`、DEV-006 业务代码）。
- 触碰 `feat/DEV-006-tei-embedding-client-token-budget` 分支或 PR #13 实现 Commit。
- 修改 TEI 镜像版本、模型 ID/Revision、`versions.env` / `versions.lock.env` Digest（只读使用）。
- 修改 GPU Override `mem_limit` 或 GPU 探针语义（本任务聚焦 **CPU** 发布阻塞路径）。
- 将 `16g` 实验性 `docker update` 结果作为 release evidence 或默认配置。
- 修改规格正文、错误码、API Contract。
- STM/EXT/RET 业务任务。
- 五命令、Orchestrator、permissions 变更。
- 完整 DEV-006 Integration 测试套件（留给 DEV-006 恢复后执行）。

## 4. 当前代码状态

### 4.1 已存在代码

- **`compose.embedding.cpu.yaml`**：`mem_limit: 8g`；`float32`；`AUTO_TRUNCATE=false`；healthcheck `start_period: 120s`（与 §3.10.3 一致）。
- **`scripts/preflight/check_linux_host.sh`**：Check 13 为 `MemTotal ≥ 10 GiB`（DEV-003 P2-001 Verdict A）；Check 8 校验 `MemAvailable`（cpu 12/16 GiB）；**无** TEI 运行时探针。
- **`scripts/start_embedding.sh`**：写入 `.runtime/embedding.env` 并 `compose.sh up -d embedding-service`；**无** OOM/health 等待与失败诊断。
- **契约/集成测试**：`test_compose_config_contract.py` 断言 CPU embedding 服务存在；`test_preflight_linux_host.py` 仅验证 preflight 退出码，不验证 TEI 内存。

### 4.2 权威故障证据（用户/Orchestrator 提供）

| 项 | 值 |
|---|---|
| 配置 | spec-compliant CPU TEI；bge-m3 rev `57aacf...`；float32 ONNX |
| Compose mem_limit | `8g`（8589934592） |
| 模型缓存 | hit（HF/Mihomo 已排除） |
| 现象 | 日志进入 `Warming up model` → `OOMKilled=true` exit=137 |
| Health | 300s 内未 ready |
| 对照实验 | `docker update --memory=16g` 可启动 — **未授权**，非 release evidence |
| Preflight | Check 13 通过（MemTotal 代理）；**未**覆盖 warm-up 峰值 |

### 4.3 当前缺失

- TEI warm-up / steady-state 内存采样脚本与报告格式。
- Preflight TEI CPU 8g 运行时探针（§3.18 #12 字面闭合）。
- `start_embedding.sh` OOM 检测与 fail-closed 错误消息。
- 针对上述行为的 Unit/Contract/Integration 测试。

### 4.4 与技术规格不一致之处

- §3.18 #12 要求 Preflight 确认 Docker **能为 TEI 提供 8g mem_limit** — 当前 Check 13 仅验证宿主机总内存，**不等价**于 TEI 在 8g cgroup 内可完成 warm-up。
- §3.10.3 规定 CPU `mem_limit: 8g` — 若实测 warm-up 峰值持续 >8g，则存在 **规格↔运行时事实冲突**（须 Spec-OI，本任务只采集证据并 fail-closed，不自行改 Contract）。

### 4.5 前置任务检查

| 前置 | 状态 | 证据 |
|---|---|---|
| DEV-003 | completed | PR #6 merged `0ac80e5` |
| DEV-006 | PAUSED | PR #13 NOT_READY_FOR_PR_MERGE；Amendment 002 已单独备份 |
| Git | `main` 干净 | `2557ef4` docs(plan) DEV-006 |

## 5. 实现方案

### Step 1 — 内存证据采集脚本 `scripts/diagnostics/measure_tei_memory.sh`

- **文件**：`scripts/diagnostics/measure_tei_memory.sh`（新建）；`scripts/diagnostics/.gitkeep` 若目录不存在。
- **输入**：`--mode=cpu`（本任务仅 CPU）；可选 `--timeout=300`；`--output=.runtime/tei_memory_report.json`。
- **行为**：
  1. 校验 `versions.lock.env`、`.runtime/embedding.env`（若无则写入 `cpu/4096` 与 preflight 一致）。
  2. 经 `compose.sh --embedding=cpu` **仅**启动 `embedding-service`（禁止改 mem_limit）。
  3. 自容器 create 起每 **1s** 采样直至 healthy 或 timeout：
     - `docker stats --no-stream` 的内存用量（解析 peak）。
     - `docker inspect` → `State.OOMKilled`、`State.ExitCode`、`State.Status`。
     - 可选：`curl -fsS http://localhost:<mapped>/health`（若端口未映射则走 `docker exec` curl）。
  4. 阶段标记：
     - **warm-up**：首次采样 → 首次 health 200 或 OOM/exit。
     - **steady-state**：health 200 后连续 3 次采样（间隔 5s）均值。
  5. 输出 JSON（字段见 **§7.1 JSON evidence schema**）+ stdout 人类摘要行。
  6. `trap` 清理：探针结束 `compose.sh down embedding-service`（保留 `embedding-model-cache` Volume）。
- **错误处理**：OOMKilled → exit 2；timeout 未 healthy → exit 3；compose 失败 → exit 1。
- **禁止**：`docker update` 修改 mem_limit；拉取 HF 模型（无缓存时 skip 并提示先 warm cache）。

### Step 2 — Preflight Check 13 硬化（§3.18 #12）

- **文件**：`scripts/preflight/check_linux_host.sh`
- **策略**：保留现有 `MemTotal` 快检作为 **Check 13a**；新增 **Check 13b TEI CPU runtime probe**（仅当 `resolved_mode=cpu`）。
- **Check 13b 行为**：
  1. 环境变量 `PREFLIGHT_SKIP_TEI_PROBE=1` → `SKIP`（供无 Docker/CI）。
  2. 调用共享函数 `probe_tei_cpu_memory_limit()`（可提取至 `scripts/preflight/lib_tei_probe.sh` 供 start_embedding 复用）：
     - 使用 **当前仓库** `compose.embedding.cpu.yaml`（`mem_limit: 8g`）。
     - 启动 embedding-service；最长等待 **300s**（对齐 DEV-006 §8.8 与 healthcheck 语义）。
     - 成功：`PASS: TEI CPU warm-up completed within 8g mem_limit`。
     - 失败：`FAIL: TEI CPU OOMKilled under mem_limit=8g` 或 `FAIL: TEI CPU not healthy within 300s`；附 peak RSS 若可观测。
  3. 探针后清理容器。
- **gpu / auto→gpu 路径**：SKIP Check 13b（本任务范围外；GPU 阻塞项另记）。
- **幂等**：多次运行 probe 不破坏已有全栈；仅操作 embedding-service。

### Step 3 — `start_embedding.sh` OOM 与 health 等待

- **文件**：`scripts/start_embedding.sh`
- **追加**（CPU 与 `auto→cpu` 回退路径）：
  1. `up -d` 后轮询容器状态（最长 300s）。
  2. 检测 `OOMKilled` 或 exit `137` → `cleanup_failed_embedding` + `fail "embedding-service OOMKilled under mem_limit=8g (exit 137). Run scripts/diagnostics/measure_tei_memory.sh for evidence."`
  3. 检测 health（`curl` 容器内 `/health` 或 compose healthcheck 状态）→ 成功则 PASS 日志；超时则 fail 并附 `docker logs --tail 50` 提示。
- **禁止**：自动 `docker update` 提限；静默 fallback 到非 spec 配置。

### Step 4 — 测试（Amendment 001：分层）

见 §8。**不得**在默认 `tests/integration/` 中要求真实 8g TEI healthy。

- **Layer A**（`tests/unit/…`）：mock/stub 验证 tooling 对 PASS / OOM / timeout / unexpected exit / incomplete evidence 的分类与 JSON/exit 码。
- **Layer B**（`tests/runtime_contract_gate/…`）：真实 8g reference gate，**独立目录、非默认 CI**；CONFLICT 时 pytest **PASS**（断言 evidence 完整 + `runtime_contract_verdict=SPEC_RUNTIME_CONTRACT_CONFLICT`）。
- **删除** `tests/integration/test_tei_cpu_memory_probe.py`（迁出至 Layer B，避免默认红灯）。
- **Contract**：`mem_limit: 8g` 静态断言不变。

### Step 5 — 文档

- **`README.md`**（最小）：增加「TEI CPU 内存探针」与 `measure_tei_memory.sh` 用法；注明 §3.18 #12 与 P2-001 闭合；**不**写入 16g 未授权实验为推荐配置。

## 6. 文件变更清单（精确白名单）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `scripts/diagnostics/measure_tei_memory.sh` | 创建 | warm-up/steady-state 内存证据采集 |
| `scripts/preflight/lib_tei_probe.sh` | 修改 | 共享 TEI CPU 8g 探针逻辑；JSON schema |
| `scripts/preflight/check_linux_host.sh` | 修改 | Check 13b runtime probe；保留 13a |
| `scripts/start_embedding.sh` | 修改 | OOM/health 等待与 fail-closed |
| `tests/unit/test_tei_memory_probe.py` | 修改 | Layer A tooling correctness |
| `tests/unit/test_preflight_tei_probe_contract.py` | 创建/修改 | preflight 输出子串、SKIP 开关 |
| `tests/contract/test_compose_config_contract.py` | 修改 | 断言 CPU `mem_limit` 为 `8g` |
| `tests/integration/test_tei_cpu_memory_probe.py` | **删除** | 迁出至 runtime_contract_gate（Amendment 001） |
| `tests/runtime_contract_gate/test_tei_cpu_runtime_contract_gate.py` | 创建 | Layer B 真实 8g reference gate（独立执行） |
| `pyproject.toml` | 修改 | **仅** `[tool.pytest.ini_options]`：注册 `runtime_contract_gate` marker |
| `README.md` | 修改 | 探针、分层测试、独立 gate 命令 |
| `02_开发管理/tasks/DEV-003-002-tei-cpu-memory-contract-validation.md` | 修改 | 本 Task Plan |
| `02_开发管理/progress.md` | 修改 | 规划态 |
| `02_开发管理/master_plan.md` | 修改 | DEV-003-002 条目：MODEL 2 完成语义；DEV-006 R2–R4 延期至 Spec-OI |

### 6.1 黑名单（禁止触碰）

| 路径 | 原因 |
|---|---|
| `compose.embedding.cpu.yaml` 的 `mem_limit` | 规格 §3.10.3 冻结 `8g`；变更须 Spec-OI |
| `compose.embedding.gpu.yaml` | 范围外 |
| `versions.env` / `versions.lock.env` | 非 Digest 更新任务 |
| `src/memory_system/**` | DEV-006 范围 |
| `feat/DEV-006-*` 分支 | 用户禁令 |
| 五命令 / `.cursor/agents/**` | 治理冻结 |

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 探针为一次性宿主机操作 |
| 幂等 | 适用 | 探针前后 `down embedding-service`；Volume 保留 |
| 并发 | 不适用 | 单主机诊断 |
| 版本冲突 | 不适用 | 无持久化状态 |
| 用户隔离 | 不适用 | 基础设施脚本 |
| 部分失败 | 适用 | OOM 或 health 超时 → 整体 fail；不标记通过 |
| 进程异常恢复 | 适用 | `trap` 清理；`cleanup_failed_embedding` 复用 DEV-003 模式 |

### 7.1 验证与证据采集设计（warm-up peak vs steady-state）

```text
Timeline (1s sample interval)
│
├─ T0: compose up embedding-service (mem_limit=8g)
├─ T_warm: logs "Warming up model" ──► track rss_peak_warmup = max(memory_samples)
├─ T_ready: GET /health → 200 ──► record time_to_ready_sec
├─ T_ss: +5s × 3 samples ──► rss_steady_state = mean(samples)
└─ Teardown: compose down embedding-service

Failure classes:
  F1: OOMKilled before T_ready → rss_peak_warmup may equal mem_limit; exit 137
  F2: timeout 300s, no OOM → rss_peak_warmup recorded; health never 200
  F3: success → assert rss_steady_state ≤ rss_peak_warmup; both recorded
```

**报告 JSON 最小字段**（`tei_memory_report.json`；Amendment 001 补齐）：

```json
{
  "schema_version": "1",
  "recorded_at_utc": "2026-08-08T…Z",
  "model_id": "BAAI/bge-m3",
  "revision": "57aacf8560157b7c1d4f771ce1a199877aeeec74",
  "dtype": "float32",
  "runtime": "ONNX CPU",
  "tei_image": "ghcr.io/…/text-embeddings-inference:…",
  "image_digest": "sha256:…",
  "spec_mem_limit_bytes": 8589934592,
  "mem_limit_human": "8g",
  "container_mem_limit_bytes": 8589934592,
  "rss_peak_warmup_bytes": 8589934592,
  "rss_steady_state_bytes": null,
  "health_ready": false,
  "time_to_ready_sec": null,
  "time_to_failure_sec": 138,
  "oom_killed": true,
  "exit_code": 137,
  "timed_out": false,
  "probe_timeout_sec": 300,
  "runtime_contract_verdict": "SPEC_RUNTIME_CONTRACT_CONFLICT",
  "host_mem_total_bytes": 1081962123264,
  "host_mem_available_bytes": 958995234816,
  "container_name": "…",
  "container_status": "…",
  "container_health": "…"
}
```

**字段规则（Amendment 001）**：

| 规则 | 说明 |
|---|---|
| OOM / 未 healthy | `rss_steady_state_bytes` **必须** `null`；不得伪造 |
| PASS | `health_ready=true` 且 `rss_steady_state_bytes` 为整数 |
| `time_to_ready_sec` | 仅 `health_ready=true` 时填充；否则 `null` |
| `time_to_failure_sec` | `health_ready=false` 时填充（至 OOM/exit/timeout） |
| `runtime_contract_verdict` | `PASS` \| `SPEC_RUNTIME_CONTRACT_CONFLICT` \| `PROBE_EVIDENCE_INCOMPLETE` |
| `image_digest` | 从 `versions.lock.env` `TEI_CPU_IMAGE` 解析 `@sha256:` |

**发布证据要求**：Integration 或人工受监督运行须归档一份 redacted 报告至 Task Plan §13 执行记录（**不得** commit 含主机标识/路径敏感信息）。

### 7.2 Preflight vs 诊断脚本职责

| 组件 | 时机 | 失败语义 |
|---|---|---|
| `measure_tei_memory.sh` | 人工/CI 诊断 | 采集完整报告；非 preflight 必经 |
| `check_linux_host.sh` Check 13b | `cpu` / `auto→cpu` preflight | 硬失败阻止 §3.17 启动 |
| `start_embedding.sh` wait | 每次 CPU 启动 | 运行期 fail-closed |

## 8. 测试计划

> **Amendment 001**：分层验证；默认 CI 不含 reference runtime contract gate。

### Layer A — Tooling correctness（默认 CI 必跑）

**位置**：`tests/unit/test_tei_memory_probe.py`（扩展）；可选 mock helper 同文件或 `tests/unit/test_tei_probe_mocked_paths.py`（若拆分须入白名单）。

| 场景 | 方法 | 预期 |
|---|---|---|
| 解析 `docker stats` 内存字符串 → bytes | 直接调用 bash helper | 正确取 peak |
| JSON writer 全字段 | 受控输入 | §7.1 schema 满足；OOM 时 steady=null |
| mock `docker inspect` → OOMKilled=true | subprocess + stub script / fixture | `tei_probe_run_cpu_validation` return 2；`runtime_contract_verdict=SPEC_RUNTIME_CONTRACT_CONFLICT` |
| mock healthy path | stub | return 0；steady 有值 |
| mock timeout | stub | return 3；`timed_out=true` |
| mock unexpected exit | stub | return 1 |
| incomplete evidence（无 JSON） | stub | `PROBE_EVIDENCE_INCOMPLETE`；非零退出 |
| `PREFLIGHT_SKIP_TEI_PROBE=1` | contract | Check 13b SKIP |
| `measure_tei_memory.sh` help / exit 码传播 | subprocess | 与 probe rc 一致 |

**禁止**：Layer A 不得要求真实 8g TEI healthy。

### Layer B — Reference runtime contract gate（独立执行，非默认 CI）

**位置**：`tests/runtime_contract_gate/test_tei_cpu_runtime_contract_gate.py`（自 `tests/integration/test_tei_cpu_memory_probe.py` 迁出并改写）。

**标记**：`@pytest.mark.runtime_contract_gate`

**执行**：

```bash
# 显式 reference gate（可长达 ~300s）
uv run pytest tests/runtime_contract_gate -m runtime_contract_gate -q

# 或诊断脚本（同等证据）
bash scripts/diagnostics/measure_tei_memory.sh --timeout=300
```

| 场景 | 预期 |
|---|---|
| 模型缓存命中 + Docker 可用 + **8g PASS** | `health_ready=true`；`runtime_contract_verdict=PASS`；exit 0 |
| 模型缓存命中 + Docker 可用 + **8g CONFLICT**（当前 reference host） | `oom_killed=true`；`exit_code=137`；steady=null；`runtime_contract_verdict=SPEC_RUNTIME_CONTRACT_CONFLICT`；**pytest PASS**（验证 tooling 正确报告 conflict）；`measure_tei_memory.sh` exit 2 |
| 无模型缓存 | `pytest.skip`（gate 不适用） |
| 无 Docker | `pytest.skip` |
| evidence incomplete | **pytest FAIL**（tooling 缺陷） |

**关键语义**：Layer B **不得**在 CONFLICT 时 `pytest.fail`；必须断言报告完整性与 verdict 正确性。

### Contract Test

| 场景 | 预期 |
|---|---|
| `compose.embedding.cpu.yaml` rendered `mem_limit` | 等于 `8g` 或 `8589934592` |
| `check_linux_host.sh` 输出 | 含 Check 13a/13b |
| preflight Check 8 `MemAvailable` | 不退化 |

### 默认 CI 命令（Amendment 001）

```bash
uv run pytest tests/unit tests/contract tests/integration -q
# 显式排除 runtime_contract_gate 目录（该目录不在上述路径内）
```

**不得**将 `tests/runtime_contract_gate/` 纳入默认 `tests/integration` 收集路径。

### E2E Test

| 场景 | 预期 |
|---|---|
| — | 不适用 |

### Operational fail-closed（非 pytest，必须保持）

| 命令 | CONFLICT  host 行为 |
|---|---|
| `check_linux_host.sh --mode=cpu` | **exit 1**（Check 13b FAIL） |
| `start_embedding.sh cpu` | **exit 1**（OOM/health fail） |
| `measure_tei_memory.sh` | **exit 2**（OOM） |

**仅测试分类调整**；运行命令语义不得改为 PASS。

## 9. 验收标准

> **Amendment 001（MODEL 2）**

- [ ] 白名单文件齐套；黑名单无触碰；`compose.embedding.cpu.yaml` `mem_limit` 仍为 `8g`
- [ ] `measure_tei_memory.sh` 输出 §7.1 完整 JSON；OOM 时 steady=null；含 `image_digest` 与 `runtime_contract_verdict`
- [ ] Preflight `cpu` 路径：Check 13b 在 8g CONFLICT 时 **operational exit 1**（fail-closed 保持）
- [ ] `start_embedding.sh cpu`：OOMKilled 时 **operational exit 1**（保持）
- [ ] **默认 CI**：`uv run pytest tests/unit tests/contract tests/integration -q` 全绿（**不**含 runtime_contract_gate）
- [ ] **Layer A** tooling correctness tests 全绿（含 mock OOM/timeout/healthy/incomplete）
- [ ] **Layer B** reference gate：§13 归档 evidence（或 `archived_conflict_evidence_v1.json` fixture）满足 schema 且 `runtime_contract_verdict=SPEC_RUNTIME_CONTRACT_CONFLICT`；**不得**为重复同一 OOM 结果自动重跑真实 probe；`measure_tei_memory.sh` exit 2 可由既有归档 evidence 验收
- [ ] `uv run ruff check .` / `uv run mypy src tests scripts` 通过
- [ ] Review 无 P0/P1
- [ ] 合并后状态：`task_status=completed` **且** `runtime_contract_status=SPEC_RUNTIME_CONTRACT_CONFLICT`（**不得**写成 8g validated successfully）
- [ ] DEV-006 保持 PAUSED；PR #13 NOT_READY_FOR_PR_MERGE

## 10. 风险与阻塞项

| 类型 | 说明 |
|---|---|
| **规格冲突（高）** | 若 bge-m3 float32 warm-up 峰值 **持续** >8g，则 §3.10.3 与实测不符 → **停止实施提限**；开 Spec-OI；证据提交人类 |
| DEV-003 P2-001 残余 | 本任务正式闭合；不再以 MemTotal 代理 TEI runtime |
| 探针耗时 | 首次无缓存可能 >300s；Layer B runtime contract gate 要求缓存命中 |
| CI 无 Docker/GPU | Layer B gate skip；默认 unit/contract/integration 仍阻塞 merge |
| DEV-006 分支 | 本任务不得在其上开发；merge 后 rebase feat |
| 16g 未授权实验 | 仅作故障对比证据；**禁止** 写入 compose 或 release |

## 11. Git 计划（NORMAL 三相）

```yaml
branch: "feat/DEV-003-002-tei-cpu-memory-contract-validation"
workflow_mode: NORMAL
release_phases:
  PLAN_LANDING:
    allowed_on: main
    commits:
      - "docs(plan): add DEV-003-002 tei cpu memory contract validation plan"
    then: "创建 exact feat 分支"
  IMPLEMENTATION_RELEASE:
    allowed_on: feat
    commits:
      - "fix(docker): harden TEI CPU 8g preflight probe and memory diagnostics"
      - "docs(status): record DEV-003-002 implementation commit and PR"
    push: "origin feat only"
    pr: "gh pr create → 人工 Merge"
  POST_MERGE_CLEANUP:
    allowed_on: main
    after: "PR MERGED verified"
    commits:
      - "docs(status): complete DEV-003-002 after PR merge"
    then: "git branch -d feat/DEV-003-002-tei-cpu-memory-contract-validation && git push origin --delete feat/DEV-003-002-tei-cpu-memory-contract-validation"
out_of_scope_changes:
  - "DEV-006 feat 分支与 PR #13 实现"
  - "compose mem_limit 非 8g 变更"
  - "src/memory_system 业务代码"
  - "五命令与 Orchestrator"
```

## 12. Plan Amendment

### Amendment 001 — MODEL 2：Tooling Delivery vs Runtime Contract Conflict

**状态**：`approved`（Plan Review Round 2：`PLAN_APPROVED`；BLOCKER=0；MUST_FIX=0）  
**触发**：`SPEC_OI_PREPARATION_AUDIT` + 人工裁决采用 MODEL 2  
**日期**：2026-08-09

#### A. 人工裁决摘要

采用 **MODEL 2**。DEV-003-002 交付 validation tooling；8g runtime OOM 为 **有效 validation 结论**，不是 tooling 失败。

**三态分离（必须同时记录）**：

| 状态键 | 当前/reference host 值 | 含义 |
|---|---|---|
| `TOOLING_STATUS` | `VALID`（实施后验收） | probe/diagnostics/preflight/startup 实现正确 |
| `RUNTIME_CONTRACT_STATUS` | `SPEC_RUNTIME_CONTRACT_CONFLICT` | 当前 spec 8g contract 不可用 |
| `DEV006_DEPENDENCY_STATUS` | `BLOCKED` | DEV-006 不得恢复 |

#### B. 任务完成语义（修订 §2 / §9）

`DEV-003-002 completed` 当且仅当：

1. Tooling 实现 merged；
2. Layer A tests + 默认 CI 全绿；
3. Layer B reference gate 在当前 host 正确报告 CONFLICT（pytest PASS）或 PASS（若未来 host 满足 8g）；
4. 权威 evidence 归档 §13；
5. Code Review APPROVED。

**不得**将 `completed` 解释为 `8g runtime contract validated successfully`。

#### C. Integration 测试修订（§8）

1. **删除** `tests/integration/test_tei_cpu_memory_probe.py` 作为默认 integration 红灯源。
2. **新建** `tests/runtime_contract_gate/test_tei_cpu_runtime_contract_gate.py`：
   - 真实 8g probe；
   - CONFLICT 时断言 evidence + verdict，**pytest 通过**；
   - incomplete/wrong classification 时 **pytest 失败**。
3. **扩展** Layer A unit tests：mock/stub 覆盖 PASS/OOM/timeout/unexpected exit/incomplete。

#### D. 默认 CI 行为（修订 §8 / README）

```bash
# 默认 merge gate
uv run pytest tests/unit tests/contract tests/integration -q

# 显式 reference contract gate（非 merge 阻塞；人工/Spec-OI 前诊断）
uv run pytest tests/runtime_contract_gate -m runtime_contract_gate -q
bash scripts/diagnostics/measure_tei_memory.sh --timeout=300
```

Operational commands **保持 fail-closed**（preflight / start_embedding / measure 在 CONFLICT 时非零退出）。

#### E. JSON schema 补齐（修订 §7.1 / `lib_tei_probe.sh`）

增补：`schema_version`、`recorded_at_utc`、`tei_image`、`image_digest`、`runtime_contract_verdict`、`time_to_failure_sec`；规范 `time_to_ready_sec` 仅 healthy 时填充。

#### F. `start_embedding.sh`（无行为变更）

保持当前 fail-closed enhancement；Amendment 不授权 retry / docker update / memory escalation / model fallback。

#### G. DEV-006 依赖（修订 §15）

DEV-003-002 merge **仅满足** §15 R1。R2–R4 移至 **Spec-OI 后新 contract** 验证；8g PASS 不再是 DEV-006 恢复前提（除非 Spec-OI 维持 8g 且重新验证 PASS）。

#### H. Spec-OI memory decision

`MEMORY_LIMIT_DECISION_NOT_YET_SUPPORTED`。本 Amendment **不执行** characterization matrix。后续 Spec-OI 输入设计（不实施）：

| 固定 | 变量 |
|---|---|
| bge-m3 / rev 57aacf… / float32 / ONNX CPU / pinned TEI digest / warmed cache / `PROXY__HTTP_URL=""` | cgroup limit ∈ {8g, 10g, 12g, 16g}；每档 ≥2 clean runs |

#### I. 白名单增量（§6）

| 路径 | 动作 |
|---|---|
| `tests/runtime_contract_gate/test_tei_cpu_runtime_contract_gate.py` | 创建 |
| `tests/integration/test_tei_cpu_memory_probe.py` | 删除 |
| `pyproject.toml` | 修改（**仅** pytest markers） |
| `scripts/preflight/lib_tei_probe.sh` | 修改（JSON schema） |

#### J. 实施前置（Amendment 批准后）

1. Developer 按修订白名单实施 Amendment；
2. **Layer B gate 数据源**：**优先**使用 §13 已归档之正式 probe JSON（`.runtime/tei_memory_report.json` 红acted 副本）做 schema/verdict 断言；**仅当**该文件不可用或 schema 升级后字段缺失时，允许 **一次** `pytest tests/runtime_contract_gate` 或 `measure_tei_memory.sh` 重采集；**禁止** characterization matrix 或额外档位 probe；
3. Code Review → Commit Recorder → Release Operator。

#### K. 与初版 Plan 差异

| 初版 | Amendment 001 |
|---|---|
| Integration 要求 8g healthy | Layer B 允许 CONFLICT 为 gate PASS |
| §9 模糊 “或 Spec-OI HALT” | 明确 MODEL 2 completed + CONFLICT 并存 |
| §15 R2 要求 8g PASS | R2 改为 Spec-OI 后 **新 contract** PASS |
| JSON 缺 digest/verdict | §7.1 补齐 |

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-08 | PLAN_LANDING | `main` @ `7172e91`；创建 `feat/DEV-003-002-tei-cpu-memory-contract-validation` | — | 成功 |
| 2026-08-08 | Developer 实现 | 白名单脚本/测试/README（见 §14） | unit+contract 18 passed；ruff/mypy 通过 | SF-001～004 已吸收 |
| 2026-08-08 | 正式 8g runtime validation（唯一一次） | `measure_tei_memory.sh --timeout=300` | **FAIL** OOMKilled exit=137 @ 138s | **ORCHESTRATOR_HALTED** → `SPEC_RUNTIME_CONTRACT_CONFLICT_CANDIDATE` |

### 正式 runtime probe 证据（Spec-OI）

| 字段 | 值 |
|---|---|
| model | `BAAI/bge-m3` |
| revision | `57aacf8560157b7c1d4f771ce1a199877aeeec74` |
| dtype | `float32` |
| runtime | `ONNX CPU` |
| spec_mem_limit_bytes | `8589934592` |
| container_mem_limit_bytes | `8589934592` |
| rss_peak_warmup_bytes | `8589934592` |
| rss_steady_state_bytes | `null`（warm-up OOM，未伪造） |
| health_ready | `false` |
| time_to_ready_sec | `null`（未达 healthy） |
| time_to_failure_sec | `138`（至 OOM） |
| oom_killed | `true` |
| exit_code | `137` |
| host_mem_total_bytes | `1081962123264`（~1007 GiB） |
| host_mem_available_bytes | `958995234816`（~893 GiB） |
| 分类 | **A. container cgroup limit 不足**（宿主机物理内存充足） |

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `scripts/diagnostics/measure_tei_memory.sh` | 创建 |
| `scripts/preflight/lib_tei_probe.sh` | 创建 |
| `scripts/preflight/check_linux_host.sh` | Check 13a/13b |
| `scripts/start_embedding.sh` | OOM/health fail-closed |
| `tests/unit/test_tei_memory_probe.py` | 创建 |
| `tests/unit/test_preflight_tei_probe_contract.py` | 创建 |
| `tests/contract/test_compose_config_contract.py` | mem_limit 8g 断言 |
| `tests/integration/test_tei_cpu_memory_probe.py` | 创建 |
| `README.md` | TEI 探针文档 |

### 与原计划的差异

- 正式 runtime validation **失败**（OOM @ 8g）；按约束 **HALT**，未进入 Code Review / Release。
- `measure_tei_memory.sh` 退出码传播已修正（`exit "${rc}"`）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit/test_tei_memory_probe.py tests/unit/test_preflight_tei_probe_contract.py -q` | **18 passed**（含 contract 子集） |
| Contract | `uv run pytest tests/contract/test_compose_config_contract.py -q` | **passed** |
| Integration | `test_tei_cpu_memory_probe` | **未单独重跑**（与正式 probe 同源；正式 probe 已 FAIL） |
| Ruff | `uv run ruff check .` | **passed** |
| Mypy | `uv run mypy src tests scripts` | **passed** |
| 正式 8g runtime | `measure_tei_memory.sh --timeout=300` | **FAIL** OOM exit 137 |

### Review 结果

```yaml
p0: null
p1: null
review_report: null
halt_reason: SPEC_RUNTIME_CONTRACT_CONFLICT_CANDIDATE
```

### Git 记录

```yaml
branch: feat/DEV-003-002-tei-cpu-memory-contract-validation
plan_commit: 7172e918647c1853d0982ce979b299920d96a0cb
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`ORCHESTRATOR_HALTED` — `SPEC_RUNTIME_CONTRACT_CONFLICT_CANDIDATE`（待人工 Spec-OI）

## 15. DEV-006 恢复条件

> **Amendment 001**：DEV-003-002 merge 仅解除 R1；R2–R4 依赖 **Spec-OI 后新 runtime memory contract**。

在 **全部** 满足前，DEV-006 保持 `PAUSED`；PR #13 保持 `NOT_READY_FOR_PR_MERGE`：

| # | 条件 | 验证方式 |
|---|---|---|
| R1 | **DEV-003-002** `completed`（PR merged to `main`） | `progress.md` `formal_DEV-003-002_status=completed`；`runtime_contract_status` 可仍为 `SPEC_RUNTIME_CONTRACT_CONFLICT` |
| R2 | **Spec-OI 批准后的 CPU TEI contract** 在 **新 spec mem_limit** 下无 OOM 且 300s 内 healthy | `measure_tei_memory.sh` 或 Layer B gate：`runtime_contract_verdict=PASS` |
| R3 | **Preflight Check 13b** 在新 contract 下通过 | `bash scripts/preflight/check_linux_host.sh --mode=cpu` exit 0 |
| R4 | **`./scripts/start_embedding.sh cpu`** 在新 contract 下成功 | exit 0；无 OOMKilled |
| R5 | **DEV-006 feat 分支** 从最新 `main` 整合 | 人工确认基点含 DEV-003-002 + Spec-OI contract 变更 |
| R6 | **DEV-006 §8.8 Integration** 重跑通过 | `uv run pytest tests/integration/test_tei_embedding_client_integration.py -q` exit 0 |
| R7 | PR #13 门禁恢复 | Orchestrator 记录 |

**当前 8g CONFLICT 下**：R2–R4 **不满足**；DEV-006 **保持 BLOCKED**。

**Spec-OI 前置**：`MEMORY_LIMIT_DECISION_NOT_YET_SUPPORTED`；须独立 Spec-OI 任务批准 characterization matrix 并修订规格/compose 后，方可验证 R2–R4。

## 16. Planner 问答摘要（Orchestrator 用）

### Q1 分类

**A — DEV-003 follow-up**（非 B 新 DEV、非 C DEV-OPS、非 D Spec-OI 首选）。

理由：根因是 DEV-003 Preflight Check 13（P2-001 Verdict A）未实现 §3.18 #12 字面语义；修复域为 `scripts/preflight`、`start_embedding.sh`、诊断脚本与 DEV-003 同类测试——与 DEV-003 同一归属。若实测证明 8g 不可行，**升级为 D Spec-OI**，但任务本身仍是闭合 DEV-003 交付缺口。

### Q2 任务 ID

**DEV-003-002**（`tei-cpu-memory-contract-validation`）。

`master_plan` Phase 0 已有 DEV-001–006；无 DEV-007 业务槽位需求；采用 **DEV-003 序号 follow-up** 而非 DEV-007，避免与 Phase 0 下一业务任务 DEV-006 混淆。

### Q3 根因

Preflight 用 `MemTotal≥10GiB` **代理** Docker 8g TEI cgroup 可行性，未测量 bge-m3 float32 **warm-up 峰值 RSS**；导致 §3.17 启动链允许进入 DEV-006 §8.8，运行期 OOMKilled exit 137。

### Q4 方案要点

证据脚本 + Preflight Check 13b 运行时探针 + `start_embedding.sh` OOM/health 等待；**不改** `mem_limit`。

### Q5 验证设计

见 §7.1：1s 采样、warm-up peak vs steady-state、JSON 报告、三类失败分类 F1–F3。

### Q6 DEV-006 恢复

见 §15 条件 R1–R7。

### Q7 最小白名单

见 §6（13 条路径）；核心 4 项：`measure_tei_memory.sh`、`lib_tei_probe.sh`、`check_linux_host.sh`、`start_embedding.sh` + 测试 + 治理三文件。

### Q8 关键风险

规格冲突（8g 不足）→ Spec-OI HALT；禁止 16g 未授权 workaround 入库。
