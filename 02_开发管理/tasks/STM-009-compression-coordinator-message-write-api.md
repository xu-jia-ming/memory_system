# STM-009 Compression Coordinator + Message Write API Wiring

## 1. 任务信息

```yaml
task_id: STM-009
task_name: Compression Coordinator + Message Write API Wiring
status: tested
plan_review_round: 1
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.1 Working Memory（写入规则 3–6；容量背压；压缩协调摘录）"
  - "§1.2.2 Context Archive（archive_batch_key；Pending 复用）"
  - "§1.2.3 Memory API — POST /api/v1/memory/working/message"
  - "§1.2.4 Kafka context.archive.created"
  - "§1.2.5 Compression Update Flow（LLM 输出；Finalize 前置）"
  - "§1.2.6 Context Compression Trigger Strategy（触发阈值；多轮；消息选择；Kafka 失败语义）"
  - "§1.2.7 Session 生命周期（closing 写入拒绝；Pending 保留）"
  - "§3.9 LLM（Compression Service 边界）"
  - "§3.23 统一 API 响应与 Request ID"
  - "§3.28 Graceful Shutdown（in-flight 压缩；本任务仅引用 STM-008 既有语义）"
prerequisites:
  formal:
    - "STM-003 — SATISFIED（write_message + Lua；PR #21 MERGED）"
    - "STM-004 — SATISFIED（read_working_memory_context；PR #22 MERGED）"
    - "STM-005 — SATISFIED（create_or_reuse_context_archive；PR #23 MERGED）"
    - "STM-006 — SATISFIED（prepare_pending_archive_and_publish；PR #25 MERGED）"
    - "STM-007 — SATISFIED（run_compression_llm + FakeLlmClient；PR #26 MERGED）"
    - "STM-008 — SATISFIED（finalize_compression；PR #27 MERGED）"
    - "DEV-005 — SATISFIED（API 壳、鉴权、request_id、错误包络、日志指标；PR #12 MERGED）"
  implementation_reuse:
    - "STM-001 — SATISFIED（estimate_tokens；ContextSettings）"
    - "STM-002 — SATISFIED（Session 创建；路由模式参考）"
  baseline:
    - "Authoritative baseline：main == origin/main == a15a2e4cd4b0f937a9f15aa9f4a1481ddb867466；working tree clean；FULL_RUFF PASS；mypy PASS"
branch: "feat/STM-009-compression-coordinator-message-write-api"
created_at: "2026-08-11 08:34 UTC"
updated_at: "2026-08-11 09:10 UTC"
approval_gates:
  planning_docs: approved
  implementation_plan: approved
```

### 1.1 编排与门禁（本轮）

```yaml
start_existing_task: true
phase: planning_only
must_not_this_round:
  - "进入 Developer / 编写业务实现或测试语义"
  - "git add / commit / push / merge / rebase"
  - "触碰 DEV-006 / PR #13"
  - "重写 STM-003–008 底层 Lua/Repository 语义"
  - "实现 STM-010 Session Close / STM-011 republish / STM-013 全链路 E2E"
  - "自行关闭 OI-004（完整 token-boundary 仍属 STM-010）"
```

---

## 2. 任务目标

交付 **Compression Coordinator** 与 **`POST /api/v1/memory/working/message` HTTP 接线**：客户端写入一条消息 → STM-003 原子写入 → 按规格判定是否需压缩 → 无需压缩则正常返回 → 需要则按 §1.2.6 在单请求内编排 STM-004/005/006/007/008 公共领域边界（**仅编排，不重实现底层原语**）→ 返回稳定 API 结果（含 `compression_status`）。

可验证交付：

1. **Coordinator 领域服务**：`run_compression_coordination(...)` + `write_working_message_with_coordination(...)`（命名可微调，须单一编排入口）；容量背压路径与触发后压缩路径共用同一协调内核。
2. **HTTP 路由**：`POST /api/v1/memory/working/message`；DEV-005 鉴权/Request ID/错误包络/可观测性。
3. **Pydantic Schema**：请求/成功响应与 §1.2.3 对齐；**不**引入规格外字段。
4. **依赖注入**：复用 `AppState`（redis/mongodb/kafka_producer/settings）；默认 LLM = `FakeLlmClient`（测试/CI）。
5. **测试**：Unit 20 场景 + Contract + Integration A–L（FakeLlmClient；非 STM-013 全 E2E）。

概念链：

```text
HTTP POST /working/message
  → MessageWriteCoordinator
      → STM-003 write_message (Lua)
      → [capacity_exceeded] → run_compression_coordination (≤N rounds) → retry write
      → [success/duplicate] → [trigger?] → run_compression_coordination (≤N rounds)
      → HTTP 200 {message_id, status, compression_status}
```

---

## 3. 非目标（必须坚持）

- 重写 STM-003 write Lua、STM-004 read Lua、STM-005 Mongo repo、STM-006 pending/lock Lua、STM-007 LLM retry、STM-008 Finalize Lua 公式。
- `GET /api/v1/memory/working/...` 读上下文 HTTP（可留后续任务；本任务仅写路由）。
- STM-010 Session Close、STM-011 `republish_archive_event.py`、STM-013 全阶段 E2E。
- DEV-006/PR#13、TEI/SiliconFlow Embedding、EXT/RET 全链路。
- Outbox、跨 Redis+Mongo+Kafka 伪原子事务、锁续期、Python 进程内全局 mutex。
- 扩展 Mongo Archive schema 写入 `estimated_tokens`（OI-004 完整闭合留给 STM-010）。
- 真实 DeepSeek 作为默认 CI 路径（opt-in 集成可 SKIP）。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `a15a2e4cd4b0f937a9f15aa9f4a1481ddb867466` |
| `git status --short` | clean（规划轮次允许 Task Plan + progress + master_plan dirty） |
| formal STM-003..008 | `completed` |
| FULL_RUFF / mypy | PASS（baseline 声明） |

### 4.2 可复用组件审计

| 组件 | 路径 | STM-009 用法 |
|---|---|---|
| `write_message` | `domain/services/message_write_service.py` | 原子写入；**唯一**消息写入入口 |
| `read_working_memory_context` | `domain/services/context_read_service.py` | 每轮压缩前读快照 |
| `create_or_reuse_context_archive` | `domain/services/context_archive_service.py` | Mongo create/reuse |
| `build_archive_batch_key` | 同上 | `session_id:first:last` |
| `prepare_pending_archive_and_publish` | `domain/services/compression_preparation_service.py` | 锁 + pending Lua + Kafka |
| `run_compression_llm` | `domain/services/compression_llm_service.py` | LLM（Fake/DeepSeek 注入） |
| `finalize_compression` | `domain/services/compression_finalize_service.py` | 单 Lua Finalize |
| `MessageWriteInput/Result` | `domain/models/message_write.py` | HTTP→领域映射 |
| `ContextSettings` | `settings/models.py` | 全部阈值/轮数/TTL |
| `AppState` | `infrastructure/runtime.py` | redis/mongodb/kafka/settings |
| DEV-005 路由模式 | `api/routes/memory_session.py` | 鉴权/包络/指标 |
| `hash_fields_to_meta` | `infrastructure/redis/working_memory_codec.py` | 读 pending/meta |

### 4.3 当前缺失

- `CompressionCoordinatorService`（编排）
- `CompressionStatus` 枚举（HTTP `compression_status` 字面量）
- `POST /api/v1/memory/working/message` 路由 + Schema
- `get_working_memory_meta`（或等价只读 meta 读取 helper）
- Coordinator 消息头部选择纯函数（§1.2.6）
- Unit / Contract / Integration 全套测试

### 4.4 前置任务检查

| 前置 | 状态 |
|---|---|
| STM-003..008 | **SATISFIED** |
| DEV-005 | **SATISFIED** |
| OI-001 | **open** → **本 Task Plan §10.1 Planner 决议闭合** |
| OI-002 | **open** → **本 Task Plan §10.2 Planner 决议闭合** |
| OI-004 | **open** → **不阻塞**；§10.3 局部决议 |
| OI-005 | **open** → **不阻塞**；§10.4 正式闭合 |

---

## 5. 实现方案

### 5.0 二十三项 Contract 闭合（Planner 权威结论）

#### 1 — HTTP endpoint（§1.2.3 + §3.23 + DEV-005）

| 项 | 结论 |
|---|---|
| Method / Path | `POST /api/v1/memory/working/message` |
| Auth | `X-API-Key` → `require_memory_api_key`（与 STM-002 相同） |
| Request Schema | `WriteMessageRequest`：`message_id`, `user_id`, `session_id`, `role` (`user`/`assistant`), `content`, `timestamp?`（int Unix；可选） |
| Response Schema（成功） | `WriteMessageResponse`：**仅** `message_id: str`, `status: Literal["success","duplicate"]`, `compression_status: CompressionStatus`（§467–475 七值） |
| 规格外字段 | **禁止**在成功响应中加入 `session_id`/`compression_version`/`estimated_tokens`（§456–464 未定义；不得私增 Contract） |
| Success HTTP | **200**（与 STM-002 Session Create 一致） |
| Request ID | `RequestIdMiddleware`；响应 Header `X-Request-ID`；错误 Body `request_id` |
| 错误包络 | `AppError` + `build_error_body`（§3.23） |

**HTTP 错误映射（写消息专用）**

| 条件 | HTTP | `error.code` |
|---|---|---|
| 缺失/无效 API Key | 401 | `unauthorized`（DEV-005 既有） |
| Pydantic schema 失败 | 422 | `validation_error` |
| `content` 空 | 422 | `validation_error` |
| `message_too_large`（Python 预检） | 400 | `message_too_large` |
| `invalid_message_timestamp` | 400 | `invalid_message_timestamp` |
| `session_not_found` | 404 | `session_not_found` |
| `session_closing` | 409 | `session_closing` |
| `working_memory_full`（容量背压二次仍失败） | 503 | `working_memory_full` |
| 未预期内部错误 | 503 | `internal_error` |

**压缩相关（消息已写入成功后）**：**不**升级为 4xx/5xx（§479、§5730）；HTTP **200** + `status=success` + `compression_status` 表达。

#### 2 — Write input（STM-003 契约）

| 项 | 结论 |
|---|---|
| 字段 | `user_id`, `session_id`, `message_id`, `role`, `content`, `timestamp?` — 映射 `MessageWriteInput` |
| 禁止 | 第二套消息模型；客户端 `estimated_tokens`（§237：服务端 `estimate_tokens(content)`） |
| 校验 | `content` 非空；`role` 枚举；`timestamp` 提供时：`<= server_time + allowed_future_timestamp_skew_seconds` |

#### 3 — Write first or compress first（§1.2.1 规则 3 + §1.2.3 流程图）

**权威状态机（单请求）**

```text
VALIDATE_REQUEST
  → WRITE_LUA (STM-003)
      ├─ session_not_found / session_closing / message_too_large → HTTP 错误（消息未写入）
      ├─ duplicate → HTTP 200 {status=duplicate, compression_status=not_triggered}（不触发压缩）
      ├─ capacity_exceeded → CAPACITY_COMPRESSION_ONCE → RETRY_WRITE_SAME_MESSAGE
      │       ├─ retry success → POST_WRITE_TRIGGER_CHECK
      │       └─ retry capacity_exceeded → HTTP 503 working_memory_full（消息仍未写入）
      └─ success → POST_WRITE_TRIGGER_CHECK
POST_WRITE_TRIGGER_CHECK:
  estimated_tokens >= compression_trigger_tokens ?
    ├─ No → HTTP 200 {status=success, compression_status=not_triggered}
    └─ Yes → TRIGGER_COMPRESSION_SYNC (≤ max_compression_rounds_per_request)
              → HTTP 200 {status=success, compression_status=<round_aggregate>}
```

**消息已写入但压缩失败**：`status` 仍为 `success`（或 `duplicate` 路径不变）；`compression_status` ∈ `{failed, skipped_lock, insufficient_messages, version_conflict, partial_completed, ...}`；**不得**回滚已写入消息（§261、§479）。

#### 4 — Compression trigger（§1.2.6 + §1047）

| 项 | 结论 |
|---|---|
| 比较字段 | Redis meta **`estimated_tokens`**（写入成功后由 STM-003 返回或 `get_working_memory_meta` 读取） |
| 比较对象 | `estimated(compressed_context) + sum(message.estimated_tokens)` 已折叠进 meta `estimated_tokens`（§1098–1104） |
| 运算符 | **`>= compression_trigger_tokens`**（规格「达到该值」；含精确等于） |
| 配置源 | `settings.context.compression_trigger_tokens`（`ContextSettings`；禁止硬编码） |
| 检查时机 | **仅**在消息 **成功写入**（含容量路径 retry 成功）且 `status != duplicate` 之后 |

#### 5 — Capacity vs trigger（§1.2.1 规则 2–3 + §1054）

| 项 | 结论 |
|---|---|
| `max_working_memory_estimated_tokens` | STM-003 Lua **硬上限**；`new_total > max` → `capacity_exceeded`（`==` 允许）；Coordinator **不得**绕过 |
| `compression_trigger_tokens` | **仅** Coordinator 在写入成功后判定是否同步压缩 |
| 容量路径 | `capacity_exceeded` → 运行 **一次** `run_compression_coordination`（语义见 §10.1 OI-001）→ **相同** `message_id`/content/timestamp 重试 STM-003 |
| 禁止 | 在 Lua 外用 trigger 阈值替代 WM 上限；在 WM 未达上限时因 trigger 拒绝写入 |

#### 6 — Compression workflow orchestration（§1.2.1 规则 4 + §1.2.6）

**单轮顺序（公共边界 ONLY）**

```text
1. STM-004 read_working_memory_context
2. [无 pending] 头部消息选择（§5.1）
   [有 pending] 从 meta 读取 pending 四字段 + Mongo find_by_batch_key
3. STM-005 create_or_reuse_context_archive（新选批次时；pending 复用则跳过 create 若 archive 已存在）
4. STM-006 prepare_pending_archive_and_publish（fresh acquire 或 pre-held token）
5. STM-007 run_compression_llm（持锁；不重复 acquire）
6. STM-008 finalize_compression（传入 lock_owner_token + pending 四字段 + 边界 message_id）
```

**多轮**：`round` 从 0 递增；每轮开始前重读 `estimated_tokens`；若 `< compression_trigger_tokens` → 聚合返回 `completed`；达到 `max_compression_rounds_per_request` 仍 `>= trigger` → `partial_completed`（§1124）。

#### 7 — Archive message boundary（§1.2.6 §1113–1118 + §1.2.2）

| 项 | 结论 |
|---|---|
| 归档范围 | Redis List **头部**连续前缀（最旧 → 较新）；**不得**跳消息、不得拆分单条 |
| 保留窗口 | 尾部至少 `absolute_min_recent_messages`；优先保留 `preferred_recent_messages`，可缩小至绝对最小 |
| 单 Archive 上限 | 前缀 `sum(message.estimated_tokens) <= max_archive_estimated_tokens` |
| 选择优化 | 在满足约束下，选 **最大** 前缀使 `meta.estimated_tokens - sum(prefix)` **最接近且尽量 ≤ `compression_target_tokens`** |
| `first_message_id` / `last_message_id` | 前缀首/尾 `message_id` |
| `archive_batch_key` | `build_archive_batch_key(session_id, first, last)` |
| token 总量 | `pending_archive_estimated_tokens` = `sum(prefix.message.estimated_tokens)`（Redis 字段，§10.3） |
| Pending 复用 | `pending_archive_id` 非空 → **禁止**重选消息；复用四字段；STM-006 幂等 pending + 重发 Kafka（§1112） |
| 不足消息 | `len(messages) <= absolute_min_recent_messages` 或无法选出合法前缀 → 本轮 `insufficient_messages`（§1119–1121） |

**MUST_FIX 计数**：**0**（规格已闭合）。

#### 8 — OI-004（§10.3）

| 项 | 结论 |
|---|---|
| 阻塞 STM-009？ | **否** |
| `archived_message_tokens` / pending tokens | **Redis WM 消息 `estimated_tokens` 求和**；Finalize `archived_message_tokens` 必须等于 `pending_archive_estimated_tokens`（STM-008 既有校验） |
| LLM `archived_messages` | 新批次：来自 WM 前缀；Pending 复用：Mongo `find_context_archive_by_batch_key` 的 `messages`（四字段） |
| Mongo | **不写** `estimated_tokens`；OI-004 **保持 open** 至 STM-010 |

#### 9 — OI-005（§10.4）

| 项 | 结论 |
|---|---|
| 阻塞 STM-009？ | **否** |
| 决议 | Kafka producer = `AppState.kafka_producer`；发布在 `memory-api` 进程内 Coordinator 调用 STM-006；**无**独立 Context Archive Service 网络组件 |
| 闭合 | 本 Task Plan 决议 + 实现证据后可在 POST_MERGE `open_issues.md` 追加 `resolved` 记录 |

#### 10 — Lock lifecycle（§1.2.1 规则 6 + STM-006/008）

| 项 | 结论 |
|---|---|
| Key / TTL | `memory:compression:lock:{user_id}:{session_id}`；`compression_lock_ttl_seconds`（默认 420s） |
| Acquire | 每轮压缩：STM-006 `prepare_pending_archive_and_publish` 在 `lock_owner_token=None` 时 `SET NX EX` |
| Pre-held | 同轮内重试 pending/Kafka：传入 `lock_owner_token`；**禁止** Python mutex |
| Token 传递 | Coordinator 保存 `lock_owner_token` → STM-006（pre-held）→ STM-008 `finalize_compression` |
| LLM 期间 | 锁保持；STM-007 **不** acquire/release |
| 释放 | **仅** STM-008 Finalize Lua 成功路径 compare-and-delete（§1.2.1 步骤 260） |
| 失败/超时 | 不调用 Finalize 或 Finalize 失败 → 锁保留至 TTL；pending 保留（§261） |
| Stale at Finalize | `lock_not_acquired` → `compression_status=failed`（消息已写入场景） |

**多轮锁语义（Planner 闭合 §1108 vs STM-008）**：§1108「同一锁内」指 **单轮** 内 prepare→LLM→finalize 链；STM-008 成功后锁释放；下一轮 **重新** `SET NX EX`。禁止为跨轮持有锁而修改 STM-008。

#### 11 — Long-running LLM vs lock TTL（§1057–1059 + §268）

| 项 | 结论 |
|---|---|
| 默认 | `420 > 3 * 120 + 30`（启动校验已保证） |
| 锁续期 | **禁止**（§268 MVP 不实现） |
| LLM 超时 | `compression_llm_timeout_seconds`（STM-007） |
| 锁过期后 Finalize | `lock_not_acquired`；pending 保留；`compression_status=failed` |
| 进程崩溃 | 同 STM-006 recovery-visible；STM-011 补发 |

#### 12 — Kafka timing（§1.2.6 步骤 6 + STM-006）

| 项 | 结论 |
|---|---|
| 顺序 | pending Lua **committed** → **then** publish（STM-006 既有 gate） |
| 禁止 | 将 publish 移到 Finalize 之后（除非规格修订） |

#### 13 — Kafka publish failure（§1126 + STM-006）

| 项 | 结论 |
|---|---|
| `publish_failed` | pending **保留**；锁 **保留**；**继续 LLM**（§1126：不阻塞压缩） |
| API | 消息已写入 → HTTP 200；若后续 LLM+Finalize 成功 → `compression_status` 按轮次聚合；若 LLM/Finalize 失败 → `failed` |
| 日志 | 记录 `archive_id`（禁止消息全文/secret） |
| 恢复 | STM-011 republish（本任务不实现） |

#### 14 — LLM failure（§261 + §1125）

| 项 | 结论 |
|---|---|
| 行为 | **不**调用 Finalize；**不**清 pending；**不**删 Mongo archive；**不** LTRIM |
| 锁 | 保持至 TTL（无主动 release） |
| API | 消息已写入 → HTTP 200 `status=success` `compression_status=failed` |
| 重试 | 客户端下次写入或相同 session 再次触发时复用 pending（§1112） |

#### 15 — Finalize failure → HTTP（§5730）

| Finalize status | 消息已写入后 HTTP | `compression_status` |
|---|---|---|
| `version_conflict` | **200** | `version_conflict` |
| `lock_not_acquired` | **200** | `failed` |
| `pending_conflict` | **200** | `failed` |
| `invalid_session_state` | **200** | `failed` |
| `message_boundary_mismatch` | **200** | `failed` |
| `session_closing` | **200** | `failed`（压缩路径；新写入已在步骤 3 拦截） |
| `session_not_found` | **200** | `failed` |

#### 16 — Retry / idempotency（§1.2.1 + §477）

| 场景 | 行为 |
|---|---|
| 重复 `message_id` | STM-003 `duplicate`；零副作用；`compression_status=not_triggered` |
| Archive REUSED | STM-005 `REUSED`；同一 `archive_id` |
| Pending 同身份 | STM-006 幂等 `success`；可再 publish |
| LLM 成功 Finalize 未知 | 客户端重试同 `message_id` → `duplicate`；**不得** double trim/bump |
| 容量路径 | 同 `message_id` 重试写入；`working_memory_full` 时消息**未**写入 |

#### 17 — Concurrency（§1.2.1 规则 6）

| 场景 | 行为 |
|---|---|
| 两写入同时触发压缩 | STM-003 原子 + STM-006 `SET NX`；失败者 `skipped_lock` |
| Loser | HTTP 200（消息已写入）`compression_status=skipped_lock` |
| 禁止 | Python `asyncio.Lock` / 进程 mutex 作为跨请求协调 |

#### 18 — Session closing（§1.2.3 + §732）

| 场景 | 行为 |
|---|---|
| 新写入 `status=closing` | STM-003 `session_closing` → HTTP **409**（不得成功 body） |
| 已写入后的 in-flight | STM-008 允许 closing+pending in-flight（STM-008 既有）；本任务 **不** 实现 STM-010 Close |

#### 19 — Coordinator transaction model（Saga / staged-state）

| Stage | 持久化状态 | 失败 | 重试 | Recovery owner |
|---|---|---|---|---|
| Write | 消息在 Redis | 未写入 | 客户端同 `message_id` | Client |
| Archive create | Mongo 文档 | 中止本轮；pending 无 | 下轮复用 pending 或重选 | Coordinator / STM-011 |
| Pending+Lock | Redis pending 四字段 + lock | `pending_conflict`/`lock_not_acquired` | 新请求竞争锁 | Coordinator |
| Kafka | 无独立状态 | `publish_failed` 日志 | STM-011 republish | STM-011 |
| LLM | 无 Redis 变更 | `failed`；pending 保留 | 下次触发复用 pending | Coordinator |
| Finalize | Redis 摘要/trim/清 pending/释锁 | 见 §15 | 同 `message_id` duplicate 防 double | STM-008 幂等 |

**禁止** cross-system rollback（删 Mongo、清 pending）作为「事务回滚」。

#### 20 — HTTP latency model（§479）

| 项 | 结论 |
|---|---|
| 模型 | **同步**：触发压缩后 **等待** 完整压缩（含多轮，至多 `max_compression_rounds_per_request`）再返回 HTTP 响应 |
| 异步 | **禁止** MVP 写路径返回 202/后台任务 ID |
| MUST_FIX | **0**（§479 已闭合） |

#### 21 — Response contract

| 路径 | `status` | `compression_status` |
|---|---|---|
| 未达触发阈值 | `success` | `not_triggered` |
| 重复消息 | `duplicate` | `not_triggered` |
| 压缩完成且低于阈值 | `success` | `completed` |
| 多轮后仍高于阈值 | `success` | `partial_completed` |
| 锁占用 | `success` | `skipped_lock` |
| 无消息可归档 | `success` | `insufficient_messages` |
| 写回版本冲突 | `success` | `version_conflict` |
| 其他压缩失败 | `success` | `failed` |

**同一 Schema** 用于压缩/未压缩成功路径（§456–464）。

#### 22 — Metrics / logging（DEV-005）

| 项 | 结论 |
|---|---|
| 访问日志 | `AccessLogMetricsMiddleware` 自动 |
| 结构化日志 | `structlog`：`request_id`, `user_id`, `session_id`, `message_id`, `compression_status`, `compression_rounds`, `archive_id`（失败时） |
| 禁止 | 完整 `content`、API Key、LLM prompt 全文 |
| 指标 | 复用既有 HTTP 指标；可增加 `compression_coordination_total{result=...}`（可选 counter；若加须入白名单） |

#### 23 — No duplicate infrastructure

| 依赖 | 注入来源 |
|---|---|
| Redis | `app_state.redis` |
| Mongo | `app_state.mongodb` |
| Kafka | `app_state.kafka_producer` + `settings.kafka.topic` |
| LLM | `FakeLlmClient`（默认测试/CI）或 `DeepSeekLlmClient`（生产 wiring，与 STM-007 相同工厂） |
| Settings | `app_state.settings` / `get_settings()` |

---

### 5.1 消息头部选择算法（权威伪代码）

```python
def select_archive_prefix(
    *,
    messages: list[WorkingMemoryMessage],
    meta_estimated_tokens: int,
    context: ContextSettings,
) -> ArchiveSelection | InsufficientMessages:
  n = len(messages)
  if n <= context.absolute_min_recent_messages:
      return InsufficientMessages()

  best: ArchiveSelection | None = None
  for tail_keep in range(context.preferred_recent_messages, context.absolute_min_recent_messages - 1, -1):
      tail_keep = min(tail_keep, n - 1)  # need at least 1 archived
      prefix = messages[: n - tail_keep]
      if not prefix:
          continue
      prefix_tokens = sum(m.estimated_tokens for m in prefix)
      if prefix_tokens > context.max_archive_estimated_tokens:
          # shrink prefix from tail of prefix until within cap (still contiguous from head)
          ...
      remaining = meta_estimated_tokens - prefix_tokens
      if remaining < 0:
          continue
      candidate = ArchiveSelection(prefix=prefix, prefix_tokens=prefix_tokens, projected_remaining=remaining)
      best = pick_better(best, candidate, target=context.compression_target_tokens)

  return best or InsufficientMessages()
```

实现须 **Unit 测试** 覆盖 preferred/absolute 窗口、max_archive cap、全不可选 → `insufficient_messages`。

### 5.2 Coordinator 核心 API（建议）

```python
class CompressionCoordinationResult(BaseModel):
    status: CompressionStatus  # completed|partial_completed|failed|skipped_lock|insufficient_messages|version_conflict
    rounds_completed: int = 0

async def run_compression_coordination(
    *,
    redis, mongodb, kafka_producer, llm_client, settings,
    user_id: str, session_id: str,
    request_id: str | None = None,
    max_rounds: int | None = None,  # default settings.context.max_compression_rounds_per_request
) -> CompressionCoordinationResult: ...

async def write_working_message_with_coordination(
    *,
    redis, mongodb, kafka_producer, llm_client, settings,
    input: MessageWriteInput,
    request_id: str | None = None,
    clock: Clock | None = None,
) -> WriteMessageCoordinatorResult: ...
```

`CompressionStatus` 枚举 **七值** 与 §467–475 字面量一致（`StrEnum`）。

### 5.3 HTTP 路由（Step 清单）

**Step 1 — Domain enums/models**

- `domain/enums/compression_coordinator.py`：`CompressionStatus`
- `domain/models/compression_coordinator.py`：`WriteMessageCoordinatorResult`, `CompressionCoordinationResult`, `ArchiveSelection`

**Step 2 — Meta read helper（最小底层）**

- `infrastructure/redis/working_memory_repository.py`：新增 `get_working_memory_meta(redis, user_id, session_id) -> WorkingMemoryMeta | None`

**Step 3 — Coordinator service**

- `domain/services/compression_coordinator_service.py`：编排 §5.0/5.1/5.2

**Step 4 — API schema + route**

- `api/schemas/memory_message.py`
- `api/routes/memory_message.py`
- `api/app.py`：`include_router(memory_message.router)`

**Step 5 — LLM factory wiring**

- 复用 STM-007 既有 client 工厂；`create_app` 测试注入 `FakeLlmClient`

**Step 6 — 测试**

- 见 §8

---

## 6. 文件变更清单（实施白名单）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/enums/compression_coordinator.py` | 创建 | `CompressionStatus` |
| `src/memory_system/domain/models/compression_coordinator.py` | 创建 | Coordinator I/O 模型 |
| `src/memory_system/domain/services/compression_coordinator_service.py` | 创建 | 编排内核 |
| `src/memory_system/infrastructure/redis/working_memory_repository.py` | 修改 | `get_working_memory_meta` |
| `src/memory_system/api/schemas/memory_message.py` | 创建 | HTTP schema |
| `src/memory_system/api/routes/memory_message.py` | 创建 | POST 路由 |
| `src/memory_system/api/app.py` | 修改 | 注册路由 |
| `tests/unit/test_compression_coordinator_service.py` | 创建 | Unit 20 场景 |
| `tests/contract/test_stm009_contract.py` | 创建 | HTTP 契约 |
| `tests/integration/test_message_write_coordinator_redis.py` | 创建 | Integration A–L |
| `tests/integration/test_message_write_coordinator_kafka.py` | 创建（可选拆分） | Kafka 失败可恢复 |
| `02_开发管理/tasks/STM-009-compression-coordinator-message-write-api.md` | 创建/更新 | 本计划 |
| `02_开发管理/progress.md` | 修改 | 规划态 |
| `02_开发管理/master_plan.md` | 修改 | STM-009 登记 |

**禁止修改（除非 Code Review 证明 STM-009 blocker）**：`message_write.lua`, `context_read.lua`, `pending_archive_write.lua`, `compression_finalize.lua`, STM-005/006/007/008 service **公共语义**。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 写入/Finalize 原子在 Lua；协调跨系统 | 分阶段 saga；失败保留中间态 |
| 幂等 | `message_id` / pending 同身份 / archive batch key | 复用 STM-003/005/006 |
| 并发 | 同 session 压缩互斥 | Redis lock NX |
| 版本冲突 | Finalize `version_conflict` | HTTP 200 + `compression_status` |
| 用户隔离 | `user_id`+`session_id` 贯穿 | 各服务既有校验 |
| 部分失败 | Kafka/LLM/Finalize 独立 | §5.0 §19 表 |
| 进程恢复 | pending+lock 可见 | STM-011；不清 pending |

---

## 8. 测试计划

### 8.1 Unit — Coordinator（20 场景，权威）

| # | 场景 | 预期 |
|---|---|---|
| U1 | 写入后 `estimated_tokens` < trigger | `not_triggered`；不调用压缩链 |
| U2 | 写入后 `>= trigger`，单轮成功 | `completed` |
| U3 | 重复 `message_id` | `duplicate` + `not_triggered` |
| U4 | `message_too_large` | 映射 HTTP 400；无 write |
| U5 | `capacity_exceeded` → 压缩成功 → retry 成功 | `success` + 适当 `compression_status` |
| U6 | `capacity_exceeded` → 压缩后仍满 | `working_memory_full` |
| U7 | STM-004 读失败 / `session_not_found` | 压缩 `failed` 或前置 HTTP 404 |
| U8 | Archive `CREATED` | Mongo 新文档 |
| U9 | Archive `REUSED` | 同 `archive_id` |
| U10 | `lock_not_acquired` | `skipped_lock` |
| U11 | `pending_conflict` | `failed` |
| U12 | Kafka `publish_failed` | 继续 LLM；日志；可 `completed`/`failed` |
| U13 | LLM success | 进入 Finalize |
| U14 | LLM timeout | `failed`；pending 保留 |
| U15 | LLM invalid output | `failed` |
| U16 | Finalize success | trim + pending clear |
| U17 | Finalize `version_conflict` | `version_conflict` |
| U18 | Finalize `lock_not_acquired`（过期） | `failed` |
| U19 | 阶段顺序 | Archive→Pending→Kafka→LLM→Finalize；无回滚幻想 |
| U20 | 多轮：两轮成功仍高于 trigger | `partial_completed` |

### 8.2 Contract — HTTP

| # | 场景 | 预期 |
|---|---|---|
| C1 | 端点存在 `POST /api/v1/memory/working/message` | 200/4xx 符合契约 |
| C2 | 无 API Key | 401 |
| C3 | 非法 body | 422 `validation_error` |
| C4 | `X-Request-ID` 透传 | Header + 错误 body |
| C5 | 成功包络字段 | 仅三字段 |
| C6 | 重复 `message_id` | `duplicate`/`not_triggered` |
| C7 | `capacity_exceeded` 路径 | 503 `working_memory_full` |
| C8 | 压缩失败 | 200 `success` + `failed` |
| C9 | `session_not_found` | 404 |
| C10 | `session_closing` | 409 |

### 8.3 Integration — A–L（FakeLlmClient；真实 Redis/Mongo/Kafka）

| ID | 场景 | 预期 |
|---|---|---|
| I-A | 低于 trigger 写入 | 无 pending/lock/Kafka |
| I-B | 全触发路径 Fake LLM | Archive+pending+Kafka+Finalize |
| I-C | Finalize 后 List trim | 头消息移除 |
| I-D | Token 会计 | meta `estimated_tokens` 符合 STM-008 公式 |
| I-E | Mongo archive 文档存在 | 四字段 messages |
| I-F | pending 清空 | 四字段空/0 |
| I-G | 锁释放 | Finalize 后 key 不存在 |
| I-H | Kafka 事件发出 | topic/key/schema |
| I-I | Kafka 失败可恢复 | pending 保留；STM-011 可补（本任务断言 legal state） |
| I-J | LLM 失败可恢复 | pending 保留；重触发复用 |
| I-K | 并发锁 | 一成功一 `skipped_lock` |
| I-L | 重试无 double-finalize | 同 `message_id` duplicate；version 不双增 |

**默认 LLM**：`FakeLlmClient` only；`RUN_COMPRESSION_LLM_INTEGRATION=1` opt-in 真实调用（SKIPPED 非阻塞）。

---

## 9. 验收标准

- [ ] `POST /api/v1/memory/working/message` 符合 §1.2.3 请求/响应/错误映射
- [ ] 写入 **先于** 触发压缩检查；容量路径 **先压缩一次再重试写入**（§247）
- [ ] `compression_trigger_tokens` 使用 meta `estimated_tokens` **`>=`** 判定
- [ ] STM-003 WM 上限语义不变；Coordinator 不绕过 Lua
- [ ] 编排 **仅** 调用 STM-004/005/006/007/008 公共 API
- [ ] 消息头部选择符合 §1113–1118；Pending 复用不重选
- [ ] Kafka `publish_failed` 不阻断 LLM（§1126）
- [ ] 消息已写入后压缩失败仍 HTTP 200 `status=success`
- [ ] OI-001/OI-002 Planner 决议已落盘 §10
- [ ] Unit 20 + Contract + Integration A–L 通过；`uv run ruff check .` + `uv run mypy src tests scripts` PASS
- [ ] 白名单外无改动；无 TODO/pass/空实现

---

## 10. Open Issues 处理

### 10.1 OI-001 决议（`resolve_by_task: STM-009`）

- **问题**：容量背压「压缩协调一次」与 `max_compression_rounds_per_request` 关系。
- **Planner 决议**：「一次压缩协调流程」= **单次** `run_compression_coordination(...)` 调用，其内部可执行 **至多** `context.max_compression_rounds_per_request` 轮（§247 与 §1108 同型）。容量路径与触发路径共用该函数；容量路径 `max_rounds` 同样取配置值（非硬编码 1）。
- **规格依据**：§1.2.1 规则 3「执行一次当前 Session 的压缩协调流程」；§1.2.6「在同一锁内最多执行 `max_compression_rounds_per_request` 轮」；§1.2.3 流程图 `Run Compression Once` 指 **一次协调入口** 而非单轮 LLM。
- **验收**：Unit U5/U20；Integration I-B 可配置 `max_compression_rounds_per_request=3`。

### 10.2 OI-002 决议（`resolve_by_task: STM-009`）

- **问题**：容量路径压缩锁被占用时是否直接 `working_memory_full`。
- **Planner 决议**：**否**。容量路径必须先调用 `run_compression_coordination`；若压缩侧返回 `skipped_lock`/`failed` 等，**仍必须用相同 `message_id` 重试 STM-003**；仅当 retry 仍 `capacity_exceeded` 时返回 HTTP **503** `working_memory_full`（§249–250）。锁占用 **不** 跳过 retry 写入步骤。
- **规格依据**：§1.2.1 规则 3 第二次写入分支；§1.2.6 步骤 1 `skipped_lock` 适用于 **已写入后** 触发路径，容量路径压缩失败等价于未能释放容量，retry 后仍 `capacity_exceeded` → `working_memory_full`。
- **验收**：Unit U6；Integration 构造锁占用 + 满 WM → 503 且消息未写入。

### 10.3 OI-004 局部决议（保持 open）

- **阻塞 STM-009**：**否**
- **决议**：Coordinator 侧所有 token 边界计算 **仅** 使用 Redis WM `WorkingMemoryMessage.estimated_tokens` 求和；Mongo 四字段不含 tokens；Finalize `archived_message_tokens == pending_archive_estimated_tokens`。
- **完整闭合**：仍由 **STM-010** 负责（Close 切分边界）。

### 10.4 OI-005 正式决议（`resolve_by_task: STM-006`；STM-009 补强证据）

- **阻塞 STM-009**：**否**
- **决议**：「Context Archive Service」= **memory-api 进程内** Coordinator 编排 + STM-005/006 领域服务；Kafka 生产者为 `AppState.kafka_producer`；**无**额外微服务、无新网络 Contract。
- **规格依据**：§1.2.4 事件由 Memory API 路径发布；STM-006 partial evidence。
- **闭合动作**：实现合并后在 `open_issues.md` 追加 `resolved` 记录（POST_MERGE 治理）。

---

## 11. 风险与阻塞项

| ID | 风险 | 缓解 |
|---|---|---|
| R1 | 多轮锁释放与 §1108 字面差异 | §5.0 §10 已 Planner 闭合；不改 STM-008 |
| R2 | Coordinator 选择算法复杂 | 纯函数 + 表驱动 Unit |
| R3 | Integration 依赖 compose 栈 | 与 STM-003/006 相同 fixture 模式 |
| R4 | LLM 真实调用成本 | 默认 FakeLlmClient |

**MUST_FIX（计划审批）**：**0**  
**BLOCKER**：**0**

---

## 12. Git 计划

```text
1. 独立 Plan Review → PLAN_APPROVED
2. PLAN_LANDING：main docs(plan) + feat/STM-009-compression-coordinator-message-write-api
3. Developer 实施白名单
4. Code Review → IMPLEMENTATION_RELEASE → PR
5. POST_MERGE_CLEANUP + OI-001/002 resolved 记录 + OI-005 resolved（若尚未）
```

```yaml
RELEASE_PHASE: IMPLEMENTATION_RELEASE  # 实施起
workflow_mode: NORMAL
branch: feat/STM-009-compression-coordinator-message-write-api
plan_commit: "8609f15b47a318e885fab9cd073b616863b8d5b5"
```

---

## 14. 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| STM-009 Unit | `uv run pytest tests/unit/test_compression_coordinator_service.py -q` | **PASS**（21） |
| STM-009 Contract | `uv run pytest tests/contract/test_stm009_contract.py -q` | **PASS**（10） |
| Integration Redis | `uv run pytest tests/integration/test_message_write_coordinator_redis.py -q` | **PASS**（10；Docker Redis+Mongo） |
| Integration Kafka | `uv run pytest tests/integration/test_message_write_coordinator_kafka.py -q` | **PASS**（2；Docker Redis+Kafka+Mongo；I-I mandatory） |
| Full unit | `uv run pytest tests/unit -q` | **PASS**（410） |
| Full contract | `uv run pytest tests/contract -q` | **PASS**（90） |
| Ruff | `uv run ruff check .` | **PASS** |
| Mypy | `uv run mypy src tests scripts` | **PASS** |

---

## 13. 修订记录

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-08-11 | 1.1 | Developer 实施完成；21 unit + 10 contract + 12 integration；FULL_RUFF/mypy PASS |
