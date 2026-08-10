# STM-002 Session 创建

## 1. 任务信息

```yaml
task_id: STM-002
task_name: Session 创建
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.1 Redis Working Memory 数据结构设计（Key 模板、Hash 字段、初始值语义）"
  - "§1.2.3 Memory API 接口定义（POST /api/v1/memory/session；Request/Response；处理流程）"
  - "§1.2.7 Session 生命周期（创建时元数据初始化规则；MVP 不使用 Redis TTL）"
  - "§3.21 Memory API 鉴权与接口暴露（Session 接口鉴权分级）"
  - "§3.23 统一 API 响应与 Request ID（错误包络；422 validation_error）"
  - "§3.7 Web 服务与应用生命周期（复用 AppState.redis；不新建连接管理）"
prerequisites:
  - "STM-001 — SATISFIED（WM Key/字段模型、枚举、Token estimator 已在 main；PR #19 MERGED）"
  - "DEV-005 — SATISFIED（API 壳、X-API-Key、Request ID、错误包络、create_app 已在 main；PR #12 MERGED）"
  - "规划基线（本轮只读）：main @ ad0dcc4；working tree clean；STM-001 后 full unit 254 / contract 49 / ruff PASS / mypy PASS"
  - "本任务不需要 SiliconFlow / LLM / TEI 网络调用"
branch: "feat/STM-002-session-creation"
created_at: "2026-08-10 02:28 UTC"
updated_at: "2026-08-10 02:52 UTC"
approval_gates:
  planning_docs: "Amendment 001 已吸收 Human Contract；pending Plan Review Round 2 → READY_FOR_PLAN_REVIEW；本轮不得 PLAN_APPROVED / 不得实施"
  implementation_plan: "status=planned；§10.1 四项 OPEN_ISSUE 已由 Amendment 001（Human Contract）关闭；待 Plan Review Round 2 后方可 Developer"
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
  - "实现消息写入、压缩、Session Close、Mongo/Kafka"
```

---

## 2. 任务目标

交付 **HTTP Session Create → 鉴权/校验 → 写入一条 Working Memory 元数据 Hash → 返回最小 Session 响应** 的端到端能力（仅 Session 创建；不含消息写入与压缩）：

1. **`POST /api/v1/memory/session`**（§1.2.3）：Request Body `{"user_id": "<upstream-provided>"}`；服务端生成 `session_id`（UUID v4）；Response `{"session_id": "<uuid>", "status": "created"}`。
2. **Redis 真实写入**：使用既有 `AppState.redis`（`infrastructure/runtime.py`）向 `working_memory_meta_key(user_id, session_id)` 写入 Hash；**仅元数据 Key**；不预创建 `:messages` / `:message_ids`（§1.2.3：「Redis List 和 Set 在首次写入时由 Redis 自动创建」）。
3. **初始 WM Hash 字段**（§1.2.7 规则 1 + §1.2.1 + STM-001 `WorkingMemoryMeta` 默认）：
   - `status=active`
   - `compression_version=0`
   - `compressed_context=""`、`estimated_tokens=0`
   - 全部 `pending_archive_*` 初始化为空值或 `0`
   - `user_id`、`session_id`、`created_time`、`updated_time`（Unix timestamp；创建时两者相等）
4. **鉴权与横切能力复用**（DEV-005 / §3.21）：`X-API-Key`（Memory 或 Admin Key）；统一错误包络；`X-Request-ID`。
5. **测试**：Unit（序列化/服务逻辑）+ Contract（HTTP 形状与鉴权复用）+ Integration（真实 Redis via compose test 栈）。

完成后 STM-003/004 可依赖本任务提供的 Session 创建与 WM 元数据落盘能力。

---

## 3. 非目标（必须坚持；黑名单语义）

- 消息写入（`POST /api/v1/memory/working/message`）、消息幂等、容量背压、Lua 脚本（**STM-003**）。
- 上下文一致性读取 Lua（**STM-004**）。
- Mongo `context_archive`、Kafka 事件、压缩锁/Coordinator/LLM（**STM-005+**）。
- Session Close（**STM-010**）。
- Redis TTL / 闲置 Session 扫描 / 自动关闭（§1.2.7 规则 12 明确禁止；**本任务不得 EXPIRE**）。
- 第二套 Session/WM 领域模型或第二套 Redis 连接管理。
- 新建鉴权中间件；修改 DEV-005 错误码/包络语义。
- 修改 STM-001 Contract（`WorkingMemoryMeta` 字段集、Key 模板、枚举字面量）除非 Plan Review 认定真实 blocker 并走 Amendment + HALT。
- SiliconFlow / TEI / LLM / Embedding / Extraction / Retrieval。
- 操作 **DEV-006** / **PR #13**。
- 修改 `settings/**`、`.env.example`、`configs/*.yaml`、`compose*.yaml`、Migration 脚本。
- 自动 Push / Merge / Rebase / Force Push。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `ad0dcc4`（`docs(status): complete STM-001 after PR merge`） |
| `git status --short` | clean |
| formal STM-001 | `completed`（PR #19 MERGED `6f2081da6266282470948ecac8e62ef3ae969c15`） |
| formal DEV-005 | `completed`（PR #12 MERGED） |
| baseline（STM-001 tested） | unit 254 / contract 49 / ruff PASS / mypy PASS |

### 4.2 STM-001 复用审计（不得新建第二套模型）

| 交付物 | 路径 | STM-002 用法 |
|---|---|---|
| `WorkingMemoryMeta` | `src/memory_system/domain/models/working_memory.py` | **直接复用**；作为 WM Hash 权威字段模型；允许新增 **codec/repository 层** 做 Redis 字符串编解码，**禁止**复制字段定义 |
| `WorkingMemoryMessage` | 同上 | **不写入**；STM-003 使用；本任务测试断言 messages Key 不存在或未写入 |
| `SessionStatus` | `src/memory_system/domain/enums/working_memory.py` | **直接复用**；创建时 WM Hash `status=active` |
| `MessageRole` | 同上 | 本任务 **不使用** |
| Redis Key helpers | `src/memory_system/infrastructure/redis/keys.py` | **直接复用** `working_memory_meta_key`；禁止内联 Key 字符串 |
| Token estimator | `src/memory_system/domain/services/token_estimator.py` | 本任务 **不使用**（创建时 `estimated_tokens=0`） |

**结论**：实施时 **零** 新建 `Session`/`WorkingMemory` 平行模型；仅在 `infrastructure/redis/` 增加 **I/O + 编解码** 薄层。

### 4.3 Redis 运行时基础审计

| 组件 | 路径 | 状态 |
|---|---|---|
| Async Redis client 工厂 | `src/memory_system/infrastructure/runtime.py` `create_app_state()` | **已存在**：`redis.from_url(..., decode_responses=True)` + 启动 `ping` |
| `AppState.redis` | 同上 `AppState` dataclass | **已存在**；路由经 `request.app.state.app_state` 访问（见 `api/routes/health.py`） |
| `Settings.redis` | `src/memory_system/settings/models.py` `RedisSettings` | **已存在**；本任务 **不改** |
| `infrastructure/redis/` | 当前仅 `keys.py` + `__init__.py` 导出 Key helpers | **缺失**：WM Hash 写入/读取编解码与 repository（本任务新增，属预期） |

**结论**：STM-002 **必须**注入 `AppState.redis`；**禁止**第二连接池、`redis.from_url` 重复调用或绕过 Lifespan 的独立 Client。

### 4.4 DEV-005 API 壳复用审计

| 能力 | 路径 | STM-002 用法 |
|---|---|---|
| `create_app()` | `src/memory_system/api/app.py` | 注册新 router；测试继续 `create_app(app_state=...)` |
| `require_memory_api_key` | `src/memory_system/api/dependencies.py` | Session 路由 Depends；§3.21 Session 类接口 |
| 错误包络 | `api/errors.py` + `api/error_handlers.py` | `AppError` / `validation_error`；不新增平行错误格式 |
| Request ID | `api/middleware.py` | 自动；Contract 断言 `X-Request-ID` |
| 业务 Memory 路由 | — | **缺失**（预期）；本任务首个 `/api/v1/memory/*` 路由 |

### 4.5 Session Create Contract 规格摘录（权威；不得猜测未写明部分）

**Endpoint**（§1.2.3）：`POST /api/v1/memory/session`

**Request Body**：

```json
{ "user_id": "user_001" }
```

- `user_id`：**唯一**请求字段；由已鉴权上游 Agent 提供（§3.21 规则 4–6）；**不是**从 API Key 推导。
- `session_id`：**不由客户端提供**；服务端 `Generate session_id(UUID v4)`（§1.2.3 流程图；§1.2.1 字段表）。

**Success Response**（§1.2.3）：

```json
{
  "session_id": "550e8400-e29b-41d4-a716",
  "status": "created"
}
```

- HTTP Response 字段 `status` 字面量为 **`"created"`**（创建结果语义）；**不同于** Redis Hash 内 `status=active`（§1.2.1 / §1.2.7）。
- 成功 HTTP 状态码：**200 OK**（**Amendment 001 / OI-STM-002-004 RESOLVED**）；MVP **不使用** `201 Created`。

**Redis 初始化**（§1.2.3 + §1.2.7 规则 1）：

- 初始化 Working Memory **元数据** Hash；`status=active`；`pending_archive_*` 空值或 `0`。
- List/Set Key **不预创建**。

**TTL**（§1.2.7 规则 12）：MVP **不使用** Redis TTL；本任务 **禁止** `EXPIRE`/`PEXPIRE`。

**鉴权**（§3.21 接口分级表）：Session 接口接受 Memory Key 或 Admin Key。

### 4.6 当前缺失

- `POST /api/v1/memory/session` 路由与 Request/Response Schema。
- WM Hash Redis 写入 repository + meta 字段编解码（STM-001 刻意无 I/O）。
- Session 创建 Unit / Contract / Redis Integration 测试。

### 4.7 与技术规格不一致之处

- 无已实现业务冲突；属 Phase 1 能力尚未落地（预期）。
- §10.1 四项 OPEN_ISSUE 已由 **Amendment 001（Human Contract）** 关闭；实施须严格遵循 Amendment 决议。

---

## 5. 实现方案（仅供后续 Developer；本轮不执行）

### 硬约束（实施时强制）

1. **复用 STM-001 模型与 Key helpers**；禁止第二套 Session/WM 类型。
2. **复用 `AppState.redis`**；禁止独立 Redis 连接管理。
3. **复用 DEV-005 鉴权/错误/Request ID**；禁止新 auth middleware。
4. **仅写 meta Hash**；禁止 `RPUSH`/`SADD`/消息内容/压缩副作用。
5. **禁止 TTL**（§1.2.7 规则 12）。
6. **Amendment 001（Human Contract）** 为 §10.1 四项决议的权威实施约束（duplicate 语义、user_id 校验、null 编解码、HTTP 200）。
7. 业务代码必须同时含对应测试；失败不得 skip/xfail/降标准。

### Step 1 — API Schema 与路由

- **文件**：`src/memory_system/api/schemas/memory_session.py`（创建）、`src/memory_system/api/routes/memory_session.py`（创建）。
- **Request Schema**：`CreateSessionRequest` — 字段 `user_id: str`（必填，`min_length=1`）；缺失、空 body 或空串 `""` → `422` + `validation_error`（§3.23；**OI-STM-002-002 RESOLVED**）；**无**额外 `user_id` 格式限制。
- **Response Schema**：`CreateSessionResponse` — `session_id: str`；`status: Literal["created"]`（§1.2.3 字面量）。
- **路由**：
  - `POST /api/v1/memory/session`
  - `Depends(require_memory_api_key)` + `Depends(get_request_id)`（或等价 request.state 访问）
  - 从 `request.app.state.app_state` 取 `redis`
- **错误处理**：
  - 无/错 API Key → `401` `invalid_api_key`（既有依赖）
  - Request Schema 失败 → `422` `validation_error`
  - Redis 不可用 → `503` `internal_error` 或既有基础设施错误映射（不发明新错误码除非规格已有）
- **成功响应**：HTTP **200 OK**（**OI-STM-002-004 RESOLVED**）；body `{"session_id": "<uuid>", "status": "created"}`。
- **幂等/并发**：见 §7；每次调用生成新 UUID v4；**不**实现客户端 `session_id`、重复检测、幂等复用或 HTTP 409（**OI-STM-002-001 RESOLVED**）。

### Step 2 — WM Hash 编解码（Redis 字符串 ↔ WorkingMemoryMeta）

- **文件**：`src/memory_system/infrastructure/redis/working_memory_codec.py`（创建）。
- **职责**：
  - `meta_to_hash_fields(meta: WorkingMemoryMeta) -> dict[str, str]`（Redis HSET 全字符串值）
  - `hash_fields_to_meta(fields: Mapping[str, str]) -> WorkingMemoryMeta`（供 Integration 断言与后续 STM-003/004 复用）
- **字段覆盖**：§1.2.1 全字段；数值/枚举转字符串；`SessionStatus` 存字面量 `active`/`closing`。
- **OI-STM-002-003 RESOLVED（Amendment 001）**：
  - 可选字符串字段（`pending_archive_id`、`pending_archive_batch_key`）：Python `None` → Redis `""`；读取 `""` → Python `None`。
  - 计数字段（`pending_archive_message_count`、`pending_archive_token_count`）：整数 → 十进制字符串（如 `"0"`）。
  - **禁止**字面量 `"null"`。
  - 创建时 **必须** 写入全部 `pending_archive_*` 字段（§1.2.7 规则 1）。
- **禁止**：修改 `WorkingMemoryMeta` 字段名或默认值语义。

### Step 3 — Session 创建 Repository（真实 Redis 写）

- **文件**：`src/memory_system/infrastructure/redis/working_memory_repository.py`（创建）。
- **函数**（示例命名）：`async def create_working_memory_session(*, redis: Redis, user_id: str, session_id: str, now: int) -> WorkingMemoryMeta`
- **逻辑**：
  1. 构造 `WorkingMemoryMeta`（`status=SessionStatus.ACTIVE`，`compression_version=0`，pending 默认，`created_time=updated_time=now`）。
  2. `key = working_memory_meta_key(user_id, session_id)`（STM-001 helper）。
  3. **原子写入策略（OI-STM-002-001 RESOLVED）**：对新 Key **无条件 `HSET`** 全字段一次写入；每次 POST 生成新 UUID v4 → 新 Key；**不**实现 `HSETNX`/重复检测/409/idempotent 复用。
  4. **禁止**：`EXPIRE`；写入 `:messages` / `:message_ids`；压缩锁 Key。
- **输出**：持久化后的 `WorkingMemoryMeta`（与 Redis 一致）。

### Step 4 — 应用层 Session 服务（薄层，可选但推荐）

- **文件**：`src/memory_system/domain/services/session_service.py`（创建）。
- **职责**：生成 `uuid.uuid4()` `session_id`；调用 repository；返回 `(session_id, "created")`。
- **时间源**：`int(time.time())` 或注入 clock（Unit 测试可 mock）。
- **user_id 校验**：Pydantic `str` + `min_length=1`；缺失/空串 → `422 validation_error`；无额外格式规则（**OI-STM-002-002 RESOLVED**）。

### Step 5 — 应用接线

- **文件**：`src/memory_system/api/app.py`（修改）：`app.include_router(memory_session.router)`。
- **文件**：`src/memory_system/infrastructure/redis/__init__.py`（修改）：导出 repository/codec（最小公开面）。
- **`api/dependencies.py`**：仅当新增 `get_app_state` 依赖可减少样板时修改；**非必须**（可沿用 `health.py` 的 `request.app.state` 模式）。

### Step 6 — 质量门禁与治理回写（实施阶段）

- STM-002 scoped：`uv run pytest tests/unit/test_session_create_service.py tests/unit/test_working_memory_redis_codec.py tests/contract/test_stm002_contract.py -q`
- Integration（Docker 可用时）：`uv run pytest tests/integration/test_session_create_redis.py -q`
- 全量：`uv run pytest tests/unit -q`、`uv run pytest tests/contract -q`、`uv run ruff check .`、`uv run mypy src tests scripts`
- 更新 Task Plan 执行记录、`progress.md`、`master_plan.md`。

---

## 6. 文件变更清单

### 6.1 Exact writable whitelist（实施阶段；精确路径）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/api/schemas/memory_session.py` | 创建 | Create Session Request/Response Pydantic |
| `src/memory_system/api/routes/memory_session.py` | 创建 | `POST /api/v1/memory/session` |
| `src/memory_system/infrastructure/redis/working_memory_codec.py` | 创建 | `WorkingMemoryMeta` ↔ Redis Hash 字符串编解码 |
| `src/memory_system/infrastructure/redis/working_memory_repository.py` | 创建 | 创建 Session 的 Redis 写入（仅 meta Hash） |
| `src/memory_system/domain/services/session_service.py` | 创建 | UUID 生成 + 编排 repository |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 | 最小导出 codec/repository |
| `src/memory_system/domain/services/__init__.py` | 修改 | 可选导出 `session_service` |
| `src/memory_system/api/app.py` | 修改 | 注册 memory session router |
| `src/memory_system/api/dependencies.py` | **条件修改** | 仅当新增 `get_app_state` 依赖且有必要 |
| `tests/unit/test_working_memory_redis_codec.py` | 创建 | 编解码 round-trip、默认值、枚举字面量 |
| `tests/unit/test_session_create_service.py` | 创建 | UUID 格式、meta 初始字段、mock redis |
| `tests/contract/test_stm002_contract.py` | 创建 | HTTP 鉴权复用、成功 **200 OK**/校验失败包络、响应 `status=created`、空 `user_id` → `422` |
| `tests/integration/test_session_create_redis.py` | 创建 | 真实 Redis：字段齐全、`status=active`、`compression_version=0`、用户隔离、无 messages Key |
| `02_开发管理/tasks/STM-002-session-creation.md` | 修改 | 执行记录 / Amendment / 状态机 |
| `02_开发管理/progress.md` | 修改 | 规划/实施/完成态治理字段 |
| `02_开发管理/master_plan.md` | 修改 | STM-002 登记 / CHANGE |

**期望规模**：约 5 个业务源文件 + 3–4 个测试文件 + 最小 `app.py`/`__init__` 接线；单 PR 可审。

### 6.2 Exact forbidden paths（非穷尽；命中即越权）

| 路径/范围 | 原因 |
|---|---|
| `src/memory_system/domain/models/working_memory.py` 字段/默认值变更 | STM-001 Contract；除非 blocker + Amendment |
| `src/memory_system/infrastructure/redis/keys.py` Key 模板变更 | STM-001 Contract |
| `src/memory_system/settings/**`、`.env.example`、`configs/**` | 非本任务范围 |
| `compose*.yaml`、`Dockerfile`、`scripts/migrate*` | 非本任务范围 |
| 消息写入 Lua、压缩、Session Close、Mongo/Kafka 代码 | STM-003+ |
| `EXPIRE`/`TTL` 任何路径 | §1.2.7 规则 12 禁止 |
| DEV-006 feat / PR #13 | 治理禁令 |
| 第二套 Redis 连接 / `redis.from_url` 在 repository 内 | 必须复用 AppState |

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 单 Key 单次写入（HSET/HSETNX 一次调用或 pipeline 单 key） | meta Hash 全字段一次写入；List/Set 不涉及 |
| 幂等 | **非幂等**；每次 POST 创建新 Session | **OI-STM-002-001 RESOLVED**：服务端生成 UUID v4；同 `user_id` 多次调用 → 多个不同 Session；**不**实现客户端 `session_id`、重复检测、幂等复用或 HTTP 409 |
| 并发 | 每次创建新 UUID v4；不同请求不同 Key | 无条件 `HSET` 于新 Key；无跨请求共享写；UUID 碰撞概率忽略 |
| 版本冲突 | 不适用 | 创建不涉及 `compression_version` 递增 |
| 用户隔离 | **必须** | Key 含 `user_id`；Integration 断言 `user_a` / `user_b` 元数据隔离 |
| 部分失败 | Redis 写入失败则无 meta Key | 返回错误；不得返回成功 `session_id`；不得留下半初始化 messages |
| 进程异常恢复 | 创建为单步写入 | 失败则无 Key；成功则完整 Hash；无 TTL 清理（§1.2.7 规则 12） |

---

## 8. 测试计划

### 8.1 Unit Test

| 场景 | 预期 |
|---|---|
| Codec round-trip | `WorkingMemoryMeta` 默认值 ↔ Hash 字段；`status=active`、`compression_version=0` |
| Codec pending 字段 | `None` ↔ `""`；计数 `"0"`；**禁止** `"null"`；创建写入全部 pending 字段 |
| `session_service` 生成 `session_id` | 符合 UUID v4 格式（regex/parse） |
| 初始 meta 字段 | `compressed_context==""`、`estimated_tokens==0`、pending 默认 |
| Mock redis 创建成功 | 调用 `working_memory_meta_key`；单次 meta 写入；无 messages/message_ids 操作 |
| Mock redis 失败 | 异常传播或映射为 HTTP 错误（不伪造成功） |

### 8.2 Contract Test

| 场景 | 预期 |
|---|---|
| 无 API Key | `401` `invalid_api_key` |
| 错误 API Key | `401` `invalid_api_key` |
| 有效 Memory Key 创建成功 | HTTP **200 OK**；响应含 `session_id`（UUID v4）+ `status=="created"`；`X-Request-ID` 存在 |
| 缺 `user_id` / 空 body / `user_id=""` | `422` `validation_error`；统一错误包络 |
| 同 `user_id` 连续两次 POST | 两次均 **200 OK**；`session_id` 不同；各自独立 Session |
| Request ID 透传 | 客户端 `X-Request-ID` 与 body `request_id` 一致 |
| 响应不含 WM 内部字段 | 不泄露 `compression_version` 等于 HTTP `status` 混淆 |

### 8.3 Integration Test（真实 Redis）

| 场景 | 预期 |
|---|---|
| compose test 栈 Redis | 经 `scripts/compose.sh --stack=test` 启动 **仅 redis**（或复用 migrate 测试 fixture 模式）；禁止 dev 栈 |
| 创建后 HGETALL meta | `status==active`、`compression_version==0`；`pending_archive_id`/`pending_archive_batch_key` 为 `""`；`pending_archive_message_count`/`pending_archive_token_count` 为 `"0"`；`user_id`/`session_id` 匹配 |
| Key 模板 | 等于 `working_memory_meta_key(user_id, session_id)` |
| 无消息副作用 | `EXISTS` messages/message_ids Key 为 0 **或** Key 不存在 |
| 用户隔离 | `user_a` 与 `user_b` 各创建；互不可见对方 meta Key |
| 无 TTL | `TTL meta_key == -1` |
| 同 `user_id` 重复创建 | 两次 POST → 两个不同 `session_id`；各自 meta Key 存在且字段完整；**不**返回 409 |

### 8.4 E2E Test

| 场景 | 预期 |
|---|---|
| 全链路 E2E | **不适用**（STM-013） |

### 8.5 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| Redis 连接失败（mock） | API 返回错误；无假成功 |
| 并发双创建同 user | 两个不同 `session_id`；各自独立 meta Hash |
| UUID 碰撞 / meta 已存在 | 本任务不专项测试；repository 仍为无条件 `HSET`（碰撞可忽略） |

---

## 9. 验收标准

- [ ] `POST /api/v1/memory/session` 可用；Request/Response 符合 §1.2.3（`user_id` 入参；服务端 UUID；`status: "created"`）；成功 HTTP **200 OK**（非 201）
- [ ] `user_id` 缺失/空串 → `422 validation_error`；同 `user_id` 多次 POST → 多个不同 `session_id`
- [ ] Redis meta Hash 写入 `working_memory_meta_key`；`status=active`、`compression_version=0`；pending 字段按 Amendment 001（`""`/`"0"`；禁止 `"null"`；全部 pending 字段写入）
- [ ] **未**预创建 messages/message_ids；**未**执行压缩/消息写入/TTL
- [ ] 复用 STM-001 模型与 Key helpers；**无**第二套 Session/WM 模型
- [ ] 复用 `AppState.redis` 与 DEV-005 鉴权/错误包络/Request ID
- [ ] Amendment 001（Human Contract）四项决议已落实；无未决议分支被实现
- [ ] STM-002 scoped Unit + Contract + Redis Integration 测试通过
- [ ] 全量 `tests/unit` + `tests/contract` 无回归
- [ ] `uv run ruff check .` PASS
- [ ] `uv run mypy src tests scripts` PASS
- [ ] Code Review 无 P0/P1

### 9.1 Release gate（实施阶段结束）

```text
STM-002 scoped tests PASS
+ full unit baseline PASS
+ full contract baseline PASS
+ Redis integration PASS（Docker 可用环境）
+ ruff PASS
+ mypy PASS
+ 无 STM-001 Contract 回归
```

---

## 10. 风险与阻塞项

### 10.1 OPEN_ISSUE（已由 Amendment 001 / Human Contract 关闭）

| ID | 主题 | 状态 | 决议（Amendment 001） |
|---|---|---|---|
| **OI-STM-002-001** | **重复创建 / meta Key 已存在** | **RESOLVED**（Amendment 001 / Human Contract） | 每次 POST 服务端生成新 UUID v4 `session_id`；同 `user_id` 多次调用 → 多个不同 Session；**不**实现客户端 `session_id`、重复检测、幂等复用、HTTP 409；Repository 对新 Key **无条件 `HSET`** |
| **OI-STM-002-002** | **`user_id` 校验规则** | **RESOLVED**（Amendment 001 / Human Contract） | `user_id: str`，`min_length=1`；缺失或空串 → `422 validation_error`；本任务无额外格式限制 |
| **OI-STM-002-003** | **Redis Hash null 编码** | **RESOLVED**（Amendment 001 / Human Contract） | 可选字符串 `None` ↔ Redis `""`；计数字段 → 十进制字符串（如 `"0"`）；**禁止**字面量 `"null"`；创建时写入全部 `pending_archive_*`（§1.2.7） |
| **OI-STM-002-004** | **成功 HTTP 状态码** | **RESOLVED**（Amendment 001 / Human Contract） | Session 创建成功：**HTTP 200 OK**；MVP **不使用** `201 Created` |

### 10.2 其他风险

| 风险 | 缓解 |
|---|---|
| 修改 STM-001 模型破坏 STM-003 前置 | 禁止改 `WorkingMemoryMeta` 除非 blocker；Codec 独立文件 |
| Integration 误用 dev 栈 | 强制 `compose.sh --stack=test`；复制 `test_migrate_infra.py` 隔离策略 |
| 混淆 HTTP `status=created` 与 WM `status=active` | Schema 命名分离；Contract 双断言 |
| DEV-006 / PR #13 | 不得触碰 |

### 10.3 设计文档冲突

- 无已识别规格正文冲突；§10.1 原 **未写明** 项已由 Amendment 001（Human Contract）关闭，不构成规格正文改写。

### 10.4 前置任务

- STM-001、DEV-005：**SATISFIED**。

---

## 11. Git 计划

```yaml
branch: "feat/STM-002-session-creation"
workflow_mode: NORMAL
release_phases:
  PLAN_LANDING:
    - "docs(plan): add STM-002 session creation plan（main）"
    - "git pull --ff-only；创建 exact feat/STM-002-session-creation"
  IMPLEMENTATION_RELEASE:
    - "feat(stm): add session creation API and redis working memory init"
    - "docs(status): record STM-002 implementation commit and PR（feat only）"
    - "gh pr create（base main）"
  POST_MERGE_CLEANUP:
    - "docs(status): complete STM-002 after PR merge（main only）"
    - "删除 exact feat 分支"
expected_commits:
  - "docs(plan): add STM-002 session creation plan"
  - "feat(stm): add session creation API and redis working memory init"
out_of_scope_changes:
  - "消息写入 / Lua / 压缩 / Session Close"
  - "settings / compose / migration"
  - "DEV-006 / PR #13"
  - "STM-001 模型或 Key Contract 变更"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

| 字段 | 内容 |
|---|---|
| 时间 | 2026-08-10 02:38 UTC |
| 触发 | Plan Review SHOULD_FIX（§5/§6.1 测试路径统一；移除 OI-001 skip 指引；§8 测试矩阵对齐）+ Human Contract 四项 MVP 决议 |
| 审批 | Human Contract ratification（规划态；待 Plan Review Round 2 → 人工 `PLAN_APPROVED`） |

**OI-STM-002-001 — RESOLVED**

- `POST /api/v1/memory/session`：每次调用服务端生成新 UUID v4 `session_id`。
- 同一 `user_id` 多次调用 → 多个不同 Session。
- **不**实现：客户端提供 `session_id`、重复检测、幂等复用、HTTP 409。
- Repository：对新 Key **无条件 `HSET`**。

**OI-STM-002-002 — RESOLVED**

- Request `user_id`：类型 `str`，校验 `min_length=1`。
- 缺失或空串 → `422 validation_error`。
- 本任务 **无** 额外 `user_id` 格式限制。

**OI-STM-002-003 — RESOLVED**

- Python `None` → Redis `""`（`pending_archive_id`、`pending_archive_batch_key`）。
- 读取：`""` → Python `None`。
- 计数字段 → 十进制字符串（如 `"0"`）。
- **禁止**字面量 `"null"`。
- 创建时 **必须** 写入全部 `pending_archive_*` 字段（§1.2.7 规则 1）。

**OI-STM-002-004 — RESOLVED**

- Session 创建成功：**HTTP 200 OK**。
- MVP **不使用** `201 Created`。

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-10 02:28 UTC | Planner 初版 | 创建 Task Plan；progress/master_plan 规划态回写 | 未运行（规划-only） | §10.1 四项 OPEN_ISSUE 待 Plan Review |
| 2026-08-10 02:38 UTC | Planner Amendment 001 | 吸收 Human Contract 四项决议；§5/§7/§8/§10 修订；§5 Step 6 与 §6.1 测试路径统一为 `test_session_create_service.py`；移除 OI-001 skip 指引 | 未运行（规划-only） | §10.1 全部 RESOLVED；待 Plan Review Round 2 |
| 2026-08-10 02:52 UTC | Developer 实施 | 新增 `POST /api/v1/memory/session`；WM codec/repository；session_service；app 接线；Unit/Contract/Integration 测试 | STM-002 scoped unit 17 / contract 10 / integration 3 PASS；full unit 269 / contract 59；ruff PASS；mypy PASS（108 files） | 无 Contract 变更；Amendment 001 四项已落实；未 commit |

---

## 14. 实际执行结果

### 14.1 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/api/schemas/memory_session.py` | 创建 — CreateSessionRequest/Response |
| `src/memory_system/api/routes/memory_session.py` | 创建 — POST /api/v1/memory/session |
| `src/memory_system/infrastructure/redis/working_memory_codec.py` | 创建 — meta ↔ Hash 编解码 |
| `src/memory_system/infrastructure/redis/working_memory_repository.py` | 创建 — 无条件 HSET 创建 WM meta |
| `src/memory_system/domain/services/session_service.py` | 创建 — UUID v4 + repository 编排 |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 — 导出 codec/repository |
| `src/memory_system/domain/services/__init__.py` | 修改 — 导出 create_session |
| `src/memory_system/api/app.py` | 修改 — 注册 memory_session router |
| `tests/unit/test_working_memory_redis_codec.py` | 创建 — 编解码 round-trip / pending 语义 |
| `tests/unit/test_session_create_service.py` | 创建 — UUID / 初始字段 / mock redis |
| `tests/contract/test_stm002_contract.py` | 创建 — 鉴权 / 200 OK / 422 / 重复创建 |
| `tests/integration/test_session_create_redis.py` | 创建 — 真实 Redis 字段/隔离/TTL |

### 14.2 与原计划的差异

暂无。

### 14.3 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit (scoped) | `uv run pytest tests/unit/test_session_create_service.py tests/unit/test_working_memory_redis_codec.py -q` | 17 passed |
| Contract (scoped) | `uv run pytest tests/contract/test_stm002_contract.py -q` | 10 passed |
| Integration | `uv run pytest tests/integration/test_session_create_redis.py -q` | 3 passed |
| Unit (full) | `uv run pytest tests/unit -q` | 269 passed |
| Contract (full) | `uv run pytest tests/contract -q` | 59 passed |
| E2E | N/A | |
| Ruff | `uv run ruff check .` | PASS |
| Mypy | `uv run mypy src tests scripts` | PASS（108 files） |

### 14.4 Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 0
review_report: null
```

### 14.5 Git 记录

```yaml
branch: feat/STM-002-session-creation
plan_commit: ac84b31210001f22df4a049d28ff1e90618c244d
implementation_commit: null
implementation_commit_message: null
```

### 14.6 最终状态

`tested` — READY_FOR_CODE_REVIEW
