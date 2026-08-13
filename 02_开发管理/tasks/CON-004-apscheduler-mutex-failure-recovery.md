# CON-004 APScheduler、互斥锁、失败恢复

## 1. 任务信息

```yaml
task_id: CON-004
task_name: APScheduler、互斥锁、失败恢复
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "8998f627b6cf0c8f5beb103006903d8c3668542a"
branch: "feat/CON-004-apscheduler-mutex-failure-recovery"
created_at: "2026-08-13 21:15 UTC"
updated_at: "2026-08-13 21:30 UTC"
spec_sections:
  - "§2.3.2 MVP 范围与基本规则（规则 2、7、11 — 用户隔离、统一 evaluation_time、单实例本地锁）"
  - "§2.3.4 调度、互斥与批量扫描（evaluation_time、run_id、mutex、cursor 编排 — 本任务拥有调度侧；读 Cypher 由 CON-002 实现）"
  - "§2.3.9 Neo4j 批量更新与并发控制（边界 only — 写语义 CON-003；本任务编排调用）"
  - "§2.3.11 完整处理流程（§2.3.11 流程图 — 本任务唯一权威编排）"
  - "§2.3.12 MVP 配置（memory_consolidation 调度参数只读消费；enabled=false / invalid config 行为）"
  - "§2.3.13 失败处理与恢复（错误码映射、指标、日志、finally 释放锁）"
  - "§2.3.14 MVP 实现边界（Scheduler、本地锁、持续扫描至完成）"
  - "§3.22 Consolidation Scheduler（AsyncIOScheduler + CronTrigger）"
  - "§3.25 优雅关闭（consolidation_worker shutdown 语义）"
  - "§3.27 日志、指标（consolidation_runs_total{status}）"
prerequisites:
  formal:
    - "CON-003 — SATISFIED/completed（PR #52 MERGED）；ConsolidationWriteService + optimistic-lock write"
    - "CON-002 — SATISFIED/completed（PR #51 MERGED）；ConsolidationBatchService + cursor batch read"
    - "CON-001 — SATISFIED/completed（PR #50 MERGED）；compute_consolidation_importance"
    - "EXT-001..009 — SATISFIED/completed"
    - "RET-001..006 — SATISFIED/completed（v0.4.0-memory-retrieval closed）"
  implementation_reuse:
    - "ConsolidationBatchService.process_batch（CON-002；禁止修改读语义）"
    - "ConsolidationWriteService.write_batch + scored_candidates_to_write_rows（CON-003；禁止修改写语义）"
    - "ConsolidationMemoryReadRepository（CON-002 批次读；本任务不修改其 Cypher）"
    - "ConsolidationMemoryWriteRepository（CON-003 批次写；本任务不修改其 Cypher）"
    - "MemoryConsolidationSettings（schedule_cron / timezone / scheduler_* / batch_size / enabled）"
    - "CONSOLIDATION_RUNS_TOTAL（observability/metrics.py 已注册）"
    - "extraction_worker.py 生命周期模式（settings → driver → graceful shutdown）"
  baseline_evidence:
    branch: "main"
    head: "8998f627b6cf0c8f5beb103006903d8c3668542a"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=8998f627b6cf0c8f5beb103006903d8c3668542a"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: PLAN_APPROVED
  amendment_recorded: true
  human_plan_approved: true
  human_plan_approved_at: "2026-08-13 21:30 UTC"
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: true
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feature branch feat/CON-004-apscheduler-mutex-failure-recovery"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_read_scope: "Neo4j read-only — DISTINCT user_id enumeration with consolidation candidate predicates"
durable_write_scope: "NONE at orchestration layer — durable writes delegated to CON-003 Neo4j write only"
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
  - "修改 CON-001/CON-002/CON-003 已完成服务语义"
  - "实现 CON-005 Integration/E2E"
stop_if:
  - "任何实现步骤需要修改 consolidation_importance.py / consolidation_batch_service.py 语义 / consolidation_write_service.py 语义"
  - "任何实现步骤需要 ES / Mongo / Kafka 同步或持久化 cursor/run 表"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要 Redis 分布式锁或多实例选主"
blocking_open_issues: []
nonblocking_open_issues: []
```

### 1.2 人工批准修订（SF-1..SF-3）

人工 `PLAN_APPROVED`（2026-08-13 21:30 UTC）吸收 Plan Review SHOULD_FIX：

| ID | 修订 | 落点 |
|---|---|---|
| SF-1 | 未捕获 run 异常 **禁止**新增第四 Prometheus `status` 标签；须记录 error 日志并 fail-closed；`consolidation_runs_total` 仅 `success` / `read_failed` / `write_failed`（LD-4） | §9、§11、CL-16 |
| SF-2 | `neo4j_timeout_seconds` 从 `settings.memory_retrieval` 注入 `ConsolidationUserEnumerationRepository` 与 Worker Neo4j driver/repository 构造（与 CON-002/003 一致） | Step 2、Step 7、CL-12 |
| SF-3 | RC-7 显式 `ConsolidationWriteBatchRequest { user_id, evaluation_time, rows[{memory_id, new_importance, expected_memory_version}] }`；`skipped` 永不传入 | §3 RC-7、§4 |

## 2. authoritative_scope

本任务 **拥有** §2.3.11 巩固运行编排、§2.3.4 调度侧（`evaluation_time`/`run_id`/mutex）、§3.22 APScheduler 注册、§3.25 consolidation_worker 接线、§2.3.13 运行指标与结构化日志、用户枚举与 per-user cursor 循环；**不** 拥有 CON-001/002/003 内部公式/读 Cypher/写 Cypher 语义、CON-005 全链路 Integration/E2E。

| 维度 | 归属 CON-004 | 非 CON-004（显式排除） |
|---|---|---|
| APScheduler `AsyncIOScheduler` + `CronTrigger` 注册 | **是** — §3.22 | — |
| `memory_consolidation.schedule_cron` / `timezone` / `scheduler_*` 只读消费 | **是** — §2.3.12、§3.22 | 修改 Settings Contract — **禁止** |
| `enabled=false` 行为（Worker 可启动、不注册 Job） | **是** — §2.3.12 配置语义 | — |
| `consolidation_invalid_config` 阻止巩固启动 | **是** — §2.3.12 规则 9 | 影响 Memory API — **禁止** |
| 进程内本地互斥锁（非分布式） | **是** — §2.3.4、§2.3.13 规则 8 | Redis 锁 — **禁止** |
| `run_id` 生成（UUID，锁获取后） | **是** — §2.3.4 | — |
| `evaluation_time` 生成（每轮一次，计划触发 Unix 秒） | **是** — §2.3.4、§2.3.2 规则 7 | CON-001/002/003 自行读墙钟 — **禁止** |
| Neo4j `DISTINCT user_id` 用户枚举（候选谓词一致） | **是** — §2.3.2 规则 2 + 本任务契约 | 外部用户注册表 — **禁止** |
| per-user `memory_id` cursor 分页循环 | **是** — §2.3.4 + PG-7b | 持久化 cursor — **禁止** |
| 调用 `ConsolidationBatchService.process_batch` | **是** — 编排 | 修改 CON-002 读语义 — **禁止** |
| 调用 `ConsolidationWriteService.write_batch` | **是** — 编排 | 修改 CON-003 写语义 — **禁止** |
| 失败恢复（读失败/写失败终止 run；冲突/skip 非致命） | **是** — §2.3.13 | — |
| §2.3.13 运行指标聚合 + 结构化日志 | **是** | OPS-002 全量审计 — **DEFERRED** |
| `consolidation_runs_total{status}` 递增 | **是** — §3.27 | 额外 Prometheus 指标 — **禁止本任务** |
| `consolidation_worker` entrypoint 接线 | **是** — §3.25 | — |
| Scheduler graceful shutdown | **是** — §3.25 | — |
| `compute_consolidation_importance` / 公式 | **否** | **CON-001**（已完成） |
| Neo4j 候选批次读 Cypher / Evidence 计数 | **否** | **CON-002**（已完成） |
| Neo4j 乐观锁写 Cypher | **否** | **CON-003**（已完成） |
| `memory_version` 递增 / `updated_time` | **否** | 萃取 only |
| ES / Mongo / Kafka | **否** | 阶段非目标 |
| Consolidation Integration + E2E | **否** | **CON-005** |
| 独立 Consolidation HTTP API | **否** | 阶段非目标 |
| 多实例调度 / 分布式锁 | **否** | §2.3.14 非目标 |

## 3. run_contract

巩固 **单次 run**（一次成功获取互斥锁后的完整扫描）契约：

| 阶段 | 行为 | 测试 ID |
|---|---|---|
| RC-1 Run 开始 | Scheduler Job 触发 → **先**尝试获取进程内互斥锁 | U5, U6 |
| RC-2 锁失败 | 记录 `consolidation_already_running`；递增 `skipped_trigger_count`；**不**生成 `run_id`；**不**递增 `consolidation_runs_total` 成功/失败计数 | U5 |
| RC-3 锁成功 | 生成 `run_id = uuid4()`；计算 `evaluation_time`（§4）；初始化运行指标计数器 | U7, U8 |
| RC-4 用户迭代 | 调用用户枚举 → 对每个 `user_id` **顺序**执行 per-user 分页循环（§5） | U2, U3 |
| RC-5 Cursor 初始化 | 每个用户 `cursor = None` | U1, U3 |
| RC-6 CON-002 读 | `ConsolidationBatchRequest(user_id, evaluation_time, cursor, batch_size=None)` → `process_batch` | U1, U9 |
| RC-7 CON-003 写 | 若 `scored` 非空：映射为 `ConsolidationWriteBatchRequest { user_id=当前用户, evaluation_time=run 固定值, rows=[{memory_id, new_importance, expected_memory_version}] }`（来自 `scored_candidates_to_write_rows` 或等价映射）→ `write_batch`；`skipped` **永不**传入写路径（SF-3） | U1, U10 |
| RC-8 指标聚合 | 每批累加 `scanned_count`、`missing_evidence_count`、`invalid_memory_count`、`updated_count`、`version_conflict_count`、`batch_count` | U1, U11 |
| RC-9 Cursor 推进 | `has_more=True` → `cursor = next_cursor` 继续；`has_more=False` → 该用户分页结束 | U1, U3 |
| RC-10 用户完成 | 当前用户所有批次处理完毕 → 下一用户 | U2 |
| RC-11 Run 终止（成功） | 所有用户处理完毕 → 记录 `run_duration_ms`；`consolidation_runs_total.labels(status="success").inc()`；结构化日志 | U2, U11 |
| RC-12 Run 终止（读失败） | Neo4j 读异常 → `consolidation_read_failed`；**立即**终止 run（不处理剩余用户/页）；`consolidation_runs_total.labels(status="read_failed").inc()` | U9 |
| RC-13 Run 终止（写失败） | Neo4j 写异常 → `consolidation_write_failed`；**立即**终止 run；已完成批次 **不回滚** | U10 |
| RC-14 Finally | **无论** RC-11..13 或异常 → `finally` 释放互斥锁 | U6, U12 |
| RC-15 空候选 | 零用户或全用户零候选 → 正常完成（RC-11 success）；非失败 | U4 |

**禁止**：run 内为每批或每用户生成不同 `evaluation_time`；禁止 CON-002/003 在编排层之外自行调用 `time.time()` 作为 `evaluation_time`。

## 4. pagination_orchestration

Per-user 分页循环（PG-7b 与 CON-002 契约对齐）：

```text
cursor = None
loop:
  batch_result = await batch_service.process_batch(
      ConsolidationBatchRequest(
          user_id=user_id,
          evaluation_time=evaluation_time,   # 整轮固定
          cursor=cursor,
          batch_size=None,                   # 使用 settings.memory_consolidation.batch_size
      ),
      settings,
  )
  aggregate batch metrics (scanned, skipped reasons)
  if batch_result.scored:
      write_result = await write_service.write_batch(...)
      aggregate write metrics
  if not batch_result.has_more:
      break                                  # memories_returned < batch_size 或 == 0
  cursor = batch_result.next_cursor          # 仅当 has_more=True
```

| 规则 | 说明 | 测试 ID |
|---|---|---|
| PG-1 | Cursor 类型为 `memory_id` 字符串；`None` 表示从头 | U3 |
| PG-2 | `has_more = memories_returned == batch_size`（CON-002 产出；编排层不得重算） | U3 |
| PG-3 | 满页最后一页后 **一次** 后续空读由 CON-002 `has_more` 自然终止；编排层 **禁止** count-ahead/lookahead | U3 |
| PG-4 | 空页或部分页（`memories_returned < batch_size`）→ `has_more=False` → 终止该用户 | U1, U4 |
| PG-5 | 当前批全部 skip 且 `scored` 为空 → **跳过** CON-003 write transaction；仍推进 cursor（若 `has_more`） | U1, U11 |
| PG-6 | 当前批存在 `version_conflict` → **不**终止 run；仅累加指标 | U7 |
| PG-7 | **无**持久化 cursor；进程崩溃后下次 run 从 `cursor=None` 重扫 | U13 |
| PG-8 | 禁止跨用户共享 cursor | U2 |

## 5. user_enumeration_contract

| 规则 | 说明 | 测试 ID |
|---|---|---|
| UE-1 数据源 | Neo4j `Memory` 节点；**禁止** Mongo/Redis/外部用户注册表 | U2, C3 |
| UE-2 候选谓词 | 与 CON-002 批次读 **相同**（不含 per-user `user_id` 过滤、不含 cursor）：`created_time <= evaluation_time`；`last_consolidated_time IS NULL OR < evaluation_time`；`status IN ['active','conflicted','superseded']` | C3 |
| UE-3 查询语义 | `RETURN DISTINCT m.user_id AS user_id ORDER BY m.user_id ASC` | U2, U3 |
| UE-4 去重 | `DISTINCT` 保证每 `user_id` 仅出现一次 | U2 |
| UE-5 空用户集 | 返回空列表 → run 正常完成；`scanned_count=0` | U4 |
| UE-6 隔离 | 枚举仅产出 `user_id` 列表；后续每用户批次读仍带 `user_id` 谓词（CON-002） | U2 |
| UE-7 读失败 | Neo4j 枚举查询失败 → `consolidation_read_failed`；终止 run | U9 |
| UE-8 实现位置 | 新建 `ConsolidationUserEnumerationRepository`（或等价命名）；**禁止**修改 `consolidation_memory_read_repository.py` 既有 Cypher | C1 |

权威 Cypher 示意：

```cypher
MATCH (m:Memory)
WHERE m.created_time <= $evaluation_time
  AND (m.last_consolidated_time IS NULL
       OR m.last_consolidated_time < $evaluation_time)
  AND m.status IN ['active', 'conflicted', 'superseded']
RETURN DISTINCT m.user_id AS user_id
ORDER BY m.user_id ASC
```

## 6. evaluation_time_contract

| 规则 | 说明 | 测试 ID |
|---|---|---|
| ET-1 | **每 entire run 一个** `evaluation_time`（int Unix epoch 秒，≥0） | U8 |
| ET-2 | 定义：`evaluation_time =` 本次 Scheduler **计划触发时间**的 Unix timestamp（非批次开始墙钟、非 `time.time()` at lock acquire） | U8 |
| ET-3 | APScheduler Job 触发时从 `scheduled_run_time`（或 APScheduler event 等价字段）转换为 Unix 秒 | U8, U14 |
| ET-4 | 同一 `evaluation_time` 传入：用户枚举、每次 `process_batch`、每次 `write_batch` | U8 |
| ET-5 | CON-001/002/003 **不得**在编排层之外独立生成 `evaluation_time` | C4 |
| ET-6 | 下一 scheduled run 使用 **新** `evaluation_time`；与 `last_consolidated_time` 协作实现恢复（§15） | U13 |

**MVP 本地**：若 APScheduler 仅提供 timezone-aware datetime，转换为 UTC Unix 秒；不得使用 float 毫秒。

## 7. mutex_contract

| 规则 | 说明 | 测试 ID |
|---|---|---|
| MX-1 | **进程内**互斥；`asyncio.Lock` 或等价原子 Running Flag；**禁止** Redis/DB 分布式锁 | U5, C2 |
| MX-2 | 获取时机：Scheduler Job **入口**、生成 `run_id` **之前** | U5 |
| MX-3 | 非阻塞或 `acquire` 失败：记录 `consolidation_already_running`；跳过本次触发；**不**视为系统故障 | U5 |
| MX-4 | 成功获取后才生成 `run_id` 并开始用户枚举 | U5 |
| MX-5 | `finally` **必须**释放锁（成功、读失败、写失败、未捕获异常） | U6, U12 |
| MX-6 | 与 `scheduler_max_instances` 对齐：默认 `1`；Job `max_instances=settings.memory_consolidation.scheduler_max_instances` | U14, C5 |
| MX-7 | 锁持有范围：整个 run（所有用户、所有页） | U5 |
| MX-8 | MVP 单 Consolidation Worker 容器；本地锁 **不**用于多实例 | 文档级 |

## 8. scheduler_contract

| 规则 | 说明 | 测试 ID |
|---|---|---|
| SCH-1 | `AsyncIOScheduler` + `CronTrigger.from_crontab(schedule_cron, timezone=timezone)` — §3.22 | U14, C5 |
| SCH-2 | Job id 固定（如 `memory_consolidation_run`）；无持久化 Job Store | U14 |
| SCH-3 | `max_instances=scheduler_max_instances`；`coalesce=scheduler_coalesce`；`misfire_grace_time=scheduler_misfire_grace_time_seconds` | U14 |
| SCH-4 | Worker 启动时注册 Job（`enabled=true` 且配置合法） | U14 |
| SCH-5 | `enabled=false`：Worker **可**完成 Neo4j ping 并 idle；**不**注册巩固 Job；进程保持运行直至 shutdown（或文档化 idle 循环） | U15 |
| SCH-6 | 配置非法（`CronTrigger` 解析失败等，启动前 `get_settings()` 已校验）→ `consolidation_invalid_config`；巩固 Worker **拒绝启动**（exit code ≠ 0）；**不影响** memory-api | U16 |
| SCH-7 | Shutdown（§3.25）：`scheduler.shutdown(wait=True)` 或等价；停止接收新 Job；等待当前批次/当前 Memory 原子更新完成 | U14, U17 |
| SCH-8 | Job 内 **禁止**第二层无限循环；每次触发 = 一次有界 run（§3.22 规则 5） | C2 |
| SCH-9 | Misfire：漏执行不丢数据；下次扫描靠 `last_consolidated_time` | U13 |

## 9. failure_recovery_contract

| 条件 | 错误码 | Run 行为 | 已完成批次 | 测试 ID |
|---|---|---|---|---|
| 互斥锁未获取 | `consolidation_already_running` | 跳过触发；无 run | — | U5 |
| 用户枚举 Neo4j 失败 | `consolidation_read_failed` | **终止** run | 不受影响 | U9 |
| CON-002 `process_batch` Neo4j 失败 | `consolidation_read_failed` | **终止** run | 已提交写批次保留 | U9 |
| CON-003 `write_batch` Neo4j 失败 | `consolidation_write_failed` | **终止** run | 前序已提交批次保留 | U10 |
| 单条 `invalid_memory_state` skip | `invalid_memory_state` | 继续 run | — | U11 |
| 单条 `missing_evidence` skip | `missing_evidence` | 继续 run | — | U11 |
| 批内 `version_conflict` | 聚合计数 | 继续 run | 冲突行 `last_consolidated_time` 不更新（CON-003） | U7 |
| Run 中途页/用户失败（读/写） | 见上 | 立即终止；**不**处理剩余用户/页 | 已提交保留 | U9, U10 |
| Scheduler Job 未捕获异常 | 记录 error + `finally` 释放锁 | run 失败；`consolidation_runs_total` **仅** `read_failed` 或 `write_failed`（按最近已知阶段映射；无法判定则 `read_failed`）；**禁止**第四 `status` 标签（SF-1） | 已提交保留 | U12 |
| 进程崩溃 | — | 无补偿事务；下次 scheduled run 新 `evaluation_time` 全量重扫 | `last_consolidated_time` 保护已提交 | U13 |
| 配置非法 | `consolidation_invalid_config` | Worker 不启动 | — | U16 |

**禁止**：自动重试队列、死信、Kafka 事件、`memory_consolidation_task` 状态表（§2.3.13 规则 6）。

## 10. version_conflict_handling

| 规则 | 说明 | 测试 ID |
|---|---|---|
| VC-1 | 从 CON-003 `ConsolidationWriteBatchResult.version_conflict_count` 聚合 | U7 |
| VC-2 | **不**终止 run；**不**在 CON-004 重试 stale 行 | U7 |
| VC-3 | 仅 metrics + structured log（`version_conflict_count`） | U7, U11 |
| VC-4 | 冲突行下次 run 可被 CON-002 重新读取（`last_consolidated_time` 未更新） | 文档级；Integration **CON-005** |
| VC-5 | **禁止**修改 CON-003 乐观锁语义或添加 CON-004 侧重试 Cypher | C4 |

## 11. metrics_contract

§2.3.13 **必需**运行指标（单次 run 聚合，结构化日志输出；**不**要求全部注册为 Prometheus 直方图）：

| 指标 | 来源 | 测试 ID |
|---|---|---|
| `scanned_count` | Σ `batch_result.memories_returned` | U11 |
| `updated_count` | Σ `write_result.updated_count` | U11 |
| `version_conflict_count` | Σ `write_result.version_conflict_count` | U11 |
| `invalid_memory_count` | Σ `len(batch_result.skipped where reason=invalid_memory_state)` | U11 |
| `missing_evidence_count` | Σ `len(batch_result.skipped where reason=missing_evidence)` | U11 |
| `batch_count` | 成功调用的 `process_batch` 次数 | U11 |
| `skipped_trigger_count` | 进程级；互斥跳过次数（可跨 run 累计或 per-worker 实例） | U5 |
| `run_duration_ms` | run 墙钟毫秒（锁获取后至 finally 前） | U11 |

Prometheus（§3.27）：

| 指标 | 行为 | 测试 ID |
|---|---|---|
| `consolidation_runs_total{status}` | **仅** `success` / `read_failed` / `write_failed`；互斥跳过 **不**计入 run total（仅 `skipped_trigger_count`）；未捕获异常 **禁止** invent 第四标签（SF-1/LD-4） | U11 |

结构化日志（§2.3.13 规则 7）**至少**包含：`run_id`、`evaluation_time`、`user_id`（批级）、`cursor`、`batch_size`、`error_code`（错误时）、上述计数；**禁止**完整 Memory `content`。

**禁止本任务**：新增 §3.27 未列出的 Prometheus 指标；记录完整 content / LLM 数据。

## 12. durable_write_scope

```yaml
orchestration_durable_write_scope: NONE
delegated_write_scope: "Neo4j Memory — importance, last_consolidated_time（CON-003 only）"
```

- CON-004 编排层：**零** Neo4j/Mongo/ES/Kafka 直接写。
- 持久化 cursor、run 表、Job Store：**禁止**。
- 所有 durable 写入通过 `ConsolidationWriteService.write_batch` 委托 CON-003。

## 13. worker_entrypoint_scope

`consolidation_worker.py`（**本任务允许 MODIFY**）：

```text
main()
  → get_settings()（失败 → exit 1 + consolidation_invalid_config 语义）
  → configure_logging
  → asyncio.run(_run_worker(settings))

_run_worker(settings):
  → Neo4j AsyncDriver（ping）
  → 构建 read/write repositories + batch/write services + run orchestrator
  → 若 enabled：注册 AsyncIOScheduler Job → scheduler.start()
  → stop_event + SIGTERM/SIGINT handlers（extraction_worker 模式）
  → await idle until stop_event（或 scheduler 驱动）
  → graceful shutdown：scheduler.shutdown → 等待当前 run（若进行中）→ driver.close
  → shutdown deadline: settings.shutdown.consolidation_worker_timeout_seconds（§3.25）
```

| 规则 | 说明 |
|---|---|
| WE-1 | **仅** Neo4j 为巩固 Worker 必需依赖（§3.32 启动检查） |
| WE-2 | 不启动 Kafka/Mongo/ES client |
| WE-3 | Signal handler 仅 `stop_event.set()`；复杂清理在主协程 |
| WE-4 | `enabled=false` 时仍可启动并等待 shutdown（无 Job） |

## 14. replay_restart_semantics

| 场景 | 预期 | 测试 ID |
|---|---|---|
| 部分用户/页完成后崩溃 | 下次 scheduled run：新 `run_id`、新 `evaluation_time`；全量重扫 | U13 |
| 已提交批次 | `last_consolidated_time = evaluation_time` → 同轮不再选中；**不回滚** | U13 |
| 版本冲突行 | `last_consolidated_time` 未更新 → 下次 run 重新候选 | 文档级 |
| 公式确定性 | 相同输入 + 新 `evaluation_time` 可重算；不依赖旧 `importance`（CON-001） | 文档级 |
| 无持久化 cursor | 崩溃后从 `cursor=None` 开始 | U13 |
| Misfire / 漏调度 | 下次扫描处理未巩固 Memory | U13 |

## 15. CON-005 boundary

| 项 | CON-004 | CON-005 |
|---|---|---|
| 真实 Neo4j Integration Fixture | **DEFERRED** | **拥有** |
| Compose E2E consolidation 全链路 | **DEFERRED** | **拥有** |
| 多服务 Worker + 真实 Scheduler 长时间运行 | **DEFERRED** | **拥有** |
| Unit 测试 | Fake/mock `ConsolidationBatchService` / `ConsolidationWriteService` / enumeration repo | 真实基础设施 |
| 失败注入（Neo4j 宕机 E2E） | Unit mock only | **拥有** |

本任务 Unit 测试 **必须**使用 fake ports 验证编排语义；**不得**引入 `compose.test.yaml` 或真实 Neo4j driver 作为 scoped test 依赖。

## 16. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/consolidation_run.py` | 创建 | `ConsolidationRunMetrics` / `ConsolidationRunResult` / run 状态枚举 |
| `src/memory_system/domain/services/consolidation_run_service.py` | 创建 | Run 编排：mutex、用户循环、分页循环、CON-002/003 调用、指标聚合 |
| `src/memory_system/infrastructure/consolidation_mutex.py` | 创建 | 进程内 `asyncio.Lock` 封装；`try_acquire` / `release` |
| `src/memory_system/infrastructure/scheduling/consolidation_scheduler.py` | 创建 | APScheduler 注册、Job 工厂、`scheduled_run_time` → `evaluation_time` |
| `src/memory_system/infrastructure/neo4j/consolidation_user_enumeration_repository.py` | 创建 | DISTINCT `user_id` 枚举 Cypher |
| `src/memory_system/observability/consolidation_run_telemetry.py` | 创建 | 结构化日志 + `CONSOLIDATION_RUNS_TOTAL` 递增 helper |
| `src/memory_system/entrypoints/consolidation_worker.py` | **修改** | settings → Neo4j → orchestrator + scheduler → graceful shutdown |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `consolidation_importance.py`、`consolidation_batch_service.py`、`consolidation_memory_read_repository.py`、`consolidation_write_service.py`、`consolidation_memory_write_repository.py`、`settings/`、EXT/RET 已完成文件、DEV-006）。

## 17. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_consolidation_run_service.py` | 创建 | 编排、分页、evaluation_time、失败恢复、指标 |
| `tests/unit/test_consolidation_mutex.py` | 创建 | 互斥获取/释放/重叠跳过 |
| `tests/unit/test_consolidation_scheduler.py` | 创建 | CronTrigger 参数、Job 注册、shutdown |
| `tests/unit/test_consolidation_user_enumeration_repository.py` | 创建 | 枚举 Cypher 契约、读失败 |
| `tests/unit/test_consolidation_worker_entrypoint.py` | 创建 | enabled/invalid config stub 路径（mock settings/driver） |
| `tests/contract/test_con004_scope_boundaries.py` | 创建 | 白名单、CON-001/002/003 零语义 diff、无 ES/Mongo |

**白名单外任何 `tests/**` 变更 → FAIL**（运行 CON-001/002/003 回归但不在白名单内编辑）。

### 17.1 governance_file_whitelist（Release Operator 各 phase）

| Phase | 允许路径 | 目的 |
|---|---|---|
| `PLAN_LANDING` | `02_开发管理/tasks/CON-004-apscheduler-mutex-failure-recovery.md` | 已批准 Task Plan |
| `PLAN_LANDING` | `02_开发管理/progress.md` | 规划态登记 |
| `PLAN_LANDING` | `02_开发管理/master_plan.md` | CON-004 规划登记 |
| `IMPLEMENTATION_RELEASE` | §16 production_file_whitelist 全部 | 实现 |
| `IMPLEMENTATION_RELEASE` | §17 test_file_whitelist 全部 | 测试 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/tasks/CON-004-apscheduler-mutex-failure-recovery.md` | 执行记录 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/progress.md` | 状态登记 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/master_plan.md` | 状态备注 |
| `POST_MERGE_CLEANUP` | 上述三份治理文件 | 完成登记 |

### 17.2 PLAN_LANDING commit contract

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含：

1. `02_开发管理/tasks/CON-004-apscheduler-mutex-failure-recovery.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`

Commit message（精确）：

```text
docs(plan): add CON-004 apscheduler mutex failure recovery plan
```

随后从更新后的 `main` 创建 exact feature branch `feat/CON-004-apscheduler-mutex-failure-recovery`。

## 18. minimum_test_plan

### 18.1 Unit — Run orchestration（`test_consolidation_run_service.py`）

| ID | 场景 | 预期 |
|---|---|---|
| U1 | 单用户多页 happy path（fake batch：2 满页 + 终止页） | 每页调用 CON-002；有 scored 时 CON-003；cursor 递进；`batch_count` 正确 |
| U2 | 多用户顺序处理 | 枚举 2 users；每用户独立 cursor=None 起始；不跨用户混 cursor |
| U3 | Cursor 确定性推进 | 满页 `has_more=True` → `next_cursor`；终止页 `has_more=False` |
| U4 | 零候选用户 / 空枚举 | success；`scanned_count=0` |
| U7 | 版本冲突不终止 run | fake write `version_conflict_count>0`；run 完成 success |
| U8 | 同一 run 内所有 `process_batch` / `write_batch` 收到相同 `evaluation_time` | 断言调用参数 |
| U9 | CON-002 读失败 | `consolidation_read_failed`；run 终止；`read_failed` metric |
| U10 | CON-003 写失败 | 前批已提交（fake 记录）；`consolidation_write_failed`；`write_failed` metric |
| U11 | 指标聚合 | scanned/updated/version_conflict/invalid/missing/batch/run_duration 精确 |
| U12 | Run 中异常 | mutex `finally` 释放；后续触发可获取锁 |
| U13 | 下一 scheduled run 恢复语义 | 第一次 partial success 后第二次 run 新 `evaluation_time`；fake 断言重扫 |
| U18 | `skipped` 永不进入 write | fake write 未被调用当 scored 空 |

### 18.2 Unit — Mutex（`test_consolidation_mutex.py`）

| ID | 场景 | 预期 |
|---|---|---|
| U5 | 重叠触发：锁已被持有 | 第二次 `try_acquire` 失败；`consolidation_already_running`；`skipped_trigger_count++` |
| U6 | 异常路径释放锁 | run 内抛错后 `release`；第三次可获取 |

### 18.3 Unit — Scheduler（`test_consolidation_scheduler.py`）

| ID | 场景 | 预期 |
|---|---|---|
| U14 | Job 注册参数 | CronTrigger cron/timezone；`max_instances`/`coalesce`/`misfire_grace_time` 与 settings 一致 |
| U15 | `enabled=false` | 不注册 Job |
| U16 | invalid cron（settings 层） | Worker `main` exit ≠ 0（或启动前拒绝） |
| U17 | shutdown | `scheduler.shutdown` 调用；stop 后不再触发新 Job |

### 18.4 Unit — User enumeration（`test_consolidation_user_enumeration_repository.py`）

| ID | 场景 | 预期 |
|---|---|---|
| U2b | DISTINCT user_id 排序 | mock records → 有序列表 |
| U9b | Neo4j 读失败 | 向上抛；编排层映射 `consolidation_read_failed` |

### 18.5 Unit — Worker entrypoint（`test_consolidation_worker_entrypoint.py`）

| ID | 场景 | 预期 |
|---|---|---|
| W1 | settings 失败 | exit 1 |
| W2 | enabled=true mock 路径 | scheduler 注册被调用（mock） |

### 18.6 Contract（`test_con004_scope_boundaries.py`）

| ID | 场景 | 预期 |
|---|---|---|
| C1 | 白名单外无 `src/**` 生产变更 | git diff 门禁 |
| C2 | Scheduler Job 无内层无限循环 | 静态/结构断言 |
| C3 | 用户枚举 Cypher 含候选谓词 + DISTINCT | 静态断言 |
| C4 | 不修改 CON-001/002/003 服务文件 | diff 断言 |
| C5 | `consolidation_worker.py` 在本任务 MODIFY 允许 | 白名单显式 |
| C6 | 无 ES/Mongo/Kafka client 于 consolidation worker | import 断言 |
| C7 | 无 CON-005 Integration/E2E 测试文件 | diff 断言 |

### 18.7 Integration / E2E

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — **CON-005** |

### 18.8 失败注入与并发

| ID | 场景 | 预期 |
|---|---|---|
| F1 | 并发两次 run 触发（mutex） | 仅一个执行；另一个 skipped |
| F2 | run 内读失败后 mutex 可再次获取 | U6 + U9 |
| F3 | write 失败后已提交批不被回滚 | U10 fake 断言 |

## 19. classification_labels

| ID | 项 | 分类 | 说明 |
|---|---|---|---|
| CL-1 | 修改 CON-001/002/003 已完成语义 | **HARD_BLOCK** | 前置 closed |
| CL-2 | 分布式锁 / 多实例调度 | **HARD_BLOCK** | §2.3.14 非目标 |
| CL-3 | 持久化 cursor / run 表 | **HARD_BLOCK** | §2.3.13 规则 6 |
| CL-4 | ES/Mongo/Kafka 读写 | **HARD_BLOCK** | 阶段非目标 |
| CL-5 | 每批不同 `evaluation_time` | **HARD_BLOCK** | §2.3.2 规则 7 |
| CL-6 | 互斥锁未 finally 释放 | **HARD_BLOCK** | §2.3.13 规则 8 |
| CL-7 | 版本冲突导致 run 终止 | **HARD_BLOCK** | §2.3.13 规则 3–4 |
| CL-8 | 读/写失败未终止 run | **HARD_BLOCK** | §2.3.13 规则 2–3 |
| CL-9 | 测试未覆盖用户 §18 场景 | **HARD_BLOCK** | 用户明确要求 |
| CL-10 | 修改 Settings Contract | **HARD_BLOCK** | dependency_changes_expected=NONE |
| CL-11 | DEV-006 / PR #13 | **HARD_BLOCK** | 治理永久禁止 |
| CL-12 | `neo4j_timeout_seconds` 只读注入自 `memory_retrieval` | **SAFE_AUTO_REMEDIATION** | 与 CON-002/003 一致 |
| CL-13 | 独立 `consolidation_run.py` models | **SAFE_AUTO_REMEDIATION** | LD-1 |
| CL-14 | `consolidation_user_enumeration_repository` 新文件而非改 CON-002 repo | **SAFE_AUTO_REMEDIATION** | LD-2 |
| CL-15 | `consolidation_run_telemetry.py` helper | **SAFE_AUTO_REMEDIATION** | LD-3 |
| CL-16 | `consolidation_runs_total` status 标签集（success/read_failed/write_failed） | **MVP_LOCAL_DECISION** | LD-4；§3.27 未枚举 |
| CL-17 | 互斥跳过不计入 `consolidation_runs_total` | **MVP_LOCAL_DECISION** | LD-5 |
| CL-18 | `enabled=false` idle 直至 SIGTERM | **MVP_LOCAL_DECISION** | LD-6 |
| CL-19 | Integration Neo4j Fixture | **DEFERRED** | CON-005 |
| CL-20 | Consolidation E2E | **DEFERRED** | CON-005 |
| CL-21 | OPS-002 全量日志/指标审计 | **DEFERRED** | OPS-002 |

## 20. dependency_changes_expected

```yaml
dependency_changes_expected: NONE
```

`apscheduler>=3.11,<4` 已在 `pyproject.toml`；本任务 **禁止**新增依赖或版本变更。

## 21. mvp_local_decisions

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | Run 领域模型独立 `consolidation_run.py` | 与 batch/write 模型解耦 |
| LD-2 | 用户枚举新仓储文件；不修改 CON-002 `consolidation_memory_read_repository.py` | 保护 CON-002 白名单 closed 语义 |
| LD-3 | Telemetry helper 独立文件 | 集中 §2.3.13 日志 + Prometheus |
| LD-4 | `consolidation_runs_total` labels: `success`, `read_failed`, `write_failed` | §3.27 仅列 metric 名 |
| LD-5 | Mutex 跳过仅 `skipped_trigger_count`；不 increment runs_total | 非完整 run |
| LD-6 | `enabled=false`：进程 idle 等待 `stop_event`（无 scheduler） | Worker 仍可健康检查 Neo4j |
| LD-7 | Orchestrator 注入 `batch_service`/`write_service` 接口（Protocol 或具体类）便于 fake | Unit 无 CON-005 漂移 |
| LD-8 | `evaluation_time` 来自 APScheduler `scheduled_run_time` UTC Unix 秒 | §2.3.4 计划触发时间 |

## 22. 任务目标

交付 §2.3.11 巩固 **运行编排** + §3.22 APScheduler + §2.3.4 进程内互斥锁 + §2.3.13 失败恢复与运行指标 + `consolidation_worker` 生产接线。

可验证目标：

1. **`ConsolidationRunService`** — 用户枚举、per-user cursor 循环、CON-002/003 编排、指标聚合、`evaluation_time` 单值传播。
2. **`ConsolidationScheduler`** — `AsyncIOScheduler` + `CronTrigger` + settings 对齐 + shutdown。
3. **`ConsolidationMutex`** — 进程内锁、重叠跳过、finally 释放。
4. **`ConsolidationUserEnumerationRepository`** — Neo4j DISTINCT `user_id` + 候选谓词。
5. **`consolidation_worker`** — 可启动、可 shutdown、Neo4j-only 依赖。
6. **测试** — §18 U1..U18 + C1..C7 + F1..F3 全部通过。
7. Ruff / Mypy 通过；Review 无 P0/P1。

## 23. 非目标与黑名单（must_not）

- 修改 `consolidation_importance.py`（CON-001）— **禁止**。
- 修改 `consolidation_batch_service.py` / `consolidation_memory_read_repository.py`（CON-002）— **禁止**。
- 修改 `consolidation_write_service.py` / `consolidation_memory_write_repository.py`（CON-003）— **禁止**。
- CON-005 Integration/E2E — **禁止本任务实现**。
- ES / Mongo / Kafka — **禁止**。
- Redis 分布式锁 — **禁止**。
- 持久化 cursor / `memory_consolidation_task` 表 — **禁止**。
- `memory_version` / `updated_time` 写入 — **禁止**。
- 修改 `MemoryConsolidationSettings` / validators — **禁止**。
- 独立 Consolidation HTTP API — **禁止**。
- DEV-006 / PR #13 — **永久禁止**。

## 24. 当前代码状态

- **已存在**：`ConsolidationBatchService` + `ConsolidationMemoryReadRepository`（CON-002）；`ConsolidationWriteService` + `ConsolidationMemoryWriteRepository`（CON-003）；`compute_consolidation_importance`（CON-001）；`MemoryConsolidationSettings` + `validate_memory_consolidation`（CronTrigger 校验）；`CONSOLIDATION_RUNS_TOTAL`（metrics.py）；`extraction_worker.py` 生命周期参考；`apscheduler` 依赖。
- **可复用**：`scored_candidates_to_write_rows`；`ConsolidationBatchRequest`/`ConsolidationBatchResult`；`ConsolidationWriteBatchRequest`/`ConsolidationWriteBatchResult`；Neo4j `AsyncDriver` 模式；`get_settings` / `configure_logging` / shutdown settings。
- **当前缺失**：Run 编排服务、用户枚举仓储、进程内 mutex、Scheduler 适配器、run telemetry、可启动的 `consolidation_worker`。
- **与技术规格不一致之处**：`consolidation_worker.py` 仍为 stub（exit 1）；§2.3.11 / §3.22 调度与编排未实现。
- **前置任务检查**：CON-003 completed（PR #52 MERGED @ `7337c86`）；CON-002 completed（PR #51）；CON-001 completed（PR #50）；EXT-001..009 completed；RET-001..006 completed。

## 25. 实现方案

### Step 1 — Run 领域模型

- **文件**：`src/memory_system/domain/models/consolidation_run.py`
- **类型**：`ConsolidationRunMetrics`；`ConsolidationRunResult`（`run_id`, `evaluation_time`, `status`, `metrics`）；`ConsolidationRunStatus` enum
- **错误处理**：frozen dataclass；无 I/O

### Step 2 — 用户枚举仓储

- **文件**：`src/memory_system/infrastructure/neo4j/consolidation_user_enumeration_repository.py`
- **类**：`ConsolidationUserEnumerationRepository`
- **方法**：`async def list_user_ids(evaluation_time: int) -> list[str]`
- **Cypher**：§5 权威示意；`authorized_enumeration_cypher_queries()` 供契约测试
- **超时**：构造函数注入 `settings.memory_retrieval.neo4j_timeout_seconds`（与 CON-002 `ConsolidationMemoryReadRepository` 一致；SF-2）
- **错误处理**：Neo4j 异常向上传播 → 编排层 `consolidation_read_failed`

### Step 3 — 进程内互斥锁

- **文件**：`src/memory_system/infrastructure/consolidation_mutex.py`
- **类**：`ConsolidationMutex` — `try_acquire() -> bool`；`release()`；内部 `asyncio.Lock`
- **规则**：§7；非阻塞 `try_acquire`

### Step 4 — Run 编排服务

- **文件**：`src/memory_system/domain/services/consolidation_run_service.py`
- **类**：`ConsolidationRunService`
- **依赖**：`ConsolidationBatchService`；`ConsolidationWriteService`；`ConsolidationUserEnumerationRepository`；`ConsolidationMutex`；telemetry helper
- **核心方法**：`async def execute_run(evaluation_time: int) -> ConsolidationRunResult`
- **流程**：§3 run_contract + §4 pagination + §9 failure_recovery
- **注入**：`Settings`；可选 `clock` 仅用于 `run_duration_ms`（**不得**用于 `evaluation_time`）

### Step 5 — Scheduler 适配器

- **文件**：`src/memory_system/infrastructure/scheduling/consolidation_scheduler.py`
- **函数**：`def create_consolidation_scheduler(settings, run_callback) -> AsyncIOScheduler`
- **Job**：`memory_consolidation_run`；从 event `scheduled_run_time` 提取 `evaluation_time` 调用 `run_callback`
- **参数**：§8 scheduler_contract

### Step 6 — Telemetry

- **文件**：`src/memory_system/observability/consolidation_run_telemetry.py`
- **函数**：`log_run_completed(...)`；`record_run_status(status)` → `CONSOLIDATION_RUNS_TOTAL`；`increment_skipped_trigger()`
- **规则**：§11；无 content 日志

### Step 7 — Worker entrypoint

- **文件**：`src/memory_system/entrypoints/consolidation_worker.py`（**修改**）
- **模式**：`extraction_worker` — settings、Neo4j ping、scheduler、signal handlers、graceful shutdown
- **Neo4j**：`AsyncGraphDatabase.driver` + repository 构造使用 `settings.memory_retrieval.neo4j_timeout_seconds`（SF-2；与 CON-002/003 一致）
- **enabled=false**：跳过 scheduler；`await stop_event.wait()`
- **shutdown**：§13 worker_entrypoint_scope

### Step 8 — 单元与契约测试

- **文件**：§17 test_file_whitelist
- **Mock**：`FakeBatchService` / `FakeWriteService` 记录调用参数与可配置失败
- **覆盖**：§18 minimum_test_plan

## 26. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/consolidation_run.py` | 创建 | Run metrics/result 模型 |
| `src/memory_system/domain/services/consolidation_run_service.py` | 创建 | 编排核心 |
| `src/memory_system/infrastructure/consolidation_mutex.py` | 创建 | 进程内互斥锁 |
| `src/memory_system/infrastructure/scheduling/consolidation_scheduler.py` | 创建 | APScheduler 注册 |
| `src/memory_system/infrastructure/neo4j/consolidation_user_enumeration_repository.py` | 创建 | 用户枚举 |
| `src/memory_system/observability/consolidation_run_telemetry.py` | 创建 | 日志与 Prometheus |
| `src/memory_system/entrypoints/consolidation_worker.py` | 修改 | 生产 Worker 接线 |
| `tests/unit/test_consolidation_run_service.py` | 创建 | 编排测试 |
| `tests/unit/test_consolidation_mutex.py` | 创建 | 互斥测试 |
| `tests/unit/test_consolidation_scheduler.py` | 创建 | Scheduler 测试 |
| `tests/unit/test_consolidation_user_enumeration_repository.py` | 创建 | 枚举仓储测试 |
| `tests/unit/test_consolidation_worker_entrypoint.py` | 创建 | Entrypoint 测试 |
| `tests/contract/test_con004_scope_boundaries.py` | 创建 | 白名单与边界 |

## 27. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 适用（委托） | 单批写由 CON-003 transaction 保证；run 级无跨批事务 |
| 幂等 | 适用 | `last_consolidated_time` + 确定性公式；§14 |
| 并发 | 适用 | 进程内 mutex 防双 run；萃取并发由 CON-003 乐观锁 |
| 版本冲突 | 适用 | 聚合计数；不终止 run；§10 |
| 用户隔离 | 适用 | 枚举 + per-user 批次；§5 UE-6 |
| 部分失败 | 适用 | 读/写失败终止 run；skip/冲突继续；§9 |
| 进程异常恢复 | 适用 | 无补偿；下次 run 新 `evaluation_time`；§14 |

## 28. 测试计划（模板 §8 映射）

### Unit Test — 见 §18.1–18.5

### Contract Test — 见 §18.6

### Integration Test — **DEFERRED**（§18.7，CON-005）

### E2E Test — **DEFERRED**（§18.7，CON-005）

### 失败注入与并发 — 见 §18.8

## 29. 验收标准

- [x] `pytest tests/unit/test_consolidation_run_service.py tests/unit/test_consolidation_mutex.py tests/unit/test_consolidation_scheduler.py tests/unit/test_consolidation_user_enumeration_repository.py tests/unit/test_consolidation_worker_entrypoint.py tests/contract/test_con004_scope_boundaries.py` 全部通过
- [x] U1 单用户多页 happy path；U2 多用户；U3 cursor 推进
- [x] U8 同一 `evaluation_time` 传播至所有 CON-002/003 调用
- [x] U5/U6 mutex 防重叠且异常释放
- [x] U7 版本冲突不终止 run
- [x] U11 missing_evidence/invalid 不终止 run
- [x] U9 读失败终止；U10 写失败终止且前批保留
- [x] U13 下次 scheduled run 恢复语义
- [x] U14/U17 Scheduler 注册与 lifecycle
- [x] C4 CON-001/002/003 服务文件零 diff；C7 无 CON-005 漂移
- [x] `consolidation_worker` 可启动（mock/smoke）且 graceful shutdown 路径存在
- [x] Ruff 通过
- [x] Mypy 通过（新增文件）
- [ ] Review 无 P0/P1

## 30. 风险与阻塞项

- **设计文档冲突**：无；用户枚举谓词与 §2.3.4 / CON-002 对齐。
- **当前代码冲突**：无；规划基线 clean @ `8998f62`。
- **前置任务**：CON-003 PR #52 MERGED；CON-002 PR #51；CON-001 PR #50。
- **未批准依赖**：`dependency_changes_expected=NONE`。
- **API/Schema 变化**：无 HTTP；内部 orchestration + worker entrypoint。
- **其他风险**：APScheduler `scheduled_run_time` 时区 — LD-8 + settings timezone；与 extraction_worker shutdown 竞态 — §3.25 deadline 对齐。

## 31. Git 计划

```yaml
branch: "feat/CON-004-apscheduler-mutex-failure-recovery"
expected_commits:
  - "docs(plan): add CON-004 apscheduler mutex failure recovery plan"
  - "feat(con): add consolidation run orchestration and scheduler wiring"
out_of_scope_changes:
  - "CON-001/002/003 服务语义修改"
  - "settings/ validators 修改"
  - "ES/Mongo/Kafka 接线"
  - "CON-005 Integration/E2E 测试"
  - "DEV-006 / PR #13"
```

## 32. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

## 33. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 21:45 UTC | Step 1–7 实现 | 7 个生产文件 + consolidation_worker 接线 | — | 无 |
| 2026-08-13 21:50 UTC | Step 8 测试 | 6 个测试文件（U1..U18/C1..C7/F1..F3） | 37 passed | 无 |
| 2026-08-13 21:52 UTC | 静态检查 | ruff + mypy 新增 src | PASS | 无 |

## 34. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/domain/models/consolidation_run.py` | 已创建 |
| `src/memory_system/domain/services/consolidation_run_service.py` | 已创建 |
| `src/memory_system/infrastructure/consolidation_mutex.py` | 已创建 |
| `src/memory_system/infrastructure/scheduling/consolidation_scheduler.py` | 已创建 |
| `src/memory_system/infrastructure/neo4j/consolidation_user_enumeration_repository.py` | 已创建 |
| `src/memory_system/observability/consolidation_run_telemetry.py` | 已创建 |
| `src/memory_system/entrypoints/consolidation_worker.py` | 已修改 |
| `tests/unit/test_consolidation_run_service.py` | 已创建 |
| `tests/unit/test_consolidation_mutex.py` | 已创建 |
| `tests/unit/test_consolidation_scheduler.py` | 已创建 |
| `tests/unit/test_consolidation_user_enumeration_repository.py` | 已创建 |
| `tests/unit/test_consolidation_worker_entrypoint.py` | 已创建 |
| `tests/contract/test_con004_scope_boundaries.py` | 已创建 |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit + Contract | `pytest tests/unit/test_consolidation_run_service.py tests/unit/test_consolidation_mutex.py tests/unit/test_consolidation_scheduler.py tests/unit/test_consolidation_user_enumeration_repository.py tests/unit/test_consolidation_worker_entrypoint.py tests/contract/test_con004_scope_boundaries.py` | 37 passed |
| Integration | — | DEFERRED (CON-005) |
| E2E | — | DEFERRED (CON-005) |
| Ruff | `ruff check` on 7 new src files | PASS |
| Mypy | `mypy` on 7 new src files | PASS |

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
branch: feat/CON-004-apscheduler-mutex-failure-recovery
plan_commit: e124b23
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`tested`
