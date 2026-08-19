# 初始化与 Backlog Prompt

```text
请初始化 Memory System MVP 的开发管理流程。

首先完整读取：

1. 00_README_FIRST.md
2. 01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md
3. 02_开发管理/master_plan.md
4. 02_开发管理/progress.md
5. 04_Git规范/git_workflow.md
6. 05_测试与验收/mvp_acceptance_checklist.md

然后检查当前 Git 仓库：

- 当前分支；
- git status；
- git log --oneline -10；
- 当前目录结构；
- 已存在的代码、配置、测试和 Migration。

本次只允许做规划，不得编写业务代码。

请执行：

1. 对照技术规格检查 master_plan.md 是否覆盖全部 MVP 要求；
2. 将过大的任务拆成可以由一个独立 Feature Commit 完成的小任务；
3. 每个任务写明：
   - Task ID；
   - 对应规格章节；
   - 前置依赖；
   - 目标和非目标；
   - 预计变更文件；
   - 测试层级；
   - 验收条件；
   - 风险；
4. 不得删除技术规格要求；
5. 不得改变技术选型；
6. 更新 master_plan.md；
7. 更新 progress.md；
8. 推荐第一个唯一可执行任务；
9. 完成后停止，不得开始编码。

输出最后必须包含：

- 发现的规格阻塞项；
- Master Plan 修改摘要；
- 推荐第一个 Task；
- 下一步应使用的 Prompt 文件。
```
