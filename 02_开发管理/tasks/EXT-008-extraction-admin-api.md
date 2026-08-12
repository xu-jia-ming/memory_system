# EXT-008 Extraction 管理 GET/Retry/Rebuild API

## 1. 任务信息

```yaml
task_id: EXT-008
task_name: Extraction 管理 GET/Retry/Rebuild API
status: planned
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "d55bf53e715378463243fcf80e49277e603c1bb5"
branch: "feat/EXT-008-extraction-admin-api"
created_at: "2026-08-12 21:40 UTC"
updated_at: "2026-08-12 21:40 UTC"
spec_sections:
  - "§2.1.3 Memory Extraction Task 数据库设计"
  - "§2.1.4 Kafka 消费与任务幂等（completed 早退；terminal 持久化后才 Offset）"
  - "§2.1.14 Memory Extraction 管理接口"
  - "§2.1.15 失败处理（可人工重试表；kafka_publish_failed）"
  - "§2.1.16 MVP 实现边界"
  - "§3.21 Memory API 鉴权与接口暴露（Extraction Admin HTTP = Admin Key only）"
  - "§3.23 统一 API 响应与 Request ID"
prerequisites:
  formal:
    - "EXT-001 — SATISFIED/completed; consumer offset gate + failed→pending 语义预留（人工路径属本任务）"
    - "EXT-007 — SATISFIED/completed; PR #41 MERGED; mark_completed 路径已存在"
    - "DEV-005 — SATISFIED/completed; FastAPI shell、require_admin_api_key、AppError/§3.23 错误包络"
  implementation_reuse:
    - "find_extraction_task_by_archive_id / mark_failed (infrastructure/mongodb/extraction_task_repository.py)"
    - "republish_archive_created_event (domain/services/archive_event_republish_service.py — STM-011)"
    - "publish_archive_created_event + settings.kafka.topic (infrastructure/kafka/)"
    - "require_admin_api_key / AppError / build_error_response (api/)"
    - "MemoryExtractionTask / ExtractionLastError (domain/models/extraction_task.py)"
  baseline_evidence:
    branch: "main"
    head: "d55bf53e715378463243fcf80e49277e603c1bb5"
    working_tree_at_planning_start: "clean before planning whitelist writes"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=d55bf53e715378463243fcf80e49277e603c1bb5"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "pending Plan Review"
  amendment_recorded: false
  human_plan_approved: false
  developer_authorized: false
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
  - "修改 PipelineTerminalDecision / extraction_task_consumer_service / extraction_worker / extraction_* pipeline 服务"
stop_if:
  - "任何实现步骤需要新增未授权 HTTP 错误码或 failed_stage 字面量（§2.1.15 + 本 Plan LD 白名单外）"
  - "任何实现步骤需要 Neo4j/Elasticsearch 写入或 Kafka Offset 提交"
  - "任何实现步骤需要暴露 republish_archive_event / migrate 为 HTTP"
  - "任何实现步骤需要触碰 DEV-006 / PR #13"
blocking_open_issues: []
nonblocking_open_issues: []
resolved_open_issues:
  - OI-006
```

## 2. 任务目标

实现 §2.1.14 规定的 Extraction **Admin HTTP** 管理接口，并闭合 OI-006 对 `reconciliation_plan_conflict` 运维清理的最小 Contract。

可验证目标：

1. **GET 萃取状态（§2.1.14 #1）**：`GET /api/v1/memory/extraction/{user_id}/{archive_id}`；Admin Key only；`user_id + archive_id` 联合过滤；不匹配 → HTTP `404` + `extraction_task_not_found`。
2. **POST 人工重试（§2.1.14 #2）**：`POST /api/v1/memory/extraction/{user_id}/{archive_id}/retry`；仅 `status=failed` 且 `last_error.error_code` 属于 §2.1.15「可人工重试=是」；永久错误 / 非 failed / 含不可复用 `extraction_result` 的冲突 → HTTP `409` + `retry_not_allowed`；Mongo：`failed→pending`、清空 `last_error`、**保留** `extraction_result`、`attempt_count` 不清零；生成新 `event_id` 经 STM-011 `republish_archive_created_event` 重发 `context.archive.created`（Message Key=`user_id`）；Kafka 成功 → 返回 `pending`；Kafka 失败 → 任务恢复/保持 `failed` 且 `last_error.error_code=kafka_publish_failed`（§2.1.14 #7）。
3. **POST 冲突重建（OI-006 / §2.1.14 #3 MVP_LOCAL_DECISION）**：`POST /api/v1/memory/extraction/{user_id}/{archive_id}/rebuild`；Admin Key only；仅 `status=failed` 且 `last_error.error_code=reconciliation_plan_conflict`；清空 `extraction_result` 后执行与 retry 相同的 `pending + republish` 流程；其它 error_code → `409 retry_not_allowed`。
4. **Durability 边界**：本任务 **仅 Mongo durable 写入**（任务状态/`last_error`/`extraction_result` 清理）；**不**写 Neo4j/ES；**不**提交 Kafka Offset。
5. **Worker/Consumer 不变**：`extraction_task_consumer_service` / `extraction_worker` / pipeline 服务 **零语义 diff**；`completed-before-offset`（EXT-001）保持不变。
6. **鉴权（§3.21）**：三路由均 `require_admin_api_key`；普通 Key → `403 forbidden`（DEV-005 工程冻结）；缺失/错误 Key → `401 invalid_api_key`。

## 3. 非目标与黑名单

- **Kafka Offset 提交**（EXT-001 consumer 责任；admin API 不得调用 consumer commit）。
- **Pipeline / Worker 接线变更**（`DEFERRED_FOR_MVP`；本任务只交付 HTTP + domain service + Mongo repository 扩展）。
- **修改** `PipelineTerminalDecision` / `extraction_task_consumer_service` / `extraction_worker` / `extraction_llm_service` / `entity_alignment_service` / `reconciliation_service` / `graph_write_service` / `retrieval_index_sync_service`。
- **Neo4j / Elasticsearch 读写**；图谱/索引清理不在 MVP 范围（冲突修复后依赖 Worker 重跑；已提交图谱由 Evidence 幂等 SKIP）。
- **通用 Admin 平台**（批量查询、任意字段 PATCH、任务删除、Offset 管理、DLT/自动重试）。
- **HTTP 暴露** `scripts/republish_archive_event.py` 或 `scripts/migrate`（§3.21 #8）。
- **Retrieval API**（RET-*）；**EXT-009** E2E/失败注入（归属 EXT-009）。
- **新依赖 / Migration / Settings Contract 变更**（`dependency_changes_expected=NONE`）。
- **DEV-006 / PR #13**。
- **新造 HTTP 业务错误码**（仅 `extraction_task_not_found`、`retry_not_allowed` + DEV-005 既有 `invalid_api_key`/`forbidden`/`validation_error`/`internal_error`）。
- 原始消息、LLM 输出、prompt、secret 的日志/fixture/异常明文。

## 4. 当前代码状态与前置检查

### 4.1 Git 与前置任务证据（只读验证）

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `d55bf53e715378463243fcf80e49277e603c1bb5`（与用户给定 baseline 一致） |
| `git status --short` | 空 |
| EXT-001 | `completed`；consumer offset gate + task state machine |
| EXT-007 | `completed`；`mark_completed` / `mark_failed` 已实现 |
| DEV-005 | `completed`；`require_admin_api_key`、`AppError`、Request ID |
| STM-011 | `completed`；`republish_archive_created_event` 可复用 |
| workflow | `NORMAL`，explicit |

### 4.2 已存在可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| `MemoryExtractionTask` | `domain/models/extraction_task.py` | GET 响应映射 |
| `find_extraction_task_by_archive_id` | `infrastructure/mongodb/extraction_task_repository.py` | 任务加载（需扩展 user 过滤） |
| `mark_failed` | 同上 | Kafka 发布失败回写 |
| `republish_archive_created_event` | `domain/services/archive_event_republish_service.py` | Kafka 重发（Mongo Archive 只读） |
| `require_admin_api_key` | `api/dependencies.py` | Admin 鉴权 |
| `AppError` / error handlers | `api/errors.py`, `api/error_handlers.py` | §3.23 包络 |
| `settings.kafka.topic` | `settings/models.py` | `context.archive.created` |

### 4.3 当前代码空缺（实测）

| 事实 | 证据 |
|---|---|
| 无 Extraction Admin HTTP 路由 | `rg extraction /api/v1/memory/extraction` 无命中 |
| 无 `failed→pending` admin repository 方法 | `extraction_task_repository.py` 仅有 `mark_processing_from_pending` |
| 无 retry 可重试表常量 | §2.1.15 表未编码 |
| 无 `reconciliation_plan_conflict` rebuild 路径 | OI-006 open |
| `find_extraction_task_by_archive_id` 无 `user_id` 过滤 | 需在 service 层 fail-closed 校验 |

**结论**：EXT-008 新建 Admin HTTP 路由 + domain service + retry policy 常量；扩展 Mongo repository；**不**改 consumer/worker/pipeline。

## 5. Exact Contract 闭合

### 5.1 HTTP 路由与鉴权

| Method | Path | Auth | 规格 |
|---|---|---|---|
| GET | `/api/v1/memory/extraction/{user_id}/{archive_id}` | Admin Key only | §2.1.14 #1 |
| POST | `/api/v1/memory/extraction/{user_id}/{archive_id}/retry` | Admin Key only | §2.1.14 #2 |
| POST | `/api/v1/memory/extraction/{user_id}/{archive_id}/rebuild` | Admin Key only | OI-006 LD-1（MVP_LOCAL_DECISION） |

Path 参数：`user_id`、`archive_id` 均为非空、`^\S+$`（与现有 memory routes 一致）。

### 5.2 GET 成功响应（§2.1.14）

```json
{
  "user_id": "user_001",
  "archive_id": "archive_000001",
  "status": "completed",
  "attempt_count": 1,
  "last_error": null,
  "completed_time": 1720001000
}
```

| 字段 | 类型 | 规则 |
|---|---|---|
| `user_id` | string | 来自任务文档；必须与 path 一致 |
| `archive_id` | string | 来自任务文档 |
| `status` | enum | `pending` / `processing` / `completed` / `failed` |
| `attempt_count` | int | ≥0 |
| `last_error` | object \| null | 非 null 时含 `error_code`、`failed_stage`、`message`（不额外暴露 `task_id`/内部字段） |
| `completed_time` | int \| null | Unix timestamp；未完成 null |

**不**在 GET 响应中返回 `extraction_result`（规格示例未包含；避免泄漏 LLM 结构化输出）。

### 5.3 POST retry 成功响应（§2.1.14）

```json
{
  "user_id": "user_001",
  "archive_id": "archive_000001",
  "status": "pending"
}
```

### 5.4 POST rebuild 成功响应（LD-1）

与 retry 成功响应 **相同形状**（`status=pending`）。

### 5.5 HTTP 错误映射（failure_mapping）

| 场景 | HTTP | `error.code` | 备注 |
|---|---|---|---|
| 缺失/无效 Admin Key | 401 | `invalid_api_key` | §3.21；不区分缺失/错误 |
| 有效普通 Key 访问 Admin 路由 | 403 | `forbidden` | DEV-005 工程冻结 |
| 任务不存在 | 404 | `extraction_task_not_found` | 含 `user_id` 不匹配（不泄露跨用户存在性） |
| 非 `failed` 状态调用 retry/rebuild | 409 | `retry_not_allowed` | 含 `pending`/`processing`/`completed` |
| 永久错误码调用 retry | 409 | `retry_not_allowed` | 见 §5.6 |
| `reconciliation_plan_conflict` 调用 retry | 409 | `retry_not_allowed` | 必须走 rebuild |
| 非 `reconciliation_plan_conflict` 调用 rebuild | 409 | `retry_not_allowed` | rebuild 窄契约 |
| Pydantic path/body 校验失败 | 422 | `validation_error` | §3.23 |
| Mongo/Kafka 非业务失败 | 503 | `internal_error` | 脱敏 message；无 stack 泄露 |

**EXT-008 授权 HTTP 业务码**：`extraction_task_not_found`、`retry_not_allowed`（加 DEV-005 横切码）。

**禁止 HTTP 业务码**：新造 `rebuild_not_allowed`、`task_not_failed` 等第二套码（统一 `retry_not_allowed`）。

### 5.6 §2.1.15 可人工重试表（编码常量）

**可 retry（是）** — `MANUAL_RETRY_ALLOWED_ERROR_CODES`：

```
llm_timeout
llm_request_failed
llm_invalid_output
entity_alignment_failed
graph_query_failed
graph_write_failed
retrieval_index_write_failed
kafka_publish_failed
```

**不可 retry（否）** — retry 返回 `409 retry_not_allowed`：

```
archive_not_found
archive_ownership_mismatch
invalid_archive
archive_too_large
reconciliation_plan_conflict    ← 必须 rebuild
memory_search_text_too_long
```

**rebuild 仅允许**：

```
reconciliation_plan_conflict
```

### 5.7 Domain Service 输入/输出

```text
ExtractionAdminGetInput {
  user_id: str
  archive_id: str
}

ExtractionAdminGetResult {
  user_id, archive_id, status, attempt_count, last_error|null, completed_time|null
}

ExtractionAdminRetryInput {
  user_id: str
  archive_id: str
}

ExtractionAdminRebuildInput {
  user_id: str
  archive_id: str
}

ExtractionAdminMutationSuccess {
  user_id, archive_id, status: "pending"
}
```

Service 抛出 typed domain errors → route 层映射为 `AppError`（404/409/503）。

### 5.8 Mongo durable 写入范围

| 操作 | Collection | 写入 |
|---|---|---|
| GET | `memory_extraction_task` | **只读** |
| retry 成功路径 | 同上 | `$set status=pending, last_error=null, updated_time=now`；**不**改 `extraction_result`；**不** `$inc attempt_count` |
| rebuild 成功路径 | 同上 | 同上 + `$set extraction_result=null` |
| Kafka 发布失败 | 同上 | `$set status=failed, last_error={error_code:kafka_publish_failed, failed_stage:extraction_admin, message:*}`（LD-2） |

**禁止 durable 写入**：Neo4j、Elasticsearch、Kafka Offset、Context Archive、新 task 文档（同 `archive_id` unique）。

### 5.9 Replay / 幂等 / task-offset 语义

| 维度 | 行为 |
|---|---|
| GET | 纯读；幂等 |
| retry/rebuild | 仅 `status=failed` 可成功；Mongo 条件更新 `status=failed` 保证并发单次成功 |
| 双次 retry | 第一次成功后 `status=pending` → 第二次 `409 retry_not_allowed` |
| `extraction_result` | retry **保留** → Worker 跳过 LLM（§2.1.14 #5）；rebuild **清空** → Worker 重跑 LLM |
| `attempt_count` | retry/rebuild **不清零**；Worker `mark_processing_from_pending` 时 `$inc`（§2.1.14 #4） |
| Kafka event | 每次成功 mutation 生成新 `event_id`；Key=`user_id`；Topic=`settings.kafka.topic` |
| Offset | Admin **不** commit；failed 任务 Offset 已在 EXT-001 提交；pending 后 consumer 正常消费新事件 |
| completed 早退 | 不变；GET 可观测 `completed`，retry/rebuild 拒绝 |

### 5.10 Kafka 重发与 STM-011 复用

调用：

```python
republish_archive_created_event(
    mongodb=mongodb,
    kafka_producer=kafka_producer,
    topic=settings.kafka.topic,
    input=ArchiveEventRepublishInput(
        archive_id=archive_id,
        expected_user_id=user_id,
    ),
)
```

映射：

| `ArchiveEventRepublishStatus` | Admin 行为 |
|---|---|
| `SUCCESS` | 返回 HTTP 200 `pending` |
| `ARCHIVE_NOT_FOUND` / `ARCHIVE_OWNERSHIP_MISMATCH` / `INVALID_ARCHIVE` | Mongo 已 pending → **回写** `failed` + `kafka_publish_failed` 或 abort 前不转 pending（见 Step 3 顺序） |
| `KAFKA_PUBLISH_FAILED` | 回写 `failed` + `last_error.error_code=kafka_publish_failed`（§2.1.14 #7） |

**顺序（LD-3）**：先 Mongo `failed→pending`（清 last_error），再 Kafka publish；publish 失败则 `mark_failed(kafka_publish_failed)`。

## 6. 实现方案

### Step 1 — Retry policy 常量

- **文件**：`src/memory_system/domain/constants/extraction_retry_policy.py`
- **内容**：`MANUAL_RETRY_ALLOWED_ERROR_CODES: frozenset[str]`、`MANUAL_RETRY_FORBIDDEN_ERROR_CODES`、`REBUILD_ALLOWED_ERROR_CODES`（仅 `reconciliation_plan_conflict`）
- **测试**：Contract 断言与 §2.1.15 表逐字一致

### Step 2 — Mongo repository 扩展

- **文件**：`src/memory_system/infrastructure/mongodb/extraction_task_repository.py`
- **新增**：
  - `find_extraction_task_by_user_and_archive_id(mongodb, user_id, archive_id) -> MemoryExtractionTask | None`（filter 两字段）
  - `admin_reset_failed_to_pending(mongodb, *, user_id, archive_id, now, clear_extraction_result: bool) -> MemoryExtractionTask | None`（条件 `status=failed`；`clear_extraction_result=False` for retry，`True` for rebuild）
  - `admin_mark_failed_from_admin_action(mongodb, *, user_id, archive_id, last_error, now) -> MemoryExtractionTask`（Kafka 失败回写；条件 `status in (pending, failed)` fail-closed）
- **幂等**：条件更新返回 `None` → service 映射 `retry_not_allowed`

### Step 3 — `ExtractionAdminService`

- **文件**：`src/memory_system/domain/services/extraction_admin_service.py`
- **方法**：
  - `get_status(mongodb, user_id, archive_id) -> ExtractionAdminGetResult`（404 domain error）
  - `retry_task(mongodb, kafka_producer, settings, user_id, archive_id, now) -> ExtractionAdminMutationSuccess`
  - `rebuild_task(...)`（同上 + `clear_extraction_result=True` + error_code gate）
- **私有**：`_mutate_failed_to_pending_and_republish(..., clear_extraction_result: bool)`
- **日志**：含 `task_id`、`archive_id`、`user_id`、`attempt_count`；不含 `extraction_result`/secret
- **禁止**：Offset、pipeline 调用、Neo4j/ES

### Step 4 — HTTP Schemas

- **文件**：`src/memory_system/api/schemas/memory_extraction_admin.py`
- **模型**：`ExtractionStatusResponse`、`ExtractionMutationResponse`、`ExtractionLastErrorResponse`（strict, extra=forbid）

### Step 5 — HTTP Routes

- **文件**：`src/memory_system/api/routes/memory_extraction_admin.py`
- **依赖**：`require_admin_api_key`；`request.app.state.app_state` 取 mongodb/kafka_producer/settings
- **注册**：`src/memory_system/api/app.py` 增加 `include_router(memory_extraction_admin.router)`

### Step 6 — 测试（见 §9）

## 7. 文件变更清单（实施白名单）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/constants/extraction_retry_policy.py` | 创建 | §2.1.15 可重试表 |
| `src/memory_system/domain/services/extraction_admin_service.py` | 创建 | GET/retry/rebuild 编排 |
| `src/memory_system/infrastructure/mongodb/extraction_task_repository.py` | 修改 | user 过滤 + admin pending/failed 写入 |
| `src/memory_system/api/schemas/memory_extraction_admin.py` | 创建 | HTTP 响应 Schema |
| `src/memory_system/api/routes/memory_extraction_admin.py` | 创建 | 三路由 + AppError 映射 |
| `src/memory_system/api/app.py` | 修改 | 注册 router |
| `tests/unit/test_extraction_admin_service.py` | 创建 | Service 分支/幂等/Kafka 失败回写 |
| `tests/contract/test_ext008_extraction_admin_contract.py` | 创建 | 路由/错误码/retry 表/响应形状 |
| `tests/integration/test_ext008_extraction_admin_http.py` | 创建 | TestClient + Mongo/Kafka fake：happy path + 404/409/401/403 |

**白名单外任何 `src/**`、`tests/**`、配置、Migration、依赖变更 → FAIL**。

## 8. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | Mongo 单文档更新；Kafka 为外部副作用 | pending 写入与 publish 顺序 LD-3；publish 失败回写 failed |
| 幂等 | retry/rebuild 非幂等 HTTP（第二次 409） | 条件更新 `status=failed` |
| 并发 | 同 archive 单任务 | Mongo 条件更新；仅一成功者转 pending |
| 版本冲突 | 不适用 | 无 optimistic lock |
| 用户隔离 | 适用 | 所有查询/更新 filter `user_id + archive_id`；跨用户 404 |
| 部分失败 | Kafka 失败 after pending | 回写 failed + kafka_publish_failed；允许再次 retry |
| 进程异常恢复 | Admin 进程崩溃 after pending before publish | 任务卡 pending 无新事件；运维可再次 retry/rebuild（若仍 failed 则 409；若 pending 则 409 — 需 STM-011 CLI 或等待 EXT-009 手册；**不**在本任务发明新码） |

## 9. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| U1 GET found | 返回 status/attempt_count/last_error/completed_time |
| U2 GET user mismatch | `ExtractionTaskNotFoundError` |
| U3 retry allowed code | pending + republish called |
| U4 retry permanent code | `RetryNotAllowedError` |
| U5 retry reconciliation_plan_conflict | `RetryNotAllowedError` |
| U6 rebuild conflict only | clears extraction_result + pending |
| U7 rebuild wrong code | `RetryNotAllowedError` |
| U8 retry non-failed | `RetryNotAllowedError` |
| U9 kafka publish fail | mark_failed kafka_publish_failed; HTTP 映射 503 或 409 per route policy（LD-4：返回 503 internal_error 且 body 不含敏感细节；Mongo 为 failed） |
| U10 republish archive mismatch | 回写 failed |

### Contract Test

| 场景 | 预期 |
|---|---|
| C1 路由路径 | 三路由路径与 §2.1.14 + LD-1 一致 |
| C2 Admin Key only | 无 Key 401；普通 Key 403 |
| C3 授权 HTTP 码 | 仅 `extraction_task_not_found`/`retry_not_allowed` + 横切码 |
| C4 retry 表 | 与 §2.1.15 逐字匹配 |
| C5 响应 forbid extra | Pydantic extra=forbid |
| C6 零 upstream diff | consumer/worker/pipeline 文件无变更 |
| C7 GET 不返回 extraction_result | 响应模型无该字段 |

### Integration Test

| 场景 | 预期 |
|---|---|
| I1 GET happy | TestClient + seeded Mongo task → 200 |
| I2 retry happy | failed+retryable → Mongo pending + fake kafka publish |
| I3 rebuild happy | failed+reconciliation_plan_conflict → extraction_result null |
| I4 cross-user GET | 404 extraction_task_not_found |
| I5 retry completed | 409 retry_not_allowed |

### E2E Test

| 场景 | 预期 |
|---|---|
| — | **不适用**；全链路失败注入归属 **EXT-009** |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| F1 并发双 retry | 至多一个 pending 成功 |
| F2 Kafka fail after pending | Mongo failed + kafka_publish_failed |

## 10. 验收标准

- [ ] `GET /api/v1/memory/extraction/{user_id}/{archive_id}` 符合 §2.1.14 响应；Admin Key only；user 不匹配 404
- [ ] `POST .../retry` 符合 §2.1.14 规则 1–7；永久错误与 reconciliation_plan_conflict → 409
- [ ] `POST .../rebuild` 闭合 OI-006；仅 reconciliation_plan_conflict；清空 extraction_result
- [ ] Mongo **仅**本任务授权写入；零 Neo4j/ES/Offset
- [ ] 复用 STM-011 republish；不暴露 CLI 为 HTTP
- [ ] consumer/worker/pipeline **零 diff**
- [ ] scoped unit + contract + integration 全通过
- [ ] Ruff / Mypy 通过
- [ ] Review 无 P0/P1

## 11. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | §2.1.14 未命名 rebuild URL → LD-1 MVP_LOCAL_DECISION；不改变规格正文 |
| OI-006 | 本 Plan 闭合；rebuild 窄契约 |
| 当前代码冲突 | 无 admin 路由；repository 缺 admin 方法 |
| 前置任务 | EXT-007、DEV-005、EXT-001、STM-011 均已 completed |
| 主要风险 | ① 误 commit Offset；② 误改 consumer；③ retry 未挡 reconciliation_plan_conflict；④ GET 泄漏 extraction_result |
| 非阻塞 | 无 |

## 12. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/EXT-008-extraction-admin-api"
baseline_main: "d55bf53e715378463243fcf80e49277e603c1bb5"
expected_commits:
  - "docs(plan): add EXT-008 extraction admin api plan"
  - "feat(ext): add extraction admin get retry rebuild api"
  - "docs(status): record EXT-008 implementation commit and PR"
  - "docs(status): complete EXT-008 after PR merge"
release_phases:
  PLAN_LANDING: "after human PLAN_APPROVED"
  IMPLEMENTATION_RELEASE: "after CODE_REVIEW_APPROVED"
  POST_MERGE_CLEANUP: "after PR MERGED"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "PipelineTerminalDecision / consumer / worker / pipeline services"
  - "Kafka offset commit"
  - "Neo4j / Elasticsearch writes"
  - "Migration / dependency / Settings"
  - "Generalized admin platform"
```

### 12.1 MVP_LOCAL_DECISION

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | 新增 `POST /api/v1/memory/extraction/{user_id}/{archive_id}/rebuild`（Admin Key） | §2.1.14 #3 要求 reconciliation_plan_conflict 经专门管理操作清理/重建；规格未命名 URL；OI-006 最小闭合 |
| LD-2 | `kafka_publish_failed` 的 `failed_stage="extraction_admin"` | §2.1.15 未定义 admin 阶段；区分 worker 阶段失败 |
| LD-3 | Mongo `failed→pending` **先于** Kafka publish；publish 失败回写 `failed` | 对齐 §2.1.14 #7「发布失败恢复或保持 failed」 |
| LD-4 | Kafka/Mongo 基础设施异常 → HTTP `503 internal_error` | §3.23；业务拒绝统一 `409 retry_not_allowed` |
| LD-5 | GET 响应 **不**包含 `extraction_result` | 规格示例未包含；减少 LLM 输出泄漏面 |
| LD-6 | `ExtractionAdminService` 为 HTTP 与 Mongo/Kafka 编排 owner | 与 EXT-007 LD-6 模式一致 |
| LD-7 | rebuild **仅** `reconciliation_plan_conflict` | OI-006 最小契约；其它永久错误不做 generalized rebuild |

### 12.2 deferred_for_mvp

| 项 | 说明 |
|---|---|
| Pipeline worker 接线 | Admin service 库就绪；不在本任务接入 worker |
| 通用 Admin 平台 | 无列表/批量/删除/Offset 管理 |
| memory_search_text_too_long rebuild | 未在 OI-006 范围；若需类似路径 → 规格修订或后续 Task |
| pending 卡死无事件运维手册 | EXT-009 / ops doc；本任务不新增 HTTP |
| Neo4j/ES 冲突数据清理 | 超出 Mongo-only 范围 |

### 12.3 OI-006 决议（Plan 闭合）

| 字段 | 值 |
|---|---|
| owner | EXT-008 |
| resolution | `POST .../rebuild` Admin-only；`reconciliation_plan_conflict` + `failed` → 清 `extraction_result` → `pending` + republish |
| retry 关系 | 同错误码调用 `retry` → `409 retry_not_allowed` |
| status | `resolved_by_plan`（待 IMPLEMENTATION 验证后 `resolved_by_task`） |

### 12.4 归属声明

| 项 | 归属 |
|---|---|
| Kafka Offset | EXT-001 consumer |
| Archive CLI republish | STM-011 `scripts/republish_archive_event.py`（CLI-only §3.21） |
| Extraction E2E + 失败注入 | EXT-009 |
| DEV-006 | PAUSED / PR #13 |

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-12 21:40 UTC | planning | 创建 Task Plan；同步 progress/master_plan/open_issues | — | baseline d55bf53 verified；prerequisites SATISFIED；OI-006 resolved_by_plan |

## 14. 实际执行结果

### 最终状态

`planned` — 待 Plan Review；Developer **NOT** authorized；`next_action=计划审查`；**不得触碰 DEV-006/PR#13**。

### Git 记录

```yaml
branch: null
plan_commit: null
implementation_commit: null
implementation_commit_message: null
```
