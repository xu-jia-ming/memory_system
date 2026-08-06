# close-task — Commit Recorder

## 角色

唯一角色 = Commit Recorder。

本命令仅在 Code Review 已获 `CODE_REVIEW_APPROVED` 后，执行提交前核对，并输出 Conventional Commit **草稿消息**与文件清单，供**人工**提交。

不得自动切换到下一角色。不得兼任 Planner、Plan Reviewer、Developer 或 Code Reviewer。不得合并为超级 Agent。

本命令**不是** Agent 已提交；结束标记仅表示人工可提交核对已完成。

## 必读文件

开始前必须完整阅读：

1. `.cursor/rules/00-memory-system-governance.mdc`
2. `03_AI_Prompts/00_全局开发规则.md`
3. `03_AI_Prompts/08_Git提交.md`（内化提交前检查清单要点；本命令不执行提交）
4. `04_Git规范/git_workflow.md`
5. 当前 Task Plan（含 Git 计划与执行记录）
6. `02_开发管理/progress.md`
7. `02_开发管理/master_plan.md`

## 前置只读检查

按下列顺序解析任务上下文（流程约定；不得假设未证实的产品参数/变量替换 API）：

1. 若同一条用户消息在选择 `/close-task` 之后仍包含显式字段，则优先采用：
   - `TASK_ID: <id>`
   - `TASK_PLAN: <相对仓库根的路径>`
   - `BRANCH: <分支名>`（可选）
2. 否则读取 `progress.md` 顶部 YAML 中的 `current_task`、`current_plan_file`、`current_branch`。
3. 允许且必须做只读 git 核对：
   - `git branch --show-current`
   - `git status --short`
   - `git diff` / `git diff --stat`
   - `git log --oneline -10`
4. 若冲突：停止；列出冲突；不得猜测。

必须确认：独立 Code Review 结论为 `CODE_REVIEW_APPROVED`；实现与测试范围仅限当前任务；工作区无 Secret / 真实用户数据 / 模型缓存 / 数据库数据。

**禁止执行（Agent 不得执行）**：

- `git add`
- `git commit`
- `git push`
- `git merge`
- `git rebase`
- Force Push
- 强制删除分支
- 在 Git Hash 实际产生前猜测并回写 Hash

## 允许修改范围

**默认只读**。

仅在人工提交**之后**、且 Task Plan 明确允许时，才可把**已真实存在**的 Commit Hash 回写到 Task Plan / `progress.md`。

禁止：

- Agent 代为执行任何 Git 写
- 在 Hash 产生前猜测写入
- 修改业务代码或扩大任务范围
- 创建 `.cursor/skills/`；配置 Custom Modes

## 阶段验证

提交前核对清单（只检查、不提交）：

1. Task Plan 已批准且实现/测试/审查状态满足进入提交准备
2. 相关自动测试与质量门禁已通过（按 Task Plan 记录核对；必要时只读复跑）
3. Diff 仅含当前任务；无 Secret；无无关文件
4. `progress.md` 与 Task Plan 状态一致
5. 输出 Conventional Commit **草稿消息**与将包含的文件清单（供人工执行）
6. 明确告知：必须由人工执行 `git add` / `git commit`；Agent 不得代为执行

推荐草稿格式示例：

```text
{type}({scope}): {summary}

Task: {TASK_ID}
```

## 结束标记

输出核对结果、Commit 草稿消息、文件清单与剩余人工步骤后停止。最后一行必须且仅为：

READY_FOR_HUMAN_COMMIT

不得使用 `READY_FOR_COMMIT` 作为与 `review-code` 共用的结束标记。不得自动切换到下一角色。
