# RET-001 BM25 关键词召回

## 1. 任务信息

```yaml
task_id: RET-001
task_name: BM25 关键词召回
status: approved
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "a780bb2d6ae6d0e47d22f508326aed8f0e4fb7ab"
branch: "feat/RET-001-bm25-retrieval"
created_at: "2026-08-13 01:40 UTC"
updated_at: "2026-08-13 01:40 UTC"
spec_sections:
  - "§2.2.4 Elasticsearch Retrieval Index 数据结构（只读消费 Alias；不创建 Mapping）"
  - "§2.2.7 BM25 关键词召回（本任务唯一权威范围）"
  - "§3.6 全异步客户端（elasticsearch AsyncElasticsearch）"
  - "§3.24 连接池、超时与重试"
  - "§3.28 测试策略（Integration + ES Fixture）"
prerequisites:
  formal:
    - "DEV-004 — SATISFIED/completed; migration 003 memory_retrieval_v1 + alias memory_retrieval_current"
    - "DEV-007 — SATISFIED/completed; create_embedding_client + SiliconFlowEmbeddingClient（BM25 不调用 embed）"
    - "EXT-007 — SATISFIED/completed; MemoryIndexDocument + RetrievalIndexWriteRepository 生产写入路径已接线（非 RET-001 测试硬前置）"
  implementation_reuse:
    - "MemoryIndexDocument (domain/models/retrieval_index_sync.py) — ES Fixture 文档契约"
    - "MemoryRetrievalSettings.index_name / bm25_top_n (settings/models.py)"
    - "RetrievalIndexWriteRepository.bulk_upsert — Integration Fixture 写入复用（只读调用方）"
    - "AsyncElasticsearch in AppState / integration es_client fixture 模式"
    - "compose.test.yaml + scripts/migrate — Migration 003 前置"
  baseline_evidence:
    branch: "main"
    head: "a780bb2d6ae6d0e47d22f508326aed8f0e4fb7ab"
    working_tree_at_planning_start: "clean before planning whitelist writes"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=a780bb2d6ae6d0e47d22f508326aed8f0e4fb7ab"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "PLAN_APPROVED — human confirmed 2026-08-13"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: false
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create the exact feature branch feat/RET-001-bm25-retrieval"
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
  - "创建或修改 Elasticsearch Mapping/Alias（DEV-004 已完成）"
  - "触碰 DEV-006 / PR #13"
stop_if:
  - "任何实现步骤需要新增 HTTP API 路由或 Retrieval API 错误码（归属 RET-005）"
  - "任何实现步骤需要 Query 标准化、Embedding、Vector、RRF、Neo4j 读回或 ACT-R 评分"
  - "任何实现步骤需要 durable 写入（Mongo/Neo4j/ES/Kafka）"
  - "任何实现步骤需要新依赖或 Migration"
  - "任何实现步骤需要修改 EXT-007 写入语义或 MemoryIndexDocument Schema"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-008
```

## 2. authoritative_scope

本任务 **仅** 拥有 §2.2.7 BM25 关键词召回通道，作为内部 Service/Repository；**不** 拥有 HTTP API、Query 标准化、Embedding、多通道融合或图谱扩展。

| 维度 | 归属 RET-001 | 非 RET-001（显式排除） |
|---|---|---|
| ES BM25 `multi_match` 查询 | **是** — alias `settings.memory_retrieval.index_name` | — |
| `user_id` / `memory_type` / `status` Filter | **是** — 按 §2.2.7 精确构建 | — |
| 字段权重 `search_text^2.0, content^1.0, predicate^0.5` | **是** | — |
| `size=bm25_top_n`（默认 30）；`_source=false` | **是** | — |
| 内部输出 `memory_id` + 1-based `rank` + ES `_score` | **是** — 供 RET-002 RRF | — |
| Query 标准化（§2.2.6） | **否** — 调用方传入已标准化 `query` | **RET-002** |
| Query Embedding / Vector kNN | **否** | **RET-002** |
| RRF 融合 | **否** | **RET-002** |
| Neo4j 权威回读 / 一跳扩展 / MGET | **否** | **RET-003** |
| ACT-R 评分 / Evidence 聚合 | **否** | **RET-004** |
| HTTP Retrieval API / 降级矩阵 / `bm25_retrieval_failed` Warning | **否** | **RET-005** |
| `retrieval_count` 等统计更新 | **否** | **RET-005** |
| ES Mapping/Alias 创建 | **否** | **DEV-004** |
| Retrieval Index Document 同步写入 | **否** | **EXT-007** |
| EXT-007 pipeline 硬依赖（Integration 测试） | **否** — 直接写 ES Fixture | **RET-006** E2E 验证写入→可检索 |

## 3. 任务目标

实现 §2.2.7 BM25 关键词召回内部通道：对 Alias `memory_retrieval_current` 执行只读 Elasticsearch 搜索，应用强制 `user_id` 隔离与可选 `memory_type`/`status` 过滤，返回最多 `bm25_top_n` 条候选及其 1-based 排名与 Elasticsearch 原始分数，供 RET-002 RRF 融合消费。

可验证目标：

1. **`Bm25RetrievalService`** 暴露内部 `search(Bm25RetrievalQuery) -> Bm25RetrievalOutcome`；**不** 调用 Embedding；**不** 执行 Query 标准化。
2. **`Bm25RetrievalRepository`** 构建并执行 §2.2.7 精确 ES Query；索引名来自 `settings.memory_retrieval.index_name`；**禁止** 硬编码物理 Index 名。
3. **Filter 语义**：`user_id` 必填；`memory_types` 缺省或空 → 省略 `memory_type` terms；`status` 默认仅 `active`；`include_conflicted` / `include_history` 按规格扩展允许集合。
4. **输出语义**：每条命中含 `memory_id`（来自 hit `_id`）、`rank`（1-based 顺序）、`score`（hit `_score`）；不返回 `_source` 字段内容。
5. **失败语义**：ES 异常/畸形响应 → 通道失败（`Bm25RetrievalFailure`）；**不** 抛 HTTP 层 `bm25_retrieval_failed`（归属 RET-005 降级 Warning）。
6. **只读**：零 durable 写入；同一查询可重复执行且结果确定（索引不变前提下）。
7. **Integration 测试**：Migration 003 后**直接 bulk upsert 固定 ES Fixture**（复用 `MemoryIndexDocument`），**不** 硬依赖 EXT-007 pipeline 或 Neo4j。

## 4. 非目标与黑名单（must_not）

- **Query 标准化**（Unicode NFKC、空格压缩等）— 归属 RET-002/RET-005。
- **Query Embedding / Vector 召回 / RRF** — 归属 RET-002。
- **Neo4j 读回 / 图扩展 / MGET** — 归属 RET-003。
- **ACT-R 评分 / Evidence 聚合** — 归属 RET-004。
- **HTTP Retrieval API / API Key 鉴权 / `top_k` 截断 / Warning 矩阵** — 归属 RET-005。
- **`retrieval_count` / `last_retrieved_time` 统计更新** — 归属 RET-005。
- **创建或修改 Elasticsearch Mapping/Alias** — 归属 DEV-004；缺失时通道失败，本任务不修复。
- **修改** `MemoryIndexDocument` Schema、`RetrievalIndexWriteRepository` 写入语义、EXT-007 服务。
- **硬依赖 EXT-007 pipeline** 作为 Integration 测试前置。
- **DEV-006 / PR #13**。
- **新依赖 / Migration / Settings Contract 变更**。
- **reranking、检索缓存、search analytics、reindex jobs、speculative personalization**。
- **Session→Consolidation 全链路 E2E**（归属 RET-006 / E2E-001）。

## 5. 当前代码状态与前置检查

### 5.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `a780bb2d6ae6d0e47d22f508326aed8f0e4fb7ab`（与用户给定 `planning_baseline_main` 一致） |
| `git status --short` | 空 |
| DEV-004 | `completed`；`003_elasticsearch_memory_v1` + alias `memory_retrieval_current` |
| DEV-007 | `completed`；`create_embedding_client`（本任务不调用） |
| EXT-007 | `completed`；`MemoryIndexDocument` + `RetrievalIndexWriteRepository` |
| BM25 检索实现 | **不存在** — `rg bm25` 仅命中 settings/规格/规划 |
| workflow | `NORMAL`，explicit |

### 5.2 已存在可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| `MemoryIndexDocument` | `domain/models/retrieval_index_sync.py` | ES Fixture 文档形状 |
| `RetrievalIndexWriteRepository` | `infrastructure/elasticsearch/retrieval_index_write_repository.py` | Integration Fixture bulk upsert |
| `MemoryRetrievalSettings` | `settings/models.py` | `index_name`, `bm25_top_n`, `elasticsearch_timeout_seconds` |
| ES integration fixture | `tests/integration/test_ext007_retrieval_index_sync.py` | `es_client`、`_clean_stores`、`test_infra` 模式 |
| Migration 003 | `scripts/migrations/003_elasticsearch_memory_v1.py` | Mapping/Alias 只读对照 |

### 5.3 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无 BM25 领域模型 | `domain/models/` 无 `bm25_retrieval` |
| 无 BM25 服务/仓储 | `rg Bm25Retrieval` 无命中 |
| 无 BM25 单元/集成测试 | `tests/` 无 `test_ret001` / `test_bm25` |

**结论**：RET-001 新建领域模型、服务、ES 只读仓储及对应测试；复用 EXT-007 文档契约与写入仓储作 Fixture 种子；不修改 EXT-007 生产语义。

## 6. request_contract（内部 — 非 HTTP）

```text
Bm25RetrievalQuery {
  user_id: str                    # 必填；非空
  query: str                       # 必填；非空；调用方已标准化（本任务不做 §2.2.6）
  memory_types: list[str] | None   # 可选；缺省或 [] 表示不限制类型
  include_conflicted: bool = false
  include_history: bool = false
}
```

| 字段 | 校验（内部 Service 层） | 说明 |
|---|---|---|
| `user_id` | 非空 `str`；strip 后不得为空 | 所有 ES Filter 必须含此值 |
| `query` | 非空 `str`；strip 后不得为空 | 直接传入 `multi_match.query`；字符/token 上限由 RET-005 负责 |
| `memory_types` | `None` 或 `list[str]`；若非空则元素 ⊆ `{fact, preference, event, profile}`；去重后若为空则视为不限制 | 与 §2.2.5 #4–#5 对齐；**省略** ES `memory_type` terms |
| `include_conflicted` | `bool`，默认 `false` | 见 §7.3 status 矩阵 |
| `include_history` | `bool`，默认 `false` | 见 §7.3 status 矩阵 |

**禁止**：在本任务引入 HTTP Request DTO、`top_k`、`graph_expand` 或 API Key 字段。

## 7. response_contract（内部 — 非 HTTP）

```text
Bm25RetrievalHit {
  memory_id: str      # Elasticsearch document _id（= §2.2.4 memory_id）
  rank: int           # 1-based，按 ES hits 顺序
  score: float        # Elasticsearch 原始 _score
}

Bm25RetrievalSuccess {
  user_id: str
  hits: list[Bm25RetrievalHit]   # 长度 0..bm25_top_n
  total_hits: int                # len(hits)；MVP 不解析 ES total relation
}

Bm25RetrievalFailure {
  kind: Literal["channel_failure"] = "channel_failure"
  message: str                    # 不含 query 原文、不含 ES 响应体敏感字段
  retryable: bool                  # ES 超时/5xx → true；畸形响应/4xx → false（实现按异常类型映射）
}

Bm25RetrievalOutcome {
  outcome: Literal["success", "failure"]
  success: Bm25RetrievalSuccess | None
  failure: Bm25RetrievalFailure | None
}
```

| 场景 | 输出 |
|---|---|
| ES 正常返回（含 0 命中） | `outcome=success`；`hits` 可为 `[]` |
| ES 抛错/超时/畸形响应 | `outcome=failure`；`kind=channel_failure` |
| 入参校验失败 | Service 层 `ValueError`（单元测试覆盖）；**不** 映射为 HTTP 4xx（无 HTTP 层） |

**禁止**：在本任务返回 `bm25_retrieval_failed`、`retrieval_unavailable`、`retrieval_mode` 或 RRF 字段。

## 8. retrieval_query_contract（精确 ES 结构）

### 8.1 请求模板

```json
POST {settings.memory_retrieval.index_name}/_search
{
  "size": <settings.memory_retrieval.bm25_top_n>,
  "_source": false,
  "query": {
    "bool": {
      "filter": <FILTER_ARRAY>,
      "must": {
        "multi_match": {
          "query": "<Bm25RetrievalQuery.query>",
          "fields": ["search_text^2.0", "content^1.0", "predicate^0.5"]
        }
      }
    }
  }
}
```

### 8.2 `FILTER_ARRAY` 构建规则（顺序固定）

1. **恒含** `{"term": {"user_id": "<user_id>"}}`
2. **若** `memory_types` 非 `None` 且去重后非空：追加 `{"terms": {"memory_type": [<deduped types>]}}`
3. **status**（§7.3 矩阵）：追加单个 `term` 或 `terms` Filter
4. **禁止** 生成 `memory_type` 的空数组 `terms` Filter

### 8.3 status Filter 矩阵（§2.2.7）

| `include_conflicted` | `include_history` | ES Filter |
|---|---|---|
| `false` | `false` | `{"term": {"status": "active"}}` |
| `true` | `false` | `{"terms": {"status": ["active", "conflicted"]}}` |
| `false` | `true` | `{"terms": {"status": ["active", "superseded"]}}` |
| `true` | `true` | `{"terms": {"status": ["active", "conflicted", "superseded"]}}` |

### 8.4 响应解析

| ES 字段 | 映射 |
|---|---|
| `hits.hits[i]._id` | `Bm25RetrievalHit.memory_id` |
| `hits.hits[i]._score` | `Bm25RetrievalHit.score`（**必须**为有效数值；缺失或非数值 → 整次响应视为畸形，返回 `channel_failure` `retryable=false`；**禁止**静默 `score=0`） |
| 命中顺序 `i` | `Bm25RetrievalHit.rank = i + 1` |

- 使用 `AsyncElasticsearch.search`；`request_timeout=settings.memory_retrieval.elasticsearch_timeout_seconds`。
- **禁止** 请求 `_source` 字段或 `stored_fields`（MVP 仅需 `_id` + `_score`）。
- **禁止** 在 Repository 硬编码 `memory_retrieval_v1` 或 `memory_retrieval_current` 字面量（必须读 settings）。

## 9. user_isolation

| 规则 |  enforcement |
|---|---|
| 每次查询 Filter **必须** 含 `user_id` term | Repository 构建 Query 时无条件注入；单元测试断言 ES body |
| 禁止跨用户批量检索 | `Bm25RetrievalQuery` 仅接受单个 `user_id` |
| Integration 交叉用户隔离 | Fixture 为 `user_a` / `user_b` 写入同名关键词文档；以 `user_a` 查询不得返回 `user_b` 的 `memory_id` |
| 日志 | 可记录 `user_id`、命中数、耗时；**禁止** 记录 `query` 全文（对齐 §B.11 脱敏 posture） |

## 10. durable_write_scope

```yaml
durable_write_scope: NONE
```

| 存储 | 读写 | 说明 |
|---|---|---|
| Elasticsearch | **只读** `_search` | 测试 Fixture 写入仅发生在 `tests/**`，非生产 Service 路径 |
| MongoDB | 无 | — |
| Neo4j | 无 | — |
| Kafka | 无 | — |
| Redis | 无 | — |

## 11. failure_mapping

| 失败源 | 基础设施异常 | Service `Bm25RetrievalOutcome` | 备注 |
|---|---|---|---|
| ES 连接失败 / 超时 | `Bm25RetrievalError`（新建，对齐 `RetrievalIndexWriteError` 模式） | `failure.channel_failure`；`retryable=true` | RET-002 可据此降级 |
| ES HTTP 5xx | 同上 | `channel_failure`；`retryable=true` | — |
| ES HTTP 4xx / 畸形响应体 | `Bm25RetrievalError` | `channel_failure`；`retryable=false` | — |
| 入参非法（空 user_id/query、非法 memory_type） | `ValueError` | 不包装为 outcome | 单元测试 |
| Alias/Index 不存在 | `Bm25RetrievalError` | `channel_failure` | 不创建 Mapping |

**显式禁止**（RET-001 内部）：

- **不得** 抛出或返回 HTTP 错误码 `bm25_retrieval_failed`（§2.2.15 Warning；仅当 Vector 成功时由 RET-005 产生）。
- **不得** 抛出 `retrieval_unavailable`（双通道均失败；RET-005）。
- **不得** 伪造空成功掩盖 ES 失败。

## 12. replay_idempotency

| 场景 | 预期行为 | 依据 |
|---|---|---|
| 相同 `Bm25RetrievalQuery` 重复调用 | 相同命中集与 rank/score（索引不变） | 只读查询天然幂等 |
| ES Fixture 不变 | Integration 断言确定性排序 | §3.28 |
| 并发相同查询 | 无写冲突；各调用独立 | 无事务 |
| 进程重启后重试 | 行为与首次一致 | 无本地状态 |

## 13. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/bm25_retrieval.py` | 创建 | `Bm25RetrievalQuery` / `Hit` / `Outcome` 模型 |
| `src/memory_system/domain/services/bm25_retrieval_service.py` | 创建 | 编排 + `create_bm25_retrieval_service` factory |
| `src/memory_system/infrastructure/elasticsearch/bm25_retrieval_repository.py` | 创建 | ES Query 构建 + `search` + `Bm25RetrievalError` |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `settings/`、`entrypoints/`、EXT-007 文件）。

## 14. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_bm25_retrieval_query_builder.py` | 创建 | Filter/status/memory_types Query body 单元测试 |
| `tests/unit/test_bm25_retrieval_service.py` | 创建 | Service 编排 + 失败映射（Fake Repository） |
| `tests/integration/test_ret001_bm25_retrieval.py` | 创建 | compose.test + ES Fixture 集成测试 |
| `tests/support/ret001_es_fixtures.py` | 创建 | 固定 `MemoryIndexDocument` 种子与 helper |

**白名单外任何 `tests/**` 变更 → FAIL**（除非 Plan Amendment 授权）。

可选：若 Query builder 测试与服务测试合并，允许 **仅保留** `test_bm25_retrieval_service.py` 一个文件覆盖 builder + service（二选一，实施时不得超出两文件之和）。

## 15. 实现方案

### Step 1 — 领域模型 `bm25_retrieval.py`

- **文件**：`src/memory_system/domain/models/bm25_retrieval.py`
- **类型**：`Bm25RetrievalQuery`、`Bm25RetrievalHit`、`Bm25RetrievalSuccess`、`Bm25RetrievalFailure`、`Bm25RetrievalOutcome`
- **约束**：`ConfigDict(strict=True, extra="forbid")`；与 §6–§7 一致
- **幂等**：纯数据模型

### Step 2 — ES 仓储 `bm25_retrieval_repository.py`

- **文件**：`src/memory_system/infrastructure/elasticsearch/bm25_retrieval_repository.py`
- **类**：`Bm25RetrievalRepository`
- **方法**：
  - `build_search_body(query: Bm25RetrievalQuery, *, size: int) -> dict[str, Any]` — 可单测
  - `async def search(query: Bm25RetrievalQuery, *, index_name: str, size: int, request_timeout: float) -> list[Bm25RetrievalHit]`
- **异常**：`Bm25RetrievalError`（继承 `Exception`；消息不含 query 原文）
- **错误处理**：捕获 `elasticsearch` 异常 → `Bm25RetrievalError`；校验 `hits.hits` 结构

### Step 3 — 领域服务 `bm25_retrieval_service.py`

- **文件**：`src/memory_system/domain/services/bm25_retrieval_service.py`
- **类**：`Bm25RetrievalService`
- **方法**：`async def search(query: Bm25RetrievalQuery) -> Bm25RetrievalOutcome`
- **逻辑**：入参校验 → 读 `settings.memory_retrieval.bm25_top_n` / `index_name` / timeout → 调用 Repository → 成功/失败 Outcome
- **Factory**：`create_bm25_retrieval_service(elasticsearch, *, settings: Settings) -> Bm25RetrievalService`

### Step 4 — 单元测试

- Query builder：四种 status 矩阵；`memory_types` 省略/非空；`user_id` term 恒存在
- Service：Fake Repository 成功/失败/空结果；`ValueError` 入参

### Step 5 — Integration 测试 + Fixture

- **文件**：`tests/support/ret001_es_fixtures.py`
  - `make_memory_index_document(...)` — 生成合法 `MemoryIndexDocument`（含 1024 维 dummy embedding）
  - `seed_ret001_bm25_fixtures(write_repo, index_alias, ...)` — 多用户、多 status、多 memory_type 文档集
- **文件**：`tests/integration/test_ret001_bm25_retrieval.py`
  - 复用 `test_ext007` 的 `test_infra` / `es_client` 模式（可复制最小 fixture 或 import 共享 conftest — **若需** 提取共享 conftest 必须列入 Amendment，默认复制最小 autouse clean）
  - Migration 003 已执行前提下 bulk upsert Fixture
  - 覆盖 §16 集成场景

## 16. 测试计划

### 16.1 Unit Test

| ID | 场景 | 预期 |
|---|---|---|
| U1 | 默认 filters（active only，无 memory_types） | ES body 含 `user_id` term + `status:active`；无 `memory_type` terms |
| U2 | `memory_types=["fact","event"]` | `terms memory_type` 存在 |
| U3 | `memory_types=[]` 或 `None` | 省略 `memory_type` terms |
| U4 | status 矩阵四组合 | 与 §8.3 表一致 |
| U5 | `multi_match` fields 权重 | 精确 `search_text^2.0, content^1.0, predicate^0.5` |
| U6 | `size` 来自 settings | 等于 `bm25_top_n` |
| U7 | 解析 3 条 hits | `rank` 1..3；`memory_id`=_id；`score`=_score |
| U8 | Repository ES 异常 | `Bm25RetrievalError` |
| U9 | Service 包装失败 | `outcome=failure`，`kind=channel_failure` |
| U10 | 空 user_id / 空 query | `ValueError` |

### 16.2 Contract Test

| ID | 场景 | 预期 |
|---|---|---|
| C1 | ES search body 与 §8.1 结构一致 | snapshot/断言 |
| C2 | 不修改 `MemoryIndexDocument` / EXT-007 写入文件 | `git diff` 白名单 |
| C3 | index_name 来自 settings 非硬编码 | grep `memory_retrieval_v1`/`memory_retrieval_current` **仅限** §13 production_file_whitelist 三文件；`settings/models.py` 默认值合法 |

### 16.3 Integration Test

| ID | 场景 | 预期 |
|---|---|---|
| I1 | Happy path：关键词命中排序 | 返回 ≥1 hit；rank 递增；score > 0 |
| I2 | 交叉用户隔离 | `user_b` 文档不可被 `user_a` 查到 |
| I3 | `memory_types` 过滤 | 仅 fact 文档命中 |
| I4 | 默认 status=active | `conflicted`/`superseded` 不命中 |
| I5 | `include_conflicted=true` | conflicted 可命中 |
| I6 | `include_history=true` | superseded 可命中 |
| I7 | 空结果 | `hits=[]`，`outcome=success` |
| I8 | `bm25_top_n` 限制 | 种子 >N 文档时仅返回 N 条 |
| I9 | ES 不可用（可选 skip/mock） | `channel_failure` 或 pytest skip 若栈未起 |

### 16.4 E2E Test

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — 写入→检索全链路归属 RET-006 |

### 16.5 失败注入与并发测试

| ID | 场景 | 预期 |
|---|---|---|
| F1 | Fake Repository `fail_on_search=True` | `channel_failure` |
| F2 | 并发 10 路相同只读查询 | 无异常；结果一致 |

## 17. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 单次只读 `_search`；无多资源写 |
| 幂等 | **是** | 相同输入 + 稳定索引 → 相同输出 |
| 并发 | 只读无锁 | ES 侧并发查询安全 |
| 版本冲突 | 不适用 | 无乐观锁 |
| 用户隔离 | **强制** | `user_id` term 不可省略 |
| 部分失败 | 不适用 | 单请求单响应 |
| 进程异常恢复 | 不适用 | 无 in-flight 写状态 |

## 18. 验收标准

- [ ] `Bm25RetrievalService.search` 实现 §2.2.7 BM25 语义；只读；零 durable 写
- [ ] ES Query 与 §8 完全一致（filter、multi_match、size、_source=false）
- [ ] 输出 `memory_id` + 1-based `rank` + ES `_score`
- [ ] `user_id` 隔离经单元 + 集成双重验证
- [ ] ES 失败映射为 `channel_failure`；**不** 使用 `bm25_retrieval_failed`
- [ ] Integration 使用 ES Fixture；**不** 依赖 EXT-007 pipeline
- [ ] 不修改 DEV-004 Mapping/Alias；不触碰 DEV-006/PR#13
- [ ] scoped unit + integration 全通过
- [ ] Ruff / Mypy（变更文件）通过
- [ ] Review 无 P0/P1
- [ ] `dependency_changes_expected=NONE`；`migration_changes_expected=NONE`

## 19. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | 无；范围与 master_plan §RET-001、规格 §2.2.7 一致 |
| 前置任务 | DEV-004、DEV-007 completed；EXT-007 非测试硬前置 |
| 主要风险 | ① 误实现 Query 标准化/Vector；② 硬编码 index 名；③ 测试误依赖 Neo4j pipeline |
| 非阻塞 | OI-008（RET-005 API 编辑性；不阻塞 BM25 内部通道） |
| DEV-006 | **禁止触碰** PR#13 |

## 20. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/RET-001-bm25-retrieval"
baseline_main: "a780bb2d6ae6d0e47d22f508326aed8f0e4fb7ab"
expected_commits:
  - "docs(plan): add RET-001 bm25 retrieval plan (includes progress.md + master_plan.md planning metadata)"
  - "feat(ret): add bm25 keyword retrieval channel"
  - "docs(status): record RET-001 implementation commit and PR"
  - "docs(status): complete RET-001 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "EXT-007 write path / MemoryIndexDocument schema"
  - "DEV-004 mapping/alias"
  - "HTTP API / RET-005 warnings"
  - "Query normalization / Embedding / Vector / RRF / Neo4j / ACT-R"
  - "Migration / dependency / Settings"
```

## 21. mvp_local_decisions

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | `memory_id` 取自 ES hit `_id`，不请求 `_source` | §2.2.4 Document ID = `memory_id`；§2.2.7 `_source=false` |
| LD-2 | 入参 `query` 视为已标准化；本任务不实现 §2.2.6 | 用户明确 RET-002 拥有 query norm/embedding |
| LD-3 | 通道失败使用 `Bm25RetrievalFailure.kind=channel_failure`；**不** 复用 `bm25_retrieval_failed` 字符串 | API Warning 归属 RET-005；避免 RET-002 误用 HTTP 码 |
| LD-4 | Integration Fixture 经 `RetrievalIndexWriteRepository.bulk_upsert` 写入；不跑 EXT-007 | master_plan：不硬依赖 EXT-007 |
| LD-5 | `Bm25RetrievalError` 对齐 `RetrievalIndexWriteError` 基础设施异常模式 | 既有 ES 仓储惯例 |
| LD-6 | `total_hits=len(hits)`；不解析 ES `hits.total` relation | MVP 仅需 top-N 候选；RRF 只用 rank |

## 22. deferred_for_mvp

| 项 | 说明 |
|---|---|
| Query 标准化 + Embedding | RET-002 |
| Vector 召回 + RRF | RET-002 |
| Neo4j 权威回读 + 一跳扩展 + MGET | RET-003 |
| ACT-R 评分 + Evidence 聚合 | RET-004 |
| HTTP Retrieval API + 降级/超时 + `bm25_retrieval_failed` Warning | RET-005 |
| `retrieval_count` 统计更新 | RET-005 |
| EXT-007 写入→BM25 全链路 E2E | RET-006 |
| reranking / hybrid 调参 / 检索缓存 | 规格外 |
| search analytics / reindex jobs | 规格外 |
| speculative personalization | 规格外 |
| Session→Consolidation E2E | E2E-001 / OPS |
| conversational retrieval | 规格外 |

## 23. open_issues

| ID | 关系 | 阻塞 RET-001？ |
|---|---|---|
| OI-008 | RET-005 API 编辑性 | **否** — 不阻塞 BM25 内部实现 |

## 24. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：2026-08-13
- 原计划：§8.4 允许 `_score` 缺失时选 `0.0` 或失败；C3 grep 全仓库；PLAN_LANDING commit 未显式列出治理文件
- 修改内容：
  - **SF-1**：PLAN_LANDING `docs(plan)` commit 必须同时包含 `02_开发管理/tasks/RET-001-bm25-retrieval.md`、`02_开发管理/progress.md`、`02_开发管理/master_plan.md`
  - **SF-2**：C3 硬编码 index 检查仅限 §13 production_file_whitelist 三文件
  - **SF-3**：hit 缺少有效数值 `_score` → 畸形 ES 响应 → `channel_failure` `retryable=false`；禁止 `score=0` 静默替代
- 修改原因：Plan Review SHOULD_FIX；人工批准吸收，无需二次 Plan Review
- 是否影响技术规格：**否**
- 审批状态：PLAN_APPROVED（人工确认）

## 25. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 01:40 UTC | planning | 创建 Task Plan；更新 progress/master_plan 规划态 | — | planning only；未 Git 写 |

## 26. 实际执行结果

### 实际修改文件

（实施前留空）

### 与原计划的差异

暂无。

### 测试结果

（实施前留空）

### Review 结果

```yaml
p0: null
p1: null
p2: null
p3: null
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

`approved`
