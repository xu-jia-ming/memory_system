# Git Commit Prompt

```text
任务 `{TASK_ID}` 已满足：

- 实现完成；
- 测试通过；
- Ruff 通过；
- Mypy 通过；
- Review 无 P0/P1；
- Task Plan 和 progress.md 已更新。

执行提交前检查：

1. git status；
2. git diff --stat；
3. git diff；
4. 确认只包含当前任务；
5. 检查 Secret、缓存、数据库数据、模型文件和临时文件；
6. 再运行当前任务的阻塞测试和质量检查；
7. 检查 Task Plan 最终状态和实际 Git 记录字段。

通过后：

1. 使用 Conventional Commit；
2. 业务代码、测试和最终 Task Plan 更新放在同一个原子实现 Commit；
3. 不 Push；
4. 不 Amend 已共享 Commit；
5. 不 Rebase；
6. 不 Force Push；
7. 创建 Commit 后，将 Commit Hash 写入 Task Plan 和 progress.md；
8. 如果写入 Commit Hash 需要第三个纯文档 Commit，使用：
   `docs(progress): record {TASK_ID} completion`
9. 最终输出：
   - Commit Hash；
   - Commit Message；
   - 包含文件；
   - 测试结果；
   - 当前工作区状态。

推荐格式：

{type}({scope}): {summary}

Task: {TASK_ID}

- implementation item
- consistency/idempotency rule
- test coverage
```
