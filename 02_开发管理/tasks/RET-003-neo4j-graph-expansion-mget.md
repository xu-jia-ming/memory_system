# RET-003 Neo4j 权威回读 + 一跳扩展 + MGET

## 1. 任务信息

```yaml
task_id: RET-003
task_name: Neo4j 权威回读 + 一跳扩展 + MGET
status: planned
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "21a99a5b217f45cd4e4c67b8758bf1705d9d0a74"
branch: "feat/RET-003-neo4j-graph-expansion-mget"
created_at: "2026-08-13 11:50 UTC"
updated_at: "2026-08-13 11:50 UTC"
spec_sections:
  - "§2.1.9 Neo4j 记忆图谱数据模型（Memory/Entity 权威字段加载范围）"
  - "§2.2.5 Memory Retrieval API 设计（graph_expand / memory_types / status 过滤语义；本任务内部消费，非 HTTP）"
  - "§2.2.10 Neo4j Memory 加载与一跳图谱扩展（本任务唯一权威范围）"
  - "§3.6 全异步客户端（neo4j AsyncDriver、elasticsearch AsyncElasticsearch）"
  - "§3.24 连接池、超时与重试（只读消费 neo4j_timeout_seconds / elasticsearch_timeout_seconds）"
  - "§3.28 测试策略（Unit + Neo4j/ES Integration Fixture）"
prerequisites:
  formal:
    - "RET-001 — SATISFIED/completed; Bm25RetrievalService + ES read path"
    - "RET-002 — SATISFIED/completed; HybridRetrievalService + FusedRetrievalCandidate + RRF fusion（PR #45 MERGED）"
    - "EXT-006 — SATISFIED/completed; Neo4j Memory/Entity 写入与图关系 SUBJECT/OBJECT/SUPERSEDES/CONFLICTS_WITH"
    - "EXT-007 — SATISFIED/completed; ES index sync + MemoryIndexDocument（Integration Fixture 复用；非硬前置 pipeline）"
    - "DEV-004 — SATISFIED/completed; alias memory_retrieval_current + MGET 目标 Index"
  implementation_reuse:
    - "HybridRetrievalSuccess / FusedRetrievalCandidate (domain/models/hybrid_retrieval.py)"
    - "build_retrieval_status_filter semantics — Neo4j status 校验须与之对齐（独立纯函数，不修改 ES builder）"
    - "MemoryRecallRepository user_id scoped read pattern (infrastructure/neo4j/memory_recall_repository.py)"
    - "RetrievalIndexWriteRepository.bulk_upsert — ES Integration Fixture"
    - "GraphWriteRepository / test_ext006 Neo4j fixture 模式 — Neo4j Integration Fixture"
    - "MemoryRetrievalSettings: graph_expand_per_seed=2, max_graph_candidates=20, graph_decay=0.60, neo4j_timeout_seconds=5, index_name=memory_retrieval_current"
  baseline_evidence:
    branch: "main"
    head: "21a99a5b217f45cd4e4c67b8758bf1705d9d0a74"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=21a99a5b217f45cd4e4c67b8758bf1705d9d0a74"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "PLAN_APPROVED — human confirmed 2026-08-13"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create the exact feature branch feat/RET-003-neo4j-graph-expansion-mget"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_write_scope: NONE
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
  - "修改 RET-002 RRF 语义或 HybridRetrievalService 编排"
  - "修改 EXT-007 RetrievalIndexReadRepository 写入/索引同步语义"
stop_if:
  - "任何实现步骤需要 ACT-R 评分或 Evidence 聚合（RET-004）"
  - "任何实现步骤需要 HTTP Retrieval API、Warning HTTP 字段、超时降级矩阵或 retrieval_count 统计（RET-005）"
  - "任何实现步骤需要 durable 写入（Mongo/Neo4j/ES/Kafka）"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要复用 EXT-007 expand_related_memory_ids 作为 §2.2.10 检索扩展（语义不同，禁止混用）"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-008
```

## 2. authoritative_scope

本任务 **仅** 拥有 §2.2.10 Neo4j 权威回读、直接候选再校验、可选一跳图谱扩展、扩展候选 ES MGET 存在性校验及内部 Warning 种类；**不** 拥有 HTTP API、ACT-R 评分、Evidence 加载或统计更新。

| 维度 | 归属 RET-003 | 非 RET-003（显式排除） |
|---|---|---|
| RRF 候选 → Neo4j 批量加载 Memory + subject/object Entity | **是** — 权威字段范围见 §6 | — |
| ES 存在但 Neo4j 缺失 → `dirty_index_document`（内部 Warning） | **是** — 跳过，不用 ES 内容 | HTTP Warning 字段映射（RET-005） |
| Neo4j 权威再校验：user_id / memory_types / status | **是** | — |
| ES 存在但 Neo4j 权威字段与过滤不一致 → `stale_index_document` | **是** — 内部 Warning | HTTP Warning 映射（RET-005） |
| `graph_expand=true` 一跳 Neo4j 扩展 + 扩展候选 ES MGET | **是** — §8 精确语义 | — |
| 扩展候选 `graph_retrieval_score`、provenance、`retrieval_source` 追加 `graph` | **是** — 保留 RET-002 元数据 | ACT-R `final_score`（RET-004） |
| Neo4j/MGET 扩展失败 → `graph_expansion_failed`；保留直接候选 | **是** — 内部 Warning | HTTP Warning 映射（RET-005） |
| MGET 仅存在性校验；Neo4j 为权威内容 | **是** | ES 字段覆盖 Neo4j（禁止） |
| BM25 / Vector / RRF / Query Embedding | **否** — 消费 RET-002 输出 | **RET-002** |
| EXT-007 `RetrievalIndexReadRepository` 索引同步扩展 | **否** — 不同排序/限额/分数语义 | **EXT-007** |
| ACT-R 评分 / Evidence 聚合 | **否** | **RET-004** |
| HTTP API / API Key / `top_k` / 总超时降级 | **否** | **RET-005** |
| `retrieval_count` / `last_retrieved_time` 更新 | **否** | **RET-005** |
| ES Mapping/Alias 创建 | **否** | **DEV-004** |
| EXT-007 pipeline 硬依赖（Integration） | **否** — 直接 Neo4j+ES Fixture | **RET-006** |

## 3. 任务目标

在 RET-002 `HybridRetrievalSuccess` 之后实现 §2.2.10 内部权威回读与一跳图谱扩展：对 RRF 候选从 Neo4j 批量加载权威 Memory 与 subject/object Entity，按请求过滤条件再校验；当 `graph_expand=true` 时执行一跳图扩展、确定性排序与去重、计算 `graph_retrieval_score`；对扩展候选执行 Elasticsearch MGET 存在性校验；输出供 RET-004 ACT-R 消费的 `ValidatedRetrievalCandidate` 列表及内部 Warning 种类；零 durable 写入。

可验证目标：

1. **`AuthoritativeRecallService`** 接收 `HybridRetrievalSuccess` + 过滤/`graph_expand` 参数，输出 `AuthoritativeRecallOutcome`。
2. **`RetrievalMemoryReadRepository`** 新建 Neo4j 只读仓储：批量加载 Memory 权威字段 + Entity；一跳扩展 Cypher **独立于** EXT-007 `RetrievalIndexReadRepository`。
3. **`MgetRetrievalRepository`** 新建 ES `_mget` 只读仓储：存在性校验；索引名来自 `settings.memory_retrieval.index_name`。
4. **Seed 边缘情况**：脏索引、错用户、status/type 不符、重复 ID、畸形 Neo4j 记录 — 按 §7 / §10 处理。
5. **图扩展**：精确 §8 路径、排序、per-seed/global 限额、`graph_decay`、与直接候选重叠规则。
6. **Integration 测试**：Neo4j Fixture（图关系）+ ES Fixture（存在性）；不硬依赖 EXT-007 pipeline。
7. **RET-002 回归**：既有 Hybrid/RRF 测试全通过（语义不变）。

## 4. 非目标与黑名单（must_not）

- ACT-R 评分 / Evidence 加载 / `final_score` — **RET-004**。
- HTTP Retrieval API / Warning HTTP 响应字段 / `retrieval_total_timeout_seconds` 跨阶段总超时 — **RET-005**。
- `retrieval_count` / `last_retrieved_time` 统计更新 — **RET-005**。
- 修改 RET-002 `fuse_rrf`、`HybridRetrievalService`、RRF 算例语义。
- 修改 EXT-007 `RetrievalIndexReadRepository` 生产语义或索引同步扩展逻辑。
- 复用 EXT-007 `expand_related_memory_ids` / `expand_entity_linked_memory_ids` 作为检索图扩展实现。
- Mongo/Neo4j/ES/Kafka **写入**。
- **DEV-006 / PR #13**。
- 新依赖 / Migration / Settings Contract 变更。
- 多跳递归扩展、通用图遍历框架。
- Session→Consolidation 全链路 E2E — **RET-006**。

## 5. 当前代码状态与前置检查

### 5.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `21a99a5b217f45cd4e4c67b8758bf1705d9d0a74`（与用户给定 `planning_baseline_main` 一致） |
| `git status --short` | 空 |
| RET-001 / RET-002 | `completed`；PR #44 / #45 MERGED |
| EXT-006 / EXT-007 / DEV-004 | `completed` |
| Neo4j 检索读回 / MGET / 图扩展检索 | **不存在** — `rg MgetRetrieval|AuthoritativeRecall|graph_expansion_ranker` 无生产命中 |
| MGET 实现 | **不存在** |
| workflow | `NORMAL`，explicit |

### 5.2 已存在可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| `FusedRetrievalCandidate` / `HybridRetrievalSuccess` | `domain/models/hybrid_retrieval.py` | RET-002 输入契约 |
| `build_retrieval_status_filter` | `infrastructure/elasticsearch/retrieval_filter_builder.py` | status 语义对照（Neo4j 校验须等价） |
| `MemoryRecallRepository` | `infrastructure/neo4j/memory_recall_repository.py` | user_id scoped Cypher 模式参考 |
| `RetrievalIndexReadRepository` | `infrastructure/neo4j/retrieval_index_read_repository.py` | **只读参考**；禁止混用扩展语义 |
| `RetrievalIndexWriteRepository` | `infrastructure/elasticsearch/retrieval_index_write_repository.py` | ES Fixture |
| `GraphWriteRepository` | `infrastructure/neo4j/graph_write_repository.py` | Neo4j Integration Fixture 参考 |
| `test_ext006_graph_write_neo4j.py` | `tests/integration/` | Neo4j compose fixture 模式 |
| `ret002_es_fixtures` | `tests/support/ret002_es_fixtures.py` | ES Fixture 模式 |

### 5.3 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无权威回读领域模型 | 无 `authoritative_recall` / `ValidatedRetrievalCandidate` |
| 无 Neo4j 检索读回仓储 | 无 `retrieval_memory_read_repository` |
| 无 ES MGET 仓储 | 无 `mget_retrieval` |
| 无图扩展排序纯函数 | 无 `graph_expansion_ranker` |
| 无 RET-003 测试 | `tests/` 无 `test_ret003` |

**结论**：新建权威回读服务、Neo4j 读回仓储、ES MGET 仓储、图扩展纯函数与领域模型；不修改 RET-002 / EXT-007 生产语义。

## 6. input_contract（消费 RET-002）

### 6.1 上游输入（必须原样消费）

来自 `HybridRetrievalSuccess`（RET-002 `fuse_rrf` 输出）：

```text
HybridRetrievalSuccess {
  user_id: str
  retrieval_mode: Literal["hybrid","bm25_only","vector_only","none"]
  effective_channel_count: int
  candidates: list[FusedRetrievalCandidate]
}

FusedRetrievalCandidate {
  memory_id: str
  bm25_rank: int | None
  vector_rank: int | None
  bm25_score: float | None
  vector_score: float | None
  retrieval_source: list[Literal["bm25","vector"]]
  rrf_score: float
  min_available_rank: int
  normalized_retrieval_score: float | None
}
```

**透传**：`user_id`、`retrieval_mode`、`effective_channel_count` 进入 `AuthoritativeRecallSuccess` 不变。

### 6.2 附加查询参数（Service 入参 — 非 `HybridRetrievalQuery` 今日字段）

`HybridRetrievalQuery` 已有 `memory_types`、`include_conflicted`、`include_history`；**缺** `graph_expand`。本任务在 **权威回读 Service 入参** 中显式要求（与 §2.2.5 对齐）：

```text
AuthoritativeRecallQuery {
  hybrid_success: HybridRetrievalSuccess      # 必填
  memory_types: list[str] | None = None       # 与 Hybrid/BM25/Vector 相同语义
  include_conflicted: bool = False
  include_history: bool = False
  graph_expand: bool = True                    # §2.2.5 默认 true
}
```

| 字段 | 校验 | 说明 |
|---|---|---|
| `hybrid_success.user_id` | 非空 `str` | 所有 Neo4j/ES 调用强制绑定 |
| `memory_types` | `None` 或 `list[str]`；非空元素 ⊆ `{fact, preference, event, profile}`；去重后空视为不限制 | 与 RET-001/002 filter builder 一致 |
| `include_conflicted` / `include_history` | `bool` | Neo4j status 校验见 §7.3 |
| `graph_expand` | `bool` | `false` 时跳过 §8 全部扩展与扩展 MGET |

**禁止**：在本任务引入 HTTP Request DTO、`top_k`、API Key 或 Query 文本字段。

### 6.3 输入预处理 — RRF 候选去重

在 Neo4j 加载前对 `hybrid_success.candidates` 按 `memory_id` 去重：

1. 保留 `min_available_rank` **最小** 的条目（最佳 rank）。
2. tie-break：`memory_id` **ASC**（字典序）。
3. 去重后顺序：按原 RRF 顺序中**首次出现**的保留项稳定重排（等价于按 `min_available_rank ASC, memory_id ASC`）。

重复 `memory_id` 不得导致双次 Neo4j 加载或双次输出。

## 7. neo4j_readback_contract（Seed 权威加载与再校验）

### 7.1 Neo4j 加载范围（§2.1.9 — RET-004 交接字段）

**Memory 节点**（批量 `UNWIND $memory_ids` + `WHERE m.user_id = $user_id`）：

| 字段 | 用途 |
|---|---|
| `memory_id`, `user_id`, `memory_type`, `status`, `content` | 权威内容与过滤 |
| `subject_entity_id`, `predicate`, `object_entity_id`, `object_value` | 结构字段 |
| `event_status`, `start_time`, `end_time`, `original_time_text` | event 字段 |
| `importance`, `confidence` | RET-004 ACT-R |
| `retrieval_count`, `last_retrieved_time`, `latest_source_time` | RET-004 ACT-R |
| `updated_time` | 调试/下游可选 |

**不加载**：`Evidence` 节点（RET-004 §2.2.12）。

**Entity 节点**（`OPTIONAL MATCH` subject/object）：

| 字段 |
|---|
| `entity_id`, `canonical_name`, `aliases`, `entity_type`, `normalized_name` |

每个 Entity 查询须 `WHERE entity.user_id = $user_id`。

### 7.2 领域快照

```text
RetrievalEntitySnapshot {
  entity_id: str
  canonical_name: str
  aliases: list[str]
  entity_type: str
  normalized_name: str
}

RetrievalMemorySnapshot {
  memory_id: str
  user_id: str
  memory_type: str
  status: str
  content: str
  subject_entity_id: str
  predicate: str
  object_entity_id: str | None
  object_value: str | None
  event_status: str | None
  start_time: int | None
  end_time: int | None
  original_time_text: str | None
  importance: float
  confidence: float
  retrieval_count: int
  last_retrieved_time: int | None
  latest_source_time: int | None
  updated_time: int
  subject_entity: RetrievalEntitySnapshot | None
  object_entity: RetrievalEntitySnapshot | None
}
```

畸形 Neo4j 记录（缺必填字段、类型错误、`user_id` 与请求不一致）→ **跳过该 memory_id**（不进入候选、不抛全局失败）；记录内部可观测错误（单元测试断言）。

### 7.3 Status 允许集合（与 ES filter 等价）

纯函数 `memory_status_allowed(status, include_conflicted, include_history) -> bool`：

| include_conflicted | include_history | 允许 status |
|---|---|---|
| false | false | `active` |
| true | false | `active`, `conflicted` |
| false | true | `active`, `superseded` |
| true | true | `active`, `conflicted`, `superseded` |

须与 `build_retrieval_status_filter` 语义一致（单元测试对照矩阵）。

### 7.4 Seed 逐条处理规则

对去重后每个 RRF 候选 `memory_id`：

| 条件 | 动作 | 内部 Warning |
|---|---|---|
| Neo4j **无** Memory 节点 | 跳过；**不得**用 ES 内容代替 | `dirty_index_document`（`memory_id` 必填） |
| Neo4j `user_id` ≠ 请求 `user_id` | 丢弃该候选（fail-closed） | 无 Warning；Security 测试须覆盖 |
| `memory_types` 非空且 `memory_type` 不在集合 | 丢弃 | 若 ES 曾命中 → `stale_index_document` |
| `status` 不在 §7.3 允许集合 | 丢弃 | 若 ES 曾命中 → `stale_index_document` |
| 通过全部校验 | 加入 `direct_candidates` | — |

**ES 曾命中判定**：该 `memory_id` 出现在去重后 RRF `candidates` 中（BM25/Vector 通道返回即视为 ES 索引存在）。

**Neo4j 批量读 transport/超时失败**（整批 `load_memories` 失败）→ `AuthoritativeRecallFailure.kind = neo4j_read_failure`；**不**返回任何候选（fail-closed）。

**`hybrid_success.candidates` 为空** → `success`；`direct_candidates=[]`；`expanded_candidates=[]`；无 Neo4j 批量读调用。

### 7.5 直接候选输出元数据

通过校验的 Seed 保留 RET-002 全部 rank/score 字段：

```text
ValidatedRetrievalCandidate {
  memory_id: str
  bm25_rank, vector_rank, bm25_score, vector_score
  retrieval_source: list[Literal["bm25","vector","graph"]]   # 初始为 RET-002 值；扩展重叠可追加 "graph"
  rrf_score: float
  min_available_rank: int
  normalized_retrieval_score: float | None
  graph_retrieval_score: float | None = None                 # 纯直接候选为 null
  candidate_origin: Literal["direct"] = "direct"
  memory: RetrievalMemorySnapshot
}
```

## 8. one_hop_expansion_contract（§2.2.10 精确语义）

**前置**：`graph_expand=true` 且存在至少一条 `direct_candidates`；否则跳过本章。

### 8.1 允许路径

**路径 A — 共享 Entity**：

```text
(seed:Memory)-[:SUBJECT|OBJECT]->(entity:Entity)<-[:SUBJECT|OBJECT]-(related:Memory)
```

**路径 B — 直接关系**：

```text
(seed:Memory)-[:SUPERSEDES|CONFLICTS_WITH]-(related:Memory)
```

**禁止**：多跳、反向路径组合、任意其他关系类型。

### 8.2 过滤规则（每条 related）

1. `related.user_id ==` 请求 `user_id`。
2. `related.memory_id != seed.memory_id`（不返回 Seed 自身）。
3. `memory_type` / `status` 与 §7.3 / `memory_types` 相同过滤。
4. **路径 A**：共享 `entity.entity_id != "user:" + user_id`（排除用户实体）。
5. **不递归**：仅 Seed→Related 一跳；Related 不再作为 Seed 扩展。

### 8.3 扩展关系优先级（排序第一维）

每条 `(seed, related)` 扩展边携带 `expansion_tier`：

| tier 值 | 条件 | 说明 |
|---|---|---|
| 0 | 路径 B：`SUPERSEDES` 或 `CONFLICTS_WITH` | 最高优先 |
| 1 | 路径 A：共享 **OBJECT** Entity（`entity` 为 seed 的 OBJECT 或 related 的 OBJECT 且相同 `entity_id`） | 次之 |
| 2 | 路径 A：共享 **非用户 SUBJECT** Entity | 再次 |

同 related 自多种路径命中 → 取 **最小 tier**（最高优先）。

### 8.4 确定性排序（per seed 内）

对单 Seed 的全部 related（过滤后）稳定排序：

1. `expansion_tier` **ASC**
2. `importance` **DESC**
3. `latest_source_time` **DESC**（`null` 视为 `0`）
4. `memory_id` **ASC**

取前 `graph_expand_per_seed`（默认 `2`）条 **related memory_id**。

### 8.5 全局聚合（跨 Seed）

1. 合并所有 Seed 的 per-seed 选取结果。
2. **去重** `related memory_id`（跨 Seed 只保留一次）。
3. 全局最多 `max_graph_candidates`（默认 `20`）条 **纯扩展候选**（尚未处理与 direct 重叠）。
4. 全局排序（用于截断 `max_graph_candidates`）：按该 related 的 **最佳**（最小）`expansion_tier`，再 `importance DESC`, `latest_source_time DESC`, `memory_id ASC`。
5. 计算 `graph_retrieval_score`：

```text
graph_retrieval_score(related) =
  max over all seeds that expanded to related:
    seed.normalized_retrieval_score * graph_decay
```

- `graph_decay` 来自 `settings.memory_retrieval.graph_decay`（默认 `0.60`）。
- 若某 Seed 的 `normalized_retrieval_score` 为 `None` → 该 Seed 对分数贡献为 `0`（不参与 max）。
- 纯扩展候选（不在 direct 集合）：`normalized_retrieval_score = null`；RET-004 使用 `graph_retrieval_score` 作为 retrieval 分量（本任务仅赋值，不算 ACT-R）。

### 8.6 与直接候选重叠（§2.2.10 #8）

设 `direct_ids` = 已通过 §7 校验的 Seed `memory_id` 集合。

对每个扩展得到的 `related_id`：

| 情况 | 动作 |
|---|---|
| `related_id ∈ direct_ids` | **不**新增扩展候选；更新对应 direct 候选：`retrieval_source` 追加 `"graph"`（稳定字母序：`bm25` < `graph` < `vector`）；**保留**原有 `normalized_retrieval_score`；**不得**用较低 `graph_retrieval_score` 覆盖 |
| `related_id ∉ direct_ids` | 作为扩展候选进入 MGET 校验队列 |

### 8.7 Neo4j 扩展失败

Neo4j 一跳查询 transport/超时/驱动异常 → **跳过全部扩展候选**；保留全部 `direct_candidates`；追加内部 Warning `graph_expansion_failed`（无 `memory_id`）。

单条畸形扩展记录 → 跳过该 related（不触发全局 `graph_expansion_failed`）。

### 8.8 扩展候选 Neo4j 加载

对将作为 **纯扩展** 进入结果的 `related_id`（不在 `direct_ids`）：

- 批量 Neo4j 加载 §7.1 字段（可与扩展 Cypher 合并或二次 `load_memories`）。
- 再执行 §7.3 / §7.4 校验（不含 dirty_index — 扩展候选无 RRF ES 命中语义；Neo4j 缺失直接丢弃无 Warning）。
- 输出 `candidate_origin = "expanded"`，`retrieval_source = ["graph"]`，`graph_retrieval_score` 按 §8.5。

**纯扩展候选 RET-002 标量元数据（SF-1 — RET-004 handoff 契约）**：

| 字段 | 纯 `expanded` 候选值 |
|---|---|
| `bm25_rank` | `None` |
| `vector_rank` | `None` |
| `bm25_score` | `None` |
| `vector_score` | `None` |
| `rrf_score` | `None` |
| `min_available_rank` | `None` |
| `normalized_retrieval_score` | `None` |
| `graph_retrieval_score` | 按 §8.5 计算 |

**禁止**为纯扩展候选合成假 BM25/Vector rank、`0.0` 占位 `rrf_score` 或任何 RRF 重算。单元测试 **必须**断言上述 `None` 语义（U22）。

## 9. mget_contract

### 9.1 调用时机与范围

| 场景 | MGET 对象 |
|---|---|
| `graph_expand=true` 且扩展成功 | 全部 **纯扩展** `memory_id`（§8.6 未重叠 direct 的那些） |
| Seed `stale_index_document` 交叉校验（可选 LD-3） | 不强制；默认 **不**对 Seed 做 MGET（RRF 已证明 ES 存在） |

### 9.2 ES 请求结构

```text
POST {settings.memory_retrieval.index_name}/_mget
{
  "ids": [<memory_id strings, sorted ASC for determinism>]
}
```

- 索引名：`settings.memory_retrieval.index_name`（alias `memory_retrieval_current`）。
- Document ID = `memory_id`。
- `request_timeout = settings.memory_retrieval.elasticsearch_timeout_seconds`。

### 9.3 响应处理

| 结果 | 动作 |
|---|---|
| `docs[i].found == true` | 扩展候选保留（Neo4j 字段仍权威） |
| `docs[i].found == false` | **丢弃**该扩展候选（不进输出） |
| 整次 MGET transport/超时/畸形 | **丢弃全部扩展候选**；保留 direct；`graph_expansion_failed` |

**禁止**：读取 `_source` 覆盖 Neo4j `content`/`status` 等权威字段。

### 9.4 顺序恢复

MGET 后输出列表顺序：

1. `direct_candidates`：保持 RRF 去重后顺序（`min_available_rank ASC`, `memory_id ASC`）。
2. `expanded_candidates`：按 §8.4 全局排序键（在 `max_graph_candidates` 截断后、MGET 过滤后）稳定顺序。

下游 RET-004 可将两者合并；本任务 `AuthoritativeRecallSuccess` 可暴露 `direct_candidates` + `expanded_candidates` 或 `all_candidates`（实现时二选一并在模型中固定；**禁止**重复 memory_id）。

## 10. failure_mapping（内部 Outcome — 非 RET-005 HTTP）

### 10.1 内部 Warning 种类

```text
InternalRetrievalWarning {
  kind: Literal[
    "dirty_index_document",
    "stale_index_document",
    "graph_expansion_failed"
  ]
  memory_id: str | None   # dirty/stale 必填；graph_expansion_failed 为 null
}
```

**禁止**在本任务返回 HTTP Warning 字符串或 Response DTO。

### 10.2 失败/降级映射表

| 失败源 | 内部表示 | 直接候选 | 扩展候选 | Warning |
|---|---|---|---|---|
| RRF 候选 Neo4j 缺失 | 跳过 | — | — | `dirty_index_document` |
| Neo4j `user_id` 不匹配 | 丢弃该条 | — | — | — |
| type/status 过滤失败 | 丢弃 | — | — | `stale_index_document`（ES 曾命中） |
| 重复 `memory_id` 输入 | 去重 §6.3 | 保留最佳 rank | — | — |
| Neo4j 批量 Seed 读失败 | `failure.neo4j_read_failure` | 无输出 | 无输出 | — |
| Neo4j 单条畸形 | 跳过该条 | — | — | — |
| Neo4j 扩展失败 | `success` 降级 | 保留 | 全部跳过 | `graph_expansion_failed` |
| MGET 失败 | `success` 降级 | 保留 | 全部跳过 | `graph_expansion_failed` |
| MGET `found=false` | 丢弃该扩展条 | 保留 | 丢弃该条 | — |
| `graph_expand=false` | 无扩展 | 仅 direct | 无 | — |
| `candidates=[]` | `success` 空 | `[]` | `[]` | — |
| 入参非法 | `ValueError` | — | — | — |

### 10.3 AuthoritativeRecall Outcome

```text
AuthoritativeRecallSuccess {
  user_id: str
  retrieval_mode: ...           # pass-through from RET-002
  effective_channel_count: int  # pass-through
  direct_candidates: list[ValidatedRetrievalCandidate]
  expanded_candidates: list[ValidatedRetrievalCandidate]
  warnings: list[InternalRetrievalWarning]
}

AuthoritativeRecallFailure {
  kind: Literal["neo4j_read_failure"]
  message: str
}

AuthoritativeRecallOutcome {
  outcome: Literal["success","failure"]
  success: AuthoritativeRecallSuccess | None
  failure: AuthoritativeRecallFailure | None
}
```

## 11. user_isolation（Code Review 证明点）

| # | 规则 | Enforcement | 测试 ID |
|---|---|---|---|
| UISO-1 | 所有 Neo4j Cypher 含 `WHERE m.user_id = $user_id`（或等价） | Repository 层；`authorized_read_cypher_queries()` 契约测试 | C5, I2 |
| UISO-2 | Entity `OPTIONAL MATCH` 含 `entity.user_id = $user_id` | Cypher + 解析断言 | C5 |
| UISO-3 | 扩展 related 过滤 `related.user_id = $user_id` | 扩展 Cypher + 单元测试 | U15, I3 |
| UISO-4 | Neo4j 返回 `user_id` ≠ 请求 → 丢弃（fail-closed） | Service 层二次校验 | U6 |
| UISO-5 | ES MGET 不携带 `user_id` filter — 仅存在性；隔离依赖 Neo4j 已校验 | 文档 + 测试：交叉用户 related 不泄漏 | I2, I4 |
| UISO-6 | 禁止跨用户批量 `memory_id` 无 `user_id` 绑定查询 | grep + 契约 | C5 |
| UISO-7 | 日志禁止记录 Memory `content` 全文 | Code Review checklist | — |

## 12. replay_idempotency

| 场景 | 预期行为 |
|---|---|
| 相同 `AuthoritativeRecallQuery` 重复调用 | 相同 `direct_candidates` / `expanded_candidates` / `warnings`（图与索引不变） |
| RRF 候选去重 | 确定性：§6.3 |
| 扩展排序 | 确定性 tier + importance + time + memory_id |
| `memory_id` 列表传入 Neo4j/ES | `sorted(memory_ids)` 稳定顺序 |
| 多 Seed 同 related | `graph_retrieval_score` 取 max；单条输出 |
| 并发相同查询 | 只读；无共享可变状态 |
| 进程重启 | 行为与首次一致 |

## 13. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/authoritative_recall.py` | 创建 | Query/Success/Warning/Outcome 模型 |
| `src/memory_system/domain/models/retrieval_memory_snapshot.py` | 创建 | Memory/Entity 权威快照 |
| `src/memory_system/domain/services/retrieval_memory_validator.py` | 创建 | status/type/user 纯函数校验 |
| `src/memory_system/domain/services/graph_expansion_ranker.py` | 创建 | tier 排序、per-seed/global 限额、score、重叠合并 |
| `src/memory_system/domain/services/authoritative_recall_service.py` | 创建 | 编排：去重→Neo4j seed→扩展→MGET |
| `src/memory_system/infrastructure/neo4j/retrieval_memory_read_repository.py` | 创建 | 批量 load + 一跳扩展 Cypher（**新**；非 EXT-007） |
| `src/memory_system/infrastructure/elasticsearch/mget_retrieval_repository.py` | 创建 | ES `_mget` 存在性 |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `hybrid_retrieval.py`、`rrf_fusion.py`、`retrieval_index_read_repository.py`、`settings/`、`entrypoints/`、DEV-006）。

## 14. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_retrieval_memory_validator.py` | 创建 | status/type 矩阵 |
| `tests/unit/test_graph_expansion_ranker.py` | 创建 | tier 排序、decay、max、重叠 |
| `tests/unit/test_authoritative_recall_service.py` | 创建 | mock Neo4j/MGET；failure mapping |
| `tests/unit/test_mget_retrieval_repository.py` | 创建 | MGET body/解析 |
| `tests/unit/test_retrieval_memory_read_repository.py` | 创建 | Cypher 授权 + 解析（mock driver） |
| `tests/integration/test_ret003_authoritative_recall.py` | 创建 | Neo4j+ES 集成 |
| `tests/support/ret003_neo4j_fixtures.py` | 创建 | 图关系 Fixture |
| `tests/support/ret003_es_fixtures.py` | 创建 | ES 存在性 Fixture（可复用 ret002 模式） |

**白名单外任何 `tests/**` 变更 → FAIL**（RET-002 测试文件不得修改语义；运行回归但不在白名单内编辑）。

### 14.1 governance_file_whitelist（SF-2 — Release Operator 各 phase）

| Phase | 允许路径 | 目的 |
|---|---|---|
| `PLAN_LANDING` | `02_开发管理/tasks/RET-003-neo4j-graph-expansion-mget.md` | 已批准 Task Plan |
| `PLAN_LANDING` | `02_开发管理/progress.md` | 规划态 / `approved` 登记 |
| `PLAN_LANDING` | `02_开发管理/master_plan.md` | RET-003 规划登记 |
| `IMPLEMENTATION_RELEASE` | §13 production_file_whitelist 全部路径 | 实现 |
| `IMPLEMENTATION_RELEASE` | §14 test_file_whitelist 全部路径 | 测试 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/tasks/RET-003-neo4j-graph-expansion-mget.md` | 执行记录 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/progress.md` | `reviewed` / `committed` 登记 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/master_plan.md` | 状态备注 |
| `POST_MERGE_CLEANUP` | `02_开发管理/tasks/RET-003-neo4j-graph-expansion-mget.md` | 完成登记 |
| `POST_MERGE_CLEANUP` | `02_开发管理/progress.md` | `completed` |
| `POST_MERGE_CLEANUP` | `02_开发管理/master_plan.md` | `completed` |

**永久禁止**（所有 phase）：`DEV-006`、PR #13 相关路径；`RET-002`/`EXT-007` 生产语义文件；规格正文。

### 14.2 PLAN_LANDING commit contract（SF-3）

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含以下三份治理文件（plus 无其他路径）：

1. `02_开发管理/tasks/RET-003-neo4j-graph-expansion-mget.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`

Commit message（精确）：

```text
docs(plan): add RET-003 neo4j authoritative recall and graph expansion plan
```

随后从更新后的 `main` 创建 exact feature branch `feat/RET-003-neo4j-graph-expansion-mget`。

## 15. 实现方案

### Step 1 — 领域快照 `retrieval_memory_snapshot.py`

- `RetrievalEntitySnapshot`、`RetrievalMemorySnapshot`（§7.2）

### Step 2 — 权威回读模型 `authoritative_recall.py`

- `AuthoritativeRecallQuery`、`ValidatedRetrievalCandidate`、`InternalRetrievalWarning`
- `AuthoritativeRecallSuccess` / `Failure` / `Outcome`（§10.3）

### Step 3 — 校验纯函数 `retrieval_memory_validator.py`

- `memory_status_allowed`、`memory_type_allowed`
- `validate_memory_for_request(snapshot, user_id, memory_types, include_conflicted, include_history) -> ValidationResult`

### Step 4 — Neo4j 读回仓储 `retrieval_memory_read_repository.py`

- `Q_LOAD_RETRIEVAL_MEMORIES` — §7.1 字段 + Entity
- `Q_ONE_HOP_EXPANSION` — 返回 `seed_id, related_id, expansion_tier, importance, latest_source_time`（或分路径查询后合并 tier）
- `async load_memories(user_id, memory_ids) -> dict[str, RetrievalMemorySnapshot]`
- `async expand_one_hop(user_id, seed_ids) -> list[ExpansionEdge]`
- `neo4j_timeout` 来自 settings；`authorized_read_cypher_queries()` 供契约测试
- **禁止** import/use `RetrievalIndexReadRepository` 扩展方法

### Step 5 — ES MGET 仓储 `mget_retrieval_repository.py`

- `async exists_many(index, memory_ids) -> set[str]`（返回 found id 集合）
- `MgetRetrievalError` 对齐 `Bm25RetrievalError` 模式

### Step 6 — 图扩展纯函数 `graph_expansion_ranker.py`

- `rank_per_seed_edges(edges, per_seed_limit) -> ...`
- `aggregate_expanded_candidates(..., max_graph_candidates, graph_decay) -> ...`
- `merge_overlap_with_direct(direct, expanded) -> (updated_direct, pure_expanded)`
- 无 I/O

### Step 7 — 编排服务 `authoritative_recall_service.py`

- 流程：
  1. 校验入参
  2. 去重 RRF candidates §6.3
  3. Neo4j batch load seeds → §7.4 校验 → `direct_candidates` + warnings
  4. 若 `graph_expand`：Neo4j expand → ranker → overlap merge
  5. Neo4j load pure expanded memories → 再校验
  6. ES MGET pure expanded → 过滤 → `expanded_candidates`
  7. 组装 `AuthoritativeRecallSuccess`
- Factory：`create_authoritative_recall_service(...)`

### Step 8 — 单元测试

- 覆盖 §16.1–§16.2 全部 ID

### Step 9 — Integration + Fixture

- `ret003_neo4j_fixtures.py`：用户 A/B 各 Memory + Entity + SUBJECT/OBJECT/SUPERSEDES/CONFLICTS_WITH
- `ret003_es_fixtures.py`：direct 种子写 ES；故意缺扩展文档测 MGET 丢弃
- `test_ret003_authoritative_recall.py`：dirty_index、stale、扩展排序、重叠 append graph、MGET 失败降级

## 16. 测试计划

### 16.1 Unit Test

| ID | 场景 | 预期 |
|---|---|---|
| U1 | status 矩阵四组合 | 与 `build_retrieval_status_filter` 等价 |
| U2 | `memory_types` 空/非空过滤 | 允许/拒绝 |
| U3 | RRF 重复 `memory_id` 去重 | 保留最小 `min_available_rank` |
| U4 | Neo4j 缺失 seed | `dirty_index_document`；无候选 |
| U5 | Neo4j status 不符 + ES 命中 | `stale_index_document`；丢弃 |
| U6 | Neo4j `user_id` 不匹配 | 丢弃；无泄漏 |
| U7 | `graph_expand=false` | 仅 direct；无 Neo4j 扩展调用 |
| U8 | tier 0 优先于 tier 1/2 | 排序断言 |
| U9 | per-seed limit=2 | 每 seed 最多 2 related |
| U10 | global `max_graph_candidates=20` | 全局截断 |
| U11 | `graph_retrieval_score = norm * 0.60` | 精确算例 |
| U12 | 多 seed 同 related | `graph_retrieval_score` 取 max |
| U13 | 扩展与 direct 重叠 | 不重复；`retrieval_source` 含 `graph`；分数不变 |
| U14 | MGET `found=false` | 丢弃扩展条 |
| U15 | 扩展 related 其他 `user_id` | 不返回 |
| U16 | 排除 `user:{user_id}` 实体扩展 | 不通过用户实体扩散 |
| U17 | Neo4j 扩展失败 | direct 保留；`graph_expansion_failed` |
| U18 | MGET 失败 | direct 保留；`graph_expansion_failed` |
| U19 | Neo4j 批量读失败 | `neo4j_read_failure` |
| U20 | 空 RRF candidates | success 空列表 |
| U21 | RET-002 回归 | 现有 hybrid/rrf 测试全通过 |
| U22 | 纯 `expanded` 候选 RET-002 标量字段 | 全部 `None`；`graph_retrieval_score` 有值；无假 rank/score |

### 16.2 Contract Test

| ID | 场景 | 预期 |
|---|---|---|
| C1 | MGET 请求体 `ids` + index from settings | snapshot |
| C2 | 不修改 RET-002 / EXT-007 生产文件 | `git diff` 白名单 |
| C3 | Neo4j Cypher 均含 `user_id` | `authorized_read_cypher_queries` |
| C4 | 无 `_source` 读取覆盖 Neo4j | grep 断言 |
| C5 | user isolation Cypher 契约 | UISO-1..6 |

### 16.3 Integration Test

| ID | 场景 | 预期 |
|---|---|---|
| I1 | direct seed Neo4j+ES 一致 | 进入 `direct_candidates` |
| I2 | 交叉用户 related | `user_b` memory 不可见 |
| I3 | OBJECT 共享扩展 | tier 1 命中 |
| I4 | SUPERSEDES 扩展 | tier 0 优先 |
| I5 | ES 无 Neo4j | `dirty_index_document` |
| I6 | Neo4j 有 ES 无（扩展） | MGET 后丢弃 |
| I7 | `graph_expand=true` 端到端 | direct + expanded 数量与顺序 |
| I8 | MGET 失败注入（mock） | 降级 direct-only + warning |

### 16.4 E2E Test

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — RET-006 |

### 16.5 失败注入与并发测试

| ID | 场景 | 预期 |
|---|---|---|
| F1 | Neo4j timeout 注入 | `neo4j_read_failure` 或扩展降级（按失败点） |
| F2 | 并发 10 路相同权威回读 | 无异常；结果一致 |

## 17. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 只读查询 |
| 幂等 | **是** | §12 确定性去重与排序 |
| 并发 | 只读无锁 | Neo4j/ES 并发安全 |
| 版本冲突 | 不适用 | 无乐观锁 |
| 用户隔离 | **强制** | §11 |
| 部分失败 | **是** | 扩展/MGET 降级；单条跳过 |
| 进程异常恢复 | 不适用 | 无 in-flight 写 |

## 18. 验收标准

- [ ] §2.2.10 Seed 权威加载 + 再校验 + dirty/stale 内部 Warning
- [ ] §8 一跳扩展路径、tier 排序、per-seed/global 限额、`graph_decay`、重叠规则
- [ ] ES MGET 仅存在性；不覆盖 Neo4j；扩展缺失丢弃
- [ ] Neo4j/MGET 扩展失败降级 + `graph_expansion_failed`
- [ ] RET-002 元数据透传保留；`retrieval_source` 可追加 `graph`
- [ ] 不修改 RET-002 RRF / EXT-007 索引同步语义
- [ ] Integration Neo4j+ES Fixture；不硬依赖 EXT-007 pipeline
- [ ] scoped unit + integration 全通过；RET-002 回归通过；Ruff/Mypy（变更文件）通过
- [ ] Review 无 P0/P1

## 19. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | 无；与 §2.2.10、master_plan RET-003 一致 |
| 前置任务 | RET-002、EXT-006、EXT-007、DEV-004 completed |
| 主要风险 | ① 误用 EXT-007 扩展 Cypher；② MGET 误读 `_source`；③ 扩展排序 tier 实现偏差 |
| 非阻塞 | OI-008（RET-005 API 编辑性） |
| DEV-006 | **禁止触碰** PR#13 |

## 20. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/RET-003-neo4j-graph-expansion-mget"
baseline_main: "21a99a5b217f45cd4e4c67b8758bf1705d9d0a74"
expected_commits:
  - "docs(plan): add RET-003 neo4j authoritative recall and graph expansion plan (includes progress.md + master_plan.md planning metadata)"
  - "feat(ret): add neo4j authoritative recall, one-hop graph expansion, and es mget"
  - "docs(status): record RET-003 implementation commit and PR"
  - "docs(status): complete RET-003 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "RET-002 rrf_fusion / hybrid_retrieval_service"
  - "EXT-007 retrieval_index_read_repository"
  - "HTTP API / RET-005 warnings"
  - "ACT-R / Evidence / RET-004"
  - "retrieval_count updates"
  - "Migration / dependency / Settings"
```

## 21. mvp_local_decisions

| ID | 决策 | 理由 | 分类 |
|---|---|---|---|
| LD-1 | 新建 `retrieval_memory_read_repository`；**不**复用 EXT-007 `RetrievalIndexReadRepository` 扩展方法 | §2.2.10 排序/限额/decay 与索引同步扩展语义不同 | HARD_BLOCK 若混用 |
| LD-2 | Neo4j status 校验用独立 `retrieval_memory_validator`；不修改 ES `retrieval_filter_builder` | 保持 ES/Neo4j 层分离；语义对照测试保证一致 | SAFE_AUTO_REMEDIATION |
| LD-3 | Seed 不做 ES MGET；脏/陈旧仅依 RRF 命中 + Neo4j 权威对比 | RRF 已证明 ES 存在；减少 ES 往返 | MVP_LOCAL_DECISION |
| LD-4 | `AuthoritativeRecallSuccess` 拆分 `direct_candidates` + `expanded_candidates` | RET-004 需区分 retrieval 分数来源；重叠已在 direct 合并 | MVP_LOCAL_DECISION |
| LD-5 | 扩展 Cypher 单次批量返回 `expansion_tier` 供 ranker | 避免 per-seed 多次往返；仍满足一跳语义 | MVP_LOCAL_DECISION |
| LD-6 | Integration 使用 compose Neo4j + ES Fixture；不跑 EXT-007 pipeline | master_plan / RET-002 先例 | DEFERRED_FOR_MVP pipeline E2E → RET-006 |
| LD-7 | 内部 Warning 使用 `InternalRetrievalWarning` 模型；**不**复用 HTTP Warning 字符串 | RET-005 负责 HTTP 映射 | HARD_BLOCK 若泄漏 HTTP |
| LD-8 | `retrieval_source` 追加 `graph` 后全列表按 `bm25 < graph < vector` 稳定排序 | 确定性输出 | SAFE_AUTO_REMEDIATION |

## 22. deferred_for_mvp

| 项 | 说明 |
|---|---|
| ACT-R 评分 + Evidence | RET-004 |
| HTTP API + Warning HTTP 字段 + 总超时 | RET-005 |
| `retrieval_count` 统计更新 | RET-005 |
| EXT-007 写入→检索全链路 E2E | RET-006 |
| Seed ES MGET 交叉校验（可选增强） | LD-3 |
| 多跳图扩展 | 规格外 |

## 23. open_issues

| ID | 关系 | 阻塞 RET-003？ |
|---|---|---|
| OI-008 | RET-005 API 编辑性 | **否** |

## 24. Plan Amendment

### Amendment 001 — SF-1 / SF-2 / SF-3（人工 PLAN_APPROVED 后吸收；无需二次 Plan Review）

- 日期：2026-08-13
- SF-1：§8.8 纯扩展候选 RET-002 标量字段全部 `None`；新增 U22
- SF-2：§14.1 `governance_file_whitelist` 供 Release Operator 各 phase
- SF-3：§14.2 `PLAN_LANDING` 三文件 `docs(plan)` commit 契约
- 是否影响技术规格：否
- 审批状态：PLAN_APPROVED（人工确认）

## 25. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 11:50 UTC | planning | 创建 Task Plan；更新 progress/master_plan 规划态 | — | planning only；未 Git 写 |

## 26. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| — | 待实施 |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | — | 待实施 |
| Integration | — | 待实施 |
| Ruff | — | 待实施 |
| Mypy | — | 待实施 |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 0
review_report: null
```

### Git 记录

```yaml
branch: null
plan_commit: null
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`planned`
