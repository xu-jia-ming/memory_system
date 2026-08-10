# STM-007 Compression LLM Client + Structured Output

## 1. 任务信息

```yaml
task_id: STM-007
task_name: Compression LLM Client + Structured Output
status: planned
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.5 Compression Service（LLM Prompt、Output Schema、compression_output_too_large、Application Service Contract 边界）"
  - "§1.2.6 Context Compression Trigger Strategy（compression_llm_timeout_seconds；本任务仅消费超时配置）"
  - "§3.9 DeepSeek LLM（json_object、thinking disabled、temperature=0、LLMClient Contract、Schema 重试、llm_empty_output）"
prerequisites:
  formal:
    - "DEV-002 — SATISFIED（LLMSettings / LLMCompressionTaskSettings / ContextSettings；openai>=2.46,<3 已在 pyproject.toml）"
    - "STM-001 — SATISFIED（estimate_tokens heuristic；ContextSettings.max_compressed_context_estimated_tokens）"
    - "STM-006 — SATISFIED（compression lock + pending + Kafka；本任务不触碰）"
  implementation_reuse:
    - "STM-005 — ContextArchiveMessage 四字段模型（messages 输入子集）"
    - "DEV-007 — infrastructure client 模式参考（errors / fake / contract helpers）；不得复制 Embedding Contract"
  baseline:
    - "Authoritative baseline（Orchestrator）：main == origin/main == dc74311d6658c87cb164283f9ec775e012aa93f5；working tree clean；FULL_RUFF PASS；mypy PASS"
    - "不需要 Redis / Mongo / Kafka live I/O；不需要真实 DeepSeek 作为默认 CI 门禁"
branch: "feat/STM-007-compression-llm-client-structured-output"
created_at: "2026-08-10 14:05 UTC"
updated_at: "2026-08-10 14:05 UTC"
approval_gates:
  planning_docs: "本轮 Planner 输出；等待独立 Plan Review → PLAN_APPROVED"
  implementation_plan: "status=planned；未实施；未 PLAN_LANDING"
open_issues_acknowledged:
  - "OI-004 — open；Mongo token boundary；**不在 STM-007 scope**"
  - "OI-005 — open；service naming；**不在 STM-007 scope**"
```

### 1.1 编排与门禁（本轮）

```yaml
start_existing_task: true
phase: planning_only
must_not_this_round:
  - "进入 Developer / 编写业务实现或测试语义"
  - "触碰 DEV-006 / PR #13"
  - "实现 STM-008 Finalize Lua / STM-009 Coordinator / HTTP / Session Close"
  - "Redis lock / pending_archive_* / Mongo archive read/write / Kafka"
  - "compression_version bump / message trimming / compression_version 写回"
  - "私自解决 OI-004 / OI-005"
```

---

## 2. 任务目标

交付 **纯 LLM 压缩能力**：在调用方已准备好压缩上下文输入的前提下，调用 Compression LLM，经 Structured Output 严格校验后，返回 **validated `compressed_context` + `new_compressed_context_tokens`**；失败 **fail-closed**，无部分结果、无静默截断。

可验证交付：

1. **`CompressionLlmService`**（进程内领域服务）：接收 `CompressionLlmInput` → 渲染 Prompt → 调用 `LLMClient` → Pydantic 校验 → token 估算 → 返回 `CompressionLlmResult`（success / failure 稳定判别）。
2. **`LLMClient` Protocol + `DeepSeekLlmClient`**：`openai.AsyncOpenAI`；Compression 专用配置来自 **既有** `LLMSettings` + `ContextSettings`（**禁止**第二套 config stack）。
3. **`FakeLlmClient`**：可注入 success / timeout / provider error / invalid JSON / schema-invalid；默认 CI 零公网。
4. **测试**：Unit 13 + Contract 4 + Integration(fake) 5 + opt-in 真实 DeepSeek Integration（非默认 CI blocker）。
5. **STM-008 兼容**：输出字段与 Finalize Lua 输入对齐（见 §5.0 Contract #16）；**不实现** Finalize。

概念链（本任务止点）：

```text
Caller（未来 STM-009 Coordinator）已持有 lock + 已读 archive + compressed_context
        → CompressionLlmInput（prepared context only）
        → CompressionLlmService.compress_context(...)
        → CompressionLlmSuccess(compressed_context, new_compressed_context_tokens)
        → 供 STM-008 Finalize Lua 与其他 token delta 一并消费
        → 本任务不写 Redis / 不 bump compression_version
```

---

## 3. 非目标（必须坚持；黑名单语义）

- Redis 压缩锁 acquire/release / `pending_archive_*` 读写（**STM-006** 已完成；本任务不触碰）。
- Mongo `context_archive` 查询 / Archive 批次选择 / `archive_id` 归属校验（**STM-005** + **STM-009**）。
- Kafka publish / `context.archive.created`（**STM-006**）。
- Finalize Lua：`compression_version` bump、LTRIM、清 pending、写 Redis `compressed_context`（**STM-008**）。
- Compression Coordinator 多轮策略、`compression_status` HTTP 字段、消息头部窗口选择、prompt 截断 / batching（**STM-009**）。
- Session Close / Extraction / Retrieval / embedding。
- `compress(archive_id, user_id, session_id, lock_owner_token)` **协调层**完整实现（属 **STM-009**；本任务仅实现其内部的 LLM 子能力）。
- OI-004 Mongo token boundary 私解；OI-005 服务命名正式闭合。
- 操作 **DEV-006** / **PR #13**。
- 默认 CI 真实 DeepSeek 计费调用；多 Provider 路由；锁续期；流式输出；Tool Calling。
- 自动 Push / Merge / Rebase / Force Push。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `dc74311d6658c87cb164283f9ec775e012aa93f5` |
| `git status --short` | 干净（规划轮次仅 docs dirty 允许） |
| `openai` 依赖 | `pyproject.toml`：`openai>=2.46,<3` 已锁定 |
| `src/memory_system/infrastructure/llm/**` | **不存在** |
| `CompressionLlmService` / `compression_llm*` | **不存在** |
| `estimate_tokens` | **存在**（`domain/services/token_estimator.py`；STM-001） |
| `ContextArchiveMessage` | **存在**（四字段；无 `estimated_tokens`） |
| `LLMSettings` / `LLMCompressionTaskSettings` | **存在**（`settings/models.py`） |
| `compression_preparation_service` | **存在**（STM-006；本任务不修改） |

### 4.2 可复用组件

| 组件 | 路径 | 用途 |
|---|---|---|
| Token 估算 | `domain/services/token_estimator.py` | `new_compressed_context_tokens` |
| Archive 消息模型 | `domain/models/context_archive.py` | LLM 输入 messages |
| Settings | `settings/models.py` | `LLMSettings` + `ContextSettings` |
| Embedding client 模式 | `infrastructure/embedding/*` | errors / fake / contract helper **参考**（非复制 Contract） |
| `ContextArchiveMessage` codec | 既有 Pydantic strict 模型 | messages 序列化 |

### 4.3 当前缺失

- `LLMClient` Protocol 与 DeepSeek 实现。
- Compression 专用 Pydantic Output Schema 与领域 Result 类型。
- Compression Prompt 模板与 `prompt_version` 常量。
- `CompressionLlmService` 与全套测试。

### 4.4 前置任务检查

| 前置 | 状态 |
|---|---|
| DEV-002 | **SATISFIED** |
| STM-001 | **SATISFIED** |
| STM-006 | **SATISFIED**（PR #25 MERGED） |

---

## 5. 实现方案

### 5.0 十六项 Contract 闭合（Planner 强制）

#### Contract #1 — 输入 Contract（协调层 vs LLM 客户端）

| 层级 | 类型 | 字段 | 去向 |
|---|---|---|---|
| **协调层**（§1.2.5 `compression_service.compress`；**STM-009**） | `CompressionCoordinatorInput`（本任务 **不实现** 完整协调） | `archive_id`, `user_id`, `session_id`, `lock_owner_token` | Mongo 查询 / Redis pending 校验 / Lua owner 校验 / tracing；**不进入 LLM Prompt** |
| **LLM 层**（**STM-007**） | `CompressionLlmInput` | `existing_compressed_context: str` | User Prompt `{compressed_context}` |
| | | `archived_messages: list[ContextArchiveMessage]` | User Prompt `{messages}`（稳定序列化） |
| | | `max_compressed_context_estimated_tokens: int` | System Prompt `{max_compressed_context_estimated_tokens}`；输出 token 上限校验 |
| | | `request_id: str \| None` | 日志 / tracing only；**不进 Prompt** |
| | | `user_id`, `session_id`, `archive_id` | 日志字段 only（可用时）；**不进 Prompt** |

规则：

- STM-007 **只接受**已准备好的 LLM 输入；不负责 archive 读取、pending 一致性、`lock_owner_token` 校验。
- `existing_compressed_context` 允许空字符串（首次压缩无摘要）。
- `archived_messages` 顺序 = Archive 内顺序；空列表 **fail-closed**（`invalid_compression_input` 或领域 ValidationError；**不调用 LLM**）。

#### Contract #2 — Output Schema（权威 §1.2.5）

Pydantic 模型 `CompressionLlmOutput`：

```python
class CompressionLlmOutput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    compressed_context: str  # required；允许 ""；禁止 null
```

| 场景 | 行为 |
|---|---|
| 合法 `{"compressed_context":""}` | Success；`new_compressed_context_tokens=0` |
| 合法非空字符串 | Success；`estimate_tokens(compressed_context)` |
| `compressed_context` 为 `null` / 非 str | Schema 失败 → 重试路径 |
| 缺少 `compressed_context` | Schema 失败 → 重试路径 |
| extra 字段 | `extra=forbid` → Schema 失败 → 重试路径 |
| 响应体非 JSON / JSON 语法损坏 | 解析失败 → 重试路径 |
| 第二次仍 Schema/解析失败 | `llm_invalid_output` |
| 非空输出 token 超过 `max_compressed_context_estimated_tokens` | `compression_output_too_large`（**不重试 LLM**；§1.2.5 禁止二次重写） |

**不**在 Pydantic 层设 `max_length` 字符截断；超长仅由 token 估算 + `compression_output_too_large` 判定。

#### Contract #3 — `json_object` Contract（§3.9）

`DeepSeekLlmClient.generate_structured` 固定参数：

| 参数 | 值 |
|---|---|
| `model` | `settings.llm.compression.model`（默认 `deepseek-v4-flash`） |
| `response_format` | `{"type": "json_object"}` |
| `temperature` | `0` |
| `stream` | `False` |
| `max_tokens` | `settings.llm.compression.max_output_tokens` |
| `extra_body` | `{"thinking": {"type": "disabled"}}` |
| `timeout` | `context.compression_llm_timeout_seconds`（per-request；非连接池全局） |

#### Contract #4 — Prompt Contract

| 项 | 值 |
|---|---|
| `COMPRESSION_PROMPT_VERSION` | 常量 `"compression_v1"`（日志记录；与 Extraction `prompt_version` 分离） |
| System template | 规格 §1.2.5 原文（Requirements 1–12 + `{max_compressed_context_estimated_tokens}`） |
| User template | 规格 §1.2.5 原文（`Previous compressed context` + `Archived conversation messages` + `Generate...`） |
| `{messages}` 序列化 | 稳定 **JSON array**：`[{"message_id","role","content","timestamp"}...]`（`model_dump(mode="json")`）；禁止依赖 Mongo ObjectId 或隐式 repr |
| JSON 字样 | System/User 均含 `JSON` / `schema` 语义（§3.9 rule 1–2） |
| 纠错 Prompt | **本 MVP 与首次 Prompt 相同**（规格 Extraction 有「更严格纠错」；Compression §1.2.5 **未要求**变体；Schema 重试使用 **相同** system+user） |

模块：`src/memory_system/infrastructure/llm/compression_prompts.py`（模板 + render 函数）。

#### Contract #5 — Model / Endpoint / Provider

| 配置源 | 字段 |
|---|---|
| `LLMSettings` | `base_url`, `api_key`（`SecretStr`） |
| `LLMCompressionTaskSettings` | `model`, `max_output_tokens`, `temperature`, `thinking`, `response_format` |
| `ContextSettings` | `compression_llm_timeout_seconds` |

- Client：`AsyncOpenAI(api_key=..., base_url=...)` per §3.9。
- **禁止**新建第二套 YAML/env compression LLM 配置栈。
- Factory（可选）：`create_llm_client(settings)` → `DeepSeekLlmClient`；测试注入 `FakeLlmClient`。

#### Contract #6 — Secret 处理

- API Key **仅**从 `LLM__API_KEY` / `settings.llm.api_key` 读取。
- 禁止 commit / log / fixture / plan / exception `__str__` 回显真实 key。
- 测试 fixture 使用 `sk-example-replace-me` 等占位；CI 使用 Fake transport。
- `DeepSeekLlmClient.__str__` / errors 沿用 embedding `_redact_for_display` 同类脱敏。

#### Contract #7 — Retry 语义（§3.9）

| 失败类 | 传输层自动重试 | 业务层重试 |
|---|---|---|
| HTTP Read Timeout | **禁止**（0 次 transport retry） | 映射 `llm_timeout`；**不** Schema 重试 |
| 连接错误 / 非超时网络错误 | **禁止**无限；**0 次** transport auto-retry | 映射 `llm_request_failed` |
| HTTP 429 / 5xx | **禁止**无限自动重试 | 映射 `llm_request_failed` |
| Assistant `content` null / 空白 | 无 | `llm_empty_output`；**不** Schema 重试 |
| JSON 解析 / Pydantic Schema 失败 | 无 | **最多 1 次**相同输入重试（**2 attempts total**） |
| `compression_output_too_large` | 无 | **禁止** LLM 重写（§1.2.5） |

实现：`CompressionLlmService` 持有 retry loop（attempt 0/1）；`DeepSeekLlmClient` **单次** HTTP 调用无内置 429/5xx 循环。

#### Contract #8 — Structured-output 失败分类（fail-closed）

| 类 | 描述 | 最终 `error_code` | 重试 |
|---|---|---|---|
| A | HTTP / provider 失败（含 429/5xx） | `llm_request_failed` | 否 |
| A′ | HTTP Read Timeout | `llm_timeout` | 否 |
| B | 响应体非 JSON 文本 | 进入 C/D 路径 | Schema 重试 |
| C | JSON 语法损坏 | 进入 D | Schema 重试 |
| D | JSON 合法但 Schema 无效 | 进入 E/F | Schema 重试 |
| E | 必填字段缺失 | `llm_invalid_output`（二次后） | Schema 重试 |
| F | 非预期 extra 字段（`extra=forbid`） | `llm_invalid_output`（二次后） | Schema 重试 |
| G | 空模型输出（null / `""` / 仅空白 content） | `llm_empty_output` | **否** |

**禁止**返回 partial `compressed_context` 或「最佳努力」摘要。

#### Contract #9 — Exception / Result Contract

```python
# 领域结果（推荐 discriminated union / 显式 outcome 枚举）

class CompressionLlmOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"

class CompressionLlmSuccess(BaseModel):
    compressed_context: str
    new_compressed_context_tokens: int = Field(ge=0)
    prompt_version: str
    model: str
  # optional: usage fields for observability passthrough

class CompressionLlmFailure(BaseModel):
    error_code: Literal[
        "llm_empty_output",
        "llm_invalid_output",
        "compression_output_too_large",
        "llm_timeout",
        "llm_request_failed",
        "invalid_compression_input",
    ]
    prompt_version: str
    model: str
    attempt_count: int = Field(ge=1, le=2)

class CompressionLlmResult(BaseModel):
    outcome: CompressionLlmOutcome
    success: CompressionLlmSuccess | None = None
    failure: CompressionLlmFailure | None = None
```

Infrastructure 层 `LlmServiceError`（可选，对齐 `EmbeddingServiceError` 字段：`code`, `sanitized_message`, `status_code`）；由 Service 映射为 `CompressionLlmFailure`，**不**向上泄露 SDK 原始异常。

规格错误码映射：

| `error_code` | 规格出处 |
|---|---|
| `llm_empty_output` | §3.9 rule 6–7 |
| `llm_invalid_output` | §3.9 rule 8–9；Extraction 表 §2.1.15（Compression 二次失败后同码） |
| `compression_output_too_large` | §1.2.5 |
| `llm_timeout` | §2.1.15 表 |
| `llm_request_failed` | §2.1.15 表 |

#### Contract #10 — Token / Size 职责

- **STM-007 负责**：对 **LLM 输出** `compressed_context` 调用 `estimate_tokens` → `new_compressed_context_tokens`；与 `max_compressed_context_estimated_tokens` 比较。
- **不负责**：prompt 输入截断；archive 消息选择；`archived_message_tokens` / `old_compressed_context_tokens` 计算（**STM-008 / Coordinator** 在 Finalize 前计算）。
- 空字符串 → `new_compressed_context_tokens = 0`（§1.2.5）。

#### Contract #11 — 确定性

- `temperature=0`；`thinking` disabled；`stream=false`。
- **不**使用 `seed`（规格未要求）。
- Fake client 默认确定性响应，便于 CI。

#### Contract #12 — Observability

日志（`structlog` 或模块 logger）**允许**：

- `request_id`, `model`, `prompt_version`, `duration_ms`, `outcome`, `error_code`（失败时）, `attempt_count`
- Token usage（API 返回 `usage.prompt_tokens` / `completion_tokens` 若存在）

**禁止**：

- API Key、完整 system/user prompt、完整 archived message 正文、完整 model response body。

#### Contract #13 — Fake LLM for CI

`FakeLlmClient` 实现 `LLMClient` Protocol：

- 模式：`success` / `timeout` / `provider_error` / `invalid_json` / `schema_invalid` / `empty_content` / `whitespace_content`
- `success` 返回可配置 JSON 字符串或预设 `CompressionLlmOutput`
- 无真实网络；Contract tests 通过 `tests/contract/helpers/compression_llm_fake.py` 共享 helper（对齐 `siliconflow_fake.py` 模式）

#### Contract #14 — 真实 Integration（opt-in）

| 项 | 值 |
|---|---|
| 环境开关 | `RUN_COMPRESSION_LLM_INTEGRATION=1` |
| 密钥 | `LLM__API_KEY`（真实 SecretStr；**不进** repo） |
| 默认 CI | `pytest` 收集时 **skip**（与 DEV-007 embedding integration 同模式） |
| 验证 | 单次最小 prompt → 解析 JSON → `compressed_context` 为 str；**不**断言业务语义质量 |

#### Contract #15 — STM-006 边界

- **不** import / 修改：`compression_lock_repository`、`compression_preparation_service`、`pending_archive` Lua、Kafka publisher。
- STM-007 可在单元测试中 **mock** 输入消息，无需 Redis/Kafka fixture。

#### Contract #16 — STM-008 兼容（不实现 Finalize）

STM-008 Finalize Lua 需要调用方传入（§1.2.5 step 3–4）：

| 字段 | STM-007 产出 | 说明 |
|---|---|---|
| `new_compressed_context`（字符串） | `CompressionLlmSuccess.compressed_context` | 直接传递 |
| `new_compressed_context_tokens` | `CompressionLlmSuccess.new_compressed_context_tokens` | STM-007 计算 |
| `archived_message_tokens` | **非 STM-007** | Coordinator 从 archive messages 估算 |
| `old_compressed_context_tokens` | **非 STM-007** | Coordinator 从 WM `compressed_context` 估算 |
| `lock_owner_token` / `compression_version` / pending 四字段 | **非 STM-007** | STM-008 Lua KEYS/ARGV |

成功路径 handoff 类型（供 STM-008 规划引用）：

```python
class CompressionFinalizeLlmPayload(BaseModel):
    compressed_context: str
    new_compressed_context_tokens: int = Field(ge=0)
```

失败路径：STM-008 **不被调用**；pending 保留（协调层/STM-009 职责）。

---

### Step 1 — 领域模型与 Output Schema

- **文件**：`src/memory_system/domain/models/compression_llm.py`
- **内容**：
  - `CompressionLlmInput`
  - `CompressionLlmOutput`（LLM JSON Schema）
  - `CompressionLlmSuccess` / `CompressionLlmFailure` / `CompressionLlmResult` / `CompressionFinalizeLlmPayload`
  - `CompressionLlmOutcome` enum
- **校验**：`archived_messages` 非空；`max_compressed_context_estimated_tokens > 0`（或复用 ContextSettings 已校验配置）
- **错误**：输入非法 → `invalid_compression_input`；不调用 LLM

### Step 2 — LLM Infrastructure

- **文件**：
  - `src/memory_system/infrastructure/llm/protocol.py` — `LLMClient.generate_structured(...)` 签名对齐 §3.9
  - `src/memory_system/infrastructure/llm/errors.py` — `LlmServiceError` + redaction
  - `src/memory_system/infrastructure/llm/deepseek_client.py` — `DeepSeekLlmClient`
  - `src/memory_system/infrastructure/llm/fake_client.py` — `FakeLlmClient`
  - `src/memory_system/infrastructure/llm/compression_prompts.py` — 模板 + render
  - `src/memory_system/infrastructure/llm/__init__.py` — 最小 export
- **DeepSeek 实现要点**：
  - 单次 `chat.completions.create`；捕获 `APITimeoutError` → `llm_timeout`；其他 API 错误 → `llm_request_failed`
  - 提取 `message.content`；空白检测在 Service 层（Contract G）
  - `json.loads` + `response_schema.model_validate` 在 Service 或 Client 内分层：建议 Client 返回 **raw content str**，Service 负责 parse/validate/retry 语义清晰

### Step 3 — CompressionLlmService

- **文件**：`src/memory_system/domain/services/compression_llm_service.py`
- **函数**：`async def run_compression_llm(input: CompressionLlmInput, llm_client: LLMClient, settings: Settings, *, request_id: str | None = None) -> CompressionLlmResult`
- **流程**：
  1. 校验 input
  2. render prompts（`compression_prompts.render(...)`）
  3. attempt loop（max 2）：call LLM → 空白检测 → parse JSON → Pydantic validate
  4. `estimate_tokens` + `compression_output_too_large` 检查
  5. 记录 observability 日志
- **幂等**：纯函数式；相同输入 + 确定性 Fake → 相同输出；真实 LLM 不保证跨调用 bitwise 相等

### Step 4 — 测试（见 §8）

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/compression_llm.py` | 创建 | Input/Output/Result/Payload 模型 |
| `src/memory_system/domain/services/compression_llm_service.py` | 创建 | 压缩 LLM 编排、重试、token 校验 |
| `src/memory_system/infrastructure/llm/protocol.py` | 创建 | `LLMClient` Protocol |
| `src/memory_system/infrastructure/llm/errors.py` | 创建 | 脱敏 LLM 错误 |
| `src/memory_system/infrastructure/llm/deepseek_client.py` | 创建 | AsyncOpenAI DeepSeek 实现 |
| `src/memory_system/infrastructure/llm/fake_client.py` | 创建 | CI 确定性 Fake |
| `src/memory_system/infrastructure/llm/compression_prompts.py` | 创建 | Prompt 模板 + `compression_v1` |
| `src/memory_system/infrastructure/llm/__init__.py` | 创建 | 模块 export |
| `tests/unit/test_compression_llm_service.py` | 创建 | Unit 13 场景 |
| `tests/unit/test_deepseek_llm_client.py` | 创建 | Client 层 timeout/参数/无 transport retry |
| `tests/contract/test_compression_llm_contract.py` | 创建 | Contract 4 场景 |
| `tests/contract/helpers/compression_llm_fake.py` | 创建 | Fake helper + mock transport |
| `tests/integration/test_compression_llm_fake.py` | 创建 | Service + Fake 集成 5 场景 |
| `tests/integration/test_compression_llm_integration.py` | 创建 | opt-in 真实 DeepSeek |

**明确不在白名单**：`src/memory_system/infrastructure/redis/**`、`mongodb/**`、`kafka/**`、HTTP routes、`compression_finalize.lua`、settings/models.py（除非 Plan Review 强制且与 DEV-002 一致）、`AppState` lifecycle（STM-009 接线）。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 无 Redis/Mongo 写；单次 LLM 调用无跨存储事务 |
| 幂等 | 适用（逻辑） | 相同输入重复调用不破坏外部状态；本任务无副作用 |
| 并发 | 不适用 | 无共享可变状态；并发调用由上层 Coordinator + 锁约束 |
| 版本冲突 | 不适用 | `compression_version` 属 STM-008 |
| 用户隔离 | 部分适用 | 输入校验由上层保证 archive 归属；本任务仅记录日志字段 |
| 部分失败 | fail-closed | 任一校验失败不返回 partial summary |
| 进程异常恢复 | 不适用 | 无持久化中间态；失败由 Coordinator 保留 pending |

---

## 8. 测试计划

### 8.1 Unit Test（13）

| ID | 场景 | 预期 |
|---|---|---|
| U1 | Fake 返回合法非空 `compressed_context` | `outcome=success`；tokens = `estimate_tokens` 值 |
| U2 | Fake 返回 `{"compressed_context":""}` | `success`；`new_compressed_context_tokens=0` |
| U3 | 输出 token 等于 `max_compressed_context_estimated_tokens` | `success`（边界 inclusive） |
| U4 | 输出 token 超过 `max` | `failure`；`error_code=compression_output_too_large`；**无**第二次 LLM 调用 |
| U5 | Assistant `content=null` | `llm_empty_output`；attempt=1 |
| U6 | Assistant 仅空白 content | `llm_empty_output`；attempt=1 |
| U7 | 无效 JSON 两次 | `llm_invalid_output`；attempt=2 |
| U8 | 合法 JSON 缺 `compressed_context` 两次 | `llm_invalid_output` |
| U9 | `compressed_context: null` 两次 | `llm_invalid_output` |
| U10 | extra 字段两次 | `llm_invalid_output`（`extra=forbid`） |
| U11 | 首次 Schema 失败、二次成功 | `success`；`attempt_count=2` |
| U12 | Mock `APITimeoutError` | `llm_timeout`；**仅 1 次** HTTP 调用 |
| U13 | 空 `archived_messages` | `invalid_compression_input`；零 LLM 调用 |

命令：`uv run pytest tests/unit/test_compression_llm_service.py tests/unit/test_deepseek_llm_client.py -q`

### 8.2 Contract Test（4）

| ID | 场景 | 预期 |
|---|---|---|
| C1 | `LLMClient.generate_structured` 签名与 §3.9 一致 | mypy + 反射/契约断言 |
| C2 | Mock OpenAI 调用参数矩阵 | `json_object`、`thinking disabled`、`temperature=0`、`stream=False`、`max_tokens` 来自 settings |
| C3 | `CompressionLlmResult` 错误码枚举稳定 | 与 §5.0 Contract #9 表一致；无未文档码 |
| C4 | `CompressionFinalizeLlmPayload` 字段 | 仅 `compressed_context` + `new_compressed_context_tokens`；可供 STM-008 消费 |

命令：`uv run pytest tests/contract/test_compression_llm_contract.py -q`

### 8.3 Integration Test — Fake（5）

| ID | 场景 | 预期 |
|---|---|---|
| I1 | `run_compression_llm` + `FakeLlmClient` 端到端 success | 与 U1 等价但经完整 service 栈 |
| I2 | Fake `timeout` 模式 | `llm_timeout` |
| I3 | Fake `provider_error`（模拟 503） | `llm_request_failed` |
| I4 | Fake `invalid_json` 持久 | `llm_invalid_output` |
| I5 | Fake `schema_invalid` 持久 | `llm_invalid_output` |

命令：`uv run pytest tests/integration/test_compression_llm_fake.py -q`

### 8.4 Integration Test — Real（opt-in）

| ID | 场景 | 预期 |
|---|---|---|
| R1 | `RUN_COMPRESSION_LLM_INTEGRATION=1` + `LLM__API_KEY` | 真实调用返回可解析 JSON；`compressed_context` 为 str |

命令：`RUN_COMPRESSION_LLM_INTEGRATION=1 uv run pytest tests/integration/test_compression_llm_integration.py -q`

默认 CI：**skip**；不计入 PR 门禁失败。

### 8.5 E2E Test

| 场景 | 预期 |
|---|---|
| 不适用 | 无 HTTP / 无 Redis 写；E2E 属 STM-013 |

### 8.6 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| Schema 重试边界 | 第 2 次失败后停止；无第 3 次调用（Unit U7/U11） |
| Transport 不重试 | Timeout 单次 attempt（U12） |
| 并发双调用 | 两独立 `CompressionLlmService` 调用无共享状态；**可选** asyncio gather smoke（非阻塞） |

---

## 9. 验收标准

- [ ] `CompressionLlmService` 对 prepared input 返回严格校验的 `compressed_context` + `new_compressed_context_tokens`
- [ ] §5.0 十六项 Contract 均可通过对应测试或代码审查核对
- [ ] Unit 13 + Contract 4 + Integration(fake) 5 全部通过
- [ ] 默认 CI 无真实 DeepSeek 网络调用
- [ ] `uv run ruff check .` PASS
- [ ] `uv run mypy src tests scripts` PASS
- [ ] 白名单外零业务文件变更
- [ ] Review 无 P0/P1

---

## 10. 风险与阻塞项

### 10.1 开放问题（不阻塞 STM-007）

| ID | 说明 | STM-007 处理 |
|---|---|---|
| OI-004 | Mongo token boundary | **OUT OF SCOPE**；不扩展 Archive schema |
| OI-005 | Service naming | **OUT OF SCOPE**；进程内服务命名遵循现有 `compression_*` 模式 |

### 10.2 设计文档冲突

- **无 BLOCKER**：§1.2.5 Output Schema 与 §3.9 JSON 规则一致。
- Compression Schema 重试使用 **相同** Prompt（Extraction 有「更严格纠错」文案；Compression 未要求）— 按规格字面，**不发明**纠错 Prompt 变体。

### 10.3 当前代码冲突

- 无；`infrastructure/llm` 从零创建。

### 10.4 API/Schema 变化

- 无 HTTP；无 Redis/Mongo schema 变更。

### 10.5 BLOCKER / MUST_FIX 哨兵

| 级别 | 说明 |
|---|---|
| BLOCKER | **无**（在遵守 OI-004/OI-005 不关闭、不接线 Redis 前提下） |
| MUST_FIX（预置） | 若实施中发现规格要求 Compression 必须使用不同于 §1.2.5 的 Output Schema 或要求 transport 层 429 自动重试 — **停止并报告** |

---

## 11. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/STM-007-compression-llm-client-structured-output"
expected_commits:
  - "docs(plan): add STM-007 compression llm client structured output plan"
  - "feat(stm): add compression llm client and structured output service"
  - "docs(status): record STM-007 implementation commit and PR"
  - "docs(status): complete STM-007 after PR merge"
out_of_scope_changes:
  - "STM-008 Finalize Lua / STM-009 Coordinator / HTTP"
  - "Redis lock / pending / Kafka / Mongo archive I/O"
  - "DEV-006 / PR #13"
  - "settings/models.py 无必要修改"
  - "五命令正文"
  - "OI-004 / OI-005 私解"
release_phases:
  PLAN_LANDING: "main: docs(plan) + ff-only + create exact feat（仅 Release Operator；PLAN_APPROVED 后）"
  IMPLEMENTATION_RELEASE: "feat only: 白名单 add/commit/push/PR；禁 push main"
  POST_MERGE_CLEANUP: "PR MERGED 后 main docs(status): complete；删 exact feat"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

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
