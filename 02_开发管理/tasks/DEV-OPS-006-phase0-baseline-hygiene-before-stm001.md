# DEV-OPS-006 Phase 0 Baseline Hygiene Before STM-001

## 1. 任务信息

```yaml
task_id: DEV-OPS-006
task_name: Phase 0 Baseline Hygiene Before STM-001
status: approved
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "非业务规格任务：Phase 0→STM-001 前 baseline hygiene；对齐 DEV-003 §3.10.2 compose wrapper 契约与 OI-011 §5.3 characterization 例外；不修改业务 Contract / TEI 12g / SiliconFlow"
prerequisites:
  - "DEV-007 completed（PR #17 MERGED；main HEAD 含 SiliconFlow MVP）"
  - "OI-011 completed（TEI CPU mem_limit=12g；characterization probe tooling 已 merge）"
  - "Phase 0 readiness audit：PHASE0_READINESS=PASS；STM_001_ENTRY_GATE=GO_FOR_STM_001；DEV-002 satisfied"
  - "基线：main @ 524786aa52f3ac79b5e9a26e46f36b93545d7c55 == origin/main；working tree clean（规划轮次只读验证通过）"
  - "本任务为用户显式 NEW_UNPLANNED_FEATURE：进入 STM-001 前最小 hygiene；不得实现 STM-001"
branch: "feat/DEV-OPS-006-phase0-baseline-hygiene-before-stm001"
created_at: "2026-08-09 10:42 UTC"
updated_at: "2026-08-09 10:42 UTC"
approval_gates:
  planning_docs: "PLAN_APPROVED（Plan Reviewer BLOCKER=0 MUST_FIX=0；人工确认 PLAN_APPROVED）"
  implementation_plan: "status=approved；待 PLAN_LANDING；未实施"
insertion_override:
  prior_current_task: "DEV-007"
  prior_current_task_status: "completed"
  prior_next_action: "等待用户显式指定下一任务（Phase 0 bootstrap 就绪；STM-001 / EXT-007 / RET-001 等可规划）"
  override_by: "用户显式 NEW_UNPLANNED_FEATURE → PROPOSED_TASK_ID=DEV-OPS-006 + WORKFLOW_MODE=NORMAL(explicit)"
  effect: "current_task 切换为 DEV-OPS-006；清理 unit baseline + progress DOC_CODE_DRIFT；完成后 next_action→STM-001 可规划；本任务期间不得实现 STM-001 / 不得触碰 DEV-006/PR#13"
```

### 1.1 Root Cause Classification（只读诊断结论）

```yaml
primary_classification: A
secondary_note: "measure_tei_memory.sh 命中点为 usage/comment 字符串（C-like），但主因与修复路径仍归 A（exact-path allowlist），禁止为逃避扫描改写文案"
exact_failing_rule: "tests/unit/test_compose_wrapper_contract.py::test_no_bare_docker_compose_outside_wrapper"
exact_failing_mechanism: "BARE_DOCKER_COMPOSE_RE = r'(?<![\\w./-])docker\\s+compose\\b'；ALLOWED_BARE_COMPOSE_FILES 仅含 scripts/compose.sh + 本测试文件"
violations:
  - path: scripts/preflight/lib_tei_probe.sh
    kind: executable_invocation
    line: 126
    evidence: 'tei_probe_compose_cpu → tei_probe_with_embedding_env docker compose "${TEI_PROBE_COMPOSE_ARGS[@]}" "$@"'
  - path: scripts/diagnostics/measure_tei_memory.sh
    kind: documentation_string_in_usage
    line: 36
    evidence: "usage() 文档声明 Starts/stops via lib_tei_probe.sh explicit docker compose -f chain"
approved_semantics:
  source: "OI-011 Task Plan §5.3.2 / §5.3.4（Amendment 001/002；PLAN_APPROVED；PR #15 MERGED）"
  rule: "characterization 全部档位（含 8g）必须走 lib_tei_probe.sh helper 内显式 docker compose 多 -f；禁止走 compose.sh；compose.sh 列入 OI-011 黑名单"
  purpose: "TEI CPU memory characterization / probe tooling（DEV-003-002 + OI-011）；非日常生产 compose 入口"
why_not_B: "将 probe 改为 compose.sh 会破坏 OI-011 已批准的「无 compose.sh 双路径 / mem overlay 不可经 compose.sh 注入」合同；本任务禁止改 TEI 12g / compose*.yaml / 启动 TEI 验证"
why_not_C_primary: "lib_tei_probe.sh:126 是真实可执行 bare docker compose，不是误判 comment；C 仅解释 measure 次要命中"
```

**一句话**：主分类 **A**——两脚本属于 OI-011 已批准的 characterization wrapper exception，当前 contract test 缺少精确 path allowlist。

---

## 2. 任务目标

在进入 STM-001 前完成 **最小 Phase 0 baseline hygiene**，使：

1. **Unit baseline green**：`uv run pytest tests/unit -q` 全绿（修复后预期 **215 passed**；当前 215 collected，1 failed）。
2. **Contract baseline green**：`uv run pytest tests/contract -q` 保持全绿（规划时只读验证 **47 passed**）。
3. **Ruff green**：`uv run ruff check .`
4. **Mypy green**：`uv run mypy src tests scripts`
5. **progress.md governance metadata** 与当前 main 可验证状态一致（HEAD / Phase 就绪叙事 / 经命令验证的 unit·contract 计数）；不伪造结果、不大范围重写历史。

完成后 `next_action` → **STM-001 可规划**（仍须另一次显式编排；**本任务不得实现 STM-001**）。

---

## 3. 非目标

- 实现 **STM-001** 或任何 STM / EXT / RET 业务代码 / 测试语义变更。
- 修改 SiliconFlow client / embedding provider / Settings pivot。
- 修改 TEI memory limit（12g）、`compose*.yaml`、OI-011 12g contract、preflight Check 语义。
- 修复 TEI HTTP 429 或其他 runtime TEI 问题。
- 操作 **DEV-006** dirty worktree / **PR #13**（DO_NOT_MERGE 保持）。
- 调用真实 SiliconFlow API；启动/停止 TEI；跑真实 memory matrix。
- 修改 `scripts/compose.sh` 行为；把 characterization 改回 `compose.sh`（违反 OI-011）。
- 删除 / skip / xfail `test_no_bare_docker_compose_outside_wrapper`；全局放宽扫描（如允许整个 `scripts/`）；模糊 substring 逃避。
- 演变为 infrastructure redesign、permissions 扩大、五命令正文修改。
- 自动 Push / Merge / Rebase / Force Push；`gh pr merge`；提交 Secret。

---

## 4. 当前代码状态

- **已存在**：
  - `scripts/compose.sh`：§3.10.2 日常/生产唯一 compose wrapper（`exec docker compose`）。
  - `tests/unit/test_compose_wrapper_contract.py`：禁止 bare `docker compose`（allowlist 仅 `compose.sh` + 测试文件自身）。
  - `scripts/preflight/lib_tei_probe.sh`：OI-011 helper；**故意** bare `docker compose` 多 `-f`（含 mem overlay）。
  - `scripts/diagnostics/measure_tei_memory.sh`：驱动上述 helper；usage 文档含 `docker compose` 字面。
  - OI-011 / DEV-003-002 已 merge；TEI formal `mem_limit=12g`；`RUNTIME_CONTRACT_STATUS=PASS`。
- **可复用组件**：现有 `ALLOWED_BARE_COMPOSE_FILES` frozenset/set 模式；OI-011 §5.3 已批准例外语义。
- **当前缺失**：contract test 对 OI-011 characterization 两路径的 **exact-path / exact-purpose allowlist**。
- **与技术规格不一致之处**：无业务 Contract 冲突；属治理契约与已批准例外未对齐（PRE_EXISTING_WARNING；非 STM-001 blocker，但本任务要清掉）。
- **progress.md DOC_CODE_DRIFT（非阻塞；本任务 hygiene）**：
  - `latest_commit` 仍写 `b7916ea…`，落后于 main HEAD `524786aa52f3ac79b5e9a26e46f36b93545d7c55`
  - unit/contract 计数停留在 DEV-OPS-005 时代（unit **156** / contract **17**）；实际 collect：unit **215** / contract **47**（contract 规划时已绿）
  - `current_phase: Phase 0` 叙事未标明 Phase 0 completed / Phase 1（STM-001）ready
- **前置任务检查**：DEV-007 `completed`；HEAD 与 Orchestrator 声明一致；工作区干净；DEV-006/PR#13 不得触碰。

### 4.1 规划时只读证据摘要

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `524786aa52f3ac79b5e9a26e46f36b93545d7c55` |
| `git status --short` | clean |
| 失败用例 | `test_no_bare_docker_compose_outside_wrapper` → 两路径同上 |
| `uv run pytest tests/contract -q` | **47 passed**（规划轮次验证） |
| `uv run pytest tests/unit --collect-only -q` | **215 tests collected** |

---

## 5. 实现方案

### Step 1 — Exact-path allowlist（分类 A 最小修复）

- **文件**：`tests/unit/test_compose_wrapper_contract.py`（修改）
- **类/函数/Schema**：更新 `ALLOWED_BARE_COMPOSE_FILES`；可选新增小型 invariant 测试（同文件）
- **输入**：现有扫描逻辑 + OI-011 批准例外路径
- **输出 / 强制约束**：
  1. **仅**追加以下 **exact resolved Path**（禁止目录级 / glob / 模糊子串放宽）：
     - `REPO_ROOT / "scripts" / "preflight" / "lib_tei_probe.sh"`
     - `REPO_ROOT / "scripts" / "diagnostics" / "measure_tei_memory.sh"`
  2. 在 allowlist 旁写清 **exact purpose** 注释（可检索）：`OI-011 characterization probe` / `never compose.sh for mem overlays`；引用 Task Plan / OI-011 §5.3。
  3. **保留**原 `BARE_DOCKER_COMPOSE_RE` 与扫描范围；**不得**删除/skip/xfail `test_no_bare_docker_compose_outside_wrapper`。
  4. **推荐（最小增强，仍白名单内）**：新增 1 个 unit 断言——allowlist 中两路径必须存在，且 `lib_tei_probe.sh` 仍含表征 helper 标记（例如 `tei_probe_compose_cpu` 与 `tei_probe_build_compose_args`），防止空 allowlist 腐烂；**不得**因此修改脚本业务逻辑。
- **错误处理**：若未来再出现第三方 bare compose → 测试继续 fail-closed（预期）。
- **幂等/并发/事务**：不适用（静态契约）。

### Step 2 — 禁止改脚本实现（本任务默认零改脚本）

- **文件**：`scripts/preflight/lib_tei_probe.sh`、`scripts/diagnostics/measure_tei_memory.sh`
- **决定**：**不修改**（分类 A；脚本语义已批准）。
- **禁止**：为通过扫描把 `docker compose` 改写成 `compose.sh`；或改写 usage 文案以逃避 regex（模糊逃避）。
- **例外**：仅当 Plan Reviewer 强制要求 comment 改写且仍保持 OI-011 语义可审计时，须走 Amendment；默认不采用。

### Step 3 — progress.md hygiene（仅真实可验证 metadata）

- **文件**：`02_开发管理/progress.md`（修改；实施阶段在 verified 命令之后）
- **允许更新字段（实施/完成时）**：
  - `latest_commit` → 当时真实 `git rev-parse HEAD`（禁止 self-ref 伪造即将产生的 SHA）
  - `current_phase` 叙事：Phase 0 **completed** / Phase 1（STM-001）**ready**（或等价清晰字段；不大改历史表）
  - 测试状态表：Unit / Contract / Ruff / Mypy —— **仅**写入本任务实际跑过的命令与结果
  - `current_task` / status / plan / next_action / formal_DEV-OPS-006_* 治理字段（按状态机）
  - 「下一任务」小节：指向 STM-001 可规划；保留 DEV-006 PAUSED / DO_NOT_MERGE 提示
- **禁止**：伪造「未跑却 passed」；把 unit 改回 156；大范围重写已完成任务历史时间线；声称 STM-001 已开始。

### Step 4 — master_plan 本任务状态回写

- **文件**：`02_开发管理/master_plan.md`
- **范围**：仅本任务登记行 / 短小节状态字段 + CHANGE-019 审批进展；不改其他任务目标。

---

## 6. 文件变更清单

### 6.1 Exact writable whitelist（实施阶段允许路径；精确到文件）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_compose_wrapper_contract.py` | 修改 | exact-path allowlist + purpose 注释 + 可选 allowlist 存在性/标记断言 |
| `02_开发管理/progress.md` | 修改 | 规划/实施/完成态治理 metadata；DOC_CODE_DRIFT hygiene |
| `02_开发管理/master_plan.md` | 修改 | DEV-OPS-006 登记状态回写 |
| `02_开发管理/tasks/DEV-OPS-006-phase0-baseline-hygiene-before-stm001.md` | 修改 | 执行记录 / 状态机 / Amendment |

### 6.2 Exact forbidden paths（非穷尽；命中即越权）

| 路径/范围 | 原因 |
|---|---|
| `src/**`（含 SiliconFlow client / embedding） | 非本任务；禁 STM/业务 |
| `compose.yaml` / `compose.*.yaml` / overlays | 禁改 TEI/mem contract |
| `scripts/compose.sh` | OI-011 黑名单；日常 wrapper 不改 |
| `scripts/preflight/lib_tei_probe.sh` | 默认不改（A）；禁语义重写为 compose.sh |
| `scripts/diagnostics/measure_tei_memory.sh` | 默认不改（A）；禁文案逃避扫描 |
| `scripts/start_embedding.sh` / `scripts/lock_tei_images.sh` | 超出 hygiene |
| `01_技术规格/**` | 禁改规格 |
| `.cursor/commands/**` / `.cursor/agents/**` / 五命令正文 | 非本任务 |
| DEV-006 feat / PR #13 相关任何路径 | DO_NOT_MERGE；禁触碰 |
| STM/EXT/RET 业务与测试 | 禁实现 STM-001 |

**期望规模**：1 个实现文件（compose wrapper contract test）+ 必要 governance 文件（≤3）。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 静态契约 + 文档 hygiene；无多写事务 |
| 幂等 | 适用 | allowlist 追加幂等；重复实施不改变扫描语义 |
| 并发 | 不适用 | 无共享可变运行时状态 |
| 版本冲突 | 不适用 | 无乐观锁/业务版本 |
| 用户隔离 | 不适用 | 无多租户数据面 |
| 部分失败 | 适用 | 任一门禁失败 → 不得标 tested；不得 skip |
| 进程异常恢复 | 不适用 | 无长驻进程；不启 TEI |

---

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| `test_no_bare_docker_compose_outside_wrapper` | 无 violations（两 OI-011 路径已 exact allowlist） |
| 可选 allowlist invariant | 两路径存在；`lib_tei_probe.sh` 保留表征 helper 标记 |
| 全量 unit | `uv run pytest tests/unit -q` → **全绿**（预期 215 passed） |
| 负向守卫（文档化） | 不得引入目录级放宽；新 bare compose 文件仍应失败 |

### Contract Test

| 场景 | 预期 |
|---|---|
| 全量 contract | `uv run pytest tests/contract -q` → **47 passed**（保持；本任务不改 contract 业务） |

### Integration / E2E / 失败注入

| 场景 | 预期 |
|---|---|
| Integration / E2E / TEI probe 实跑 | **不跑**（禁止启停 TEI；非本任务） |
| 真实 SiliconFlow | **不跑** |

### 质量门禁命令（expected test commands）

```bash
uv run pytest tests/unit -q
uv run pytest tests/contract -q
uv run ruff check .
uv run mypy src tests scripts
```

修复后 unit baseline 必须全绿；不得 xfail/skip 该失败用例。

---

## 9. 验收标准

- [ ] Root cause 按 **A** 落地：exact-path allowlist（两路径）+ purpose 注释；未删测试、未全局放宽、未改脚本语义
- [ ] `uv run pytest tests/unit -q` 全绿（预期 215 passed）
- [ ] `uv run pytest tests/contract -q` 全绿（预期 47 passed）
- [ ] `uv run ruff check .` 通过
- [ ] `uv run mypy src tests scripts` 通过
- [ ] `progress.md`：`latest_commit`=真实 HEAD；Phase 0 completed / Phase 1 ready 叙事；unit/contract/ruff/mypy 为经命令验证的结果；无伪造
- [ ] 未触碰 forbidden paths；未操作 DEV-006/PR#13；未实现 STM-001；未启 TEI；未调真实 SiliconFlow
- [ ] Review 无 P0/P1
- [ ] 完成后 `next_action` = STM-001 可规划（不得在本任务实施 STM-001）

---

## 10. 风险与阻塞项

- **设计文档冲突**：无（对齐 OI-011 已批准例外与 §3.10.2 wrapper 分工）。
- **当前代码冲突**：unit 1 fail 为已知 PRE_EXISTING_WARNING；本任务修复。
- **前置任务**：DEV-007 / OI-011 completed（满足）。
- **未批准依赖**：无。
- **API/Schema 变化**：无。
- **其他风险**：
  - 若 Reviewer 主张分类 B（改脚本走 compose.sh）→ **必须 HALT** 并报告与 OI-011 §5.3 冲突；不得擅自改 Contract。
  - allowlist 腐烂：用存在性/标记断言缓解。
  - progress 误写未验证计数 → 禁止；只写实跑结果。
  - 范围膨胀到 TEI 429 / STM-001 → fail-closed 拒绝。

### 10.1 Plan Reviewer 检查点对齐（7 点）

| # | 检查点 | 本计划位置 |
|---|---|---|
| 1 | proposed task ID / title / goal / non-goals | §1 / §2 / §3 |
| 2 | root cause classification A/B/C + evidence | §1.1 / §4 |
| 3 | exact failing rule | §1.1 `exact_failing_rule` |
| 4 | recommended minimal remediation | §5 Step 1 |
| 5 | exact writable whitelist | §6.1 |
| 6 | exact forbidden paths | §6.2 / §3 |
| 7 | expected test commands + progress update scope + risks | §8 / §5 Step 3 / §10 |

---

## 11. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/DEV-OPS-006-phase0-baseline-hygiene-before-stm001"
expected_commits:
  - "docs(plan): add DEV-OPS-006 phase0 baseline hygiene before stm001 plan"
  - "test(compose): allowlist OI-011 tei probe bare compose paths"
  - "docs(status): record DEV-OPS-006 implementation commit and PR"  # feat；IMPLEMENTATION_RELEASE 可选
  - "docs(status): complete DEV-OPS-006 after PR merge"  # POST_MERGE_CLEANUP on main
out_of_scope_changes:
  - "STM-001 / STM/EXT/RET 业务与测试"
  - "SiliconFlow client / embedding provider"
  - "compose*.yaml / TEI 12g / OI-011 contract 正文"
  - "scripts/compose.sh / lib_tei_probe.sh / measure_tei_memory.sh 语义重写"
  - "DEV-006 feat / PR #13"
  - "启停 TEI / 真实 SiliconFlow / 修 HTTP 429"
release_phases:
  PLAN_LANDING: "main: docs(plan) + ff-only + 创建 exact feat"
  IMPLEMENTATION_RELEASE: "仅 feat: 白名单 add/commit/push/PR；禁 push main"
  POST_MERGE_CLEANUP: "PR MERGED 后：ff-only main + docs(status) complete + 删 exact feat"
```

### 11.1 状态机（本任务）

```text
planned
→ (Plan Review + 人工 PLAN_APPROVED) approved
→ (NORMAL) PLAN_LANDING
→ in_progress → implemented → tested
→ reviewed (CODE_REVIEW_APPROVED)
→ (Commit Recorder READY_FOR_HUMAN_COMMIT)
→ committed (IMPLEMENTATION_RELEASE)
→ WAITING_FOR_PR_MERGE（人工 Merge）
→ completed (POST_MERGE_CLEANUP)
```

`current_task_status` = **approved**（Plan Reviewer + 人工 `PLAN_APPROVED`）；`next_action` = **PLAN_LANDING**。

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-09 10:42 UTC | Planner 初版 | 创建本 Task Plan；progress/master_plan 规划态登记 | 只读：unit 失败用例确认；contract 47 passed；215 unit collected | 分类 A；未实施；未 Git 写；未启 TEI |
| 2026-08-09 12:25 UTC | Plan Review + 人工 PLAN_APPROVED | status→approved；吸收 SHOULD_FIX（存在性断言 + drift 基于实测） | n/a | BLOCKER=0 MUST_FIX=0；待 PLAN_LANDING |

---

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
| Unit | `uv run pytest tests/unit -q` | pending implementation |
| Contract | `uv run pytest tests/contract -q` | 规划只读：**47 passed**（实施后须复跑） |
| Integration | n/a | 本任务不跑 |
| E2E | n/a | 本任务不跑 |
| Ruff | `uv run ruff check .` | pending implementation |
| Mypy | `uv run mypy src tests scripts` | pending implementation |

### Review 结果

```yaml
p0: null
p1: null
p2: null
p3: null
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

`approved`（待 PLAN_LANDING）
