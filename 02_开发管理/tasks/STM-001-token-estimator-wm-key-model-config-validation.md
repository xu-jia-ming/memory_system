# STM-001 Token 估算、WM Key/字段模型、配置校验

## 1. 任务信息

```yaml
task_id: STM-001
task_name: Token 估算、WM Key/字段模型、配置校验
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.1 Redis Working Memory 数据结构设计（Key 模板、Hash/List/Set 字段、MVP Token 估算公式、启动不等式）"
  - "§1.2.6 Context Compression Trigger Strategy（context YAML 启动校验不等式；与 §1.2.1 规则 4 对齐；本任务仅复用/补测，不实现压缩）"
  - "§3.4 单仓库目录结构（domain/services、domain/models、domain/enums、infrastructure/redis 落点）"
  - "§3.28 测试策略（Unit：Token 估算；本任务无 Integration/E2E Redis I/O）"
prerequisites:
  - "DEV-002 — SATISFIED（配置系统 / ContextSettings / validate_context 已在 main）"
  - "PHASE0_READINESS=PASS；PHASE0_SECRET_READINESS=PASS"
  - "STM_001_ENTRY_GATE=GO；STM_001_SECRET_GATE=GO"
  - "DEV-OPS-006 completed（Phase 0 baseline GREEN；PR #18 MERGED）"
  - "规划基线（Orchestrator 提供、本轮只读核对）：main == origin/main；working tree clean；unit 216 / contract 47 / ruff PASS / mypy PASS"
  - "本任务不依赖 live Redis auth；不需要 SILICONFLOW_API_KEY；不需要 LLM__API_KEY（测试可用既有 fake env 模式）"
  - "本轮 START_EXISTING_TASK=true：只规划，不实施；Plan Review 后 Orchestrator 暂停人工确认；不得暗示本轮进入 Developer"
branch: "feat/STM-001-token-estimator-wm-key-model-config-validation"
created_at: "2026-08-10 01:42 UTC"
updated_at: "2026-08-10 09:50 UTC"
approval_gates:
  planning_docs: "pending Plan Review → READY_FOR_PLAN_REVIEW；本轮不得 PLAN_APPROVED / 不得实施"
  implementation_plan: "status=planned；implementation_commit=null；PR=null"
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
```

---

## 2. 任务目标

在 **不进行任何 Redis live I/O、不引入 HTTP API、不调用 LLM/Embedding 网络** 的前提下，交付短期记忆（STM）后续任务可复用的 **纯函数与契约层**：

1. **Token 估算（heuristic）**：确定性纯函数，按规格 §1.2.1：
   ```
   estimated_tokens = ceil(chinese_character_count * 1.25 + other_character_count * 0.25)
   ```
   中文汉字用 `\u4e00-\u9fff`；其余字符计入 `other_character_count`。文档/命名/注释 **不得**声称 exact tokenizer / 模型 tokenizer。
2. **Working Memory Redis Key / field model**：按 §1.2.1 定义：
   - Key 模板：`memory:working:{user_id}:{session_id}`、`:messages`、`:message_ids`
   - Hash 字段模型（元数据）、List 元素消息 JSON 字段模型、`status`/`role` 枚举
   - **仅**常量与模型；**禁止** `redis` 客户端连接、命令、pipeline、Lua 执行
3. **配置不等式校验**：以 DEV-002 已实现的 `validate_context` 为权威实现；本任务补齐 **STM-001 定向 Unit**，证明 §1.2.6 **MANDATORY STARTUP VALIDATION CONTRACT**（含 `max_compressed_context_estimated_tokens < compression_trigger_tokens` 的 **strict inequality `<`**，非 `<=`）及 §1.2.1 规则 4 其余链；仅当确认相对规格存在真实缺口时，才允许最小修改 `validators.py`（须在执行记录写明 gap）。

完成后系统具备可 import、可单测的 STM 基础契约，供 STM-002+ 复用；**本任务本身不创建 Session、不写 Redis、不暴露 API**。

---

## 3. 非目标（必须坚持；黑名单语义）

- Redis **live write / 真实 Redis I/O**（connect、GET/SET/HSET、RPUSH、Lua、锁）。
- HTTP API / FastAPI 路由 / Memory API Session·消息端点（**STM-002+**）。
- Mongo Context Archive、Kafka、Compression Service、LLM calls、embedding、extraction、retrieval。
- 操作 **DEV-006** dirty worktree / **PR #13**（DO_NOT_MERGE）。
- 因 Redis/Mongo/Kafka/ES/Neo4j 本地无认证而阻塞或扩展本任务。
- 需要真实 `SILICONFLOW_API_KEY` / `LLM__API_KEY`（禁止引入 SiliconFlow / DeepSeek / TEI 网络调用）。
- 实现 STM-002～STM-013 任一业务能力；扩大本任务范围为后续 STM。
- 将 Token estimator 实现为或宣传为 exact tokenizer（含 tiktoken、HF tokenizer、TEI `/tokenize`）。
- 修改五命令正文、`.cursor/agents/**` 角色合并、`compose*.yaml` 大改、新增规格外依赖。
- 自动 Push / Merge / Rebase / Force Push；`gh pr merge`；提交 Secret。

---

## 4. 当前代码状态

- **已存在代码**：
  - `ContextSettings` / `RedisSettings`（`src/memory_system/settings/models.py`）含 §1.2.6 默认阈值。
  - `validate_context`（`src/memory_system/settings/validators.py`）已实现 §1.2.1/§1.2.6 启动不等式（含 archive 链、compression 链、**MANDATORY** `max_compressed < trigger` strict `<` at L37–43、lock TTL、`absolute_min` 等）。
  - `tests/unit/test_settings_validation.py` 已有部分 context 校验用例（**未**覆盖 §1.2.6 mandatory `max_compressed < trigger` strict `<` 三用例链）。
  - 包骨架：`domain/{models,enums,services}`、`infrastructure/redis/` 均为空 `__init__.py` 占位（§3.4）。
- **可复用组件**：DEV-002 Settings + monkeypatch env 测试模式；`math.ceil`；Pydantic `BaseModel`；既有 `VALID_ENV` fixture 模式。
- **当前缺失**：
  - MVP 字符比例 Token 估算纯函数。
  - WM Key builder / Hash·Message 字段模型 / `active|closing` 与 `user|assistant` 枚举。
  - 面向 §1.2.1 的 STM-001 定向 inequality Unit 集（补齐未显式断言的链）。
- **与技术规格不一致之处**：无业务 Contract 冲突；属 Phase 1 能力尚未落地（预期）。
- **前置任务检查**：DEV-002 SATISFIED；Phase 0 GO；`git branch=main`；`HEAD=6721a54066fb0bc67d9c0313ab69e10bcaef2804` == `origin/main`；working tree clean（规划轮次只读）。
- **OI**：OI-001 / OI-002 **不在本任务解释**（阻塞 STM-009；`blocks_current_task=false`）。

### 4.1 规划时只读证据摘要

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `6721a54066fb0bc67d9c0313ab69e10bcaef2804` |
| `main == origin/main` | 是 |
| `git status --short` | clean |
| Phase 0 baseline（用户/Orchestrator） | unit 216 / contract 47 / ruff PASS / mypy PASS |
| formal prerequisite DEV-002 | SATISFIED |
| live Redis / SiliconFlow / LLM keys | **不需要** |

---

## 5. 实现方案（仅供后续 Developer；本轮不执行）

### 硬约束（实施时强制）

1. Token estimator = **deterministic pure function**；公式与 §1.2.1 字面一致；**禁止** exact tokenizer 冒充。
2. **禁止** SiliconFlow / DeepSeek / TEI 网络调用；禁止新增网络客户端。
3. Redis：**只** schema/key/field contract；**禁止**真实 Redis I/O；白名单新文件 **禁止** `import redis` 及 redis-py 客户端类型（`Redis`、`ConnectionPool` 等）。
4. writable whitelist **必须小**；一个小 PR 可完成。
5. 业务代码必须同时含对应测试；失败不得 skip/xfail/降标准。
6. 不得解释 OI-001/OI-002；不得改 API Contract / 错误码 / 状态机。
7. §1.2.6 启动校验中 `max_compressed_context_estimated_tokens < compression_trigger_tokens` 为 **MANDATORY STARTUP VALIDATION CONTRACT**（strict `<`）；本任务以既有 `validate_context` 为权威，补定向 Unit 证明，不得降级为 recommendation。

### Step 1 — Token estimator（heuristic）

- **文件**：`src/memory_system/domain/services/token_estimator.py`（创建）；可选更新 `domain/services/__init__.py` 导出。
- **函数**：例如 `estimate_tokens(text: str) -> int`（命名不得含 `tokenize` 误导；模块 docstring 明确 **heuristic / character-ratio approximation**，引用 §1.2.1）。
- **算法**：
  - `chinese_character_count` = 匹配 `[\u4e00-\u9fff]` 的字符数；
  - `other_character_count` = 总长 − 中文数（含英文、数字、标点、空白、其他非 BMP 中文范围字符）；
  - `return math.ceil(chinese * 1.25 + other * 0.25)`；
  - 空串 → `0`；结果为 `int`。
- **输入/输出**：纯字符串 → 非负整数；无 I/O、无全局可变状态。
- **错误处理**：类型由类型检查保证；不吞异常；不对非法类型静默成功。
- **幂等/并发**：纯函数；天然幂等；线程安全。

### Step 2 — Working Memory Key / field model

- **文件**：
  - `src/memory_system/infrastructure/redis/keys.py`（创建）：纯函数/常量构造三 Key；**禁止** `import redis` 及任何 redis-py 客户端类型。
  - `src/memory_system/domain/models/working_memory.py`（创建）：Hash 元数据模型 + 消息元素模型（字段对齐 §1.2.1 表）。
  - `src/memory_system/domain/enums/working_memory.py`（创建）：`SessionStatus` = `active` \| `closing`；`MessageRole` = `user` \| `assistant`。
  - 对应 `__init__.py` 仅做最小导出（可选）。
- **Key 合同**（字面）：
  - meta：`memory:working:{user_id}:{session_id}`
  - messages：`memory:working:{user_id}:{session_id}:messages`
  - message_ids：`memory:working:{user_id}:{session_id}:message_ids`
- **Hash 字段（模型字段名与规格一致）**：`user_id`, `session_id`, `compressed_context`, `estimated_tokens`, `compression_version`, `status`, `pending_archive_id`, `pending_archive_batch_key`, `pending_archive_message_count`, `pending_archive_estimated_tokens`, `created_time`, `updated_time`。
- **Optional 字段语义（§1.2.1 示例与字段表；不得猜测）**：
  - `pending_archive_id`: `str | None`；不存在时为 `null`（§1.2.1 示例）
  - `pending_archive_batch_key`: `str | None`；不存在时为 `null`
  - `pending_archive_message_count`: `int`；不存在时为 `0`（**非** `None`）
  - `pending_archive_estimated_tokens`: `int`；不存在时为 `0`
  - `compressed_context`: `str`；允许空串 `""`，**不允许** `null`（§1.2.5 压缩语义引用）
  - Session 创建时（STM-002+）pending 字段初始化为空值或 `0`（§1.2.6 附近 Session init 规则）；本任务模型须支持上述默认值
  - Pydantic：`Optional[str]` + 默认值 `None` 表示「无 pending archive」；`int` 字段默认值 `0`；`None` **不是**跳过 settings validation 的语义
- **Message 元素字段**：`message_id`, `role`, `content`, `estimated_tokens`, `timestamp`。
- **禁止**：`import redis`、client、pool、序列化写 Redis、TTL、锁 Key（压缩锁属后续任务）。
- **幂等/并发**：无运行时状态；模型校验失败 → ValidationError（测试覆盖非法 enum、`compressed_context=null`）。

### Step 3 — Config inequality coverage（STM-001 定向）

- **权威实现**：既有 `validate_context`（`src/memory_system/settings/validators.py` L37–43 已实现 §1.2.6 strict `<`）；本任务 **默认不改语义**，以 `validate_context` 为权威，补 **定向 Unit** 证明规格契约。
- **文件**：`tests/unit/test_context_inequalities_stm001.py`（创建）——用 monkeypatch + `get_settings()` 显式断言 §1.2.1 规则 4 / §1.2.6 **MANDATORY STARTUP VALIDATION CONTRACT**：
  1. archive 链：`max_message_estimated_tokens <= max_archive_estimated_tokens <= memory_extraction.max_archive_estimated_tokens`
  2. compression 链：`compression_target_tokens < compression_trigger_tokens < max_working_memory_estimated_tokens`
  3. message/working：`max_message_estimated_tokens < max_working_memory_estimated_tokens`
  4. **MANDATORY STARTUP VALIDATION CONTRACT**：`max_compressed_context_estimated_tokens < compression_trigger_tokens`（**strict inequality `<`**，非 `<=`；相等与反转均须 `ValidationError`）
- **定向 Unit 矩阵（§1.2.6 strict `<`；三用例强制）**：

  | # | 场景 | 预期 |
  |---|------|------|
  | 1 | 正向合法：`max_compressed < compression_trigger` | Settings validation **PASS** |
  | 2 | 相等：`max_compressed == compression_trigger` | **ValidationError** |
  | 3 | 反转：`max_compressed > compression_trigger` | **ValidationError** |

- **正向 inequality chain assertions**（合法 ContextSettings 完整通过；不只“不抛错”）：
  - 默认配置 `get_settings()` 成功（fake env；无网络）
  - 显式断言四链在合法配置下成立：
    1. archive 链：`max_message <= max_archive <= memory_extraction.max_archive`
    2. compression 链：`target < trigger < max_working_memory`
    3. message/working：`max_message < max_working_memory`
    4. **mandatory** `max_compressed < trigger`
  - 各链破坏时 `ValidationError`（含 mandatory 链三用例）
- **条件修改**：仅当对照规格发现 `validators.py` 真实缺口 → 最小修复 `src/memory_system/settings/validators.py`，并在执行记录写明 gap；**禁止**发明新不等式或改默认阈值。
- **Contract**：新增 `tests/contract/test_stm001_contract.py`（小文件；复用 `test_env_example_contract.py` 模式）；**仅**无网络、无 Redis I/O 的稳定公开 contract（如 `estimate_tokens` 对固定 fixture 的确定性输出、WM key 模板字面量）；不得为此建立大型新测试框架。

### Step 4 — 质量门禁与治理回写（实施阶段）

- 运行：`uv run pytest tests/unit -q`（含本任务新测）、`uv run pytest tests/contract -q`、`uv run ruff check .`、`uv run mypy src tests scripts`。
- 更新 Task Plan 执行记录、`progress.md`、`master_plan.md` STM-001 状态字段（按状态机；不得伪造未跑结果）。

---

## 6. 文件变更清单

### 6.1 Exact writable whitelist（实施阶段；精确路径）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/services/token_estimator.py` | 创建 | §1.2.1 heuristic Token 估算纯函数 |
| `src/memory_system/domain/services/__init__.py` | 修改 | 最小导出（可选；若导出则白名单内） |
| `src/memory_system/domain/models/working_memory.py` | 创建 | WM Hash + Message 字段模型 |
| `src/memory_system/domain/models/__init__.py` | 修改 | 最小导出（可选） |
| `src/memory_system/domain/enums/working_memory.py` | 创建 | `SessionStatus` / `MessageRole` |
| `src/memory_system/domain/enums/__init__.py` | 修改 | 最小导出（可选） |
| `src/memory_system/infrastructure/redis/keys.py` | 创建 | WM Key 模板纯函数（无 I/O） |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 | 最小导出（可选） |
| `src/memory_system/settings/validators.py` | **条件修改** | 仅规格真实缺口时最小修复；默认不改 |
| `tests/unit/test_token_estimator.py` | 创建 | 中英文边界、ceil、空串、混合文本 |
| `tests/unit/test_working_memory_keys_and_models.py` | 创建 | Key 格式、字段、枚举 |
| `tests/unit/test_context_inequalities_stm001.py` | 创建 | §1.2.1/§1.2.6 不等式定向 Unit（含 MANDATORY strict `<` 三用例 + 正向链断言） |
| `tests/contract/test_stm001_contract.py` | 创建 | 无网络/无 Redis I/O 稳定公开 contract（token 确定性输出、WM key 字面量） |
| `02_开发管理/progress.md` | 修改 | 规划/实施/完成态治理字段 |
| `02_开发管理/master_plan.md` | 修改 | 本任务登记字段 / CHANGE |
| `02_开发管理/tasks/STM-001-token-estimator-wm-key-model-config-validation.md` | 修改 | 执行记录 / 状态机 / Amendment |

**期望规模**：≤4 个新建业务源文件 + ≤3 个 unit 测试文件 + 1 个 contract 测试文件 + 必要 `__init__`/governance；一个小 PR。

### 6.2 Exact forbidden paths（非穷尽；命中即越权）

| 路径/范围 | 原因 |
|---|---|
| 白名单新文件内 `import redis` / redis-py 客户端类型 | STM-001 只定义 WM key/field contract，不执行 Redis I/O |
| Redis client / pool / Lua / 任何 live I/O 实现 | 非目标 |
| `src/memory_system/api/**` 新路由或 Session/消息 handler | HTTP API = STM-002+ |
| `src/memory_system/application/short_term_memory/**` 业务编排 | 后续 STM |
| `src/memory_system/infrastructure/{mongodb,kafka,llm,embedding,neo4j,elasticsearch}/**` | 非本任务 |
| `src/memory_system/infrastructure/embedding/**` / SiliconFlow client | 禁止网络与 embedding |
| Mongo archive / Compression / Extraction / Retrieval 代码与测试 | 非目标 |
| `compose*.yaml` 大改、TEI 12g、OI-011 probe 脚本 | 非本任务 |
| DEV-006 feat / PR #13 相关任何路径 | DO_NOT_MERGE |
| `01_技术规格/**` | 禁改规格 |
| `.cursor/commands/**` 五命令正文 | 禁改 |
| 新增 `pyproject.toml` 依赖 / `uv.lock`（无规格依据） | 禁 |

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 无多写事务；无 Redis 写入 |
| 幂等 | 适用 | `estimate_tokens` 同输入同输出；Key builder 幂等 |
| 并发 | 适用（无共享可变状态） | 纯函数/不可变模型；无需锁 |
| 版本冲突 | 不适用 | 不触碰 `compression_version` 写路径 |
| 用户隔离 | 适用（契约层） | Key 必须含 `user_id`+`session_id`；本任务仅定义格式，不测 live 隔离 |
| 部分失败 | 不适用 | 无多步骤外部 I/O |
| 进程异常恢复 | 不适用 | 无持久化副作用 |

---

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 空字符串 | `estimate_tokens("") == 0` |
| 纯英文 / 数字 / 空格 / 标点 | 按 `other * 0.25` 后 ceil（例：4 个 ASCII → `ceil(1.0)=1`） |
| 纯中文（`\u4e00-\u9fff`） | 按 `chinese * 1.25` 后 ceil（例：1 字 → `ceil(1.25)=2`；4 字 → `ceil(5.0)=5`） |
| 中英混合 | 分别计数后求和再 ceil；固定 fixture 断言精确整数值 |
| 边界 ceil | 构造使小数部分 ∈ (0,1) 的输入，断言向上取整（非 trunc） |
| 确定性 | 同输入多次调用结果相同 |
| Key builder | 给定 user/session，三 Key 字面等于规格模板 |
| Hash/Message 模型 | 合法字段可构造；非法 `status`/`role` 失败 |
| WM Optional 字段语义 | `pending_archive_id`/`pending_archive_batch_key` 默认 `None`；`pending_archive_message_count`/`pending_archive_estimated_tokens` 默认 `0`；`compressed_context` 允许 `""`、拒绝 `null` |
| 不等式：默认配置 | `get_settings()` 成功（fake env；无网络） |
| 不等式：正向链断言 | 合法配置下显式断言四链成立（archive / compression / message-working / **mandatory** `max_compressed < trigger`） |
| 不等式：破坏各链 | archive / compression / message-working 链破坏均 `ValidationError` |
| **MANDATORY strict `<` 矩阵**（`test_context_inequalities_stm001.py`） | 见下表 |

#### MANDATORY STARTUP VALIDATION CONTRACT — Unit Test Matrix

文件：`tests/unit/test_context_inequalities_stm001.py`。权威实现：`validate_context`（`validators.py` L37–43）。证明 **strict inequality (`<`)**，不是 `<=`。

| # | 场景 | 预期 |
|---|------|------|
| 1 | 正向合法：`max_compressed < compression_trigger` | Settings validation **PASS** |
| 2 | 相等：`max_compressed == compression_trigger` | **ValidationError** |
| 3 | 反转：`max_compressed > compression_trigger` | **ValidationError** |

| 命名/文档冒烟 | 模块 docstring 含 heuristic / 非 exact tokenizer 语义（若用契约字符串断言，保持稳定可维护） |

### Contract Test

| 场景 | 预期 |
|---|---|
| `tests/contract/test_stm001_contract.py` | 复用 `test_env_example_contract.py` 模式；**仅**无网络、无 Redis I/O |
| `estimate_tokens` 确定性 | 固定 fixture 输入 → 确定性整数输出（与 Unit 一致、可重复） |
| WM key 模板字面量 | 三 Key 模板字符串与 §1.2.1 字面一致（稳定 contract） |
| 全量 contract 不回退 | `uv run pytest tests/contract -q` 通过（含既有 47 + 本任务新增） |

### Integration Test

| 场景 | 预期 |
|---|---|
| 全部 | **不适用** — 本任务无 Redis/Mongo/Kafka live I/O |

### E2E Test

| 场景 | 预期 |
|---|---|
| 全部 | **不适用** |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 网络/Redis 失败注入 | **不适用**（无 I/O） |
| 并发 | 纯函数无需；可选同输入并行调用结果一致（非必须） |

---

## 9. 验收标准

- [ ] `estimate_tokens` 实现与 §1.2.1 公式一致；Unit 覆盖中英文边界与 ceil；**文档/命名不声称 exact tokenizer**
- [ ] WM 三 Key 模板与 Hash/Message 字段模型对齐 §1.2.1；Optional 字段语义符合 §1.2.1/§1.2.5（pending 默认 `null`/`0`；`compressed_context` 允许空串、拒绝 `null`）；无 Redis I/O 代码路径；白名单新文件无 `import redis`
- [ ] §1.2.1/§1.2.6 启动不等式具备 STM-001 定向 Unit；默认配置合法、四链正向断言成立、各链破坏失败
- [ ] **MANDATORY STARTUP VALIDATION CONTRACT**：`max_compressed_context_estimated_tokens < compression_trigger_tokens`（strict `<`）三用例（PASS / 相等 ValidationError / 反转 ValidationError）全部通过；以既有 `validate_context` 为权威
- [ ] `tests/contract/test_stm001_contract.py` 通过；全量 `tests/unit` 与 `tests/contract` 不回退红
- [ ] `uv run pytest tests/unit -q` 通过
- [ ] `uv run pytest tests/contract -q` 通过
- [ ] `uv run ruff check .` 通过
- [ ] `uv run mypy src tests scripts` 通过
- [ ] 未引入 SiliconFlow/DeepSeek/TEI 网络调用；未操作 DEV-006/PR#13
- [ ] Code Review 无 P0/P1
- [ ] 白名单外无改动；PR 保持小而可审

---

## 10. 风险与阻塞项

- **设计文档冲突**：无已知；若公式与 tokenizer 表述冲突，以 §1.2.1「字符比例近似、不使用模型 tokenizer」为准并 HALT 报告。
- **当前代码冲突**：`validate_context` 已存在——本任务以复用+补测为主，避免重复实现分叉。
- **前置任务**：DEV-002 SATISFIED；Phase 0 GO。
- **未批准依赖**：无；禁止新增依赖。
- **API/Schema 变化**：本任务不改 HTTP Contract；仅内部 domain/infra 契约。
- **OI-001 / OI-002**：不在本任务解释（对齐 master_plan）；不得借机定压缩协调 Contract。
- **其他风险**：误把 heuristic 写成「精确 Token」导致后续与 TEI `/tokenize` 混淆——用命名与 docstring 硬约束缓解。
- **密钥/基础设施**：本地 Redis 无认证 **不得**阻塞本任务；不需要 SiliconFlow/LLM keys。

---

## 11. Git 计划（`workflow_mode=NORMAL`）

```yaml
branch: "feat/STM-001-token-estimator-wm-key-model-config-validation"
workflow_mode: NORMAL
workflow_mode_source: explicit
this_planning_round: "仅到计划审查 + 人工确认；不得 PLAN_LANDING / 不得进入 Developer"
expected_commits_after_human_approval:
  - "docs(plan): add STM-001 token estimator wm key model config validation plan"  # PLAN_LANDING on main
  - "feat(stm): add token estimator, wm key/field models, context inequality tests"  # IMPLEMENTATION_RELEASE on feat
  - "docs(status): record STM-001 implementation commit and PR"  # feat only
  - "docs(status): complete STM-001 after PR merge"  # POST_MERGE_CLEANUP on main
out_of_scope_changes:
  - "Redis live client / HTTP API / Mongo / Kafka / compression / LLM / embedding"
  - "DEV-006 / PR #13"
  - "compose*.yaml redesign / TEI 12g / SiliconFlow client"
  - "OI-001/OI-002 自行定论"
```

### 11.1 NORMAL 三相要点（批准且人工确认 **之后**；本轮不执行）

| RELEASE_PHASE | 允许（摘要） | 禁止 |
|---|---|---|
| `PLAN_LANDING` | main：`docs(plan)` commit/push；`git pull --ff-only`；从更新后 main 创建 **exact** feat 分支 | 实施编码；STRICT 误调 |
| `IMPLEMENTATION_RELEASE` | 仅 feat：白名单 `git add` / commit / `push origin <feat>`（禁 force）/ `gh pr create` / `gh pr view`；可选同 feat `docs(status): record` | `git push origin main`；main 上实现 commit；自动 merge |
| `POST_MERGE_CLEANUP` | PR **MERGED** 后：ff-only 更新 main；`docs(status): complete`；仅 exact feat `git branch -d` + `git push origin --delete` | `-D`；未 MERGED 删分支；内容 `git merge` / `gh pr merge` / rebase / force |

**本轮明确**：Planner 输出后 → Plan Review → Orchestrator **暂停人工确认**；在人工 `PLAN_APPROVED` 之前不得进入 Developer，不得 Git 写。

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：2026-08-10
- 原计划：Planner 初版（2026-08-10 01:42 UTC）
- 修改内容：
  - **MUST_FIX-1**：Step 3 第 4 条、`§8` Unit Test 矩阵、`§9` 验收标准 — `max_compressed_context_estimated_tokens < compression_trigger_tokens` 从「建议」升级为 **MANDATORY STARTUP VALIDATION CONTRACT**（strict `<`）；明确以既有 `validate_context` 为权威，补定向 Unit 三用例 + 正向四链断言
  - **SHOULD_FIX-1**：Step 2 / §8 明确 WM Hash Optional 字段语义（§1.2.1/§1.2.5）
  - **SHOULD_FIX-2**：硬约束 / Step 2 / §6.2 写死禁止白名单新文件 `import redis`
  - **SHOULD_FIX-3**：新增 `tests/contract/test_stm001_contract.py`（小 contract；无网络/无 Redis I/O）
  - **SHOULD_FIX-4**：Step 4 / §9 补 `uv run pytest tests/contract -q`
- 修改原因：Plan Review Round 1 `PLAN_REJECTED`（BLOCKER=0；MUST_FIX=1）；Orchestrator HALTED
- 是否影响技术规格：**否**（对齐既有 §1.2.6 与 `validators.py` 实现）
- 审批状态：待 Plan Review Round 2

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-10 01:42 UTC | Planner 初版 Task Plan | 新建本计划；progress/master_plan 规划态登记 | 未跑实施测试（规划轮） | 本轮只规划；待 Plan Review |
| 2026-08-10 09:50 UTC | Planner Amendment 001（PLAN_REMEDIATION） | 修订 MUST_FIX-1 + SHOULD_FIX 1–4；§3/§5/§6/§8/§9/Amendment 001 | 未跑实施测试（规划轮） | Round 1 PLAN_REJECTED；待 Plan Review Round 2 |
| 2026-08-10 10:05 UTC | Developer Step 1–4 实施 | 白名单 8 源文件 + 4 测试文件；`validators.py` 未改（无缺口） | STM-001 定向 37 unit + 2 contract；全量 254 unit / 49 contract；ruff/mypy PASS | 无规格偏差；无 Redis I/O |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/domain/services/token_estimator.py` | 创建 — `estimate_tokens` heuristic 纯函数 |
| `src/memory_system/domain/services/__init__.py` | 修改 — 导出 `estimate_tokens` |
| `src/memory_system/domain/models/working_memory.py` | 创建 — `WorkingMemoryMeta` / `WorkingMemoryMessage` |
| `src/memory_system/domain/models/__init__.py` | 修改 — 最小导出 |
| `src/memory_system/domain/enums/working_memory.py` | 创建 — `SessionStatus` / `MessageRole` |
| `src/memory_system/domain/enums/__init__.py` | 修改 — 最小导出 |
| `src/memory_system/infrastructure/redis/keys.py` | 创建 — 三 Key 模板纯函数 |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 — 最小导出 |
| `tests/unit/test_token_estimator.py` | 创建 — 17 用例 |
| `tests/unit/test_working_memory_keys_and_models.py` | 创建 — 12 用例 |
| `tests/unit/test_context_inequalities_stm001.py` | 创建 — 8 用例（含 mandatory strict `<` 三用例） |
| `tests/contract/test_stm001_contract.py` | 创建 — 2 用例 |
| `02_开发管理/progress.md` | 修改 — 实施态治理字段 |
| `02_开发管理/master_plan.md` | 修改 — STM-001 状态 |
| 本 Task Plan | 修改 — 执行记录 / `status=tested` |

### 与原计划的差异

- `validators.py`：未修改；既有 `validate_context` L37–43 已满足 MANDATORY strict `<`，无真实缺口。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| STM-001 Unit | `uv run pytest tests/unit/test_token_estimator.py tests/unit/test_working_memory_keys_and_models.py tests/unit/test_context_inequalities_stm001.py -q` | **37 passed** |
| STM-001 Contract | `uv run pytest tests/contract/test_stm001_contract.py -q` | **2 passed** |
| Unit（全量） | `uv run pytest tests/unit -q` | **254 passed**（baseline 216 + 38 新增） |
| Contract（全量） | `uv run pytest tests/contract -q` | **49 passed**（baseline 47 + 2 新增） |
| Ruff | `uv run ruff check .` | **PASS** |
| Mypy | `uv run mypy src tests scripts` | **PASS** — 99 source files |
| Integration | — | 不适用 |
| E2E | — | 不适用 |

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
branch: feat/STM-001-token-estimator-wm-key-model-config-validation
plan_commit: 06c272f25e15fd5c7b4afd6e44257bc164dc83ca
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`tested`
