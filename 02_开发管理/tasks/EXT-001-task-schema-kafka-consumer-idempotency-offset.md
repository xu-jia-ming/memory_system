# EXT-001 Task Schema + Kafka Consumer Idempotency / Offset

## 1. 任务信息

```yaml
task_id: EXT-001
task_name: Task Schema + Kafka Consumer Idempotency / Offset
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
plan_review_round: 2
human_plan_approved: true
human_plan_approved_at: "2026-08-11T12:51:00Z"
remediation: "Amendment 001 — Round 1 PLAN_REJECTED MF-001 (consumer-boundary exact six-field keys; do not modify ArchiveCreatedEvent) + MF-002 (key≠user_id fail-closed no upsert/commit) + absorb SF-001..005"
spec_sections:
  - "§1.2.4 Kafka Event 设计（topic / six-field schema / Message Key=user_id / consumer group / at-least-once）"
  - "§2.1.1 记忆萃取整体流程（Create or Load Task → … → Commit Offset 边界）"
  - "§2.1.3 Memory Extraction Task 数据库设计（schema / indexes / 状态机 / last_error）"
  - "§2.1.4 Kafka 消费与任务幂等（Upsert / 状态分支 / Offset 提交条件）"
  - "§2.1.15 失败处理（failed + last_error 成功写入后才允许 Commit Offset；错误码表供结构对齐，本任务不发明新码）"
  - "§3.6 全异步客户端（AIOKafkaConsumer；enable_auto_commit=false）"
  - "§3.19 Kafka Topic 与客户端参数（kafka_consumer 固定配置；max_poll_records=1）"
  - "§3.20 MongoDB 规则（Extraction Task 唯一索引；单文档原子更新）"
prerequisites:
  formal:
    - "STM-006 — SATISFIED（context.archive.created 六字段 Producer；key=user_id；AT_LEAST_ONCE；PR #25 MERGED）"
    - "DEV-004 — SATISFIED（001 Mongo indexes for memory_extraction_task；004 Kafka topic；PR #10 MERGED）— 见 §4.6 复核结果"
  implementation_reuse:
    - "STM-005 — SATISFIED（Mongo repository 模式；AsyncMongoClient；DuplicateKey 处理范例）"
    - "STM-011 — SATISFIED（ArchiveCreatedEvent 模型与发布侧补发；新 event_id 同 archive_id）— 消费侧不实现 STM-012"
    - "DEV-002 — SATISFIED（KafkaSettings / KafkaConsumerSettings / MongoDBSettings / memory_extraction settings）"
    - "DEV-005 — SATISFIED（metrics 名称已注册；本任务可不接线计数，禁止改 metrics Contract）"
  baseline:
    - "Authoritative baseline（Orchestrator）：main HEAD == f4015cdca8694c3c2be96992a4957b2838c873e4；working tree clean"
    - "本任务需要真实 Mongo + 真实 Kafka（compose test 栈）；不需要 Redis / Neo4j / ES / LLM / HTTP / STM-012"
branch: "feat/EXT-001-task-schema-kafka-consumer-idempotency-offset"
created_at: "2026-08-11 12:31 UTC"
updated_at: "2026-08-11 12:44 UTC"
approval_gates:
  planning_docs: "Round 2 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0）；Human PLAN_APPROVED Amendment 001"
  implementation_plan: "status=tested; human PLAN_APPROVED Round 2; awaiting Code Review remediation close-out"
```

### 1.1 编排与门禁（本轮）

```yaml
start_existing_task: true
phase: plan_remediation_round_2
workflow_mode: NORMAL
plan_remediation_round: 2
must_not_this_round:
  - "编写业务实现或测试语义（本 phase 仅 Task Plan + progress/master_plan 规划态）"
  - "开始或规划 STM-012"
  - "触碰 DEV-006 / PR #13"
  - "修改 Migration 001/004 正文或已执行 migration 语义"
  - "修改 Settings Contract（新增 group_id 字段等）除非 Plan Review 明确批准并同步规格"
  - "修改 ArchiveCreatedEvent / STM-006 producer Contract（MF-001：仅 consumer-boundary 校验）"
  - "实现 EXT-002 Archive 读取/预处理或其后 Pipeline 阶段"
  - "声称 exactly-once Kafka delivery"
  - "发明 memory_extraction_task 规格未列出的字段（含 session_id / event_id 落库）"
  - "发明 key≠user_id 时 continue/Upsert/commit（MF-002 禁止）"
```

---

## 2. 任务目标

交付 **Memory Extraction Task 持久化 Schema + Kafka Consumer 幂等创建 + Offset 提交语义**，使 `context.archive.created` 的 at-least-once 投递在业务层收敛为「每个 `archive_id` 至多一个任务文档」，并严格遵守规格 Offset 门禁。

可验证交付：

1. **`memory_extraction_task` 领域模型与 Mongo 仓储**（§2.1.3）
   - Document 字段 **仅**规格列出的集合（见 §5.0 C1）
   - 唯一幂等键 = `archive_id`（unique index；DEV-004 已建，本任务 **不**新建 migration）
   - 状态机字面量：`pending` → `processing` → `completed` | `failed`；（人工重试 `failed`→`pending` **不**在本任务实现 —— EXT-008）
2. **Kafka Consumer 循环**（§2.1.4 / §3.6 / §3.19）
   - Topic：`settings.kafka.topic`（默认 `context.archive.created`）
   - Group：字面量 `memory-extraction-group`（规格 §1.2.4 / §2.1.4；见 §5.0 C3）
   - `enable_auto_commit=false`；`max_poll_records=1`；同 Partition **串行**
   - Consumer-boundary：**先**校验 JSON object key 集 **精确等于** `ARCHIVE_CREATED_EVENT_FIELD_NAMES` 六字段，再构造 `ArchiveCreatedEvent`（**不**修改该模型 / STM-006）
3. **§2.1.4 事件处理规则 1–8 的可测试实现骨架**
   - Upsert `$setOnInsert` → `pending`（不覆盖已有状态）
   - `completed` / `failed` 早退并 **Commit Offset**
   - `pending` / `processing` 进入执行前状态转移（`attempt_count++`；`pending` 路径清空 `last_error`）
   - **仅当** Mongo 已成功持久化终态（`completed` 或 `failed`+`last_error`）后才允许 Commit Offset
   - Mongo 终态写入失败 → **禁止** Commit Offset
4. **可注入的 `ExtractionPipelinePort`**（本任务边界）
   - 生产完整 Pipeline（Archive 读 / LLM / Neo4j / ES）属 EXT-002+；本任务只定义 Port + 用 Fake 驱动 Offset/幂等测试
   - **禁止**用生产默认实现把任务标为 `completed` 而跳过后续规格门禁（Neo4j/ES）
5. **测试**：Unit + Contract + Mongo Integration + **真实 Kafka** Integration（重复投递 / replay / DB 失败不提交 / 畸形事件 fail-closed 行为按 §10 Open Issues）

概念链（本任务止点）：

```text
Kafka poll (max 1, auto_commit=false)
  → UTF-8 JSON object
  → consumer-boundary: key set == exact six ARCHIVE_CREATED_EVENT_FIELD_NAMES
  → empty-string ID reject (archive_id/user_id/event_id)
  → ArchiveCreatedEvent model validate (unchanged STM-006 model)
  → Message Key UTF-8 == event.user_id (else fail-closed: no upsert/no pipeline/no commit/stop)
  → upsert memory_extraction_task by archive_id ($setOnInsert pending)
  → branch on status (completed/failed → commit; pending/processing → transition + PipelinePort)
  → PipelinePort returns terminal outcome OR abort
  → persist completed|failed to Mongo (success required)
  → ONLY THEN commit Kafka offset
  → EXT-002+ owns real pipeline stages
```

---

## 3. 非目标（必须坚持；黑名单语义）

- **STM-012** 补发消费验证（需本任务 completed 之后；本轮 **不得**规划或实施）。
- **EXT-002**：Context Archive 读取、ownership/`session_id` 一致性校验、预处理、脱敏、`archive_too_large` 等。
- **EXT-003+**：LLM Structured Extraction、Fingerprint、Entity Alignment、Reconciliation、Neo4j 写、ES 同步、管理 HTTP（EXT-008）。
- 人工重试 API / `failed`→`pending` 管理路径（EXT-008）；自动重试 / Retry Topic / DLT / Outbox（规格明确不实现）。
- Worker 租约、任务抢占、阶段级细粒度状态机、定时扫描（§2.1.3 MVP 不实现）。
- 修改 `ArchiveCreatedEvent` 六字段 Contract；修改 Producer 语义（STM-006/STM-011）。
- 新增或修改已执行 Migration（001/004）；改 ES Mapping/Alias；改 Neo4j schema。
- 向 `memory_extraction_task` **发明**规格未列字段：`session_id`、`event_id`、`event_type`、`failed_stage` 顶层字段（`failed_stage` 仅存在于 `last_error` 内）、lease、cursor 等。
- 把 Kafka 投递伪装成 exactly-once；把 Mongo upsert + Offset commit 伪装成跨系统原子事务。
- 操作 **DEV-006** / **PR #13**。
- 修改 `configs/base.yaml` / Settings 模型以新增未规格化的 consumer `group_id` 配置项（见 §5.0 C3 决议）。
- E2E Session→Extraction 全链路（EXT-009）；本任务 Integration 止于 Task+Consumer+Offset。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `f4015cdca8694c3c2be96992a4957b2838c873e4` |
| `git status --short` | **CLEAN**（规划写盘前） |
| Orchestrator `baseline_main` | **MATCH** `f4015cd…` |
| `formal_STM-006_status` | `completed`；PR #25 **MERGED** |
| `formal_DEV-004_status` | `completed`；PR #10 **MERGED** |
| STM-012 | **NOT ready**（needs EXT-001）；本计划不启动 |
| DEV-006 / PR #13 | **不得触碰** |

### 4.2 可复用组件审计

| 交付物 | 路径 | EXT-001 用法 |
|---|---|---|
| `ArchiveCreatedEvent` 六字段模型 | `domain/models/archive_created_event.py` | **只读复用**：`ConfigDict(strict=True)` **无** `extra="forbid"`；Consumer **不得**改模型；未知字段拒绝在 **consumer-boundary**（C4）完成 |
| `publish_archive_created_event` | `infrastructure/kafka/archive_created_publisher.py` | Integration 测试造数；**不**改 Producer |
| `KafkaSettings` / `KafkaConsumerSettings` | `settings/models.py` + `configs/base.yaml` | topic + consumer 超时/auto_commit/max_poll_records；**不**改默认值语义 |
| Mongo `AsyncMongoClient` 模式 | `infrastructure/mongodb/context_archive_repository.py` | 同构新建 `memory_extraction_task` repository |
| Migration 001 indexes | `scripts/migrations/001_initial_mongodb.py` | **只读依赖**：`archive_id` unique + `(status, updated_time)` |
| Migration 004 topic | `scripts/migrations/004_initial_kafka_topics.py` | Topic `context.archive.created` 已存在 |
| `extraction_worker` stub | `entrypoints/extraction_worker.py` | EXT-001 **钉死** `main()` 仍 exit≠0 拒绝启动 poll loop（C7）；库级 consumer API 供测试 / 后续 EXT-002+ 接线 |
| Metrics 名称 | `observability/metrics.py` | 名称已存在；本任务 **可不**接线计数；禁止改名 |

### 4.3 当前缺失

- `MemoryExtractionTask` / `ExtractionTaskStatus` / `LastError` 领域模型
- `memory_extraction_task` Mongo repository（upsert `$setOnInsert`、按 `archive_id` 加载、状态转移、终态写入）
- `AIOKafkaConsumer` 适配与 Offset 手动提交封装
- 按 §2.1.4 分支的消费处理服务 + `ExtractionPipelinePort`
- Unit / Contract / Mongo+Kafka Integration 测试（含重复投递、replay、DB 失败不提交）

### 4.4 与技术规格一致性

- 任务 Document **不含** `session_id` / `event_id`（§2.1.3 schema 字面）；事件侧保留二者（§1.2.4）。
- 幂等键是 `archive_id`，**不是** `event_id`（§2.1.3 / §2.1.4 / §3.19 #4）。
- Offset 提交晚于任务终态 Mongo 持久化（§2.1.4 #6–#8 / §2.1.15 #4）；`enable_auto_commit=false`（§3.6 / §3.19）。
- §2.1.1 流程图将 Commit 画在 Completed 之后；§2.1.4 同时允许 **failed 持久化成功后** Commit —— 以 **§2.1.4 / §2.1.15** 为 Offset 权威（failed 不阻塞 Partition）。
- §2.1.4 #6 提及「Neo4j 写入成功…才 completed」；完整 completed 门禁含 ES（§2.2.3）。本任务 **不**实现 Neo4j/ES；`completed` 仅能由 **注入的 PipelinePort**（测试 Fake）或未来 EXT-007 门禁后的真实 Pipeline 产出 —— 禁止生产默认空跑标 completed。

### 4.5 前置任务检查

| 前置 | 状态 |
|---|---|
| STM-006 | **SATISFIED**（PR #25 MERGED；六字段 at-least-once Producer） |
| DEV-004 | **SATISFIED**（PR #10 MERGED；见 §4.6 索引/Topic 复核） |
| STM-011 | **SATISFIED**（补发新 `event_id`；消费验证仍属 STM-012） |
| STM-012 | **blocked** on EXT-001 — 本任务完成后才 READY_FOR_PLANNING |

### 4.6 DEV-004 / STM-006 治理复核（规划强制）

#### DEV-004 — Extraction Task 相关 migrations / indexes

| 项 | 规格 §2.1.3 / §3.19 / §3.20 | 当前代码 | 结论 |
|---|---|---|---|
| Collection `memory_extraction_task` | 是 | `001_initial_mongodb.py` 对 `db["memory_extraction_task"]` 建索引 | **MATCH** |
| Unique `{archive_id:1}` name `archive_id_unique` | 是 | `create_index([("archive_id", ASCENDING)], unique=True, name="archive_id_unique")` | **MATCH** |
| Index `{status:1, updated_time:1}` name `status_updated_time` | 是 | 同文件 `name="status_updated_time"` | **MATCH** |
| Topic `context.archive.created` partitions=3 等 | §3.19 | `004_initial_kafka_topics.py` 按 Settings 创建/校验 | **MATCH** |
| Integration 断言覆盖 `memory_extraction_task` 索引 | 期望可回归 | `tests/integration/test_migrate_infra.py` **仅**断言 `context_archive` 索引名，**未**断言 `memory_extraction_task` | **GAP（测试覆盖）** — 不改 migration；本任务 Contract/Integration **补断言**索引存在与 unique |

**DEV-004 verification result: SATISFIED（schema/index/topic 与规格一致；测试覆盖缺口由 EXT-001 补齐，不修改 001/004 升级逻辑）。**

#### STM-006 — Kafka archive-event contract（消费侧依赖）

| 项 | 规格 | 当前 | 结论 |
|---|---|---|---|
| Topic | `context.archive.created` | `KafkaSettings.topic` 默认同名 | **MATCH** |
| 六字段 | `event_id,event_type,archive_id,user_id,session_id,created_time` | `ArchiveCreatedEvent` + `ARCHIVE_CREATED_EVENT_FIELD_NAMES` | **MATCH** |
| Message Key | `user_id` UTF-8 | `publish_archive_created_event` | **MATCH** |
| Delivery | at-least-once | progress `formal_STM-006_delivery_semantics: AT_LEAST_ONCE` | **MATCH** |
| Consumer | 尚未实现 | `extraction_worker.py` stub | **EXPECTED GAP → 本任务** |

---

## 5. 实现方案

### 5.0 Contract 闭合（Planner 权威结论）

#### C1 — Extraction Task Document Schema（§2.1.3 唯一字段集）

| 字段 | 类型/约束 | 说明 |
|---|---|---|
| `task_id` | string；UUID v4 | 插入时生成；之后不可变 |
| `archive_id` | string | **幂等/唯一键**；同一 Archive 仅一任务 |
| `user_id` | string | 来自事件；插入时写入；用于隔离（管理 API 属 EXT-008） |
| `status` | enum string | **仅** `pending` \| `processing` \| `completed` \| `failed` |
| `attempt_count` | int | 每次 **开始执行** 时递增（§2.1.4 #4/#5） |
| `extraction_result` | object \| null | 本任务不填充真实 LLM 结果；须允许 null；非空时 processing 恢复不得再调 LLM（规则留给 EXT-003+；Port 必须遵守「非空则跳过 LLM」接口契约） |
| `last_error` | object \| null | 形状：`{error_code, failed_stage, message}`；成功路径为 null |
| `created_time` | int Unix | 插入时 |
| `updated_time` | int Unix | 每次更新 |
| `completed_time` | int \| null | 仅 `completed` 时非 null |

**禁止落库**：`session_id`、`event_id`、`event_type`、顶层 `failed_stage`、lease/owner、offset 元数据。

**身份 / 幂等键**：

- Kafka 业务幂等：**`archive_id`**（unique index）
- 任务主键展示：`task_id`（UUID）；**不**用作 Kafka 去重键
- **`event_id`**：仅事件层标识；重复投递或 republish 可换新 `event_id`；**不**写入 task；**不**作为幂等键

#### C2 — Indexes / Uniqueness（只验证，不新建 migration）

| Index | 规格 | 本任务动作 |
|---|---|---|
| `archive_id` unique | §2.1.3 | 依赖 DEV-004；测试断言存在 |
| `(status, updated_time)` | §2.1.3 | 同上 |

并发双 insert 同 `archive_id`：一方 `DuplicateKey` → 转为 load existing（与 `$setOnInsert` upsert 语义一致）；**不得**覆盖已有 `status` / `extraction_result`。

#### C3 — Consumer Group / Client 参数

| 项 | 值 | 来源 |
|---|---|---|
| Topic | `settings.kafka.topic` | DEV-002 / STM-006 |
| Group id | 常量 `MEMORY_EXTRACTION_CONSUMER_GROUP = "memory-extraction-group"` | §1.2.4 / §2.1.4 字面量 |
| `enable_auto_commit` | `false` | `KafkaConsumerSettings` / §3.19 |
| `auto_offset_reset` | `earliest` | 同上 |
| `max_poll_records` | `1` | 同上 |
| `session_timeout_ms` / `heartbeat_interval_ms` / `max_poll_interval_ms` | Settings 默认 | §3.19 |
| Key 期望 | UTF-8 bytes decode 后 **精确等于** `event.user_id` | §3.19 #1；否则 → **C3.1 fail-closed**（非 continue） |

**决议**：`group_id` **不**新增 Settings 字段（避免未规格化 Contract 扩张）；模块级 Final 常量对齐规格字面量。若 Plan Review 要求配置化，须 Amendment + 规格确认。

##### C3.1 — Kafka Message Key ≠ `event.user_id`（MF-002；fail-closed 中间态）

规格要求 Key **必须**为 `user_id`（§1.2.4 / §3.19 #1），但未定义不一致时的运维恢复策略（无 DLT）。

**EXT-001 强制中间行为（禁止发明 continue/value-wins）**：

1. 在 C4 成功解析出 `event.user_id` 之后、任何 Mongo upsert / Pipeline 调用之前，比较：
   - `key is None` / 非 UTF-8 / decode 后字符串 **≠** `event.user_id` → mismatch
2. 发射 **非 Secret** 诊断日志（可含 `archive_id`、decoded key 摘要、`event.user_id`；禁止完整用户消息/凭证）
3. **不得** create/update `memory_extraction_task`
4. **不得** 调用 `ExtractionPipelinePort`
5. **不得** Commit Kafka Offset
6. **停止**当前 consumer 处理路径（向上抛出可测异常 / 终止 poll loop，使 worker 按既有失败语义退出）；**不得**静默跳过并继续后续 record；**不得** DLQ（规格未定义）

OI-EXT-001-002 保持 open：**仅**作为「等待规格 Amendment 定义替代策略（例如跳过+commit / DLT）」的跟踪项；**interim 行为以上表为准，不是 continue**。

#### C4 — Deserialize / Validation（事件；MF-001 consumer-boundary）

**权威事实**：当前 `ArchiveCreatedEvent` 为 `ConfigDict(strict=True)`，**没有** `extra="forbid"`。Producer `to_json_bytes` 只写出六字段，但 **模型本身不拒绝未知键**。规格 §1.2.4 Message Schema 列出且仅列出六字段 —— consumer 侧 exact-key 拒绝与六字段 Contract **一致**，且 **不**要求修改 STM-006 模型。

**处理顺序（必须）**：

1. Value bytes → UTF-8；JSON parse 为 `dict`（非 object / JSON 非法 → **畸形** C8）。
2. **Consumer-boundary exact-key 校验（本任务新增；不改模型）**：
   - `set(payload.keys()) == set(ARCHIVE_CREATED_EVENT_FIELD_NAMES)` 必须成立
   - 缺任一必填键 → **畸形**
   - 存在任一未知/额外键 → **畸形**
3. 空串 ID（SF-005）：`archive_id`、`user_id`、`event_id`、`session_id` 任一值 **精确等于** `""` → **畸形**（不发明额外 trim/空白折叠规则）。
4. 通过 boundary 后：`ArchiveCreatedEvent.model_validate(payload)`（沿用现有 `strict=True`；**不**改模型）；`event_type` 必须等于 `context.archive.created`。
5. 类型错误 / 校验失败 → **畸形**（C8）。
6. **然后**执行 C3.1 Message Key 校验。
7. `event_id` / `session_id`：**不**落库；ownership 深校验属 EXT-002。

**禁止**：修改 `ArchiveCreatedEvent`、`ARCHIVE_CREATED_EVENT_FIELD_NAMES`、publisher、或 STM-006/STM-011 生产路径来「补」`extra="forbid"`。Exact-key / 空串拒绝 **仅**存在于 consumer-boundary helper（建议纯函数，Unit 单测）。

#### C5 — §2.1.4 状态分支与 Offset（权威）

| # | 条件 | 动作 | Offset |
|---|---|---|---|
| 1 | 任意合法事件 | `update_one({archive_id}, {$setOnInsert: pending 文档}, upsert=True)` 后 load | 尚未 |
| 2 | `status==completed` | 不调用 Pipeline；不改文档（或仅可观测日志） | **Commit** |
| 3 | `status==failed` | 不自动重试；不调用 Pipeline | **Commit** |
| 4 | `status==pending` | → `processing`；`attempt_count += 1`；`last_error=null`；`updated_time=now`；然后 PipelinePort | 按 Pipeline 结果 |
| 5 | `status==processing` | `attempt_count += 1`；`updated_time=now`；若 `extraction_result` 非空，Port **不得**再调 LLM；然后 PipelinePort | 按 Pipeline 结果 |
| 6/7 | Pipeline 成功终态 / 失败终态 | Mongo 写入 `completed`（+`completed_time`）或 `failed`（+`last_error`）**成功后** | **Commit** |
| 8 | 终态 Mongo 写入失败 | 不改 Offset | **禁止 Commit**（将 replay） |

**通用不变量**：`status` 仍为 `processing`（或 Upsert/转移未完成）时 **禁止** Commit Offset。

#### C6 — 四类语义显式区分（强制专节）

##### C6.1 Duplicate Kafka event（同一消息重复投递 / 同 `event_id` 重送）

- Broker/consumer at-least-once 导致同一 offset 或同一 payload 再次处理。
- 行为：Upsert **不**覆盖；若任务已 `completed`/`failed` → 直接 Commit；若仍 `pending`/`processing` → 按 #4/#5 恢复执行。
- **不**因重复 `event_id` 创建第二任务。

##### C6.2 Same archive republished with a **new** `event_id`（STM-011 / 人工重试发布）

- Payload：`archive_id` 相同，`event_id` 不同（可能 `created_time` 不同）。
- 行为：仍按 `archive_id` 幂等；**不**新建任务；`event_id` 不落库故无「事件去重表」。
- 若任务已 `completed`/`failed`：Commit 并跳过（§2.1.4 #2/#3）。人工把 `failed`→`pending` 后的再执行属 EXT-008，不在本任务。
- 与 C6.1 差异：业务上是**新发布**，但消费幂等键仍是 `archive_id`。

##### C6.3 Consumer replay after crash（进程在 Commit 前退出）

- Offset 未提交 → 同 Partition 消息重新投递。
- 任务可能已是 `processing`（甚至已有 `extraction_result`）→ 走 #5 恢复；`attempt_count` 递增。
- 若崩溃发生在终态 Mongo 成功之后、Commit 之前：replay 后走 #2 或 #3 → Commit；**不**重复副作用（Pipeline 在 completed/failed 早退）。
- 若崩溃在终态 Mongo **之前**：replay 继续 #4/#5。

##### C6.4 Database uniqueness conflict（并发 upsert / 双 Consumer 竞态）

- 唯一索引 `archive_id` 保证物理至多一行。
- 处理：捕获 `DuplicateKeyError` **或**依赖 upsert 原子性；冲突后 **load existing**，进入 C5 分支；**禁止** delete-retry 抹掉已有状态；**禁止** `$set` 覆盖非 OnInsert 字段来「修好」竞态。

#### C7 — `ExtractionPipelinePort` + 生产 Entrypoint 钉死（SF-001）

```text
Protocol ExtractionPipelinePort:
  async def run(task: MemoryExtractionTask, event: ArchiveCreatedEvent) -> PipelineTerminalDecision
```

`PipelineTerminalDecision`：

- `complete` — 消费层写 `status=completed`、`completed_time`、清/保留 `last_error` 按规格（成功清 null）
- `fail(last_error)` — 消费层写 `status=failed` + `last_error`；**不得删除**已有 `extraction_result`
- `abort_without_terminal` — 模拟「终态写库前崩溃/中止」；消费层 **不** Commit（测试用）

本任务：

- Unit/Integration **注入 Fake Port** 覆盖 Offset 矩阵
- **禁止**生产默认 Port 直接 `complete`（会违反尚未实现的 Neo4j/ES 完成门禁）
- **生产 `extraction_worker.main()` 唯一钉死行为（SF-001 / 关闭 OI-004 双选项）**：
  - `main()` **必须** print 明确 stderr（说明 production extraction pipeline 未就绪 / EXT-002+）并以 **非 0** 退出
  - `main()` **不得**启动 Kafka poll loop、**不得**创建/提交 Offset、**不得**写入 `memory_extraction_task`
  - 可测试的库级 API（例如 `run_archive_created_consumer_loop(...)` / consumer service）由 Unit/Integration **直接调用**；EXT-002+ 再将真实 Port 接入 `main()`
  - **禁止**伪造 `completed` 或 exit 0「假装就绪」

#### C8 — Malformed event / boundary reject（fail-closed；见 Open Issue）

规格未定义「无法解析 / 额外字段 / 空 ID」时的 Offset 策略。MVP **无** DLT。

**本任务强制（畸形与 C3.1 key mismatch 共用「不 Commit + 停处理」外形；分类日志不同）**：

- **不得**为了不阻塞 Partition 而擅自 Commit 畸形消息（可能丢事件）。
- **不得**发明 `error_code` 写入不存在的 task。
- 畸形包含（C4）：JSON 非法、非 object、缺键、**额外/未知键**、空串 `archive_id`/`user_id`/`event_id`/`session_id`、`event_type` 非法、类型校验失败。
- 实现：检测后记录结构化错误日志（无 Secret）、**不** Commit、**不** upsert、向上抛出或停止 poll 循环；生产运维影响记入 §10 OI-EXT-001-001，等待规格 Amendment（跳过/DLT）。关闭前禁止改「不 Commit」中间态。

#### C9 — At-least-once 含义（本任务承诺）

- 允许：重复处理、`attempt_count` 增大、重复 Fake Pipeline 调用（在非终态时）。
- 禁止：同一 `archive_id` 两条 task 文档；在 `completed`/`failed` 后再次执行 Pipeline；终态未入 Mongo 却 Commit。

#### C10 — `user_id` 在 Upsert 时的处理

- `$setOnInsert` 写入事件的 `user_id`。
- 若已存在任务且 `task.user_id != event.user_id`：规格深层校验在 §2.1.5（EXT-002）。本任务 **Open Issue OI-EXT-001-003**：不得在 EXT-001 私自覆盖 `user_id` 或自动 `failed`。实现：**保持已有文档不变**，仍按现有 `status` 走 C5（completed/failed 仍 Commit；pending/processing 仍进 Port）。日志记录 mismatch 可观测字段。

---

### Step 1 — 领域模型与枚举

- 文件：
  - `src/memory_system/domain/enums/extraction_task.py`（新建）
  - `src/memory_system/domain/models/extraction_task.py`（新建）
- Schema：`ExtractionTaskStatus`；`ExtractionLastError`（`error_code`/`failed_stage`/`message`）；`MemoryExtractionTask`（C1 字段；Pydantic strict / `extra=forbid`）
- 输入/输出：纯模型；无 IO
- 错误处理：非法 status 构造失败
- 幂等：N/A

### Step 2 — Mongo repository

- 文件：`src/memory_system/infrastructure/mongodb/extraction_task_repository.py`（新建）
- **SF-003**：`infrastructure/mongodb/__init__.py` / `infrastructure/kafka/__init__.py` — **不修改**（无 package 导出更新；测试与调用方直 import 新模块路径）
- 函数（建议命名，实现可微调）：
  - `upsert_pending_extraction_task(...)` — `update_one` filter=`{archive_id}`，`$setOnInsert` 含 `task_id/user_id/status=pending/attempt_count=0/extraction_result=null/last_error=null/created_time/updated_time/completed_time=null`
  - `find_extraction_task_by_archive_id`
  - `mark_processing_from_pending` / `bump_processing_attempt`（对应 #4/#5；可用 find_one_and_update 保证条件更新）
  - `mark_completed` / `mark_failed`
- 输入：`AsyncMongoClient` + 字段
- 输出：领域模型
- 错误处理：`DuplicateKeyError` → reload；条件更新失败（状态已变）→ reload 再分支
- 幂等/并发：单文档；唯一索引；禁止多文档事务

### Step 3 — Pipeline Port + 消费应用服务

- 文件：
  - `src/memory_system/domain/services/extraction_pipeline_port.py`（或同目录 protocol 模块）
  - `src/memory_system/domain/services/extraction_task_consumer_service.py`
- 逻辑：实现 C5 全部分支；调用 repository；根据 Port 决策写终态；返回 `should_commit_offset: bool`
- **SF-004**：凡将任务置 `failed`（含 Port `fail` 路径）的日志 **必须**包含 `task_id`、`archive_id`、`user_id`、`failed_stage`、`attempt_count`（§2.1.15 #6）；`session_id` 可从 event 在可用时附加，非强制落库
- 错误处理：repository 终态写失败 → `should_commit_offset=False`；向上传播可测异常
- 幂等：C6 全部分类由服务行为覆盖

### Step 4 — Kafka Consumer 适配

- 文件：`src/memory_system/infrastructure/kafka/archive_created_consumer.py`（新建）
- 类/函数：创建 `AIOKafkaConsumer`（topic、`group_id` 常量、settings.kafka_consumer.*、`enable_auto_commit=False`）；`getmany`/`__anext__` 拉取单条；`commit` 显式提交当前消息 offset
- 反序列化：**C4 consumer-boundary exact-key** → `ArchiveCreatedEvent`；畸形走 C8；**C3.1** key 校验
- 库级 loop API：供 Integration 直接调用（`main()` 不调用 — C7）
- **串行**：单协程处理循环；禁止同 Partition 并发 `asyncio.create_task` 多消息

### Step 5 — Entrypoint（钉死拒绝启动）

- 文件：`src/memory_system/entrypoints/extraction_worker.py`（修改 stub 文案即可）
- 行为：按 C7 — **exit ≠ 0**；更新 stderr 说明「pipeline stages EXT-002+；库级 consumer 已实现但不由 main 启动」
- **不得**在 EXT-001 使 `main()` 进入 poll loop

### Step 6 — 测试（见 §8）

- 补齐 migrate 对 `memory_extraction_task` 索引的断言（integration 查真实 indexes）

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/enums/extraction_task.py` | 创建 | `ExtractionTaskStatus` 等枚举 |
| `src/memory_system/domain/models/extraction_task.py` | 创建 | Task / LastError 模型（§2.1.3） |
| `src/memory_system/domain/services/extraction_pipeline_port.py` | 创建 | Pipeline Protocol + 终态决策类型 |
| `src/memory_system/domain/services/extraction_task_consumer_service.py` | 创建 | §2.1.4 分支 + Offset 门禁 |
| `src/memory_system/infrastructure/mongodb/extraction_task_repository.py` | 创建 | Upsert / 状态更新 |
| `src/memory_system/infrastructure/kafka/archive_created_consumer.py` | 创建 | AIOKafkaConsumer 封装；group 常量；手动 commit；C4 boundary |
| `src/memory_system/entrypoints/extraction_worker.py` | 修改 | **仅**更新拒绝启动文案；`main()` exit≠0（C7）；不启动 poll |
| `tests/unit/test_extraction_task_models.py` | 创建 | Schema / 枚举 / last_error 形状 |
| `tests/unit/test_extraction_task_repository.py` | 创建 | Upsert 幂等 / 状态转移（可 fake mongo 或 mongomock 若项目已有；否则重逻辑单测 + integration 真 Mongo） |
| `tests/unit/test_extraction_task_consumer_service.py` | 创建 | C5/C6 矩阵 + DB 失败不提交 + C4/C3.1 + failed 日志字段 |
| `tests/unit/test_archive_created_consumer_boundary.py` | 创建 | exact-key / 空串 ID / 不改 ArchiveCreatedEvent |
| `tests/contract/test_ext001_contract.py` | 创建 | 字段集、status 枚举、group 字面量、consumer settings、索引名与 migration 001 一致；模型仍无 extra=forbid |
| `tests/integration/test_extraction_task_mongo.py` | 创建 | 真 Mongo unique / upsert / 并发 |
| `tests/integration/test_extraction_consumer_kafka.py` | 创建 | 真 Kafka：消费、重复投递、replay、commit 时机、key mismatch |
| `tests/integration/test_migrate_infra.py` | 修改 | **仅追加** `memory_extraction_task` 索引断言；不改 migration 逻辑 |
| `02_开发管理/tasks/EXT-001-task-schema-kafka-consumer-idempotency-offset.md` | 创建/更新 | 本计划与执行记录 |
| `02_开发管理/progress.md` | 修改 | 规划态 / 完成后状态 |
| `02_开发管理/master_plan.md` | 修改 | EXT-001 登记 |

### 6.1 明确不在白名单

- `scripts/migrations/001_*.py` / `004_*.py` 升级逻辑
- `src/memory_system/settings/**`（除非 Amendment 批准 group_id）
- `configs/**`
- `src/memory_system/domain/models/archive_created_event.py`（**禁止**改 STM-006 模型）
- `src/memory_system/infrastructure/kafka/archive_created_publisher.py` / STM-011 脚本
- `src/memory_system/infrastructure/mongodb/__init__.py` / `src/memory_system/infrastructure/kafka/__init__.py`（SF-003：**不修改**）
- Neo4j / ES / LLM / Redis / HTTP 路由
- DEV-006 / PR #13 任何路径
- STM-012 任何路径

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | Mongo 单文档更新原子；Kafka offset 独立 | 终态成功后才 commit；失败窗口 = at-least-once replay |
| 幂等 | `archive_id` unique + `$setOnInsert` | 重复事件不覆盖状态；completed/failed 早退 |
| 并发 | 同 key 分区串行；跨实例可能竞态 upsert | unique index + DuplicateKey→load；条件更新 |
| 版本冲突 | 无独立 version 字段 | 用不适用；状态条件更新代替 |
| 用户隔离 | task 含 `user_id`；管理 API 属 EXT-008 | 本任务日志带 `user_id`；不实现跨用户查询 API |
| 部分失败 | Pipeline 已副作用但未写终态 | 不 commit → replay；Port/后续阶段自备幂等（EXT-004+） |
| 进程异常恢复 | 未 commit → replay；processing 恢复 | §2.1.4 #5；`extraction_result` 复用契约由 Port 遵守 |

不适用说明：无跨 Collection 事务（§3.20 禁止为方便新增）。

---

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| Task 模型仅含 C1 字段；`extra=forbid` | 构造多余字段失败 |
| status 枚举四值 | 字面量与规格一致 |
| `last_error` 三字段形状 | 可序列化；成功路径 null |
| Consumer-boundary：exact six keys OK | 进入 model_validate |
| Consumer-boundary：额外未知键 | 畸形；不 upsert；不 commit |
| Consumer-boundary：缺键 | 畸形 |
| 空串 `archive_id`/`user_id`/`event_id`/`session_id` | 畸形（SF-005） |
| `ArchiveCreatedEvent` 模型仍接受额外键（证明未改模型） | 直接 `model_validate` 含额外键 **不**因本任务而变成 forbid；拒绝只在 boundary |
| Key ≠ `event.user_id` / key missing | C3.1：无 task 写；不调 Port；不 commit；处理路径失败/停止 |
| Upsert `$setOnInsert` 语义（repo 单测或服务单测 + stub） | 第二次不覆盖 status/result |
| `completed` 早退 | 不调 Port；`should_commit=True` |
| `failed` 早退 | 不调 Port；`should_commit=True` |
| `pending`→`processing` | `attempt_count` +1；`last_error` 清空；调 Port |
| `processing` 恢复 | `attempt_count` +1；调 Port；若 result 非空 Port 跳过 LLM（Fake 断言） |
| Port `complete` | Mongo completed + `completed_time`；`should_commit=True` |
| Port `fail` | Mongo failed + last_error；**保留**既有 extraction_result；`should_commit=True`；日志含 SF-004 五字段 |
| 终态写库失败 | `should_commit=False` |
| Port `abort_without_terminal` | 保持 processing；`should_commit=False` |
| DuplicateKey 路径 | load existing 后正确分支 |
| 畸形 JSON | 不 commit；不创建 task；见 OI-001 |
| `extraction_worker.main()` | exit ≠ 0；无 Kafka/Mongo 副作用（C7） |

### Contract Test

| 场景 | 预期 |
|---|---|
| Task JSON 字段名全集 == 规格 C1 | 无 session_id/event_id |
| Status 四值集合 | 精确匹配 |
| Consumer group 常量 | `memory-extraction-group` |
| `KafkaConsumerSettings.enable_auto_commit is False` | 与 base.yaml / 模型默认一致 |
| `max_poll_records == 1` | 一致 |
| Migration 001 源含 `memory_extraction_task` 两索引名 | `archive_id_unique` / `status_updated_time` |
| `ArchiveCreatedEvent` 源码仍无 `extra="forbid"` | 静态/AST 或 `model_config` 断言；本任务未改该文件 |
| `ARCHIVE_CREATED_EVENT_FIELD_NAMES` 恰为六元组 | 与 boundary 使用同一常量 |

### Integration Test

| 场景 | 预期 |
|---|---|
| 真 Mongo：upsert 同 `archive_id` 两次 | 仅 1 文档；同一 `task_id` |
| 真 Mongo：unique 冲突 | 不出现两行 |
| 真 Mongo：索引名存在 | `archive_id_unique` unique；`status_updated_time` 存在 |
| 真 Kafka：合法六字段 + key=user_id → 库级 consumer | Fake Port 至终态后 **手动 commit**；断言 **同一 consumer group** 下 committed offset **前进**且对该消息 **不再 redelivery**（SF-002；禁止仅用「新 group」偷换语义） |
| Duplicate delivery（同 payload 两次处理 / 未 commit 重放） | 仍 1 task；completed 后第二次不调 Port |
| New `event_id` 同 `archive_id` | 仍 1 task；行为同 C6.2 |
| Crash/replay：Fake Port abort 后再次投递 | attempt_count 递增；最终可完成；仅终态后 commit |
| DB failure before commit（注入 repository 终态写失败） | offset **未**提交；同 group 可再消费 |
| Malformed / extra-key / empty ID | 无 task 行；offset 未提交；处理失败（C8） |
| Key mismatch | 无 task 行；offset 未提交；不继续后续 record（C3.1） |
| Idempotent task creation | 并发双处理同 archive → 1 文档 |

### E2E Test

| 场景 | 预期 |
|---|---|
| 不适用本任务 | 全链路 E2E 属 EXT-009 / STM-012；本任务不新增 `tests/e2e/**` |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 终态 Mongo 写失败 | 不 commit |
| Upsert 后、转 processing 前失败 | 不 commit；replay 可继续 |
| 并发两协程同 `archive_id` upsert | 单文档；无覆盖 completed→pending |
| Consumer `enable_auto_commit` 误开防护 | 创建 consumer 时强制 False（断言配置） |

---

## 9. 验收标准

- [ ] `memory_extraction_task` 模型字段与 §2.1.3 一致（无发明字段）
- [ ] Consumer-boundary exact six-key + 空串 ID 拒绝可测；**未**修改 `ArchiveCreatedEvent`（MF-001）
- [ ] Key≠`user_id`：无 upsert / 无 pipeline / 无 commit / 停止处理（MF-002）
- [ ] Upsert `$setOnInsert` + `archive_id` 唯一幂等可测通过
- [ ] §2.1.4 状态分支与 Offset 门禁（含 failed 后 commit、终态写失败不 commit）可测通过
- [ ] C6.1–C6.4 四类语义均有对应测试
- [ ] failed 日志含 `task_id/archive_id/user_id/failed_stage/attempt_count`（SF-004）
- [ ] `main()` exit≠0 且不启动 poll（SF-001）
- [ ] 真实 Kafka Integration：同 group committed offset 前进 / 无 redelivery（SF-002）
- [ ] 真实 Mongo 索引断言通过（补齐 migrate 缺口）
- [ ] 未修改 Migration 升级逻辑；未触碰 DEV-006/PR#13；未实施 STM-012；未改 `__init__.py` 导出（SF-003）
- [ ] 对应测试全部通过
- [ ] Ruff 通过
- [ ] Mypy 通过
- [ ] Review 无 P0/P1

---

## 10. 风险与阻塞项

### 10.1 Open Issues（fail-closed；不得私解）

#### OI-EXT-001-001 — Malformed / undecodeable Kafka message Offset 策略（仍 OPEN）

| 项 | 内容 |
|---|---|
| 规格缺口 | §2.1.4 未定义 JSON 损坏、缺键、**额外键**、空串 ID、`event_type` 错误时是否允许 Commit / 跳过 / DLT |
| 风险 | Commit → 静默丢事件；不 Commit → Partition 头阻塞 |
| EXT-001 interim（钉死） | **不 Commit** + **不**发明 failed task + **停止**处理路径（C8）；含 exact-key / 空串拒绝 |
| 关闭条件 | 规格 Amendment 定义替代策略（跳过+commit 或 DLT）；关闭前禁止改「不 Commit」 |

#### OI-EXT-001-002 — Kafka Message Key 与 value.`user_id` 不一致（仍 OPEN；interim 已钉死）

| 项 | 内容 |
|---|---|
| 规格 | Key **必须**为 `user_id`（§3.19 #1）；**未**定义不一致时的恢复/跳过策略 |
| Round 1 错误 | 曾发明「value wins / continue Upsert+commit」—— **已删除**（MF-002） |
| EXT-001 interim（钉死） | C3.1：诊断日志 → **无** upsert → **无** pipeline → **无** commit → **停止**处理；不静默续消费；无 DLT |
| 关闭条件 | 规格 Amendment 批准替代策略（例如跳过+commit / DLT / 管理干预）；在此之前实现必须遵循 C3.1 |

#### OI-EXT-001-003 — 重复事件 `user_id` 与已有 task.`user_id` 不一致（仍 OPEN）

| 项 | 内容 |
|---|---|
| 规格 | 归属深校验在 §2.1.5（`archive_ownership_mismatch`） |
| EXT-001 interim | 不覆盖已有 `user_id`；不自动 failed（C10）；按现有 status 走 C5 |
| 关闭 | EXT-002 Archive ownership 三角校验 |

#### OI-EXT-001-004 — 生产 Entrypoint 在 EXT-002 前（**RESOLVED at plan** by SF-001）

| 项 | 内容 |
|---|---|
| 决议 | `main()` **唯一**行为 = exit≠0 拒绝启动 poll（C7）；库级 API + 测试为 EXT-001 验收权威 |
| 状态 | **resolved（plan-level）**；实现后由 Code Review 核对 `main()` 无 poll |
| 后续 | EXT-002+ 将真实 Port 接入 `main()` 属后续任务 Amendment/计划 |

**open_issues after remediation**：OI-001 **OPEN**；OI-002 **OPEN**（interim C3.1 fail-closed）；OI-003 **OPEN**；OI-004 **RESOLVED（plan）**。

### 10.2 其他风险

- 设计文档冲突：§2.1.1 流程图 vs §2.1.4 failed-commit —— 以 §2.1.4/§2.1.15 为准（已记录）。
- 当前代码冲突：无；`ArchiveCreatedEvent` 无 `extra=forbid` —— 由 consumer-boundary 闭合（MF-001）。
- 前置任务：STM-006 / DEV-004 **SATISFIED**。
- Partition 阻塞：畸形 / key mismatch 的不 Commit 策略（OI-001/002）属已知运维风险，直至规格 Amendment。

**Integration group_id（SF-002）**：commit/redelivery 断言必须在**同一 group** 上观测 committed offset 前进与无再投递；可用唯一测试 group 名避免污染，但**禁止**用「换新 group」代替「已 commit 不再消费」的证明。工厂默认仍注入生产常量 `memory-extraction-group`（Contract 锁定）。

---

## 11. Git 计划

```yaml
branch: "feat/EXT-001-task-schema-kafka-consumer-idempotency-offset"
workflow_mode: NORMAL
expected_commits:
  - "docs(plan): add EXT-001 task schema kafka consumer plan"
  - "feat(ext): add extraction task schema and kafka consumer idempotency"
  - "docs(status): record EXT-001 implementation"
out_of_scope_changes:
  - "STM-012 / EXT-002+ pipeline stages"
  - "DEV-006 / PR #13"
  - "Migration 001/004 upgrade semantics"
  - "Settings Contract new fields without Amendment"
  - "Neo4j / ES / LLM / HTTP extraction admin"
RELEASE_PHASE_NOTES:
  PLAN_LANDING: "docs(plan) on main + ff-only + create exact feat branch"
  IMPLEMENTATION_RELEASE: "whitelist paths only on feat; gh pr create; no push main"
  POST_MERGE_CLEANUP: "after MERGED; docs(status): complete on main; delete exact feat only"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：2026-08-11 12:44 UTC
- 原计划：Round 1 初版（`plan_review_round: 1`）
- 修改内容：
  - **MF-001**：纠正「`ArchiveCreatedEvent` extra 禁止扩展」误述；钉死 **consumer-boundary exact six-key** 校验（缺键/未知键=畸形）；**不**修改 STM-006 模型
  - **MF-002**：删除 OI-002「value wins / continue Upsert」；钉死 C3.1 key mismatch fail-closed（无 upsert / 无 pipeline / 无 commit / 停止处理）
  - **SF-001**：钉死 `main()` exit≠0 不启动 poll；OI-004 plan-level resolved
  - **SF-002**：Integration 改为同 group committed offset 前进 / 无 redelivery
  - **SF-003**：白名单钉死 **不修改** `mongodb/__init__.py` 与 `kafka/__init__.py`
  - **SF-004**：failed 日志强制五字段
  - **SF-005**：空串 `archive_id`/`user_id`/`event_id`/`session_id` = 畸形
- 修改原因：Plan Review Round 1 `PLAN_REJECTED`（BLOCKER=0，MUST_FIX=2，SHOULD_FIX=5）
- 是否影响技术规格：否（不改规格正文；interim fail-closed 待 Amendment 关闭 OI-001/002）
- 审批状态：pending Plan Review Round 2

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-11 12:31 UTC | Planner 初版计划 | 本文件 + progress/master_plan 规划态 | N/A | Open Issues 001–004 |
| 2026-08-11 12:44 UTC | Planner Round 2 remediation（Amendment 001） | MF-001/MF-002 + SF-001..005；OI 状态更新；progress/master_plan 规划态 | N/A | OI-004 plan-resolved；OI-001/002/003 remain open |
| 2026-08-11 13:57 UTC | POST_MERGE_CLEANUP | progress/master_plan completed governance；PR #34 MERGED merge ae346dd | N/A | feat 分支待删；STM-012 prerequisites SATISFIED — NOT auto-started |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/domain/enums/extraction_task.py` | Created |
| `src/memory_system/domain/models/extraction_task.py` | Created |
| `src/memory_system/domain/services/extraction_pipeline_port.py` | Created |
| `src/memory_system/domain/services/extraction_task_consumer_service.py` | Created |
| `src/memory_system/infrastructure/mongodb/extraction_task_repository.py` | Created |
| `src/memory_system/infrastructure/kafka/archive_created_consumer.py` | Created |
| `src/memory_system/entrypoints/extraction_worker.py` | Updated refusal-only entrypoint |
| `tests/unit/test_extraction_task_models.py` | Created |
| `tests/unit/test_extraction_task_repository.py` | Created |
| `tests/unit/test_extraction_task_consumer_service.py` | Created |
| `tests/unit/test_archive_created_consumer_boundary.py` | Created |
| `tests/contract/test_ext001_contract.py` | Created |
| `tests/integration/test_extraction_task_mongo.py` | Created |
| `tests/integration/test_extraction_consumer_kafka.py` | Created and corrected record isolation |
| `tests/integration/test_migrate_infra.py` | Added approved task-index assertions only |

### 与原计划的差异

Integration tests required sequential real test-stack execution; no implementation or Contract deviation.

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit + Contract | `uv run pytest -q tests/unit/test_extraction_task_models.py tests/unit/test_extraction_task_repository.py tests/unit/test_extraction_task_consumer_service.py tests/unit/test_archive_created_consumer_boundary.py tests/contract/test_ext001_contract.py` | 45 passed |
| Integration Mongo/migration | `uv run pytest -q tests/integration/test_extraction_task_mongo.py tests/integration/test_migrate_infra.py` | 5 passed |
| Integration Kafka | `uv run pytest -q tests/integration/test_extraction_consumer_kafka.py` | 8 passed |
| E2E | N/A |  |
| Ruff | `uv run ruff check <all changed scoped files>` | PASS |
| Mypy | `uv run mypy <7 changed production files>` | PASS |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 1
review_report: CODE_REVIEW_APPROVED Round 2
```

### Git 记录

```yaml
branch: feat/EXT-001-task-schema-kafka-consumer-idempotency-offset
plan_commit: 6f716946638d9585f0aa53854723559b9f8044bb
implementation_commit: afd8b64dfd4856b4a2f00f82846dace76617e0d1
implementation_commit_message: "feat(ext): add extraction task schema and kafka consumer idempotency"
record_commit: b16c2e05c351cf5402489262a601f9e3afcd20ba
record_commit_message: "docs(status): record EXT-001 implementation commit and PR"
merge_commit: ae346dd27cda39f93fa38b7316ec17559df217ef
merged_at: "2026-08-11T13:57:07Z"
pr: "#34"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/34"
pr_state: MERGED
status_record_completed: 128ab7dcae452561ecedf06aadb88b572fadf0be
```

### 最终状态

`completed`
