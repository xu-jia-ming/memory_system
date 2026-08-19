# Memory System MVP：AI 开发文档包

## 1. 这个开发包的用途

本开发包用于让 AI Coding Agent 按照已经确定的技术规格，分阶段开发 Memory System MVP。

其中：

- `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` 是唯一业务与技术规格来源。
- `02_开发管理/master_plan.md` 管理全局阶段、任务拆分和依赖关系。
- `02_开发管理/progress.md` 记录项目当前状态。
- `02_开发管理/tasks/` 保存每个任务独立的实施计划和执行记录。
- `docs/ai-workflow/prompts/` 保存各阶段可以直接复制给 AI 的 Prompt。
- `04_Git规范/` 规定分支、Commit、Review 和 Tag 规则。
- `05_测试与验收/` 保存测试矩阵和 MVP 最终验收清单。

AI 不得把本开发包当作重新设计项目的邀请。技术规格已经确定，AI 的职责是按规格实现、测试和记录。

---

## 2. 第一次给 AI 的文件

第一次初始化项目时，把整个开发包交给 AI，并要求它首先阅读：

1. 本文件；
2. `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`；
3. `02_开发管理/master_plan.md`；
4. `02_开发管理/progress.md`；
5. `docs/ai-workflow/prompts/01_初始化与Backlog.md`；
6. `04_Git规范/git_workflow.md`；
7. `05_测试与验收/mvp_acceptance_checklist.md`。

第一次只允许 AI 生成 Backlog 和完善 Master Plan，不允许直接编写业务代码。

---

## 3. 每个任务实际需要给 AI 的最小文档集合

每次开发一个任务时，AI 至少需要读取：

1. 技术规格文档；
2. `master_plan.md`；
3. `progress.md`；
4. 当前任务的 `tasks/{TASK_ID}-{slug}.md`；
5. 当前任务对应的 Prompt；
6. 当前 Git 仓库状态和最近提交。

不需要每次把所有 Prompt 全部粘贴给 AI。只使用当前阶段对应的 Prompt，避免混淆职责。

---

## 4. 标准执行顺序

```text
初始化仓库
→ AI 生成/完善 Master Plan 与 Backlog
→ 选择一个小任务
→ AI 编写 Task Plan
→ 独立 AI 审查 Task Plan
→ 人工批准计划
→ AI 实现代码与测试
→ AI 更新 Task Plan 与 Progress
→ 独立 AI 做 Code Review
→ AI 修复 P0/P1
→ 运行测试和质量检查
→ Git Commit
→ 合并后进入下一个任务
```

---

## 5. AI 的权限边界

### AI 可以执行

- 阅读技术规格和仓库代码；
- 创建任务分支；
- 编写计划；
- 修改代码；
- 编写并运行测试；
- 更新 `progress.md` 和 Task Plan；
- 创建本地 Commit；
- 生成 Review 报告；
- 创建本地里程碑 Tag。

### 必须由人工明确授权

- Push 到远程仓库；
- Merge 到 `main`；
- 修改技术规格；
- 修改 API Contract；
- 修改数据库 Schema；
- 增加或替换核心依赖；
- 修改固定模型或基础设施版本；
- Rebase、Force Push；
- 删除持久化数据或 Docker Volume。

### 永远禁止

- 提交 `.env` 或任何 Secret；
- 提交真实用户数据；
- 修改已经执行的 Migration；
- 为通过测试删除断言、跳过测试或降低验收标准；
- 使用 `TODO`、`pass`、空实现冒充完成；
- 未运行测试就声称任务完成；
- 一次性实现整个项目。

---

## 6. 建议的 AI 会话分工

建议使用三个独立会话：

1. **规划会话**：只负责 Master Plan、Backlog 和 Task Plan。
2. **开发会话**：一次只负责一个 Task。
3. **审查会话**：只看规格、计划和 Git Diff，独立发现问题。

不要让同一会话在没有独立检查的情况下同时承担计划、开发、测试和最终审查。
