# CON-005 Consolidation Integration + E2E

## 1. 任务信息

```yaml
task_id: CON-005
task_name: Consolidation Integration + E2E
status: committed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "010d74112fb760907e710f2ba27123e021dd3d61"
branch: "feat/CON-005-consolidation-integration-e2e"
milestone: "v0.5.0-consolidation"
created_at: "2026-08-13 22:15 UTC"
updated_at: "2026-08-13 23:30 UTC"
spec_sections:
  - "§2.3.4 调度、互斥与批量扫描（cursor、evaluation_time、用户隔离 — E2E 验证）"
  - "§2.3.8 强化与软遗忘规则（边界 only — 无 status/ES/content 副作用）"
  - "§2.3.9 Neo4j 批量更新与并发控制（Integration + E2E 真实驱动）"
  - "§2.3.11 完整处理流程（垂直切片 E2E 权威边界）"
  - "§2.3.12 MVP 配置（batch_size 等只读消费 — 测试 monkeypatch 允许）"
  - "§2.3.13 失败处理与恢复（读/写失败、版本冲突、部分进度、指标）"
  - "§2.3.14 MVP 实现边界（单实例本地锁；无分布式/持久化 cursor）"
  - "§3.22 Consolidation Scheduler（边界 only — APScheduler E2E 非必需）"
  - "§3.25 优雅关闭（边界 only — 本任务不新增 worker E2E）"
  - "§3.28 测试策略（Integration + E2E 层；失败注入；Neo4j Fixture）"
prerequisites:
  formal:
    - "CON-004 — SATISFIED/completed（PR #53 MERGED）；ConsolidationRunService + mutex + scheduler + worker wiring"
    - "CON-003 — SATISFIED/completed（PR #52 MERGED）；ConsolidationWriteService + optimistic-lock write"
    - "CON-002 — SATISFIED/completed（PR #51 MERGED）；ConsolidationBatchService + cursor batch read"
    - "CON-001 — SATISFIED/completed（PR #50 MERGED）；compute_consolidation_importance"
    - "EXT-001..009 — SATISFIED/completed"
    - "RET-001..006 — SATISFIED/completed（v0.4.0-memory-retrieval closed）"
  implementation_reuse:
    - "ConsolidationRunService.execute_run（CON-004；真实编排入口）"
    - "ConsolidationBatchService + ConsolidationMemoryReadRepository（CON-002）"
    - "ConsolidationWriteService + ConsolidationMemoryWriteRepository（CON-003）"
    - "ConsolidationUserEnumerationRepository（CON-004）"
    - "ConsolidationMutex（CON-004）"
    - "consolidation_worker.py 生产接线模式（只读参考；E2E 使用 in-process 等价 wiring）"
    - "compute_consolidation_importance（CON-001；E2E 断言公式输出）"
    - "CONSOLIDATION_RUNS_TOTAL + consolidation_run_telemetry（既有指标；仅验证）"
    - "tests/integration/test_ext005_memory_recall_neo4j.py — Neo4j-only compose.test 模式"
    - "tests/integration/test_ret004_evidence_aggregation.py — Neo4j fixture + DETACH DELETE 清理"
    - "tests/e2e/conftest.py — compose.test 隔离模式参考（本任务 Neo4j-only 子集）"
    - "tests/support/ret003_neo4j_fixtures.py — Memory 节点字段参考"
  baseline_evidence:
    branch: "main"
    head: "010d74112fb760907e710f2ba27123e021dd3d61"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=010d74112fb760907e710f2ba27123e021dd3d61"
approval_gates:
  planning: "AWAIT_PLAN_REVIEW"
  approval_posture: PLAN_APPROVED
  amendment_recorded: true
  human_plan_approved: true
  human_plan_approved_at: "2026-08-13T14:37:00Z"
  developer_authorized: true
  reviewer_authorized: true
  release_operator_authorized: true
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feature branch feat/CON-005-consolidation-integration-e2e"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup; milestone v0.5.0-consolidation closure on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_read_scope: "Neo4j read-only — CON-002 candidate batch + CON-004 user enumeration（Integration/E2E 验证）"
durable_write_scope: "Neo4j Memory — importance, last_consolidated_time only（经 CON-003 既有写路径；E2E 验证）"
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
  - "修改 CON-001..004 生产 Service 语义"
stop_if:
  - "任何实现步骤需要修改 CON-001..004 生产 Service 语义（默认 production_file_whitelist=NONE）"
  - "任何实现步骤需要 ES / Mongo / Kafka 写入或 HTTP API"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要 Session→Archive→Extraction 全链路 E2E（归属 E2E-001）"
  - "E2E 暴露生产缺陷时在本任务内修复（须 HALT → 报告 owning task）"
blocking_open_issues: []
nonblocking_open_issues: []
```

## 2. authoritative_scope

本任务 **唯一** 拥有 Consolidation 阶段 **真实 Neo4j Integration + E2E 垂直切片**；闭合 CON-001..004 延后的 Integration/E2E；闭合 **`v0.5.0-consolidation` 里程碑**；**不** 拥有公式/读 Cypher/写 Cypher/编排生产语义变更。

| 维度 | 归属 CON-005 | 非 CON-005（显式排除） |
|---|---|---|
| 真实 Neo4j Integration（CON-002/003/004 仓储 + 事务） | **是** — §INT-* | 修改生产 Cypher 语义 |
| Consolidation **垂直切片 E2E**（seed → run → durable readback） | **是** — §E2E-* | Session→Consolidation 全链 |
| `ConsolidationRunService` **生产接线** in-process E2E | **是** — 非 fake CON-002/003 ports | 修改 `consolidation_run_service.py` |
| 固定 `evaluation_time` E2E 断言 | **是** | 墙钟 `time.time()` 作为 evaluation_time |
| `missing_evidence` / `version_conflict` / 读写在真实 Neo4j 上验证 | **是** | 修改 CON-003 乐观锁语义 |
| 用户隔离 + cursor 分页 + 多页无 dup/skip | **是** — E2E-2 | 持久化 cursor 表 |
| 部分进度恢复（Run A fail@T1 → Run B new run@T2>T1 全量重扫） | **是** — E2E-6 / §6.3 | 补偿事务；同 T 重试跳过已巩固行 |
| 互斥锁重叠跳过 + finally 释放（最小子场景） | **是** — E2E-5 子断言 | 长时间 APScheduler wall-clock E2E |
| `consolidation_runs_total{status}` + 结构化计数器验证 | **是** — 既有指标 only | 新增 Prometheus 指标名 |
| `compute_consolidation_importance` / 读 Cypher / 写 Cypher | **否** — 仅消费 | **CON-001/002/003** |
| Run 编排 / mutex / scheduler 生产实现 | **否** — E2E 调用 | **CON-004** |
| §2.3.8 软遗忘副作用（status/ES delete/content clear） | **否** — **禁止** | 任何阶段 |
| ES / Mongo / Kafka durable 写 | **否** | **HARD_BLOCK** |
| 独立 Consolidation HTTP API | **否** | 阶段非目标 |
| Redis 分布式锁 / 多实例调度长运行证明 | **否** | §2.3.14 / **DEFERRED** |
| Session→Archive→Extraction→Consolidation 全链路 | **否** | **E2E-001 / §3.32 #4** |
| DEV-006 / PR #13 | **否** | **HARD_BLOCK** |

## 3. e2e_boundary

### 3.1 垂直切片权威流程

```text
Neo4j seed (Memory + Evidence w/ archive_id)
  → ConsolidationUserEnumerationRepository.list_user_ids(evaluation_time)
  → per-user cursor loop:
       ConsolidationBatchService.process_batch (real CON-002 repo)
       → compute_consolidation_importance (CON-001)
       → ConsolidationWriteService.write_batch (real CON-003 repo) [scored only]
  → ConsolidationRunService.execute_run(evaluation_time)  # 生产编排
  → Neo4j durable readback (importance, last_consolidated_time, memory_version, unrelated fields)
```

| 项 | 结论 |
|---|---|
| 驱动入口 | **`ConsolidationRunService.execute_run(fixed_evaluation_time)`** — 与 `consolidation_worker` 回调等价 |
| 禁止 | Fake/mock `ConsolidationBatchService` / `ConsolidationWriteService` 作为 E2E 主路径 |
| `evaluation_time` | **固定常量** `CON005_EVALUATION_TIME`（如 `1_700_100_000`）；全场景统一或可参数化但不得墙钟 |
| 真实基础设施 | **Neo4j 必须**；`init-infra` migration |
| ES / Mongo / Kafka / Redis | **不需要** |
| HTTP API | **不需要** |
| `consolidation-worker` 容器 | **不启动** — in-process 生产 wiring 足够 |
| 生产零 diff 默认 | E2E 暴露 CON-001..004 缺陷 → **HALT**；不得在本任务修复 |

### 3.2 CON-004 §15 边界闭合（显式取代）

> **CON-005 取代 CON-004 §15 中 Integration/E2E 与 in-process run/mutex 条目**；**不**取代 Worker 容器 / APScheduler wall-clock 长运行 E2E（仍 **DEFERRED**）。

| CON-004 §15 DEFERRED | CON-005 归属 | 闭合方式 |
|---|---|---|
| 真实 Neo4j Integration Fixture | **CON-005 拥有** | §INT-1..INT-6 Integration 测试 |
| Compose E2E consolidation 全链路（in-process 垂直切片） | **CON-005 拥有** | §E2E-1..E2E-6 |
| 进程内 `execute_run` + mutex 最小子场景 | **CON-005 拥有** | E2E-5 INJ-6 |
| 多服务 Worker + 真实 Scheduler **长时间 wall-clock** E2E | **仍 DEFERRED** | LD-2：CON-004 Unit U14–U17 足够；**禁止**本任务启动 `consolidation-worker` 容器或 Cron 等待 |
| Unit fake ports 编排语义 | 保留 CON-004 | CON-005 使用真实 ports |

## 4. infrastructure_requirements

### 4.1 Compose 与隔离

| 项 | 值 |
|---|---|
| 入口 | `./scripts/compose.sh --stack=test --embedding=none` |
| Project | `memory-system-test`（`compose.test.yaml` 独立 volume） |
| 启动服务 | **`neo4j` only** + `init-infra` |
| 不启动 | `redis`, `mongodb`, `kafka`, `elasticsearch`, `memory-api`, `extraction-worker`, `consolidation-worker`, embedding |
| Teardown | `compose down -v`（module fixture）；`MATCH (n) DETACH DELETE n` per-test |
| 连接 | `bolt://{neo4j_ip}:7687` 或 `neo4j://{neo4j_ip}:7687`（与 EXT-005 / RET-004 一致） |
| 模式参考 | `tests/integration/test_ext005_memory_recall_neo4j.py` Neo4j-only module fixture |

### 4.2 Fixture 分层

| Fixture | Scope | 用途 |
|---|---|---|
| `con005_neo4j_uri` | module | Neo4j-only compose 启停 + init-infra |
| `con005_neo4j_driver` | function | AsyncDriver + connectivity verify |
| `_clean_graph` | function autouse | `DETACH DELETE` 隔离 |
| `con005_settings` | function | `get_settings()` + monkeypatch `memory_consolidation.batch_size` 等 |
| `con005_run_service` | function | 生产等价 wiring → `ConsolidationRunService` |
| `con005_seed_*` | function | `tests/support/con005_neo4j_fixtures.py` 种子 helpers |

### 4.3 种子契约（`con005_neo4j_fixtures`）

**Memory 节点**（对齐 CON-002 读契约）：

- `user_id`, `memory_id`, `memory_type`, `status` ∈ `{active, conflicted, superseded}`
- `created_time <= evaluation_time`
- `last_consolidated_time IS NULL` 或 `< evaluation_time`（eligible）
- `confidence`, `latest_source_time`, `importance`（初始值用于断言变更）
- `memory_version`（int，乐观锁）
- `content`（非空；E2E 断言 **不**变更）
- **禁止**设置 `retrieval_count` / `last_retrieved_time` 作为公式输入（CON-001 不使用）

**Evidence 节点**（`count(DISTINCT e.archive_id)`）：

- `Evidence`-[:`SUPPORTS`]->`Memory`
- `e.user_id = m.user_id`（双端隔离）
- **`e.archive_id` 必填**（DISTINCT 计数权威字段）
- 同 `archive_id` 多条 Evidence → count 去重（E2E-1 子断言可选）

**固定时间**：

```python
CON005_USER_A = "user_con005_a"
CON005_USER_B = "user_con005_b"
CON005_EVALUATION_TIME = 1_700_100_000  # T1 — 默认单 run / E2E-1..5
CON005_EVALUATION_TIME_T2 = 1_700_200_000  # T2 — E2E-6 Run B；**必须** T2 > T1
```

## 5. production_wiring_contract

E2E / Integration 必须通过 **与 `consolidation_worker.py` 等价的生产组装** 构建 `ConsolidationRunService`（helper 内实现；**不**修改 worker 文件）：

```text
ConsolidationMemoryReadRepository(driver, neo4j_timeout_seconds)
ConsolidationMemoryWriteRepository(driver, neo4j_timeout_seconds)
ConsolidationBatchService(read_repository)
_WriteBatchAdapter(write_repository)  # 调用 write_batch()
ConsolidationUserEnumerationRepository(driver, neo4j_timeout_seconds)
ConsolidationMutex()
ConsolidationRunService(
    batch_service=...,
    write_service=...,
    enumeration_repository=...,
    mutex=...,
    settings=...,
)
```

| 规则 | 说明 |
|---|---|
| PW-1 | **禁止** E2E 主路径使用 CON-004 Unit 的 `FakeBatchService` / `FakeWriteService` |
| PW-2 | 允许测试 helper 包装 repository 以注入失败（见 §6） |
| PW-3 | `batch_size` 经 `settings.memory_consolidation.batch_size` monkeypatch（E2E-2 小批次） |
| PW-4 | `execute_run(evaluation_time=CON005_EVALUATION_TIME)` 直接调用 |

## 6. failure_injection_contract

**原则**：测试侧 wrapper / `unittest.mock` / `pytest monkeypatch` 注入；**禁止**新生产 hook、新 Settings 字段、修改 CON-001..004 源码。

### 6.1 注入点（权威）

| 注入点 | 机制 | 适用场景 |
|---|---|---|
| `FailingConsolidationMemoryWriteRepository`（test helper 子类） | 第 N 次 `write_batch` 抛 `ConsolidationWriteError` | E2E-5 write_failed |
| `FailingConsolidationMemoryReadRepository`（test helper 子类） | 第 N 次 `fetch_candidate_batch` 抛 `ConsolidationReadError` | E2E-5 read_failed |
| Direct Neo4j Cypher（测试 helper） | `SET m.memory_version = m.memory_version + 1` 模拟萃取竞态 | E2E-4 |
| `asyncio.create_task` 并发两次 `execute_run` | 第二路 `SKIPPED` + `consolidation_already_running` | E2E-5 mutex 子场景 |
| Run A partial + 注入读/写失败 | 第一页已提交后 fail@T1；Run B 新 `run_id` + **新** `evaluation_time=T2>T1` | E2E-6 |

### 6.2 注入矩阵

| INJ ID | 注入 | Run 结果 | 已完成批次 | Mutex | 绑定场景 |
|---|---|---|---|---|---|
| INJ-1 | 无 | `SUCCESS` | — | released | E2E-1, E2E-2 |
| INJ-2 | 零 qualifying Evidence | `SUCCESS`；`missing_evidence_count>0` | — | released | E2E-3 |
| INJ-3 | 写前 bump `memory_version` | `SUCCESS`；`version_conflict_count>0` | 其他行 committed | released | E2E-4 |
| INJ-4 | 写失败（中途） | `WRITE_FAILED` | 前序批次保留 | released | E2E-5 |
| INJ-5 | 读失败（中途） | `READ_FAILED` | 已提交写保留 | released | E2E-5 |
| INJ-6 | 并发第二路 run | 第二路 `SKIPPED` | — | 第一路结束后可再获取 | E2E-5 mutex |
| INJ-7 | Run A@T1 部分成功 + 读/写 fail；Run B@T2（T2>T1） | B=`SUCCESS`；T1 已提交行 durable；T1 行在 T2 **重新入选**并写 `last_consolidated_time=T2` | A 已提交保留；无补偿/回滚 | released | E2E-6 |

### 6.3 `evaluation_time` 与候选 eligibility 权威区分（E2E-6 / INJ-7）

**权威候选谓词**（CON-002 / CON-004 一致）：

```text
last_consolidated_time IS NULL OR last_consolidated_time < evaluation_time
```

| 场景 | Run A | Run B | `last_consolidated_time=T1` 行在 B 中 | 预期 |
|---|---|---|---|---|
| **同 `evaluation_time` 重试**（T1 vs T1） | 部分成功 + fail@T1 | 新 `run_id`；**同一** `evaluation_time=T1`；`cursor=None` 重扫 | **不** eligible（`T1 < T1` 为 false） | 已巩固行跳过；仅未巩固行继续；**非** E2E-6 主路径（见 CON-004 U13 Unit） |
| **新 scheduled run**（T1 然后 T2，T2>T1） | 部分成功 + fail@T1；至少一批经 CON-003 提交 | 新 `run_id`；**新** `evaluation_time=T2`；全用户枚举；每用户 `cursor=None`；**无**持久化 checkpoint | **eligible**（`T1 < T2`） | 全量重扫；T1 行 **重新入选**；按 T2 确定性重算；写 `last_consolidated_time=T2`；Run A 未提交行在 B 中处理 |

**E2E-6 / INJ-7 采用上表第二行（新 run@T2>T1）**。下列 10 条断言 **全部**必须实现：

1. Run A 已提交批次在 fail 后仍 durable（Neo4j 读回）
2. Run B 自 `cursor=None` 全量重扫（每用户；无恢复 cursor）
3. Run A 在 T1 已写 `last_consolidated_time=T1` 的 Memory 在 Run B@T2 **重新被选中**
4. 重算使用 **T2** 作为 `evaluation_time`（`compute_consolidation_importance` 预期值基于 T2）
5. Run B 成功写回 `last_consolidated_time=T2`（含原 T1 行与 Run A 未提交行）
6. Run A 未提交行在 Run B 中被处理并写回
7. **无**持久化 cursor / run-state / checkpoint 表或文件
8. **无**对 Run A 已提交批次的补偿或回滚
9. **禁止**断言「T2 run 跳过 `last_consolidated_time=T1` 的行」
10. 测试注释或 docstring **显式区分**同 T 重试（跳过 T1 行）vs 新 T2 run（T1 行再 eligible、全量重算）

## 7. scheduler_mutex_decision

| 项 | 决策 | 分类 |
|---|---|---|
| APScheduler CronTrigger 长时间 wall-clock E2E | **不实现** — CON-004 `test_consolidation_scheduler.py` U14–U17 已覆盖 | **MVP_LOCAL_DECISION**（LD-2） |
| `consolidation_worker` 容器级启动 E2E | **不实现** — in-process wiring 足够证明垂直切片 | **MVP_LOCAL_DECISION**（LD-3） |
| 进程内 mutex 重叠 + finally 释放 | **E2E-5 最小子场景**（INJ-6；无 sleep 等待 cron） | **HARD_BLOCK**（用户矩阵） |
| 分布式锁 / 多实例 | **DEFERRED** | §2.3.14 |

## 8. metrics_verification

**仅验证既有指标**（§2.3.13 / §3.27）；禁止新增 metric 名。

| ID | 断言 | 方法 | 场景 |
|---|---|---|---|
| MV-1 | `consolidation_runs_total.labels(status="success")._value` 递增 | Prometheus client 读回 | E2E-1 |
| MV-2 | `read_failed` / `write_failed` 递增 | 同上 | E2E-5 |
| MV-3 | mutex 跳过 **不**递增 runs_total | SKIPPED 后 success 计数不变 | E2E-5 INJ-6 |
| MV-4 | `result.metrics.scanned_count` / `updated_count` / `version_conflict_count` / `missing_evidence_count` / `invalid_memory_count` / `batch_count` | `ConsolidationRunResult` | E2E-1..6 子集（`invalid_memory_count` 仅当种子触发 `invalid_memory_state` skip 时断言；**不**新增 outcome 词汇） |
| MV-5 | **禁止**第四 `status` 标签 | 仅 success/read_failed/write_failed | 全部 |

## 9. integration_test_plan（INT-1..INT-6）

> 目录 `tests/integration/`；`@pytest.mark.integration`；Neo4j-only fixture。

| ID | 名称 | 被测组件 | 核心断言 |
|---|---|---|---|
| **INT-1** | CON-002 read repo cursor + archive count | `ConsolidationMemoryReadRepository` | 满页/末页 cursor；`count(DISTINCT archive_id)`；user B Evidence 不计入 user A |
| **INT-2** | CON-002 zero Evidence | 同上 | Memory 返回；`independent_archive_count=0` |
| **INT-3** | CON-003 optimistic write | `ConsolidationMemoryWriteRepository` + `write_batch` | `importance` + `last_consolidated_time` 更新；`memory_version` 不变；`updated_time` 不变 |
| **INT-4** | CON-003 version conflict | 同上 | 错误 `expected_memory_version` → 行未更新；`version_conflict_count=1` |
| **INT-5** | User enumeration | `ConsolidationUserEnumerationRepository` | DISTINCT `user_id` ASC；候选谓词与 CON-002 一致 |
| **INT-6** | CON-004 run single-user happy | `ConsolidationRunService` + 真实 repos | 与 E2E-1 同构但更窄；可作为 E2E 前置 smoke |

**闭合 CON-002/003 deferred 项**：INT-1/2 ← CON-002 §13.4；INT-3/4 ← CON-003 §13.4。

## 10. e2e_test_plan（E2E-1..E2E-6）

> 目录 `tests/e2e/`；`@pytest.mark.integration`；`pytest tests/e2e/test_con005_consolidation_e2e.py -v`。

| ID | 名称 | 注入 | 核心断言 |
|---|---|---|---|
| **E2E-1** | Happy path + durable readback | INJ-1 | eligible Memory 选中；DISTINCT `archive_id` count 参与公式；`importance` = CON-001 预期；`last_consolidated_time=evaluation_time`；`memory_version` 不变；`content`/其他字段不变；run `SUCCESS`；MV-1/MV-4 |
| **E2E-2** | Multi-page + multi-user isolation | INJ-1；`batch_size=2` | 5+ memories/user A 跨页无 dup/skip；user B 独立 cursor=None；末页 `has_more=false`；trailing 空页 OK；B 不受 A 影响 |
| **E2E-3** | missing_evidence path | INJ-2 | 合法 Memory 无 qualifying Evidence → 选中；count=0；skip write；`importance`/`last_consolidated_time` 不变；`missing_evidence_count>0` |
| **E2E-4** | Version conflict partial success | INJ-3 | 批内一行竞态 bump version → 该行不覆盖；其他行 commit；`version_conflict_count++`；run 继续 `SUCCESS` |
| **E2E-5** | Write/read failure + mutex recovery | INJ-4/5/6 | 前批 committed；run `WRITE_FAILED` 或 `READ_FAILED`；mutex 释放；下一 `execute_run` 可成功；MV-2/MV-3 |
| **E2E-6** | Partial-progress next-run recovery（T2>T1） | INJ-7 | **Run A**：`evaluation_time=T1`；`cursor=None`；`batch_size` 小；至少一批 CON-003 提交后读/写 fail；已提交 durable；mutex 释放。**Run B**：新 `run_id`；`evaluation_time=T2`（`T2>T1`）；全用户枚举；每用户 `cursor=None`；无 checkpoint。断言 §6.3 全部 10 条（含 T1 行再入选、T2 重算、`last_consolidated_time=T2`、未提交行补齐；**禁止**断言 T1 行在 T2 run 被跳过） |

### 10.1 E2E-1 公式断言子契约

- 使用 `compute_consolidation_importance` + seeded 字段 **独立计算** `expected_importance`
- 断言 Neo4j 读回 `importance` ≈ `expected_importance`（float 容差 `1e-6`）
- 断言 **未**读取或依赖旧 `importance` 作为输入（种子初始 `importance` 与公式输出不同亦可证明覆盖）

### 10.2 E2E-1 durable readback 字段白名单

| 字段 | 预期 |
|---|---|
| `importance` | 更新为 `new_importance` |
| `last_consolidated_time` | `= evaluation_time` |
| `memory_version` | **不变** |
| `content`, `status`, `user_id`, `memory_type`, `confidence`, `created_time`, `latest_source_time`, `updated_time`, `retrieval_count` | **不变** |

### 10.3 §2.3.8 负向断言（全 E2E 适用）

- **不**变更 `status`
- **不**删除 ES 文档（本任务无 ES）
- **不**清空 `content`

## 11. production_file_whitelist

**默认：NONE**。实现阶段 **预期零** `src/**` 生产代码变更。

| 路径 | 创建/修改 | 条件 |
|---|---|---|
| — | — | **无** |

**HALT 规则**：若 Integration/E2E 暴露 CON-001..004 真实缺陷，Developer **停止**并报告 Orchestrator；**不得**在 CON-005 白名单外修复。

**允许的最小配置例外**（仅 Plan Review 批准且零语义变更）：

| 路径 | 条件 |
|---|---|
| `pyproject.toml` | 仅当必须注册 pytest marker；优先复用 `@pytest.mark.integration` |

## 12. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/support/con005_neo4j_fixtures.py` | 创建 | Memory/Evidence 种子、读回 helper、公式预期 |
| `tests/support/con005_failure_doubles.py` | 创建 | 失败注入 repository wrappers（可选合并入 fixtures） |
| `tests/integration/conftest_con005_neo4j.py` | 创建 | Neo4j-only module fixture 共享 |
| `tests/integration/test_con005_consolidation_read_neo4j.py` | 创建 | INT-1, INT-2, INT-5 |
| `tests/integration/test_con005_consolidation_write_neo4j.py` | 创建 | INT-3, INT-4 |
| `tests/integration/test_con005_consolidation_run_neo4j.py` | 创建 | INT-6（可选 smoke） |
| `tests/e2e/helpers/con005_e2e_helpers.py` | 创建 | 生产 wiring builder、Prometheus 读回、run 执行 |
| `tests/e2e/test_con005_consolidation_e2e.py` | 创建 | E2E-1..E2E-6 |
| `tests/contract/test_con005_scope_boundaries.py` | 创建 | 零 src diff、白名单、无 CON-001..004 生产变更 |

**白名单外任何 `tests/**` 变更 → FAIL**（运行 CON-001..004 回归但不在白名单内编辑）。

**`tests/e2e/conftest.py`**：本任务 **不修改**（Neo4j-only fixture 置于 `tests/integration/conftest_con005_neo4j.py`）。

### 12.0 pytest fixture 加载契约（仓库权威模式）

与 `tests/integration/test_ext002_archive_preprocessing_mongo.py` 的 `pytest_plugins` 模式一致；**禁止**依赖隐式 conftest 发现或跨目录手工 import fixture 模块。

| 消费方测试文件 | 必须声明 |
|---|---|
| `tests/integration/test_con005_consolidation_read_neo4j.py` | `pytest_plugins = ("tests.integration.conftest_con005_neo4j",)` |
| `tests/integration/test_con005_consolidation_write_neo4j.py` | 同上 |
| `tests/integration/test_con005_consolidation_run_neo4j.py` | 同上 |
| `tests/e2e/test_con005_consolidation_e2e.py` | 同上 |

`tests/integration/conftest_con005_neo4j.py` **仅**导出 fixture（`con005_neo4j_uri`、`con005_neo4j_driver`、`_clean_graph`、`con005_settings`、`con005_run_service` 等）；**不**包含测试用例。

### 12.1 governance_file_whitelist（Release Operator 各 phase）

| Phase | 允许路径 | 目的 |
|---|---|---|
| `PLAN_LANDING` | `02_开发管理/tasks/CON-005-consolidation-integration-e2e.md` | 已批准 Task Plan |
| `PLAN_LANDING` | `02_开发管理/progress.md` | 规划态登记 |
| `PLAN_LANDING` | `02_开发管理/master_plan.md` | CON-005 规划登记 |
| `IMPLEMENTATION_RELEASE` | §12 test_file_whitelist 全部 | 测试实现 |
| `IMPLEMENTATION_RELEASE` | 上述三份治理文件 | 执行记录 |
| `POST_MERGE_CLEANUP` | 上述三份治理文件 | 完成登记 + milestone |

### 12.2 PLAN_LANDING commit contract

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含：

1. `02_开发管理/tasks/CON-005-consolidation-integration-e2e.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`

Commit message（精确）：

```text
docs(plan): add CON-005 consolidation integration e2e plan
```

随后从更新后的 `main` 创建 exact feature branch `feat/CON-005-consolidation-integration-e2e`。

## 13. classification_labels

| ID | 项 | 分类 | 说明 |
|---|---|---|---|
| CL-1 | 修改 CON-001..004 生产 Service 语义 | **HARD_BLOCK** | 前置 closed |
| CL-2 | E2E 暴露缺陷于本任务修复生产代码 | **HARD_BLOCK** | HALT → owning task |
| CL-3 | ES/Mongo/Kafka 写入 | **HARD_BLOCK** | 阶段非目标 |
| CL-4 | §2.3.8 软遗忘副作用 | **HARD_BLOCK** | 负向断言 |
| CL-5 | E2E 正确性 / 用户隔离 / cursor / 乐观锁 / 恢复 | **HARD_BLOCK** | 用户矩阵 |
| CL-6 | 里程碑 `v0.5.0-consolidation` 闭合证据 | **HARD_BLOCK** | POST_MERGE_CLEANUP only |
| CL-7 | 新依赖 / Migration / Settings Contract | **HARD_BLOCK** | dependency_changes_expected=NONE |
| CL-8 | DEV-006 / PR #13 | **HARD_BLOCK** | 治理永久禁止 |
| CL-9 | 新增 Prometheus 指标名 | **HARD_BLOCK** | 仅验证既有 |
| CL-10 | Neo4j-only compose fixture | **SAFE_AUTO_REMEDIATION** | LD-1 |
| CL-11 | test helper 文件 / conftest 结构 | **SAFE_AUTO_REMEDIATION** | LD-4 |
| CL-12 | APScheduler 长时间 E2E | **DEFERRED** | LD-2；CON-004 Unit 足够 |
| CL-13 | 分布式锁 / exactly-once / 多实例 | **DEFERRED** | §2.3.14 |
| CL-14 | Session→Consolidation 全链路 | **DEFERRED** | E2E-001 |
| CL-15 | 持久化 cursor/run 表 | **DEFERRED** | §2.3.13 规则 6 |

## 14. mvp_local_decisions

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | Neo4j-only compose（`up -d neo4j` + `init-infra`） | 用户要求最小基础设施；对齐 EXT-005/RET-004 |
| LD-2 | APScheduler **不**做 E2E；CON-004 Unit U14–U17 足够 | 用户授权判定；避免 wall-clock flake |
| LD-3 | in-process 生产 wiring；**不**启动 `consolidation-worker` 容器 | RET-006 LD-1 同构；垂直切片无需容器 |
| LD-4 | 共享 fixture 文件 `conftest_con005_neo4j.py` + 消费方 `pytest_plugins` 显式加载；**不**改 `tests/e2e/conftest.py` | 对齐 EXT-002 `pytest_plugins` 仓库模式；Neo4j-only 与 RET-006 full stack 解耦 |
| LD-5 | 失败注入经 test repository wrapper；**不**改生产 repository | 零 src diff 默认 |
| LD-6 | `batch_size` 经 `monkeypatch.setenv` + `get_settings.cache_clear()` 或 settings fixture | E2E-2 多页；不修改 Settings Contract |
| LD-7 | E2E-5 mutex 用并发 `execute_run`；**不**依赖 Cron 触发 | 确定性；无长等待 |
| LD-8 | Integration 与 E2E 分层：INT 验仓储契约；E2E 验 run 垂直切片 | CON-002/003 deferred 闭合 |

## 15. 任务目标

交付 Consolidation 阶段 **真实 Neo4j Integration + E2E 垂直切片**，证明 CON-001..004 生产栈协同工作；闭合 **`v0.5.0-consolidation` 里程碑**。

可验证交付：

1. **INT-1..INT-6** — CON-002/003/004 仓储真实 Neo4j 契约。
2. **E2E-1** — Happy path + CON-001 公式 + durable readback。
3. **E2E-2** — 多页 cursor + 多用户隔离。
4. **E2E-3** — `missing_evidence` 跳过写。
5. **E2E-4** — 版本冲突部分成功。
6. **E2E-5** — 读/写失败 + mutex 释放恢复。
7. **E2E-6** — Run A@T1 部分提交 + fail；Run B@T2>T1 全量重扫与 T2 重算（§6.3）。
8. **默认零** `src/**` 生产 diff；scoped 测试全通过。

## 16. 非目标与黑名单（must_not）

- 修改 `consolidation_importance.py` / `consolidation_batch_service.py` / `consolidation_memory_read_repository.py` / `consolidation_write_service.py` / `consolidation_memory_write_repository.py` / `consolidation_run_service.py` / `consolidation_worker.py` — **禁止**（HALT 例外流程）。
- ES / Mongo / Kafka durable 写 — **禁止**。
- §2.3.8 软遗忘副作用 — **禁止**。
- 独立 Consolidation HTTP API — **禁止**。
- 持久化 cursor / `memory_consolidation_task` 表 — **禁止**。
- Redis 分布式锁 / 多实例调度长运行证明 — **禁止**。
- Session→Archive→Extraction 全链路 — **禁止**（E2E-001）。
- 新 Prometheus 指标名 — **禁止**。
- DEV-006 / PR #13 — **永久禁止**。

## 17. 当前代码状态

- **已存在**：CON-001..004 全部生产服务 + worker 接线；CON-004 Unit 37 passed；CON-001..003 Unit/Contract 完整。
- **可复用**：`consolidation_worker.py` wiring 模式；`compute_consolidation_importance`；Neo4j integration 模式（EXT-005/RET-004）；`CONSOLIDATION_RUNS_TOTAL`。
- **当前缺失**：`con005_*` fixtures；Consolidation Integration 测试；Consolidation E2E 测试；`archive_id` Evidence 种子 helper。
- **与技术规格不一致之处**：无；CON-002/003/004 Integration/E2E 仍为 DEFERRED。
- **前置任务检查**：CON-004 completed（PR #53 MERGED @ `ae70a94`）；CON-003 PR #52；CON-002 PR #51；CON-001 PR #50；baseline `010d741` clean main。

## 18. 实现方案（Developer 指引 — 本轮不执行）

> **原则：TEST / INTEGRATION / E2E ONLY**。默认 **不** 修改 `src/**`。

### Step 1 — `tests/support/con005_neo4j_fixtures.py`

- 常量：`CON005_EVALUATION_TIME`（T1）、`CON005_EVALUATION_TIME_T2`（T2>T1，E2E-6）、`CON005_USER_A/B`、memory_id 命名空间。
- `seed_memory_with_evidence(driver, *, archive_ids: list[str])` — Evidence 含 `archive_id`。
- `seed_memory_no_evidence(driver)` — OPTIONAL MATCH count=0。
- `read_memory_consolidation_state(driver, user_id, memory_id)` — importance / last_consolidated_time / memory_version / content / status。
- `expected_importance_for_seed(...)` — 调用 `compute_consolidation_importance`。
- `cleanup_con005_users(driver, user_ids)` — 按 user_id 清理。

### Step 2 — `tests/support/con005_failure_doubles.py`（可与 Step 1 合并）

- `FailingWriteRepository` / `FailingReadRepository` — 计数后失败。
- `bump_memory_version(driver, user_id, memory_id)` — E2E-4 竞态模拟。

### Step 3 — `tests/integration/conftest_con005_neo4j.py`

- Module fixture：Neo4j-only compose + init-infra + driver + autouse graph clean。
- 复用 EXT-005 启停逻辑；project=`memory-system-test`。
- **不**在测试文件内重复 compose 启停；由 §12.0 `pytest_plugins` 加载。

### Step 4 — Integration 测试

- 各 `test_con005_*.py` 文件顶部：`pytest_plugins = ("tests.integration.conftest_con005_neo4j",)`。
- `test_con005_consolidation_read_neo4j.py`：INT-1, INT-2, INT-5。
- `test_con005_consolidation_write_neo4j.py`：INT-3, INT-4。
- `test_con005_consolidation_run_neo4j.py`：INT-6 smoke（可选）。

### Step 5 — `tests/e2e/helpers/con005_e2e_helpers.py`

- `build_production_run_service(driver, settings, *, read_repo=None, write_repo=None)` — §5 wiring。
- `reset_consolidation_metrics()` — Prometheus 测试隔离。
- `assert_run_success(result, *, expected_updated=...)` — MV-4。

### Step 6 — `tests/e2e/test_con005_consolidation_e2e.py`

- 文件顶部：`pytest_plugins = ("tests.integration.conftest_con005_neo4j",)`。
- 实现 E2E-1..E2E-6；`pytestmark = pytest.mark.integration`。
- E2E-6 使用 `CON005_EVALUATION_TIME`（T1）与 `CON005_EVALUATION_TIME_T2`（T2）；断言 §6.3 全部 10 条。
- 每场景 `try/finally` cleanup。

### Step 7 — `tests/contract/test_con005_scope_boundaries.py`

- C1：零 `src/**` diff。
- C2：不修改 CON-001..004 生产文件。
- C3：白名单测试文件完整。

### Step 8 — 验证命令

```bash
./scripts/compose.sh --stack=test --embedding=none up -d neo4j
./scripts/compose.sh --stack=test --embedding=none run --rm init-infra
uv run pytest tests/integration/test_con005_consolidation_read_neo4j.py \
  tests/integration/test_con005_consolidation_write_neo4j.py \
  tests/integration/test_con005_consolidation_run_neo4j.py -v
uv run pytest tests/e2e/test_con005_consolidation_e2e.py -v
uv run pytest tests/unit/test_consolidation_importance.py \
  tests/unit/test_consolidation_batch_service.py \
  tests/unit/test_consolidation_write_service.py \
  tests/unit/test_consolidation_run_service.py -q
uv run ruff check tests/support/con005_neo4j_fixtures.py tests/support/con005_failure_doubles.py \
  tests/integration/conftest_con005_neo4j.py \
  tests/integration/test_con005_*.py tests/e2e/helpers/con005_e2e_helpers.py \
  tests/e2e/test_con005_consolidation_e2e.py tests/contract/test_con005_scope_boundaries.py
uv run mypy tests/support/con005_neo4j_fixtures.py \
  tests/support/con005_failure_doubles.py \
  tests/integration/conftest_con005_neo4j.py \
  tests/integration/test_con005_consolidation_read_neo4j.py \
  tests/integration/test_con005_consolidation_write_neo4j.py \
  tests/integration/test_con005_consolidation_run_neo4j.py \
  tests/e2e/helpers/con005_e2e_helpers.py \
  tests/e2e/test_con005_consolidation_e2e.py \
  tests/contract/test_con005_scope_boundaries.py
```

## 19. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/support/con005_neo4j_fixtures.py` | 创建 | 种子与读回 |
| `tests/support/con005_failure_doubles.py` | 创建 | 失败注入 doubles |
| `tests/integration/conftest_con005_neo4j.py` | 创建 | Neo4j-only fixture |
| `tests/integration/test_con005_consolidation_read_neo4j.py` | 创建 | INT-1,2,5 |
| `tests/integration/test_con005_consolidation_write_neo4j.py` | 创建 | INT-3,4 |
| `tests/integration/test_con005_consolidation_run_neo4j.py` | 创建 | INT-6 |
| `tests/e2e/helpers/con005_e2e_helpers.py` | 创建 | 生产 wiring + 断言 |
| `tests/e2e/test_con005_consolidation_e2e.py` | 创建 | E2E-1..6 |
| `tests/contract/test_con005_scope_boundaries.py` | 创建 | 白名单与零 src diff |

## 20. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 适用（委托） | 单批写 CON-003 transaction；E2E-4/5 断言 |
| 幂等 | 适用 | 权威谓词 `last_consolidated_time IS NULL OR last_consolidated_time < evaluation_time`。**同 T 重试**（T1 vs T1）：`last_consolidated_time=T1` 行不 eligible。**新 run**（T2>T1）：T1 行再 eligible、全量重算、写 `last_consolidated_time=T2`；E2E-6 / §6.3 |
| 并发 | 适用（有限） | mutex INJ-6；萃取竞态 E2E-4 |
| 版本冲突 | 适用 | 部分成功；E2E-4 |
| 用户隔离 | 适用 | INT-1/5；E2E-2 |
| 部分失败 | 适用 | 读/写失败终止 run；E2E-5/6 |
| 进程异常恢复 | 适用 | 无补偿；E2E-6 下轮重扫 |

## 21. 测试计划（模板 §8 映射）

### Unit Test

| 场景 | 预期 |
|---|---|
| 无新增 | CON-001..004 既有 Unit **回归**通过；本任务不新增 Unit |

### Contract Test

| 场景 | 预期 |
|---|---|
| C1–C3 | `test_con005_scope_boundaries.py` — 零 src diff + 白名单 |

### Integration Test — 见 §9 INT-1..INT-6

### E2E Test — 见 §10 E2E-1..E2E-6

### 失败注入与并发 — 见 §6 INJ-1..INJ-7

## 22. 验收标准

- [ ] INT-1..INT-6 全部通过（Integration 层）
- [ ] E2E-1..E2E-6 全部通过（`tests/e2e/test_con005_consolidation_e2e.py`）
- [ ] E2E-1：`importance` 符合 CON-001；`last_consolidated_time=evaluation_time`；`memory_version` 不变；无关字段不变
- [ ] E2E-2：小 `batch_size` 多页无 dup/skip；用户间 cursor 独立
- [ ] E2E-3：`missing_evidence` 不写 importance / last_consolidated_time
- [ ] E2E-4：冲突行不覆盖；`version_conflict_count>0`；run `SUCCESS`
- [ ] E2E-5：读/写失败 + mutex 释放 + 下轮可运行；`consolidation_runs_total` 正确
- [ ] E2E-6：Run A@T1 部分提交 durable + fail；Run B@T2>T1 新 `run_id`；`cursor=None` 全量重扫；T1 行再入选；T2 确定性重算；写 `last_consolidated_time=T2`；未提交行在 B 处理；无 checkpoint/补偿；**不**断言 T1 行在 T2 run 被跳过；显式区分同 T 重试 vs 新 T2 run（§6.3 断言 1–10）
- [ ] **零** `src/**` 生产 diff（除非 HALT）
- [ ] CON-001..004 既有测试回归通过
- [ ] Ruff / Mypy（变更测试文件）PASS
- [ ] Review 无 P0/P1

### 22.1 里程碑完成标准

```yaml
milestone: v0.5.0-consolidation
closes_when: CON-005 status=completed on main after POST_MERGE_CLEANUP
evidence:
  - "PR MERGED with INT-1..6 + E2E-1..6 green"
  - "master_plan CON-005 status=completed"
  - "progress.md next_action points to OPS-001 or next planned task"
not_required_for_milestone:
  - "E2E-001 full chain"
  - "ES importance sync"
  - "multi-instance scheduler proof"
```

## 23. 风险与阻塞项

- **设计文档冲突**：无已知冲突；边界与 §2.3.11–13 / §3.28 / master_plan 一致。
- **前置任务**：CON-004 PR #53 MERGED；CON-001..003 completed。
- **主要风险**：① Evidence 种子缺 `archive_id` 导致 count=0；② E2E 误用 fake batch/write service；③ 测试暴露生产缺陷后 scope creep 修 src；④ 与 RET-006 full infra_stack 混用导致不必要依赖。
- **环境**：Docker 不可用 → skip（与现有 integration 一致）。
- **DEV-006**：**禁止触碰** PR #13。

## 24. Git 计划

```yaml
branch: "feat/CON-005-consolidation-integration-e2e"
expected_commits:
  - "docs(plan): add CON-005 consolidation integration e2e plan"
  - "test(con): add consolidation neo4j integration and e2e suite"
  - "docs(status): record CON-005 implementation commit and PR"
  - "docs(status): complete CON-005 after PR merge"
out_of_scope_changes:
  - "CON-001..004 production semantics"
  - "src/** (default NONE)"
  - "ES/Mongo/Kafka"
  - "Settings / Migration / dependency"
  - "E2E-001 full chain"
  - "DEV-006 / PR #13"
```

## 25. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- **时间**：2026-08-13 14:45 UTC
- **原因**：Plan Review Round 1 — MF-1（E2E-6 / INJ-7 采用 option 1：Run B 必须 T2>T1；T1 行在 T2 run 再 eligible）+ SHOULD_FIX SF-1..SF-5；无技术规格 / Contract 变更
- **变更**：
  - MF-1：新增 §6.3 `evaluation_time` eligibility 权威区分；修正 INJ-7、E2E-6、§20 幂等、§22 验收、§28 摘要；删除「T2 run 跳过 T1 行」错误断言
  - SF-1：§9 标题对齐 INT-1..INT-6
  - SF-2：§12.0 `pytest_plugins` 显式加载 `conftest_con005_neo4j`
  - SF-3：§3.2 显式取代 CON-004 §15 — 仅 in-process run/mutex Integration/E2E；Worker/APScheduler wall-clock 仍 DEFERRED
  - SF-4：MV-4 纳入 `invalid_memory_count`（既有 contract 词汇）
  - SF-5：Step 8 mypy 覆盖全部 CON-005 新增测试/support 模块

## 26. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 22:55 UTC | Steps 1-7 | 创建 §12 全部 9 个测试/support 文件；零 `src/**` diff | INT-1..6 6 passed；E2E-1..6 6 passed；CON-001..004 unit 92 passed；contract C1-C3 4 passed；ruff/mypy PASS | E2E-4 采用写前 bump wrapper；E2E-5 mutex 用 BlockingReadRepository；E2E-6 Run B@T2 全量重扫 T1 行 |
| 2026-08-13 23:15 UTC | Code Review P1 fix | `tests/e2e/test_con005_consolidation_e2e.py` — E2E-5 INJ-5 durable readback after READ_FAILED；reuse `mutex_service` for write/read recovery；E2E-6 §6.3 #7 no-checkpoint comment/assertion | E2E-5 1 passed；INT+E2E+contract 16 passed | 零 `src/**` diff |

## 27. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `tests/support/con005_neo4j_fixtures.py` | 创建 |
| `tests/support/con005_failure_doubles.py` | 创建 |
| `tests/integration/conftest_con005_neo4j.py` | 创建 |
| `tests/integration/test_con005_consolidation_read_neo4j.py` | 创建 |
| `tests/integration/test_con005_consolidation_write_neo4j.py` | 创建 |
| `tests/integration/test_con005_consolidation_run_neo4j.py` | 创建 |
| `tests/e2e/helpers/con005_e2e_helpers.py` | 创建 |
| `tests/e2e/test_con005_consolidation_e2e.py` | 创建 |
| `tests/contract/test_con005_scope_boundaries.py` | 创建 |

### 与原计划的差异

无生产代码变更；E2E-4 增加 `VersionBumpBeforeWriteRepository`（写前 bump，对齐 INJ-3）；E2E-5 增加 `BlockingConsolidationMemoryReadRepository`（确定性 mutex 重叠）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Integration | `uv run pytest tests/integration/test_con005_consolidation_*.py -v` | 6 passed |
| E2E | `uv run pytest tests/e2e/test_con005_consolidation_e2e.py -v` | 6 passed |
| Regression | `uv run pytest tests/unit/test_consolidation_*.py -q` | 92 passed |
| Contract | `uv run pytest tests/contract/test_con005_scope_boundaries.py -v` | 4 passed |
| Ruff | Step 8 ruff check（§12 文件） | PASS |
| Mypy | Step 8 mypy（§12 文件） | PASS |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 3
code_review: CODE_REVIEW_APPROVED
review_report: null
```

### Git 记录

```yaml
branch: feat/CON-005-consolidation-integration-e2e
plan_commit: 2862b7a
implementation_commit: a8625ea81f21a686f2c84a0a9e204e313c4e95c9
implementation_commit_message: "test(con): add consolidation neo4j integration and e2e suite"
pr: "#54"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/54"
pr_state: OPEN
pr_base: main
pr_head: feat/CON-005-consolidation-integration-e2e
release_gate: WAITING_FOR_PR_MERGE
```

### 最终状态

`committed`

## 28. CON_005_PLAN_RESULT（Planner 摘要）

```yaml
task_id: CON-005
task_name: "Consolidation Integration + E2E"
workflow_mode: NORMAL
branch: "feat/CON-005-consolidation-integration-e2e"
milestone: "v0.5.0-consolidation"
planning_baseline_main: "010d74112fb760907e710f2ba27123e021dd3d61"
plan_file: "02_开发管理/tasks/CON-005-consolidation-integration-e2e.md"
e2e_boundary: "§2.3.11 consolidation vertical slice; in-process ConsolidationRunService + real Neo4j; NOT §3.32 full chain"
infrastructure: "compose.test Neo4j-only + init-infra"
scheduler_e2e: "NONE — CON-004 unit suffices; mutex minimal in E2E-5"
production_file_whitelist: NONE
integration_matrix: "INT-1..INT-6 (CON-002 read, CON-003 write, enumeration, optional run smoke)"
e2e_matrix: "E2E-1 happy+formula+readback; E2E-2 multi-page+isolation; E2E-3 missing_evidence; E2E-4 version_conflict; E2E-5 failure+mutex; E2E-6 partial recovery T1 fail then T2>T1 full rescan (T1 rows re-eligible, NOT skipped)"
failure_injection: "INJ-1..INJ-7; INJ-7 Run A@T1 partial+fail → Run B@T2>T1; test repository wrappers; direct Cypher version bump"
evaluation_time_distinction: "§6.3 — same-T retry skips T1 rows; new T2>T1 run re-selects T1 rows and writes last_consolidated_time=T2"
pytest_fixture_loading: "pytest_plugins = ('tests.integration.conftest_con005_neo4j',) on all CON-005 test modules"
con004_section15_supersede: "owns in-process Integration/E2E + mutex; APScheduler/container wall-clock E2E remains DEFERRED"
metrics: "existing consolidation_runs_total + ConsolidationRunMetrics only (MV-4 incl. invalid_memory_count)"
dependency_changes_expected: NONE
completion_closes_milestone: "v0.5.0-consolidation"
next_action: WAITING_FOR_PR_MERGE
status: committed
```
