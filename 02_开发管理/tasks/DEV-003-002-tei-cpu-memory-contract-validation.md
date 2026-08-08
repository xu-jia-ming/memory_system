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
  - "DEV-006 §8.8 Integration 真实 TEI（CPU 发布阻塞）"
  - "DEV-006 PR #13 NOT_READY_FOR_PR_MERGE"
branch: "feat/DEV-003-002-tei-cpu-memory-contract-validation"
created_at: "2026-08-08 14:52 UTC"
updated_at: "2026-08-08 15:18 UTC"
```

## 2. 任务目标

闭合 **DEV-003 P2-001 Verdict A** 暴露的残余风险：Preflight Check 13 仅以宿主机 `MemTotal ≥ 10 GiB` 代理 §3.18 #12「Docker 能为 TEI 提供 `8g` Memory Limit」，**未验证** TEI 在 `mem_limit: 8g`（8589934592 bytes）下 warm-up 峰值 RSS 能否在 grace period 内完成模型加载并达到 healthy。

完成后应具备：

1. **可复现的内存证据采集**：区分 warm-up 峰值 RSS 与 steady-state RSS；记录 OOMKilled、time-to-ready、镜像 Digest、模型 Revision、dtype；输出机器可读报告（JSON + 人类摘要）。
2. **Preflight 硬化**：在 `resolved_mode=cpu`（含 `auto→cpu`）路径上，以 **spec-compliant** `compose.embedding.cpu.yaml`（`mem_limit: 8g` 不变）执行 TEI 启动探针；OOM 或 300s 内未 healthy → **硬失败**并输出诊断。
3. **`start_embedding.sh` OOM 可观测性**：CPU 路径启动后检测容器 `OOMKilled` / exit 137；失败时清理并给出明确错误（禁止静默重试或掩盖）。
4. **契约测试**：静态断言 CPU Override `mem_limit: 8g` 未被削弱；Preflight 探针逻辑 Unit/Contract；Integration 在具备 Docker + 模型缓存的主机上验证探针通过或按规则 skip。
5. **DEV-006 解阻路径清晰**：本任务 merged 且证据满足 §15 恢复条件后，DEV-006 可恢复 §8.8 Integration。

**规格边界**：本任务 **不得** 将 `compose.embedding.cpu.yaml` 的 `mem_limit` 改为 `16g` 或任何非 `8g` 值，除非人类先行批准 **Spec-OI** 并修订规格 §3.10.3 / §3.18 #12（见 §12）。

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
  5. 输出 JSON（字段见 §7.2）+ stdout 人类摘要行。
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

### Step 4 — 测试

见 §8。Contract 锁定 `mem_limit: 8g` 字面量；Unit 测试 probe 决策逻辑（mock docker）；Integration 在 `embedding-model-cache` 命中且 Docker 可用时跑真实 probe（否则 skip）。

### Step 5 — 文档

- **`README.md`**（最小）：增加「TEI CPU 内存探针」与 `measure_tei_memory.sh` 用法；注明 §3.18 #12 与 P2-001 闭合；**不**写入 16g 未授权实验为推荐配置。

## 6. 文件变更清单（精确白名单）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `scripts/diagnostics/measure_tei_memory.sh` | 创建 | warm-up/steady-state 内存证据采集 |
| `scripts/preflight/lib_tei_probe.sh` | 创建 | 共享 TEI CPU 8g 探针逻辑 |
| `scripts/preflight/check_linux_host.sh` | 修改 | Check 13b runtime probe；保留 13a |
| `scripts/start_embedding.sh` | 修改 | OOM/health 等待与 fail-closed |
| `tests/unit/test_tei_memory_probe.py` | 创建 | probe 决策、解析、退出码 Unit |
| `tests/unit/test_preflight_tei_probe_contract.py` | 创建 | preflight 输出子串、SKIP 开关 |
| `tests/contract/test_compose_config_contract.py` | 修改 | 断言 CPU `mem_limit` 为 `8g` |
| `tests/integration/test_tei_cpu_memory_probe.py` | 创建 | 真实探针（缓存命中时） |
| `README.md` | 修改 | 探针与诊断命令 |
| `02_开发管理/tasks/DEV-003-002-tei-cpu-memory-contract-validation.md` | 修改 | 本 Task Plan |
| `02_开发管理/progress.md` | 修改 | 规划态 |
| `02_开发管理/master_plan.md` | 修改 | CHANGE-012 登记 |

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

**报告 JSON 最小字段**（`tei_memory_report.json`）：

```json
{
  "spec_mem_limit_bytes": 8589934592,
  "mem_limit_human": "8g",
  "image_digest": "sha256:…",
  "model_id": "BAAI/bge-m3",
  "model_revision": "57aacf…",
  "dtype": "float32",
  "oom_killed": false,
  "exit_code": 0,
  "time_to_ready_sec": 0,
  "rss_peak_warmup_bytes": 0,
  "rss_steady_state_bytes": 0,
  "health_ready": true,
  "probe_timeout_sec": 300,
  "recorded_at_utc": "…"
}
```

**发布证据要求**：Integration 或人工受监督运行须归档一份 redacted 报告至 Task Plan §13 执行记录（**不得** commit 含主机标识/路径敏感信息）。

### 7.2 Preflight vs 诊断脚本职责

| 组件 | 时机 | 失败语义 |
|---|---|---|
| `measure_tei_memory.sh` | 人工/CI 诊断 | 采集完整报告；非 preflight 必经 |
| `check_linux_host.sh` Check 13b | `cpu` / `auto→cpu` preflight | 硬失败阻止 §3.17 启动 |
| `start_embedding.sh` wait | 每次 CPU 启动 | 运行期 fail-closed |

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 解析 `docker stats` 内存字符串 → bytes | 正确取 peak |
| `probe_tei_cpu_memory_limit` + mock docker OOM | 返回失败；消息含 `OOMKilled` |
| `probe_tei_cpu_memory_limit` + mock healthy | 返回成功 |
| `PREFLIGHT_SKIP_TEI_PROBE=1` | Check 13b SKIP |
| `measure_tei_memory.sh` timeout 路径 | exit 3 |

### Contract Test

| 场景 | 预期 |
|---|---|
| `compose.embedding.cpu.yaml` rendered `mem_limit` | 等于 `8g` 或 `8589934592` |
| `check_linux_host.sh` 帮助/输出 | 含 `Check 13b` 或 `TEI CPU runtime probe` 子串 |
| preflight 脚本仍含 Check 8 `MemAvailable` | 不退化 |

### Integration Test

| 场景 | 预期 |
|---|---|
| 模型缓存命中 + Docker 可用：`test_tei_cpu_memory_probe` | probe 成功；`health_ready=true`；`oom_killed=false` |
| 无模型缓存 | `pytest.skip` 明确 reason |
| 无 Docker | skip |
| 探针 OOM 环境（若可安全模拟） | 硬失败；**禁止** 用 16g 作为预期 |

### E2E Test

| 场景 | 预期 |
|---|---|
| — | 不适用 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 模拟 `docker inspect` 返回 `OOMKilled=true` | start_embedding fail 消息含 `exit 137` |
| 连续两次 preflight probe | 第二次仍通过（清理有效） |

## 9. 验收标准

- [ ] 白名单文件齐套；黑名单无触碰；`compose.embedding.cpu.yaml` `mem_limit` 仍为 `8g`
- [ ] `measure_tei_memory.sh` 可输出 §7.1 JSON 字段；区分 warm-up peak 与 steady-state
- [ ] Preflight `cpu` 路径：Check 13b 在 TEI 不可于 8g 内 ready 时 **硬失败**
- [ ] `start_embedding.sh cpu`：OOMKilled 时非零退出且消息 actionable
- [ ] `uv run pytest tests/unit/test_tei_memory_probe.py tests/unit/test_preflight_tei_probe_contract.py tests/contract/test_compose_config_contract.py -q` 全绿
- [ ] Integration：参考主机上 spec-compliant 探针 **通过**（`health_ready=true`）；或 documented Spec-OI HALT
- [ ] `uv run ruff check .` / `uv run mypy src tests scripts` 通过
- [ ] Review 无 P0/P1
- [ ] DEV-006 恢复条件（§15）可满足或明确触发 Spec-OI

## 10. 风险与阻塞项

| 类型 | 说明 |
|---|---|
| **规格冲突（高）** | 若 bge-m3 float32 warm-up 峰值 **持续** >8g，则 §3.10.3 与实测不符 → **停止实施提限**；开 Spec-OI；证据提交人类 |
| DEV-003 P2-001 残余 | 本任务正式闭合；不再以 MemTotal 代理 TEI runtime |
| 探针耗时 | 首次无缓存可能 >300s；Integration 要求缓存命中 |
| CI 无 Docker/GPU | Integration skip；Contract/Unit 仍阻塞 merge |
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

### Amendment 001

（空 — 初版）

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
|  |  |  |  |  |

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
|  |  |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit |  |  |
| Contract |  |  |
| Integration |  |  |
| Ruff |  |  |
| Mypy |  |  |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 0
review_report: null
```

### Git 记录

```yaml
branch: null
plan_commit: null
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`approved`

## 15. DEV-006 恢复条件

在 **全部** 满足前，DEV-006 保持 `PAUSED`；PR #13 保持 `NOT_READY_FOR_PR_MERGE`：

| # | 条件 | 验证方式 |
|---|---|---|
| R1 | **DEV-003-002** `completed`（PR merged to `main`） | `progress.md` `formal_DEV-003-002_status=completed` |
| R2 | **Spec-compliant CPU TEI** 在 `mem_limit=8g` 下 **无 OOM** 且 **300s 内 healthy** | `measure_tei_memory.sh` 报告：`oom_killed=false`，`health_ready=true`，`time_to_ready_sec≤300`；或 Integration `test_tei_cpu_cpu_memory_probe` 通过 |
| R3 | **Preflight Check 13b** 在参考开发主机通过 | `bash scripts/preflight/check_linux_host.sh --mode=cpu` exit 0 |
| R4 | **`./scripts/start_embedding.sh cpu`** 成功完成（含 health 等待） | 命令 exit 0；`docker inspect` 无 OOMKilled |
| R5 | **DEV-006 feat 分支** 从最新 `main` 整合（rebase/merge 由 Release 流程执行）；**不**在本任务修改 DEV-006 代码 | 人工确认分支基点含 DEV-003-002 实现 |
| R6 | **DEV-006 §8.8 Integration** 重跑通过 | `uv run pytest tests/integration/test_tei_embedding_client_integration.py -q` exit 0 |
| R7 | PR #13 状态可由人工标记为可继续 Code Review / Merge 门禁 | Orchestrator 记录 |

**Spec-OI 分支**：若 R2 在重复测量下仍失败（OOM 或 timeout），则：

1. **停止** 任何 mem_limit>8g 的「修复」；
2. 将证据附于 `open_issues.md` 新 OI 条目（Planner **不**在本任务创建 OI，由人类/Orchestrator 决议）；
3. DEV-006 保持 PAUSED 直至规格修订批准。

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
