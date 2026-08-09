# OI-011 BAAI/bge-m3 CPU TEI Memory Contract (Spec-OI)

## 1. 任务信息

```yaml
task_id: OI-011
task_name: "BAAI/bge-m3 CPU TEI Memory Contract (Spec-OI)"
status: committed
task_class: Spec-OI
open_issue_id: OI-011
spec_sections:
  - "§3.10.3 CPU 默认模式（当前 mem_limit: 8g；float32；bge-m3；env 调低歧义）"
  - "§3.10.8 Health、Readiness 与降级"
  - "§3.18 Preflight #8/#9 MemAvailable（cpu_mode 12/16）"
  - "§3.18 Preflight #12 Docker TEI mem_limit；Check 13a/13b 对齐"
  - "compose.embedding.cpu.yaml 字面 mem_limit"
prerequisites:
  - "DEV-003 completed"
  - "DEV-003-002 completed（TOOLING_STATUS=VALID；RUNTIME_CONTRACT_STATUS=SPEC_RUNTIME_CONTRACT_CONFLICT）"
  - "main 含 PR #14 merge（4d894cc）与 docs(status) complete（2356a85）"
  - "DEV-006 保持 PAUSED；PR #13 保持 OPEN / NOT_READY_FOR_PR_MERGE（本任务不得修改/merge）"
branch: "feat/OI-011-bge-m3-cpu-tei-memory-contract"
created_at: "2026-08-09 01:30 UTC"
updated_at: "2026-08-09 02:40 UTC"
workflow_mode_for_this_task: NORMAL
workflow_mode_source: explicit
insertion_reason: "NEW_UNPLANNED_FEATURE：DEV-003-002 确认 SPEC_RUNTIME_CONTRACT_CONFLICT；须 Spec-OI characterization 修订 CPU TEI memory contract，方可恢复 DEV-006 R2–R7"
bound_open_issue: "02_开发管理/open_issues.md#OI-011"
runtime_contract_status_at_plan: SPEC_RUNTIME_CONTRACT_CONFLICT
tooling_status_at_plan: VALID
dev006_dependency_status_at_plan: BLOCKED
changes_technical_spec: true
human_plan_approved_at: "2026-08-09 02:00 UTC"
human_plan_approved_note: "PLAN_APPROVED Round 3；BLOCKER=0；MUST_FIX=0；人工确认批准 OI-011"
plan_review:
  round_1: "PLAN_REJECTED（BLOCKER=0；MUST_FIX=4；SHOULD_FIX=4）"
  amendment_001: "Amendment 001 — Plan Remediation Round 1（吸收 Round 1 MF-1～MF-4 + SF-1～SF-4）"
  round_2_should_fix: "Round 2 SHOULD_FIX=SF-1～SF-4（已由 Amendment 002 吸收）"
  round_3_must_fix: "Round 3 MUST_FIX=MF-3（§5.8 查表 TEI=12→CPU_MIN 错误；已由 Amendment 002 修正）"
  amendment_002: "Amendment 002 — Plan Remediation Round 3（修正 MF-3 查表 + 吸收 Round 2 SF-1～SF-4）"
  round_3: "PLAN_APPROVED（BLOCKER=0；MUST_FIX=0）"
  next: "PLAN_LANDING → Developer 实施"
```

### 1.1 Task ID 命名论证

| 候选 | 结论 | 理由 |
|---|---|---|
| `DEV-003-003` | **拒绝** | DEV-003-002 已闭合 tooling；本任务目标是**修订规格 Contract**（mem_limit），属 Spec-OI，非又一次 Preflight tooling follow-up |
| `DEV-007` | **拒绝** | Phase 0 下一业务槽位语义上仍属 DEV-006（PAUSED）；占用 DEV-007 会与 master_plan 业务序号冲突 |
| `SPEC-OI-011`（仅前缀） | 可接受但冗余 | 与 open_issues 编号重复维护成本高 |
| **`OI-011`** | **采用** | `open_issues.md` 下一号为 OI-011；Task ID 与 OI 1:1 绑定；文件名 `OI-011-bge-m3-cpu-tei-memory-contract.md`；分支 `feat/OI-011-…`；**不与 DEV-006 冲突** |

## 2. 任务目标

在 **不修改 DEV-006 / 不 Merge PR #13** 的前提下，对 **BAAI/bge-m3 float32 ONNX CPU TEI** 完成有限、可审计的 memory-limit Spec-OI，使仓库具备：

1. **根因闭合**：以 DEV-003-002 §13 正式证据为输入，确认当前 spec `mem_limit=8g` 与 bge-m3 float32 ONNX CPU warm-up 峰值冲突（分类 A：container cgroup limit 不足）。
2. **有限 characterization matrix**：唯一变量 = container cgroup memory limit ∈ `{8g,10g,12g,16g}`；每档 **恰好 2 次**正式 clean run（最多 8 有效正式 runs；每档最多 1 次 invalid replacement）；产出完整字段表。
3. **决策 + safety margin**：按本计划 §5.4–§5.5 选择最终 CPU TEI `mem_limit`，并明确 contract 类型推荐。
4. **规格/compose/preflight 对齐**：将选定 limit 写入权威规格相关章节、`compose.embedding.cpu.yaml`、Check 13a/13b / Check 8（§3.18 #8）常量、probe 与 Contract 断言；闭合 MemAvailable / MemTotal / cgroup 职责边界。
5. **DEV-006 resume 前置**：完成本任务后，更新并满足相对 DEV-003-002 §15 的 R2–R4 技术条件（R5–R7 仍在 DEV-006 恢复流程中执行；本任务不执行）。

**本轮（Planner Remediation）只交付修订后的 Task Plan + 规划态治理文档；不执行 characterization、不改业务/测试代码、不 Git 写。**

## 3. 非目标

- 实施本计划任何 Phase（characterization / Spec 修订 / Preflight 改写）——须 `PLAN_APPROVED` 后方可。
- 无限扫描 mem_limit、dtype、model、revision、TEI 镜像或并发参数；**禁止**扩展到 20g+。
- 将 **`docker update --memory=…`** 的结果写入正式 evidence、Task Plan §13、release 或规格。
- 修改 / rebase / merge **DEV-006** Task Plan、feat 分支或 **PR #13**。
- 改变模型、`revision`、`dtype`、Pooling/Normalize、维度、单条 1024 Token 上限、GPU `mem_limit`（§3.10.4 仍 8g，本任务范围外）。
- 修改 `src/memory_system/**`、DEV-006 Embedding Client 行为。
- **修改 `scripts/compose.sh`**（本任务黑名单；见 §5.3 / SF-4）。
- 以宿主机物理内存不足（分类 B）或代理/镜像问题（分类 C/D）为结论前提——DEV-003-002 已确认分类 A。
- 把 experimental 16g 未授权 workaround 直接写入默认 compose（须经本 Spec-OI decision rule）。
- 同档 1 PASS + 1 FAIL 择优计为 Viable（SF-3 硬禁止）。

## 4. 当前代码状态

### 4.1 已存在 / 可复用

- `compose.embedding.cpu.yaml`：`mem_limit: 8g`；float32；与 §3.10.3 一致；挂载 `embedding-model-cache:/data`。
- `scripts/compose.sh`：固定 `-f` 链 = `compose.yaml` → `compose.override.yaml`（dev）|`compose.test.yaml`（test）→ `compose.embedding.cpu|gpu.yaml`；**不会**加载任何 `compose.embedding.cpu.mem*.yaml` overlay。
- `scripts/diagnostics/measure_tei_memory.sh` + `scripts/preflight/lib_tei_probe.sh`：经 `compose.sh --embedding=cpu` 启停；硬编码 `TEI_SPEC_MEM_LIMIT_BYTES=8589934592` / `mem_limit_human=8g`（DEV-003-002；`TOOLING_STATUS=VALID`）。
- `scripts/preflight/check_linux_host.sh`：Check 8 `CPU_MIN_GIB=12` / `CPU_REC_GIB=16`；Check 13a `MemTotal >= 10`（注释：ES 2g + TEI 8g）；Check 13b 字面绑定 8g。
- `scripts/start_embedding.sh`：硬编码失败文案含 `mem_limit=8g`。
- `tests/contract/test_compose_config_contract.py`：断言 CPU `mem_limit` ∈ `{8g, 8589934592}`。
- `tests/runtime_contract_gate/`：Layer B；fixture `fixtures/archived_conflict_evidence_v1.json` 期望 CONFLICT@8g。

### 4.2 当前缺失

- 对 `{10g,12g,16g}` 的**正式、可审计** clean-run characterization。
- **闭合**的 mem overlay 注入路径（probe 内显式多 `-f`；见 §5.3）。
- Check 13a 随 TEI limit 变化的**公式化**阈值（非死常量 10）。
- §3.18 #8 MemAvailable 与新 TEI limit 的同步决策（本计划选定 **方案 A**）。
- 经 Spec-OI 批准的新 CPU TEI memory contract 与规格正文同步。
- Layer B：**保留** historical CONFLICT fixture **并新增** PASS@`<NEW_LIMIT>` fixture（禁止覆盖改写 CONFLICT）。

### 4.3 与技术规格不一致之处（已证实冲突）

权威证据：`DEV-003-002` Task Plan §13「正式 runtime probe 证据」：

| 字段 | 值 |
|---|---|
| model | `BAAI/bge-m3` |
| revision | `57aacf8560157b7c1d4f771ce1a199877aeeec74` |
| dtype | `float32` |
| runtime | `ONNX CPU` |
| spec / container mem_limit | `8589934592`（8g） |
| rss_peak_warmup_bytes | `8589934592`（触顶） |
| rss_steady_state_bytes | `null` |
| health_ready | `false` |
| oom_killed | `true` |
| exit_code | `137` |
| time_to_failure_sec | `138` |
| 分类 | **A. container cgroup limit 不足**（host ~1007 GiB 充足） |

→ `RUNTIME_CONTRACT_STATUS=SPEC_RUNTIME_CONTRACT_CONFLICT`。§3.10.3 / §3.18 #12 字面 `8g` 与该 profile warm-up 峰值不可同时成立。

### 4.4 前置任务检查

| 前置 | 状态 |
|---|---|
| DEV-003 | completed |
| DEV-003-002 | completed；tooling VALID；contract CONFLICT |
| git | `main` @ `2356a85`；规划态文档本地未提交变更（只读确认）；无 feat 分支 |
| DEV-006 | PAUSED；不得触碰 |

## 5. 实现方案（批准后分相；本轮不执行）

### 5.0 分相总览

| Phase | 名称 | 目的 | 本轮 |
|---|---|---|---|
| **A** | Characterization | 有限 matrix 正式测量；产出决策输入表 | **不执行** |
| **B** | Spec / compose / preflight 修订 | 按 decision rule 写入选定 contract；同步 #8/#12/13a/13b/`start_embedding` | **不执行** |
| **C** | Contract gate 重验 | 新 limit PASS fixture + evidence；更新 OI 决议与 DEV-006 R2–R4 技术门 | **不执行** |

Phase 边界：A **不得**修改权威规格正文中的正式 `mem_limit` 为最终值（仅 characterization-only overlay）；B 才改正式 Contract；C 验证 B。

---

### 5.1 根因（必须写入实施记录）

**根因陈述**：规格与 compose 冻结的 CPU TEI `mem_limit=8g`，不足以容纳 `BAAI/bge-m3` @ `57aacf…`、`dtype=float32`、`ONNX CPU`、pinned TEI digest 在 warm-up 阶段的 RSS 峰值；cgroup 触顶 → `OOMKilled=true` / `exit_code=137` / `health_ready=false`。宿主机物理内存充足 → **分类 A**（引用 DEV-003-002 §13）。

本 Spec-OI **不**重新争辩分类；若 Phase A 复现与 §13 矛盾，必须 HALT 并报告（不得静默改分类）。

---

### 5.2 Characterization matrix（有限；非无限扫描）

#### 固定不变（Controlled constants）

| 维度 | 固定值 |
|---|---|
| model | `BAAI/bge-m3` |
| revision | `57aacf8560157b7c1d4f771ce1a199877aeeec74` |
| dtype | `float32` |
| runtime | `ONNX CPU` |
| TEI image | `versions.lock.env` 中 `TEI_CPU_IMAGE` digest（pinned；不得 `--update`） |
| model cache | warmed `embedding-model-cache` volume（保持命中；禁止冷启动作为正式档） |
| proxy | `PROXY__HTTP_URL=""`（与 DEV-003-002 probe 一致） |
| host | 同一开发主机（分类 A 前提） |
| cpus / batch / concurrency | 保持 `compose.embedding.cpu.yaml` 现有值 |
| timeout | warm-up/ready 观察窗 **300s**（与现 probe 一致） |
| stack | **dev**（`compose.override.yaml`；与现 `tei_probe_start_cpu`→`compose.sh` 默认一致） |

#### 唯一变量

| 变量 | 候选集合 | 期望 HostConfig.Memory（字节） |
|---|---|---|
| container cgroup `mem_limit` | **`{8g, 10g, 12g, 16g}`** | `8589934592` / `10737418240` / `12884901888` / `17179869184` |

**微调论证**：集合来自 DEV-003-002 Amendment 001 §H 预留设计；覆盖「确认 8g 失败 → 小步上探 → 上界 16g」。**禁止**增加 9g/11g/… 或 >16g（含 20g+），除非本任务 HALT 后另开 Spec-OI。

#### 每档采集字段（强制）

每条正式 run 必须写入可审计 JSON + Task Plan §13 摘要表：

1. `rss_peak_warmup_bytes`
2. `rss_steady_state_bytes`（未达 steady 则 `null`，禁止伪造）
3. `health_ready`
4. `oom_killed`
5. `exit_code`
6. `time_to_ready_sec`（未 ready 则 `null`）
7. `time_to_failure_sec`（成功则 `null`）

**审计元数据（强制；非决策唯一变量）**：`run_id`、`requested_limit`、`actual HostConfig.Memory`（=`container_mem_limit_bytes`）、`model_id`/`revision`/`dtype`/`runtime`、`tei_image`/`image_digest`、host `MemTotal`/`MemAvailable`、`clean_create=true`、`invalidation_reason`（仅作废 run 填写；有效 run 为 `null`）。

#### Clean run / Viable / NON_VIABLE / 作废（SF-3 强化）

**Clean run**（正式、可计入该档的有效样本）必须同时满足：

1. **禁止** `docker update`（含 memory）作为该 run 的配置手段或 evidence 来源。
2. 使用 **§5.3 写死的唯一注入路径**（characterization overlay + probe 内显式多 `-f`）；override 在 `compose up` **之前**已定稿。
3. 每次 run 前：embedding-service **destroy + recreate**（同 `-f` 链 `down`/`up -d --force-recreate`）；确认 `HostConfig.Memory` **字节精确等于**目标；否则该 run **作废**（非 NON_VIABLE 判定样本）。
4. 复用 DEV-003-002 probe 采样语义（约 1s RSS 采样；区分 warm-up peak vs steady-state）。
5. evidence schema 完整；否则 **作废**。

**同档有效次数**：每档 **恰好 2** 次 clean formal runs。总有效正式 run 上界 = **8**。

**作废（invalid）替换规则**：

- 仅当可证明的**无效条件**成立时，允许同档补跑 **至多 1 次**，并记录 `invalidation_reason`（例：`HostConfig.Memory mismatch`、`evidence schema incomplete`、`compose up failed before probe`）。
- **不得**因「结果不理想」作废。
- 作废 run **不**计入 Viable/NON_VIABLE 样本；替换后该档仍须凑满 2 次有效 clean runs（若补跑仍作废 → HALT 报告，不得无限重试）。

**NON_VIABLE(C)**（该档不可行；Round 1 SF-3 + **Round 2 SF-3**）：若该档 **任意一次**有效 clean run 出现以下任一，则整档 **NON_VIABLE**（禁止用另一次 PASS 择优）：

- `oom_killed == true`
- `health_ready == false`（观察窗结束）
- `timed_out == true` / 超过 300s 未 ready
- unexpected exit（含 `exit_code == 137` 或容器非预期退出）
- incomplete measurement fields（若仍被误标为有效 → 应先作废；若已当作有效则整档 NON_VIABLE）
- **`rss_peak_warmup_bytes >= container_limit_bytes`（=`HostConfig.Memory` / 该档 `B(C)`）** — 即使 `health_ready` 尚未明确失败、或未观察到 OOM，peak **触顶或超过** cgroup limit → 该档 **不得** Viable（Round 2 **SF-3**）

**Viable(C)**：该档 **全部 2 次**有效 clean runs 均满足 §5.4 成功条件（且非整档 NON_VIABLE）。

对 **8g**：DEV-003-002 §13 归档证据可计为 **历史 Run-0（引用，不计本任务 2 次配额）**；Phase A 仍须完成 **2 次本任务正式 clean recreate** 于 8g。

---

### 5.3 正式运行方式（MF-1 闭合；反 docker-update；compose.sh 黑名单）

#### 5.3.1 唯一正式注入方案（写死）

**采用**：**characterization overlay + probe 内显式多 `-f`**。  
**不采用**：`docker update`；shell 临时手工改现有 compose；不同 run 使用不同/不可追溯启动方式；**不修改** `scripts/compose.sh`。

| 档 | Overlay | 说明 |
|---|---|---|
| **8g** | **无额外 overlay** | base `compose.embedding.cpu.yaml` 已含 `mem_limit: 8g` |
| **10g** | `compose.embedding.cpu.mem10g.yaml` | **仅** `services.embedding-service.mem_limit: 10g` |
| **12g** | `compose.embedding.cpu.mem12g.yaml` | **仅** `services.embedding-service.mem_limit: 12g` |
| **16g** | `compose.embedding.cpu.mem16g.yaml` | **仅** `services.embedding-service.mem_limit: 16g` |

Overlay 文件内容形态（示意；实施时字面一致）：

```yaml
services:
  embedding-service:
    mem_limit: 10g   # 或 12g / 16g
```

#### 5.3.2 Base compose 文件列表与顺序（与仓库真实 probe/dev 栈对齐）

只读确认：日常生产路径 `tei_probe_start_cpu` / `compose.sh --embedding=cpu`（`--stack=dev` 默认）的 `-f` 展开为：

```text
-f compose.yaml
-f compose.override.yaml
-f compose.embedding.cpu.yaml
```

**env-file 规则（Round 2 SF-4；与 `scripts/compose.sh` 对齐；写死）**：

| 文件 | 规则 |
|---|---|
| `.env` | **必选**；缺失 → fail-closed（与 `compose.sh` 一致） |
| `versions.env` | **仅存在时**加入 `--env-file` |
| `versions.lock.env` | **仅存在时**加入 `--env-file` |
| `.runtime/embedding.env` | **仅存在时**加入 `--env-file` |

不得因 characterization 使用不同 env-file 语义引入额外变量或额外必选文件。

外加进程环境（与现 probe 一致；非 env-file）：`PROXY__HTTP_URL=""`、`EMBEDDING_EFFECTIVE_RUNTIME_MODE=cpu`、`EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET=4096`（见 `tei_probe_with_embedding_env`）。

**Phase A 正式 characterization 启动/停止（Round 2 SF-1；写死）**：

- **全部档位**（含 **N=8**）**必须一律**走同一 `lib_tei_probe.sh` helper 构建的多 `-f` 链（由 `measure_tei_memory.sh --mem-limit=` 驱动）。
- **删除**「N=8 可走 `compose.sh`」双路径；**不得**保留 `compose.sh` 等价可选路径；**不得**混用 helper / `compose.sh` / 手工 `docker compose`。
- N=8：同一 helper，**不**附加 mem overlay；N∈{10,12,16}：同一 helper + 对应 mem overlay。

```text
# 环境与 compose.sh 对齐；env-file 规则见上表（SF-4）
PROXY__HTTP_URL="" \
EMBEDDING_EFFECTIVE_RUNTIME_MODE=cpu \
EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET=4096 \
docker compose \
  -f compose.yaml \
  -f compose.override.yaml \
  -f compose.embedding.cpu.yaml \
  [-f compose.embedding.cpu.mem{N}g.yaml] \   # 仅当 N∈{10,12,16}；N=8 不加
  --env-file .env \                          # 必选
  [--env-file versions.env] \                # 仅存在时
  [--env-file versions.lock.env] \           # 仅存在时
  [--env-file .runtime/embedding.env] \      # 仅存在时
  up -d --force-recreate embedding-service
```

Teardown 使用**相同** `-f` / `--env-file` 链 + `down embedding-service`，并清理残留 `name=embedding-service` 容器（保持现 `tei_probe_stop_cpu` 语义）。

#### 5.3.3 HostConfig.Memory 验证 / volume / 唯一变量

| 项 | 规则 |
|---|---|
| HostConfig.Memory | `docker inspect` 后必须 **字节精确**等于该档映射表；否则 run **作废** |
| `embedding-model-cache` | overlay **不**改 volumes；复用 base cpu yaml 的 named volume；正式 run 要求 warmed |
| 唯一变量 | 跨档差异**仅** `services.embedding-service.mem_limit`；禁止顺带改 cpus/command/env/image |
| 禁止 | `docker update`；手工编辑运行中容器；Phase A 改 `compose.embedding.cpu.yaml` 正式字面为非 8g |

#### 5.3.4 为何不需要改 `compose.sh`（SF-4 → 黑名单）

1. `compose.sh` 是日常/生产唯一 wrapper（§3.10.2）；其 `-f` 集合**有意**固定为 yaml+override+embedding profile，**无** mem overlay 钩子。
2. Characterization 是 **probe 专属、临时多档**测量；把 overlay 注入 `compose.sh` 会污染默认启动语义或引入未审计 CLI 旋钮。
3. Phase B 将最终 `MEMORY_LIMIT_DECISION` **烘焙**进 `compose.embedding.cpu.yaml` 后，日常路径继续 `compose.sh --embedding=cpu` / `start_embedding.sh` **无需** mem overlay。
4. 因此：**`scripts/compose.sh` 列入本任务永久黑名单**；characterization **不得**修改该文件。

若未来有人主张必须改 `compose.sh`：须新 Amendment 论证必要性、移出黑名单、最小改动 + contract tests——**本 Amendment 001 明确不采纳**。

| 允许 | 禁止 |
|---|---|
| §5.3.2 helper 内显式 `docker compose` 多 `-f` + mem overlay（**含 N=8**） | `docker update --memory=…` |
| Phase A 创建 `compose.embedding.cpu.mem{10,12,16}g.yaml` | 修改 `scripts/compose.sh` |
| `measure_tei_memory.sh --mem-limit=` → **一律**调用同一 helper | Phase A 任何档位走 `compose.sh` / 手工 docker / update（含「N=8 等价」可选路径） |
| Phase B 烘焙正式 limit 到 `compose.embedding.cpu.yaml` 后，**日常生产**回 `compose.sh` | 把未授权实验笔记当作 Contract |
| env-file：`.env` 必选；其余三文件仅存在时加入（SF-4） | characterization 另设必选 env-file 或注入额外变量 |

---

### 5.4 Decision rule（选择最终 memory limit）

定义候选 `C ∈ {8g, 10g, 12g, 16g}`，字节 `B(C)`。

**Viable(C)** 当且仅当该档 **2 次**有效 clean runs **全部**满足：

- `oom_killed == false`
- `health_ready == true`
- `exit_code == 0`（或容器仍在跑且 Healthy；不得为 137）
- `rss_peak_warmup_bytes` 有值且 **严格** `< B(C)`（未触顶；`>= B(C)` → NON_VIABLE，见 §5.2 Round 2 SF-3）
- `time_to_ready_sec` 有值且 `≤ 300`
- `rss_steady_state_bytes` 非 null（达 ready 后采样得到）

令 `P(C) = max(rss_peak_warmup_bytes over 有效 runs of C)`（仅 Viable 档计算）。

**选择规则（按序）：**

1. 丢弃全部 NON_VIABLE / 非 Viable 档。
2. 在 Viable 档中，仅保留满足 **§5.5 safety margin** 的档。
3. 在剩余档中选择 **最小** `C`（最小充分原则；禁止无故跳到 16g）。
4. 若 **无** 档满足（含 16g 仍不足）→ **HALT**：`MEMORY_LIMIT_DECISION=UNRESOLVED`；**禁止**扩展到 20g+；报告人类；不写正式 Contract。
5. 选定后记 `MEMORY_LIMIT_DECISION=<C>` 与完整决策表；进入 Phase B。

**明确**：历史 16g `docker update` 轶事 **零权重**，不得进入步骤 1–3。

---

### 5.5 Safety margin 规则

对候选 `C`（Viable）要求：

```text
headroom_bytes = B(C) - P(C)
required_headroom = max(1610612736, ceil(0.15 * B(C)))
  # max(1.5 GiB, 15% of mem_limit)
headroom_bytes >= required_headroom
```

| 规则点 | 说明 |
|---|---|
| 为何 15% | warm-up 峰值接近 cgroup 时仍可能抖动；百分比随 limit 放大 |
| 为何另设 1.5 GiB 地板 | 小档（10g）上纯百分比可能偏紧；绝对地板降低触顶复发风险 |
| steady-state | 另记录；**决策主键仍为 warm-up peak**（与 CONFLICT 根因一致） |
| 触顶即失败 | `rss_peak == B(C)` 或 OOM → NON_VIABLE，不适用 margin |

---

### 5.6 最终 contract 类型（推荐；Round 1 SF-2 + Round 2 SF-2）

| 类型 | 含义 | 本任务推荐 |
|---|---|---|
| 固定值 | §3.10.3 / compose 写死单一 `mem_limit` | **采用（作为载体）** |
| configurable | 运维可经 env 任意改 limit 而不经 Spec-OI | **拒绝** |
| model-runtime-profile-specific | limit 绑定「bge-m3 + float32 + ONNX CPU + pinned TEI」profile | **采用（作为语义）** |

**推荐组合（明确）**：

> **model-runtime-profile-specific 固定值**：在规格中写明该 `mem_limit` 仅适用于当前 MVP CPU profile（model/revision/dtype/ONNX CPU/TEI digest 约束）；compose 与 Preflight 使用该**固定**字面值；**不**提供自由 `MEM_LIMIT` 配置旋钮。未来变更 profile → 新 OI + 新 matrix。

#### Round 2 SF-2 — §3.10.3 **唯一**规格句式（Phase B 必改；禁止二选一）

Phase B 对 §3.10.3 采用**唯一**规格句式（不得保留含糊「或」句 / 双路径读法）：

1. **CPU TEI memory limit 是 model-runtime-profile-specific fixed contract**（绑定当前 MVP CPU profile）。
2. **任何低于正式 contract 的 override**（含环境变量、临时 compose overlay、手工 `docker update` 等）→ **`NON_SPEC_COMPLIANT`**（unsupported；不得视为 spec-compliant）。
3. **删除**「可通过环境变量调低且仍合规」及一切等价含糊表述；**不再保留**「收窄为非 mem_limit 参数 **或** 写明调低=non-compliant」二选一句式——统一为上述唯一句式。
4. Preflight / probe / Check 13b **始终按规格字面 `mem_limit`** 验证；发现实际 `HostConfig.Memory` ≠ 规格字面 → fail-closed。

**现状句**（§3.10.3，待删/改）：「CPU 参数是开发默认值，可以通过环境变量调低，但不得改变模型、Revision、Pooling、Normalize、维度或单条输入上限。」——Phase B **必须**改为上述唯一句式，消除与固定 Contract 的歧义。

GPU §3.10.4 `mem_limit: 8g`：**本任务不修订**（无 GPU characterization 授权）。

---

### 5.7 Check 13a 数值公式（MF-2）

#### 职责边界

| Check | 度量 | 职责 |
|---|---|---|
| **Check 8**（§3.18 #8/#9） | `/proc/meminfo` **MemAvailable** | 开发环境共同开销门槛（TEI+ES+Mongo+Kafka+Neo4j+Redis+应用）；见 §5.8 |
| **Check 13a**（§3.18 #12 代理之一） | `/proc/meminfo` **MemTotal** | 宿主机总内存能否支撑 **容器 mem_limit 之和**（ES + TEI）的粗代理 |
| **Check 13b** | 真实 TEI cgroup warm-up | 在正式 `mem_limit` 下探针 PASS/FAIL |

#### Exact formula（写死）

```text
ES_LIMIT_GIB = 2
  # 来源：§3.18 #12 / compose ES mem_limit: 2g
TEI_LIMIT_GIB = <MEMORY_LIMIT_DECISION 的 GiB 整数>
  # Phase B 后与 TEI_SPEC_MEM_LIMIT / compose.embedding.cpu.yaml 一致
HOST_RESERVE_GIB = 0
  # 理由：13a 仅验证「Docker 能提供两容器 cgroup 之和」的 MemTotal 代理；
  # 全栈可用内存余量由 Check 8（MemAvailable）负责，职责分离，避免双重加垫导致阈值漂移不可审计

required_host_mem_gib = ES_LIMIT_GIB + TEI_LIMIT_GIB + HOST_RESERVE_GIB
# 例：TEI=8 → 10；TEI=12 → 14；TEI=16 → 18
```

验收断言：`host_mem_total_gib >= required_host_mem_gib`。

#### 硬编码 10 的迁移

| 阶段 | Check 13a 行为 |
|---|---|
| 现状 | `MemTotal >= 10`（隐含 2+8） |
| Phase A | **不改**正式 Check 13a 阈值（仍 8g contract）；characterization 不依赖放宽 13a |
| Phase B | 将死常量 `10` 替换为 `required_host_mem_gib = 2 + TEI_LIMIT_GIB`；文案同步「ES 2g + TEI `<D>`g」 |
| TEI_LIMIT_GIB 来源 | **常量**（与 `lib_tei_probe.sh` 的 `TEI_SPEC_MEM_LIMIT_BYTES` / 人类可读 `TEI_SPEC_MEM_LIMIT=Dg` 同源）；**不**在 Check 13a 运行时解析 YAML（避免 shell YAML 脆弱性）。Contract tests **必须**断言：compose `mem_limit` ↔ 该常量 ↔ Check 13a 公式输入一致 |

#### 测试

- Unit/contract：对 `TEI_LIMIT_GIB ∈ {8,10,12,16}` 映射 `required_host_mem_gib`；Phase B 后固定为决策值。
- `tests/unit/test_preflight_tei_probe_contract.py` 等：文案/常量不再写死「8g / 10」为唯一合法值。

---

### 5.8 §3.18 #8 MemAvailable 决策（MF-3）— **方案 A（修改）**

#### 当前 exact requirement

```yaml
preflight:
  cpu_mode:
    minimum_available_memory_gib: 12   # check_linux_host.sh: CPU_MIN_GIB=12
    recommended_available_memory_gib: 16  # CPU_REC_GIB=16
  gpu_mode:
    minimum_available_memory_gib: 8
    recommended_available_memory_gib: 12
```

§3.18 #9：该门槛覆盖 TEI、ES、MongoDB、Kafka、Neo4j、Redis 和应用容器的**开发环境共同开销**。

#### 与 mem_limit / MemTotal / MemAvailable 的关系

| 量 | 含义 |
|---|---|
| 容器 `mem_limit` | cgroup 硬顶（TEI / ES）；由 compose + Check 13b 验证 |
| Check 13a MemTotal | 能否分配 cgroup 之和的粗代理（§5.7） |
| Check 8 MemAvailable | 主机**当前可用**内存是否够整栈开发开销（含 TEI 占用倾向） |

当 TEI `mem_limit` 从 8 → `D` 上调时，若仍保留 CPU MemAvailable min=12 / rec=16，则相对原规格「共同开销」假设发生**规格漂移**（TEI 预算增加但主机可用门槛未动）。

#### 决策：**A — 修改**（推荐；本计划采纳）

**权威公式（唯一权威来源；所有示例 / 验收断言 / 测试设计数值必须与公式一致）**：

```text
# D = TEI_LIMIT_GIB（= MEMORY_LIMIT_DECISION 的 GiB 整数）
CPU_MIN = 12 + (D - 8)
CPU_REC = 16 + (D - 8)
# 等价写法：
# delta = D - 8
# cpu_min' = 12 + delta
# cpu_rec' = 16 + delta
```

**查表仅为公式展开示例，不是第二权威**。若查表与公式冲突，以公式为准并修正查表。

| TEI_LIMIT_GIB (D) | CPU_MIN_GIB | CPU_REC_GIB |
|---|---|---|
| 8（现状） | 12 | 16 |
| 10 | 14 | 18 |
| 12 | **16** | 20 |
| 16 | 20 | 24 |

核对：`D=12` → `CPU_MIN = 12 + (12-8) = 16`；`CPU_REC = 16 + 4 = 20`。**禁止**「TEI=12 → min=14」类错误（旧查表笔误；Amendment 002 已修正）。

**GPU 门槛：默认不改**（无本任务 GPU matrix；除非另开 Amendment 论证）。

**Phase B whitelist 纳入**：规格 §3.18 #8 YAML、`check_linux_host.sh` 的 `CPU_MIN_GIB`/`CPU_REC_GIB`、相关 unit/contract（若有断言）、`README.md` 中对应说明——数值须由公式算出，不得手抄错误查表。

**若选 B 的反证要求**（本计划不采用）：须证明新 TEI limit 与旧 12/16 不自相矛盾——当前认为无法给出不漂移的可验收理由，故拒绝 B。

---

### 5.9 Layer B fixture 策略（MF-4）

白名单显式包含：`tests/runtime_contract_gate/fixtures/**`

| 规则 | 说明 |
|---|---|
| 1 | **保留**历史 8g → `SPEC_RUNTIME_CONTRACT_CONFLICT` fixture：`archived_conflict_evidence_v1.json`（或等价路径）；**禁止**覆盖改成 PASS |
| 2 | **新增**最终 contract `<NEW_LIMIT>` → `PASS` fixture（例：`approved_pass_evidence_v1.json`；字段齐全；`spec_mem_limit_bytes=B(DECISION)`） |
| 3 | Layer B 测试必须**同时**能验证：historical conflict evidence **与** current approved contract evidence |
| 4 | 不得删除 CONFLICT 回归；`test_archived_conflict_evidence_schema_and_verdict` 语义保留 |

---

### Step A1 — 扩展测量工具（Phase A；参数化唯一变量 + §5.3 helper）

- 文件：`scripts/preflight/lib_tei_probe.sh`；`scripts/diagnostics/measure_tei_memory.sh`；**必建** `compose.embedding.cpu.mem{10,12,16}g.yaml`
- 输入：`--mem-limit=8g|10g|12g|16g`；固定 constants 见 §5.2
- 行为：**全部档位（含 8g）一律**按 §5.3 同一 helper 构建 `-f` 链（Round 2 SF-1）；env-file 按 SF-4（`.env` 必选；其余仅存在时）；`up -d --force-recreate`；inspect Memory 字节断言；采样；teardown 同链
- 输出：每 run JSON（§5.2 强制字段 + 审计元数据）
- 错误处理：schema 不完整 / Memory 不匹配 → run 作废；禁止 fallback 到 `docker update`、改 `compose.sh`、或 N=8 改走 `compose.sh`
- 幂等：每次 clean recreate；不依赖旧容器状态

### Step A2 — 执行 matrix 并归档

- 按 §5.2 跑满 4×2=8 有效正式 run（加合法作废替换）；红acted 摘要写入本 Task Plan §13
- 应用 §5.4–§5.5 → `MEMORY_LIMIT_DECISION`（或 UNRESOLVED HALT）
- **不得**在本步修改规格正文正式 Contract / Check 8 常量

### Step B1 — 规格修订

- 文件：`01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`
- 范围：
  - §3.10.3 CPU `mem_limit` → 决策值 + profile-specific 固定值说明
  - §3.10.3「环境变量调低」句 → **Round 2 SF-2 唯一句式**（fixed contract；低于 formal contract 的 override → `NON_SPEC_COMPLIANT`；删除含糊/二选一）
  - §3.18 #8 CPU MemAvailable min/rec → **方案 A 权威公式** `CPU_MIN/REC = 12/16 + (D-8)`（查表仅示例）
  - §3.18 #12「TEI … 8g」→ 选定值
  - Preflight 文案若仍写死「TEI 8g」则同步
- **不**改 ES 2g、GPU #8/#12、模型/Revision/dtype/API Contract/错误码/状态机

### Step B2 — Compose / Preflight / Contract 测试对齐

- `compose.embedding.cpu.yaml`：`mem_limit: <DECISION>`
- `lib_tei_probe.sh`：`TEI_SPEC_MEM_LIMIT_BYTES` / `mem_limit_human` 对齐决策；Phase A helper 路径保留；正式默认 limit 对齐决策值（日常生产仍经 `compose.sh`，characterization 不走 `compose.sh`）
- `check_linux_host.sh`：Check 13a 公式（§5.7）；Check 13b 文案；**CPU_MIN_GIB/CPU_REC_GIB**（§5.8 A）
- `scripts/start_embedding.sh`：**若 `MEMORY_LIMIT_DECISION ≠ 8g`，Phase B 必改**所有硬编码 `8g` / `8 GiB` / `8589934592` 相关错误文案/判断（SF-1；非「仅当需要」）
- `tests/contract/test_compose_config_contract.py` 断言新值
- `tests/unit/test_preflight_tei_probe_contract.py` 及 probe unit：13a/13b/常量对齐
- `tests/runtime_contract_gate/**` + `fixtures/**`：保留 CONFLICT；新增 PASS fixture（MF-4）
- `README.md`：探针/内存合同/MemAvailable 说明同步
- 清理 Phase A 多余 overlay：正式值已写入主 cpu yaml 后，删除或停止引用 `mem{10,12,16}g` 中与正式值重复/未选中的文件（避免矩阵污染默认启动；若保留须文档标明 characterization-only 且不被 `compose.sh` 加载）

### Step C1 — 新 contract 正式验证

- 在 **正式** compose（无 docker update、无临时 overlay）上：`measure_tei_memory.sh` → `runtime_contract_verdict=PASS`
- Preflight `--mode=cpu` Check 13b exit 0（发布证据须真实跑通一次）
- `./scripts/start_embedding.sh cpu` 无 OOM
- Layer B：CONFLICT fixture + PASS fixture 双绿
- 更新 `open_issues.md` OI-011 → `resolved`（追加决议；不覆盖历史）
- 更新 progress：`runtime_contract_status` → 新约定值；`dev006_dependency_status` 对 R2–R4 技术项标记可恢复（R5–R7 仍待 DEV-006 流程）

### Step C2 — DEV-006 交接（不实施 DEV-006）

- 仅文档：确认 §15' resume 条件；**禁止** merge PR #13；**禁止**改 DEV-006 计划正文（除非另任务）

## 6. 文件变更清单（proposed writable whitelist；精确路径）

### 6.1 Phase A（characterization）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `scripts/preflight/lib_tei_probe.sh` | 修改 | §5.3 helper；参数化 mem_limit；inspect 字节断言；禁止 docker update |
| `scripts/diagnostics/measure_tei_memory.sh` | 修改 | CLI `--mem-limit=`；usage 声明禁止 docker update / 不改 compose.sh |
| `compose.embedding.cpu.mem10g.yaml` | **创建（必建）** | 仅 mem_limit: 10g |
| `compose.embedding.cpu.mem12g.yaml` | **创建（必建）** | 仅 mem_limit: 12g |
| `compose.embedding.cpu.mem16g.yaml` | **创建（必建）** | 仅 mem_limit: 16g |
| `tests/unit/test_tei_memory_probe.py` | 修改 | 多档参数 / Memory 期望 / 作废语义 |
| `tests/unit/test_tei_probe_mocked_paths.py` | 修改 | mock 路径不绑定死 8g-only |
| `02_开发管理/tasks/OI-011-bge-m3-cpu-tei-memory-contract.md` | 修改 | §13 归档 matrix |
| `02_开发管理/progress.md` | 修改 | 阶段状态 |
| `02_开发管理/master_plan.md` | 修改 | 状态备注 |

### 6.2 Phase B–C（contract 落地）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` | 修改 | §3.10.3 mem_limit + SF-2 句；§3.18 #8（方案 A）；§3.18 #12 |
| `compose.embedding.cpu.yaml` | 修改 | 正式 `mem_limit` |
| `scripts/preflight/check_linux_host.sh` | 修改 | Check 13a 公式；13b 文案；`CPU_MIN_GIB`/`CPU_REC_GIB` |
| `scripts/preflight/lib_tei_probe.sh` | 修改 | `TEI_SPEC_MEM_LIMIT_*` 最终值；默认正式启动路径 |
| `scripts/diagnostics/measure_tei_memory.sh` | 修改 | 默认正式 limit |
| `scripts/start_embedding.sh` | **修改（SF-1 必改，当 DECISION≠8g）** | 所有 8g/8 GiB/8589934592 文案与判断对齐决策值；保持 fail-closed；不引入 escalation |
| `tests/contract/test_compose_config_contract.py` | 修改 | 断言新 mem_limit |
| `tests/unit/test_preflight_tei_probe_contract.py` | 修改 | 13a/13b/#8 期望对齐 |
| `tests/unit/test_tei_memory_probe.py` | 修改 | 最终常量 |
| `tests/unit/test_tei_probe_mocked_paths.py` | 修改 | 最终常量 |
| `tests/runtime_contract_gate/test_tei_cpu_runtime_contract_gate.py` | 修改 | 双 fixture：CONFLICT + PASS |
| `tests/runtime_contract_gate/fixtures/**` | 修改/创建 | **保留** `archived_conflict_evidence_v1.json`；**新增** PASS@DECISION fixture（禁止覆盖 CONFLICT） |
| `README.md` | 修改 | 探针/内存合同/MemAvailable |
| `02_开发管理/open_issues.md` | 修改 | OI-011 决议记录 |
| `02_开发管理/tasks/OI-011-bge-m3-cpu-tei-memory-contract.md` | 修改 | 执行/结果 |
| `02_开发管理/progress.md` | 修改 | 状态机 |
| `02_开发管理/master_plan.md` | 修改 | CHANGE / 状态 |

### 6.3 永久黑名单（本任务）

| 路径/动作 | 原因 |
|---|---|
| **`scripts/compose.sh`** | **SF-4 / MF-1：不改；characterization 用 probe 内显式 `-f`** |
| `02_开发管理/tasks/DEV-006-*.md` | 不得修改 DEV-006 |
| `feat/DEV-006-*` / PR #13 | 不得触碰；不得 Merge |
| `src/memory_system/**` | 非本 Spec-OI 范围 |
| `compose.embedding.gpu.yaml` mem_limit | 无 GPU matrix 授权 |
| GPU §3.18 #8 门槛 | 默认不改 |
| `git merge` / `gh pr merge` / force push | 治理禁止 |
| 将 `docker update` 输出写入 evidence | 硬禁止 |
| 扩展矩阵至 20g+ | 硬禁止；16g 不足则 UNRESOLVED HALT |
| 覆盖改写 CONFLICT fixture 为 PASS | MF-4 禁止 |

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 适用（配置一致性） | Phase B 同一 PR 内规格 + compose + preflight(#8/#12/13a/13b) + start_embedding + contract/gate 对齐同一 `mem_limit` |
| 幂等 | 适用（测量） | clean recreate；重复 run 不累积容器侧状态 |
| 并发 | 不适用 | 单主机串行 matrix；禁止并行多档抢同一 embedding-service 名 |
| 版本冲突 | 适用 | pinned TEI digest；禁止 lock `--update` |
| 用户隔离 | 不适用 | 无多租户 API |
| 部分失败 | 适用 | 单 run 作废不污染其他档；NON_VIABLE 不择优；HALT 时不写正式 Contract |
| 进程异常恢复 | 适用 | OOM/137 记录字段后 teardown；不自动提限重试为「成功」 |

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| `--mem-limit` 解析 8/10/12/16g | 字节映射正确；非法值非零退出 |
| Memory inspect 不匹配 | run 作废路径（非 PASS） |
| mock OOM / healthy 多档 | verdict 与字段完整；NON_VIABLE 语义可测则覆盖 |
| Check 13a 公式 | `required = 2 + TEI_LIMIT_GIB`（HOST_RESERVE=0） |
| Check 8 方案 A | **公式权威**：`CPU_MIN = 12+(D-8)`；`CPU_REC = 16+(D-8)`；例 D=12 → 16/20（禁止 min=14） |
| NON_VIABLE peak 触顶 | `rss_peak_warmup_bytes >= container_limit_bytes` → NON_VIABLE（Round 2 SF-3） |
| Phase A 启动路径 | 含 8g 一律 helper；无 compose.sh 可选分支（Round 2 SF-1） |
| env-file | `.env` 必选；versions*/embedding.env 仅存在时（Round 2 SF-4） |
| 拒绝 docker update 作为配置源 | help/注释契约存在禁令 |

### Contract Test

| 场景 | 预期 |
|---|---|
| `compose.embedding.cpu.yaml` mem_limit | Phase B 后等于 `MEMORY_LIMIT_DECISION` |
| 规格示例 YAML 与 compose 一致 | 无陈旧 8g 残留（若决策非 8g） |
| Preflight 常量与 compose/probe 同源 | 13a/13b/#8 一致 |
| SF-2 | 规格采用唯一句式：fixed contract；低于 formal contract 的 override → `NON_SPEC_COMPLIANT`；无「可调低仍合规」 |

### Integration / Runtime gate

| 场景 | 预期 |
|---|---|
| Layer B @ CONFLICT fixture | 仍为 `SPEC_RUNTIME_CONTRACT_CONFLICT`（历史） |
| Layer B @ PASS fixture | `runtime_contract_verdict=PASS` @ DECISION |
| 默认 CI | 仍不强制每次真实 TEI；真实 PASS 证据人工/受监督归档 |

### E2E Test

| 场景 | 预期 |
|---|---|
| 不适用完整产品 E2E | 本任务以 matrix + Preflight/start_embedding 为验收 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 模拟 inspect Memory 不匹配 | run 作废，非 PASS |
| 禁止并行两档 | 文档约束；不做多容器同名并发 |
| 同档 1 PASS + 1 FAIL | **不得**标 Viable（SF-3） |

## 9. 验收标准

- [ ] Task ID=`OI-011`；与 `open_issues.md` OI-011 绑定
- [ ] Phase A：`{8g,10g,12g,16g}` 每档 **2** 正式 clean run；字段 7 项 + 审计元数据齐全；**无** docker update 正式 evidence；**一律** §5.3 helper 多 `-f`（含 8g；无 compose.sh 双路径；Round 2 SF-1）
- [ ] Round 2 SF-4：env-file 与 `compose.sh` 对齐（`.env` 必选；`versions.env`/`versions.lock.env`/`.runtime/embedding.env` 仅存在时）；未引入额外变量
- [ ] SF-3（R1+R2）：无「1 PASS + 1 FAIL 择优」；NON_VIABLE 含 `rss_peak_warmup_bytes >= container_limit_bytes`；invalid 替换 ≤1/档且有 `invalidation_reason`
- [ ] §5.4–§5.5 决策表完整；`MEMORY_LIMIT_DECISION` 有值或正式 `UNRESOLVED` HALT（禁 20g+）
- [ ] Phase B：规格 §3.10.3（Round 2 SF-2 唯一句式）、§3.18 #8（方案 A **公式权威**；D=12→min=16/rec=20）、§3.18 #12、`compose.embedding.cpu.yaml`、probe/Preflight 13a 公式/13b、contract 测试对齐决策值
- [ ] Round 1 SF-1：若 DECISION≠8g，`start_embedding.sh` 硬编码 8g 文案/判断已改
- [ ] Round 1 SF-4：`scripts/compose.sh` **未**被本任务修改
- [ ] MF-4：CONFLICT fixture 保留；PASS fixture 新增；Layer B 双验证
- [ ] Contract 类型落实为 **model-runtime-profile-specific 固定值**；低于 formal contract 的 override → `NON_SPEC_COMPLIANT`
- [ ] Phase C：新 limit 下 `measure_tei_memory.sh` PASS；Check 13b 与 `start_embedding.sh cpu` 技术门可通过
- [ ] OI-011 决议已追加；`RUNTIME_CONTRACT_STATUS` 不再为阻塞 DEV-006 R2 的 CONFLICT（或等价已验证状态）
- [ ] **未**修改 DEV-006 计划/feat；**未** Merge PR #13
- [ ] 对应测试（unit/contract/gate）通过；Ruff/Mypy 通过
- [ ] Review 无 P0/P1

## 10. 风险与阻塞项

| 项 | 说明 |
|---|---|
| 设计文档冲突 | 本任务**预期**修订规格；须 PLAN_APPROVED 后按白名单改字面，禁止顺带改 API/Schema |
| 16g 仍不足 | HALT UNRESOLVED；新 Spec-OI 扩展矩阵；禁止 silent 再提限 / 20g+ |
| 工具硬编码 8g | Phase A 必须先参数化 + §5.3 helper，否则无法正式测 10/12/16g |
| compose.sh 漂移 | 黑名单；helper 须与 compose.sh 的 `-f`/env-file 规则保持对齐（SF-4：`.env` 必选；其余仅存在时） |
| Phase A 双路径 | 已禁止；含 8g 一律 helper（R2 SF-1） |
| MemAvailable 查表笔误 | Amendment 002 已修；公式权威 |
| DEV-006 压力 | 保持 PAUSED；人类不得要求本任务顺手 merge #13 |
| 缓存未 warmed | 冷启动峰值可能偏离；正式 run 要求 warmed cache |
| MemAvailable 上调 | 方案 A 可能使低内存开发机 Check 8 更严——属预期规格诚实性，不回退 B |
| GPU 误改 | 黑名单 |

## 11. Git 计划

```yaml
branch: "feat/OI-011-bge-m3-cpu-tei-memory-contract"
workflow_mode: NORMAL
expected_commits:
  - "docs(plan): add OI-011 bge-m3 cpu tei memory contract plan"
  - "feat(tei-probe): parameterize cpu mem_limit characterization matrix"
  - "docs(spec): update cpu tei mem_limit contract for bge-m3 onnx profile"
  - "fix(docker): align compose preflight and contracts to new tei mem_limit"
out_of_scope_changes:
  - "DEV-006 任何文件/分支/PR #13"
  - "scripts/compose.sh"
  - "GPU mem_limit / GPU MemAvailable 门槛"
  - "src/memory_system/**"
  - "docker update evidence"
  - "无关 DEV-OPS / STM / EXT / RET"
release_phases:
  PLAN_LANDING: "docs(plan) on main → create exact feat from updated main"
  IMPLEMENTATION_RELEASE: "feat only；gh pr create；禁 push main"
  POST_MERGE_CLEANUP: "仅 PR MERGED 后；docs(status): complete；删 exact feat"
```

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001 — Plan Remediation Round 1

```yaml
amendment_id: Amendment-001
date: "2026-08-09 01:45 UTC"
trigger: "Plan Review Round 1 — PLAN_REJECTED（BLOCKER=0；MUST_FIX=4；SHOULD_FIX=4）"
status: approved
affects_technical_spec: true  # 计划层明确 Phase B 将改规格；本轮仅修订计划
```

#### MF / SF 吸收表

| ID | 原问题 | 本 Amendment 落点 | 状态 |
|---|---|---|---|
| **MF-1** | compose override 注入路径未闭合；compose.sh 不加载 mem overlay | **§5.3**：唯一方案 = overlay + probe 内显式多 `-f`；base 顺序对齐 compose.sh；Memory 字节断言；teardown 同链；volume 复用；**不改 compose.sh** | **已吸收** |
| **MF-2** | Check 13a 死常量 10 | **§5.7**：`required_host_mem_gib = 2 + TEI_LIMIT_GIB + 0`；常量同源；职责 vs 13b/#8 | **已吸收** |
| **MF-3** | §3.18 #8 MemAvailable 未决策 | **§5.8 方案 A**：`cpu_min/rec += (TEI_LIMIT_GIB-8)`；GPU 不改；whitelist 含规格/#8 常量/tests/README | **已吸收** |
| **MF-4** | Layer B fixture / whitelist | **§5.9** + §6.2：`fixtures/**` 白名单；保留 CONFLICT；新增 PASS；禁覆盖 | **已吸收** |
| **SF-1** | `start_embedding.sh` 硬编码 8g | §6.2 / Step B2：**DECISION≠8g 时必改**（非可选） | **已吸收** |
| **SF-2** | §3.10.3 env 调低 vs 固定 mem_limit | **§5.6**：mem_limit 固定 Contract；不可 env 调低仍合规；Phase B 改规格句 | **已吸收** |
| **SF-3** | 同档 2 runs 择优风险 | **§5.2**：任意一次失败 → 整档 NON_VIABLE；禁择优；invalid ≤1 + `invalidation_reason` | **已吸收** |
| **SF-4** | compose.sh 未黑名单 | **§6.3 / §5.3.4**：`scripts/compose.sh` 永久黑名单 | **已吸收** |

#### 相对初版的关键修改摘要

1. 将「可选 override / 或经 compose.sh」收紧为 **唯一可审计** probe 内 `-f` 链。
2. 写死 Check 13a / Check 8 公式与方案 A。
3. Layer B 双 fixture 策略与 whitelist。
4. Viable 判定与作废规则按 SF-3 强化。
5. 黑名单加入 `compose.sh`；`start_embedding.sh` 标必改。

### Amendment 002 — Plan Remediation Round 3

```yaml
amendment_id: Amendment-002
date: "2026-08-09 01:55 UTC"
trigger: "PLAN_REMEDIATION_ROUND_3 — MUST_FIX MF-3（§5.8 查表 TEI=12→min 错误）+ 吸收 Round 2 SHOULD_FIX SF-1～SF-4"
status: approved
affects_technical_spec: true  # 计划层明确 Phase B 将改规格；本轮仅修订计划
```

#### MF / SF 吸收表（Round 3）

| ID | 原问题 | 本 Amendment 落点 | 状态 |
|---|---|---|---|
| **MF-3（R3）** | §5.8 查表 `TEI_LIMIT_GIB=12` 行误写 `CPU_MIN=14`；与公式 `12+(D-8)` 冲突 | **§5.8**：权威公式 `CPU_MIN/REC = 12/16 + (D-8)`；查表仅为展开示例；`\| 12 \| 16 \| 20 \|`；全文禁止「TEI=12→min=14」；验收/测试数值跟公式 | **已吸收** |
| **SF-1（R2）** | Phase A 仍允许 N=8 走 `compose.sh` 双路径 | **§5.3.2 / Step A1**：含 8g **一律** `lib_tei_probe.sh` helper 多 `-f`；删除 compose.sh 等价可选路径 | **已吸收** |
| **SF-2（R2）** | §3.10.3 仍保留「或」二选一句式 | **§5.6**：唯一句式 = profile-specific fixed contract；低于 formal contract 的 override → `NON_SPEC_COMPLIANT`；删除含糊可调低表述 | **已吸收** |
| **SF-3（R2）** | NON_VIABLE 未显式含 peak 触顶 | **§5.2 / §5.4**：`rss_peak_warmup_bytes >= container_limit_bytes` → NON_VIABLE（即使 health 未明确失败） | **已吸收** |
| **SF-4（R2）** | env-file 语义与 `compose.sh` 不完全对齐 | **§5.3.2**：`.env` 必选；`versions.env` / `versions.lock.env` / `.runtime/embedding.env` 仅存在时加入；禁止 characterization 另引入变量 | **已吸收** |

#### 相对 Amendment 001 的关键修改摘要

1. 修正 MemAvailable 查表笔误；写死「公式权威 / 查表示例」。
2. Phase A 单一 helper 路径（含 8g）；删除 compose.sh 双路径。
3. §3.10.3 Phase B 唯一规格句式 + `NON_SPEC_COMPLIANT`。
4. peak 触顶显式进入 NON_VIABLE。
5. env-file 规则与 `compose.sh` 对齐。

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-09 01:30 UTC | Planner 初版 | 创建本计划；progress/master_plan/open_issues 规划态 | 无（规划） | 本轮不实施 |
| 2026-08-09 01:45 UTC | Amendment 001 | 吸收 Round 1 MF-1～MF-4 + SF-1～SF-4；闭合 §5.3/§5.7/§5.8/§5.9；更新白名单/黑名单 | 无（规划修订） | 待 Round 2 计划审查；仍不实施 |
| 2026-08-09 01:55 UTC | Amendment 002 | Round 3 remediation：MF-3 查表 12→16/20；吸收 R2 SF-1～SF-4（单一 helper、唯一 SF-2 句式、peak≥limit NON_VIABLE、env-file 对齐） | 无（规划修订） | 待 Round 3 计划审查；仍不实施 |
| 2026-08-09 02:00 UTC | PLAN_APPROVED + PLAN_LANDING | status→approved；Amendment 001/002→approved；human_plan_approved Round 3；同步 progress/master_plan/open_issues | 无（治理） | docs(plan) on main；创建 exact feat；plan_commit 禁 self-ref（报告内给出） |
| 2026-08-09 02:10 UTC | Developer Phase A1 | status→in_progress；创建 mem{10,12,16}g overlays；lib_tei_probe/measure 参数化 `--mem-limit`；一律 helper 多 `-f`（含 8g）；禁 compose.sh/docker update；unit 34 passed | unit 34 passed | 未改正式 contract；未跑真实 matrix |
| 2026-08-09 02:22 UTC | Developer Phase A2 | 串行 matrix 4×2 完成（无 invalid；无 docker update）；8g/10g NON_VIABLE；12g/16g Viable；**MEMORY_LIMIT_DECISION=12g** | 真实 TEI evidence `.runtime/oi011/` | peak@12g=10919954350；headroom=1964947538≥1932735284 |
| 2026-08-09 02:30 UTC | Developer Phase B–C | 规格/compose/preflight/start_embedding/tests/README/OI 决议落地 12g；删 mem12g overlay；保留 mem10g/mem16g characterization-only；Layer B 双 fixture；formal measure PASS；Check 13b PASS；start_embedding exit 0 | unit/contract/gate 52 passed + formal/13b/start PASS | compose.sh 未改；preflight 整脚本仍因既有 vm.max_map_count 非零；DEV-006/PR#13 未触碰 |

### 13.1 Characterization matrix 归档表（Phase A 填写）

| run_id | requested_limit | HostConfig.Memory | rss_peak_warmup_bytes | rss_steady_state_bytes | health_ready | oom_killed | exit_code | time_to_ready_sec | time_to_failure_sec | host_MemTotal | host_MemAvailable | clean_create | invalidation_reason | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oi011_8g_1 | 8g | 8589934592 | 8589934592 | null | false | true | 137 | null | 138 | 1081962123264 | 858326155264 | true | null | NON_VIABLE（OOM；peak触顶） |
| oi011_8g_2 | 8g | 8589934592 | 8589934592 | null | false | true | 137 | null | 140 | 1081962123264 | 856443715584 | true | null | NON_VIABLE（OOM；peak触顶） |
| oi011_10g_1 | 10g | 10737418240 | 10737418240 | 10734912842 | true | false | 0 | 206 | null | 1081962123264 | 838408617984 | true | null | NON_VIABLE（SF-3 peak≥limit） |
| oi011_10g_2 | 10g | 10737418240 | 10737418240 | 10734912842 | true | false | 0 | 212 | null | 1081962123264 | 845156069376 | true | null | NON_VIABLE（SF-3 peak≥limit） |
| oi011_12g_1 | 12g | 12884901888 | 10919954350 | 10919954350 | true | false | 0 | 190 | null | 1081962123264 | 857464373248 | true | null | Viable |
| oi011_12g_2 | 12g | 12884901888 | 10919954350 | 10919954350 | true | false | 0 | 198 | null | 1081962123264 | 858124042240 | true | null | Viable |
| oi011_16g_1 | 16g | 17179869184 | 10919954350 | 10919954350 | true | false | 0 | 204 | null | 1081962123264 | 851074232320 | true | null | Viable（非最小） |
| oi011_16g_2 | 16g | 17179869184 | 10919954350 | 10919954350 | true | false | 0 | 201 | null | 1081962123264 | 848785403904 | true | null | Viable（非最小） |

### 13.2 决策记录（Phase A 末填写）

```yaml
MEMORY_LIMIT_DECISION: 12g
P_selected_bytes: 10919954350
headroom_bytes: 1964947538
required_headroom_bytes: 1932735284  # max(1.5GiB, ceil(0.15*12g))
contract_type: "model-runtime-profile-specific-fixed"
check_13a_required_host_mem_gib: 14  # 2 + 12
cpu_min_gib_after_A: 16  # 12 + (12 - 8)
cpu_rec_gib_after_A: 20  # 16 + (12 - 8)
docker_update_used_in_formal_evidence: false
compose_sh_modified: false
tier_summary:
  8g: NON_VIABLE
  10g: NON_VIABLE  # healthy but peak==limit
  12g: Viable + safety margin → SELECTED (minimal)
  16g: Viable + margin (not selected)
```

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `compose.embedding.cpu.mem10g.yaml` / `mem16g.yaml` | 创建（characterization-only；保留） |
| `compose.embedding.cpu.mem12g.yaml` | Phase A 创建后 Phase B 删除（正式值已烘焙） |
| `scripts/preflight/lib_tei_probe.sh` | 参数化 helper；正式 `TEI_SPEC_MEM_LIMIT=12g` |
| `scripts/diagnostics/measure_tei_memory.sh` | `--mem-limit=`；禁 compose.sh / docker update |
| `compose.embedding.cpu.yaml` | `mem_limit: 12g` |
| `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` | §3.10.3 / §3.18 #8 / #12 |
| `scripts/preflight/check_linux_host.sh` | Check 8/13a/13b 对齐 D=12 |
| `scripts/start_embedding.sh` | OOM 文案 → 12g |
| `tests/**` + Layer B fixtures | 对齐；保留 CONFLICT；新增 PASS@12g |
| `README.md` / `open_issues.md` / progress / master_plan / 本 Task Plan | 回写 |

### 与原计划的差异

- Phase B 删除 `mem12g` overlay（与正式 12g 重复）；保留 `mem10g`/`mem16g` 并标明 characterization-only。
- 正式烘焙后 `--mem-limit=8g` compose 路径 fail-closed（无 mem8g overlay；历史 CONFLICT 用 fixture）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit/test_tei_*.py tests/unit/test_preflight_tei_probe_contract.py -q` | PASS |
| Contract | `uv run pytest tests/contract/test_compose_config_contract.py -q` | PASS |
| Integration / Gate | `uv run pytest tests/runtime_contract_gate -m runtime_contract_gate -q` | PASS（CONFLICT@8g + PASS@12g） |
| Formal measure | `bash scripts/diagnostics/measure_tei_memory.sh --timeout=300` | PASS（peak=10919954350；verdict=PASS） |
| E2E | N/A |  |
| Ruff | `uv run ruff check`（相关 tests） | PASS |
| Mypy | `uv run mypy`（相关 tests） | PASS |
| Check 13b | `check_linux_host.sh --mode=cpu` | **Check 13b PASS**（peak=10919954350；ready_sec=200）；整脚本 exit 1 因既有 `vm.max_map_count=65530`（非本任务范围） |
| start_embedding | `./scripts/start_embedding.sh cpu` | PASS（exit 0；无 OOM） |

### Review 结果

```yaml
p0: 0
p1: 0
p2: null
p3: null
review_report: "CODE_REVIEW_APPROVED"
plan_review_round_1: "PLAN_REJECTED（BLOCKER=0；MUST_FIX=4；SHOULD_FIX=4）"
plan_review_round_2: "待修项已吸收为 Amendment 002（R2 SF-1～SF-4 + R3 MF-3）"
plan_review_round_3: "PLAN_APPROVED（BLOCKER=0；MUST_FIX=0）；人工确认批准 OI-011"
```

### Git 记录

```yaml
branch: "feat/OI-011-bge-m3-cpu-tei-memory-contract"
plan_commit: bda5018a712766a5981f8e1a19940132a56de536
implementation_commit: 131a2e994690adb4b06b4d0fa299b229e88ca7d3
implementation_commit_message: "feat(tei-probe): land bge-m3 cpu mem_limit 12g contract"
pr: "#15"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/15"
pr_status: OPEN
pr_base: main
pr_head: feat/OI-011-bge-m3-cpu-tei-memory-contract
```

### 最终状态

`committed`（MEMORY_LIMIT_DECISION=12g；implementation `131a2e994690adb4b06b4d0fa299b229e88ca7d3`；PR #15 OPEN；等待人工 Merge；禁 push main；不得触碰 DEV-006 / PR #13）

## 15. DEV-006 resume conditions（对齐 DEV-003-002 §15 R2–R7；Spec-OI 完成后）

> 本表在 **OI-011 completed（PR merged + 新 contract 验证 PASS）** 之后作为恢复 DEV-006 的权威技术门。  
> **本任务执行期间**不得恢复 DEV-006、不得 Merge PR #13。

| # | 条件 | 验证方式 | 规划时状态 |
|---|---|---|---|
| R1 | DEV-003-002 `completed`（tooling VALID） | `formal_DEV-003-002_status=completed`；PR #14 merged | **satisfied** |
| R2 | **OI-011** 完成且 **新 spec/compose mem_limit** 下正式 probe `runtime_contract_verdict=PASS`（无 OOM；300s 内 healthy） | `measure_tei_memory.sh`（默认正式 limit）或 Layer B PASS fixture + 受监督真实跑 | **satisfied locally**（待 OI-011 PR merge） |
| R3 | Preflight Check 13b 在**新 contract**下通过 | `bash scripts/preflight/check_linux_host.sh --mode=cpu` exit 0 | **Check 13b PASS**；整脚本仍受既有 `vm.max_map_count` 硬失败影响（非 TEI） |
| R4 | `./scripts/start_embedding.sh cpu` 在新 contract 下成功 | exit 0；无 OOMKilled | **satisfied locally**（exit 0） |
| R5 | DEV-006 feat 从含 OI-011 merge 的最新 `main` 整合 | 人工确认基点；**不**由 OI-011 执行 | pending（OI-011 后） |
| R6 | DEV-006 §8.8 Integration 重跑通过 | `uv run pytest tests/integration/test_tei_embedding_client_integration.py -q` | pending |
| R7 | PR #13 门禁恢复为可人工 Merge 评估 | Orchestrator 记录；**仍须人类 Merge** | pending |

**插入覆盖解除条件**：OI-011 `completed` 且 R2–R4 satisfied 后，才可将 `current_task` 切回 DEV-006 恢复流程；此前 `deferred_business_task=DEV-006` 保持 `PAUSED`。

## 16. Expected spec / compose / preflight impact

| 区域 | 影响 |
|---|---|
| §3.10.3 | CPU `mem_limit` 字面；profile-specific **fixed contract**；低于 formal contract 的 override → `NON_SPEC_COMPLIANT`（Round 2 SF-2 唯一句式） |
| §3.10.8 | 通常无行为变更；若文案提及 8g 启动假设则同步 |
| §3.18 #8 | CPU MemAvailable：权威公式 `CPU_MIN/REC = 12/16+(D-8)`（例 D=12→16/20）；**不改 GPU** |
| §3.18 #9 | 语义不变；门槛数值随 #8 更新 |
| §3.18 #12 | 「TEI … 8g Memory Limit」→ 选定值；Check 与 Docker 可提供该 limit |
| `compose.embedding.cpu.yaml` | `mem_limit` 正式值 |
| Preflight Check 8 | `CPU_MIN_GIB` / `CPU_REC_GIB`（由公式） |
| Preflight Check 13a | `required_host_mem_gib = 2 + TEI_LIMIT_GIB`（HOST_RESERVE=0） |
| Preflight Check 13b | 运行时探针期望 limit / 成功失败文案 |
| `lib_tei_probe.sh` / `measure_tei_memory.sh` | 多档测量 **单一** helper（含 8g）+ 默认正式 limit；env-file 对齐 compose.sh |
| `start_embedding.sh` | DECISION≠8g 时必改硬编码文案 |
| `scripts/compose.sh` | **无改动** |
| Contract tests | compose mem_limit 断言；#8 公式数值；SF-2/`NON_SPEC_COMPLIANT` |
| Runtime contract gate | 保留 CONFLICT@8g fixture；新增 PASS@DECISION fixture |
| DEV-006 | **无代码影响**；仅 resume 门 R2–R4 依赖本任务 |

## 17. Planner 摘要（Orchestrator 用）

- **Task**：`OI-011` Spec-OI；**Amendment 002**（Round 3 remediation）已吸收 R3 MF-3 + R2 SF-1～SF-4；Round 3 `PLAN_APPROVED`；status=`approved`
- **注入（MF-1 + R2 SF-1）**：overlay + probe 显式 `-f`；**含 8g 一律 helper**；无 compose.sh 双路径；**compose.sh 黑名单**
- **env-file（R2 SF-4）**：`.env` 必选；versions*/embedding.env 仅存在时
- **Matrix**：cgroup ∈ {8g,10g,12g,16g}；每档 2 clean runs；最多 8 有效；每档 ≤1 invalid replacement；禁择优
- **NON_VIABLE（R2 SF-3）**：含 `rss_peak_warmup_bytes >= container_limit_bytes`
- **Decision**：最小 Viable + safety margin `max(1.5GiB, 15%×limit)`；16g 仍无 → UNRESOLVED HALT；禁 20g+
- **13a（MF-2）**：`2 + TEI_LIMIT_GIB + 0`
- **#8（MF-3）**：方案 A；**公式权威** `CPU_MIN/REC=12/16+(D-8)`；查表示例 D=12→**16**/20（禁 min=14）
- **Layer B（MF-4）**：保留 CONFLICT + 新增 PASS fixtures/**
- **Contract type（R2 SF-2）**：profile-specific **fixed contract**；低于 formal contract 的 override → `NON_SPEC_COMPLIANT`
- **R1 SF-1**：`start_embedding.sh` 在 DECISION≠8g 时 **必改**
- **Hard ban**：docker update 正式 evidence；改 compose.sh；改 DEV-006 / merge #13；`src/**`
- **Phases**：A characterize → B spec/compose/preflight → C validate（本轮只修订计划）
