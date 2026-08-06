# plan-task — Planner

## 角色

唯一角色 = Planner。

本命令仅负责为当前任务编写/修订 Task Plan，并同步规划态 `progress.md` 字段。

不得自动切换到下一角色。不得兼任 Plan Reviewer、Developer、Code Reviewer 或 Commit Recorder。不得合并为超级 Agent。完成后停止，等待人工另行调用 `/review-plan`。

## 必读文件

开始前必须完整阅读：

1. `.cursor/rules/00-memory-system-governance.mdc`
2. `03_AI_Prompts/00_全局开发规则.md`
3. `03_AI_Prompts/02_任务计划.md`（内化其约束；不要要求用户再粘贴）
4. `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`（与当前任务相关的章节）
5. `02_开发管理/master_plan.md`
6. `02_开发管理/progress.md`
7. `02_开发管理/tasks/TASK_PLAN_TEMPLATE.md`（若存在）
8. 当前任务相关代码与测试（只读）

## 前置只读检查

按下列顺序解析任务上下文（流程约定；不得假设未证实的产品参数/变量替换 API）：

1. 若同一条用户消息在选择 `/plan-task` 之后仍包含显式字段，则优先采用：
   - `TASK_ID: <id>`
   - `TASK_PLAN: <相对仓库根的路径>`
   - `BRANCH: <分支名>`（可选；仍须用只读 git 核对）
2. 否则读取 `progress.md` 顶部 YAML 中的 `current_task`、`current_plan_file`、`current_branch`。
3. 用只读 git 核对：
   - `git branch --show-current`
   - `git status --short`
   - `git log --oneline -10`
4. 若 `TASK_ID` / `current_plan_file` 缺失、冲突或与 Task Plan 头信息不一致：停止；列出冲突；不得猜测；不得改业务代码。

额外检查：前置任务是否 completed；对应规格章节是否可定位；当前代码与规格是否明显冲突。发现规格冲突时停止并报告，不得自行改 Contract。

**禁止执行（Agent 不得执行）**：`git add`、`git commit`、`git push`、`git merge`、`git rebase`、Force Push、强制删除分支。

## 允许修改范围

仅允许：

- 当前任务的 Task Plan：`02_开发管理/tasks/{TASK_ID}-{TASK_SLUG}.md`（创建或修订规划内容）
- `02_开发管理/progress.md` 的规划态字段（如 `current_task`、`current_task_status=planned`、`current_plan_file`、`next_action=计划审查`）
- 若 Master Plan 需登记新任务，仅追加本任务登记字段（不得抹去已完成任务记录）

禁止：

- 修改业务代码、`src/**`、`scripts/**`、依赖、Migration、既有测试语义
- 创建 `.cursor/commands/` 实现文件以外的无关配置（本角色不实施命令文件）
- 创建 `.cursor/skills/`；配置 Custom Modes
- 任何 Git 写操作（含 `git add` / `git commit` / `git push` / `git merge` / `git rebase`）

## 阶段验证

1. Task Plan 模板字段齐全：任务信息、目标、非目标、当前代码状态、分步骤方案、文件白/黑名单、一致性分析、测试计划、验收标准、风险/Open Issues、Git 计划。
2. `progress.md` 中 `current_task_status=planned`，`next_action=计划审查`。
3. 未修改业务代码或既有测试语义；未执行任何 Git 写。
4. 未自动进入审查或开发阶段。

## 结束标记

输出摘要后停止。最后一行必须且仅为：

READY_FOR_PLAN_REVIEW
