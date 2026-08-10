# STM-003 Message Write Lua

## 1. 任务信息

```yaml
task_id: STM-003
task_name: Message Write Lua
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.1 Redis Working Memory 数据结构设计（消息 List/Set、Token 规则、写入 Lua 原子语义）"
  - "§1.2.3 Memory API 接口定义（写入消息 Request/校验规则；duplicate/capacity 流程图摘录）"
  - "§1.2.6 Context 配置阈值（max_message / max_working_memory / compression_trigger 区分）"
  - "§1.2.7 Session 生命周期（status=active 方可写入；session_not_found 语义参照）"
prerequisites:
  - "STM-001 — SATISFIED（`estimate_tokens()`、`WorkingMemoryMessage`、Key helpers、`ContextSettings` 已在 main；PR #19 MERGED）"
  - "STM-002 — SATISFIED（Session 创建 + WM meta Hash repository/codec 已在 main；PR #20 MERGED）"
  - "规划基线（本轮只读）：main @ 033e05ac23acd72f17458cdb701ddc37d28799bf；working tree clean；STM-002 后 full unit 269 / contract 59 / ruff PASS / mypy PASS"
  - "本任务不需要 SiliconFlow / LLM / TEI / Mongo / Kafka / ES / Neo4j 网络调用"
branch: "feat/STM-003-message-write-lua"
created_at: "2026-08-10 04:17 UTC"
updated_at: "2026-08-10 14:20 UTC"
approval_gates:
  planning_docs: "pending Plan Review → READY_FOR_PLAN_REVIEW；本轮不得 PLAN_APPROVED / 不得实施"
  implementation_plan: "status=committed；implementation_commit e1913d17b159d426aadfd54d32e07c84ea61043a；PR #21 OPEN；next_action=Human PR merge"
```

### 1.1 编排与门禁（本轮）

```yaml
start_existing_task: true
phase: planning_only
human_gate_after_plan_review: true
must_not_this_round:
  - "进入 Developer / 编写业务实现或测试语义"
  - "Git 写（add/commit/push/merge/rebase/force）"
  - "输出 PLAN_APPROVED 或自行批准"
  - "触碰 DEV-006 / PR #13"
  - "实现 HTTP 写入路由、压缩 Coordinator、Kafka、STM-004+"
```

---

## 2. 任务目标

交付 **领域层消息写入服务 + Redis 单 Lua 原子脚本**（不含 HTTP 路由与压缩协调），使 STM-009 可接线 `POST /api/v1/memory/working/message`：

1. **消息输入契约**（§1.2.3 Request + §1.2.1 规则 3/5）：`user_id`、`session_id`、`message_id`（客户端 UUID v4）、`role`、`content`、可选 `timestamp`；**不**接受客户端 `estimated_tokens`；Python 在调用 Lua **之前**用 STM-001 `estimate_tokens(content)` 计算整型并写入消息 JSON。
2. **Session 校验内部语义**：meta Key 缺失 / Hash 字段与请求 `user_id`/`session_id` 不一致 → `session_not_found`；`status != active`（含 `closing`）→ `session_closing`；**本任务不定义 HTTP 映射**（STM-009 负责）。
3. **`message_id` 幂等**（§1.2.1 规则 3）：首次写入 → `success`；同 `message_id` 已存在于 Set → `duplicate`；**零副作用**（List、Set、`estimated_tokens`、`updated_time` 均不变）。
4. **容量契约分离**：
   - **单条消息**：`estimate_tokens(content) > context.max_message_estimated_tokens` → 内部 `message_too_large`；**不调用 Lua**；不得写 Redis（§1.2.1 规则 1 / §1.2.3 规则 2）。
   - **WM 累计**：Lua 内 `new_total = current_estimated_tokens + message_estimated_tokens`；若 `new_total > max_working_memory_estimated_tokens` → `capacity_exceeded`；不得 RPUSH/SADD/更新 token/updated_time（§1.2.1 规则 3）。
   - **`compression_trigger_tokens` 本任务不使用**；不得与 `max_working_memory_estimated_tokens` 混为同一上限检查（触发阈值留给 STM-009 Coordinator）。
5. **Redis 原子性**：单 Lua 脚本原子执行 meta 校验、duplicate 检查、WM 容量检查、RPUSH 消息 JSON、SADD `message_id`、HSET `estimated_tokens` + `updated_time`；复用 STM-001 Key helpers（`meta` / `messages` / `message_ids`）；**禁止**新 Key 模式。
6. **序列化**：`WorkingMemoryMessage` ↔ Redis List 元素 JSON（字段：`message_id`、`role`、`content`、`estimated_tokens`、`timestamp`；`role` 存字面量 `user`/`assistant`）。
7. **测试**：Unit（estimator 复用、消息编解码、内部结果映射）+ Contract（`MessageWriteStatus` 字面量稳定）+ Integration（真实 Redis；**至少 15 项场景**，见 §8.3）。

完成后 STM-009 可依赖本任务的写入服务与 Lua；STM-004 读取 Lua 与本任务写入 Key **并行独立**。

---

## 3. 非目标（必须坚持；黑名单语义）

- **`POST /api/v1/memory/working/message` HTTP 路由**、Pydantic Request/Response Schema、鉴权接线、`compression_status` 返回（**STM-009**；§1.2.3 端点存在但本任务不实现 HTTP 层）。
- 压缩协调、压缩锁、`compression_trigger_tokens` 检查、压缩重试写入、`working_memory_full` HTTP 503（**STM-009**）。
- 上下文一致性读取 Lua（**STM-004**）。
- Mongo `context_archive`、Kafka、Compression LLM、Finalize Lua、Session Close（**STM-005+**）。
- Lua 内 Token 重算；第二套 estimator；修改 STM-001 `estimate_tokens()` 公式或 Contract。
- 修改 STM-002 Session 创建 repository/codec Contract（无条件 HSET、pending `""`/`"0"` 语义）。
- `timestamp` 未来偏差校验（`invalid_message_timestamp`）的 HTTP 400 映射（**STM-009**）；本任务服务层可接受已解析 `timestamp` 整数，偏差规则在 API 层实现。
- duplicate 时校验 `content`/`role` 是否与首次一致（规格要求不覆盖；**不**因内容不一致而失败）。
- Redis TTL / EXPIRE（§1.2.7 规则 12）。
- 操作 **DEV-006** / **PR #13**。
- 修改 `settings/**`、`.env.example`、`configs/**`、`compose*.yaml`、Migration。
- 自动 Push / Merge / Rebase / Force Push。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `033e05ac23acd72f17458cdb701ddc37d28799bf`（`docs(status): complete STM-002 after PR merge`） |
| `git status --short` | clean |
| formal STM-001 | `completed`（PR #19 MERGED） |
| formal STM-002 | `completed`（PR #20 MERGED） |
| baseline（STM-002 tested） | unit 269 / contract 59 / ruff PASS / mypy PASS |

### 4.2 STM-001 复用审计（不得新建第二套模型）

| 交付物 | 路径 | STM-003 用法 |
|---|---|---|
| `estimate_tokens()` | `src/memory_system/domain/services/token_estimator.py` | **唯一** Token 计算入口；服务层在 Lua 前调用；Lua **禁止**重算 |
| `WorkingMemoryMessage` | `src/memory_system/domain/models/working_memory.py` | List 元素权威字段模型；JSON 编解码目标类型 |
| `MessageRole` | `src/memory_system/domain/enums/working_memory.py` | 写入校验与 JSON `role` 字面量 |
| `SessionStatus` | 同上 | Lua 校验 `status == active` |
| Redis Key helpers | `src/memory_system/infrastructure/redis/keys.py` | **直接复用** 三个 Key 函数；禁止内联 Key 字符串 |
| `ContextSettings` | `src/memory_system/settings/models.py` | `max_message_estimated_tokens`、`max_working_memory_estimated_tokens`；**不读** `compression_trigger_tokens` |

### 4.3 STM-002 复用审计

| 交付物 | 路径 | STM-003 用法 |
|---|---|---|
| `meta_to_hash_fields` / `hash_fields_to_meta` | `infrastructure/redis/working_memory_codec.py` | Integration 断言 meta；Lua 读写字段格式一致 |
| `create_working_memory_session` | `infrastructure/redis/working_memory_repository.py` | Integration 前置：创建 active Session |
| `create_session` | `domain/services/session_service.py` | Integration 可选编排 |
| `AppState.redis` | `infrastructure/runtime.py` | Integration 注入真实 Redis |

**结论**：WM meta 写入仍仅通过 STM-002 路径创建；本任务 **新增** messages List / message_ids Set 写入与 Lua，**不**改 STM-002 创建语义。

### 4.4 规格摘录（权威；STM-003 范围）

**HTTP Request 字段**（§1.2.3 — **STM-009 实现 HTTP；本任务服务层对齐同字段**）：

| 字段 | 来源 | STM-003 服务层 |
|---|---|---|
| `message_id` | 外部 Agent UUID v4 | 必填；幂等键 |
| `user_id` | 外部 Agent | 必填；参与 Key 与 Hash 校验 |
| `session_id` | Memory System 创建 | 必填；参与 Key 与 Hash 校验 |
| `role` | 请求 | `user` / `assistant` |
| `content` | 请求 | 非空；用于 `estimate_tokens()` |
| `timestamp` | 可选 Unix 秒 | 未提供时服务层用 `clock()` 在**构建 Lua 参数时**生成；duplicate 重试不改变已存 timestamp |
| `estimated_tokens` | **不存在于 Request** | Python 计算后写入消息 JSON 与 Lua 参数 |

**写入 Lua 原子步骤**（§1.2.1 规则 3 + §10.1 OI-STM-003-002 — **本任务完整实现**；顺序固定）：

1. 检查 meta Key 存在性（`EXISTS`）；不存在 → `session_not_found`
2. 校验 Hash `user_id` / `session_id` 与请求一致；不匹配 → `session_not_found`（用户隔离；**先于** `status` 检查）
3. 检查 Session `status == active`；否则 → `session_closing`
4. 检查 `message_id` 是否在 Set（`SISMEMBER`）；已存在 → `duplicate`（零副作用）
5. `new_total = current_estimated_tokens + message_estimated_tokens`
6. `new_total > max_working_memory_estimated_tokens` → `capacity_exceeded`（零副作用）；`new_total == max` → **允许**写入（精确边界 success）
7. 否则：`RPUSH` 消息 JSON、`SADD message_id`、HSET `estimated_tokens=new_total`、`updated_time`；return `success`

**单条消息上限**（§1.2.1 规则 1）：Python 层 `estimate_tokens(content) > max_message_estimated_tokens` → `message_too_large`；**不进 Lua**。

**WM 绝对上限 vs 压缩触发**（§1.2.1 规则 2 + §1.2.6）：`max_working_memory_estimated_tokens` 为最终背压上限；`compression_trigger_tokens` 为正常压缩触发阈值 — **STM-003 仅实现前者于 Lua**。

**HTTP 路由归属**：§1.2.3 定义 `POST /api/v1/memory/working/message`，但 `master_plan.md` STM-009 明确「写入 API 接线」；STM-003 master_plan 条目为「消息写入 Lua」— **HTTP 留给 STM-009**。

### 4.5 当前缺失

- 消息写入领域服务与内部结果类型。
- `WorkingMemoryMessage` Redis List JSON 编解码。
- 消息写入 Lua 脚本及 `EVAL`/`register_script` 封装。
- message write repository（调用 Lua + 解析结果）。
- Unit / Contract / Redis Integration 测试（15 场景）。

### 4.6 与技术规格不一致之处

- 无已实现业务冲突；§1.2.1 Lua 流程未显式命名「成功」返回字面量 — **§10.1 OI-STM-003-001 已决议**（`success`）。
- §1.2.7 `session_not_found` 原文针对 Session Close；消息写入 Lua 未逐字列出 — **§10.1 OI-STM-003-002 已决议**（meta 缺失或 Hash 身份字段不匹配 → `session_not_found`）。

---

## 5. 实现方案（仅供后续 Developer；本轮不执行）

### 硬约束（实施时强制）

1. **复用** `estimate_tokens()`、`WorkingMemoryMessage`、Key helpers、STM-002 codec 格式；禁止第二套 WM 消息模型。
2. **复用** `AppState.redis`；禁止独立 Redis 连接池。
3. **单 Lua 原子脚本** 完成 §1.2.1 规则 3 所列写入步骤；禁止应用层 RPUSH + SADD + HSET 分步写。
4. **Lua 禁止** Token 重算；`message_estimated_tokens` 由 Python 传入。
5. **`message_too_large`** 在 Python 判定；**`capacity_exceeded`** 在 Lua 判定；**不得**用 `compression_trigger_tokens` 替代 WM 上限。
6. **不实现** HTTP、压缩、Kafka、Mongo。
7. 业务代码必须同时含对应测试；失败不得 skip/xfail/降标准。

### Step 1 — 内部结果枚举与领域类型

- **文件**：`src/memory_system/domain/enums/message_write.py`（创建）。
- **枚举 `MessageWriteStatus`**（稳定内部字面量；与规格 Lua/HTTP 对齐）：
  | 值 | 含义 | 副作用 |
  |---|---|---|
  | `success` | 首次写入成功 | RPUSH + SADD + meta 更新 |
  | `duplicate` | `message_id` 已存在 | **无** |
  | `capacity_exceeded` | WM 累计超 `max_working_memory_estimated_tokens` | **无** |
  | `session_closing` | `status != active` | **无** |
  | `session_not_found` | meta 不存在或身份字段不匹配 | **无** |
  | `message_too_large` | 单条消息超 `max_message_estimated_tokens` | **无**（Python 层；不进 Lua） |
- **文件**：`src/memory_system/domain/models/message_write.py`（创建）。
- **`MessageWriteInput`**：`user_id`、`session_id`、`message_id`、`role`、`content`、`timestamp: int | None`。
- **`MessageWriteResult`**：`status: MessageWriteStatus`；`message_id`；可选 `estimated_tokens`（success 时 WM 新总量）；可选 `message_estimated_tokens`（success 时本条）。

### Step 2 — 消息 List JSON 编解码

- **文件**：`src/memory_system/infrastructure/redis/working_memory_message_codec.py`（创建）。
- **`message_to_json(message: WorkingMemoryMessage) -> str`**：紧凑 JSON；字段顺序固定：`message_id`、`role`（`.value`）、`content`、`estimated_tokens`、`timestamp`。
- **`json_to_message(payload: str) -> WorkingMemoryMessage`**：Integration 断言 List 元素。
- **禁止**修改 `WorkingMemoryMessage` 字段集。

### Step 3 — 消息写入 Lua 脚本

- **文件**：`src/memory_system/infrastructure/redis/scripts/message_write.lua`（创建，推荐独立文件便于审阅）。
- **KEYS**（3）：
  - `KEYS[1]` = meta Hash key（`working_memory_meta_key`）
  - `KEYS[2]` = messages List key
  - `KEYS[3]` = message_ids Set key
- **ARGV**（7）：
  - `ARGV[1]` = `message_json`（完整 JSON 字符串，已含 `estimated_tokens`）
  - `ARGV[2]` = `message_estimated_tokens`（十进制字符串整数）
  - `ARGV[3]` = `max_working_memory_estimated_tokens`（十进制字符串整数）
  - `ARGV[4]` = `updated_time`（十进制字符串 Unix 秒）
  - `ARGV[5]` = `expected_user_id`
  - `ARGV[6]` = `expected_session_id`
  - `ARGV[7]` = `message_id`（幂等键；**固定传入**供 `SISMEMBER`/`SADD`；禁止 Lua 内解析 JSON 取 id）
- **逻辑**（顺序固定；与 §10.1 OI-STM-003-002 一致）：
  1. `EXISTS meta` 为 0 → return `session_not_found`
  2. `HGET user_id` / `HGET session_id` 与 `ARGV[5]`/`ARGV[6]` 不等 → return `session_not_found`（用户隔离；不泄露跨租户；**先于** `status`）
  3. `HGET status`；非 `active` → return `session_closing`
  4. `SISMEMBER message_ids ARGV[7]` → 1 则 return `duplicate`（零副作用）
  5. `current = tonumber(HGET estimated_tokens)`；`new_total = current + tonumber(ARGV[2])`
  6. `new_total > tonumber(ARGV[3])` → return `capacity_exceeded`（`==` 允许继续）
  7. `RPUSH messages ARGV[1]`；`SADD message_ids ARGV[7]`；`HSET meta estimated_tokens new_total updated_time ARGV[4]`
  8. return `success`
- **文件**：`src/memory_system/infrastructure/redis/message_write_script.py`（创建）：加载 Lua、`register_script` 得 SHA、暴露 `run_message_write_lua(...)`。
- **禁止**：`EXPIRE`；压缩锁 Key；`LTRIM`；修改 `compression_version` / `compressed_context` / `pending_archive_*`。

### Step 4 — Repository

- **文件**：`src/memory_system/infrastructure/redis/message_write_repository.py`（创建）。
- **`async def execute_message_write_lua(*, redis, user_id, session_id, message_id, message_json, message_estimated_tokens, max_wm_tokens, updated_time) -> MessageWriteStatus`**
- 将 `message_id` 作为 `ARGV[7]` 传入 Lua（与 JSON 内 `message_id` 一致由服务层保证）。
- 解析 Lua 返回字符串 → `MessageWriteStatus`；未知返回 → 抛错（不伪造 success）。

### Step 5 — 消息写入领域服务

- **文件**：`src/memory_system/domain/services/message_write_service.py`（创建）。
- **输入校验**（服务层最小集；HTTP 额外校验留给 STM-009）：
  - `content` 非空（`strip` 后长度 > 0 或规格「不能为空」— 与 §1.2.3 规则 1 一致）
  - `role` 为合法 `MessageRole`
- **流程**：
  1. `tokens = estimate_tokens(content)`（**唯一** estimator）
  2. 若 `tokens > settings.context.max_message_estimated_tokens` → return `MessageWriteResult(message_too_large)` **不调用 Lua**
  3. `ts = timestamp if timestamp is not None else clock()`
  4. 构造 `WorkingMemoryMessage` + `message_json`
  5. 调用 repository Lua
  6. 映射为 `MessageWriteResult`
- **依赖注入**：`redis`、`settings`（或 `ContextSettings` 子集）、可选 `clock`（Unit 固定时间）。
- **不实现**：压缩重试、`working_memory_full`。

### Step 6 — 模块导出

- **修改**：`infrastructure/redis/__init__.py` — 最小导出 message codec / repository / script runner。
- **修改**：`domain/services/__init__.py` — 可选导出 `write_message`。
- **不修改** `api/app.py`（无 HTTP 路由）。

### Step 7 — 质量门禁与治理回写（实施阶段）

- STM-003 scoped：`uv run pytest tests/unit/test_message_write_service.py tests/unit/test_working_memory_message_codec.py tests/unit/test_message_write_status_mapping.py tests/contract/test_stm003_contract.py -q`
- Integration：`uv run pytest tests/integration/test_message_write_redis.py -q`
- 全量：`uv run pytest tests/unit -q`、`uv run pytest tests/contract -q`、`uv run ruff check .`、`uv run mypy src tests scripts`
- 更新 Task Plan 执行记录、`progress.md`、`master_plan.md`。

---

## 6. 文件变更清单

### 6.1 Exact writable whitelist（实施阶段；精确路径）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/enums/message_write.py` | 创建 | `MessageWriteStatus` 内部结果枚举 |
| `src/memory_system/domain/models/message_write.py` | 创建 | `MessageWriteInput` / `MessageWriteResult` |
| `src/memory_system/domain/services/message_write_service.py` | 创建 | Token 预检 + Lua 编排 |
| `src/memory_system/infrastructure/redis/working_memory_message_codec.py` | 创建 | `WorkingMemoryMessage` ↔ List JSON |
| `src/memory_system/infrastructure/redis/scripts/message_write.lua` | 创建 | 原子写入 Lua |
| `src/memory_system/infrastructure/redis/message_write_script.py` | 创建 | Lua 加载与 `register_script` |
| `src/memory_system/infrastructure/redis/message_write_repository.py` | 创建 | `EVALSHA` 封装与结果解析 |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 | 最小导出 |
| `src/memory_system/domain/services/__init__.py` | 修改 | 可选导出 `write_message` |
| `src/memory_system/domain/enums/__init__.py` | 修改 | 可选导出 `MessageWriteStatus` |
| `tests/unit/test_working_memory_message_codec.py` | 创建 | JSON round-trip、role 字面量 |
| `tests/unit/test_message_write_service.py` | 创建 | estimator 复用、message_too_large、mock Lua |
| `tests/unit/test_message_write_status_mapping.py` | 创建 | Lua 字符串 ↔ 枚举；未知值异常 |
| `tests/contract/test_stm003_contract.py` | 创建 | `MessageWriteStatus` 字面量与 Lua 返回字符串稳定对齐（无网络/无 Redis I/O） |
| `tests/integration/test_message_write_redis.py` | 创建 | 15 场景真实 Redis（含精确边界） |
| `02_开发管理/tasks/STM-003-message-write-lua.md` | 修改 | 执行记录 / Amendment / 状态机 |
| `02_开发管理/progress.md` | 修改 | 规划/实施/完成态治理字段 |
| `02_开发管理/master_plan.md` | 修改 | STM-003 登记 / CHANGE |

**期望规模**：约 8 个业务源文件 + 1 Lua + 5 测试文件 + 最小 `__init__` 接线；单 PR 可审。

### 6.2 Exact forbidden paths（非穷尽；命中即越权）

| 路径/范围 | 原因 |
|---|---|
| `src/memory_system/api/routes/**` 新增 message HTTP 路由 | STM-009 |
| `src/memory_system/api/schemas/**` message HTTP Schema | STM-009 |
| `src/memory_system/domain/services/token_estimator.py` 公式/行为变更 | STM-001 Contract |
| `src/memory_system/domain/models/working_memory.py` 字段变更 | STM-001 Contract |
| `src/memory_system/infrastructure/redis/keys.py` Key 模板变更 | STM-001 Contract |
| `working_memory_repository.py` `create_working_memory_session` 语义变更 | STM-002 Contract |
| 压缩锁 / Coordinator / Kafka / Mongo / LLM 代码 | STM-005+ |
| `EXPIRE`/`TTL` | §1.2.7 规则 12 |
| DEV-006 feat / PR #13 | 治理禁令 |
| `settings/**`、`configs/**`、`compose*.yaml` | 非本任务范围 |

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 单 Lua 脚本覆盖 meta 读校验 + List/Set 写 + meta 计数更新 | 禁止应用层多命令拆分；Integration 断言失败路径无 partial state |
| 幂等 | `message_id` 级幂等 | Set `SISMEMBER` 前置；`duplicate` 零副作用；并发同 id 仅一条 `success` |
| 并发 | 同 Session 并发不同 `message_id` | Lua 串行化；各写入顺序由 Redis 单线程 + RPUSH 顺序保证 |
| 版本冲突 | 不适用 | 本任务不修改 `compression_version` |
| 用户隔离 | **必须** | Key 含 `user_id`；Lua 校验 Hash `user_id`/`session_id`；错误 `user_id` 访问 → `session_not_found` |
| 部分失败 | Lua 返回 error 状态前不得 RPUSH/SADD/HSET | `capacity_exceeded`/`session_closing`/`duplicate` 后 Integration 断言 List 长度与 token 不变 |
| 进程异常恢复 | Lua 单步原子 | 脚本中断由 Redis 保证无半写入；成功则完整三 Key 一致 |

---

## 8. 测试计划

### 8.1 Unit Test

| 场景 | 预期 |
|---|---|
| `estimate_tokens` 复用 | `message_write_service` 调用 `token_estimator.estimate_tokens`；**不**内联公式 |
| `message_too_large` | `content` 使 tokens > `max_message_estimated_tokens` → `message_too_large`；mock 证明 **未** 调用 Lua |
| `message_to_json` round-trip | 字段齐全；`role` 为 `user`/`assistant` 字面量 |
| 空 `content` | 服务层拒绝（ValidationError 或约定内部错误）；不进 Lua |
| Lua 结果映射 | `success`/`duplicate`/`capacity_exceeded`/`session_closing`/`session_not_found` 正确映射 |
| 未知 Lua 返回 | 抛异常；不映射为 success |
| mock redis success | 传入正确 Key 模板与 7 项 ARGV（含 `ARGV[7]=message_id`）；返回 `success` |

### 8.2 Contract Test

| 场景 | 预期 |
|---|---|
| HTTP 写入接口 | **不适用**（STM-009） |
| `MessageWriteStatus` 字面量稳定 | `tests/contract/test_stm003_contract.py`：枚举 `.value` 与 Lua 返回字符串（`success`/`duplicate`/`capacity_exceeded`/`session_closing`/`session_not_found`/`message_too_large`）一致；无网络/无 Redis I/O；对齐 STM-001/002 contract 模式 |

### 8.3 Integration Test（真实 Redis；**15 场景**）

前置：复用 `test_session_create_redis.py` 的 compose test Redis fixture 模式；Session 经 `create_working_memory_session` 或 `create_session` 创建 `active` meta。

| # | 场景 | 预期 |
|---|---|---|
| 1 | active Session + 新 `message_id` | `success` |
| 2 | success 后 messages List | `LLEN==1`；元素 JSON 可 `json_to_message` |
| 3 | success 后 message_ids Set | `SISMEMBER message_id==1` |
| 4 | success 后 meta | `estimated_tokens == prior + message_estimated_tokens`；`updated_time` 更新 |
| 5 | 重复同 `message_id` | `duplicate` |
| 6 | duplicate 零副作用 | List 长度、Set 大小、`estimated_tokens`、`updated_time` 与首次 success 后相同 |
| 7 | 单条消息超 `max_message_estimated_tokens` | `message_too_large`；List/Set 不存在或未增长 |
| 8 | WM 累计超 `max_working_memory_estimated_tokens` | 预填 meta `estimated_tokens` 接近上限后写入 → `capacity_exceeded`；无新 List 元素 |
| 9 | Session meta 不存在 | `session_not_found` |
| 10 | Session `status=closing` | `session_closing`；无写入 |
| 11 | 用户隔离 | `user_a` 的 `session_id` 用 `user_b` 写入 → `session_not_found`；`user_a` 数据不变 |
| 12 | 并发同 `message_id` | `asyncio.gather` 或线程多次并发 → 恰好 1 次 `success`、其余 `duplicate`；`LLEN==1` |
| 13 | 原子失败无 partial state | `capacity_exceeded` 或 `session_closing` 后：`LLEN`、`SCARD`、`estimated_tokens` 与调用前一致 |
| 14 | 单条消息 **精确边界** `tokens == max_message_estimated_tokens` | `success`（Python 层 `>` 才 `message_too_large`；`==` 允许进 Lua） |
| 15 | WM 累计 **精确边界** `new_total == max_working_memory_estimated_tokens` | `success`（Lua `>` 才 `capacity_exceeded`；`==` 允许写入） |

清理：每用例删除测试 Key 或专用 `user_id`/`session_id` 前缀。

### 8.4 E2E Test

| 场景 | 预期 |
|---|---|
| 全链路 HTTP 写入 E2E | **不适用**（STM-009 / STM-013） |

### 8.5 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 并发同 `message_id`（#12） | 见 §8.3 |
| Redis 连接失败（mock） | 异常传播；无假 success |
| Lua 返回未知字符串（mock） | 服务层抛错 |

---

## 9. 验收标准

- [x] `write_message` 服务可用；输入契约符合 §1.2.3（无客户端 `estimated_tokens`；`timestamp` 可选）
- [x] **唯一** `estimate_tokens()` 在 Lua 前计算；Lua **不重算** Token
- [x] 单 Lua 原子脚本实现 §1.2.1 规则 3 写入路径（success/duplicate/capacity/session 分支）
- [x] `message_too_large` 与 `capacity_exceeded` **分离**；未使用 `compression_trigger_tokens` 作 WM 上限
- [x] `duplicate` / `capacity_exceeded` / `session_closing` / `session_not_found` **零副作用**
- [x] List JSON 符合 `WorkingMemoryMessage` 字段集；复用 STM-001 Key helpers
- [x] **未**实现 HTTP 路由、压缩、Kafka、Mongo
- [x] **未**修改 STM-001 estimator / STM-002 session-create Contract
- [x] STM-003 scoped Unit + Contract + Redis Integration（17 场景含 #16 malformed / #17 ARGV 校验）通过
- [x] 全量 `tests/unit` + `tests/contract` 无回归
- [x] `uv run ruff check .` PASS
- [x] `uv run mypy src tests scripts` PASS
- [ ] Code Review 无 P0/P1

### 9.1 Release gate（实施阶段结束）

```text
STM-003 scoped tests PASS
+ full unit baseline PASS
+ full contract baseline PASS
+ contract test_stm003_contract PASS
+ Redis integration 15 scenarios PASS（Docker 可用环境；含精确边界 #14/#15）
+ ruff PASS
+ mypy PASS
+ 无 STM-001 / STM-002 Contract 回归
```

---

## 10. 风险与阻塞项

### 10.1 OPEN_ISSUE（Planner 决议；待 Plan Review 确认）

| ID | 主题 | 状态 | 决议 |
|---|---|---|---|
| **OI-STM-003-001** | Lua **成功**返回字面量 | **RESOLVED**（Planner） | §1.2.1 规则 3 未命名成功分支；本任务 Lua return **`success`**，与 §1.2.3 Response `status: "success"` 对齐；Python `MessageWriteStatus.SUCCESS = "success"` |
| **OI-STM-003-002** | meta 缺失 vs Hash `user_id`/`session_id` 不匹配 | **RESOLVED**（Planner） | 均返回 **`session_not_found`**（§1.2.7 Close 路径同名语义；不匹配不返回独立 `ownership_mismatch`，避免跨用户存在性泄露）；Lua 在 `status` 检查前校验 Key 存在与 Hash 身份字段 |

### 10.2 其他风险

| 风险 | 缓解 |
|---|---|
| 首个 Lua 脚本引入维护成本 | 独立 `.lua` 文件 + Integration 15 场景锁语义 |
| Integration 误用 dev 栈 | 强制 `compose.sh --stack=test`；复制 STM-002 隔离策略 |
| 与 STM-009 职责边界模糊 | 本计划 §3 黑名单 + master_plan STM-009 接线明确 |
| DEV-006 / PR #13 | 不得触碰 |

### 10.3 设计文档冲突

- 无已识别规格正文冲突；§1.2.3 HTTP 端点存在但 master_plan 将 API 接线划入 STM-009 — **与本任务范围一致，非规格冲突**。

### 10.4 前置任务

- STM-001、STM-002：**SATISFIED**。

---

## 11. Git 计划

```yaml
branch: "feat/STM-003-message-write-lua"
workflow_mode: NORMAL
release_phases:
  PLAN_LANDING:
    - "docs(plan): add STM-003 message write lua plan（main）"
    - "git pull --ff-only；创建 exact feat/STM-003-message-write-lua"
  IMPLEMENTATION_RELEASE:
    - "feat(stm): add message write lua and domain service"
    - "docs(status): record STM-003 implementation commit and PR（feat only）"
    - "gh pr create（base main）"
  POST_MERGE_CLEANUP:
    - "docs(status): complete STM-003 after PR merge（main only）"
    - "删除 exact feat 分支"
expected_commits:
  - "docs(plan): add STM-003 message write lua plan"
  - "feat(stm): add message write lua and domain service"
out_of_scope_changes:
  - "HTTP 写入路由 / compression_status / Coordinator"
  - "settings / compose / migration"
  - "DEV-006 / PR #13"
  - "STM-001 estimator / STM-002 session-create Contract 变更"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001（Plan Review Round 1 修订）

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 触发 | Plan Review Round 1 `PLAN_REJECTED`（MF-1：Lua 步骤顺序与 §10.1 OI-STM-003-002 矛盾） |
| MF-1 | §4.4 与 §5 Step 3 Lua 逻辑重排：EXISTS → 身份字段校验 → `status` → `SISMEMBER` → 容量 → 写入 |
| SF-1 | `message_id` 固定为 `ARGV[7]`；`SISMEMBER`/`SADD` 使用 `ARGV[7]`，禁止 Lua 解析 JSON |
| SF-2 | Integration #14/#15：单条 `tokens == max_message` 与 WM `new_total == max_wm` 精确边界 → `success` |
| SF-3 | 白名单新增 `tests/contract/test_stm003_contract.py`；scoped pytest 含 contract |
| 状态 | `planned`；待 Plan Review Round 2 |

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-10 04:17 UTC | Planner 初版 | 创建 Task Plan；progress/master_plan 规划态回写 | 未运行（规划-only） | §10.1 两项 OPEN_ISSUE 已 Planner 决议；待 Plan Review |
| 2026-08-10 04:30 UTC | Planner Amendment 001 | MF-1 Lua 步骤重排对齐 OI-STM-003-002；SF-1 ARGV[7] message_id；SF-2 精确边界 #14/#15；SF-3 contract 白名单 | 未运行（规划-only） | Round 1 PLAN_REJECTED 修订；待 Plan Review Round 2 |
| 2026-08-10 06:10 UTC | Developer 实施 | `MessageWriteStatus`/`MessageWriteInput`/`MessageWriteResult`；`write_message` 服务；`message_write.lua`（ARGV[7]、malformed `estimated_tokens`→`invalid_session_state`）；message codec/repository/script；Unit+Contract+Integration（17 场景） | STM-003 scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS（119 files） | Human 约束：malformed token fail-closed；#16/#17；未 Git commit；`next_action=Code Review` |
| 2026-08-10 14:12 UTC | Developer P1-1 修复 | `git checkout --` 回滚 17 条越权路径（`settings/**`、`scripts/migrate.py`、非 STM-003 contract/unit/integration）；保留 §6.1 白名单 | STM-003 scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS（119 files） | Code Review P1-1：工作区越权变更已清零；未 Git commit；`next_action=Code Review` |
| 2026-08-10 14:20 UTC | Release Operator IMPLEMENTATION_RELEASE | implementation commit `e1913d17b159d426aadfd54d32e07c84ea61043a`；PR #21 OPEN | scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS（119 files） | `status=committed`；`next_action=Human PR merge` |
| 2026-08-10 06:26 UTC | POST_MERGE_CLEANUP | PR #21 MERGED（`3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4`）；docs(status): complete on main；删 exact feat | scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS（119 files） | `status=completed`；STM-004 READY_FOR_PLANNING only |

---

## 14. 实际执行结果

`completed` — PR #21 MERGED；POST_MERGE_CLEANUP 完成。

| 维度 | 结果 |
|---|---|
| 交付 | atomic Redis Lua + `write_message` 领域服务；`MessageWriteStatus`（含 `invalid_session_state`）；`WorkingMemoryMessage` List JSON codec |
| 语义 | `message_id` 幂等；duplicate 零副作用；hard WM capacity；concurrent same `message_id` 单写；malformed `estimated_tokens` fail-closed |
| 范围外 | 无 compression / Kafka / HTTP |
| Human 约束 | Python 预检 `message_too_large`；Lua 不重算 token；`ARGV[7]=message_id`；malformed/missing `estimated_tokens` fail-closed；精确边界 #14/#15 |
| STM-003 scoped | **21 passed**（unit 18 + contract 3） |
| Integration | **11 passed**（17 场景分布于 11 用例；compose test Redis） |
| Full unit | **287 passed** |
| Full contract | **62 passed** |
| ruff | PASS |
| mypy | PASS — 119 source files |
| Git | implementation `e1913d17b159d426aadfd54d32e07c84ea61043a`；record `34bbebd`；PR #21 MERGED（`3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4`） |
| next_action | STM-004 READY_FOR_PLANNING only（须显式编排；不得自动开始实施） |

### 14.5 Git 记录

```yaml
branch: feat/STM-003-message-write-lua
plan_commit: 926f37d166089f02b3143470ca74ba1258d48010
implementation_commit: e1913d17b159d426aadfd54d32e07c84ea61043a
implementation_commit_message: "feat(stm): add message write lua and domain service"
pr_number: 21
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/21"
pr_state: MERGED
merge_commit: 3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4
merged_at: "2026-08-10T06:26:37Z"
status_record_committed: 34bbebd
status_record_completed: null  # pending this docs(status): complete commit SHA
```
