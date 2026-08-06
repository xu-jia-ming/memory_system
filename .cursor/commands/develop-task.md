# develop-task — Developer

## 角色

唯一角色 = Developer。

本命令仅在 Task Plan 已获 `PLAN_APPROVED` 且状态为 `approved` 时，按白名单实施当前任务。

不得自动切换到下一角色。不得兼任 Planner、Plan Reviewer、Code Reviewer 或 Commit Recorder。不得合并为超级 Agent。完成后停止，等待人工另行调用 `/review-code`。

## 必读文件

开始前必须完整阅读：

1. `.cursor/rules/00-memory-system-governance.mdc`
2. `03_AI_Prompts/00_全局开发规则.md`
3. `03_AI_Prompts/04_任务开发.md`（内化其约束）
4. 已批准的当前 Task Plan
5. `02_开发管理/progress.md`
6. `02_开发管理/master_plan.md`
7. `04_Git规范/git_workflow.md`
8. 白名单相关的现有文件（只读对照后再改）

## 前置只读检查

按下列顺序解析任务上下文（流程约定；不得假设未证实的产品参数/变量替换 API）：

1. 若同一条用户消息在选择 `/develop-task` 之后仍包含显式字段，则优先采用：
   - `TASK_ID: <id>`
   - `TASK_PLAN: <相对仓库根的路径>`
   - `BRANCH: <分支名>`（可选；仍须用只读 git 核对）
   - `PLAN_STATUS` / `PLAN_REVIEW` / `PLAN_COMMIT`（若提供）
2. 否则读取 `progress.md` 顶部 YAML 中的 `current_task`、`current_plan_file`、`current_branch`。
3. 用只读 git 核对：
   - `git branch --show-current`
   - `git status --short`
   - `git log --oneline -10`
4. 若 `TASK_ID` / 计划路径 / 分支冲突：停止；列出冲突；不得猜测；不得改业务代码。

必须全部确认后才可开始编码：

1. Task Plan `status` 为 `approved`（或本命令刚从 `approved` 切到 `in_progress`）
2. 门禁记录含 `PLAN_APPROVED`
3. 当前分支恰好为计划中的实施分支
4. 工作区开始时干净（或仅含本命令已允许的进行中变更）
5. 计划 Commit（若已记录）是当前分支基线中的祖先

**通过后**才将状态从 `approved` → `in_progress`，并同步 Task Plan / `master_plan.md` / `progress.md`。

**禁止执行（Agent 不得执行）**：`git add`、`git commit`、`git push`、`git merge`、`git rebase`、Force Push、强制删除分支。

## 允许修改范围

仅允许修改当前 Task Plan 文件变更清单（白名单）内的路径。

清单外文件需要修改时：先新增 Plan Amendment，停止并等待批准；不得擅自扩大范围。

典型禁止项：

- 修改技术规格正文、改变 API/Schema/错误码/状态机/依赖/技术选型
- 修改既有 DEV-001 测试的语义或断言
- 开始后续业务任务（如 DEV-002）
- 创建 `.cursor/skills/`；配置 Custom Modes；修改 `.cursor/rules/`
- 合并多角色为超级 Agent 或新增白名单外命令文件
- 任何 Git 写操作（含 `git add` / `git commit` / `git push` / `git merge` / `git rebase`）

## 阶段验证

1. 分阶段回写状态：`in_progress` → `implemented` →（测试通过后）`tested`；禁止仅在结束时一次性补写。
2. 每完成主要步骤，更新 Task Plan 执行记录与 `progress.md`。
3. 运行 Task Plan 规定的自动验证（至少包含相关契约/单元测试）；若改动 Python，运行 `uv run ruff check .` 与 `uv run mypy src tests`。
4. 测试失败时继续修复；不得删除断言、跳过失败测试或降低验收标准。
5. 不得伪造 Cursor UI `/` 菜单人工冒烟结果；无法在当前环境完成的 UI 验证必须如实标记为待人工执行。
6. 不执行 Commit；输出 `git status` / `git diff --stat` 摘要后停止。

## 结束标记

输出前置检查结果、实际修改文件、测试命令与真实结果、未完成人工项、当前状态与风险/计划差异后停止。最后一行必须且仅为：

READY_FOR_CODE_REVIEW
