# EXT-006 Neo4j 图谱事务写入

## 1. 任务信息

```yaml
task_id: EXT-006
task_name: Neo4j 图谱事务写入
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "59281d1e8d6e3fabfc0fe55f70b3fa50ac44bac2"
branch: "feat/EXT-006-neo4j-graph-transaction-write"
created_at: "2026-08-12 18:10 UTC"
updated_at: "2026-08-12 18:10 UTC"
plan_review_round: 2
spec_sections:
  - "§1.2.1 记忆萃取整体流程（Persist to Neo4j 位置）"
  - "§2.1.3 Memory Extraction Task（任务表不保存 Memory/Entity 结果 ID 数组）"
  - "§2.1.4 Kafka 消费与任务幂等（processing + 非空 extraction_result 复用）"
  - "§2.1.6–§2.1.7 抽取结果校验（Evidence 字段来源；candidate_fingerprint 只读消费）"
  - "§2.1.9 Neo4j 记忆图谱数据模型（Entity/Memory/Evidence 授权字段与关系）"
  - "§2.1.10 实体对齐与别名合并（写入阶段消费对齐计划）"
  - "§2.1.12 置信度与重要性初始化（应用 EXT-005 计划值）"
  - "§2.1.13 图谱写入事务与幂等（本任务权威范围：第 8–10 步 + 事务内写入）"
  - "§2.1.15 失败处理（graph_write_failed、memory_search_text_too_long）"
  - "§2.1.16 MVP 实现边界"
  - "§2.2.3 Retrieval Index 同步设计（仅消费 core_search_text 校验语义；ES 写入属 EXT-007）"
  - "§3.6 全异步客户端（neo4j AsyncDriver、httpx）"
  - "§3.10 Embedding / TEI（/tokenize 精确计数）"
  - "§3.24 连接池、超时与重试（Neo4j 既有固定值；禁止通用 Retry Decorator）"
  - "§3.26 Schema Migration（已执行 Migration 不得修改）"
  - "§3.27 日志、指标与敏感信息保护"
  - "§3.28 测试策略"
  - "Appendix B §B.7 Fingerprint、§B.10 Pipeline handoff、§B.11 Privacy"
prerequisites:
  formal:
    - "EXT-005 — SATISFIED/completed; PR #39 MERGED merge 638598080b2d24e9291933c5ef92d3e4d65a0612; transient ReconciliationOutcome with PlannedMemoryCreate / PlannedExistingMemoryUpdate"
    - "EXT-004 — SATISFIED/completed; transient EntityAlignmentSuccess with alignments + planned_alias_merge"
    - "EXT-003 — SATISFIED/completed; persisted extraction_result with candidate_fingerprint + source_message_ids"
    - "DEV-004 — SATISFIED/completed; §2.1.9 Neo4j constraints/indexes"
    - "EXT-001 — SATISFIED/completed; terminal-persistence-before-offset gate（本任务不提交 Offset）"
  implementation_reuse:
    - "ReconciliationSuccess / PlannedMemoryCreate / PlannedExistingMemoryUpdate (domain/models/reconciliation.py)"
    - "EntityAlignmentSuccess / AlignedEntity / PlannedEntityAliasMerge (domain/models/entity_alignment.py)"
    - "ExtractionValidatedResult / ExtractionMemoryCandidate (domain/models/extraction_llm.py)"
    - "compute_evidence_id (domain/services/evidence_identity.py)"
    - "compute_entity_key / normalize_entity_name (domain/services/entity_key.py)"
    - "Existing neo4j AsyncDriver in AppState; Neo4jSettings §3.24 fixed timeouts"
    - "memory_extraction.prompt_version Settings field"
  baseline_evidence:
    branch: "main"
    head: "59281d1e8d6e3fabfc0fe55f70b3fa50ac44bac2"
    working_tree_at_planning_start: "clean before planning whitelist writes"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=59281d1e8d6e3fabfc0fe55f70b3fa50ac44bac2"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "Round 2 pending Plan Review (Amendment 001)"
  amendment_recorded: true
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
stop_if:
  - "任何实现步骤需要新增错误码、新增未在 Task Plan 授权的 failed_stage 字面量、新增 durable 字段或改变既有 Schema"
  - "任何实现步骤需要 Elasticsearch 写入、Embedding 生成、任务 completed 或 Kafka Offset 提交"
  - "任何实现步骤需要改变 EXT-001/EXT-002/EXT-003/EXT-004/EXT-005 语义或 PipelineTerminalDecision"
  - "任何实现步骤需要触碰 DEV-006 / PR #13"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-006
```

## 2. 任务目标

在 EXT-003 已持久化 `extraction_result`、EXT-004 已产出瞬态 `EntityAlignmentSuccess`、EXT-005 已产出瞬态 `ReconciliationSuccess` 之后，实现 §2.1.13 **第 8–10 步事务前准备**与**事务内 Neo4j 原子写入**，将授权 Entity/Memory/Evidence 节点与关系落盘，并产出供 EXT-007 消费的 `index_sync_memory_set`（含已计算的 `core_search_text`）。

可验证目标：

1. **权威责任（§2.1.12 + §2.1.13）**：应用 EXT-005 计划态 `planned_confidence` / `planned_importance` / `planned_merged_confidence`；执行 `referenced_entity_write_set` 过滤；构建 `planned_index_sync_memory_set` 与 `core_search_text`；TEI `/tokenize` 门禁；单 Archive **一个原子 Neo4j 写事务**写入 Entity/Memory/Evidence 与授权关系。
2. **输入零重算 LLM**：不得重新调用 extraction/reconciliation LLM；不得重算 `candidate_fingerprint` / `candidate_source_time`；不得重跑实体对齐或 reconciliation 召回。
3. **Evidence 幂等**：`evidence_id` 唯一 + `MERGE`；全部计划 Evidence 已存在且 `SUPPORTS` 已连接 → 跳过图谱写入，返回成功 handoff（供 EXT-007 重试索引同步）。
4. **Entity 收敛**：`MERGE` 以 `entity_key` 去重；replay 时以图谱既有节点为准，不以 EXT-004 占位 `entity_id` 绕过唯一约束。
5. **Memory 所有权**：字段级 `SET`；新 Memory `memory_version=1`；已有 Memory 仅当 `increment_memory_version=true` 时递增一次；`SUPERSEDE`/`CONFLICT` 按 §2.1.11 更新 `status` 与关系方向。
6. **事务原子性**：写事务失败不得保留部分图谱修改；失败映射 `graph_write_failed` 或 `memory_search_text_too_long`。
7. **任务/Offset 边界**：成功图谱写入后任务保持 `processing`；**不**标 `completed`、**不**提交 Kafka Offset（属 EXT-007 完成门禁）。
8. **零上游语义变更**：`PipelineTerminalDecision` / consumer / `extraction_llm_service` / `extraction_worker` / `entity_alignment_service` / `reconciliation_service` **逐字不变**（continuation `DEFERRED_FOR_MVP`）。

## 3. 非目标与黑名单

- **Elasticsearch / Embedding / `search_text` 含 alias 扩展**（EXT-007）；本任务仅构建并校验 `core_search_text`，不写入 ES、不生成向量。
- **任务终态与 Offset**：不得将任务标为 `completed`/`failed`、不得写 `last_error`、不得提交 Offset（库级返回值契约；pipeline 接线 `DEFERRED_FOR_MVP`）。
- **EXT-003→EXT-006 生产 continuation 编排**：Appendix B §B.10.4 延续 `DEFERRED_FOR_MVP`。
- **重调上游阶段**：不重跑 EXT-003 LLM、EXT-004 对齐、EXT-005 reconciliation LLM/召回。
- **改变上游语义**：不修改 `extraction_result`、不修改 `ReconciliationOutcome`/`EntityAlignmentOutcome` 形状。
- **EXT-007+**；EXT-008/009；DEV-006 / PR #13。
- **新错误码**（优先 §2.1.15 既有码）；**禁止** `entity_alignment_failed`、`graph_query_failed`、`reconciliation_plan_conflict`、`llm_*`、`archive_*`、`retrieval_index_write_failed`。
- **Schema/Migration/依赖/Settings 变更**（`dependency_changes_expected=NONE`；`prompt_version` 等既有字段只读消费）。
- 原始消息内容、memory content、实体名、prompt、response、Cypher 参数值、secret 的日志/fixture/异常。

## 4. 当前代码状态与前置检查

### 4.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `59281d1e8d6e3fabfc0fe55f70b3fa50ac44bac2`（与用户给定 `planning_baseline_main` 一致） |
| `git status --short` | 空 |
| EXT-005 | `completed`；`ReconciliationSuccess` 模型与 plan builder 已实现 |
| EXT-004 | `completed`；`EntityAlignmentSuccess` 已实现 |
| EXT-003 | `completed`；`extraction_result` 持久化已实现 |
| workflow | `NORMAL`，explicit |

### 4.2 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无 graph write 领域模型/服务 | `rg graph_write` 仅命中规格/规划文档 |
| 无 Neo4j 写 repository | `infrastructure/neo4j/` 仅只读 recall/evidence/alignment |
| 无 TEI `/tokenize` client | embedding 栈仅有 SiliconFlow `/v1/embeddings` |
| 无 `referenced_entity_write_set` / `core_search_text` 模块 | EXT-005 明确 defer |
| Neo4j 约束/索引已存在 | `002_initial_neo4j.py` |
| `failed_stage=graph_write` 已在规格示例与测试中授权 | `extraction_task_models.py` / consumer tests |

**结论**：EXT-006 需新建 graph write 领域层、TEI tokenize 端口、Neo4j 写事务 repository；不需要 Migration、依赖或 Settings 变更。

## 5. Exact Contract 闭合

### 5.1 输入契约

```text
GraphWriteInput {
  task_id: str
  archive_id: str
  user_id: str
  session_id: str | null              # 从任务文档读取（LD-6 / EXT-005 SF-003）
  extraction_result: ExtractionValidatedResult   # 已持久化 re-hydrate；Evidence 字段来源
  entity_alignment: EntityAlignmentSuccess       # EXT-004 成功输出
  reconciliation: ReconciliationSuccess            # EXT-005 成功输出
}
```

| 输入 | 耐久性 | Replay 行为 | 前置条件 |
|---|---|---|---|
| `extraction_result` | **持久化**（Mongo） | 只读 re-hydrate；禁止重算 fingerprint/source time | 非空；`status=processing`（服务前置） |
| `EntityAlignmentSuccess` | **瞬态** | 调用方重跑 EXT-004 或传入等价对象 | `outcome=success` |
| `ReconciliationSuccess` | **瞬态** | 调用方重跑 EXT-005 或传入等价对象 | 无 `ReconciliationFailure` |
| `task_id` / `archive_id` / `user_id` / `session_id` | **持久化**（Mongo 任务文档） | 从任务文档读取 | `user_id` 与 archive/event 一致 |
| 当前 Neo4j 状态 | **外部读** | 写前只读查询 `entity_key`/`evidence_id`/`memory_id` 存在性 | 驱动可用 |

硬性规则：

- **禁止**重调 extraction/reconciliation/alignment LLM。
- **禁止**修改 Mongo `extraction_result` 或任务 `status`（库服务边界；接线后由下游阶段改状态）。
- `user_id` 仅取任务文档；全部 Cypher 必须 `user_id` 过滤。
- `session_id` **不得**从 `ReconciliationSuccess` 读取（该对象不含此字段）。

### 5.2 EXT-005 计划 ID 消费

| 字段 | 消费规则 |
|---|---|
| `new_memory_create_plans[].planned_memory_id` | 新 Memory 主键；`MERGE (m:Memory {memory_id})`；replay 使用相同 ID，禁止重新 mint |
| `existing_memory_update_plans[].target_memory_id` | 已有 Memory 更新目标；写前断言节点存在且 `user_id` 匹配 |
| `planned_new_memory_id` | 仅用于与 `new_memory_create_plans` 双向校验；**不得**作为新侧唯一来源 |
| `create_kind` | `create`：纯新节点；`supersede_new`：新节点 + `(new)-[:SUPERSEDES]->(old)` + old `status=superseded`；`conflict_new`：新节点 + `(new)-[:CONFLICTS_WITH]->(old)` + 双方 `status=conflicted` |
| `contributing_evidence_ids` | 每条 Evidence `MERGE` + `SUPPORTS` 到对应 Memory |
| `increment_memory_version` | 已有 Memory 内容/Evidence 更新时最多递增一次 |
| `entity_alignment.alignments[].entity_id` | 写 Entity 时以 `entity_key` MERGE；replay 后最终 `entity_id` 以图谱节点为准 |

**`existing_memory_update_plans[]` 字段应用（SF-001）**：

| 字段 | 写入规则 |
|---|---|
| `planned_merged_content` | 非 null 时 `SET m.content`；null 时保留原 content |
| `planned_merged_confidence` | MERGE 组非 null 时 `SET m.confidence` |
| `planned_latest_source_time` | 非 null 时 `SET m.latest_source_time` |
| `increment_memory_version` | true 时同事务一次 `memory_version = memory_version + 1` |
| `aggregated_action=SUPERSEDE` | 目标 Memory `status=superseded` + `memory_version+1`；新侧见 `create_kind=supersede_new` |
| `aggregated_action=CONFLICT` | 目标 Memory `status=conflicted` + `memory_version+1`；新侧见 `create_kind=conflict_new` |
| `aggregated_action=MERGE` | 仅字段级更新 + Evidence；**不**改 `status` |

### 5.2.1 Evidence 时间字段来源（MF-001 闭合）

`ExtractionMemoryCandidate` 仅持久化 `source_message_ids` 与 `candidate_source_time`（user 消息 timestamp 最大值）。Evidence 还要求：

```text
source_time_start = min(timestamp of each source_message_id)
source_time_end   = max(timestamp of each source_message_id)
```

**MVP_LOCAL_DECISION LD-9**：允许 **只读** `context_archive` 查找（按 `archive_id` + `source_message_ids`）解析消息 `timestamp`；**禁止**重跑预处理/redaction/LLM；**禁止**重算 `candidate_fingerprint`/`candidate_source_time`。若 Archive 缺失或消息 ID 无法解析 → `abort_without_terminal`（不造码）。单消息时 `source_time_start = source_time_end = candidate_source_time`（contract 测试断言）。

### 5.3 事务前准备（§2.1.13 第 8–10 步）

**第 8 步 — `referenced_entity_write_set`**：

- 从 `reconciliation` 全部非 SKIP 计划的 `subject_entity_id` / `object_entity_id`（非 null）收集。
- 仅保留 `entity_alignment.alignments` 中对应条目；未被引用的候选 Entity **不得**写入。
- 输出 `ReferencedEntityWritePlan[]`：`entity_key`、`entity_id`（计划态）、`planned_create`、`planned_aliases`、`canonical_name` 等 EXT-004 已计划字段。

**第 9 步 — `planned_index_sync_memory_set` + `core_search_text`**：

- 集合 = 本 Archive **写事务内**将创建或更新的全部 Memory ID（`new_memory_create_plans[].planned_memory_id` + `existing_memory_update_plans[].target_memory_id`）。
- **DEFERRED_FOR_MVP（SF-002）**：跨 Archive、因 Entity alias 更新而需重同步的**其他** Memory 不在 EXT-006 展开查询；若规格后续强制要求，由 EXT-007 以 Neo4j 权威数据扩展 `index_sync_memory_set`（本任务 handoff 仅保证本 Archive 写入集完整）。
- 对每条 Memory 构建 `core_search_text`（§2.2.3 公式；**不含** aliases）：
  ```text
  join_non_empty_with_single_space(content, subject_canonical_name, predicate, object_canonical_name_or_object_value)
  ```
- 主体/客体为 `user:{user_id}` 时**不**拼接 `canonical_name=current_user`。
- 通过 TEI `POST /tokenize` 精确计数；`token_count > 1024` → `memory_search_text_too_long`，**不得**开启写事务。
- NFKC、首尾去空白、连续空格压缩（与 §2.2.3 规则 1 一致）。

**第 10 步 — 不可变最终写入计划**：

- 冻结 Entity 写入行、Memory 创建/更新行、Evidence 行、关系行；写事务内不得再调用 LLM、不得重算长度策略。

### 5.4 事务内写入（§2.1.13 单事务）

**边界**：当前 Archive 全部写入操作在 **一个** Neo4j 写事务内完成；`session.execute_write` 回调内顺序执行，最后 `commit`；异常 → 整事务回滚。

写入顺序（MVP_LOCAL_DECISION LD-2）：

1. **Entity**：对 `referenced_entity_write_set` 每项 `MERGE (e:Entity {entity_key})` + `ON CREATE SET` 授权字段 + `ON MATCH` 仅更新 `aliases`/`updated_time`（字段级）；禁止覆盖 `canonical_name`（MVP 恒 `canonical_name_replaced=false`）。
2. **Memory CREATE**：`new_memory_create_plans[]`；`memory_version=1`；`status=active`；`abstraction_level=0`；`retrieval_count=0`；`last_retrieved_time=null`；`last_consolidated_time=null`；事件字段按 `memory_type` 规则。
3. **Memory UPDATE**：`existing_memory_update_plans[]`；字段级 `SET` 仅 Memory Extraction 拥有字段；`increment_memory_version=true` 时 `memory_version = memory_version + 1`（一次）；`planned_latest_source_time` 写入 `latest_source_time`；新 Evidence 连接时 `last_seen_time=server_now`（SF-003）。
4. **Memory CREATE 时间字段（SF-003）**：`first_seen_time=created_time=server_now`；`last_seen_time=server_now`；`latest_source_time=planned_latest_source_time`；`updated_time=server_now`。
5. **SUPERSEDE/CONFLICT 目标侧**：更新 old Memory `status`；SUPERSEDE 时 old `memory_version+1`；CONFLICT 时 old/new 双方 `conflicted` 且 old `memory_version+1`（§2.1.11）。
6. **关系**：`SUPERSEDES`、`CONFLICTS_WITH`（固定方向）；`SUBJECT`；条件 `OBJECT`。
7. **Evidence**：每条 `contributing_evidence_id` → `MERGE (ev:Evidence {evidence_id})` + `SUPPORTS` → Memory；`extracted_content` 取对应候选原始 `content`（非 merged）；`source_message_ids` 来自 `extraction_result`；`source_time_start`/`source_time_end` 按 §5.2.1；`prompt_version` 来自 Settings；`created_time` 仅 ON CREATE（幂等重试不得更新）。
8. **提交**。

**时间字段**（MVP_LOCAL_DECISION LD-5）：`first_seen_time`/`created_time`/`last_seen_time`/`updated_time` 使用可注入 `server_time_provider`（默认 `time.time()` 整秒）；Evidence 幂等重试**不得**更新 `created_time`（SF-004）。

### 5.5 幂等 / Replay

| 场景 | 行为 |
|---|---|
| 全部计划 `evidence_id` 已存在且 `SUPPORTS` 已连接 | **跳过**写事务；返回 `GraphWriteSuccess(skipped_graph_write=true)`；仍返回 `index_sync_memory_set` 供 EXT-007 |
| 写事务成功后 Kafka 重投 | 同上 SKIP 路径；**不得**重复节点/关系 |
| 写事务失败 | 无部分图谱状态；返回 `GraphWriteFailure(graph_write_failed)`；**不**标任务完成；**不**提交 Offset |
| 重复 `evidence_id` 同事务 | `MERGE` 幂等；不重复 `SUPPORTS` |
| Entity replay | `entity_key` MERGE 复用既有 `entity_id`；占位 ID 与图谱不一致时以 MERGE 结果为准 |
| `memory_id` replay | `MERGE` on `memory_id`；禁止 second CREATE |

### 5.6 输出契约

```text
GraphWriteOutcome {
  outcome: "success" | "failure"
  success: GraphWriteSuccess | null
  failure: GraphWriteFailure | null
}

GraphWriteSuccess {
  user_id: str
  archive_id: str
  skipped_graph_write: bool
  index_sync_memory_set: [
    {
      memory_id: str
      core_search_text: str
      token_count: int
    }
  ]
}

GraphWriteFailure {
  error_code: "graph_write_failed" | "memory_search_text_too_long"
  failed_stage: "graph_write"
}

GraphWriteAbort {
  kind: "abort_without_terminal"
}
```

`index_sync_memory_set` 为 EXT-007 权威 handoff；本任务不持久化。

### 5.7 授权失败词表与映射

| 条件 | error_code | failed_stage | 终态/Offset（接线后） |
|---|---|---|---|
| Neo4j 写事务失败（驱动异常/超时/Cypher 错误/约束冲突） | `graph_write_failed` | `graph_write` | 可重试 `failed`；Offset 仅在 failed 持久化成功后 |
| `core_search_text` TEI 计数 > 1024 | `memory_search_text_too_long` | `graph_write` | 永久 `failed`；不得开启写事务 |
| TEI `/tokenize` 不可用/响应非法 | `graph_write_failed` | `graph_write` | 可重试 `failed`（LD-3：基础设施失败归入 graph_write_failed） |
| 输入无法 re-hydrate、计划校验失败、图谱 property 异常、不可预期内部故障 | — | — | `abort_without_terminal` |

**EXT-006 禁止产生的错误码**：`entity_alignment_failed`、`graph_query_failed`、`reconciliation_plan_conflict`、`llm_*`、`archive_*`、`retrieval_index_write_failed`、任何新造码。

**日志（§2.1.15 #6 / §3.27 / Appendix B §B.11）**：失败日志必须且只包含 `task_id`、`archive_id`、`user_id`、`failed_stage`、`attempt_count`（`session_id` 可选）；**不得**记录 memory `content`、`core_search_text` 全文、实体名、Cypher 参数、secret。

### 5.8 任务 / Offset 语义

| 问题 | 结论 |
|---|---|
| 成功图谱写入是否完成整个 extraction task？ | **否**；§2.1.13 完成顺序要求 Neo4j → ES → `completed` → Offset |
| 后续阶段 | EXT-007 Retrieval Index 同步；然后任务 `completed` + Offset |
| EXT-006 可否提交 Offset？ | **禁止** |
| Offset 前必须存在什么 durable 状态？ | 图谱已提交（本任务）；`completed` + Offset 属 EXT-007 |
| 是否写 Mongo task status？ | 库服务**不**写；任务保持 `processing` |

### 5.9 与既有 pipeline 的衔接

- EXT-003→EXT-004→EXT-005→EXT-006 continuation 与上游同样 `DEFERRED_FOR_MVP`。
- 本任务交付**库级可注入服务**；`extraction_pipeline_port.py`、`extraction_task_consumer_service.py`、`extraction_llm_service.py`、`extraction_worker.py`、`entity_alignment_service.py`、`reconciliation_service.py` **零 diff**。
- 失败映射为**契约声明**；EXT-006 只在返回值表达 failure，不自行写 `last_error`、不改 `status`、不提交 Offset。

## 6. 原子性、幂等、并发、版本冲突、用户隔离、部分失败、进程恢复

| 维度 | 结论 | 必需处理 |
|---|---|---|
| 原子性 | 单 Archive 单写事务 | 失败整事务回滚；集成测试断言无部分节点 |
| 幂等 | `evidence_id`/`entity_key`/`memory_id` MERGE + 全 Evidence 已处理 SKIP | 重复投递不得重复图谱 |
| Replay | 重跑 EXT-004/005 或复用瞬态计划 | 相同输入+图谱状态 → 相同写入效果 |
| 并发 | 同 Partition 串行（§2.1.4） | `archive_id` 唯一任务；不加分布式锁 |
| 版本冲突 | `increment_memory_version` 一次递增 | 写事务内 `memory_version = memory_version + 1`；不做 CAS 重试（MVP） |
| 用户隔离 | 单 `user_id` | 全部 Cypher `user_id` 谓词；跨用户节点不可链接 |
| 部分失败 | 写事务失败 → 无图谱变更 | 返回 `graph_write_failed`；不 partial success |
| 进程恢复 | 崩溃后 replay | Evidence 幂等 SKIP 或完整重试写事务 |
| Privacy | content/实体名属用户数据 | 不进日志/异常/指标 |

## 7. 分步骤实现方案

实现以 **PLAN_APPROVED** 为前提；未获批准前不得编写业务代码。

### Step 1 — 领域模型

- 文件：`domain/models/graph_write.py`
- `GraphWriteInput` / `GraphWriteOutcome` / `GraphWriteSuccess` / `GraphWriteFailure` / `GraphWriteAbort`
- `ReferencedEntityWritePlan` / `ImmutableGraphWritePlan` / `IndexSyncMemoryEntry`
- `Memory`/`Evidence` 写侧 label/property 常量（与 §2.1.9 对齐；可与只读常量共享或扩展）
- 严格 `extra="forbid"`

### Step 2 — `referenced_entity_write_set` 纯函数

- 文件：`domain/services/referenced_entity_write_set.py`
- 输入：`ReconciliationSuccess` + `EntityAlignmentSuccess`
- 输出：过滤后的 `ReferencedEntityWritePlan[]`
- 无 IO

### Step 3 — `core_search_text` 构建

- 文件：`domain/services/core_search_text.py`
- 实现 §2.2.3 `core_search_text` 拼接与规范化
- 需要 Entity `canonical_name`：写前从 alignment 计划或 Neo4j 只读快照解析
- 无 TEI 依赖（计数在 service 层）

### Step 4 — TEI Tokenize 端口

- 文件：`domain/ports/tokenize_client.py`（Protocol）、`infrastructure/tei/tei_tokenize_client.py`、`infrastructure/tei/fake_tokenize_client.py`
- `POST {embedding_service_base}/tokenize`；返回 `token_count`
- 可注入 Fake（固定计数或按长度启发，仅测试）
- **不**实现 `TEIEmbeddingClient` 全量（DEV-006 superseded；LD-4）

### Step 5 — 不可变写入计划构建

- 文件：`domain/services/graph_write_plan_builder.py`
- 组合 Step 2–4：referenced entities + index sync set + token gate + 冻结 `ImmutableGraphWritePlan`
- **LD-9 调用点**：在冻结 Evidence 行之前，调用 `context_archive_message_timestamp_repository` 解析每条 `contributing_evidence_id` 对应候选的 `source_time_start`/`source_time_end`；Archive 缺失或消息 ID 不可解析 → 向上抛 `GraphWriteAbort`（不进入写事务）
- `memory_search_text_too_long` 在此阶段返回 failure

### Step 6 — Neo4j 写 Repository

- 文件：`infrastructure/neo4j/graph_write_repository.py`
- 单写事务执行 `ImmutableGraphWritePlan`
- 批量 `UNWIND`；字段级 `SET`；显式 `user_id`
- 写前可选只读存在性检查（Evidence SKIP 路径）
- 驱动异常向上抛，由 service 映射 `graph_write_failed`

### Step 7 — Graph Write 主编排服务

- 文件：`domain/services/graph_write_service.py`
- 流程：校验前置 → Evidence 全已处理？→ SKIP success : plan builder → repository.write → `GraphWriteOutcome`
- 只读 Mongo 加载任务元数据（`session_id`；沿用 EXT-004/005 模式）
- 前置：`processing` + 非空 `extraction_result` + 成功 alignment + 成功 reconciliation

### Step 8 — 测试与质量门禁

- 按 §9 编写 Unit / Contract / Integration
- Ruff + Mypy strict

## 8. 文件变更清单（精确路径白名单，无 glob）

### 8.1 本轮规划白名单（已使用）

- `02_开发管理/tasks/EXT-006-neo4j-graph-transaction-write.md`
- `02_开发管理/progress.md`
- `02_开发管理/master_plan.md`

### 8.2 条件实现白名单（PLAN_APPROVED 后）

生产（新建）：

- `src/memory_system/domain/models/graph_write.py`
- `src/memory_system/domain/ports/tokenize_client.py`
- `src/memory_system/domain/services/referenced_entity_write_set.py`
- `src/memory_system/domain/services/core_search_text.py`
- `src/memory_system/domain/services/graph_write_plan_builder.py`
- `src/memory_system/domain/services/graph_write_service.py`
- `src/memory_system/infrastructure/neo4j/graph_write_repository.py`
- `src/memory_system/infrastructure/tei/tei_tokenize_client.py`
- `src/memory_system/infrastructure/tei/fake_tokenize_client.py`
- `src/memory_system/infrastructure/mongodb/context_archive_message_timestamp_repository.py`（只读；§5.2.1 LD-9）

生产（**禁止修改**，零 diff）：

- `extraction_pipeline_port.py`、`extraction_task_consumer_service.py`、`extraction_llm_service.py`、`extraction_worker.py`
- `entity_alignment_service.py`、`reconciliation_service.py`、`reconciliation_plan_builder.py`
- 全部 Migration、`pyproject.toml`、Settings 模型

测试（新建）：

- `tests/unit/test_referenced_entity_write_set.py`
- `tests/unit/test_core_search_text.py`
- `tests/unit/test_graph_write_plan_builder.py`
- `tests/unit/test_graph_write_service.py`
- `tests/contract/test_ext006_contract.py`
- `tests/integration/test_ext006_graph_write_neo4j.py`
- `tests/integration/test_ext006_graph_write_replay_mongo.py`

## 9. 测试计划

### 9.1 Unit — `test_referenced_entity_write_set.py`

| ID | 场景 | 期望 |
|---|---|---|
| E1 | 仅被 Memory 引用的实体进入 write set | 未引用候选排除 |
| E2 | user 实体引用 | `user:{user_id}` 保留 |
| E3 | object_entity_id null | 不引用 object 实体 |

### 9.2 Unit — `test_core_search_text.py`

| ID | 场景 | 期望 |
|---|---|---|
| T1 | 公式拼接顺序 | content → subject → predicate → object |
| T2 | user 实体省略 canonical | 不含 `current_user` |
| T3 | NFKC/空白规范化 | 确定性 |

### 9.3 Unit — `test_graph_write_plan_builder.py`

| ID | 场景 | 期望 |
|---|---|---|
| P1 | token_count ≤ 1024 | 计划可冻结 |
| P2 | token_count > 1024 | `memory_search_text_too_long` |
| P3 | index_sync_memory_set 覆盖新建+更新 | memory_id 全集 |

### 9.4 Unit — `test_graph_write_service.py`

| ID | 场景 | 期望 |
|---|---|---|
| S1 | CREATE 新 Memory + Evidence | 成功 outcome |
| S2 | MERGE 更新已有 Memory | 字段级 SET + version |
| S3 | SUPERSEDE 路径 | 新 active + old superseded + 关系 |
| S4 | CONFLICT 路径 | 双方 conflicted + 关系 |
| S5 | 全 Evidence 已存在 | `skipped_graph_write=true`；无写调用 |
| S6 | Replay 两次 | 第二次 SKIP；零重复 |
| S7 | 写失败注入 | `graph_write_failed` + `failed_stage=graph_write` |
| S8 | 跨用户隔离 | Cypher 含 `user_id`；不可写他户节点 |
| S9 | 无上游 LLM 重调 | Fake LLM 计数 0 |
| S10 | Privacy | caplog 无 content/实体名/Cypher 参数 |
| S11 | 前置失败 | 非 processing / 空 result → `abort_without_terminal` |
| S12 | 禁用码负向 | 无 `graph_query_failed`/`llm_*` 等 |
| S13 | Evidence source_time_* | 多消息 min/max；单消息 = candidate_source_time |
| S14 | LD-9 abort path | Archive 缺失或消息 ID 不可解析 → `abort_without_terminal`；零 graph write |

### 9.5 Contract — `test_ext006_contract.py`

| ID | 场景 | 期望 |
|---|---|---|
| C1 | 输入契约 | 消费三阶段成功输出 + 任务元数据 |
| C2 | 输出形状 | `GraphWriteOutcome` + `index_sync_memory_set`；`extra=forbid` |
| C3 | 错误码白名单 | 仅 `graph_write_failed`/`memory_search_text_too_long` |
| C4 | failed_stage | 恒 `graph_write` |
| C5 | 不持久化任务状态 | 无 Mongo status/offset 写 |
| C6 | 写 Cypher 授权 | 仅 MERGE/CREATE/SET 授权标签与关系 |
| C7 | 无 EXT-007+ 行为 | 无 ES/embedding/search_text alias |
| C8 | 上游零变更 | pipeline/worker/alignment/reconciliation 不变 |
| C9 | Migration/依赖零变更 | 无新 migration；`pyproject.toml` 不变 |

### 9.6 Integration — `test_ext006_graph_write_neo4j.py`

| ID | 场景 | 期望 |
|---|---|---|
| I1 | CREATE Memory + Evidence + Entity | 节点/关系完整 |
| I2 | UPDATE existing Memory | version++；Evidence 新增 |
| I3 | SUPERSEDE / CONFLICT | status 与关系正确 |
| I4 | Evidence replay idempotency | 第二次无新节点 |
| I5 | 事务回滚 | 注入写失败；节点数不变 |
| I6 | 跨用户隔离 | 用户 B 数据不可写 |
| I7 | entity_key MERGE 收敛 | replay 不重复 Entity |

### 9.7 Integration — `test_ext006_graph_write_replay_mongo.py`

| ID | 场景 | 期望 |
|---|---|---|
| M1 | 从 Mongo 加载元数据 + 注入计划 | 成功写入 |
| M2 | 任务文档零变更 | `status`/`extraction_result` 不变 |
| M3 | 保持 processing | 无 completed/offset |

### 9.8 E2E / 失败注入 / 并发

| 场景 | 结论 |
|---|---|
| Kafka 全链路 | 不适用；EXT-009 |
| ES 失败恢复 | 不适用；EXT-007 |
| 并发同 Archive | 不适用；Partition 串行 |

## 10. 验收标准（可客观验证）

- [ ] Plan Review Round 2 通过（Amendment 001）；`human_plan_approved=true` 后方可开发。
- [ ] 权威输入为持久化 `extraction_result` + `EntityAlignmentSuccess` + `ReconciliationSuccess`；不重调上游 LLM（S9）。
- [ ] `referenced_entity_write_set` 过滤正确（E1–E3）。
- [ ] `core_search_text` + TEI token gate（T1–T3/P1–P2）。
- [ ] 单原子 Neo4j 写事务；失败无部分状态（I5）。
- [ ] CREATE/UPDATE/SUPERSEDE/CONFLICT 路径正确（S1–S4/I1–I3）。
- [ ] Evidence/`entity_key`/`memory_id` 幂等（S5/S6/I4/I7）。
- [ ] `index_sync_memory_set` handoff 正确；任务保持 `processing`（M2/M3/C5）。
- [ ] 失败仅 `graph_write_failed`/`memory_search_text_too_long` + `failed_stage=graph_write`（S7/C3/C4）。
- [ ] 上游零 diff（C8/C9）；Privacy（S10）。
- [ ] scoped tests PASS；Ruff/Mypy PASS；Review 无 P0/P1。

## 11. Open Issues

### 11.1 OI-006（非阻塞）

`reconciliation_plan_conflict` 运维清理无 API Contract；`blocks_current_task: false`；`resolve_by_task: EXT-008`。

## 12. MVP 分类与决议记录

### 12.1 HARD_BLOCK

| 项 | 理由 |
|---|---|
| 单事务原子写入 | §2.1.13 + §2.1.15 #2 |
| Evidence/entity_key/memory_id 幂等 | §2.1.13 跨存储幂等 |
| 字段级 SET / Memory 所有权 | §2.1.9 |
| `memory_search_text_too_long` 写前门禁 | §2.1.13 #9 |
| 任务/Offset 不得提前完成 | §2.1.13 完成顺序 |
| 授权错误码白名单 | §2.1.15 |
| 对应测试 | 治理要求 |

### 12.2 DEFERRED_FOR_MVP

| 项 | 归属 |
|---|---|
| EXT-003→EXT-006 pipeline 接线 | Appendix B §B.10.4 |
| Elasticsearch / Embedding / `search_text` alias | EXT-007 |
| 任务 `completed` + Kafka Offset | EXT-007 |
| `memory_entity_alias_omitted_total` 指标发射 | 写入后指标；非阻塞 |
| `memory_search_text_omitted_alias_total` | EXT-007 |
| TEI 全量 `TEIEmbeddingClient` | DEV-006 superseded |
| OI-006 运维 API | EXT-008 |

### 12.3 MVP_LOCAL_DECISION

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | `graph_write_failed` 与 `memory_search_text_too_long` 均 → `failed_stage="graph_write"` | 规格示例仅授权 `graph_write`；二者均属图谱写入阶段 |
| LD-2 | 写事务内顺序：Entity → Memory → 关系 → Evidence | 满足外键式依赖；单事务仍原子 |
| LD-3 | TEI 不可用映射 `graph_write_failed`（非新码） | §2.1.15 优先既有码 |
| LD-4 | 最小 `TokenizeClient` 端口 + Fake | §2.1.13 #9 要求 TEI `/tokenize`；不引入 DEV-006 全量 |
| LD-5 | `server_time_provider` 可注入 | 测试确定性 |
| LD-6 | Mongo 只读加载置于 `graph_write_service.py` | 同 EXT-004 LD-4 / EXT-005 LD-7 |
| LD-7 | 全 Evidence 已处理 → `skipped_graph_write=true` 仍返回 `index_sync_memory_set` | §2.1.13 replay 索引重同步路径 |
| LD-8 | `index_sync_memory_set` 仅含本 Archive 写事务内 create/update 的 memory_id | SF-002 MVP 最小 handoff；跨 Archive alias 重同步 DEFERRED |
| LD-9 | Evidence `source_time_*` 经只读 `context_archive` 消息 timestamp 解析 | MF-001 闭合；不重跑预处理/LLM |

### 12.4 Amendment 001 — Round 1 Plan Remediation

| ID | 级别 | 修订 |
|---|---|---|
| MF-001 | MUST_FIX | §5.2.1 Evidence `source_time_start`/`source_time_end` 只读 Archive 解析契约 |
| SF-001 | SHOULD_FIX | §5.2 `existing_memory_update_plans[]` 字段应用表 |
| SF-002 | SHOULD_FIX | §5.3 step 9 + LD-8 alias 重同步边界 |
| SF-003 | SHOULD_FIX | §5.4 CREATE/UPDATE 时间字段显式化 |
| SF-004 | SHOULD_FIX | LD-5 Evidence 仅 `created_time` 不变 |

## 13. 风险与依赖结论

- **依赖**：`NONE`；`neo4j>=5.28,<6`、`httpx`、既有 Settings 已存在。
- **Migration**：`NONE`。
- **配置**：`NONE`；TEI base URL 复用既有 embedding service 配置路径（只读消费，不新增 Settings 字段）。
- **主要风险**：
  1. 误标 `completed`/提交 Offset → C5/M3。
  2. 部分写入未回滚 → I5。
  3. 占位 `entity_id` 绕过 `entity_key` → I7。
  4. content 泄漏 → S10。

## 14. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/EXT-006-neo4j-graph-transaction-write"
baseline_main: "59281d1e8d6e3fabfc0fe55f70b3fa50ac44bac2"
expected_commits:
  - "docs(plan): add EXT-006 neo4j graph transaction write plan"
  - "feat(ext): add neo4j graph transaction write"
  - "docs(status): record EXT-006 implementation commit and PR"
  - "docs(status): complete EXT-006 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "Elasticsearch / Embedding"
  - "pipeline continuation wiring"
  - "Migration / dependency / Settings"
```

## 15. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-12 18:10 UTC | planning | 创建 Task Plan；同步 progress/master_plan | — | baseline 59281d1 verified |
| 2026-08-12 10:48 UTC | implementation | 9 production + 7 test files per whitelist | scoped **41** passed（unit 23 + contract 9 + integration 9）；ruff/mypy PASS | single `execute_write` transaction；Evidence SKIP path；LD-9 archive timestamp；session_id from context_archive on load_from_persisted_task |
| 2026-08-12 11:05 UTC | code_review_remediation | P1: `graph_write_repository.py` entity_key MERGE → resolve authoritative `entity_id` for Memory props + SUBJECT/OBJECT; I7 extended; I3 SUPERSEDE/CONFLICT integration; S14b LD-9 unresolvable message ID | scoped **44** passed（unit 24 + contract 9 + integration 11）；ruff/mypy PASS | P1 convergence via MERGE RETURN + fallback resolve query; no plan_builder change |
| 2026-08-12 11:06 UTC | Release IMPLEMENTATION_RELEASE | implementation `b19e913af3848e932b8adb404dc5d5304167fb73`；PR #40 OPEN；feat push only | scoped 44 passed；ruff PASS；mypy PASS | `status=committed`；`next_action=WAITING_FOR_PR_MERGE` |
| 2026-08-12 12:15 UTC | Release POST_MERGE_CLEANUP | PR #40 MERGED `372e0232c1e5cfa1d71e2bb0152a22f59e60cd03`；governance completion on main；feat 分支已删 | — | `status=completed`；`next_action=EXT-007 planned / NOT AUTO-STARTED` |

## 16. 实际执行结果

### 最终状态

`completed` — POST_MERGE_CLEANUP complete；implementation `b19e913af3848e932b8adb404dc5d5304167fb73`；record `eafc07a3e01f376f4bd2c6c658c1dd5536c3b61f`；PR #40 MERGED (`https://github.com/xu-jia-ming/memory_system/pull/40` merge `372e0232c1e5cfa1d71e2bb0152a22f59e60cd03` mergedAt `2026-08-12T12:12:38Z`)；scoped 44 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2 non-blocking；zero upstream pipeline/consumer/alignment/reconciliation diff；no task completed/offset writes；OI-006 non-blocking；feat 分支已删；`next_action=EXT-007 planned / NOT AUTO-STARTED`；**不得触碰 DEV-006/PR#13**。

### Git 记录

```yaml
branch: "feat/EXT-006-neo4j-graph-transaction-write"
plan_commit: "66c547fcd1a4c529e95f776ec7165e08038e81cc"
implementation_commit: "b19e913af3848e932b8adb404dc5d5304167fb73"
implementation_commit_message: "feat(ext): add neo4j graph transaction write"
status_record_committed: "eafc07a3e01f376f4bd2c6c658c1dd5536c3b61f"
pr: "#40"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/40"
pr_state: MERGED
merge_commit: "372e0232c1e5cfa1d71e2bb0152a22f59e60cd03"
merged_at: "2026-08-12T12:12:38Z"
next_action: "EXT-007 planned / NOT AUTO-STARTED"
```

**验证命令**：
```bash
uv run pytest tests/unit/test_referenced_entity_write_set.py tests/unit/test_core_search_text.py tests/unit/test_graph_write_plan_builder.py tests/unit/test_graph_write_service.py tests/contract/test_ext006_contract.py tests/integration/test_ext006_graph_write_neo4j.py tests/integration/test_ext006_graph_write_replay_mongo.py -q
uv run ruff check src/memory_system/domain/models/graph_write.py src/memory_system/domain/ports/tokenize_client.py src/memory_system/domain/services/referenced_entity_write_set.py src/memory_system/domain/services/core_search_text.py src/memory_system/domain/services/graph_write_plan_builder.py src/memory_system/domain/services/graph_write_service.py src/memory_system/infrastructure/neo4j/graph_write_repository.py src/memory_system/infrastructure/tei/tei_tokenize_client.py src/memory_system/infrastructure/tei/fake_tokenize_client.py src/memory_system/infrastructure/mongodb/context_archive_message_timestamp_repository.py tests/unit/test_referenced_entity_write_set.py tests/unit/test_core_search_text.py tests/unit/test_graph_write_plan_builder.py tests/unit/test_graph_write_service.py tests/contract/test_ext006_contract.py
uv run mypy src/memory_system/domain/models/graph_write.py src/memory_system/domain/ports/tokenize_client.py src/memory_system/domain/services/referenced_entity_write_set.py src/memory_system/domain/services/core_search_text.py src/memory_system/domain/services/graph_write_plan_builder.py src/memory_system/domain/services/graph_write_service.py src/memory_system/infrastructure/neo4j/graph_write_repository.py src/memory_system/infrastructure/tei/tei_tokenize_client.py src/memory_system/infrastructure/tei/fake_tokenize_client.py src/memory_system/infrastructure/mongodb/context_archive_message_timestamp_repository.py
```

**结果**：44 passed；ruff PASS；mypy PASS（10 production files）。
