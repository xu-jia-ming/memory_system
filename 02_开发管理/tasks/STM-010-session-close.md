# STM-010 Session Close

## 1. 任务信息

```yaml
task_id: STM-010
task_name: Session Close
status: planned
plan_review_round: 2
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.1 Working Memory（status active/closing；终端=Redis Key 删除）"
  - "§1.2.2 Context Archive（archive_batch_key；create/reuse；四字段 messages；§331 base_compression_version）"
  - "§1.2.3 Memory API — POST /api/v1/memory/session/{user_id}/{session_id}/close"
  - "§1.2.4 Kafka context.archive.created（关闭路径发布语义）"
  - "§1.2.6 Context Compression Trigger Strategy（关闭不受 WM 背压；关闭切分上限）"
  - "§1.2.7 Session 生命周期（关闭状态机；Pending 复用；失败恢复）"
  - "§3.23 统一 API 响应与 Request ID"
prerequisites:
  formal:
    - "STM-006 — SATISFIED（compression lock + pending Lua + Kafka publish；PR #25 MERGED）"
    - "STM-009 — SATISFIED（CompressionCoordinator + Message Write API；PR #28 MERGED）"
  implementation_reuse:
    - "STM-001 — SATISFIED（estimate_tokens；ContextSettings；WM models）"
    - "STM-002 — SATISFIED（Session 创建；路由模式）"
    - "STM-003 — SATISFIED（write_message closing 语义；不重写 Lua）"
    - "STM-004 — SATISFIED（read_working_memory_context 读快照）"
    - "STM-005 — SATISFIED（create_or_reuse_context_archive）"
    - "STM-006 — SATISFIED（acquire/release lock；publish_archive_created_event）"
    - "DEV-005 — SATISFIED（API 壳、鉴权、request_id、错误包络）"
  baseline:
    - "Authoritative baseline：main == origin/main == 22c50f29dccb586ed2a99a061ef9e92ae3595e57；working tree clean；FULL_RUFF PASS；mypy PASS"
branch: "feat/STM-010-session-close"
created_at: "2026-08-11 09:30 UTC"
updated_at: "2026-08-11 09:45 UTC"
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
  - "触碰 DEV-006 / PR #13"
  - "实现 STM-011 republish / STM-012 / STM-013 E2E"
  - "重写 STM-003–009 核心 Contract 或 STM-008 token 公式"
  - "第二套 compression coordinator / close 专用锁"
```

---

## 2. 任务目标

交付 **Session Close 状态机** + **关闭路径 Archive 协调** + **`POST /api/v1/memory/session/{user_id}/{session_id}/close` HTTP 接线**：外部 Agent 显式关闭 Session → 获取压缩锁 → 原子 `active→closing`（或 `closing` 恢复）→ 复用 Pending Archive → 将剩余消息按 `max_archive_estimated_tokens` 确定性拆分并 Mongo create/reuse → 确认全部 Archive 持久化 → 对每个 `archive_id` 发布 Kafka（失败仅日志）→ Lua 原子删除 Redis WM Keys → `finally` 释放锁 → 返回 `status=closed` 与有序 `archive_ids`。

可验证交付：

1. **领域服务**：`close_session(...)` 单一编排入口；**不**调用 `run_compression_coordination` / `run_compression_llm` / `finalize_compression`。
2. **Redis Lua**：`enter_closing`（原子 transition）、`revert_active`（早失败回滚）、`terminal_delete`（原子删 meta/messages/message_ids）。
3. **纯函数**：`split_close_suffix_batches(...)` — 关闭后缀消息按 token 上限拆分（**归档全部剩余**；**不**应用 `absolute_min_recent_messages`）。
4. **HTTP**：DEV-005 鉴权/Request ID/错误包络；同步 API（等待关闭完成或失败）。
5. **测试**：Unit 22 + Contract 10 + Integration A–R + **OI-004 专用验收用例**；含 `base_compression_version` 快照/冻结/重试复用全链路。
6. **`base_compression_version` 生命周期**：`enter_closing` 后、构建 `ClosePlan` 前自 Redis WM meta 单次快照并冻结；全部 suffix Archive create 输入取自 `ClosePlan`；禁止 Archive helper 重读 Redis。

---

## 3. 非目标（必须坚持）

- STM-011 `republish_archive_event.py`、STM-012 消费验证、STM-013 全阶段 E2E。
- Extraction / Retrieval / Embedding / LLM 压缩写回（关闭路径 **不** 跑 Finalize）。
- 重写 STM-003 `message_write.lua`、STM-006 pending Lua、STM-008 Finalize Lua、STM-009 Coordinator 内核。
- 第二套 close 专用锁、锁 heartbeat、Outbox、跨 Redis+Mongo+Kafka 伪原子事务。
- 扩展 Mongo Archive schema 写入 `estimated_tokens`。
- 在 Redis meta 引入 `status=closed`（终端语义 = **Key 已删除**；响应 `status` 字面量 `"closed"` 仅 HTTP）。
- 修改 STM-008 `archived_message_tokens` / `estimated_tokens` 公式。
- DEV-006/PR#13、TEI/SiliconFlow、EXT/RET 全链路。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `22c50f29dccb586ed2a99a061ef9e92ae3595e57` |
| `git status --short` | clean（规划轮次允许 Task Plan + progress + master_plan dirty） |
| formal STM-006, STM-009 | `completed` |
| FULL_RUFF / mypy | PASS（baseline 声明） |

### 4.2 可复用组件审计

| 组件 | 路径 | STM-010 用法 |
|---|---|---|
| `acquire_compression_lock` / `release_compression_lock` | `compression_lock_repository.py` | 关闭全程持锁；`finally` 释放 |
| `read_working_memory_context` | `context_read_service.py` | 读 messages + meta 快照 |
| `get_working_memory_meta` | `working_memory_repository.py` | 进入 closing 后读 pending；**`ClosePlan.base_compression_version` 唯一快照源**（`hash_fields_to_meta` 整数解码） |
| `create_or_reuse_context_archive` | `context_archive_service.py` | 关闭新增批次 Mongo 持久化 |
| `build_archive_batch_key` | 同上 | `session_id:first:last` |
| `publish_archive_created_event` | `archive_created_publisher.py` | 关闭路径 Kafka（**不**经 pending Lua） |
| `write_message` | `message_write_service.py` | Integration 竞态探测（**不重写**） |
| `compression_lock_key` / WM keys | `keys.py` | terminal Lua KEYS |
| DEV-005 路由模式 | `api/routes/memory_session.py` | 扩展 close 路由 |
| `SessionStatus` | `domain/enums/working_memory.py` | `active` / `closing` only |

### 4.3 当前缺失

- Session Close 领域枚举/模型/服务
- `enter_closing` / `revert_active` / `terminal_delete` Lua + Repository
- `split_close_suffix_batches` 纯函数
- `POST .../close` 路由 + Schema
- 全套 Unit / Contract / Integration 测试

### 4.4 前置任务检查

| 前置 | 状态 |
|---|---|
| STM-006, STM-009 | **SATISFIED** |
| DEV-005 | **SATISFIED** |
| OI-003 | **open** → **本 Task Plan §10.3 Planner 决议闭合** |
| OI-004 | **open** → **本 Task Plan §10.4 权威闭合（实现后验收）** |
| STM-011 | **NOT blocker**（§10.5） |

---

## 5. 实现方案

### 5.0 二十二项 Contract 闭合（Planner 权威结论）

#### 0 — `base_compression_version` 快照与冻结（§331 + §735 rule 6）

| 项 | 结论 |
|---|---|
| 规格依据 | §331（Schema 字段语义）；§735 rule 6（关闭开始时读取一次 `compression_version`）；§744–746 / §1184（`closing` 恢复重建计划 + `archive_batch_key` 复用） |
| 快照时机 | **每个 close 请求**（含 `status=closing` 恢复）：`acquire_compression_lock` → `enter_closing` **成功之后**、读取 messages / 构建 `ClosePlan` **之前** |
| 唯一数据源 | **仅** Redis WM meta `compression_version`：经既有 `get_working_memory_meta` → `hash_fields_to_meta` 整数解码（与 STM-004 codec 同路径） |
| 禁止来源 | 默认值 `0`；猜测；Mongo 推导；HTTP path/body 入参；`create_or_reuse_context_archive` 内二次 HGET；上一 Archive 的 `base_compression_version` |
| fail-closed | 字段缺失 / 非整数 / `hash_fields_to_meta` 抛错 / `compression_version < 0` → **503** `internal_error`；**不得**进入 Archive 创建 |
| `ClosePlan` 字段 | `base_compression_version: int`（`Field(ge=0)`）；构建计划时写入；**单次 ClosePlan 内不可变** |
| 适用范围 | **仅 suffix 关闭新增 Archive**（§735「后续 Archive」）；Pending Archive（§733）复用既有 Mongo 文档，**保留**压缩路径写入时的 `base_compression_version`，**不**覆写为 Close 快照值 |
| 多 suffix 批次 | 同一 `ClosePlan` 内 **全部** suffix 批次共享 **同一** `base_compression_version`；允许 0/1/N 个 suffix Archive（由 `split_close_suffix_batches` 决定）；**禁止**批次 A 用 V3、批次 B 中途重读 Redis 得 V4 |
| Archive 接线 | `create_or_reuse_context_archive(..., input=ContextArchiveCreateInput(..., base_compression_version=close_plan.base_compression_version, ...))` |
| Helper 禁令 | `session_close_service` / batch 构建 helper **不得**在循环内重读 `compression_version`；仅 `ClosePlan` 构造点读取一次 |
| 重试语义（§744–746 / §1184） | **按 attempt 新快照（方案 A）**：每次 close 请求重建 `ClosePlan` 时从当前 Redis 读取并冻结；Close 路径不调 Finalize，故 `compression_version` 在 `closing` 期间应稳定 |
| REUSED 不变性 | STM-005 `REUSED` **不覆盖**已有文档；若 `existing.base_compression_version != close_plan.base_compression_version` → **503** `internal_error` fail-closed；禁止静默 overwrite |
| 重试验收 | 首次 close 创建 suffix archive 后失败 → 第二次 close `REUSED` 同 `archive_batch_key` → Mongo `base_compression_version` **不变**、与首次一致 |

**编排插入点（§5.3 Step 4 权威序）**

```text
acquire_lock → enter_closing → snapshot meta.compression_version → ClosePlan.base_compression_version
  → read messages/meta → build batches → mongo create/reuse → kafka → terminal → release
```

#### 1 — HTTP Contract（§651–675 + §3.23 + DEV-005）

| 项 | 结论 |
|---|---|
| Method / Path | `POST /api/v1/memory/session/{user_id}/{session_id}/close` |
| Path 参数 | `user_id`、`session_id`（与 STM-002/003 一致；身份校验） |
| Request Body | **无**（规格未定义 body；不得私增） |
| Auth | `X-API-Key` → `require_memory_api_key` |
| Success Response | `CloseSessionResponse`：`session_id: str`, `archive_ids: list[str]`, `status: Literal["closed"]` |
| Success HTTP | **200**（与 Session Create / Message Write 同步成功模式一致；规格流程图为同步阻塞，**无** 202/polling） |
| 空关闭 | 无剩余消息且无 Pending → `archive_ids=[]`, `status=closed` |
| Request ID | `RequestIdMiddleware`；Header `X-Request-ID`；错误 Body `request_id` |
| 错误包络 | `AppError` + `build_error_body`（§3.23） |

**HTTP 错误映射（Close 专用）**

| 条件 | HTTP | `error.code` | 规格依据 |
|---|---|---|---|
| 缺失/无效 API Key | 401 | `unauthorized` | DEV-005 |
| Path 参数非法 | 422 | `validation_error` | §3.23 |
| Session Key 不存在（含终端后重复 close） | 404 | `session_not_found` | §731 |
| `status=closing` 恢复执行 | — | **非错误**；HTTP 200 `closed` 或 503 `close_incomplete` | §730 |
| 锁未获取（其他持有者占用） | 503 | `internal_error` | §3.23 503 基础设施/暂时失败；**未**进入 closing |
| Mongo/内部不可恢复错误（早失败可回滚） | 503 | `internal_error` | §3.23 |
| Redis 终端删除失败或结果不可确认 | 503 | `close_incomplete` | §750–751；**OI-003 决议 §10.3** |
| 未预期内部错误 | 503 | `internal_error` | §3.23 |

**禁止**：`closing` 重复 close 返回 409；将 `session_closing` 作为 Close 成功 `status`。

#### 2 — Session 状态机（§184 + §651–755 + §1182–1185）

| 状态 | 存储 | 合法转移 |
|---|---|---|
| `active` | Redis meta `status` | → `closing`（原子 Lua）；→ 终端（删 Key） |
| `closing` | Redis meta `status` | → `active`（**仅**早失败 Lua）；→ 终端（删 Key） |
| 终端 | **Redis Key 不存在** | 无；HTTP 响应 `status="closed"` |

**禁止**：Redis meta `status=closed`；禁止 invent 第四状态值。

**关闭失败保持 `closing`**：一旦满足 §742–746（至少一个关闭新增 Archive 已持久化，或全部 Archive 已确认持久化），**不得**回滚 `active`。

**Close 失败可回滚 `active`**：仅当 **尚未** 持久化任何关闭新增 Archive，且 **尚未** 进入「全部 Archive 已确认持久化」阶段（§737–741）。关闭开始前已存在的 Pending **不** 计为关闭新增。

#### 3 — Write-vs-close 竞态（§755 + STM-003）

| 项 | 结论 |
|---|---|
| 机制 | STM-003 Lua：`status != active` → `session_closing`；**不重写** Lua |
| Close 后写入 | HTTP 409 `session_closing`（STM-009 既有映射） |
| 竞态语义 | Lua 串行：写入先执行 → 消息进入待归档；`closing` 先执行 → 写入拒绝；**无**「读后写」撕裂 |
| 验收 | Integration **I-M**：并发 write-vs-close；证明无漏消息、无 close 后写入、无 archive 边界撕裂 |

#### 4 — Enter-closing 原子 transition（§728–730）

| 项 | 结论 |
|---|---|
| 需要独立 Lua | **是** — `session_close_enter.lua` |
| 原子操作 | EXISTS meta → 身份 `user_id/session_id` 匹配 → `status==active` 则 HSET `closing` + `updated_time`；`status==closing` 则幂等成功；否则 `session_not_found` / `invalid_session_state` |
| 禁止 | GET→Python→HSET TOCTOU |
| 调用时机 | 成功 `acquire_compression_lock` **之后**、读消息/建计划 **之前** |

#### 5 — 既有 Pending 压缩（§733–734 + STM-006/008/009）

| 场景 | 关闭行为 | STM-011 |
|---|---|---|
| A) pending + Kafka 已发 | 复用 Mongo Archive；含于 `archive_ids`；Close **不** Finalize | 非必须 |
| B) publish failed/unknown | 同 A；Close 仍发布 Kafka（at-least-once 可重复） | 可选补发；**非 blocker** |
| C) LLM 未完成 | 同 A；**不**等待 LLM；**不**调用 Finalize | 非必须 |
| D) Finalize 未知/未完成 | 同 A；头部消息仍在 Redis List；Close 归档计划含 pending 覆盖范围 | 非必须 |

**Pending `base_compression_version`**：复用 Mongo 既有值（压缩路径创建时写入）；**不**使用 `ClosePlan.base_compression_version` 覆写；仍计入 `archive_ids` 有序列表。

**权威结论**：Close 正确性 **不** 依赖 STM-011；Kafka `publish_failed` 按 §747–748 **仅日志**，不阻止 Redis 删除（与 STM-009 压缩路径不同）。

#### 6 — Final compression 需求（§1183 + §702–714）

| 项 | 结论 |
|---|---|
| Close 是否强制 LLM 压缩 | **否** — 关闭路径 **归档原始消息** 到 Mongo，**不** 更新 `compressed_context` |
| 协调器 | **不** 使用 `run_compression_coordination` |
| 原语 | STM-004 读 + STM-005 create/reuse + `publish_archive_created_event` |
| 低于 `compression_trigger_tokens` | **仍** 归档全部剩余消息（按 `max_archive_estimated_tokens` 拆分） |
| Pending 存在 | 复用 Pending Archive；**不** 再跑一轮 compression |

#### 7 — 剩余消息选择 / OI-004 核心（§734–736 + §1183）

| 项 | 结论 |
|---|---|
| 头部 | 若 `pending_archive_id != ""`：复用 Pending，覆盖 List 头部 `pending_archive_message_count` 条 |
| 后缀 | Pending 之后 **全部** 剩余消息，按 Redis List 顺序 |
| 拆分上限 | `context.max_archive_estimated_tokens`；**按消息边界**；**不得** 拆分单条消息 |
| `absolute_min_recent_messages` | **不适用**于 Close（仅普通压缩 §1114–1117） |
| 空 Session | `messages=[]` 且无 Pending → 零 Archive；直接终端删除 |
| 未归档消息 | 成功 close **不得** 遗留未进入某 Archive 的 WM 消息 |
| 边界未闭合 | **MUST_FIX** — 实现须 fail-closed + 测试证明 |

#### 8 — OI-004 闭合映射（§10.4）

见 §10.4 逐项映射；本计划 **证明** 全部 criteria 可在 STM-010 验收。

#### 9 — Token accounting（§734 + STM-008 公式边界）

| 项 | 结论 |
|---|---|
| 批次 token 和 | **仅** Redis `WorkingMemoryMessage.estimated_tokens` 精确求和 |
| Pending 批次 | 使用 meta `pending_archive_estimated_tokens`（STM-006 写入时即 Redis 和） |
| 禁止 | 从 Mongo `content` 重算 token 做切分边界 |
| Finalize 公式 | Close **不** 调用 Finalize；in-flight compression 在 Close 时 **放弃** LLM/Finalize（§6 非目标） |

#### 10 — 空 Session / 无消息（§676–677）

`active` + `messages=[]` + 无 Pending → `archive_ids=[]`；执行 terminal Lua；HTTP 200 `closed`；**不** 创建空 `context_archive`。

#### 11 — 已 `closing` 重复 close（§730）

| 项 | 结论 |
|---|---|
| 语义 | **恢复** 上次未完成关闭；**非** 409 |
| 幂等 | 重建确定性拆分计划；`archive_batch_key` 复用；**无** 重复 create 覆盖相同消息范围 |
| 部分完成 + 客户端未收响应 | 重试 close → 继续至 `closed` 或 `close_incomplete` |
| 禁止 | 重复 terminal 删导致双版本 bump / 双 trim（Close 无 trim） |

#### 12 — 已终端重复 close（§731）

Redis 已删 → `session_not_found` HTTP 404；文档化 MVP 已知限制；调用方查 Mongo Archive。

#### 13 — Close 期间失败语义（§737–746）

| 失败类型 | Session 状态 | 说明 |
|---|---|---|
| `lock_not_acquired` | 保持 `active`（未 enter closing） | 503 `internal_error` |
| malformed `compression_version`（§5.0 #0） | 保持 `active` 或 `closing`（视是否已过 enter） | 503 `internal_error`；无 Archive 创建 |
| Mongo create 失败（早阶段） | 可 `revert_active` | 503 `internal_error` |
| Kafka `publish_failed` | 保持 `closing`（若已过早失败门） | 继续 Redis 删除（§747） |
| LLM/Finalize | **不适用**（Close 不调） | — |
| `version_conflict` / `pending_conflict` | **不适用**（Close 不调 Finalize/pending Lua 写） | — |
| `message_boundary_mismatch` | 保持 `closing` | 503 `internal_error`；人工恢复 |

**禁止**：压缩/Finalize 完成前标记 `closed`（Close 路径无此步骤）；Archive 未全持久化前 terminal 删除。

#### 14 — Kafka publish_failed during close（§747–748 + §1126 对照）

与 STM-009 压缩路径 **不同**：Close **允许** `publish_failed` 后继续 terminal 删除；仅 structlog 记录；**不** 改 AT_LEAST_ONCE；STM-011 可选补发。

#### 15 — Lock lifecycle（§727 + §1186）

| 项 | 结论 |
|---|---|
| 锁 | 复用 STM-006 `memory:compression:lock:{user_id}:{session_id}` |
| 流程 | acquire → enter_closing → … → terminal_delete → `finally` release |
| 第二把锁 | **禁止** |
| 多轮过期 | 长 close 若 TTL 过期：重试 close 恢复；**无** heartbeat（规格未定义） |
| pending Lua | Close **不** 调用 `prepare_pending_archive_and_publish` |

#### 16 — 原子终端 transition（§748–752 + §1186）

| 项 | 结论 |
|---|---|
| 前置（Python 层） | 全部计划内 Archive 已在 Mongo 确认（create/reuse 成功）；Kafka 已 **尝试** 发布（失败不阻塞） |
| Lua | `session_close_terminal.lua`：校验 `status=closing` + 身份 → DEL meta + messages List + message_ids Set |
| 禁止 | Python 逐 Key DEL 留窗口；terminal 前 DEL pending 字段但保留 messages |
| Lock | terminal 在持锁下执行；之后 `finally` release |

#### 17 — Cleanup 语义（§752–753）

成功 terminal 后：三 Key **全部** 不存在；Pending 字段随 meta 删除；**无** 孤立 messages/message_ids。

#### 18 — Close vs Archive 耐久性顺序（§706–720）

```text
enter_closing → snapshot compression_version → ClosePlan(base_compression_version frozen)
  → 读快照 → 构建确定性计划
  → Mongo create/reuse（全部批次；suffix 用 ClosePlan.base_compression_version）
  → 确认全部持久化
  → Kafka publish（每 archive_id；失败仅日志）
  → terminal Lua 删 Redis
  → release lock
  → HTTP 200 closed
```

**无** 跨系统原子事务声明；合法中间态可恢复。

#### 19 — Crash/retry 表（§742–751）

| 阶段 | 持久态 | 重试动作 | 重复风险 | Recovery owner |
|---|---|---|---|---|
| active→closing 前 crash | `active` | 重试 close | 无 | Client close |
| enter closing 后、无新 Archive | `closing` | close 恢复或 `revert_active`（若失败点允许） | 无 | Client close |
| 新 Archive 已 Mongo、pending 未写 | `closing` | close 恢复；batch_key 复用 | 无 duplicate doc | Client close |
| pending committed（压缩路径）+ Close 交叉 | `closing` + pending | Close 复用 pending archive | Kafka 重复 | Client close；STM-011 可选 |
| Mongo 部分批次成功 | `closing` | close 重建计划；已存在 batch 复用 | 无新 doc | Client close |
| Kafka published unknown | `closing` | close 继续；可能重复 publish | at-least-once | STM-011 可选 |
| LLM failed（压缩 in-flight） | `closing` | Close 跳过 LLM | — | Client close |
| Finalize committed、terminal 未 | `closing` + pending 或 已 trim | Close 复用/归档剩余 | — | Client close |
| terminal committed、响应未送达 | **终端** | close → 404 `session_not_found` | 无 Redis 状态 | Client 查 Archive |
| terminal 失败 | `closing` | close → `close_incomplete` | batch_key 复用 | Client close |

#### 20 — STM-011 交互（§10.5）

Close 可在 STM-009 `publish_failed` 语义下完成；**STM-011 NOT prerequisite blocker**。

#### 21 — HTTP 延迟（§479 对照 + §651–723）

| 项 | 结论 |
|---|---|
| 模式 | **同步** — 等待归档 + Kafka 尝试 + terminal 删除 |
| 成功 | HTTP 200 + `status=closed` |
| 部分完成 | HTTP 503 + `close_incomplete`；Session 保持 `closing` |
| 异步 | **无** 202 / polling Contract |

---

### 5.1 关闭后缀拆分算法（权威伪代码）

```python
def split_close_suffix_batches(
    messages: list[WorkingMemoryMessage],
    max_archive_estimated_tokens: int,
) -> list[list[WorkingMemoryMessage]]:
    """Archive ALL suffix messages; split only by max_archive cap; never split one message."""
    if not messages:
        return []
    batches: list[list[WorkingMemoryMessage]] = []
    current: list[WorkingMemoryMessage] = []
    current_tokens = 0
    for message in messages:
        t = message.estimated_tokens
        if t > max_archive_estimated_tokens:
            raise SingleMessageExceedsArchiveCapError(...)  # fail-closed; config 应保证 max_message < max_archive
        if current and current_tokens + t > max_archive_estimated_tokens:
            batches.append(current)
            current = [message]
            current_tokens = t
        else:
            current.append(message)
            current_tokens += t
    if current:
        batches.append(current)
    return batches
```

**与 Coordinator `select_archive_prefix` 区别**：无 `preferred_recent`/`absolute_min`/`compression_target`；**穷尽**后缀。

### 5.2 Close 编排核心 API（建议）

```python
class ClosePlan(BaseModel):
    """Deterministic close plan; built once per close attempt after enter_closing."""
    session_id: str
    user_id: str
    base_compression_version: int  # frozen at plan build; ge=0; sole source for suffix archives
    batches: list[CloseArchiveBatch]  # pending reuse + suffix splits
    # ... other deterministic fields as needed

class CloseArchiveBatch(BaseModel):
    archive_batch_key: str
    messages: list[WorkingMemoryMessage]
    is_pending_reuse: bool  # True → skip create; reuse pending_archive_id
    # suffix batches: base_compression_version always from parent ClosePlan

class SessionCloseResult(BaseModel):
    session_id: str
    archive_ids: list[str]
    status: Literal["closed"]

class SessionCloseIncompleteError(Exception):
    """Maps to HTTP 503 close_incomplete."""

async def close_session(
    *,
    redis, mongodb, kafka_producer, settings,
    user_id: str,
    session_id: str,
    request_id: str | None = None,
    clock: Clock | None = None,
) -> SessionCloseResult: ...
```

**`build_close_plan` 伪代码（`base_compression_version` 权威）**

```python
async def build_close_plan(...) -> ClosePlan:
    meta = await get_working_memory_meta(redis, user_id, session_id)
    if meta is None:
        raise SessionNotFoundError(...)
    try:
        base_version = meta.compression_version
    except (ValueError, KeyError) as exc:
        raise MalformedWorkingMemoryMetaError(...) from exc
    if base_version < 0:
        raise MalformedWorkingMemoryMetaError(...)
    # freeze — no further Redis reads of compression_version in this attempt
    frozen = base_version
    # ... read messages, pending, split_close_suffix_batches ...
    return ClosePlan(
        session_id=session_id,
        user_id=user_id,
        base_compression_version=frozen,
        batches=batches,
    )

async def persist_suffix_batch(close_plan: ClosePlan, batch: CloseArchiveBatch) -> ContextArchiveResult:
    return await create_or_reuse_context_archive(
        mongodb=mongodb,
        input=ContextArchiveCreateInput(
            user_id=close_plan.user_id,
            session_id=close_plan.session_id,
            archive_batch_key=batch.archive_batch_key,
            base_compression_version=close_plan.base_compression_version,  # NOT live Redis
            messages=batch.messages,
        ),
    )
```

### 5.3 实现步骤

**Step 1 — Domain enums/models**

- `domain/enums/session_close.py`：`SessionCloseEnterStatus`（lua 返回映射）
- `domain/models/session_close.py`：`ClosePlan`（**含 `base_compression_version: int`**）、`CloseArchiveBatch`、`SessionCloseResult`、内部进度标记

**Step 2 — Redis Lua + Repository**

- `scripts/session_close_enter.lua`
- `scripts/session_close_revert_active.lua`
- `scripts/session_close_terminal.lua`
- `infrastructure/redis/session_close_repository.py`：注册脚本 + 薄封装

**Step 3 — 纯函数**

- `split_close_suffix_batches` in `session_close_service.py` 或 `domain/services/session_close_split.py`

**Step 4 — Session close service**

- `domain/services/session_close_service.py`：§5.0 编排；`build_close_plan` 在 `enter_closing` 后单次快照 `meta.compression_version` → `ClosePlan.base_compression_version`；`CloseProgress` 跟踪「关闭新增 Archive 已持久化」「全部 Archive 已确认」
- suffix `create_or_reuse_context_archive`：**仅** `close_plan.base_compression_version`；`REUSED` 时校验 `existing.base_compression_version` 匹配，否则 fail-closed
- **禁止**在 batch 循环或 Archive helper 内 HGET `compression_version`

**Step 5 — HTTP**

- 扩展 `api/schemas/memory_session.py`：`CloseSessionResponse`
- 扩展 `api/routes/memory_session.py`：`POST /session/{user_id}/{session_id}/close`

**Step 6 — 测试**

- 见 §8

---

## 6. 文件变更清单（实施白名单）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/enums/session_close.py` | 创建 | Lua 状态枚举 |
| `src/memory_system/domain/models/session_close.py` | 创建 | Close 计划/结果模型 |
| `src/memory_system/domain/services/session_close_service.py` | 创建 | 关闭编排 |
| `src/memory_system/infrastructure/redis/scripts/session_close_enter.lua` | 创建 | 原子 active→closing |
| `src/memory_system/infrastructure/redis/scripts/session_close_revert_active.lua` | 创建 | 早失败回滚 active |
| `src/memory_system/infrastructure/redis/scripts/session_close_terminal.lua` | 创建 | 原子删 WM Keys |
| `src/memory_system/infrastructure/redis/session_close_repository.py` | 创建 | Lua 注册/调用 |
| `src/memory_system/api/schemas/memory_session.py` | 修改 | Close 响应 Schema |
| `src/memory_system/api/routes/memory_session.py` | 修改 | Close HTTP 路由 |
| `tests/unit/test_session_close_split.py` | 创建 | 后缀拆分纯函数 |
| `tests/unit/test_session_close_service.py` | 创建 | 编排 Unit |
| `tests/unit/test_session_close_status_mapping.py` | 创建 | HTTP/Lua 映射 |
| `tests/contract/test_stm010_contract.py` | 创建 | HTTP Contract |
| `tests/integration/test_session_close_redis.py` | 创建 | Redis/Mongo/Kafka Integration |
| `02_开发管理/tasks/STM-010-session-close.md` | 创建/修改 | 本计划 |
| `02_开发管理/progress.md` | 修改 | 规划态字段 |
| `02_开发管理/master_plan.md` | 修改 | STM-010 登记 |
| `02_开发管理/open_issues.md` | 修改 | OI-003/OI-004 决议（条件满足） |

**禁止修改（除非 Plan Amendment 批准）**：`message_write.lua`、`compression_finalize.lua`、`pending_archive_write.lua`、`compression_coordinator_service.py` 核心语义、`compression_finalize_service.py` token 公式、STM-003–009 已交付测试语义。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | Redis 内原子 | `enter_closing` / `revert_active` / `terminal_delete` 各为单 Lua；跨 Mongo/Kafka **无** 原子事务 |
| 幂等 | Close 恢复幂等 | `archive_batch_key` create/reuse；`closing` 重试不双建同范围 Archive；terminal 后 Redis 无状态 |
| 并发 | 锁 + Lua 串行 | 与压缩互斥；write-vs-close 由 STM-003 + enter_closing 序保证 |
| 版本冲突 | 关闭路径不参与 Finalize `version_conflict` | suffix Archive 写入 `ClosePlan.base_compression_version`（§735）；`REUSED` 不匹配 → fail-closed |
| `base_compression_version` | 单次 ClosePlan 冻结；suffix 全批次同值 | §5.0 #0；禁止 mid-close 重读 Redis；Pending 保留原值 |
| 用户隔离 | `user_id` 路径 + meta 身份校验 | 与 STM-003 相同 fail-closed |
| 部分失败 | 分阶段门控 | 早失败可 `revert_active`；过门后保持 `closing`；删 Redis 失败 → `close_incomplete` |
| 进程异常恢复 | Client 重试 close | §5.0 #19 表；STM-011 仅补 Kafka |

---

## 8. 测试计划

### 8.1 Unit — Session Close（22 场景，权威）

| # | 场景 | 预期 |
|---|---|---|
| U-base-1 | `meta.compression_version=7` → `build_close_plan` | `ClosePlan.base_compression_version == 7` |
| U-base-2 | suffix archive create 输入 | `ContextArchiveCreateInput.base_compression_version == close_plan.base_compression_version` |
| U-base-3 | `ClosePlan` 构建后 Redis `compression_version` 变更（mock） | suffix create 仍用原冻结值 `7`，非新值 |
| U1 | Happy path：有消息无 pending | `closed`；Mongo archives；Redis 空；有序 `archive_ids` |
| U2 | 空 Session | `archive_ids=[]`；terminal 删；200 `closed` |
| U3 | `session_not_found` | 404；无 mutation |
| U4 | `closing` 重试恢复 | 继续完成；非 409 |
| U5 | 终端后重复 close | 404 `session_not_found` |
| U6 | 有剩余消息的最终归档 | 全部后缀进 Archive |
| U7 | 低于 `compression_trigger_tokens` 仍归档 | 不调用 Coordinator |
| U8 | 存在 pending（Kafka 已发模拟） | 复用 pending；不重复归档头部 |
| U9 | Kafka publish_failed | 仍 `closed`；日志；Redis 删 |
| U10 | LLM 失败态（pending 存在） | Close 完成；不调 LLM |
| U11 | Finalize 失败态（pending 存在） | Close 完成；不调 Finalize |
| U12 | `lock_not_acquired` | 503；`active` 保持 |
| U13 | Finalize 后模拟 + close | terminal 成功 |
| U14 | OI-004 token boundary | 批次 token 和 = Redis 精确和 |
| U15 | 精确消息集合 | Archive messages == Redis 子序列 |
| U16 | 无 double archive/finalize | 重试 close batch_key 复用 |
| U17 | Crash-after-finalize 恢复 | `closing` 重试 → `closed` |
| U18 | `split_close_suffix_batches` 边界 | 单批/多批/空 |
| U19 | `revert_active` 早失败路径（SF-1） | **仅**允许回滚点：`status→active`；`updated_time` 按 contract 更新；**不**破坏已持久化 archive / pending；**不** revert 终端 session |
| U20 | 多 suffix 批次同 `base_compression_version` | 2+ suffix batch → 全部 create 输入 `base_compression_version` 相同 |
| U21 | `REUSED` 版本不匹配 | 已有 archive `base_compression_version=3`，`ClosePlan=7` → fail-closed 503；无 overwrite |
| U22 | malformed `compression_version`（缺失/非整数/负） | fail-closed 503；无 Archive 创建 |

### 8.2 Contract — HTTP

| # | 场景 | 预期 |
|---|---|---|
| C1 | `POST /api/v1/memory/session/{user_id}/{session_id}/close` 存在 | 路由注册 |
| C2 | 无 API Key | 401 |
| C3 | 非法 path 参数 | 422 |
| C4 | `X-Request-ID` | Header + 错误 body |
| C5 | 成功包络 | 三字段；`status=closed` |
| C6 | `session_not_found` | 404 |
| C7 | `closing` 重试 | 200 或 503 `close_incomplete`；非 409 |
| C8 | 终端重复 | 404 |
| C9 | `close_incomplete` | 503 + code 字面量 |
| C10 | 身份错配（SF-3）：`user_A`/`session_X` 存在，close `user_B`/`session_X` | 404 `session_not_found`（或规格等价）；**ZERO_SIDE_EFFECT**：无 `closing`、无 archive、无 Kafka、无 Redis delete |

### 8.3 Integration — A–R（Fake Kafka；真实 Redis/Mongo）

| ID | 场景 | 预期 |
|---|---|---|
| I-A | Close 完整路径 | `closed`；Redis 三 Key 不存在 |
| I-B | Close 后 write | 409 `session_closing` |
| I-C | Mongo messages 四字段精确 | 与 Redis 一致 |
| I-D | Token sum 精确 | `sum(estimated_tokens)` |
| I-E | 无 Finalize 路径 accounting | pending 批次 token = meta 字段 |
| I-F | Pending cleared | terminal 后无 Redis |
| I-G | Lock released | `finally` 后 lock key 不存在 |
| I-H | WM 终端态 | meta/messages/message_ids 全删 |
| I-I | 空 Session close | `archive_ids=[]` |
| I-J | `closing` 重试幂等 | 无 duplicate archive doc |
| I-K | 并发 write-vs-close | §5.0 #3 |
| I-L | LLM fail 可恢复 close | pending 存在 → close 成功 |
| I-M | Kafka fail 语义 | `closed`；publish_failed 日志 |
| I-N | Crash 模拟重试 | 中断后 close 恢复 |
| I-O | `base_compression_version` 精确值 | close 开始时 `compression_version=V` → 每个 **suffix** Mongo archive `base_compression_version==V`（精确相等，非仅字段存在） |
| I-P | suffix 重试 REUSED 不变 | 首次 close 创建 suffix archive 后 terminal 前失败；第二次 close `REUSED` → `base_compression_version` 与首次相同、无 overwrite |
| I-Q | `closing` 阻塞普通压缩（SF-2） | `status=closing` 时 Message Write API 触发压缩 → `session_closing` / 压缩 blocked；**不**影响 close 恢复路径 |
| I-R | close 恢复 vs 普通压缩区分（SF-2） | 同一 session `closing` 状态下 `POST .../close` 恢复执行成功或 `close_incomplete`；**非** 409；证明 close recovery ≠ ordinary compression |

### 8.4 OI-004 专用验收（Integration **OI4**）

构造 Redis messages `M1..Mn`，`estimated_tokens` 已知且各异；执行 close；断言：

1. 每个 Archive 文档 messages 集合 = 计划子序列；
2. 各批次 Mongo 消息与 Redis `estimated_tokens` 一致；
3. 后缀批次 token 和 = `sum(message.estimated_tokens)`（**非** content 重算）；
4. Pending 批次（若有）使用 `pending_archive_estimated_tokens`；
5. 全部消息恰好覆盖一次（边界闭合）。

### 8.5 E2E Test

**本任务非目标** — 全链路 E2E 归属 STM-013。

### 8.6 失败注入与并发

| 场景 | 预期 |
|---|---|
| Mongo insert 失败（早阶段） | `revert_active` 或保持 `closing` 按门控 |
| terminal Lua 返回失败 | 503 `close_incomplete`；`closing` 保持 |
| 并发双 close | 锁互斥；一单成功一单 503 lock |
| Lock TTL 过期后重试 | `closing` 恢复完成 |

---

## 9. 验收标准

- [ ] `POST /api/v1/memory/session/{user_id}/{session_id}/close` 符合 §651–675 与 §10.3 HTTP 映射
- [ ] `active→closing` 原子 Lua；**无** Redis `status=closed`
- [ ] 终端 = Redis 三 Key 删除；响应 `status=closed`
- [ ] **不**调用 `run_compression_coordination` / LLM / Finalize
- [ ] 后缀 **全部** 归档；`absolute_min_recent_messages` **不** 应用于 Close
- [ ] Token 边界 **仅** Redis `estimated_tokens` 求和（OI-004 验收 **OI4**）
- [ ] `closing` 重试恢复；终端重复 404；**非** 409 closing 冲突
- [ ] Kafka `publish_failed` 不阻止 terminal（§747）
- [ ] STM-011 **非** 前置 blocker
- [ ] `base_compression_version`：§5.0 #0 快照/冻结/后缀同值/REUSED 校验；U-base-1/2/3、I-O、I-P 通过
- [ ] `revert_active` 仅早失败 approved 路径（U19）；身份错配 ZERO_SIDE_EFFECT（C10）
- [ ] `closing` 阻塞普通压缩、不阻塞 close 恢复（I-Q、I-R）
- [ ] Unit 22 + Contract 10 + Integration A–R + OI4 通过
- [ ] `uv run ruff check .` + `uv run mypy src tests scripts` PASS
- [ ] 白名单外无改动；无 TODO/pass/空实现

---

## 10. 风险与阻塞项

### 10.1 设计文档冲突

- 无未决议冲突；OI-003/OI-004 由本计划 §10.3/§10.4 闭合。

### 10.2 当前代码冲突

- 无 Session Close 实现；与规格一致（缺失待补）。

### 10.3 OI-003 决议（`resolve_by_task: STM-010`）

- **问题**：`close_incomplete` HTTP 状态码未在 §1 写死。
- **Planner 决议**：`close_incomplete` → HTTP **503** + `error.code=close_incomplete`；语义为 Redis 终端删除失败或结果不可确认；Session 保持 `closing`；客户端可安全重试 close。
- **规格依据**：§750–751（错误码）；§3.23 表「503 = 基础设施不可用或外部依赖暂时失败」；与 `working_memory_full` 同类可重试 503，**非** 409。
- **验收**：Contract C9；Integration terminal 失败注入。

### 10.4 OI-004 决议（`resolve_by_task: STM-010`）

**权威 resolution criteria 与 STM-010 映射：**

| # | Criteria | STM-010 满足方式 | 验收 |
|---|---|---|---|
| 1 | Mongo Archive messages 仅四字段（无 `estimated_tokens`） | 复用 STM-005；Close 不写第五字段 | I-C |
| 2 | 切分/选择 token 来源 = Redis WM | `split_close_suffix_batches` + pending meta 字段 | U14, I-D, OI4 |
| 3 | 禁止 Mongo content 重算做边界 | 服务层 **禁止** `estimate_tokens(content)` 用于切分 | Unit + OI4 |
| 4 | `archived_message_tokens` 等价 Redis 精确和 | Close 不调 Finalize；批次和写入 Mongo 前由 Redis 消息求和校验 | OI4 |
| 5 | Final archive 边界闭合 | 后缀 **全部** 消息进 Archive；terminal 前无遗漏 | U6, U15, OI4 |
| 6 | Finalize token accounting 一致性 | Close 路径无 Finalize；in-flight compression 由 Close 整体归档放弃压缩写回 | I-L |
| 7 | Post-close token 无歧义 | Redis 删除；无 meta `estimated_tokens` 残留 | I-A, I-H |

**结论**：STM-010 实现 + OI4 测试 **闭合** OI-004；不得在 STM-010 之前标记 resolved。

### 10.5 STM-011 交互

- **非 BLOCKER**：Close 完整性由 `archive_batch_key` 复用 + at-least-once Kafka + 可选 STM-011 补发保障萃取，**不** 阻塞 Close API 交付。

### 10.6 其他风险

| ID | 级别 | 描述 | 缓解 |
|---|---|---|---|
| R1 | SHOULD_FIX | 单消息 token > `max_archive_estimated_tokens` | 配置链 `max_message < max_archive`；fail-closed |
| R2 | SHOULD_FIX | 长 close 锁 TTL 过期 | 客户端重试 `closing` 恢复；不实现 heartbeat |
| R3 | 已知限制 | terminal 后重复 close → 404 | 文档化 §731 |

**BLOCKER**：无。**MUST_FIX**：无（Round 2 已闭合 MF-1 `base_compression_version`）。

---

## 11. Git 计划

```yaml
branch: "feat/STM-010-session-close"
pr_sizing: "single PR, medium-sized scoped change"  # SF-4：非 tiny/minimal；白名单精确不变
expected_commits:
  - "docs(plan): add STM-010 session close plan"
  - "feat(stm): add session close state machine and API"
out_of_scope_changes:
  - "STM-011 republish 脚本"
  - "STM-013 E2E"
  - "STM-003/006/008 Lua 语义变更"
  - "Compression Coordinator 第二套逻辑"
  - "DEV-006 / PR #13"
```

---

## 12. Plan Amendment

### Amendment 001 — Round 2 PLAN REMEDIATION（MF-1 + SF-1–SF-4）

| ID | 来源 | 修订 |
|---|---|---|
| MF-1 | Plan Reviewer R1 MUST_FIX | 新增 §5.0 #0 `base_compression_version` 全生命周期；`ClosePlan.base_compression_version`；§5.2/§5.3 接线；U-base-1/2/3、I-O、I-P、U20–U22；重试方案 A + REUSED 不变性 |
| SF-1 | SHOULD_FIX | U19 `revert_active` 早失败专用 Unit |
| SF-2 | SHOULD_FIX | I-Q/I-R：`closing` 阻塞普通压缩、不阻塞 close 恢复 |
| SF-3 | SHOULD_FIX | C10 身份错配 ZERO_SIDE_EFFECT Contract |
| SF-4 | SHOULD_FIX | §11 `pr_sizing: single PR, medium-sized scoped change` |

`plan_review_round: 2`；Round 1 已批准决策（HTTP 200/503、Redis 终端删 Key、`closing` 恢复非 409、无 Coordinator/LLM/Finalize、suffix 全归档、OI-003/004、STM-011 非 blocker）**保持不变**。

计划批准后如需进一步修改，新增 Amendment 记录，禁止覆盖原计划。

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
|  |  |  |  |  |

---

## 14. 实际执行结果

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
