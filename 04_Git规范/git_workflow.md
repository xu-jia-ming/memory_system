# Git Workflow

## 1. 分支

```text
main
└── feat/{TASK_ID}-{short-name}
└── fix/{BUG_ID}-{short-name}
└── docs/{TASK_ID}-{short-name}
```

示例：

```text
feat/STM-003-message-write
feat/EXT-004-neo4j-transaction
fix/RET-003-stale-index
```

MVP 不要求复杂 `develop` 分支。

---

## 2. 每个核心任务的 Commit

推荐：

### Commit A：计划

计划审查通过后：

```text
docs(plan): add STM-003 message write plan
```

只包含：

- 当前 Task Plan；
- progress.md；
- 必要的 Master Plan 状态变化。

### Commit B：实现

代码、测试和最终执行记录完成后：

```text
feat(short-term): implement idempotent message append
```

包含：

- 业务代码；
- 测试；
- 必要配置；
- Task Plan 执行结果；
- progress.md 状态。

如需在 Commit 后写入 Hash，可增加：

```text
docs(progress): record STM-003 completion
```

---

## 3. Commit 前门禁

全部满足才可 Commit：

- [ ] Task Plan 已批准；
- [ ] 实现完成；
- [ ] 相关测试通过；
- [ ] Ruff 通过；
- [ ] Mypy 通过；
- [ ] Review 无 P0/P1；
- [ ] Git Diff 无无关修改；
- [ ] 无 Secret；
- [ ] 无模型缓存、数据库数据和真实用户数据；
- [ ] Task Plan 和 progress.md 已更新。

---

## 4. 禁止事项

- 测试失败时提交；
- 为保存进度提交已知错误代码；
- 一个 Commit 混合多个无关 Task；
- 自动 Push（一般会话禁止；**唯一例外**：仅 Release Operator 按已批准 Task Plan 的 `RELEASE_PHASE` 执行受控 push——见治理窄例外 DEV-OPS-002/003；不扩大到 Orchestrator 或其他角色；`IMPLEMENTATION_RELEASE` 永久禁止 `git push origin main`）；
- 自动 Merge；
- Force Push；
- 修改已执行 Migration；
- Rebase 已共享分支；
- 提交 `.env`；
- 提交真实数据。

---

## 5. Conventional Commit 类型

| Type | 使用场景 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `test` | 纯测试改进 |
| `docs` | 文档和计划 |
| `refactor` | 不改变行为的重构 |
| `build` | 构建和依赖 |
| `ci` | CI |
| `chore` | 其他工程维护 |

---

## 6. Merge 规则

AI 不得自动 Merge。

人工 Merge 前检查：

- 分支与 Task 一一对应；
- Review 无 P0/P1；
- CI 全绿；
- 工作区干净；
- Task 状态为 committed；
- 合并后更新为 completed；
- 阶段结束后运行阶段 E2E。

---

## 7. Tag

只有阶段 E2E 通过后才能创建 annotated tag。

AI 可以创建本地 Tag，但不得 Push。

建议：

```text
v0.1.0-bootstrap
v0.2.0-short-term-memory
v0.3.0-memory-extraction
v0.4.0-memory-retrieval
v0.5.0-consolidation
v0.9.0-mvp-rc1
v1.0.0-mvp
```
