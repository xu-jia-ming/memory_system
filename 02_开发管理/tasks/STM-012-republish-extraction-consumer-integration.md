# STM-012 Republish Archive Event → Extraction Consumer Integration Verification

## 1. 任务信息

```yaml
task_id: STM-012
task_name: Republish Archive Event → Extraction Consumer Integration Verification
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
plan_review_round: 3
spec_sections:
  - "§1.2.4 Kafka Event 设计（topic / six-field schema / Message Key=user_id / consumer group / at-least-once）"
  - "§2.1.1 记忆萃取整体流程（Create or Load Task → Commit Offset）"
  - "§2.1.3 Memory Extraction Task 数据库设计（schema / archive_id unique）"
  - "§2.1.4 Kafka 消费与任务幂等（Upsert / duplicate / Offset gate）"
  - "§2.1.5 仅作为边界说明；本任务不实现 Archive 读取与预处理"
  - "§3.4 Kafka Producer / artificial republish CLI"
  - "§3.6 AIOKafkaConsumer manual commit"
  - "§3.19 Kafka Topic and client parameters"
  - "§3.20 MongoDB unique index and atomic updates"
  - "§3.32 Integration/E2E verification boundary"
prerequisites:
  formal:
    - "STM-011 — SATISFIED/completed; PR #33 MERGED; baseline implementation includes CLI/service republish"
    - "EXT-001 — SATISFIED/completed; PR #34 MERGED; baseline implementation includes consumer, task upsert, and manual offset"
  baseline_main_sha: "d6e7941eeaa2a8409b09eaf181d2924eb3865138"
branch: "feat/STM-012-republish-extraction-consumer-integration"
created_at: "2026-08-11 14:11 UTC"
updated_at: "2026-08-11 15:10 UTC"
human_plan_approved: true
approval_gates:
  plan_review: "Round 3 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0 SHOULD_FIX=3）；MF-001 CLOSED"
  human_plan_approval: "granted 2026-08-11T14:55:45Z"
  implementation_review: "required; no P0/P1"
release_phase: "IMPLEMENTATION_RELEASE"
```

## 2. 任务目标

在不改变 STM-011 或 EXT-001 Contract 的前提下，用真实 MongoDB、Kafka 和 STM-011 CLI 验证补发事件可以被 EXT-001 的真实 Kafka consumer adapter 消费，并为同一 `archive_id` 只创建一个 Extraction Task。

可验证结果：

1. 为 Mongo 中的固定测试 Archive 执行第一次 `python -m scripts.republish_archive_event --archive-id ...`，真实消息进入 `context.archive.created`。
2. EXT-001 consumer 从真实 Kafka 消费该消息，使用测试专用 `ExtractionPipelinePort` Fake 产生合法 terminal decision，Mongo 中出现一条完整任务。
3. 对同一 Archive 再次执行 CLI：消息具有新的 `event_id`、相同 `archive_id`，仍使用 `user_id` key 和精确六字段；consumer 再次处理后任务数量仍为一条，已有任务状态和业务字段不被覆盖，Fake 不被重复调用。
4. 仅证明与本链路相关的 manual offset：每条合法记录在 terminal Mongo 写成功后提交 `offset + 1`；不把 Mongo 和 Kafka 宣称为跨系统原子事务。

## 3. 非目标

- 不修改 `scripts/republish_archive_event.py`、`archive_event_republish_service`、`ArchiveCreatedEvent`、Kafka producer 或 EXT-001 consumer/repository/service。
- 不修改 `memory_extraction_task` Schema、唯一索引、状态机、六字段事件 Contract、topic、key、consumer group、offset 语义或错误码。
- 不实现 EXT-002 Archive 读取/预处理/脱敏，不实现 EXT-003+ 的 LLM、Neo4j、Elasticsearch、重试 API 或管理 HTTP。
- 不要求或启动真实 production extraction worker；`src/memory_system/entrypoints/extraction_worker.py` 继续按 EXT-001 约定以非零码拒绝启动，避免伪造已完成的生产 Pipeline。
- 不触碰 DEV-006、PR #13、STM-011/EXT-001 既有测试语义、Migration 正文或任何生产代码。
- 不验证 malformed/key-mismatch 的完整矩阵；该边界已由 EXT-001 Integration suite 覆盖，本任务只验证由 STM-011 产生的合法事件。
- 不声称 exactly-once Kafka delivery、全链路 Extraction 完成或 Neo4j/ES 门禁已满足。

## 4. 当前代码状态

- 已存在代码：
  - STM-011 `scripts/republish_archive_event.py`：从 Settings 连接 Mongo/Kafka，调用 republish service，成功返回 0，失败按既有 1/2 语义退出。
  - STM-011 `archive_event_republish_service`：只读加载 Archive，生成新的 UUID v4 `event_id`，保持 Archive 的 `archive_id/user_id/session_id/created_time`，通过既有 publisher 发布。
  - `ArchiveCreatedEvent`：生产序列化的唯一六字段为 `event_id,event_type,archive_id,user_id,session_id,created_time`。
  - EXT-001 `create_archive_created_consumer` / `run_archive_created_consumer_loop` / `process_consumer_record`：`enable_auto_commit=false`、`max_poll_records=1`、边界校验、archive_id upsert、terminal 后 manual commit。
  - EXT-001 Mongo repository：`$setOnInsert`，`archive_id` unique，重复事件不覆盖已有 task。
  - `ExtractionPipelinePort`：仅为可注入协议，完整生产 stages 属 EXT-002+。
  - `extraction_worker.main()`：当前明确拒绝启动生产 poll loop，exit 1。
- 可复用组件：
  - STM-011/EXT-001 已有 compose test stack fixture 模式、Mongo migration/bootstrap、Kafka topic bootstrap、container-IP 连接适配及清理逻辑。
  - EXT-001 integration helpers 可复用 consumer factory、真实 loop、offset 查询和 `FakeCompletePipeline` 的行为模式，但 STM-012 新测试必须只断言本任务目标。
- 当前缺失：
  - 一条同时调用 STM-011 CLI、真实 Kafka record、EXT-001 consumer loop 和 Mongo task 查询的跨任务 Integration/E2E 测试。
- 与技术规格不一致之处：
  - 未发现需要修复的生产 Contract。生产 worker 未就绪是 EXT-002+ 的明确边界，不是本任务缺陷；如实现过程中必须修改 `src/**` 或生产 worker 才能通过，立即 HALT 并报告，不得补丁式实现。
- 前置任务检查：
  - 当前只读检查：branch `main`；HEAD `d6e7941eeaa2a8409b09eaf181d2924eb3865138`；无 Git 写操作。
  - STM-011 completed（implementation merged `19fdb55`）；EXT-001 completed（implementation merged `ae346dd`）；两者 SATISFIED。
  - DEV-006/PR #13 disposition 不变，不触碰。

## 5. 实现方案

### Step 1 — 建立隔离的真实基础设施和测试夹具

- 文件：`tests/integration/test_stm012_republish_extraction_consumer_integration.py`（新建）。
- 夹具：复用 `scripts/compose.sh --stack=test --embedding=none` 启动 MongoDB 与 Kafka；确认 test project isolation；执行既有 init-infra；确保 `context.archive.created` topic；使用随机 user/archive/session 标识并在前后清理 `context_archive` 与 `memory_extraction_task`。
- 输入：测试 Mongo URI、Kafka bootstrap、固定 Archive fixture（含合法 messages/created_time）。
- 宿主 endpoint 策略：沿用现有 `tests/integration/test_extraction_consumer_kafka.py` / `test_republish_archive_event_kafka.py` 约定，通过 `docker inspect -f "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}" memory-system-mongodb-test` 与同样方式取得 `mongo_ip`、`kafka_ip`；测试进程和 CLI subprocess 使用 `mongodb://<mongo_ip>:27017/memory_system` 与 `<kafka_ip>:9092`。这些是 test compose 容器 IP 的宿主可达 endpoint，明确覆盖 `.env.example` 的 Docker 内部 `mongodb:27017` / `kafka:9092`，不是生产 Settings 默认值。
- CLI subprocess 环境：按 Amendment 002 构造显式 sanitized allowlist，绝不从 fixture 环境副本或 `os.environ.copy()` 派生；仅含 `PATH`、`PYTHONPATH`、精确 `_REQUIRED_ENV_KEYS` 全集及 `KAFKA__TOPIC`。显式固定 `APP_ENV=test`、`MONGODB__URI=mongodb://<mongo_ip>:27017/memory_system`、`KAFKA__BOOTSTRAP_SERVERS=<kafka_ip>:9092`、`KAFKA__TOPIC=context.archive.created`、`PROXY__HTTP_URL=""`、`EMBEDDING_EFFECTIVE_RUNTIME_MODE=cpu`、`EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET=4096`；其余 required Settings keys 使用非机密 test placeholders，禁止注入或提交真实凭证。`KAFKA__TOPIC` 与 topic bootstrap 均固定为已有 test topic。
- 输出：可从宿主 Python 测试和 CLI subprocess 连接真实 Mongo/Kafka 的隔离环境。
- 错误处理：Docker/服务未就绪时仅按现有 integration convention skip；配置隔离无法确认时不得连接非 test stack；测试断言失败不得降级或吞掉。
- 幂等/并发/事务要求：fixture 不改变业务数据 Contract；每个测试使用唯一 archive_id 和 test-only consumer group；不把 fixture 清理误当业务事务。

### Step 2 — 以 CLI 为主路径验证第一次补发

- 文件：同上；不修改 CLI/service。
- 调用：从 repository root 固定使用显式脚本路径命令 `python scripts/republish_archive_event.py --archive-id <archive_id> --user-id <user_id>`（不使用隐式 module/path resolution），并传入 Amendment 002 的 sanitized allowlisted subprocess environment、`cwd=REPO_ROOT`、finite timeout、captured stdout/stderr；断言 exit code 为 0 且诊断不含 secrets。第二次调用使用完全相同命令参数。
- 记录发现：使用临时、唯一的 raw-reader group 按 `archive_id` 过滤，取得真实 record 的 partition/offset/payload；断言 payload 的 key 和内容，而不依赖日志格式解析。该 raw-reader group 仅用于发现 record，不替代 EXT-001 consumer group。
- Contract 断言：topic 为 `context.archive.created`；message key 等于 `user_id.encode("utf-8")`；payload keys 集合精确等于六字段；`event_type`、`archive_id`、`user_id`、`session_id`、`created_time` 与 Archive 一致；`event_id` 为非空 UUID v4。
- 输出：第一条真实 republish record 的 `event_id`、partition、offset，供下一步把 consumer 定位到该 record。

### Step 3 — 以 EXT-001 consumer adapter 消费并验证首个 task

- 文件：同上；调用既有 `create_archive_created_consumer`、`run_archive_created_consumer_loop`，将 consumer assign/seek 到 Step 2 的精确 partition/offset。
- Consumer group：EXT-001 factory 支持显式 `group_id` 参数；测试传入唯一 test-only 值 `memory-extraction-group-stm012-<uuid>`，并在两次消费中复用该值，避免污染其他测试。生产默认 `MEMORY_EXTRACTION_CONSUMER_GROUP` 仍是规格字面量 `memory-extraction-group`，不修改生产 Settings、默认值或 Contract。
- `ExtractionPipelinePort` handling：注入测试专用 `CompleteForBoundaryPipeline`，只记录调用次数和收到的 `task.archive_id/event.archive_id`，返回 `PipelineTerminalDecision.complete()`；不得读取 Archive、生成 extraction_result、调用 LLM/Neo4j/ES、添加 production fallback 或表达 EXT-002 语义。它只证明 EXT-001 的 task/offset 边界可被驱动。
- 断言：处理一条记录；Fake 恰好调用一次；Mongo 仅一条 `memory_extraction_task`；task `archive_id/user_id` 正确，`status=completed`，`attempt_count=1`，合法 `task_id`，时间字段符合固定 clock，`session_id/event_id` 不被发明为 task 顶层字段。只在确认该 record 的 terminal Mongo task 已存在后，读取同一 test consumer group 的 committed offset 并断言为该 record offset + 1；这只证明该合法 event 已消费、terminal Mongo state 已存在且该 record 的 commit 已完成，不证明 Mongo/Kafka 原子性或 exactly-once。
- 失败处理：若 terminal Mongo 写失败，测试不得转为成功或跳过；本 Step 只验证正常合法路径，EXT-001 已有 dedicated failure suite。

### Step 4 — 重复补发验证新 event_id、archive_id 幂等和非破坏性

- 文件：同上。
- 调用：对完全相同 `archive_id` 再运行一次精确命令 `python scripts/republish_archive_event.py --archive-id <archive_id> --user-id <user_id>`，使用相同 sanitized env/cwd/timeout/capture，exit code 必须为 0；从真实 Kafka 取得第二条匹配 record。
- Contract 断言：第二条 `event_id != first_event_id`，`archive_id` 相同，`user_id` key 相同，仍是精确六字段；不得以 event_id 作为 task 幂等键。
- 消费：用同一 `memory-extraction-group-stm012-<uuid>` test consumer group 将第二条 record 定位消费；注入新的 Fake 并断言其 `run` 次数为 0，因为第一条已完成且 EXT-001 completed 分支应直接 commit。
- Mongo 断言：`archive_id` count 仍为 1；保存第一次 task 的完整 document 快照，第二次后 `task_id`、`archive_id`、`user_id`、`status`、`attempt_count`、`created_time`、`updated_time`、`completed_time`、`last_error`、`extraction_result` 均不发生非 Contract 允许的覆盖；不新增 `session_id/event_id`。
- Offset：只在第二条已有 terminal task state 保持不变后断言第二条合法 record 的 offset 被手动提交；这只证明第二条 valid event 的消费和该 record commit，不要求或宣称跨记录、Mongo/Kafka 原子性。

### Step 5 — 收敛验证、记录结果和门禁

- 运行 established command `uv run pytest -q tests/integration/test_stm012_republish_extraction_consumer_integration.py -m integration`（`integration` marker 已在 `pyproject.toml` 注册），以及相关 Ruff/Mypy；只在上述白名单内修改。
- 任何生产变更、Contract 变化、需要 EXT-002 才能通过、无法隔离 test stack、或与权威规格冲突，均 HALT 并报告，不自行扩大范围。
- 实现完成后更新本计划执行记录和 progress.md；Plan Review/Developer/Code Review/Commit Recorder/Release Operator 依次按治理门禁执行，本 Planner 不执行 Git 写。

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `02_开发管理/tasks/STM-012-republish-extraction-consumer-integration.md` | 创建（Round 1）/追加 Amendment 001 与后续执行记录 | STM-012 权威 Task Plan |
| `tests/integration/test_stm012_republish_extraction_consumer_integration.py` | 计划创建（实现阶段） | CLI→Kafka→EXT-001 consumer→Mongo 的真实 Integration/E2E 验证 |
| `02_开发管理/progress.md` | 本轮修改规划态；实现后追加状态记录 | current task / plan / next action |
| `02_开发管理/master_plan.md` | 本轮修改 STM-012 登记字段 | 计划文件、范围、门禁和规划状态 |
| `src/**` | **NONE** | 明确 production delta NONE |
| `scripts/republish_archive_event.py` | **NONE** | STM-011 语义冻结 |
| `DEV-006 / PR #13` | **NONE** | 强制隔离 |

Exact implementation whitelist:

```yaml
allowed_paths:
  - "tests/integration/test_stm012_republish_extraction_consumer_integration.py"
  - "02_开发管理/tasks/STM-012-republish-extraction-consumer-integration.md"
  - "02_开发管理/progress.md"
  - "02_开发管理/master_plan.md"
production_delta: NONE
forbidden_paths:
  - "src/**"
  - "scripts/republish_archive_event.py"
  - "src/memory_system/domain/services/archive_event_republish_service.py"
  - "src/memory_system/domain/models/archive_created_event.py"
  - "02_开发管理/tasks/STM-011-republish-archive-event.md"
  - "02_开发管理/tasks/EXT-001-task-schema-kafka-consumer-idempotency-offset.md"
  - "DEV-006/**"
```

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | Mongo upsert/terminal write 与 Kafka offset commit 非跨系统原子事务 | 只验证 EXT-001 既有门禁：terminal Mongo 成功后才 commit；不声称 exactly-once |
| 幂等 | **适用且核心**；`archive_id` 是权威幂等键，event_id 每次补发不同 | 先后两条真实事件各消费一次，Mongo unique + `$setOnInsert` 使 count=1、completed 早退且 Fake 不再运行 |
| 并发 | 本任务不新增并发 Contract；STM-011 已有并发 republish 覆盖，EXT-001 已有串行 Partition/duplicate 覆盖 | 不加入并发断言，除非 Plan Review 依据规格要求；避免把重复验证膨胀为新并发语义 |
| 版本冲突 | 不适用；STM-012 不修改 task 状态版本或 Archive 版本 | 仅保存/比较重复前后的既有 task 字段 |
| 用户隔离 | **适用**；Archive 的 `user_id` 是 Kafka key 与任务 user_id 来源 | 随机用户 fixture；断言 key 精确匹配且 task.user_id 正确，不跨用户复用 archive |
| 部分失败 | 本任务主路径不注入生产失败；malformed/key mismatch 与 DB failure 由 EXT-001 专 suite 覆盖 | 不重复实现；若基础设施失败则 fail/skip 按 integration harness 规则，不改业务断言 |
| 进程异常恢复 | 仅验证合法 record 已有 terminal task 后该 record 的 manual commit proof；完整 crash/replay 已由 EXT-001 覆盖 | 不启动未就绪 production worker；不声称 STM-012 覆盖 crash recovery |

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 无新增 Unit 业务代码 | 不创建 Unit 测试；STM-011/EXT-001 Unit 已覆盖各自组件语义 |

### Contract Test

| 场景 | 预期 |
|---|---|
| 真实 CLI record 的 topic/key/payload | 仅验证 `context.archive.created`、key=`user_id`、精确六字段和 Archive 值一致 |
| 两次同 archive 的 event identity | 两个 `event_id` 非空且不同；`archive_id` 相同；不将 event_id 落入 task |
| malformed/key-mismatch | 本任务不复制 EXT-001 suite；保留其既有测试作为回归前置 |

### Integration Test

| 场景 | 预期 |
|---|---|
| Mongo fixture → STM-011 CLI → real Kafka → EXT-001 consumer → Mongo | exit 0；真实 record 被处理；一条 completed task |
| First task fields | `archive_id/user_id/status/attempt_count/times/task_id` 符合 EXT-001 schema；不出现 session_id/event_id 顶层字段 |
| Repeat same archive | 第二次新 event_id/同 archive_id；task count=1；已有 task 全字段非破坏性保持；第二 Fake calls=0 |
| Manual offset proof | 确认合法 event 已消费且 terminal Mongo task state 已存在后，该 record 的 committed offset 为 record offset+1；仅证明该 record 的 commit，不证明 Mongo/Kafka atomicity |
| Consumer group/config | 使用 EXT-001 factory 显式注入唯一 test group `memory-extraction-group-stm012-<uuid>`；生产默认仍为 `memory-extraction-group`；`enable_auto_commit=false`、`max_poll_records=1` 不变 |

### E2E Test

| 场景 | 预期 |
|---|---|
| Operational republish-to-consume vertical slice | 从 repository root 执行 `python scripts/republish_archive_event.py --archive-id <id> --user-id <id>`（sanitized allowlisted env、finite timeout、captured stdout/stderr）是发布入口，真实 Kafka 与 EXT-001 library consumer 是消费入口，Mongo task 是最终可观测结果 |
| Production worker | 不执行；其 main() 仍因 EXT-002+ 未就绪退出非零，不能作为 STM-012 通过条件 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| malformed payload / wrong Kafka key | 不新增；EXT-001 已有 fail-closed/no task/no commit 测试，避免重复语义 |
| Kafka/Mongo unavailable | 由 fixture readiness/skip 或测试失败暴露；不得伪造成功 |
| concurrent republish | 不新增；STM-011 已有 distinct event_id coverage，STM-012 目标是 sequential consumer integration |

## 9. 验收标准

- [ ] 在 baseline main 上仅存在本计划允许的规划文件变更；实施前已收到 PLAN_APPROVED 和 human approval。
- [ ] Scoped real-infrastructure test 使用真实 Mongo、真实 Kafka、真实 STM-011 CLI 和 EXT-001 consumer adapter；不修改 `src/**`，production delta 为 NONE。
- [ ] 第一次补发成功，topic/key/精确六字段和 Archive-authoritative `archive_id/user_id/session_id/created_time` 全部断言通过。
- [ ] 第一次消费创建且仅创建一个合法 `memory_extraction_task`，字段/状态/attempt_count 可客观验证，Fake 只调用一次。
- [ ] 第二次同 archive 补发得到新 event_id/同 archive_id；消费后任务数量仍为一条，原 task 非破坏性保持，第二 Fake 调用为 0。
- [ ] 两次合法 record 的 manual offset 均为 offset+1；不声称 exactly-once 或全链路 Extraction 完成。
- [ ] malformed/key-mismatch 不重复实现，EXT-001 既有 fail-closed scoped suite 仍通过。
- [ ] `uv run pytest -q tests/integration/test_stm012_republish_extraction_consumer_integration.py -m integration` 通过（或按环境明确 skip，不能静默跳过）；相关 Ruff、Mypy 通过；Review 无 P0/P1。
- [ ] 不触碰 DEV-006/PR #13、STM-011/EXT-001 语义及生产文件。

## 10. 风险与阻塞项

- 设计文档冲突：当前未发现。若测试需要修改六字段、task schema、status、key、offset 或生产 worker，立即 HALT。
- 当前代码冲突：`extraction_worker.main()` 按 EXT-001 明确未就绪；不能用它证明本任务，改用已实现的 library consumer adapter + test-only Port。
- 前置任务：STM-011、EXT-001 已 SATISFIED；若当前 HEAD 不再是指定 baseline 或前置状态被撤销，停止。
- 未批准依赖：无新增依赖；Docker、Mongo、Kafka 为现有 test compose 依赖。
- API/Schema 变化：NONE；不新增 HTTP Endpoint、task 字段、consumer settings 或 migration。
- 其他风险：
  - CLI subprocess 必须使用精确脚本路径和 Step 1 显式 test-only env；`<mongo_ip>:27017` / `<kafka_ip>:9092` 覆盖 Docker 内部 `mongo`/`kafka` 名称，不得使用生产 `.env` endpoint；这些 overrides 不提交且不含真实 Secret。
  - Kafka 中可能有其他测试记录；必须按 archive_id 过滤并使用 partition/offset 精确定位，不能仅取“第一条消息”。
  - offset 是异步可观察状态；使用有界轮询读取 committed offset，超时即失败，不放宽断言。
  - test-only Fake 若读取 Archive、写入 extraction_result 或假设 EXT-002 规则即越界；Plan Review 应拒绝此类实现。
- Open Issues:
  - OI-STM-011-001 的批量扫描工具不在 STM-011，STM-012 也不扩展为扫描；本任务只验证单 archive CLI 的真实链路。
  - 是否由后续任务接入 production extraction worker 仍由 EXT-002+ 规格决定；STM-012 不预决策。
  - 不引入规格未定义的“消费成功” API 或跨系统事务 Contract。

## 11. Git 计划

```yaml
workflow_mode: NORMAL
baseline_main_sha: "d6e7941eeaa2a8409b09eaf181d2924eb3865138"
plan_review_gate:
  - "PLAN_REVIEWER 输出 PLAN_APPROVED"
  - "Human PLAN_APPROVED"
  - "仅批准后进入 Developer"
release_phase: IMPLEMENTATION_RELEASE
branch: "feat/STM-012-republish-extraction-consumer-integration"
expected_commits:
  - "docs(plan): add STM-012 republish extraction consumer integration plan"
  - "test(integration): verify republish event extraction consumer idempotency"
allowed_git_paths:
  - "tests/integration/test_stm012_republish_extraction_consumer_integration.py"
  - "02_开发管理/tasks/STM-012-republish-extraction-consumer-integration.md"
  - "02_开发管理/progress.md"
  - "02_开发管理/master_plan.md"
out_of_scope_changes:
  - "任何 src/** production change"
  - "STM-011/EXT-001 implementation or test semantic changes"
  - "Migration/settings/dependency changes"
  - "DEV-006 / PR #13"
  - "git push origin main in IMPLEMENTATION_RELEASE"
release_sequence:
  - "PLAN_LANDING（NORMAL 下由 Release Operator 在批准后落计划并创建 exact feat branch）"
  - "Developer 仅修改 whitelist"
  - "Code Review / Commit Recorder"
  - "IMPLEMENTATION_RELEASE 仅在 exact feat branch add/commit/push/PR；禁止 merge/rebase/force push"
  - "PR merge 与 post-merge cleanup 由后续门禁处理"
```

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：2026-08-11 14:18 UTC
- 原计划：Round 1 plan Sections 5.1–5.4, 8, 9, 10, 11 and progress/master_plan planning notes.
- 修改内容：闭合 MF-001：固定 CLI 为 `uv run python scripts/republish_archive_event.py --archive-id <id> --user-id <id>`；固定 subprocess test-only env 与容器 IP host endpoints（Mongo `<mongo_ip>:27017`, Kafka `<kafka_ip>:9092`）、DB/topic、非机密 placeholders，并明确覆盖 Docker-internal `mongodb`/`kafka` names；确认 EXT-001 `create_archive_created_consumer(..., group_id=...)` 支持 test-only unique group，保留 production default `memory-extraction-group`；把 offset 断言收窄为 valid event consumed + terminal Mongo state exists + that record commit only，无 Mongo/Kafka atomicity claim；统一 `uv run pytest -q ... -m integration`。
- 修改原因：Independent review Round 2 BLOCKER=0, MUST_FIX=1, SHOULD_FIX=3；补足 CLI resolution、subprocess endpoint/config、group isolation 和 offset proof wording。
- 是否影响技术规格：否；baseline_main_sha 保持 `d6e7941eeaa2a8409b09eaf181d2924eb3865138`，production_delta 仍为 `NONE`，whitelist 未扩展，未修改业务 Contract。
- 审批状态：Round 2 PLAN_REJECTED（BLOCKER=0 MUST_FIX=1 SHOULD_FIX=3）；已由 Amendment 002 吸收

### Amendment 002 — Round 3 remediation（MF-001 closure）

- 日期：2026-08-11 14:27 UTC
- 原计划：Amendment 001 的 Settings/subprocess environment、Kafka raw-reader、Fake pipeline 和 CLI invocation wording；Round 2 review 结果为 BLOCKER=0 / MUST_FIX=1 / SHOULD_FIX=3。
- 实际代码核查结果（冻结为本任务依据，不修改生产代码）：
  - `src/memory_system/settings/models.py::Settings` 使用 `env_nested_delimiter="__"`；`Settings.settings_customise_sources` 的有效优先级是 **environment > `.env` dotenv > YAML (`configs/<APP_ENV>`) > init/defaults**。
  - CLI `scripts/republish_archive_event.py` 通过 `get_settings()` 读取 `settings.mongodb.uri`, `settings.kafka.bootstrap_servers`, `settings.kafka.topic`，而 `Settings` 的 `_REQUIRED_ENV_KEYS` 仍要求以下精确名称：`APP_ENV`, `REDIS__URI`, `MONGODB__URI`, `KAFKA__BOOTSTRAP_SERVERS`, `NEO4J__URI`, `ELASTICSEARCH__URL`, `LLM__BASE_URL`, `LLM__API_KEY`, `LLM__COMPRESSION__MODEL`, `LLM__EXTRACTION__MODEL`, `EMBEDDING__MODEL_ID`, `EMBEDDING__BASE_URL`, `MEMORY_API_KEY`, `MEMORY_ADMIN_API_KEY`, `PROXY__HTTP_URL`, `EMBEDDING_EFFECTIVE_RUNTIME_MODE`, `EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET`; `KAFKA__TOPIC` is the exact nested env override for the archive-event topic.
  - Existing integration helper `_compose_env()` uses `os.environ.copy()`, but that is not an acceptable CLI subprocess boundary for STM-012 and is superseded below.
- Binding subprocess environment contract:
  - Build an explicit dictionary; **never** call or derive it from unconstrained `os.environ.copy()` (or pass ambient `os.environ`).
  - Permit only the repository-convention minimal OS launch variables `PATH` and `PYTHONPATH` (with values resolved by the test process), plus the exact application keys listed above and `KAFKA__TOPIC`. No proxy, database, Mongo, Kafka, topic, config-selector, or other application variable may enter from the ambient environment.
  - Pin test-supplied values as authoritative in that dictionary: `APP_ENV=test`; `MONGODB__URI=mongodb://<host-reachable-mongo-ip>:27017/memory_system` (the database name is the URI path `memory_system`); `KAFKA__BOOTSTRAP_SERVERS=<host-reachable-kafka-ip>:9092`; `KAFKA__TOPIC=context.archive.created`; `PROXY__HTTP_URL=""`; and the existing non-secret test values for all other required Settings keys. The unused required URI/API-key fields use non-secret placeholders and are never logged; no secret is accepted or submitted.
  - This allowlist must exclude ambient `MONGODB__*`, `KAFKA__*`, topic/database/config-selector, proxy, `APP_ENV`, and other application variables capable of changing Settings resolution. Because the exact required keys are all pinned, `.env`/YAML cannot supersede the test values under the verified precedence mechanism; do not change `.env`, YAML, Settings defaults, or Settings production contract.
- Binding CLI contract:
  - From `REPO_ROOT` as `cwd`, invoke exactly `python scripts/republish_archive_event.py --archive-id <archive_id> --user-id <user_id>` for both first and second publication; do not use module resolution or substitute `uv run`.
  - Use the sanitized allowlisted environment above, a finite subprocess timeout (60 seconds), `capture_output=True`, `text=True`, and require `returncode == 0`. On failure, report bounded stdout/stderr diagnostics with IDs and secrets redacted; never print the environment or credentials.
- Binding raw Kafka reader contract:
  - Connect to the host-reachable `<kafka-ip>:9092` endpoint and exact `context.archive.created` test topic with a unique test-only group per test/attempt. Configure `enable_auto_commit=False`, `auto_offset_reset="earliest"`, and a bounded poll/deadline; do not use an existing group or prior committed offsets, and do not poll unboundedly.
  - Filter records by the unique fixture `archive_id` and `user_id`, and the expected `event_id` once known; assert the record’s topic/key/payload and use its partition/offset for the EXT-001 consumer. The raw reader only observes publication and never substitutes for, consumes in place of, or changes the EXT-001 consumer group.
- Binding test-only FakeCompletePipeline contract:
  - Inspect and conform to `ExtractionPipelinePort.run(task, event) -> PipelineTerminalDecision` and the existing `FakeCompletePipeline` behavior. The STM-012 test Fake must be deterministic, record invocation count and both `task.archive_id`/`event.archive_id`, return only `PipelineTerminalDecision.complete()`, and have no EXT-002/LLM/embedding/Neo4j/Elasticsearch access or production fallback.
  - Assert the first valid event invokes the Fake exactly once and creates the terminal task state. Assert the second event has a new `event_id` but stable `archive_id`, leaves the task count and terminal document non-destructively unchanged, and leaves the second Fake invocation count at zero (therefore total invocation count remains one).
- Binding flow and stop condition: preserve the approved first/second real CLI → Kafka → EXT-001 consumer adapter → Mongo flow, use a new `event_id` and stable `archive_id`, verify terminal duplicate behavior and the committed offset for each valid record, and make no Kafka/Mongo atomicity claim. If current infrastructure cannot satisfy these requirements without a production change, contract/default change, or whitelist expansion, **HALT in the plan and report the exact limitation; do not invent env names or APIs**.
- Required plan text corrections: wherever the prior plan says `uv run` for the STM-012 CLI, it is superseded by the exact `python scripts/...` command above; wherever it says “environment copy”, it is superseded by this explicit allowlist. The whitelist remains exact and `production_delta: NONE`.
- 是否影响技术规格：否；baseline_main_sha remains `d6e7941eeaa2a8409b09eaf181d2924eb3865138`, STM-011/EXT-001 semantics and Settings production contract/defaults remain frozen, and no whitelist path is added.
- 审批状态：Round 3 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0 SHOULD_FIX=3）；MF-001 CLOSED；human PLAN_APPROVED 待确认；不得进入 Developer / PLAN_LANDING

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-11 14:11 UTC | planning | 创建本 Task Plan；未修改业务代码或测试 | 未执行（planning-only） | Round 1 等待 PLAN_REVIEW |
| 2026-08-11 14:18 UTC | planning remediation | 追加 Amendment 001；仅更新计划内容 | 未执行（planning-only） | MF-001/MF-001-related SHOULD_FIX closure；等待 Round 2 PLAN_REVIEW |
| 2026-08-11 14:27 UTC | planning remediation Round 3 | 追加 Amendment 002；核查实际 Settings env 名称/优先级、CLI、ExtractionPipelinePort 和 FakeCompletePipeline；仅规划文件治理更新 | 未执行（planning-only） | 关闭 Round 2 MF-001；吸收 raw-reader/Fake/CLI SHOULD_FIX；等待 Round 3 PLAN_REVIEW |
| 2026-08-11 14:47 UTC | plan review metadata sync Round 3 | 回写 Round 3 PLAN_APPROVED；BLOCKER=0 MUST_FIX=0 SHOULD_FIX=3；MF-001 CLOSED；human PLAN_APPROVED 仍为 pending | 未执行（planning-only） | 仅治理元数据同步；不修改实质性计划语义；不实施 SHOULD_FIX 抛光项 |
| 2026-08-11 15:05 UTC | PLAN_LANDING | docs(plan) `b0cc223c60d0d8a1011a7a92e8f705285726792d` on main；创建 `feat/STM-012-republish-extraction-consumer-integration` | 未执行 | human PLAN_APPROVED granted |
| 2026-08-11 15:10 UTC | implementation | 创建 `tests/integration/test_stm012_republish_extraction_consumer_integration.py`；CLI subprocess sanitized env + sitecustomize kafka DNS bridge；Mongo fixture → CLI → Kafka raw reader → EXT-001 consumer → Mongo assertions | `uv run pytest -q tests/integration/test_stm012_republish_extraction_consumer_integration.py -m integration` **1 passed**（59.97s）；ruff **PASS**；mypy **PASS** | production_delta **NONE**；test-only sitecustomize via PYTHONPATH for CLI subprocess kafka hostname resolution（in-process tests use socket patch；Amendment 002 CLI env unchanged） |

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `02_开发管理/tasks/STM-012-republish-extraction-consumer-integration.md` | 本轮创建；仅计划 |
| `tests/integration/test_stm012_republish_extraction_consumer_integration.py` | 创建；STM-012 Integration/E2E |

### 与原计划的差异

- CLI subprocess 增加 test-only `sitecustomize`（经 `PYTHONPATH` temp dir）将 broker metadata 的 `kafka` 主机名解析到 `KAFKA__BOOTSTRAP_SERVERS` IP；不修改 `src/**` 或 STM-011 CLI 本体；与 in-process integration 的 `socket.getaddrinfo` patch 等效。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | — | 无新增 |
| Contract | — | 无新增 |
| Integration | `uv run pytest -q tests/integration/test_stm012_republish_extraction_consumer_integration.py -m integration` | **1 passed**（59.97s） |
| E2E | — | 同上（vertical slice in integration test） |
| Ruff | `uv run ruff check tests/integration/test_stm012_republish_extraction_consumer_integration.py` | **PASS** |
| Mypy | `uv run mypy tests/integration/test_stm012_republish_extraction_consumer_integration.py` | **PASS** |

### Review 结果

```yaml
plan_review: PLAN_APPROVED
plan_review_round: 3
blocker: 0
must_fix: 0
should_fix: 3
mf001_status: CLOSED
human_plan_approved: true
production_delta_expected: NONE
review_report: "Round 3 independent Plan Review PLAN_APPROVED; MF-001 CLOSED; implementation tested — integration 1 passed; ruff+mypy PASS; production_delta NONE"
```

### Git 记录

```yaml
branch: feat/STM-012-republish-extraction-consumer-integration
plan_commit: b0cc223c60d0d8a1011a7a92e8f705285726792d
implementation_commit: 26aa710d62123d341fb79349c9ad86fc5d58c0a6
implementation_commit_message: "test(integration): verify republish event extraction consumer idempotency"
pr: "#35"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/35"
pr_state: OPEN
```

### 最终状态

`committed`
