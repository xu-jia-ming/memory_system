# STM-011 Republish Archive Event Script

## 1. 任务信息

```yaml
task_id: STM-011
task_name: scripts/republish_archive_event.py (publishing-side)
status: committed
workflow_mode: NORMAL
workflow_mode_source: explicit
plan_review_round: 1
spec_sections:
  - "§1.2.2 Context Archive 生命周期（Mongo archive 字段；archive_id 唯一索引）"
  - "§1.2.4 Kafka Event 设计（topic/schema/Message Key/发布失败人工补发；§836 补发工具）"
  - "§2.1.14 Memory Extraction 管理接口（retry 规则 6：新 event_id、key=user_id、同 archive_id）"
  - "§3.4 单仓库目录结构（scripts/republish_archive_event.py）"
  - "§3.4 安全约束（CLI-only；受信任环境；凭证来自环境变量）"
prerequisites:
  formal:
    - "STM-006 — SATISFIED（ArchiveCreatedEvent + publish_archive_created_event + at-least-once 语义；PR #25 MERGED）"
  implementation_reuse:
    - "STM-005 — SATISFIED（ContextArchive 模型 + context_archive_repository；PR #23 MERGED）"
    - "DEV-002 — SATISFIED（Settings / KafkaSettings / KafkaProducerSettings / Mongo URI）"
  baseline:
    - "Authoritative baseline（Orchestrator）：main == 26f31bdf44e879881c8a160ec3855fab88d4e86e；working tree clean"
    - "本任务需要 Mongo + Kafka（compose test 栈）；不需要 Redis / Neo4j / ES / LLM / HTTP / EXT-001"
branch: "feat/STM-011-republish-archive-event"
created_at: "2026-08-11 11:30 UTC"
updated_at: "2026-08-11 11:30 UTC"
approval_gates:
  planning_docs: pending
  implementation_plan: pending
```

### 1.1 编排与门禁（本轮）

```yaml
start_existing_task: true
phase: planning_only
must_not_this_round:
  - "进入 Developer / 编写业务实现或测试语义"
  - "git add / commit / push / merge / rebase"
  - "规划或实现 STM-012"
  - "创建/修改 EXT-001"
  - "触碰 DEV-006 / PR #13"
  - "修改 archive event 六字段 Contract"
  - "增加 HTTP republish Endpoint（OI-007）"
```

---

## 2. 任务目标

交付 **发布侧人工补发** 能力：运维人员可通过受信任环境中的 CLI，对 **已存在于 Mongo `context_archive` 的单个 Archive** 重新发布 `context.archive.created` Kafka 事件，用于 STM-006 / STM-010 等路径中 **Archive 已持久化但事件丢失** 的恢复。

可验证交付：

1. **`scripts/republish_archive_event.py`**：受信任环境 CLI；通过 `get_settings()` / 环境变量获取 Mongo 与 Kafka 凭证；**不**暴露 HTTP。
2. **Mongo 只读 lookup**：按 `archive_id` 加载 Archive；从文档取得 `user_id`、`session_id`、`created_time`；**不**写入或修改 Mongo。
3. **Kafka publish 复用 STM-006 Contract**：
   - Topic：`settings.kafka.topic`（默认 `context.archive.created`）
   - Message Key：`user_id`（UTF-8 bytes）
   - Body：**仅**六字段 `event_id`、`event_type`、`archive_id`、`user_id`、`session_id`、`created_time`
   - 构造与发布 **必须** 经 `ArchiveCreatedEvent` + `publish_archive_created_event`；**禁止**手写 JSON 或第二套 publisher。
4. **新 `event_id`**：每次补发生成 UUID v4 新 `event_id`（对齐 §2.1.14 规则 6 与 STM-006 重复发布允许语义）。
5. **at-least-once**：脚本可安全重复执行；每次产生新 `event_id`；**不**声称 exactly-once；**不**检查 extraction task 是否存在。
6. **明确 exit code**、失败日志（含 `archive_id`；**无** secret 泄漏）、单元/脚本级 + Kafka Integration 测试；**无** EXT Consumer 断言。

概念链（本任务止点）：

```text
CLI --archive-id <uuid> [--user-id <id>]
        → Mongo find by archive_id (read-only)
        → validate ownership (optional user_id) + document parse
        → NEW event_id (uuid4)
        → ArchiveCreatedEvent(archive fields + created_time from archive doc)
        → publish_archive_created_event(producer, topic, event)
        → exit 0 / log event_id
        → NO Redis / NO pending mutation / NO Mongo write / NO extraction consumer
```

---

## 3. 非目标（必须坚持；黑名单语义）

- STM-012 补发事件 **消费侧** 验证（Extraction Consumer、任务幂等创建、offset commit）。
- EXT-001 / `memory_extraction_task` 查询、扫描或断言。
- §836 **批量扫描**「不存在对应 `memory_extraction_task` 的 Archive」模式（见 §10.1 OI-STM-011-001；本 MVP 脚本 **仅** 单 `archive_id` 补发）。
- HTTP Endpoint 或 API 包装（OI-007：**仅 CLI**）。
- 修改 `ArchiveCreatedEvent` 六字段 schema；在事件中加入 `archive_batch_key`、`base_compression_version`、`compression_version`。
- Redis Working Memory / compression lock / `pending_archive_*` 读写或变更。
- Mongo Archive create/reuse / 任何写入。
- 独立 Outbox、DLT、自动后台扫描任务、cron。
- 第二套 Kafka producer lifecycle 或手写 `send_and_wait` 绕过 `publish_archive_created_event`。
- 操作 **DEV-006** / **PR #13**。
- 自动 Push / Merge / Rebase / Force Push。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `26f31bdf44e879881c8a160ec3855fab88d4e86e` |
| `git status --short` | clean（规划轮仅允许规划文档 dirty） |
| formal STM-006 | `completed`（PR #25 MERGED） |
| formal STM-005 | `completed`（PR #23 MERGED） |
| `scripts/republish_archive_event.py` | **不存在** |
| `find_context_archive_by_id` | **不存在**（仅有 `find_context_archive_by_batch_key`） |

### 4.2 可复用组件审计

| 交付物 | 路径 | STM-011 用法 |
|---|---|---|
| `ArchiveCreatedEvent` | `domain/models/archive_created_event.py` | **唯一** 事件 body 模型；`to_json_bytes()` 六字段序列化 |
| `publish_archive_created_event` | `infrastructure/kafka/archive_created_publisher.py` | **唯一** publish 入口；key=`user_id` |
| `ContextArchive` / `context_archive_from_document` | `domain/models/context_archive.py` | 解析 Mongo 文档；字段含 `base_compression_version`（**不进 Kafka**） |
| `find_context_archive_by_batch_key` | `infrastructure/mongodb/context_archive_repository.py` | 模式参考；本任务新增 `find_context_archive_by_id` |
| `get_settings` | `settings` | Mongo URI、Kafka bootstrap、topic、producer 参数 |
| `prepare_pending_archive_and_publish` | `compression_preparation_service.py` | **参考** event_id/created_time 模式；**不**调用（含 Redis/Lock 副作用） |
| `scripts/migrate.py` | `scripts/migrate.py` | CLI 模式参考：`argparse`、`logging.basicConfig`、`sys.exit`、最小客户端连接、`asyncio.run` |
| STM-006 Kafka Integration | `tests/integration/test_archive_created_kafka.py` | compose test 栈、producer/consumer fixture 模式复用 |

### 4.3 当前缺失

- `scripts/republish_archive_event.py`
- 可测试的 republish 领域服务（避免 CLI-only 逻辑无法 Unit 覆盖）
- `find_context_archive_by_id` repository 函数
- republish 稳定结果枚举 / Result 模型
- Unit / Contract / Kafka Integration 测试

### 4.4 与技术规格一致性

| 规格要点 | 本任务对齐 |
|---|---|
| §1.2.4 六字段 schema | **严格复用**；禁止扩展字段 |
| §1.2.4 Message Key = `user_id` | 经 `publish_archive_created_event` |
| §1.2.4 发布失败人工补发 | 本脚本即补发工具（单 archive） |
| §836 扫描无 extraction task | **本 MVP 不实现扫描**（OI-STM-011-001）；单 archive 补发满足「人工补发」核心恢复路径 |
| §2.1.14 retry 规则 6 | 新 `event_id` + key=`user_id` + 同 `archive_id`；**不**重建 Archive |
| §335 Archive 不可变 | 脚本只读 Mongo |
| §5665 CLI-only | **无 HTTP**；凭证来自环境变量（OI-007 闭合） |
| `compression_version` | **Redis WM 字段**；**不在** Kafka 事件；脚本 **不使用** |
| `base_compression_version` | **Mongo archive 字段**（§331）；用于 Finalize 校验；**不在** Kafka 事件；脚本 **不读取用于 publish**（仅随 archive 文档存在） |

### 4.5 前置任务检查

| 前置 | 状态 |
|---|---|
| STM-006 | **SATISFIED** |
| STM-005 | **SATISFIED**（Mongo archive 模型与 repository） |
| EXT-001 | **不在依赖**；不得查询 extraction task |
| STM-012 | **OUT OF SCOPE** |
| OI-007 | **open** — 本计划闭合为 CLI-only |
| OI-004 | **open** — 不阻塞（脚本不涉 token 边界） |

---

## 5. 实现方案

### 5.0 八项 Contract 闭合（Planner 权威结论）

#### C1 — CLI 接口（仅 CLI；OI-007）

| 项 | 结论 |
|---|---|
| 入口 | `python scripts/republish_archive_event.py` 或 `python -m scripts.republish_archive_event`（二者实现时择一为主并在脚本 `--help` 说明；推荐 **模块方式** 与 `scripts.migrate` 一致） |
| 必选参数 | `--archive-id <string>`：非空；trim 后不得为空 |
| 可选参数 | `--user-id <string>`：若提供，必须与 Mongo 文档 `user_id` **精确相等**；用于运维误操作防护（对齐 §2.1.14 ownership 精神） |
| 禁止参数 | 扫描模式、`--scan`、`--all`、batch、`--dry-run` 写 Kafka（MVP 无 dry-run 发布到 broker 的歧义需求） |
| 凭证 | **仅** `get_settings()` → 环境变量 / `.env`；**禁止** CLI 传入 secret |
| HTTP | **永久禁止** |

#### C2 — 字段来源与 `compression_version` 澄清

| 字段 | 来源 | 进入 Kafka？ |
|---|---|---|
| `archive_id` | CLI `--archive-id`（必须与 Mongo 文档一致） | 是 |
| `user_id` | Mongo `context_archive.user_id` | 是（且为 Message Key） |
| `session_id` | Mongo `context_archive.session_id` | 是 |
| `created_time` | Mongo `context_archive.created_time`（见 C3） | 是 |
| `event_id` | **新生成** UUID v4 | 是 |
| `event_type` | 常量 `context.archive.created` | 是 |
| `archive_batch_key` | Mongo 有，**不进事件** | **否** |
| `base_compression_version` | Mongo 有（§331），Finalize 用 | **否** |
| `compression_version` | Redis WM 字段（§183），**不在 Mongo archive** | **否** |

脚本 **不得** 读取 Redis 获取 `compression_version`；补发与 WM 版本无关。

#### C3 — `created_time` 语义（OI-STM-011-002）

| 项 | Planner 决议 |
|---|---|
| 取值 | **Mongo `archive.created_time`**（Archive 持久化时间） |
| 理由 | 事件标识同一不可变 Archive；Consumer 按 `archive_id` 查文档；与 Archive 创建时刻一致 |
| 非取值 | 补发时刻 wall clock（STM-006 默认 `now()` 适用于 **首次** pending 后 publish；补发场景 Archive 已存在） |
| 开放项 | 若 Plan Review 要求对齐 §2.1.14「新 event_id」并隐含「新事件时间」，须在 Amendment 中显式改决议 |

#### C4 — Mongo lookup 与校验

| 场景 | 行为 |
|---|---|
| `archive_id` 不存在 | `archive_not_found`；exit **1**；**不** publish |
| 提供 `--user-id` 且 ≠ 文档 `user_id` | `archive_ownership_mismatch`；exit **1**；**不** publish；**不**泄露其他用户 archive 内容 |
| BSON 缺字段 / 畸形 messages | `invalid_archive`；exit **1**；经 `context_archive_from_document` fail-closed |
| `messages` 为空列表 | **仍允许 republish**（数据质量问题留给 Extraction；脚本不实现 §2.1.15 `invalid_archive` 萃取语义） |
| 成功解析 | 继续 publish |

Lookup：**仅**新增 `find_context_archive_by_id(mongodb, archive_id)`；查询 `{"archive_id": archive_id}`；利用 `archive_id` unique index。

#### C5 — Kafka publish（复用 STM-006）

```python
event_id = str(uuid.uuid4())
event = ArchiveCreatedEvent(
    event_id=event_id,
    event_type=ARCHIVE_CREATED_EVENT_TYPE,
    archive_id=archive.archive_id,
    user_id=archive.user_id,
    session_id=archive.session_id,
    created_time=archive.created_time,
)
await publish_archive_created_event(producer, topic, event)
```

| 项 | 结论 |
|---|---|
| Topic | `settings.kafka.topic` |
| Producer | `AIOKafkaProducer` 参数对齐 `runtime.create_app_state` / STM-006 Integration（`acks=all`、`enable_idempotence=True` 等来自 settings） |
| 连接范围 | 脚本 **仅** 连接 Mongo + Kafka；**不** 调用 `create_app_state`（避免 Redis/Neo4j/ES 硬依赖） |
| 成功 | 记录 INFO：`archive_id`、`event_id`；exit **0** |
| 失败 | 记录 ERROR：`archive_id` + exception（`exc_info=True`）；**不** 修改 Mongo/Redis；exit **1** |

#### C6 — at-least-once 与幂等期望

| 项 | 结论 |
|---|---|
| 重复执行脚本 | **允许**；每次新 `event_id` |
| 与首次 STM-006 publish 关系 | 同 `archive_id` 可有多条事件；Consumer 须幂等（STM-012 / EXT） |
| 脚本侧幂等 | **无**「已发布则跳过」检测 |
| Redis pending | **不读不写**；锁过期后 pending 仍可能存在——补发 **不** 依赖锁 |
| exactly-once | **禁止声称** |

#### C7 — Exit codes

| Code | 含义 | 示例 |
|---|---|---|
| **0** | Kafka publish 成功 | 正常补发 |
| **1** | 可恢复/业务失败 | archive not found、ownership mismatch、invalid archive、kafka/mongo 连接失败、publish 异常 |
| **2** | CLI 用法错误 | 缺少 `--archive-id`、空 `archive_id`、未知参数（`argparse` error） |

与 `scripts/migrate.py`（0/1）对齐；**2** 专用于 usage。

#### C8 — 日志与安全

| 项 | 结论 |
|---|---|
| 成功日志 | INFO：`republish succeeded archive_id=... event_id=...` |
| 失败日志 | ERROR：含 `archive_id`；publish 失败 `exc_info=True` |
| Request ID | **不适用**（CLI 无 HTTP request trace） |
| Secret | **禁止** 打印 Mongo URI、Kafka 凭证、完整 settings |
| 消息 body | **禁止** 日志打印完整 messages 内容（仅 archive 元数据） |

---

### Step 1 — Repository：`find_context_archive_by_id`

- **文件**：`src/memory_system/infrastructure/mongodb/context_archive_repository.py`
- **函数**：`async def find_context_archive_by_id(mongodb, archive_id: str) -> ContextArchive | None`
- **输入**：非空 `archive_id`
- **输出**：`ContextArchive` 或 `None`
- **错误处理**：`context_archive_from_document` 抛 `ValueError` 时由上层转为 `invalid_archive`
- **幂等/并发**：只读；无事务要求

### Step 2 — 领域服务：`republish_archive_created_event`

- **文件**：`src/memory_system/domain/services/archive_event_republish_service.py`（新建）
- **枚举**：`ArchiveEventRepublishStatus` — `success` / `archive_not_found` / `archive_ownership_mismatch` / `invalid_archive` / `kafka_publish_failed` / `invalid_input`
- **模型**：`ArchiveEventRepublishInput(archive_id, expected_user_id: str | None)`、`ArchiveEventRepublishResult(status, event_id: str | None)`
- **函数**：

```python
async def republish_archive_created_event(
    *,
    mongodb: AsyncMongoClient,
    kafka_producer: KafkaProducerLike,
    topic: str,
    input: ArchiveEventRepublishInput,
    logger: logging.Logger | None = None,
) -> ArchiveEventRepublishResult
```

- **流程**：
  1. 校验 `archive_id` 非空 → 否则 `invalid_input`
  2. `find_context_archive_by_id`
  3. None → `archive_not_found`
  4. `expected_user_id` 提供且不匹配 → `archive_ownership_mismatch`
  5. 构造 `ArchiveCreatedEvent`（C3/C5）
  6. `publish_archive_created_event`；异常 → `kafka_publish_failed`
  7. 成功 → `success` + `event_id`
- **禁止**：import Redis、compression lock、pending Lua、`prepare_pending_archive_and_publish`

### Step 3 — CLI：`scripts/republish_archive_event.py`

- **文件**：`scripts/republish_archive_event.py`
- **模式**：参考 `scripts/migrate.py`
  - `argparse`：`--archive-id`（required）、`--user-id`（optional）
  - `logging.basicConfig` → stderr
  - `settings = get_settings()`
  - `AsyncMongoClient` + `AIOKafkaProducer`（settings 参数）
  - `asyncio.run(_async_main())`
  - 映射 `ArchiveEventRepublishStatus` → exit code（C7）
- **main 返回值**：`int`；`if __name__ == "__main__": sys.exit(main())`

### Step 4 — 测试（与实现同步；见 §8）

- Unit：mock Mongo + mock producer
- Script：subprocess 或 `main([...])` 测 exit code
- Integration：compose Kafka + Mongo seed archive + consume 验证 payload

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `scripts/republish_archive_event.py` | 创建 | CLI 入口；Mongo+Kafka 接线；exit codes |
| `src/memory_system/domain/services/archive_event_republish_service.py` | 创建 | 可测试 republish 核心逻辑 |
| `src/memory_system/domain/enums/archive_event_republish.py` | 创建 | `ArchiveEventRepublishStatus` 稳定枚举 |
| `src/memory_system/domain/models/archive_event_republish.py` | 创建 | Input/Result 模型 |
| `src/memory_system/infrastructure/mongodb/context_archive_repository.py` | 修改 | `find_context_archive_by_id` |
| `tests/unit/test_archive_event_republish_service.py` | 创建 | 服务层 Unit |
| `tests/unit/test_republish_archive_event_script.py` | 创建 | CLI / exit code Unit |
| `tests/contract/test_stm011_contract.py` | 创建 | 枚举字面量 + 六字段契约稳定 |
| `tests/integration/test_republish_archive_event_kafka.py` | 创建 | Mongo seed + Kafka publish + consume |

**实施白名单（精确路径；禁止通配）：**

- 上表全部路径
- `02_开发管理/progress.md`（`docs(status): record` 轮，Release Operator）
- `02_开发管理/master_plan.md`（`docs(status): record` 轮，Release Operator）

**永久禁止触碰（实施阶段）：**

- `src/memory_system/domain/models/archive_created_event.py`（除非规格缺陷 HALT）
- `src/memory_system/infrastructure/kafka/archive_created_publisher.py`（除非规格缺陷 HALT）
- `src/memory_system/domain/services/compression_preparation_service.py`
- `api/**`、`EXT-001/**`、extraction consumer、STM-012 测试
- `DEV-006` / PR #13 路径

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | **不适用**（单读 + 单 Kafka send；无跨存储事务） | Mongo 只读；Kafka 独立；失败不产生 Mongo 副作用 |
| 幂等 | **适用（at-least-once）** | 每次新 `event_id`；可重复补发；Consumer 侧幂等不在本任务 |
| 并发 | **不适用** | 无共享可变状态；并发 CLI 对同 archive 仅产生多条事件 |
| 版本冲突 | **不适用** | 不读 `compression_version` / `base_compression_version` 做 publish 决策 |
| 用户隔离 | **适用** | 可选 `--user-id` 校验；mismatch fail-closed |
| 部分失败 | **适用** | Kafka 失败 → exit 1；Mongo 不变；无 partial publish 状态 |
| 进程异常恢复 | **适用** | 脚本无状态；重跑即可；不确定 ack 按 at-least-once 由 Consumer 处理 |

---

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| U1 空/空白 `archive_id` | `invalid_input`；脚本 exit 2 |
| U2 缺少 CLI `--archive-id` | exit 2 |
| U3 Mongo 无文档 | `archive_not_found`；exit 1；producer 未调用 |
| U4 `--user-id` 与文档不匹配 | `archive_ownership_mismatch`；exit 1 |
| U5 畸形 BSON（缺 `session_id`） | `invalid_archive`；exit 1 |
| U6 成功路径 | `success`；`event_id` 非空；producer `send_and_wait` 被 await 一次 |
| U7 payload 精确性 | mock 捕获 value：恰好六字段；无 `base_compression_version`；key=user_id bytes |
| U8 `created_time` 来自 archive | payload `created_time == archive.created_time` |
| U9 注入 publish 异常 | `kafka_publish_failed`；exit 1 |
| U10 重复调用 | 两次 `event_id` 不同；均 `success` |

### Contract Test

| 场景 | 预期 |
|---|---|
| CT1 `ArchiveEventRepublishStatus` 字面量稳定 | 与 Task Plan 枚举一致 |
| CT2 复用 `ARCHIVE_CREATED_EVENT_FIELD_NAMES` | republish payload keys 集合相等 |
| CT3 `event_type` 常量 | `context.archive.created` |

### Integration Test

| 场景 | 预期 |
|---|---|
| I1 Mongo insert archive + 脚本/服务 republish | Kafka consumer 收到消息；六字段；key=user_id |
| I2 archive 不存在 | exit 1；topic 无新消息（或 consumer 超时） |
| I3 ownership mismatch | exit 1；无消息 |
| I4 注入 broker 失败（mock/patch `send_and_wait`） | exit 1；Mongo 文档不变 |

**Integration 栈**：复用 `test_archive_created_kafka.py` compose fixture 模式（test Redis **不需要**；仅需 Mongo + Kafka）。Mongo 可用 `insert_context_archive` + `archive_document_from_input` 或直接向 collection insert。

### E2E Test

| 场景 | 预期 |
|---|---|
| — | **不适用**（STM-013 已 completed；本任务不要求全链路 E2E） |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| F1 Kafka `send_and_wait` RuntimeError | exit 1；ERROR 日志含 archive_id |
| F2 并发两次 subprocess 同 archive_id | 均 exit 0；两条消息；不同 event_id |
| F3 **无** EXT consumer 断言 | 测试 **不得** import extraction worker 或查 `memory_extraction_task` |

### 测试命令（验收）

```bash
uv run pytest tests/unit/test_archive_event_republish_service.py tests/unit/test_republish_archive_event_script.py -q
uv run pytest tests/contract/test_stm011_contract.py -q
uv run pytest tests/integration/test_republish_archive_event_kafka.py -q
uv run ruff check .
uv run mypy src tests scripts
```

---

## 9. 验收标准

- [ ] `scripts/republish_archive_event.py` 存在且 **仅 CLI**（OI-007）
- [ ] `--archive-id` 必选；`--user-id` 可选 ownership 校验
- [ ] Mongo 只读；`user_id`/`session_id`/`created_time` 来自 archive 文档；**不使用** `compression_version`；Kafka **不含** `base_compression_version`
- [ ] 每次补发 **新** `event_id`（UUID v4）；topic/key/payload 经 `ArchiveCreatedEvent` + `publish_archive_created_event`
- [ ] exit 0/1/2 行为与 §5.0 C7 一致
- [ ] 失败日志含 `archive_id`；无 secret 泄漏
- [ ] §8 全部 scoped 测试 PASS
- [ ] 全量 `uv run pytest tests/unit -q` / `tests/contract -q` 无回归
- [ ] Ruff / Mypy PASS
- [ ] Review 无 P0/P1
- [ ] **无** EXT-001 依赖；**无** STM-012 消费断言

---

## 10. 风险与阻塞项

### 10.1 Open Issues（Planner 登记；fail-closed）

#### OI-STM-011-001 — §836 扫描 vs 单 archive CLI

| 项 | 内容 |
|---|---|
| 规格 | §836 要求扫描无 `memory_extraction_task` 的 Archive 并补发 |
| 本任务范围 | **仅** `--archive-id` 单条补发 |
| 理由 | 用户 Explicit Non-Goals：无 EXT-001；扫描依赖 extraction task 集合 |
| 风险 | 与 §836 字面「扫描」不完全一致 |
| 处置 | MVP 交付单条 CLI；运维可脚本化多次调用；批量扫描 **后续任务** 或规格修订；**不得** 在本任务偷偷查 extraction collection |
| blocks | **否**（Orchestrator 与用户 Explicit Scope 已收窄） |

#### OI-STM-011-002 — 补发 `created_time` 取值

| 项 | 内容 |
|---|---|
| 规格 | §2.1.14 规则 6 仅规定新 `event_id`；未规定 `created_time` |
| Planner 决议 | 使用 Mongo `archive.created_time`（§5.0 C3） |
| 备选 | 补发时刻 wall clock |
| blocks | **否**（Plan Review 可 Amendment） |

#### OI-007 — CLI-only（闭合）

| 项 | 内容 |
|---|---|
| 决议 | **仅 CLI**；不增加 HTTP republish |
| 状态 | 本计划闭合；实施不得添加 REST |

### 10.2 其他风险

| 风险 | 级别 | 缓解 |
|---|---|---|
| 重复事件导致重复萃取 | 低 | at-least-once 规格语义；STM-012 验证 Consumer 幂等 |
| 脚本误补发错误 archive | 中 | 可选 `--user-id`；运维规程 |
| `create_app_state` 强依赖全栈 | 低 | 脚本最小化连接，仅 Mongo+Kafka |
| 规格要求必须扫描模式 | 中 | HALT 并报告；不擅自实现 EXT 查询 |

- **设计文档冲突**：§836 扫描 — 见 OI-STM-011-001；按 Explicit Scope 收窄。
- **当前代码冲突**：无。
- **前置任务**：STM-006 **SATISFIED**。
- **未批准依赖**：无。
- **API/Schema 变化**：无（六字段不变）。

---

## 11. Git 计划

```yaml
branch: "feat/STM-011-republish-archive-event"
workflow_mode: NORMAL
RELEASE_PHASE: IMPLEMENTATION_RELEASE
expected_commits:
  - "docs(plan): add STM-011 republish archive event plan"
  - "feat(stm): add republish_archive_event CLI and service"
  - "test(stm): add STM-011 republish unit contract and kafka integration"
out_of_scope_changes:
  - "STM-012 / EXT-001 / extraction consumer"
  - "compression_preparation_service / Redis pending / lock"
  - "archive_created_event six-field schema changes"
  - "HTTP republish endpoint"
  - "DEV-006 / PR #13"
  - "master_plan.md / progress.md 以外的治理文档（plan landing 已写 plan）"
```

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
| 2026-08-11 19:55 UTC | Step 1-4 implement + test | 9 whitelist files | unit 16 / contract 3 / integration 5 PASS; ruff+mypy PASS | none |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `scripts/republish_archive_event.py` | created |
| `src/memory_system/domain/services/archive_event_republish_service.py` | created |
| `src/memory_system/domain/enums/archive_event_republish.py` | created |
| `src/memory_system/domain/models/archive_event_republish.py` | created |
| `src/memory_system/infrastructure/mongodb/context_archive_repository.py` | modified |
| `tests/unit/test_archive_event_republish_service.py` | created |
| `tests/unit/test_republish_archive_event_script.py` | created |
| `tests/contract/test_stm011_contract.py` | created |
| `tests/integration/test_republish_archive_event_kafka.py` | created |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit/test_archive_event_republish_service.py tests/unit/test_republish_archive_event_script.py -q` | PASS (16) |
| Contract | `uv run pytest tests/contract/test_stm011_contract.py -q` | PASS (3) |
| Integration | `uv run pytest tests/integration/test_republish_archive_event_kafka.py -q` | PASS (5) |
| Ruff | `uv run ruff check .` | PASS |
| Mypy | `uv run mypy src tests scripts` | PASS |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 2
p3: 3
review_report: null
```

### Git 记录

```yaml
branch: feat/STM-011-republish-archive-event
plan_commit: 68cee46011f011f3074662f846c64da670741cb3
implementation_commit: 23939a3f3d25f5243978e967949beb4fe6282e2f
implementation_commit_message: "feat(stm): add republish_archive_event CLI and service"
```

### 最终状态

`committed`
