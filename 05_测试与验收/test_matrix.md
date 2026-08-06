# Test Matrix

## 1. 测试层级

| 层级 | 适用内容 |
|---|---|
| Unit | Token 估算、选择算法、Fingerprint、RRF、评分、巩固公式 |
| Contract | LLM Structured Output、Embedding Contract、Kafka Event Schema |
| Integration | Redis Lua、MongoDB Index、Kafka Offset、Neo4j Transaction、Elasticsearch Mapping |
| E2E | 跨模块完整业务链路 |

---

## 2. 所有任务的通用测试维度

| 维度 | 必测 |
|---|---|
| 正常路径 | 是 |
| 空值和边界 | 是 |
| 最大长度/容量 | 是 |
| 重复请求 | 是 |
| 并发 | 涉及共享状态时必须 |
| 用户隔离 | 所有业务资源必须 |
| 版本冲突 | 有版本字段时必须 |
| 外部依赖超时 | 调用外部依赖时必须 |
| 部分成功 | 跨存储/跨步骤时必须 |
| 进程异常恢复 | Worker、压缩、关闭流程必须 |
| 错误码与 HTTP 状态 | API 必须 |
| 敏感日志 | 所有外部输入和 Secret 路径必须 |

---

## 3. 关键失败注入

必须至少覆盖：

- Archive 已写入但 Kafka 发布失败；
- Compression LLM 超时；
- Extraction LLM 非法 JSON；
- Elasticsearch Bulk 部分失败；
- Worker 在 Neo4j Commit 后退出；
- Worker 在 Task completed 后、Offset commit 前退出；
- Session Close 部分 Archive 成功；
- Redis Finalize 前锁失效；
- Version Conflict；
- Embedding 服务不可用；
- Retrieval 单通道失败；
- Retrieval 总超时；
- Consolidation 批次写入失败。

---

## 4. 测试禁止行为

- 不得删除断言以通过；
- 不得把失败测试改为 skip；
- 不得无依据扩大容差；
- 不得仅 Mock 掉需要验证的数据库原子语义；
- 不得用实现内部细节替代业务结果断言；
- CI 不调用真实计费 LLM API；
- 发布验收必须至少运行真实 CPU TEI + BGE-M3 Contract/E2E。
