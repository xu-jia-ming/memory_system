# RET-006 Retrieval 阶段 E2E + 失败注入

## 1. 任务信息

```yaml
task_id: RET-006
task_name: Retrieval 阶段 E2E + 失败注入
status: tested
plan_review_round: 2
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "538cf13ac3d33d1f337a9e5f5b450626ddd6529d"
branch: "feat/RET-006-retrieval-e2e-failure-injection"
milestone: "v0.4.0-memory-retrieval"
created_at: "2026-08-13 08:00 UTC"
updated_at: "2026-08-13 08:08 UTC"
human_plan_approved_at: "2026-08-13T08:08:00Z"
spec_sections:
  - "§2.2.5 Memory Retrieval API（HTTP Request/Response；鉴权；user_id 隔离）"
  - "§2.2.12 Evidence + Response DTO（score=final_score；retrieval_source；evidence_count；source_message_ids）"
  - "§2.2.13 召回统计更新（Neo4j retrieval_count + last_retrieved_time）"
  - "§2.2.15 失败处理与降级策略（单通道失败、总超时、Embedding 不可用）"
  - "§2.2.16 完整处理流程（Receive → validate → normalize → BM25+Vector+RRF → Neo4j 权威 → 图扩展 → ACT-R → Top-K Evidence → stats → return）"
  - "§2.2.3 Retrieval Document 同步（EXT-007 写入结果可被检索消费 — E2E-2 子集）"
  - "§3.21 Memory API 鉴权（X-API-Key）"
  - "§3.23 统一 API 响应与 Request ID"
  - "§3.28 测试策略（E2E 层；失败注入；Fake clients；CI 不调用计费 API）"
prerequisites:
  formal:
    - "RET-001 — SATISFIED/completed; BM25 internal channel + ES fixture pattern（PR #44 MERGED）"
    - "RET-002 — SATISFIED/completed; Vector + fuse_rrf（PR #45 MERGED）"
    - "RET-003 — SATISFIED/completed; Neo4j authoritative + graph expansion + MGET（PR #46 MERGED）"
    - "RET-004 — SATISFIED/completed; ACT-R scoring + Evidence aggregation（PR #47 MERGED）"
    - "RET-005 — SATISFIED/completed; POST /api/v1/memory/retrieval + degradation/stats（PR #48 MERGED）"
    - "EXT-007 — SATISFIED/completed; RetrievalIndexSyncService ES upsert（PR #41 MERGED）"
  implementation_reuse:
    - "tests/e2e/conftest.py — infra_stack（redis/mongodb/kafka/neo4j/elasticsearch）；hybrid_api_client（ASGITransport in-process + 真实后端）"
    - "tests/support/ret001_es_fixtures.py / ret002_es_fixtures.py — ES 种子与确定性 embedding"
    - "tests/support/ret003_neo4j_fixtures.py / ret004_neo4j_fixtures.py / ret005_neo4j_fixtures.py — Neo4j 图/Evidence/stats 种子"
    - "tests/support/fake_retrieval_index_embedding_client.py — FakeEmbeddingClient"
    - "memory_system.infrastructure.tei.fake_tokenize_client.FakeTokenizeClient"
    - "memory_system.domain.services.retrieval_index_sync_service.RetrievalIndexSyncService — EXT-007 write path（E2E-2）"
    - "memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state — E2E monkeypatch 注入点（SF-1 Route 绑定）"
    - "tests/integration/test_ext007_retrieval_index_sync.py — Neo4j→ES sync 真实基础设施模式"
  baseline_evidence:
    branch: "main"
    head: "538cf13ac3d33d1f337a9e5f5b450626ddd6529d"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=538cf13ac3d33d1f337a9e5f5b450626ddd6529d"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "PLAN_APPROVED — human confirmed 2026-08-13"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feature branch feat/RET-006-retrieval-e2e-failure-injection"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup; milestone v0.4.0-memory-retrieval closure on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_write_scope: "existing authorized writes only — RET-005 Neo4j retrieval_count/last_retrieved_time（E2E 断言）；EXT-007 ES upsert（E2E-2 仅，经既有 RetrievalIndexSyncService）"
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
  - "修改 RET-001..005 + EXT-007 生产语义"
stop_if:
  - "任何实现步骤需要修改 RET-001..005 / EXT-007 生产 Service 语义"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要 Session→Consolidation 全链路 E2E（归属 E2E-001）"
  - "E2E 暴露生产缺陷时在本任务内修复（须 HALT → 新开修复 Task）"
blocking_open_issues: []
nonblocking_open_issues: []
```

---

## 2. authoritative_scope

本任务 **唯一** 拥有 Retrieval 阶段 **E2E 测试套件**（`tests/e2e/` 下 RET-006 场景）与 **失败注入子集**（§3.28）；闭合 RET-001..005 与 EXT-007 延后的 write→retrieve / Session→Retrieval compose 验证；**不** 拥有检索算法、HTTP 编排或索引同步生产语义。

| 维度 | 归属 RET-006 | 非 RET-006（显式排除） |
|---|---|---|
| `POST /api/v1/memory/retrieval` **E2E** 驱动（真实 ES + Neo4j + in-process FastAPI） | **是** — §2.2.16 HTTP 边界 | 修改 `RetrievalApiService` 编排语义 |
| §2.2.16 全链路 E2E（validate → hybrid → authoritative → scoring → evidence → stats → response） | **是** — E2E-1,2,3,4a,4b,5a,5b,6 | RET-001..005 unit/integration 重复实现 |
| EXT-007 同步文档可被 BM25/检索链路消费（write→retrieve） | **是** — E2E-2 | 修改 `RetrievalIndexSyncService` 语义 |
| 失败注入：单通道失败、双通道致命、Embedding 不可用、总超时/降级 | **是** — E2E-3/4a/4b/5 | 新 retry 框架 / 新生产 hook |
| Neo4j `retrieval_count`/`last_retrieved_time` **端到端**断言 | **是** — 跨 E2E-1/6 | 修改 `RetrievalStatisticsRepository` Cypher |
| HTTP Response DTO / Warning / 致命码 **公共契约** E2E 断言 | **是** — 各场景子集 | 修改 Pydantic Schema 字段 |
| `user_id` 隔离 E2E | **是** — E2E-6 | — |
| BM25 / Vector / RRF / Neo4j 权威 / ACT-R / Evidence **算法** | **否** — 仅消费 | **RET-001..004** |
| HTTP 编排 / tokenize gate / 超时矩阵 **生产实现** | **否** — 仅调用 | **RET-005** |
| EXT-007 index sync **生产实现** | **否** — E2E-2 仅调用 | **EXT-007** |
| Session→Archive→Extraction→Retrieval 全链路 | **否** | **E2E-001 / §3.32 #4** |
| STM / Extraction / Consolidation E2E | **否** | **STM-013 / EXT-009 / CON-*** |
| Cache / reranking / pagination / streaming | **否** | **DEFERRED** |
| 新 durable write 语义 | **否** | **HARD_BLOCK** |
| DEV-006 / PR #13 | **否** | **HARD_BLOCK** |

---

## 3. e2e_boundary

### 3.1 规格依据（最小权威边界）

| 来源 | 结论 |
|---|---|
| `master_plan` RET-006 | 「阶段 E2E：**包含** EXT-007 同步文档可被 BM25/检索链路消费的验证；失败注入（单通道失败、总超时、Embedding 不可用等）」 |
| §2.2.16 | Retrieval **完整处理流程** 的端到端可观测性（非 Session 起点） |
| §3.28 E2E 层 | 「完整测试 Compose」；失败注入必须覆盖；Fake Service 默认；CI 不调用计费 API |
| §3.32 #4 | **全链路** `Session → … → Retrieval → Consolidation` — **不** 属 RET-006；归属 E2E-001 |
| RET-005 §18 | Session→Retrieval 全链路 E2E + compose 失败注入 → **归属 RET-006**（本任务闭合 **Retrieval 垂直切片**，非 STM/EXT 全链） |
| EXT-007 §E2E | 写入→可检索 E2E → **归属 RET-006**（E2E-2） |
| RET-001/002/003 | Integration 使用直接 ES+Neo4j Fixture；write→retrieve **deferred to RET-006** |

### 3.2 Fixture 策略判定：A / B / Both

| 策略 | 定义 | RET-006 是否采用 | 理由 |
|---|---|---|---|
| **A — Pre-seeded fixtures** | 测试直接写入对齐的 ES `MemoryIndexDocument` + Neo4j Memory/Evidence/Entity（复用 ret001..005 support 模式） | **是** — E2E-1,3,4a,4b,5a,5b,6 主路径 | §2.2.16 验证检索编排；与 RET-001..005 integration 一致；最小、确定性最高 |
| **B — EXT-007 write path** | Neo4j 种子 → `RetrievalIndexSyncService.sync` → ES → HTTP retrieval | **是** — **E2E-2 必选单场景** | `master_plan` 明确要求；闭合 EXT-007 deferred E2E；验证真实 sync 产出可被 BM25/Vector 消费 |
| **Both** | A 覆盖矩阵广度；B 覆盖 write→retrieve 闭环 | **权威结论：Both（最小）** | A 不得替代 B；B 不得替代 A 的失败注入矩阵 |

**明确排除**：不得将 EXT-009 extraction pipeline / Kafka consumer 作为 RET-006 硬前置；E2E-2 直接调用 EXT-007 `RetrievalIndexSyncService`（与 `test_ext007_retrieval_index_sync.py` 同模式）。

### 3.3 E2E 驱动边界

| 项 | 结论 |
|---|---|
| HTTP 入口 | **仅** `POST /api/v1/memory/retrieval`（§2.2.5） |
| 进程模型 | `hybrid_api_client` — ASGITransport in-process `create_app` + `request.app.state.app_state`；**不**启动 `memory-api` 容器（Retrieval E2E 无需 STM compression 配置） |
| 真实基础设施 | **ES + Neo4j 必须**；`init-infra` migration |
| Mongo | **仅 E2E-2**：EXT-007 `mark_completed`/`mark_processing` 需要 extraction task 文档 |
| Kafka / Redis | **不需要**（Retrieval E2E 边界不经过 Archive/Session） |
| Embedding / Tokenize | **Fake**（`FakeEmbeddingClient` / `FakeTokenizeClient`）；`--embedding=none` |
| 生产零 diff 默认 | E2E 暴露 RET-001..005 / EXT-007 缺陷 → **HALT**；不得在本任务修复 |

---

## 4. infrastructure_requirements

### 4.1 Compose 与隔离

| 项 | 值 |
|---|---|
| 入口 | `./scripts/compose.sh --stack=test --embedding=none` |
| Project | `memory-system-test`（`compose.test.yaml` 独立 volume） |
| 启动服务 | `redis`, `mongodb`, `kafka`, `neo4j`, `elasticsearch` + `init-infra` |
| 不启动 | `memory-api`, `extraction-worker`, `consolidation-worker`, embedding service |
| Teardown | `compose down --remove-orphans`（module fixture）；不得污染 dev volume |
| 连接 | 经 `_container_ip` 解析容器 IP（与 `tests/e2e/conftest.py` 一致） |

### 4.2 Fixture 分层

| Fixture | Scope | 用途 |
|---|---|---|
| `infra_stack` | module | 共享 ES/Neo4j/Mongo/Kafka/Redis；RET-006 复用现有 conftest |
| `ret006_retrieval_client` | function | 新建：in-process app + monkeypatch **Route 导入点** `memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state`；可注入 Fake embedding/tokenize/ports |
| `ret006_aligned_seed` | function | 新建 helper：Neo4j（ret003/004 扩展）+ ES（ret002 确定性 embedding）**同一 memory_id 对齐** |
| `ret006_ext007_synced_seed` | function | E2E-2：Neo4j 种子 + Mongo task + `RetrievalIndexSyncService.sync` → ES |

### 4.3 最小对齐 Fixture 契约（ret006）

- 至少 1 条 **user A** `active` Memory：`memory_id` ES 与 Neo4j 一致；`search_text` 含唯一关键词 `ret006e2ekeyword`；embedding 由 `make_deterministic_embedding(query_key)` 生成且 query embedding 与文档 embedding 可对齐。
- 至少 1 条 **user B** Memory：用于隔离（E2E-6）；user A query **不得**返回。
- 至少 1 条 Memory 带 Evidence `SUPPORTS`（ret004 模式）：断言 `evidence_count` / `source_message_ids`。
- Stats 基线：`retrieval_count=0` 或已知初值；E2E 后 Neo4j 直接读回断言（不经 mock）。

### 4.4 鉴权与 HTTP

| 项 | 值 |
|---|---|
| Header | `X-API-Key: dev-memory-api-key-change-me`（`.env.example`） |
| Admin Key | E2E 可选子断言；主路径 Memory Key |
| Request ID | 至少 E2E-1 含 `X-Request-ID` 透传；错误响应符合 §3.23 包络 |

---

## 5. failure_injection_contract

**原则**：确定性 Fake / monkeypatch factory 注入；**禁止**新 retry 框架、新生产 middleware、新 Settings 字段。

### 5.1 注入点（权威）

**Monkeypatch 目标（SF-1）**：必须 patch Route 模块内 **已绑定** 的 factory 引用，而非仅 patch `retrieval_api_service` 定义处：

```python
# 权威 patch 路径（与 memory_retrieval.py import 一致）
memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state
```

Route handler 在 import 时绑定该符号；patch 源模块而不 patch Route 引用将导致注入不生效。

| 注入点 | 机制 | 适用场景 |
|---|---|---|
| Route factory monkeypatch（见上） | 返回 `create_retrieval_api_service(...)` 组装的服务，替换 `embedding_client` / `tokenize_client` / port | 全部 E2E |
| `FakeEmbeddingClient(fail=True)` | 抛 `EmbeddingServiceError` | E2E-3 |
| `FakeEmbeddingClient` + `make_deterministic_embedding` | 正常向量；与 fixture 对齐 | E2E-1/2/6 |
| `FakeTokenizeClient(token_count=N)` | 控制 tokenize gate | 可选；默认 `10` |
| Stub `Bm25RetrievalSearchPort` | 返回 `channel_failure` outcome | E2E-4a（单通道降级） |
| Stub BM25 **+** Vector `channel_failure` | 双通道均 failure | **E2E-4b**（致命 503） |
| `monkeypatch.setenv` + `get_settings.cache_clear()` | 缩短 `MEMORY_RETRIEVAL__RETRIEVAL_TOTAL_TIMEOUT_SECONDS` | E2E-5 |
| Slow `RetrievalScoringPort` / `AuthoritativeRecallPort` stub | `asyncio.sleep` 超过 deadline | E2E-5 `retrieval_timeout` 503 分支 |
| `RetrievalStatisticsPort` 抛 `RetrievalStatisticsWriteError` | stub statistics repo | 可选子场景；主矩阵由 E2E-5 degraded 覆盖 stats 跳过 |

### 5.2 注入矩阵（与 RET-005 §16.6 对齐；**INJ-*** 为注入契约 ID，与 §6 **E2E-*** 交付场景分离）

| INJ ID | 注入 | HTTP | warnings | stats | 绑定 E2E 场景 |
|---|---|---|---|---|---|
| INJ-1 | 无（happy） | 200 `retrieval_mode=hybrid` | 无或仅非阻塞 internal | Top-K `retrieval_count+1`；`last_retrieved_time` 更新 | E2E-1 |
| INJ-2 | `FakeEmbeddingClient(fail=True)` | 200 `bm25_only` | 含 `embedding_failed` | 仍更新（若 Top-K 非空） | E2E-3 |
| INJ-3 | BM25 port `channel_failure` only | 200 `vector_only` 或 `hybrid` 降级 | 含 `bm25_retrieval_failed` | 同上 | E2E-4a |
| INJ-4 | BM25 **+** Vector 双通道 `channel_failure` | **503** `retrieval_unavailable` | **无**（致命码不进 `warnings`；§3.23 错误包络） | **不**更新 | **E2E-4b** |
| INJ-5 | 总超时（response 未完成） | **503** `retrieval_timeout` | — | **不**调用 stats | E2E-5a |
| INJ-6 | response 完成后 stats 前超时 | 200 | 含 `retrieval_timeout_degraded` | **跳过** stats | E2E-5b |

§6 交付场景与 INJ 映射见 §6.2。

---

## 6. e2e_test_plan（E2E-1..6 + E2E-4a/4b）

> 标记：`@pytest.mark.integration`；目录 `tests/e2e/`；scoped 运行 `uv run pytest tests/e2e/test_ret006_retrieval_e2e.py -v`。
>
> **编号说明**：`E2E-4a` / `E2E-4b` 为 E2E-4 子场景（单通道降级 vs 双通道致命）；`E2E-5a` / `E2E-5b` 为 E2E-5 子场景。交付物计数仍为 **8 个必测场景**（E2E-1,2,3,4a,4b,5a,5b,6）。

| ID | 名称 | Fixture 路径 | 基础设施 | 注入（INJ） | 核心断言 |
|---|---|---|---|---|---|
| **E2E-1** | Happy path hybrid retrieval | **A** pre-seeded | ES + Neo4j | INJ-1；`FakeEmbeddingClient` 确定性向量 | 200；`retrieval_mode=hybrid`；`memories[]` 含 §2.2.12 字段；匹配关键词 memory；Neo4j stats +1 |
| **E2E-2** | EXT-007 write→retrieve | **B** sync path | ES + Neo4j + Mongo | sync + Fake embed/tokenize；再 HTTP retrieval | ES 由 sync 写入；BM25/Vector 至少一路命中；200；`memory_id` 与 Neo4j 一致 |
| **E2E-3** | Embedding unavailable degradation | **A** | ES + Neo4j | INJ-2 | 200 `bm25_only`；`embedding_failed` ∈ warnings；BM25 命中（fixture 允许） |
| **E2E-4a** | Single-channel BM25 degradation | **A** | ES + Neo4j | INJ-3；Stub BM25 `channel_failure` only | 200；`bm25_retrieval_failed` ∈ warnings；`retrieval_mode` ∈ `{vector_only, hybrid}`；Vector 仍工作；stats 可更新 |
| **E2E-4b** | Dual-channel fatal unavailable | **A** | ES + Neo4j | INJ-4；Stub BM25 **+** Vector `channel_failure` | **503**；body.code **`retrieval_unavailable`**（§3.23 包络）；**无** `warnings` 字段或为空；**stats 不变**（POST 前后 Neo4j 基线一致） |
| **E2E-5** | Total timeout matrix | **A** | ES + Neo4j | INJ-5 / INJ-6 | **5a**：503 `retrieval_timeout`；stats 不变。**5b**：200 + `retrieval_timeout_degraded`；stats 跳过 |
| **E2E-6** | User isolation + stats | **A** | ES + Neo4j | INJ-1 | user A query 不返回 user B `memory_id`；B stats 不变；A Top-K stats +1 |

### 6.1 用户请求矩阵 ↔ Plan 场景映射（权威）

| 用户 E2E # | 用户意图 | Plan 场景 | 状态 |
|---|---|---|---|
| E2E-1 | Happy path + stats + DTO | **E2E-1** | OK |
| E2E-2 | Cross-user isolation | **E2E-6** | OK |
| E2E-3 | Channel degradation（200 + warnings） | **E2E-3**（embedding）+ **E2E-4a**（BM25 单通道） | OK |
| E2E-4 | Fatal dual-channel → 503 精确契约 + 无 stats 突变 | **E2E-4b** | **MF-1 闭合** |
| E2E-5 | Total timeout / degraded | **E2E-5a** + **E2E-5b** | OK |
| E2E-6 | Write-to-retrieve（EXT-007） | **E2E-2** | OK |

### 6.2 INJ ↔ E2E 交叉引用

| INJ | E2E 场景 |
|---|---|
| INJ-1 | E2E-1, E2E-6 |
| INJ-2 | E2E-3 |
| INJ-3 | E2E-4a |
| INJ-4 | **E2E-4b** |
| INJ-5 | E2E-5a |
| INJ-6 | E2E-5b |

### 6.3 场景与 §2.2.16 阶段映射（E2E-1）

```text
POST /api/v1/memory/retrieval
  → validate + normalize
  → tokenize gate (FakeTokenizeClient)
  → BM25 + Vector (真实 ES)
  → fuse_rrf
  → AuthoritativeRecallService (真实 Neo4j)
  → graph_expand (默认 true)
  → RetrievalScoringService + Evidence (真实 Neo4j)
  → Response DTO
  → Neo4j stats update
  → 200 + body
```

---

## 7. statistics_verification

| ID | 断言 | 方法 |
|---|---|---|
| SV-1 | Top-K 每条 `memory_id` 的 `retrieval_count` 递增 1 | E2E-1/6：POST 前 Neo4j `MATCH` 读基线；POST 后读回 |
| SV-2 | `last_retrieved_time` 更新为请求 `current_time` 近似（±容差 5s） | 同上 |
| SV-3 | 空 Top-K（无命中）**不**调用 stats | E2E-6 子断言或 dedicated query 无匹配 |
| SV-4 | stats 写失败 → 200 + `retrieval_stat_update_failed` | 可选 unit 已有；E2E 主矩阵不强制（避免过多 stub） |
| SV-5 | `retrieval_timeout` 503 → stats **不变** | E2E-5a |
| SV-6 | `retrieval_timeout_degraded` → stats **跳过** | E2E-5b |
| SV-7 | stats Cypher `user_id` 过滤 | user B memory stats 不因 user A 请求改变（E2E-6） |
| SV-8 | `retrieval_unavailable` 503 → stats **不变** | **E2E-4b**；POST 前后 seeded memory `retrieval_count` / `last_retrieved_time` 完全一致 |

**禁止**：仅断言 HTTP 200 而不读 Neo4j；不得 mock `RetrievalStatisticsRepository` 于 E2E-1/6 happy/isolation 路径。

---

## 8. api_contract_verification

| ID | 断言 | 场景 |
|---|---|---|
| AC-1 | `POST /api/v1/memory/retrieval` 路径 | 全部 |
| AC-2 | 缺失/无效 Key → 401 `invalid_api_key` | E2E-1 子步骤或 `test_ret006_retrieval_e2e.py` 独立用例 |
| AC-3 | 200 body：`retrieval_mode` ∈ `{hybrid,bm25_only,vector_only,none}` | E2E-1/3/4a |
| AC-4 | `memories[].score` 存在；**无** `final_score` 泄漏 | E2E-1 |
| AC-5 | 200 降级：`warnings` 为 `list[str]`；致命场景 **无** warnings | E2E-3/4a/5b |
| AC-6 | `query_too_long` → 400 | 可选单用例（contract 已覆盖；E2E 可 1 条 lightweight） |
| AC-7 | 503 致命码：`retrieval_unavailable`（E2E-4b）、`retrieval_timeout`（E2E-5a）；§3.23 包络含 `code`/`message` | **E2E-4b 必绑** |
| AC-8 | Response `extra=forbid` — 无内部字段 | E2E-1 json keys 子集检查 |
| AC-9 | E2E-4b：503 body **无** `retrieval_mode`/`memories` 成功载荷；**不得**返回 200 | E2E-4b |

---

## 9. user_isolation_verification

| ID | 断言 | 场景 |
|---|---|---|
| UI-1 | Request `user_id=A` 时 ES BM25/Vector filter 含 A | E2E-6（间接：结果集） |
| UI-2 | Neo4j 权威回读剔除 B 的 memory | E2E-6：`memories[].memory_id` ∩ B = ∅ |
| UI-3 | user B 高 BM25 分文档对 user A 不可见 | E2E-6：B 的 `search_text` 更匹配 query 仍不返回 |
| UI-4 | stats 更新不触及 B 节点 | E2E-6：B `retrieval_count` 不变 |

---

## 10. write_to_retrieve_verification

```yaml
write_to_retrieve_verification: REQUIRED
owner_scenario: E2E-2
path: "Neo4j seed → RetrievalIndexSyncService.sync (EXT-007) → ES alias → POST /api/v1/memory/retrieval"
success_criteria:
  - "ES 文档由 sync 服务写入（_id=memory_id）；非测试 direct bulk 跳过 sync"
  - "HTTP retrieval 命中该 memory_id"
  - "BM25 和/或 Vector 通道至少一路有 rank"
  - "Neo4j 权威 content 与响应 content 一致（非 ES 直出）"
not_required:
  - "Kafka archive event"
  - "Extraction pipeline / LLM"
  - "Session → Archive 路径"
```

---

## 11. production_file_whitelist

**默认：NONE**。实现阶段 **预期零** `src/**` 生产代码变更。

| 路径 | 创建/修改 | 条件 |
|---|---|---|
| — | — | **无** |

**HALT 规则**：若 E2E 暴露 RET-001..005 / EXT-007 真实缺陷，Developer **停止**并报告 Orchestrator；**不得**在 RET-006 白名单外修复。

**允许的最小配置例外**（仅当 Plan Review 批准且仍为零语义变更）：

| 路径 | 条件 |
|---|---|
| `pyproject.toml` | 仅当必须注册 pytest marker；优先复用现有 `@pytest.mark.integration` |
| `.github/workflows/*.yml` | 仅当必须将 RET-006 scoped 加入 CI job；**非**本任务默认范围 |

---

## 12. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/e2e/test_ret006_retrieval_e2e.py` | 创建 | E2E-1,2,3,4a,4b,5a,5b,6 |
| `tests/e2e/helpers/ret006_e2e_helpers.py` | 创建 | seed/cleanup、factory monkeypatch、Neo4j stats 读回、HTTP 断言 |
| `tests/e2e/conftest.py` | 修改 | `ret006_retrieval_client` fixture；复用 `infra_stack` |
| `tests/support/ret006_e2e_fixtures.py` | 创建 | 对齐 ES+Neo4j 种子；EXT-007 E2E-2 Mongo task 种子 |
| `tests/support/ret006_fake_embedding.py` | 创建（可选） | 查询向量与文档向量对齐的 `FakeEmbeddingClient` 子类；可合并入 helpers |

**白名单外任何 `tests/**` 变更 → FAIL**（含修改 `test_ret005_*` 语义、`test_ret001..004`、EXT-007 integration）。

---

## 13. deferred_for_mvp

| 项 | 说明 | 归属 |
|---|---|---|
| Session → Archive → Extraction → Retrieval 全链路 | §3.32 #4 | E2E-001 |
| Session → Retrieval compose 失败注入（跨 STM+EXT） | RET-005 §18 全链部分 | E2E-001 + 本任务已覆盖 Retrieval 垂直切片 |
| Consolidation 阶段 E2E | — | CON-* / E2E-001 |
| 真实 SiliconFlow / TEI 计费 API | §3.28 | 禁止 |
| `memory-api` 容器级 E2E | STM-013 模式 | 本任务 in-process 足够 |
| Cache / reranking / pagination / streaming | 规格未要求 | DEFERRED |
| Mongo Retrieval Log | §2.2.17 MVP 边界 | DEFERRED |
| 请求幂等 / stats 精确一次 | §2.2.13 #6 | DEFERRED |
| 并发 10 路相同 POST stats 精确性 | RET-005 F1 unit 已覆盖 | 不重复 E2E |
| graph_load_failed / neo4j_read_failure E2E | unit+integration 已覆盖 | 可选；**不**入最小交付矩阵（E2E-4b 已覆盖双通道致命 503） |
| DEV-006 / PR #13 | 永久禁止 | HARD_BLOCK |
| 新依赖 / Migration / Settings Contract | — | HARD_BLOCK |

---

## 14. mvp_local_decisions

| ID | 决策 | 理由 | 分类 |
|---|---|---|---|
| LD-1 | E2E 使用 `hybrid_api_client` 模式（in-process ASGI + 真实 ES/Neo4j），**不**启动 `memory-api` 容器 | Retrieval 无 STM compression 依赖；与 EXT-009 E2E 一致；更快更稳 | MVP_LOCAL_DECISION |
| LD-2 | Fixture **A + B 双路径**：A 主矩阵；B 仅 E2E-2 | `master_plan` 明确要求 EXT-007 消费验证；A 不可替代 B | MVP_LOCAL_DECISION |
| LD-3 | 失败注入经 monkeypatch **`memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state`**（Route 导入绑定点）；**不**改 Route 签名 | RET-005 factory 经 Route import；零生产 diff（SF-1） | MVP_LOCAL_DECISION |
| LD-4 | `@pytest.mark.integration`；目录 `tests/e2e/`；不新增 `e2e` marker | 与 STM-013 / EXT-009 一致；`--strict-markers` 兼容 | SAFE_AUTO_REMEDIATION |
| LD-5 | E2E-2 Mongo 仅用于 extraction task 状态门控 | EXT-007 `mark_completed` 契约；不引入 Kafka | SAFE_AUTO_REMEDIATION |
| LD-6 | 修改 RET-001..005 / EXT-007 生产语义 | — | **HARD_BLOCK** |
| LD-7 | 新 retry 框架 / 新生产 injection hook | — | **HARD_BLOCK** |
| LD-8 | Session→Consolidation 全链路 | — | **DEFERRED**（E2E-001） |

---

## 15. NORMAL classification（HARD_BLOCK / SAFE_AUTO / MVP_LOCAL / DEFERRED）

| ID | 项 | 分类 |
|---|---|---|
| CL-1 | 修改 RET-001..005 / EXT-007 生产 Service 语义 | **HARD_BLOCK** |
| CL-2 | 新 durable write 语义（除既有 stats + EXT-007 sync） | **HARD_BLOCK** |
| CL-3 | 新依赖 / Migration / Settings Contract | **HARD_BLOCK** |
| CL-4 | DEV-006 / PR #13 | **HARD_BLOCK** |
| CL-5 | E2E 暴露缺陷于本任务修复生产代码 | **HARD_BLOCK**（须 HALT） |
| CL-6 | in-process ASGI + infra_stack | **MVP_LOCAL_DECISION**（LD-1） |
| CL-7 | A+B fixture 策略 | **MVP_LOCAL_DECISION**（LD-2） |
| CL-8 | factory monkeypatch 注入 | **MVP_LOCAL_DECISION**（LD-3） |
| CL-9 | conftest fixture 扩展 | **SAFE_AUTO_REMEDIATION**（LD-4/5） |
| CL-10 | Session→Consolidation 全链路 | **DEFERRED** |
| CL-11 | 真实付费 Embedding API | **HARD_BLOCK** |

---

## 16. 任务目标

交付 **Retrieval 阶段端到端测试套件**，在 **真实 Elasticsearch + Neo4j** 上经 **公共 HTTP API** 验证 §2.2.16 完整处理流程、§2.2.13 统计语义、§2.2.15 失败注入子集，并闭合 **EXT-007 write→retrieve** 延后项。

**本任务完成即闭合 `v0.4.0-memory-retrieval` 里程碑**（`master_plan` §4）。

可验证交付：

1. **E2E-1** — Hybrid happy path + stats + Response DTO。
2. **E2E-2** — EXT-007 sync → retrievable（**write_to_retrieve REQUIRED**）。
3. **E2E-3 / E2E-4a** — 通道降级（200 + warnings）。
4. **E2E-4b** — 双通道致命 `503 retrieval_unavailable` + stats 不变。
5. **E2E-5a/5b** — 总超时 / 降级。
6. **E2E-6** — `user_id` 隔离 + stats 不串用户。
7. **默认零生产代码变更**；scoped E2E 全通过。

---

## 17. 非目标

- 修改 RET-001..005、EXT-007 业务实现或既有测试语义。
- Session / Extraction / Consolidation 阶段 E2E 或生产接线。
- §3.32 #4 全链路 E2E（E2E-001）。
- 新 HTTP 端点、新错误码、新 Settings 字段。
- 真实 SiliconFlow / TEI 网络调用。
- 新 retry 框架或生产环境 failure injection hook。
- DEV-006 / PR #13。
- 在 RET-006 内修复 E2E 暴露的上游生产缺陷。

---

## 18. 当前代码状态

### 18.1 Git 与前置证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `538cf13ac3d33d1f337a9e5f5b450626ddd6529d` |
| `git status --short` | 空 |
| RET-001..005 | `completed`；PR #44..#48 MERGED |
| EXT-007 | `completed`；PR #41 MERGED |
| OI-008 | `resolved_by_task=RET-005` |

### 18.2 可复用组件

| 组件 | 路径 | RET-006 用法 |
|---|---|---|
| E2E infra | `tests/e2e/conftest.py` | `infra_stack`, `hybrid_api_client` 模式 |
| EXT-009 helpers | `tests/e2e/helpers/ext009_e2e_helpers.py` | cleanup/seed 模式参考 |
| ES fixtures | `tests/support/ret001_es_fixtures.py`, `ret002_es_fixtures.py` | 扩展为 ret006 对齐种子 |
| Neo4j fixtures | `ret003_neo4j_fixtures.py`, `ret004_neo4j_fixtures.py`, `ret005_neo4j_fixtures.py` | 图/Evidence/stats |
| Fake clients | `fake_retrieval_index_embedding_client.py`, `fake_tokenize_client.py` | 全 E2E |
| HTTP route | `api/routes/memory_retrieval.py` | E2E 驱动 |
| Factory | `memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state` | Route 级 monkeypatch 注入（SF-1） |
| EXT-007 sync | `retrieval_index_sync_service.py` | E2E-2 |
| RET-005 tests | `test_ret005_retrieval_http.py`（mock service） | **不**满足 E2E；RET-006 补齐 |

### 18.3 当前缺失

- `tests/e2e/test_ret006_retrieval_e2e.py`
- `tests/e2e/helpers/ret006_e2e_helpers.py`
- `tests/support/ret006_e2e_fixtures.py`
- `ret006_retrieval_client` conftest fixture
- ES+Neo4j **对齐**的全链路 E2E 种子（跨 ret001..005 组合）

---

## 19. 实现方案（Developer 指引 — 本轮不执行）

> **原则：TEST / E2E ONLY**。默认 **不** 修改 `src/**`。

### Step 1 — `tests/support/ret006_e2e_fixtures.py`

- `RET006_KEYWORD`, `RET006_SEMANTIC_QUERY`, `USER_RET006_A`, `USER_RET006_B`。
- `seed_ret006_aligned_graph(driver)` — Neo4j Memory + Entity + Evidence（扩展 ret003/004）。
- `seed_ret006_aligned_es(write_repo, index_alias)` — ES docs 与 Neo4j `memory_id` 一致；`make_deterministic_embedding`。
- `seed_ret006_ext007_task(mongo, ...)` — Mongo extraction task `processing`（E2E-2）。
- `build_ext007_sync_input(...)` — 最小 `RetrievalIndexSyncInput` / `GraphWriteSuccess` handoff。

### Step 2 — `tests/e2e/helpers/ret006_e2e_helpers.py`

- `build_retrieval_client(infra_stack, *, embedding, tokenize, service_overrides)` — monkeypatch **`memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state`**；返回 `httpx.AsyncClient`。
- `read_memory_stats(driver, user_id, memory_id)` — Neo4j 读 `retrieval_count` / `last_retrieved_time`。
- `cleanup_ret006_data(es, driver, mongo, user_ids)` — 按 user_id 清理。
- `assert_retrieval_response_contract(payload)` — §8 子集断言。

### Step 3 — `tests/e2e/conftest.py` 扩展

- `ret006_retrieval_client` fixture：默认成功 `FakeEmbeddingClient` + `FakeTokenizeClient(10)`。
- 复用 `infra_stack`；**不**引入 `full_container_stack` / coordinated bundle（非 STM）。

### Step 4 — `tests/e2e/test_ret006_retrieval_e2e.py`

- 实现 §6 交付场景：E2E-1,2,3,**4a,4b**,5a,5b,6（E2E-5 可参数化）。
- 每场景：`try/finally` cleanup。
- `pytestmark = pytest.mark.integration`。

### Step 5 — 验证命令

```bash
./scripts/compose.sh --stack=test --embedding=none up -d redis mongodb kafka neo4j elasticsearch
./scripts/compose.sh --stack=test --embedding=none run --rm init-infra
uv run pytest tests/e2e/test_ret006_retrieval_e2e.py -v
uv run pytest tests/unit tests/contract -q   # 回归
uv run ruff check tests/e2e tests/support/ret006_e2e_fixtures.py
uv run mypy tests/e2e tests/support/ret006_e2e_fixtures.py
```

---

## 20. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | E2E 只读检索 + 授权 stats 写 | 断言 response 先于 stats；失败注入验证分支 |
| 幂等 | HTTP 非幂等 | 接受重复 POST stats +N；不做 E2E 幂等表 |
| 并发 | 不测 | RET-005 F1 unit 已覆盖 |
| 版本冲突 | 不适用 | — |
| 用户隔离 | **强制** | E2E-6 + UI-* |
| 部分失败 | 降级 vs 致命路径 | E2E-3/4a（200 降级）；**E2E-4b**（503 致命，stats 不变） |
| 进程恢复 | 不适用 | 无状态 HTTP E2E |

---

## 21. 验收标准 / 完成标准

### 21.1 验收标准

- [ ] E2E-1,2,3,**4a,4b**,5a,5b,6 全部通过（`tests/e2e/test_ret006_retrieval_e2e.py`）
- [ ] **E2E-4b**：双通道 stub → **503** `retrieval_unavailable`；§3.23 错误包络；**无** warnings；Neo4j stats **不变**（SV-8 / AC-7 / AC-9）
- [ ] E2E-4a：单通道 BM25 降级 → 200 + `bm25_retrieval_failed`（INJ-3）
- [ ] E2E-2 证明 EXT-007 sync 产出可被 BM25/检索链路消费（**非** direct ES seed）
- [ ] E2E-1/6 Neo4j stats 端到端验证（SV-*）
- [ ] E2E-3/5 失败注入符合 §5.2 INJ-* / §2.2.15
- [ ] E2E-6 user_id 隔离（UI-*）
- [ ] 公共 API 契约断言（AC-*）在 E2E 中覆盖
- [ ] Factory monkeypatch 使用 Route 导入路径（SF-1）
- [ ] **零** `src/**` 生产代码 diff（除非 HALT 后另开 Task）
- [ ] RET-001..005 + EXT-007 既有 unit/contract/integration **回归通过**
- [ ] Ruff / Mypy（变更测试文件）PASS
- [ ] Review 无 P0/P1

### 21.2 里程碑完成标准

```yaml
milestone: v0.4.0-memory-retrieval
closes_when: RET-006 status=completed on main after POST_MERGE_CLEANUP
evidence:
  - "PR MERGED with E2E-1,2,3,4a,4b,5a,5b,6 green"
  - "master_plan RET-006 status=completed"
  - "progress.md next_action points to CON-001 or next planned task"
not_required_for_milestone:
  - "E2E-001 full chain"
  - "CON-* consolidation"
```

---

## 22. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | 无已知冲突；边界与 §2.2.16 / §3.28 / master_plan 一致 |
| 前置任务 | RET-005、EXT-007 completed |
| 主要风险 | ① ES/Neo4j fixture 未对齐导致 flaky；② monkeypatch 目标错误未注入；③ E2E 误改生产代码；④ 将 E2E-001 全链 scope  creep 入本任务 |
| 环境 | Docker 不可用 → skip（与现有 e2e 一致） |
| DEV-006 | **禁止触碰** PR#13 |

---

## 23. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/RET-006-retrieval-e2e-failure-injection"
baseline_main: "538cf13ac3d33d1f337a9e5f5b450626ddd6529d"
expected_commits:
  - "docs(plan): add RET-006 retrieval e2e failure injection plan"
  - "test(ret): add retrieval stage e2e with failure injection"
  - "docs(status): record RET-006 implementation commit and PR"
  - "docs(status): complete RET-006 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED; register v0.4.0-memory-retrieval"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "RET-001..005 production semantics"
  - "EXT-007 production semantics"
  - "src/** (default NONE)"
  - "Migration / dependency / Settings"
  - "E2E-001 full chain"
```

### 23.1 PLAN_LANDING commit contract

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含：

1. `02_开发管理/tasks/RET-006-retrieval-e2e-failure-injection.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`（RET-006 登记字段）

---

## 24. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 08:15 UTC | plan amendment round 2 | MF-1：新增 E2E-4b 双通道致命；INJ-1..6 重命名；SF-1 Route monkeypatch；§6.1 用户矩阵映射 | — | Plan Review remediation |
| 2026-08-13 08:08 UTC | human PLAN_APPROVED + PLAN_LANDING pending | approval gates → PLAN_APPROVED；`developer_authorized=true`；Release Operator docs(plan) on main + feat branch | — | Round 2 PLAN_APPROVED；不得触碰 DEV-006/PR#13 |
| 2026-08-13 16:35 UTC | implementation resumed | `tests/e2e/helpers/ret006_e2e_helpers.py`；`tests/e2e/test_ret006_retrieval_e2e.py`；`tests/e2e/conftest.py`（`ret006_retrieval_client`）；`tests/support/ret006_e2e_fixtures.py`（EXT-007 graph seed fix） | `uv run pytest tests/e2e/test_ret006_retrieval_e2e.py -v` → **9 passed**；ruff/mypy PASS（scoped）；`git diff src/` empty | 零 `src/**` diff；Route factory monkeypatch SF-1；E2E-1..6 + auth 子用例全绿 |

---

## 25. Plan Amendment

### Amendment 001（Round 2 — Plan Review MF-1）

| MF/SF | 修订 |
|---|---|
| **MF-1** | §6 新增 **E2E-4b** 双通道致命 `503 retrieval_unavailable`；E2E-4 拆为 **4a**（单通道降级 200）+ **4b**（双通道致命 503）；SV-8 / AC-7 / AC-9 / §21 验收绑定 |
| SF-1 | Monkeypatch 目标明确为 `memory_system.api.routes.memory_retrieval.create_retrieval_api_service_from_app_state` |
| SF-3 | §5.2 注入 ID 由 `F-E2E-*` 改为 **`INJ-1..INJ-6`**，与 §6 `E2E-*` 交付场景分离；§6.2 交叉引用 |
| — | §6.1 用户请求矩阵 ↔ Plan 场景映射表 |

---

## 26. RET_006_PLAN_RESULT（Planner 摘要）

```yaml
task_id: RET-006
task_name: "Retrieval 阶段 E2E + 失败注入"
workflow_mode: NORMAL
branch: "feat/RET-006-retrieval-e2e-failure-injection"
milestone: "v0.4.0-memory-retrieval"
planning_baseline_main: "538cf13ac3d33d1f337a9e5f5b450626ddd6529d"
plan_file: "02_开发管理/tasks/RET-006-retrieval-e2e-failure-injection.md"
e2e_boundary: "§2.2.16 Retrieval vertical slice; NOT §3.32 full chain"
fixture_strategy: "BOTH — A pre-seeded (E2E-1,3..6) + B EXT-007 write→retrieve (E2E-2 REQUIRED)"
write_to_retrieve_verification: REQUIRED
infrastructure: "compose.test ES+Neo4j (+Mongo for E2E-2 only); in-process ASGI; no memory-api container"
failure_injection: "INJ-1..INJ-6; Route-level factory monkeypatch (SF-1); FakeEmbeddingClient / stub ports / timeout env"
e2e_matrix: "E2E-1 happy+stats; E2E-2 EXT-007 sync→retrieve; E2E-3 embedding_failed; E2E-4a bm25 single-channel degrade; E2E-4b dual-channel 503 retrieval_unavailable+stats unchanged; E2E-5a/5b timeout/degraded; E2E-6 user isolation"
user_matrix_mapping:
  user_E2E-1: plan_E2E-1
  user_E2E-2: plan_E2E-6
  user_E2E-3: "plan_E2E-3 + plan_E2E-4a"
  user_E2E-4: plan_E2E-4b
  user_E2E-5: "plan_E2E-5a + plan_E2E-5b"
  user_E2E-6: plan_E2E-2
production_file_whitelist: NONE
test_file_whitelist:
  - "tests/e2e/test_ret006_retrieval_e2e.py"
  - "tests/e2e/helpers/ret006_e2e_helpers.py"
  - "tests/e2e/conftest.py"
  - "tests/support/ret006_e2e_fixtures.py"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_write_scope: "existing RET-005 stats + EXT-007 ES upsert (E2E-2 only)"
deferred_for_mvp:
  - "Session→Consolidation full chain (E2E-001)"
  - "Real SiliconFlow/TEI paid API"
  - "memory-api container E2E"
  - "Cache/reranking/pagination/streaming"
  - "DEV-006/PR#13"
completion_closes_milestone: "v0.4.0-memory-retrieval"
next_action: "Code Reviewer on feat/RET-006-retrieval-e2e-failure-injection"
status: tested
```
