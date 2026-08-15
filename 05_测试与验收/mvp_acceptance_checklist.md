# MVP Acceptance Checklist

只有全部阻塞项通过，才可以创建 `v1.0.0-mvp`。

## A. 空白环境

- [ ] Linux Preflight 通过；
- [x] Docker Engine 和 Compose v2 可用；
- [x] CPU Embedding 模式可启动；
- [x] Migration 首次执行成功；
- [x] Migration 重复执行幂等；
- [x] 修改已执行 Migration Checksum 后失败；
- [x] 三个应用 Entrypoint 启动；
- [x] Readiness 正确反映依赖状态。

## B. 业务链路

- [x] Session 创建；
- [x] Message 写入；
- [x] 重复 Message 幂等；
- [x] Archive 创建；
- [x] Compression；
- [x] Extraction；
- [x] Neo4j 写入；
- [x] Elasticsearch 同步；
- [x] Retrieval；
- [x] Consolidation；
- [x] Session Close。

## C. 一致性与恢复

- [x] Pending Archive 可恢复；
- [x] 压缩失败不丢消息；
- [x] 重复 Kafka Event 不重复写入；
- [x] Worker 重启不重复 Memory/Evidence；
- [x] Neo4j Commit 后异常可恢复 Elasticsearch；
- [x] Session Close 部分成功可继续；
- [x] Version Conflict 不覆盖新状态；
- [x] 所有用户资源强制 `user_id` 隔离。

## D. 测试门禁

- [x] Unit 全部通过；
- [x] Contract 全部通过；
- [x] Integration 全部通过；
- [x] 完整 E2E 通过；
- [x] 失败注入全部通过；
- [x] `domain` 和 `application` 行覆盖率不低于 80%；
- [x] Ruff 通过；
- [x] Mypy 通过。

## E. 安全与可观测性

- [x] API Key 比较使用 constant-time；
- [x] Secret 不出现在日志；
- [x] 完整用户消息不出现在日志；
- [x] 完整 Prompt/Response 不出现在日志；
- [x] 统一错误响应；
- [x] Request ID 全链路一致；
- [x] Metrics 暴露并受保护；
- [x] Graceful Shutdown 验证。

## F. 工程一致性

- [x] `.env.example` 完整且无 Secret；
- [x] `versions.env` 和 `versions.lock.env` 与运行镜像一致；
- [x] YAML 与 Pydantic Settings 一致；
- [x] Compose 命令统一经过 Wrapper；
- [x] README 启动命令有效；
- [x] 无影响主流程的 TODO；
- [x] 无占位实现；
- [ ] Git 工作区干净；
- [x] Review 无 P0/P1。
