# EXT-005 Reconciliation + 聚合门禁

## 1. 任务信息

```yaml
task_id: EXT-005
task_name: Reconciliation + 聚合门禁
status: committed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "5deb8949ee5ac367a08f173ef67c0c0689c26f5d"
branch: "feat/EXT-005-reconciliation-aggregation-gate"
created_at: "2026-08-12 16:15 UTC"
updated_at: "2026-08-12 09:10 UTC"
plan_review_round: 2
spec_sections:
  - "§1.2.1 记忆萃取整体流程（Reconcile Memories with Existing Graph 位置）"
  - "§2.1.3 Memory Extraction Task（任务表不保存 Memory/Entity 结果 ID 数组）"
  - "§2.1.4 Kafka 消费与任务幂等（processing + 非空 extraction_result 复用）"
  - "§2.1.6–§2.1.7 抽取结果校验（仅消费既有候选字段与 candidate_fingerprint/candidate_source_time）"
  - "§2.1.9 Neo4j 记忆图谱数据模型（Memory/Evidence 只读快照字段；本任务不写入）"
  - "§2.1.11 记忆候选召回与新旧记忆处理（本任务权威范围）"
  - "§2.1.12 置信度与重要性初始化（本任务仅产出计划态数值，不写图）"
  - "§2.1.13 图谱写入事务与幂等（事务前准备第 1/3–7 步；第 8–10 步与事务内写入 = EXT-006）"
  - "§2.1.15 失败处理（授权错误码词表）"
  - "§2.1.16 MVP 实现边界"
  - "§3.6 全异步客户端（neo4j AsyncDriver、LLMClient）"
  - "§3.24 连接池、超时与重试（Neo4j/LLM 既有固定值；禁止通用 Retry Decorator）"
  - "§3.26 Schema Migration（已执行 Migration 不得修改）"
  - "§3.27 日志、指标与敏感信息保护"
  - "§3.28 测试策略"
  - "Appendix B §B.7 Fingerprint、§B.8 Duplicate normalization、§B.10 Pipeline handoff、§B.11 Privacy、§B.12 MF-001"
prerequisites:
  formal:
    - "EXT-004 — SATISFIED/completed; PR #38 MERGED merge 229f5e960f51e55a7389599eeccdf650a9a7beff; transient EntityAlignmentOutcome with local_entity_id -> entity_id map available"
    - "EXT-003 — SATISFIED/completed; PR #37 MERGED; persisted extraction_result with candidate_fingerprint + candidate_source_time"
    - "DEV-004 — SATISFIED/completed; §2.1.9 Neo4j constraints/indexes including memory_subject_predicate, memory_user_type_status, evidence_id_unique"
    - "EXT-001 — SATISFIED/completed; task idempotency, PipelineTerminalDecision, terminal-persistence-before-offset gate"
  implementation_reuse:
    - "ExtractionValidatedResult / ExtractionMemoryCandidate typed models (domain/models/extraction_llm.py)"
    - "EntityAlignmentOutcome / EntityAlignmentSuccess (domain/models/entity_alignment.py)"
    - "compute_candidate_fingerprint (domain/services/extraction_fingerprint.py)"
    - "EntityAlignmentService read-only Mongo loader pattern (domain/services/entity_alignment_service.py)"
    - "Existing neo4j AsyncDriver in AppState; Neo4jSettings §3.24 fixed timeouts"
    - "Existing LLMClient / FakeLlmClient / DeepSeekLlmClient; settings.llm.extraction (MF-001)"
    - "memory_extraction settings: llm_timeout_seconds=120, max_memory_candidates_per_archive=50"
  baseline_evidence:
    branch: "main"
    head: "5deb8949ee5ac367a08f173ef67c0c0689c26f5d"
    working_tree_at_planning_start: "clean before planning whitelist writes"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=5deb8949ee5ac367a08f173ef67c0c0689c26f5d"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "Round 2 Plan Review PLAN_APPROVED (BLOCKER=0 MUST_FIX=0 SHOULD_FIX=0); human PLAN_APPROVED granted; Amendment 001 MF-001/SF-001–SF-004; Developer authorized post-PLAN_LANDING"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: true
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
stop_if:
  - "任何实现步骤需要新增错误码、新增未在 Task Plan 授权的 failed_stage 字面量、新增 durable 字段或改变既有 Schema"
  - "任何实现步骤需要写入 Neo4j（Entity/Memory/Evidence 或任何关系）"
  - "任何实现步骤需要改变 EXT-001/EXT-002/EXT-003/EXT-004 语义或 PipelineTerminalDecision"
  - "任何实现步骤需要实现 referenced_entity_write_set、core_search_text、TEI tokenize、memory_search_text_too_long（属 EXT-006）"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-006
```

## 2. 任务目标

在 EXT-003 已持久化 `extraction_result` 且 EXT-004 已产出瞬态 `EntityAlignmentOutcome` 之后，实现 §2.1.11 规定的**只读**已有 Memory 候选召回、逐候选 LLM Reconciliation、Archive 内候选聚合与 `reconciliation_plan_conflict` 门禁，并产出 §2.1.12 置信度/重要性计划值与 §2.1.13 事务前准备第 1/6/7 步计划字段，形成**瞬态非持久化** Reconciliation Plan 供 EXT-006 消费。

可验证目标：

1. **权威输入**：以已持久化 `extraction_result` + 瞬态 `EntityAlignmentOutcome` 为唯一输入；**不得**重新调用 extraction LLM、不得重读 `context_archive`、不得重算 `candidate_fingerprint` / `candidate_source_time`、不得重新执行实体对齐。
2. **Evidence 幂等跳过（§2.1.13 第 1 步）**：对每条候选计算 `evidence_id = SHA256(archive_id + ":" + candidate_fingerprint)`（UTF-8 拼接 + 小写 hex）；只读查询 Evidence 是否已存在且经 `SUPPORTS` 连接 Memory；已处理候选标记 `SKIP`（`reason_code` 计划态 = 已处理跳过，不调用 reconciliation LLM）。
3. **实体 ID 替换**：召回与 Reconciliation 输入中的 `subject_entity_id` / `object_entity_id` 必须使用 EXT-004 对齐后的最终 `entity_id`（含 `"user"` → `"user:" + user_id`）。
4. **只读 Memory 召回（§2.1.11）**：按 `user_id`、`memory_type`、对齐后 `subject_entity_id`、`predicate` 精确匹配；`status ∈ {active, conflicted}`；确定性 `ORDER BY` + `LIMIT 20`；所有 Cypher 显式 `user_id` 过滤。
5. **LLM Reconciliation**：当召回 ≥1 条已有 Memory 时，每候选调用一次 LLM（Structured Output）；输出 `action`/`target_memory_id`/`reason_code`/`merged_content`；应用层校验 `merged_content` 仅可来自候选与目标 Memory 原文。
6. **零召回确定性路径（MVP_LOCAL_DECISION LD-1）**：召回 0 条时，不调用 reconciliation LLM；确定性 `action=CREATE`、`reason_code=new_memory`、`target_memory_id=null`、`merged_content=null`。
7. **`aligned_memory_key`（CREATE 候选）**：实体对齐后按 §2.1.11 B.1 公式计算；仅用于本 Archive 计划聚合，不写入 Neo4j。
8. **Archive 内聚合与冲突门禁**：§2.1.11 A（已有 Memory 组）+ B（CREATE 组）；冲突返回 `reconciliation_plan_conflict`（永久错误）。
9. **计划态 §2.1.12**：新 Memory `final_confidence = round(llm_confidence, 4)` + 类型固定 `importance`；已有 Memory MERGE 组 `merged_confidence` 按合并公式；**不写图**。
10. **计划态 §2.1.13 第 6 步**：每条已有 Memory 更新计划输出 `increment_memory_version: bool`。
11. **计划态 §2.1.13 第 7 步**：每个聚合 CREATE 组预生成唯一 `memory_id`（可注入 factory，默认 UUID v4）。
12. **零持久化副作用**：不写入 Mongo/Neo4j；不改变任务 `status`；不提交 Kafka Offset；成功路径任务保持 `processing`。
13. **不改变上游语义**：`PipelineTerminalDecision`、`extraction_pipeline_port.py`、`extraction_task_consumer_service.py`、`extraction_llm_service.py`、`extraction_worker.py`、`entity_alignment_service.py` **逐字不变**。

## 3. 非目标与黑名单

- **任何 Neo4j 写入**：Entity/Memory/Evidence 节点、`SUBJECT`/`OBJECT`/`SUPPORTS`/`SUPERSEDES`/`CONFLICTS_WITH` 关系、写事务（§2.1.13 事务内写入 = EXT-006）。
- **§2.1.13 第 8–10 步**：`referenced_entity_write_set`、`planned_index_sync_memory_set`、`core_search_text`、TEI `/tokenize`、`memory_search_text_too_long`（EXT-006/EXT-007）。
- **Retrieval / Elasticsearch / Embedding**（EXT-007）。
- **任务终态与 Offset**：不得将任务标为 `completed`/`failed`、不得写 `last_error`、不得提交 Offset（库级返回值契约；pipeline 接线 `DEFERRED_FOR_MVP`）。
- **EXT-003→EXT-004→EXT-005 生产 continuation 编排**：Appendix B §B.10.4 延续 `DEFERRED_FOR_MVP`；不修改 `PipelineTerminalDecision` / consumer / worker。
- **改变 EXT-003/EXT-004 语义**：不重算 fingerprint、不重跑对齐、不修改 `extraction_result` 持久化边界或 `EntityAlignmentOutcome` 形状。
- **EXT-006+ 行为**；EXT-008/009；DEV-006 / PR #13。
- **新错误码**（优先 §2.1.15 既有码）；**禁止** `entity_alignment_failed`、`graph_write_failed`、`memory_search_text_too_long`、`retrieval_index_write_failed`、`archive_*`。
- **Schema/Migration/依赖/Settings 变更**（`dependency_changes_expected=NONE`；reconciliation LLM 复用 `llm.extraction` + 既有 `memory_extraction.llm_timeout_seconds`，不新增 `llm.reconciliation` 路径或 prompt_version Settings 字段）。
- 原始消息内容、memory content、prompt、response、secret、Cypher 参数值的日志/fixture/异常。

## 4. 当前代码状态与前置检查

### 4.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `5deb8949ee5ac367a08f173ef67c0c0689c26f5d`（与用户给定 `planning_baseline_main` 一致） |
| `git status --short` | 空 |
| `git log --oneline -10` | `5deb894` docs(status): backfill EXT-004 …；`db89455` complete EXT-004；`229f5e9` Merge PR #38；`0641ac3` feat(ext): entity alignment |
| EXT-004 | `completed`；PR #38 MERGED；`EntityAlignmentOutcome` 已实现 |
| EXT-003 | `completed`；`candidate_fingerprint` / `candidate_source_time` 已持久化 |
| workflow | `NORMAL`，explicit |

### 4.2 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无 reconciliation 领域模型/服务 | `rg reconciliation` 仅命中规划文档与 EXT-004 负向断言 |
| 无 Memory/Evidence 只读 Neo4j repository | `infrastructure/neo4j/` 仅 `entity_alignment_repository.py` |
| `compute_candidate_fingerprint` 已存在 | `extraction_fingerprint.py` |
| 无 `evidence_id` / `aligned_memory_key` 计算模块 | 需新建纯函数 |
| Neo4j 索引 `memory_subject_predicate` 已存在 | `002_initial_neo4j.py` |
| `LLMClient` + `FakeLlmClient` 可注入 | `infrastructure/llm/` |
| `max_memory_candidates_per_archive=50` | `settings/models.py` |

**结论**：EXT-005 需新建 reconciliation 领域层、只读 Memory/Evidence 查询层、reconciliation LLM 编排；不需要 Migration、依赖或 Settings 变更。

## 5. Exact Contract 闭合

### 5.1 输入契约

```text
ReconciliationInput {
  task_id: str
  archive_id: str
  user_id: str
  session_id: str | null          # 仅 Evidence 计划字段透传；本任务不写入
  extraction_result: ExtractionValidatedResult   # 已持久化 re-hydrate
  entity_alignment: EntityAlignmentSuccess        # EXT-004 成功输出；failure 时不得进入本服务
}
```

硬性规则：

- `extraction_result` 只能来自 Mongo 只读加载（`find_extraction_task_by_archive_id` + `ExtractionValidatedResult` strict re-hydrate）或调用方传入等价 typed 对象。
- `entity_alignment` 必须为 `EntityAlignmentOutcome.outcome=success`；对齐失败由上游处理，本服务不接受 `EntityAlignmentFailure` 作为可继续输入。
- **禁止**重算 `candidate_fingerprint` / `candidate_source_time`（除 contract 测试向量外，服务路径只读取持久化字段）。
- **禁止**修改 `extraction_result` 或任务文档。
- `user_id` 仅取任务文档；所有 Neo4j 查询必须 `user_id` 过滤。

### 5.2 Evidence ID 与已处理跳过（§2.1.13 第 1 步 + §2.1.7）

```text
evidence_id = lowercase_hex( SHA256( utf8( archive_id + ":" + candidate_fingerprint ) ) )
```

- `candidate_fingerprint` **必须**使用持久化值（EXT-003 已写入）；服务默认不重新计算（contract 测试可断言与 `compute_candidate_fingerprint` 一致）。
- 只读存在性查询（Q-E1）：Evidence 节点 `evidence_id` 存在 **且** 存在 `(evidence)-[:SUPPORTS]->(memory:Memory)` → 该候选 `action=SKIP`，`skip_reason=evidence_already_processed`（瞬态计划字段，非 §2.1.11 `reason_code`），**不**调用 reconciliation LLM，**不**进入聚合冲突检测。

### 5.3 对齐后候选视图（召回/Reconciliation 前）

对每条未跳过的 `ExtractionMemoryCandidate`，构建 `AlignedMemoryCandidateView`：

```text
AlignedMemoryCandidateView {
  candidate_index: int              # memories[] 原顺序索引（0-based）
  memory_type, content, predicate, object_value,
  event_status, start_time, end_time, original_time_text,
  confidence, source_message_ids,
  candidate_source_time, candidate_fingerprint,   # 来自持久化
  subject_entity_id: str            # 对齐后 entity_id
  object_entity_id: str | null       # 对齐后 entity_id 或 null
  evidence_id: str                  # §5.2 计算值
}
```

替换规则：

- `subject_entity_id`：`entity_alignment.local_entity_id_map()[candidate.subject_entity_id]`（保留值 `"user"` 已由 EXT-004 映射）。
- `object_entity_id`：若候选 `object_entity_id` 非 null，映射对齐后 ID；否则保持 null。
- `object_entity_id` 与 `object_value` 互斥不变（EXT-003 已校验）。
- 若任一 local ID 无法解析 → **不可预期内部失败** → `abort_without_terminal`（不新造错误码）。

### 5.4 只读 Memory 召回（§2.1.11）

**召回键**（每条 `AlignedMemoryCandidateView` 独立查询，可批量 `UNWIND`）：

| 维度 | 规则 |
|---|---|
| `user_id` | 必须等于任务 `user_id` |
| `memory_type` | 精确相等 |
| `subject_entity_id` | 对齐后最终 `entity_id` |
| `predicate` | 逐字完全相同 |
| `status` | `active` 或 `conflicted` |

**确定性排序 + LIMIT 20**（Cypher 逐字受 contract test 约束）：

```cypher
MATCH (m:Memory)
WHERE m.user_id = $user_id
  AND m.memory_type = $memory_type
  AND m.subject_entity_id = $subject_entity_id
  AND m.predicate = $predicate
  AND m.status IN ['active', 'conflicted']
RETURN m.memory_id AS memory_id,
       m.user_id AS user_id,
       m.memory_type AS memory_type,
       m.content AS content,
       m.subject_entity_id AS subject_entity_id,
       m.predicate AS predicate,
       m.object_entity_id AS object_entity_id,
       m.object_value AS object_value,
       m.status AS status,
       m.event_status AS event_status,
       m.start_time AS start_time,
       m.end_time AS end_time,
       m.original_time_text AS original_time_text,
       m.confidence AS confidence,
       m.latest_source_time AS latest_source_time
ORDER BY CASE m.status
           WHEN 'active' THEN 0
           WHEN 'conflicted' THEN 1
           ELSE 2
         END ASC,
         coalesce(m.latest_source_time, 0) DESC,
         m.memory_id ASC
LIMIT 20
```

批量形状（LD-2）：`UNWIND $recall_keys AS k` + 上述谓词；结果按 `candidate_index` 分组；禁止 per-candidate 串行往返（50 候选上限）。

**只读**：`session.execute_read`；禁止 `CREATE`/`MERGE`/`SET`/`DELETE`。

召回失败（驱动异常/超时/Cypher 错误/节点 property 无法映射）→ `graph_query_failed` + `failed_stage=reconciliation`（LD-10；码属 §2.1.11 记忆查询，stage 为本阶段）。

### 5.5 LLM Reconciliation（§2.1.11）

**调用条件**：

| 条件 | 行为 |
|---|---|
| Q-E1 已处理 | `SKIP`，不调 LLM |
| 召回 0 条 | LD-1：确定性 `CREATE` / `new_memory`，不调 LLM |
| 召回 ≥1 条 | 调用 reconciliation LLM **一次/候选** |

**输入 JSON**（严格 typed；不得含 Archive 全文、不得含未召回 Memory）：

```text
ReconciliationLlmInput {
  candidate: {
    memory_type, content,
    subject_entity_id,          # 对齐后
    predicate,
    object_entity_id,           # 对齐后或 null
    object_value,
    event_status, start_time, end_time, original_time_text,  # event 字段按候选原样
    candidate_source_time: int
  }
  existing_memories: [          # 0–20；§5.4 排序顺序
    {
      memory_id, memory_type, content,
      subject_entity_id, predicate,
      object_entity_id, object_value,
      event_status, start_time, end_time, original_time_text,
      status, confidence, latest_source_time
    }
  ]
}
```

**输出 Schema**（`extra=forbid`）：

```text
ReconciliationLlmOutput {
  action: "CREATE" | "MERGE" | "SUPERSEDE" | "CONFLICT" | "SKIP"
  target_memory_id: str | null     # CREATE/SKIP → null；其余必须 ∈ 输入 existing_memories
  reason_code: ReasonCode
  merged_content: str | null
}

ReasonCode =
  | "new_memory"
  | "same_semantic_memory"
  | "additional_evidence"
  | "explicit_correction"
  | "newer_value"
  | "unresolved_contradiction"
  | "different_event_time"
  | "not_durable"
  | "invalid_candidate"
```

**应用层校验（HARD_BLOCK）**：

1. `target_memory_id` 只能引用本次输入 `existing_memories[].memory_id`。
2. `CREATE`/`SKIP` → `target_memory_id` 必须为 null。
3. `MERGE`/`SUPERSEDE`/`CONFLICT` → `target_memory_id` 必须非 null。
4. `reason_code=additional_evidence` 且存在新信息 → `merged_content` 非空；完全重复 → `merged_content` 必须为 null。
5. `merged_content` 非空时，必须可验证为候选 `content` 与目标 Memory `content` 的融合子集（不得引入第三条来源）；校验失败 → `llm_invalid_output`。
6. Reconciliation 必须使用 `candidate_source_time` vs `latest_source_time` 判断新旧（规格禁止用 Archive 创建时间/服务器时间）。
7. LLM 不得输出自由文本推理；仅 Structured Output。

**LLM 调用约定（MF-001 延续 + LD-3）**：

- 复用既有 `LLMClient.generate_structured`；provider 路径使用 `settings.llm.extraction`（model/temperature/thinking/max_output_tokens）；timeout=`memory_extraction.llm_timeout_seconds`（120s）。
- System prompt 版本常量 `RECONCILIATION_PROMPT_VERSION = "memory_reconciliation_v1"`（模块内常量；**不**新增 Settings 字段；Evidence.`prompt_version` 仍指 extraction prompt，属 EXT-006）。
- Schema 校验失败：一次 correction retry（与 EXT-003 模式一致）；仍失败 → `llm_invalid_output`。
- Transport 失败映射：`llm_timeout` / `llm_request_failed`；`failed_stage="reconciliation"`（LD-10，**非** `llm_extraction`）。

### 5.6 `aligned_memory_key`（§2.1.11 B.1）

仅对最终 `action=CREATE` 的候选，在对齐后结构字段上计算：

```text
aligned_memory_key = lowercase_hex( SHA256( utf8( canonical_json({
  memory_type,
  final_subject_entity_id,
  predicate,
  final_object_entity_id,
  object_value,
  event_status,
  start_time,
  end_time
}) ) ) )
```

- `canonical_json`：固定字段顺序（上表）、`ensure_ascii=false`、`separators=(",", ":")`、JSON null 语义；**不含** `content` / `original_time_text` / `candidate_fingerprint`。
- `final_object_entity_id` / `object_value` 互斥与 EXT-003 一致。
- 不写入 Neo4j；不跨 Archive 复用为全局身份。

### 5.7 Archive 内候选聚合（§2.1.11 A/B + §2.1.13 第 5 步）

**聚合参与边界（SF-002）**：

- 仅 `action ∈ {MERGE, SUPERSEDE, CONFLICT, CREATE}` 的候选参与 §5.7 A/B 聚合。
- **排除**：`skip_reason=evidence_already_processed`（§5.2 Q-E1 幂等跳过）与 **LLM `action=SKIP`**（`reason_code` 为 LLM 输出，如 `invalid_candidate` / `not_durable`）——二者均**不得**进入 A/B 分组、不得贡献 `contributing_evidence_ids`、不得触发 `increment_memory_version`。

#### A. 指向已有 Memory 的候选聚合

1. 分组键：`target_memory_id`（仅 `action ∈ {MERGE, SUPERSEDE, CONFLICT}` 且非 null；且非 SF-002 排除项）。
2. 同组全部 `MERGE`：
   - 每组保留全部候选各自 `evidence_id`（不合并 Evidence）；
   - `merged_content`（SF-004）：对组内全部候选的 `merged_content`（含 null）经 `normalize_memory_content_for_aggregation` 后：
     - **全 null** → 计划态 `planned_merged_content=null`（合法）；
     - **恰好一个** distinct 非 null 规范化值 → 采用该值（允许组内混合 null/非 null）；
     - **≥2** distinct 非 null 规范化值 → `reconciliation_plan_conflict`；
   - 计划态 `planned_merged_confidence`：取组内最大 `new_confidence`（§5.8）代入 §2.1.12 合并公式；
   - 计划态 `planned_latest_source_time`：组内最大 `candidate_source_time`。
3. 同一 `target_memory_id` 出现不同 `action` → `reconciliation_plan_conflict`。
4. 同一 `target_memory_id` 出现 ≥2 个 `SUPERSEDE` 或 ≥2 个 `CONFLICT` → `reconciliation_plan_conflict`。
5. `SUPERSEDE`/`CONFLICT` 每组最多一条操作计划（不与其他 action 混组）。

#### B. 实体对齐后 CREATE 候选聚合

1. 仅 `action=CREATE` 候选参与（且非 SF-002 排除项）；按 `aligned_memory_key` 分组。
2. 同组预生成**一个** `planned_memory_id`（§5.10）；组内全部 `evidence_id` 指向该 ID；产出 `PlannedMemoryCreate` 且 `create_kind="create"`。
3. `planned_content` 选择（确定性）：
   - NFKC → 连续空白压缩 → 去首尾空白；
   - 规范化后全部相同 → 使用该值；
   - 否则按 `confidence DESC`、`candidate_source_time DESC`、`candidate_fingerprint ASC` 取第一条候选的**原始** `content`。
4. 同组 `planned_confidence` = 组内最大候选 `confidence`（再 `round(,4)`）；`planned_importance` 按 memory_type 表（§5.8）。
5. 同组 `planned_latest_source_time` = 组内最大 `candidate_source_time`。
6. **冲突门禁（LD-4）**：同组若存在规格意义上的「显式否定」或互斥事件语义且无法由 §B.3 确定性规则消解 → `reconciliation_plan_conflict`。MVP 最小实现：
   - 互斥 `event_status` 不可能同键（已含于 `aligned_memory_key`）；
   - 显式否定 NLP 检测 `DEFERRED_FOR_MVP`；
   - 不同 action 混入同 CREATE 组不可能（CREATE 组定义）。
7. 不同 `aligned_memory_key` 的 CREATE 分别生成独立 `PlannedMemoryCreate`（`create_kind="create"`）。

#### C. SUPERSEDE / CONFLICT 新 Memory 侧（MF-001）

1. 每个 `action=SUPERSEDE` 或 `action=CONFLICT` 聚合组（§5.7 A，且非 SF-002 排除项）除产出 `PlannedExistingMemoryUpdate` 外，**必须**同步产出一条自包含 `PlannedMemoryCreate` 行，供 EXT-006 **直接消费**，**禁止**要求 EXT-006 从 `extraction_result` 重推导新侧字段。
2. `create_kind`：
   - `SUPERSEDE` 组 → `create_kind="supersede_new"`；`supersedes_target_memory_id=target_memory_id`；`conflicts_with_target_memory_id=null`。
   - `CONFLICT` 组 → `create_kind="conflict_new"`；`conflicts_with_target_memory_id=target_memory_id`；`supersedes_target_memory_id=null`。
3. 新侧 `PlannedMemoryCreate` 必须包含与纯 CREATE 组相同的完整计划字段（§5.11）：结构字段、`planned_content`、`planned_confidence`、`planned_importance`、`planned_latest_source_time`、`initial_memory_version=1`、`contributing_candidate_indices`、`contributing_evidence_ids`。
4. `planned_content` 与结构字段：取该组唯一候选的**原始** `content` 与结构字段（§5.7 A 保证每组 SUPERSEDE/CONFLICT 仅一条操作计划）。
5. `aligned_memory_key`：对 `create_kind ∈ {supersede_new, conflict_new}` 置 `null`（不参与 CREATE 键聚合；`create_kind="create"` 时必填）。
6. `PlannedExistingMemoryUpdate.planned_new_memory_id` **必须**等于对应 `PlannedMemoryCreate.planned_memory_id`（双向可链接）。

### 5.8 计划态置信度与重要性（§2.1.12 — 仅输出，不写图）

**新 Memory（全部 `PlannedMemoryCreate` 行：`create_kind ∈ {create, supersede_new, conflict_new}`）**：

```text
planned_confidence = round(candidate_confidence, 4)   # create 组内取 max 后再 round；supersede_new/conflict_new 取唯一候选
planned_importance = IMPORTANCE_BY_TYPE[memory_type]

IMPORTANCE_BY_TYPE = {
  profile: 0.75,
  fact: 0.70,
  preference: 0.65,
  event: 0.55,
}
```

**已有 Memory MERGE 组**：

```text
planned_merged_confidence = round(
  min(1.0, old_confidence + (1 - old_confidence) * new_confidence * 0.25),
  4
)
```

其中 `old_confidence` 来自图谱召回快照；`new_confidence` 为组内最大候选 `confidence`（已 round）。

**SUPERSEDE / CONFLICT 目标侧（已有 Memory）**：计划态记录 `increment_memory_version=true`（status 变更）+ 保留旧 `importance`（萃取不修改已有 importance）。新侧置信度/重要性按上表 `PlannedMemoryCreate` 行输出（MF-001；**不得**仅留 `planned_new_memory_id` 占位）。

### 5.9 `increment_memory_version`（§2.1.13 第 6 步 — 计划布尔）

对每条**已有 Memory**（`MERGE`/`SUPERSEDE`/`CONFLICT` 目标或被动更新方）：

```text
increment_memory_version = true  当且仅当 聚合计划将：
  (a) 修改内容状态字段（content / confidence / latest_source_time / last_seen_time / event 字段 / status），或
  (b) 新增 ≥1 条 Evidence SUPPORTS 连接到该 Memory
```

- 同一 `target_memory_id` 在当前 Archive 计划内最多 `true` 一次。
- 纯 `SKIP`（已处理 Evidence）不触发。
- CREATE 新 Memory 的 `memory_version` 初始值 `1` 属 EXT-006 写入语义；本任务仅在 `PlannedMemoryCreate` 标注 `initial_memory_version: 1`。

### 5.10 预生成 `memory_id`（§2.1.13 第 7 步 — 计划占位）

- 每个 `PlannedMemoryCreate` 行（`create_kind ∈ {create, supersede_new, conflict_new}`）调用 `memory_id_factory()` 一次（默认 UUID v4；测试可注入固定序列）。
- 纯 CREATE 组：同 `aligned_memory_key` 组内共享一个 `planned_memory_id`。
- `supersede_new` / `conflict_new`：每组独立 `planned_memory_id`；通过 `PlannedExistingMemoryUpdate.planned_new_memory_id` 链接。
- 占位 ID **不**写入 Neo4j；EXT-006 必须以 `new_memory_create_plans[]` 中完整 `PlannedMemoryCreate` 行为准执行写入（MF-001）。

### 5.11 输出契约（瞬态 Reconciliation Plan）

**归属**：`src/memory_system/domain/models/reconciliation.py`；由 `reconciliation_service.py` 产出。

**不持久化**（§2.1.3 + Appendix B §B.1）：禁止 Mongo 新字段、Neo4j 写入、缓存。

**`session_id` 透传（SF-003）**：`ReconciliationSuccess` **不包含** `session_id`。EXT-006 写入 Evidence 时从**任务文档**（Mongo `extraction_task.session_id`）读取；`ReconciliationInput.session_id` 仅作编排层输入校验/日志上下文，**不得**作为 reconciliation 输出契约字段。

```text
ReconciliationOutcome {
  outcome: "success" | "failure"
  success: ReconciliationSuccess | null
  failure: ReconciliationFailure | null
}

ReconciliationSuccess {
  user_id: str
  archive_id: str
  per_candidate_decisions: [PerCandidateDecision]    # 与 memories[] 同序；含 SKIP/已处理
  existing_memory_update_plans: [PlannedExistingMemoryUpdate]
  new_memory_create_plans: [PlannedMemoryCreate]     # 纯 CREATE + supersede_new + conflict_new 全集（MF-001）
}

PerCandidateDecision {
  candidate_index: int
  candidate_fingerprint: str
  evidence_id: str
  action: ReconciliationAction
  target_memory_id: str | null
  reason_code: ReasonCode | null       # evidence_already_processed 时 null + skip_reason
  skip_reason: "evidence_already_processed" | null
  merged_content: str | null
  recalled_memory_count: int
  aligned_memory_key: str | null       # 仅 action=CREATE
}

PlannedExistingMemoryUpdate {
  target_memory_id: str
  aggregated_action: "MERGE" | "SUPERSEDE" | "CONFLICT"
  contributing_candidate_indices: [int]
  contributing_evidence_ids: [str]
  planned_merged_content: str | null
  planned_merged_confidence: float | null      # 仅 MERGE 组非 null
  planned_latest_source_time: int | null
  increment_memory_version: bool
  planned_new_memory_id: str | null           # SUPERSEDE/CONFLICT 时 = 对应 PlannedMemoryCreate.planned_memory_id
}

PlannedMemoryCreate {
  create_kind: "create" | "supersede_new" | "conflict_new"
  planned_memory_id: str                       # memory_id_factory 预生成；EXT-006 写入主键
  aligned_memory_key: str | null               # create_kind="create" 时必填；supersede_new/conflict_new 为 null
  supersedes_target_memory_id: str | null      # create_kind="supersede_new" 时 = target_memory_id
  conflicts_with_target_memory_id: str | null  # create_kind="conflict_new" 时 = target_memory_id
  memory_type: str
  planned_content: str
  subject_entity_id: str
  predicate: str
  object_entity_id: str | null
  object_value: str | null
  event_status, start_time, end_time, original_time_text  # 按组内确定性代表候选（LD-5）
  planned_confidence: float
  planned_importance: float
  planned_latest_source_time: int
  initial_memory_version: 1
  contributing_candidate_indices: [int]
  contributing_evidence_ids: [str]
}

ReconciliationFailure {
  error_code: ReconciliationErrorCode
  failed_stage: "reconciliation"
}

ReconciliationErrorCode =
  | "graph_query_failed"
  | "reconciliation_plan_conflict"
  | "llm_timeout"
  | "llm_request_failed"
  | "llm_invalid_output"
```

**EXT-006 消费规则（MF-001）**：

- 所有新 Memory 写入**仅**遍历 `new_memory_create_plans[]`；按 `create_kind` 决定关系：`create` → 纯 CREATE；`supersede_new` → 新 Memory + `SUPERSEDES` 到 `supersedes_target_memory_id`；`conflict_new` → 新 Memory + `CONFLICTS_WITH` 到 `conflicts_with_target_memory_id`。
- `existing_memory_update_plans[]` 仅处理目标侧更新；`planned_new_memory_id` 用于校验与 `new_memory_create_plans[].planned_memory_id` 一致，**不得**作为新侧字段唯一来源。

`ReconciliationAbort`（前置不满足 / 不可预期内部故障）：

```text
ReconciliationAbort { kind: "abort_without_terminal" }
```

### 5.12 授权失败词表与映射

| 条件 | error_code | failed_stage | 终态/Offset（接线后） |
|---|---|---|---|
| Memory 召回或 Evidence 存在性查询失败 | `graph_query_failed` | `reconciliation` | 可重试 `failed` |
| Archive 内聚合无法形成确定性计划 | `reconciliation_plan_conflict` | `reconciliation` | 永久 `failed`；不得用原 `extraction_result` 直接重试 |
| Reconciliation LLM 超时 | `llm_timeout` | `reconciliation` | 可重试 `failed` |
| Reconciliation LLM 请求失败 | `llm_request_failed` | `reconciliation` | 可重试 `failed` |
| Reconciliation LLM 输出校验失败（含 correction 后） | `llm_invalid_output` | `reconciliation` | 可重试 `failed` |
| 持久化结果/对齐结果无法 re-hydrate、图谱 property 异常、不可预期内部故障 | — | — | `abort_without_terminal` |

**EXT-005 禁止产生的错误码**：`entity_alignment_failed`（EXT-004）、`graph_write_failed`、`memory_search_text_too_long`、`retrieval_index_write_failed`、`archive_*`、以及任何新造码。

**日志（§2.1.15 #6 / §3.27 / Appendix B §B.11）**：失败日志必须且只包含 `task_id`、`archive_id`、`user_id`、`failed_stage`、`attempt_count`（`session_id` 可选）；**不得**记录 memory `content`、`merged_content`、实体名、prompt、response、Cypher 参数、secret。

### 5.13 与既有 pipeline 的衔接

- EXT-004→EXT-005 continuation 与 EXT-003→EXT-004 同样 `DEFERRED_FOR_MVP`（Appendix B §B.10.4 类推；不得为此改 `PipelineTerminalDecision`）。
- 本任务交付**库级可注入服务**；`extraction_pipeline_port.py`、`extraction_task_consumer_service.py`、`extraction_llm_service.py`、`extraction_worker.py`、`entity_alignment_service.py` **零 diff**。
- 失败映射为**契约声明**；EXT-005 只在返回值表达 failure，不自行写 `last_error`、不改 `status`、不提交 Offset。

## 6. 原子性、幂等、并发、版本冲突、用户隔离、部分失败、进程恢复

| 维度 | 结论 | 必需处理 |
|---|---|---|
| 原子性 | 零写入 → 无部分持久化 | 失败即整体 failure；不返回部分计划 |
| 幂等 | 无副作用 | 相同 `extraction_result` + 相同 `EntityAlignmentOutcome` + 相同图谱状态 → 相同计划 |
| Replay | Evidence 已存在 → SKIP | Q-E1 只读；跳过后不重调 reconciliation LLM |
| 并发 | 同 Partition 串行（§2.1.4） | 只读查询无写竞争；不加锁 |
| 版本冲突 | 不读写生产 `memory_version` | 仅输出 `increment_memory_version` 布尔；乐观锁属 EXT-006 |
| 用户隔离 | 单 `user_id` | 全部 Cypher `user_id` 谓词；跨用户 Memory 不可召回 |
| 部分失败 | 单候选 LLM/查询失败 → 整批失败 | 不返回部分 `per_candidate_decisions` |
| 进程恢复 | 无中间态 | 崩溃后 replay；任务保持 `processing` |
| Privacy | content 属用户数据 | 不进日志/异常/指标 label |

## 7. 分步骤实现方案

实现以 **PLAN_APPROVED** 为前提；未获批准前不得编写业务代码。

### Step 1 — 纯函数：Evidence ID、`aligned_memory_key`、内容规范化

- 文件：`domain/services/evidence_identity.py`、`domain/services/aligned_memory_key.py`（SF-001：**唯一**归一化归属；**禁止**新建 `memory_content_normalization.py`）。
- `compute_evidence_id(archive_id, candidate_fingerprint)` — §5.2。
- `compute_aligned_memory_key(...)` — §5.6；固定 `canonical_json` 字段顺序。
- `normalize_memory_content_for_aggregation(content)` — §5.7 A.2 / §5.7 B.3 NFKC/空白规则；定义于 `aligned_memory_key.py`。
- 无 IO/LLM/Neo4j 依赖。

### Step 2 — 领域模型

- 文件：`domain/models/reconciliation.py`、`domain/models/memory_recall.py`（Memory 只读快照 + label/property 常量）。
- 严格 `extra="forbid"`；`ReasonCode`/`ReconciliationAction` 枚举与 §5.5/§5.11 一致。
- **不**定义 `referenced_entity_write_set`、`core_search_text`、检索字段（EXT-006+）。

### Step 3 — 只读 Neo4j：Memory 召回 + Evidence 存在性

- 文件：`infrastructure/neo4j/memory_recall_repository.py`、`infrastructure/neo4j/evidence_lookup_repository.py`。
- Q-M1：§5.4 批量召回；Q-E1：`MATCH (ev:Evidence {evidence_id: $id})-[:SUPPORTS]->(m:Memory) WHERE ev.user_id = $user_id RETURN ev.evidence_id`（批量 `UNWIND`）。
- 只读事务；property 映射失败 → 服务层 `graph_query_failed`。
- 不修改 `entity_alignment_repository.py`。

### Step 4 — Reconciliation LLM 编排

- 文件：`domain/services/reconciliation_llm_service.py`（prompt 常量 + schema 校验 + correction retry）。
- 注入 `LLMClient`；使用 `settings.llm.extraction` + `memory_extraction.llm_timeout_seconds`（LD-3）。
- `failed_stage="reconciliation"`；禁止 `failed_stage="llm_extraction"`。
- 默认 CI 使用 `FakeLlmClient`；不默认真实 DeepSeek。

### Step 5 — 聚合、置信度、`increment_memory_version` 计划构建

- 文件：`domain/services/reconciliation_plan_builder.py`。
- 实现 §5.7 A/B、§5.8、§5.9、§5.10；`reconciliation_plan_conflict` 门禁。
- 纯函数 + typed 输入；便于 unit test。

### Step 6 — Reconciliation 主编排服务

- 文件：`domain/services/reconciliation_service.py`。
- 流程：加载输入 → 构建对齐候选视图 → Q-E1 跳过 → Q-M1 召回 → LLM/确定性 CREATE → plan builder → `ReconciliationOutcome`。
- 只读 Mongo 加载方法（沿用 EXT-004 模式，同一文件内；不修改 `extraction_task_repository.py` 写方法）。
- 前置：`status=processing` 且 `extraction_result != null` 且 `EntityAlignmentSuccess`；否则 `ReconciliationAbort`。

### Step 7 — 测试与质量门禁

- 按 §9 编写 Unit / Contract / Integration。
- Ruff + Mypy strict；不得降低断言。

## 8. 文件变更清单（精确路径白名单，无 glob）

### 8.1 本轮规划白名单（已使用）

- `02_开发管理/tasks/EXT-005-reconciliation-aggregation-gate.md`
- `02_开发管理/progress.md`
- `02_开发管理/master_plan.md`

本轮**未**修改权威规格正文、`src/**`、`tests/**`、配置、依赖、lockfile；本轮**未**执行任何 Git 写命令。

### 8.2 条件实现白名单（PLAN_APPROVED 后）

生产（新建）：

- `src/memory_system/domain/models/memory_recall.py` — Memory 只读快照、§2.1.9 property 常量。
- `src/memory_system/domain/models/reconciliation.py` — 输入/输出/计划/失败模型。
- `src/memory_system/domain/services/evidence_identity.py` — `compute_evidence_id`。
- `src/memory_system/domain/services/aligned_memory_key.py` — `compute_aligned_memory_key` + 内容规范化 helper。
- `src/memory_system/domain/services/reconciliation_llm_service.py` — reconciliation LLM + prompts + 校验。
- `src/memory_system/domain/services/reconciliation_plan_builder.py` — 聚合、置信度、increment 布尔、memory_id 预生成。
- `src/memory_system/domain/services/reconciliation_service.py` — 主编排 + 只读 Mongo 加载。
- `src/memory_system/infrastructure/neo4j/memory_recall_repository.py` — Q-M1 只读 Cypher。
- `src/memory_system/infrastructure/neo4j/evidence_lookup_repository.py` — Q-E1 只读 Cypher。

生产（**显式不变**，审查零 diff）：

- `src/memory_system/domain/services/entity_alignment_service.py`
- `src/memory_system/domain/services/extraction_llm_service.py`
- `src/memory_system/domain/services/extraction_pipeline_port.py`
- `src/memory_system/domain/services/extraction_task_consumer_service.py`
- `src/memory_system/domain/models/entity_alignment.py`
- `src/memory_system/domain/models/extraction_llm.py`
- `src/memory_system/infrastructure/neo4j/entity_alignment_repository.py`
- `src/memory_system/infrastructure/mongodb/extraction_task_repository.py`
- `src/memory_system/entrypoints/extraction_worker.py`
- `src/memory_system/infrastructure/runtime.py`
- `src/memory_system/settings/models.py`、`validators.py`
- `src/memory_system/observability/metrics.py`
- `scripts/migrations/**`

测试（新建）：

- `tests/unit/test_evidence_identity.py` — evidence_id 公式固定向量。
- `tests/unit/test_aligned_memory_key.py` — aligned_memory_key 字段顺序/编码/互斥。
- `tests/unit/test_reconciliation_plan_builder.py` — 聚合 A/B、冲突门禁、confidence/importance/increment 布尔。
- `tests/unit/test_reconciliation_service.py` — 全分支、LLM 注入、失败映射、零写入、privacy。
- `tests/unit/test_reconciliation_llm_service.py` — schema/merged_content 校验、correction retry、失败码。
- `tests/contract/test_ext005_contract.py` — 输入/输出契约、错误码白名单、只读 Cypher、无 EXT-006+ 字段、上游零变更。
- `tests/integration/test_ext005_memory_recall_neo4j.py` — 真实 Neo4j：召回排序/LIMIT/隔离/零写入/查询失败。
- `tests/integration/test_ext005_reconciliation_replay_mongo.py` — Mongo 加载 + replay 幂等 + 任务零变更 + Fake extraction LLM 零调用。

测试（**显式不变**）：`tests/**/test_ext004_*`、`test_ext003_*`、`test_ext002_*`、`test_ext001_*`、`test_entity_alignment_*`、`test_extraction_llm_*` 等上游套件。

明确不在白名单：

- `pyproject.toml`、`uv.lock`、`configs/**`、`.env.example`、`scripts/migrations/**`
- `src/memory_system/infrastructure/elasticsearch/**`、`embedding/**`、`kafka/**`
- `src/memory_system/api/**`
- graph write / retrieval sync / `referenced_entity_write_set` / `core_search_text` 模块
- DEV-006、PR #13
- 权威规格正文

## 9. Contract / Unit / Integration 测试计划

### 9.1 Unit — `test_evidence_identity.py`

| ID | 场景 | 期望 |
|---|---|---|
| E1 | evidence_id 公式 | `SHA256(archive_id + ":" + candidate_fingerprint)` UTF-8 小写 hex |
| E2 | 与持久化 fingerprint 一致 | 使用 `ExtractionMemoryCandidate.candidate_fingerprint` 不重算 |

### 9.2 Unit — `test_aligned_memory_key.py`

| ID | 场景 | 期望 |
|---|---|---|
| K1 | 字段顺序与 canonical_json | 固定向量；不含 content |
| K2 | 对齐后 entity_id 参与 | local ID 已替换为 final entity_id |
| K3 | object 互斥 | entity_id 与 object_value 互斥 |

### 9.3 Unit — `test_reconciliation_plan_builder.py`

| ID | 场景 | 期望 |
|---|---|---|
| P1 | MERGE 组多候选 | 单一更新计划；evidence_ids 全部保留 |
| P2 | MERGE 组 merged_content 多 distinct 非 null | `reconciliation_plan_conflict` |
| P2b | MERGE 组混合 null/非 null 且仅一个 distinct 非 null | 采用该非 null；合法 |
| P2c | MERGE 组全 null merged_content | `planned_merged_content=null`；合法 |
| P3 | 同 target 不同 action | `reconciliation_plan_conflict` |
| P4 | 多 SUPERSEDE 同 target | `reconciliation_plan_conflict` |
| P5 | CREATE 组同 aligned_memory_key | 单 `planned_memory_id`；`create_kind=create`；content tie-break 确定性 |
| P6 | CREATE 组不同 key | 多个 `PlannedMemoryCreate`（`create_kind=create`） |
| P7 | planned_confidence/importance | §2.1.12 公式与表 |
| P8 | increment_memory_version | MERGE 仅新 Evidence 也为 true；SKIP 为 false |
| P9 | SUPERSEDE/CONFLICT | 各产出完整 `PlannedMemoryCreate`（`supersede_new`/`conflict_new`）+ `PlannedExistingMemoryUpdate.planned_new_memory_id` 链接 |
| P10 | LLM SKIP 不参与聚合 | `action=SKIP` 候选不出现在 A/B 组 `contributing_*`（SF-002） |
| P11 | `new_memory_create_plans` 全集 | 纯 CREATE + supersede_new + conflict_new 均在 `new_memory_create_plans[]`（MF-001） |
| P12 | create_kind 链接字段 | `supersedes_target_memory_id`/`conflicts_with_target_memory_id` 与 `aggregated_action` 一致 |

### 9.4 Unit — `test_reconciliation_llm_service.py`

| ID | 场景 | 期望 |
|---|---|---|
| L1 | 合法 Structured Output | 解析成功 |
| L2 | target_memory_id 不在召回列表 | `llm_invalid_output` |
| L3 | additional_evidence 无 merged_content | `llm_invalid_output` |
| L4 | merged_content 含第三条来源 | `llm_invalid_output` |
| L5 | correction retry 一次 | 第二次成功；transport 不重试 |
| L6 | failed_stage | 恒为 `reconciliation` |

### 9.5 Unit — `test_reconciliation_service.py`

| ID | 场景 | 期望 |
|---|---|---|
| R1 | Happy path：无已有 Memory | 全 CREATE；零 reconciliation LLM 调用（LD-1） |
| R2 | Happy path：MERGE | 召回 + LLM + 聚合计划 |
| R3 | Evidence 已存在 | `SKIP` + `skip_reason=evidence_already_processed`；零 LLM |
| R4 | Replay 幂等 | 两次相同输入相同计划；零 Mongo 变更 |
| R5 | 图谱查询失败 | `graph_query_failed` + `failed_stage=reconciliation` |
| R6 | 聚合冲突 | `reconciliation_plan_conflict` |
| R7 | LLM 失败码 | 仅 `llm_timeout`/`llm_request_failed`/`llm_invalid_output` |
| R8 | 禁用码负向 | 无 `entity_alignment_failed`/`graph_write_failed`/`archive_*` 等 |
| R9 | 零 Neo4j 写入 | fake repo 无写方法；集成前后节点数不变 |
| R10 | 无 extraction LLM 重调 | Fake extraction LLM 计数 0 |
| R11 | 不重算 fingerprint/source time | 服务不调用 `compute_candidate_fingerprint`（除 evidence_id 输入已带 fingerprint） |
| R12 | 用户隔离 | 召回查询含 `user_id`；跨用户不命中 |
| R13 | Privacy | caplog 无 content/merged_content/prompt/response |
| R14 | 前置失败 | 非 processing / 空 extraction_result / 对齐失败 → `abort_without_terminal` |
| R15 | 50 候选批量召回 | 常数级查询次数 |

### 9.6 Contract — `test_ext005_contract.py`

| ID | 场景 | 期望 |
|---|---|---|
| C1 | 输入契约 | 消费持久化 extraction + EntityAlignmentSuccess；不接受 Archive raw |
| C2 | 输出形状 | `ReconciliationOutcome` 字段逐字；`PlannedMemoryCreate.create_kind` + 链接字段；`ReconciliationSuccess` **无** `session_id`（SF-003）；`extra=forbid` |
| C2b | MF-001 新侧自包含 | `supersede_new`/`conflict_new` 行含完整计划字段；EXT-006 无需重读 extraction_result |
| C3 | 错误码白名单 | §5.12 集合；负向断言禁用码 |
| C4 | failed_stage | reconciliation 失败恒 `reconciliation` |
| C5 | 不持久化 | 无 Mongo/Neo4j 写；`AUTHORIZED_*_FIELDS` 零变更 |
| C6 | 只读 Cypher | Q-M1/Q-E1 无 CREATE/MERGE/SET/DELETE；含 `user_id` |
| C7 | 无 EXT-006+ 字段 | 无 `referenced_entity_write_set`/`core_search_text`/`planned_index_sync_memory_set` |
| C8 | 上游零变更 | PipelineTerminalDecision / worker / extraction_llm / entity_alignment 不变 |
| C9 | Migration/依赖零变更 | 无新 migration；`pyproject.toml` 不变 |
| C10 | recall ORDER BY/LIMIT | Cypher 文本含 §5.4 排序与 `LIMIT 20` |

### 9.7 Integration — `test_ext005_memory_recall_neo4j.py`

| ID | 场景 | 期望 |
|---|---|---|
| I1 | 召回排序 | active 先于 conflicted；`latest_source_time DESC`；`memory_id ASC` |
| I2 | LIMIT 20 | 插入 >20 匹配仅返回 20 |
| I3 | 跨用户隔离 | 用户 B Memory 不可被用户 A 召回 |
| I4 | Evidence 存在性 | Q-E1 命中 → 服务层 SKIP |
| I5 | 零写入 | Memory/Evidence 节点数与 property 前后不变 |
| I6 | 查询失败注入 | `graph_query_failed` |

### 9.8 Integration — `test_ext005_reconciliation_replay_mongo.py`

| ID | 场景 | 期望 |
|---|---|---|
| M1 | 从 Mongo 加载并规划 | processing + 非空 extraction_result + 注入对齐结果 |
| M2 | 任务文档零变更 | 规划前后 `status`/`extraction_result`/`attempt_count` 不变 |
| M3 | Replay 两次计划一致 | 确定性 |
| M4 | 保持 processing | 无 completed/failed；无 Offset |

### 9.9 E2E / 失败注入 / 并发

| 场景 | 结论 |
|---|---|
| Kafka → 全链路 | 不适用；EXT-009 |
| 写失败注入 | N/A（无写入） |
| 并发同 Archive | 不适用；Partition 串行；只读幂等 |
| 真实 DeepSeek | 默认 skipped；Fake LLM |

## 10. 验收标准（可客观验证）

- [ ] Plan Review Round 2 通过（Amendment 001 闭合 MF-001）；`human_plan_approved=true` 后方可开发。
- [ ] 权威输入为持久化 `extraction_result` + `EntityAlignmentSuccess`；不重调 extraction LLM、不重算 fingerprint/source time、不重跑对齐（R10/R11/M2）。
- [ ] evidence_id 公式与 Q-E1 跳过语义正确（E1/R3/I4）。
- [ ] Memory 召回 Cypher 含确定性 `ORDER BY` + `LIMIT 20` + `user_id` 过滤（C6/C10/I1/I2）。
- [ ] 零召回确定性 CREATE 不调 reconciliation LLM（LD-1/R1）。
- [ ] 召回 ≥1 时 LLM Reconciliation schema/merged_content 校验（L1–L4）。
- [ ] `aligned_memory_key` 与 CREATE 聚合正确（K1–K3/P5/P6）。
- [ ] `reconciliation_plan_conflict` 门禁（P2–P4/P2b/P2c/R6）。
- [ ] `new_memory_create_plans` 含 create/supersede_new/conflict_new 全集；链接字段与 `planned_new_memory_id` 一致（P9/P11/P12/C2b）。
- [ ] LLM SKIP 不参与 A/B 聚合（P10/SF-002）。
- [ ] MERGE 组混合 null/非 null merged_content 规则（P2b/P2c/SF-004）。
- [ ] `session_id` 不在 reconciliation 输出；EXT-006 从任务文档读取（SF-003/C2）。
- [ ] 内容归一化仅 `aligned_memory_key.py`（SF-001）；无 `memory_content_normalization.py`。
- [ ] 计划态 confidence/importance/increment_memory_version/planned_memory_id 正确（P7–P9）。
- [ ] 输出瞬态不持久化；任务保持 `processing`；无 Offset（M2/M4/C5）。
- [ ] 零 Neo4j/Mongo 写入（R9/I5）。
- [ ] 失败映射仅 §5.12 授权码 + `failed_stage=reconciliation`（R5–R8/C3/C4）。
- [ ] `entity_alignment_failed`/`graph_write_failed`/`memory_search_text_too_long` 负向断言（R8/C3/C7）。
- [ ] 上游 pipeline/alignment/llm/worker/settings/migrations 零 diff（C8/C9）。
- [ ] Privacy：无 content/merged_content/prompt/response/secret 泄漏（R13）。
- [ ] 白名单外零文件变更；scoped tests PASS；Ruff/Mypy PASS；Review 无 P0/P1。

## 11. Open Issues

### 11.1 OI-006（非阻塞）

**OI-006** — `reconciliation_plan_conflict` 运维清理无 API Contract；`blocks_current_task: false`；`resolve_by_task: EXT-008 前需规格确认`。

- EXT-005 必须实现 `reconciliation_plan_conflict` 失败映射与永久错误语义（§2.1.15）。
- 不得在本任务发明管理 API 或清理操作；仅返回库级 `ReconciliationFailure`。

## 12. MVP 分类与决议记录

### 12.1 HARD_BLOCK

| 项 | 理由 |
|---|---|
| 只读 Neo4j + 零持久化 | 规格 §2.1.13 事务前准备 vs 事务内写入边界 |
| `reconciliation_plan_conflict` 门禁 | §2.1.11/§2.1.13 确定性写入计划前置条件 |
| merged_content 校验 | §2.1.11 防止 LLM 引入第三条来源 |
| 授权错误码白名单 | §2.1.15 + EXT-004/EXT-003 边界 |
| 对应测试 | 治理要求业务代码与测试并存 |

### 12.2 DEFERRED_FOR_MVP

| 项 | 归属 |
|---|---|
| EXT-004→EXT-005→EXT-006 生产 pipeline 接线 | Appendix B §B.10.4 类推 |
| `referenced_entity_write_set` / `core_search_text` / TEI / `memory_search_text_too_long` | §2.1.13 第 8–9 步；EXT-006 |
| CREATE 组「显式否定」NLP 检测 | §2.1.11 B.5；LD-4 最小门禁外语义 |
| 谓词语义相似召回 | §2.1.11 后续版本 |
| OI-006 运维清理 API | EXT-008 |
| SHA-256 collision | OI-EXT-003-005 |

### 12.3 MVP_LOCAL_DECISION

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | 召回 0 条 → 确定性 CREATE，不调 reconciliation LLM | §2.1.13「必要时」；降低 MVP 成本；可复现 |
| LD-2 | Q-M1/Q-E1 批量 `UNWIND` | 50 候选上限性能 |
| LD-3 | Reconciliation LLM 复用 `settings.llm.extraction` + 模块内 `memory_reconciliation_v1` 常量 | MF-001 延续；无 Settings 变更 |
| LD-4 | CREATE 组冲突门禁：结构键内互斥 + 不做显式否定 NLP | 闭合规格最小可测子集 |
| LD-5 | CREATE 组结构字段取 content tie-break 胜出候选 | 确定性代表 |
| LD-6 | `memory_id_factory` 默认 UUID v4，可注入 | 同 EXT-004 LD-1 |
| LD-7 | Mongo 只读加载置于 `reconciliation_service.py` | 同 EXT-004 LD-4 |
| LD-8 | Evidence 已处理 SKIP 使用瞬态 `skip_reason`，不占用 LLM `reason_code` | 区分 §2.1.13 幂等跳过与 LLM SKIP |
| LD-9 | `merged_content` 一致性比较使用与 content 相同的 NFKC/空白规范化 | 对齐 §2.1.11 A.3；SF-004 扩展混合 null/非 null |
| LD-10 | 本阶段全部失败码（含 `graph_query_failed`）→ `failed_stage="reconciliation"` | 与 `entity_alignment`（EXT-004 LD-9）对称；非 Appendix 修订 |
| LD-11 | `session_id` 不在 `ReconciliationSuccess`；EXT-006 从任务文档读取 | SF-003；reconciliation 输出不含 Evidence 会话字段 |

### 12.4 Amendment 001 — Round 2 Plan Remediation（MF-001 + SF-001–SF-004）

**触发**：Plan Review Round 1 `MUST_FIX=1`（MF-001）；`SHOULD_FIX=4`（SF-001–SF-004）。

| ID | 级别 | 问题 | 修订 |
|---|---|---|---|
| MF-001 | MUST_FIX | SUPERSEDE/CONFLICT 新侧输出契约不完整；§5.8「同 CREATE」但输出仅 `planned_new_memory_id` | §5.7 C、§5.8、§5.10、§5.11：`new_memory_create_plans[]` 为全部新 Memory 自包含行；`create_kind` + 链接字段；`PlannedExistingMemoryUpdate.planned_new_memory_id` 双向链接 |
| SF-001 | SHOULD_FIX | 归一化模块归属不清 | 内容规范化**仅** `aligned_memory_key.py`；禁止 `memory_content_normalization.py` |
| SF-002 | SHOULD_FIX | LLM SKIP 是否参与聚合未写明 | §5.7 聚合参与边界：LLM `action=SKIP` 与 evidence 已处理 SKIP 均排除 |
| SF-003 | SHOULD_FIX | `session_id` 透传路径 | `ReconciliationSuccess` 不含 `session_id`；EXT-006 从任务文档读取（LD-11） |
| SF-004 | SHOULD_FIX | MERGE 组混合 null/非 null `merged_content` | §5.7 A.2：恰好一个 distinct 非 null → 采用；≥2 → conflict；全 null OK |

**Round 1 决议保留**：LD-1–LD-10、HARD_BLOCK、DEFERRED_FOR_MVP、授权错误码白名单、上游零 diff、零写入边界**不变**。

**审批状态**：Amendment 001 落盘；`plan_review_round=2`；Round 2 `PLAN_APPROVED`（BLOCKER=0 MUST_FIX=0 SHOULD_FIX=0）；human PLAN_APPROVED granted；Developer authorized post-PLAN_LANDING。

### 12.4 SAFE_AUTO_REMEDIATION

| 项 | 处理 |
|---|---|
| （无） | — |

## 13. 风险与依赖结论

- **依赖**：`NONE`；`neo4j>=5.28,<6`、LLM 栈、`Neo4jSettings`、`memory_extraction` 已存在。
- **Migration**：`NONE`；`memory_subject_predicate` 等已由 DEV-004 创建。
- **配置**：`NONE`；不新增 `llm.reconciliation`。
- **主要风险**：
  1. 误用 `entity_alignment_failed` 或 `llm_extraction` stage → C3/C4 负向断言。
  2. 误写入 Neo4j → I5/R9 零写入断言。
  3. 误接线 pipeline 改变 Offset 语义 → C8。
  4. content 泄漏 → R13 caplog。
  5. `reconciliation_plan_conflict` 永久错误被当作可重试 → R6 + §5.12 映射。

## 14. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/EXT-005-reconciliation-aggregation-gate"
baseline_main: "5deb8949ee5ac367a08f173ef67c0c0689c26f5d"
expected_commits:
  - "docs(plan): add EXT-005 reconciliation aggregation gate plan"
  - "feat(ext): add reconciliation plan and read-only recall"
  - "docs(status): record EXT-005 implementation commit and PR"
  - "docs(status): complete EXT-005 after PR merge"
release_phases:
  PLAN_LANDING: "main: approved planning whitelist only; after PLAN_APPROVED; exact branch creation"
  IMPLEMENTATION_RELEASE: "feature branch only; exact production/test whitelist; no main write/push"
  POST_MERGE_CLEANUP: "NORMAL only after verified MERGED PR; complete governance on main; delete exact feat branch"
out_of_scope_changes:
  - "authoritative specification body"
  - "EXT-001/EXT-002/EXT-003/EXT-004 semantics"
  - "EXT-006 Neo4j graph transaction write"
  - "EXT-007 retrieval/Elasticsearch/Embedding"
  - "EXT-008/EXT-009"
  - "DEV-006 / PR #13"
  - "dependencies, migrations, settings expansion"
```

## 15. Plan Amendment

未来修改必须追加 Amendment 并重新 Plan Review。

- **Amendment 001**（2026-08-12）：Round 2 MF-001 + SF-001–SF-004；见 §12.4。

## 16. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-12 16:15 UTC | Planner 创建 Task Plan | 仅规划白名单（Task Plan / progress / master_plan）；未改 `src/**`、`tests/**`、规格正文、配置、依赖；未执行 Git 写 | N/A（规划-only） | `next_action=计划审查`；`developer_authorized=false`；不得触碰 DEV-006/PR#13 |
| 2026-08-12 16:30 UTC | Planner Amendment 001 (Round 2) | §5.7–§5.11 输出契约 MF-001；SF-001–SF-004；§12.4；Step 1/测试/验收同步；progress/master_plan 规划态 | N/A（规划-only） | `plan_review_round=2`；`approval_posture=AWAIT_PLAN_REVIEW_ROUND_2`；Developer NOT authorized |
| 2026-08-12 08:50 UTC | Developer implementation | 9 production + 8 test files per whitelist; reconciliation service/plan builder/LLM/Neo4j read repos; zero Mongo/Neo4j writes | scoped 63 passed; ruff/mypy PASS | `next_action=Code Review`; upstream zero diff verified |
| 2026-08-12 09:10 UTC | Release IMPLEMENTATION_RELEASE | implementation `c6e619d312bfd83fef30c9f394e16b42a65cba81`；PR #39 OPEN；feat push only | scoped 63 passed；ruff PASS；mypy PASS | `status=committed`；`next_action=WAITING_FOR_PR_MERGE` |
| 2026-08-12 08:35 UTC | Release Operator PLAN_LANDING | docs(plan) on main；feat branch created | N/A | human PLAN_APPROVED；`developer_authorized=true`；`next_action=Developer on feat/EXT-005-reconciliation-aggregation-gate` |

## 17. 最终状态

`committed` — IMPLEMENTATION_RELEASE complete；implementation `c6e619d312bfd83fef30c9f394e16b42a65cba81`；PR #39 OPEN；scoped 63 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；zero Mongo/Neo4j writes；upstream zero diff；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**。

### Git 记录

```yaml
branch: "feat/EXT-005-reconciliation-aggregation-gate"
plan_commit: "1556a3f50c0edca453ff992e15187d1dba93a425"
implementation_commit: "c6e619d312bfd83fef30c9f394e16b42a65cba81"
implementation_commit_message: "feat(ext): add reconciliation plan and read-only recall"
pr: "#39"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/39"
pr_state: OPEN
release_gate: IMPLEMENTATION_RELEASE_COMPLETE
```

### Code Review

```yaml
review_report: CODE_REVIEW_APPROVED
p0: 0
p1: 0
```
