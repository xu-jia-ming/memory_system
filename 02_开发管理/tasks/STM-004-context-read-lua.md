# STM-004 Context Read Lua

## 1. 任务信息

```yaml
task_id: STM-004
task_name: Context Read Lua
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.1 Redis Working Memory 数据结构设计（规则 7：上下文一致性读取 Lua）"
  - "§1.2.3 Memory API 接口定义（获取当前上下文接口；Lua 读取流程图）"
  - "§1.2.7 Session 生命周期（status=active/closing；无 TTL/闲置清理）"
prerequisites:
  formal:
    - "STM-002 — SATISFIED（`master_plan.md` 权威前置依赖；Session 创建 + WM meta Hash 已在 main；PR #20 MERGED）"
  implementation_reuse:
    - "STM-001 — SATISFIED（`WorkingMemoryMeta`/`WorkingMemoryMessage`、Key helpers、codec 已在 main；PR #19 MERGED）"
    - "STM-003 — SATISFIED（`write_message` Integration 种子（I2 等）、`json_to_message` 解码；PR #21 MERGED；**非** master_plan 正式前置）"
  baseline:
    - "规划基线（本轮只读）：main @ b9fda716b0775eeeb6a351f6e194303ed18e7c7f；STM-003 后 full unit 287 / contract 62 / integration 11 / ruff PASS / mypy PASS"
    - "本任务不需要 SiliconFlow / LLM / TEI / Mongo / Kafka / ES / Neo4j / HTTP 路由网络调用"
branch: "feat/STM-004-context-read-lua"
created_at: "2026-08-10 06:38 UTC"
updated_at: "2026-08-10 07:38 UTC"
approval_gates:
  planning_docs: "pending Plan Review Round 3 → READY_FOR_PLAN_REVIEW；本轮不得 PLAN_APPROVED / 不得实施"
  implementation_plan: "status=planned；不得 Developer / 不得 Git 写"
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
  - "实现 HTTP GET 路由、压缩写回、STM-005+"
```

---

## 2. 任务目标

交付 **领域层上下文读取服务 + Redis 单 Lua 只读原子脚本**，使 STM-009 可接线 `GET /api/v1/memory/working/{user_id}/{session_id}`：

1. **输入契约**（§1.2.3）：`user_id`、`session_id` — **仅此二项**；无其他业务输入。
2. **Session 校验内部语义**（对齐 STM-003 用户隔离；**本任务不定义 HTTP 映射**）：
   - meta Key 不存在 → `session_not_found`；
   - Hash `user_id` / `session_id` 与请求不一致 → `session_not_found`（身份校验 **先于** 任何数据读取；不匹配不返回独立 `ownership_mismatch`）；
   - `status=active` **与** `status=closing` **均允许成功读取**（关闭流程期间 WM 数据仍在 Redis；§1.2.3 读取流程图 **未** 要求 `status==active`；写入/压缩的 `session_closing` 语义 **不** 适用于只读路径）。
3. **原子一致性快照**（§1.2.1 规则 7 + §1.2.3）：单 Lua 在同一次脚本执行窗口内读取 `compression_version`、`compressed_context`、messages List（`LRANGE 0 -1`），保证三者属于同一 Redis 状态，避免应用层 `HGET` + `LRANGE` 分步读在压缩 `LTRIM`/摘要更新之间产生 **torn read**（旧 `compressed_context` + 已裁剪消息列表的混合态）。
4. **Lua 严格只读**（OI-009 Planner 决议）：脚本内 **禁止** `HSET`/`SET`/`RPUSH`/`LPUSH`/`SADD`/`DEL`/`EXPIRE`/`INCR` 及任何写操作；**不** 更新 `updated_time`（见 §10.1 OI-009）；**不** 读取 `message_ids` Set（本快照不需要幂等键）。
5. **快照模型**：`compression_version`（整型）、`compressed_context`（字符串；Redis `""` ↔ Python `""`，**禁止** 转为 `None`）、`messages: list[WorkingMemoryMessage]`（List 顺序；复用 STM-003 `json_to_message` 解码）。
6. **fail-closed**：meta 中 `compression_version` 缺失/非整型 → `invalid_session_state`；`compressed_context` 字段缺失 → `invalid_session_state`（Redis `""` 合法，见 I8）；List 元素 JSON 畸形 → `json_to_message` 抛出 `JSONDecodeError`/`KeyError`/`ValueError` 时，服务层 **捕获并映射** 为 `ContextReadFailure`（领域异常；见 §5 Step 4；**HTTP 状态码映射由 STM-009 负责，本任务不定义**）；**不** 静默跳过、**不** 部分返回。
7. **测试**：Unit（结果映射、快照解码、畸形 fail-closed、codec 复用）+ Contract（`ContextReadStatus` 字面量稳定）+ Integration（真实 Redis；**13 场景**，见 §8.3）。

完成后 STM-009 可依赖本任务的读取服务与 Lua；与 STM-003 写入 **共享** STM-001 Key helpers，**并行独立**。

---

## 3. 非目标（必须坚持；黑名单语义）

- **`GET /api/v1/memory/working/{user_id}/{session_id}` HTTP 路由**、Pydantic Response Schema、鉴权接线（**STM-009**；§1.2.3 端点存在但本任务不实现 HTTP 层）。
- 压缩写回、`compression_version` 递增、Finalize Lua、压缩锁、Coordinator（**STM-006～009**）。
- 消息写入语义修改（**不得**改 STM-003 Lua/服务/测试断言）。
- Mongo `context_archive`、Kafka、Compression LLM、Session Close（**STM-005+**）。
- Redis TTL / EXPIRE / 闲置 Session 扫描 / 自动关闭（§1.2.7 规则 12；OI-009 禁止引申）。
- 读取路径更新 `updated_time`（§10.1 OI-009 Planner 决议；与规格字面「读取时更新」的偏离 **仅** 在本任务 OI-009 决议内实施）。
- 第二套 WM Key 模式；读取 `message_ids` Set。
- 修改 STM-001 `WorkingMemoryMeta`/`WorkingMemoryMessage` 字段集；修改 STM-002 创建语义；修改 STM-003 write codec。
- 操作 **DEV-006** / **PR #13**。
- 修改 `settings/**`、`.env.example`、`configs/**`、`compose*.yaml`、Migration。
- 自动 Push / Merge / Rebase / Force Push。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `b9fda716b0775eeeb6a351f6e194303ed18e7c7f`（`docs(status): complete STM-003 after PR merge`） |
| `git status --short` | clean |
| formal STM-001 | `completed`（PR #19 MERGED） |
| formal STM-002 | `completed`（PR #20 MERGED） |
| formal STM-003 | `completed`（PR #21 MERGED） |
| baseline（STM-003 tested） | unit 287 / contract 62 / integration 11 / ruff PASS / mypy PASS |

### 4.2 STM-001/002/003 复用审计（不得新建第二套模型）

| 交付物 | 路径 | STM-004 用法 |
|---|---|---|
| `working_memory_meta_key` / `working_memory_messages_key` | `infrastructure/redis/keys.py` | **直接复用**；禁止内联 Key 字符串；**不**使用 `working_memory_message_ids_key` |
| `hash_fields_to_meta` / `meta_to_hash_fields` | `infrastructure/redis/working_memory_codec.py` | Integration 种子/断言；理解 `compressed_context`/`compression_version` Redis 字段格式 |
| `message_to_json` / `json_to_message` | `infrastructure/redis/working_memory_message_codec.py` | Lua 返回的 List 元素 **必须** 经 `json_to_message` 解码；畸形 fail-closed |
| `WorkingMemoryMessage` | `domain/models/working_memory.py` | 快照 `messages` 元素类型；**不**修改模型 |
| `WorkingMemoryMeta` | 同上 | 参考字段；快照 **不** 要求返回完整 meta（仅读路径所需三字段 + messages） |
| `create_working_memory_session` | `infrastructure/redis/working_memory_repository.py` | Integration 前置 |
| `write_message` | `domain/services/message_write_service.py` | Integration 种子消息（I2 等）；**不** 用于 I12（I12 使用 `tests/integration/**` 内 test-only 原子 mutator，见 §8.3.1） |
| `AppState.redis` | `infrastructure/runtime.py` | Integration 注入真实 Redis |
| `MessageWriteStatus` 校验模式 | `message_write_repository.py` | 参照 `parse_*_lua_result` fail-closed 模式 |

**结论**：WM 结构与 Key 契约已由 STM-001～003 建立；本任务 **新增** 只读 Lua + 领域读取服务，**不**改既有写入/创建 Contract。

### 4.3 规格摘录（权威；STM-004 范围）

**HTTP Response 字段**（§1.2.3 — **STM-009 实现 HTTP；本任务内部快照对齐同语义**）：

| 字段 | STM-004 内部快照 |
|---|---|
| `compression_version` | 必填整型；来自同一次 Lua 窗口 |
| `compressed_context` | 必填字符串；允许 `""` |
| `messages` | `WorkingMemoryMessage` 列表；按 Redis List 顺序；含 `estimated_tokens`（Redis 存储字段；HTTP 层可由 STM-009 裁剪） |

**读取 Lua 原子步骤**（§1.2.1 规则 7 + §1.2.3 流程图 — **本任务实现；OI-009 修订写操作**，见 §10.1）：

1. 检查 meta Key 存在性（`EXISTS`）；不存在 → `session_not_found`
2. 校验 Hash `user_id` / `session_id` 与请求一致；不匹配 → `session_not_found`
3. **不** 因 `status != active` 拒绝读取（`closing` 仍可读）
4. `HGET compression_version`；缺失或 `tonumber` 失败 → `invalid_session_state`
5. `HGET compressed_context`；缺失 → `invalid_session_state`；Redis `false`/空 → 当作 `""` 返回（与 STM-002 codec `""` 语义一致）
6. `LRANGE messages_key 0 -1` 获取全部近期消息（同脚本窗口）
7. **不** 执行 `updated_time` 或任何写操作
8. 将 `success` + 三字段数据一次性返回给 Python

**为何必须 Lua（Plan Reviewer 关注点）**：

| 分步读风险 | Lua 保证 |
|---|---|
| 线程 A：`HGET compression_version=2` | 单脚本执行期间 Redis 不插入其他命令 |
| 线程 B：Finalize `LTRIM` + 更新 `compressed_context` | `LRANGE` 与 `HGET` 在同一原子窗口 |
| 线程 A：`LRANGE` 得裁剪后列表 | 返回的 version/context/messages **一致** |

**HTTP 路由归属**：§1.2.3 定义 `GET /api/v1/memory/working/{user_id}/{session_id}`，但 `master_plan.md` STM-009 负责 API 接线；STM-004 master_plan 条目为「上下文一致性读取 Lua」— **HTTP 留给 STM-009**。

### 4.4 当前缺失

- 上下文读取领域服务与内部结果/快照类型。
- 上下文读取 Redis Lua 脚本及 `register_script` 封装。
- context read repository（调用 Lua + 解析结果 + 消息解码）。
- Unit / Contract / Redis Integration 测试（13 场景）。

### 4.5 与技术规格不一致之处

- §1.2.1 规则 7 / §1.2.3 / §1.2.7 规则 2 字面要求读取时更新 `updated_time` — **§10.1 OI-009 Planner 决议**：本任务 Lua **只读、不更新** `updated_time`（见决议全文）；不得在 STM-004 引入 TTL/自动关闭。
- §1.2.3 读取流程图含 “Update updated_time” 步骤 — **同上 OI-009 决议**，该步骤在 STM-004 **省略**；若未来需恢复，须单独 Spec-OI / 人工决议，不得由本任务悄悄写回。
- `session_not_found` 在 §1.2.7 Close 路径有明确定义；读取路径未逐字列出身份不匹配 — **沿用 STM-003 OI-STM-003-002 先例**（meta 缺失或 Hash 身份字段不匹配 → `session_not_found`）。

---

## 5. 实现方案（仅供后续 Developer；本轮不执行）

### 硬约束（实施时强制）

1. **复用** STM-001 Key helpers、STM-002 codec 字段格式、STM-003 `json_to_message`；禁止第二套消息模型/Key。
2. **复用** `AppState.redis`；禁止独立 Redis 连接池。
3. **单 Lua 只读脚本** 完成 §4.3 读取步骤；禁止应用层 `HGET` + `LRANGE` 分步读。
4. **Lua 禁止** 任何写命令；Integration 必须证明 `updated_time`/`compression_version`/List 长度与内容在读前后不变。
5. **不实现** HTTP、压缩、Kafka、Mongo。
6. **`compressed_context`**：Redis `""` → Python `""`；禁止 `None` 替代。
7. 业务代码必须同时含对应测试；失败不得 skip/xfail/降标准。

### Step 1 — 内部结果枚举与快照领域类型

- **文件**：`src/memory_system/domain/enums/context_read.py`（创建）。
- **枚举 `ContextReadStatus`**（稳定内部字面量）：

  | 值 | 含义 | Lua 返回 |
  |---|---|---|
  | `success` | 快照读取成功 | 是 |
  | `session_not_found` | meta 不存在或身份字段不匹配 | 是 |
  | `invalid_session_state` | `compression_version` 等 meta 字段缺失/畸形 | 是 |

- **文件**：`src/memory_system/domain/models/context_read.py`（创建）。
- **`ContextReadInput`**：`user_id: str`、`session_id: str`。
- **`WorkingMemorySnapshot`**：`compression_version: int`、`compressed_context: str`、`messages: list[WorkingMemoryMessage]`。
- **`ContextReadResult`**：`status: ContextReadStatus`；`snapshot: WorkingMemorySnapshot | None`（仅 `success` 时非空）。

### Step 2 — 上下文读取 Lua 脚本

- **文件**：`src/memory_system/infrastructure/redis/scripts/context_read.lua`（创建）。
- **KEYS**（2）：
  - `KEYS[1]` = meta Hash key（`working_memory_meta_key`）
  - `KEYS[2]` = messages List key（`working_memory_messages_key`）
- **ARGV**（2）：
  - `ARGV[1]` = `expected_user_id`
  - `ARGV[2]` = `expected_session_id`
- **逻辑**（顺序固定；**只读**）：

  ```text
  EXISTS meta → session_not_found
  HGET user_id/session_id → 与 ARGV 比对 → 不匹配 session_not_found
  HGET compression_version → tonumber 失败 → invalid_session_state
  HGET compressed_context → nil 字段 → invalid_session_state；false → ""
  LRANGE messages 0 -1
  return {status, compression_version_str, compressed_context, ...message_elements}
  ```

- **返回契约**：
  - 错误：单字符串 `'session_not_found'` 或 `'invalid_session_state'`
  - 成功：数组 `{ 'success', compression_version, compressed_context, msg_json_1, ... }`（`compression_version` 为字符串数字；messages 可为空数组即仅 3 元素）

- **禁止**：`message_ids` Key；任何写命令；`cjson` 编解码消息（List 元素已是 JSON 字符串，原样传递）。

### Step 3 — Script loader 与 repository

- **文件**：`src/memory_system/infrastructure/redis/context_read_script.py`（创建）。
- **`load_context_read_lua()`** / **`run_context_read_lua(...)`**：`register_script` + `keys`/`args` 传参。
- **文件**：`src/memory_system/infrastructure/redis/context_read_repository.py`（创建）。
- **`parse_context_read_lua_result(raw) -> ContextReadStatus | tuple`**：错误字符串映射枚举；成功数组解析。
- **`execute_context_read_lua(...) -> ContextReadStatus | tuple[str, str, list[str]]`**：调用 script；成功时返回 `(compression_version, compressed_context, message_jsons)`。

### Step 4 — 领域读取服务

- **文件**：`src/memory_system/domain/services/context_read_service.py`（创建）。
- **`read_working_memory_context(*, redis, input: ContextReadInput) -> ContextReadResult`**：
  1. 调用 `execute_context_read_lua`
  2. `session_not_found` / `invalid_session_state` → 无 snapshot 返回
  3. `success` → `int(compression_version)`；`compressed_context` 保持 `str`（`""` 合法）
  4. 对每条 message JSON 调用 `json_to_message`；**任一** `JSONDecodeError`/`KeyError`/`ValueError` → 捕获并抛出 **`ContextReadFailure`**（领域异常；fail-closed；Integration I11 覆盖）
  5. 组装 `WorkingMemorySnapshot` 返回

- **`ContextReadFailure`**（领域异常；`context_read_service.py` 或同级 `exceptions` 模块）：表示 Lua 成功返回后 Python 层快照组装失败（畸形 message JSON、字段类型不符等）；**不** 用于 Lua 层 `session_not_found`/`invalid_session_state`（后者走 `ContextReadResult.status`）；**不** 在本任务定义 HTTP 状态码或 Response 映射（**STM-009** 负责将领域异常接线为 HTTP 错误响应）。

- **不** 接受 `clock` 参数（无 `updated_time` 写入）。

### Step 5 — 测试

见 §8。Integration 复用 STM-003 的 `compose.sh --stack=test` 隔离策略。

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/enums/context_read.py` | 创建 | `ContextReadStatus` 内部枚举 |
| `src/memory_system/domain/models/context_read.py` | 创建 | `ContextReadInput`、`WorkingMemorySnapshot`、`ContextReadResult` |
| `src/memory_system/domain/services/context_read_service.py` | 创建 | `read_working_memory_context` 领域服务 |
| `src/memory_system/infrastructure/redis/scripts/context_read.lua` | 创建 | 只读原子快照 Lua |
| `src/memory_system/infrastructure/redis/context_read_script.py` | 创建 | Lua loader/runner |
| `src/memory_system/infrastructure/redis/context_read_repository.py` | 创建 | Lua 调用 + 结果解析 |
| `src/memory_system/domain/enums/__init__.py` | 修改 | 最小导出 `ContextReadStatus`（若生产 import 需要） |
| `src/memory_system/domain/models/__init__.py` | 修改 | 最小导出 `ContextReadInput`/`WorkingMemorySnapshot`/`ContextReadResult`（若生产 import 需要） |
| `src/memory_system/domain/services/__init__.py` | 修改 | 最小导出 `read_working_memory_context`（若生产 import 需要） |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 | 最小导出 context read script/repository（若生产 import 需要） |
| `tests/unit/test_context_read_status_mapping.py` | 创建 | Lua 结果 → 枚举映射；未知值 fail-closed |
| `tests/unit/test_context_read_service.py` | 创建 | 快照组装、`""` 语义、畸形解码 fail-closed（Fake Redis / mock repository） |
| `tests/contract/test_stm004_contract.py` | 创建 | `ContextReadStatus` 字面量稳定 |
| `tests/integration/test_context_read_redis.py` | 创建 | 13 场景真实 Redis Integration（含 I12 三段式 torn-read 证明） |
| `tests/integration/context_read_torn_read_helpers.py` | 创建 | **test-only**：原子 mutator、broken split-reader、barrier 协调（**禁止** `src/**`） |
| `02_开发管理/tasks/STM-004-context-read-lua.md` | 创建 | 本 Task Plan |
| `02_开发管理/progress.md` | 修改 | 规划态字段 |
| `02_开发管理/master_plan.md` | 修改 | STM-004 登记 + CHANGE-032 |

**白名单外禁止修改**（含但不限于）：`settings/**`、STM-003 写入路径、`api/routes/**`、compose/migration、DEV-006。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | **适用** | 单 Lua 读取 `compression_version` + `compressed_context` + `LRANGE`；避免 torn read |
| 幂等 | **适用（只读）** | 相同 `user_id`+`session_id` 重复读取不改变 Redis；返回当时快照 |
| 并发 | **适用** | 与邻接写并发时，生产单 Lua reader 每次读获得 **规范态** 快照（`NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID`）；Integration I12 三段式证明：test-only **原子** mutator + broken split-reader 负对照 + 生产 Lua 正对照（§8.3.1） |
| 版本冲突 | **不适用** | 只读；不校验/不递增 `compression_version` |
| 用户隔离 | **适用** | Hash `user_id`/`session_id` 与请求比对；不匹配 → `session_not_found` |
| 部分失败 | **适用** | Lua 错误 → 无 snapshot；消息 JSON 畸形 → 全请求 fail-closed，不返回部分 messages |
| 进程异常恢复 | **不适用** | 只读无副作用；无状态需恢复 |

---

## 8. 测试计划

### 8.1 Unit Test

| 场景 | 预期 |
|---|---|
| U1 `ContextReadStatus` 字面量 | `success`/`session_not_found`/`invalid_session_state` 稳定 |
| U2 成功快照组装 | `compression_version` 整型、`compressed_context` 字符串、`messages` 列表 |
| U3 `compressed_context=""` | Redis/Lua 返回 `""` → Python `""`，非 `None` |
| U4 `session_not_found` 映射 | 无 snapshot |
| U5 `invalid_session_state` 映射 | 无 snapshot |
| U6 未知 Lua 返回 | `ContextReadLuaError`（或同等 fail-closed） |
| U7 畸形 message JSON | `json_to_message` 触发 `JSONDecodeError`/`KeyError`/`ValueError` → 服务层 **`ContextReadFailure`**；无 snapshot；不部分返回 |
| U8 空 messages 列表 | Lua 成功返回 **最小 3 元素数组** `{ 'success', compression_version, compressed_context }`（无 message 元素）；Python `messages=[]` 合法成功 |

### 8.2 Contract Test

| 场景 | 预期 |
|---|---|
| C1 `test_stm004_contract.py` | `ContextReadStatus` 枚举值与 Lua 返回字符串集合一致 |
| C2 Lua 返回集合 | 仅 `success`/`session_not_found`/`invalid_session_state` 三种 |

### 8.3 Integration Test（真实 Redis；13 场景）

| # | 场景 | 预期 |
|---|---|---|
| I1 | 新建 Session（STM-002）空 WM | `success`；`compression_version=0`；`compressed_context=""`；`messages=[]` |
| I2 | STM-003 写入多条消息后读取 | `success`；messages 顺序与 List 一致；字段与写入 JSON 一致 |
| I3 | 种子 `compressed_context` + `compression_version>0` | 快照含对应摘要与版本 |
| I4 | meta Key 不存在 | `session_not_found`；零 Redis 写 |
| I5 | 错误 `user_id`（Hash 不匹配） | `session_not_found` |
| I6 | 错误 `session_id`（Hash 不匹配） | `session_not_found` |
| I7 | `status=closing`（HSET 模拟） | `success`；仍返回当前快照（**非** `session_closing`） |
| I8 | Redis `compressed_context=""` | Python `snapshot.compressed_context == ""` |
| I9 | meta `compression_version` 非整型 / 缺失 | `invalid_session_state` |
| I10 | meta `compressed_context` 字段缺失（HDEL） | `invalid_session_state`（fail-closed；与 §4.3「缺失 → invalid_session_state」一致；**区别于** I8 空字符串合法） |
| I11 | List 中一条畸形 JSON | 服务层 **`ContextReadFailure`**；Integration 断言无部分成功 Response；**不** 断言 HTTP 状态（STM-009 职责） |
| I12 | **读者组合 torn-read 三段式证明（`NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID`）** | 见 §8.3.1：Part B 负对照确定性构造混合态；Part C 生产 Lua 正对照每次 success **仅** `OLD_STATE` 或 `NEW_STATE` |
| I13 | **只读零写入** | 读取前后：`updated_time`、`compression_version`、`estimated_tokens`、List 内容、`message_ids` 基数 **不变**；`TTL=-1`；重复读取两次结果确定性一致（同 Redis 状态下） |

#### 8.3.1 Integration I12 — `NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID` 读者组合 torn-read 三段式设计

**证明目标（Amendment 002 权威）**：STM-004 证明 **reader-composed torn snapshot prevention**（读者分步组合导致的不一致快照可被避免），**不** 证明隐藏 writer 瞬态中间态。Writer 在测试中仅通过 **原子** 跃迁在 `OLD_STATE` ↔ `NEW_STATE` 间切换；Redis 已提交态 **仅** 允许这两种规范态，**禁止** V1+C0+M0 等中间混合作为持久态。

**不变量名称**：`NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID` — 生产路径 `read_working_memory_context` 任意 `status=success` 快照 `(compression_version, compressed_context, messages)` **必须** 完整匹配 `OLD_STATE` **或** `NEW_STATE` 三元组，不得为读者分步读组合出的混合态。

**规范态定义**（测试内 `CanonicalState` helper；V0/C0/M0 与 V1/C1/M1 **两两字段均不同**）：

| 态 | `compression_version` | `compressed_context` | `messages`（按 List 顺序） |
|---|---|---|---|
| `OLD_STATE` | V0 | C0 | M0（N 条，内容可辨识） |
| `NEW_STATE` | V1 | C1 | M1（裁剪后 K 条，K<N；内容与 M0 不同） |

**范围约束**：

- test-only mutator、broken split-reader、barrier 协调 **仅** 位于 `tests/integration/**`（含 `context_read_torn_read_helpers.py`）；**禁止** 进入 `src/**`。
- **禁止** STM-008 Finalize Lua、压缩 coordinator、生产写 repository/helper。
- **禁止** Mongo / Kafka / LLM / HTTP。

---

##### Part 1 — 原子 test-only writer transition（`tests/integration/**` only）

**职责**：在 OLD↔NEW 间切换 Redis WM 状态；**单次 Redis 原子操作**内完成 `compression_version` + `compressed_context` + messages `LTRIM` 三字段同步更新。

**允许实现**（二选一）：

1. test-only Lua script（`EVAL`/`register_script` 于测试模块内，**不** 落 `src/`）；或
2. `MULTI`/`EXEC` 事务包裹 `HSET compression_version` + `HSET compressed_context` + `LTRIM messages`。

**禁止**：三条独立 `HSET`/`LTRIM` 分步命令（非原子 mutator 与 OLD/NEW-only 断言冲突 — Round 2 MF-2 驳回根因）。

**不变量**：mutator 每次成功执行后，Redis 已提交态 **仅** `OLD_STATE` 或 `NEW_STATE`；**不存在** V1+C0+M0、V0+C1+M1 等持久中间态。

---

##### Part 2 — Broken split-reader 负对照（`tests/integration/**` only；**非** `src/**`）

**职责**：**确定性**证明分步读可构造禁止混合态；**非**「多次运行碰运气」。

**Broken reader 语义**（应用层三次往返，**不得** 调用生产 `read_working_memory_context` / 生产 Lua）：

```text
HGET compression_version → HGET compressed_context → LRANGE messages 0 -1
```

**确定性 barrier 序列**（`asyncio.Event` / `threading.Barrier` 或等价；步骤间 **必须** 可观测暂停）：

| 步骤 | 动作 | 说明 |
|---|---|---|
| A | broken reader 读取 `compression_version` | 得到 V0（OLD） |
| B | barrier **暂停** broken reader | 在读取 C/M **之前** 阻塞 |
| C | 原子 mutator 执行 OLD→NEW（单次原子 op） | Redis 提交态变为 NEW_STATE |
| D | barrier **恢复** broken reader | 继续读取 `compressed_context` 与 messages |
| E | broken reader 完成分步读 | 组合快照为 **V0 + C1 + M1** |

**负对照断言**（本 Part **必须 PASS** = 成功构造禁止混合态）：

```python
assert snapshot_matches(composed, FORBIDDEN_HYBRID)  # V0 + C1 + M1
assert not (snapshot_matches(composed, OLD_STATE) or snapshot_matches(composed, NEW_STATE))
```

证明：分步读在 writer 原子跃迁窗口内可观测 **读者组合 torn snapshot**；该混合态 **禁止** 作为生产读取结果。

---

##### Part 3 — 生产 Lua reader 正对照

**职责**：同一 OLD/NEW 原子跃迁下，调用生产 `read_working_memory_context()`（单 Lua 只读脚本）；验证生产路径 **不** 返回读者组合混合态。

**执行模型**：

1. 种子 `OLD_STATE`。
2. **有界并发循环**（建议 N=50～200，**非** 无限 stress）：后台 task 反复 **原子 toggle** OLD↔NEW；前台并发调用 `read_working_memory_context`。
3. 每次 `status=success`：

```python
assert snapshot_matches(snapshot, OLD_STATE) or snapshot_matches(snapshot, NEW_STATE)
# 禁止任一混合态，例如 V0+C1+M1、V1+C0+M0、V1+C1+M0 等
```

**正对照断言**（本 Part **必须 PASS** = 仅规范态）。

---

##### 测试有效性对照表（Plan 必须包含；Developer 实现时两 Part 均须存在）

| 组合 | 读取实现 | 预期结果 | 证明 |
|---|---|---|---|
| **A** | 原子 mutator + **broken split-reader**（Part 2 barrier） | **可构造**禁止混合态 V0+C1+M1；负对照 **PASS** | 分步读本身会产生 torn snapshot |
| **B** | 原子 mutator + **生产单 Lua reader**（Part 3） | 每次 success **仅** OLD_STATE 或 NEW_STATE；正对照 **PASS** | 单 Redis Lua 避免读者侧 torn snapshot |

**结论**：I12 直接验证 STM-004 核心设计动机（§4.3 规则 7）— 问题在 **读者分步组合**，非 writer 瞬态；生产单 Lua 读路径消除该风险。若生产实现退化为分步读，Part 3 **必须** 失败。

**实现提示**（非验收放宽）：

- Part 2 与 Part 3 可为同一测试文件内两个 test case，或 `test_context_read_redis.py` + `context_read_torn_read_helpers.py` 分工。
- barrier 须可单测/日志佐证步骤 A→E 顺序（避免假阳性）。

### 8.4 E2E Test

| 场景 | 预期 |
|---|---|
| — | **不适用**（无 HTTP；E2E 由 STM-009/STM-013 覆盖） |

### 8.5 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| I12 读者组合 torn-read 三段式 | §8.3.1：原子 test-only mutator + broken split-reader 负对照 + 生产 Lua 正对照 |
| I13 零写入 | 见 §8.3 |
| 畸形 meta/message | I9/I10/I11 fail-closed |

### 8.6 质量门禁（Developer 完成时）

```text
uv run pytest tests/unit/test_context_read_*.py tests/unit/test_working_memory_message_codec.py -q
uv run pytest tests/contract/test_stm004_contract.py -q
uv run pytest tests/integration/test_context_read_redis.py -q
uv run pytest tests/unit -q
uv run pytest tests/contract -q
uv run ruff check .
uv run mypy src tests scripts
```

---

## 9. 验收标准

- [x] `read_working_memory_context(user_id, session_id)` 经单 Lua 返回一致快照（`compression_version` + `compressed_context` + `messages`）
- [x] Lua 脚本 **只读**；Integration I13 证明无 `updated_time`/消息/meta 变更
- [x] 复用 `working_memory_meta_key` + `working_memory_messages_key`；不读 `message_ids`
- [x] 复用 STM-003 `json_to_message`；畸形消息 → **`ContextReadFailure`**（非裸 `JSONDecodeError`/`KeyError`）；**不** 在本任务定义 HTTP 映射（STM-009）
- [x] 空 messages：Lua 返回最小 3 元素成功数组；Python `messages=[]`
- [x] `compressed_context` Redis `""` ↔ Python `""`；字段 **缺失** → `invalid_session_state`（I10）
- [x] `session_not_found`（缺失/身份不匹配）；`invalid_session_state`（畸形 version / 缺失 compressed_context）
- [x] `status=closing` 可读；读取 **不** 返回 `session_closing`
- [x] OI-009 决议落实在 Lua（无 `updated_time` 写；无 TTL）
- [x] Integration 13 场景全通过（含 I12 `NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID` 三段式证明）
- [x] STM-004 scoped unit + contract + full unit/contract 无回归
- [x] Ruff / Mypy 通过
- [ ] Review 无 P0/P1
- [x] 白名单外零 diff

---

## 10. 风险与阻塞项

### 10.1 OI-009 决议（Planner；本任务 **MUST_FIX** 落实）

| 字段 | 内容 |
|---|---|
| **ID** | OI-009 |
| **规格章节** | §1.2.3、§1.2.7 规则 2、§1.2.1 规则 7 |
| **问题** | 规格字面要求 GET 上下文时 Lua 更新 `updated_time`；与 MVP「不做 idle session 清理 / 无 TTL」（§1.2.7 规则 12）并存时，实现者易误将 `updated_time` 当作闲置计时器并引申 TTL/自动 Close |
| **Planner 决议（STM-004）** | **RESOLVED** — 本任务上下文读取 Lua 为 **严格只读**：**不** `HSET updated_time`；**不** 引入 Redis TTL/EXPIRE/闲置扫描/自动关闭；`updated_time` 仅由 **写入**（STM-003）与未来 **压缩写回**（STM-008）更新；被动读取不视为「会话活动」 |
| **与规格字面偏离** | 有意省略 §1.2.3 流程图 “Update updated_time” 步骤；偏离范围 **仅限** 本任务 Lua 读路径；若产品要求恢复「读触达更新时间」，须 future Spec-OI 或 STM-009 HTTP 层单独决议，**不得**由 STM-004 悄悄写回 |
| **验收** | Integration I13：`updated_time` 读前后不变；全 Key `TTL=-1` |
| **open_issues.md** | 实施完成 + POST_MERGE 时由治理流程将 OI-009 标为 `resolved` 并追加决议记录（本轮 Plan 仅文档决议） |

### 10.2 OPEN_ISSUE（Planner 决议；待 Plan Review 确认）

| ID | 主题 | 状态 | 决议 |
|---|---|---|---|
| **OI-STM-004-001** | 读取路径 `status=closing` 语义 | **RESOLVED**（Planner） | 只读路径 **允许** `closing`；返回当前 WM 快照；**不** 映射 `session_closing`（该码保留给写入/压缩） |
| **OI-STM-004-002** | meta 缺失 vs 身份不匹配 | **RESOLVED**（Planner） | 沿用 STM-003：**均** `session_not_found` |
| **OI-STM-004-003** | `compression_version` 畸形 | **RESOLVED**（Planner） | Lua 返回 `invalid_session_state`；Python fail-closed |

### 10.3 其他风险

| 风险 | 缓解 |
|---|---|
| Lua 成功返回数组解析脆弱 | repository 单测 + Integration I2/I3 |
| 与邻接写 torn-read | Integration I12 三段式 + 不变量 `NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID`（§8.3.1）；原子 mutator 仅 test-only |
| 误实现 `updated_time` 写 | §10.1 决议 + I13 断言 |
| Integration 误用 dev 栈 | 强制 `compose.sh --stack=test` |
| DEV-006 / PR #13 | 不得触碰 |

### 10.4 设计文档冲突

- §1.2.3「读取时更新 `updated_time`」与 §10.1 OI-009 决议 — **已在计划内明确偏离**；非未决阻塞。
- §1.2.3 HTTP 端点 — master_plan STM-009 接线；**非冲突**。

### 10.5 前置任务

- **正式前置**（`master_plan.md` 权威）：STM-002 — **SATISFIED**。
- **实现/测试复用**（非 master_plan 正式前置）：STM-001（Key/codec/模型）、STM-003（`write_message` 种子、`json_to_message`）— **SATISFIED**。

---

## 11. Git 计划

```yaml
branch: "feat/STM-004-context-read-lua"
workflow_mode: NORMAL
release_phases:
  PLAN_LANDING:
    - "docs(plan): add STM-004 context read lua plan（main）"
    - "git pull --ff-only；创建 exact feat/STM-004-context-read-lua"
  IMPLEMENTATION_RELEASE:
    - "feat(stm): add context read lua and domain service"
    - "docs(status): record STM-004 implementation commit and PR（feat only）"
    - "gh pr create（base main）"
  POST_MERGE_CLEANUP:
    - "docs(status): complete STM-004 after PR merge（main only）"
    - "删除 exact feat 分支"
    - "open_issues.md：OI-009 追加 resolved 决议记录"
expected_commits:
  - "docs(plan): add STM-004 context read lua plan"
  - "feat(stm): add context read lua and domain service"
out_of_scope_changes:
  - "HTTP GET 路由 / compression / Coordinator"
  - "STM-003 写入语义变更"
  - "settings / compose / migration"
  - "DEV-006 / PR #13"
  - "STM-001/002/003 Contract 破坏性变更"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001（2026-08-10 — PLAN_REMEDIATION Round 2）

**触发**：Plan Review Round 1 `PLAN_REJECTED` — BLOCKER=0、MUST_FIX=1（MF-1：I11 torn-read 测试空洞）。

| 项 | 修订 |
|---|---|
| **MF-1 I11** | 替换 `write_message` 并发循环为 **对抗性 torn-read**：test-only 原始 `HSET`/`LTRIM` mutator（非 STM-008 Finalize）；规范态 `OLD_STATE`/`NEW_STATE`；不变量 `NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID`；§8.3.1 全文 |
| **SF-1 前置依赖** | 区分 **正式前置**（STM-002，`master_plan` 权威）与 **实现/测试复用**（STM-001、STM-003）；§1 prerequisites、§10.5 |
| **SF-2 畸形 JSON** | `json_to_message` 的 `JSONDecodeError`/`KeyError`/`ValueError` → 服务层 **`ContextReadFailure`**；§2、§5 Step 4、§8 U7/I10、§9 |
| **SF-3 空 messages** | Lua 成功返回 **最小 3 元素数组**；§8 U8 |
| **SF-4 master_plan** | STM-004 登记同步正式/实现依赖区分与 I11 设计 |

**未变更**：Lua 只读范围、OI-009、Git 计划、HTTP/压缩黑名单。

### Amendment 002（2026-08-10 — PLAN_REMEDIATION Round 3）

**触发**：Plan Review Round 2 `PLAN_REJECTED` — MUST_FIX=1（MF-2：非原子 mutator 与 OLD/NEW-only 断言冲突）。Human 废止「三条独立 HSET/LTRIM mutator」要求；Round 3 三段式 I11 模型为权威。

| 项 | 修订 |
|---|---|
| **MF-2 I12（原 I11）** | **全文替换** §8.3.1：证明 **reader-composed torn snapshot prevention**（非隐藏 writer 瞬态）；Part 1 **原子** test-only mutator（单 Lua 或 MULTI/EXEC）；Part 2 **broken split-reader** 负对照 + **确定性 barrier**（V0→暂停→原子 OLD→NEW→恢复→断言 V0+C1+M1）；Part 3 生产 Lua 正对照（有界并发 toggle + 仅 OLD/NEW）；有效性对照表 A/B |
| **SF-1 `__init__.py`** | §6 白名单增补 `domain/enums|models|services/__init__.py`、`infrastructure/redis/__init__.py` 精确路径 |
| **SF-2 compressed_context** | 新增 Integration **I10**：`compressed_context` 字段缺失 → `invalid_session_state`；总场景 12→**13**；I11/I12/I13 重编号 |
| **SF-3 ContextReadFailure** | §2/§5/§8 明确：**STM-009** HTTP 映射职责；STM-004 **不** 定义 HTTP 状态码 |
| **SF-4 test-only 范围** | 新增 `tests/integration/context_read_torn_read_helpers.py`；mutator + broken reader **仅** `tests/integration/**`；**禁止** `src/**` |
| **SF-5 master_plan** | CHANGE-032 登记 Amendment 002 |

**未变更**：生产 Lua 严格只读；STM-001 keys；STM-003 message codec；malformed fail-closed；OI-009；正式 STM-002 vs 复用 STM-001/003 区分。

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-10 06:38 UTC | Planner 初版 | 创建 Task Plan；progress/master_plan 规划态回写 | 未运行（规划-only） | OI-009 + OI-STM-004-001～003 已 Planner 决议；待 Plan Review |
| 2026-08-10 07:10 UTC | Planner Amendment 001 | PLAN_REMEDIATION：MF-1 I11 对抗性 torn-read + `NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID`；前置正式/复用区分；`ContextReadFailure`；空 messages 3 元素 Lua 返回 | 未运行（规划-only） | Round 1 MF-1 已吸收；待 Plan Review Round 2 |
| 2026-08-10 07:18 UTC | Planner Amendment 002 | PLAN_REMEDIATION Round 3：MF-2 原子 mutator + 三段式 I12（负/正对照）；I10 compressed_context 缺失；`__init__.py` 白名单；ContextReadFailure→STM-009 注记 | 未运行（规划-only） | Round 2 MF-2 已吸收；待 Plan Review Round 3 |
| 2026-08-10 07:38 UTC | Developer 实施 | 只读 Lua + 领域服务 + unit/contract/integration（13 场景含 I12 三段式） | scoped unit 15 / contract 3 / integration 14 / full unit 300 / full contract 65 / ruff PASS / mypy PASS | OI-009 只读 Lua；`compressed_context` 缺失 HGET false→invalid_session_state |

---

## 14. 实际执行结果

（空 — 尚未实施）

### 最终状态

`tested`
