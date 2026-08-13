# RET-004 ACT-R 评分 + Evidence 聚合

## 1. 任务信息

```yaml
task_id: RET-004
task_name: ACT-R 评分 + Evidence 聚合
status: planned
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "c8d9d38d92414b9e041dd3d97dcbfd17b9e61582"
branch: "feat/RET-004-act-r-scoring-evidence-aggregation"
created_at: "2026-08-13 06:01 UTC"
updated_at: "2026-08-13 06:01 UTC"
spec_sections:
  - "§2.2.11 基础 ACT-R 近似评分（本任务唯一权威范围 — 评分与排序）"
  - "§2.2.12 Evidence 加载与 Retrieval Response 设计（本任务仅内部 Evidence 批量读与聚合；不含 HTTP Response DTO）"
  - "§2.2.14 MVP 配置（消费 MemoryRetrievalSettings 权重/半衰期/max_source_message_ids；不修改 Settings Contract）"
  - "§3.28 测试策略（Unit + Neo4j Integration Fixture）"
prerequisites:
  formal:
    - "RET-001 — SATISFIED/completed; Bm25RetrievalService + ES read path"
    - "RET-002 — SATISFIED/completed; HybridRetrievalService + RRF fusion（PR #45 MERGED）"
    - "RET-003 — SATISFIED/completed; AuthoritativeRecallService + ValidatedRetrievalCandidate + Neo4j/ES read-only path（PR #46 MERGED）"
    - "EXT-005 — SATISFIED/completed; Evidence 节点写入与 EvidenceLookupRepository（本任务新建独立 Evidence 读仓储，禁止混用 EXT-005 存在性语义）"
    - "EXT-006 — SATISFIED/completed; Neo4j Memory/Entity 图模型"
  implementation_reuse:
    - "AuthoritativeRecallSuccess / ValidatedRetrievalCandidate / InternalRetrievalWarning (domain/models/authoritative_recall.py)"
    - "RetrievalMemorySnapshot (domain/models/retrieval_memory_snapshot.py)"
    - "MemoryRetrievalSettings: retrieval_score_weight, importance_weight, confidence_weight, frequency_weight, recency_weight, recency_half_life_days, conflicted_penalty, superseded_penalty, max_source_message_ids, default_top_k, max_top_k"
    - "rrf_fusion.py 纯函数模式 — 新建 act_r_scoring.py 同级纯函数模块"
    - "ret003_neo4j_fixtures.py — Integration Neo4j Fixture 复用/扩展"
  baseline_evidence:
    branch: "main"
    head: "c8d9d38d92414b9e041dd3d97dcbfd17b9e61582"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=c8d9d38d92414b9e041dd3d97dcbfd17b9e61582"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "PLAN_APPROVED — human confirmed 2026-08-13"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: false
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create the exact feature branch feat/RET-004-act-r-scoring-evidence-aggregation"
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
  - "修改 RET-001/002/003 生产语义"
  - "修改 EXT-005 EvidenceLookupRepository 生产语义"
stop_if:
  - "任何实现步骤需要 HTTP Retrieval API、Warning HTTP 字段映射或 retrieval_count 统计更新（RET-005）"
  - "任何实现步骤需要 durable 写入（Mongo/Neo4j/ES/Kafka）"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要修改 Evidence 节点或 Memory 统计字段"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-008
```

## 2. authoritative_scope

本任务 **仅** 拥有 §2.2.11 ACT-R 评分、§2.2.12 Evidence 批量读与确定性聚合、Top-K 截断与最终排序；**不** 拥有 HTTP API、retrieval_count/last_retrieved_time 更新、总超时降级矩阵或 Response DTO 组装。

| 维度 | 归属 RET-004 | 非 RET-004（显式排除） |
|---|---|---|
| 消费 `AuthoritativeRecallSuccess` 合并 direct+expanded 候选 | **是** | — |
| ACT-R 五分量计算 + status 惩罚 + 6 位小数 `final_score` | **是** — §4 | — |
| 确定性排序 + `top_k` 截断 | **是** — §7 | HTTP `top_k` 请求校验（RET-005） |
| Top-K 后 Neo4j 批量 Evidence 读 + `evidence_count` / `source_message_ids` | **是** — §5 | HTTP `memories[]` Response 字段映射（RET-005） |
| Evidence 加载失败 → 内部 `graph_load_failed` | **是** — §9 | HTTP 4xx/5xx 映射（RET-005） |
| RET-003 内部 Warning 透传 | **是** — 不 remap | HTTP Warning 字符串（RET-005） |
| BM25 / Vector / RRF / Neo4j 权威回读 / 图扩展 / MGET | **否** — 消费 RET-003 | **RET-001..003** |
| EXT-005 `EvidenceLookupRepository` 存在性检查 | **否** — 语义不同 | **EXT-005** |
| `retrieval_count` / `last_retrieved_time` Neo4j 更新 | **否** | **RET-005 §2.2.13** |
| HTTP API / API Key / 总超时降级 | **否** | **RET-005** |
| Session→Retrieval 全链路 E2E | **否** | **RET-006** |

## 3. input_contract（精确消费 RET-003）

### 3.1 上游输入（必须原样消费）

来自 `AuthoritativeRecallSuccess`（RET-003 `AuthoritativeRecallService` 输出）：

```text
AuthoritativeRecallSuccess {
  user_id: str
  retrieval_mode: Literal["hybrid","bm25_only","vector_only","none"]
  effective_channel_count: int
  direct_candidates: list[ValidatedRetrievalCandidate]
  expanded_candidates: list[ValidatedRetrievalCandidate]
  warnings: list[InternalRetrievalWarning]
}

ValidatedRetrievalCandidate {
  memory_id: str
  bm25_rank: int | None
  vector_rank: int | None
  bm25_score: float | None
  vector_score: float | None
  retrieval_source: list[Literal["bm25","vector","graph"]]
  rrf_score: float | None
  min_available_rank: int | None
  normalized_retrieval_score: float | None
  graph_retrieval_score: float | None
  candidate_origin: Literal["direct","expanded"]
  memory: RetrievalMemorySnapshot
}
```

**透传**（进入 `RetrievalScoringSuccess` 不变）：

- `user_id`
- `retrieval_mode`
- `effective_channel_count`
- `warnings`（RET-003 种类：`dirty_index_document` / `stale_index_document` / `graph_expansion_failed`；**禁止** remap 为 HTTP Warning）

### 3.2 候选合并规则

评分前合并 `direct_candidates` + `expanded_candidates`：

1. RET-003 保证 **无重复** `memory_id`（重叠已在 direct 合并，`candidate_origin="direct"`）。
2. 合并顺序：**先** `direct_candidates`（保持 RET-003 顺序），**再** `expanded_candidates`（保持 RET-003 顺序）；仅用于评分输入稳定化；**最终排序**由 §7 ACT-R 规则决定，不保留合并顺序。
3. 若合并后为空 → `success`；`scored_memories=[]`；**不**调用 Evidence 读。

### 3.3 附加 Service 入参（非 HTTP DTO）

```text
RetrievalScoringQuery {
  authoritative_success: AuthoritativeRecallSuccess   # 必填
  top_k: int                                           # 必填；本任务校验 1..settings.memory_retrieval.max_top_k
  current_time: int                                    # 必填；Unix epoch 秒；注入式，禁止单元测试依赖 wall-clock
}
```

| 字段 | 校验 | 说明 |
|---|---|---|
| `authoritative_success.user_id` | 非空 `str` | Evidence Neo4j 查询强制绑定 |
| `top_k` | `1 <= top_k <= settings.memory_retrieval.max_top_k` | 默认由调用方取 `default_top_k`；HTTP 层校验归属 RET-005 |
| `current_time` | 非负 `int` | Recency 计算；测试注入固定值 |

**禁止**：在本任务引入 HTTP Request DTO、API Key、Query 文本或 `graph_expand` 参数。

### 3.4 上游 Failure 传播（SF-1 — 调用方/Orchestrator 责任）

`RetrievalScoringService` **仅**接受 `AuthoritativeRecallSuccess`；**不**接受 `AuthoritativeRecallOutcome` 包装。

上游 `AuthoritativeRecallOutcome.outcome="failure"`（`neo4j_read_failure`）的分支由 **调用方 / Orchestrator / RET-005** 负责；**禁止**在本 Service 内 remap 或吞掉上游 failure。RET-004 不得将 `neo4j_read_failure` 转为其他 kind。

## 4. act_r_contract

### 4.1 分量公式（§2.2.11 — 权重来自 `MemoryRetrievalSettings`）

**1. retrieval_score**（按 `candidate_origin` 选择 — HARD_BLOCK 若选错源）：

| `candidate_origin` | 使用字段 | 必填 |
|---|---|---|
| `"direct"` | `normalized_retrieval_score` | **非 null**；否则 **跳过**该候选（不进入评分池） |
| `"expanded"` | `graph_retrieval_score` | **非 null**；否则 **跳过**该候选 |

- 直接候选与扩展重叠已在 RET-003 保留于 `direct_candidates`，`candidate_origin="direct"`，使用 `normalized_retrieval_score`（即使 `retrieval_source` 含 `"graph"`）。

**2. importance_score** = `memory.importance`

**3. confidence_score** = `memory.confidence`

**4. frequency_score**：

```text
frequency_score = min(1.0, ln(1 + retrieval_count) / ln(21))
```

- `retrieval_count` 来自 `memory.retrieval_count`（≥0，Pydantic 已约束）。
- `retrieval_count >= 20` → `frequency_score = 1.0`（单元测试精确断言）。

**5. recency_score**：

```text
reference_time = max(last_retrieved_time or 0, latest_source_time or 0)
age_days = max(0, current_time - reference_time) / 86400
recency_score = exp(-ln(2) * age_days / recency_half_life_days)
```

- `recency_half_life_days` 来自 `settings.memory_retrieval.recency_half_life_days`（默认 `30`）。
- **`latest_source_time` 为 `null`** → MVP_LOCAL_DECISION：视为 `0`（与 RET-003 排序中 null→0 一致）；见 §21 LD-1。
- **`last_retrieved_time` 为 `null`** → 规格 `or 0`。

**6. 加权求和**：

```text
weighted =
  retrieval_score_weight * retrieval_score
+ importance_weight * importance_score
+ confidence_weight * confidence_score
+ frequency_weight * frequency_score
+ recency_weight * recency_score
```

权重字段：`retrieval_score_weight`, `importance_weight`, `confidence_weight`, `frequency_weight`, `recency_weight`（启动时已校验和=1.0）。

**7. Status 惩罚**（乘法，在 clamp 前应用于 weighted 结果）：

| `memory.status` | 乘数（来自 settings） |
|---|---|
| `conflicted` | `conflicted_penalty`（默认 `0.85`） |
| `superseded` | `superseded_penalty`（默认 `0.60`） |
| 其他（含 `active`） | `1.0` |

**8. Clamp 与舍入**：

1. 每个分量 **先** clamp 到 `[0.0, 1.0]`（importance/confidence 已在快照约束；仍 defensive clamp）。
2. `final_score = round(clamp(weighted * status_penalty, 0.0, 1.0), 6)` — **6 位小数**。

### 4.2 纯函数模块（`domain/services/act_r_scoring.py`）

| 函数 | 职责 |
|---|---|
| `select_retrieval_score(candidate) -> float \| None` | 按 §4.1 #1 选择；None → 跳过 |
| `compute_frequency_score(retrieval_count) -> float` | §4.1 #4 |
| `compute_recency_score(last_retrieved_time, latest_source_time, current_time, half_life_days) -> float` | §4.1 #5 |
| `compute_act_r_components(candidate, current_time, settings) -> ActRScoreComponents \| None` | 全分量 + None 若 retrieval 缺失 |
| `compute_final_score(components, status, settings) -> float` | 加权 + 惩罚 + clamp + round(6) |

**禁止**在 Service/Repository 内散落公式；与 `rrf_fusion.py` 同级纯函数。

### 4.3 缺失/畸形值处理

| 条件 | 动作 |
|---|---|
| `candidate_origin=direct` 且 `normalized_retrieval_score is None` | **跳过**该候选 |
| `candidate_origin=expanded` 且 `graph_retrieval_score is None` | **跳过**该候选 |
| `importance` / `confidence` 超出 [0,1]（不应发生） | defensive clamp 后计分 |
| 全部被跳过 | `success`；`scored_memories=[]`；无 Evidence 读 |
| 入参 `top_k` / `current_time` 非法 | `ValueError`（单元测试；非 HTTP 映射） |

## 5. evidence_aggregation_contract

### 5.1 调用时机（§2.2.12 #1 — HARD_BLOCK 若提前加载）

**仅当** §7 排序 + `top_k` 截断完成后，对 **最终 Top-K** `memory_id` 列表执行 **一次** Neo4j 批量查询。

- **禁止**对全部 direct/expanded 候选预加载 Evidence。
- **禁止** per-memory 单独查询。

### 5.2 Neo4j 查询契约

```text
(Evidence)-[:SUPPORTS]->(Memory)
WHERE Memory.memory_id IN $memory_ids
  AND Memory.user_id = $user_id
  AND Evidence.user_id = $user_id
```

返回每条 Evidence 至少：

| 字段 | 用途 |
|---|---|
| `evidence_id` | 排序 tie-break |
| `memory_id` | 分组 |
| `source_time_end` | Evidence 排序第一维 |
| `source_message_ids` | 聚合来源（数组，保持 Neo4j 存储顺序） |

- 新建 **`RetrievalEvidenceReadRepository`**（`infrastructure/neo4j/retrieval_evidence_read_repository.py`）。
- **禁止**复用 EXT-005 `EvidenceLookupRepository`（仅 evidence_id 存在性；无 message_ids 聚合）。
- `neo4j_timeout` 来自 `settings.memory_retrieval.neo4j_timeout_seconds`。
- **只读**；**禁止** mutate Evidence/Memory。

### 5.3 确定性聚合规则

对每个 Top-K `memory_id`：

1. 收集关联 Evidence 列表。
2. Evidence **稳定排序**：`source_time_end DESC`，`evidence_id ASC`（null `source_time_end` → MVP_LOCAL_DECISION 视为 `0`，排在最后）。
3. 按排序顺序遍历 Evidence；每个 Evidence 内按 `source_message_ids` **数组原序**展开。
4. 合并为全局列表；对重复 `message_id` **保留第一次出现**（first occurrence wins）。
5. `evidence_count` = 该 Memory 关联 Evidence **总数**（不受截断影响）。
6. `source_message_ids` = 合并去重列表的前 `max_source_message_ids` 条（默认 `20`；来自 settings）。

纯函数：`aggregate_evidence_for_memory(evidence_rows, max_source_message_ids) -> EvidenceAggregationResult`。

### 5.4 无 Evidence 情况

Memory 在 Top-K 但无 SUPPORTS 边 → `evidence_count=0`；`source_message_ids=[]`（**合法**；非失败）。

### 5.5 Evidence 加载失败

Neo4j transport/超时/驱动异常 → `RetrievalScoringFailure.kind = graph_load_failed`；**不得**返回 Top-K 结果或伪造空 `source_message_ids` 冒充成功（§2.2.12 #5）。

## 6. score_composition / final handoff model

### 6.1 领域模型（新建 `domain/models/retrieval_scoring.py`）

```text
ActRScoreComponents {
  retrieval_score: float
  importance_score: float
  confidence_score: float
  frequency_score: float
  recency_score: float
}

EvidenceAggregationResult {
  evidence_count: int
  source_message_ids: list[str]
}

ScoredRetrievalMemory {
  memory_id: str
  memory_type: str
  status: str
  content: str
  subject_entity: RetrievalEntitySnapshot | None      # 来自 memory 快照
  object_entity: RetrievalEntitySnapshot | None
  predicate: str
  object_value: str | None
  event_status: str | None
  start_time: int | None
  end_time: int | None
  confidence: float
  importance: float
  latest_source_time: int | None
  retrieval_source: list[RetrievalSource]
  bm25_rank, vector_rank, bm25_score, vector_score: 同 ValidatedRetrievalCandidate 可空字段
  rrf_score: float | None                                    # SF-2：透传 RET-002/003；不参与 ACT-R
  min_available_rank: int | None                               # SF-2：透传 RET-002/003；不参与 ACT-R
  candidate_origin: CandidateOrigin
  act_r_components: ActRScoreComponents
  final_score: float                                   # round(., 6)
  evidence_count: int
  source_message_ids: list[str]
}

RetrievalScoringSuccess {
  user_id: str
  retrieval_mode: Literal["hybrid","bm25_only","vector_only","none"]
  effective_channel_count: int
  scored_memories: list[ScoredRetrievalMemory]          # 已 Top-K；按 §7 排序
  warnings: list[InternalRetrievalWarning]              # RET-003 透传
}

RetrievalScoringFailure {
  kind: Literal["neo4j_read_failure", "graph_load_failed"]
  message: str
}

RetrievalScoringOutcome {
  outcome: Literal["success","failure"]
  success: RetrievalScoringSuccess | None
  failure: RetrievalScoringFailure | None
}
```

**RET-005 消费说明**（本任务不实现）：

- HTTP Response `score` ← `final_score`
- `memories[]` 字段映射 ← `ScoredRetrievalMemory` 子集 + Entity 名称格式化
- `warnings` HTTP 字符串 ← 内部 Warning kind 映射（RET-005）

### 6.2 编排服务（`domain/services/retrieval_scoring_service.py`）

```text
async score(query: RetrievalScoringQuery) -> RetrievalScoringOutcome
```

流程：

1. 校验 `top_k` / `current_time` / `user_id`。
2. 合并 direct+expanded → 逐条 ACT-R 计分（跳过缺失 retrieval 分候选）。
3. §7 排序 → 取 Top-K。
4. 若 Top-K 非空：`RetrievalEvidenceReadRepository.load_evidence_for_memories(user_id, top_k_ids)` → 聚合。
5. 组装 `ScoredRetrievalMemory` 列表 + 透传 warnings → `RetrievalScoringSuccess`。

Factory：`create_retrieval_scoring_service(settings, evidence_repo)`.

## 7. final_ordering + top_k ownership

### 7.1 排序键（§2.2.11 #5 — RET-004 唯一拥有）

对计分成功的候选稳定排序：

1. `final_score` **DESC**
2. `memory.latest_source_time` **DESC**（`null` → `0`）
3. `memory.importance` **DESC**
4. `memory_id` **ASC**

纯函数：`sort_scored_candidates(candidates) -> list[ScoredCandidateIntermediate]`。

### 7.2 Top-K 截断（§2.2.11 #6 — RET-004 拥有）

- 排序后取前 `top_k` 条（`RetrievalScoringQuery.top_k`）。
- **RET-005** 负责 HTTP 请求 `top_k` 默认值与 `invalid_top_k`；本任务只接受已校验整数。
- Evidence 加载 **仅**针对截断后列表（§5.1）。

### 7.3 空结果

| 场景 | 输出 |
|---|---|
| 上游候选为空 | `scored_memories=[]` |
| 全部被跳过（缺 retrieval 分） | `scored_memories=[]` |
| Top-K 后列表空 | 不调用 Evidence |

## 8. user_isolation

| # | 规则 | Enforcement | 测试 ID |
|---|---|---|---|
| UISO-1 | Evidence Cypher 同时约束 `Memory.user_id` 与 `Evidence.user_id = $user_id` | `RetrievalEvidenceReadRepository` | C3, I2 |
| UISO-2 | `memory_ids` 批量查询仍绑定 `$user_id` | Cypher + 契约测试 | C3 |
| UISO-3 | 评分/Evidence 聚合不读取请求 `user_id` 以外用户数据 | Service 入参强制 | U8 |
| UISO-4 | 交叉用户 Evidence 不得出现在 `source_message_ids` | Integration fixture A/B | I2 |
| UISO-5 | 禁止无 `user_id` 的 Evidence 批量读 | grep + `authorized_read_cypher_queries()` | C3 |
| UISO-6 | 日志禁止记录 Memory `content` 全文 | Code Review checklist | — |

## 9. failure_mapping（内部 Outcome — 非 RET-005 HTTP）

| 失败源 | 内部表示 | scored_memories | Warning 透传 |
|---|---|---|---|
| 上游 `neo4j_read_failure` | `failure.neo4j_read_failure` | 无 | — |
| Evidence Neo4j 读失败 | `failure.graph_load_failed` | 无 | — |
| 入参非法（top_k/current_time） | `ValueError` | — | — |
| 候选缺 retrieval 分 | 跳过该条 | 其余正常 | 原 warnings 保留 |
| Top-K 无 Evidence 边 | `success` | `evidence_count=0` | 原 warnings 保留 |
| 上游 success 空候选 | `success` 空 | `[]` | 原 warnings 保留 |

**禁止**：在本任务返回 HTTP 错误码字符串、`retrieval_timeout` 或 RET-005 Warning HTTP 映射。

## 10. durable_write_scope

```yaml
durable_write_scope: NONE
```

- **零** Mongo/Neo4j/ES/Kafka 写入。
- **零** `retrieval_count` / `last_retrieved_time` 更新（RET-005 §2.2.13）。
- **零** Evidence/Memory 突变。

## 11. preserve boundaries

| 边界 | 要求 |
|---|---|
| RET-001/002/003 | **禁止**修改生产语义；允许 import 其模型 |
| EXT-005 `EvidenceLookupRepository` | **禁止**修改或混用为 Evidence 聚合读 |
| EXT-007 索引同步 | **禁止**触碰 |
| DEV-006 / PR #13 | **永久禁止** |
| Settings Contract | **禁止**新增字段或修改 validator |
| HTTP / OpenAPI | **禁止**；归属 RET-005 |
| `retrieval_count` 更新 | **禁止**；归属 RET-005 |

## 12. replay_idempotency

| 场景 | 预期行为 |
|---|---|
| 相同 `RetrievalScoringQuery`（含相同 `current_time`）重复调用 | 相同 `scored_memories` 顺序、分数、evidence 聚合 |
| 相同输入不同 `current_time` | 仅 `recency_score` / `final_score` 可能变化；测试分开断言 |
| Evidence 聚合 | 确定性排序 + 去重；同图数据同输出 |
| 并发相同查询 | 只读；无共享可变状态 |
| 进程重启 | 行为与首次一致 |
| Top-K 边界 | 同分 tie-break 稳定（§7.1） |

## 13. numerical_correctness_test_cases

以下算例 **必须**作为单元测试精确断言（允许 `pytest.approx` 于 `final_score` ±1e-6）。

### NC-1 — frequency_score 饱和

| retrieval_count | frequency_score |
|---|---|
| 0 | 0.0 |
| 1 | ln(2)/ln(21) ≈ 0.229574 |
| 19 | ln(20)/ln(21) ≈ 0.984293 |
| 20 | 1.0 |
| 100 | 1.0 |

### NC-2 — recency_score 半衰期

设 `recency_half_life_days=30`，`current_time=1_000_000`，`last_retrieved_time=None`，`latest_source_time=None` → `reference_time=0` → `age_days=current_time/86400` → `recency_score=exp(-ln(2)*age_days/30)`。

固定小数值用例：

| current_time | reference_time | age_days | recency_score |
|---|---|---|---|
| 86400 | 0 | 1.0 | exp(-ln(2)/30) ≈ 0.977159 |
| 86400*30 | 0 | 30.0 | 0.5 |
| 86400*60 | 86400*30 | 30.0 | 0.5 |
| 0 | 0 | 0 | 1.0 |

### NC-3 — 权重合成（active，无惩罚）

Settings 默认权重；分量全 `1.0` → `final_score=1.0`。

分量：`retrieval=0.8, importance=0.6, confidence=0.9, frequency=0.5, recency=0.4` →

```text
weighted = 0.55*0.8 + 0.15*0.6 + 0.10*0.9 + 0.10*0.5 + 0.10*0.4
         = 0.44 + 0.09 + 0.09 + 0.05 + 0.04 = 0.71
final_score = 0.710000
```

### NC-4 — status 惩罚

NC-3 基础上 `status=conflicted` → `0.71 * 0.85 = 0.603500`；`superseded` → `0.71 * 0.60 = 0.426000`。

### NC-5 — retrieval_score 选择

| candidate_origin | normalized | graph | 使用 |
|---|---|---|---|
| direct | 0.75 | 0.30 | 0.75 |
| expanded | None | 0.42 | 0.42 |
| direct | None | 0.50 | **跳过** |

### NC-6 — clamp

某分量计算结果为 `1.2`（mock）→ clamp 后 `1.0` 再参与加权。

### NC-7 — 排序 tie-break

两候选 `final_score=0.710000`；A：`latest_source_time=100`，`importance=0.5`；B：`latest_source_time=200`，`importance=0.9` → **B 在前**（较新 source_time）。

再 tie：同 `latest_source_time` → 较高 `importance` 在前；仍 tie → `memory_id ASC`。

### NC-8 — evidence 聚合顺序

Evidence E1(`source_time_end=200`, `id=e2`, msgs `[m2,m1]`)，E2(`source_time_end=200`, `id=e1`, msgs `[m3]`)，E3(`source_time_end=100`, msgs `[m1,m4]`) →

排序：E2(e1) 先于 E1(e2)（同 time，id ASC）→ 合并 `[m3, m2, m1, m4]`；`evidence_count=3`。

若 `max_source_message_ids=2` → `[m3, m2]`，`evidence_count` 仍为 `3`。

## 14. minimum_test_plan

### 14.1 Unit Test

| ID | 场景 | 预期 |
|---|---|---|
| U1 | NC-1..NC-6 全算例 | 精确数值 |
| U2 | NC-7 排序 tie-break | 顺序断言 |
| U3 | NC-8 evidence 聚合 | 顺序 + dedup + cap |
| U4 | direct 缺 `normalized_retrieval_score` | 跳过 |
| U5 | expanded 缺 `graph_retrieval_score` | 跳过 |
| U6 | 全部跳过 | success 空列表 |
| U7 | top_k=3 截断 | 仅 3 条 |
| U7b | top_k > len(valid_scored_candidates)（SF-3） | 返回全部有效候选；顺序不变；Evidence 查询仅含返回 ID |
| U8 | 错误 user_id 不传下游（mock repo 断言参数） | 参数绑定 |
| U9 | status 惩罚 conflicted/superseded | NC-4 |
| U10 | warnings 透传 | 与输入相同 |
| U11 | 上游 failure 传播 | neo4j_read_failure |
| U12 | Evidence repo 异常 | graph_load_failed |
| U13 | Top-K 空 | 不调用 Evidence repo |
| U14 | injectable `current_time` | 无 wall-clock 依赖 |
| U15 | RET-003 回归 | 既有 ret003 测试全通过（不修改语义） |

### 14.2 Contract Test

| ID | 场景 | 预期 |
|---|---|---|
| C1 | 不修改 RET-001/002/003/EXT-005 生产文件 | git diff 白名单 |
| C2 | Evidence Cypher 含双 user_id 约束 | authorized_read_cypher_queries |
| C3 | UISO-1..5 | 契约断言 |
| C4 | 无 Evidence mutate Cypher | grep 断言 |

### 14.3 Integration Test

| ID | 场景 | 预期 |
|---|---|---|
| I1 | Neo4j Memory + 多 Evidence SUPPORTS | evidence_count + source_message_ids 正确 |
| I2 | 用户 B Evidence 不可见于用户 A 查询 | 隔离 |
| I3 | Top-K 后 batch 单次查询（spy 计数） | 1 次 Neo4j evidence 调用 |
| I4 | 无 Evidence 的 Memory | count=0, ids=[] |
| I5 | ACT-R 端到端分数与 unit 算例一致 | 固定 current_time |

### 14.4 E2E Test

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — RET-006 |

### 14.5 失败注入

| ID | 场景 | 预期 |
|---|---|---|
| F1 | Neo4j Evidence timeout | graph_load_failed |
| F2 | 并发 10 路相同评分查询 | 无异常；结果一致 |

## 15. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/retrieval_scoring.py` | 创建 | Outcome / ScoredRetrievalMemory / ActRScoreComponents |
| `src/memory_system/domain/services/act_r_scoring.py` | 创建 | ACT-R 纯函数（§4） |
| `src/memory_system/domain/services/evidence_aggregation.py` | 创建 | source_message_ids 确定性聚合纯函数 |
| `src/memory_system/domain/services/retrieval_scoring_service.py` | 创建 | 编排：合并→计分→排序→top_k→Evidence |
| `src/memory_system/infrastructure/neo4j/retrieval_evidence_read_repository.py` | 创建 | Top-K Evidence 批量只读 |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `authoritative_recall_service.py`、`rrf_fusion.py`、`evidence_lookup_repository.py`、`settings/`、`entrypoints/`、DEV-006）。

## 16. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_act_r_scoring.py` | 创建 | NC-1..NC-6 + retrieval 选择 |
| `tests/unit/test_evidence_aggregation.py` | 创建 | NC-8 + dedup/cap |
| `tests/unit/test_retrieval_scoring_service.py` | 创建 | 编排、failure、top_k、透传 |
| `tests/unit/test_retrieval_evidence_read_repository.py` | 创建 | Cypher 授权 + 解析（mock driver） |
| `tests/integration/test_ret004_evidence_aggregation.py` | 创建 | Neo4j Fixture I1..I5 |
| `tests/support/ret004_neo4j_fixtures.py` | 创建 | Evidence SUPPORTS Fixture（可扩展 ret003） |

**白名单外任何 `tests/**` 变更 → FAIL**（RET-003 测试文件不得修改语义；运行回归但不在白名单内编辑）。

### 16.1 governance_file_whitelist（Release Operator 各 phase）

| Phase | 允许路径 | 目的 |
|---|---|---|
| `PLAN_LANDING` | `02_开发管理/tasks/RET-004-act-r-scoring-evidence-aggregation.md` | 已批准 Task Plan |
| `PLAN_LANDING` | `02_开发管理/progress.md` | 规划态登记 |
| `PLAN_LANDING` | `02_开发管理/master_plan.md` | RET-004 规划登记 |
| `IMPLEMENTATION_RELEASE` | §15 production_file_whitelist 全部 | 实现 |
| `IMPLEMENTATION_RELEASE` | §16 test_file_whitelist 全部 | 测试 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/tasks/RET-004-act-r-scoring-evidence-aggregation.md` | 执行记录 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/progress.md` | 状态登记 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/master_plan.md` | 状态备注 |
| `POST_MERGE_CLEANUP` | 上述三份治理文件 | 完成登记 |

**永久禁止**（所有 phase）：DEV-006、PR #13；RET-001/002/003 生产语义文件；规格正文。

### 16.2 PLAN_LANDING commit contract

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含：

1. `02_开发管理/tasks/RET-004-act-r-scoring-evidence-aggregation.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`

Commit message（精确）：

```text
docs(plan): add RET-004 act-r scoring and evidence aggregation plan
```

随后从更新后的 `main` 创建 exact feature branch `feat/RET-004-act-r-scoring-evidence-aggregation`。

## 17. NORMAL classification（HARD_BLOCK / SAFE_AUTO / MVP_LOCAL / DEFERRED）

| ID | 项 | 分类 | 说明 |
|---|---|---|---|
| CL-1 | 修改 RET-001/002/003 生产语义 | **HARD_BLOCK** | 仅消费上游 Outcome |
| CL-2 | 复用 EXT-005 `EvidenceLookupRepository` 做 Evidence 聚合 | **HARD_BLOCK** | 语义不同；须新建仓储 |
| CL-3 | Top-K 前加载 Evidence | **HARD_BLOCK** | §2.2.12 #1 |
| CL-4 | Evidence 失败伪造空来源成功返回 | **HARD_BLOCK** | §2.2.12 #5 |
| CL-5 | HTTP Response / Warning HTTP 映射 | **HARD_BLOCK** | RET-005 |
| CL-6 | retrieval_count 更新 | **HARD_BLOCK** | RET-005 §2.2.13 |
| CL-7 | DEV-006 / PR #13 | **HARD_BLOCK** | 治理永久禁止 |
| CL-8 | `latest_source_time null → 0` in reference_time | **MVP_LOCAL_DECISION** | LD-1；与 RET-003 排序一致 |
| CL-9 | `source_time_end null → 0` in Evidence 排序 | **MVP_LOCAL_DECISION** | LD-2 |
| CL-10 | 缺 retrieval 分跳过候选（非全局失败） | **MVP_LOCAL_DECISION** | LD-3 |
| CL-11 | injectable `current_time` 参数 | **SAFE_AUTO_REMEDIATION** | 测试确定性 |
| CL-12 | 新建 `evidence_aggregation.py` 纯函数 | **SAFE_AUTO_REMEDIATION** | 与 act_r 分离 |
| CL-13 | defensive clamp 分量 | **SAFE_AUTO_REMEDIATION** | 防 Neo4j 脏数据 |
| CL-14 | Integration 复用 ret003 Neo4j compose | **SAFE_AUTO_REMEDIATION** | 减少 fixture 重复 |
| CL-15 | E2E Retrieval 全链路 | **DEFERRED** | RET-006 |
| CL-16 | HTTP top_k 默认值 / invalid_top_k | **DEFERRED** | RET-005 |
| CL-17 | 新依赖 / Migration / Settings 变更 | **HARD_BLOCK** | dependency_changes_expected=NONE |

## 18. 任务目标

在 RET-003 `AuthoritativeRecallSuccess` 之后实现 §2.2.11 ACT-R 评分与 §2.2.12 Evidence 批量聚合：合并 direct+expanded 候选、按配置权重计算 `final_score`、确定性排序并截断 Top-K、对 Top-K 执行单次 Neo4j Evidence 读并生成 `evidence_count` / `source_message_ids`；输出供 RET-005 HTTP 组装的 `RetrievalScoringOutcome`；零 durable 写入。

可验证目标：

1. **`act_r_scoring.py`** 纯函数覆盖 §4 全公式与 NC 算例。
2. **`RetrievalScoringService`** 编排计分→排序→top_k→Evidence；透传 RET-003 warnings。
3. **`RetrievalEvidenceReadRepository`** 批量只读 Evidence；双 user_id 隔离。
4. **`evidence_aggregation.py`** 确定性 message_id 合并。
5. Integration：Neo4j Evidence SUPPORTS Fixture；I1..I5 通过。
6. RET-003 回归测试全通过（语义不变）。

## 19. 非目标与黑名单（must_not）

- HTTP Retrieval API / Response DTO / Warning HTTP 字段 — **RET-005**。
- `retrieval_count` / `last_retrieved_time` Neo4j 更新 — **RET-005 §2.2.13**。
- 修改 RET-001/002/003 生产服务或 RRF/图扩展语义。
- 修改 EXT-005 `EvidenceLookupRepository`。
- Mongo/Neo4j/ES/Kafka **写入**；Evidence **突变**。
- **DEV-006 / PR #13**。
- 新依赖 / Migration / Settings Contract 变更。
- Session→Retrieval E2E — **RET-006**。

## 20. 当前代码状态与前置检查

### 20.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `c8d9d38d92414b9e041dd3d97dcbfd17b9e61582`（与用户给定 `planning_baseline_main` 一致） |
| `git status --short` | 空 |
| RET-001 / RET-002 / RET-003 | `completed`；PR #44 / #45 / #46 MERGED |
| ACT-R 评分 / Evidence 聚合检索读 | **不存在** — 无 `act_r_scoring` / `retrieval_scoring` / `retrieval_evidence_read` |
| workflow | `NORMAL`，explicit |

### 20.2 已存在可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| `AuthoritativeRecallSuccess` / `ValidatedRetrievalCandidate` | `domain/models/authoritative_recall.py` | RET-003 输入契约 |
| `RetrievalMemorySnapshot` | `domain/models/retrieval_memory_snapshot.py` | ACT-R 字段来源 |
| `MemoryRetrievalSettings` | `settings/models.py` | 权重/半衰期/max_source_message_ids |
| `rrf_fusion.py` | `domain/services/rrf_fusion.py` | 纯函数模块模式参考 |
| `EvidenceLookupRepository` | `infrastructure/neo4j/evidence_lookup_repository.py` | **只读参考**；禁止混用 |
| `ret003_neo4j_fixtures.py` | `tests/support/ret003_neo4j_fixtures.py` | Integration Fixture 基础 |

### 20.3 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无 ACT-R 纯函数 | 无 `act_r_scoring` |
| 无评分编排服务 | 无 `retrieval_scoring_service` |
| 无 Evidence 聚合读仓储 | 无 `retrieval_evidence_read_repository` |
| 无 RET-004 测试 | `tests/` 无 `test_ret004` / `test_act_r` |

**结论**：新建 ACT-R 纯函数、Evidence 聚合纯函数、评分编排服务、Evidence 读仓储与领域模型；不修改 RET-003 / EXT-005 生产语义。

## 21. mvp_local_decisions

| ID | 决策 | 理由 | 分类 |
|---|---|---|---|
| LD-1 | `latest_source_time is None` → `reference_time` 贡献 `0` | 规格 `max(last_retrieved_time or 0, latest_source_time)` 在 null 时歧义；与 RET-003 排序 null→0 一致 | MVP_LOCAL_DECISION |
| LD-2 | Evidence `source_time_end is None` → 排序视为 `0` | 规格未明示；排在已知时间 Evidence 之后 | MVP_LOCAL_DECISION |
| LD-3 | 缺 required retrieval 分 → 跳过候选而非全局失败 | 防御 RET-003 异常数据；其余候选仍可返回 | MVP_LOCAL_DECISION |
| LD-4 | 拆分 `act_r_scoring.py` 与 `evidence_aggregation.py` | 公式与 message 合并正交；便于单测 | SAFE_AUTO_REMEDIATION |
| LD-5 | `current_time` 由调用方注入 | 单元/集成测试确定性 | SAFE_AUTO_REMEDIATION |
| LD-6 | 新建 `RetrievalEvidenceReadRepository`；不扩展 EXT-005 | EXT-005 仅 existence check | HARD_BLOCK 若混用 |
| LD-7 | Top-K 无 Evidence → 空数组成功 | §2.2.12 允许 count=0 | SAFE_AUTO_REMEDIATION |

## 22. 实现方案

### Step 1 — 领域模型 `retrieval_scoring.py`

- `ActRScoreComponents`、`EvidenceAggregationResult`、`ScoredRetrievalMemory`
- `RetrievalScoringQuery`、`RetrievalScoringSuccess` / `Failure` / `Outcome`（§6.1）

### Step 2 — ACT-R 纯函数 `act_r_scoring.py`

- §4.1 全公式；`select_retrieval_score`；NC 算例覆盖

### Step 3 — Evidence 聚合纯函数 `evidence_aggregation.py`

- `aggregate_evidence_for_memory`；NC-8

### Step 4 — Neo4j Evidence 读仓储 `retrieval_evidence_read_repository.py`

- 批量 Cypher §5.2；`async load_evidence_for_memories(user_id, memory_ids)`
- `authorized_read_cypher_queries()`；timeout from settings

### Step 5 — 编排服务 `retrieval_scoring_service.py`

- §6.2 流程；factory `create_retrieval_scoring_service`

### Step 6 — 单元测试

- §14.1 U1..U15；§13 NC 全算例

### Step 7 — Integration + Fixture

- `ret004_neo4j_fixtures.py`：Memory + Evidence SUPPORTS + source_message_ids
- `test_ret004_evidence_aggregation.py`：I1..I5

## 23. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 只读 |
| 幂等 | **是** | §12 确定性 |
| 并发 | 只读无锁 | Neo4j 并发安全 |
| 版本冲突 | 不适用 | 无乐观锁 |
| 用户隔离 | **强制** | §8 |
| 部分失败 | **是** | 缺分跳过；Evidence 失败全局 fail |
| 进程异常恢复 | 不适用 | 无 in-flight 写 |

## 24. 验收标准

- [ ] §2.2.11 五分量 + 惩罚 + clamp + round(6) + 排序 + top_k
- [ ] §2.2.12 Top-K 后单次 batch Evidence 读 + 确定性 `source_message_ids` + `evidence_count`
- [ ] Evidence 失败 → 内部 `graph_load_failed`；不伪造空来源
- [ ] RET-003 warnings 透传；不 HTTP 映射
- [ ] 不修改 RET-001/002/003/EXT-005 生产语义
- [ ] NC-1..NC-8 单元测试精确通过
- [ ] Integration Neo4j Fixture I1..I5 通过；RET-003 回归通过
- [ ] scoped unit + integration 全通过；Ruff/Mypy（变更文件）通过
- [ ] Review 无 P0/P1

## 25. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | 无；与 §2.2.11/§2.2.12、master_plan RET-004 一致 |
| 前置任务 | RET-003 completed |
| 主要风险 | ① 误用 EXT-005 仓储；② Top-K 前加载 Evidence；③ retrieval 分源选错 |
| 非阻塞 | OI-008（RET-005 API 编辑性） |
| DEV-006 | **禁止触碰** PR#13 |

## 26. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/RET-004-act-r-scoring-evidence-aggregation"
baseline_main: "c8d9d38d92414b9e041dd3d97dcbfd17b9e61582"
expected_commits:
  - "docs(plan): add RET-004 act-r scoring and evidence aggregation plan (includes progress.md + master_plan.md planning metadata)"
  - "feat(ret): add act-r scoring, top-k ordering, and evidence aggregation"
  - "docs(status): record RET-004 implementation commit and PR"
  - "docs(status): complete RET-004 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "RET-001/002/003 authoritative/rrf/hybrid production files"
  - "EXT-005 evidence_lookup_repository"
  - "HTTP API / RET-005 warnings / retrieval_count updates"
  - "Migration / dependency / Settings"
```

## 27. deferred_for_mvp

| 项 | 说明 |
|---|---|
| HTTP Retrieval API + Response DTO | RET-005 |
| retrieval_count / last_retrieved_time 更新 | RET-005 |
| Retrieval 全链路 E2E | RET-006 |
| HTTP top_k 校验与 default | RET-005 |

## 28. open_issues

| ID | 关系 | 阻塞 RET-004？ |
|---|---|---|
| OI-008 | RET-005 API 编辑性 | **否** |

## 29. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

## 30. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 06:01 UTC | planning | 创建 Task Plan；更新 progress/master_plan 规划态 | — | planning only；未 Git 写 |

## 31. 实际执行结果

### 最终状态

`planned`

## 32. ready for plan review

- 全部 16 节用户清单已覆盖：§2 authoritative_scope … §17 NORMAL classification。
- `progress.md` 已同步 `current_task=RET-004`、`current_task_status=planned`、`next_action=计划审查`。
- `master_plan.md` RET-004 节已登记 Task Plan 路径。
- 未编写业务代码；未 Git 写；Developer 未授权。

READY_FOR_PLAN_REVIEW
