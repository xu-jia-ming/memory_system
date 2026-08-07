# DEV-OPS-002-E2E-SMOKE DEV-OPS-002 专用低风险 Orchestrator E2E 冒烟

## 1. 任务信息

```yaml
task_id: DEV-OPS-002-E2E-SMOKE
task_name: DEV-OPS-002 专用低风险 Orchestrator E2E 冒烟
status: approved
spec_sections:
  - "非业务：执行父任务 DEV-OPS-002 §9 受监督低风险完整 E2E；不修改技术规格正文"
prerequisites:
  - "父任务 DEV-OPS-002 status=implemented（UI discovery passed；完整 E2E pending）"
  - "父计划：02_开发管理/tasks/DEV-OPS-002-cursor-orchestrator-subagents-release.md"
  - "隔离 E2E 副本仓库；规划基线分支 test/DEV-OPS-002-e2e-base 存在且干净"
  - "基线 Commit dd5e158 test(e2e): prepare DEV-OPS-002 orchestrator baseline"
  - "tests/e2e/ 仅有空 .gitkeep；尚无 devops002_orchestrator_smoke.txt"
branch: "feat/DEV-OPS-002-e2e-smoke"
planning_baseline_branch: "test/DEV-OPS-002-e2e-base"
implementation_branch: "feat/DEV-OPS-002-e2e-smoke"
created_at: "2026-08-07 03:03 UTC"
updated_at: "2026-08-07 03:22 UTC"
approval_gates:
  planning_docs: "已人工确认 PLAN_APPROVED（Round 2；BLOCKER=0 / MUST_FIX=0 / SHOULD_FIX=0；含 Amendment 001）；approved 仍不得实施；下一步人工 docs(plan) 后创建 feat/DEV-OPS-002-e2e-smoke"
  parent_e2e_gate: "本任务通过并完成 PR create 后，父任务 DEV-OPS-002 方可标 tested；此前不得 Code Review/completed"
```

## 2. 任务目标

作为 **DEV-OPS-002 的专用低风险完整 E2E 冒烟任务**（非业务实现），在隔离副本上走通 Orchestrator 全角色链路，验证：

1. Orchestrator 能按状态机顺序调用：Planner → Plan Reviewer → Developer → Code Reviewer → Commit Recorder → Release Operator。
2. Developer 仅新增精确白名单文件 `tests/e2e/devops002_orchestrator_smoke.txt`，内容恰好为单行 `DEV-OPS-002_ORCHESTRATOR_E2E_OK` + trailing newline。
3. Release Operator 在人工确认后，仅对该白名单路径执行受控 `git add` / `git commit` / `git push`（禁止 force），并以 `test/DEV-OPS-002-e2e-base` 为 base 创建 PR；**创建 PR 后立即停止**。
4. 客观验收命令通过（见 §8 / §9）；失败即 halt，不得伪造后续阶段。

本任务成功用于解除父任务 DEV-OPS-002 的「完整 E2E pending」阻塞（由人工/Orchestrator 回写父任务状态）；**本任务本身不是业务功能交付**。

## 3. 非目标

- 修改任何业务代码、依赖、配置、Migration、Compose、API/Schema/Contract。
- 修改既有 `.cursor/commands/**`、`.cursor/agents/**`、`.cursor/permissions.json`、CLI 权限文件、治理规则正文（除本任务规划文档登记外）。
- 修改既有测试语义或新增 pytest/契约测试文件。
- 修改父任务 DEV-OPS-002 的业务目标、白名单或 Contract。
- 自动 Merge、`gh pr merge`、删分支、`git push --force`、`git rebase`、`git reset --hard`、`git clean -fd`、`git branch -D`。
- 直接向 `main` 或规划基线 `test/DEV-OPS-002-e2e-base` 写实现 Commit。
- 将契约-only / 只读 replay 计为完整 E2E。
- 启动真实基础设施（Compose/DB/Embedding）。
- 开始 DEV-002 或插入 DEV-OPS-003 / Phase B。
- 本冒烟任务**不**交付「E2E 不可行时的降级实现」；对齐父任务 §9：若完整 E2E 不可行，由**人工/Orchestrator**回退 DEV-OPS-001 五 Slash Commands（`/plan-task`、`/review-plan`、`/develop-task`、`/review-code`、`/close-task`），**非**本任务白名单交付物。

## 4. 当前代码状态

- 已存在代码：
  - 父任务 DEV-OPS-002 实现已落地（Orchestrator、六 Subagent、permissions、治理窄例外、契约测试）；状态 `implemented`；UI discovery passed。
  - `tests/e2e/.gitkeep` 存在（空目录占位）。
- 可复用组件：
  - 既有 Orchestrator / 六角色 Subagent 与 Release Operator 受控 Git 写门禁（只调用，不修改）。
- 当前缺失：
  - `tests/e2e/devops002_orchestrator_smoke.txt`（实施阶段唯一新增交付物）。
  - 本 Task Plan（规划阶段创建）。
- 与技术规格不一致之处：
  - 无。本任务为非业务 E2E 冒烟，不触及规格 Contract。
- 前置任务检查：
  - DEV-OPS-001 `completed`；DEV-OPS-002 `implemented` 且完整 E2E pending — 与 Orchestrator 环境事实一致。
  - 当前分支（只读核对）：`test/DEV-OPS-002-e2e-base`；最新 commit `dd5e158`；工作区规划前干净（Orchestrator 编排态已切 progress 字段）。

## 5. 实现方案

### Step 0 — 计划批准与分支准备（人工 / Orchestrator；非 Developer）

- 独立 Plan Reviewer 输出 `PLAN_APPROVED` 后，人工将本任务标为 `approved`（此时仍不得实施）。
- 人工或受控流程：在规划基线 **`test/DEV-OPS-002-e2e-base`** 上提交本 Task Plan / master_plan / progress 的 `docs(plan)`（若需落盘）。**规划/治理文档仅经本 Step 落盘**；不得经实施态 Release Operator 混入实现 Commit。
- 再从 **`test/DEV-OPS-002-e2e-base`** 创建实施分支 **`feat/DEV-OPS-002-e2e-smoke`**。
- Developer 仅在：`PLAN_APPROVED` 已确认、状态可切 `in_progress`、当前分支为 `feat/DEV-OPS-002-e2e-smoke`、工作区干净时开始编码。

### Step 1 — Developer：仅新增冒烟标记文件

- 文件：`tests/e2e/devops002_orchestrator_smoke.txt`（**创建**）
- 类/函数/Schema：无
- 输入：无运行时输入
- 输出：文件内容必须**恰好**为：

```text
DEV-OPS-002_ORCHESTRATOR_E2E_OK
```

  （即该单行字符串 + 一个 trailing newline；不得有多余空行、空格、BOM 或其它字符）
- 错误处理：若文件已存在且内容不符 → 停止并报告；不得静默覆盖为错误内容；不得改其它文件「修复」。
- 幂等/并发/事务要求：单文件写入；重复执行应以内容精确匹配为成功条件。

### Step 2 — 验证（Developer / Code Reviewer 门禁）

执行 §8 测试命令；全部通过后才可将本任务标 `tested` 并进入 Code Review。

### Step 3 — Commit Recorder → Release Operator（人工确认后）

- Commit Recorder：只读核对白名单与草稿；输出 `READY_FOR_HUMAN_COMMIT`；**不**执行 Git 写。
- Release Operator（须人工确认一次后）：
  1. `git add -- tests/e2e/devops002_orchestrator_smoke.txt`（**仅**允许此精确路径；**禁止** `git add` 任何规划/治理文档或其他路径；progress / master_plan / Task Plan **不得**经本步混入）
  2. `git commit`（Conventional Commit；禁止 `--no-verify` / force 类旗标；Commit 内容应仅含上述白名单文件）
  3. `git push -u origin HEAD`（**禁止** `--force` / `--force-with-lease`）
  4. `gh pr create`，**base = `test/DEV-OPS-002-e2e-base`**，head = `feat/DEV-OPS-002-e2e-smoke`
  5. 创建 PR 后**立即停止**；输出 `RELEASE_COMPLETED`（附真实 Hash/PR）或失败时 `RELEASE_OPERATOR_FAILED`
- 每条 shell 必须检查退出码；非零 → 立即失败停止。

### Step 4 — 禁止操作（全程）

- `git merge` / `gh pr merge` / `git rebase` / `git push --force` / `git reset --hard` / `git clean -fd` / `git branch -D` / 删远程分支
- 修改白名单外任何路径
- 向 `main` 或 `test/DEV-OPS-002-e2e-base` 推送实现 Commit

## 6. 文件变更清单

### 6.1 规划阶段（仅 Planner；本轮）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `02_开发管理/tasks/DEV-OPS-002-E2E-SMOKE.md` | 创建 | 本 Task Plan |
| `02_开发管理/master_plan.md` | 修改（追加登记 + CHANGE） | 登记 E2E smoke 任务；不改业务任务目标 |
| `02_开发管理/progress.md` | 修改（规划态字段） | `current_task_status=approved`；下一步人工 `docs(plan)` 后创建 feat；仍不得实施 |

### 6.2 实施阶段白名单（Developer；`PLAN_APPROVED` 后方可）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/e2e/devops002_orchestrator_smoke.txt` | **仅创建** | E2E 冒烟标记文件；内容精确固定 |

**实施阶段精确白名单（唯一）**：

```text
tests/e2e/devops002_orchestrator_smoke.txt
```

**Release Operator `git add` 范围**：与上表完全一致——**仅** `tests/e2e/devops002_orchestrator_smoke.txt`。§6.1 规划/治理路径**不**在实施白名单，亦**不**在 Release `git add` 允许集；仅经 Step 0 `docs(plan)` 在基线 `test/DEV-OPS-002-e2e-base` 落盘。

### 6.3 黑名单（明确禁止）

| 路径/范围 | 说明 |
|---|---|
| `src/**`、业务测试、依赖锁、Compose、配置 | 禁止 |
| `.cursor/**`、既有 commands/agents/permissions | 禁止修改 |
| `03_AI_Prompts/**`、规格正文 | 禁止 |
| 既有 `tests/unit/**` 等 | 禁止修改语义 |
| 父任务 `DEV-OPS-002-*.md` 目标/白名单 | 禁止静默改写 |

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用（无多存储事务） | 单文件创建；Git Commit 作为发布原子边界 |
| 幂等 | 适用 | 文件内容精确匹配即视为已达成；重复写入不得改变语义 |
| 并发 | 不适用 | 单人/单 Orchestrator 串行 E2E；禁止并行改同一白名单 |
| 版本冲突 | 不适用 | 无业务 version 字段 |
| 用户隔离 | 不适用 | 无多租户数据 |
| 部分失败 | 适用 | 任一角色/命令失败 → halt；不得伪造后续结束标记或状态 |
| 进程异常恢复 | 部分适用 | 从 `progress.md` + 只读 git 恢复；不得猜测已 push/已建 PR |

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 不适用 | 本任务不新增/不修改 unit 测试 |

### Contract Test

| 场景 | 预期 |
|---|---|
| 不适用 | 不改 API/Schema；不改 orchestrator 契约测试正文 |

### Integration Test

| 场景 | 预期 |
|---|---|
| 不适用 | 不启动基础设施 |

### E2E Test（本任务主体；强制）

| 场景 | 预期 |
|---|---|
| 全角色链路 | Orchestrator → Planner → Plan Reviewer → Developer → Code Reviewer → Commit Recorder → Release Operator 顺序执行；失败即停 |
| 白名单文件字符串本体 | `test "$(cat tests/e2e/devops002_orchestrator_smoke.txt)" = "DEV-OPS-002_ORCHESTRATOR_E2E_OK"` 退出码 0。**说明**：Bash `$(cat …)` 会剥离全部尾部换行，本命令**仅**验字符串本体，**不能单独**证明「恰好一个 trailing newline」 |
| trailing newline（另验） | 客观字节级比较通过（见下方强制命令第 3 条）；证明内容恰好为该字符串 + **一个**换行、无多余字符 |
| `git diff --check` | 退出码 0（无冲突标记/空白错误） |
| Release | 人工确认后：仅白名单 txt 的 `git add` → commit → push `feat/DEV-OPS-002-e2e-smoke` → `gh pr create`（base=`test/DEV-OPS-002-e2e-base`）→ 立即停止；不得混入治理文档 |
| 禁止操作未发生 | 无 merge/force/rebase/reset/clean/删分支 |

**强制验证命令（至少；均须退出码 0）**：

```bash
git diff --check
test "$(cat tests/e2e/devops002_orchestrator_smoke.txt)" = "DEV-OPS-002_ORCHESTRATOR_E2E_OK"
cmp -s tests/e2e/devops002_orchestrator_smoke.txt <(printf '%s\n' 'DEV-OPS-002_ORCHESTRATOR_E2E_OK')
```

- 第 1 条：空白/冲突标记检查。
- 第 2 条：字符串本体（保留硬约束；不单独证明 trailing newline）。
- 第 3 条：`cmp` + `printf '%s\n'` 客观验证恰好一个 trailing newline（字节级一致）。

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 白名单外路径出现在 `git status` | Release Operator 必须失败停止 |
| 未获人工确认即 Release | 禁止执行 Git 写 |
| 未获 `CODE_REVIEW_APPROVED` | 不得触发 Release Operator |
| 内容字符串错误 | `test "$(cat …)" = "…"` 失败；不得标 tested |

### 人工 UI / 编排冒烟

| 场景 | 预期 |
|---|---|
| 受监督完整编排（父任务 §9） | 人工记录结果；PR create 后停止 |
| 契约-only | **不计**本任务完成 |

## 9. 验收标准

- [ ] 实施分支为 `feat/DEV-OPS-002-e2e-smoke`；规划基线为 `test/DEV-OPS-002-e2e-base`
- [ ] 实施阶段**仅**新增 `tests/e2e/devops002_orchestrator_smoke.txt`
- [ ] 文件内容恰好为 `DEV-OPS-002_ORCHESTRATOR_E2E_OK` + **一个** trailing newline（由 `cmp`/`printf` 客观证明；非仅靠 `cat` 比较）
- [ ] `git diff --check` 通过
- [ ] `test "$(cat tests/e2e/devops002_orchestrator_smoke.txt)" = "DEV-OPS-002_ORCHESTRATOR_E2E_OK"` 通过（字符串本体）
- [ ] `cmp -s tests/e2e/devops002_orchestrator_smoke.txt <(printf '%s\n' 'DEV-OPS-002_ORCHESTRATOR_E2E_OK')` 通过（含恰好一个 trailing newline）
- [ ] 未修改业务代码、依赖、配置、既有命令/Agent/既有测试
- [ ] Release Operator 仅在人工确认后：**仅**对 `tests/e2e/devops002_orchestrator_smoke.txt` 执行 `git add` → `commit` → `push`（无 force）→ 以 `test/DEV-OPS-002-e2e-base` 为 base 创建 PR → 立即停止；**未**将 progress/master_plan/Task Plan 混入该 Release
- [ ] 未执行 Merge / 删分支 / force push / rebase / reset / clean
- [ ] Review 无 P0/P1（针对本冒烟变更）
- [ ] Ruff / Mypy：**不适用新增 Python**；不得为通过而改既有质量门禁或跳过父任务既有门禁要求

## 10. 风险与阻塞项

- 设计文档冲突：无（非业务；对齐父任务 §9）
- 当前代码冲突：无；`tests/e2e/` 仅 `.gitkeep`
- 前置任务：父任务 DEV-OPS-002 必须保持 `implemented` 且实现文件可用；E2E 失败则父任务不得标 `tested`
- 未批准依赖：已人工确认 `PLAN_APPROVED` 且状态 `approved`，但**仍不得实施** txt，直至人工 `docs(plan)` 落盘并创建 `feat/DEV-OPS-002-e2e-smoke`、Developer 前置满足
- API/Schema 变化：无
- 其他风险：
  - IDE `permissions.json` 非安全边界（沿用 DEV-OPS-002）
  - `git push` 前缀与 `--force` 区分不可硬保证 → Release Operator 黑名单 + 人工确认
  - 隔离副本与真实远程权限/网络失败 → `RELEASE_OPERATOR_FAILED`，不得伪造 PR
  - 误用 `main` 作为 PR base → **禁止**；必须 `test/DEV-OPS-002-e2e-base`
  - 误将治理文档经实施态 Release `git add` → **禁止**；治理仅 Step 0 `docs(plan)` 落盘
  - **降级归属（父任务 §9）**：完整 E2E 不可行时，由人工/Orchestrator 回退 DEV-OPS-001 五 Slash Commands；**非**本冒烟任务交付物，本任务不实现降级逻辑

## 11. Git 计划

```yaml
planning_baseline_branch: "test/DEV-OPS-002-e2e-base"
implementation_branch: "feat/DEV-OPS-002-e2e-smoke"
pr_base: "test/DEV-OPS-002-e2e-base"
pr_head: "feat/DEV-OPS-002-e2e-smoke"
expected_sequence:
  - "1. 独立 Plan Review → PLAN_APPROVED"
  - "2. 状态回写 approved（不得实施）"
  - "3. 人工 docs(plan) 落盘本 Task Plan/master_plan/progress（仅在基线 test/DEV-OPS-002-e2e-base；不得经实施态 Release）"
  - "4. 从 test/DEV-OPS-002-e2e-base 创建 feat/DEV-OPS-002-e2e-smoke"
  - "5. Developer：仅创建 tests/e2e/devops002_orchestrator_smoke.txt"
  - "6. 验证：git diff --check；test \"$(cat …)\" = \"…\"（字符串本体）；cmp -s … <(printf '%s\\n' '…')（恰好一个 trailing newline）"
  - "7. Code Review → CODE_REVIEW_APPROVED → reviewed"
  - "8. Commit Recorder 草稿 → READY_FOR_HUMAN_COMMIT"
  - "9. 人工确认后 Release Operator：git add 仅 tests/e2e/devops002_orchestrator_smoke.txt / commit / push / gh pr create（base=test/DEV-OPS-002-e2e-base）"
  - "10. 创建 PR 后立即停止；禁止 merge/删分支/force/rebase/reset/clean"
expected_commits:
  - "docs(plan): add DEV-OPS-002-E2E-SMOKE orchestrator e2e smoke plan"
  - "test(e2e): add DEV-OPS-002 orchestrator smoke marker"
out_of_scope_changes:
  - "任何业务代码或依赖变更"
  - "修改 .cursor/agents|commands|permissions"
  - "修改父任务 DEV-OPS-002 目标/白名单"
  - "向 main 推送或以 main 为 PR base"
  - "实施态 Release 混入 progress/master_plan/Task Plan 或其他治理路径"
release_operator_constraints:
  allow:
    - "git add -- tests/e2e/devops002_orchestrator_smoke.txt（唯一允许路径）"
    - "git commit（无 --no-verify / 无 amend 除非用户规则显式允许且门禁满足；内容仅含上述白名单文件）"
    - "git push（禁止 force）"
    - "gh pr create / gh pr view"
  deny:
    - "git merge / gh pr merge"
    - "git rebase / git push --force / git reset --hard / git clean -fd"
    - "git branch -D / 删远程分支"
    - "白名单外 git add（含 progress.md / master_plan.md / Task Plan / 任何治理回写路径）"
    - "直接向 main 或 test/DEV-OPS-002-e2e-base 写实现 Commit"
```

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001（Round 2；PLAN_REJECTED 后修订）

- 日期：2026-08-07 03:15 UTC
- 原计划：Round 1 Task Plan（`updated_at` 2026-08-07 03:03 UTC）
- 修改内容：
  - **MF-001**：删除 Step 3「允许同时…治理回写路径」扩展表述；明确 Release Operator `git add` **仅**允许 `tests/e2e/devops002_orchestrator_smoke.txt`；规划/治理文档仅经 Step 0 `docs(plan)` 在基线落盘，不得经实施态 Release 混入；§6.2 / §9 / §11 同步收窄。
  - **SF-001**：澄清 `test "$(cat …)"` 仅验字符串本体（Bash 剥离尾部换行）；强制命令保留前两条并新增 `cmp -s … <(printf '%s\n' '…')` 客观验恰好一个 trailing newline；§8/§9 同步。
  - **SF-002**：§3 非目标与 §10 风险补齐父任务 §9 降级归属——E2E 不可行时由人工/Orchestrator 回退 DEV-OPS-001 五 Slash Commands；非本冒烟交付物。
- 修改原因：落实 Round 1 Plan Reviewer 全部意见（MUST_FIX + SHOULD_FIX）。
- 是否影响技术规格：否
- 审批状态：Round 2 Plan Reviewer `PLAN_APPROVED`（BLOCKER=0 / MUST_FIX=0 / SHOULD_FIX=0）；**已人工确认**；status=`approved`；仍不得实施

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-07 03:03 UTC | Planner 创建 Task Plan；登记 master_plan / progress | 仅规划文档 | 未实施 | 等待计划审查 |
| 2026-08-07 03:15 UTC | Planner Amendment 001（Round 2）：落实 MF-001 + SF-001 + SF-002 | 仅修订本 Task Plan + progress/master_plan 规划态 | 未实施 | Round 1 PLAN_REJECTED 后修订；等待计划复审 |
| 2026-08-07 03:22 UTC | 人工确认 PLAN_APPROVED；planned → approved | 仅本 Task Plan + master_plan + progress 状态回写 | 未实施 | Round 1 PLAN_REJECTED 与 Amendment 001 历史保留；下一步人工 docs(plan) 后创建 feat；approved 仍不得实施 |

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
|  |  |

### 与原计划的差异

Amendment 001（见 §12）：收窄 Release `git add`；增补 trailing newline 客观检查；补齐 §9 降级归属说明。实施交付物范围不变。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | n/a |  |
| Contract | n/a |  |
| Integration | n/a |  |
| E2E | `git diff --check`；`test "$(cat …)" = "…"`（本体）；`cmp -s … <(printf '%s\n' '…')`（换行） | 待实施 |
| Ruff | n/a（无新增 Python） |  |
| Mypy | n/a（无新增 Python） |  |

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
pr_url: null
pr_base: "test/DEV-OPS-002-e2e-base"
```

### 最终状态

`approved`（仍不得实施；下一步人工 `docs(plan)`，随后创建 `feat/DEV-OPS-002-e2e-smoke`）
