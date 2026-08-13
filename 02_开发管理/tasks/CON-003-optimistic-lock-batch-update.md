# CON-003 乐观锁批量更新

## 1. 任务信息

```yaml
task_id: CON-003
task_name: 乐观锁批量更新
status: planned
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "cabcc6f98e5cd676b962b49e3b0c943587a11689"
branch: "feat/CON-003-optimistic-lock-batch-update"
created_at: "2026-08-13 11:30 UTC"
updated_at: "2026-08-13 11:30 UTC"
spec_sections:
  - "§2.1.9 Neo4j 记忆图谱数据模型（Memory 字段；user_id 隔离；memory_version 由萃取维护）"
  - "§2.3.2 MVP 范围与基本规则（规则 2、4、6、7 — 用户隔离、仅改 importance/last_consolidated_time、统一 evaluation_time）"
  - "§2.3.3 Memory 字段补充（importance / last_consolidated_time / memory_version 只读引用；不得改 updated_time）"
  - "§2.3.4 调度、互斥与批量扫描（规则 3–4 — 空写跳过、版本冲突不阻塞 Cursor；本任务仅实现写侧，不实现调度/Cursor）"
  - "§2.3.9 Neo4j 批量更新与并发控制（本任务唯一权威范围 — 乐观锁 Cypher、批次事务、version_conflict_count）"
  - "§2.3.10 与萃取和检索模块的协作（巩固不增 memory_version；ES 不同步 importance）"
  - "§2.3.13 失败处理与恢复（consolidation_write_failed；部分成功；版本冲突非整任务失败）"
  - "§2.3.14 MVP 实现边界（乐观并发校验 + Neo4j 批量更新 importance/last_consolidated_time）"
prerequisites:
  formal:
    - "CON-002 — SATISFIED/completed（PR #51 MERGED）；ConsolidationScoredCandidate 透传 memory_version；零 durable write"
    - "CON-001 — SATISFIED/completed（PR #50 MERGED）；new_importance 由 compute_consolidation_importance 产出"
    - "EXT-001..009 — SATISFIED/completed"
    - "RET-001..006 — SATISFIED/completed（v0.4.0-memory-retrieval closed）"
  implementation_reuse:
    - "ConsolidationScoredCandidate（consolidation_batch.py）— CON-002 handoff 输入；禁止修改 CON-002 读语义"
    - "RetrievalStatisticsRepository / ConsolidationMemoryReadRepository — Neo4j execute_write/timeout/错误模式"
    - "MemoryRetrievalSettings.neo4j_timeout_seconds（只读注入 Neo4j 超时；禁止修改 Settings Contract）"
  baseline_evidence:
    branch: "main"
    head: "cabcc6f98e5cd676b962b49e3b0c943587a11689"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=cabcc6f98e5cd676b962b49e3b0c943587a11689"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: PLAN_APPROVED
  amendment_recorded: true
  human_plan_approved: true
  developer_authorized: false
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feature branch feat/CON-003-optimistic-lock-batch-update"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_read_scope: NONE
durable_write_scope: "Neo4j Memory only — importance, last_consolidated_time"
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
  - "修改 CON-001 公式语义 / CON-002 读语义"
  - "接线 consolidation_worker / APScheduler / 调度循环 / 指标落盘"
stop_if:
  - "任何实现步骤需要 memory_version 递增或 updated_time 写入"
  - "任何实现步骤需要 ES / Mongo / Kafka 同步"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要修改 consolidation_importance.py / consolidation_batch_service.py 读路径"
blocking_open_issues: []
nonblocking_open_issues: []
```

## 2. authoritative_scope

本任务 **仅** 拥有 §2.3.9 Neo4j 乐观锁批量写入：`importance`（来自 `new_importance`）与 `last_consolidated_time`（= 调用方 `evaluation_time`）；批次事务语义；`version_conflict_count`；用户隔离；预 Cypher 畸形行跳过；**不** 拥有调度、读批次、公式、ES 同步或 `memory_version` 变更。

| 维度 | 归属 CON-003 | 非 CON-003（显式排除） |
|---|---|---|
| 持久化 `new_importance` → `importance` | **是** — §2.3.9 | — |
| 持久化 `last_consolidated_time = evaluation_time` | **是** — §2.3.9 | 调用方生成 `evaluation_time` — **CON-004** |
| 乐观锁 `expected_memory_version` 谓词（READ/CHECK） | **是** — §2.3.9 规则 1–3 | `memory_version` **递增** — 萃取 only |
| 单批 Neo4j write transaction | **是** — §2.3.9 规则 5–7 | — |
| 版本冲突行跳过、批次内部分成功 | **是** — §2.3.9 规则 6；§2.3.13 规则 3–4 | 整任务失败归因 — **CON-004** |
| 空写数组跳过 transaction | **是** — §2.3.9 规则 7 | — |
| 预 Cypher `invalid_candidate` 校验与跳过 | **是** — §2.3.13 规则 4 | — |
| 消费 CON-002 `scored` 行作为写输入 | **是** — handoff | CON-002 `skipped` **禁止**写入 |
| `updated_time` 不变 | **是** — §2.3.3 | 任何 `updated_time` SET — **禁止** |
| `memory_version` 不变 | **是** — §2.3.9 规则 4 | 萃取递增语义 — **禁止本任务触碰** |
| Cursor 分页 / 候选扫描 / Evidence 计数 | **否** | **CON-002**（已完成） |
| `compute_consolidation_importance` | **否** | **CON-001**（已完成） |
| APScheduler / 互斥锁 / run_id / cursor 循环 | **否** | **CON-004** |
| 指标计数器落盘（`version_conflict_count` 等） | **否** — outcome 返回即可 | **CON-004** |
| ES importance 同步 | **否** — §2.3.10 | 阶段非目标 |
| `consolidation_worker` 接线 | **否** | **CON-004** |
| Consolidation Integration + E2E | **否** | **CON-005** |
| 独立 Consolidation HTTP API | **否** | 阶段非目标 |

## 3. input_contract

### 3.1 批次写服务入参

调用方（CON-004 调度层，本任务仅定义契约）在每次写批次调用前组装。**仅**接受 CON-002 `scored` 行；`skipped` 不得进入写路径。

```text
ConsolidationWriteBatchRequest {
  user_id: str                              # 必填；本批次所有行归属该用户
  evaluation_time: int                      # 必填；本轮统一评估时间（Unix epoch 秒，≥0）；写入 last_consolidated_time
  rows: list[ConsolidationWriteRow]         # 可为空；来自 ConsolidationScoredCandidate 映射
}

ConsolidationWriteRow {
  memory_id: str
  new_importance: float                     # CON-001 产出；持久化为 importance
  expected_memory_version: int              # 来自 CON-002 ConsolidationScoredCandidate.memory_version
}
```

**CON-002 → CON-003 映射**（调用方或 service 适配层）：

| CON-002 字段 | CON-003 字段 |
|---|---|
| `ConsolidationScoredCandidate.memory_id` | `ConsolidationWriteRow.memory_id` |
| `ConsolidationScoredCandidate.new_importance` | `ConsolidationWriteRow.new_importance` |
| `ConsolidationScoredCandidate.memory_version` | `ConsolidationWriteRow.expected_memory_version` |
| `ConsolidationBatchResult.user_id` | `ConsolidationWriteBatchRequest.user_id` |
| `ConsolidationBatchResult.evaluation_time` | `ConsolidationWriteBatchRequest.evaluation_time` |

**显式禁止由本任务生成或修改的字段**：

- `run_id`、调度触发时间、锁状态 — **CON-004**
- `memory_version` 递增 — **萃取模块**
- `updated_time` — **禁止任何写入**
- CON-002 `skipped` 行 — **禁止**进入 `rows`

### 3.2 入参校验契约（pre_cypher_validation_contract）

| 规则 | 说明 |
|---|---|
| PV-1 | `user_id` 非空字符串 |
| PV-2 | `evaluation_time >= 0` |
| PV-3 | `rows` 可为空列表 |
| PV-4 | 每行 `memory_id` 非空字符串 |
| PV-5 | 每行 `expected_memory_version` 为 `int` 且 `>= 1`（非 bool） |
| PV-6 | 每行 `new_importance` 为有限 `float`，且 `0.0 <= new_importance <= 1.0`（与 CON-001 clamp 一致） |
| PV-7 | 同批 `memory_id` 重复 → 后者标 `invalid_candidate`（保留首次有效行） |
| PV-8 | 未通过 PV-4..PV-7 的行 → `invalid_candidate`；**不**进入 Cypher `$rows` |
| PV-9 | 校验失败行不导致整批抛异常（除非 request 级 PV-1/PV-2 违反 → `ValueError`） |

### 3.3 Neo4j 写契约（authoritative Cypher — §2.3.9）

Repository 将请求级 `user_id` 注入每行后执行：

```cypher
UNWIND $rows AS row
MATCH (m:Memory {memory_id: row.memory_id})
WHERE m.user_id = row.user_id
  AND m.memory_version = row.expected_memory_version
SET m.importance = row.importance,
    m.last_consolidated_time = $evaluation_time
RETURN count(m) AS updated_count
```

Cypher 参数：

| 参数 | 来源 |
|---|---|
| `$rows[].memory_id` | `ConsolidationWriteRow.memory_id` |
| `$rows[].user_id` | `ConsolidationWriteBatchRequest.user_id`（每行注入） |
| `$rows[].expected_memory_version` | `ConsolidationWriteRow.expected_memory_version` |
| `$rows[].importance` | `ConsolidationWriteRow.new_importance` |
| `$evaluation_time` | `ConsolidationWriteBatchRequest.evaluation_time` |

| 规则 | 说明 |
|---|---|
| NW-1 | **仅**字段级 `SET`；禁止整节点覆盖（`SET m = row` / `REMOVE` / `DELETE`） |
| NW-2 | **禁止** `SET m.memory_version`、`SET m.updated_time` 或任何 §2.3.2 规则 5 列出的内容/状态字段 |
| NW-3 | `WHERE` 必须同时包含 `memory_id`、`user_id`、`expected_memory_version` |
| NW-4 | 单批单次 `execute_write` transaction |
| NW-5 | `valid_rows` 为空时 **不**调用 `execute_write`（`write_executed=false`） |
| NW-6 | Neo4j 传输/超时/`Neo4jError` → 整批回滚 → `consolidation_write_failed` |
| NW-7 | 批内版本冲突：transaction **成功**；`updated_count < len(valid_rows)`；差值 = `version_conflict_count` |
| NW-8 | 不存在 Memory 或 `user_id` 不匹配或版本不匹配 → 该行不计入 `updated_count`（视为 version_conflict 语义，不单独区分 missing node） |

## 4. con002_handoff

### 4.1 输入边界

1. **仅** `ConsolidationBatchResult.scored` 可映射为写请求 `rows`。
2. `ConsolidationBatchResult.skipped`（`missing_evidence` / `invalid_memory_state`）**永远不得**传入写服务。
3. `memory_version` 自 CON-002 只读透传为 `expected_memory_version`；本任务不重新读取 Neo4j 校验版本（乐观锁在写 Cypher 完成）。
4. 本任务 **不**调用 `ConsolidationBatchService` 或 `compute_consolidation_importance`。

### 4.2 与 CON-002 读过滤的协作语义

- CON-002 候选谓词：`last_consolidated_time IS NULL OR < evaluation_time`。
- 成功写入后 `last_consolidated_time = evaluation_time` → 同轮 `evaluation_time` 重扫不会再次选中该行（CON-004 负责循环；本任务仅保证写后字段正确）。
- 版本冲突行 **不**更新 `last_consolidated_time`（§2.3.9 规则 3）→ 后续轮次可重新读取计算。

## 5. output_contract

```text
ConsolidationWriteBatchResult {
  user_id: str
  evaluation_time: int
  input_count: int                          # len(request.rows)
  valid_count: int                           # 通过 PV 校验、进入 Cypher 的行数
  updated_count: int                        # Neo4j RETURN count(m)；空写时为 0
  version_conflict_count: int               # valid_count - updated_count（空写时为 0）
  invalid_candidates: list[ConsolidationInvalidWriteCandidate]
  write_executed: bool                       # 是否实际执行了 execute_write
}

ConsolidationInvalidWriteCandidate {
  memory_id: str
  reason: Literal["invalid_candidate"]      # MVP 本地细分可含 duplicate_memory_id / invalid_version / invalid_importance / empty_memory_id
}
```

| 规则 | 说明 |
|---|---|
| OC-1 | `version_conflict_count = valid_count - updated_count`；**不**抛异常、**不**映射为 `consolidation_write_failed` |
| OC-2 | `input_count = len(rows)`；`invalid_candidates` 与 PV 跳过一一对应 |
| OC-3 | 空 `rows` 或全部 invalid → `write_executed=false`，计数全 0 |
| OC-4 | 成功写后 **不**返回新 `memory_version`（巩固不递增） |
| OC-5 | **不**落盘指标；供 CON-004 聚合 `updated_count` / `version_conflict_count` |
| OC-6 | **无** ES / Mongo / Kafka 副作用 |

## 6. user_isolation

| # | 规则 | Enforcement | 测试 ID |
|---|---|---|---|
| UISO-1 | 单次写请求仅接受一个 `user_id` | 入参契约 | U2, C2 |
| UISO-2 | Cypher `m.user_id = row.user_id` 且 `row.user_id` 来自请求级 | 权威查询 | U2 |
| UISO-3 | 用户 B 的 Memory 不得被用户 A 的请求更新 | Fixture / mock 断言 | U2 |
| UISO-4 | `memory_id` 全局唯一但写仍须 `user_id` 双谓词 | Cypher WHERE | U2, C3 |
| UISO-5 | 跨用户同 `memory_id`（脏数据场景）不得误更新 | mock 行级 | U2 |

## 7. failure_mapping

映射 **仅**使用 §2.3.13 巩固域错误码语义（本任务不暴露 HTTP / 调度词汇）：

| 条件 | 错误码 / 结果 | 批次行为 | 测试 ID |
|---|---|---|---|
| Neo4j 传输失败、超时、`ServiceUnavailable`、`Neo4jError` | `consolidation_write_failed` | 整批回滚；抛 `ConsolidationWriteError` | U8, F2 |
| Cypher 返回结构异常（缺 `updated_count`） | `consolidation_write_failed` | 整批失败 | U7, F3 |
| 批内 `memory_version` 不匹配 / 节点不存在 / user 不匹配 | `version_conflict`（聚合） | transaction 成功；该行不更新 | U3, U4 |
| 预 Cypher 畸形行 | `invalid_candidate` | 跳过该行；其余继续 | U12, U13, U19, U20 |
| `valid_count=0` | —（空写跳过） | 不执行 transaction | U14, U15 |
| 非法 request（`evaluation_time < 0`） | — | `ValueError` | U11 |
| 非法 request（空 `user_id`） | — | `ValueError`；无 Neo4j write | U18 |
| 读失败 / 公式 skip | — | **CON-002 / CON-001** | — |
| 调度 / 锁重入 | — | **CON-004** | — |

异常类型（MVP 本地，与 CON-002 / RET 仓储模式一致）：

- `ConsolidationWriteError` — 携带 `retryable: bool`；表示 `consolidation_write_failed`

## 8. durable_read_scope / durable_write_scope

```yaml
durable_read_scope: NONE
durable_write_scope: "Neo4j Memory — SET importance, last_consolidated_time only"
```

- **允许**：Neo4j `execute_write` 单条批量 Cypher（§3.3）。
- **禁止**：Mongo / ES / Kafka；`memory_version` / `updated_time` / 内容字段 / 关系变更；整节点覆盖。

## 9. replay_idempotency

| 场景 | 预期行为 | 测试 ID |
|---|---|---|
| 巩固写 **不**递增 `memory_version` | 成功写后同 `expected_memory_version` 仍匹配 | U9 |
| 调用方用相同 `rows` 重放写请求（图无萃取变更） | transaction 再次成功；`importance` 可重写为相同值 | U9 |
| 萃取在写后递增 `memory_version` | 同 `expected_memory_version` 重放 → `version_conflict`；节点不被覆盖 | U3 |
| 新 `evaluation_time` 轮次（CON-004） | CON-002 重新选中；公式确定性重算（§2.3.13 规则 5） | 文档级；Integration **CON-005** |
| 写失败整批回滚 | 已提交的前序批次不受影响（§2.3.13 规则 3） | F2（mock）；多批编排 **CON-004** |
| 同轮 `evaluation_time` 写成功后 CON-002 重扫 | 该行 `last_consolidated_time = evaluation_time` 不再入选 | 文档级（CON-002 读谓词；非本任务单测） |

## 10. preserve boundaries

| 边界 | 要求 |
|---|---|
| `consolidation_importance.py`（CON-001） | **禁止**修改 |
| `consolidation_batch_service.py` / `consolidation_memory_read_repository.py`（CON-002） | **禁止**修改读语义 |
| `consolidation_batch.py` | **禁止**修改既有 CON-002 契约类型（可新增 import 引用 ScoredCandidate，但不得改字段） |
| `consolidation_worker.py` | **禁止**修改 stub |
| `settings/models.py` / `validators.py` | **禁止**修改 Contract |
| `graph_write_repository.py` / 萃取写路径 | **禁止**修改 |
| EXT-001..009 / RET 已完成生产语义 | **禁止**修改 |
| DEV-006 / PR #13 | **永久禁止** |
| APScheduler / 互斥锁 / run loop | **禁止**本任务实现 |
| ES / Mongo / Kafka | **禁止** |

## 11. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/consolidation_write.py` | 创建 | `ConsolidationWriteBatchRequest` / `Result` / `ConsolidationWriteRow` / `ConsolidationInvalidWriteCandidate` |
| `src/memory_system/domain/services/consolidation_write_service.py` | 创建 | 入参校验、CON-002 handoff 适配、`valid_rows` 编排、结果聚合 |
| `src/memory_system/infrastructure/neo4j/consolidation_memory_write_repository.py` | 创建 | §2.3.9 权威 Cypher、`ConsolidationWriteError`、`authorized_write_cypher_queries()` |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `consolidation_importance.py`、`consolidation_batch_service.py`、`consolidation_memory_read_repository.py`、`consolidation_worker.py`、`settings/`、EXT/RET 已完成文件、DEV-006）。

## 12. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_consolidation_memory_write_repository.py` | 创建 | Cypher 契约、乐观锁、隔离、空写、写失败 |
| `tests/unit/test_consolidation_write_service.py` | 创建 | PV 校验、handoff、冲突计数、replay、skipped 永不写入 |
| `tests/contract/test_con003_scope_boundaries.py` | 创建 | 白名单、无 ES/Mongo、无 memory_version/updated_time SET |

**白名单外任何 `tests/**` 变更 → FAIL**（运行 EXT/RET/CON-001/CON-002 回归但不在白名单内编辑）。

### 12.1 governance_file_whitelist（Release Operator 各 phase）

| Phase | 允许路径 | 目的 |
|---|---|---|
| `PLAN_LANDING` | `02_开发管理/tasks/CON-003-optimistic-lock-batch-update.md` | 已批准 Task Plan |
| `PLAN_LANDING` | `02_开发管理/progress.md` | 规划态登记 |
| `PLAN_LANDING` | `02_开发管理/master_plan.md` | CON-003 规划登记 |
| `IMPLEMENTATION_RELEASE` | §11 production_file_whitelist 全部 | 实现 |
| `IMPLEMENTATION_RELEASE` | §13 test_file_whitelist 全部 | 测试 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/tasks/CON-003-optimistic-lock-batch-update.md` | 执行记录 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/progress.md` | 状态登记 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/master_plan.md` | 状态备注 |
| `POST_MERGE_CLEANUP` | 上述三份治理文件 | 完成登记 |

### 12.2 PLAN_LANDING commit contract

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含：

1. `02_开发管理/tasks/CON-003-optimistic-lock-batch-update.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`

Commit message（精确）：

```text
docs(plan): add CON-003 optimistic lock batch update plan
```

随后从更新后的 `main` 创建 exact feature branch `feat/CON-003-optimistic-lock-batch-update`。

## 13. minimum_test_plan

### 13.1 Unit Test — Repository（`test_consolidation_memory_write_repository.py`）

| ID | 场景 | 预期 |
|---|---|---|
| U1 | 单行合法写 | `updated_count=1`；Cypher 参数含 `importance`、`evaluation_time` |
| U2 | 用户隔离：`user_id` 不匹配 | `updated_count=0` |
| U3 | `expected_memory_version` 不匹配 | `updated_count=0`；节点 mock 无 SET |
| U4 | 混合批：2 行合法 1 行版本冲突 | `updated_count=2`；transaction 仍提交 |
| U5 | repository 入参 `rows=[]` 由 service 短路 | service 不调用 repository（见 U14/U15） |
| U6 | 精确 SET 字段 | 仅 `importance`、`last_consolidated_time`；无 `memory_version`/`updated_time` |
| U7 | 返回缺 `updated_count` | `ConsolidationWriteError` |
| U8 | Neo4j `ServiceUnavailable` | `ConsolidationWriteError(retryable=True)` |
| U9 | 同版本连续两次写 | 两次均 `updated_count=1`（replay 不触发版本冲突） |
| F1 | mock driver | `execute_write` 恰好一次/批 |

### 13.2 Unit Test — Service（`test_consolidation_write_service.py`）

| ID | 场景 | 预期 |
|---|---|---|
| U10 | CON-002 handoff：`ConsolidationScoredCandidate` → `ConsolidationWriteRow` | 字段映射精确 |
| U11 | 非法 `evaluation_time=-1` | `ValueError` |
| U12 | 重复 `memory_id` | 一条 valid、一条 `invalid_candidate` |
| U13 | 非法 `new_importance=1.5` | `invalid_candidate`；不进入 Cypher |
| U14 | 空 `rows` | `write_executed=false`；计数 0 |
| U15 | 全 invalid | `write_executed=false` |
| U16 | `version_conflict_count = valid_count - updated_count` | 精确聚合 |
| U17 | `skipped` 永不写入 | service 无 skipped 入参路径；契约测试双重断言 |
| U18 | 空 `user_id=""` | `ValueError`；repository 未被调用 |
| U19 | `expected_memory_version=0` | `invalid_candidate`；不进入 Cypher |
| U20 | `expected_memory_version` 负数或 bool | `invalid_candidate`；不进入 Cypher |
| F2 | repository 抛 `ConsolidationWriteError` | 向上传播；无部分成功伪造 |
| F3 | 部分 invalid + 部分 valid | valid 仍写；invalid 列表完整 |
| F4 | 写成功 | 零 ES/Mongo/Kafka 调用（mock 无相关 import 使用） |

### 13.3 Contract Test（`test_con003_scope_boundaries.py`）

| ID | 场景 | 预期 |
|---|---|---|
| C1 | 白名单外无 `src/**` 生产变更 | git diff 门禁 |
| C2 | 权威 Cypher 含 `user_id` + `expected_memory_version` + 双字段 SET | 静态断言 `authorized_write_cypher_queries()` |
| C3 | 无 `memory_version` / `updated_time` SET | Cypher 全文否定断言 |
| C4 | 不修改 CON-001/CON-002 读路径文件 | diff 断言 |
| C5 | `durable_write_scope` 仅 Neo4j Memory 两字段 | 无 ES/Mongo repository |
| C6 | 不修改 `consolidation_worker.py` / `settings/` | diff 断言 |

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
| F1 | 批写成功 | 仅 Neo4j write；无其他 durable 存储 |
| F2 | Neo4j 写失败 | `consolidation_write_failed`；无伪造 `updated_count` |
| F4 | 并发 10 路相同写请求（mock） | 无异常；结果一致（无进程内可变状态） |

## 14. NORMAL classification（HARD_BLOCK / SAFE_AUTO / MVP_LOCAL / DEFERRED）

| ID | 项 | 分类 | 说明 |
|---|---|---|---|
| CL-1 | Cypher 与 §2.3.9 不一致 | **HARD_BLOCK** | 规格唯一权威 |
| CL-2 | `memory_version` 或 `updated_time` 被写入 | **HARD_BLOCK** | §2.3.3 / §2.3.9 规则 4 |
| CL-3 | 跨用户写隔离失败 | **HARD_BLOCK** | §2.3.2 规则 2 |
| CL-4 | 版本冲突导致整批失败 | **HARD_BLOCK** | §2.3.9 规则 6 |
| CL-5 | Neo4j 失败未回滚语义 / 错误码错误 | **HARD_BLOCK** | §2.3.13 规则 3 |
| CL-6 | CON-002 skipped 被写入 | **HARD_BLOCK** | handoff 边界 |
| CL-7 | 修改 CON-001/CON-002 已完成语义 | **HARD_BLOCK** | 前置 closed |
| CL-8 | 测试未覆盖乐观锁/隔离/replay/冲突/失败/空写/字段精确 | **HARD_BLOCK** | 用户明确要求 |
| CL-9 | 修改 Settings Contract | **HARD_BLOCK** | dependency_changes_expected=NONE |
| CL-10 | DEV-006 / PR #13 | **HARD_BLOCK** | 治理永久禁止 |
| CL-11 | `neo4j_timeout_seconds` 只读注入自 `memory_retrieval` | **SAFE_AUTO_REMEDIATION** | LD-1；与 CON-002/RET 一致 |
| CL-12 | 独立 `consolidation_write.py` models 文件 | **SAFE_AUTO_REMEDIATION** | LD-2；与读批次解耦 |
| CL-13 | 重复 memory_id 后者 invalid | **MVP_LOCAL_DECISION** | LD-3 |
| CL-14 | 缺失节点归入 version_conflict 聚合 | **MVP_LOCAL_DECISION** | LD-4；Cypher 无法区分 |
| CL-15 | `invalid_candidate` reason 子类型 | **MVP_LOCAL_DECISION** | LD-5；测试可选细分 |
| CL-16 | Integration Neo4j Fixture | **DEFERRED** | CON-005 |
| CL-17 | APScheduler / mutex / metrics 落盘 | **DEFERRED** | CON-004 |
| CL-18 | Consolidation E2E | **DEFERRED** | CON-005 |
| CL-19 | ES importance 同步 | **DEFERRED** | §2.3.10 |
| CL-20 | per-row version_conflict 列表（无额外 Cypher） | **DEFERRED** | 批聚合已满足 §2.3.9 |

## 15. deferred_for_mvp（本任务显式不交付）

- CON-004：APScheduler、本地互斥锁、`evaluation_time`/`run_id` 生成、cursor 循环、失败恢复、指标落盘
- CON-005：Consolidation Integration + E2E（含真实 Neo4j 全链路）
- `memory_version` 递增（萃取职责）
- `updated_time` 任何变更
- ES / Mongo / Kafka 同步
- `consolidation_worker` 启动与调度接线
- 独立 Consolidation HTTP API
- per-row `version_conflict` 明细（无 §2.3.9 额外 RETURN 要求时仅批聚合）
- 修改 `MemoryConsolidationSettings` / validators
- 修改 CON-001 公式 / CON-002 读语义

## 16. mvp_local_decisions

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | Neo4j 超时使用 `settings.memory_retrieval.neo4j_timeout_seconds` 注入 repository | 与 CON-002/RET 一致；不改 Contract |
| LD-2 | 写模型独立 `consolidation_write.py`；读模型 `consolidation_batch.py` 不变 | 清晰 handoff；避免 CON-002 回归 |
| LD-3 | 同批重复 `memory_id`：保留首次 valid，其余 `invalid_candidate` | 避免 UNWIND 非确定性双更新 |
| LD-4 | 节点不存在与版本不匹配均计入 `version_conflict_count` | 单条 Cypher 仅 RETURN count；对巩固语义等价（均未写入） |
| LD-5 | `ConsolidationInvalidWriteCandidate.reason` 固定 `"invalid_candidate"`；子原因放可选 detail 字段或测试断言 PV 规则 | §2.3.13 表无更细码；MVP 本地可扩展 |
| LD-6 | Service 提供 `scored_candidates_to_write_rows(scored: list[ConsolidationScoredCandidate]) -> list[ConsolidationWriteRow]` 纯函数 | 显式 CON-002 handoff；禁止 skipped 参数重载 |
| LD-7 | Repository 返回 `int`（`updated_count`）；service 计算 `version_conflict_count` | 与 §2.3.9 RETURN 一致；编排层单一职责 |

## 17. open_issues

- `02_开发管理/open_issues.md`：**无** blocking CON-003 的 open issue。
- `blocking_open_issues: []`；`nonblocking_open_issues: []`。

## 18. 任务目标

交付 §2.3.9 Neo4j **乐观锁批量写入**：将 CON-002 `scored` 行的 `new_importance` 持久化为 `importance`，将 `last_consolidated_time` 设为调用方 `evaluation_time`；通过 `expected_memory_version` 谓词防止覆盖萃取并发修改；批次事务内部分成功；空写跳过；为 CON-004 调度编排提供唯一写实现。

可验证目标：

1. **`ConsolidationMemoryWriteRepository`** — 权威 Cypher + `execute_write` + 用户/版本谓词。
2. **`ConsolidationWriteService`** — PV 校验、handoff、空写跳过、`version_conflict_count` 聚合。
3. **契约** — 仅写 `importance` / `last_consolidated_time`；不碰 `memory_version` / `updated_time` / ES。
4. **测试** — U1..U17 + F1..F4 + C1..C6 全部通过。
5. Ruff / Mypy 通过；Review 无 P0/P1。

## 19. 非目标与黑名单（must_not）

- `memory_version` 递增 — **萃取 only**。
- `updated_time` 写入 — **禁止**。
- `evaluation_time` / `run_id` 生成 — **CON-004**。
- APScheduler、互斥锁、`consolidation_worker` 接线 — **CON-004**；**禁止**修改 `consolidation_worker.py`。
- CON-002 候选读 / Evidence 计数 / 公式 — **禁止**修改已完成模块。
- CON-002 `skipped` 行写入 — **禁止**。
- Consolidation E2E / 真实 Neo4j Integration — **CON-005**。
- ES / Mongo / Kafka 读写。
- 修改 `consolidation_importance.py`（CON-001）。
- 修改 `MemoryConsolidationSettings` / validators。
- 修改 RET / EXT 已完成生产语义。
- DEV-006 / PR #13 — **永久禁止**。

## 20. 当前代码状态

- **已存在**：`ConsolidationScoredCandidate`（含 `memory_version` 透传）；`ConsolidationMemoryReadRepository`（CON-002 只读模式）；`RetrievalStatisticsRepository`（Neo4j `execute_write` 参考）；`compute_consolidation_importance`（CON-001）。
- **可复用**：CON-002 scored 行契约；`memory_retrieval.neo4j_timeout_seconds`；Fake/mock driver 测试模式（CON-002/RET unit tests）。
- **当前缺失**：巩固写 domain models、write service、consolidation Neo4j write repository、对应 unit/contract 测试。
- **与技术规格不一致之处**：无（规划基线 clean @ `cabcc6f`）；§2.3.9 批量写尚未实现。
- **前置任务检查**：CON-002 completed（PR #51 MERGED）；CON-001 completed（PR #50 MERGED）；EXT-001..009 completed；RET-001..006 completed。

## 21. 实现方案

### Step 1 — 写领域模型

- **文件**：`src/memory_system/domain/models/consolidation_write.py`
- **类型**：`ConsolidationWriteBatchRequest`；`ConsolidationWriteRow`；`ConsolidationWriteBatchResult`；`ConsolidationInvalidWriteCandidate`；`InvalidWriteReason = Literal["invalid_candidate"]`（及可选 MVP 子原因常量）
- **输入/输出**：§3.1、§5
- **错误处理**：frozen dataclass；request 级校验在 service
- **幂等/并发**：不可变模型；无状态

### Step 2 — Neo4j 写仓储

- **文件**：`src/memory_system/infrastructure/neo4j/consolidation_memory_write_repository.py`
- **类**：`ConsolidationMemoryWriteRepository`；`ConsolidationWriteError`
- **方法**：`async def write_importance_batch(user_id, evaluation_time, rows: list[ConsolidationWriteRow]) -> int`（返回 `updated_count`；`rows` 已预校验非空）
- **构造**：`ConsolidationMemoryWriteRepository(driver, *, neo4j_timeout_seconds: float)` — 由调用方从 `settings.memory_retrieval.neo4j_timeout_seconds` 注入
- **Cypher**：§3.3 权威查询；`authorized_write_cypher_queries()` 供契约测试
- **错误处理**：§7 failure_mapping；Neo4j 异常 → `ConsolidationWriteError`；空 `rows` 由 service 短路，repository 可 assert 非空或 no-op
- **幂等/并发**：同版本可重复 SET；乐观锁由 WHERE 保证

### Step 3 — 写服务与 CON-002 handoff

- **文件**：`src/memory_system/domain/services/consolidation_write_service.py`
- **函数**：`def scored_candidates_to_write_rows(scored: list[ConsolidationScoredCandidate]) -> list[ConsolidationWriteRow]`；`async def write_batch(request, repository) -> ConsolidationWriteBatchResult`
- **流程**：校验 request → 逐行 PV → 构建 `valid_rows` → 若空则跳过 write → 否则 repository → 聚合 `version_conflict_count` / `invalid_candidates`
- **错误处理**：写失败向上抛；PV 单行不抛；request 级非法 → `ValueError`
- **幂等/并发**：无共享可变状态

### Step 4 — 单元与契约测试

- **文件**：§12 test_file_whitelist
- **覆盖**：§13 minimum_test_plan（U1..U17、F1..F4、C1..C6）
- **Mock 策略**：内存 fake Neo4j records / mock `AsyncDriver`；断言 Cypher 参数与 SET 字段；不启动真实 Neo4j

## 22. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/consolidation_write.py` | 创建 | 写请求/结果契约 |
| `src/memory_system/domain/services/consolidation_write_service.py` | 创建 | PV + handoff + 结果聚合 |
| `src/memory_system/infrastructure/neo4j/consolidation_memory_write_repository.py` | 创建 | §2.3.9 Neo4j 乐观锁写 |
| `tests/unit/test_consolidation_memory_write_repository.py` | 创建 | 写契约与冲突 |
| `tests/unit/test_consolidation_write_service.py` | 创建 | handoff/replay/空写 |
| `tests/contract/test_con003_scope_boundaries.py` | 创建 | 白名单与边界 |

## 23. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 适用 | 单批单 transaction；失败整批回滚；§3.3 NW-6 |
| 幂等 | 适用 | 巩固不写 `memory_version`；同版本可重放 SET；§9 |
| 并发 | 适用 | 乐观锁 WHERE；萃取增版本 → 冲突跳过；§2.3.9 规则 3 |
| 版本冲突 | 适用 | 批内部分成功；`version_conflict_count`；非整任务失败 |
| 用户隔离 | 适用 | Cypher `user_id` 双谓词；§6 |
| 部分失败 | 适用 | invalid 行跳过；冲突行跳过；写失败整批失败 |
| 进程异常恢复 | 不适用 | 无批次间持久化状态；CON-004 重新扫描 |

## 24. 测试计划（模板 §8 映射）

### Unit Test — 见 §13.1、§13.2

### Contract Test — 见 §13.3

### Integration Test — **DEFERRED**（§13.4）

### E2E Test — **DEFERRED**（§13.5）

### 失败注入与并发 — 见 §13.6

## 25. 验收标准

- [ ] `pytest tests/unit/test_consolidation_memory_write_repository.py tests/unit/test_consolidation_write_service.py tests/contract/test_con003_scope_boundaries.py` 全部通过
- [ ] U1/U6 精确持久化 `importance` 与 `last_consolidated_time=evaluation_time`
- [ ] U2 用户隔离：跨用户不得更新
- [ ] U3/U4 版本冲突无 mutation、混合批部分成功
- [ ] U9 replay 同版本不冲突
- [ ] U14/U15 空写跳过 transaction
- [ ] U17/C6 skipped 永不写入、worker/settings 不变
- [ ] U8/F2 Neo4j 失败 → `consolidation_write_failed`
- [ ] C2/C3 权威 Cypher 无 `memory_version`/`updated_time` SET
- [ ] C5 无 ES/Mongo/Kafka
- [ ] Ruff 通过
- [ ] Mypy 通过（新增文件）
- [ ] Review 无 P0/P1

## 26. 风险与阻塞项

- **设计文档冲突**：无；§2.3.9 Cypher 与用户查询一致。
- **当前代码冲突**：无；CON-002 已完成且 `memory_version` 已透传。
- **前置任务**：CON-002 PR #51 MERGED；CON-001 PR #50 MERGED。
- **未批准依赖**：`dependency_changes_expected=NONE`。
- **API/Schema 变化**：无 HTTP；内部 dataclass + repository。
- **其他风险**：与萃取写路径混淆 — 通过 C3/C5 契约测试隔离；与检索统计写混淆 — 字段级 SET 断言。

## 27. Git 计划

```yaml
branch: "feat/CON-003-optimistic-lock-batch-update"
expected_commits:
  - "docs(plan): add CON-003 optimistic lock batch update plan"
  - "feat(con): add consolidation optimistic lock batch write"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "consolidation_worker.py"
  - "consolidation_importance.py（CON-001 公式）"
  - "consolidation_batch_service.py / consolidation_memory_read_repository.py（CON-002 读路径）"
  - "settings/models.py / validators.py"
  - "graph_write_repository.py / extraction 写路径"
  - "ES / Mongo / Kafka / Scheduler"
  - "CON-004..005 范围"
```

## 28. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- **时间**：2026-08-13 12:35 UTC
- **原因**：人工 `PLAN_APPROVED` 后吸收 Plan Reviewer SHOULD_FIX（SF-1..SF-3）；无语义变更
- **变更**：
  - SF-1：统一 §7 / §9 与 §13 测试 ID 交叉引用
  - SF-2：新增 U18（`user_id=""` → `ValueError`；无 Neo4j write）
  - SF-3：新增 U19/U20（非法 `expected_memory_version` → `invalid_candidate`）

## 29. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 11:30 UTC | planning | 创建 Task Plan；同步 progress/master_plan | N/A（规划-only） | baseline `cabcc6f` verified；`approval_posture=AWAIT_PLAN_REVIEW`；Developer NOT authorized |

## 30. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| （尚未实施） | — |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | — | 待实施 |
| Contract | — | 待实施 |
| Integration | — | DEFERRED（CON-005） |
| E2E | — | DEFERRED（CON-005） |
| Ruff | — | 待实施 |
| Mypy | — | 待实施 |

### Review 结果

```yaml
code_review: null
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
