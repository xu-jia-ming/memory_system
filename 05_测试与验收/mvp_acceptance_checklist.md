# MVP Acceptance Checklist

只有全部阻塞项通过，才可以创建 `v1.0.0-mvp`。

## A. 空白环境

- [ ] Linux Preflight 通过；
- [ ] Docker Engine 和 Compose v2 可用；
- [ ] CPU Embedding 模式可启动；
- [ ] Migration 首次执行成功；
- [ ] Migration 重复执行幂等；
- [ ] 修改已执行 Migration Checksum 后失败；
- [ ] 三个应用 Entrypoint 启动；
- [ ] Readiness 正确反映依赖状态。

## B. 业务链路

- [ ] Session 创建；
- [ ] Message 写入；
- [ ] 重复 Message 幂等；
- [ ] Archive 创建；
- [ ] Compression；
- [ ] Extraction；
- [ ] Neo4j 写入；
- [ ] Elasticsearch 同步；
- [ ] Retrieval；
- [ ] Consolidation；
- [ ] Session Close。

## C. 一致性与恢复

- [ ] Pending Archive 可恢复；
- [ ] 压缩失败不丢消息；
- [ ] 重复 Kafka Event 不重复写入；
- [ ] Worker 重启不重复 Memory/Evidence；
- [ ] Neo4j Commit 后异常可恢复 Elasticsearch；
- [ ] Session Close 部分成功可继续；
- [ ] Version Conflict 不覆盖新状态；
- [ ] 所有用户资源强制 `user_id` 隔离。

## D. 测试门禁

- [ ] Unit 全部通过；
- [ ] Contract 全部通过；
- [ ] Integration 全部通过；
- [ ] 完整 E2E 通过；
- [ ] 失败注入全部通过；
- [ ] `domain` 和 `application` 行覆盖率不低于 80%；
- [ ] Ruff 通过；
- [ ] Mypy 通过。

## E. 安全与可观测性

- [ ] API Key 比较使用 constant-time；
- [ ] Secret 不出现在日志；
- [ ] 完整用户消息不出现在日志；
- [ ] 完整 Prompt/Response 不出现在日志；
- [ ] 统一错误响应；
- [ ] Request ID 全链路一致；
- [ ] Metrics 暴露并受保护；
- [ ] Graceful Shutdown 验证。

## F. 工程一致性

- [ ] `.env.example` 完整且无 Secret；
- [ ] `versions.env` 和 `versions.lock.env` 与运行镜像一致；
- [ ] YAML 与 Pydantic Settings 一致；
- [ ] Compose 命令统一经过 Wrapper；
- [ ] README 启动命令有效；
- [ ] 无影响主流程的 TODO；
- [ ] 无占位实现；
- [ ] Git 工作区干净；
- [ ] Review 无 P0/P1。
