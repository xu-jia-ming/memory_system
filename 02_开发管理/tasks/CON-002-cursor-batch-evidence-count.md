# CON-002 Cursor 分页批量读取与 Evidence 计数

## 1. 任务信息

```yaml
task_id: CON-002
task_name: Cursor 分页批量读取与 Evidence 计数
status: approved
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "85875ff4d86ad39ccff9d4632088713ef8b052af"
branch: "feat/CON-002-cursor-batch-evidence-count"
created_at: "2026-08-13 10:37 UTC"
updated_at: "2026-08-13 10:50 UTC"
spec_sections:
  - "§2.1.9 Neo4j 记忆图谱数据模型（Memory / Evidence 字段；user_id 隔离）"
  - "§2.2.12 Evidence 加载（user_id 双端隔离模式；本任务复用 OPTIONAL MATCH 隔离语义，非 retrieval evidence_count）"
  - "§2.3.2 MVP 范围与基本规则（规则 2、6、7 — 用户隔离、统一 evaluation_time、确定性）"
  - "§2.3.3 Memory 字段补充（last_consolidated_time / memory_version 只读引用）"
  - "§2.3.4 调度、互斥与批量扫描（本任务唯一权威范围 — 候选选择、Cursor 分页、Neo4j 批量读、independent_archive_count）"
  - "§2.3.12 memory_consolidation 配置默认值（只读消费 batch_size；不修改 Settings Contract）"
  - "§2.3.13 失败处理与恢复（consolidation_read_failed / invalid_memory_state / missing_evidence 映射）"
prerequisites:
  formal:
    - "CON-001 — SATISFIED/completed（PR #50 MERGED）；compute_consolidation_importance + ConsolidationImportanceInput 契约"
    - "EXT-001..009 — SATISFIED/completed"
    - "RET-001..006 — SATISFIED/completed（v0.4.0-memory-retrieval closed）"
  implementation_reuse:
    - "ConsolidationImportanceInput / compute_consolidation_importance（CON-001；禁止修改公式语义）"
    - "MemoryConsolidationSettings.batch_size 默认 500（settings/models.py）"
    - "MemoryRetrievalSettings.neo4j_timeout_seconds（只读注入 Neo4j 超时；禁止修改 Settings Contract）"
    - "RetrievalMemoryReadRepository / RetrievalEvidenceReadRepository / EvidenceLookupRepository — user_id 隔离与 Neo4j 只读错误模式"
  baseline_evidence:
    branch: "main"
    head: "85875ff4d86ad39ccff9d4632088713ef8b052af"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=85875ff4d86ad39ccff9d4632088713ef8b052af"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: PLAN_APPROVED
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: true
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feature branch feat/CON-002-cursor-batch-evidence-count"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_read_scope: "Neo4j read-only — consolidation candidate batch scan + independent_archive_count aggregation"
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
  - "修改 EXT/RET 已完成阶段生产语义"
  - "修改 CON-001 公式语义"
  - "接线 consolidation_worker / APScheduler / 乐观锁写入"
stop_if:
  - "任何实现步骤需要 Neo4j 写入、ES 同步或 Mongo 读写"
  - "任何实现步骤需要调度器、互斥锁或 evaluation_time 生成"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要修改 consolidation_importance.py 公式"
blocking_open_issues: []
nonblocking_open_issues: []
```

## 2. authoritative_scope

本任务 **仅** 拥有 §2.3.4 巩固候选选择、Cursor 分页、Neo4j 批量 Memory 只读、Evidence `independent_archive_count` 聚合、per-user 隔离、CON-001 输入组装与批次 outcome 编排；**不** 拥有 evaluation_time 生成、调度/锁、Neo4j 写入、HTTP API 或指标落盘。

| 维度 | 归属 CON-002 | 非 CON-002（显式排除） |
|---|---|---|
| 巩固候选 Memory 选择（status / created_time / last_consolidated_time） | **是** — §2.3.4 | — |
| `memory_id` Cursor 分页（`ORDER BY memory_id ASC`） | **是** — §2.3.4 | — |
| Neo4j 批量读 Memory + `count(DISTINCT e.archive_id)` | **是** — §2.3.4 权威 Cypher | — |
| Evidence `user_id = Memory.user_id` 隔离（OPTIONAL MATCH） | **是** — §2.2.12 模式 | retrieval `evidence_count`（RET-004） |
| `independent_archive_count` 运行时聚合（不持久化） | **是** | ES / Mongo 字段 |
| 组装 `ConsolidationImportanceInput` 并调用 `compute_consolidation_importance` | **是** — CON-001 handoff | 修改 CON-001 公式 |
| 批次输出：scored / skip / next_cursor / batch metadata | **是** | CON-003 写入 payload |
| per-user `user_id` 批次上下文 | **是** — §2.3.2 规则 2 | 跨用户合并扫描 |
| `evaluation_time` 生成 | **否** — 调用方注入 | **CON-004** |
| APScheduler / 本地互斥锁 / run_id | **否** | **CON-004** |
| Neo4j 乐观锁批量更新 `importance` / `last_consolidated_time` | **否** | **CON-003** |
| `consolidation_worker` 接线 | **否** | **CON-004**；当前 stub 禁止修改 |
| Consolidation Integration + E2E | **否** | **CON-005** |
| ES importance 同步 | **否** | 阶段非目标 |
| 独立 Consolidation HTTP API | **否** | 阶段非目标 |
| 多实例调度 / 持久化 Cursor | **否** | 阶段非目标 |
| 指标计数器落盘（`missing_evidence_count` 等） | **否** — outcome 返回即可 | **CON-004** |

## 3. input_contract

### 3.1 批次服务入参

调用方（CON-004 调度层，本任务仅定义契约）在每次批次调用前组装：

```text
ConsolidationBatchRequest {
  user_id: str                              # 必填；本批次仅处理该用户的 Memory
  evaluation_time: int                      # 必填；本轮统一评估时间（Unix epoch 秒，≥0）；本任务不生成
  cursor: str | null                        # 上一批 next_cursor；首批为 null
  batch_size: int | None = None             # None → resolve settings.memory_consolidation.batch_size（500）；显式值必须 > 0
}
```
```

**显式禁止由本任务生成或修改的字段**：

- `run_id`、调度触发时间、锁状态 — **CON-004**
- `importance` / `last_consolidated_time` / `memory_version` 写入 — **CON-003**

### 3.2 候选选择契约（candidate_selection_contract）

Neo4j `WHERE` 谓词 **必须**与 §2.3.4 字面一致，并追加 per-user 隔离（§2.3.2 规则 2；§2.2.12 模式）：

```text
MATCH (m:Memory)
WHERE m.user_id = $user_id
  AND m.created_time <= $evaluation_time
  AND (m.last_consolidated_time IS NULL
       OR m.last_consolidated_time < $evaluation_time)
  AND ($cursor IS NULL OR m.memory_id > $cursor)
  AND m.status IN ["active", "conflicted", "superseded"]
```

| 规则 | 说明 |
|---|---|
| CS-1 | 仅 `active` / `conflicted` / `superseded` |
| CS-2 | `created_time <= evaluation_time` |
| CS-3 | `last_consolidated_time IS NULL OR < evaluation_time` |
| CS-4 | `m.user_id = $user_id` — 不得跨用户扫描 |
| CS-5 | 空候选集合为正常结果（返回空 batch，非失败） |

**不**在本任务过滤 `memory_type`；所有符合 status 的 Memory 均为候选。

### 3.3 分页契约（pagination_contract）

| 规则 | 说明 |
|---|---|
| PG-1 | 稳定游标字段：`memory_id`（全局唯一约束） |
| PG-2 | `ORDER BY m.memory_id ASC` |
| PG-3 | `LIMIT $batch_size` |
| PG-4 | 首批：`cursor = null` → `($cursor IS NULL OR m.memory_id > $cursor)` 为真 |
| PG-5 | 后续批：`cursor = 上一批最后一个 memory_id`（严格大于） |
| PG-6 | `next_cursor`：若本批返回 ≥1 条 Memory，取 **最后一条** `memory_id`；若 0 条则为 `null` |
| PG-7 | 本任务 **不**保存持久化 Cursor |
| PG-7b | **CON-004 调用方终止**（本任务仅文档）：`while has_more` 继续分页；满页最后一页后允许 **一次** 后续空读；`memories_returned < batch_size` 或 `memories_returned == 0` 终止；禁止 count-ahead/lookahead |
| PG-8 | 非法 `cursor`（非 `null` 且非非空字符串）→ `ValueError`（批次入参校验；映射见 §9） |
| PG-9 | `batch_size=None` → service 解析为 `settings.memory_consolidation.batch_size`；显式 `batch_size` 必须 `> 0` |

### 3.4 Neo4j 读契约

权威 Cypher（在 §3.2 候选谓词基础上）：

```cypher
MATCH (m:Memory)
WHERE m.user_id = $user_id
  AND m.created_time <= $evaluation_time
  AND (m.last_consolidated_time IS NULL
       OR m.last_consolidated_time < $evaluation_time)
  AND ($cursor IS NULL OR m.memory_id > $cursor)
  AND m.status IN ["active", "conflicted", "superseded"]
OPTIONAL MATCH (e:Evidence)-[:SUPPORTS]->(m)
WHERE e.user_id = m.user_id
RETURN m,
       count(DISTINCT e.archive_id) AS independent_archive_count
ORDER BY m.memory_id ASC
LIMIT $batch_size
```

**CRITICAL — OPTIONAL MATCH 语义**：`e.user_id = m.user_id` 谓词 **必须**置于 `OPTIONAL MATCH` 子句的 `WHERE`（如上），**禁止**放入前置 `MATCH (m:Memory)` 的 `WHERE` 或写成会消除零 Evidence 行的 `MATCH (e:Evidence)`。无 Evidence 的合法 Memory **必须**仍返回一行且 `independent_archive_count = 0` → CON-001 `missing_evidence` skip。

| 规则 | 说明 |
|---|---|
| NR-1 | 单条查询返回 Memory 字段 + `independent_archive_count`；禁止逐条 Evidence 查询 |
| NR-2 | Evidence 隔离：`e.user_id = m.user_id`（OPTIONAL MATCH WHERE）；禁止跨用户 JOIN；零 Evidence 行不得被过滤 |
| NR-2b | 无 Evidence Memory 必须返回且 `independent_archive_count=0`（显式测试 U5/U5b/U5c） |
| NR-3 | 返回行按 `memory_id ASC`；不得客户端重排 |
| NR-4 | Memory 节点 `user_id` 与请求 `user_id` 不一致（脏数据）→ 该行 `invalid_memory_state`，跳过并继续 |
| NR-5 | Neo4j 传输/超时/服务不可用 → `consolidation_read_failed`（整批失败） |
| NR-6 | 记录字段无法映射为 CON-001 所需类型 → 该行 `invalid_memory_state` |
| NR-7 | **零** Neo4j 写语句 |

### 3.5 independent_archive_count 契约（independent_archive_count_contract）

| 规则 | 说明 |
|---|---|
| IC-1 | 语义 = `count(DISTINCT e.archive_id)`，其中 `e` 满足 `SUPPORTS` 且 `e.user_id = m.user_id` |
| IC-2 | 同一 `archive_id` 多条 Evidence（重试/拆分）只计 1 |
| IC-3 | `archive_id IS NULL` 的 Evidence **不计入** distinct 集合（Neo4j `count(DISTINCT null)` 行为 + LD-2 显式文档） |
| IC-4 | 无 Evidence 时 `independent_archive_count = 0`（非错误） |
| IC-5 | **不**写入 Memory 节点；**不同于** retrieval `evidence_count`（Evidence 节点总数） |
| IC-6 | 返回值为非负整数；映射后注入 `ConsolidationImportanceInput.independent_archive_count` |

### 3.6 Memory → CON-001 所需字段映射

从 Neo4j `m` 节点读取并映射（**不**读取 `importance` / `retrieval_count` / `last_retrieved_time` 用于公式）：

| ConsolidationImportanceInput 字段 | Neo4j 来源 | 校验 |
|---|---|---|
| `memory_type` | `m.memory_type` | 四枚举之一 |
| `confidence` | `m.confidence` | float |
| `status` | `m.status` | active/conflicted/superseded |
| `created_time` | `m.created_time` | int ≥ 0 |
| `latest_source_time` | `m.latest_source_time` | int \| null |
| `independent_archive_count` | 查询聚合 | int ≥ 0 |
| `evaluation_time` | 请求注入 | int ≥ 0 |

批次行还须携带 `memory_id`（及可选 `memory_version` 只读透传供 CON-003，本任务 **不写入**）。

## 4. con001_handoff

对批次内每条 **映射成功** 的 Memory 行：

1. 构造 `ConsolidationImportanceInput`（§3.6；**无** `importance` / `retrieval_count` / `last_retrieved_time` / `user_id`）。
2. 调用 `compute_consolidation_importance(input, settings.memory_consolidation)`（**禁止**修改 CON-001 实现语义）。
3. 结果分类：

| CON-001 Outcome | CON-002 批次项 |
|---|---|
| `ConsolidationImportanceSuccess` | `ConsolidationScoredCandidate { memory_id, new_importance, ... }` |
| `ConsolidationImportanceSkip(reason="missing_evidence")` | `ConsolidationSkippedCandidate { memory_id, reason="missing_evidence" }` |
| `ValueError`（非法枚举/负时间等） | `ConsolidationSkippedCandidate { memory_id, reason="invalid_memory_state" }` |

**禁止**：在 handoff 层捕获 `missing_evidence` 后伪造 `new_importance`；禁止读取旧 `importance` 作为 fallback。

## 5. output_contract

```text
ConsolidationBatchResult {
  user_id: str
  evaluation_time: int
  cursor_in: str | null
  batch_size: int
  memories_returned: int                    # 本批 Neo4j 行数（含 skip）
  next_cursor: str | null                   # §3.3 PG-6
  scored: list[ConsolidationScoredCandidate]
  skipped: list[ConsolidationSkippedCandidate]
  has_more: bool                             # memories_returned == batch_size
}

ConsolidationScoredCandidate {
  memory_id: str
  new_importance: float
  memory_version: int                        # 只读透传；供 CON-003
}

ConsolidationSkippedCandidate {
  memory_id: str
  reason: Literal["missing_evidence", "invalid_memory_state"]
}
```

| 规则 | 说明 |
|---|---|
| OC-1 | **无** Neo4j/Mongo/ES 写副作用 |
| OC-2 | `scored` + `skipped` 覆盖本批全部成功映射行（一一对应） |
| OC-3 | 空图 → `memories_returned=0`，`scored=[]`，`skipped=[]`，`next_cursor=null`，`has_more=false` |
| OC-4 | 不返回 CON-003 写入结果或 `version_conflict`（归属 CON-003） |
| OC-5 | 批次元数据可供 CON-004 记录 `scanned_count` / `batch_count`（本任务不落盘指标） |

## 6. user_isolation

| # | 规则 | Enforcement | 测试 ID |
|---|---|---|---|
| UISO-1 | 单次 `ConsolidationBatchRequest` 仅接受一个 `user_id` | 入参契约 | U2, C2 |
| UISO-2 | Cypher `m.user_id = $user_id` | 权威查询 | U2 |
| UISO-3 | Evidence 计数 `e.user_id = m.user_id` | OPTIONAL MATCH WHERE | U2 |
| UISO-4 | 不得 JOIN 其他用户 Memory/Evidence | Cypher + 行级校验 | U2 |
| UISO-5 | 用户 A 的 Evidence 不得计入用户 B 的 Memory | Fixture 双用户 | U2 |
| UISO-6 | `compute_consolidation_importance` 仍无 `user_id` 入参（CON-001 不变） | handoff 契约 | U9, C3 |

## 7. failure_mapping

映射 **仅**使用 §2.3.13 巩固域错误码语义（本任务不暴露 HTTP / 调度词汇）：

| 条件 | 错误码 / 结果 | 批次行为 | 测试 ID |
|---|---|---|---|
| Neo4j 传输失败、超时、`ServiceUnavailable`、`Neo4jError` | `consolidation_read_failed` | 整批失败；抛 `ConsolidationReadError` | U8, F2 |
| 查询返回结构异常（无法解析聚合/count） | `consolidation_read_failed` | 整批失败 | U7, F3 |
| 单条 Memory 缺字段 / 非法枚举 / 负 `created_time` | `invalid_memory_state` | 跳过该行；继续同批其他行 | U6 |
| 单条 `m.user_id != request.user_id` | `invalid_memory_state` | 跳过该行 | U6 |
| `independent_archive_count == 0` | `missing_evidence` | skip outcome；非异常 | U5 |
| `independent_archive_count > 0` 且 CON-001 成功 | —（scored） | 加入 `scored` | U9 |
| 非法 `cursor` 入参（空字符串等） | — | `ValueError`（调用方错误） | U11 |
| 非法 `batch_size <= 0` 或 `evaluation_time < 0` | — | `ValueError` | U11 |
| 乐观锁 / 写入失败 | — | **CON-003** | — |
| 锁 / 调度重入 | — | **CON-004** | — |

异常类型（MVP 本地，与 RET 仓储模式一致）：

- `ConsolidationReadError` — 携带 `retryable: bool`；表示 `consolidation_read_failed`
- `ConsolidationBatchRequestError` — 入参 `ValueError` 包装（可选）

## 8. durable_read_scope / durable_write_scope

```yaml
durable_read_scope: "Neo4j read-only — consolidation_memory_read_repository batch scan"
durable_write_scope: NONE
```

- **允许**：Neo4j `execute_read` 单条批量查询。
- **禁止**：Mongo / ES / Kafka；任何 `CREATE`/`SET`/`MERGE`/`DELETE`；`importance` / `last_consolidated_time` / `memory_version` 更新。

## 9. replay_idempotency

| 场景 | 预期行为 | 测试 ID |
|---|---|---|
| 相同 `user_id` + `evaluation_time` + `cursor` + `batch_size` + 稳定图数据 | 相同行序、相同 `independent_archive_count`、相同 CON-001 outcomes | U10 |
| 重复调用同一批次（无图变更） | 深度相等 `ConsolidationBatchResult`（除非确定性字段无） | U10 |
| 进程重启后相同参数重放 | 与上相同（无进程内 Cursor 状态） | U10 |
| 图数据变更（新增 Evidence） | `independent_archive_count` 与 outcomes 随图变化；确定性对 **快照** 成立 | U10 |
| `evaluation_time` 变化 | 候选集合与 `inactive_days` 可能变化；分别断言 | U10 |

## 10. preserve boundaries

| 边界 | 要求 |
|---|---|
| `consolidation_importance.py`（CON-001） | **禁止**修改公式与输入契约 |
| `consolidation_worker.py` | **禁止**修改 stub |
| `settings/models.py` / `validators.py` | **禁止**修改 Contract |
| `act_r_scoring.py` / RET 模块 | **禁止**修改 |
| EXT-001..009 生产语义 | **禁止**修改 |
| DEV-006 / PR #13 | **永久禁止** |
| APScheduler / 互斥锁 / run loop | **禁止**本任务实现 |
| Neo4j 写入 / ES 同步 | **禁止**（CON-003+） |

## 11. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/consolidation_batch.py` | 创建 | `ConsolidationBatchRequest` / `ConsolidationBatchResult` / Scored / Skipped |
| `src/memory_system/domain/services/consolidation_batch_service.py` | 创建 | 批次编排、CON-001 handoff、入参校验 |
| `src/memory_system/infrastructure/neo4j/consolidation_memory_read_repository.py` | 创建 | §2.3.4 权威 Cypher 只读仓储 |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `consolidation_importance.py`、`consolidation_worker.py`、`settings/`、EXT/RET 已完成文件、DEV-006）。

## 12. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_consolidation_memory_read_repository.py` | 创建 | Neo4j 读契约、隔离、计数、畸形行、读失败 |
| `tests/unit/test_consolidation_batch_service.py` | 创建 | 分页、handoff、skip、replay、零写 |
| `tests/contract/test_con002_scope_boundaries.py` | 创建 | 白名单、无写入、边界 preserve |

**白名单外任何 `tests/**` 变更 → FAIL**（运行 EXT/RET/CON-001 回归但不在白名单内编辑）。

### 12.1 governance_file_whitelist（Release Operator 各 phase）

| Phase | 允许路径 | 目的 |
|---|---|---|
| `PLAN_LANDING` | `02_开发管理/tasks/CON-002-cursor-batch-evidence-count.md` | 已批准 Task Plan |
| `PLAN_LANDING` | `02_开发管理/progress.md` | 规划态登记 |
| `PLAN_LANDING` | `02_开发管理/master_plan.md` | CON-002 规划登记 |
| `IMPLEMENTATION_RELEASE` | §11 production_file_whitelist 全部 | 实现 |
| `IMPLEMENTATION_RELEASE` | §13 test_file_whitelist 全部 | 测试 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/tasks/CON-002-cursor-batch-evidence-count.md` | 执行记录 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/progress.md` | 状态登记 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/master_plan.md` | 状态备注 |
| `POST_MERGE_CLEANUP` | 上述三份治理文件 | 完成登记 |

### 12.2 PLAN_LANDING commit contract

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含：

1. `02_开发管理/tasks/CON-002-cursor-batch-evidence-count.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`

Commit message（精确）：

```text
docs(plan): add CON-002 cursor batch evidence count plan
```

随后从更新后的 `main` 创建 exact feature branch `feat/CON-002-cursor-batch-evidence-count`。

## 13. minimum_test_plan

### 13.1 Unit Test — Repository（`test_consolidation_memory_read_repository.py`）

| ID | 场景 | 预期 |
|---|---|---|
| U1 | Cursor 分页：null cursor 首批 → `next` cursor 第二批 → 空批 | 严格 `memory_id ASC`；LIMIT；`next_cursor` 正确 |
| U2 | 用户隔离：用户 A Memory + 用户 B Evidence 同 archive | B 的 Evidence 不计入 A 的 count |
| U3 | `independent_archive_count`：3 个不同 `archive_id` | count = 3 |
| U4 | 去重：同一 `archive_id` 2 条 Evidence | count = 1 |
| U5 | 零 Evidence（OPTIONAL MATCH 仍返回 Memory 行） | `independent_archive_count = 0`；行不被过滤 |
| U5c | 零 Evidence + 其他用户 Evidence 存在 | 仍返回 Memory；count=0；非跨用户计入 |
| U6 | 畸形 Memory（缺 `memory_type` / 非法 status） | 行级 `invalid_memory_state` 信号（或映射异常供 service 转换） |
| U7 | 畸形聚合结果 / 缺 `independent_archive_count` 列 | `ConsolidationReadError` → `consolidation_read_failed` |
| U8 | Neo4j 抛 `ServiceUnavailable` | `ConsolidationReadError(retryable=True)` |
| U11 | 非法 cursor（`""`）在 service 层 | `ValueError` |

### 13.2 Unit Test — Service（`test_consolidation_batch_service.py`）

| ID | 场景 | 预期 |
|---|---|---|
| U9 | CON-001 handoff：合法行 + count>0 | 精确 `ConsolidationImportanceInput` 字段；`scored` 含 `new_importance` |
| U5b | count=0 | `skipped[missing_evidence]`；无 `new_importance` |
| U6b | CON-001 `ValueError` 路径 | `skipped[invalid_memory_state]` |
| U10 | 相同请求重复执行 | 深度相等 `ConsolidationBatchResult` |
| U12 | `batch_size=None` 解析 settings 默认 500 | 显式 `batch_size=100` 使用 100 |
| U13 | Service `next_cursor` / `has_more`：空页 | `next_cursor=null`，`has_more=false` |
| U14 | Service `next_cursor` / `has_more`：部分页 | `next_cursor=末行 id`，`has_more=false` |
| U15 | Service `next_cursor` / `has_more`：满页 | `next_cursor=末行 id`，`has_more=true` |
| F1 | 任意成功批次 | 零 Neo4j 写（mock driver 无 write API 调用） |
| F2 | 读失败注入 | 整批 `ConsolidationReadError`；无 partial scored |
| F3 | 部分畸形 + 部分合法 | 合法行仍 scored/skip；畸形行 skipped |

### 13.3 Contract Test（`test_con002_scope_boundaries.py`）

| ID | 场景 | 预期 |
|---|---|---|
| C1 | 白名单外无 `src/**` 生产变更 | git diff 门禁 |
| C2 | Cypher 含完整 §3.2/§3.4 谓词：`m.user_id`、`created_time`、`last_consolidated_time`、`status IN`、`cursor`、`ORDER BY memory_id ASC`、`LIMIT`、OPTIONAL MATCH `e.user_id = m.user_id` | 静态断言 authorized query 全文 |
| C3 | 不修改 `consolidation_importance.py` / `consolidation_worker.py` / `settings/` / RET 模块 | diff 断言 |
| C4 | `ConsolidationImportanceInput` handoff 无 `importance` / `retrieval_count` | 字段断言 |
| C5 | `durable_write_scope=NONE` | 无 write repository / mutation Cypher |

### 13.4 Integration Test

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — 真实 Neo4j Fixture 全链路归属 **CON-005**；本任务 Unit 使用 mock/fake driver |

### 13.5 E2E Test

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — **CON-005** |

### 13.6 失败注入与并发

| ID | 场景 | 预期 |
|---|---|---|
| F1 | 批次成功 | 零 durable write |
| F2 | Neo4j 读失败 | `consolidation_read_failed`；无伪造候选 |
| F4 | 并发 10 路相同只读批次（mock） | 无异常；结果一致 |

## 14. NORMAL classification（HARD_BLOCK / SAFE_AUTO / MVP_LOCAL / DEFERRED）

| ID | 项 | 分类 | 说明 |
|---|---|---|---|
| CL-1 | Cypher 谓词与 §2.3.4 不一致 | **HARD_BLOCK** | 规格唯一权威 |
| CL-2 | 跨用户 Evidence 计入 count | **HARD_BLOCK** | §2.3.2 规则 2 |
| CL-3 | Cursor 乱序或游标语义错误 | **HARD_BLOCK** | 死循环 / 漏扫风险 |
| CL-4 | `independent_archive_count` 与 `evidence_count` 混用 | **HARD_BLOCK** | §2.3.4 字面区分 |
| CL-5 | 修改 CON-001 公式或输入契约 | **HARD_BLOCK** | CON-001 已完成 |
| CL-6 | Neo4j 写 / `importance` 更新 | **HARD_BLOCK** | CON-003 |
| CL-7 | 调度器 / Worker 接线 | **HARD_BLOCK** | CON-004 |
| CL-8 | 测试未覆盖分页/隔离/计数/去重/skip/失败/handoff/replay/零写 | **HARD_BLOCK** | 用户明确要求 |
| CL-9 | 修改 Settings Contract | **HARD_BLOCK** | dependency_changes_expected=NONE |
| CL-10 | DEV-006 / PR #13 | **HARD_BLOCK** | 治理永久禁止 |
| CL-11 | `neo4j_timeout_seconds` 只读注入自 `memory_retrieval` | **SAFE_AUTO_REMEDIATION** | LD-1；与 RET 仓储一致 |
| CL-12 | 拆分 models / service / repository 三文件 | **SAFE_AUTO_REMEDIATION** | 与 RET-003/004 结构一致 |
| CL-13 | `archive_id IS NULL` 不计入 distinct | **MVP_LOCAL_DECISION** | LD-2 |
| CL-14 | 单条畸形 skip 继续同批 | **MVP_LOCAL_DECISION** | LD-3；§2.3.13 规则 4 |
| CL-15 | `memory_version` 只读透传 | **MVP_LOCAL_DECISION** | LD-4；供 CON-003 |
| CL-16 | Integration Neo4j Fixture | **DEFERRED** | CON-005 |
| CL-17 | 乐观锁批量写 | **DEFERRED** | CON-003 |
| CL-18 | APScheduler / mutex / recovery | **DEFERRED** | CON-004 |
| CL-19 | Consolidation E2E | **DEFERRED** | CON-005 |
| CL-20 | ES importance 同步 | **DEFERRED** | 阶段非目标 |
| CL-21 | 多实例 / 持久化 Cursor | **DEFERRED** | §2.3.4 明确非 MVP |

## 15. deferred_for_mvp（本任务显式不交付）

- CON-003：乐观锁批量更新 `importance` / `last_consolidated_time`
- CON-004：APScheduler、本地互斥锁、`evaluation_time`/`run_id` 生成、失败恢复、指标落盘
- CON-005：Consolidation Integration + E2E（含真实 Neo4j 全链路）
- ES importance 同步；独立 Consolidation HTTP API
- 多实例调度、Redis 分布式锁、持久化 Cursor
- `consolidation_worker` 启动与调度接线
- 修改 `MemoryConsolidationSettings` / validators
- 修改 CON-001 纯函数语义

## 16. mvp_local_decisions

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | Neo4j 超时使用 `settings.memory_retrieval.neo4j_timeout_seconds` 注入 repository | `MemoryConsolidationSettings` 无独立 timeout；与 RET 仓储一致；不改 Contract |
| LD-2 | `archive_id IS NULL` 的 Evidence 不计入 `independent_archive_count` | `count(DISTINCT null)` 为 0；脏数据不虚假抬高 evidence_score |
| LD-3 | 单条 Memory 映射失败 → `invalid_memory_state` skip，不失败整批 | §2.3.13 规则 4；与巩固写入阶段一致 |
| LD-4 | `ConsolidationScoredCandidate` 透传 `memory_version`（只读） | CON-003 乐观锁需要；本任务不校验版本 |
| LD-5 | 入参 `batch_size: int | None = None`；`None` → `settings.memory_consolidation.batch_size`；显式值须 `> 0` | §2.3.12 默认 500；吸收 SF-1 |
| LD-6 | Repository 返回中间类型 `ConsolidationMemoryRow`（含 `memory_id` + 原始字段 + count） | Service 层负责 CON-001 handoff 与 skip 分类 |

## 17. open_issues

- `02_开发管理/open_issues.md`：**无** blocking CON-002 的 open issue。
- `blocking_open_issues: []`；`nonblocking_open_issues: []`。

## 18. 任务目标

交付 §2.3.4 巩固候选 **Cursor 分页批量 Neo4j 只读**：按 `user_id` 隔离扫描 eligible Memory，聚合 `independent_archive_count`，组装 CON-001 输入并输出 scored/skip 批次结果与 `next_cursor`；**零** durable 写入；为 CON-003 写入与 CON-004 调度提供唯一批量读实现。

可验证目标：

1. **`ConsolidationMemoryReadRepository`** — 权威 Cypher + user_id/Evidence 隔离。
2. **`ConsolidationBatchService`** — 分页编排 + CON-001 handoff + 批次 outcome。
3. **契约** — 输入/输出字段与 §2.3.4 / CON-001 完全一致；无旧 `importance` 参与计算。
4. **测试** — U1..U12 + F1..F4 + C1..C5 全部通过。
5. Ruff / Mypy 通过；Review 无 P0/P1。

## 19. 非目标与黑名单（must_not）

- `evaluation_time` / `run_id` 生成 — **CON-004**。
- APScheduler、互斥锁、`consolidation_worker` 接线 — **CON-004**；**禁止**修改 `consolidation_worker.py`。
- Neo4j 批量写入 / 乐观锁 — **CON-003**。
- Consolidation E2E / 真实 Neo4j Integration — **CON-005**。
- ES / Mongo / Kafka 读写。
- 修改 `consolidation_importance.py`（CON-001）。
- 修改 `MemoryConsolidationSettings` / validators。
- 修改 RET / EXT 已完成生产语义。
- DEV-006 / PR #13 — **永久禁止**。

## 20. 当前代码状态

- **已存在**：`compute_consolidation_importance` + `ConsolidationImportanceInput`（CON-001，PR #50）；`MemoryConsolidationSettings.batch_size=500`；RET Neo4j 只读仓储模式（user_id 隔离、timeout、错误类型）；`consolidation_worker.py` refusal-only stub。
- **可复用**：CON-001 纯函数；`memory_retrieval.neo4j_timeout_seconds`；Fake/mock driver 测试模式（RET unit tests）。
- **当前缺失**：巩固批量读 domain models、batch service、consolidation Neo4j read repository、对应 unit/contract 测试。
- **与技术规格不一致之处**：无（规划基线 clean @ `85875ff`）；§2.3.4 批量读尚未实现。
- **前置任务检查**：CON-001 completed（PR #50 MERGED）；EXT-001..009 completed；RET-001..006 completed。

## 21. 实现方案

### Step 1 — 领域模型

- **文件**：`src/memory_system/domain/models/consolidation_batch.py`
- **类型**：`ConsolidationBatchRequest`；`ConsolidationBatchResult`；`ConsolidationScoredCandidate`；`ConsolidationSkippedCandidate`；`ConsolidationMemoryRow`（repository → service 中间行）；`SkipReason = Literal["missing_evidence", "invalid_memory_state"]`
- **输入/输出**：§3.1、§5
- **错误处理**：frozen dataclass；入参校验在 service
- **幂等/并发**：不可变模型；无状态

### Step 2 — Neo4j 只读仓储

- **文件**：`src/memory_system/infrastructure/neo4j/consolidation_memory_read_repository.py`
- **类**：`ConsolidationMemoryReadRepository`；`ConsolidationReadError`；`ConsolidationMemoryGraphDataError`
- **方法**：`async def fetch_candidate_batch(user_id, evaluation_time, cursor, batch_size) -> list[ConsolidationMemoryRow]`
- **构造**：`ConsolidationMemoryReadRepository(driver, *, neo4j_timeout_seconds: float)` — 由调用方从 `settings.memory_retrieval.neo4j_timeout_seconds` 注入；**禁止**全局可变 settings
- **Cypher**：§3.4 权威查询；`authorized_read_cypher_queries()` 供契约测试
- **错误处理**：§7 failure_mapping；Neo4j 异常 → `ConsolidationReadError`
- **幂等/并发**：只读；相同参数确定性行序

### Step 3 — 批次服务与 CON-001 handoff

- **文件**：`src/memory_system/domain/services/consolidation_batch_service.py`
- **类/函数**：`async def process_batch(request, settings: AppSettings) -> ConsolidationBatchResult`（或注入 `MemoryConsolidationSettings` + repository）；`batch_size=None` 时解析 `settings.memory_consolidation.batch_size`
- **流程**：校验入参 → repository 读 → 逐行映射 → `compute_consolidation_importance` → 聚合 scored/skipped → 计算 `next_cursor` / `has_more`
- **错误处理**：读失败向上抛；单行映射/公式 `ValueError` → `invalid_memory_state`；`missing_evidence` → skip
- **幂等/并发**：无共享可变状态；依赖 repository 确定性

### Step 4 — 单元与契约测试

- **文件**：§12 test_file_whitelist
- **覆盖**：§13 minimum_test_plan（U1..U12、F1..F4、C1..C5）
- **Mock 策略**：内存 fake Neo4j records / mock `AsyncDriver`；不启动真实 Neo4j

## 22. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/consolidation_batch.py` | 创建 | 批次请求/结果契约 |
| `src/memory_system/domain/services/consolidation_batch_service.py` | 创建 | 批次编排 + CON-001 handoff |
| `src/memory_system/infrastructure/neo4j/consolidation_memory_read_repository.py` | 创建 | §2.3.4 Neo4j 只读 |
| `tests/unit/test_consolidation_memory_read_repository.py` | 创建 | 读契约与计数 |
| `tests/unit/test_consolidation_batch_service.py` | 创建 | 分页/handoff/replay |
| `tests/contract/test_con002_scope_boundaries.py` | 创建 | 白名单与边界 |

## 23. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 只读单查询；无事务写入 |
| 幂等 | 适用 | 相同图快照 + 相同请求 → 相同结果；§9 |
| 并发 | 适用 | 无共享可变状态；F4 并发只读 |
| 版本冲突 | 不适用 | 只读 `memory_version`；写入归属 CON-003 |
| 用户隔离 | 适用 | Cypher + 行级校验；§6 |
| 部分失败 | 适用 | 单行 skip；读失败整批失败；§7 LD-3 |
| 进程异常恢复 | 不适用 | 无持久化 Cursor 状态（CON-004 重新扫描） |

## 24. 测试计划（模板 §8 映射）

### Unit Test — 见 §13.1、§13.2

### Contract Test — 见 §13.3

### Integration Test — **DEFERRED**（§13.4）

### E2E Test — **DEFERRED**（§13.5）

### 失败注入与并发 — 见 §13.6

## 25. 验收标准

- [ ] `pytest tests/unit/test_consolidation_memory_read_repository.py tests/unit/test_consolidation_batch_service.py tests/contract/test_con002_scope_boundaries.py` 全部通过
- [ ] U1 Cursor 分页、`next_cursor`、`ORDER BY memory_id ASC` 断言通过
- [ ] U2 用户隔离：跨用户 Evidence 不计入
- [ ] U3/U4 `independent_archive_count` 正确计数与去重
- [ ] U5/U5b `independent_archive_count=0` → `missing_evidence` skip
- [ ] U6/U6b 畸形 Memory → `invalid_memory_state` skip
- [ ] U7/U8 Neo4j 读失败 → `consolidation_read_failed`
- [ ] U9 CON-001 handoff 字段精确（无 `importance` / `retrieval_count`）
- [ ] U10 重放确定性
- [ ] F1 零 durable write
- [ ] C1..C5 白名单与边界契约通过
- [ ] Ruff 通过
- [ ] Mypy 通过（新增文件）
- [ ] Review 无 P0/P1

## 26. 风险与阻塞项

- **设计文档冲突**：无；§2.3.4 Cypher 与用户隔离追加与 §2.2.12 / §2.3.2 一致。
- **当前代码冲突**：无；CON-001 已完成且契约稳定。
- **前置任务**：CON-001 PR #50 MERGED；EXT/RET 阶段 closed。
- **未批准依赖**：`dependency_changes_expected=NONE`。
- **API/Schema 变化**：无 HTTP；内部 dataclass + repository。
- **其他风险**：`independent_archive_count` 与 retrieval `evidence_count` 混淆 — 通过命名与 C4/C5 测试隔离。

## 27. Git 计划

```yaml
branch: "feat/CON-002-cursor-batch-evidence-count"
expected_commits:
  - "docs(plan): add CON-002 cursor batch evidence count plan"
  - "feat(con): add consolidation cursor batch read and evidence count"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "consolidation_worker.py"
  - "consolidation_importance.py（CON-001 公式）"
  - "settings/models.py / validators.py"
  - "act_r_scoring.py / retrieval 模块"
  - "Neo4j 写入 / ES 同步 / Scheduler"
  - "CON-003..005 范围"
```

## 28. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：2026-08-13
- 原计划：初版 CON-002 plan（AWAIT_PLAN_REVIEW）
- 修改内容：吸收人工 PLAN_APPROVED + SF-1..SF-5：`batch_size: int | None = None`；OPTIONAL MATCH 零 Evidence 显式契约；C2 完整谓词断言；U13-U15 service 分页元数据测试；async/settings 注入显式；CON-004 循环终止文档（PG-7b）
- 修改原因：人工批准；Plan Review SHOULD_FIX 无需二次审查
- 是否影响技术规格：**否**（澄清与测试加强）
- 审批状态：**PLAN_APPROVED**（人工 2026-08-13）

## 29. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 10:37 UTC | planning | 创建 Task Plan；同步 progress/master_plan | N/A（规划-only） | baseline `85875ff` verified；`approval_posture=AWAIT_PLAN_REVIEW`；Developer NOT authorized |
| 2026-08-13 10:50 UTC | plan_amendment_001 | 人工 PLAN_APPROVED；吸收 SF-1..SF-5 | N/A | `approval_posture=PLAN_APPROVED`；Developer authorized；Release Operator PLAN_LANDING next |

## 30. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
|  |  |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit |  |  |
| Contract |  |  |
| Integration |  |  |
| E2E |  |  |
| Ruff |  |  |
| Mypy |  |  |

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
