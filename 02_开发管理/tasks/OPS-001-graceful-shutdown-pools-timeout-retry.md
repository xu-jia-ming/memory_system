# OPS-001 Graceful Shutdown, Connection Pools, Timeout & Retry MVP-wide Audit

## 1. 任务信息

```yaml
task_id: OPS-001
task_name: Graceful Shutdown, Connection Pools, Timeout & Retry MVP-wide Audit
status: committed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "8fb64f10255add1a57404f6894cc374780d33413"
branch: "feat/OPS-001-graceful-shutdown-pools-timeout-retry"
created_at: "2026-08-13 23:55 UTC"
updated_at: "2026-08-14 00:45 UTC"
spec_sections:
  - "§3.24 连接池、超时与重试"
  - "§3.25 优雅关闭"
  - "§3.27 日志（仅 shutdown handler 规则 6 交叉引用）"
  - "§3.28 测试策略（focused failure tests only；非 E2E-001 全量注入）"
prerequisites:
  formal:
    - "CON-001..005 — completed；v0.5.0-consolidation closed"
    - "STM-001..013 — completed"
    - "EXT-001..009 — completed"
    - "RET-001..006 — completed"
    - "DEV-002 — settings/shutdown validators"
    - "DEV-003 — compose stop_grace_period contract"
    - "DEV-005 — memory-api lifespan + uvicorn graceful shutdown"
    - "DEV-007 — SiliconFlow embedding retry contract"
    - "CON-004 — consolidation worker + scheduler shutdown wiring"
    - "EXT-009 — extraction worker production loop + terminal-before-offset"
  baseline_evidence:
    branch: "main"
    head: "8fb64f10255add1a57404f6894cc374780d33413"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=8fb64f1"
approval_gates:
  planning: "PLAN_APPROVED"
  human_plan_approved: true
  plan_review_round: 2
  plan_review_blocker: 0
  plan_review_must_fix: 0
  plan_review_should_fix: 3
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator lands this plan on main and creates exact feat/OPS-001-graceful-shutdown-pools-timeout-retry"
  IMPLEMENTATION_RELEASE: "feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "after verified MERGED PR; exact feat branch cleanup"
dependency_changes_expected: NONE
migration_changes_expected: NONE
production_file_whitelist_default: "3 files if HARD_BLOCK remediation confirmed (see §20)"
test_file_whitelist_default: "see §14"
```

### 1.1 本轮门禁

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现或测试实现"
  - "进入 Developer / Code Reviewer / Release Operator"
  - "执行 Git 写"
  - "修改权威规格正文"
  - "触碰 DEV-006 / PR #13"
stop_if:
  - "审计发现需要改变 API Contract / Schema / 错误码 / 状态机"
  - "审计发现需要通用 Retry Decorator 或架构重写"
blocking_open_issues: []
```

## 2. 任务目标

完成 MVP 全进程 **只读审计** 与 **最小必要修复**：对照 §3.24 / §3.25，验证三 Entrypoint 生命周期、基础设施 Client 连接池/超时/重试、Kafka extraction offset 顺序、Settings/Compose 一致性；对 **真实违规** 做聚焦修复与失败注入单测；若绝大部分已合规，允许 **零或极小** 生产 diff。

**可验证交付**：

1. 完整审计矩阵（本计划 §4–§11）与 Findings 表（§12）。
2. 每项发现分类：`COMPLIANT` / `HARD_BLOCK` / `SAFE_AUTO_REMEDIATION` / `DEFERRED_FOR_MVP`。
3. 仅对 `HARD_BLOCK` / 必要 `SAFE_AUTO_REMEDIATION` 实施白名单内修复。
4. 新增 focused failure tests（非 E2E-001 全量注入）。

## 3. 非目标

- OPS-002 日志/PII/用户隔离审计
- OPS-003 compose/migration 空白环境认证
- OPS-004 CI / 80% 覆盖率
- E2E-001 全链路失败注入
- REL-001 验收清单
- 通用 Client Retry Framework 或架构重写
- 修改 Compression / Extraction / Retrieval / Consolidation **业务语义**
- 修改 Kafka topic/schema、Migration、依赖版本
- Compose `stop_grace_period` 变更（已由 DEV-003 contract 锁定）
- DEV-007 SiliconFlow 3-attempt embedding contract 回退（见 §12 F-015）

## 4. 当前代码状态（规划时只读事实）

| 维度 | 事实 |
|---|---|
| Entrypoints | 三进程：`api.py`、`extraction_worker.py`、`consolidation_worker.py`；`scripts.migrate` 为一次性 Job，非 daemon |
| Settings | `configs/base.yaml` §3.24/§3.25 默认值与 `models.py` 一致；`validators.validate_shutdown` 校验 grace 关系 |
| Compose | `compose.yaml` stop_grace_period 480/300/300；contract `test_app_services_stop_grace_periods` 已覆盖 |
| memory-api | Uvicorn `timeout_graceful_shutdown=settings.shutdown.memory_api_timeout_seconds`；FastAPI lifespan → `create_app_state` / `shutdown_app_state` |
| extraction-worker | SIGTERM/SIGINT → `stop_event`；`run_archive_created_consumer_loop(should_stop=...)`；`finally` 中 `close_all` 用 **完整** 270s（未扣 in-flight） |
| consolidation-worker | SIGTERM/SIGINT → `stop_event`；`scheduler.shutdown(wait=True)` 无界；Neo4j `close` 用 **完整** 270s |
| Kafka consumer | `enable_auto_commit=False`、`max_poll_records=1`；terminal Mongo 后 commit；malformed/key mismatch fail-closed |
| Pools/timeouts | `runtime.py` + worker entrypoints 均从 Settings 注入 §3.24 默认值 |
| 既有 shutdown 测试 | `test_settings_validation` shutdown 校验；`test_consolidation_worker_entrypoint` scheduler shutdown mock；**无** dedicated OPS-001 SIGTERM/deadline 测试 |
| Git baseline | `main @ 8fb64f1` clean |

## 5. Runtime 进程清单（§3.25）

| 进程 | 启动 | 资源创建 | 运行时 | 关闭 |
|---|---|---|---|---|
| **memory-api** | `entrypoints.api.main()` → `get_settings()` → `create_app()` → `uvicorn.run(...)` | Lifespan `create_app_state`: Redis, MongoDB, Neo4j, ES, httpx, Kafka Producer；启动 ping/info/start | 处理 HTTP；Uvicorn 管理连接 intake | Uvicorn 收 SIGTERM/SIGINT → 停新请求 → lifespan `finally` → `shutdown_app_state`（producer.stop → ES → Neo4j → Mongo → Redis → httpx） |
| **memory-extraction-worker** | `main()` → `get_settings()` → `configure_logging` → `asyncio.run(_run_worker)` | MongoDB, Neo4j, ES, httpx, `AIOKafkaConsumer`；ping 后 `consumer.start()` | `run_archive_created_consumer_loop` serial poll（max 1）；`should_stop` 在 loop 顶检查 | SIGTERM/SIGINT → 记录 `shutdown_started_monotonic` + `stop_event`；in-flight record 与 resource close **共享** 270s 总预算 |
| **memory-consolidation-worker** | 同上模式 | Neo4j driver only；可选 `AsyncIOScheduler` | `stop_event.wait()` idle；cron 触发 tracked `execute_run` Task | SIGTERM/SIGINT → `shutdown_started_monotonic`；scheduler drain + Neo4j close **共享** 270s 总预算 |
| **init-infra / migrate**（非本任务 daemon） | `python -m scripts.migrate` one-shot | 临时 clients | 执行 migration | 进程退出 | 不适用 §3.25 长期 graceful |

**审计结论（进程级）**：intake 停止与资源 close 顺序基本符合 §3.25；**缺口**见 §7、§15（worker 内部 deadline 未作为 **单一总预算** 覆盖 in-flight + close；§3.25 #8 未强制 cancel）。

### 5.1 共享 Shutdown 总预算（§3.25 语义 — Amendment 001 澄清）

§3.25 规定 worker 应用内部 deadline（extraction/consolidation 均为 **270s**）为 **shutdown 全过程总预算**，包含：

1. in-flight 任务 drain（或 deadline 到达后 cancel）
2. scheduler / consumer 停止
3. 全部 client close

**禁止**将 270s 理解为「in-flight 270s + close 再 270s」两段独立预算。

```text
signal received
  → shutdown_started_monotonic = time.monotonic()
  → stop intake (stop_event / no new poll / no new scheduler job)

remaining() = max(0, shutdown_timeout_seconds - (time.monotonic() - shutdown_started_monotonic))

Phase A: in-flight drain/cancel     ─┐
Phase B: scheduler/consumer stop    ─┼─ 全部使用同一 remaining()；每阶段完成后重新计算
Phase C: client close               ─┘

finally close  MUST NOT 重新获得完整 270s
```

memory-api 的 450s 由 Uvicorn 作为 **单一总预算** 管理（已合规）；本 Amendment 仅约束两 worker。

## 6. 基础设施 Client 清单（§3.24）

| Client | 创建点 | Pool / 连接 | Timeout | Retry | Close |
|---|---|---|---|---|---|
| **Redis** | `runtime.create_app_state` | `max_connections=50` | connect 3s / socket 5s | 无应用层 retry | `redis.aclose()` |
| **MongoDB** | `runtime` / `extraction_worker` | `max_pool_size=50` | selection 5000ms / connect 5000ms | 无应用层 retry | `mongodb.close()` |
| **Neo4j** | `runtime` / workers | `max_connection_pool_size=50` | connect 5s / acquisition 10s；repo 层 `neo4j_timeout_seconds` wait_for | 无自动 retry loop | `driver.close()` |
| **Elasticsearch** | `runtime` / `extraction_worker` | transport pool（ES client 内部） | `request_timeout=10`；per-op `request_timeout` 可覆盖（retrieval 5s） | client `max_retries=2`, `retry_on_timeout=true` | `elasticsearch.close()` |
| **Kafka Producer** | `runtime` only | aiokafka 内部 | `request_timeout_ms` from settings | transport 与业务分离 | `producer.stop()`（flush） |
| **Kafka Consumer** | `extraction_worker` | single consumer | session/heartbeat/max_poll_interval from `kafka_consumer` | 无业务 skip 幂等 | `consumer.stop()` |
| **LLM HTTP** | OpenAI SDK in `DeepSeekLlmClient` | SDK 内部 | per-call `timeout=timeout_seconds` | **无 transport retry**（§3.24 #4） | SDK lifecycle随进程 |
| **Embedding HTTP** | shared `httpx.AsyncClient` | `max_connections=100`, keepalive 20 | shared client §3.24；SiliconFlow POST 用 `embedding_timeout_seconds` per-request | `SiliconFlowEmbeddingClient` max 3 attempts（见 §9） | `http_client.aclose()` |
| **TEI tokenize**（非 MVP 主路径） | `tei_tokenize_client` | 注入 httpx | `embedding_http_client` | 无 | 随 httpx |

## 7. Shutdown 审计（§3.25）

| 规则 | memory-api | extraction-worker | consolidation-worker | 状态 |
|---|---|---|---|---|
| 监听 SIGTERM/SIGINT | Uvicorn 内置 | `loop.add_signal_handler` | 同左 | COMPLIANT |
| 停止 intake | Uvicorn graceful | loop 顶 `should_stop` 不再 poll | `stop_event` + scheduler 不再 submit 新 job（shutdown 后） | COMPLIANT |
| 等待 in-flight | Uvicorn drain requests | 当前 record 处理完再退出 loop（**无 deadline cancel**） | `scheduler.shutdown(wait=True)` 等待当前 job（**无 deadline cancel**） | **PARTIAL** |
| 内部 deadline | 450s via uvicorn（**总预算**） | 270s 应对 in-flight+close **总和**；当前 close 单独 bound、in-flight 无界 | 同左 | **HARD_BLOCK**（§3.25 #8 + 总预算语义） |
| Handler 不做重 DB 逻辑 | Uvicorn/FastAPI | handler 仅 `stop_event.set()` | 同左 | COMPLIANT |
| Compose grace > internal deadline | 480>450 contract+validator | 300>270 | 300>270 | COMPLIANT |
| api deadline > compression lock TTL | 450>420 validator | N/A | N/A | COMPLIANT |
| Shutdown 后不开新压缩轮次 | Uvicorn 拒新 HTTP → 无新 write/compression 请求 | N/A | N/A | COMPLIANT（Uvicorn 语义） |
| Close 顺序 | producer → ES → Neo4j → Mongo → Redis → httpx | consumer → ES → Neo4j → Mongo → httpx | scheduler → Neo4j | COMPLIANT（合理逆序） |

**§3.25 #8 缺口详述**：

1. Extraction / Consolidation worker 在 in-flight 超过剩余 budget 时 **未** `asyncio.wait_for` + cancel。
2. 当前 `finally` close 使用 **完整** `shutdown.*_timeout_seconds`，未扣除 in-flight 已消耗时间 → 总 wall-clock 可达 **2×270s**，违反 §3.25 总预算语义，且可能超过 Compose `stop_grace_period` 被 SIGKILL。

## 8. Kafka 正确性（extraction worker）

| 检查项 | 当前行为 | 要求 | 状态 |
|---|---|---|---|
| auto_commit | `enable_auto_commit=False` enforced in factory | 手动 commit | COMPLIANT |
| max_poll_records | `1` enforced | 串行 | COMPLIANT |
| offset before terminal | `process_archive_created_event` 返回 `should_commit_offset`；`TerminalPersistError` 不 commit | terminal Mongo 先于 offset | COMPLIANT |
| failed terminal commits | `mark_failed` 后 commit | 可恢复 failed 不重投 | COMPLIANT |
| malformed / key mismatch | raise；loop 传播；不 commit | fail-closed | COMPLIANT |
| duplicate unsafe mutation | pipeline 幂等 + task status reload | 依赖前文幂等 | COMPLIANT（既有 EXT-001/009 测试） |
| producer flush on shutdown | worker 无 producer | N/A | COMPLIANT |
| stop 后不再 poll | `should_stop` at loop head | §3.25 #3 | COMPLIANT |
| in-flight 中途 stop | 完成当前 record 后退出 | 允许完成或 failed 持久化 | COMPLIANT |
| shutdown deadline 取消 in-flight | **未实现** | §3.25 #8 | HARD_BLOCK |

## 9. Pool 审计 vs §3.24

| 组件 | §3.24 默认 | configs/base.yaml | models 默认 | runtime/worker 接线 | 状态 |
|---|---|---|---|---|---|
| http_client.max_connections | 100 | 100 | 100 | `httpx.Limits` | COMPLIANT |
| http_client.max_keepalive | 20 | 20 | 20 | 同左 | COMPLIANT |
| http_client connect/read/write/pool timeout | 5/120/30/5 | 同左 | 同左 | `httpx.Timeout` | COMPLIANT |
| embedding_http_client connect/read | 5/30 | 5/30 | 5/30 | TEI/health check | COMPLIANT |
| redis max_connections | 50 | 50 | 50 | `from_url(...)` | COMPLIANT |
| redis socket timeouts | 3/5 | 3/5 | 3/5 | 同左 | COMPLIANT |
| mongodb max_pool_size | 50 | 50 | 50 | `maxPoolSize` | COMPLIANT |
| mongodb timeouts ms | 5000/5000 | 同左 | 同左 | 同左 | COMPLIANT |
| neo4j pool/timeouts | 50 / 5 / 10 | 同左 | 同左 | `AsyncGraphDatabase.driver` | COMPLIANT |
| elasticsearch request_timeout | 10 | 10 | 10 | client + per-op override | COMPLIANT |
| elasticsearch max_retries | 2 | 2 | 2 | client ctor | COMPLIANT |

**F-012 审计范围（Amendment 001）**：

| 子范围 | 覆盖文件 | 测试断言 |
|---|---|---|
| memory-api runtime | `runtime.create_app_state` | U10a — Redis/Mongo/Neo4j/ES/httpx/kafka kwargs |
| extraction-worker clients | `extraction_worker._run_worker` ctor | U10b — Mongo/Neo4j/ES/httpx kwargs（worker 无 Redis/Kafka producer） |
| consolidation-worker clients | `consolidation_worker._run_worker` Neo4j driver only | U10c — Neo4j pool/timeout kwargs |

## 10. Timeout 矩阵

| 组件 | connect | request/read | transaction/overall | 配置源 | 状态 |
|---|---|---|---|---|---|
| httpx (API/worker shared) | 5s | read 120s / write 30s / pool 5s | per-request override allowed | `http_client` | COMPLIANT |
| Embedding SiliconFlow POST | inherits pool | `embedding_timeout_seconds` (10) per POST | batch sequential | `memory_retrieval` | COMPLIANT |
| Embedding health (readiness) | pool | `embedding_http_client.read` (30) | non-blocking | `runtime.check_embedding` | COMPLIANT |
| Redis command | 3s connect | 5s socket | per-op | `redis` | COMPLIANT |
| MongoDB | 5s connect | 5s server selection | per-op | `mongodb` | COMPLIANT |
| Neo4j driver | 5s | 10s acquisition | repo `neo4j_timeout_seconds` (5) wait_for | `neo4j` + `memory_retrieval` | COMPLIANT |
| Elasticsearch transport | ES internal | 10s default; retrieval ops 5s | per-request | `elasticsearch` + `memory_retrieval` | COMPLIANT |
| Kafka producer | — | `request_timeout_ms` | producer lifecycle | `kafka_producer` | COMPLIANT |
| Kafka consumer | — | session 30s / max_poll_interval 900s | poll 1000ms | `kafka_consumer` | COMPLIANT |
| LLM DeepSeek | SDK | per-call `timeout_seconds` | compression/extraction settings | domain service | COMPLIANT |
| Retrieval total budget | — | `retrieval_total_timeout_seconds=15` | **未在 orchestration 层 wait_for 强制** | validator 仅 stage≤total | DEFERRED_FOR_MVP |
| Shutdown internal | — | api 450 / workers 270 | compose grace 480/300 | `shutdown` + validators | COMPLIANT（值）；workers 执行缺口见 §7 |

## 11. Retry 矩阵

| 调用域 | Owner | Count | Retryable | Non-retryable | Backoff | 幂等前提 | 状态 |
|---|---|---|---|---|---|---|---|
| ES Search/MGET/Index (transport) | ES AsyncClient | max_retries=2 | timeout, transport | 4xx mapping errors | ES client 内置短重试 | deterministic doc id / read | COMPLIANT |
| ES app-level loops | repositories | 0 extra loops | 仅分类 `retryable` flag | 4xx | — | 无自动重试 | COMPLIANT |
| Redis Lua | STM services | 0 transport retry | — | all | — | 幂等脚本 | COMPLIANT |
| Mongo state transition | domain repos | 0 auto retry | — | all | — | 条件更新 | COMPLIANT |
| Neo4j transaction | repos | 0 auto retry | — | all | — | consolidation optimistic lock | COMPLIANT |
| LLM transport | `DeepSeekLlmClient` | 0 | — | timeout/5xx/429 | — | N/A | COMPLIANT |
| LLM schema retry | compression/extraction/reconciliation services | 1 correction attempt | validation failures | timeout/provider | same prompt policy | business-level | COMPLIANT |
| Embedding HTTP | `SiliconFlowEmbeddingClient` | 3 attempts (1+2) | connect/timeout/429/5xx | 400/auth/schema/dim | exponential+jitter | deterministic input | **DEFERRED**（§3.24 #5 字面 1 次连接重试 vs DEV-007 已批准 3 attempts） |
| Kafka transport | aiokafka | internal | separated from business | — | — | extraction idempotency | COMPLIANT |
| Extraction business retry | admin API manual | human-driven | per §2.1.14 | — | — | Mongo status gates | COMPLIANT |
| Generic retry decorator | — | **禁止** | — | — | — | — | COMPLIANT（不存在） |

## 12. Timeout × Retry 组合（有界最坏情况）

| 路径 | 组合 | 最坏 wall-clock（粗算） | 是否违反 §3.24/§3.25 | 分类 |
|---|---|---|---|---|
| ES read (retrieval) | 5s op × (1+2) transport retries | ~15s | 规格允许 ES 最多 2 次短重试 | COMPLIANT |
| ES read (client default) | 10s × 3 attempts | ~30s | 用于非 retrieval 路径（worker ping/info） | COMPLIANT |
| Embedding embed | 10s × 3 attempts + backoff ≤8s | ~38s | 可能超过 `retrieval_total_timeout_seconds=15` | DEFERRED_FOR_MVP（无 orchestration 总超时；DEV-007 contract） |
| LLM compression | single transport call; schema retry is separate business call | bounded by `compression_llm_timeout_seconds` × rounds | shutdown 由 uvicorn 450s 覆盖 | COMPLIANT |
| Worker shutdown in-flight+close | **无界** in-flight + close 各用满 270s | ≤270s **总预算** < 300s grace | §3.25 #8 + 总预算 | **HARD_BLOCK** |
| memory-api shutdown | uvicorn 450s total | ≤450s < 480s grace | — | COMPLIANT |

## 13. Settings 审计

| 项 | base.yaml | models | validators | .env.example | compose contract | 状态 |
|---|---|---|---|---|---|---|
| http_client 全套 | ✓ | ✓ | — | 无独立 env（YAML 默认） | — | COMPLIANT |
| embedding_http_client | ✓ | ✓ | — | — | — | COMPLIANT |
| redis/mongodb/neo4j/elasticsearch | ✓ | ✓ | — | URI/URL env | — | COMPLIANT |
| shutdown 450/270/270 | ✓ | ✓ | grace+lock 交叉 | 无必需 env（可 override） | 480/300/300 | COMPLIANT |
| SILICONFLOW / API keys | — | ✓ | conditional | ✓ | required_env_keys | COMPLIANT |
| development.yaml | 注释占位 | — | — | — | — | COMPLIANT |
| test.yaml | compression_llm_timeout override only | — | — | — | — | COMPLIANT |

**备注**：`embedding_http_client` 未被 `SiliconFlowEmbeddingClient` 用于 POST（使用 `embedding_timeout_seconds`）；与 DEV-007 决策一致，非 shutdown/pool 缺陷 → `COMPLIANT` with note。

## 14. Entrypoint 生命周期验证

| 检查 | api | extraction | consolidation | 状态 |
|---|---|---|---|---|
| settings 失败 exit 1 | ✓ stderr | ✓ stderr | ✓ stderr | COMPLIANT |
| 启动依赖 ping | lifespan create | pre-loop ping | neo4j ping | COMPLIANT |
| 正常 shutdown exit 0 | uvicorn | asyncio.run returns 0 | 同左 | COMPLIANT |
| KeyboardInterrupt | — | return 0 | return 0 | COMPLIANT |
| startup 异常 exit 1 | settings only at main | pre-loop failure | pre-loop failure | COMPLIANT |
| logging configure | via create_app | explicit | explicit | COMPLIANT |
| SIGTERM handler | uvicorn | stop_event | stop_event | COMPLIANT |

## 15. Findings 表

| ID | Component | Current behavior | Requirement | Status | Remediation | Tests | Owning files |
|---|---|---|---|---|---|---|---|
| F-001 | memory-api SIGTERM | Uvicorn handles | §3.25 listen | COMPLIANT | none | U1 | `entrypoints/api.py` |
| F-002 | memory-api graceful timeout | `timeout_graceful_shutdown=450` | §3.25 + uvicorn flag | COMPLIANT | none | U1 | `entrypoints/api.py` |
| F-003 | memory-api lifespan close | `shutdown_app_state` reverse order | §3.25 flush/close | COMPLIANT | none | U2 | `api/app.py`, `infrastructure/runtime.py` |
| F-004 | memory-api compression on shutdown | no new HTTP intake | §3.25 #2 | COMPLIANT | none | U1 | uvicorn behavior |
| F-005 | extraction SIGTERM | `stop_event` handlers | §3.25 | COMPLIANT | none | U3 | `entrypoints/extraction_worker.py` |
| F-006 | extraction stop poll | `should_stop` at loop head | §3.25 #3 | COMPLIANT | none | U4 | `archive_created_consumer.py` |
| F-007 | extraction offset ordering | terminal Mongo before commit | §3.25 + EXT-001 | COMPLIANT | none | 既有 INT | `extraction_task_consumer_service.py` |
| F-008 | extraction shutdown deadline | close 用满 270s；in-flight 无界；**总预算可超 540s** | §3.25 #8 总预算 270s | **HARD_BLOCK** | signal 时记录 `shutdown_started_monotonic`；consumer loop 对 in-flight `process_consumer_record` 用 `wait_for(remaining())`；timeout → cancel、**no commit**；`finally` close 用 **同一** `remaining()`（非完整 270s） | U5, U6, U12 | `entrypoints/extraction_worker.py`, `kafka/archive_created_consumer.py` |
| F-009 | consolidation SIGTERM | `stop_event` handlers | §3.25 | COMPLIANT | none | U7 | `entrypoints/consolidation_worker.py` |
| F-010 | consolidation scheduler stop | `shutdown(wait=True)` | §3.25 #4 | COMPLIANT | none | 既有 unit | `consolidation_worker.py` |
| F-011 | consolidation shutdown deadline | scheduler wait 无界；close 再用满 270s | §3.25 #8 总预算 270s | **HARD_BLOCK** | signal 记录 `shutdown_started_monotonic`；track `current_run_task`；Phase A `wait_for(task, remaining())` → cancel + mutex release；Phase B `wait_for(scheduler.shutdown, remaining())`；Phase C neo4j close `remaining()` | U8, U9, U13 | `entrypoints/consolidation_worker.py` |
| F-012 | connection pools §3.24 | settings wired | §3.24 yaml | COMPLIANT | none | U10a/b/c | `runtime.py`, `extraction_worker.py`, `consolidation_worker.py` |
| F-013 | LLM no transport retry | single SDK call | §3.24 #4 | COMPLIANT | none | 既有 | `deepseek_client.py` |
| F-014 | ES client retries | max_retries=2 | §3.24 #2 | COMPLIANT | none | U10a, U11 | `runtime.py` |
| F-015 | Embedding retry count/scope | 3 HTTP attempts incl. 429/5xx | §3.24 #5 literal "连接失败重试1次" | **DEFERRED_FOR_MVP** | **no change** — DEV-007/OI-012 approved contract (C12–C15) | 既有 contract | `siliconflow_client.py`, `retry.py` |
| F-016 | retrieval total timeout | validator only; no runtime wait_for | implicit budget | DEFERRED_FOR_MVP | document; E2E-001/OPS-004 | optional U11 | hybrid/authoritative services |
| F-017 | shutdown settings validators | grace/lock checks | §3.25 | COMPLIANT | none | 既有 | `validators.py` |
| F-018 | compose stop_grace_period | 480/300/300 | §3.25 | COMPLIANT | none | contract | `compose.yaml` |
| F-019 | generic retry decorator | absent | §3.24 #1 | COMPLIANT | none | — | — |
| F-020 | Kafka business vs transport | manual commit + idempotency | §3.24 #6 | COMPLIANT | none | INT | consumer + task service |
| F-021 | memory-api shutdown_app_state timeout | unbounded close inside uvicorn window | §3.25 | COMPLIANT | optional `wait_for` — **not required** if uvicorn bounds total | DEFERRED | `runtime.py` |

## 16. 实现方案（仅 HARD_BLOCK 修复）

### 共享 helper（两 worker 各自 module-local 或 `infrastructure/shutdown_budget.py` — 若新增 helper 文件须入白名单；**默认不放新文件**，entrypoint 内联 ≤10 行）

```python
def remaining_shutdown_seconds(
    shutdown_started_monotonic: float | None,
    shutdown_timeout_seconds: int,
) -> float:
    if shutdown_started_monotonic is None:
        return float(shutdown_timeout_seconds)
    elapsed = time.monotonic() - shutdown_started_monotonic
    return max(0.0, float(shutdown_timeout_seconds) - elapsed)
```

### Step 1 — Extraction worker + consumer（共享 270s 总预算）

**设计决策（Amendment 001 MUST_FIX #2）**：in-flight record 的 cancellable `wait_for` **必须**在 `run_archive_created_consumer_loop` 内实现（entrypoint 无法在不改 loop 的情况下截获已 poll 的 record 且保持 offset 语义）。因此 **`archive_created_consumer.py` 入 production 白名单**。

**文件**：

- `src/memory_system/entrypoints/extraction_worker.py`
- `src/memory_system/infrastructure/kafka/archive_created_consumer.py`

**entrypoint 行为**：

1. 创建 `shutdown_started_monotonic: float | None = None`（mutable cell / list ref）。
2. Signal handler：`shutdown_started_monotonic = time.monotonic()` **然后** `stop_event.set()`（§3.25 #6：handler 仅设状态）。
3. 调用 `run_archive_created_consumer_loop(..., get_shutdown_started=lambda: shutdown_started_monotonic, shutdown_timeout_seconds=settings.shutdown.extraction_worker_timeout_seconds)`。
4. `finally` → `_close_worker_resources(..., timeout_seconds=remaining_shutdown_seconds(shutdown_started_monotonic, settings.shutdown.extraction_worker_timeout_seconds))` — **不得**传入完整 270。

**consumer loop 行为**（`archive_created_consumer.py`）：

1. 新增可选参数 `get_shutdown_started: Callable[[], float | None]`、`shutdown_timeout_seconds: int`（默认 `None`/0 表示 legacy 测试路径无 budget）。
2. Loop 顶 `should_stop()` 且无 in-flight record → 立即 return（不变）。
3. **已 poll 的 record**（in-flight）：`remaining = remaining_shutdown_seconds(get_shutdown_started(), shutdown_timeout_seconds)`；若 shutdown 已开始且 `remaining <= 0` → log、return（no commit）。
4. 否则 `should_commit = await asyncio.wait_for(process_consumer_record(...), timeout=remaining)`（仅当 shutdown 已开始；idle 路径无 wait_for）。
5. `asyncio.TimeoutError` → log error、**不 commit**、return processed（offset 语义 preserved）。
6. Malformed/key mismatch fail-closed raise 语义 **不变**。

**幂等**：cancel / timeout 后无 offset commit → Kafka replay → extraction idempotency（EXT-009）。

### Step 2 — Consolidation worker（共享 270s 总预算 + run task 跟踪）

**文件**：`src/memory_system/entrypoints/consolidation_worker.py`（**仅 entrypoint**；不改 `ConsolidationRunService` 语义）

**run task 跟踪（Amendment 001 SHOULD_FIX F-011）**：

```text
current_run_task: asyncio.Task[None] | None = None

async def run_callback(evaluation_time: int) -> None:
    nonlocal current_run_task
    async def _run() -> None:
        try:
            await run_service.execute_run(evaluation_time)
        finally:
            nonlocal current_run_task
            current_run_task = None
    current_run_task = asyncio.create_task(_run())
    await current_run_task
```

**shutdown 流程**（`stop_event` 触发后，`finally` 块）：

1. `remaining = remaining_shutdown_seconds(shutdown_started_monotonic, settings.shutdown.consolidation_worker_timeout_seconds)`。
2. **Phase A — in-flight run**：若 `current_run_task` 且 not done → `await asyncio.wait_for(asyncio.shield(current_run_task), timeout=remaining)`；`TimeoutError` → `current_run_task.cancel()` → `await current_run_task`（suppress `CancelledError`）→ **defensive** `if mutex.is_held(): await mutex.release()`（`execute_run` 的 `finally` 通常已 release；此为 deadline 兜底）。
3. 重新计算 `remaining`。
4. **Phase B — scheduler stop**：若 scheduler → `await asyncio.wait_for(asyncio.to_thread(scheduler.shutdown, wait=True), timeout=remaining)`；timeout → log error，继续。
5. 重新计算 `remaining`。
6. **Phase C — Neo4j close**：`await _close_neo4j(driver, timeout_seconds=int(remaining))`（**不得**用完整 270）。
7. `enabled=false` 路径：无 scheduler；Phase A/B 跳过；Phase C 用 full budget（因无 in-flight）。

**mutex 释放保证**：优先依赖 `execute_run` 现有 `finally: await self._mutex.release()`；cancel 后 await task 完成；若 `mutex.is_held()` 仍为 True → 显式 `await mutex.release()` 并 log warning。

### Step 3 — Focused failure tests（见 §18）

- 不修改 F-015 / F-016 行为。
- 零 settings/compose/migration 变更预期。

## 17. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/entrypoints/extraction_worker.py` | 修改 | signal 时记录 `shutdown_started_monotonic`；共享 budget；finally close 用 remaining |
| `src/memory_system/infrastructure/kafka/archive_created_consumer.py` | 修改 | in-flight `process_consumer_record` 用 `wait_for(remaining())`；timeout 不 commit |
| `src/memory_system/entrypoints/consolidation_worker.py` | 修改 | track `current_run_task`；Phase A/B/C 共享 270s 总预算；mutex defensive release |
| `tests/unit/test_ops001_extraction_worker_shutdown.py` | 创建 | SIGTERM idle / in-flight / deadline |
| `tests/unit/test_ops001_consolidation_worker_shutdown.py` | 创建 | scheduler shutdown / deadline |
| `tests/unit/test_ops001_runtime_pools_timeouts.py` | 创建 | settings→client wiring 快照断言 |
| `tests/unit/test_ops001_kafka_offset_shutdown.py` | 创建 | stop 后不 poll；terminal-before-commit 回归 |
| `02_开发管理/progress.md` | 修改 | 实施态字段 |
| `02_开发管理/master_plan.md` | 修改 | OPS-001 状态备注 |

**若 Reviewer 认定 F-008/F-011 可接受为 operational risk**：`production_file_whitelist=NONE`，仅交付测试+文档化 findings。

## 18. 失败测试计划（focused；非 E2E-001）

### Unit

| ID | 场景 | 预期 |
|---|---|---|
| U1 | memory-api entrypoint 传递 `timeout_graceful_shutdown=450` | 与 settings 一致 |
| U2 | `shutdown_app_state` 调用顺序 | kafka.stop before es/neo4j/mongo/redis/httpx close |
| U3 | extraction `_install_stop_handlers` 注册 SIGTERM/SIGINT | handler 仅 set event |
| U4 | consumer loop：`should_stop=True` 且无 pending record | 立即退出；0 commit |
| U5 | extraction in-flight + stop + 短 deadline | in-flight `wait_for` 超时；**无** commit；close 用 **剩余** budget（非 270） |
| U6 | extraction idle + stop | 干净退出；close remaining ≈ 270 |
| U7 | consolidation `enabled=false` + stop | 无 scheduler；neo4j close 用 full budget |
| U8 | consolidation in-flight run + stop + 短 deadline | run task cancelled；mutex released；scheduler shutdown；close 用剩余 |
| U9 | consolidation idle + stop | scheduler shutdown + neo4j close；总耗时 ≤ budget |
| U10a | `create_app_state` pool/timeout kwargs | 匹配 §3.24/base.yaml（memory-api） |
| U10b | extraction worker client ctor kwargs | Mongo/Neo4j/ES/httpx 匹配 §3.24 |
| U10c | consolidation worker Neo4j driver kwargs | pool/timeout 匹配 §3.24 |
| U11 | ES client `max_retries=2` | settings 接线 |
| U12 | consumer loop：`get_shutdown_started` 返回 started + 短 timeout | in-flight timeout → no commit；malformed 仍 raise |
| U13 | consolidation deadline + `mutex.is_held()` after cancel | defensive release 路径 |

### Contract / Integration

| ID | 场景 | 预期 |
|---|---|---|
| C-OPS1 | `test_compose_config_contract` stop_grace | 保持 480/300/300 PASS（无 compose 改动） |
| C-OPS2 | `test_settings_validation` shutdown | 保持 PASS |
| I-OPS1 | 复跑 `test_extraction_consumer_kafka` offset 套件 | 无回归 |

### 非本任务

- Compose SIGTERM 真容器注入 → E2E-001
- 全链路 timeout 注入 → E2E-001

## 19. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用（运维生命周期） | cancel 时未完成事务回滚靠 Kafka replay |
| 幂等 | **关键** | extraction cancel 不 commit → replay；consolidation cancel 依赖 cursor/run 无 checkpoint 重扫 |
| 并发 | 单 consumer / scheduler max_instances=1 | 不变 |
| 版本冲突 | 不适用 | — |
| 用户隔离 | 不适用 | — |
| 部分失败 | shutdown timeout 视为部分失败 | 依赖既有 status/idempotency |
| 进程异常恢复 | **本任务核心** | §3.25 #5/#8 + extraction offset 规则 |

## 20. production_file_whitelist

```yaml
# HARD_BLOCK Remediation 路径（Amendment 001 对齐）：
production_file_whitelist:
  - "src/memory_system/entrypoints/extraction_worker.py"
  - "src/memory_system/infrastructure/kafka/archive_created_consumer.py"
  - "src/memory_system/entrypoints/consolidation_worker.py"

# 若 Plan Review 接受 F-008/F-011 为 documented operational risk：
production_file_whitelist: NONE
```

## 21. test_file_whitelist

```yaml
test_file_whitelist:
  - "tests/unit/test_ops001_extraction_worker_shutdown.py"
  - "tests/unit/test_ops001_consolidation_worker_shutdown.py"
  - "tests/unit/test_ops001_runtime_pools_timeouts.py"
  - "tests/unit/test_ops001_kafka_offset_shutdown.py"
```

## 22. 验收标准

- [ ] §4–§15 审计矩阵与 Findings 表完整，每项有分类
- [ ] `HARD_BLOCK` 项已修复 **或** Reviewer 书面接受风险并 `production_file_whitelist=NONE`
- [ ] Worker shutdown 总 wall-clock ≤ `shutdown.*_timeout_seconds`（in-flight + close 共享预算；Amendment 001）
- [ ] 新增 focused failure tests 全部通过
- [ ] 既有 `test_settings_validation` / `test_compose_config_contract` / extraction kafka integration 无回归
- [ ] `ruff check` / `mypy`（scoped）PASS
- [ ] 未引入通用 retry framework；未改业务 Contract
- [ ] `progress.md` / `master_plan.md` 实施态同步
- [ ] Review 无 P0/P1

## 23. 风险与阻塞项

| 风险 | 级别 | 缓解 |
|---|---|---|
| F-008 cancel 中途 extraction 半状态 | 中 | 不 commit offset；依赖 EXT-009 idempotency；U5/U12 覆盖 |
| F-011 consolidation cancel 中途 batch | 中 | 无 checkpoint；下次 run 重扫；task cancel + mutex defensive release；U8/U13 |
| F-015 §3.24 vs DEV-007 语义张力 | 低 | DEFERRED；不在本任务改 |
| Reviewer 判定零生产 diff | 低 | 测试+文档亦可交付 |
| 触碰 DEV-006/PR#13 | — | 禁止 |

## 24. Git 计划

```yaml
branch: "feat/OPS-001-graceful-shutdown-pools-timeout-retry"
expected_commits:
  - "docs(plan): add OPS-001 graceful shutdown pools timeout retry audit plan"
  - "fix(ops): bound worker in-flight shutdown deadlines"
  - "test(ops): add focused shutdown timeout retry audit tests"
out_of_scope_changes:
  - "OPS-002+"
  - "DEV-006 / PR #13"
  - "compose.yaml stop_grace_period"
  - "SiliconFlow embedding retry semantics (F-015)"
  - "Generic retry framework"
```

## 25. Plan Amendment

### Amendment 001

- **日期**：2026-08-14 00:45 UTC
- **触发**：Plan Review Round 1 PLAN_REJECTED（MUST_FIX #1 shared shutdown budget；MUST_FIX #2 whitelist alignment；SHOULD_FIX U10/F-011）
- **原计划**：worker in-flight 与 close 各自 bounded；close 可用完整 270s；F-008 可能仅改 entrypoint
- **修改内容**：
  1. §5.1 新增：270s 为 worker shutdown **总预算**（in-flight + scheduler/consumer stop + close）
  2. §7/§12/§16 Step 1/2：`shutdown_started_monotonic` on signal；全程 `remaining()` 单调递减；finally close **不得**重置 270s
  3. F-008 明确需改 `archive_created_consumer.py`（cancellable in-flight + offset 语义）；白名单 3 文件
  4. F-011 明确 `current_run_task` 跟踪、Phase A/B/C、mutex defensive release
  5. U10 拆为 U10a/b/c（runtime + extraction + consolidation wiring）；新增 U12/U13
- **修改原因**：Reviewer 指出 §3.25 总预算语义与 close 双计 270s 违规；consumer loop 为 offset 正确性所必需
- **是否影响技术规格**：**否**（澄清既有 §3.25 语义，不改 Contract）
- **审批状态**：PLAN_APPROVED Round 2（人工确认 2026-08-14）

## 26. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 23:55 UTC | planning | 创建本 Task Plan；审计矩阵；progress/master_plan 规划态 | 未实施 | 发现 F-008/F-011 HARD_BLOCK；F-015 DEFERRED |
| 2026-08-14 00:45 UTC | planning (Amendment 001) | Round 1 PLAN_REJECTED 修订：共享 270s 总预算；consumer 入白名单；F-011 run task 跟踪；U10a/b/c | 未实施 | MUST_FIX #1/#2 + SHOULD_FIX 已落实；等待 Round 2 Review |
| 2026-08-14 10:00 UTC | IMPLEMENTATION_RELEASE | implementation `61afe0d9fc44116e8a8f08b1058840a3d3f4701c`；docs(status): record on feat | scoped 20 unit + entrypoint regression；ruff/mypy PASS | phase=IMPLEMENTATION_RELEASE；`next_action=WAITING_FOR_PR_MERGE` |
| 2026-08-14 09:11 UTC | PLAN_LANDING | Release Operator；plan_commit `1ce8b65` pushed main；feat branch created | N/A | phase=PLAN_LANDING RELEASE_COMPLETED |

## 27. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/entrypoints/extraction_worker.py` | F-008 shared shutdown budget wiring |
| `src/memory_system/infrastructure/kafka/archive_created_consumer.py` | F-008 cancellable in-flight + no commit on timeout |
| `src/memory_system/entrypoints/consolidation_worker.py` | F-011 in_flight_task + Phase A/B/C shared budget |
| `tests/unit/test_ops001_extraction_worker_shutdown.py` | 创建 |
| `tests/unit/test_ops001_consolidation_worker_shutdown.py` | 创建 |
| `tests/unit/test_ops001_runtime_pools_timeouts.py` | 创建 |
| `tests/unit/test_ops001_kafka_offset_shutdown.py` | 创建 |
| `tests/unit/test_consolidation_worker_entrypoint.py` | entrypoint regression fix |

### Git 记录

```yaml
branch: feat/OPS-001-graceful-shutdown-pools-timeout-retry
plan_commit: 1ce8b65feaf8569c971e93c1b33ef7a4e9cafb5d
implementation_commit: 61afe0d9fc44116e8a8f08b1058840a3d3f4701c
implementation_commit_message: "fix(ops): bound worker shutdown shared 270s budget"
release_gate: WAITING_FOR_PR_MERGE
```

### 最终状态

`committed`
