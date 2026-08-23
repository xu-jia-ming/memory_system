# RET-007 SiliconFlow Cross-Encoder Rerank（RRF 后、ACT-R 前）

## 1. 任务信息

```yaml
task_id: RET-007
task_name: SiliconFlow Cross-Encoder Rerank（BAAI/bge-reranker-v2-m3）
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "188305b9e689f8a760fb57904fbadeb3f4ccdad1"
branch: "feat/RET-007-siliconflow-cross-encoder-rerank"
created_at: "2026-08-23 08:00 UTC"
updated_at: "2026-08-23 16:45 UTC"
spec_sections:
  - "§2.2.9 RRF 多路结果融合（消费 fused 候选；不修改 RRF 算法）"
  - "§2.2.10 Neo4j Memory 加载与一跳图谱扩展（插入点：权威 direct 校验之后、图扩展之前）"
  - "§2.2.11 基础 ACT-R 近似评分（direct 候选 normalized_retrieval_score 来源切换为 rerank）"
  - "§2.2.15 失败处理与降级策略（新增非致命 Warning rerank_failed）"
  - "§2.2.16 完整处理流程（插入 Rerank 步骤）"
  - "§2.2.17 MVP 实现边界（将 Cross-Encoder Reranker 从「暂不实现」移至「必须实现」）"
  - "§3.6 全异步客户端（httpx RerankClient，复用 Embedding HTTP 池模式）"
  - "§3.24 连接池、超时与重试（rerank_timeout_seconds）"
  - "§3.28 测试策略（Unit + Contract MockTransport + 可选 Integration）"
prerequisites:
  formal:
    - "RET-003 — SATISFIED/completed; AuthoritativeRecallService + ValidatedRetrievalCandidate"
    - "RET-004 — SATISFIED/completed; act_r_scoring.select_retrieval_score 消费 normalized_retrieval_score"
    - "RET-005 — SATISFIED/completed; RetrievalApiService 编排 fuse_rrf → authoritative → scoring"
    - "DEV-007 — SATISFIED/completed; SiliconFlowEmbeddingClient + create_embedding_client factory 模式"
  implementation_reuse:
    - "fuse_rrf（RET-002；只读调用，不修改）"
    - "AuthoritativeRecallService.recall（RET-003；本任务在 direct 权威校验后插入 rerank 子步骤）"
    - "RetrievalApiService 编排顺序（RET-005；不修改 HTTP Contract）"
    - "SiliconFlowEmbeddingClient 的 retry/redaction/httpx 模式（DEV-007 infrastructure/embedding/）"
    - "Settings.siliconflow_api_key + memory_retrieval.siliconflow_base_url（与 Embedding 共用）"
    - "InternalRetrievalWarning 枚举扩展模式（RET-003/005）"
  baseline_evidence:
    branch: "main"
    head: "188305b9e689f8a760fb57904fbadeb3f4ccdad1"
    working_tree_at_planning_start: "dirty — 本地 LoCoMo temporal_only 实验改动未提交；与本任务无关，实施前须在干净 feat 分支起步"
    verification: "git rev-parse HEAD=188305b9e689f8a760fb57904fbadeb3f4ccdad1"
approval_gates:
  planning: PLAN_APPROVED
  approval_posture: "PLAN_APPROVED — human confirmed 2026-08-23"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: true
  release_operator_authorized: true
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feat/RET-007-siliconflow-cross-encoder-rerank"
  IMPLEMENTATION_RELEASE: "only after CODE_REVIEW_APPROVED; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after verified MERGED PR; exact feature branch cleanup and docs(status): complete on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_write_scope: NONE
```

### 1.1 本轮门禁与停止条件

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现、测试实现、Migration、配置落地或依赖变更"
  - "进入 Developer、Code Reviewer、Commit Recorder 或 Release Operator"
  - "执行任何 Git 写命令"
  - "修改权威规格正文（Amendment 在 PLAN_APPROVED 后由独立 docs 流程记录）"
  - "触碰 DEV-006 / PR #13"
  - "修改 RET-001/002 BM25/Vector/RRF 生产算法语义"
stop_if:
  - "任何实现步骤需要新 Python 依赖"
  - "任何实现步骤需要 Elasticsearch / Mongo / Kafka / Neo4j schema 变更"
  - "任何实现步骤需要修改 HTTP Retrieval Request/Response Contract（本任务仅服务端配置开关）"
  - "任何实现步骤需要 LoCoMo answer_pipeline 的 LLM rerank 路径（eval 协议 rerank:false 保持不变）"
  - "SILICONFLOW_API_KEY 不可用且无法以 MockTransport 完成 Contract 测试"
blocking_open_issues: []
nonblocking_open_issues:
  - "LoCoMo conv-30 基线对比（README 62.6%）— 实施后可做可选 ablation，非阻塞合并"
```

### 1.2 背景与动机

当前检索链路：`BM25 + Vector → RRF (k=60, fused_top_n=30) → Neo4j 权威加载 → 一跳图扩展 → ACT-R → Top-K`。

规格 §2.2.17 将 **Cross-Encoder Reranker** 列为 MVP 暂不实现。经人工确认，本任务将其纳入 MVP，使用硅基流动托管 **`BAAI/bge-reranker-v2-m3`**，与现有 **`BAAI/bge-m3` Embedding** 共用 `SILICONFLOW_API_KEY` 与 `siliconflow_base_url`。

**插入位置（已确认）**：RRF 融合之后、一跳图扩展之前；对 **direct** 候选（已完成 Neo4j 权威校验并具备 rerank 文本）重排，再以其顺序作为图扩展 seed；ACT-R 的 direct `normalized_retrieval_score` 改为 rerank 相关性分数（0–1），`rrf_score` 保留供 telemetry/debug。

## 2. authoritative_scope

| 维度 | 归属 RET-007 | 非 RET-007（显式排除） |
|---|---|---|
| `SiliconFlowRerankClient` + `create_rerank_client` factory | **是** | 修改 EmbeddingClient |
| `CrossEncoderRerankService` 纯函数/领域服务 | **是** | — |
| AuthoritativeRecallService 内 direct 候选 rerank 子步骤 | **是** | 修改图扩展算法/Neo4j 读模型 |
| `memory_retrieval` Settings 新字段（rerank_*） | **是** | 修改 embedding_* 语义 |
| `configs/base.yaml` rerank 默认值 | **是** | — |
| Warning `rerank_failed` + 降级为 RRF 顺序 | **是** | 新增 HTTP 致命码 |
| ACT-R `select_retrieval_score` 行为 | **否** — 仍读 `normalized_retrieval_score`；由 rerank 步骤写入新值 | 修改 ACT-R 权重公式 |
| BM25 / Vector / `fuse_rrf` | **否** | **RET-001/002** |
| HTTP `/api/v1/memory/retrieval` Request 字段 | **否** | **RET-005** |
| LoCoMo eval `rerank:false` answer 协议 | **否** | eval 脚本非本任务必须项 |
| ES/Mongo/Kafka/Neo4j 写入 | **否** | **HARD_BLOCK** |

## 3. spec_amendment_record（PLAN_APPROVED 后落地；本轮不改正文）

### 3.1 §2.2.10 后新增小节（建议编号 §2.2.10a）

**Cross-Encoder 重排（SiliconFlow BAAI/bge-reranker-v2-m3）**

1. 在 RRF 融合并完成 Neo4j 权威 direct 候选加载与 `user_id` / `memory_type` / `status` 重校验之后，若 `rerank_enabled=true`，对 direct 候选调用 Cross-Encoder Rerank。
2. Rerank 输入：
   - `query`：标准化后的检索 query（与 Vector 通道相同 normalized query）。
   - `documents[]`：每条 direct 候选的 `search_text`（Neo4j 权威字段；缺失时降级使用该候选的 `content` 截断至 `embedding_max_input_tokens` 字符预算的等价策略，与 Vector 索引文本一致）。
3. 模型：`BAAI/bge-reranker-v2-m3`；端点：`POST {siliconflow_base_url}/v1/rerank`；鉴权：`Authorization: Bearer {SILICONFLOW_API_KEY}`。
4. 输出：`relevance_score`（float，越高越相关）；按分数降序重排 direct 候选；将 `normalized_retrieval_score` 覆盖为 `relevance_score`（已在 [0,1]）；保留原 `rrf_score` 不变。
5. `top_n` 默认等于 direct 候选数（≤ `fused_top_n`）；API 返回顺序即最终 direct 顺序，再进入图扩展。
6. 图扩展 seed 顺序：使用 rerank 后的 direct 顺序（而非 RRF 顺序）。
7. `graph_expanded` 候选 **不** 调用 rerank；其 `graph_retrieval_score` 语义不变。

### 3.2 §2.2.15 非致命 Warning 增补

| Warning | 含义 |
| --- | --- |
| `rerank_failed` | Cross-Encoder 服务异常或超时；已保留 RRF 顺序与原始 `normalized_retrieval_score` |

### 3.3 §2.2.16 流程图插入

在 `Load Authoritative Memory from Neo4j` 与 `Revalidate ...` 之后、`Execute Optional One-Hop Graph Expansion` 之前插入：

```text
Cross-Encoder Rerank Direct Candidates (optional, config-gated)
```

### 3.4 §2.2.17 边界调整

- **移至必须实现**：Cross-Encoder Reranker（SiliconFlow `BAAI/bge-reranker-v2-m3`）。
- **仍暂不实现**：MongoDB Retrieval Log、LLM Query 改写、多跳图推理、个性化权重学习等（原列表其余项不变）。

## 4. siliconflow_rerank_api_contract

### 4.1 预研验证（2026-08-23）

使用环境变量 `SILICONFLOW_API_KEY`（与 Embedding 相同）调用：

```bash
curl -sS -X POST "https://api.siliconflow.cn/v1/rerank" \
  -H "Authorization: Bearer $SILICONFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "BAAI/bge-reranker-v2-m3",
    "query": "When did Gina get her tattoo?",
    "documents": [
      "Gina got her tattoo in March 2022.",
      "Gina likes hiking on weekends.",
      "The weather was sunny yesterday."
    ],
    "top_n": 3
  }'
```

**结果**：HTTP **200**；`results[0].index=0`，`relevance_score≈0.998`；无关文档分数接近 0。`document` 字段为 `null`（按 `index` 映射回候选）。**结论：API Key 通用，无需新 Secret。**

### 4.2 Request Body

| 字段 | 类型 | 必填 | 默认 |
|---|---|---|---|
| `model` | `str` | 是 | settings `rerank_model` |
| `query` | `str` | 是 | normalized retrieval query |
| `documents` | `list[str]` | 是 | direct 候选 search_text |
| `top_n` | `int` | 否 | `len(documents)` |
| `max_chunks_per_doc` | `int` | 否 | settings 可选 |
| `overlap_tokens` | `int` | 否 | settings 可选 |

### 4.3 Response（消费字段）

```json
{
  "results": [
    {"index": 0, "relevance_score": 0.9975565671920776}
  ],
  "meta": {"tokens": {"input_tokens": 57}}
}
```

- 按 `results` 顺序（已按 score 降序）映射 `index` → `memory_id`。
- 未出现在 `results` 中的候选（异常响应）→ 视为 `rerank_failed`，保持 RRF 顺序。

### 4.4 错误与重试

对齐 `SiliconFlowEmbeddingClient`：

- HTTP 429 / 5xx / 网络超时：指数退避重试（`MAX_HTTP_ATTEMPTS` 复用 embedding retry 模块或抽取共享常量）。
- 401 / 400：不重试；记录 redacted 日志；降级 `rerank_failed`。
- 日志禁止打印 query 全文与 document 全文；允许 `user_id`、query_hash、`memory_id` 列表长度、trace id。

## 5. settings_contract

在 `MemoryRetrievalSettings`（`settings/models.py`）新增：

| 字段 | 类型 | 默认 | 校验 |
|---|---|---|---|
| `rerank_enabled` | `bool` | `true` | — |
| `rerank_model` | `str` | `"BAAI/bge-reranker-v2-m3"` | 非空 |
| `rerank_top_n` | `int` | `30` | `1 <= rerank_top_n <= fused_top_n` |
| `rerank_timeout_seconds` | `int` | `5` | 正整数；≤ `retrieval_total_timeout_seconds` |
| `rerank_max_chunks_per_doc` | `int \| null` | `null` | 若设置则 > 0 |
| `rerank_overlap_tokens` | `int \| null` | `null` | 若设置则 ≥ 0 |

`configs/base.yaml` 同步上述默认值。

**启动校验**（`settings/validators.py`）：

- 当 `rerank_enabled=true` 且 `embedding_provider=siliconflow` 时，要求 `SILICONFLOW_API_KEY` 非空（与 embedding 同一规则，不新增 env 名）。
- `rerank_timeout_seconds` 参与 RET-005 总超时预算（与 embedding/elasticsearch/neo4j 同级）。

## 6. implementation_design

### 6.1 模块布局

```text
src/memory_system/infrastructure/rerank/
  __init__.py
  errors.py              # RerankServiceError（对齐 EmbeddingServiceError）
  types.py               # RerankResult, RerankScoredDocument
  retry.py               # 复用或从 embedding/retry 提取共享
  siliconflow_client.py  # SiliconFlowRerankClient
  factory.py             # create_rerank_client(settings, http_client) -> RerankClient Protocol

src/memory_system/domain/services/cross_encoder_rerank_service.py
  rerank_direct_candidates(query, candidates, settings, client) -> RerankOutcome
```

### 6.2 `RerankClient` Protocol

```python
async def rerank(self, *, query: str, documents: list[str], top_n: int) -> RerankResult: ...
```

### 6.3 `CrossEncoderRerankService` 行为

**输入**：`list[ValidatedRetrievalCandidate]`（仅 `candidate_origin=="direct"` 且已通过 Neo4j 校验）。

**步骤**：

1. 若 `not rerank_enabled` 或 `len(direct)==0`：no-op。
2. 构建 `documents[]`；空 `search_text` 且空 `content` 的候选跳过 rerank（保留原位，记 debug 日志）。
3. 调用 `SiliconFlowRerankClient.rerank`；`top_n=min(rerank_top_n, len(documents))`。
4. 成功：按 API 顺序重排；更新 `normalized_retrieval_score=relevance_score`。
5. 失败：返回 `warnings=[rerank_failed]`；候选顺序与分数保持 RRF 结果。

**输出**：`RerankOutcome{direct_candidates, warnings}`。

### 6.4 AuthoritativeRecallService 集成点

在 `authoritative_recall_service.py` 中，**direct 候选 Neo4j 校验完成之后、图扩展之前**：

```text
validated_direct = ...
rerank_outcome = await cross_encoder_rerank_service.rerank_direct_candidates(...)
validated_direct = rerank_outcome.direct_candidates
warnings.extend(rerank_outcome.warnings)
seeds_for_graph_expand = validated_direct   # 新顺序
```

Factory（`create_authoritative_recall_service`）注入 `RerankClient`；`rerank_enabled=false` 时注入 `NoOpRerankClient`。

### 6.5 RetrievalApiService

**不修改**阶段顺序；rerank 作为 AuthoritativeRecallService 内部子步骤，RET-005 编排保持不变：

```text
fuse_rrf → AuthoritativeRecallService.recall（含 rerank）→ RetrievalScoringService.score
```

### 6.6 ACT-R 交互

- **不修改** `act_r_scoring.py` 公式。
- direct 候选：`normalized_retrieval_score` 在 rerank 成功后为 `relevance_score`。
- graph 候选：仍使用 `graph_retrieval_score`。
- `rrf_score` 字段保留，供日志与 future telemetry；HTTP Response 不暴露。

## 7. degradation_and_timeout

| 场景 | 行为 | Warning |
|---|---|---|
| Rerank HTTP 超时 | 跳过 rerank | `rerank_failed` |
| Rerank 4xx/5xx 耗尽重试 | 跳过 rerank | `rerank_failed` |
| `rerank_enabled=false` | 跳过 | 无 |
| 部分 document 为空 | 空 document 候选保持 RRF 相对位置；其余 rerank | 无（或单条 debug） |
| 总检索超时已进入 authoritative 阶段 | 遵循 RET-005 deadline；rerank 子调用受剩余 budget 约束 | 若 authoritative 整体失败则上游处理 |

**禁止**：rerank 失败时返回伪造分数或清空候选列表。

## 8. file_whitelist（IMPLEMENTATION_RELEASE）

### 8.1 新增

- `src/memory_system/infrastructure/rerank/__init__.py`
- `src/memory_system/infrastructure/rerank/errors.py`
- `src/memory_system/infrastructure/rerank/types.py`
- `src/memory_system/infrastructure/rerank/siliconflow_client.py`
- `src/memory_system/infrastructure/rerank/factory.py`
- `src/memory_system/domain/services/cross_encoder_rerank_service.py`
- `tests/unit/test_siliconflow_rerank_client.py`
- `tests/unit/test_cross_encoder_rerank_service.py`
- `tests/contract/test_authoritative_recall_rerank.py`
- `tests/support/fake_rerank_client.py`

### 8.2 修改

- `src/memory_system/domain/services/authoritative_recall_service.py`
- `src/memory_system/settings/models.py`
- `src/memory_system/settings/validators.py`
- `configs/base.yaml`
- `src/memory_system/app/factory.py`（或同等 wiring 入口：注入 RerankClient）
- `tests/unit/test_authoritative_recall_service.py`（既有用例 + rerank 分支）
- `tests/contract/test_retrieval_api_*.py`（若 warning 矩阵有断言表）
- `02_开发管理/tasks/RET-007-siliconflow-cross-encoder-rerank.md`（status 更新）
- `02_开发管理/progress.md`
- `02_开发管理/master_plan.md`（任务行登记）

### 8.3 显式禁止触碰

- `src/memory_system/domain/services/rrf_fusion.py`
- `src/memory_system/domain/services/bm25_retrieval_service.py`
- `src/memory_system/domain/services/vector_retrieval_service.py`
- `src/memory_system/infrastructure/embedding/siliconflow_client.py`（除提取共享 retry 常量若需）
- `scripts/locomo_eval/**`（可选 ablation 另开 FAST 任务或实施后人工实验）
- Migrations / `pyproject.toml` dependencies

## 9. test_plan

### 9.1 Unit — `SiliconFlowRerankClient`

- MockTransport 200：解析 `results[].index` + `relevance_score`。
- 401/429/500 映射 `RerankServiceError`；429 验证退避重试次数。
- 请求体 `model` / `query` / `documents` / `top_n` 形状。
- 日志 redaction：无 query/document 明文。

### 9.2 Unit — `CrossEncoderRerankService`

- 3 候选 RRF 顺序 A,B,C；mock rerank 返回 C,A,B → 验证顺序与 `normalized_retrieval_score` 更新。
- `rerank_enabled=false` → 原序不变。
- 客户端抛错 → `rerank_failed` warning + RRF 原序。
- 空 direct 列表 → no-op。

### 9.3 Contract — AuthoritativeRecallService

- 端到端 memory fixture：fuse 结果 → authoritative recall with fake rerank → 验证 graph expand seed 顺序随 rerank 变化。
- Warning 传播至 `AuthoritativeRecallOutcome.warnings`。

### 9.4 Regression

- 既有 RET-003/005 contract tests 全绿；`rerank_enabled=false` 时与当前 main 行为 **零 diff**（golden / 快照测试若存在）。

### 9.5 可选 Integration（非合并阻塞）

- 真实 `SILICONFLOW_API_KEY` 单测标记 `@pytest.mark.integration`；CI 默认 skip。

### 9.6 可选 LoCoMo ablation（非合并阻塞）

- 在 `rerank_enabled=true` 部署后，对 conv-30 跑一轮 `evaluate.py`；对比 README 基线 62.6%（50.7/81 mean）。
- 记录于 `data/locomo/conv30/ablations/`，不纳入 PR 白名单除非用户显式授权。

## 10. acceptance_criteria

1. `rerank_enabled=true` 时，direct 候选经 SiliconFlow rerank 重排，`normalized_retrieval_score` 来自 `relevance_score`。
2. 图扩展 seed 顺序与 rerank 后 direct 顺序一致。
3. Rerank 失败时返回 `rerank_failed` warning，顺序与 RRF 分数不变，HTTP 200 检索仍成功。
4. `rerank_enabled=false` 时行为与当前 main 完全一致。
5. 全部 Unit + Contract 测试通过；Ruff + Mypy PASS。
6. 无新依赖、无 Migration、无 durable write、无 HTTP Contract 变更。

## 11. rollout_sequence

```text
1. Plan Review → PLAN_APPROVED（人工）
2. PLAN_LANDING：docs(plan) on main + feat/RET-007-siliconflow-cross-encoder-rerank
3. Developer 按白名单实施 + 测试
4. Code Review → CODE_REVIEW_APPROVED
5. IMPLEMENTATION_RELEASE：commit + PR
6. CI green → 人工 merge
7. POST_MERGE_CLEANUP
8. （可选）LoCoMo conv-30 ablation 记录质量增益
```

## 12. risks_and_mitigations

| 风险 | 缓解 |
|---|---|
| Rerank 增加延迟 | `rerank_timeout_seconds=5`；失败快速降级；总超时预算内执行 |
| 长 `search_text` 超 token | 复用 indexing 相同截断策略；必要时传 `max_chunks_per_doc` |
| API 与 Embedding 争用配额 | 监控 `meta.tokens` 日志；future DEV-010 token budget 共享 |
| LoCoMo 增益不确定 | 生产路径与 eval 解耦；ablation 非阻塞 |

---

**Planner 输出**：`READY_FOR_PLAN_REVIEW`

---

## 13. implementation_progress（Developer 2026-08-23）

```yaml
status: completed
developer_authorized: true
verification:
  unit_contract_scoped: "30 passed"
  ruff: PASS
  mypy: PASS
files_added:
  - src/memory_system/infrastructure/rerank/*
  - src/memory_system/domain/services/cross_encoder_rerank_service.py
  - tests/unit/test_siliconflow_rerank_client.py
  - tests/unit/test_cross_encoder_rerank_service.py
  - tests/contract/test_authoritative_recall_rerank.py
  - tests/support/fake_rerank_client.py
files_modified:
  - src/memory_system/domain/services/authoritative_recall_service.py
  - src/memory_system/domain/models/authoritative_recall.py
  - src/memory_system/settings/models.py
  - src/memory_system/settings/validators.py
  - configs/base.yaml
  - src/memory_system/domain/services/retrieval_api_service.py
  - src/memory_system/domain/services/retrieval_warning_mapper.py
  - tests/unit/test_authoritative_recall_service.py
  - tests/unit/test_retrieval_warning_mapper.py
  - tests/integration/test_ret003_authoritative_recall.py
notes:
  - "Graph expand seed IDs now preserve reranked direct order (not sorted)"
  - "AuthoritativeRecallQuery.normalized_query wired from RetrievalApiService"
```

## 14. merge_record（POST_MERGE_CLEANUP 2026-08-23）

```yaml
status: completed
plan_commit: "52742369c248e46efeba9ac71cff96f867a0acab"
implementation_commit: "5b635c963b3d957e8e9deac7740ceac805af7e72"
implementation_commit_message: "feat(retrieval): add siliconflow cross-encoder rerank after Neo4j validation"
pr: "#66"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/66"
pr_state: MERGED
pr_base: main
pr_head: "feat/RET-007-siliconflow-cross-encoder-rerank"
merge_commit: "42ef374729fc1864dccea55a044e413b4acab7b6"
merged_at: "2026-08-23T08:38:21Z"
verification: "scoped 30 passed; ruff PASS; mypy PASS"
feat_branch: deleted
next_action: "RET-007 completed — NO AUTO-START"
```
