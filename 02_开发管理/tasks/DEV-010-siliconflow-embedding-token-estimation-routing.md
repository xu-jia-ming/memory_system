# DEV-010 SiliconFlow embedding token-estimation routing

## 1. 任务信息

```yaml
task_id: DEV-010
task_name: SiliconFlow embedding token-estimation routing
task_slug: siliconflow-embedding-token-estimation-routing
status: reviewed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "fc3fbd0fdc410aef2e21e6e3932cc6b9f7560a8a"
changes_technical_spec: true
insertion_reason: NEW_UNPLANNED_FEATURE
human_plan_approved: true
developer_authorized: true
created_at: "2026-08-15 07:50 UTC"
updated_at: "2026-08-15 08:30 UTC"
branch: "feat/DEV-010-siliconflow-embedding-token-estimation-routing"
spec_sections:
  - "§1.2.1 estimated_tokens 字符比例公式（复用；不得改公式）"
  - "§2.1.13 图谱写入事务前准备 item 9（core_search_text 计数来源；Orchestrator 简报写作 #4，规格正文为 item 9）"
  - "§2.2.3 Retrieval Index 同步 #4 / #7（core_search_text 与最终 search_text 计数来源）"
  - "§2.2.5 请求校验 #3（Vector 通道 1024 门闩计数来源）"
  - "§2.2.6 Query 标准化与 Embedding（只读交叉；TEIEmbeddingClient /tokenize 规则不重写）"
  - "§3.1 Embedding Input Limit（最小澄清 SiliconFlow EXT/RET 计数来源）"
  - "§3.10.0 MVP 默认 Embedding Provider Pivot（最小追加 provider-aware 计数来源一句）"
  - "OI-012 §5.4 Token 超长诚实策略 / §5.5 D6（不得扩大精确 1024 tokenizer）"
  - "DEV-007 非目标与 Amendment 001（不得在 SiliconFlowEmbeddingClient 内做精确 1024 预检）"
prerequisites:
  formal:
    - "REL-001 — SATISFIED/completed（PR #60 MERGED @ 4e8ceff74b95880b1c035d518bf2be43d2bbc907）；Phase 5 无后续 planned Task；本任务为用户显式 NEW_UNPLANNED_FEATURE"
    - "DEV-007 — SATISFIED/completed（PR #17）；create_embedding_client + SiliconFlowEmbeddingClient；local_tei embedding NotImplementedError"
    - "STM-001 — SATISFIED/completed；estimate_tokens 公式已落盘"
    - "EXT-006/007 — SATISFIED/completed；TokenizeClient Protocol + TeiTokenizeClient + 1024 gates"
    - "RET-005 — SATISFIED/completed；Retrieval Vector tokenize gate + vector_skipped_query_too_long"
    - "OI-012 — SATISFIED/completed；HF tokenizer DEFERRED；EXT/RET exact 1024 DEFERRED"
    - "DEV-006 PAUSED / SUPERSEDED_FOR_MVP；PR #13 OPEN / DO_NOT_MERGE — 禁止触碰"
  baseline_evidence:
    branch: "main"
    head: "fc3fbd0fdc410aef2e21e6e3932cc6b9f7560a8a"
    head_short: "fc3fbd0"
    head_subject: "docs(status): complete REL-001 after PR merge"
    working_tree_at_planning_start: "clean"
    origin_note: "Planner 只读复核；不得 Git 写"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=fc3fbd0fdc410aef2e21e6e3932cc6b9f7560a8a"
    planner_git_log_oneline_10:
      - "fc3fbd0 docs(status): complete REL-001 after PR merge"
      - "4e8ceff Merge pull request #60 from xu-jia-ming/feat/REL-001-mvp-rc-review-acceptance-checklist"
      - "725c89b docs(status): record REL-001 implementation commit and PR"
      - "703bb10 docs(rel): record MVP RC evidence and acceptance checklist"
      - "04c4a7e docs(plan): add REL-001 MVP RC review and acceptance checklist plan"
      - "412fb7b docs(status): complete E2E-001 after PR merge"
      - "43b6975 Merge pull request #59 from xu-jia-ming/feat/E2E-001-full-chain-e2e-failure-injection"
      - "526c840 docs(status): record E2E-001 implementation commit and PR"
      - "4a44e99 test(e2e): add full-chain e2e and failure injection suite"
      - "c2afaaa docs(plan): add E2E-001 full-chain e2e and failure injection plan"
approval_gates:
  planning: approved
  human_plan_approved: true
  human_plan_approved_at: "2026-08-15 08:03 UTC"
  developer_authorized: true
  approval_posture: IMPLEMENTATION_RELEASE
  plan_review_round: 1
  plan_review_status: "Round 1 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=2 (implementation Step 0; no Amendment this phase)"
  next_action: "IMPLEMENTATION_RELEASE on feat; do not push origin main"
  post_human_plan_approved_state_machine: |
    Human PLAN_APPROVED received. status=approved; next_action=PLAN_LANDING then Developer on feat.
    developer_authorized=false until exact feat/DEV-010-siliconflow-embedding-token-estimation-routing exists.
    Do not start Developer on main. Developer starts only after PLAN_LANDING creates the feat branch.
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator lands this plan on main (docs(plan) commit/push) then git pull --ff-only then create exact feat/DEV-010-siliconflow-embedding-token-estimation-routing from updated main"
  IMPLEMENTATION_RELEASE: "NORMAL and STRICT; DD-006; feature-branch whitelist git add/commit/push origin feat (no force); gh pr create / gh pr view; optional same-feat docs(status): record; NEVER git push origin main; NEVER commit/add on main; NEVER auto-push record to main"
  POST_MERGE_CLEANUP: "NORMAL only; after verified MERGED PR; git fetch; ff-only update main; docs(status): complete on main; only exact planned feat may git branch -d and git push origin --delete; no -D; no delete before MERGED"
dependency_changes_expected: NONE
migration_changes_expected: NONE
settings_fields_expected: NONE
production_file_whitelist_default: |
  src/memory_system/infrastructure/tokenize/__init__.py
  src/memory_system/infrastructure/tokenize/factory.py
  src/memory_system/infrastructure/tokenize/heuristic_token_count_adapter.py
  src/memory_system/domain/ports/tokenize_client.py
  src/memory_system/domain/services/production_extraction_pipeline.py
  src/memory_system/domain/services/retrieval_api_service.py
test_file_whitelist_default: |
  tests/unit/test_heuristic_token_count_adapter.py
  tests/unit/test_tokenize_client_factory.py
  tests/contract/test_dev010_tokenize_provider_routing.py
  tests/e2e/helpers/e2e001_helpers.py
spec_file_whitelist_default: |
  01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md
governance_file_whitelist_implementation: |
  02_开发管理/tasks/DEV-010-siliconflow-embedding-token-estimation-routing.md
  02_开发管理/progress.md
  02_开发管理/master_plan.md
why_dev_010: "DEV-008/009 已被 OI-012 Amendment 002 取消；本任务是 EXT+RET 共享计数来源路由，类比 DEV-007 factory，不是 EXT-010 或 RET-007"
```

### 1.1 本轮门禁（planning-only）

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现或测试实现"
  - "修改规格正文（规格 delta 仅在 PLAN_APPROVED 后由 Developer 实施）"
  - "在 main 上启动 Developer / Code Reviewer / Commit Recorder / Release Operator"
  - "PLAN_LANDING 本身（本轮只出待审计划）"
  - "IMPLEMENTATION_RELEASE / POST_MERGE_CLEANUP"
  - "读取 .env 或提交 Secret"
  - "触碰 DEV-006 / PR #13"
  - "创建 OI-013 作为第二任务"
  - "实现 TEIEmbeddingClient"
  - "新增 tokenizer / HuggingFace tokenizer / transformers / tiktoken / SiliconFlow count-tokens API"
  - "扩大 OI-012 DEFERRED 精确 1024 tokenizer 强制"
  - "修改 extraction schema / Mongo / Kafka / Neo4j / ES mapping"
  - "修改 estimate_tokens 公式、错误码、状态机、幂等或恢复语义"
stop_if:
  - "实施需要改变错误码、阈值 1024、Schema、状态机、幂等或恢复语义"
  - "实施需要新依赖、Migration、Settings 新字段、compose/preflight/TEI 镜像变更"
  - "实施需要把 heuristic 1024 比较宣传为 TEI-level exact tokenizer"
  - "需要实现 SiliconFlowEmbeddingClient 内精确 1024 预检（OI-012 / DEV-007 Amendment 001 禁止）"
blocking_open_issues: []
nonblocking_open_issues:
  - "OI-DEV010-ITEM9 — Orchestrator 简报写作 §2.1.13 #4；规格正文 tokenize 强制句是事务前准备 item 9。本计划补丁目标锁定 item 9，不改 item 4（LLM Reconciliation）"
  - "OI-DEV010-TEI-CHAPTERS — §2.2.6 #3、§3.2 embedding-service #6、§3.10 TEI 章仍描述 TEIEmbeddingClient /tokenize；属 TEI embedding-client 合同（DEV-006 DEFERRED），本任务不重写"
  - "OI-DEV010-HEURISTIC-GAP — siliconflow 路径 1024 比较使用 estimate_tokens，与 BGE-M3 tokenizer 在边界上可能不一致；接受为 MVP 启发式；精确强制仍为 OI-012 D6 DEFERRED"
  - "OI-DEV010-LOCAL-TEI-SPLIT — local_tei tokenize 仍返回 TeiTokenizeClient；create_embedding_client(local_tei) 仍 NotImplementedError。有意分裂；本任务不实现 TEIEmbeddingClient"
```

### 1.2 Ownership / 插入理由

| 问题 | 结论 |
|---|---|
| 既有未完成 Task？ | **否。** `progress.md` `current_task=REL-001` `current_task_status=completed`。Phase 5 无后续 planned Task。 |
| 需要新 Task？ | **是。** 用户显式 NEW_UNPLANNED_FEATURE。 |
| Spec 触达？ | **是，最小。** 不是新 tokenizer，不是 extraction schema。必须补 provider-aware 计数来源澄清，因为部分业务章节仍无条件要求 TEI `/tokenize`。 |
| 先单独 OI-013？ | **否。** 用户要求一个 Task 内完成最小规格 delta + 实现 + 测试。`changes_technical_spec: true`。本轮不创建 OI-013。 |
| 为何 DEV-010？ | DEV-008/009 已被 OI-012 Amendment 002 取消。本任务是 EXT + RET 共享基础设施路由，类比 DEV-007 factory，不是 EXT-010 或 RET-007。 |

---

## 2. 任务目标

交付 **provider-aware token-count 路由**（复用既有 `estimate_tokens`，**不是**新产品 tokenizer），使 MVP 默认 `embedding_provider=siliconflow` 的 EXT/RET 1024 门闩不再无条件构造 `TeiTokenizeClient`、不再要求 `embedding-service` 仅因 token 计数而运行。

完成后应具备：

1. **最小规格 delta**：token-count **来源**按 `memory_retrieval.embedding_provider` 分流。错误码、阈值 1024、Schema、状态机、幂等、恢复、`estimate_tokens` 公式均不变。不得宣称 SiliconFlow 路径达到 TEI `/tokenize` 级精确。
2. **`create_tokenize_client(settings, http_client) -> TokenizeClient`**：镜像 `create_embedding_client`。
   - `siliconflow` → `HeuristicTokenCountAdapter`：`count_tokens` 返回既有 `estimate_tokens(text)`（async 包装 sync 启发式；零 HTTP）。
   - `local_tei` → `TeiTokenizeClient(settings, http_client)`（精确 `/tokenize`）。
   - 其他 → fail-closed `ValueError`（与 embedding factory 同形）。
3. **两处生产接线**替换硬编码 `TeiTokenizeClient(...)` 默认值为 `create_tokenize_client(...)`。显式注入的测试 fake 仍优先。
4. **测试**：Unit（adapter = `estimate_tokens`、零 HTTP；local_tei 仍 `TeiTokenizeClient`；factory fail-closed）+ Contract（siliconflow 生产路径不得构造 `TeiTokenizeClient` / 不得 POST `/tokenize`）。默认 CI 不要求 live TEI 或 live SiliconFlow。
5. **E2E helper 补丁**：若生产构造迁到 factory，更新 `tests/e2e/helpers/e2e001_helpers.py` 中按类名 patch `TeiTokenizeClient` 的点。不新增完整 E2E 套件。

**可验证能力**：默认 SiliconFlow MVP 下，Worker `core_search_text` / alias 预算 / Vector query 1024 门闩使用启发式 estimated tokens；`local_tei` 仍走 TEI `/tokenize`。既有错误码 `memory_search_text_too_long`、`vector_skipped_query_too_long` 与 alias 预算比较逻辑不变，只换计数来源。

---

## 3. 非目标

- 新 tokenizer 产品；本地 HuggingFace tokenizer / `transformers` / tiktoken / SiliconFlow count-tokens API。
- 扩大 OI-012 **DEFERRED** 精确 1024-token 强制（本地 HF tokenizer 或 SiliconFlow 上 TEI-level exact counts）。允许启发式 1024 比较；禁止宣称 exact tokenizer 精度。
- 修改 extraction schema（Mongo `extraction_result` / task schema / Kafka event schema / Neo4j property schema / ES mapping）。
- 实现 `TEIEmbeddingClient`；改变 `create_embedding_client(local_tei)` 的 `NotImplementedError` fail-closed。
- 触碰 DEV-006 / PR #13（merge / rewrite / extract / 访问 dirty worktree）。
- 修改 `estimate_tokens` 公式（§1.2.1 / STM-001）。
- 修改错误码、阈值 1024、状态机、幂等或恢复语义。
- 在 `SiliconFlowEmbeddingClient` 内实现精确 1024 预检（OI-012 DEFERRED；DEV-007 Amendment 001：依赖 API 400）。本任务是 **EXT/RET 门闩的计数来源路由**，不是 embedding-client token 强制。
- 修改 `search_text_builder` / `graph_write_plan_builder` / `graph_write_service` / `retrieval_index_sync_service` 的 1024 比较逻辑（只换注入的 client）。
- 新增 Settings 字段（路由仅用既有 `memory_retrieval.embedding_provider`）。
- 新依赖、Migration、compose / preflight / TEI 镜像 / §3.3 / §3.18 / OI-011 12g contract。
- 新增完整 E2E 套件；将 E2E 纳入 OPS-004 默认 CI。
- Provider 热切换；默认 CI 真实 TEI / 真实 SiliconFlow。

---

## 4. 当前代码状态

### 4.1 Git 与前置（规划时只读复核）

| 检查 | 结果 |
|---|---|
| 分支 | `main` |
| HEAD | `fc3fbd0fdc410aef2e21e6e3932cc6b9f7560a8a` |
| working tree | clean |
| `02_开发管理/tasks/DEV-010-*` | **规划本轮创建** |
| REL-001 | `completed`；PR #60 MERGED；feat 已删 |
| DEV-007 / STM-001 / EXT-006/007 / RET-005 | `completed` |
| `progress.md` 规划前 | `current_task=REL-001` / `current_task_status=completed` / `next_action=REL-001 completed — NO AUTO-START` |

与 Orchestrator Git facts 一致；无 dirty；规格冲突见 §4.5（本任务以最小白名单 delta 解决，不纸上抹平）。

### 4.2 缺陷：两处生产硬编码 TEI tokenize

MVP 默认 `embedding_provider=siliconflow`，但生产默认路径仍无条件构造 `TeiTokenizeClient`：

1. `src/memory_system/domain/services/production_extraction_pipeline.py` ~L377：

```text
resolved_tokenize_client = tokenize_client or TeiTokenizeClient(settings, http_client)
```

同文件 ~L75 导入 `TeiTokenizeClient`。`create_production_extraction_pipeline` 在 `tokenize_client is None` 时走该默认（Worker 生产路径）。显式注入的 `FakeTokenizeClient` 仍优先。

2. `src/memory_system/domain/services/retrieval_api_service.py` ~L734：

```text
tokenize_client = TeiTokenizeClient(settings, http_client)
```

位于 `create_retrieval_api_service_from_app_state`。同文件 ~L65–67 导入 `TeiTokenizeClient`。对比：同函数已用 `create_embedding_client(settings, http_client)` 做 embedding 分流。

`TeiTokenizeClient.count_tokens` 会 `POST {embedding.base_url}/tokenize`。默认 `embedding.base_url` 仍指向 Compose `embedding-service`。因此 SiliconFlow MVP 在 EXT/RET 1024 门闩上仍依赖本应可选的 TEI 容器。

### 4.3 可复用组件（禁止改 1024 门闩语义；只换注入 client）

| 组件 | 路径 | 本任务关系 |
|---|---|---|
| `TokenizeClient` Protocol | `src/memory_system/domain/ports/tokenize_client.py` | 保留；可选最小 docstring：port 为 provider-aware（TEI exact vs heuristic） |
| `TeiTokenizeClient` | `src/memory_system/infrastructure/tei/tei_tokenize_client.py` | 保留；`local_tei` 仍返回它 |
| `FakeTokenizeClient` | `src/memory_system/infrastructure/tei/fake_tokenize_client.py` | 测试 fake；不改语义 |
| `estimate_tokens` | `src/memory_system/domain/services/token_estimator.py` | **复用**；禁止复制公式 |
| `create_embedding_client` | `src/memory_system/infrastructure/embedding/factory.py` | **镜像分流形状**；不改 embedding factory |
| `graph_write_plan_builder.py` | core_search_text 1024 → `memory_search_text_too_long` | 不改比较逻辑 |
| `graph_write_service.py` | 注入 `TokenizeClient` | 不改 |
| `search_text_builder.py` | alias 预算 + 最终 `1 <= token_count <= 1024` | 不改比较逻辑 |
| `retrieval_index_sync_service.py` | 注入 `TokenizeClient` | 不改 |
| `retrieval_api_service.py` tokenize gate | `token_count > 1024` → `vector_skipped_query_too_long` | 不改比较逻辑；只换默认 client |
| `RetrievalApiService.TokenizeCountPort` | 本地 Protocol，`async count_tokens` | 保留；与 `TokenizeClient` 结构相同 |

### 4.4 测试现状

- Unit / Integration / E2E 普遍 **显式注入** `FakeTokenizeClient`（`tokenize_client=FakeTokenizeClient(...)`）。这些路径不经过生产默认构造，因此 **掩盖了缺陷**。
- 生产默认路径（`tokenize_client is None` / `create_retrieval_api_service_from_app_state`）才是 bug。
- E2E-001 helper **按类名** patch：`tests/e2e/helpers/e2e001_helpers.py` ~L170  
  `"memory_system.domain.services.retrieval_api_service.TeiTokenizeClient"`  
  对照同文件 ~L166 已 patch `create_embedding_client`。生产构造迁到 factory 后，该类名 patch **会失效**，必须改为 patch `create_tokenize_client`。
- EXT-009 / E2E-001 pipeline helper 显式传入 `FakeTokenizeClient`，不依赖生产默认。
- RET-006 helper 若提供 `tokenize=` 则覆盖；仍会先调用 `create_retrieval_api_service_from_app_state` 构造默认 client（当前即 `TeiTokenizeClient`，仅构造不 HTTP）。factory 化后默认变为 heuristic adapter，覆盖 fake 仍有效。**不**把 `ret006_e2e_helpers.py` 列入白名单，除非实施时证明会破。

### 4.5 规格冲突（诚实记录；最小白名单 delta 解决）

| 规格位置 | 当前表述 | 冲突 |
|---|---|---|
| §2.1.13 事务前准备 **item 9**（简报误作 #4） | Worker 必须通过 TEI `/tokenize` **精确**校验 `core_search_text` | 与 OI-012 / §3.1 SiliconFlow 例外、以及默认 provider=`siliconflow` 无 TEI 矛盾 |
| §2.2.3 #4 | Worker 必须用同一 TEI 实例 `/tokenize` **精确计数** | 同上 |
| §2.2.3 #7 | 最终 `search_text` 必须再次通过 `/tokenize` 校验 `1 <= token_count <= 1024` | 无条件 `/tokenize` |
| §2.2.5 请求校验 #3 | Vector 通道使用 TEI `/tokenize` 计算**精确** Token 数 | 无条件 `/tokenize` |
| §3.1 Embedding Input Limit | TEI 路径 `/tokenize` 精确；SiliconFlow 路径见 §3.10.0 与 DEV-007 Contract | 已有例外指针，但未写明 EXT/RET **计数来源** |
| §3.10.0 | SiliconFlow pivot；HF tokenizer **DEFERRED**；无 EXT/RET 计数来源句 | 业务章仍强制 TEI tokenize |
| OI-012 §5.4 | 不引入本地 HF tokenizer；须写明 **非** TEI `/tokenize` 级精确；EXT/RET 精确 1024 **DEFERRED** | 生产代码忽略该例外 |
| 生产代码 | 两处无条件 `TeiTokenizeClient(...)` | 与 SiliconFlow 默认及 OI-012 诚实策略冲突 |

**授权解决（本任务）**：只改 token-count **来源** 为 provider-aware。阈值、错误码、比较逻辑不变。SiliconFlow 路径比较的是 **estimated** tokens，不得宣称 TEI-level exactness。这 **不是** 实现 OI-012 已 DEFERRED 的精确强制工作。

### 4.6 本任务不重写、但实施后仍可能显得张力的句子（Open Issues，禁止静默大改）

| 位置 | 为何留下 |
|---|---|
| §2.2.6 规则 3：`TEIEmbeddingClient` 调用 `/v1/embeddings` 前必须 `/tokenize` | TEI **embedding client** 合同；DEV-006 DEFERRED；本任务不实现 `TEIEmbeddingClient` |
| §2.2.6 `POST http://embedding-service:80/tokenize` | `local_tei` 原生接口文档 |
| §3.2 `embedding-service` 职责与规则 6 | TEI **容器**合同，不是 Worker 计数路由 |
| §3.10.1–§3.10.x `POST /tokenize`、`TEIEmbeddingClient` 必须先 `/tokenize` | TEI 章；禁止静默重写大段 §3.10 |
| §3.3 Compose / §3.18 Preflight / OI-011 12g | 禁止触达 |
| §2.2.6 规则 8 Query 超 1024 降级 | 结果语义；计数来源由 §2.2.5 #3 补丁覆盖 |

### 4.7 前置任务检查

| 前置 | 状态 |
|---|---|
| REL-001 | completed；本任务为其后 NEW_UNPLANNED_FEATURE |
| DEV-007 | completed；factory 模式可镜像；`local_tei` embedding 仍 NotImplementedError |
| STM-001 | completed；`estimate_tokens` 可复用 |
| OI-012 | completed；D6 / exact 1024 仍 DEFERRED，本任务不得扩大 |
| DEV-006 / PR #13 | PAUSED / DO_NOT_MERGE；禁止触碰 |

---

## 5. 实现方案

### Step 1 — 最小规格 delta（白名单章节 only）

- 文件：`01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`
- 目的：把 token-count **来源**改为 provider-aware；不改错误码 / 1024 / Schema / 状态机 / `estimate_tokens` 公式。
- 精确补丁目标：

| 章节 | 当前要点 | 最小补丁（Developer 必须按此语义，不得扩写） |
|---|---|---|
| §2.1.13 事务前准备 **item 9** | 「通过 TEI `/tokenize` 精确校验 Token 数」 | 改为 provider-aware：**siliconflow** → §1.2.1 `estimate_tokens`（启发式；不得调用 TEI `/tokenize`；不得仅因 token 计数要求 `embedding-service`）；**local_tei** → 同一 TEI 实例 `/tokenize` 精确计数。超过 `1024` 仍返回 `memory_search_text_too_long`，不得开 Neo4j 写事务。SiliconFlow 路径比较 estimated tokens；不得宣称 TEI 级精确。不实现 OI-012 DEFERRED 精确强制。 |
| §2.2.3 #4 | 「通过同一 TEI 实例的 `/tokenize` 精确计数」 | 同上分流。错误码 `memory_search_text_too_long` 不变。 |
| §2.2.3 #7 | 「必须再次通过 `/tokenize` 校验 `1 <= token_count <= 1024`」 | 「必须再次通过同一 provider-aware token-count source 校验 `1 <= token_count <= 1024`」；siliconflow = `estimate_tokens`；local_tei = `/tokenize`。逐字节一致文本规则不变。 |
| §2.2.5 请求校验 #3 | 「Vector 通道使用 TEI `/tokenize` 计算精确 Token 数」 | siliconflow → `estimate_tokens`；local_tei → TEI `/tokenize`。`1`–`1024` 生成 Query Embedding；超过 `1024` 不调用 `/v1/embeddings`，跳过 Vector，Warning `vector_skipped_query_too_long`。不得宣称 siliconflow 精确。 |
| §3.1 Embedding Input Limit | 「TEI 路径 `/tokenize` 精确；SiliconFlow 路径见 §3.10.0 与 DEV-007 Contract」 | 澄清：`local_tei` EXT/RET 门闩用 `/tokenize` 精确；`siliconflow` EXT/RET 门闩用 §1.2.1 `estimate_tokens`（启发式；见 §3.10.0）。SiliconFlow **Embedding Client** 仍按 DEV-007 Amendment 001：Client 内无精确 1024 预检，超长依赖 API 400。 |
| §3.10.0 | 无 EXT/RET 计数来源句 | 在 HF tokenizer DEFERRED 句后追加最短段：EXT/RET 1024 计数来源按 `memory_retrieval.embedding_provider` 路由；siliconflow → STM-001 `estimate_tokens`（零 HTTP；非精确 tokenizer；不得 POST `/tokenize`）；local_tei → `TeiTokenizeClient`。错误码/阈值/Schema/状态机不变。不是新 tokenizer，不是 OI-012 D6，不是 `SiliconFlowEmbeddingClient` 内精确预检。 |

- 禁止：重写 §2.2.6 TEIEmbeddingClient 规则、§3.2 embedding-service 容器合同、§3.10.1+ TEI 章、§3.3、§3.18、OI-011 12g。
- 若实施时发现白名单外句子在补丁后仍与新 Contract **直接矛盾**（不仅是 TEI-client 章残留）：**停止并报告**，不得自行扩大白名单。
- 错误处理：规格冲突扩大 → HALT。
- 幂等/并发/事务：不适用（文档）。

### Step 2 — Factory + heuristic adapter（不是新 tokenizer）

- 文件（创建）：
  - `src/memory_system/infrastructure/tokenize/heuristic_token_count_adapter.py`
  - `src/memory_system/infrastructure/tokenize/factory.py`
  - `src/memory_system/infrastructure/tokenize/__init__.py`
- 类/函数：
  - `HeuristicTokenCountAdapter`：实现 `TokenizeClient.count_tokens`。模块 docstring 必须写明 **heuristic / character-ratio**，引用 §1.2.1 / STM-001；**禁止**类名或文档声称 exact tokenize。
  - `async def count_tokens(self, text: str) -> int`：`return estimate_tokens(text)`。禁止复制公式。零 HTTP；不使用 `http_client`。
  - `create_tokenize_client(settings, http_client) -> TokenizeClient`：

```text
provider = settings.memory_retrieval.embedding_provider
siliconflow -> HeuristicTokenCountAdapter()
local_tei   -> TeiTokenizeClient(settings, http_client)
else        -> ValueError(f"unsupported embedding_provider: {provider!r}")
```

- 输入：`Settings`、`httpx.AsyncClient`（与 embedding factory 签名对齐；siliconflow 路径忽略 HTTP client）。
- 输出：满足 `TokenizeClient` 的对象。
- 错误处理：未知 provider fail-closed；`local_tei` 不因 embedding factory 的 `NotImplementedError` 而改 tokenize 分流。
- 禁止：新 Settings 字段；adapter 内 HTTP；tiktoken/transformers/HF。
- 可选：`tokenize_client.py` Protocol 模块 docstring 从「TEI /tokenize exact counts」改为「provider-aware token counts（TEI `/tokenize` exact vs STM-001 heuristic）」。不改 `count_tokens` 签名。

### Step 3 — 接线两处生产默认路径

- 文件（修改）：
  - `src/memory_system/domain/services/production_extraction_pipeline.py`
  - `src/memory_system/domain/services/retrieval_api_service.py`
- 变更：
  - 默认构造 `TeiTokenizeClient(settings, http_client)` → `create_tokenize_client(settings, http_client)`。
  - 显式 `tokenize_client` 实参仍优先（`tokenize_client or create_tokenize_client(...)`）。
  - 删除仅用于该默认构造的 `TeiTokenizeClient` 导入。`retrieval_api_service.py` 继续导入 `TokenizeServiceError`（Vector gate 仍捕获 TEI tokenize 失败）。
- 禁止修改：`search_text_builder.py`、graph-write 1024 比较、`SiliconFlowEmbeddingClient`、`create_embedding_client`。
- 幂等/并发/事务：不适用（纯装配）；下游 Neo4j/ES 幂等不变。

### Step 4 — 测试

见 §8。必须覆盖：siliconflow adapter = `estimate_tokens` 且零 HTTP；local_tei factory 返回 `TeiTokenizeClient`；未知 provider `ValueError`；两处生产源码/装配不在 siliconflow 默认路径构造 `TeiTokenizeClient`；更新 E2E-001 helper patch。

### Step 5 — 静态检查

- `uv run ruff check src tests`
- `uv run mypy src`（OPS-004 CI 范围）
- 不得 skip/删断言/降验收。

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` | 修改 | 最小 provider-aware 计数来源澄清（§2.1.13 item 9、§2.2.3 #4/#7、§2.2.5 #3、§3.1、§3.10.0） |
| `src/memory_system/infrastructure/tokenize/heuristic_token_count_adapter.py` | 创建 | STM-001 `estimate_tokens` 的 async 适配器（非 tokenizer） |
| `src/memory_system/infrastructure/tokenize/factory.py` | 创建 | `create_tokenize_client` provider 分流 |
| `src/memory_system/infrastructure/tokenize/__init__.py` | 创建 | 导出 factory（镜像 embedding 包） |
| `src/memory_system/domain/ports/tokenize_client.py` | 修改 | 可选 docstring：port 为 provider-aware |
| `src/memory_system/domain/services/production_extraction_pipeline.py` | 修改 | 生产默认改 factory |
| `src/memory_system/domain/services/retrieval_api_service.py` | 修改 | 生产默认改 factory |
| `tests/unit/test_heuristic_token_count_adapter.py` | 创建 | adapter = `estimate_tokens`；零 HTTP |
| `tests/unit/test_tokenize_client_factory.py` | 创建 | siliconflow / local_tei / fail-closed |
| `tests/contract/test_dev010_tokenize_provider_routing.py` | 创建 | 生产路径不得构造 `TeiTokenizeClient` / 不得 POST `/tokenize` |
| `tests/e2e/helpers/e2e001_helpers.py` | 修改 | 将 `TeiTokenizeClient` 类名 patch 改为 `create_tokenize_client` |
| `02_开发管理/tasks/DEV-010-siliconflow-embedding-token-estimation-routing.md` | 创建/回写 | 本计划与执行记录 |
| `02_开发管理/progress.md` | 修改 | 规划态 / 后续状态 |
| `02_开发管理/master_plan.md` | 修改 | DEV-010 登记 + CHANGE-092 |

**白名单外一律禁止。** 尤其禁止：`token_estimator.py` 公式、`tei_tokenize_client.py` 行为、`siliconflow_client.py`、`embedding/factory.py`、`search_text_builder.py`、`graph_write_*.py`、`retrieval_index_sync_service.py`、compose/preflight、`pyproject.toml`、Migration、DEV-006/PR#13。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用（装配/计数来源；不新增跨存储事务） | 既有 Neo4j→ES→Mongo 完成顺序不变 |
| 幂等 | 不适用到新存储写入；计数来源对同一文本确定性 | `estimate_tokens` 与 TEI `/tokenize` 各自确定性；siliconflow 路径同一输入同一估计值；不引入新幂等键 |
| 并发 | 不适用（无新共享可变状态） | adapter 无内部可变缓存；factory 每次返回新实例可接受 |
| 版本冲突 | 不适用 | 不改 Memory/task version 语义 |
| 用户隔离 | 不适用/保持 | 不改 `user_id` filter；token 计数不跨用户 |
| 部分失败 | 保持既有 | TEI tokenize 失败仍 `TokenizeServiceError` → Retrieval `embedding_failed` 降级；heuristic 路径无 HTTP 故无该类失败。不把 heuristic 失败伪装成 TEI 失败 |
| 进程异常恢复 | 不适用/保持 | 不改 Kafka offset / replay / Admin retry |

不适用的维度已写明原因。

---

## 8. 测试计划

默认 CI **不得**要求 live TEI 或 live SiliconFlow。

### Unit Test

| 场景 | 预期 |
|---|---|
| U1 中英混合 / 空串 / 纯中文：adapter `count_tokens` | 与 `estimate_tokens(text)` **逐值相等** |
| U2 adapter 零 HTTP | 构造时可不传 `http_client`；若传入则不得 `post`；可用 Dummy/AsyncMock 断言零调用 |
| U3 factory `embedding_provider=siliconflow` | 返回 `HeuristicTokenCountAdapter`（或等价 Protocol 对象）；`count_tokens` = `estimate_tokens` |
| U4 factory `embedding_provider=local_tei` | 返回 `TeiTokenizeClient` 实例（`isinstance`） |
| U5 factory 未知 provider | `ValueError`；不得静默回退 siliconflow |
| U6 siliconflow factory 不构造 `TeiTokenizeClient` | monkeypatch/wrap `TeiTokenizeClient.__init__` 或断言类型不是 `TeiTokenizeClient` |
| U7 `create_production_extraction_pipeline(..., tokenize_client=None)` + siliconflow settings | 解析出的 client 为 heuristic adapter，不是 `TeiTokenizeClient` |
| U8 显式注入 fake 仍优先 | `tokenize_client=FakeTokenizeClient(...)` 时 factory 不被用来覆盖 fake |

禁止：在 unit 中复制 `estimate_tokens` 公式；用 adapter 测试去「证明」精确 tokenizer。

### Contract Test

| 场景 | 预期 |
|---|---|
| C1 生产源码不变量 | `production_extraction_pipeline.py` 与 `retrieval_api_service.py` 正文在默认装配处调用 `create_tokenize_client`；不得再出现 `TeiTokenizeClient(settings, http_client)` 字面默认构造 |
| C2 siliconflow 不得 POST `/tokenize` | 对 heuristic adapter / siliconflow factory 路径，httpx MockTransport 记录为零 `/tokenize` |
| C3 spec/code 路由不变量 | 规格白名单章节补丁后含 provider-aware 关键词（`estimate_tokens` 或 `embedding_provider=siliconflow` 计数来源）；同时 C1 成立 |
| C4 local_tei 仍绑定 TEI client | factory `local_tei` → `TeiTokenizeClient`（不要求真实 HTTP） |
| C5 非目标守卫 | 测试或源码扫描：未新增 `transformers`/`tiktoken` 依赖；未实现 `TEIEmbeddingClient`；`create_embedding_client(local_tei)` 仍 `NotImplementedError` |

### Integration Test

| 场景 | 预期 |
|---|---|
| I1 | **默认不新增** Integration。既有 EXT-006/007/RET 集成继续注入 `FakeTokenizeClient`，预期保持通过 |
| I2 | 若实施后既有集成因默认构造变化而失败：只允许在白名单内修装配，不得改 1024 断言语义 |

### E2E Test

| 场景 | 预期 |
|---|---|
| E1 更新 `e2e001_helpers.py` | `_install_fake_retrieval_clients` patch 目标改为 `retrieval_api_service.create_tokenize_client`（镜像 `create_embedding_client` patch）；删除对 `TeiTokenizeClient` 类名的依赖 |
| E2 | **不**新增 `test_dev010_*` 全链 E2E 套件 |
| E3 | 不把跑完整 E2E-001 列为默认 CI 阻塞；helper 补丁是为既有套件在人工/后续跑时不破 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| F1 factory 未知 provider | `ValueError` fail-closed |
| F2 local_tei `TeiTokenizeClient` 仍可在注入/单测中触发 `TokenizeServiceError` | Retrieval 既有 `embedding_failed` 降级保持；本任务不改该分支 |
| F3 并发 | 不适用；无新共享可变状态。不新增压力测试 |

---

## 9. 验收标准

- [x] 规格白名单六处（§2.1.13 item 9、§2.2.3 #4、§2.2.3 #7、§2.2.5 #3、§3.1 Embedding Input Limit、§3.10.0）已按 §5 Step 1 语义补丁；未重写 §3.10 TEI 大章 / §3.3 / §3.18 / OI-011 12g / extraction schema
- [x] `create_tokenize_client` 存在且分流：siliconflow → heuristic adapter；local_tei → `TeiTokenizeClient`；其他 → `ValueError`
- [x] adapter `count_tokens` 与 `estimate_tokens` 相等；零 HTTP；公式未复制、未修改
- [x] `production_extraction_pipeline.py` 与 `create_retrieval_api_service_from_app_state` 默认使用 factory；siliconflow 生产路径不构造 `TeiTokenizeClient`
- [x] 1024 门闩错误码/Warning 不变：`memory_search_text_too_long`、`vector_skipped_query_too_long`；比较逻辑仅经注入 client
- [x] 未实现 `TEIEmbeddingClient`；`create_embedding_client(local_tei)` 仍 `NotImplementedError`
- [x] 未新增依赖 / Settings 字段 / Migration / compose/preflight
- [x] 未在 `SiliconFlowEmbeddingClient` 内做精确 1024 预检
- [x] `tests/e2e/helpers/e2e001_helpers.py` 改为 patch factory
- [x] Unit + Contract 本任务白名单测试全部通过
- [x] `uv run ruff check src tests` 通过
- [x] `uv run mypy src` 通过
- [ ] Review 无 P0/P1
- [x] 未触碰 DEV-006 / PR #13

建议命令（实施后；规划轮次不跑）：

```bash
uv run pytest tests/unit/test_heuristic_token_count_adapter.py tests/unit/test_tokenize_client_factory.py tests/contract/test_dev010_tokenize_provider_routing.py -q
uv run ruff check src tests
uv run mypy src
```

---

## 10. 风险与阻塞项

- 设计文档冲突：§4.5 已记录；本任务用最小白名单 delta 解决。残留 TEI 章张力见 `OI-DEV010-TEI-CHAPTERS`（非阻塞，禁止借机重写）。
- 当前代码冲突：两处硬编码 `TeiTokenizeClient`（缺陷本身）；测试 fake 掩盖生产路径。
- 前置任务：REL-001/DEV-007/STM-001/OI-012 均 completed；无阻塞未完成前置。
- 未批准依赖：无。`dependency_changes_expected=NONE`。
- API/Schema 变化：**否**（错误码/Schema/状态机不变）。`changes_technical_spec=true` 仅限计数来源澄清。
- 其他风险：
  - 启发式与 BGE-M3 tokenizer 在 1024 边界不一致（`OI-DEV010-HEURISTIC-GAP`；接受）。
  - E2E 类名 patch 漏改会导致 E2E-001 在人工跑时失败 → Step 4/E1 强制改 helper。
  - 误把本任务做成精确 tokenizer 或 `TEIEmbeddingClient` → 非目标 + Contract C5 守卫。
  - 误改 `search_text_builder` 比较逻辑 → 白名单 fail-closed。

---

## 11. Git 计划

```yaml
branch: "feat/DEV-010-siliconflow-embedding-token-estimation-routing"
workflow_mode: NORMAL
planning_baseline_main: "fc3fbd0fdc410aef2e21e6e3932cc6b9f7560a8a"
expected_commits:
  - "docs(plan): add DEV-010 siliconflow embedding token-estimation routing plan"
  - "feat(tokenize): route siliconflow token counts through estimate_tokens"
  - "docs(status): record DEV-010 implementation commit and PR"
  - "docs(status): complete DEV-010 after PR merge"
implementation_commit_policy: "prefer ONE implementation commit covering spec delta + factory/adapter + two production wires + tests (atomic MVP)"
out_of_scope_changes:
  - "DEV-006 feat / PR #13"
  - "TEIEmbeddingClient"
  - "estimate_tokens 公式"
  - "extraction schema / ES mapping / 错误码 / 状态机"
  - "compose / preflight / TEI 镜像 / 新依赖 / 新 Settings 字段"
  - "SiliconFlowEmbeddingClient 精确 1024 预检"
  - "search_text_builder / graph-write 1024 比较逻辑"
  - "完整新 E2E 套件"
  - "真实 SILICONFLOW_API_KEY / .env"
pr_base: main
pr_title: "feat(DEV-010): SiliconFlow embedding token-estimation routing"
release_phases:
  PLAN_LANDING:
    when: "Human PLAN_APPROVED；仅 NORMAL"
    actor: "Release Operator only"
    commands_narrow:
      - "main 上 docs(plan) commit/push（本计划 + progress 规划态 + master_plan CHANGE-092）"
      - "git pull --ff-only"
      - "从更新后的 main 创建 exact feat/DEV-010-siliconflow-embedding-token-estimation-routing"
    forbid: ["git merge 内容合并", "gh pr merge", "rebase", "force push", "在 PLAN_LANDING 写实现 Commit"]
  IMPLEMENTATION_RELEASE:
    when: "CODE_REVIEW_APPROVED 且 READY_FOR_HUMAN_COMMIT 之后；NORMAL 与 STRICT"
    actor: "Release Operator only"
    commands_narrow:
      - "仅功能分支 git add 白名单精确路径"
      - "git commit"
      - "git push origin feat/DEV-010-siliconflow-embedding-token-estimation-routing（禁止 force）"
      - "gh pr create / gh pr view"
      - "可选同 feat 上 docs(status): record"
    forbid:
      - "git push origin main"
      - "在 main 上 commit/add"
      - "将 record 自动推到 main"
  POST_MERGE_CLEANUP:
    when: "PR 已验证 MERGED；仅 NORMAL"
    actor: "Release Operator only"
    commands_narrow:
      - "git fetch；ff-only 更新 main"
      - "docs(status): complete commit/push main"
      - "仅 exact planned feat：git branch -d 与 git push origin --delete"
    forbid: ["-D", "未 MERGED 时删除", "删无关分支/tags", "git tag"]
permanent_forbid:
  - "git merge（内容合并）"
  - "gh pr merge"
  - "git rebase"
  - "git push --force"
  - "git reset --hard"
  - "git clean -fd"
  - "git branch -D"
  - "直接向 main 写实现 Commit"
```

PLAN_LANDING 可 add 路径（治理 only）：

- `02_开发管理/tasks/DEV-010-siliconflow-embedding-token-estimation-routing.md`
- `02_开发管理/progress.md`
- `02_开发管理/master_plan.md`

IMPLEMENTATION_RELEASE 可 add 路径 = §6 白名单（生产 + 测试 + 规格 + 三份治理回写）。fail-closed：白名单外路径不得 `git add`。

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-15 07:50 UTC | Planner 初版 | 创建本 Task Plan；progress/master_plan 规划态 | 未实施 | 无 Git 写；待计划审查 |
| 2026-08-15 08:03 UTC | Human PLAN_APPROVED | 用户模板 PLAN_APPROVED；独立 Plan Reviewer Round 1 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=2（session 9ef8a973-95d9-4798-8203-a63181c3b2b0） | 未实施 | SHOULD_FIX 留给 Developer Step 0；本 phase 无 Amendment |
| 2026-08-15 08:06 UTC | PLAN_LANDING | status=approved；三份治理文件回写；docs(plan) 落 main 后创建 exact feat；plan_commit 不写入本 commit | 未实施 | developer_authorized=false until feat exists；无实现文件 |
| 2026-08-15 08:11 UTC | Developer start | status=approved → in_progress；persist developer_authorized=true；HEAD=plan_commit a55f991；branch=feat/DEV-010-siliconflow-embedding-token-estimation-routing | 未实施 | 吸收 SHOULD_FIX Step 0；无 Git 写 |
| 2026-08-15 08:20 UTC | Steps 0–4 implemented | spec 六处 delta；factory+adapter；两处生产接线；U1–U8 + RET runtime + C1–C5 tightened；E1 helper patch | 待跑 | SHOULD_FIX 无 Amendment；无 Git 写 |
| 2026-08-15 08:25 UTC | Step 5 tested | status=implemented → tested；白名单测试 + ruff + mypy + 聚焦回归 | unit+contract 18 passed；ruff PASS；mypy src 0；regression 56 passed | 未 commit；next_action=CODE_REVIEW |
| 2026-08-15 08:30 UTC | Code Review + Commit Recorder | status=tested → reviewed；CODE_REVIEW_APPROVED session 93de8d64；P0=0 P1=0 P3=2；READY_FOR_HUMAN_COMMIT session 44cb5320 | 未复跑 | implementation_commit=null until feat git rev-parse；next_action=IMPLEMENTATION_RELEASE |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` | 六处 provider-aware 计数来源补丁 |
| `src/memory_system/infrastructure/tokenize/heuristic_token_count_adapter.py` | 创建；async `estimate_tokens` 包装 |
| `src/memory_system/infrastructure/tokenize/factory.py` | 创建；`create_tokenize_client` 分流 |
| `src/memory_system/infrastructure/tokenize/__init__.py` | 创建；导出 factory/adapter |
| `src/memory_system/domain/ports/tokenize_client.py` | docstring 改为 provider-aware |
| `src/memory_system/domain/services/production_extraction_pipeline.py` | 默认 `create_tokenize_client`；删除 `TeiTokenizeClient` 导入 |
| `src/memory_system/domain/services/retrieval_api_service.py` | 默认 `create_tokenize_client`；保留 `TokenizeServiceError` |
| `tests/unit/test_heuristic_token_count_adapter.py` | 创建；U1/U2 |
| `tests/unit/test_tokenize_client_factory.py` | 创建；U3–U8 + RET runtime assertion |
| `tests/contract/test_dev010_tokenize_provider_routing.py` | 创建；C1–C5（C1 tightened） |
| `tests/e2e/helpers/e2e001_helpers.py` | patch `create_tokenize_client` |
| `02_开发管理/tasks/DEV-010-siliconflow-embedding-token-estimation-routing.md` | 执行记录 / tested |
| `02_开发管理/progress.md` | in_progress → tested |
| `02_开发管理/master_plan.md` | DEV-010 tested + CHANGE-094/095 |

### 与原计划的差异

无 Amendment。吸收 Plan Review SHOULD_FIX=2：U 侧 RET `create_retrieval_api_service_from_app_state` runtime 断言；C1 禁止两处生产文件 `import TeiTokenizeClient`。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit/test_heuristic_token_count_adapter.py tests/unit/test_tokenize_client_factory.py -q` | **passed**（计入下方 18） |
| Contract | `uv run pytest tests/contract/test_dev010_tokenize_provider_routing.py -q` | **passed**（计入下方 18） |
| Unit+Contract（计划命令） | `uv run pytest tests/unit/test_heuristic_token_count_adapter.py tests/unit/test_tokenize_client_factory.py tests/contract/test_dev010_tokenize_provider_routing.py -q` | **18 passed** in 1.73s；exit=0 |
| Integration | 默认不新增 | 未跑 live TEI / live SiliconFlow |
| E2E | 仅 helper 补丁；不新增套件 | 未跑完整 E2E-001 |
| Focused regression | `uv run pytest tests/unit/test_production_extraction_pipeline.py tests/unit/test_retrieval_api_service.py tests/unit/test_siliconflow_embedding_client.py tests/unit/test_token_estimator.py -q` | **56 passed** in 2.03s；exit=0 |
| Ruff | `uv run ruff check src tests` | **All checks passed**；exit=0 |
| Mypy | `uv run mypy src` | **Success: no issues found in 200 source files**；exit=0 |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 2
review_report: "CODE_REVIEW_APPROVED session 93de8d64-bcaf-478c-8c57-f0c77c8e8670; P0=0 P1=0 P3=2 (non-blocking)"
```

### Git 记录

```yaml
branch: feat/DEV-010-siliconflow-embedding-token-estimation-routing
plan_commit: a55f99167863f508ef09033e13134348ab5e8b60
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`reviewed`
