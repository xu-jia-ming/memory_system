# EXT-004 Entity Alignment + Neo4j 模型基础

## 1. 任务信息

```yaml
task_id: EXT-004
task_name: Entity Alignment + Neo4j 模型基础
status: committed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "8330d42a9f2fe9365e180bdd68c6c9dc7add6e48"
branch: "feat/EXT-004-entity-alignment-neo4j-model-basis"
created_at: "2026-08-12 06:20 UTC"
updated_at: "2026-08-12 15:35 UTC"
spec_sections:
  - "§1.2.1 记忆萃取整体流程（Align Entities with Existing Graph 位置）"
  - "§2.1.3 Memory Extraction Task（任务表不保存 Memory/Entity 结果 ID 数组）"
  - "§2.1.4 Kafka 消费与任务幂等（仅复用既有边界；processing + 非空 extraction_result 复用）"
  - "§2.1.6 LLM Structured Extraction（仅消费既有候选实体字段与 alias 预处理规则）"
  - "§2.1.7 抽取结果校验与标准化（持久化 extraction_result 作为权威输入）"
  - "§2.1.9 Neo4j 记忆图谱数据模型（Entity 节点、entity_key、约束与索引；本任务权威范围）"
  - "§2.1.10 实体对齐与别名合并（本任务权威范围）"
  - "§2.1.11 记忆候选召回与新旧记忆处理（**非本任务**；仅记录对齐输出的下游消费者）"
  - "§2.1.13 图谱写入事务与幂等（事务前准备第 2 步；写入禁令）"
  - "§2.1.15 失败处理（授权错误码词表）"
  - "§2.1.16 MVP 实现边界"
  - "§3.6 全异步客户端（neo4j AsyncDriver）"
  - "§3.24 连接池、超时与重试（Neo4j 既有固定值；禁止通用 Retry Decorator）"
  - "§3.26 Schema Migration（已执行 Migration 不得修改）"
  - "§3.27 日志、指标与敏感信息保护"
  - "§3.28 测试策略"
  - "Appendix A Amendment EXT-002-004（终态/Offset 门禁；abort_without_terminal 语义）"
  - "Appendix B Amendment EXT-003（§B.1 durable 字段、§B.2/§B.10 终态与 replay、§B.11 privacy）"
prerequisites:
  formal:
    - "EXT-003 — SATISFIED/completed; PR #37 MERGED merge 0eb45e20c64777a03dc770be70cba2316b47fdf6; persisted extraction_result + candidate_fingerprint + candidate_source_time available for replay"
    - "DEV-004 — SATISFIED/completed; §2.1.9 Neo4j constraints/indexes created by scripts/migrations/002_initial_neo4j.py and asserted by tests/integration/test_migrate_infra.py"
    - "EXT-001 — SATISFIED/completed; task idempotency, PipelineTerminalDecision, terminal-persistence-before-offset gate"
    - "EXT-002 — SATISFIED/completed; ExtractionReadyArchive boundary (not re-consumed by EXT-004)"
  implementation_reuse:
    - "Existing ExtractionValidatedResult / ExtractionEntityCandidate / ExtractionMemoryCandidate typed models (domain/models/extraction_llm.py)"
    - "Existing read-only extraction task repository lookup (infrastructure/mongodb/extraction_task_repository.find_extraction_task_by_archive_id)"
    - "Existing neo4j AsyncDriver in AppState (infrastructure/runtime.py) and Neo4jSettings fixed timeouts"
    - "Existing §2.1.9 constraints/indexes from migration 002 (read-only reliance; no new migration)"
    - "Existing memory_extraction settings (max_entity_candidates_per_archive=100, max_stored_entity_alias_count=50)"
  baseline_evidence:
    branch: "main"
    head: "8330d42a9f2fe9365e180bdd68c6c9dc7add6e48"
    working_tree_at_planning_start: "clean before planning whitelist writes"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=8330d42a9f2fe9365e180bdd68c6c9dc7add6e48"
approval_gates:
  planning: "PLAN_APPROVED_PENDING_HUMAN"
  approval_posture: "PLAN_REVIEW_APPROVED Round 2 — BLOCKER=0 MUST_FIX=0 SHOULD_FIX=1; await human PLAN_APPROVED; Developer NOT authorized"
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: true
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create the exact feature branch"
  IMPLEMENTATION_RELEASE: "only after all blocking Open Issues are resolved and implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
dependency_changes_expected: NONE
```

### 1.1 本轮门禁与停止条件

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现、测试实现、Migration、配置或依赖"
  - "进入 Developer、Code Reviewer、Commit Recorder 或 Release Operator"
  - "执行任何 Git 写命令"
  - "修改权威规格正文（本轮不追加 Appendix；如需修订须由 owner 决议后单独落盘）"
stop_if:
  - "任何实现步骤需要新增错误码、新增 **未在 Task Plan 授权的** failed_stage 字面量、新增 durable 字段或改变既有 Schema"
  - "任何实现步骤需要写入 Neo4j（创建/更新 Entity、Memory、Evidence 或任何关系）"
  - "任何实现步骤需要改变 EXT-001 Kafka/offset/task 状态机、EXT-002 预处理/脱敏或 EXT-003 LLM/持久化语义"
  - "任何实现步骤需要调用 LLM"
blocking_open_issues: []
nonblocking_open_issues:
  - OI-EXT-004-001
  - OI-EXT-004-002
  - OI-EXT-004-003
  - OI-EXT-004-004
```

## 2. 任务目标

在 EXT-003 已持久化 `memory_extraction_task.extraction_result` 之后，提供 §2.1.10 规定的**纯确定性实体对齐**能力，并落地 §2.1.9 中实体对齐实际需要的 Neo4j 数据模型基础；产出 `local_entity_id -> entity_id` 对齐映射与**计划态**（未写入）实体创建/别名合并记录，供后续 EXT-005 Reconciliation 与 EXT-006 图谱写事务消费。

可验证目标：

1. **权威输入**：以已持久化的 `extraction_result` 为唯一抽取输入。当任务处于 `processing` 且 `extraction_result != null` 时，**不得**再次调用 LLM、不得重新读取 `context_archive`、不得重算 `candidate_fingerprint` 或 `candidate_source_time`。
2. **对齐范围**：对 `extraction_result.entities[]` 中**全部**候选实体建立对齐映射（§2.1.10 允许对齐阶段查询全部候选实体）；当任一 memory 以 `subject_entity_id` 或 `object_entity_id` 引用保留值 `user` 时，额外产出用户实体映射 `entity_id = "user:" + user_id`。
3. **确定性匹配**：严格按 §2.1.10 第 1–6 步顺序执行；MVP **仅**实现确定性匹配，**不**调用 LLM、**不**使用模糊相似度、全文检索或向量相似度。
4. **模型基础**：实现 §2.1.9 中对齐实际使用的 Entity 节点读取模型、property 名称常量、`entity_key = SHA256(user_id + ":" + entity_type + ":" + normalized_name)` 与确定性用户实体 ID / 固定字段集合。
5. **只读图谱访问**：实体对齐阶段只执行只读 Cypher 查询；**不得**创建或更新任何 Entity（§2.1.13 事务前准备第 2 步「此阶段不得立即创建新 Entity」），不得写入任何节点、关系或别名。
6. **别名合并计划**：按 §2.1.6 / §2.1.10 计算**计划态**别名合并（候选 alias NFKC/去空白/去重/排序；保留既有 alias 与 `canonical_name`；合计上限 `max_stored_entity_alias_count=50`；超限记录被忽略数量），仅作为输出，不写入、不发指标。
7. **用户隔离**：所有查询与匹配严格限定在单一 `user_id` 内；MVP 不做跨用户全局实体合并。
8. **失败与幂等**：实体对齐执行失败仅映射到 §2.1.15 既有 `entity_alignment_failed`；对齐输出不持久化，任何 replay 以相同持久化输入与相同图谱状态得到相同匹配判定。
9. **不改变上游语义**：`PipelineTerminalDecision`、`extraction_pipeline_port.py`、`extraction_task_consumer_service.py`、`extraction_worker.py` 与 `ExtractionLlmService.run` 的既有行为**逐字不变**。

## 3. 非目标与黑名单

- **任何 Neo4j 写入**：创建/更新 Entity、Memory、Evidence 节点，`SUBJECT`/`OBJECT`/`SUPPORTS`/`SUPERSEDES`/`CONFLICTS_WITH` 关系，别名落盘，`MERGE`、写事务（§2.1.13 事务内写入 = EXT-006）。
- **§2.1.11 记忆候选召回与 Reconciliation**：已有 Memory 召回查询、`ORDER BY`/`LIMIT 20`、LLM Reconciliation、`CREATE`/`MERGE`/`SUPERSEDE`/`CONFLICT`/`SKIP`、`reason_code`、`merged_content`、`aligned_memory_key`、候选聚合与 `reconciliation_plan_conflict`（全部属 EXT-005）。
- **§2.1.12 置信度与重要性初始化**、`increment_memory_version`、`referenced_entity_write_set`、`memory_id` 生成、Evidence/`evidence_id` 生产写入（属 EXT-005/EXT-006）。
- **Retrieval 索引**：`core_search_text`、`planned_index_sync_memory_set`、TEI `/tokenize`、`memory_search_text_too_long`、Elasticsearch、Embedding（属 EXT-006/EXT-007）。
- **EXT-005+ 一切行为**；EXT-008 管理接口；EXT-009 E2E。
- **改变 EXT-003 语义**：不修改 LLM 调用、校验、duplicate normalization、fingerprint、`candidate_source_time`、`extraction_result` 持久化边界或 `ExtractionLlmService.run` 的终态返回；非空结果继续保持 `processing` 且不提交 Offset。
- **EXT-003→EXT-004 生产编排**：Appendix B §B.10.4 明确 continuation 编排 `DEFERRED_FOR_MVP`；本任务交付可注入的库级服务，**不**接线到生产 pipeline，**不**修改 `PipelineTerminalDecision`，worker `main()` 保持 refusal-only。
- **EXT-001/EXT-002 语义**：Kafka topic/group/partition/offset、六字段事件、任务状态机、终态持久化顺序、raw 校验、normalization、redaction、first-person（仍 deferred）。
- **Schema/Migration/依赖/配置**：不新增或修改 Migration（§3.26 + 治理：不得修改已执行 Migration）、`pyproject.toml`、`uv.lock`、`configs/**`、`settings/models.py`、`settings/validators.py`。
- **新错误码、未在 Task Plan 授权的 `failed_stage` 字面量、新 durable 字段、新 Collection、新 API/HTTP route、第二套 Settings**（`entity_alignment` 已由 LD-9 授权）。
- **DEV-006、PR #13**，以及任何 TEI / SiliconFlow / 无关 runtime 工作。
- 原始消息内容、pre-redaction content、secret、完整 prompt/response、真实用户数据的日志、fixture、异常与提交。

## 4. 当前代码状态与前置检查

### 4.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `8330d42a9f2fe9365e180bdd68c6c9dc7add6e48`（与用户给定 `baseline_main` 一致） |
| `git status --short` | 空（规划开始前工作树干净；本轮仅允许规划白名单变更） |
| `git log --oneline -10` | `8330d42` docs(status): backfill EXT-003 …；`0eb45e2` Merge PR #37；`7c6309e` feat(ext): add llm extraction and candidate fingerprint |
| EXT-003 | `completed`；PR #37 MERGED；`formal_EXT-003_release_gate=COMPLETED` |
| DEV-004 | `completed`；migration `002_initial_neo4j.py` 含 §2.1.9 全部 4 约束 + 2 索引（名称逐字一致） |
| workflow | `NORMAL`，explicit |

### 4.2 人工给定前置的仓库验证

| 人工给定前置 | 验证结果 | 证据 |
|---|---|---|
| EXT-003 = completed | **确认** | `progress.md` `formal_EXT-003_status: completed`；merge `0eb45e2` |
| 持久化 `extraction_result` 可用于 replay | **确认** | `extraction_task_repository.set_extraction_result`；`MemoryExtractionTask.extraction_result: dict \| None` |
| `candidate_fingerprint` 可用 | **确认** | `ExtractionMemoryCandidate.candidate_fingerprint`；`AUTHORIZED_MEMORY_FIELDS` 含该字段 |
| `candidate_source_time` 可用 | **确认** | `ExtractionMemoryCandidate.candidate_source_time`（应用层派生，int） |
| EXT-003 非空结果留在 `processing`，Offset 未提交 | **确认** | `ExtractionLlmService.run` 非空结果返回 `abort_without_terminal`；consumer 对 `ABORT_WITHOUT_TERMINAL` 返回 `should_commit_offset=False` |
| `PipelineTerminalDecision` / `extraction_worker` 未被 EXT-003 改动 | **确认** | `extraction_pipeline_port.py` 仅 complete/fail/abort；`extraction_worker.main()` 仍 refusal-only（exit 1） |
| 前置结论 | **SATISFIED**（形式前置全部满足）；但实现仍被 2 项 blocking Open Issue 阻塞 | §12.1 |

### 4.3 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| `src/memory_system/infrastructure/neo4j/__init__.py` 为**空**；仓库无任何 Neo4j repository、Cypher 业务查询或图谱领域模型 | 文件为空；`rg -n "neo4j"` 仅命中 `runtime.py`（driver 生命周期/健康检查）与 `settings` |
| Neo4j `AsyncDriver` 已在 `AppState` 中创建并在 readiness 中使用 | `runtime.py` L73–78、L109–110、L161–163 |
| `Neo4jSettings` 已固定 §3.24 值（connection 5s / acquisition 10s / pool 50） | `settings/models.py` L248–252 |
| `neo4j>=5.28,<6` 已在 `pyproject.toml` `dependencies` | `pyproject.toml` |
| §2.1.9 约束/索引已由 DEV-004 创建，名称与规格逐字一致 | `scripts/migrations/002_initial_neo4j.py` L12–68 |
| 该约束/索引存在性已有集成断言，无需重复实现 | `tests/integration/test_migrate_infra.py` L33、L339–356 |
| 无 `memory_entity_alias_omitted_total` 指标 | `observability/metrics.py` 仅 8 个既有指标 |
| `max_stored_entity_alias_count=50`、`max_entity_candidates_per_archive=100`、`max_entity_alias_count_per_candidate=32`、`max_entity_alias_characters=128` 已存在 | `settings/models.py` L60–69 |
| 既有 SHA-256 约定为 UTF-8 编码 + 小写 hexdigest | `extraction_fingerprint.py` L72–73 |
| 既有确定性 normalization 约定（NFKC + 空白压缩 + strip） | `extraction_archive_preprocessing_service.normalize_content` L66–72 |

**结论**：EXT-004 需要**新建** Neo4j 只读查询层与实体对齐领域层；不需要任何 Migration、依赖、配置或 Settings 变更。

### 4.4 §2.1.10 Neo4j 模型基础是否需要 Schema/Constraint/Migration 产物

**明确回答：不需要新增任何 Schema/Constraint/Migration 产物。**

1. §2.1.9 要求的 4 个约束（`entity_id_unique`、`entity_key_unique`、`memory_id_unique`、`evidence_id_unique`）与 2 个索引（`memory_user_type_status`、`memory_subject_predicate`）**已由 DEV-004 的 `scripts/migrations/002_initial_neo4j.py` 逐字创建**，且已有集成测试断言其存在。
2. EXT-004 的对齐查询只依赖 `entity_key_unique`（精确匹配走唯一约束索引）与 `Entity.user_id`/`Entity.entity_type`/`Entity.canonical_name`/`Entity.aliases` property 读取；规格未为后者定义额外索引，**不得**自行新增索引。
3. 因此 EXT-004 的「Neo4j 模型基础」= **应用层模型/常量/键计算 + 只读查询**，而非数据库 Schema 产物。
4. 治理与 §3.26 明确禁止修改已执行 Migration；本任务**不得**新建 `005_*` 迁移、不得改 `002_initial_neo4j.py`、不得在运行时执行 DDL。

## 5. Exact Contract 闭合

### 5.1 输入契约（权威输入 = 已持久化 extraction_result）

```text
EntityAlignmentInput {
  task_id: str                       # 仅用于日志 metadata
  archive_id: str                    # 仅用于日志 metadata / 任务定位
  user_id: str                       # 唯一对齐作用域（来自任务文档）
  entities: [ExtractionEntityCandidate]     # 来自持久化 extraction_result.entities（provider 顺序）
  referenced_local_entity_ids: set[str]     # 由 memories[].subject_entity_id / object_entity_id 收集（含保留值 "user"）
}
```

硬性规则：

- 输入只能来自**已持久化**的 `memory_extraction_task.extraction_result`（read-only 读取既有 `find_extraction_task_by_archive_id`，再用既有 `ExtractionValidatedResult` 严格 re-hydrate），或由调用方直接传入同一 typed 结果。
- **禁止**调用 LLM（服务构造与方法签名中**不出现**任何 LLM client 类型；模块不 import `infrastructure.llm.*`）。
- **禁止**重新读取 `context_archive`、重新执行 EXT-002 normalization/redaction、重算 `candidate_fingerprint` / `candidate_source_time`。
- 对齐**只**消费 `entities[]` 的 `local_entity_id` / `name` / `type` / `aliases`，以及 `memories[]` 的 `subject_entity_id` / `object_entity_id` 引用；**不**消费 `content`、`predicate`、`object_value`、事件字段、`confidence`、`source_message_ids`、`candidate_source_time`、`candidate_fingerprint`。
- `user_id` 只取任务文档的 `user_id`（已由 EXT-001/EXT-002 校验归属）；**不**接受调用方另行传入的第二个用户来源，**不**跨用户查询。
- 若持久化结果无法用授权 typed 模型 re-hydrate（不应发生；EXT-003 只写授权字段）：视为**不可预期内部失败** → 不产生终态、不产生 `last_error`、不提交 Offset（沿用 Appendix A.1 #4 / B.6 `abort_without_terminal` 语义）；**不得**新造错误码，**不得**降级为部分对齐。

### 5.2 §2.1.10 确定性对齐算法（逐步固定）

**处理顺序（全局）**：

1. 收集 `referenced_local_entity_ids`（来自 `memories[].subject_entity_id` / `object_entity_id`，含保留值 `"user"`）。
2. 若 `"user" ∈ referenced_local_entity_ids` 或 `entities[]` 中存在 `local_entity_id="user"`：先执行 **S1 保留用户实体对齐**（见 §5.2.1）；该条目**永不**进入 S2–S5。
3. 对其余 `entities[]` 元素（`local_entity_id != "user"`）按 **provider 原顺序**逐条执行 S2–S5。
4. **同批次 `entity_key` 分组（计划创建）**：所有进入 S5 `planned_create` 的候选，在分配 `entity_id` 前按 `entity_key` 分组；同一 `entity_key` 在单次对齐运行中**只 mint 一个** `planned entity_id`；该组内全部 `local_entity_id` 映射到同一 `entity_id`（§5.4.1）。
5. 输出顺序：保留 `user` 条目置首；其余按 `entities[]` provider 原顺序（LD-2）。

对每个**非保留**候选实体，按顺序执行；S3/S4 命中即停止并进入别名合并计划（§5.5）：

| 步 | 规格依据 | 行为 | 状态 |
|---|---|---|---|
| S0 | §2.1.10.6 | 全流程限定 `user_id`；任何查询必须显式带 `user_id` 谓词 | 固定 |
| S1 | §2.1.10.1 | **仅**保留值 `local_entity_id="user"` 或 `referenced_local_entity_ids` 触发的用户实体条目：直接映射 `entity_id = "user:" + user_id`；**不**执行 S2–S5；**不**做 `entity_key`/名称/别名对齐查询（Q2/Q3 跳过）；见 §5.2.1 | 固定 |
| S2 | §2.1.10.2 | 候选 `name` → `normalized_name`：Unicode NFKC → 转小写 → 连续空白压缩 → 去首尾空白 | 固定（micro-semantics 见 OI-EXT-004-003 / LD-3） |
| S3 | §2.1.10.3 + §2.1.9 | 由 `user_id + entity_type + normalized_name` 计算 `entity_key`，执行**精确匹配**（`entity_key_unique` 唯一约束，至多一条） | 固定 |
| S4 | §2.1.10.4 | 若 S3 未匹配，执行次级精确匹配（§5.2.2）；命中则 `match_kind=canonical_or_alias_exact` | 固定（OI-EXT-004-001 → MVP_LOCAL_DECISION LD-7/LD-8） |
| S5 | §2.1.10.5 | 若仍未匹配，产出**计划态创建**记录；禁止模糊相似度强制合并；`entity_id` 经 §5.4.1 同批次 `entity_key` 分组复用 | 固定 |
| S6 | §2.1.10 末段 | 计划态别名合并（§5.5）；`canonical_name` 不自动替换 | 固定（OI-EXT-004-004 记录） |

#### 5.2.1 保留值 `local_entity_id="user"`（权威规则）

**触发条件**（满足任一即产出用户实体对齐条目）：

- `entities[]` 中存在 `local_entity_id == "user"`；或
- `referenced_local_entity_ids` 包含 `"user"`（即使 `entities[]` 未列出该 local ID）。

**行为（逐字固定）**：

1. **不**对保留 `"user"` 执行 S2（`normalized_name`）、S3（`entity_key` 查询）、S4（次级匹配）、S5（普通计划创建）。
2. 确定性映射 `entity_id = "user:" + user_id`（§2.1.9 / §2.1.10.1）。
3. 仅执行 Q1 只读存在性检查；命中 → `match_kind=reserved_user_existing`；未命中 → `match_kind=reserved_user_planned_create` 且固定字段见 §5.4（**不** mint 第二个用户实体 ID）。
4. `planned_alias_merge`：命中时 `planned_aliases = existing_aliases`；计划创建时 `planned_aliases = []`；**不**合并候选 aliases（§2.1.10.1「用户实体不参与普通名称和别名对齐」）。
5. `memories[]` 中 `subject_entity_id` / `object_entity_id == "user"` 通过对齐输出中的 `local_entity_id="user"` 条目解析到同一 `entity_id`；**不得**为 `"user"` 再计划一条普通 Entity。
6. 若 `entities[]` 同时含 `local_entity_id="user"` 与其它候选：用户条目仅走本小节；其它候选**不得**因名称归一化为 `current_user` 等而绕过 S1（普通候选仍走 S2–S5；若其 `entity_key` 与用户实体 `entity_key` 相同，S3 命中用户实体节点属图谱数据异常 → `entity_alignment_failed`，见 §5.6）。

#### 5.2.2 S4 次级精确匹配契约（§2.1.10 第 4 步；OI-EXT-004-001 闭合）

**目的**：在 S3 `entity_key` 未命中时，查找当前用户、相同 `entity_type` 下名称或别名**完全相同**的既有 Entity。

| 维度 | 规则 |
|---|---|
| **候选操作数** | 仅候选 S2 产出的 `normalized_name`；候选 `aliases[]` **不参与** S4 身份查找（aliases 仅用于 §5.5 计划合并） |
| **既有操作数** | 同 `user_id`、同 `entity_type` 的 Entity 节点之 `normalized_name` 字段；以及其 `aliases[]` 各元素经 `normalize_entity_alias()` 后的值 |
| **命中条件** | `existing.normalized_name == candidate.normalized_name` **或** `candidate.normalized_name == normalize_entity_alias(alias)` 对任一 `alias ∈ existing.aliases` |
| **`normalize_entity_alias`** | NFKC → 连续 Unicode 空白压缩为单个 `U+0020` → 去首尾空白；**不**转小写（§2.1.6 alias 预处理，与 `normalized_name` 区分） |
| **`user_id` 过滤** | 所有 Q3 查询与内存过滤必须 `e.user_id = $user_id`；禁止跨用户命中 |
| **`entity_type` 兼容** | `existing.entity_type` 必须等于候选 `type`（LLM `type` → 图谱 `entity_type`）；不做跨类型匹配 |
| **零命中** | 进入 S5 `planned_create` |
| **单命中** | `match_kind=canonical_or_alias_exact`；绑定该 `entity_id` |
| **多命中** | **MVP_LOCAL_DECISION LD-8**：在全部命中实体中按 `entity_id` **字典序升序**取第一条；`match_kind=canonical_or_alias_exact`；**不** fail-closed，**不**新造歧义错误码；不阻塞 EXT-005 reconciliation 语义 |
| **禁止** | 模糊/embedding/LLM 匹配；候选 aliases 作为 S4 查找键；静默无排序取首条（必须 `entity_id ASC`） |

**Q3 批量形状（contract 约束，最终实现逐字受测）**：

```cypher
UNWIND $candidates AS c
MATCH (e:Entity)
WHERE e.user_id = $user_id
  AND e.entity_type = c.entity_type
  AND (
    e.normalized_name = c.normalized_name
    OR c.normalized_name IN coalesce(e.aliases, [])
  )
RETURN c.local_entity_id AS local_entity_id,
       e.entity_id AS entity_id,
       e.entity_key AS entity_key,
       e.user_id AS user_id,
       e.entity_type AS entity_type,
       e.canonical_name AS canonical_name,
       e.normalized_name AS normalized_name,
       e.aliases AS aliases
ORDER BY c.local_entity_id ASC, e.entity_id ASC
```

> 服务层在比较前对 `e.aliases[]` 各元素执行 `normalize_entity_alias()` 再与 `c.normalized_name` 比较；亦可将规范化后的 alias 集与 `e.normalized_name` 一并参与命中判定（§5.2.2 表）。若同一 `local_entity_id` 对应多行，取 **`entity_id` 字典序最小** 的一条（LD-8）。

`entity_key` 计算逐字固定为：

```text
entity_key = lowercase_hex( SHA256( utf8( user_id + ":" + entity_type + ":" + normalized_name ) ) )
```

其中 `entity_type` = LLM 候选的 `type`（§2.1.9：`name`/`type` 映射为 `canonical_name`/`entity_type`）。SHA-256 表示沿用仓库既有约定（UTF-8 编码 + 小写 hexdigest，与 `extraction_fingerprint.py` 一致）。

**S2 归一化逐字固定**（顺序不可调换）：

1. `unicodedata.normalize("NFKC", name)`；
2. `str.lower()`（规格「转小写」；**不**使用 `casefold()`）；
3. 将每一段连续 Unicode 空白替换为单个 `U+0020`；
4. 去除首尾空白。

不得追加 case folding 之外的大小写规则、locale 排序、标点剥离、同义词映射、数字归一或任何规格未写明的 canonicalization。

### 5.3 只读图谱查询契约

所有查询：只读、批量化、显式 `user_id` 过滤、确定性排序、不写入。

| ID | 用途 | Cypher 形状（最终实现须逐字受 contract test 约束） |
|---|---|---|
| Q1 | S1 用户实体存在性 | `MATCH (e:Entity {entity_id: $user_entity_id}) WHERE e.user_id = $user_id RETURN e.entity_id, e.entity_key, e.user_id, e.entity_type, e.canonical_name, e.normalized_name, e.aliases` |
| Q2 | S3 `entity_key` 精确匹配（批量） | `UNWIND $entity_keys AS k MATCH (e:Entity {entity_key: k}) WHERE e.user_id = $user_id RETURN e.entity_id, e.entity_key, …, e.aliases` |
| Q3 | S4 次级精确匹配（批量） | §5.2.2；`UNWIND` 候选列表；显式 `user_id` + `entity_type`；应用层按 `entity_id ASC` 多命中择一（LD-8） |

约束：

- 使用既有 `AsyncDriver` 的**读事务**（`session.execute_read` 或等价只读 API）；不得开启写事务，不得执行 `CREATE`/`MERGE`/`SET`/`DELETE`/`REMOVE`/DDL。
- 不新增 Neo4j 配置或超时字段；沿用 §3.24 既有 `Neo4jSettings` 固定值。
- §3.24 #1：不得引入通用 Retry Decorator；EXT-004 不实现应用层重试（只读查询本身幂等，如需重试由驱动 managed read transaction 负责）。
- 单个 Archive 候选实体上限 100（`max_entity_candidates_per_archive`），Q2/Q3 必须批量执行（`UNWIND`），不得 per-candidate 串行往返。
- 返回值必须映射为严格 typed 快照（`extra="forbid"`）；缺失/类型非法的 property 视为图谱数据异常 → 按 §5.6 失败处理，不得 coercion、不得填默认值。
- 查询**不得**返回或读取 Memory/Evidence 节点、关系或任何非 Entity 数据。

### 5.4 对齐输出契约（形状、归属、位置、是否持久化）

**归属**：新建领域模型 `src/memory_system/domain/models/entity_alignment.py`；由新建领域服务 `entity_alignment_service.py` 产出。

**位置与持久化**：**不持久化**。对齐输出是**进程内瞬态**值对象，作为方法返回值交给下游（EXT-005/EXT-006）。依据：

1. §2.1.3 明确「任务表不保存 Memory、Entity 结果 ID 数组」；
2. Appendix B §B.1 固定 `extraction_result` 只允许授权字段，新增对齐字段属未授权 Schema 变更；
3. §2.1.13 事务前准备第 2 步只要求「先建立 `local_entity_id -> entity_id` 对齐映射」，未授权任何持久化位置。

因此**禁止**：新增 Mongo 字段/Collection、写入 Neo4j、写入 Redis/ES 缓存、写文件。

```text
EntityAlignmentOutcome {
  outcome: "success" | "failure"
  success: EntityAlignmentSuccess | null
  failure: EntityAlignmentFailure | null
}

EntityAlignmentSuccess {
  user_id: str
  alignments: [AlignedEntity]        # 确定性顺序：存在保留 user 条目时置于首位，其后为 entities[] provider 原顺序
  # 派生只读访问：local_entity_id -> entity_id 映射（§2.1.13 第 2 步要求的映射）
}

AlignedEntity {
  local_entity_id: str               # 候选 local ID，或保留值 "user"
  entity_id: str                     # 最终数据库 entity_id（既有节点的 ID，或计划态新实体 ID）
  match_kind: EntityMatchKind
  entity_type: str                   # 候选 type（= 图谱 entity_type）；命中既有节点时必须与其 entity_type 相同
  canonical_name: str                # 命中既有节点 → 既有 canonical_name（保留，不替换）；计划创建 → 候选 name
  normalized_name: str               # S2 结果；计划创建时写入新节点；命中时为既有节点值
  entity_key: str                    # 命中 → 既有节点 entity_key；计划创建 → S3 计算值
  planned_alias_merge: PlannedEntityAliasMerge
  existing_entity: EntityNodeSnapshot | null   # 命中既有节点时的只读快照，否则 null
  planned_create: bool               # 与 existing_entity 互斥
}

EntityMatchKind =
  | "reserved_user_existing"          # S1 命中既有用户实体
  | "reserved_user_planned_create"    # S1 未命中 → 计划创建固定字段用户实体
  | "entity_key_exact"                # S3 命中
  | "canonical_or_alias_exact"        # S4 命中（§5.2.2）
  | "planned_create"                  # S5 计划创建

PlannedEntityAliasMerge {
  normalized_candidate_aliases: [str]    # NFKC/去空白/去重/排序后的候选 aliases
  existing_aliases: [str]                # 既有节点 aliases 原顺序（计划创建时为 []）
  planned_aliases: [str]                 # 合并后计划别名列表（≤ max_stored_entity_alias_count）
  omitted_alias_count: int               # 因 50 上限被忽略的新 alias 数量（仅输出，不发指标）
  canonical_name_replaced: false         # MVP 恒为 false（§5.5）
}

EntityAlignmentFailure {
  error_code: "entity_alignment_failed"   # §2.1.15 既有码；EXT-004 唯一授权终态码
  failed_stage: "entity_alignment"        # MVP_LOCAL_DECISION OI-EXT-004-002 / LD-9
  # 无 message 内容泄露：message 只允许非内容型描述
}

EntityNodeSnapshot {                      # §2.1.9 Entity 只读快照（对齐所需字段）
  entity_id: str
  user_id: str
  entity_key: str
  entity_type: str
  canonical_name: str
  normalized_name: str
  aliases: [str]
}
```

**用户实体计划创建固定字段**（§2.1.10.1 逐字）：

```text
entity_id       = "user:" + user_id
user_id         = user_id
entity_key      = SHA256(user_id + ":" + "person" + ":" + "current_user")   # 按 §5.2 公式
entity_type     = "person"
canonical_name  = "current_user"
normalized_name = "current_user"
aliases         = []
```

`created_time` / `updated_time` 由图谱写事务的服务器时间写入（§2.1.9），**不由 EXT-004 生成**；计划态记录不含这两个字段（避免伪造服务器时间）。

#### 5.4.1 同批次 `entity_key` 碰撞与计划态 `entity_id` 边界（LD-1 / Round 2 MF-1）

**同批次分组规则**（S5 `planned_create`）：

1. 维护 `planned_entity_id_by_entity_key: dict[str, str]`（仅本次对齐运行、进程内瞬态）。
2. 按 `entities[]` **provider 原顺序**处理；当某候选进入 S5 且尚无既有节点：
   - 若其 `entity_key` **不在** map：调用 `entity_id_factory()` **一次**，存入 map；
   - 若其 `entity_key` **已在** map：**复用**已有 `planned entity_id`，**不得** mint 第二个 ID。
3. 两个 EXT-003 候选在同批次解析到相同 `entity_key` 且无既有匹配时，**只产生一个** `planned entity_id`；全部对应 `local_entity_id` 映射到该 ID。
4. 确定性：map 写入顺序由 provider 顺序决定；replay 在相同输入与图谱状态下产生相同分组与相同匹配判定；`entity_id_factory` 默认 UUID v4，测试注入固定序列。

**计划态 `entity_id` 边界（LD-1 澄清）**：

| 断言 | 说明 |
|---|---|
| 瞬态占位 | UUID v4 `planned entity_id` **仅**为对齐输出占位身份；EXT-004 **不**执行任何 Entity 节点写入 |
| 未来写入 | EXT-006 必须以 `entity_key` 唯一性 / `MERGE` 语义落盘；不得以占位 `entity_id` 绕过 `entity_key` 去重 |
| 同键单身份 | 同批次相同 `entity_key` **禁止**两个不同占位 `entity_id` |
| Replay 收敛 | 图谱未写入时 replay 复用相同分组；图谱已写入后 replay 经 S3 `entity_key` 命中既有节点 |
| 非持久化 | 占位 `entity_id` 不写入 Mongo / Neo4j / Redis / ES |

**新实体 `entity_id` 生成（MVP_LOCAL_DECISION LD-1）**：`planned_create` 使用可注入 `entity_id_factory`（默认 UUID v4）。理由：§2.1.13 第 2 步与 §2.1.11 B.1 要求事务前完整 `local_entity_id -> entity_id` 映射；**匹配判定完全确定**；未写入前 ID 为占位，replay 通过 `entity_key` 收敛。

### 5.5 别名合并计划契约（§2.1.6 + §2.1.10）

- 候选 aliases 预处理：NFKC → 去空白 → 去重 → 排序（§2.1.6「Entity 对齐时，候选 aliases 先执行 NFKC、去空白、去重并排序」）；具体空白语义见 OI-EXT-004-003 的固定读法（NFKC → 连续空白压缩为单空格 → 去首尾空白 → 精确去重 → 按 code point 字典序排序）。
- 合并规则（§2.1.6 + §2.1.10）：优先保留既有合法 aliases（保持既有顺序），再按排序顺序追加尚不存在的新 aliases；合计达到 `max_stored_entity_alias_count = 50` 后忽略剩余新 aliases 并在输出中记录 `omitted_alias_count`；**不得**因超限删除既有 alias。
- `canonical_name`：必须保留既有值；「除非新名称是用户明确给出的正式名称，否则不得自动替换」——MVP 无确定性判据可用（判定需语义/LLM，属 §2.1.11 之后的能力），故 **MVP 恒不替换**（`canonical_name_replaced=false`），记录于 OI-EXT-004-004。
- 候选 `name` **不得**被自动加入既有实体的 aliases（规格未授权）；别名合并输入只有候选 `aliases`。
- 用户实体：§2.1.10.1「用户实体不参与普通名称和别名对齐」→ 任何解析到 `entity_id = "user:" + user_id` 的对齐条目，其 `planned_alias_merge.planned_aliases` 必须等于既有 aliases（命中时）或 `[]`（计划创建时），`normalized_candidate_aliases` 不参与合并。
- 写入与指标：EXT-004 **不写入**别名，**不**发 `memory_entity_alias_omitted_total`（该指标的发射点属于真正执行 alias 更新的写入阶段；见 §12.2 DEFERRED_FOR_MVP）。
- §2.1.10 写入约束在本任务中体现为「只输出、不写入」：未被最终非 `SKIP` Memory 引用的候选实体的过滤（`referenced_entity_write_set`）属 EXT-005/EXT-006；EXT-004 输出全部候选对齐结果并保留 `referenced_local_entity_ids` 供下游过滤。

### 5.6 授权失败词表与映射

**只读现状核对**：§2.1.15 现有两个相关错误码——

| 错误码 | 规格含义 | 归属 |
|---|---|---|
| `entity_alignment_failed` | 「实体对齐执行失败」；可人工重试=是 | **EXT-004 唯一授权终态码** |
| `graph_query_failed` | 「**查询已有记忆**失败」；可人工重试=是 | **§2.1.11 已有 Memory 候选召回 = EXT-005；EXT-004 不得使用** |

代码侧核对：`ExtractionLastError` 为通用 `{error_code, failed_stage, message}` 字符串三元组；仓库当前**不存在**任何错误码枚举常量集合，也不存在 `entity_alignment_failed` / `graph_query_failed` 的任何引用。既有已授权 `failed_stage` 字面量：`archive_read`、`archive_validate`（Appendix A.1）、`redaction`（A.2）、`llm_extraction`（B.6）。**EXT-004 MVP_LOCAL_DECISION（OI-EXT-004-002 / LD-9）**：`entity_alignment_failed` → `failed_stage="entity_alignment"`（与 `archive_read` / `llm_extraction` 命名模式一致；**非**规格 Appendix 修订，属 Task Plan 授权的可逆内部字面量，供下游接线与 contract test 锁定）。

EXT-004 失败映射：

| 条件 | error_code | failed_stage | 终态/Offset |
|---|---|---|---|
| Neo4j 只读查询失败（连接、超时、服务不可用、Cypher 执行错误、驱动异常） | `entity_alignment_failed` | `entity_alignment` | 终态 `failed` 持久化成功后才可提交 Offset（沿用 A.1 #3） |
| 图谱 Entity 节点 property 缺失/类型非法，无法映射为授权快照 | `entity_alignment_failed` | `entity_alignment` | 同上 |
| S4 多命中 | **不失败**；LD-8 按 `entity_id ASC` 确定性择一 | — | — |
| 持久化 `extraction_result` 无法 re-hydrate / 不可预期内部与基础设施故障 | 无终态码 | — | `abort_without_terminal`；不写 `last_error`；**不提交 Offset** |

**EXT-004 禁止产生的错误码**：`graph_query_failed`（EXT-005 召回）、`reconciliation_plan_conflict`（EXT-005）、`memory_search_text_too_long`（EXT-006 事务前）、`graph_write_failed`（EXT-006）、`retrieval_index_write_failed`（EXT-007）、`llm_*`（EXT-003）、`archive_*`（EXT-002），以及任何新造码（含 `entity_alignment_ambiguous`、`entity_not_found` 等）。

日志（§2.1.15 #6 / §3.27 / Appendix B §B.11）：失败日志必须且只包含 `task_id`、`archive_id`、`user_id`、`failed_stage`、`attempt_count`（`session_id` 可用时可选）；**不得**记录实体名称、别名、`canonical_name`、`normalized_name`、`entity_key`、原始消息内容、Cypher 参数值、prompt、response、连接串或任何 secret。

### 5.7 与既有 pipeline 的衔接（不改变任何上游语义）

- Appendix B §B.10.4 权威结论：EXT-003→EXT-004 continuation 编排 `DEFERRED_FOR_MVP`；不得为未来编排修改 `PipelineTerminalDecision`；EXT-004 消费已持久化 `extraction_result`。
- 因此 EXT-004 交付**库级可注入服务 + 只读 repository**，由后续拥有完成门禁的任务（EXT-005/EXT-006/EXT-007）接线；本任务：
  - `extraction_pipeline_port.py`：**不改**（`PipelineTerminalDecision` 三种 kind 不变）；
  - `extraction_task_consumer_service.py`：**不改**（状态分支、终态持久化先于 Offset、`TerminalPersistError` 不变）；
  - `extraction_llm_service.py`：**不改**（非空结果仍返回 `abort_without_terminal`，任务保持 `processing`，Offset 不提交）；
  - `extraction_worker.py`：**不改**（`main()` 保持 refusal-only，exit≠0）；
  - 任务状态机：EXT-004 **不**执行任何状态迁移，不将任务标为 `completed` 或 `failed`。
- 上述失败映射（§5.6）是**契约声明**，用于后续接线时逐字采用；EXT-004 只在服务返回值中表达 `EntityAlignmentFailure`，不自行写 `last_error`、不提交 Offset。

## 6. 原子性、幂等、并发、版本冲突、用户隔离、部分失败、进程恢复

| 维度 | 结论 | 必需处理 |
|---|---|---|
| 原子性 | EXT-004 不写任何存储，天然无部分写入 | 只读查询；失败即整体失败，不返回部分对齐结果 |
| 幂等 | 无副作用 → 幂等 | 同一持久化 `extraction_result` + 同一图谱状态 → 相同匹配判定与相同 `entity_key`/`normalized_name` |
| Replay | 不依赖任何 EXT-004 自有状态 | 每次 replay 重新确定性计算；不调用 LLM；不重算 fingerprint / source time |
| Replay（图谱已提交场景） | 前一次尝试若已提交图谱写事务（未来 EXT-006），实体已存在 | S3 `entity_key` 精确匹配复用既有节点，不产生重复计划创建 |
| 并发 | 同 Partition 串行（§2.1.4）；跨进程重复消费不保证 exactly-once | 只读查询无写竞争；不声明 exactly-once；不加锁、不加租约 |
| 版本冲突 | 不涉及 `memory_version`（属 EXT-005/EXT-006） | 不读写 `memory_version`、不实现乐观锁 |
| 用户隔离 | 单 `user_id` 作用域（§2.1.10.6） | 所有 Cypher 显式 `user_id` 谓词；`entity_key` 含 `user_id`；跨用户同名同型必须不匹配（测试断言） |
| 部分失败 | 单个候选查询失败即整批失败 | 返回 `EntityAlignmentFailure`；不返回部分 `alignments` |
| 进程恢复 | 无中间态可丢失 | 崩溃后 replay 从持久化 `extraction_result` 重新对齐；任务保持 `processing`，Offset 未提交 |
| 时间字段 | 不生成任何服务器时间 | `created_time`/`updated_time`/`first_seen_time`/`last_seen_time` 均属写事务；计划态记录不含 |
| Privacy | 实体名称/别名属用户数据 | 不进日志、不进异常 message、不进指标 label；fixture 使用合成数据 |

## 7. 分步骤实现方案

实现以 **PLAN_APPROVED** 为前提；Round 2 已闭合 OI-EXT-004-001/002（MVP_LOCAL_DECISION）；未获 PLAN_APPROVED 前不得编写业务代码。

### Step 1 — §2.1.9 Entity 模型基础与键计算

- 文件：`src/memory_system/domain/models/entity_alignment.py`（§2.1.9 Entity 只读快照 + property/label 常量）、`src/memory_system/domain/services/entity_key.py`（纯函数）。
- 实现 `normalize_entity_name`（§5.2 四步，顺序固定）、`compute_entity_key`（§5.2 公式，UTF-8 + 小写 hexdigest）、`build_user_entity_id`、`planned_user_entity_fields`（§5.4 固定字段，不含服务器时间）。
- 只定义 Entity 相关模型；**不**定义 Memory/Evidence 节点模型与关系常量（属 EXT-005/EXT-006；避免未被使用的死代码）。
- 不引入任何 Neo4j/LLM/IO 依赖。

### Step 2 — 只读 Neo4j 实体查询层

- 文件：`src/memory_system/infrastructure/neo4j/entity_alignment_repository.py`（新建；当前 `infrastructure/neo4j/` 为空包）。
- 实现 Q1、Q2、Q3（§5.2.2），使用既有 `AsyncDriver` 只读事务；批量 `UNWIND`；显式 `user_id` 过滤；S4 多命中按 LD-8 `entity_id ASC` 择一；结果映射为严格 typed 快照。
- 抛出的驱动异常在服务层转换为 §5.6 映射；repository 不吞异常、不重试、不写入。
- 不新增 Settings、不新增 driver、不修改 `runtime.py`。

### Step 3 — 确定性实体对齐服务

- 文件：`src/memory_system/domain/services/entity_alignment_service.py`。
- 输入：`EntityAlignmentInput`（或既有 `ExtractionValidatedResult` + `user_id`）；依赖注入只读 repository 与 `entity_id_factory`；**无 LLM 依赖**。
- 按 §5.2 S0–S6 顺序实现；输出 §5.4 `EntityAlignmentOutcome`；别名合并计划按 §5.5。
- 失败按 §5.6 映射；不可预期故障不产生终态码。
- 日志只输出 §5.6 允许的 metadata。

### Step 4 — 持久化结果读取适配（read-only）

- 文件：`src/memory_system/domain/services/entity_alignment_service.py`（同一模块内的只读加载方法；不新增文件）。
- 通过既有 `extraction_task_repository.find_extraction_task_by_archive_id` 读取任务，取 `extraction_result` 并用既有 `ExtractionValidatedResult` 严格 re-hydrate；`status != processing` 或 `extraction_result is None` 时不进行对齐（返回不可对齐的 abort 语义，不新造错误码）。
- **不得**新增/修改 repository 写方法；**不得**修改 `extraction_task_repository.py`（若确需只读 helper 且既有函数不足，必须停止并报告）。

### Step 5 — 测试与质量门禁

- 按 §10 编写 Unit / Contract / Integration；Neo4j 集成使用既有 compose 测试栈与既有 migration；无网络外部 provider 调用。
- 运行 Ruff + Mypy（strict）；不得降低断言或跳过失败。

## 8. 文件变更清单（精确路径白名单，无 glob）

### 8.1 本轮规划白名单（已使用）

- `02_开发管理/tasks/EXT-004-entity-alignment-neo4j-model-basis.md`
- `02_开发管理/open_issues.md`
- `02_开发管理/progress.md`
- `02_开发管理/master_plan.md`

本轮**未**修改权威规格正文、`src/**`、`tests/**`、配置、依赖、lockfile；本轮**未**执行任何 Git 写命令。

### 8.2 条件实现白名单（PLAN_APPROVED + OI 关闭后）

生产（新建）：

- `src/memory_system/domain/models/entity_alignment.py` — 对齐输入/输出模型、`EntityMatchKind`、`PlannedEntityAliasMerge`、`EntityNodeSnapshot`、失败模型、§2.1.9 Entity label/property 常量。
- `src/memory_system/domain/services/entity_key.py` — `normalize_entity_name` / `compute_entity_key` / `build_user_entity_id` / `planned_user_entity_fields` 纯函数。
- `src/memory_system/domain/services/entity_alignment_service.py` — §2.1.10 确定性对齐 + 别名合并计划 + 失败映射 + 只读持久化结果加载。
- `src/memory_system/infrastructure/neo4j/entity_alignment_repository.py` — Q1/Q2（及 OI 关闭后的 Q3）只读 Cypher。

生产（**显式不变**，列出以便审查断言零 diff）：

- `src/memory_system/domain/services/extraction_pipeline_port.py`
- `src/memory_system/domain/services/extraction_task_consumer_service.py`
- `src/memory_system/domain/services/extraction_llm_service.py`
- `src/memory_system/domain/services/extraction_archive_preprocessing_service.py`
- `src/memory_system/domain/services/extraction_redaction_service.py`
- `src/memory_system/domain/services/extraction_fingerprint.py`
- `src/memory_system/domain/models/extraction_llm.py`
- `src/memory_system/domain/models/extraction_task.py`
- `src/memory_system/domain/enums/extraction_task.py`
- `src/memory_system/infrastructure/mongodb/extraction_task_repository.py`
- `src/memory_system/entrypoints/extraction_worker.py`
- `src/memory_system/infrastructure/runtime.py`
- `src/memory_system/settings/models.py`、`src/memory_system/settings/validators.py`
- `src/memory_system/observability/metrics.py`
- `scripts/migrations/002_initial_neo4j.py` 及全部 migration

测试（新建）：

- `tests/unit/test_entity_key.py` — 归一化向量、`entity_key` 公式/编码/hex、用户实体 ID 与固定字段。
- `tests/unit/test_entity_alignment_service.py` — 全部确定性分支、别名合并计划、失败映射、零 LLM 依赖、privacy 日志（使用 fake 只读 repository）。
- `tests/contract/test_ext004_contract.py` — 输入/输出契约、§2.1.9 property 集合、错误码白名单、不持久化契约、无 EXT-005+ 字段、上游文件零变更断言。
- `tests/integration/test_ext004_entity_alignment_neo4j.py` — 真实 Neo4j（既有 compose 栈 + 既有 migration）：命中/未命中/用户实体/跨用户隔离/零写入/查询失败注入。
- `tests/integration/test_ext004_alignment_replay_mongo.py` — 从 Mongo 读取持久化 `extraction_result` 两次对齐得到相同判定；Fake LLM 调用计数为 0；Mongo 文档零变更。

测试（**显式不变**）：`tests/unit/test_extraction_llm_service.py`、`tests/unit/test_extraction_fingerprint.py`、`tests/unit/test_extraction_task_consumer_service.py`、`tests/unit/test_extraction_pipeline_ext002.py`、`tests/unit/test_extraction_task_repository.py`、`tests/contract/test_ext001_contract.py`、`tests/contract/test_ext002_contract.py`、`tests/contract/test_ext003_contract.py`、`tests/integration/test_extraction_*`、`tests/integration/test_migrate_infra.py`、`tests/e2e/**`。

明确不在白名单：

- `pyproject.toml`、`uv.lock`、`configs/**`、`.env.example`、`scripts/**`（含全部 migration）、`compose*.yaml`
- `src/memory_system/infrastructure/kafka/**`、`src/memory_system/infrastructure/elasticsearch/**`、`src/memory_system/infrastructure/embedding/**`、`src/memory_system/infrastructure/llm/**`
- `src/memory_system/api/**`、`src/memory_system/application/**`
- 任何 EXT-005/EXT-006/EXT-007 模块（reconciliation、graph write、retrieval sync）
- DEV-006 相关路径、PR #13 产物
- 权威规格正文（本轮不追加 Appendix；若 owner 决议需要修订，由授权轮次单独落盘）

## 9. Contract / Unit / Integration 测试计划

### 9.1 Unit — `tests/unit/test_entity_key.py`

| ID | 场景 | 期望 |
|---|---|---|
| U1 | `entity_key` 公式 | 逐字 `SHA256(user_id + ":" + entity_type + ":" + normalized_name)`；UTF-8；小写 hex；固定向量 |
| U2 | `normalized_name` NFKC | 全角/兼容字符按 NFKC 折叠 |
| U3 | 转小写 | 使用 `str.lower()` 语义（固定向量断言，不使用 `casefold`） |
| U4 | 连续空白压缩 + 去首尾空白 | 多空格/制表/换行压缩为单空格；首尾清除 |
| U5 | 顺序不可换 | NFKC→lower→压缩→strip 的固定向量结果 |
| U6 | 未授权归一化缺失 | 不做标点剥离、同义词、locale 排序、数字归一（负向断言） |
| U7 | 用户实体 ID / 固定字段 | `"user:" + user_id`；`person`/`current_user`/`current_user`/`aliases=[]`；`entity_key` 与公式一致；无 `created_time`/`updated_time` |
| U8 | 不同 `user_id` 同名同型 | `entity_key` 不同 |

### 9.2 Unit — `tests/unit/test_entity_alignment_service.py`

| ID | 场景 | 期望 |
|---|---|---|
| A1 | **Happy path**：多候选，部分命中既有实体、部分新建 | 完整 `alignments`；`local_entity_id -> entity_id` 全覆盖；顺序 = user 条目在首、其余 provider 顺序 |
| A2 | **无匹配 / 新实体路径** | `match_kind=planned_create`；`planned_create=true`；`existing_entity=null`；`entity_key`/`normalized_name` 为计算值；**未**发生任何写调用 |
| A3 | **既有实体对齐**（S3 `entity_key` 精确命中） | `match_kind=entity_key_exact`；`entity_id`/`canonical_name`/`entity_key` 取既有节点值；`canonical_name` 未被替换 |
| A4 | S4 次级精确命中（canonical / normalized_name） | `match_kind=canonical_or_alias_exact`；命中 `existing.normalized_name == candidate.normalized_name` |
| A4b | S4 次级精确命中（alias） | 既有 `aliases[]` 元素经 `normalize_entity_alias` 后与 `candidate.normalized_name` 相等即命中 |
| A5 | S4 零命中 | 进入 S5 `planned_create` |
| A5b | S4 多命中确定性（LD-8） | ≥2 个既有 Entity 均命中时绑定 **`entity_id` 字典序最小** 者；`match_kind=canonical_or_alias_exact`；**不**返回 failure |
| A5c | 同批次相同 `entity_key` 双候选 | 两个 `local_entity_id`、相同 `normalized_name`+`type`、均无既有节点 → **一个** `planned entity_id`；两 local ID 映射相同；`entity_id_factory` 仅调用一次 |
| A6 | 保留值 `user` 已存在 | `match_kind=reserved_user_existing`；`entity_id="user:{user_id}"`；**未**执行 Q2/Q3；不参与名称/别名对齐 |
| A7 | 保留值 `user` 不存在 | `match_kind=reserved_user_planned_create`；固定字段逐字；`planned_aliases=[]`；**无**第二个用户实体计划 |
| A7b | 仅 memory 引用 `user`、entities 无 user 行 | 仍产出 `local_entity_id="user"` 对齐条目；memory 引用可解析 |
| A7c | entities 含 `local_entity_id="user"` | 走 S1 专用路径；**不**经 S2–S5；不与普通候选共享 planned_create 逻辑 |
| A8 | 无 memory 引用 `user` | 输出不含保留 user 条目（不无故计划创建用户实体） |
| A9 | 候选实体未被任何 memory 引用 | 仍产出对齐条目（§2.1.10 允许查询全部候选）；输出保留 `referenced_local_entity_ids` 供下游过滤；**不**在 EXT-004 过滤或写入 |
| A10 | **图谱查询失败**（驱动异常/超时/Cypher 错误） | `outcome=failure`；`error_code=entity_alignment_failed`；`failed_stage=entity_alignment`；无部分 `alignments` |
| A11 | **对齐失败**：Entity 节点 property 缺失/类型非法 | 同 A10 映射；不得 coercion 或填默认值 |
| A12 | 禁用码负向断言 | 输出永不含 `graph_query_failed`、`reconciliation_plan_conflict`、`graph_write_failed`、`memory_search_text_too_long`、`retrieval_index_write_failed`、`llm_*`、`archive_*` 或新造码 |
| A13 | 持久化结果不可 re-hydrate / 不可预期内部故障 | 不产生终态码；abort 语义；不写 `last_error`；不提交 Offset（由调用契约断言） |
| A14 | **Replay / 幂等**：同输入 + 同图谱状态连续两次对齐 | 匹配判定、`entity_key`、`normalized_name`、`planned_aliases`、同键 `planned entity_id` 分组完全一致；无任何写调用 |
| A15 | Replay：首次计划创建、随后实体已存在 | 第二次通过 S3 命中既有节点；不再产出 `planned_create` |
| A15b | **planned-create replay 确定性** | 固定 `entity_id_factory` 序列；同输入两次对齐：相同 `entity_key` 组获得相同占位 `entity_id`；provider 顺序不变则分组不变 |
| A16 | **无 LLM 重抽取**：服务构造/调用不接受 LLM client | 模块不 import `infrastructure.llm.*`；注入 Fake LLM 至周边不产生调用（计数 0） |
| A17 | 不重算 fingerprint / source time | 服务不引用 `compute_candidate_fingerprint`，输出不含 `candidate_fingerprint` / `candidate_source_time` |
| A18 | 别名合并：新 alias 追加 | 既有顺序保留，新 alias 排序追加，去重 |
| A19 | 别名合并：50 上限 | `planned_aliases` 长度 ≤ 50；既有 alias 一条未删；`omitted_alias_count` 精确；不发指标 |
| A20 | 别名合并：候选 name 不入 alias | `planned_aliases` 不含候选 `name`（除其本身即为候选 alias） |
| A21 | 别名合并：`canonical_name` 永不替换 | `canonical_name_replaced=false`；输出 `canonical_name` = 既有值 |
| A22 | 用户实体别名不参与合并 | 解析到 `user:{user_id}` 的条目 `planned_aliases` 等于既有 aliases 或 `[]` |
| A23 | **用户隔离** | 仅本 `user_id` 的既有实体可命中；跨用户同名同型不命中（fake repository 断言查询参数含 `user_id`） |
| A24 | **Privacy / 安全日志** | caplog 断言：无实体名/别名/`canonical_name`/`normalized_name`/`entity_key`/Cypher 参数/原始消息/prompt/response/secret；失败日志含且仅含 `task_id`/`archive_id`/`user_id`/`failed_stage`/`attempt_count`（`session_id` 可选） |
| A25 | 100 候选批量 | 查询次数为常数级（批量 `UNWIND`），非 per-candidate 串行 |
| A26 | **零写入** | fake repository 不暴露写方法；服务对其调用集合仅为只读方法（断言调用名单） |

### 9.3 Contract — `tests/contract/test_ext004_contract.py`

| ID | 场景 | 期望 |
|---|---|---|
| C1 | 输入契约 | 只消费 `entities[]` 授权字段与 memory 的 subject/object 引用；不接受 Archive、raw content、event payload、LLM client |
| C2 | 输出契约形状 | `EntityAlignmentOutcome` / `AlignedEntity` / `PlannedEntityAliasMerge` / `EntityNodeSnapshot` 字段集合逐字；`extra="forbid"` |
| C3 | §2.1.9 Entity property 集合 | 只读 property 名称逐字：`entity_id`/`user_id`/`entity_key`/`entity_type`/`canonical_name`/`normalized_name`/`aliases` |
| C4 | `entity_key` 公式与编码 | 固定向量；UTF-8；小写 hex |
| C5 | 用户实体确定性 ID + 固定字段 | §2.1.10.1 逐字；无服务器时间字段 |
| C6 | `entity_type` 枚举 | 复用 §2.1.6 七值枚举，不新增类型 |
| C7 | 错误码白名单 | EXT-004 可产出集合 = `{entity_alignment_failed}`；禁用码负向断言（含 `graph_query_failed`） |
| C8 | `failed_stage` 字面量 | 断言 `entity_alignment_failed` → `failed_stage="entity_alignment"`；不得出现未授权字面量 |
| C9 | 不持久化契约 | 输出模型无持久化方法；`extraction_result` 授权字段集合不变（`AUTHORIZED_MEMORY_FIELDS`/`AUTHORIZED_ENTITY_FIELDS` 零变更）；无新增 Mongo 字段/Collection |
| C10 | 只读 Cypher 契约 | Q1/Q2（/Q3）文本不含 `CREATE`/`MERGE`/`SET`/`DELETE`/`REMOVE`/`CONSTRAINT`/`INDEX`；均含 `user_id` 谓词 |
| C11 | 无 EXT-005+ 字段 | 输出不含 `aligned_memory_key`、`memory_id`、`evidence_id`、`action`、`reason_code`、`merged_content`、`increment_memory_version`、`referenced_entity_write_set`、`core_search_text`、`importance`、`confidence`、`memory_version` |
| C12 | 上游零变更 | `PipelineTerminalKind` 仍为三值；`PipelineTerminalDecision` 工厂方法集合不变；`extraction_worker.main()` 仍返回 ≠0；`ExtractionLlmService.run` 非空结果仍 `abort_without_terminal` |
| C13 | Migration 零变更 | `002_initial_neo4j.NEO4J_SCHEMA_NAMES` 与 §2.1.9 名称逐字一致且未被本任务修改；无新增 migration 文件 |
| C14 | 依赖零变更 | `pyproject.toml` 中 `neo4j>=5.28,<6` 未变；无新增依赖组/包 |
| C15 | 别名上限来源 | 使用既有 `max_stored_entity_alias_count`/`max_entity_candidates_per_archive` Settings，不硬编码第二套常量 |

### 9.4 Integration — `tests/integration/test_ext004_entity_alignment_neo4j.py`（真实 Neo4j）

| ID | 场景 | 期望 |
|---|---|---|
| I1 | 既有 Entity（`entity_key` 精确）命中 | 返回既有 `entity_id`；`entity_key_unique` 索引路径可用 |
| I2 | 无匹配 → 计划创建 | 无 Entity 节点被创建（前后 `count(:Entity)` 相等） |
| I3 | 用户实体存在 / 不存在 | 分别 `reserved_user_existing` / `reserved_user_planned_create`；后者不创建节点 |
| I4 | S4 次级精确匹配（canonical / alias / 多命中） | A4/A4b/A5/A5b 场景；多命中取 `entity_id ASC` |
| I4b | 同批次 `entity_key` 碰撞 | 两候选同键计划创建 → 单 `planned entity_id`；零 Neo4j 写入 |
| I5 | 跨用户隔离 | 用户 B 的同名同型实体不被用户 A 命中 |
| I6 | 零写入总断言 | 对齐前后 Entity 节点数、property、aliases 全部逐字不变；无新增关系 |
| I7 | 图谱查询失败注入（关闭/不可达 session） | `entity_alignment_failed` + `failed_stage=entity_alignment`；无部分结果 |
| I8 | 100 候选批量 | 完成且查询次数常数级；无超时（沿用 §3.24 既有超时） |
| I9 | 约束前置 | 依赖既有 migration 已建约束；测试不创建/修改约束或索引 |

### 9.5 Integration — `tests/integration/test_ext004_alignment_replay_mongo.py`（真实 Mongo）

| ID | 场景 | 期望 |
|---|---|---|
| M1 | 从持久化 `extraction_result` 加载并对齐 | 使用既有 fixture 写入 `processing` + 非空结果的任务；对齐成功 |
| M2 | **无不必要 LLM 重抽取** | 注入 Fake LLM 至周边协作者，调用计数严格为 0 |
| M3 | Replay 幂等 | 连续两次对齐结果判定一致；Mongo 文档（含 `extraction_result`、`status`、`attempt_count`、`updated_time`）零变更 |
| M4 | `status`/结果不符合前置 | `status != processing` 或 `extraction_result is None` 时不对齐；不新造错误码；不改任务状态 |
| M5 | 任务状态机零影响 | 对齐后任务仍为 `processing`；未产生 `completed`/`failed`；未提交 Offset（无 consumer 调用） |

### 9.6 E2E / 真实外部调用

| 场景 | 结论 |
|---|---|
| Kafka → Archive → LLM → Neo4j → ES 全链路 | 不适用；属 EXT-009 |
| 真实 DeepSeek / SiliconFlow 调用 | 不适用；EXT-004 无 LLM/Embedding 行为；默认 CI 无外部 provider 调用 |
| 生产 worker 启动 | 不适用；`main()` 保持 refusal-only |

## 10. 验收标准（可客观验证）

- [ ] Plan Review Round 2 通过；OI-EXT-004-001/002 已按 MVP_LOCAL_DECISION 闭合（非 blocking）。
- [ ] 权威输入唯一为已持久化 `extraction_result`；实施代码不 import 任何 LLM client；Fake LLM 调用计数为 0（A16/M2）。
- [ ] 不重新读取 `context_archive`、不重算 `candidate_fingerprint` / `candidate_source_time`（A17）。
- [ ] §2.1.10 S0–S6 顺序逐条实现且被测试覆盖；MVP 完全确定性，无 LLM、无模糊/向量/全文匹配。
- [ ] `entity_key` 与 `normalized_name` 按 §5.2 逐字实现，固定向量测试通过。
- [ ] 用户实体确定性 ID 与 §2.1.10.1 固定字段逐字；不生成服务器时间字段。
- [ ] 对齐输出为瞬态返回值：无新增 Mongo 字段/Collection、无 Neo4j 写入、无缓存/文件写入；`AUTHORIZED_ENTITY_FIELDS`/`AUTHORIZED_MEMORY_FIELDS` 零变更（C9）。
- [ ] 所有 Cypher 只读且含 `user_id` 谓词；Entity 节点数与 property 在集成测试前后逐字不变（C10/I6）。
- [ ] 别名合并仅为计划态：50 上限、既有 alias 零删除、`canonical_name` 永不替换、`omitted_alias_count` 精确、无指标发射（A18–A22）。
- [ ] 跨用户隔离通过（A23/I5）。
- [ ] 失败映射只使用 `entity_alignment_failed`；`graph_query_failed` 与全部 EXT-005+/EXT-003/EXT-002 码负向断言通过（A12/C7）。
- [ ] `failed_stage` 使用 `entity_alignment`（LD-9）；无未授权字面量（C8）。
- [ ] 不可预期故障保持 abort 语义、不写 `last_error`、不提交 Offset（A13）。
- [ ] Replay 幂等（A14/A15/M3）；任务状态机与 Offset 语义零影响（M5/C12）。
- [ ] `PipelineTerminalDecision`、consumer、`extraction_llm_service`、`extraction_worker`、`runtime.py`、Settings、metrics、全部 migration 零 diff（C12/C13）。
- [ ] 无 EXT-005+ 输出字段与行为（C11）。
- [ ] `dependency_changes_expected=NONE` 成立：`pyproject.toml`/`uv.lock`/`configs/**` 零 diff（C14）。
- [ ] Privacy：无实体名/别名/`entity_key`/Cypher 参数/原始内容/secret 进入日志、异常或指标 label；失败日志含五项必需 metadata（A24）。
- [ ] 精确白名单外零文件变更；Unit / Contract / Integration 全通过；Ruff PASS；Mypy strict PASS；Code Review 无 P0/P1。

## 11. Open Issues

### 11.1 原 Round 1 阻塞项（已降级为 MVP_LOCAL_DECISION — Amendment 002）

**OI-EXT-004-001** — `resolved_by_plan` / `blocks_current_task: false`

- Round 1：`blocks_current_task: true`（历史见 open_issues.md 原文）。
- Round 2 闭合：§5.2.2 + LD-7/LD-8；测试 A4/A4b/A5/A5b/I4。

**OI-EXT-004-002** — `resolved_by_plan` / `blocks_current_task: false`

- Round 1：`blocks_current_task: true`（历史见 open_issues.md 原文）。
- Round 2 闭合：`failed_stage="entity_alignment"`（LD-9）；§5.6。

### 11.2 已登记非阻塞项（本计划已固定读法）

**OI-EXT-004-003 — `normalized_name` 与候选 alias 归一化的 micro-semantics**：§2.1.10.2 列明四项操作（NFKC、转小写、去首尾空格、连续空白），§2.1.6 列明候选 alias「NFKC、去空白、去重并排序」，但未定义 `lower()` 与 `casefold()` 的取舍、空白字符集合、以及 alias「去空白」是去首尾还是压缩内部。本计划固定为 §5.2/§5.5 的字面读法并以固定向量测试锁定。`blocks_current_task: false`。

**OI-EXT-004-004 — `canonical_name` 替换判据与用户实体别名非参与**：§2.1.10 允许在「新名称是用户明确给出的正式名称」时替换 `canonical_name`，但 MVP 无确定性判据（判定需语义能力）。本计划固定为 MVP 恒不替换（`canonical_name_replaced=false`），并据 §2.1.10.1 固定用户实体不做别名合并。`blocks_current_task: false`。

### 11.3 相关既有 Open Issues

| ID | 状态 | 与 EXT-004 关系 |
|---|---|---|
| OI-006 | open | `reconciliation_plan_conflict` 运维清理无 Contract；属 EXT-005/EXT-008，EXT-004 不触及 |
| OI-EXT-003-005 | deferred_for_mvp | SHA-256 collision；EXT-004 的 `entity_key` 同样只做普通 SHA-256 身份比较，不发明 collision 处理 |
| OI-EXT-002-003 | deferred / out_of_scope | first-person binding；EXT-004 不得依赖，用户实体只由保留值 `user` 与确定性 ID 表达 |

## 12. MVP 分类与决议记录

### 12.1 HARD_BLOCK

| 项 | 理由 |
|---|---|
| （无） | Round 2 已闭合原 OI-EXT-004-001/002 |

### 12.2 DEFERRED_FOR_MVP

| 项 | 归属 |
|---|---|
| `memory_entity_alias_omitted_total` 指标发射 | 发射点属真正执行 alias 更新的图谱写入阶段（EXT-006）；EXT-004 仅在输出中给出 `omitted_alias_count` |
| `referenced_entity_write_set` 过滤与孤立节点防护 | §2.1.13 第 8 步；依赖 EXT-005 非 `SKIP` 计划 |
| EXT-003→EXT-004 生产 continuation 编排 | Appendix B §B.10.4 权威 `DEFERRED_FOR_MVP`；由拥有完成门禁的后续任务接线 |
| Memory / Evidence 节点模型、关系常量、字段所有权与 `memory_version` 语义 | §2.1.9 中属 EXT-005/EXT-006 使用面；EXT-004 不产生未被使用的死代码 |
| 模糊/全文/向量实体合并、跨用户全局对齐 | §2.1.10 / §2.1.16 明确后续版本 |
| SHA-256 collision 处理 | OI-EXT-003-005 deferred；`entity_key` 只做普通身份比较 |

### 12.3 MVP_LOCAL_DECISION（可逆内部实现选择；显式记录）

| ID | 决策 | 理由 / 可逆性 |
|---|---|---|
| LD-1 | 计划态新实体 `entity_id` 由可注入 `entity_id_factory`（默认 UUID v4）生成；**同批次 `entity_key` 单占位**（§5.4.1） | §2.1.13 第 2 步完整映射；未写入前瞬态；replay 经 `entity_key` 收敛；EXT-006 必须 `MERGE` by `entity_key` |
| LD-2 | 输出顺序：保留 `user` 条目置首，其余按 `entities[]` provider 原顺序 | 与 Appendix B §B.8 一致；仅影响瞬态输出 |
| LD-3 | Q1/Q2/Q3 使用批量 `UNWIND` 单查询而非 per-candidate 往返 | 100 候选上限下的性能；不改变匹配语义 |
| LD-4 | 只读加载持久化结果的方法置于 `entity_alignment_service.py`，不新增文件、不修改既有 repository | 沿用 EXT-003 SF-1 先例 |
| LD-5 | 仅实现 Entity 侧模型基础，不预先定义 Memory/Evidence 模型与关系常量 | 避免死代码 |
| LD-6 | EXT-004 不实现应用层查询重试 | §3.24 #1 禁止通用 Retry Decorator |
| LD-7 | S4 候选操作数仅 `normalized_name`；既有侧 `normalized_name` + `normalize_entity_alias(aliases[])` | 闭合 OI-EXT-004-001；候选 aliases 不参与 S4 身份查找 |
| LD-8 | S4 多命中：按 `entity_id` 字典序升序取第一条；不 fail-closed | 闭合 OI-EXT-004-001 多命中；最简单确定性 MVP 规则 |
| LD-9 | `entity_alignment_failed` → `failed_stage="entity_alignment"` | 闭合 OI-EXT-004-002；非 Appendix 修订 |

### 12.4 SAFE_AUTO_REMEDIATION

| 项 | 处理 |
|---|---|
| `progress.md` 重复 YAML 键 `next_action` | Round 1 规划同步时存在重复键；已将历史 STM-006 条目处的重复键重命名为 `historical_next_action_EXT-002`（L754），保留当前任务 `next_action: "计划审查"`（L27/L755）；**非阻塞**；本条目诚实记录于执行日志 §16 |

## 13. 风险与依赖结论

- **依赖变化**：`NONE`。`neo4j>=5.28,<6` 已在 `dependencies`；`Neo4jSettings`（§3.24 固定值）与 `AppState.neo4j` AsyncDriver 已存在；无新增包、无 lockfile 变更。
- **Schema / Migration**：`NONE`。§2.1.9 约束/索引已由 DEV-004 migration `002_initial_neo4j.py` 创建并有集成断言；禁止新增或修改 migration，禁止运行时 DDL（§3.26 + 治理）。
- **配置**：`NONE`。别名上限与候选上限沿用既有 `memory_extraction` Settings。
- **主要风险**：
  1. ~~两项 blocking Open Issue 未决~~ → Round 2 已闭合（MVP_LOCAL_DECISION）。
  2. 误用 `graph_query_failed` 会污染 EXT-005 的失败语义 → C7 负向断言。
  3. 误在对齐阶段写入 Neo4j 会违反 §2.1.13 并产生孤立节点 → I6 零写入断言 + C10 Cypher 文本断言。
  4. 误接线生产 pipeline 会改变 EXT-003 终态/Offset 语义 → C12 上游零变更断言。
  5. 实体名称/别名属用户数据，误入日志构成隐私违规 → A24 caplog 断言。

## 14. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/EXT-004-entity-alignment-neo4j-model-basis"
baseline_main: "8330d42a9f2fe9365e180bdd68c6c9dc7add6e48"
expected_commits:
  - "docs(plan): add EXT-004 entity alignment neo4j model basis plan"
  - "feat(ext): add deterministic entity alignment and neo4j entity model basis"
  - "docs(status): record EXT-004 implementation commit and PR"
  - "docs(status): complete EXT-004 after PR merge"
release_phases:
  PLAN_LANDING: "main: approved planning whitelist only; after PLAN_APPROVED; exact branch creation; no implementation"
  IMPLEMENTATION_RELEASE: "feature branch only; exact production/test whitelist; only after blocking Open Issues resolved and implementation approved; no main write/push"
  POST_MERGE_CLEANUP: "NORMAL only after verified MERGED PR; complete governance on main; delete only exact planned branch"
out_of_scope_changes:
  - "authoritative specification body"
  - "EXT-001 Kafka/topic/group/offset/task status semantics"
  - "EXT-002 raw validation/normalization/redaction semantics"
  - "EXT-003 LLM/validation/fingerprint/extraction_result persistence semantics"
  - "EXT-005 reconciliation/candidate recall/aggregation"
  - "EXT-006 Neo4j graph transaction and any graph write"
  - "EXT-007 retrieval indexing/Embedding/Elasticsearch"
  - "EXT-008 admin/retry API; EXT-009 E2E"
  - "DEV-006 / PR #13"
  - "dependencies, migrations, settings/config expansion, secrets, real user data"
```

## 15. Plan Amendment

未来修改必须追加 Amendment 并重新 Plan Review；已批准计划正文不得静默覆盖。

### Amendment 001

- 日期：2026-08-12
- 原计划：Initial fail-closed plan (Round 1)
- 修改内容：Round 1 初版；OI-EXT-004-001/002 blocking
- 修改原因：Planner 初版
- 是否影响技术规格：**否**
- 审批状态：Round 1 `PLAN_REJECTED`（BLOCKER=0 MUST_FIX=5 SHOULD_FIX=2）

### Amendment 002 — Round 2 Plan Remediation

- 日期：2026-08-12
- 原计划：Amendment 001 / Round 1 fail-closed
- 修改内容：
  1. §5.2.1 保留 `user` 专用路径（不经 S2–S5 / Q2–Q3）
  2. §5.2.2 S4 次级匹配完整契约 + Q3
  3. §5.4.1 同批次 `entity_key` 单 `planned entity_id` + LD-1 占位边界
  4. §5.6 `failed_stage=entity_alignment`（LD-9）
  5. OI-EXT-004-001/002 降级为 MVP_LOCAL_DECISION（非 blocking）
  6. 测试计划增补 A4b/A5/A5b/A5c/A7b/A7c/A15b/I4b
  7. §12.4 记录 SAFE_AUTO_REMEDIATION（progress 重复 `next_action` 键重命名）
- 修改原因：`AUTHORIZE_PLAN_REMEDIATION_ROUND_2`；Round 1 MUST_FIX=5
- 是否影响技术规格：**否**（无 Spec Amendment）
- 审批状态：Round 2 Plan Review `PLAN_APPROVED`（BLOCKER=0 MUST_FIX=0 SHOULD_FIX=1）

## 16. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-12 06:20 UTC | Planner 创建 fail-closed 计划 | 仅规划白名单（Task Plan / open_issues / progress / master_plan）；未改 `src/**`、`tests/**`、规格正文、配置、依赖；未执行 Git 写 | N/A（规划-only） | OI-EXT-004-001 / OI-EXT-004-002 blocking；`approval_posture=FAIL_CLOSED_BLOCKED`；`next_action=计划审查` |
| 2026-08-12 14:50 UTC | Planner Round 2 remediation (Amendment 002) | §5.2.1/§5.2.2/§5.4.1/S4 Q3/同批次 entity_key/LD-1/LD-7/LD-8/LD-9/测试计划；同步 open_issues/progress/master_plan；SAFE_AUTO_REMEDIATION 记录 progress 重复 `next_action` 键重命名 | N/A（规划-only） | OI-EXT-004-001/002 → MVP_LOCAL_DECISION non-blocking；`approval_posture=AWAIT_PLAN_REVIEW_ROUND_2`；Developer NOT authorized |
| 2026-08-12 15:00 UTC | Plan Review Round 2 | `PLAN_APPROVED`；BLOCKER=0 MUST_FIX=0 SHOULD_FIX=1（SF-R2-001：Q3 示例 Cypher 对 aliases 为原文比较，实现须以 §5.2.2 表为准做 `normalize_entity_alias`） | N/A | `status=READY_FOR_PLAN_APPROVAL`；Developer still NOT authorized until human PLAN_APPROVED |
| 2026-08-12 07:25 UTC | Developer implementation | 新建 entity_alignment 模型/entity_key/entity_alignment_service/entity_alignment_repository + unit/contract/integration 测试白名单；Q3 按 user_id+entity_type 批量 fetch + Python `normalize_entity_alias` 过滤（SF-R2-001）；零 Neo4j 写入；未改 pipeline/consumer/llm/worker/repository | `pytest` unit+contract 53 passed；`ruff` PASS；`mypy` PASS；integration 需 Docker（skip if unavailable） | `status=tested`；`READY_FOR_CODE_REVIEW` |
| 2026-08-12 15:30 UTC | Code Review | `CODE_REVIEW_APPROVED`；P0=0 P1=0 P2=2 P3=2 non-blocking | N/A | `status=reviewed`；`READY_FOR_HUMAN_COMMIT` |
| 2026-08-12 15:35 UTC | Release IMPLEMENTATION_RELEASE | implementation `0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c`；PR #38 OPEN；feat push only | scoped 53 passed；ruff PASS；mypy PASS | `status=committed`；`next_action=WAITING_FOR_PR_MERGE` |

## 17. 最终状态

`committed` — IMPLEMENTATION_RELEASE complete；implementation `0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c`；PR #38 OPEN；scoped 53 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2 non-blocking；零 Neo4j 写入；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**。

### Git 记录

```yaml
branch: "feat/EXT-004-entity-alignment-neo4j-model-basis"
plan_commit: "8330d42a9f2fe9365e180bdd68c6c9dc7add6e48"
implementation_commit: "0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c"
implementation_commit_message: "feat(ext): add deterministic entity alignment and neo4j read model"
pr: "#38"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/38"
pr_state: OPEN
release_gate: IMPLEMENTATION_RELEASE_COMPLETE
```

### Code Review

```yaml
review_report: CODE_REVIEW_APPROVED
p0: 0
p1: 0
p2: 2
p3: 2
```
