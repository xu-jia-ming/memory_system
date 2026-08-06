# DEV-OPS-001 Cursor Agent 工作流自动化

## 1. 任务信息

```yaml
task_id: DEV-OPS-001
task_name: Cursor Agent 工作流自动化
status: completed
completed_at: "2026-08-06 15:30 UTC"
spec_sections:
  - "非业务规格任务：对齐仓库治理与 03_AI_Prompts 角色流程；不修改技术规格正文"
prerequisites:
  - "DEV-001 completed（工程骨架与质量工具已就绪；本任务不依赖其业务代码变更）"
  - "当前工作区干净；默认分支 main 与 origin/main 同步"
branch: "feat/DEV-OPS-001-cursor-workflow-commands"  # 实施分支；计划 Commit 在 main，见 §13
created_at: "2026-08-06 14:03 UTC"
updated_at: "2026-08-06 15:33 UTC"
approval_gates:
  planning_docs: "Round 2 复审通过；PLAN_APPROVED"
  implementation_plan: "status=completed；CODE_REVIEW_APPROVED；实现 Commit 69fabb7；治理 committed Commit 5d00a49；PR #2 merged（57800c3）；最终 docs(status) 待人工提交"
```

## 2. 任务目标

减少人工重复粘贴长提示词，在仓库内建立**项目级 Cursor Slash Commands**（beta），使各开发阶段可由人工显式 `/` 调用对应角色流程。

完成后应具备：

1. 恰好 5 个项目级命令文件（见 §5.1 白名单），内容为普通 Markdown。
2. 每个命令在正文中强制：读取治理规则与相关计划文档；执行允许的只读检查；按角色限制可写范围；运行该阶段验证；输出明确结束标记。
3. 每个命令明确禁止 Agent 执行 Git Add / Commit / Push / Merge / Rebase / 强制删除分支。
4. 保留 Planner、Plan Reviewer、Developer、Code Reviewer、Commit Recorder 的角色隔离（一人一命令；不得合并为超级 Agent）。
5. 强制新增并通过 `tests/unit/test_cursor_commands_contract.py` 静态契约测试（文件存在性 + 最小必含子串 + 角色隔离断言）。

### 2.1 完整状态机（本任务与仓库统一）

```text
planned
→ PLAN_APPROVED          # 独立 Plan Reviewer 口令（会话输出）
→ approved               # 立即回写 Task Plan / master_plan / progress；此时不得实施
→ in_progress            # 仅当 /develop-task 开始且前置检查通过后
→ implemented
→ tested
→ reviewed
→ committed
→ completed
```

强制澄清：

1. Plan Reviewer 通过并输出 `PLAN_APPROVED` 后，**先**将 Task Plan、`master_plan.md`、`progress.md` 更新为 `approved`。
2. `approved` **不等于**允许编码；此时仍不得创建 `.cursor/commands/` 或修改白名单实现文件。
3. 仅当人工调用 `/develop-task`，且确认计划状态为 `approved`、门禁记录含 `PLAN_APPROVED`、分支/任务解析通过后，才将状态从 `approved` → `in_progress` 并开始实施。
4. Round 2 已输出 `PLAN_APPROVED`；当前状态为 `approved`；在人工 `docs(plan)` 与 `/develop-task` 前置通过前，不得进入 `in_progress`，不得创建 `.cursor/commands/`。

### 2.2 已确认的 Cursor Commands 能力边界（本计划唯一产品依据）

下列事实以人工确认的官方「Cursor – Commands」文档（`docs.cursor.com`，路径 `agent/chat/commands`）为准；**不得扩展猜测**：

| 事实 | 说明 |
|---|---|
| 存放位置 | 项目级自定义命令存放于 `.cursor/commands/*.md` |
| 文件格式 | 命令内容为**普通 Markdown** |
| 调用方式 | 在 Agent 输入框输入 `/` 后选择命令调用 |
| 稳定性 | Commands 当前仍属 **beta**，语法与能力可能变化 |

仓库现状（规划时核查）：`.cursor/commands/` **尚不存在**；仅有 `.cursor/rules/00-memory-system-governance.mdc`。

### 2.3 任务编号 / Task Plan / 分支信息的获取策略（禁止假设产品参数）

官方文档**未确认**命名参数、模板变量替换或自动注入机制。因此本任务**不得**依赖诸如 `$ARGUMENTS`、`{TASK_ID}` 产品级替换、隐藏 frontmatter 参数 schema 等未证实能力。

每个命令正文必须采用下列**可验证、文档内约定**的解析顺序：

```text
1) 若同一条用户消息在选择 /command 之后仍包含显式字段，则优先采用用户显式值：
   - TASK_ID: <id>
   - TASK_PLAN: <相对仓库根的路径>
   - BRANCH: <分支名>（可选；仍须用只读 git 核对）
2) 否则读取 02_开发管理/progress.md 顶部 YAML 块中的：
   - current_task
   - current_plan_file
   - current_branch
3) 用只读 git 核对：
   - git branch --show-current
   - git status --short
   - git log --oneline -10
4) 若 TASK_ID / current_plan_file 缺失、冲突或与打开的 Task Plan 头信息不一致：
   - 停止；列出冲突；不得猜测；不得改业务代码
```

说明：步骤 1 依赖「用户在调用命令的同一条聊天消息里手写字段」。这是**流程约定**，不是已证实的产品参数 API。若未来官方确认参数机制，须经 Plan Amendment 后再改命令正文（见 Open Issue OI-OPS-001）。

## 3. 非目标

- 修改任何业务代码、`pyproject.toml`、`uv.lock`、`src/`、`scripts/`（本任务工程实现范围外的文件）。
- **禁止修改既有 DEV-001 测试的语义和断言**（例如不得改动 `tests/unit/test_entrypoints_import.py`、`tests/unit/test_dependency_contract.py` 的既有断言）。
- **允许且要求新增** `tests/unit/test_cursor_commands_contract.py`（见 §5.3）。
- 开始 DEV-002 或任何 Phase 0+ 业务任务实施。
- 修改技术规格正文 `01_技术规格/...`。
- 配置 Custom Modes / 复杂自定义 Agent Mode。
- 实现自动 Commit、自动 Push、自动 Merge、自动创建/删除远程分支。
- 把全部阶段合并为一个超级 Agent 或单个超级命令。
- 若官方未来提供将 Commands 迁移为 Skills 的能力，也不属于本任务范围（见 OI-OPS-003）；本任务不创建 `.cursor/skills/`。
- 假设或实现未证实的命令参数/变量替换/自动角色切换产品能力。
- Agent 执行 `git add` / `git commit` / `git push` / `git merge` / `git rebase` / Force Push / 强制删除分支。
- Agent 猜测或提前写入尚未产生的 Git Commit Hash。
- 修改已完成的 DEV-001 完成记录语义（仅允许在 master_plan/progress 中**追加**本任务登记）。

## 4. 当前代码状态

- 已存在：DEV-001 工程骨架；`.cursor/rules/00-memory-system-governance.mdc`；完整 `03_AI_Prompts/` 提示词；DEV-001 Task Plan 可作为状态机与 Git 流程参考。
- 可复用：`03_AI_Prompts/02_任务计划.md`、`03_计划审查.md`、`04_任务开发.md`、`06_代码审查.md`、`08_Git提交.md` 的角色约束与检查清单（命令正文应**内化**其约束，而不是要求用户再粘贴）。
- 当前缺失：`.cursor/commands/` 目录及五个命令文件；`tests/unit/test_cursor_commands_contract.py`。
- 与技术规格不一致之处：无（本任务不改规格 Contract）。
- 前置任务检查：DEV-001 = `completed`；`main` 与 `origin/main` 同步；工作区干净（规划时核查）。

## 5. 文件白名单（本任务允许创建/修改的全部路径）

实施时**仅允许**下列路径。禁止通配描述为“整个 `.cursor/`”。

### 5.1 命令文件（实施阶段创建；本规划轮次不得创建）

| 路径 | 唯一角色 | 结束标记（命令必须要求输出） |
|---|---|---|
| `.cursor/commands/plan-task.md` | Planner | `READY_FOR_PLAN_REVIEW` |
| `.cursor/commands/review-plan.md` | Plan Reviewer | 无 BLOCKER/MUST_FIX 时最后一行 `PLAN_APPROVED`；否则最后一行 `PLAN_REJECTED` |
| `.cursor/commands/develop-task.md` | Developer | `READY_FOR_CODE_REVIEW` |
| `.cursor/commands/review-code.md` | Code Reviewer | 无 P0/P1 且允许进入提交准备时 `CODE_REVIEW_APPROVED`；否则 `CODE_REVIEW_REJECTED` |
| `.cursor/commands/close-task.md` | Commit Recorder | `READY_FOR_HUMAN_COMMIT`（仅表示人工可提交核对已完成；**不是** Agent 已提交） |

角色集合必须恰好为上述五者；每个命令**分别对应且仅对应**一个角色；禁止多角色合并。

### 5.2 开发管理文档（实施与状态回写允许）

| 路径 | 允许操作 |
|---|---|
| `02_开发管理/tasks/DEV-OPS-001-cursor-agent-workflow-commands.md` | 状态机与执行记录回写；Amendment |
| `02_开发管理/master_plan.md` | 仅本任务状态字段与变更记录追加 |
| `02_开发管理/progress.md` | 当前任务/状态/next_action 等回写；不得抹去 DEV-001 已完成表行 |

### 5.3 静态契约测试（**强制**；非可选）

| 路径 | 说明 |
|---|---|
| `tests/unit/test_cursor_commands_contract.py` | **必须创建**；仅用标准库 + 已声明 pytest；断言 §5.1 五文件存在、§7.1 最小必含子串、角色一一对应、禁止超级 Agent 合并；不得新增依赖；不得修改 DEV-001 既有测试语义 |

## 6. 文件黑名单（禁止本任务创建或修改）

| 路径 / 模式 | 原因 |
|---|---|
| `src/**`、`scripts/**` | 业务/工程实现 |
| `configs/**`、`.env.example` | DEV-002 |
| `Dockerfile`、`compose*.yaml`、`versions.*` | DEV-003 |
| `01_技术规格/**` | 禁止改规格正文 |
| `03_AI_Prompts/**` | 本任务通过命令内化约束；不改提示词源文件（见 OI-OPS-004） |
| `.cursor/rules/**` | 不在候选范围；治理 rule 已存在 |
| `.cursor/skills/**`、`.agents/skills/**` | 非本任务范围 |
| Custom Modes / 自定义 Agent Mode 配置 | 非目标 |
| 除 §5.1 五个白名单命令外的其他 `.cursor/**` 配置 | 禁止扩大 Cursor 配置面 |
| `~/.cursor/commands/**`（用户级） | 非项目级交付物 |
| 既有 DEV-001 测试文件的语义/断言修改 | 禁止 |
| 任何 Git hooks / 自动 commit 脚本 | 禁止自动 Git 写 |
| DEV-002+ 业务 Task Plan 实施内容 | 非目标 |

## 7. 实现方案

### Step 0 — 状态回写（强制，贯穿全程）

状态迁移必须遵守 §2.1，分阶段写入 Task Plan 与 `progress.md` / `master_plan.md`：

| 触发条件 | 状态 |
|---|---|
| 本修订轮次 / 计划未获批 | `planned`（历史） |
| 独立 Plan Reviewer 输出 `PLAN_APPROVED` | 立即 → `approved`（回写三文档；**不得实施**；**当前**） |
| `/develop-task` 开始且前置检查通过 | `approved` → `in_progress` |
| 五个命令文件 + 契约测试已落地 | `implemented` |
| `uv run pytest tests/unit/test_cursor_commands_contract.py` 与相关质量门禁通过 | `tested` |
| 独立 Code Review 通过（`CODE_REVIEW_APPROVED`） | `reviewed` |
| 人工实现 Commit 完成 | `committed` |
| PR 合并后治理回写 | `completed` |

**禁止**仅在任务结束时一次性补写上述状态。
**禁止**在 `approved` 阶段创建 `.cursor/commands/` 或开始编码。

### Step 1 — 创建目录、五个命令 Markdown 与契约测试

- 创建 `.cursor/commands/`。
- 仅创建 §5.1 五个文件；普通 Markdown；文件名即 `/` 菜单中的命令名。
- **必须**创建 `tests/unit/test_cursor_commands_contract.py`。
- Steps 2–6 每个命令文件**统一**使用下列六段结构（标题可同名；顺序固定）：

```text
# <命令标题>
## 角色
## 必读文件
## 前置只读检查
## 允许修改范围
## 阶段验证
## 结束标记
```

### Step 2 — `plan-task.md`（Planner）

统一六段，并内化 `03_AI_Prompts/02_任务计划.md` 与治理约束：

| 段 | 要求 |
|---|---|
| 角色 | 唯一角色 = Planner；含「不得自动切换到下一角色」 |
| 必读文件 | 治理规则、`master_plan.md`、`progress.md`、规格相关章节、Task Plan 模板、相关代码 |
| 前置只读检查 | §2.3 解析；`git status` / `git branch` / `git log` 只读 |
| 允许修改范围 | 仅当前任务 Task Plan + `progress.md`（规划态字段）；禁止业务代码/既有测试语义/依赖/Migration；禁止 Git 写 |
| 阶段验证 | Task Plan 模板字段齐全；`progress.md` 中 `current_task_status=planned`，`next_action=计划审查` |
| 结束标记 | 输出 `READY_FOR_PLAN_REVIEW` 并停止 |

### Step 3 — `review-plan.md`（Plan Reviewer）

| 段 | 要求 |
|---|---|
| 角色 | 唯一角色 = Plan Reviewer；含「不得自动切换到下一角色」 |
| 必读文件 | 规格、`master_plan.md`、`progress.md`、目标 Task Plan、相关代码/测试 |
| 前置只读检查 | §2.3；确认审查对象路径；禁止编写业务代码 |
| 允许修改范围 | **只读零修改**（审查意见仅输出到会话；状态 `approved` 回写由获批后的约定流程完成，本命令不得跳到 `in_progress`） |
| 阶段验证 | 输出 BLOCKER / MUST_FIX / SHOULD_FIX；核对 §2.1 状态机与 Git 顺序 |
| 结束标记 | 无 BLOCKER 且无 MUST_FIX → 最后一行 `PLAN_APPROVED`；否则最后一行 `PLAN_REJECTED` |

获 `PLAN_APPROVED` 后的文档回写规则：将 Task Plan / master_plan / progress 更新为 `approved`，**停止**；不得实施。

### Step 4 — `develop-task.md`（Developer）

| 段 | 要求 |
|---|---|
| 角色 | 唯一角色 = Developer；含「不得自动切换到下一角色」 |
| 必读文件 | 已批准 Task Plan、`progress.md`、`master_plan.md`、治理规则、白名单相关现有文件 |
| 前置只读检查 | 计划状态必须为 `approved`；存在 `PLAN_APPROVED` 门禁记录；§2.3；确认在实施分支；**通过后才** `approved` → `in_progress` |
| 允许修改范围 | 仅当前 Task Plan 文件变更清单（§5 白名单）；清单外须先 Amendment 并停止 |
| 阶段验证 | 分阶段回写；运行 `uv run pytest tests/unit/test_cursor_commands_contract.py`；若改动 Python 则 ruff/mypy；不得改 DEV-001 既有测试语义 |
| 结束标记 | `READY_FOR_CODE_REVIEW` |

### Step 5 — `review-code.md`（Code Reviewer）

| 段 | 要求 |
|---|---|
| 角色 | 唯一角色 = Code Reviewer；含「不得自动切换到下一角色」 |
| 必读文件 | 规格（若相关）、Task Plan、`progress.md`、`git diff`、契约测试与命令文件 |
| 前置只读检查 | §2.3；确认实现与测试已写入；对照白/黑名单 |
| 允许修改范围 | **只读零修改**（不直接改代码；修复属独立会话） |
| 阶段验证 | P0–P3；复跑契约测试；核对角色隔离与结束标记 |
| 结束标记 | 无 P0/P1 且允许进入人工提交准备 → `CODE_REVIEW_APPROVED`；否则 `CODE_REVIEW_REJECTED` |

**禁止**使用 `READY_FOR_COMMIT` / `READY_FOR_HUMAN_COMMIT` 作为本命令结束标记。

### Step 6 — `close-task.md`（Commit Recorder）

| 段 | 要求 |
|---|---|
| 角色 | 唯一角色 = Commit Recorder；含「不得自动切换到下一角色」 |
| 必读文件 | Task Plan、`progress.md`、内化自 `03_AI_Prompts/08_Git提交.md` 的**检查清单**要点 |
| 前置只读检查 | 允许只读 `git status` / `git diff` / `git log` / `git branch --show-current`；确认 Code Review 为 `CODE_REVIEW_APPROVED` |
| 允许修改范围 | **默认只读**；仅在人工提交**之后**、且计划允许时，才可回写已真实存在的 Commit Hash 到 Task Plan/progress（**禁止**在 Hash 产生前猜测写入） |
| 阶段验证 | 核对无 Secret、范围仅本任务、契约测试与质量门禁通过；输出 Conventional Commit **草稿消息**与文件清单 |
| 结束标记 | `READY_FOR_HUMAN_COMMIT` |

**明确排除（Agent 不得执行）**：

- `git add`
- `git commit`
- `git push`
- `git merge` / `git rebase` / force push / 强制删分支
- 在 Git Hash 实际产生前猜测并回写 Hash

本命令只内化 Git **检查清单**与 Commit message **草稿**，不执行提交。

### Step 7 — 公共强制条款与最小必含子串表

#### 7.1 每个命令文件必须出现的最小必含子串

契约测试必须对**每一个** §5.1 文件断言包含下列子串（精确匹配，大小写敏感，除非测试显式规定）：

| 必含子串 |
|---|
| `git add` |
| `git commit` |
| `git push` |
| `git merge` |
| `git rebase` |
| `progress.md` |
| `不得自动切换到下一角色` |

说明：上述 Git 子串出现在「禁止执行」语境中；契约测试验证子串存在，命令正文必须将其列为禁止项。

#### 7.2 各命令结束标记（互不混用）

| 命令文件 | 必须要求输出的结束标记 |
|---|---|
| `plan-task.md` | `READY_FOR_PLAN_REVIEW` |
| `review-plan.md` | `PLAN_APPROVED` 或 `PLAN_REJECTED` |
| `develop-task.md` | `READY_FOR_CODE_REVIEW` |
| `review-code.md` | `CODE_REVIEW_APPROVED` 或 `CODE_REVIEW_REJECTED` |
| `close-task.md` | `READY_FOR_HUMAN_COMMIT` |

`review-code` 与 `close-task` **不得**共用 `READY_FOR_COMMIT`。

#### 7.3 角色隔离（契约测试必须客观验证）

1. 五个命令分别对应且仅对应一个角色。
2. 角色集合必须恰好是：`Planner`、`Plan Reviewer`、`Developer`、`Code Reviewer`、`Commit Recorder`。
3. 每个命令必须包含子串 `不得自动切换到下一角色`。
4. 不得把多个角色合并为一个超级 Agent（测试可断言：每个文件仅出现一次其映射角色名作为「唯一角色」声明，且不出现其它四角色的「唯一角色」声明）。

### Step 8 — 静态验收与强制契约测试

- 实现 `tests/unit/test_cursor_commands_contract.py`，覆盖 §10。
- 运行：`uv run pytest tests/unit/test_cursor_commands_contract.py`
- 运行：`uv run pytest tests/unit`（确认未破坏 DEV-001 既有测试）
- 若新增 Python：`uv run ruff check .`、`uv run mypy src tests`

## 8. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `.cursor/commands/plan-task.md` | 创建 | Planner 工作流 |
| `.cursor/commands/review-plan.md` | 创建 | Plan Reviewer 工作流 |
| `.cursor/commands/develop-task.md` | 创建 | Developer 工作流 |
| `.cursor/commands/review-code.md` | 创建 | Code Reviewer 工作流 |
| `.cursor/commands/close-task.md` | 创建 | Commit 前核对（无 Git 写） |
| `tests/unit/test_cursor_commands_contract.py` | 创建（强制） | 命令 Markdown 静态契约 + 角色隔离 |
| `02_开发管理/tasks/DEV-OPS-001-cursor-agent-workflow-commands.md` | 修改 | 状态与执行记录 |
| `02_开发管理/master_plan.md` | 修改 | 任务状态同步 |
| `02_开发管理/progress.md` | 修改 | 当前任务状态同步 |

## 9. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 无跨存储业务写入 |
| 幂等 | 部分适用 | 重复创建同名命令文件应为覆盖同一白名单路径；不得生成额外命令 |
| 并发 | 不适用 | 无共享可变业务状态；多 Agent 会话并发属流程风险，靠角色隔离与人工门禁 |
| 版本冲突 | 不适用 | 无业务乐观锁 |
| 用户隔离 | 不适用 | 无用户资源 |
| 部分失败 | 适用（流程） | 任一命令文件缺失、缺最小必含子串、或缺结束标记则契约测试失败；不得标记 `tested` |
| 进程异常恢复 | 不适用 | 无长跑业务进程 |

## 10. 测试计划

### Unit — `tests/unit/test_cursor_commands_contract.py`（强制）

| 场景 | 预期 |
|---|---|
| §5.1 五个路径均存在 | 断言通过 |
| `.cursor/commands/` 下无白名单外文件 | 断言通过 |
| 每个文件含 §7.1 全部最小必含子串 | 断言通过 |
| 角色映射：五文件 ↔ 五角色一一对应且集合完整 | 断言通过 |
| 每个文件含 `不得自动切换到下一角色` | 断言通过 |
| 各文件含对应结束标记（§7.2） | 断言通过 |
| 不存在将多角色合并为超级 Agent 的正文声明 | 断言通过（按 §7.3） |
| DEV-001 既有 unit 测试未被改语义 | `uv run pytest tests/unit` 中原有用例仍通过 |

### Contract / Integration / E2E / 失败注入

| 层级 | 本任务 |
|---|---|
| Contract（LLM/TEI/Kafka） | 不适用 |
| Integration（Docker） | 不适用 |
| E2E（业务链路） | 不适用 |
| 产品 UI 级“按下 / 菜单必出现命令” | **人工冒烟**（见下）；CI 无 Cursor UI（OI-OPS-005） |

### 人工冒烟（实施后、`reviewed` 前）

| 步骤 | 预期 |
|---|---|
| 在 Agent 输入框输入 `/` | 能看到五个项目命令（名称与文件名对应） |
| 任选一个命令打开 | 注入/展示的正文与仓库文件一致（人工目视） |
| 不进行业务任务实施 | 冒烟仅验证发现与加载 |

### 质量门禁

| 检查 | 预期 |
|---|---|
| 契约测试 | `uv run pytest tests/unit/test_cursor_commands_contract.py` 通过（**强制**） |
| 全量 unit | `uv run pytest tests/unit` 通过 |
| Ruff | `uv run ruff check .` 通过 |
| Mypy | `uv run mypy src tests` 通过 |

## 11. 验收标准

- [x] `.cursor/commands/` 下恰好存在 §5.1 五个文件，无额外命令文件
- [x] 五个文件均为普通 Markdown；均采用 §7 统一六段结构
- [x] 五个命令分别对应且仅对应一个角色；角色集合恰好为 Planner / Plan Reviewer / Developer / Code Reviewer / Commit Recorder
- [x] 每个命令包含「不得自动切换到下一角色」；未合并为超级 Agent
- [x] 结束标记符合 §7.2；`review-code` 与 `close-task` 不共用 `READY_FOR_COMMIT`
- [x] 每个命令含 §7.1 最小必含子串表全部条目
- [x] `tests/unit/test_cursor_commands_contract.py` 已创建且上述断言全部通过
- [x] 未修改既有 DEV-001 测试语义/断言；`uv run pytest tests/unit` 通过
- [x] 任务编号/计划/分支获取符合 §2.3；正文不得宣称未证实的产品参数 API
- [x] `close-task` 仅检查清单 + Commit message 草稿；明确排除 `git add` / `git commit` / `git push` 及 Hash 猜测回写
- [x] 未修改黑名单路径；未改技术规格；未开始 DEV-002 实现；未配置 Custom Modes；未创建 `.cursor/skills/`
- [x] 状态机符合 §2.1：`PLAN_APPROVED` → `approved`（不实施）→ `/develop-task` 才 → `in_progress`
- [x] 人工 `/` 冒烟完成并记录结果
- [x] Review 无 P0/P1
- [x] 状态已按 Step 0 分阶段回写

## 12. 风险与 Open Issues

### 12.1 风险

- Commands 为 beta，语法/发现行为可能变化，导致 `/` 菜单找不到命令或加载方式改变。
- 仅靠 Markdown 提示无法从产品层强制只读；违规依赖模型遵守 + Code Review + 人工门禁。
- `03_AI_Prompts/` 与 `.cursor/commands/` 可能双源漂移（OI-OPS-004）。
- 用户忘记在消息中写 `TASK_ID:` 且 `progress.md` 过期时，Agent 可能选错任务——命令必须要求冲突时停止。

### 12.2 Open Issues（产品/流程未证实项；不得猜测实现）

#### OI-OPS-001 — 命令参数 / 变量替换机制未证实

```yaml
id: OI-OPS-001
status: open
blocks_implementation: false
blocks_claiming_product_params: true
```

官方 Commands 文档未确认：命名参数、`$ARGUMENTS`、模板占位符自动替换、或其它变量注入。本任务采用 §2.3 的 progress.md + 用户消息显式字段约定。若日后官方确认参数机制，须 Amendment 后再改命令。

#### OI-OPS-002 — 自动角色切换未证实

```yaml
id: OI-OPS-002
status: open
blocks_implementation: false
```

未确认产品能在输出结束标记后自动切换角色或自动链式调用下一命令。本任务要求**人工**分会话/分次调用五个命令；命令正文禁止自动进入下一角色。

#### OI-OPS-003 — Commands 与 Skills 的长期关系

```yaml
id: OI-OPS-003
status: open
blocks_implementation: false
```

若官方未来提供将 Commands 迁移为 Skills（或其它形式）的能力，**也不属于本任务范围**。本计划**不宣称**任何具体迁移命令（含 `/migrate-to-skills`）已得到当前官方 Commands 文档确认。是否迁移须另开任务；**不阻塞** DEV-OPS-001 实施。

#### OI-OPS-004 — 提示词源文件是否同步修改

```yaml
id: OI-OPS-004
status: open
blocks_implementation: false
```

本计划默认**不修改** `03_AI_Prompts/**`，由命令内化约束。若审查要求保持单源（提示词 ↔ 命令）同步策略，须 Amendment 明确同步规则或「命令仅引用提示词路径、不复制长文」。

#### OI-OPS-005 — `/` 菜单发现性无法在无 UI 的 CI 中自动证明

```yaml
id: OI-OPS-005
status: open
blocks_implementation: false
manual_smoke_dev_ops_001: passed
manual_smoke_at: "2026-08-06 14:51 UTC"
```

CI 不能替代 Cursor UI 冒烟。验收依赖人工冒烟记录；不得伪造「已在 UI 验证」结果。

**DEV-OPS-001 人工冒烟记录（通过）**：

1. 在 Agent 输入框输入 `/`，五个项目命令全部出现：`plan-task`、`review-plan`、`develop-task`、`review-code`、`close-task`。
2. 命令可被菜单发现与加载。
3. 本次仅验证发现与加载，未触发业务实施。

## 13. Git 计划

```yaml
implementation_branch: "feat/DEV-OPS-001-cursor-workflow-commands"
expected_sequence:
  - "1. 独立 Plan Review"
  - "2. PLAN_APPROVED"
  - "3. 状态更新为 approved（Task Plan / master_plan / progress；不得实施）"
  - "4. 人工在 main 提交 docs(plan): add DEV-OPS-001 cursor agent workflow commands plan"
  - "5. 从 main 创建 feat/DEV-OPS-001-cursor-workflow-commands"
  - "6. Developer（/develop-task）实施：approved → in_progress → …"
expected_commits:
  - branch: "main"
    message: "docs(plan): add DEV-OPS-001 cursor agent workflow commands plan"
    after: "PLAN_APPROVED and status=approved"
  - branch: "feat/DEV-OPS-001-cursor-workflow-commands"
    message: "chore(cursor): add project slash commands and command contract tests"
  - branch: "feat/DEV-OPS-001-cursor-workflow-commands"
    message: "docs(status): record DEV-OPS-001 implementation commit and PR"
  - branch: "main"
    message: "docs(status): complete DEV-OPS-001 after PR merge"
out_of_scope_changes:
  - "业务代码与 DEV-002+ 实现"
  - "技术规格正文"
  - "03_AI_Prompts 源文件（除非 OI-OPS-004 决议后 Amendment）"
  - ".cursor/skills 或 Custom Modes"
  - "修改 DEV-001 既有测试语义"
  - "自动 Git 写脚本或 hooks"
  - "Agent 代为 Add/Commit/Push/Merge/Rebase"
  - "在 Hash 产生前猜测回写"
```

说明：

1. **禁止**将 `docs(plan)` 放在独立 Plan Review / `PLAN_APPROVED` 之前。
2. 顶部 `branch` 表示**实施分支**；计划 Commit 在 `main`，且仅在 `approved` 之后由人工提交。
3. 实现 Commit 在 feat 分支，且仅在 `/develop-task` 进入 `in_progress` 并完成实现与测试后。
4. 治理 `docs(status)` 两条对齐 DEV-001 状态机（committed → completed）。
5. **本规划/修订会话禁止**任何 Git Add/Commit/Push/Merge/Rebase。

## 14. Plan Amendment

### Amendment 001

- 日期：2026-08-06 14:16 UTC
- 独立审查结果：`BLOCKER 0` / `MUST_FIX 4` / `SHOULD_FIX 6` / `PLAN_REJECTED`
- 原计划问题摘要：状态机在 `PLAN_APPROVED` 后直接跳到 `in_progress`；`docs(plan)` 顺序错误；契约测试标为可选导致测试范围矛盾；角色隔离缺少可执行断言；结束标记混用；六段结构与黑名单/必含子串表不完整；Skills 表述过满。
- 修改内容：
  - MF-001：恢复完整状态机 `planned → PLAN_APPROVED → approved → in_progress → …`；明确 `approved` 不实施；仅 `/develop-task` 前置通过后进入 `in_progress`；修订 Step 0 / Step 4 / 验收。
  - MF-002：Git 顺序改为 Review → `PLAN_APPROVED` → `approved` → 人工 `docs(plan)` on main → 创建 feat 分支 → Developer 实施；分支名统一为 `feat/DEV-OPS-001-cursor-workflow-commands`。
  - MF-003：非目标改为禁止改 DEV-001 既有测试语义；强制新增 `tests/unit/test_cursor_commands_contract.py` 并列入白名单/步骤/测试/验收/Git。
  - MF-004：§10/§11 增加可执行角色隔离断言；契约测试必须客观验证。
  - SF：统一 Steps 2–6 六段结构；黑名单显式 Custom Modes / `.cursor/skills/` / 其它 `.cursor/**`；`close-task` 排除 add/commit/push 与 Hash 猜测；最小必含子串表；区分五组结束标记；OI-OPS-003 克制表述。
- 是否影响技术规格：否
- 是否改变任务业务范围：否（仍为五命令 + 契约测试的工作流自动化）
- 审批状态：修订后曾为 `planned`；Round 2 复审已通过（见 §16）
- 本轮禁止（修订当时）：创建 `.cursor/commands/`；Git 写；将状态改为 `approved`（已由后续批准回写解除「待复审」限制，但仍不得实施）

## 15. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-06 14:03 UTC | 计划落盘 | 创建本 Task Plan；登记 master_plan / progress | 无 | status=planned；未创建 `.cursor/commands/`；未 Git 写 |
| 2026-08-06 14:16 UTC | Amendment 001 | 按 MF-001–004 与 SF 全部修订规划文档 | 无 | status 仍为 planned；等待复审；未实施 |
| 2026-08-06 14:25 UTC | Round 2 批准回写 | status=planned → approved；同步 master_plan / progress | 无 | PLAN_APPROVED；未实施；未创建 `.cursor/commands/`；未 Git 写 |
| 2026-08-06 14:42 UTC | /develop-task 前置通过 | status=approved → in_progress；同步 master_plan / progress | 无 | 分支 feat/DEV-OPS-001-cursor-workflow-commands；工作区干净；plan Commit 48a7525 为祖先 |
| 2026-08-06 14:45 UTC | Step 1–6 落地 | 创建五个 `.cursor/commands/*.md` + `tests/unit/test_cursor_commands_contract.py` | 待跑 | status → implemented；未改黑名单；未 Git 写 |
| 2026-08-06 14:46 UTC | §10 自动验证 | 回写测试结果与状态 | 契约 8 passed；unit 20 passed；ruff/mypy 通过 | status → tested；UI 冒烟待人工；未 Git 写 |
| 2026-08-06 14:51 UTC | OI-OPS-005 人工 UI 冒烟 | 仅记录冒烟结果；未改命令/测试 | 人工 `/` 菜单：五命令均可见且可加载 | 冒烟通过；状态保持 tested；未 Git 写 |
| 2026-08-06 15:03 UTC | 独立 Code Review 回写 | status=tested → reviewed；仅改三份治理文档 | 复跑：契约 8 passed；unit 20 passed；ruff/mypy 通过 | CODE_REVIEW_APPROVED；P2/P3 已接受残余、本轮不修复；未改实现；未 Git 写 |
| 2026-08-06 15:23 UTC | 人工实现 Commit + PR 创建 | 实现 Commit `69fabb7`；GitHub PR #2 已创建（open，base main，未 merge） | N/A（治理回写） | status→committed；下一步人工 `docs(status)`、推送分支后再合并 PR #2 |
| 2026-08-06 15:28 UTC | 治理 committed 记录 | 人工 Commit `5d00a49`（`docs(status): record DEV-OPS-001 implementation commit and PR`）于 feat 分支 | N/A（治理回写） | status 保持 committed；PR #2 待合并 |
| 2026-08-06 15:30 UTC | PR 合并与最终治理回写 | PR #2 merged → main（Merge Commit `57800c3`）；治理 committed Commit `5d00a49` 已记录 | N/A（治理回写） | status→completed；最终 docs(status) 待 main 人工提交 |

## 16. 实际执行结果

### 实际修改文件

| 路径 | 操作 |
|---|---|
| `.cursor/commands/plan-task.md` | 创建 |
| `.cursor/commands/review-plan.md` | 创建 |
| `.cursor/commands/develop-task.md` | 创建 |
| `.cursor/commands/review-code.md` | 创建 |
| `.cursor/commands/close-task.md` | 创建 |
| `tests/unit/test_cursor_commands_contract.py` | 创建 |
| `02_开发管理/tasks/DEV-OPS-001-cursor-agent-workflow-commands.md` | 修改（状态与执行记录） |
| `02_开发管理/master_plan.md` | 修改（本任务状态同步） |
| `02_开发管理/progress.md` | 修改（当前任务状态同步） |

### 与原计划的差异

无范围差异。未修改黑名单路径；未改 DEV-001 既有测试语义；未开始 DEV-002；未创建 `.cursor/skills/`；未配置 Custom Modes；未修改 `.cursor/rules/`。OI-OPS-005 人工 UI 冒烟已于 2026-08-06 14:51 UTC 通过（五命令均可发现与加载；仅验证发现与加载，未触发业务实施）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit/静态契约 | `uv run pytest tests/unit/test_cursor_commands_contract.py` | **8 passed** |
| Unit 全量 | `uv run pytest tests/unit` | **20 passed**（含 DEV-001 既有 12 + 本任务 8） |
| UI 冒烟 | `/` 菜单（OI-OPS-005） | **通过**（人工；2026-08-06 14:51 UTC；五命令均可见且可加载；仅验证发现与加载） |
| Ruff | `uv run ruff check .` | **All checks passed** |
| Mypy | `uv run mypy src tests` | **Success: no issues found in 34 source files** |

**Code Review 复跑（2026-08-06 15:03 UTC）**：

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit/静态契约 | `uv run pytest tests/unit/test_cursor_commands_contract.py` | **8 passed** |
| Unit 全量 | `uv run pytest tests/unit` | **20 passed** |
| Ruff | `uv run ruff check .` | **All checks passed** |
| Mypy | `uv run mypy src tests` | **Success: no issues found in 34 source files** |

### Review 结果

```yaml
plan_review:
  round: 1
  blocker: 0
  must_fix: 4
  should_fix: 6
  verdict: PLAN_REJECTED
  amendment: 001
  re_review: completed
  round_2:
    blocker: 0
    must_fix: 0
    should_fix: 0
    verdict: PLAN_APPROVED
    reviewed_at: "2026-08-06 14:25 UTC"
implementation_review:
  reviewed_at: "2026-08-06 15:03 UTC"
  p0: 0
  p1: 0
  p2: 1
  p3: 1
  verdict: CODE_REVIEW_APPROVED
  accepted_residuals:
  - level: P2
    count: 1
    disposition: accepted_non_blocking
    fix_in_this_round: false
    note: 已接受为可维护性/非阻塞残余项；审批后为避免扩大 diff，本轮不修复实现
  - level: P3
    count: 1
    disposition: accepted_non_blocking
    fix_in_this_round: false
    note: 已接受为风格/建议性残余项；审批后为避免扩大 diff，本轮不修复实现
  re_run:
    contract: "8 passed"
    unit: "20 passed"
    ruff: "All checks passed"
    mypy: "Success: no issues found in 34 source files"
```

### Git 记录

```yaml
implementation_branch: feat/DEV-OPS-001-cursor-workflow-commands
current_branch: main
plan_commit: 48a752506943d7aa239f213ee103a7e11561b5dd
implementation_commit: 69fabb7b54f6107c424666f145a2ca68507f3fec
implementation_commit_message: "chore(cursor): add project slash commands and command contract tests"
status_record_commit_committed: 5d00a497842a46912ddde8683146d986c2d0619a
status_record_commit_committed_message: "docs(status): record DEV-OPS-001 implementation commit and PR"
status_record_commit_completed: null
status_record_commit_completed_message: "docs(status): complete DEV-OPS-001 after PR merge"
pr: "#2"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/2"
pr_status: merged
pr_merged: true
pr_base: main
pr_head: feat/DEV-OPS-001-cursor-workflow-commands
merge_commit: 57800c3
completed_at: "2026-08-06 15:30 UTC"
next_git_step: "人工提交 docs(status): complete DEV-OPS-001 after PR merge；推送 main；随后删除本地和远程功能分支 feat/DEV-OPS-001-cursor-workflow-commands；不得开始 DEV-002 或 DEV-OPS-002；Agent 不得代为 Add/Commit/Push/Delete"
```

### 最终状态

`completed`
