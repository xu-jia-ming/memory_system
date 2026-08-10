# DEV-OPS-007 Phase 1 Baseline Hygiene Before STM-006

## 1. 任务信息

```yaml
task_id: DEV-OPS-007
task_name: Phase 1 Baseline Hygiene Before STM-006
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "非业务规格任务：Phase 1→STM-006 前 baseline hygiene；治理 metadata 与 main lineage 对齐；Ruff E501 格式化-only 修复；不修改业务 Contract / STM-005 实现 / STM-004 生产逻辑"
prerequisites:
  - "STM-005 completed（PR #23 MERGED；main HEAD `b0736431a636f0ba20a9cf5aad61a2ea8dc365df` == origin/main；working tree clean）"
  - "STM-006 prerequisites SATISFIED — READY_FOR_PLANNING only（本任务不得启动 STM-006 规划或实施）"
  - "基线：main @ b0736431a636f0ba20a9cf5aad61a2ea8dc365df；working tree clean（规划轮次只读验证通过）"
  - "本任务为用户显式 START_NEW_TASK：进入 STM-006 前最小 hygiene；不得实现 STM-006"
branch: "feat/DEV-OPS-007-phase1-baseline-hygiene-before-stm006"
created_at: "2026-08-10 10:14 UTC"
updated_at: "2026-08-10 10:30 UTC"
approval_gates:
  planning_docs: "PLAN_APPROVED"
  implementation_plan: "tested"
insertion_override:
  prior_current_task: "STM-005"
  prior_current_task_status: "completed"
  prior_next_action: "STM-006 READY_FOR_PLANNING only（do NOT auto-start）"
  override_by: "用户显式 START_NEW_TASK=DEV-OPS-007 + WORKFLOW_MODE=NORMAL(explicit)"
  effect: "current_task=DEV-OPS-007 planned；修正 STM-005 orphan SHA metadata + Ruff E501 baseline；完成后 next_action→STM-006 可规划；本任务期间不得实现 STM-006 / 不得触碰 DEV-006/PR#13"
```

---

## 2. 任务目标

在进入 STM-006 前完成 **最小 Phase 1 baseline hygiene**，使：

1. **治理 metadata 与 main lineage 一致**：所有 STM-005 `status_record_completed` / 权威完成证据引用 main 血统 commit `b0736431a636f0ba20a9cf5aad61a2ea8dc365df`；仓库内不再残留 orphan SHA `301c8d9ff873ba826b122f6cbb34a3dc0d2aa40b` 作为权威引用。
2. **Ruff baseline green**：`uv run ruff check .` → **FULL_RUFF=PASS**（修复 2 处 pre-existing E501；仅格式化换行，零语义变更）。
3. **STM-004 torn-read 相关 Integration 回归通过**：`tests/integration/test_context_read_redis.py`（含 I12 torn-read 场景）保持全绿。
4. **Mypy green**（若仓库治理要求）：`uv run mypy src tests scripts` 通过。

完成后 `next_action` → **STM-006 可规划**（仍须另一次显式编排；**本任务不得实现 STM-006**）。

---

## 3. 非目标

- 实现 **STM-006** 或任何 STM / EXT / RET 业务代码 / 测试语义变更。
- 修改 STM-005 `src/**` 实现、STM-004 `src/**` 生产代码、Redis Lua、Mongo、Kafka、compression、LLM。
- **resurrect / cherry-pick** orphan SHA `301c8d9…`；reset main；rewrite history；修改 STM-005 实现 commit。
- 修改 torn-read 并发逻辑、I12 三段式语义、FORBIDDEN_HYBRID 断言行为。
- 操作 **DEV-006** dirty worktree / **PR #13**（DO_NOT_MERGE 保持）。
- 修改 TEI 12g / SiliconFlow / `compose*.yaml` / embedding provider。
- 自动 Push / Merge / Rebase / Force Push；`gh pr merge`；提交 Secret。

---

## 4. 当前代码状态

### 4.1 只读确认（Planner 规划轮次已验证）

#### Issue A — governance orphan SHA（metadata only）

| 项 | 值 |
|---|---|
| **Orphan SHA** | `301c8d9ff873ba826b122f6cbb34a3dc0d2aa40b` |
| **权威 main-lineage commit** | `b0736431a636f0ba20a9cf5aad61a2ea8dc365df`（`docs(status): complete STM-005 after PR merge`；main HEAD） |
| **已知引用位置** | `02_开发管理/progress.md` L189：`formal_STM-005_status_record_completed: 301c8d9…` |
| | `02_开发管理/tasks/STM-005-context-archive-create-reuse.md` L463：`status_record_completed: 301c8d9…` |
| **Ancestry 验证命令与结果** | `git merge-base --is-ancestor 301c8d9ff873ba826b122f6cbb34a3dc0d2aa40b main` → **exit 1**（orphan **不在** main 血统） |
| | `git merge-base --is-ancestor b0736431a636f0ba20a9cf5aad61a2ea8dc365df main` → **exit 0**（权威 commit **在** main 血统） |
| **修复性质** | 仅 metadata 更正；将上述引用替换为 `b0736431a636f0ba20a9cf5aad61a2ea8dc365df` |

#### Issue B — Ruff baseline（pre-existing E501 only）

| 文件 | 行 | 规则 | 说明 |
|---|---|---|---|
| `tests/integration/context_read_torn_read_helpers.py` | 174:101 | E501 | Line too long (106 > 100) — `compression_version=...` |
| `tests/integration/context_read_torn_read_helpers.py` | 175:101 | E501 | Line too long (101 > 100) — `compressed_context=...` |

规划轮次 `uv run ruff check tests/integration/context_read_torn_read_helpers.py` 确认仅上述 2 处 E501；**无其他 Ruff 违规**（全仓 `uv run ruff check .` 当前 FAIL 仅因此 2 行）。

#### Git / 基线摘要

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `b0736431a636f0ba20a9cf5aad61a2ea8dc365df` |
| `git status --short` | clean |
| `git log --oneline -3` | `b073643 docs(status): complete STM-005 after PR merge` / `164dc1a Merge PR #23` / `a522074 docs(status): record STM-005` |
| STM-005 状态 | `completed`；PR #23 MERGED |
| DEV-OPS-007 ID 冲突 | **无**（仓库内无既有 `DEV-OPS-007` 登记） |

- **已存在**：STM-005 实现与测试已在 main；Ruff E501 为 STM-004 torn-read helper 遗留；orphan SHA 仅存在于治理文档。
- **可复用组件**：DEV-OPS-006 hygiene 模式（最小 diff、exact whitelist、verified 命令后更新 progress）。
- **当前缺失**：main-lineage 一致的 STM-005 `status_record_completed` 引用；全仓 Ruff PASS。
- **与技术规格不一致之处**：无业务 Contract 冲突；属治理 metadata 漂移 + 质量门禁 pre-existing E501。
- **前置任务检查**：STM-005 `completed`；HEAD 与 Orchestrator 声明一致；工作区干净；DEV-006/PR#13 不得触碰。

---

## 5. 实现方案

### Step 1 — 修正 STM-005 orphan SHA metadata（Issue A）

- **文件**：
  - `02_开发管理/progress.md`（修改 `formal_STM-005_status_record_completed`）
  - `02_开发管理/tasks/STM-005-context-archive-create-reuse.md`（修改 §14 `status_record_completed`）
- **输入**：权威 commit `b0736431a636f0ba20a9cf5aad61a2ea8dc365df`
- **输出**：两处 `status_record_completed` 均指向 `b0736431a636f0ba20a9cf5aad61a2ea8dc365df`
- **错误处理**：实施前 `rg 301c8d9` 全仓搜索；实施后再次搜索确认零命中（作为权威引用）
- **禁止**：cherry-pick orphan；修改 STM-005 implementation commit 记录（`c166be5…` 等保持不变）；改动 STM-005 `src/**`

### Step 2 — Ruff E501 格式化-only 修复（Issue B）

- **文件**：`tests/integration/context_read_torn_read_helpers.py`（修改 L174–175）
- **类/函数**：`broken_split_read_with_barrier` 内 `BrokenSplitReadSnapshot(...)` 构造参数
- **输入**：当前 2 行超长表达式
- **输出**：换行后每行 ≤100 字符；**逻辑与返回值语义不变**
- **错误处理**：若换行导致 mypy/ruff 新告警 → 调整缩进/括号，不得改变表达式求值顺序
- **禁止**：修改 torn-read barrier 时序、mutator/reader 并发逻辑、FORBIDDEN_HYBRID 断言

### Step 3 — progress.md / master_plan.md 本任务治理回写

- **文件**：`02_开发管理/progress.md`、`02_开发管理/master_plan.md`、本 Task Plan
- **范围**：DEV-OPS-007 规划/实施/完成态字段；`verified_ruff` 等仅在实测后写入
- **禁止**：伪造未跑命令结果；将 STM-006 标为 in_progress

---

## 6. 文件变更清单

### 6.1 Exact writable whitelist（实施阶段允许路径）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `02_开发管理/progress.md` | 修改 | STM-005 `status_record_completed` 更正 + DEV-OPS-007 治理字段 |
| `02_开发管理/tasks/STM-005-context-archive-create-reuse.md` | 修改 | §14 `status_record_completed` 更正为 main-lineage SHA |
| `tests/integration/context_read_torn_read_helpers.py` | 修改 | E501 换行（L174–175）；零语义变更 |
| `02_开发管理/tasks/DEV-OPS-007-phase1-baseline-hygiene-before-stm006.md` | 修改 | 执行记录 / 状态机 |
| `02_开发管理/master_plan.md` | 修改 | DEV-OPS-007 登记状态回写 |

### 6.2 Exact forbidden paths（命中即越权）

| 路径/范围 | 原因 |
|---|---|
| `src/**`（含 STM-004/005 生产代码） | 非本任务 |
| `src/**/context_read.lua`、Redis Lua | STM-004 生产逻辑禁改 |
| STM-005 `src/**`、Mongo repository/service | STM-005 实现禁改 |
| `tests/integration/test_context_read_redis.py` 语义 | 仅 helper 格式化；不改测试断言 |
| Kafka / compression / LLM / HTTP 相关 | 非本任务 |
| DEV-006 feat / PR #13 | DO_NOT_MERGE |
| `01_技术规格/**`、五命令正文 | 禁改规格/治理命令 |

**期望规模**：1 个测试 helper 文件 + 2–3 个治理文档；≤5 文件。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 文档 metadata + 格式化；无多写事务 |
| 幂等 | 适用 | SHA 替换与换行幂等；重复实施不改变语义 |
| 并发 | 不适用 | 无共享可变运行时状态 |
| 版本冲突 | 不适用 | 无乐观锁/业务版本 |
| 用户隔离 | 不适用 | 无多租户数据面 |
| 部分失败 | 适用 | 任一门禁失败 → 不得标 tested |
| 进程异常恢复 | 不适用 | 无长驻进程 |

---

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 全量 unit | **不强制全量**（本任务未改 `src/**`）；可选 `uv run pytest tests/unit -q` 保持通过 |

### Contract Test

| 场景 | 预期 |
|---|---|
| 全量 contract | **不强制全量**；可选 `uv run pytest tests/contract -q` 保持通过 |

### Integration Test

| 场景 | 预期 |
|---|---|
| STM-004 context read + I12 torn-read | `uv run pytest tests/integration/test_context_read_redis.py -q` → **全绿**（14 scenarios；含 FORBIDDEN_HYBRID / production Lua 正对照） |

### E2E Test

| 场景 | 预期 |
|---|---|
| E2E | **不跑**（非本任务） |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| I12 torn-read 负对照 | 由 `test_context_read_redis.py` 覆盖；helper 格式化后行为不变 |

### 质量门禁命令（expected test commands）

```bash
# Ancestry / orphan 搜索（实施前后各一次）
git merge-base --is-ancestor 301c8d9ff873ba826b122f6cbb34a3dc0d2aa40b main  # 期望 exit 1
git merge-base --is-ancestor b0736431a636f0ba20a9cf5aad61a2ea8dc365df main  # 期望 exit 0
rg 301c8d9  # 期望零命中（或仅本 Task Plan 历史诊断节若保留）

uv run ruff check .
uv run pytest tests/integration/test_context_read_redis.py -q
uv run mypy src tests scripts
```

---

## 9. 验收标准

- [x] `git merge-base --is-ancestor 301c8d9… main` → exit **1**（orphan 仍不在 main 血统；不得 resurrect）
- [x] `git merge-base --is-ancestor b0736431… main` → exit **0**
- [x] 全仓 `rg 301c8d9` → **零** stale 权威引用（`status_record_completed` / `formal_STM-005_status_record_completed` 均已更正）
- [x] `formal_STM-005_status_record_completed` 与 STM-005 Task Plan §14 均为 `b0736431a636f0ba20a9cf5aad61a2ea8dc365df`
- [x] `uv run ruff check .` → **FULL_RUFF=PASS**
- [x] `uv run pytest tests/integration/test_context_read_redis.py -q` → 全绿
- [x] `uv run mypy src tests scripts` → PASS（若仓库治理要求）
- [x] 未修改 STM-005/004 `src/**`、Redis Lua、Mongo、Kafka、compression、LLM
- [ ] Review 无 P0/P1

---

## 10. 风险与阻塞项

- **设计文档冲突**：无。
- **当前代码冲突**：无；orphan SHA 为治理 metadata 漂移，非实现缺陷。
- **前置任务**：STM-005 `completed` — SATISFIED。
- **未批准依赖**：无。
- **API/Schema 变化**：无。
- **其他风险**：
  - 误将 orphan SHA cherry-pick 到 main → **禁止**；仅 metadata 替换。
  - Ruff 换行意外改变表达式语义 → 以 Integration I12 场景回归验证。
  - 实施范围膨胀至 STM-006 → **禁止**；须独立 Task Plan。

---

## 11. Git 计划

```yaml
branch: "feat/DEV-OPS-007-phase1-baseline-hygiene-before-stm006"
workflow_mode: NORMAL
release_phase_sequence:
  - PLAN_LANDING  # docs(plan) on main + create exact feat
  - IMPLEMENTATION_RELEASE  # hygiene commit + PR
  - POST_MERGE_CLEANUP  # docs(status): complete on main; delete exact feat
expected_commits:
  - "docs(plan): add DEV-OPS-007 phase1 baseline hygiene plan"
  - "chore(hygiene): fix STM-005 governance SHA and ruff E501 in torn-read helpers"
  - "docs(status): record DEV-OPS-007 implementation commit and PR"
  - "docs(status): complete DEV-OPS-007 after PR merge"
out_of_scope_changes:
  - "STM-005/004 src/**"
  - "STM-006 任何代码或计划"
  - "DEV-006 / PR #13"
  - "resurrect orphan SHA 301c8d9"
  - "torn-read 并发逻辑语义变更"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

（暂无）

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-10 10:30 UTC | Developer tested | Issue A：progress.md + STM-005 §14 SHA 更正；Issue B：E501 换行 | integration 14 / unit 323 / contract 68；ruff PASS；mypy PASS | ZERO_STALE_AUTHORITATIVE_REFERENCES；未 commit |
| 2026-08-10 10:14 UTC | Planner 初版 | 创建 Task Plan；progress/master_plan 规划态回写 | 未运行（规划-only） | orphan SHA + E501 已只读确认；待 Plan Review |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `02_开发管理/progress.md` | `formal_STM-005_status_record_completed` 更正为 `b0736431…`；DEV-OPS-007 tested 治理回写 |
| `02_开发管理/tasks/STM-005-context-archive-create-reuse.md` | §14 `status_record_completed` 更正为 `b0736431…` |
| `tests/integration/context_read_torn_read_helpers.py` | L174–175 E501 换行（零语义变更） |
| `02_开发管理/master_plan.md` | DEV-OPS-007 状态 `planned` → `tested` |

### 与原计划的差异

无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Ancestry (orphan) | `git merge-base --is-ancestor 301c8d9ff873ba826b122f6cbb34a3dc0d2aa40b main` | exit **1** |
| Ancestry (authoritative) | `git merge-base --is-ancestor b0736431a636f0ba20a9cf5aad61a2ea8dc365df main` | exit **0** |
| Orphan search | `rg 301c8d9` | **ZERO_STALE_AUTHORITATIVE_REFERENCES**（剩余命中仅诊断/历史节） |
| Integration | `uv run pytest tests/integration/test_context_read_redis.py -q` | **14 passed** in 2.29s |
| Unit (optional) | `uv run pytest tests/unit -q` | **323 passed** in 4.61s |
| Contract (optional) | `uv run pytest tests/contract -q` | **68 passed** in 4.61s |
| Ruff | `uv run ruff check .` | **All checks passed!** |
| Mypy | `uv run mypy src tests scripts` | **Success: no issues found in 139 source files** |

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

`tested`
