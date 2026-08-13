# RET-002 Vector 召回 + RRF 融合

## 1. 任务信息

```yaml
task_id: RET-002
task_name: Vector 召回 + RRF 融合
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "e5f5c9de9883d04759f19080c01f1f50d2c62513"
branch: "feat/RET-002-vector-retrieval-rrf"
created_at: "2026-08-13 02:40 UTC"
updated_at: "2026-08-13 03:15 UTC"
spec_sections:
  - "§2.2.6 Query 标准化与 Embedding（RET-002 拥有检索内部路径的 query norm + single-query embed）"
  - "§2.2.8 Vector 语义召回（本任务 Vector 通道权威范围）"
  - "§2.2.9 RRF 多路结果融合（本任务 RRF 权威范围）"
  - "§3.6 全异步客户端（elasticsearch AsyncElasticsearch、httpx EmbeddingClient）"
  - "§3.24 连接池、超时与重试（只读消费既有 Settings timeout）"
  - "§3.28 测试策略（Integration + ES Fixture + Fake Embedding）"
prerequisites:
  formal:
    - "RET-001 — SATISFIED/completed; PR #44 MERGED; Bm25RetrievalService + Bm25RetrievalRepository + domain models"
    - "DEV-007 — SATISFIED/completed; create_embedding_client + SiliconFlowEmbeddingClient + EmbeddingClient Protocol; dimension=1024"
    - "DEV-004 — SATISFIED/completed; migration 003 memory_retrieval_v1 + alias memory_retrieval_current（dense_vector embedding 字段）"
    - "EXT-007 — SATISFIED/completed; MemoryIndexDocument.embedding (1024 dims) + RetrievalIndexWriteRepository（Integration Fixture 写入复用；非硬前置 pipeline）"
  implementation_reuse:
    - "Bm25RetrievalService.search(Bm25RetrievalQuery) -> Bm25RetrievalOutcome（RET-001；本任务编排调用，不修改语义）"
    - "normalize_search_text_fragment (domain/services/core_search_text.py) — NFKC + strip + whitespace compress"
    - "create_embedding_client + EmbeddingClient.embed (infrastructure/embedding/factory.py)"
    - "MemoryIndexDocument + RetrievalIndexWriteRepository.bulk_upsert — Integration Fixture"
    - "MemoryRetrievalSettings: vector_top_n=30, vector_num_candidates=100, fused_top_n=30, rrf_k=60, embedding_timeout_seconds, elasticsearch_timeout_seconds"
    - "FakeEmbeddingClient pattern (tests/support/fake_retrieval_index_embedding_client.py)"
  baseline_evidence:
    branch: "main"
    head: "e5f5c9de9883d04759f19080c01f1f50d2c62513"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=e5f5c9de9883d04759f19080c01f1f50d2c62513"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "PLAN_APPROVED — human confirmed 2026-08-13"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create the exact feature branch feat/RET-002-vector-retrieval-rrf"
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
  - "复活 TEI /tokenize 路径或修改 DEV-007 SiliconFlow 客户端语义"
stop_if:
  - "任何实现步骤需要 Neo4j 读回、图谱扩展或 MGET（RET-003）"
  - "任何实现步骤需要 ACT-R 评分或 Evidence 聚合（RET-004）"
  - "任何实现步骤需要 HTTP Retrieval API、Warning 矩阵或 retrieval_count 统计（RET-005）"
  - "任何实现步骤需要 durable 写入（Mongo/Neo4j/ES/Kafka）"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要修改 EXT-007 写入语义或 MemoryIndexDocument Schema"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-008
```

## 2. authoritative_scope

本任务 **仅** 拥有检索内部路径的 Query 标准化、Query Embedding（复用 DEV-007）、Vector ES kNN 召回、BM25+Vector 并行编排与 RRF 融合；**不** 拥有 HTTP API、Neo4j 权威回读、ACT-R 或统计更新。

| 维度 | 归属 RET-002 | 非 RET-002（显式排除） |
|---|---|---|
| Query 标准化（§2.2.6 NFKC/trim/空格压缩） | **是** — 检索内部路径 `normalize_retrieval_query` | HTTP 层 re-validate（RET-005） |
| 单条 Query Embedding（`texts=[normalized_query]`） | **是** — 经 `EmbeddingClient` / `create_embedding_client` | 索引同步批量 embed（EXT-007） |
| ES kNN on `embedding` 字段 | **是** — 同 BM25 的 user_id/memory_type/status filters | — |
| Vector 通道输出 memory_id + 1-based rank + ES `_score` | **是** | — |
| BM25 + Vector 并行；Vector 等 Embedding；BM25 不等 Embedding | **是** — `HybridRetrievalService` | — |
| RRF 融合、retrieval_mode、normalized_retrieval_score | **是** — 内部表示 | HTTP Response 字段映射（RET-005） |
| 内部 `retrieval_unavailable`（双通道均失败） | **是** — 内部 Outcome；**非** HTTP 错误码 | HTTP `retrieval_unavailable`（RET-005） |
| BM25 ES Query 构建与执行 | **否** — 调用 RET-001 `Bm25RetrievalService` | RET-001 拥有；本任务仅编排 |
| Neo4j 权威回读 / 一跳扩展 / MGET | **否** | **RET-003** |
| ACT-R 评分 / Evidence 聚合 | **否** | **RET-004** |
| HTTP API / Warning（`embedding_failed`、`vector_skipped_query_too_long`、`bm25_retrieval_failed`） | **否** | **RET-005** |
| `retrieval_count` 统计更新 | **否** | **RET-005** |
| ES Mapping/Alias 创建 | **否** | **DEV-004** |
| EXT-007 pipeline 硬依赖（Integration 测试） | **否** — 直接写 ES Fixture | **RET-006** |

## 3. 任务目标

实现 §2.2.6（检索路径）、§2.2.8 Vector 语义召回与 §2.2.9 RRF 多路融合的内部 Service 层：对同一 `user_id` 查询并行执行 BM25（RET-001）与 Vector（Embedding + kNN），按 RRF 合并为最多 `fused_top_n` 条候选，输出 `retrieval_mode`、每候选 `bm25_rank`/`vector_rank`/`retrieval_source`/`rrf_score`/`normalized_retrieval_score`/`min_available_rank`；零 durable 写入。

可验证目标：

1. **`normalize_retrieval_query`** 实现 §2.2.6 标准化规则（复用 `normalize_search_text_fragment`）。
2. **`HybridRetrievalService`** 拥有 Query Embedding：`embed(texts=[normalized_query])` 后构造 `VectorRetrievalQuery`；**`VectorRetrievalService` 仅 ES kNN**（接收 `query_vector`；不调用 Embedding）。
3. **`HybridRetrievalService`** 并行启动 BM25 与 Vector 路径；Vector 路径等待 Embedding；BM25 使用 **normalized** query（`Bm25RetrievalQuery.query = normalized_query`）；单通道失败降级；双通道失败 → 内部 `retrieval_unavailable`。
4. **`fuse_rrf`** 纯函数实现 §2.2.9 精确算法、排序、归一化与 `retrieval_mode`。
5. **Integration 测试**：ES Fixture（含差异化 embedding）+ Fake Embedding；不硬依赖 EXT-007 pipeline 或真实 SiliconFlow。
6. **RET-001 回归**：既有 BM25 unit/integration 测试全部通过（语义不变）。

## 4. 非目标与黑名单（must_not）

- Neo4j 读回 / 图扩展 / MGET — **RET-003**。
- ACT-R 评分 / Evidence / 最终 `score` — **RET-004**。
- HTTP Retrieval API / API Key / `top_k` 截断 / Warning 矩阵 — **RET-005**。
- `retrieval_count` / `last_retrieved_time` — **RET-005**。
- ES Mapping/Alias 创建或修改 — **DEV-004**。
- 修改 `MemoryIndexDocument` Schema、`RetrievalIndexWriteRepository` 写入语义。
- **DEV-006 / PR #13**；不得实现或接线 `TEIEmbeddingClient`。
- 新依赖 / Migration / Settings Contract 变更。
- reranking、检索缓存、LLM query rewrite、停用词删除。
- Session→Consolidation 全链路 E2E — **RET-006 / E2E-001**。

## 5. 当前代码状态与前置检查

### 5.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `e5f5c9de9883d04759f19080c01f1f50d2c62513`（与用户给定 `planning_baseline_main` 一致） |
| `git status --short` | 空 |
| RET-001 | `completed`；PR #44 MERGED；`Bm25RetrievalService` / `Bm25RetrievalRepository` 已落盘 |
| DEV-007 | `completed`；`create_embedding_client` + `SiliconFlowEmbeddingClient` |
| EXT-007 | `completed`；`MemoryIndexDocument.embedding` 1024 维 |
| Vector / RRF 实现 | **不存在** — `rg VectorRetrieval|fuse_rrf|HybridRetrieval` 无生产命中 |
| workflow | `NORMAL`，explicit |

### 5.2 已存在可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| `Bm25RetrievalService` | `domain/services/bm25_retrieval_service.py` | 并行 BM25 通道 |
| `Bm25RetrievalRepository` | `infrastructure/elasticsearch/bm25_retrieval_repository.py` | Filter 逻辑来源（拟提取共享 builder） |
| `normalize_search_text_fragment` | `domain/services/core_search_text.py` | Query NFKC 标准化 |
| `create_embedding_client` | `infrastructure/embedding/factory.py` | Query Embedding 工厂 |
| `EmbeddingClient` / `EmbeddingResult` | `infrastructure/embedding/types.py` | embed 契约 |
| `MemoryRetrievalSettings` | `settings/models.py` | vector_top_n、rrf_k、fused_top_n 等 |
| `ret001_es_fixtures` | `tests/support/ret001_es_fixtures.py` | ES Fixture 模式参考 |
| `FakeEmbeddingClient` | `tests/support/fake_retrieval_index_embedding_client.py` | 单元/集成 Fake embed |

### 5.3 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无检索 Query 标准化入口 | 无 `normalize_retrieval_query` / `retrieval_query_normalizer` |
| 无 Vector 领域模型/服务/仓储 | 无 `vector_retrieval` / `VectorRetrieval` |
| 无 RRF / Hybrid 融合 | 无 `rrf_fusion` / `hybrid_retrieval` |
| 无 RET-002 测试 | `tests/` 无 `test_ret002` |

**结论**：新建 Query 标准化、Vector 通道、RRF 融合与 Hybrid 编排；最小提取共享 ES Filter builder；复用 RET-001 BM25 与 DEV-007 Embedding；不修改 EXT-007 生产语义。

## 6. query_embedding_contract

### 6.1 Query 标准化

```text
normalize_retrieval_query(raw: str) -> str
```

| 规则 | 实现 |
|---|---|
| Unicode NFKC | 复用 `normalize_search_text_fragment`（与 §2.2.6 / §2.2.3 rule 1 一致） |
| 去除首尾空白 | 同上（`.strip()`） |
| 连续空格压缩为单空格 | 同上 |
| 保留中英文、数字、标点 | 不额外删除字符 |
| 不删除停用词 / 不同义词扩展 / LLM 改写 | 本函数不做 |
| 不拼接短期上下文 | 本函数不做 |

**入参校验**（`HybridRetrievalService` 层）：标准化后不得为空字符串 → `ValueError`（单元测试）；**不**映射为 HTTP 4xx。

**禁止**：在本任务引入 TEI `/tokenize` 或本地 token 计数（见 §21 LD-1）。

### 6.2 Embedding 调用

| 项 | 约定 |
|---|---|
| 工厂 | `create_embedding_client(settings, http_client)` — **不**修改 factory |
| 调用 | `result = await client.embed(texts=[normalized_query])` — **单条** Query；禁止 batch 多 query |
| 模型/维度 | `settings.memory_retrieval.embedding_model`（默认 `BAAI/bge-m3`）；`result.dimension == 1024`；`len(result.vectors) == 1`；`len(result.vectors[0]) == 1024` |
| 超时 | 沿用 `EmbeddingClient` 内部 httpx + `settings.memory_retrieval.embedding_timeout_seconds`；本任务不新增 timeout 配置 |
| 非法向量 | NaN/Inf/全零 — DEV-007 `SiliconFlowEmbeddingClient` 已拒绝；Vector Service 对任何维度不匹配再 fail-closed |
| 空字符串 | DEV-007 抛 `EmbeddingServiceError(code=embedding_input_too_long)`；标准化后为空须在 embed 前 `ValueError` |
| 持久化 | **禁止**持久化 Query Embedding（§2.2.6 #9） |

### 6.3 Embedding 失败映射（内部 Vector 通道）

| 源 | Vector 通道 Outcome |
|---|---|
| `EmbeddingServiceError`（含 provider 400/5xx、超时） | `outcome=failure`；`kind=channel_failure`；`retryable` 按 `status_code>=500` 或 transport |
| 标准化后空 query | `ValueError`（不进入 embed） |
| 返回向量维度 ≠ 1024 | `channel_failure`；`retryable=false` |
| `skipped_query_too_long` | **MVP SiliconFlow 路径不主动产生**（见 §21 LD-1）；若未来实现，映射为 Vector `kind=skipped_query_too_long`（非 `channel_failure`），RRF 视为无效通道 |

## 7. vector_query_contract

### 7.1 内部请求

```text
VectorRetrievalQuery {
  user_id: str
  query_vector: list[float]   # 必填；len==1024
  memory_types: list[str] | None
  include_conflicted: bool = false
  include_history: bool = false
}
```

`HybridRetrievalService` 从 raw query 标准化 → embed → 构造 `VectorRetrievalQuery`。

### 7.2 精确 ES kNN 结构

```json
POST {settings.memory_retrieval.index_name}/_search
{
  "size": <settings.memory_retrieval.vector_top_n>,
  "_source": false,
  "knn": {
    "field": "embedding",
    "query_vector": <1024 floats>,
    "k": <settings.memory_retrieval.vector_top_n>,
    "num_candidates": <settings.memory_retrieval.vector_num_candidates>,
    "filter": {
      "bool": {
        "filter": <FILTER_ARRAY>
      }
    }
  }
}
```

**约束**：

- `k == vector_top_n`（默认 30）；`num_candidates == vector_num_candidates`（默认 100）；`num_candidates >= k`（Settings 已有不变式）。
- `query_vector` 必须恰好 1024 个 `float`；Repository 发送前断言。
- `FILTER_ARRAY` 与 RET-001 §8.2 **完全相同**（经共享 `retrieval_filter_builder` 构建，保证与 BM25 一致）。
- 索引名来自 `settings.memory_retrieval.index_name`；**禁止**硬编码物理 Index 名。
- `request_timeout=settings.memory_retrieval.elasticsearch_timeout_seconds`。

### 7.3 响应解析

| ES 字段 | 映射 |
|---|---|
| `hits.hits[i]._id` | `VectorRetrievalHit.memory_id` |
| `hits.hits[i]._score` | `VectorRetrievalHit.score`（有效数值；缺失/非数值 → 畸形 → `channel_failure` `retryable=false`） |
| 命中顺序 `i` | `VectorRetrievalHit.rank = i + 1` |

### 7.4 内部 Vector 通道 Outcome

```text
VectorRetrievalHit { memory_id, rank, score }
VectorRetrievalSuccess { user_id, hits, total_hits }
VectorRetrievalFailure {
  kind: Literal["channel_failure", "skipped_query_too_long"]
  message: str
  retryable: bool   # skipped_query_too_long → false
}
VectorRetrievalOutcome { outcome: success|failure, success?, failure? }
```

## 8. rrf_contract

### 8.1 输入

```text
fuse_rrf(
  bm25: Bm25RetrievalOutcome,
  vector: VectorRetrievalOutcome,
  *,
  rrf_k: int,           # settings.memory_retrieval.rrf_k, default 60
  fused_top_n: int,     # settings.memory_retrieval.fused_top_n, default 30
) -> HybridRetrievalOutcome
```

### 8.2 通道有效性（用于 RRF 与 retrieval_mode）

| 通道状态 | 参与 RRF rank 贡献 | 计入 effective_channel_count |
|---|---|---|
| `success` 且 `hits` 非空 | **是** | **是** |
| `success` 且 `hits==[]` | **否** | **否** |
| `failure` / `skipped_query_too_long` | **否** | **否** |

### 8.3 RRF 分数（per memory_id）

对每条 `memory_id`，合并 BM25 与 Vector 命中：

```
rrf_score(memory_id) =
  (1 / (rrf_k + bm25_rank)  if bm25_rank is not None else 0)
+ (1 / (rrf_k + vector_rank) if vector_rank is not None else 0)
```

- `bm25_rank` / `vector_rank` 为各通道 1-based rank。
- 单通道命中、另一通道未命中该 id：仅加一项（one-channel-only）。
- 同一通道内 ES 不应重复 `_id`；若解析发现重复 `_id` → 该通道 `channel_failure`。

### 8.4 合并字段（FusedRetrievalCandidate）

```text
FusedRetrievalCandidate {
  memory_id: str
  bm25_rank: int | None
  vector_rank: int | None
  bm25_score: float | None      # 原始 ES _score；无则 null
  vector_score: float | None
  retrieval_source: list[Literal["bm25","vector"]]  # 按字母序稳定 ["bm25","vector"]
  rrf_score: float
  min_available_rank: int       # min(non_null(bm25_rank, vector_rank))
  normalized_retrieval_score: float | None
}
```

### 8.5 effective_channel_count 与归一化

```
effective_channel_count =
  (1 if bm25 success and len(hits)>0 else 0)
+ (1 if vector success and len(hits)>0 else 0)
```

| effective_channel_count | 行为 |
|---|---|
| 2 | `retrieval_mode=hybrid`；`rrf_max = 2 / (rrf_k + 1)` |
| 1 | `retrieval_mode` = `bm25_only` 或 `vector_only`；`rrf_max = 1 / (rrf_k + 1)` |
| 0 且至少一通道 `success`（均空） | `retrieval_mode=none`；`candidates=[]`；**不**计算 normalized |
| 0 且两通道均 `failure`（或 vector skipped 且 BM25 failure） | `HybridRetrievalOutcome.outcome=failure`；`kind=retrieval_unavailable` |

```
normalized_retrieval_score = min(1.0, rrf_score / rrf_max)   # 仅当 effective_channel_count > 0
```

### 8.6 排序与截断

稳定排序（§2.2.9 #7）：

1. `rrf_score` **DESC**
2. `min_available_rank` **ASC**
3. `memory_id` **ASC**（字典序）

取前 `fused_top_n` 条（默认 30）。

### 8.7 确定性 RRF 算例（单元测试必须覆盖）

固定 `rrf_k=60`，`fused_top_n=30`：

| memory_id | bm25_rank | vector_rank | rrf_score | min_available_rank |
|---|---|---|---|---|
| `mem_a` | 1 | 1 | `1/61 + 1/61 = 0.03278688524590164` | 1 |
| `mem_b` | 2 | None | `1/62 = 0.016129032258064516` | 2 |
| `mem_c` | None | 2 | `1/62 = 0.016129032258064516` | 2 |

- `mem_b` vs `mem_c` 同分 → `min_available_rank` 均为 2 → tie-break `memory_id ASC` → `mem_b` 在前。
- `effective_channel_count=2` → `rrf_max = 2/61` → `mem_a.normalized = 1.0`。
- 仅 BM25 有效（Vector failure）→ `effective_channel_count=1` → `retrieval_mode=bm25_only`；`rrf_max=1/61`。

### 8.8 原始 ES 分数角色

- `bm25_score` / `vector_score` **仅保存**供下游调试与 RET-004；**不参与** RRF 求和或排序（排序仅用 rank 推导的 `rrf_score`）。

### 8.9 Hybrid 内部 Outcome

```text
HybridRetrievalSuccess {
  user_id: str
  retrieval_mode: Literal["hybrid","bm25_only","vector_only","none"]
  candidates: list[FusedRetrievalCandidate]   # len 0..fused_top_n
  effective_channel_count: int
}

HybridRetrievalFailure {
  kind: Literal["retrieval_unavailable"] = "retrieval_unavailable"
  message: str
}

HybridRetrievalOutcome {
  outcome: Literal["success","failure"]
  success: HybridRetrievalSuccess | None
  failure: HybridRetrievalFailure | None
}
```

**禁止**：在本任务返回 HTTP Warning 字符串或 RET-005 Response DTO。

## 9. user_isolation

| 规则 | enforcement |
|---|---|
| 每次 Vector kNN Filter **必须** 含 `user_id` term | 共享 `build_retrieval_filters` 无条件注入；单元测试断言 ES body |
| BM25 隔离 | 委托 RET-001；Hybrid 集成测试交叉用户 |
| Integration | Fixture 为 `user_a` / `user_b` 写入不同 embedding 邻近文档；`user_a` Hybrid 查询不得返回 `user_b` 的 `memory_id` |
| 日志 | 可记录 `user_id`、通道状态、命中数；**禁止**记录 query 全文或 embedding 向量 |

## 10. failure_mapping

| 失败源 | 内部表示 | RRF / retrieval_mode 影响 |
|---|---|---|
| Embedding 失败 | Vector `channel_failure` | 若 BM25 有效非空 → `bm25_only`；否则见下行 |
| Vector ES 失败/畸形 | Vector `channel_failure` | 同上 |
| BM25 失败（RET-001） | BM25 `channel_failure` | 若 Vector 有效非空 → `vector_only` |
| Vector `skipped_query_too_long`（MVP 不产生） | Vector `skipped_query_too_long` | 同 failure（无效通道） |
| 两通道均 failure/skipped | `HybridRetrievalFailure.retrieval_unavailable` | 无 candidates |
| 两通道均 success 但空 | `success`；`retrieval_mode=none`；`candidates=[]` | 非 failure |
| 入参非法 | `ValueError` | 不包装为 outcome |

**显式禁止**（RET-002 内部）：

- **不得** 抛出 HTTP `embedding_failed`、`vector_skipped_query_too_long`、`bm25_retrieval_failed`。
- **不得** 伪造空成功掩盖双通道失败。

## 11. durable_write_scope

```yaml
durable_write_scope: NONE
```

| 存储 | 读写 | 说明 |
|---|---|---|
| Elasticsearch | **只读** `_search` | Fixture 写入仅 `tests/**` |
| Embedding API | **只读** embed | 不持久化向量 |
| MongoDB / Neo4j / Kafka / Redis | 无 | — |

## 12. replay_idempotency

| 场景 | 预期行为 |
|---|---|
| 相同 `HybridRetrievalQuery` 重复调用 | 相同融合结果（索引与 Fake embed 不变） |
| BM25/Vector 只读 | 无写冲突；天然幂等 |
| 并发相同查询 | 各调用独立；无共享可变状态 |
| 进程重启 | 行为与首次一致 |

## 13. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/services/retrieval_query_normalizer.py` | 创建 | `normalize_retrieval_query` |
| `src/memory_system/domain/models/vector_retrieval.py` | 创建 | Vector 通道模型 |
| `src/memory_system/domain/models/hybrid_retrieval.py` | 创建 | Fused candidate + Hybrid Outcome |
| `src/memory_system/domain/services/rrf_fusion.py` | 创建 | `fuse_rrf` 纯函数 |
| `src/memory_system/domain/services/vector_retrieval_service.py` | 创建 | Vector 编排（仅 ES；不含 embed） |
| `src/memory_system/domain/services/hybrid_retrieval_service.py` | 创建 | 并行 BM25+Embed+Vector + 调 RRF |
| `src/memory_system/infrastructure/elasticsearch/retrieval_filter_builder.py` | 创建 | 共享 user_id/memory_type/status filters |
| `src/memory_system/infrastructure/elasticsearch/vector_retrieval_repository.py` | 创建 | ES kNN + `VectorRetrievalError` |
| `src/memory_system/infrastructure/elasticsearch/bm25_retrieval_repository.py` | 修改 | **仅** 改为 import 共享 filter builder；**零语义变更** |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `settings/`、`entrypoints/`、DEV-007 文件、RET-001 service）。

## 14. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_retrieval_query_normalizer.py` | 创建 | NFKC / whitespace 标准化 |
| `tests/unit/test_retrieval_filter_builder.py` | 创建 | 共享 filter 与 status 矩阵 |
| `tests/unit/test_vector_retrieval_query_builder.py` | 创建 | kNN body、k/num_candidates、1024 维 |
| `tests/unit/test_vector_retrieval_service.py` | 创建 | Vector Service 失败映射 |
| `tests/unit/test_rrf_fusion.py` | 创建 | 精确 RRF 算例、tie-break、one-channel、mode |
| `tests/unit/test_hybrid_retrieval_service.py` | 创建 | 并行编排、embed 失败、双失败 |
| `tests/integration/test_ret002_vector_retrieval_rrf.py` | 创建 | ES + Fake embed 集成 |
| `tests/support/ret002_es_fixtures.py` | 创建 | 差异化 embedding Fixture |

**白名单外任何 `tests/**` 变更 → FAIL**（RET-001 测试文件不得修改语义；运行回归但不在白名单内编辑）。

## 15. 实现方案

### Step 1 — Query 标准化 `retrieval_query_normalizer.py`

- **函数**：`normalize_retrieval_query(raw: str) -> str`
- **实现**：委托 `normalize_search_text_fragment`
- **测试**：NFKC、全角空格、连续空白、标点保留

### Step 2 — 共享 Filter `retrieval_filter_builder.py`

- **函数**：
  - `build_retrieval_status_filter(include_conflicted, include_history) -> dict`
  - `build_retrieval_filters(*, user_id, memory_types, include_conflicted, include_history) -> list[dict]`
- **重构**：`bm25_retrieval_repository.py` 删除本地 `_build_status_filter`，改 import；**行为不变**
- **测试**：与 RET-001 U1–U4 等价断言（新文件）；跑通原 RET-001 测试

### Step 3 — Vector 模型 `vector_retrieval.py`

- 类型：`VectorRetrievalQuery`、`VectorRetrievalHit`、`VectorRetrievalSuccess`、`VectorRetrievalFailure`、`VectorRetrievalOutcome`
- `VectorRetrievalFailure.kind`: `channel_failure` | `skipped_query_too_long`

### Step 4 — Vector 仓储 `vector_retrieval_repository.py`

- `build_knn_search_body(query, *, k, num_candidates, size) -> dict`
- `async def search(...) -> list[VectorRetrievalHit]`
- `VectorRetrievalError`（对齐 `Bm25RetrievalError` 模式）
- 校验 `len(query_vector)==1024`

### Step 5 — Vector 服务 `vector_retrieval_service.py`

- 入参校验 → settings → repository.search
- **不** 调用 Embedding（Hybrid 层负责）

### Step 6 — Hybrid 模型 `hybrid_retrieval.py`

- `HybridRetrievalQuery`（含 raw `query` + 与 BM25 相同 filter 字段）
- `FusedRetrievalCandidate`、`HybridRetrievalSuccess`、`HybridRetrievalFailure`、`HybridRetrievalOutcome`

### Step 7 — RRF 纯函数 `rrf_fusion.py`

- `fuse_rrf(bm25_outcome, vector_outcome, *, rrf_k, fused_top_n) -> HybridRetrievalOutcome`
- 无 I/O；完整 §8 语义

### Step 8 — Hybrid 编排 `hybrid_retrieval_service.py`

- 依赖：`Bm25RetrievalService`、`VectorRetrievalService`、`EmbeddingClient`
- 流程：
  1. 校验 + `normalized = normalize_retrieval_query(query.query)`
  2. `bm25_task = asyncio.create_task(bm25_service.search(Bm25RetrievalQuery(..., query=normalized, ...)))` — **禁止**传入 raw query
  3. `vector_task = asyncio.create_task(_embed_and_vector_search(normalized, ...))`
  4. `bm25_outcome, vector_outcome = await asyncio.gather(bm25_task, vector_task)`
  5. `return fuse_rrf(bm25_outcome, vector_outcome, rrf_k=..., fused_top_n=...)`
- `_embed_and_vector_search`：`embed` → 构造 `VectorRetrievalQuery` → `vector_service.search`
- Factory：`create_hybrid_retrieval_service(...)`

### Step 9 — 单元测试

- 覆盖 §16.1–§16.2 全部 ID

### Step 10 — Integration + Fixture

- `ret002_es_fixtures.py`：为不同 `memory_id` 生成可区分余弦相似度的 1024 维 embedding（确定性伪向量，非随机）
- `test_ret002_vector_retrieval_rrf.py`：Vector happy path、Hybrid RRF、用户隔离、filter、空结果、embed 失败降级
- 复用 `test_ext007` / `test_ret001` 的 `es_client` / `test_infra` 模式（复制最小 autouse clean，不修改既有 conftest 除非 Amendment）

## 16. 测试计划

### 16.1 Unit Test

| ID | 场景 | 预期 |
|---|---|---|
| U1 | `normalize_retrieval_query` NFKC + 空格 | 与 §2.2.6 一致 |
| U2 | 标准化后空字符串 | `ValueError` |
| U3 | 共享 filter 默认（active only） | 与 RET-001 U1 等价 |
| U4 | status 矩阵四组合 | 与 RET-001 U4 一致 |
| U5 | kNN body：`k=vector_top_n`，`num_candidates>=k` | 精确结构 §7.2 |
| U6 | `query_vector` len≠1024 | `ValueError` 或 `channel_failure` |
| U7 | Vector 解析 hits | rank 1..n；score 有效 |
| U8 | Vector ES 异常 | `channel_failure` |
| U9 | RRF 算例 §8.7 | 精确 `rrf_score`、normalized、`mem_b`/`mem_c` tie |
| U10 | duplicate memory_id 跨通道融合 | 单条 candidate；`retrieval_source` 含双来源 |
| U11 | one-channel-only BM25 | `bm25_only`；vector ranks null |
| U12 | one-channel-only Vector | `vector_only` |
| U13 | both channels empty success | `none`；`candidates=[]` |
| U14 | both channels failure | `retrieval_unavailable` |
| U15 | embedding failure + BM25 ok | `bm25_only` |
| U16 | `fused_top_n` 截断 | 输入 >N 候选时输出 N 条 |
| U17 | Hybrid 并行 | Fake 计时：BM25 不等待 embed（mock delay） |
| U18 | RET-001 回归 | 现有 `test_bm25_*` + `test_ret001_*` 全通过（CI 同跑） |
| U19 | 一通道 `channel_failure` + 另一通道 `success`/`hits=[]` | `outcome=success`；`retrieval_mode=none`；`candidates=[]`；**非** `retrieval_unavailable` |

### 16.2 Contract Test

| ID | 场景 | 预期 |
|---|---|---|
| C1 | kNN ES body 与 §7.2 一致 | snapshot/断言 |
| C2 | 不修改 DEV-007 / EXT-007 生产文件 | `git diff` 白名单 |
| C3 | index_name 来自 settings | grep 硬编码 index 仅限白名单文件 |
| C4 | BM25 repository 重构后 Query body 不变 | 与 RET-001 C1 等价 |

### 16.3 Integration Test

| ID | 场景 | 预期 |
|---|---|---|
| I1 | Vector happy path | 语义相近文档 ranked；rank/score 有效 |
| I2 | 交叉用户隔离 | `user_b` 不可见 |
| I3 | `memory_types` 过滤 | 仅允许类型 |
| I4 | 默认 status=active | conflicted/superseded 不命中 |
| I5 | Hybrid RRF 双通道 | `retrieval_mode=hybrid`；融合顺序稳定 |
| I6 | 空 Vector（无相近向量） | `success`；`hits=[]`；可 `vector_only`/`none` 视 BM25 |
| I7 | Fake embed failure | `bm25_only` 若 BM25 有命中 |
| I8 | ES Vector 失败注入（mock repo） | 降级 BM25-only |
| I9 | `fused_top_n` | 种子 >N 时截断 |

### 16.4 E2E Test

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — RET-006 |

### 16.5 失败注入与并发测试

| ID | 场景 | 预期 |
|---|---|---|
| F1 | Fake Embedding `fail=True` | Vector failure；BM25 继续 |
| F2 | 双通道均 fail | `retrieval_unavailable` |
| F3 | 并发 10 路相同 Hybrid 查询 | 无异常；结果一致 |

## 17. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 只读查询 + 无状态融合 |
| 幂等 | **是** | 相同输入 + 稳定索引 → 相同输出 |
| 并发 | 只读无锁 | ES/embed 并发安全 |
| 版本冲突 | 不适用 | 无乐观锁 |
| 用户隔离 | **强制** | 共享 filter builder |
| 部分失败 | **是** | 单通道降级 §10 |
| 进程异常恢复 | 不适用 | 无 in-flight 写 |

## 18. 验收标准

- [ ] `normalize_retrieval_query` 符合 §2.2.6；单条 `embed` 经 `create_embedding_client`
- [ ] Vector kNN Query 与 §7.2 一致；`query_vector` 1024 维；filters 与 BM25 相同
- [ ] `fuse_rrf` 与 §8 一致（含算例、tie-break、mode、normalized）
- [ ] Hybrid 并行：BM25 不等待 Embedding；Vector 等待 Embedding
- [ ] 单通道失败降级；双通道失败 → 内部 `retrieval_unavailable`
- [ ] Integration ES Fixture + Fake embed；不依赖 EXT-007 pipeline
- [ ] RET-001 全量测试回归通过；BM25 语义零变更
- [ ] 不触碰 DEV-006/PR#13；不修改 Settings/Migration
- [ ] scoped unit + integration 全通过；Ruff/Mypy（变更文件）通过
- [ ] Review 无 P0/P1

## 19. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | 无；与 master_plan §RET-002、规格 §2.2.6/§2.2.8/§2.2.9 一致 |
| 前置任务 | RET-001、DEV-007 completed |
| 主要风险 | ① Filter 与 BM25 漂移 — 用共享 builder + C4 回归；② 误实现 HTTP Warning；③ Integration embedding 不可区分导致 flaky |
| SiliconFlow token 上限 | 无本地 tokenize；见 LD-1 |
| 非阻塞 | OI-008（RET-005 API 编辑性） |
| DEV-006 | **禁止触碰** PR#13 |

## 20. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/RET-002-vector-retrieval-rrf"
baseline_main: "e5f5c9de9883d04759f19080c01f1f50d2c62513"
expected_commits:
  - "docs(plan): add RET-002 vector retrieval and RRF fusion plan (includes progress.md + master_plan.md planning metadata)"
  - "feat(ret): add vector retrieval, query embedding path, and RRF fusion"
  - "docs(status): record RET-002 implementation commit and PR"
  - "docs(status): complete RET-002 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "EXT-007 write path / MemoryIndexDocument schema"
  - "DEV-007 siliconflow_client / factory semantics"
  - "DEV-004 mapping/alias"
  - "HTTP API / RET-005 warnings"
  - "Neo4j / ACT-R / retrieval_count"
  - "Migration / dependency / Settings"
```

## 21. mvp_local_decisions

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | **SiliconFlow MVP 不实现** `skipped_query_too_long` 本地 token 预检；超长 query 由 provider 返回错误 → `embedding_failed` → Vector `channel_failure` | DEV-007 明确不做 `/tokenize`；规格 §2.2.6 #3/#8 针对 `TEIEmbeddingClient`；不得复活 DEV-006 |
| LD-2 | Query 标准化复用 `normalize_search_text_fragment` 而非新算法 | 与 §2.2.3 rule 1 / §2.2.6 规则一致；避免重复实现 |
| LD-3 | 提取 `retrieval_filter_builder.py` 并最小重构 BM25 Repository | 保证 Vector/BM25 filter 永远一致；RET-001 行为不变，靠回归测试证明 |
| LD-4 | `VectorRetrievalService` 不内嵌 embed；`HybridRetrievalService` 拥有 embed 编排 | 分离关注点；Vector 可单测 ES；Hybrid 测并行 |
| LD-5 | 内部双通道失败使用 `retrieval_unavailable`；**不**复用 HTTP 错误码字符串于 Outcome 外 | RET-005 映射 HTTP；避免 RET-002 泄漏 API 层 |
| LD-6 | Integration 使用确定性伪 embedding（非 live SiliconFlow） | master_plan：不硬依赖外部 embed；Fake 可控相似度 |
| LD-7 | `retrieval_source` 列表按字母序 `["bm25","vector"]` | 确定性输出；便于断言 |
| LD-8 | 原始 ES `_score` 保存在 Fused candidate 但不参与 RRF | §2.2.8/§2.2.9 明确仅 rank 融合 |

## 22. deferred_for_mvp

| 项 | 说明 |
|---|---|
| `skipped_query_too_long` 本地 token 预检（SiliconFlow 路径） | 待 TEI 或独立 tokenizer；见 LD-1 |
| Neo4j 权威回读 + 一跳扩展 + MGET | RET-003 |
| ACT-R 评分 + Evidence 聚合 | RET-004 |
| HTTP Retrieval API + Warning 矩阵 + 统计 | RET-005 |
| EXT-007 写入→检索全链路 E2E | RET-006 |
| `retrieval_total_timeout_seconds` 跨通道总超时 | RET-005 |
| reranking / hybrid 调参 / 检索缓存 | 规格外 |
| L2 normalize 语义验证（SiliconFlow UNKNOWN） | OI-012 / DEV-007 已记录 UNKNOWN |

## 23. open_issues

| ID | 关系 | 阻塞 RET-002？ |
|---|---|---|
| OI-008 | RET-005 API 编辑性 | **否** |

## 24. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

## 25. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 02:40 UTC | planning | 创建 Task Plan；更新 progress/master_plan 规划态 | — | planning only；未 Git 写 |
| 2026-08-13 03:01 UTC | implemented → tested | 9 生产文件 + 8 测试文件；共享 filter 提取；BM25 零语义变更 | 71 passed（31 RET-002 unit + 7 integration + 33 RET-001 regression）；ruff/mypy PASS | 无计划外差异 |
| 2026-08-13 03:15 UTC | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #45 MERGED；验证 main 含 implementation `3bf3a1b760080d4f581ab53dad0961a28dfb63a4`、merge `2bfc2b2ddbd5ef69a2a3f473722b32a9ead3d461`；治理三文件 + `docs(status): complete`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=1 non-blocking；`next_action=RET-003 planned / NOT AUTO-STARTED` | 无计划外差异 |

## 26. 实际执行结果

### 实际修改文件

**Production (9)**:
- `src/memory_system/domain/services/retrieval_query_normalizer.py` (create)
- `src/memory_system/domain/models/vector_retrieval.py` (create)
- `src/memory_system/domain/models/hybrid_retrieval.py` (create)
- `src/memory_system/domain/services/rrf_fusion.py` (create)
- `src/memory_system/domain/services/vector_retrieval_service.py` (create)
- `src/memory_system/domain/services/hybrid_retrieval_service.py` (create)
- `src/memory_system/infrastructure/elasticsearch/retrieval_filter_builder.py` (create)
- `src/memory_system/infrastructure/elasticsearch/vector_retrieval_repository.py` (create)
- `src/memory_system/infrastructure/elasticsearch/bm25_retrieval_repository.py` (modify — shared filter only)

**Tests (8)**:
- `tests/unit/test_retrieval_query_normalizer.py`
- `tests/unit/test_retrieval_filter_builder.py`
- `tests/unit/test_vector_retrieval_query_builder.py`
- `tests/unit/test_vector_retrieval_service.py`
- `tests/unit/test_rrf_fusion.py`
- `tests/unit/test_hybrid_retrieval_service.py`
- `tests/integration/test_ret002_vector_retrieval_rrf.py`
- `tests/support/ret002_es_fixtures.py`

### 与原计划的差异

暂无。

### 测试结果

```yaml
scoped_tests: "71 passed (31 RET-002 unit + 7 RET-002 integration + 33 RET-001 regression)"
ruff: PASS
mypy: PASS
```

### Review 结果

```yaml
p0: 0
p1: 0
p2: 1
p3: 0
review_report: null
```

### Git 记录

```yaml
branch: "feat/RET-002-vector-retrieval-rrf"
plan_commit: da1736925b767777bd8f538d5719d5821bebc017
implementation_commit: 3bf3a1b760080d4f581ab53dad0961a28dfb63a4
implementation_commit_message: "feat(ret): add vector retrieval, query embedding path, and RRF fusion"
pr: "#45"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/45"
pr_state: MERGED
pr_base: main
pr_head: "feat/RET-002-vector-retrieval-rrf"
merge_commit: 2bfc2b2ddbd5ef69a2a3f473722b32a9ead3d461
merged_at: "2026-08-13T03:13:39Z"
status_record_committed: null
```

### 最终状态

`completed`
