# EXT-007 Retrieval Document 同步

## 1. 任务信息

```yaml
task_id: EXT-007
task_name: Retrieval Document 同步
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "2db6f5a8957e26a672aa4fcba3bf69eb65b0de1e"
branch: "feat/EXT-007-retrieval-document-sync"
created_at: "2026-08-12 20:55 UTC"
updated_at: "2026-08-12 21:30 UTC"
spec_sections:
  - "§2.1.3 Memory Extraction Task（任务表不保存 Memory/Entity 结果 ID 数组）"
  - "§2.1.4 Kafka 消费与任务幂等（completed 早退；terminal 持久化后才 Offset）"
  - "§2.1.13 图谱写入事务与幂等（完成顺序：Neo4j → Index Sync → completed → Offset）"
  - "§2.1.15 失败处理（retrieval_index_write_failed）"
  - "§2.1.16 MVP 实现边界"
  - "§2.2.3 Retrieval Index 同步设计（权威范围）"
  - "§2.2.4 Elasticsearch Retrieval Index 数据结构（消费 Alias；不创建 Mapping）"
  - "§3.6 全异步客户端（neo4j、httpx、elasticsearch AsyncElasticsearch）"
  - "§3.10 Embedding（create_embedding_client / SiliconFlow；TEI /tokenize 仅计数）"
  - "§3.24 连接池、超时与重试"
  - "§3.26 Schema Migration（已执行 Migration 不得修改）"
  - "§3.27 日志、指标与敏感信息保护（memory_search_text_omitted_alias_total）"
  - "§3.28 测试策略"
  - "Appendix B §B.10 Pipeline handoff、§B.11 Privacy"
prerequisites:
  formal:
    - "EXT-006 — SATISFIED/completed; PR #40 MERGED merge 372e0232c1e5cfa1d71e2bb0152a22f59e60cd03; transient GraphWriteSuccess.index_sync_memory_set with IndexSyncMemoryEntry{memory_id, core_search_text, token_count}"
    - "DEV-007 — SATISFIED/completed; create_embedding_client + SiliconFlowEmbeddingClient (default provider)"
    - "DEV-004 — SATISFIED/completed; migration 003 memory_retrieval_v1 + alias memory_retrieval_current"
    - "EXT-001 — SATISFIED/completed; terminal-persistence-before-offset gate（本任务不提交 Offset）"
  implementation_reuse:
    - "GraphWriteSuccess / IndexSyncMemoryEntry (domain/models/graph_write.py)"
    - "EntityAlignmentSuccess / AlignedEntity (domain/models/entity_alignment.py)"
    - "build_core_search_text / normalize_search_text_fragment (domain/services/core_search_text.py)"
    - "TokenizeClient / TeiTokenizeClient / FakeTokenizeClient (EXT-006 TEI /tokenize — 非 DEV-006 embedding)"
    - "create_embedding_client / EmbeddingClient / EmbeddingServiceError (DEV-007)"
    - "extraction_task_repository.mark_completed / mark_failed (infrastructure/mongodb/)"
    - "AsyncElasticsearch in AppState; settings.memory_retrieval.index_name (alias)"
    - "MEMORY_RETRIEVAL_V1_MAPPINGS field set (scripts/migrations/003 — 只读对照，不修改)"
  baseline_evidence:
    branch: "main"
    head: "2db6f5a8957e26a672aa4fcba3bf69eb65b0de1e"
    working_tree_at_planning_start: "clean before planning whitelist writes"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=2db6f5a8957e26a672aa4fcba3bf69eb65b0de1e"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "pending Plan Review"
  amendment_recorded: false
  human_plan_approved: true
  developer_authorized: true
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
  - "修改 PipelineTerminalDecision / extraction_task_consumer_service / extraction_worker / extraction_llm_service / entity_alignment_service / reconciliation_service / graph_write_service"
stop_if:
  - "任何实现步骤需要新增错误码、新增未在 Task Plan 授权的 failed_stage 字面量、新增 durable 字段或改变既有 Schema/Mapping"
  - "任何实现步骤需要创建或修改 Elasticsearch Mapping/Alias（缺失则 retrieval_index_write_failed）"
  - "任何实现步骤需要提交 Kafka Offset 或修改 consumer offset 语义"
  - "任何实现步骤需要触碰 DEV-006 / PR #13"
  - "任何实现步骤需要 pipeline continuation 接线（DEFERRED_FOR_MVP）"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-006
```

## 2. 任务目标

在 EXT-006 已提交 Neo4j 写事务并产出瞬态 `GraphWriteSuccess.index_sync_memory_set` 之后，实现 §2.2.3 **完整 Retrieval Index 同步**：扩展 `index_sync_memory_set`、从 Neo4j 加载权威 Memory/Entity 数据、构建含 alias 预算的 `search_text`、经 `create_embedding_client` 生成向量、Bulk Upsert 至 Alias `memory_retrieval_current`（`refresh=wait_for`），并在全部成功后**首次**将 `memory_extraction_task.status` 持久化为 `completed`。

可验证目标：

1. **集合扩展（§2.2.3 + LD-8 闭合）**：以 EXT-006 handoff 为种子，经 Neo4j 只读查询扩展为完整 `index_sync_memory_set`（Evidence 直接支持 Memory + `SUPERSEDES`/`CONFLICTS_WITH` 关联 Memory + 本次已对齐非用户 Entity 的 `SUBJECT`/`OBJECT` 关联 Memory）；`user:{user_id}` 保留实体不得触发批量重建；按 `memory_id` 去重。
2. **权威数据加载**：对集合内每条 Memory 从 Neo4j 加载 §2.2.4 Document 所需字段及关联 Entity `canonical_name`/`aliases`；全部 Cypher 必须 `user_id` 过滤。
3. **`search_text` 构建**：`core_search_text` 复用 `build_core_search_text`；alias 按 §2.2.3 规则 5–7 用 **TEI `/tokenize`**（`TeiTokenizeClient`，非 DEV-006 `TEIEmbeddingClient`）做预算裁剪；最终 `1 <= token_count <= 1024`；累计 `memory_search_text_omitted_alias_total`。
4. **Embedding**：经 `create_embedding_client(settings, http_client)`（默认 `siliconflow` / DEV-007）对最终 `search_text` 批量生成 `1024` 维向量；`EmbeddingServiceError` 映射 `retrieval_index_write_failed`。
5. **Elasticsearch 写入**：Bulk Upsert 至 `settings.memory_retrieval.index_name`（`memory_retrieval_current`）；Document `_id = memory_id`；`refresh=wait_for`；逐 Item 检查；任一 Item 或 HTTP 失败 → 整次同步失败。
6. **任务终态（§2.1.13 完成顺序）**：全部 Item 成功 → `mark_completed`；索引/Embedding 失败 → `mark_failed(retrieval_index_write_failed, failed_stage=retrieval_index)`；**不**提交 Kafka Offset（仍由 EXT-001 consumer 在 terminal Mongo 成功后提交）。
7. **幂等/重放**：`status=completed` 任务跳过重复同步；Neo4j 已提交 + 索引失败重试通过 ES Upsert 收敛；图谱 Evidence SKIP 重放路径仍可重新同步。
8. **零上游语义变更**：`PipelineTerminalDecision` / consumer / worker / EXT-001–006 服务 **逐字不变**；pipeline 接线 `DEFERRED_FOR_MVP`。

## 3. 非目标与黑名单

- **Mapping/Alias 创建或修改**（DEV-004 已完成；缺失或不兼容 → `retrieval_index_write_failed`）。
- **Kafka Offset 提交**（EXT-001 consumer 责任）。
- **Pipeline continuation 接线**（`GraphWriteService` → 本服务 → consumer；`DEFERRED_FOR_MVP`）。
- **修改** `PipelineTerminalDecision` / `extraction_task_consumer_service` / `extraction_worker` / `extraction_llm_service` / `entity_alignment_service` / `reconciliation_service` / `graph_write_service`。
- **Retrieval API**（RET-*）；**EXT-008** 管理接口；**EXT-009** E2E；speculative reindex jobs。
- **DEV-006 / PR #13**（`TEIEmbeddingClient` 全量 embedding 适配层）。
- **新错误码**；**禁止** `graph_write_failed`、`memory_search_text_too_long`、`llm_*`、`archive_*`、`entity_alignment_failed` 等上游码。
- **Schema/Migration/依赖/Settings 变更**（`dependency_changes_expected=NONE`）。
- 原始消息、memory content、实体名、向量值、prompt、secret 的日志/fixture/异常明文。

## 4. 当前代码状态与前置检查

### 4.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `2db6f5a8957e26a672aa4fcba3bf69eb65b0de1e`（与用户给定 `planning_baseline_main` 一致） |
| `git status --short` | 空 |
| EXT-006 | `completed`；`GraphWriteSuccess` + `IndexSyncMemoryEntry` 已实现 |
| DEV-007 | `completed`；`create_embedding_client` + `SiliconFlowEmbeddingClient` |
| DEV-004 | `completed`；`003_elasticsearch_memory_v1` + alias `memory_retrieval_current` |
| workflow | `NORMAL`，explicit |

### 4.2 已存在可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| `IndexSyncMemoryEntry` / `GraphWriteSuccess` | `domain/models/graph_write.py` | EXT-006 handoff 种子 |
| `build_core_search_text` | `domain/services/core_search_text.py` | core 文本（无 alias） |
| `TeiTokenizeClient` | `infrastructure/tei/tei_tokenize_client.py` | `/tokenize` 精确计数 |
| `FakeTokenizeClient` | `infrastructure/tei/fake_tokenize_client.py` | 单元/契约测试 |
| `create_embedding_client` | `infrastructure/embedding/factory.py` | Embedding 工厂 |
| `EmbeddingServiceError` | `infrastructure/embedding/errors.py` | 失败映射源 |
| `mark_completed` / `mark_failed` | `infrastructure/mongodb/extraction_task_repository.py` | 任务终态 |
| `AsyncElasticsearch` | `infrastructure/runtime.py` | ES 客户端 |
| `MEMORY_RETRIEVAL_V1_MAPPINGS` | `scripts/migrations/003_elasticsearch_memory_v1.py` | Document 字段对照 |

### 4.3 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无 retrieval index sync 领域模型/服务 | `rg retrieval_index_sync` 仅命中规格/规划 |
| 无 ES bulk write repository | `src/` 无 `bulk` / retrieval write |
| 无 Neo4j Memory+Entity 索引加载 repository | `neo4j/` 仅 alignment/recall/evidence/graph_write |
| 无 `search_text` alias 预算构建器 | 仅 `core_search_text` |
| 无 `index_sync_memory_set` 扩展查询 | EXT-006 LD-8 仅 Archive 写集 |
| 无任务 `completed` 写入路径 | EXT-006 明确 zero completed |
| `memory_search_text_omitted_alias_total` 未实现 | 规格 §2.2.3 #6 |

**结论**：EXT-007 需新建索引同步领域层、Neo4j 只读扩展/加载 repository、ES bulk write repository、search_text 构建器；不需要 Migration、依赖或 Settings 变更。

## 5. Exact Contract 闭合

### 5.1 输入契约

```text
RetrievalIndexSyncInput {
  task_id: str
  archive_id: str
  user_id: str
  session_id: str | null
  graph_write_success: GraphWriteSuccess          # EXT-006 成功输出；含种子 index_sync_memory_set
  entity_alignment: EntityAlignmentSuccess        # 扩展非用户 Entity 关联 Memory 所需
}
```

| 输入 | 耐久性 | Replay 行为 | 前置条件 |
|---|---|---|---|
| `graph_write_success` | **瞬态**（调用方传入；replay 可经 Evidence SKIP 重算 handoff） | 消费 `index_sync_memory_set` 为种子；**不得**仅信任 handoff 为最终集合 | `skipped_graph_write` 可为 true；Neo4j 图谱已 durable |
| `entity_alignment` | **瞬态** | 调用方重跑 EXT-004 或传入等价对象 | `outcome=success`；用于非用户 Entity 扩展 |
| `task_id` / `archive_id` / `user_id` / `session_id` | **持久化**（Mongo） | 服务内只读校验任务文档 | `status=processing`（非 completed/failed） |
| Neo4j Memory/Entity | **外部读** | 扩展集合 + 加载 Document 字段 | 图谱已由 EXT-006 提交 |

硬性规则：

- **禁止**重调 extraction/reconciliation/alignment/graph LLM 或重写 Neo4j。
- **禁止**修改 Mongo `extraction_result`。
- **禁止**提交 Kafka Offset。
- `user_id` 仅取任务文档；全部 Cypher/ES 过滤器必须含 `user_id`。
- `session_id` 仅用于日志（可用时）；不得从 `entity_alignment` 读取。

### 5.2 EXT-006 LD-8 与 §2.2.3 完整集合 — 闭合策略

| 来源 | EXT-006 LD-8（种子） | EXT-007 扩展（§2.2.3） |
|---|---|---|
| 本 Archive create/update Memory | handoff `index_sync_memory_set` | 保留；`core_search_text` 可复用 handoff 预计算值 |
| `SUPERSEDES` / `CONFLICTS_WITH` 关联 Memory | **不在** handoff | Neo4j：从种子 `memory_id` 双向查询关联 Memory |
| 非用户 Entity 的 `SUBJECT`/`OBJECT` 关联 Memory | **不在** handoff（SF-002 DEFERRED） | Neo4j：对 `entity_alignment.alignments` 中 `entity_id != user:{user_id}` 的 Entity 查询相连 Memory |
| `user:{user_id}` 保留实体 | — | **排除**；不得因其 alias 更新批量加入集合 |
| 去重 | handoff 内唯一 | 全集合按 `memory_id` 去重 |

扩展后集合 = `seed_memory_ids ∪ related_supersedes_conflict_ids ∪ entity_linked_memory_ids \ {invalid}`。

对扩展新增（非 handoff）的 `memory_id`：必须从 Neo4j 重建 `core_search_text`（不得使用 handoff 条目）；事务前 `memory_search_text_too_long` 门禁已在图谱写入时覆盖本 Archive 新建/更新 Memory，扩展 Memory 为历史节点，假定 core 合法。

### 5.3 `search_text` 构建（§2.2.3 规则 1–7）

```text
core_search_text = build_core_search_text(...)   # 复用 EXT-006 模块

search_text = core_search_text + aliases_that_fit_budget
```

| 规则 | 实现要点 |
|---|---|
| 1 规范化 | 复用 `normalize_search_text_fragment` / `join_non_empty_with_single_space` |
| 2 用户实体隐私 | `subject_entity_id` 或 `object_entity_id == user:{user_id}` 时不拼接其 `canonical_name` 与 aliases |
| 3 核心不可截断 | `content`、主体名、`predicate`、客体名/值不可省略或重排 |
| 4 事务前 core 门禁 | 本 Archive 新建/更新 Memory 已在 EXT-006 校验；扩展 Memory 从 Neo4j 重建 core |
| 5 alias 顺序 | 主体 aliases（code point 升序）→ 客体 aliases（code point 升序）；逐条尝试追加 |
| 6 预算 | 每次追加后 `/tokenize` 全文；`> 1024` 跳过该 alias；累计 `omitted_alias_count` → 指标 `memory_search_text_omitted_alias_total` |
| 7 最终校验 | `1 <= token_count <= 1024`；相同 Neo4j 数据逐字节一致 |

handoff 种子条目：若 Neo4j 加载后 core 与 handoff `core_search_text` 一致，可复用 handoff `core_search_text` 与 `token_count` 作为 alias 循环起点（优化，非必须）。

### 5.4 Elasticsearch Document（§2.2.4）

写入 Alias：`settings.memory_retrieval.index_name`（`memory_retrieval_current`）。

| 字段 | 来源 |
|---|---|
| `memory_id` | Neo4j `Memory.memory_id`；Bulk `_id` |
| `user_id` | 任务文档 |
| `memory_type` | Neo4j |
| `status` | Neo4j |
| `content` | Neo4j |
| `search_text` | 本任务构建 |
| `predicate` | Neo4j |
| `event_status` | Neo4j（非 Event 为 `null`） |
| `latest_source_time` | Neo4j |
| `updated_time` | Neo4j |
| `embedding` | `EmbeddingClient.embed([search_text])`；长度 `1024` |

Bulk 参数：`refresh=wait_for`；检查 HTTP status 与每个 `items[]`；无跨 Item 原子性 — 部分成功允许暂时可被直接召回，失败时任务 `failed`，重试 Upsert 收敛。

### 5.5 输出契约

```text
RetrievalIndexSyncOutcomeKind = success | failure | skip_already_completed

RetrievalIndexSyncSuccess {
  user_id: str
  archive_id: str
  synced_memory_count: int
  omitted_alias_total: int          # 本次同步累计 skipped aliases
  task: MemoryExtractionTask        # status=completed
}

RetrievalIndexSyncFailure {
  error_code: Literal["retrieval_index_write_failed"]
  failed_stage: Literal["retrieval_index"]
  message: str                      # 脱敏；无 content/向量/secret
  task: MemoryExtractionTask | None # mark_failed 成功后填充
}

RetrievalIndexSyncSkip {
  reason: Literal["task_already_completed"]
  task: MemoryExtractionTask
}
```

**EXT-007 授权错误码**：仅 `retrieval_index_write_failed`（`failed_stage=retrieval_index`）。

**EXT-007 禁止产生的错误码**：`graph_write_failed`、`memory_search_text_too_long`、`entity_alignment_failed`、`graph_query_failed`、`reconciliation_plan_conflict`、`llm_*`、`archive_*`、`kafka_publish_failed`、任何新造码。

### 5.6 完成顺序与 Offset 边界（§2.1.13）

```
Neo4j committed (EXT-006)
        |
Expand + Load + search_text + Embedding
        |
Bulk Upsert ES (refresh=wait_for)
        |
mark_completed (EXT-007 — 首个写入 completed 的阶段)
        |
(consumer) Commit Kafka Offset   ← EXT-001；本任务不实现
```

索引失败路径：

```
mark_failed(retrieval_index_write_failed, failed_stage=retrieval_index)
        |
(consumer) Commit Kafka Offset   ← 失败 terminal 持久化成功后
```

本任务 **不得** 调用 consumer offset API；库服务仅负责 Mongo terminal 写入。

## 6. 实现方案

### Step 1 — 领域模型与端口

- **文件**：`src/memory_system/domain/models/retrieval_index_sync.py`
- **类**：`RetrievalIndexSyncInput`、`RetrievalIndexSyncOutcome`、`RetrievalIndexSyncSuccess`、`RetrievalIndexSyncFailure`、`RetrievalIndexSyncSkip`、`MemoryIndexDocument`（ES payload，无 `omitted_alias_count` 持久化字段）
- **输入**：§5.1
- **输出**：§5.5；`extra=forbid`
- **错误处理**：Outcome 判别；不抛未映射业务异常到 consumer
- **幂等**：Outcome 纯函数部分无副作用；terminal 写入在 service 层

### Step 2 — `index_sync_memory_set` 扩展器

- **文件**：`src/memory_system/domain/services/index_sync_set_expander.py`
- **函数**：`expand_index_sync_memory_ids(seed_ids, entity_alignment, user_id) -> set[str]`（纯逻辑）；配合 repository 端口
- **输入**：handoff memory_id 列表 + 对齐的非用户 `entity_id` 列表
- **输出**：去重后的 `memory_id` 全集
- **Neo4j 查询**（新 repository Step 3）：
  - `Q-RI-1`：从种子 Memory 查 `SUPERSEDES`/`CONFLICTS_WITH` 双向邻居（`user_id` 过滤）
  - `Q-RI-2`：从非用户 Entity 查 `SUBJECT`/`OBJECT` 相连 Memory（`user_id` 过滤；排除仅因 `user:{user_id}` 连通的批量）
- **幂等**：只读；相同图谱状态 → 相同集合

### Step 3 — Neo4j 只读加载 Repository

- **文件**：`src/memory_system/infrastructure/neo4j/retrieval_index_read_repository.py`
- **类**：`RetrievalIndexReadRepository`
- **方法**：
  - `expand_related_memory_ids(user_id, seed_memory_ids) -> set[str]`
  - `expand_entity_linked_memory_ids(user_id, entity_ids) -> set[str]`
  - `load_memory_index_rows(user_id, memory_ids) -> list[MemoryIndexRow]`（含 subject/object entity names + aliases）
- **输入/输出**：Cypher 参数化；返回 typed dataclass/Pydantic
- **错误处理**：驱动/查询异常 → 上层映射 `retrieval_index_write_failed`
- **事务**：只读；无写

### Step 4 — `search_text` 构建器（含 alias 预算）

- **文件**：`src/memory_system/domain/services/search_text_builder.py`
- **函数**：`build_search_text_with_alias_budget(*, core_search_text, subject_aliases, object_aliases, user_id, subject_entity_id, object_entity_id, tokenize_client, max_tokens=1024) -> SearchTextBuildResult`
- **返回**：`search_text: str`、`token_count: int`、`omitted_alias_count: int`
- **依赖**：`TokenizeClient`（`TeiTokenizeClient`）；**不得**使用 `create_embedding_client` 做 token 计数
- **错误处理**：`TokenizeServiceError` → 上层 `retrieval_index_write_failed`

### Step 5 — Elasticsearch Bulk Write Repository

- **文件**：`src/memory_system/infrastructure/elasticsearch/retrieval_index_write_repository.py`
- **类**：`RetrievalIndexWriteRepository`
- **方法**：`bulk_upsert(index_alias, documents: list[MemoryIndexDocument]) -> None`
- **实现**：`AsyncElasticsearch.bulk`；`refresh=wait_for`；`_id=memory_id`；逐 item 检查 `error` 字段
- **错误处理**：HTTP 非 2xx 或任一 item 失败 → 抛 `RetrievalIndexWriteError`（内部类型）→ service 映射 `retrieval_index_write_failed`
- **幂等**：Upsert by `memory_id`

### Step 6 — 编排服务 `RetrievalIndexSyncService`

- **文件**：`src/memory_system/domain/services/retrieval_index_sync_service.py`
- **类**：`RetrievalIndexSyncService`
- **依赖注入**：`RetrievalIndexReadRepository`、`RetrievalIndexWriteRepository`、`TokenizeClient`、`EmbeddingClient`、`Settings`、`server_time_provider`（测试）
- **主方法**：`async def sync(input: RetrievalIndexSyncInput, *, mongodb) -> Outcome`
- **流程**：
  1. 只读加载 Mongo 任务；`status=completed` → `RetrievalIndexSyncSkip`；`status!=processing` → 失败/abort（不标 terminal）
  2. 扩展 `index_sync_memory_set` memory_ids
  3. Neo4j 加载 Memory+Entity 行
  4. 对每条 Memory 构建 `search_text`（handoff core 可复用）
  5. `embedding_client.embed(search_texts)` 批量（顺序与 documents 对齐）
  6. `bulk_upsert` 至 alias
  7. 成功 → `mark_completed`；失败 → `mark_failed` + 日志（`task_id`、`archive_id`、`user_id`、`failed_stage=retrieval_index`、`attempt_count`）
- **指标**：发射 `memory_search_text_omitted_alias_total`（累计本次 omitted aliases）
- **禁止**：Offset、pipeline 修改、上游服务修改

### Step 7 — 工厂辅助（可选最小）

- **文件**：`src/memory_system/domain/services/retrieval_index_sync_service.py` 内 `build_retrieval_index_sync_service(...)` 或同级 `factory` 函数
- **用途**：测试与未来 worker 接线；本任务不接线 worker

## 7. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/retrieval_index_sync.py` | 创建 | 输入/输出/ES document 模型 |
| `src/memory_system/domain/services/index_sync_set_expander.py` | 创建 | 集合扩展纯逻辑 |
| `src/memory_system/domain/services/search_text_builder.py` | 创建 | alias 预算 + search_text |
| `src/memory_system/domain/services/retrieval_index_sync_service.py` | 创建 | 编排 + terminal 写入 |
| `src/memory_system/infrastructure/neo4j/retrieval_index_read_repository.py` | 创建 | 扩展查询 + Memory/Entity 加载 |
| `src/memory_system/infrastructure/elasticsearch/retrieval_index_write_repository.py` | 创建 | Bulk upsert |
| `tests/unit/test_search_text_builder.py` | 创建 | alias 顺序/预算/用户实体隐私 |
| `tests/unit/test_index_sync_set_expander.py` | 创建 | 去重与扩展逻辑 |
| `tests/unit/test_retrieval_index_sync_service.py` | 创建 | 成功/失败/skip/completed 路径 |
| `tests/contract/test_ext007_contract.py` | 创建 | 模型形状、错误码白名单、无上游字段 |
| `tests/integration/test_ext007_retrieval_index_sync.py` | 创建 | Neo4j+ES 真实写入、bulk 部分失败、replay upsert |
| `tests/support/fake_retrieval_index_*.py`（按需） | 创建 | Fake read/write/embedding 端口 |

**白名单外禁止修改**（含 zero diff 门禁）：

- `src/memory_system/domain/services/extraction_task_consumer_service.py`
- `src/memory_system/domain/services/extraction_pipeline_port.py`
- `src/memory_system/domain/services/graph_write_service.py`
- `src/memory_system/domain/services/extraction_llm_service.py`
- `src/memory_system/domain/services/entity_alignment_service.py`
- `src/memory_system/domain/services/reconciliation_service.py`
- `scripts/migrations/*`
- `pyproject.toml` / `uv.lock`

## 8. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | Bulk 无跨 Item 原子性；任务级非原子 | §2.2.3 #10–11：部分 Item 成功可暂时可见；任务保持 `failed` 直至重试全成功；禁止 silent 标 `completed` |
| 幂等 | ES Upsert by `memory_id`；completed 任务 skip | 重放相同数据 → 相同 Document；`status=completed` 不重复同步 |
| 并发 | 同 `archive_id` 单任务；Kafka partition key=`user_id` | Mongo `mark_completed`/`mark_failed` 条件更新 `status=processing`；失败若已被其他 worker 终端化则抛/abort |
| 版本冲突 | 不适用（无 optimistic lock） | ES 最后写入胜出；Retrieval 最终经 Neo4j 权威校验（RET-003） |
| 用户隔离 | 适用 | 全部 Neo4j/ES 查询 `user_id` 过滤；用户实体不进入扩展集合 |
| 部分失败 | 适用 | Bulk 部分成功 → 整次失败 + `mark_failed`；已成功 doc 靠重试 Upsert 收敛 |
| 进程异常恢复 | 适用 | Neo4j durable 后进程退出 → 重试跳过图谱（Evidence 幂等）并重新索引；不得标 `completed` 除非 ES 全成功 |

## 9. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| U1 alias 顺序 | 主体 aliases code point 升序先于客体 |
| U2 alias 预算 | 超 1024 token 的 alias 被跳过；`omitted_alias_count` 正确 |
| U3 用户实体隐私 | `user:{user_id}` 的 canonical_name/aliases 不进入 `search_text` |
| U4 core 不可变 | 核心字段不被 alias 逻辑截断或重排 |
| U5 集合扩展去重 | seed + related + entity-linked 并集去重 |
| U6 `EmbeddingServiceError` 映射 | → `retrieval_index_write_failed` / `failed_stage=retrieval_index` |
| U7 completed skip | `status=completed` → skip；不调用 ES write |
| U8 handoff core 复用 | 种子条目 core 一致时允许复用 handoff 预计算 |

### Contract Test

| 场景 | 预期 |
|---|---|
| C1 输入/输出形状 | `extra=forbid`；必填字段齐全 |
| C2 授权错误码 | 仅 `retrieval_index_write_failed` |
| C3 `failed_stage` 字面量 | 仅 `retrieval_index` |
| C4 禁止上游码 | 不出现 `graph_write_failed` 等 |
| C5 ES Document 字段 | 与 §2.2.4 一致；无 `omitted_alias_count` 字段 |
| C6 零上游 diff | consumer/pipeline/graph_write 文件无变更 |

### Integration Test

| 场景 | 预期 |
|---|---|
| I1  happy path | Neo4j 种子 Memory + ES alias 存在 → bulk upsert 成功 → Mongo `completed` |
| I2 集合扩展 | 存在 `SUPERSEDES` 邻居 Memory → 一并写入 ES |
| I3 bulk 部分失败 | 注入一条非法 doc → 整次失败 → Mongo `failed` + `retrieval_index_write_failed` |
| I4 replay upsert | 同一 `memory_id` 二次同步 → ES doc 更新不重复；最终一致 |
| I5 Neo4j 成功后 ES 失败恢复 | 第一次 failed；修复后重试 → `completed` |
| I6 user 实体不扩展 | 仅 `user:{user_id}` 关联时不批量加入无关 Memory |

### E2E Test

| 场景 | 预期 |
|---|---|
| — | **不适用**；端到端写入→检索归属 RET-006 / EXT-009 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| F1 Embedding 不可用 | Fake 抛 `EmbeddingServiceError` → `failed`；不 `completed` |
| F2 TEI tokenize 不可用 | → `retrieval_index_write_failed` |
| F3 `mark_failed` 条件竞争 | 非 `processing` 状态 → 不静默成功 |

## 10. 验收标准

- [x] `index_sync_memory_set` 按 §2.2.3 扩展（闭合 EXT-006 LD-8）；`user:{user_id}` 不触发批量重建
- [x] `search_text` 含 alias 预算；TEI `/tokenize` 计数；`memory_search_text_omitted_alias_total` 发射
- [x] Embedding 经 `create_embedding_client`（默认 siliconflow）；`1024` 维
- [x] ES Bulk Upsert 至 `memory_retrieval_current`；`_id=memory_id`；`refresh=wait_for`；逐 Item 检查
- [x] 全成功 → `mark_completed`；失败 → `mark_failed(retrieval_index_write_failed, failed_stage=retrieval_index)`
- [x] **零** Kafka Offset 写入；**零** upstream pipeline/consumer/worker/EXT-001–006 服务 diff
- [x] 不创建/修改 Mapping/Alias
- [x] 对应测试全部通过（scoped unit + contract + integration）
- [x] Ruff 通过
- [x] Mypy 通过
- [ ] Review 无 P0/P1

## 11. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | 无已知冲突；LD-8 与 §2.2.3 全文由本任务扩展闭合 |
| 当前代码冲突 | 无 retrieval write 模块；与 EXT-006 handoff 形状一致 |
| 前置任务 | EXT-006、DEV-007、DEV-004 均已 completed |
| 未批准依赖 | `dependency_changes_expected=NONE` |
| API/Schema 变化 | 无；仅新增库级服务与 repository |
| 主要风险 | ① 误提交 Offset → 门禁 C6；② 误改 upstream → 门禁 C6；③ Bulk 部分成功却标 completed → I3；④ content/向量泄漏 → privacy；⑤ 误用 DEV-006 TEI embedding 做 token 计数 |
| 非阻塞 | OI-006 |

## 12. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/EXT-007-retrieval-document-sync"
baseline_main: "2db6f5a8957e26a672aa4fcba3bf69eb65b0de1e"
expected_commits:
  - "docs(plan): add EXT-007 retrieval document sync plan"
  - "feat(ext): add retrieval index document sync"
  - "docs(status): record EXT-007 implementation commit and PR"
  - "docs(status): complete EXT-007 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "PipelineTerminalDecision / consumer / worker wiring"
  - "Mapping/Alias creation or modification"
  - "Migration / dependency / Settings"
  - "EXT-001–006 service semantic changes"
```

### 12.1 MVP_LOCAL_DECISION

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | `retrieval_index_write_failed` → `failed_stage="retrieval_index"` | 规格 §2.1.15 授权码；图谱阶段已用 `graph_write`；索引阶段需区分 failed_stage |
| LD-2 | TEI `/tokenize` 复用 `TeiTokenizeClient`（`settings.embedding.base_url`） | 与 EXT-006 同一 TEI 实例；**非** DEV-006 `TEIEmbeddingClient` |
| LD-3 | `EmbeddingServiceError` 一律映射 `retrieval_index_write_failed` | 用户指定；不新增 provider 级错误码 |
| LD-4 | `TokenizeServiceError`（alias 阶段）映射 `retrieval_index_write_failed` | 索引阶段失败；`memory_search_text_too_long` 仅事务前（EXT-006） |
| LD-5 | `status=completed` → skip 同步，返回 `RetrievalIndexSyncSkip` | 对齐 EXT-001 consumer completed 早退；避免重复 ES 写入 |
| LD-6 | 库服务内调用 `mark_completed`/`mark_failed`；不返回 `PipelineTerminalDecision` | pipeline 接线 DEFERRED；但本任务拥有 completed 门禁 |
| LD-7 | EXT-006 handoff 为种子；§2.2.3 全文扩展在 EXT-007 经 Neo4j 完成 | 闭合 LD-8 / SF-002 |
| LD-8 | `omitted_alias_count` 仅日志/指标；**不**写入 ES Document | 规格 §2.2.3 #6 MVP 不要求 Mapping 字段 |
| LD-9 | Mongo 任务只读加载置于 `retrieval_index_sync_service.py` | 同 EXT-006 LD-6 模式 |

### 12.2 归属声明

| 项 | 归属 |
|---|---|
| EXT-006→EXT-007 pipeline 接线 | Appendix B §B.10.4 `DEFERRED_FOR_MVP` |
| Kafka Offset 提交 | EXT-001 consumer（terminal Mongo 后） |
| Mapping/Alias 创建 | DEV-004（已完成） |
| Retrieval API / BM25 / Vector | RET-* |
| 写入→可检索 E2E | RET-006 / EXT-009 |
| DEV-006 `TEIEmbeddingClient` | PAUSED / PR #13 |

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-12 20:55 UTC | planning | 创建 Task Plan；同步 progress/master_plan | — | baseline 2db6f5a verified；prerequisites SATISFIED |
| 2026-08-12 21:30 UTC | implementation | 新增 EXT-007 领域模型、Neo4j 只读/ES bulk repository、search_text 构建器、RetrievalIndexSyncService 及测试/support fakes | unit 25 + contract 11 + integration 5 PASS；ruff/mypy PASS | SF-1 MemoryIndexRow；SF-2 空集合 mark_completed synced_count=0；SF-3 EMBEDDING_BATCH_SIZE=32；零 upstream diff |

## 14. 实际执行结果

### 最终状态

`tested` — 实现与 scoped 测试完成；等待 Code Review。

### Git 记录

```yaml
branch: "feat/EXT-007-retrieval-document-sync"
plan_commit: "d2dcfe709f3f7a4e8ae933b7ded2874c33d4af5d"
implementation_commit: null
implementation_commit_message: null
next_action: "Code Review"
```
