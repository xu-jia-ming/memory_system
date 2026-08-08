# DEV-OPS-003-SMOKE NORMAL workflow supervised smoke

## 1. 任务信息

```yaml
task_id: DEV-OPS-003-SMOKE
task_name: NORMAL workflow supervised smoke (minimal)
status: tested
workflow_mode_for_this_task: NORMAL
workflow_mode_source: default
# Orchestrator 未收到 WORKFLOW_MODE / MODE 显式字段 → 默认 NORMAL；本 smoke 以 NORMAL / default 执行（不得改 STRICT）
spec_sections:
  - "N/A（无业务规格变更；验证 DEV-OPS-003 已合并实现的 NORMAL 编排）"
prerequisites:
  - "正式 DEV-OPS-003：PR #7 MERGED（merge 1189447）；实现已在 main"
  - "正式 DEV-OPS-003：尚未 completed；Step 7 冒烟进行中"
  - "仓库在 main，与 origin/main 同步；本规划轮次无 dirty tree"
  - "正式 feat/DEV-OPS-003-normal-strict-workflow-modes 仍存在；本 smoke 不得删除"
relationship_to_formal_DEV-OPS-003:
  role: "临时 smoke 任务（正式 DEV-OPS-003 Step 7）"
  formal_task_id: DEV-OPS-003
  formal_status_at_smoke_start: "PR #7 MERGED；尚未 completed；不得标 completed"
  progress_override: "规划/执行期间可临时 current_task=DEV-OPS-003-SMOKE"
  progress_restore_required: "smoke completed（或中止）后必须恢复 progress current_task=DEV-OPS-003（及正式未完成态字段）；不得开始 DEV-004"
branch: "feat/DEV-OPS-003-SMOKE-normal-workflow"
# 人工 PLAN_APPROVED 已确认；PLAN_LANDING 已完成（plan_commit=ba0d827）；Developer 已创建 marker
writable_paths_exact:
  - "02_开发管理/tasks/DEV-OPS-003-SMOKE-normal-workflow.md"
  - "02_开发管理/progress.md"
  - "tests/e2e/devops003_normal_workflow_smoke.txt"
master_plan_registration: false
# 用户明确：smoke 不登记正式 master_plan 项；禁止修改 02_开发管理/master_plan.md
created_at: "2026-08-08 01:26 UTC"
updated_at: "2026-08-08 01:32 UTC"
human_plan_approved: true
planning_round_stop: null
```

## 2. 任务目标

受监督验证 **合并后的** DEV-OPS-003 NORMAL 编排（真实 Release Operator 三相路径，非仅契约 grep）：

1. **默认 mode 声明**：未提供 `WORKFLOW_MODE` → Orchestrator 声明 `workflow_mode=NORMAL`、`source=default`。
2. **角色链**：Planner → Plan Reviewer → 人工 `PLAN_APPROVED` → 自动 `PLAN_LANDING` → Developer → Code Reviewer → Commit Recorder → 自动 `IMPLEMENTATION_RELEASE` → PR → `WAITING_FOR_PR_MERGE` →（后轮）人工 merge → 自动 `POST_MERGE_CLEANUP`。
3. **唯一实现产物**：创建 `tests/e2e/devops003_normal_workflow_smoke.txt`，内容恰好一行：
   `DEV-OPS-003-SMOKE NORMAL workflow supervised smoke marker`
4. **两个人工门禁**（NORMAL）：
   - 人工确认 `PLAN_APPROVED`
   - 人工 GitHub PR Review / Merge
5. **POST_MERGE_CLEANUP** 仅允许删除本 smoke exact feat：`feat/DEV-OPS-003-SMOKE-normal-workflow`（本地 `-d` + 远程 `--delete`）；**不得**删除正式 `feat/DEV-OPS-003-normal-strict-workflow-modes`。

## 3. 非目标

- 修改业务代码 / 技术规格 / 五命令正文 / `.cursor/**` 正式 DEV-OPS-003 实现
- 登记或修改 `02_开发管理/master_plan.md`
- 开始 `DEV-004`
- 将正式 `DEV-OPS-003` 标为 `completed`
- 删除正式 feat `feat/DEV-OPS-003-normal-strict-workflow-modes`
- 伪造冒烟通过（契约-only / 只读 replay **不计**本 E2E）
- `gh pr merge` / `git push --force` / `git reset --hard` / `git clean -fd` / `git branch -D` / 内容 `git merge` / 向 main 写实现 Commit
- 本规划轮次：创建 feat、任何 Git 写、Release、`PLAN_LANDING`

## 4. 当前代码状态

- **已存在**：main 含 DEV-OPS-003 实现（merge `1189447`）；Orchestrator / Release Operator / 契约测试已落地；正式 Task Plan `02_开发管理/tasks/DEV-OPS-003-normal-strict-workflow-modes.md`。
- **可复用**：NORMAL 三相 Release 合同与 Orchestrator 自动续跑语义（已合并）。
- **当前缺失**：无（Developer 已创建 smoke marker；全链路 E2E 后续阶段仍 pending）。
- **与技术规格**：无业务规格变更；无不一致需改 Contract。
- **前置检查（2026-08-08 Developer 轮次只读）**：
  - 当前分支：`feat/DEV-OPS-003-SMOKE-normal-workflow`（精确匹配）
  - `plan_commit`：`ba0d827`
  - 正式 feat 仍在；**禁止删除**
  - 正式 DEV-OPS-003：**未 completed**；不得借 smoke 标 completed

## 5. 实现方案

### 白名单（§5；恰好三路径；精确等于）

| # | 路径 | 角色可写时机 |
|---|---|---|
| 1 | `02_开发管理/tasks/DEV-OPS-003-SMOKE-normal-workflow.md` | Planner（本轮）/ 后续状态回写 |
| 2 | `02_开发管理/progress.md` | 规划态与执行态回写；**禁止**把正式 DEV-OPS-003 标 completed |
| 3 | `tests/e2e/devops003_normal_workflow_smoke.txt` | **唯一** Developer implementation 产物 |

### 黑名单（非穷尽；越界 → HALT / FAIL）

- `02_开发管理/master_plan.md`
- `src/**`
- `01_技术规格/**`
- `.cursor/**`（正式 DEV-OPS-003 实现）
- 五命令 `.cursor/commands/{plan,review-plan,develop,review-code,close}-task.md` 等业务命令正文（若路径不在白名单）
- 正式 Task Plan `02_开发管理/tasks/DEV-OPS-003-normal-strict-workflow-modes.md`（本 smoke 不改正式计划正文作为实现）
- 开始 / 规划 / 实施 `DEV-004`
- 删除 `feat/DEV-OPS-003-normal-strict-workflow-modes`

### Step 0 — 本规划轮次（已完成；人工 PLAN_APPROVED 已确认）

- 新建本 Task Plan；回写 `progress.md` 规划态（`current_task=DEV-OPS-003-SMOKE`，`status=planned`）。
- Plan Reviewer `PLAN_APPROVED`；人工确认 `PLAN_APPROVED`。
- 本 Step 0 结束；进入 `PLAN_LANDING`（Release Operator）。

### Step 1 — NORMAL 期望流（批准后；受监督执行）

```text
[/orchestrate-task TASK_ID=DEV-OPS-003-SMOKE]
  （不提供 WORKFLOW_MODE → 默认 NORMAL / source=default；须显式声明）
→ Planner（若计划已在；或核对） / Plan Reviewer
→ 人工 PLAN_APPROVED                                    ← 人工门禁 #1
→ Orchestrator 自动 Release Operator RELEASE_PHASE=PLAN_LANDING
     main: docs(plan) commit/push；ff-only；创建 exact feat
→ Developer：仅创建 smoke marker 文件（恰好一行指定文本）
→ Code Reviewer → Commit Recorder
→ Orchestrator 自动 Release Operator RELEASE_PHASE=IMPLEMENTATION_RELEASE
     仅 feat：add（白名单精确）/ commit / push / gh pr create
     可选同 feat docs(status): record
     永久禁止本 phase push/commit main
→ WAITING_FOR_PR_MERGE（ORCHESTRATOR_PAUSED_FOR_HUMAN）
→ 人工 GitHub Review/Merge                                  ← 人工门禁 #2
→ 恢复编排 → 自动 RELEASE_PHASE=POST_MERGE_CLEANUP
     fetch；ff-only main；docs(status): complete on main；
     仅删 exact smoke feat（-d / --delete）；禁止 -D；禁止删正式 feat
→ smoke completed；progress 恢复 current_task=DEV-OPS-003（正式仍未 completed 则保持未完成语义）
```

### Step 2 — Developer 唯一实现

- 文件：`tests/e2e/devops003_normal_workflow_smoke.txt`
- 内容**恰好一行**（无额外空行要求以外的多余内容；以计划指定文本为准）：

```text
DEV-OPS-003-SMOKE NORMAL workflow supervised smoke marker
```

- 不得改其它路径；不得伪造「已冒烟」。

### Step 3 — 数据一致性 / 治理

- smoke 期间 progress 可临时指向 `DEV-OPS-003-SMOKE`。
- smoke 结束后**必须**恢复 `current_task=DEV-OPS-003`；**不得**将正式 DEV-OPS-003 标 `completed`（completed 属正式任务 post-merge 治理，不在本 smoke 范围）。
- **不得**修改 `master_plan.md`。

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `02_开发管理/tasks/DEV-OPS-003-SMOKE-normal-workflow.md` | 创建 | 本 Task Plan |
| `02_开发管理/progress.md` | 修改 | 规划/执行态；结束后恢复正式 DEV-OPS-003 指针 |
| `tests/e2e/devops003_normal_workflow_smoke.txt` | 创建 | 唯一 implementation / E2E 冒烟标记 |

**明确不变更**：`02_开发管理/master_plan.md`、`src/**`、`.cursor/**`、正式 DEV-OPS-003 Task Plan 实现文件。

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 适用（Git 相位） | 每条 Release shell 检查退出码；失败立即 `RELEASE_OPERATOR_FAILED` / Orchestrator HALT |
| 幂等 | 部分适用 | marker 文件内容固定；重复写入同文允许；PR/分支已存在则按 Release 合同 fail-closed 或核对后停止 |
| 并发 | 不适用 | 单任务串行编排；不得并行第二 Task |
| 版本冲突 | 适用 | PLAN_LANDING / POST_MERGE 前 ff-only；分歧 → FAIL |
| 用户隔离 | 不适用 | 无多租户业务数据 |
| 部分失败 | 适用 | 任一 phase 中途失败不得继续下一 Git 步骤；不得假成功 |
| 进程异常恢复 | 适用 | 从 progress / PR 状态恢复；未 MERGED 不得 POST_MERGE；不得 force/hard reset |

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 本 smoke 不新增 unit | 沿用已合并 DEV-OPS-003 契约；不降低门槛 |

### Contract Test

| 场景 | 预期 |
|---|---|
| 既有 workflow modes / orchestrator / commands 契约 | 保持通过；本 smoke **不改**契约源 |

### Integration Test

| 场景 | 预期 |
|---|---|
| 不适用 | 无业务服务变更 |

### E2E Test（本任务主体；受监督）

| 场景 | 预期 |
|---|---|
| 默认 mode | `workflow_mode=NORMAL`，`source=default`（未传 WORKFLOW_MODE） |
| PLAN_LANDING | 真实执行：main `docs(plan)` + exact smoke feat 创建 |
| Developer | 仅三白名单内创建 marker；内容恰好指定一行 |
| IMPLEMENTATION_RELEASE | 真实 feat commit/push/PR；禁 push main |
| WAITING_FOR_PR_MERGE | pause；**不** `gh pr merge` |
| 人工 merge 后 POST_MERGE_CLEANUP | complete on main；**仅**删 smoke feat |
| 正式 feat 保留 | `feat/DEV-OPS-003-normal-strict-workflow-modes` 本地/远程均不得删 |
| 契约-only | **不计**本 E2E 通过 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 未 MERGED 调 POST_MERGE | FAIL |
| 试图删正式 feat | FAIL / 禁止 |
| 白名单外路径 | HALT / FAIL |
| force / hard reset / clean -fd / branch -D / gh pr merge | 永久禁止 |

## 9. 验收标准

- [ ] Orchestrator 声明 `workflow_mode=NORMAL` 且 `source=default`（本 smoke 未提供 WORKFLOW_MODE）
- [ ] 仅两个人工门禁：`PLAN_APPROVED` 与人工 PR Merge；其间三相 Release 为真实自动调度（非仅 grep）
- [ ] `PLAN_LANDING` / `IMPLEMENTATION_RELEASE` / `POST_MERGE_CLEANUP` 均出现真实 `RELEASE_COMPLETED`（含对应 phase）
- [x] marker 文件存在且内容恰好：`DEV-OPS-003-SMOKE NORMAL workflow supervised smoke marker`
- [ ] 白名单外无改动；`master_plan.md` 未改；`.cursor/**` / `src/**` 未改
- [ ] POST_MERGE 仅删除 `feat/DEV-OPS-003-SMOKE-normal-workflow`；正式 feat 仍在
- [ ] 正式 `DEV-OPS-003` **未**被标 `completed`；smoke 结束后 progress 恢复 `current_task=DEV-OPS-003`
- [ ] 未开始 `DEV-004`
- [ ] Review 无 P0/P1（对本最小变更）
- [ ] 未使用 `gh pr merge` / force / hard reset / clean -fd / `git branch -D`

### 本规划轮次验收（已完成）

- [x] Task Plan 已创建且字段齐全
- [x] `progress.md`：`current_task=DEV-OPS-003-SMOKE`，`current_task_status=planned`，`next_action=计划审查 / 等待 PLAN_APPROVED`
- [x] 未改 `master_plan.md`；未 Git 写；未建分支；未 Release；未实施 marker
- [x] Plan Reviewer `PLAN_APPROVED`；人工 `PLAN_APPROVED` 已确认；status → `approved`

## 10. 风险与阻塞项

- 设计文档冲突：无（无规格变更）
- 当前代码冲突：progress 历史可能仍写 PR #7 OPEN——须在 smoke 叙述中承认正式任务 MERGED 但未 completed，避免误标 completed
- 前置任务：正式 DEV-OPS-003 实现已 merge；正式 completed 治理可能仍 pending——**不阻塞**本 smoke，但 smoke 不得代替正式 completed
- 未批准依赖：已解除（Plan Review + 人工 `PLAN_APPROVED`）
- API/Schema 变化：无
- 其他风险：误删正式 feat；误改 master_plan；误启 DEV-004；把契约通过当成 E2E

## 11. Git 计划

```yaml
branch: "feat/DEV-OPS-003-SMOKE-normal-workflow"
# PLAN_LANDING：main 上 docs(plan) + 创建 exact feat
expected_commits:
  - "docs(plan): add DEV-OPS-003-SMOKE normal workflow smoke plan"            # PLAN_LANDING；on main
  - "test(e2e): add DEV-OPS-003-SMOKE normal workflow smoke marker"           # IMPLEMENTATION_RELEASE；on feat
  - "docs(status): record DEV-OPS-003-SMOKE implementation commit and PR"     # 可选；on feat only
  - "docs(status): complete DEV-OPS-003-SMOKE after PR merge"                 # POST_MERGE_CLEANUP；on main
release_phases:
  PLAN_LANDING: "仅 NORMAL；人工 PLAN_APPROVED 之后（本 phase 执行中）"
  IMPLEMENTATION_RELEASE: "仅 feat；禁 push/commit main"
  POST_MERGE_CLEANUP: "仅 NORMAL 且 PR MERGED；仅删 exact smoke feat"
out_of_scope_changes:
  - "02_开发管理/master_plan.md"
  - "src/**"
  - ".cursor/**"
  - "正式 DEV-OPS-003 实现与正式 feat 删除"
  - "DEV-004 任何文件"
  - "gh pr merge / force / hard reset / clean -fd / git branch -D"
```

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-08 01:26 UTC | Planner 起草 | 新建本 Task Plan；progress 规划态 → DEV-OPS-003-SMOKE | 无 | 本轮止于等待 PLAN_APPROVED；未 Git 写；未改 master_plan |
| 2026-08-08 01:30 UTC | PLAN_LANDING | status → approved；docs(plan) 白名单两路径；创建 exact feat | 无 | 人工 PLAN_APPROVED 已确认；marker 仍未创建 |
| 2026-08-08 01:32 UTC | Developer | approved → in_progress → implemented → tested；创建 smoke marker | 文件内容精确断言通过；可选 unit 见下 | 仅白名单三路径；未 Git 写；未改 master_plan/src/.cursor |

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `02_开发管理/tasks/DEV-OPS-003-SMOKE-normal-workflow.md` | status → tested；执行记录回写 |
| `02_开发管理/progress.md` | tested 态回写；仍指向 smoke；正式 DEV-OPS-003 未标 completed |
| `tests/e2e/devops003_normal_workflow_smoke.txt` | 已创建；恰好一行指定 marker 文本 |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Marker 自检 | `test -f` + 精确内容比较（恰好一行指定文本） | **passed**（bytes=58） |
| Unit | `uv run pytest tests/unit -q` | **102 passed**（0.66s） |
| Contract | — | 本 Developer 轮次未改契约源；未强制重跑 |
| Integration | N/A | — |
| E2E | 受监督 NORMAL 全链路 | marker 已落盘；全链路仍 pending（待 Code Review → Release → PR merge） |
| Ruff | — | N/A（无 Python 实现变更） |
| Mypy | — | N/A |

### Review 结果

```yaml
p0: null
p1: null
p2: null
p3: null
review_report: null
plan_review: PLAN_APPROVED（人工已确认）
```

### Git 记录

```yaml
branch: feat/DEV-OPS-003-SMOKE-normal-workflow
plan_commit: ba0d827
implementation_commit: null
implementation_commit_message: null
smoke_pr: null
```

### 最终状态

`tested`（Developer 完成；等待独立 Code Review；未 Git 写）
