# STM-005 Context Archive Create / Reuse

## 1. 任务信息

```yaml
task_id: STM-005
task_name: Mongo context_archive Create / Reuse
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.2 Context Archive 文档数据库设计（Schema、索引、archive_batch_key、create/reuse 唯一键冲突语义、不可变性）"
prerequisites:
  formal:
    - "STM-003 — SATISFIED（`WorkingMemoryMessage`、消息 JSON codec、Integration 种子模式；PR #21 MERGED）"
    - "DEV-004 — SATISFIED（`001_initial_mongodb.py` 已创建 `context_archive` 三索引；PR #10 MERGED）"
  implementation_reuse:
    - "STM-001 — SATISFIED（`WorkingMemoryMessage` 模型；PR #19 MERGED）"
    - "STM-004 — SATISFIED（非 master_plan 正式前置；上下文读取模式参考；PR #22 MERGED）"
  baseline:
    - "规划基线（本轮只读）：main @ 5be0f07b7a5183aedc9ff2c67abc8e9cea8b0031；STM-004 后 full unit 300 / contract 65 / integration 含 migrate 11+ / ruff PASS / mypy PASS"
    - "本任务需要真实 Mongo（compose test 栈）；不需要 Kafka / Redis pending 写 / 压缩锁 / LLM / HTTP"
branch: "feat/STM-005-context-archive-create-reuse"
created_at: "2026-08-10 08:15 UTC"
updated_at: "2026-08-10 08:15 UTC"
approval_gates:
  planning_docs: "pending Plan Review → READY_FOR_PLAN_REVIEW；本轮不得 PLAN_APPROVED / 不得实施"
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
  - "新增 migration / 修改 001_initial_mongodb.py"
  - "实现 STM-006+（Kafka、pending_archive_*、压缩锁、Finalize、HTTP）"
```

---

## 2. 任务目标

交付 **Mongo `context_archive` 领域服务 + Repository**，使上游（未来 STM-006 Coordinator）可 **幂等地** 将一批 Working Memory 消息归档到 MongoDB：

1. **输入契约**（§1.2.2）：调用方提供 `user_id`、`session_id`、**预计算** `archive_batch_key`、`base_compression_version`、消息列表（来自 WM；含 `estimated_tokens` 于 Redis 侧，但 **Mongo 归档消息按规格示例不含该字段**）、可选 `created_time`（Unix timestamp；缺省由 `clock` 注入）。
2. **CREATE**：首次以给定 `archive_batch_key` 插入 → 生成 `archive_id`（UUID v4）、持久化完整文档、返回 `outcome=created` 与 `archive_id`。
3. **REUSE**：同一 `archive_batch_key` 再次调用 → 捕获 Mongo 唯一键冲突（`archive_batch_key_unique`）→ 查询已有文档 → 返回 `outcome=reused` 与 **相同** `archive_id`；**禁止** 静默覆盖或更新已有文档。
4. **不可变性**（§1.2.2）：文档创建后不得修改；REUSE 路径 **零** Mongo 写（仅读已有文档）。
5. **并发**（§1.2.2 唯一索引语义）：两路并发相同 `archive_batch_key` → 物理上 **至多一条** 文档；两路均获得 **相同** `archive_id`（Integration **必须** 证明并发，非仅顺序双调）。
6. **索引消费**：复用 DEV-004 已创建的 `context_archive` 集合与三索引（`archive_id_unique`、`user_session_created_time`、`archive_batch_key_unique`）；**不** 新增 additive migration。
7. **连接复用**：经 `AppState.mongodb`（`AsyncMongoClient`）；禁止第二连接池。
8. **测试**：Unit（模型映射、`archive_batch_key` helper、服务 create/reuse、Repository DuplicateKey 映射）+ Contract（`ContextArchiveOutcome` 字面量稳定）+ Integration（**11** 场景真实 Mongo；见 §8.3）。

完成后 STM-006 可接线 pending archive + Kafka；与 STM-003 消息模型 **共享** `WorkingMemoryMessage` 输入，归档持久化 **剥离** `estimated_tokens`（见 §10.1 OI-004）。

---

## 3. 非目标（必须坚持；黑名单语义）

- **Kafka** `context.archive.created` 发布（**STM-006**）。
- Redis `pending_archive_*` 字段写入（**STM-006**）。
- 压缩锁、Coordinator、Compression LLM、Finalize Lua（**STM-006～009**）。
- Session Close、HTTP API 路由（**STM-009 / STM-010**）。
- **消息批次选择逻辑**（从 Redis List 头部选多少条、token 边界切分）— **调用方** 负责；STM-005 **不** 发明 batch 选择算法。
- **修改** `scripts/migrations/001_initial_mongodb.py` 或任何 migration 文件。
- 修改 STM-003 写入、STM-004 读取、Redis codec、settings、compose、`.env.example`。
- 在 Mongo archive `messages` 中 **写入** `estimated_tokens`（规格 §1.2.2 示例未包含；OI-004 决议见 §10.1；**不得** 自行扩展 Schema）。
- 操作 **DEV-006** / **PR #13**。
- 自动 Push / Merge / Rebase / Force Push。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `5be0f07b7a5183aedc9ff2c67abc8e9cea8b0031`（`docs(status): complete STM-004 after PR merge`） |
| `git status --short` | clean |
| formal STM-003 | `completed`（PR #21 MERGED） |
| formal DEV-004 | `completed`（PR #10 MERGED；`001_initial_mongodb` 含 `context_archive` 索引） |
| formal STM-004 | `completed`（PR #22 MERGED） |
| baseline（STM-004 tested） | unit 300 / contract 65 / ruff PASS / mypy PASS |

### 4.2 可复用组件审计

| 交付物 | 路径 | STM-005 用法 |
|---|---|---|
| `WorkingMemoryMessage` | `domain/models/working_memory.py` | 服务 **输入** 消息元素类型；持久化时 **映射** 为 Archive 子集（去 `estimated_tokens`） |
| `message_to_json` / `json_to_message` | `infrastructure/redis/working_memory_message_codec.py` | **不** 直接用于 Mongo 写；可参考字段名；Archive BSON **不含** `estimated_tokens` |
| `AppState.mongodb` | `infrastructure/runtime.py` | Integration + Repository 注入；**禁止** 新建 `AsyncMongoClient` |
| `001_initial_mongodb` | `scripts/migrations/001_initial_mongodb.py` | **只读消费** 三索引；STM-005 **不** 改 migration |
| `test_migrate_infra.py` | `tests/integration/test_migrate_infra.py` | 已断言 `archive_batch_key_unique` 存在；I11 可引用或直查 `getIndexes()` |
| `Clock` 模式 | `session_service.py` / `message_write_service.py` | `create_or_reuse_context_archive(..., clock=...)` 注入 `created_time` |
| STM-004 分层模式 | `context_read_service.py` + `*_repository.py` | 领域服务 → infrastructure repository 边界参考 |

**结论**：Mongo 集合与索引已由 DEV-004 建立；`src/memory_system/infrastructure/mongodb/` **尚不存在**；本任务 **新增** 领域模型 + 服务 + Mongo repository，**不** 改 Redis / Kafka / HTTP。

### 4.3 规格摘录（权威；STM-005 范围）

**Document Schema**（§1.2.2 — **严格字段集**）：

| 字段 | 类型 / 约束 | STM-005 职责 |
|---|---|---|
| `archive_id` | UUID v4 | CREATE 路径生成；REUSE 返回已有值 |
| `user_id` | string | 调用方提供；持久化 |
| `session_id` | string | 调用方提供；持久化 |
| `archive_batch_key` | string | 调用方 **预计算** 提供；幂等键 |
| `base_compression_version` | int | 调用方提供；持久化 |
| `messages` | array | 元素：`message_id`、`role`、`content`、`timestamp`；**无** `estimated_tokens` |
| `created_time` | Unix timestamp int | CREATE 时写入；REUSE 读已有值 |

**`archive_batch_key` 契约**（§1.2.2）：

- MVP 公式：`session_id:first_message_id:last_message_id`
- **生成方**：调用方（未来 STM-006 Coordinator）；STM-005 **接受** 预计算 key
- **可选 helper**：`build_archive_batch_key(session_id, first_message_id, last_message_id)` — 确定性、无 hash、无额外盐

**create/reuse 语义**（§1.2.2 唯一索引段落）：

1. 尝试 `insert_one` 完整文档
2. `archive_batch_key` 唯一键冲突 → **不** 重试插入、**不** upsert、**不** 覆盖
3. 按 `archive_batch_key` 查询已有文档 → REUSE，返回相同 `archive_id`

**不可变性**（§1.2.2）：「文档创建后保持不可变」— REUSE 不得 `update` / `replace`。

**索引**（DEV-004 已创建；STM-005 消费）：

| 索引名 | 键 | 用途 |
|---|---|---|
| `archive_id_unique` | `archive_id` | 文档主标识唯一 |
| `user_session_created_time` | `user_id, session_id, created_time` | 查询索引（本任务 Integration 隔离断言间接覆盖） |
| `archive_batch_key_unique` | `archive_batch_key` | create/reuse 幂等键 |

### 4.4 当前缺失

- `ContextArchive` / `ContextArchiveMessage` / `ContextArchiveCreateInput` / `ContextArchiveResult` 领域类型。
- `ContextArchiveOutcome` 枚举（`created` / `reused`）。
- `build_archive_batch_key` helper（可选但计划内交付）。
- `create_or_reuse_context_archive` 领域服务。
- `context_archive_repository`（Mongo insert + DuplicateKey 映射 + find by batch key）。
- `infrastructure/mongodb/` 模块。
- Unit / Contract / Mongo Integration 测试（11 场景）。

### 4.5 与技术规格不一致之处

- §1.2.2 示例 `archive_id` 字面为 `"archive_000001"`，字段说明要求 **UUID v4** — **沿用 STM-002 session_id 先例**：实现 **UUID v4** 字符串（与字段说明一致；示例为示意）。
- Redis WM 消息含 `estimated_tokens`，Mongo Archive 示例 **不含** — **§10.1 OI-004 Planner 决议**：STM-005 按规格 Schema **不** 持久化 `estimated_tokens`；token 来源留给 STM-010；**非** 本任务阻塞项。

---

## 5. 实现方案（仅供后续 Developer；本轮不执行）

### 硬约束（实施时强制）

1. **复用** `AppState.mongodb`；禁止独立 Mongo 连接池。
2. **不** 新增 migration；**不** 修改 `001_initial_mongodb.py`。
3. **不** 写 Kafka / Redis pending / 压缩锁 / HTTP。
4. Mongo `messages` **仅** 四字段；从 `WorkingMemoryMessage` 映射时 **剥离** `estimated_tokens`。
5. REUSE 路径 **只读** Mongo；禁止 `update_one` / `replace_one`。
6. `archive_batch_key` 由调用方提供；服务可校验与 `session_id` / 首尾 `message_id` 一致性（fail-closed）；**不** 替调用方选择消息批次。
7. 业务代码必须同时含对应测试；失败不得 skip/xfail/降标准。

### Step 1 — 枚举与领域模型

- **文件**：`src/memory_system/domain/enums/context_archive.py`（创建）。
- **`ContextArchiveOutcome`**（稳定内部字面量）：

  | 值 | 含义 |
  |---|---|
  | `created` | 首次插入成功 |
  | `reused` | `archive_batch_key` 冲突后复用已有文档 |

- **文件**：`src/memory_system/domain/models/context_archive.py`（创建）。
- **`ContextArchiveMessage`**：`message_id: str`、`role: MessageRole`、`content: str`、`timestamp: int` — **无** `estimated_tokens`。
- **`ContextArchive`**：完整持久化文档模型（`archive_id`、`user_id`、`session_id`、`archive_batch_key`、`base_compression_version`、`messages: list[ContextArchiveMessage]`、`created_time`）。
- **`ContextArchiveCreateInput`**：`user_id`、`session_id`、`archive_batch_key`（预计算）、`base_compression_version`、`messages: list[WorkingMemoryMessage]`（服务内映射为 `ContextArchiveMessage`）。
- **`ContextArchiveResult`**：`outcome: ContextArchiveOutcome`、`archive_id: str`、`archive: ContextArchive`（或等价快照；须含验收所需字段）。

- **映射函数**（同文件或 `context_archive_service.py`）：
  - `wm_message_to_archive_message(msg: WorkingMemoryMessage) -> ContextArchiveMessage` — 丢弃 `estimated_tokens`
  - `archive_document_from_input(input, archive_id, created_time) -> dict` — BSON 可插入 dict；`messages` 仅四字段

### Step 2 — `archive_batch_key` helper

- **文件**：`src/memory_system/domain/services/context_archive_service.py`（或 `domain/models/context_archive.py` 内模块级函数）。
- **`build_archive_batch_key(session_id: str, first_message_id: str, last_message_id: str) -> str`**：
  - 返回 `f"{session_id}:{first_message_id}:{last_message_id}"`
  - **确定性**；无 hash；无额外编码
  - Unit 覆盖边界与重复调用一致性

### Step 3 — Mongo Repository

- **文件**：`src/memory_system/infrastructure/mongodb/context_archive_repository.py`（创建）。
- **集合名**：`context_archive`（字面量常量；禁止别名）。
- **`insert_context_archive(mongodb, document: dict) -> None`**：
  - `collection.insert_one(document)`
  - `DuplicateKeyError` **不** 吞没；向上抛出或映射为 repository 层可识别信号（供服务区分 batch key 冲突）
- **`find_context_archive_by_batch_key(mongodb, archive_batch_key: str) -> ContextArchive | None`**：
  - `find_one({"archive_batch_key": archive_batch_key})`
  - BSON → `ContextArchive` 映射；缺失字段 fail-closed
- **`count_by_batch_key(mongodb, archive_batch_key: str) -> int`** — Integration 断言「仅一条物理文档」
- **文件**：`src/memory_system/infrastructure/mongodb/__init__.py`（若生产 import 需要最小导出）

- **DuplicateKey 处理约定**：
  - `pymongo.errors.DuplicateKeyError` on `archive_batch_key_unique` → REUSE 路径
  - 若冲突键为 `archive_id_unique`（极低概率 UUID 碰撞）→ fail-closed 向上抛（不 silent reuse）

### Step 4 — 领域服务

- **文件**：`src/memory_system/domain/services/context_archive_service.py`（创建）。
- **`create_or_reuse_context_archive(*, mongodb, input: ContextArchiveCreateInput, clock: Clock | None = None) -> ContextArchiveResult`**：

  1. **输入校验**（fail-closed）：
     - `user_id` / `session_id` / `archive_batch_key` 非空
     - `messages` 非空列表
     - 每条 `WorkingMemoryMessage` 字段合法（Pydantic 已约束 `estimated_tokens >= 0`）
     - **一致性**（推荐 MUST_FIX）：`archive_batch_key == build_archive_batch_key(session_id, messages[0].message_id, messages[-1].message_id)`；不匹配 → `ValueError` 或领域异常（fail-closed）
  2. 映射 `messages` → `ContextArchiveMessage` 列表（去 `estimated_tokens`）
  3. `archive_id = str(uuid4())`；`created_time = (clock or _default_clock)()`
  4. 组装 document dict
  5. `insert_context_archive`：
     - 成功 → `ContextArchiveOutcome.CREATED`
     - `DuplicateKeyError`（batch key）→ `find_context_archive_by_batch_key` → 若 None 则 fail-closed（不应发生）→ `ContextArchiveOutcome.REUSED`
  6. 返回 `ContextArchiveResult`；REUSE 时 `archive_id` 与已有文档 **相同**

- **不** 接受 Kafka producer、Redis client、compression lock 参数。

### Step 5 — 测试

见 §8。Integration 使用 `compose.sh --stack=test` 启动 **mongodb**（可 `--embedding=none`）；迁移须已应用（`test_migrate_infra` 模式或测试内 `run_migrations` / 依赖已 init 的 test 栈）。

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/enums/context_archive.py` | 创建 | `ContextArchiveOutcome` |
| `src/memory_system/domain/models/context_archive.py` | 创建 | Archive 文档模型、CreateInput、Result、WM→Archive 映射 |
| `src/memory_system/domain/services/context_archive_service.py` | 创建 | `create_or_reuse_context_archive`、`build_archive_batch_key` |
| `src/memory_system/infrastructure/mongodb/context_archive_repository.py` | 创建 | insert / find / count；DuplicateKey 边界 |
| `src/memory_system/infrastructure/mongodb/__init__.py` | 创建/修改 | 最小导出（若需要） |
| `src/memory_system/domain/enums/__init__.py` | 修改 | 最小导出 `ContextArchiveOutcome`（若生产 import 需要） |
| `src/memory_system/domain/models/__init__.py` | 修改 | 最小导出 ContextArchive 类型（若需要） |
| `src/memory_system/domain/services/__init__.py` | 修改 | 最小导出 `create_or_reuse_context_archive`（若需要） |
| `tests/unit/test_context_archive_models.py` | 创建 | 模型映射、WM→Archive 剥离 `estimated_tokens` |
| `tests/unit/test_context_archive_batch_key.py` | 创建 | `build_archive_batch_key` 确定性 |
| `tests/unit/test_context_archive_service.py` | 创建 | create/reuse 服务行为（Fake Mongo / mock repository） |
| `tests/unit/test_context_archive_repository.py` | 创建 | BSON 映射、DuplicateKey 信号 |
| `tests/contract/test_stm005_contract.py` | 创建 | `ContextArchiveOutcome` 字面量稳定 |
| `tests/integration/test_context_archive_mongo.py` | 创建 | 11 场景真实 Mongo Integration |
| `02_开发管理/tasks/STM-005-context-archive-create-reuse.md` | 创建 | 本 Task Plan |
| `02_开发管理/progress.md` | 修改 | 规划态字段 |
| `02_开发管理/master_plan.md` | 修改 | STM-005 登记 + CHANGE-035 |

**白名单外禁止修改**（含但不限于）：`scripts/migrations/**`、STM-003/004 路径、`api/routes/**`、Redis/Kafka 代码、settings、compose、DEV-006。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | **部分适用** | 单文档 `insert_one` 原子；create/reuse **非** 跨 Redis+Mongo 事务（本任务仅 Mongo 侧） |
| 幂等 | **适用** | 相同 `archive_batch_key` 重复调用 → 相同 `archive_id`；无重复文档 |
| 并发 | **适用** | `archive_batch_key_unique` + insert 竞争 → 至多一条成功 insert；其余 DuplicateKey → find reuse；Integration I5 并发证明 |
| 版本冲突 | **不适用** | 无 `compression_version` 写回；`base_compression_version` 仅快照字段 |
| 用户隔离 | **适用** | `archive_batch_key` 含 `session_id`；不同 session 不同 key → 不同 archive；Integration I7 |
| 部分失败 | **适用** | insert 失败（非 DuplicateKey）→ 不返回假成功；校验失败 fail-closed |
| 进程异常恢复 | **不适用** | 无 Redis pending 状态；Mongo 已提交文档由唯一索引保证不重复 |

---

## 8. 测试计划

### 8.1 Unit Test

| 场景 | 预期 |
|---|---|
| U1 `ContextArchiveOutcome` 字面量 | `created` / `reused` 稳定 |
| U2 WM → Archive 消息映射 | 输出仅 `message_id/role/content/timestamp`；**无** `estimated_tokens` 键 |
| U3 `build_archive_batch_key` | 确定性；`session:a:b` 格式；重复调用相同输入 → 相同输出 |
| U4 CREATE 成功路径 | `outcome=created`；返回新 `archive_id` |
| U5 REUSE 路径（mock DuplicateKey） | `outcome=reused`；`archive_id` 与已有文档相同；**无** second insert |
| U6 输入校验 fail-closed | 空 `user_id` / 空 `messages` / key 与首尾 message_id 不一致 → 异常 |
| U7 Repository BSON 往返 | Mongo dict ↔ `ContextArchive`；messages 四字段 |
| U8 Repository DuplicateKey | `DuplicateKeyError` 正确向上传递或映射 |

### 8.2 Contract Test

| 场景 | 预期 |
|---|---|
| C1 `test_stm005_contract.py` | `ContextArchiveOutcome` 枚举值集合稳定 |
| C2 字面量与规格语义一致 | 仅 `created` / `reused` |

### 8.3 Integration Test（真实 Mongo；11 场景）

前置：`compose.sh --stack=test --embedding=none` 启动 mongodb；确保 `001_initial_mongodb` 已应用（与 `test_migrate_infra` 同栈或测试 fixture 跑 migration）。

| # | 场景 | 预期 |
|---|---|---|
| I1 | 首次归档（新 `archive_batch_key`） | `outcome=created`；文档存在 |
| I2 | 相同 `archive_batch_key` 第二次调用 | `outcome=reused` |
| I3 | 相同 key 两次 | **相同** `archive_id` |
| I4 | 相同 key | `count_by_batch_key == 1`（仅一条物理文档） |
| I5 | **并发** 相同 `archive_batch_key`（`asyncio.gather` N≥10） | 全部成功；**同一** `archive_id`；`count == 1` |
| I6 | 不同 `archive_batch_key` | 不同 `archive_id`；两条文档 |
| I7 | 不同 `session_id`（key 含 session） | 用户/会话隔离；互不覆盖 |
| I8 | 必填字段持久化 | `user_id`、`session_id`、`archive_batch_key`、`base_compression_version`、`messages[]` 四字段、`created_time` 与 BSON 一致 |
| I9 | REUSE 不覆盖 | 第二次调用后第一次写入的 `messages`/`created_time`/`base_compression_version` **不变** |
| I10 | 畸形/无效输入 | 空 messages、key 不匹配、空 `user_id` 等 → fail-closed；**无** 新文档 |
| I11 | 唯一索引存在 | `getIndexes()` 含 `archive_batch_key_unique`（可引用 migrate 测试或直查） |

### 8.4 E2E Test

| 场景 | 预期 |
|---|---|
| — | **不适用**（无 HTTP；E2E 由 STM-013 覆盖） |

### 8.5 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| I5 并发相同 key | §8.3；**必须** 非顺序双调 |
| I10 畸形输入 | fail-closed |
| UUID `archive_id` 碰撞 | 极低概率；若发生 DuplicateKey on `archive_id_unique` → 向上失败（Unit/文档注记） |

### 8.6 质量门禁（Developer 完成时）

```text
uv run pytest tests/unit/test_context_archive_*.py -q
uv run pytest tests/contract/test_stm005_contract.py -q
uv run pytest tests/integration/test_context_archive_mongo.py -q
uv run pytest tests/unit -q
uv run pytest tests/contract -q
uv run ruff check .
uv run mypy src tests scripts
```

---

## 9. 验收标准

- [ ] `create_or_reuse_context_archive` 首次 `archive_batch_key` → CREATE + 新 UUID v4 `archive_id`
- [ ] 相同 `archive_batch_key` → REUSE + **相同** `archive_id`；Mongo **无** 第二文档
- [ ] REUSE **不** update/replace 已有文档（I9）
- [ ] 并发相同 key → 至多一条物理文档、相同 identity（I5）
- [ ] Mongo `messages` **不含** `estimated_tokens`（U2 / I8）
- [ ] 复用 `AppState.mongodb`；无第二 Mongo 池
- [ ] **无** 新 migration；DEV-004 三索引仍有效（I11）
- [ ] **无** Kafka / Redis pending / 压缩 / HTTP 代码
- [ ] Integration 11 场景全通过
- [ ] STM-005 scoped unit + contract + full unit/contract 无回归
- [ ] Ruff / Mypy 通过
- [ ] Review 无 P0/P1
- [ ] 白名单外零 diff

---

## 10. 风险与阻塞项

### 10.1 OI-004 决议（Planner；本任务 **不阻塞**）

| 字段 | 内容 |
|---|---|
| **ID** | OI-004 |
| **规格章节** | §1.2.2、§1.2.6 |
| **问题** | Archive 文档未持久化 `estimated_tokens`；选择与 Close 切分依赖 token 边界 |
| **Planner 决议（STM-005）** | **ACKNOWLEDGED — 不阻塞 create/reuse** — STM-005 **严格按 §1.2.2 示例 Schema** 持久化 messages（四字段）；**不** 向 Mongo 写入 `estimated_tokens`；归档选择时 token 应从 Redis WM 消息读取或重算 — **留给 STM-010 / STM-006** 调用链决议；`open_issues.md` 保持 `open` 直至 STM-010 |
| **验收** | U2 / I8 断言 BSON messages 无 `estimated_tokens` 键 |
| **若误判为阻塞** | 仅当 create/reuse 语义无法实现时标 MUST_FIX 并 HALT — **当前不成立** |

### 10.2 OPEN_ISSUE（Planner 决议；待 Plan Review 确认）

| ID | 主题 | 状态 | 决议 |
|---|---|---|---|
| **OI-STM-005-001** | `archive_batch_key` 与 messages 一致性校验 | **RESOLVED**（Planner） | 服务层 **必须** 校验 `archive_batch_key == build_archive_batch_key(session_id, first_msg_id, last_msg_id)`；不匹配 fail-closed |
| **OI-STM-005-002** | `archive_id` 格式 | **RESOLVED**（Planner） | UUID v4 字符串（非示例字面 `archive_000001`） |
| **OI-STM-005-003** | Migration 责任 | **RESOLVED**（Planner） | DEV-004 已创建集合+索引；STM-005 **禁止** 新 migration |

### 10.3 其他风险

| 风险 | 缓解 |
|---|---|
| DuplicateKey 后 find 返回 None | fail-closed；Integration I2/I5 |
| Integration 误用 dev 栈 | 强制 `compose.sh --stack=test` |
| 并发测试偶发 | I5 N≥10 + `asyncio.gather`；断言 count==1 |
| DEV-006 / PR #13 | 不得触碰 |

### 10.4 设计文档冲突

- 示例 `archive_id` vs UUID v4 说明 — **OI-STM-005-002 已决议**；非阻塞。
- WM `estimated_tokens` vs Archive 四字段 — **OI-004 已决议**；非阻塞。

### 10.5 前置任务

- **正式前置**：STM-003、DEV-004 — **SATISFIED**。
- **实现复用**：STM-001（`WorkingMemoryMessage`）、STM-004（分层模式）— **SATISFIED**。

---

## 11. Git 计划

```yaml
branch: "feat/STM-005-context-archive-create-reuse"
workflow_mode: NORMAL
release_phases:
  PLAN_LANDING:
    - "docs(plan): add STM-005 context archive create reuse plan（main）"
    - "git pull --ff-only；创建 exact feat/STM-005-context-archive-create-reuse"
  IMPLEMENTATION_RELEASE:
    - "feat(stm): add context archive mongo create reuse service"
    - "docs(status): record STM-005 implementation commit and PR（feat only）"
    - "gh pr create（base main）"
  POST_MERGE_CLEANUP:
    - "docs(status): complete STM-005 after PR merge（main only）"
    - "删除 exact feat 分支"
out_of_scope_changes:
  - "Kafka / Redis pending / compression lock / LLM / HTTP"
  - "scripts/migrations/**"
  - "STM-003/004 语义变更"
  - "settings / compose"
  - "DEV-006 / PR #13"
expected_commits:
  - "docs(plan): add STM-005 context archive create reuse plan"
  - "feat(stm): add context archive mongo create reuse service"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-10 08:15 UTC | Planner 初版 | 创建 Task Plan；progress/master_plan 规划态回写 | 未运行（规划-only） | OI-004 acknowledged；OI-STM-005-001～003 Planner 决议；待 Plan Review |
| 2026-08-10 08:50 UTC | Developer 实施 | ContextArchive 模型/枚举/服务 + Mongo Repository + unit/contract/integration | scoped unit 26 / integration 12 / full unit 323 / contract 68 / ruff PASS / mypy PASS | OI-004 acknowledged；DuplicateKey reuse；无 estimated_tokens；无新 migration |
| 2026-08-10 08:50 UTC | Release Operator IMPLEMENTATION_RELEASE | implementation `c166be5cd40475a513cede67f53cafec8fc8529a`；record `a52207473534b1667967be32957c9e1f500ac429`；PR #23 MERGED | scoped unit 26 / integration 12 / full unit 323 / contract 68 / mypy PASS / ruff baseline E501 pre-existing | OI-004 partial evidence；feat 分支待删 |
| 2026-08-10 09:16 UTC | Release Operator POST_MERGE_CLEANUP | PR #23 MERGED（`164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf`）；docs(status): complete on main；删 exact feat | scoped unit 26 / integration 12 / full unit 323 / contract 68 / mypy PASS | STM-006 READY_FOR_PLANNING only |

---

## 14. 实际执行结果

- **implementation_commit**：`c166be5cd40475a513cede67f53cafec8fc8529a`
- **implementation_commit_message**：`feat(stm): add context archive mongo create reuse service`
- **status_record_committed**：`a52207473534b1667967be32957c9e1f500ac429`
- **status_record_completed**：`b0736431a636f0ba20a9cf5aad61a2ea8dc365df`
- **merge_commit**：`164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf`
- **merged_at**：`2026-08-10T09:16:52Z`
- **PR**：#23 MERGED — https://github.com/xu-jia-ming/memory_system/pull/23
- **测试**：scoped unit 26 / contract 3 / integration 12 / full unit 323 / contract 68 / mypy PASS / ruff baseline E501 pre-existing（非回归）
- **交付物**：`create_or_reuse_context_archive`；`build_archive_batch_key`；Mongo insert + DuplicateKey reuse；`context_archive_repository`；archived messages 四字段（无 `estimated_tokens`）；DEV-004 索引消费；无新 migration；empty messages fail-closed；concurrent same key → one doc same `archive_id`；message order preserved

### 最终状态

`completed`
