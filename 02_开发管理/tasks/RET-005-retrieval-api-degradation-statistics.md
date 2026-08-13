# RET-005 Retrieval API、降级/超时、统计更新

## 1. 任务信息

```yaml
task_id: RET-005
task_name: Retrieval API、降级/超时、统计更新
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "c086b9953829d0ca19e930cde9b1c64dadde5fb9"
branch: "feat/RET-005-retrieval-api-degradation-statistics"
created_at: "2026-08-13 07:00 UTC"
updated_at: "2026-08-13 07:48 UTC"
spec_sections:
  - "§2.2.5 Memory Retrieval API（HTTP Request 校验与字段）"
  - "§2.2.12 Evidence + Response DTO（score=final_score；retrieval_source；evidence_count；source_message_ids）"
  - "§2.2.13 召回统计更新（Neo4j retrieval_count + last_retrieved_time）"
  - "§2.2.14 MVP 配置（timeouts、default_top_k、max_top_k）"
  - "§2.2.15 失败处理与降级策略（致命码、Warning、降级规则 1-8）"
  - "§3.21 Memory API 鉴权（X-API-Key；Memory 或 Admin Key）"
  - "§3.23 统一 API 响应与 Request ID（400/401/503 映射）"
prerequisites:
  formal:
    - "RET-001 — SATISFIED/completed; Bm25RetrievalService + ES read path（PR #44 MERGED）"
    - "RET-002 — SATISFIED/completed; HybridRetrievalService + fuse_rrf 纯函数（PR #45 MERGED）"
    - "RET-003 — SATISFIED/completed; AuthoritativeRecallService + InternalRetrievalWarning（PR #46 MERGED）"
    - "RET-004 — SATISFIED/completed; RetrievalScoringService + ScoredRetrievalMemory（PR #47 MERGED）"
    - "DEV-005 — SATISFIED/completed; FastAPI shell、require_memory_api_key、AppError/§3.23 错误包络"
  implementation_reuse:
    - "Bm25RetrievalService / VectorRetrievalService / fuse_rrf（RET-001/002；编排层直接调用，**不**修改服务语义）"
    - "HybridRetrievalService（**禁止**修改；RET-005 自建 HTTP 编排，不复用其 search 以保留 tokenize 门控与 embedding/vector Warning 区分）"
    - "AuthoritativeRecallService.recall -> AuthoritativeRecallOutcome（RET-003）"
    - "RetrievalScoringService.score -> RetrievalScoringOutcome（RET-004）"
    - "normalize_retrieval_query（RET-002）"
    - "TeiTokenizeClient.count_tokens（EXT-006 基础设施；HTTP 层 tokenize gate）"
    - "require_memory_api_key / AppError / build_error_response（DEV-005）"
    - "memory_extraction_admin.py 路由模式（app.state.app_state 注入）"
  baseline_evidence:
    branch: "main"
    head: "c086b9953829d0ca19e930cde9b1c64dadde5fb9"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=c086b9953829d0ca19e930cde9b1c64dadde5fb9"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "PLAN_APPROVED — human confirmed 2026-08-13"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: false
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create the exact feature branch feat/RET-005-retrieval-api-degradation-statistics"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_write_scope: "Neo4j Memory.retrieval_count + Memory.last_retrieved_time ONLY（§2.2.13）"
```

### 1.1 本轮门禁与停止条件

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现、测试实现、Migration、配置或依赖"
  - "进入 Developer、Code Reviewer、Commit Recorder 或 Release Operator"
  - "执行任何 Git 写命令"
  - "修改权威规格正文"
  - "触碰 DEV-006 / PR #13"
  - "修改 RET-001..004 生产服务语义"
stop_if:
  - "任何实现步骤需要修改 fuse_rrf / HybridRetrievalService / AuthoritativeRecallService / RetrievalScoringService 生产语义"
  - "任何实现步骤需要 ES/Mongo/Kafka/extraction durable 写入"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要 RET-006 E2E、cache、reranking、pagination、streaming"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-008
```

## 2. authoritative_scope

本任务 **唯一** 拥有 §2.2.5 HTTP Retrieval API、§2.2.12 Response DTO 组装、§2.2.13 `retrieval_count`/`last_retrieved_time` Neo4j 批量更新、§2.2.15 内部 Outcome → HTTP 致命码/Warning 映射、总超时 `retrieval_total_timeout_seconds` 编排与 `retrieval_timeout`/`retrieval_timeout_degraded` 分支；**不** 拥有 BM25/Vector/RRF/Neo4j 权威回读/图扩展/ACT-R/Evidence 加载内部算法。

| 维度 | 归属 RET-005 | 非 RET-005（显式排除） |
|---|---|---|
| `POST /api/v1/memory/retrieval` HTTP 路由 + Request/Response Pydantic Schema | **是** — §3 | — |
| Request 校验（user_id/query/top_k/memory_types/字符长度） | **是** — §3.1 | — |
| TEI `/tokenize` HTTP 层门控（>1024 Token → synthetic `skipped_query_too_long` + `fuse_rrf`） | **是** — §5.2、§17 LD-1 | 修改 RET-002 `HybridRetrievalService` |
| HTTP 编排：normalize → hybrid recall → authoritative → scoring → stats → response | **是** — §4 | 修改 RET-001..004 Service 内部语义 |
| `ScoredRetrievalMemory` → HTTP `memories[]` 字段映射（`score`←`final_score`） | **是** — §6 | RET-004 内部模型 |
| 内部 Warning/Failure → HTTP `warnings` 字符串 + 致命 `AppError` | **是** — §7、§10 | RET-003/004 内部 kind 定义 |
| `retrieval_total_timeout_seconds` 包裹全请求；单阶段超时消费 settings | **是** — §8 | Settings Contract 变更 |
| Neo4j 批量更新 `retrieval_count` + `last_retrieved_time`（Top-K only） | **是** — §9 | RET-004 只读 Evidence |
| `require_memory_api_key`（Memory 或 Admin Key） | **是** — §3.1 | — |
| BM25 / Vector / RRF 融合算法 | **否** — 调用 RET-001/002 | **RET-001/002** |
| Neo4j 权威回读 / 图扩展 / MGET | **否** — 调用 RET-003 | **RET-003** |
| ACT-R 评分 / Evidence 批量读与聚合 | **否** — 调用 RET-004 | **RET-004** |
| Session→Retrieval 全链路 E2E / 失败注入 compose | **否** | **RET-006** |
| Cache / reranking / pagination / streaming | **否** | **DEFERRED** |
| ES/Mongo/Kafka/extraction 写入 | **否** | **HARD_BLOCK** |

## 3. request_contract

### 3.1 HTTP 路由与鉴权

| 属性 | 值 |
|---|---|
| Method | `POST` |
| Path | `/api/v1/memory/retrieval` |
| Auth | `require_memory_api_key` — **Memory Key 或 Admin Key**（§3.21）；缺失/无效 → `401 invalid_api_key` |
| `user_id` 来源 | Request Body `user_id`（非 Path）；上游 Agent 负责传入；API 强制用于全链路过滤 |

### 3.2 Request Body（§2.2.5 — strict, extra=forbid）

```json
{
  "user_id": "user_001",
  "query": "用户之前设计的 Agent 记忆系统使用了哪些技术",
  "memory_types": ["fact", "event"],
  "top_k": 10,
  "include_conflicted": false,
  "include_history": false,
  "graph_expand": true
}
```

| 字段 | 类型 | 必填 | 默认 | 校验 | 失败码 |
|---|---|---|---|---|---|
| `user_id` | `str` | **是** | — | `strip()` 后非空；`^\S+$` 模式（与现有 memory routes 一致） | `invalid_request` |
| `query` | `str` | **是** | — | 原始非空；经 `normalize_retrieval_query` 后非空 | `invalid_request`（空）/ `query_too_long`（>2000 字符） |
| `memory_types` | `list[str] \| null` | 否 | `null` | 去重（稳定顺序）；元素 ∈ `{fact, preference, event, profile}`；去重后空数组 → 视为 `null`（不限制类型） | `invalid_memory_type` |
| `top_k` | `int` | 否 | `settings.memory_retrieval.default_top_k`（**10**） | `1 <= top_k <= settings.memory_retrieval.max_top_k`（**20**）；**禁止**静默截断 | `invalid_top_k` |
| `include_conflicted` | `bool` | 否 | `false` | — | — |
| `include_history` | `bool` | 否 | `false` | — | — |
| `graph_expand` | `bool` | 否 | `true` | — | — |

### 3.3 校验顺序（HARD_BLOCK — 必须按序短路）

1. Pydantic Schema（类型/extra）→ `422 validation_error`（§3.23）。
2. API Key（dependency）→ `401 invalid_api_key`。
3. `user_id` 非空。
4. `query` 原始非空 → `normalize_retrieval_query`。
5. 标准化后 `1 <= len(normalized_query) <= 2000`；否则 `query_too_long`（**>2000**）或 `invalid_request`（**0**）。
6. `memory_types` 去重与枚举校验。
7. `top_k` 范围校验（默认已填充）。
8. 进入编排（§4）；**不在** Route 层调用 BM25/Neo4j。

### 3.4 Query Hash（日志）

- 对 **标准化后** query 计算 SHA-256 hex（不含原始 query 明文入日志）。
- 错误日志必须含：`user_id`、query_hash、失败阶段、错误码（§2.2.15 DR-10）；**禁止**记录 Query Embedding。

## 4. orchestration_contract

### 4.1 编排 Owner

新建 **`RetrievalApiService`**（`domain/services/retrieval_api_service.py`）为 HTTP 与全链路编排唯一 Owner；Route 层仅做 Schema 校验 + `AppError` 映射。

```text
async retrieve(input: RetrievalApiInput, *, deadline: float) -> RetrievalApiResult
```

**禁止**修改 `HybridRetrievalService`、`AuthoritativeRecallService`、`RetrievalScoringService` 生产语义；允许通过 factory 注入其 **实例** 或同级底层 port（BM25/Vector/Embedding）。

### 4.2 全链路顺序（§2.2.16 + §11）

```text
Receive HTTP Request
  → validate (§3)
  → normalize query
  → tokenize gate (§5.2)
  → parallel BM25 + Vector path (§5.3)
  → fuse_rrf (§5.4)
  → AuthoritativeRecallService.recall (RET-003)
  → RetrievalScoringService.score (RET-004)
  → build HTTP Response DTO (§6)          ← "response complete" 里程碑
  → Neo4j retrieval statistics update (§9) ← 仅 Top-K；失败 → warning
  → return 200 + warnings
```

**里程碑定义**（超时分支 §8.3）：

- **Response complete**：`RetrievalScoringOutcome.outcome=success` 且 HTTP `memories[]` DTO 已组装（含 `evidence_count`/`source_message_ids`）。
- **Stats pending**：Response complete 之后、Neo4j stats write 之前。

### 4.3 阶段输入/输出契约

| 阶段 | 输入 | 输出 | 上游 Failure 处理 |
|---|---|---|---|
| Hybrid recall | `HybridRetrievalQuery` 字段 + normalized query | `HybridRetrievalOutcome` | `failure.retrieval_unavailable` → HTTP 503（§10） |
| Authoritative | `AuthoritativeRecallQuery{hybrid_success, filters, graph_expand}` | `AuthoritativeRecallOutcome` | `neo4j_read_failure` → HTTP 503 `graph_load_failed` |
| Scoring | `RetrievalScoringQuery{authoritative_success, top_k, current_time}` | `RetrievalScoringOutcome` | `neo4j_read_failure` → `graph_load_failed`；`graph_load_failed` → 同左 |
| Stats | `user_id` + Top-K `memory_id[]` deduped | `void` / 异常 | 捕获 → `retrieval_stat_update_failed` warning；**不影响** 200 响应 |

### 4.4 与 RET-001..004 边界

| 组件 | RET-005 用法 | 禁止 |
|---|---|---|
| `Bm25RetrievalService.search` | 直接调用 | 修改 BM25 repo/service |
| `VectorRetrievalService.search` | Embedding 成功后调用 | 修改 Vector repo/service |
| `fuse_rrf` | 纯函数；含 synthetic vector skipped | 修改 `rrf_fusion.py` |
| `HybridRetrievalService.search` | **不调用**（避免无法区分 embedding vs vector failure；无法插入 tokenize gate） | 修改其 `_embed_and_vector_search` |
| `AuthoritativeRecallService.recall` | 接受 `HybridRetrievalSuccess` | 修改 recall 语义 |
| `RetrievalScoringService.score` | 仅接受 `AuthoritativeRecallSuccess` | 修改 scoring 语义 |

### 4.5 Factory 接线

```text
create_retrieval_api_service(
  settings,
  bm25_service,
  vector_service,
  embedding_client,
  tokenize_client,          # TeiTokenizeClient
  authoritative_service,
  scoring_service,
  statistics_repository,    # 新建 write repo
) -> RetrievalApiService
```

HTTP Route 从 `request.app.state.app_state` 取 `elasticsearch`/`neo4j`/`http_client`/`settings`，在 lifespan 或 route 级 lazy factory 组装（与 extraction admin 模式一致）；**禁止**在 `AppState` dataclass 中持久化 Retrieval 专用可变状态（MVP 每次请求新建 service 或使用无状态 factory）。

## 5. hybrid_recall_sub_contract（HTTP 层 — 不修改 RET-002 Service）

### 5.1 BM25 + Vector 并行

与 RET-002 相同：`asyncio.gather(bm25_task, vector_task)`；BM25 **不**等待 Embedding。

### 5.2 Tokenize Gate（§2.2.5 #3 — RET-005 Owner）

在 Vector 路径 **之前**（Embedding **之前**）：

```text
token_count = await tokenize_client.count_tokens(normalized_query)
```

| 条件 | 动作 |
|---|---|
| `1 <= token_count <= 1024` | 正常调用 `embedding_client.embed` → `VectorRetrievalService.search` |
| `token_count > 1024` | **不**调用 `/v1/embeddings`；构造 synthetic `VectorRetrievalOutcome(outcome=failure, failure=VectorRetrievalFailure(kind=skipped_query_too_long, retryable=false))`；BM25 并行继续 |
| `token_count == 0` | 不应发生（query 已校验非空）；防御 → `invalid_request` |
| `TokenizeServiceError` | MVP_LOCAL_DECISION LD-2：视为 Vector 通道 `channel_failure`（retryable 按 transport）；映射 Warning `embedding_failed`；BM25 继续 |

**关键**：synthetic skipped outcome 传入 `fuse_rrf`；`fuse_rrf` 已将 `skipped_query_too_long` 视为无效通道（RET-002 `_is_channel_failure`），与规格一致。

### 5.3 Embedding 路径 Warning 区分

| 阶段失败 | `VectorRetrievalFailure.kind` | HTTP Warning |
|---|---|---|
| `EmbeddingServiceError` / embed 校验失败 | `channel_failure` | `embedding_failed` |
| `token_count > 1024` | `skipped_query_too_long` | `vector_skipped_query_too_long` |
| `VectorRetrievalService` ES 失败 | `channel_failure` | `vector_retrieval_failed` |

### 5.4 fuse_rrf 调用

```python
fuse_rrf(
    bm25_outcome,
    vector_outcome,
    rrf_k=settings.memory_retrieval.rrf_k,
    fused_top_n=settings.memory_retrieval.fused_top_n,
    user_id=user_id,
)
```

| `HybridRetrievalOutcome` | 后续 |
|---|---|
| `success` | → `AuthoritativeRecallService.recall` |
| `failure.retrieval_unavailable` | → HTTP 503 `retrieval_unavailable`（两通道均 failure/skipped） |

## 6. response_contract

### 6.1 成功 HTTP 200 Body（§2.2.5 / §2.2.12 — strict）

```json
{
  "retrieval_mode": "hybrid",
  "warnings": [],
  "memories": []
}
```

| 字段 | 类型 | 来源 |
|---|---|---|
| `retrieval_mode` | `"hybrid" \| "bm25_only" \| "vector_only" \| "none"` | `RetrievalScoringSuccess.retrieval_mode` |
| `warnings` | `list[str]` | §7 映射 + 去重排序 |
| `memories` | `list[RetrievalMemoryItem]` | `RetrievalScoringSuccess.scored_memories` 映射 |

### 6.2 `RetrievalMemoryItem` 字段映射（`ScoredRetrievalMemory` → HTTP）

| HTTP 字段 | 来源 | 规则 |
|---|---|---|
| `memory_id` | `memory_id` | 直传 |
| `memory_type` | `memory_type` | 直传 |
| `content` | `content` | 直传 |
| `subject` | `subject_entity` | `{entity_id, name: canonical_name}`；`subject_entity is None` → **不得**出现在 Top-K（RET-003 保证；防御性跳过或 503 — 实现选 fail-closed `graph_load_failed`） |
| `predicate` | `predicate` | 直传 |
| `object` | `object_entity` / `object_value` | 见 §6.3 |
| `status` | `status` | 直传 |
| `event_status` | `event_status` | 直传 |
| `start_time` | `start_time` | 直传 |
| `end_time` | `end_time` | 直传 |
| `confidence` | `confidence` | 直传 |
| `importance` | `importance` | 直传 |
| `latest_source_time` | `latest_source_time` | 直传 |
| `score` | `final_score` | **6 位小数**（已由 RET-004 round） |
| `retrieval_source` | `retrieval_source` | `list["bm25","vector","graph"]` |
| `source_message_ids` | `source_message_ids` | 直传（已截断至 `max_source_message_ids`） |
| `evidence_count` | `evidence_count` | 直传 |

**禁止**在 Response 中暴露：`act_r_components`、`bm25_rank`、`vector_rank`、`rrf_score`、`candidate_origin` 等内部字段。

### 6.3 `object` 子对象规则（§2.2.12）

| 条件 | HTTP `object` |
|---|---|
| `object_entity is not None` | `{ "entity_id": ..., "name": canonical_name, "value": null }` |
| `object_entity is None` 且 `object_value is not None` | `{ "entity_id": null, "name": null, "value": object_value }` |
| 两者均为 None | `{ "entity_id": null, "name": null, "value": null }` |

纯函数：`map_scored_memory_to_response_item(scored: ScoredRetrievalMemory) -> RetrievalMemoryItem`（`domain/services/retrieval_response_mapper.py`）。

### 6.4 空结果（§2.2.12）

`retrieval_mode="none"`（或 `bm25_only`/`vector_only` 但无候选）且 `memories=[]` → HTTP **200**；失败通道 Warning 仍写入 `warnings`。

## 7. degradation_contract

### 7.1 致命错误 → HTTP（非 200）

见 §10 `http_failure_mapping`。致命错误 **不** 出现在 `warnings` 数组。

### 7.2 内部 Outcome → HTTP Warning 字符串

| 内部来源 | 条件 | HTTP Warning |
|---|---|---|
| Vector `channel_failure`（Embedding 阶段） | `_embed` 异常或维度校验失败 | `embedding_failed` |
| Vector `skipped_query_too_long` | tokenize > 1024 | `vector_skipped_query_too_long` |
| Bm25 `channel_failure` | `Bm25RetrievalOutcome.outcome=failure` | `bm25_retrieval_failed` |
| Vector `channel_failure`（Vector search 阶段） | ES kNN 失败 | `vector_retrieval_failed` |
| `InternalRetrievalWarning.kind=dirty_index_document` | RET-003 | `dirty_index_document` |
| `InternalRetrievalWarning.kind=stale_index_document` | RET-003 | `stale_index_document` |
| `InternalRetrievalWarning.kind=graph_expansion_failed` | RET-003 | `graph_expansion_failed` |
| Stats write 失败 | §9 | `retrieval_stat_update_failed` |
| 总超时且 Response complete | §8.3 | `retrieval_timeout_degraded` |

**注意**：同一请求 **不会** 同时出现 `embedding_failed` 与 `vector_retrieval_failed`（互斥阶段）；`vector_skipped_query_too_long` 与 `embedding_failed` 互斥。

### 7.3 Warning 收集来源

1. Hybrid recall 阶段：BM25/Vector channel outcomes（§7.2 前 4 行）。
2. Authoritative + Scoring 阶段：透传 `InternalRetrievalWarning`（RET-003 → RET-004 透传 → HTTP）。
3. Stats 阶段：`retrieval_stat_update_failed`。
4. 超时降级：`retrieval_timeout_degraded`。

### 7.4 Warning 排序与去重（MVP_LOCAL_DECISION LD-3）

**排序**（稳定优先级 — 出现顺序按此排列；同类多条 `dirty`/`stale` 按 `memory_id` ASC 追加）：

```text
1. embedding_failed
2. vector_skipped_query_too_long
3. bm25_retrieval_failed
4. vector_retrieval_failed
5. graph_expansion_failed
6. dirty_index_document
7. stale_index_document
8. retrieval_stat_update_failed
9. retrieval_timeout_degraded
```

**去重**：

- 通道级 Warning（1–5、8–9）：每种 kind **至多一条**。
- `dirty_index_document` / `stale_index_document`：按 `(kind, memory_id)` 去重；HTTP 字符串仍为 kind 字面量（**不**附带 memory_id；与规格示例一致）。

纯函数：`collect_and_order_warnings(...) -> list[str]`（`domain/services/retrieval_warning_mapper.py`）。

### 7.5 降级规则对照（§2.2.15 DR-1..DR-9 — 语义不变）

| DR# | 规则 | RET-005 落点 |
|---|---|---|
| DR-1 | 双通道有效非空 → `hybrid` | `fuse_rrf` + 下游透传 |
| DR-2 | 仅 BM25 有效非空 → `bm25_only` | 同左 |
| DR-3 | 仅 Vector 有效非空 → `vector_only` | 同左 |
| DR-4 | 均成功但空 → `none` + `[]` | 同左；通道 failure warnings 仍返回 |
| DR-5 | 双通道 failure → `retrieval_unavailable` | HTTP 503 |
| DR-6 | Neo4j/Evidence 权威加载失败 → `graph_load_failed` | HTTP 503；禁止 ES 回填 |
| DR-7 | 图扩展失败 → 仅直接候选 | Warning `graph_expansion_failed` |
| DR-8 | 脏/过期索引逐条跳过 | Warnings `dirty_*` / `stale_*` |
| DR-9 | 单阶段超时按失败；总超时见 §8 | `retrieval_timeout` / `retrieval_timeout_degraded` |

## 8. timeout_contract

### 8.1 配置来源（§2.2.14 — 只读，禁止改 Contract）

| 配置项 | 默认 | 用途 |
|---|---|---|
| `embedding_timeout_seconds` | 10 | Embedding HTTP 调用（`asyncio.wait_for` 包裹 embed） |
| `elasticsearch_timeout_seconds` | 5 | BM25/Vector ES 调用（repo 层已有 settings；编排层额外守卫可选） |
| `neo4j_timeout_seconds` | 5 | Authoritative / Evidence / Stats Neo4j |
| `retrieval_total_timeout_seconds` | 15 | **整请求**上限 |

单阶段超时 **不得**大于总超时（Settings 启动已校验）。

### 8.2 总超时包裹

```text
deadline = loop.time() + settings.memory_retrieval.retrieval_total_timeout_seconds
```

`RetrievalApiService.retrieve(..., deadline=...)` **必须**将总超时拆为两阶段作用域（与 §8.3 一致）：

1. **Pre-response phase**（normalize → tokenize → hybrid → authoritative → scoring → DTO 组装）：每个 `await` 前检查 `loop.time() < deadline`；耗尽则取消 in-flight 子任务 → **503** `retrieval_timeout`；**不**调用 stats。
2. **Post-response phase**（stats update only）：仅在 Response complete 里程碑之后执行；此阶段耗尽 → **跳过** stats → **200** + `retrieval_timeout_degraded`；**禁止**返回 `retrieval_timeout` 致命错误。

**禁止**用单一顶层 `asyncio.wait_for(retrieve_entire_request_including_stats)` 包裹 stats 阶段（会导致 DTO-complete 后误报 `retrieval_timeout`）。

### 8.3 总超时分支（§2.2.15 DR-9）

| 状态 | 动作 |
|---|---|
| 超时且 **未** Response complete（含 Evidence 未加载完） | 终止；HTTP **503** `retrieval_timeout` |
| Response complete 后、stats 前/中超时 | 跳过 stats；HTTP **200**；`warnings` += `retrieval_timeout_degraded` |
| Response complete 后、stats 已成功 | 正常 200 |

### 8.4 单阶段超时

| 阶段 | 超时配置 | 失败语义 |
|---|---|---|
| Embedding | `embedding_timeout_seconds` | Vector `channel_failure` → `embedding_failed` |
| ES BM25/Vector | `elasticsearch_timeout_seconds` | 对应通道 `channel_failure` |
| Neo4j read（authoritative/evidence） | `neo4j_timeout_seconds` | `neo4j_read_failure` / `graph_load_failed` |
| Neo4j stats write | 剩余总超时内 best-effort；失败 → warning | `retrieval_stat_update_failed` |

### 8.5 取消语义

- 总超时触发时 **取消** 仍在进行的子任务（`asyncio.Task.cancel()`）；已完成的阶段结果若未到 Response complete 则丢弃。
- 不向客户端返回部分 `memories[]`（§2.2.15 DR-9：禁止未完成 Evidence 聚合时返回伪造空来源）。

## 9. statistics_update_contract

### 9.1 范围（§2.2.13 — HARD_BLOCK）

| 规则 | 要求 |
|---|---|
| 更新对象 | **仅**最终 HTTP Response `memories[]` 中的 Top-K |
| 去重 | 单次请求内 `memory_id` 去重；每条最多 `+1` |
| 用户隔离 | Cypher `WHERE m.user_id = $user_id AND m.memory_id IN $memory_ids` |
| 字段 | **仅** `retrieval_count`、`last_retrieved_time` |
| 单调性 | `last_retrieved_time` 使用规格 CASE 表达式；`current_time` = 请求内注入 Unix 秒 |
| 失败影响 | **不影响** 200 响应；`warnings` += `retrieval_stat_update_failed`；记录错误日志 |
| 超时 | Response complete 后若总超时 → 跳过更新 + `retrieval_timeout_degraded`（§8.3） |

### 9.2 Cypher（§2.2.13 — 精确）

```cypher
UNWIND $memory_ids AS memory_id
MATCH (m:Memory {memory_id: memory_id, user_id: $user_id})
SET m.retrieval_count = coalesce(m.retrieval_count, 0) + 1,
    m.last_retrieved_time =
        CASE
            WHEN m.last_retrieved_time IS NULL
              OR m.last_retrieved_time < $current_time
            THEN $current_time
            ELSE m.last_retrieved_time
        END
```

### 9.3 仓储

- 新建 **`RetrievalStatisticsRepository`**（`infrastructure/neo4j/retrieval_statistics_repository.py`）。
- `async def increment_retrieval_stats(*, user_id, memory_ids: list[str], current_time: int) -> None`
- `neo4j_timeout_seconds` 来自 settings；`authorized_write_cypher_queries()` 供契约测试。
- **禁止**写入 ES/Mongo/Kafka；**禁止**更新 Evidence 或除上述两字段外的 Memory 属性。

### 9.4 空 Top-K

`memories=[]` → **不**调用 stats write；无 `retrieval_stat_update_failed`。

## 10. durable_write_scope

```yaml
durable_write_scope:
  neo4j:
    - "Memory.retrieval_count"
    - "Memory.last_retrieved_time"
  forbidden:
    - "Elasticsearch"
    - "MongoDB"
    - "Kafka"
    - "extraction pipeline"
    - "Evidence nodes"
    - "Memory 除 §9 外任何字段"
```

## 11. statistics ordering（规范复述）

检索管线 **严格**顺序：

```text
retrieve (BM25 + Vector + fuse_rrf)
  → rank (RRF sort — RET-002)
  → authoritative load + optional graph expand (RET-003)
  → ACT-R score + final order + top_k truncate (RET-004)
  → evidence load for Top-K only (RET-004)
  → build HTTP response (RET-005)
  → stats update for Top-K only (RET-005)
  → return response
```

**禁止**在 Top-K 确定前更新 `retrieval_count`；**禁止**对未返回候选做 stats 写入。

## 12. replay / idempotency

| 维度 | 行为 |
|---|---|
| HTTP 语义 | **非**只读 API；成功 200 可改变 Neo4j `retrieval_count` |
| 客户端重试 | 同 query 重复 POST 可能多次 `+1`（§2.2.13 #6 — **接受**） |
| 超时重试 | 若上次已 stats 更新但客户端未收到响应，重试再次 `+1` — MVP 接受 |
| 幂等键 | **不**实现 request idempotency 表（规格明确首版不做） |
| 读路径 | BM25/Vector/Neo4j 读无写入副作用（除 §9） |
| `retrieval_count` 用途 | 弱排序信号；非计费/强一致数据 |

## 13. user_isolation checklist（Code Review）

| # | 规则 | Enforcement | 测试 ID |
|---|---|---|---|
| UISO-1 | Request `user_id` 传入全部 BM25/Vector/Authoritative/Scoring/Stats | Service 入参绑定 | U1, I4 |
| UISO-2 | BM25/Vector ES filter 含 `user_id` | RET-001/002 regression（U19） | U19, I4 |
| UISO-3 | Neo4j 读/写 Cypher 含 `m.user_id = $user_id` | grep + `authorized_write_cypher_queries` | C4, `test_retrieval_statistics_repository` |
| UISO-4 | Stats 写仅更新请求用户 Memory | `RetrievalStatisticsRepository` | U11, I3 |
| UISO-5 | 交叉用户 Memory 不得出现在 `memories[]` | Integration fixture A/B | I4 |
| UISO-6 | 日志禁止 Memory `content` 全文与 query 明文 | Code review + grep | — |
| UISO-7 | 单次请求单 `user_id`；无批量跨用户 API | Route 契约 | C1, C2 |

## 14. http_failure_mapping

| 场景 | HTTP | `error.code` | 备注 |
|---|---|---|---|
| 缺失/无效 API Key | 401 | `invalid_api_key` | §3.21；不区分缺失/错误 |
| Pydantic Request 校验失败 | 422 | `validation_error` | §3.23 |
| `user_id`/`query` 空（业务层） | 400 | `invalid_request` | |
| `memory_types` 含非法值 | 400 | `invalid_memory_type` | |
| `top_k` 越界 | 400 | `invalid_top_k` | 禁止静默截断 |
| 标准化 query 长度 > 2000 | 400 | `query_too_long` | |
| BM25 + Vector 双通道不可用 | 503 | `retrieval_unavailable` | `fuse_rrf` failure |
| Neo4j 权威读失败 / Evidence 加载失败 | 503 | `graph_load_failed` | `neo4j_read_failure` / `graph_load_failed` |
| 总超时且 Response 未 complete | 503 | `retrieval_timeout` | §8.3 |
| 未预期基础设施异常 | 503 | `internal_error` | 脱敏 message |

**授权业务致命码**（RET-005）：`invalid_request`、`invalid_memory_type`、`invalid_top_k`、`query_too_long`、`retrieval_unavailable`、`graph_load_failed`、`retrieval_timeout`（加 DEV-005 横切码）。

**成功 200**：含 warnings 的降级响应、空 `memories`、含 `conflicted`/`superseded`（当 filter 允许）。

## 15. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/api/schemas/memory_retrieval.py` | 创建 | Request/Response Pydantic（§3、§6） |
| `src/memory_system/api/routes/memory_retrieval.py` | 创建 | POST 路由 + AppError 映射 |
| `src/memory_system/api/app.py` | 修改 | 注册 `memory_retrieval.router` |
| `src/memory_system/domain/services/retrieval_api_service.py` | 创建 | 全链路编排（§4） |
| `src/memory_system/domain/services/retrieval_response_mapper.py` | 创建 | `ScoredRetrievalMemory` → HTTP DTO 纯函数 |
| `src/memory_system/domain/services/retrieval_warning_mapper.py` | 创建 | Warning 收集/排序/去重（§7） |
| `src/memory_system/infrastructure/neo4j/retrieval_statistics_repository.py` | 创建 | §2.2.13 Neo4j 批量写 |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `hybrid_retrieval_service.py`、`rrf_fusion.py`、`authoritative_recall_service.py`、`retrieval_scoring_service.py`、`settings/`、DEV-006）。

### 15.1 governance_file_whitelist（Release Operator 各 phase）

| Phase | 允许路径 | 目的 |
|---|---|---|
| `PLAN_LANDING` | `02_开发管理/tasks/RET-005-retrieval-api-degradation-statistics.md` | 已批准 Task Plan |
| `PLAN_LANDING` | `02_开发管理/progress.md` | 规划态登记 |
| `PLAN_LANDING` | `02_开发管理/master_plan.md` | RET-005 规划登记 |
| `IMPLEMENTATION_RELEASE` | §15 production_file_whitelist 全部 | 实现 |
| `IMPLEMENTATION_RELEASE` | §16 test_file_whitelist 全部 | 测试 |
| `IMPLEMENTATION_RELEASE` | 上述治理文件 status 记录 | 执行记录 |
| `POST_MERGE_CLEANUP` | `02_开发管理/open_issues.md` | OI-008 `status: resolved` + `resolved_by_task: RET-005` |
| `POST_MERGE_CLEANUP` | 治理文件完成登记 | `docs(status): complete` |

## 16. test_file_whitelist + test_plan

### 16.1 test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_retrieval_warning_mapper.py` | 创建 | Warning 映射/排序/去重 |
| `tests/unit/test_retrieval_response_mapper.py` | 创建 | Entity/object 映射 |
| `tests/unit/test_retrieval_api_service.py` | 创建 | 编排、超时、tokenize gate、failure |
| `tests/unit/test_retrieval_statistics_repository.py` | 创建 | Cypher 授权 + 解析（mock driver） |
| `tests/contract/test_ret005_retrieval_api_contract.py` | 创建 | 路由/错误码/响应形状/白名单 |
| `tests/integration/test_ret005_retrieval_http.py` | 创建 | TestClient + Fake ports：happy/degraded/fatal |
| `tests/integration/test_ret005_retrieval_statistics_neo4j.py` | 创建 | Neo4j Fixture stats 写入 + 单调性 |
| `tests/support/ret005_neo4j_fixtures.py` | 创建 | Memory stats 初始状态 Fixture |

**白名单外任何 `tests/**` 变更 → FAIL**（RET-001..004 测试文件不得修改语义；运行回归但不在白名单内编辑）。

### 16.2 Unit Test

| ID | 场景 | 预期 |
|---|---|---|
| U1 | 合法 Request 全字段 | 编排 happy path（mock 全层） |
| U2 | `top_k` 默认 10 / 越界 0、21 | 默认填充；越界 → `invalid_top_k` |
| U3 | `memory_types` 去重 + 非法值 | 去重；非法 → `invalid_memory_type` |
| U4 | query 标准化后 2001 字符 | `query_too_long` |
| U5 | tokenize > 1024 | synthetic skipped + `vector_skipped_query_too_long`；不调用 embed |
| U6 | tokenize 1..1024 | 正常 embed 路径 |
| U7 | Embedding 失败 | `embedding_failed`；BM25 继续 |
| U8 | BM25 failure only | `bm25_retrieval_failed`；vector_only 或 none |
| U9 | Vector search failure only | `vector_retrieval_failed` |
| U10 | 双通道 failure | `retrieval_unavailable` |
| U11 | stats 写失败 | 200 + `retrieval_stat_update_failed` |
| U12 | Response complete 后总超时 | 200 + `retrieval_timeout_degraded`；stats 未调用 |
| U13 | Evidence 前总超时 | `retrieval_timeout` 503 |
| U14 | `neo4j_read_failure` | 503 `graph_load_failed` |
| U15 | `graph_load_failed`（Evidence） | 503 `graph_load_failed` |
| U16 | Warning 排序/去重 | §7.4 顺序；通道 kind 唯一 |
| U17 | 空 Top-K | 不调用 stats repo |
| U18 | `memory_ids` stats 去重 | 10 条含重复 ID 仅 +1 一次（mock 断言） |
| U19 | RET-001..004 回归 | 既有测试全通过（不修改语义） |

### 16.3 Contract Test

| ID | 场景 | 预期 |
|---|---|---|
| C1 | 路由 `POST /api/v1/memory/retrieval` | 路径精确 |
| C2 | Memory/Admin Key 200；无 Key 401 | §3.21 |
| C3 | 授权 HTTP 致命码白名单 | §14 表 |
| C4 | Stats Cypher 含 `user_id` | `authorized_write_cypher_queries` |
| C5 | 零 RET-001..004 生产语义 diff | git diff 白名单 |
| C6 | Response `extra=forbid` | 无内部字段泄漏 |
| C7 | `score` 字段存在；无 `final_score` | §6.2 |

### 16.4 Integration Test

| ID | 场景 | 预期 |
|---|---|---|
| I1 | TestClient happy path（fake 全链路） | 200 + memories 形状 |
| I2 | embedding_failed 降级 | 200 + warning + bm25_only/hybrid |
| I3 | Neo4j stats 写入 | `retrieval_count+1`；`last_retrieved_time` 单调 |
| I4 | 用户 B Memory 不可见于用户 A | `memories` 不含 B |
| I5 | 双通道 failure | 503 `retrieval_unavailable` |
| I6 | `query_too_long` | 400 |
| I7 | stats 失败注入 | 200 + `retrieval_stat_update_failed` |

### 16.5 E2E Test

| 场景 | 预期 |
|---|---|
| 全链路 compose Session→Retrieval | **DEFERRED** — RET-006 |

### 16.6 失败注入与并发

**文件归属**：F1–F3 均在 `tests/unit/test_retrieval_api_service.py`（mock 编排层；不扩展 production 白名单）。

| ID | 文件 | 场景 | 预期 |
|---|---|---|---|
| F1 | `test_retrieval_api_service.py` | 并发 10 路相同 POST（mock stats repo） | 无异常；stats 调用次数与去重后 Top-K 一致 |
| F2 | `test_retrieval_api_service.py` | 总超时 15s 注入慢 Evidence（pre-response） | 503 `retrieval_timeout`；stats 未调用 |
| F3 | `test_retrieval_api_service.py` | DTO complete 后慢 stats + 紧 deadline | 200 `retrieval_timeout_degraded`；stats 跳过或取消 |

## 17. OI-008 disposition

| 字段 | 值 |
|---|---|
| owner | RET-005 |
| issue | §2.2.15 降级规则列表编号笔误（两个「5.」及跳过「9.」） |
| resolution | 在 Task Plan 与 `open_issues.md` 登记 **canonical DR 映射**；**不**修改规格正文语义 |
| canonical_mapping | 见 §7.5 表 DR-1..DR-10 |
| spec_original → canonical | 原「1.」→DR-1 … 原「4.」→DR-4；原第一个「5.」→DR-5（`retrieval_unavailable`）；原第二个「5.」→DR-6（`graph_load_failed`）；原「6.」→DR-7；原「7.」→DR-8；原「8.」→DR-9（超时）；原「10.」→DR-10（日志） |
| status | `resolved_by_task`（RET-005 PR #48 MERGED） |
| blocks_implementation | **否** |

## 18. deferred_for_mvp

| 项 | 说明 |
|---|---|
| Session→Retrieval 全链路 E2E + compose 失败注入 | RET-006 |
| 请求幂等表 / `retrieval_count` 去重 | §2.2.13 #6 明确不做 |
| Cache / reranking / pagination / streaming | 规格未要求 |
| 修改 `HybridRetrievalService` 内置 tokenize | RET-005 HTTP 编排解决（LD-1） |
| ES/Mongo/Kafka/extraction 写入 | 本任务禁止 |
| DEV-006 / PR #13 | 永久禁止 |
| 新依赖 / Migration / Settings Contract | `dependency_changes_expected=NONE` |

## 19. mvp_local_decisions

| ID | 决策 | 理由 | 分类 |
|---|---|---|---|
| LD-1 | HTTP 编排层调用 `TeiTokenizeClient` + 直接调用 BM25/Vector/`fuse_rrf`；**不**调用 `HybridRetrievalService.search` | §2.2.5 要求 TEI tokenize gate；RET-002 SiliconFlow 路径无 skipped；需 synthetic vector outcome；且需区分 embedding vs vector warnings | MVP_LOCAL_DECISION |
| LD-2 | `TokenizeServiceError` → Vector `channel_failure` + Warning `embedding_failed` | tokenize 属 Embedding 基础设施；规格未单列 tokenize 失败码 | MVP_LOCAL_DECISION |
| LD-3 | Warning 固定优先级排序 + 通道 kind 去重 | 规格未定义顺序；确定性利于测试与 Agent 消费 | MVP_LOCAL_DECISION |
| LD-4 | `retrieval_timeout` → HTTP **503**（非 400） | §3.23 基础设施/依赖不可用；与用户指定映射一致 | MVP_LOCAL_DECISION |
| LD-5 | `current_time` 在请求入口捕获一次 `int(time.time())` 注入 scoring + stats | 同请求内 recency 与 stats 一致 | SAFE_AUTO_REMEDIATION |
| LD-6 | 拆分 `retrieval_response_mapper` / `retrieval_warning_mapper` 纯函数 | 可测性；编排服务保持薄 | SAFE_AUTO_REMEDIATION |
| LD-7 | Route 级 per-request factory 组装 services | 与 EXT-008 一致；不扩展 `AppState` 字段 | SAFE_AUTO_REMEDIATION |
| LD-8 | 修改 RET-001..004 生产语义 | — | **HARD_BLOCK** |

## 20. NORMAL classification（HARD_BLOCK / SAFE_AUTO / MVP_LOCAL / DEFERRED）

| ID | 项 | 分类 | 说明 |
|---|---|---|---|
| CL-1 | 修改 RET-001..004 生产 Service/纯函数语义 | **HARD_BLOCK** | 仅调用 |
| CL-2 | ES/Mongo/Kafka/extraction 写入 | **HARD_BLOCK** | §10 |
| CL-3 | Evidence 失败伪造空 `source_message_ids` 返回 200 | **HARD_BLOCK** | §2.2.12 #5 |
| CL-4 | Top-K 前更新 `retrieval_count` | **HARD_BLOCK** | §11 |
| CL-5 | DEV-006 / PR #13 | **HARD_BLOCK** | 治理永久禁止 |
| CL-6 | HTTP tokenize gate + synthetic `skipped_query_too_long` | **MVP_LOCAL_DECISION** | LD-1 |
| CL-7 | Warning 排序/去重规则 | **MVP_LOCAL_DECISION** | LD-3 |
| CL-8 | `retrieval_timeout` → 503 | **MVP_LOCAL_DECISION** | LD-4 |
| CL-9 | `retrieval_response_mapper` 纯函数 | **SAFE_AUTO_REMEDIATION** | LD-6 |
| CL-10 | per-request service factory | **SAFE_AUTO_REMEDIATION** | LD-7 |
| CL-11 | RET-006 E2E | **DEFERRED** | §18 |
| CL-12 | 请求幂等 / stats 精确一次 | **DEFERRED** | §12 / §2.2.13 #6 |
| CL-13 | 新依赖 / Migration / Settings | **HARD_BLOCK** | NONE expected |

## 21. 任务目标

实现 §2.2.5 `POST /api/v1/memory/retrieval`：请求校验与鉴权、Query 标准化与 tokenize 门控、消费 RET-001..004 内部 Outcome 完成检索编排、§2.2.12 Response DTO 组装、§2.2.13 Top-K Neo4j 召回统计更新、§2.2.15 全量降级/超时矩阵；闭合 OI-008 编号映射。

可验证目标：

1. **`memory_retrieval` 路由** — Memory/Admin Key；致命码与 Warning 符合 §14、§7。
2. **`RetrievalApiService`** — 薄编排；不修改上游 Service 语义；tokenize gate + `fuse_rrf` synthetic skipped 路径。
3. **`RetrievalStatisticsRepository`** — 仅 `retrieval_count`/`last_retrieved_time`；失败 → warning。
4. **超时** — `retrieval_total_timeout_seconds` 包裹全请求；`retrieval_timeout` vs `retrieval_timeout_degraded` 分支正确。
5. **Scoped tests** — §16 全通过；RET-001..004 回归通过。

## 22. 非目标与黑名单

- 修改 `HybridRetrievalService` / `fuse_rrf` / `AuthoritativeRecallService` / `RetrievalScoringService` 生产语义。
- RET-006 E2E、cache、reranking、pagination、streaming。
- ES/Mongo/Kafka/extraction 写入；Evidence/Memory 除 §9 外字段更新。
- 新依赖 / Migration / Settings Contract 变更。
- **DEV-006 / PR #13**。
- 新造超出 §14 白名单的 HTTP 业务致命码。

## 23. 当前代码状态与前置检查

### 23.1 Git 与前置任务证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `c086b9953829d0ca19e930cde9b1c64dadde5fb9` |
| `git status --short` | 空 |
| RET-001..004 | `completed`；PR #44..#47 MERGED |
| DEV-005 | `completed`；`require_memory_api_key`、AppError |
| Retrieval HTTP 路由 | **不存在** |
| `RetrievalStatisticsRepository` | **不存在** |
| `RetrievalApiService` | **不存在** |

### 23.2 已存在可复用组件

| 组件 | 路径 |
|---|---|
| `Bm25RetrievalService` / `VectorRetrievalService` | `domain/services/*_retrieval_service.py` |
| `fuse_rrf` | `domain/services/rrf_fusion.py` |
| `AuthoritativeRecallService` | `domain/services/authoritative_recall_service.py` |
| `RetrievalScoringService` | `domain/services/retrieval_scoring_service.py` |
| `normalize_retrieval_query` | `domain/services/retrieval_query_normalizer.py` |
| `TeiTokenizeClient` | `infrastructure/tei/tei_tokenize_client.py` |
| `require_memory_api_key` | `api/dependencies.py` |
| `memory_extraction_admin` 路由模式 | `api/routes/memory_extraction_admin.py` |

## 24. 实现方案

### Step 1 — HTTP Schemas `api/schemas/memory_retrieval.py`

- `RetrievalRequest`、`RetrievalMemoryItem`、`RetrievalSubject`、`RetrievalObject`、`RetrievalResponse`（strict, extra=forbid）。

### Step 2 — 纯函数 `retrieval_response_mapper.py` + `retrieval_warning_mapper.py`

- §6 字段映射；§7 Warning 收集/排序/去重。

### Step 3 — `RetrievalStatisticsRepository`

- §9.2 Cypher；`authorized_write_cypher_queries()`；timeout from settings。

### Step 4 — `RetrievalApiService`

- §4 编排；§5 tokenize gate；§8 超时；注入 `current_time`。
- 私有：`_run_hybrid_recall`、`_embed_and_vector_search`（**本服务内**，不修改 RET-002 文件）。

### Step 5 — HTTP Route `api/routes/memory_retrieval.py`

- `require_memory_api_key`；`AppError` 映射 §14；`app.state.app_state` 注入。

### Step 6 — `api/app.py` 注册 router

### Step 7 — 测试 §16

## 25. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | Stats 单 Cypher batch；与 Response 非同一事务 | Response 先返回；stats 失败仅 warning |
| 幂等 | HTTP 非幂等 | §12；接受 retry 多次 +1 |
| 并发 | 同 Memory 并发 POST | `last_retrieved_time` CASE 单调；`retrieval_count` 可能丢增量 — MVP 接受 |
| 用户隔离 | **强制** | §13 |
| 部分失败 | 通道/图扩展/stats 可部分降级 | §7 |
| 进程恢复 | 无 in-flight 状态 | 无状态 HTTP |

## 26. 验收标准

- [ ] `POST /api/v1/memory/retrieval` 符合 §2.2.5 Request/校验/默认/上限
- [ ] Response DTO 符合 §2.2.12；`score`←`final_score`；Entity/object 映射正确
- [ ] 全量 Warning/致命码映射符合 §2.2.15 + §14
- [ ] `retrieval_total_timeout_seconds` + 单阶段超时；`retrieval_timeout` / `retrieval_timeout_degraded` 分支
- [ ] Top-K only Neo4j stats；去重；`user_id` 过滤；失败 → `retrieval_stat_update_failed`
- [ ] 零 ES/Mongo/Kafka 写入；零 RET-001..004 生产语义 diff
- [ ] scoped unit + contract + integration 全通过；RET-001..004 回归通过
- [ ] Ruff / Mypy（变更文件）通过
- [ ] Review 无 P0/P1
- [ ] OI-008 canonical DR 映射已登记

## 27. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | 无；与 §2.2.5/12/13/14/15 一致 |
| 前置任务 | RET-004、DEV-005 completed |
| 主要风险 | ① 误改 RET-002 服务；② stats 在 Top-K 前写入；③ tokenize gate 未走 synthetic skipped；④ Evidence 失败返回 200 |
| OI-008 | 本 Plan 闭合编号；不阻塞 |
| DEV-006 | **禁止触碰** PR#13 |

## 28. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/RET-005-retrieval-api-degradation-statistics"
baseline_main: "c086b9953829d0ca19e930cde9b1c64dadde5fb9"
expected_commits:
  - "docs(plan): add RET-005 retrieval api degradation and statistics plan"
  - "feat(ret): add memory retrieval api with degradation and statistics"
  - "docs(status): record RET-005 implementation commit and PR"
  - "docs(status): complete RET-005 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "RET-001..004 production service semantics"
  - "HybridRetrievalService / rrf_fusion / authoritative_recall / retrieval_scoring"
  - "RET-006 E2E"
  - "Migration / dependency / Settings"
```

### 28.1 PLAN_LANDING commit contract

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含：

1. `02_开发管理/tasks/RET-005-retrieval-api-degradation-statistics.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`

Commit message（精确）：

```text
docs(plan): add RET-005 retrieval api degradation and statistics plan
```

随后从更新后的 `main` 创建 exact feature branch `feat/RET-005-retrieval-api-degradation-statistics`。

## 29. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 07:00 UTC | planning | 创建 Task Plan；更新 progress/master_plan 规划态 | — | planning only；未 Git 写；baseline c086b99 verified |
| 2026-08-13 15:30 UTC | implementation | §15 生产 7 文件 + §16 测试 8 文件；`RetrievalApiService` 编排 + tokenize gate + 超时降级 + Neo4j stats | scoped 48 passed（unit 34 + contract 8 + integration HTTP 8）；RET-001..004 unit regression 34 passed；ruff/mypy clean；Neo4j I3 需 docker（未在本轮执行） | HTTP 编排 bypass `HybridRetrievalService.search`（LD-1）；mapper 使用 domain dataclass 避免 api 循环导入；未 Git commit |
| 2026-08-13 16:00 UTC | P2 remediation | `retrieval_api_service.py`：ruff import/E501；`validate_retrieval_input` 返回 canonical `user_id` 并全链路传播；vector search 包裹 `_await_with_deadline` | scoped 48 passed；ruff PASS；未 Git commit | 最小 diff；仅 P2-1/2/3 |
| 2026-08-13 07:48 UTC | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #48 MERGED；验证 main 含 implementation `9baf16a7c6f7b0ad3cec8155b54c9fdeeb8c4250`、merge `5b577d6e04c8b1e0a7336169a18855c66e4a2a3a`；治理四文件 + `docs(status): complete`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=3/P3=2 non-blocking；OI-008 resolved_by_task；`next_action=RET-006 planned / NOT AUTO-STARTED` | 无计划外差异 |

## 30. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

## 31. 实际执行结果

### Git 记录

```yaml
branch: "feat/RET-005-retrieval-api-degradation-statistics"
plan_commit: a6b0884f9cc6489f009d3d02a68a422dba88574b
implementation_commit: 9baf16a7c6f7b0ad3cec8155b54c9fdeeb8c4250
implementation_commit_message: "feat(ret): add memory retrieval api with degradation and statistics"
pr: "#48"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/48"
pr_state: MERGED
pr_base: main
pr_head: "feat/RET-005-retrieval-api-degradation-statistics"
merge_commit: 5b577d6e04c8b1e0a7336169a18855c66e4a2a3a
merged_at: "2026-08-13T07:42:25Z"
status_record_committed: null
```

### 测试结果

```yaml
scoped_tests: "48 passed (unit 34 + contract 8 + integration HTTP 8)"
ruff: PASS
mypy: PASS
```

### Review 结果

```yaml
p0: 0
p1: 0
p2: 3
p3: 2
review_report: null
```

### 最终状态

`completed`

---

