# review-code — Code Reviewer

## 角色

唯一角色 = Code Reviewer。

本命令仅对当前任务实现做独立代码审查，并在会话中输出分级问题与结束标记。

不得自动切换到下一角色。不得兼任 Planner、Plan Reviewer、Developer 或 Commit Recorder。不得合并为超级 Agent。不得在本会话直接修改代码；修复属于独立 Developer 会话。

## 必读文件

开始前必须完整阅读：

1. `.cursor/rules/00-memory-system-governance.mdc`
2. `03_AI_Prompts/00_全局开发规则.md`
3. `03_AI_Prompts/06_代码审查.md`（内化其检查清单）
4. `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`（若本任务相关）
5. 当前 Task Plan（含执行记录与验收标准）
6. `02_开发管理/progress.md`
7. `02_开发管理/master_plan.md`
8. 只读 `git status` / `git diff` / `git log`
9. 本任务新增/修改的文件与测试（含契约测试与命令文件，若适用）

## 前置只读检查

按下列顺序解析审查对象（流程约定；不得假设未证实的产品参数/变量替换 API）：

1. 若同一条用户消息在选择 `/review-code` 之后仍包含显式字段，则优先采用：
   - `TASK_ID: <id>`
   - `TASK_PLAN: <相对仓库根的路径>`
   - `BRANCH: <分支名>`（可选）
2. 否则读取 `progress.md` 顶部 YAML 中的 `current_task`、`current_plan_file`、`current_branch`。
3. 用只读 git 核对：
   - `git branch --show-current`
   - `git status --short`
   - `git log --oneline -10`
4. 若冲突：停止；列出冲突；不得猜测。

确认：实现与测试已写入；状态至少为 `tested`（或计划允许的审查入口状态）；对照 Task Plan 白名单与黑名单。

**禁止执行（Agent 不得执行）**：`git add`、`git commit`、`git push`、`git merge`、`git rebase`、Force Push、强制删除分支。

## 允许修改范围

**只读零修改**。

不得直接改代码、测试、依赖、Migration、技术规格、Task Plan 状态机以外的实现文件。不得执行 Git 写。不得创建 `.cursor/skills/` 或配置 Custom Modes。

发现问题时应给出可复现的修复建议；由人工另行启动 Developer 会话修复。

## 阶段验证

按 P0–P3 分级输出问题；每个问题尽量包含：文件、行号、问题、违反的规格/计划条款、复现方式、修复建议。

重点核对：

1. 是否超出白名单或触碰黑名单
2. 角色隔离与结束标记是否符合计划（五命令不得混用结束标记）
3. 是否出现超级 Agent / 多角色合并
4. 是否依赖未证实的命令参数、变量替换或自动角色切换
5. 是否改动既有 DEV-001 测试语义/断言
6. 复跑相关契约测试 / 质量门禁（只读执行测试命令，不改代码）
7. Task Plan 执行记录与测试结果是否真实（不得接受伪造 UI 冒烟）

**禁止**使用 `READY_FOR_COMMIT` 或 `READY_FOR_HUMAN_COMMIT` 作为本命令结束标记。

## 结束标记

- 无 P0/P1 且允许进入人工提交准备时，最后一行必须且仅为：`CODE_REVIEW_APPROVED`
- 否则最后一行必须且仅为：`CODE_REVIEW_REJECTED`

不得自动切换到下一角色。
