# EXT-009 Extraction E2E + Pipeline Wiring

## 1. 任务信息

```yaml
task_id: EXT-009
task_name: Extraction E2E + Pipeline Wiring
status: planned
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "779963257e33a93ad02ef4e3f997b3c9f6706802"
branch: "feat/EXT-009-extraction-e2e-pipeline-wiring"
created_at: "2026-08-12 22:30 UTC"
updated_at: "2026-08-12 22:30 UTC"
spec_sections:
  - "§2.1.3 Memory Extraction Task"
  - "§2.1.4 Kafka 消费与任务幂等（completed 早退；terminal 持久化后才 Offset）"
  - "§2.1.13 图谱写入事务与幂等（Neo4j → Index Sync → completed → Offset）"
  - "§2.1.14 Memory Extraction 管理接口（retry/rebuild 人工恢复路径）"
  - "§2.1.15 失败处理（可人工重试表；失败注入场景）"
  - "§2.1.16 MVP 实现边界"
  - "§2.2.3 Retrieval Index 同步设计"
  - "§3.28 测试策略（Integration/E2E + 失败注入）"
  - "§3.32 MVP 开发完成验收标准（Extraction 重试不得重复写入）"
  - "Appendix B §B.10 EXT-003 边界与 Pipeline handoff"
prerequisites:
  formal:
    - "EXT-008 — SATISFIED/completed; PR #42 MERGED; Admin GET/retry/rebuild HTTP"
    - "EXT-007 — SATISFIED/completed; RetrievalIndexSyncService + mark_completed/failed"
    - "EXT-006 — SATISFIED/completed; GraphWriteService atomic Neo4j write"
    - "EXT-005 — SATISFIED/completed; ReconciliationService transient plan"
    - "EXT-004 — SATISFIED/completed; EntityAlignmentService read-only alignment"
    - "EXT-003 — SATISFIED/completed; ExtractionLlmService + extraction_result persist"
    - "EXT-002 — SATISFIED/completed; Archive preprocessing"
    - "EXT-001 — SATISFIED/completed; consumer offset gate + ExtractionPipelinePort"
    - "DEV-005 — SATISFIED/completed; Admin API shell for E2E-4"
    - "STM-011 — SATISFIED/completed; republish for admin retry/rebuild"
  implementation_reuse:
    - "ExtractionPipelinePort / PipelineTerminalDecision (domain/services/extraction_pipeline_port.py)"
    - "ExtractionLlmService + ExtractionArchivePreprocessingService (EXT-002/003)"
    - "EntityAlignmentService.load_from_persisted_task + create_entity_alignment_service"
    - "ReconciliationService.load_from_persisted_task + create_reconciliation_service"
    - "GraphWriteService.load_from_persisted_task + create_graph_write_service"
    - "RetrievalIndexSyncService.sync + create_retrieval_index_sync_service"
    - "process_archive_created_event / run_archive_created_consumer_loop (EXT-001)"
    - "ExtractionAdminService retry/rebuild (EXT-008)"
    - "FakeLlmClient / FakeTokenizeClient / FakeEmbeddingClient (§3.28)"
  baseline_evidence:
    branch: "main"
    head: "779963257e33a93ad02ef4e3f997b3c9f6706802"
    working_tree_at_planning_start: "clean before planning whitelist writes"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=779963257e33a93ad02ef4e3f997b3c9f6706802"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "pending Plan Review"
  amendment_recorded: false
  human_plan_approved: false
  developer_authorized: false
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create the exact feature branch"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
```

### 1.1 本轮门禁与停止条件

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现、测试实现、Migration、配置或依赖"
  - "进入 Developer、Code Reviewer、Commit Recorder 或 Release Operator"
  - "执行任何 Git 写命令"
  - "修改权威规格正文"
  - "修改 EXT-002..007 阶段服务内部语义（entity_alignment/reconciliation/graph_write/retrieval_index_sync/extraction_llm_service）"
stop_if:
  - "任何实现步骤需要新增未授权错误码或 failed_stage 字面量（§2.1.15 白名单外）"
  - "任何实现步骤需要修改 PipelineTerminalDecision 类型语义"
  - "任何实现步骤需要触碰 DEV-006 / PR #13"
  - "任何实现步骤需要新依赖或 Migration"
blocking_open_issues: []
nonblocking_open_issues: []
```

## 2. authoritative_scope

本任务是 **EXT-003→EXT-007 生产 pipeline continuation 的唯一权威闭合 owner**（此前各阶段 `DEFERRED_FOR_MVP`）。

权威范围（规格 + master_plan §2.1.15 / §3.28）：

| 维度 | 归属 |
|---|---|
| Production pipeline 接线 | **EXT-009** — `ProductionExtractionPipeline` 串联既有阶段库 |
| `extraction_worker.main()` 生产启动 | **EXT-009** — 替换 exit 1 stub，接入 Kafka poll loop |
| Consumer 终态 Offset 门禁 | **EXT-001** + **EXT-009 窄补丁** — terminal Mongo 后才 commit；已终态则跳过重复 `mark_*` |
| 阶段库语义 | **EXT-002..007** — **零语义 diff** |
| Admin retry/rebuild | **EXT-008** — E2E-4 仅调用既有 HTTP，不改 Admin 语义 |
| `v0.3.0-memory-extraction` 里程碑 | **EXT-009 complete** |

## 3. production_continuation_owner

```yaml
production_continuation_owner: EXT-009
prior_deferred_tasks:
  - "EXT-003→EXT-004 continuation — DEFERRED_FOR_MVP until EXT-009"
  - "EXT-004→EXT-005 continuation — DEFERRED_FOR_MVP until EXT-009"
  - "EXT-005→EXT-006 continuation — DEFERRED_FOR_MVP until EXT-009"
  - "EXT-006→EXT-007 continuation — DEFERRED_FOR_MVP until EXT-009"
closure_mechanism:
  - "新建 ProductionExtractionPipeline（implements ExtractionPipelinePort）"
  - "extraction_worker.main() 装配 pipeline + consumer loop"
  - "不重设计阶段内部；仅编排调用顺序与 outcome→PipelineTerminalDecision 映射"
forbidden:
  - "在 EXT-002..007 服务内新增 continuation 逻辑"
  - "修改 PipelineTerminalDecision / ExtractionPipelinePort 契约"
```

## 4. 任务目标

闭合记忆萃取 MVP 生产路径与 §3.28 E2E/失败注入验收，使 `Archive → Extraction（全阶段）→ Neo4j → Elasticsearch → completed → Offset` 可端到端验证，并支持 §2.1.14/§2.1.15 人工恢复。

可验证目标：

1. **`ProductionExtractionPipeline`** 实现 `ExtractionPipelinePort`；按 §2.1.13 顺序串联：LLM（可跳过）→ Entity Alignment → Reconciliation → Graph Write → Retrieval Index Sync。
2. **`extraction_worker.main()`** 启动真实 consumer poll loop（`enable_auto_commit=false`；`group=memory-extraction-group`）；不再 exit 1。
3. **Resume**：`extraction_result` 已持久化 → **跳过 LLM**，从 alignment 继续至 index sync（§2.1.14 #5 / Appendix B §B.10 #2）。
4. **Consumer 终态幂等（LD-1）**：pipeline 返回 `COMPLETE`/`FAIL` 时，consumer **先 reload**；若 EXT-007 已将任务持久化为 `completed`/`failed`，则 **直接 commit offset**，不重复 `mark_completed`/`mark_failed`（§2.1.13 完成顺序）。
5. **E2E-1..4**（见 §9.4）在 `compose.test.yaml` + Fake LLM/Embedding/Tokenize 下通过。
6. **零上游阶段服务语义 diff**；`dependency_changes_expected=NONE`；不得触碰 DEV-006/PR#13。

## 5. 非目标与黑名单

- **修改** `EntityAlignmentService` / `ReconciliationService` / `GraphWriteService` / `RetrievalIndexSyncService` / `ExtractionLlmService` / `ExtractionArchivePreprocessingService` **内部语义**。
- **修改** `PipelineTerminalDecision` / `ExtractionPipelinePort` 类型与校验规则。
- **Retrieval API**（RET-*）；全链路 Session→Consolidation E2E（E2E-001）。
- **新依赖 / Migration / Settings Contract 变更**。
- **DEV-006 / PR #13**。
- **真实 DeepSeek / 真实 SiliconFlow 计费 API** 作为 CI 默认（§3.28 Fake Server）。
- **通用 Worker 多 Topic / 自动重试 / DLT**。
- **新造错误码或 failed_stage**（仅 §2.1.15 既有表 + 本 Plan 授权映射）。

## 6. 当前代码状态与前置检查

### 6.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `779963257e33a93ad02ef4e3f997b3c9f6706802`（与用户给定 baseline 一致） |
| `git status --short` | 空 |
| EXT-008 | `completed`；Admin GET/retry/rebuild |
| EXT-007 | `completed`；`mark_completed` / `mark_failed(retrieval_index)` 在 sync 内 |
| EXT-001 consumer | `process_archive_created_event` 在 COMPLETE/FAIL 时无条件 `mark_*` |
| `extraction_worker.main()` | **stub exit 1**（实测） |
| 无 `ProductionExtractionPipeline` | 需新建 |
| workflow | `NORMAL`，explicit |

### 6.2 已存在可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| Stage libraries | `entity_alignment_service.py` 等 | 各阶段 `load_from_persisted_task` / `sync` |
| Factory helpers | `create_*_service` | Neo4j/ES/LLM 装配 |
| Consumer | `extraction_task_consumer_service.py` | 状态分支 + offset gate（需 LD-1 补丁） |
| Kafka adapter | `archive_created_consumer.py` | poll loop + manual commit |
| Fake clients | `FakeLlmClient`, `FakeTokenizeClient`, `FakeEmbeddingClient` | §3.28 Contract/E2E |
| E2E harness | `tests/e2e/conftest.py` | compose.test 基础设施模式 |
| Admin HTTP | `extraction_admin_service.py` | E2E-4 retry/rebuild |

### 6.3 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无生产 pipeline 串联 | consumer 注入 `ExtractionLlmService` 仅覆盖 LLM 阶段 |
| worker 拒绝启动 | `extraction_worker.main()` return 1 |
| consumer 可能双写终态 | COMPLETE 时 EXT-007 已 `mark_completed`，consumer 再次 `mark_completed` |
| 无 Extraction E2E | `tests/e2e/` 仅有 STM-013 |

**结论**：EXT-009 新建 pipeline + worker 接线 + consumer 窄补丁 + E2E/集成测试；不重写阶段库。

## 7. pipeline_contract

### 7.1 `ProductionExtractionPipeline`

```text
class ProductionExtractionPipeline(ExtractionPipelinePort):
    async def run(task, event) -> PipelineTerminalDecision
```

**装配依赖**（构造函数或 factory 注入，不得硬编码全局）：

- `mongodb`, `neo4j driver`, `elasticsearch`, `http_client`, `settings`
- `llm_client`（生产：DeepSeek；测试/E2E：FakeLlmClient）
- `tokenize_client`（生产：TeiTokenizeClient；测试：FakeTokenizeClient）
- `embedding_client`（生产：create_embedding_client；测试：FakeEmbeddingClient）
- 可选 `clock` / `server_time_provider`（测试固定时间）

**内部持有**（通过既有 factory 创建，不复制阶段逻辑）：

- `ExtractionLlmService`（含 preprocessing）
- `EntityAlignmentService`
- `ReconciliationService`
- `GraphWriteService`
- `RetrievalIndexSyncService`

### 7.2 `run()` 阶段顺序与分支

```text
1. LLM 阶段（EXT-003）
   IF task.extraction_result IS NULL:
     decision = await llm_service.run(task, event)
     IF decision.kind == COMPLETE: return COMPLETE          # both-empty 终态
     IF decision.kind == FAIL: return FAIL                  # llm_* 等
     IF decision.kind == ABORT_WITHOUT_TERMINAL:
       reload task; IF still no extraction_result: return ABORT
   ELSE IF is_both_empty_extraction_result(task.extraction_result):
     return COMPLETE
   ELSE:
     # extraction_result 非空 — 跳过 LLM（§2.1.14 #5 / B.10 #2）

2. Entity Alignment（EXT-004）
   outcome = alignment_service.load_from_persisted_task(mongodb, archive_id)
   IF Abort: return ABORT_WITHOUT_TERMINAL
   IF Failure: return FAIL(entity_alignment_failed, entity_alignment)

3. Reconciliation（EXT-005）
   outcome = reconciliation_service.load_from_persisted_task(
     mongodb, archive_id, entity_alignment_success=...)
   IF Abort: return ABORT_WITHOUT_TERMINAL
   IF Failure: map error_code → FAIL (graph_query_failed / reconciliation_plan_conflict / llm_*)

4. Graph Write（EXT-006）
   outcome = graph_write_service.load_from_persisted_task(
     mongodb, archive_id, entity_alignment_success=..., reconciliation_success=...)
   IF Abort: return ABORT_WITHOUT_TERMINAL
   IF Failure: return FAIL(graph_write_failed | memory_search_text_too_long, graph_write)

5. Retrieval Index Sync（EXT-007）
   sync_input = RetrievalIndexSyncInput(...)  # graph_write_success + alignment + session_id from event
   outcome = retrieval_sync_service.sync(sync_input, mongodb=mongodb, attempt_count=task.attempt_count)
   IF Abort: return ABORT_WITHOUT_TERMINAL
   IF SKIP_ALREADY_COMPLETED: return COMPLETE
   IF Failure: return FAIL(retrieval_index_write_failed, retrieval_index)  # EXT-007 已 mark_failed
   IF Success: return COMPLETE                                              # EXT-007 已 mark_completed
```

### 7.3 Pipeline 与阶段 `mark_*` 边界

| 阶段 | 失败时 Mongo `mark_failed` | 成功时 Mongo `mark_completed` |
|---|---|---|
| LLM / Alignment / Reconciliation / Graph | **否** — pipeline 返回 FAIL，由 consumer `mark_failed` | **否**（both-empty LLM 路径由 consumer `mark_completed`） |
| Retrieval Index Sync | **是**（`retrieval_index_write_failed`） | **是**（§2.1.13 完成顺序） |

Pipeline **不得**自行调用 `mark_completed`/`mark_failed`（除通过阶段库已有行为）；consumer 负责 alignment/reconciliation/graph 失败路径的 terminal 写入。

### 7.4 `create_production_extraction_pipeline` factory

- **文件**：`src/memory_system/domain/services/production_extraction_pipeline.py`（或同级 `extraction_pipeline_factory.py` 仅当单文件过长时拆分；优先单文件）
- 导出 `create_production_extraction_pipeline(...)` 供 worker 与测试复用
- 支持可选注入 `tokenize_client` / `embedding_client` / `llm_client`（E2E 失败注入 LD-3）

## 8. terminal_offset_contract

### 8.1 §2.1.13 完成顺序（不变）

```text
Commit Neo4j → Upsert ES → mark_completed → Commit Kafka Offset
```

失败路径：`mark_failed` 成功后才允许 commit offset（§2.1.15 #4）。

### 8.2 Consumer 窄补丁（LD-1）— `extraction_task_consumer_service.py`

在 `decision.kind == COMPLETE` 分支：

```text
reloaded = find_extraction_task_by_archive_id(archive_id)
IF reloaded.status == COMPLETED:
  return ProcessArchiveCreatedResult(should_commit_offset=True, task=reloaded)
ELSE:
  mark_completed(...)  # 既有逻辑（both-empty LLM 等未经过 EXT-007 的路径）
```

在 `decision.kind == FAIL` 分支：

```text
reloaded = find_extraction_task_by_archive_id(archive_id)
IF reloaded.status == FAILED:
  return ProcessArchiveCreatedResult(should_commit_offset=True, task=reloaded)
ELSE:
  mark_failed(...)  # 既有逻辑（alignment/reconciliation/graph 失败）
```

**禁止**：修改 PENDING/PROCESSING/COMPLETED 早退分支；修改 `ABORT_WITHOUT_TERMINAL` 不 commit 语义。

### 8.3 Justification（§2.1.13）

EXT-007 在 index sync 成功/失败时已 durable 写入终态；consumer 重复 `mark_*` 虽多为幂等更新，但可能产生竞态日志与重复 `updated_time` 抖动。reload + skip 是 §2.1.13「completed-before-offset」与 EXT-007 handoff 的最小闭合。

## 9. replay_idempotency

| 场景 | 预期行为 | 规格依据 |
|---|---|---|
| Kafka 重复投递（completed 任务） | consumer 早退 `should_commit_offset=True`；pipeline 不执行 | §2.1.4 |
| Kafka 重复投递（failed 任务） | consumer 早退 commit offset | §2.1.4 |
| `extraction_result` 保留 + 重试 | 跳过 LLM；Evidence MERGE 跳过重复图谱写入；ES upsert 收敛 | §2.1.13 / §2.1.14 #5 |
| Neo4j 已提交 + index 失败 | 任务 `failed`；retry 保留 `extraction_result`；重跑跳过 graph；重新 index sync | §2.1.13 末段 |
| `reconciliation_plan_conflict` | retry 拒绝；rebuild 清 `extraction_result` + republish | §2.1.14 / EXT-008 |
| 重复 Memory/Evidence/ES Document | 不得新增重复节点或文档（MERGE + ES `_id=memory_id`） | §3.32 #5 |

## 10. admin_integration

E2E-4 使用 **EXT-008 既有 Admin HTTP**（不得新增路由）：

| 步骤 | API | 预期 |
|---|---|---|
| 注入 `reconciliation_plan_conflict` | — | 任务 `failed`；`last_error.error_code=reconciliation_plan_conflict` |
| rebuild | `POST .../rebuild` | `extraction_result=null`；`status=pending`；Kafka republish |
| worker 消费 | consumer + pipeline | 全阶段重跑（含 LLM）→ `completed` |
| retry 误用 | `POST .../retry` on conflict | `409 retry_not_allowed`（可选 contract 断言） |

Admin Key：E2E harness 使用 `.env` / `API_KEY` 既有 Admin Key fixture 模式（对齐 STM E2E）。

## 11. infrastructure

### 11.1 Compose 测试栈（§3.28）

| 组件 | 来源 | 备注 |
|---|---|---|
| MongoDB | `compose.test.yaml` via `scripts/compose.sh --stack=test` | 独立 test volume |
| Kafka | 同上 | `context.archive.created` |
| Neo4j | 同上 | Migration 002 |
| Elasticsearch | 同上 | Migration 003 + alias |
| Redis | 可选（Admin E2E 不需；STM seed 若需要则启） | 与 STM E2E 模式对齐 |
| Embedding TEI | **不启动**（`--embedding=none`） | FakeEmbeddingClient |
| LLM | **不调用真实 API** | FakeLlmClient |

### 11.2 Fake 客户端（§3.28）

| 客户端 | 实现 | 用途 |
|---|---|---|
| LLM | `FakeLlmClient` | extraction JSON + reconciliation（若需） |
| Tokenize | `FakeTokenizeClient(token_count=10)` | alias 预算 / gate |
| Embedding | `FakeEmbeddingClient` / `fail=True` | E2E-2 失败注入 |

### 11.3 Worker E2E 运行模式

- 测试 harness **in-process** 调用 `process_archive_created_event` 或 `run_archive_created_consumer_loop`（`max_records=1`），避免 CI 中长期进程
- 可选：subprocess 启动 worker + `max_records` 环境变量（LD-4，仅当 in-process 无法覆盖 worker `main()` 时）

### 11.4 Migration 前置

E2E fixture 必须确保 `001..004` migrations 已执行（复用 integration 测试 `scripts/migrate` 或 conftest 逻辑）。

## 12. 实现方案

### Step 1 — `ProductionExtractionPipeline` + factory

- **文件**：`src/memory_system/domain/services/production_extraction_pipeline.py`
- 实现 §7 pipeline_contract
- 错误映射严格使用 §2.1.15 白名单
- 日志：失败路径含 §B.11 五字段；不含 content/prompt/secret

### Step 2 — Consumer 终态幂等补丁

- **文件**：`src/memory_system/domain/services/extraction_task_consumer_service.py`
- 仅 §8.2 LD-1 reload 逻辑
- 更新/新增 unit tests

### Step 3 — `extraction_worker.main()` 生产接线

- **文件**：`src/memory_system/entrypoints/extraction_worker.py`
- 加载 settings → 创建 mongodb/neo4j/es/http/kafka consumer（**非** producer 长连可选最小集）
- `create_production_extraction_pipeline` + `run_archive_created_consumer_loop`
- 优雅 shutdown：对齐 `shutdown.extraction_worker_timeout_seconds` 设置
- `main()` return 0 on normal shutdown；malformed/key mismatch 仍 fail-closed 退出

### Step 4 — Unit + Contract 测试

- Pipeline 阶段编排 mock（每阶段 outcome 映射）
- Contract：EXT-002..007 服务文件 **零 diff**；`PipelineTerminalDecision` 零 diff
- Consumer terminal idempotency

### Step 5 — Integration 测试（compose.test）

- Mongo + Kafka + Neo4j + ES + Fake clients
- 单 archive happy path（可视为 E2E-1 子集）

### Step 6 — E2E 测试（§9.4）

- `tests/e2e/test_ext009_extraction_e2e.py`
- helpers：`tests/e2e/helpers/ext009_e2e_helpers.py`
- 扩展 `tests/e2e/conftest.py`（仅 fixture；不破坏 STM-013）

## 13. 文件变更清单（实施白名单）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/services/production_extraction_pipeline.py` | 创建 | Pipeline 串联 + factory |
| `src/memory_system/entrypoints/extraction_worker.py` | 修改 | 生产 worker 启动 |
| `src/memory_system/domain/services/extraction_task_consumer_service.py` | 修改 | LD-1 terminal reload |
| `tests/unit/test_production_extraction_pipeline.py` | 创建 | Pipeline 编排 unit |
| `tests/unit/test_extraction_task_consumer_terminal_idempotency.py` | 创建 | Consumer LD-1（或合并入既有 consumer unit 文件之一，二选一） |
| `tests/contract/test_ext009_extraction_pipeline_contract.py` | 创建 | 零 upstream diff + 契约 |
| `tests/integration/test_ext009_extraction_pipeline_integration.py` | 创建 | compose.test 集成 |
| `tests/e2e/test_ext009_extraction_e2e.py` | 创建 | E2E-1..4 |
| `tests/e2e/helpers/ext009_e2e_helpers.py` | 创建 | seed archive/task/event/admin |
| `tests/e2e/conftest.py` | 修改 | EXT-009 fixtures（最小扩展） |

**白名单外任何 `src/**`、`tests/**`、配置、Migration、依赖变更 → FAIL**。

## 14. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | Neo4j 单事务（EXT-006）；ES bulk 全成败；Mongo 单文档 | §2.1.13 顺序；index 失败不标 completed |
| 幂等 | Evidence MERGE；ES upsert；task `archive_id` unique | §2.1.13；E2E-3 验证 |
| 并发 | 单 consumer `max_poll_records=1` | 不变 |
| 版本冲突 | 不适用 | 无 optimistic lock |
| 用户隔离 | 全阶段 `user_id` 过滤 | 不变 |
| 部分失败 | Neo4j 成功 + index 失败 | `failed` + retry 跳过 graph |
| 进程异常恢复 | Worker 在 Neo4j commit 后退出 | index 未 completed；retry 收敛（F1 / E2E-2） |

## 15. 测试计划

### 15.1 Unit Test

| 场景 | 预期 |
|---|---|
| U1 both-empty LLM → COMPLETE | 不进入 alignment |
| U2 LLM fail → FAIL llm_* | consumer 可 mark_failed |
| U3 extraction_result 非空 → 跳过 LLM | alignment 被调用 |
| U4 alignment fail → FAIL entity_alignment_failed | |
| U5 reconciliation_plan_conflict → FAIL | |
| U6 graph_write_failed → FAIL | |
| U7 index sync success → COMPLETE（EXT-007 已 completed） | |
| U8 index sync fail → FAIL（EXT-007 已 failed） | |
| U9 consumer COMPLETE + 已 completed → 无 mark_completed | LD-1 |
| U10 consumer FAIL + 已 failed → 无 mark_failed | LD-1 |

### 15.2 Contract Test

| 场景 | 预期 |
|---|---|
| C1 `ProductionExtractionPipeline` implements port | |
| C2 EXT-002..007 服务文件无变更 | `git diff` 白名单 |
| C3 `PipelineTerminalDecision` 无变更 | |
| C4 授权错误码/failed_stage 白名单 | §2.1.15 |
| C5 worker `main` 存在且非 stub | |

### 15.3 Integration Test

| 场景 | 预期 |
|---|---|
| I1 compose.test happy path | Neo4j 节点 + ES 文档 + completed |
| I2 index fail injection | `failed` + `retrieval_index_write_failed` |

### 15.4 e2e_test_plan

| ID | 场景 | 预期 |
|---|---|---|
| **E2E-1** | Happy path：seed context archive + publish `archive.created` + run pipeline/worker | `status=completed`；Neo4j Memory/Evidence；ES `memory_retrieval_current` 文档；offset committed |
| **E2E-2** | Index fail after graph：`FakeEmbeddingClient(fail=True)` 或 write repo 注入 | Neo4j 已写入；`status=failed`；`retrieval_index_write_failed`；**无** completed |
| **E2E-3** | Replay/idempotency：重复事件或保留 `extraction_result` 重跑 | 无重复 Memory/Evidence/ES doc；Evidence count 稳定 |
| **E2E-4** | Admin integration：冲突 → rebuild → 重跑；或 index fail → **retry** | Admin HTTP `pending`；最终 `completed`；retry 保留 extraction_result 时跳过 LLM |

### 15.5 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| F1 Worker 在 Neo4j commit 后「退出」（模拟进程终止于 index 前） | 任务非 completed；retry 后 index 收敛 |
| F2 并发双消费同一 archive | `max_poll_records=1` + Mongo 条件更新；至多一条终态 |

## 16. 验收标准

- [ ] `ProductionExtractionPipeline` 串联 EXT-003→007；implements `ExtractionPipelinePort`
- [ ] `extraction_result` 非空时跳过 LLM，继续 alignment→index
- [ ] `extraction_worker.main()` 启动 consumer；非 exit 1 stub
- [ ] Consumer LD-1：已终态任务 commit offset 且无重复 `mark_*`
- [ ] EXT-002..007 阶段服务 **零语义 diff**
- [ ] E2E-1..4 通过（compose.test + Fake LLM/Embedding/Tokenize）
- [ ] §3.28 失败注入 F1 覆盖
- [ ] scoped unit + contract + integration + e2e 全通过
- [ ] Ruff / Mypy 通过
- [ ] Review 无 P0/P1
- [ ] `dependency_changes_expected=NONE`；未触碰 DEV-006/PR#13

## 17. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | 无；continuation 闭合与 §2.1.13/B.10 一致 |
| 双写终态 | LD-1 consumer 补丁闭合 |
| Worker 生命周期 | E2E 优先 in-process harness；subprocess 为备选 |
| 前置任务 | EXT-008 completed；EXT-001..007 completed |
| 主要风险 | ① 误改阶段库；② consumer 补丁范围扩大；③ E2E 依赖真实 LLM |
| 非阻塞 | 无 |

## 18. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/EXT-009-extraction-e2e-pipeline-wiring"
baseline_main: "779963257e33a93ad02ef4e3f997b3c9f6706802"
expected_commits:
  - "docs(plan): add EXT-009 extraction e2e pipeline wiring plan"
  - "feat(ext): wire production extraction pipeline and worker"
  - "docs(status): record EXT-009 implementation commit and PR"
  - "docs(status): complete EXT-009 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "EXT-002..007 service internals"
  - "PipelineTerminalDecision / ExtractionPipelinePort types"
  - "Migration / dependency / Settings"
  - "RET-* / CON-* / E2E-001 full chain"
```

### 18.1 MVP_LOCAL_DECISION

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | Consumer 在 COMPLETE/FAIL 前 reload；已 `completed`/`failed` 则跳过 `mark_*` 直接 commit offset | EXT-007 已 mark_completed/mark_failed；§2.1.13 完成顺序；避免双写 |
| LD-2 | `ProductionExtractionPipeline` 为唯一生产 continuation owner | 闭合 EXT-003..007 `DEFERRED_FOR_MVP` |
| LD-3 | E2E 默认 injectable Fake Embedding/Tokenize；E2E-2 用 `FakeEmbeddingClient(fail=True)` | §3.28；graph 后 index 失败可复现 |
| LD-4 | E2E 优先 in-process `run_archive_created_consumer_loop(max_records=1)` | CI 稳定性；避免 hung worker |
| LD-5 | Pipeline 不在 alignment/reconciliation/graph 失败时调用 `mark_failed` | 保持 EXT-004..006 库行为；consumer 统一 terminal 写入 |
| LD-6 | `create_production_extraction_pipeline` 支持测试注入 LLM/Embedding/Tokenize | 单 factory 供 worker 与 E2E 复用 |
| LD-7 | both-empty LLM COMPLETE 仍由 consumer `mark_completed` | EXT-007 未参与；保持 EXT-003 语义 |

### 18.2 deferred_for_mvp

| 项 | 说明 |
|---|---|
| 全链路 E2E-001 Session→Consolidation | 归属 OPS/E2E-001 |
| RET-006 检索阶段 E2E | 归属 RET-006 |
| Worker subprocess 长驻生产部署验证 | OPS-003 空白环境 |
| GPU Embedding E2E | 不阻塞 CPU MVP（§3.32 #7） |
| 自动重试 / DLT | §2.1.16 暂不实现 |

### 18.3 归属声明

| 项 | 归属 |
|---|---|
| EXT-003..007 阶段算法 | 各 EXT 任务（本任务仅接线） |
| Admin HTTP | EXT-008 |
| Kafka Offset 语义 | EXT-001 + EXT-009 LD-1 |
| `v0.3.0-memory-extraction` | EXT-009 complete |
| DEV-006 | PAUSED / PR #13 |

## 19. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-12 22:30 UTC | planning | 创建 Task Plan；同步 progress/master_plan | — | baseline 7799632 verified；prerequisites SATISFIED；continuation closure planned |

## 20. 实际执行结果

### 最终状态

`planned` — 等待 Plan Review；`developer_authorized=false`；`next_action=计划审查`；**不得触碰 DEV-006/PR#13**。

### Git 记录

```yaml
branch: feat/EXT-009-extraction-e2e-pipeline-wiring
plan_commit: null
implementation_commit: null
implementation_commit_message: null
```
