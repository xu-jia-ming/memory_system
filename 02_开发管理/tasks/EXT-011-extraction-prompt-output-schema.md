# EXT-011 Extraction Prompt Output Schema

## 1. 任务信息

```yaml
task_id: EXT-011
task_name: Extraction Prompt Output Schema
status: planned
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "f161952b8669f6bacab06d953cafdc588a4679bb"
branch: "feat/EXT-011-extraction-prompt-output-schema"
created_at: "2026-08-25 07:22 UTC"
updated_at: "2026-08-25 07:22 UTC"
spec_sections:
  - "§2.1.6 LLM Structured Extraction 设计（Output Schema + 字段约束）"
  - "Appendix B（extraction output 授权字段，仅 prompt 引用，不修改校验）"
prerequisites:
  formal:
    - "EXT-003 — SATISFIED/completed; validate_extraction_payload + EXTRACTION_SYSTEM_PROMPT + SCHEMA_CORRECTION_INSTRUCTION"
    - "EXT-010 — SATISFIED/completed; memory type definitions in prompt; prompt_version memory_extraction_v2 (PR #67 MERGED)"
  implementation_reuse:
    - "EXTRACTION_SYSTEM_PROMPT / SCHEMA_CORRECTION_INSTRUCTION constants in extraction_llm_service.py"
    - "ENTITY_TYPES / MEMORY_TYPES / EVENT_STATUSES / AUTHORIZED_*_FIELDS in extraction_llm.py (prompt literals must align, validation unchanged)"
    - "tests/contract/test_ext003_contract.py C7/C11; tests/unit/test_extraction_system_prompt.py"
  baseline_evidence:
    branch: "main"
    head: "f161952b8669f6bacab06d953cafdc588a4679bb"
    working_tree_at_planning_start: "dirty — 本地 LoCoMo/debug 实验与多 service 未提交改动；实施前须在干净 feat/EXT-011 分支起步，且不得混入无关 diff"
    investigation_evidence: "deepseek-v4-flash 在仅含 'Return valid JSON matching the required schema' 时返回 category/object、缺 entities；将 §2.1.6 Output Schema + xor/event-null 规则写入 system prompt 后 Jon/Gina archive 单次 run_extraction_llm 成功"
approval_gates:
  planning: "PLAN_APPROVED"
  human_plan_approved: true
  developer_authorized: false
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feat/EXT-011-extraction-prompt-output-schema"
  IMPLEMENTATION_RELEASE: "only after CODE_REVIEW_APPROVED; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after verified MERGED PR; exact feature branch cleanup and docs(status): complete on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_write_scope: NONE
schema_changes_expected: NONE
api_changes_expected: NONE
error_code_changes_expected: NONE
```

### 1.1 本轮门禁与停止条件

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现、测试实现、Migration、配置落地或依赖变更"
  - "进入 Developer、Code Reviewer、Commit Recorder 或 Release Operator"
  - "执行任何 Git 写命令"
  - "修改权威规格正文 01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md"
  - "修改 validate_extraction_payload 或 Appendix B 校验语义"
  - "触碰 DEV-006 / PR #13"
stop_if:
  - "任何实现步骤需要新 Python 依赖或 lockfile 变更"
  - "任何实现步骤需要修改 extraction JSON Schema、Appendix B 授权字段、error code 或 task state machine"
  - "任何实现步骤需要修改 HTTP API Contract 或 Kafka event Contract"
  - "实现被要求同步修改 spec §1446/§1850 示例 YAML 中的 prompt_version（本任务仅改运行时配置与 prompt 常量）"
blocking_open_issues: []
nonblocking_open_issues: []
```

## 2. 任务目标

在 EXT-010 已补充 memory type 定义的基础上，将 §2.1.6 **Output Schema**（`entities` + `memories` 字段清单与示例）及关键字段约束**嵌入** extraction prompt，使真实 LLM（尤其 `deepseek-v4-flash`）首次输出即对齐 Appendix B，减少 `category`/`object` 等常见幻觉键与缺 `entities` 的失败；并将 `prompt_version` 升至 `memory_extraction_v3`。

本任务的可验证目标：

1. `EXTRACTION_SYSTEM_PROMPT` 在 Requirements 13 之后新增 **Output schema** 段：包含顶层 `entities`/`memories` 数组、各字段名称列表、与 §2.1.6 语义等价的 JSON 示例（可英文化，结构必须与 Appendix B 一致）。
2. 同段或紧邻子段嵌入**关键字段规则**（英文，与现有 prompt 语言一致）：
   - 顶层必须含 `entities` 与 `memories`（不得使用 `category` 等未授权键）。
   - Memory 使用 `memory_type`（`fact`/`preference`/`event`/`profile`），不得使用 `category`。
   - `object_entity_id` 与 `object_value` **必须且只能有一个**非 `null`。
   - `memory_type` 非 `event` 时，`event_status`、`start_time`、`end_time`、`original_time_text` 必须全部为 `null`。
   - Entity `type` 枚举：`person`、`organization`、`product`、`project`、`location`、`concept`、`other`。
   - `memory_type=event` 时 `event_status` 必填，枚举：`occurred`、`ongoing`、`planned`、`cancelled`、`unknown`。
3. `SCHEMA_CORRECTION_INSTRUCTION` 强化：在 retry 时显式提醒 `entities` 必填、`memory_type` 非 `category`、仅使用 archive 内 `source_message_ids`、返回单个 JSON 对象。
4. `configs/base.yaml` 与 `MemoryExtractionSettings.prompt_version` 默认同步为 `memory_extraction_v3`。
5. Contract/Unit 测试覆盖 output schema 字面、字段规则、correction 指令与 v3 配置；**零** `validate_extraction_payload` 逻辑变更。

## 3. 非目标

- 修改 `validate_extraction_payload`、`ENTITY_TYPES`/`MEMORY_TYPES`/`EVENT_STATUSES` 集合或 Appendix B 授权字段。
- 修改 `render_extraction_user_prompt` / `EXTRACTION_USER_PROMPT_TEMPLATE` 正文（archive 消息格式不变；retry 仍通过 `user_prompt + SCHEMA_CORRECTION_INSTRUCTION` 拼接）。
- 修改 LLM provider 参数矩阵（model/temperature/thinking/max_output_tokens/timeout）、retry 次数或 fingerprint/duplicate merge 逻辑。
- 修改 Neo4j Evidence schema、graph write、pipeline continuation 或 Kafka/task state machine。
- 对已持久化 `memory_extraction_v1`/`v2` Evidence 做回填或迁移。
- 修改规格正文、Migration、依赖 manifest/lockfile。
- LoCoMo eval 脚本、debug 工具、unrelated service refactors。
- DEV-006、PR #13、RET-*、CON-*、OPS-* 任务范围。

## 4. 当前代码状态

### 4.1 Git 和前置任务证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| planning baseline HEAD | `f161952`（`docs(status): complete EXT-010...`） |
| `git status --short` | **dirty** — 含 LoCoMo/debug 实验与多 service 未提交改动；实施前须基于 PLAN_LANDING 后 main 创建干净 feat 分支 |
| EXT-003 | completed |
| EXT-010 | completed（PR #67 MERGED） |
| workflow | `NORMAL`，explicit |

### 4.2 已存在代码

- `EXTRACTION_SYSTEM_PROMPT`（`extraction_llm_service.py` L54–105）含 EXT-010 memory type 定义与 Requirements 1–13；Requirement 13 仅写 “Return only valid JSON matching the required schema.”，**无** Output Schema 字段清单或示例。
- `SCHEMA_CORRECTION_INSTRUCTION`（L115–120）仅泛化 “invalid / required extraction schema / JSON only”，**未**点名 `entities`、`memory_type` vs `category`。
- `settings.memory_extraction.prompt_version` 与 `configs/base.yaml` 均为 `memory_extraction_v2`。
- `validate_extraction_payload` 已完整实现 §2.1.6 字段约束（xor、event nullability、enum）；**本任务不修改**。
- `tests/contract/test_ext003_contract.py` C7 断言 v2；C11 断言 memory type 分类关键字。

### 4.3 可复用组件

- `EXTRACTION_SYSTEM_PROMPT` / `SCHEMA_CORRECTION_INSTRUCTION` 常量模式。
- `ENTITY_TYPES`、`MEMORY_TYPES`、`EVENT_STATUSES`（prompt 枚举字面应与模型常量一致，测试可 import 对齐）。
- EXT-010 `tests/unit/test_extraction_system_prompt.py` 扩展点。
- EXT-003 contract 测试矩阵。

### 4.4 当前缺失

- System Prompt 中 §2.1.6 Output Schema JSON 结构与字段列表。
- Prompt 内嵌 xor / non-event null / entity type / event_status 枚举规则。
- Retry correction 指令中对常见错误键（`category`、缺 `entities`）的显式纠正。
- `memory_extraction_v3` 配置与测试断言。

### 4.5 与技术规格不一致之处

| 项 | 规格 | 当前代码 | 本任务处理 |
|---|---|---|---|
| Output Schema in prompt | §2.1.6 含完整 JSON 示例与字段表 | 仅模糊 “required schema” | 嵌入 schema + 规则到 system prompt |
| `prompt_version` 示例值 | §1446 仍写 `memory_extraction_v1` | 运行时 v2 | 运行时升至 v3；**不改**规格正文 |
| Validation | Appendix B | 已对齐 | **不变** |

### 4.6 前置任务检查

- EXT-003 LLM extraction：**SATISFIED**
- EXT-010 prompt memory types：**SATISFIED**
- 无 blocking Open Issue

## 5. 实现方案

### Step 1 — 扩展 `EXTRACTION_SYSTEM_PROMPT`（Output Schema + 字段规则）

- **文件**：`src/memory_system/domain/services/extraction_llm_service.py`
- **类/函数/Schema**：模块常量 `EXTRACTION_SYSTEM_PROMPT`
- **输入**：无（静态常量）
- **输出**：更新后的多行英文字符串
- **内容要求**：
  1. 保留 opening、Requirements 1–12、EXT-010 Memory type definitions / Classification order 不变。
  2. 将 Requirement 13 扩展为明确指向下方 Output schema 段，或在其后新增 **Output schema** 子段（Requirement 13 语义保留）。
  3. 嵌入 §2.1.6 结构（与 spec L1553–1598 对齐）：
     - 顶层键：`entities`（数组）、`memories`（数组）。
     - `entities[]` 字段：`local_entity_id`、`name`、`type`、`aliases`（含 `user` 保留值说明）。
     - `memories[]` 字段：`memory_type`、`content`、`subject_entity_id`、`predicate`、`object_entity_id`、`object_value`、`event_status`、`start_time`、`end_time`、`original_time_text`、`confidence`、`source_message_ids`。
     - 内嵌 JSON 示例（可与规格示例等价英文化；`memory_type` 不得写成 `category`）。
  4. 紧随 schema 后添加 **Critical field rules**  bullet 列表，覆盖：
     - Top-level keys must be exactly `entities` and `memories`.
     - Use `memory_type`, never `category`.
     - `entities` is required even when empty (use `[]`).
     - `object_entity_id` XOR `object_value`（exactly one non-null）。
     - Non-event memories: all four event-related fields `null`.
     - Entity `type` 与 `event_status` 枚举（与 `ENTITY_TYPES`/`EVENT_STATUSES` 一致）。
  5. 语言：**English**；不得引入未授权字段名。
- **错误处理**：不适用（常量）
- **幂等/并发/事务要求**：不适用

### Step 2 — 强化 `SCHEMA_CORRECTION_INSTRUCTION`

- **文件**：`src/memory_system/domain/services/extraction_llm_service.py`
- **类/函数/Schema**：模块常量 `SCHEMA_CORRECTION_INSTRUCTION`
- **输入**：无
- **输出**：更新后的 retry 纠正字符串（仍由 `correction_user_prompt = f"{user_prompt}\n\n{SCHEMA_CORRECTION_INSTRUCTION}"` 消费）
- **内容要求**：
  1. 保留 “previous response was invalid” 与 “Return JSON only” 语义。
  2. 追加显式要求：
     - Return a single JSON object with required top-level keys `entities` and `memories`.
     - Use `memory_type` (not `category`) for each memory.
     - `entities` must be present (array, may be empty).
     - Obey object_entity_id XOR object_value and non-event event-field null rules.
     - Use only `source_message_ids` from the provided archive.
  3. 不得改变 retry 次数（仍一次 schema correction）或 `run_extraction_llm` 控制流。
- **错误处理**：不适用
- **幂等/并发/事务要求**：不适用

### Step 3 — 升级 `prompt_version` 配置

- **文件**：`configs/base.yaml`、`src/memory_system/settings/models.py`
- **类/函数/Schema**：`MemoryExtractionSettings.prompt_version` 字段默认值
- **输入**：无
- **输出**：`memory_extraction_v3`
- **错误处理**：不适用
- **幂等/并发/事务要求**：新 extraction 调用写入 v3；历史 v1/v2 Evidence 保留，不回填

### Step 4 — 更新 Contract 测试

- **文件**：`tests/contract/test_ext003_contract.py`
- **变更**：
  - `test_c7_provider_settings_matrix`：`prompt_version == "memory_extraction_v3"`
  - `test_c11_retry_contract_literals`：
    - 保留 `EXTRACTION_SYSTEM_PROMPT.startswith(...)` 与 memory type 关键字；
    - 追加断言 system prompt 含 `entities`/`memories` 与 `memory_type`（非仅 `category`）；
    - 断言 `SCHEMA_CORRECTION_INSTRUCTION` 含 `entities`、`memory_type`（或 “not category”）等 retry 关键字
- **错误处理**：测试失败即阻塞合并
- **幂等/并发/事务要求**：不适用

### Step 5 — 扩展 Unit 测试（output schema + correction）

- **文件**：`tests/unit/test_extraction_system_prompt.py`（扩展）；可选新建 `tests/unit/test_extraction_schema_correction_prompt.py`（若将 correction 测试独立更清晰）
- **场景**：
  - System prompt 含顶层 `entities` 与 `memories` 字段名及 JSON 示例结构提示。
  - 含 xor 规则表述（`object_entity_id` + `object_value`）。
  - 含 non-event null 规则（`event_status`/`start_time`/`end_time`/`original_time_text`）。
  - 含 entity type 与 event_status 枚举字面（可与 `ENTITY_TYPES`/`EVENT_STATUSES` import 交叉断言）。
  - 保留 EXT-010 既有分类顺序测试通过。
  - `SCHEMA_CORRECTION_INSTRUCTION` 含 `entities` required 与 `memory_type` not `category` 语义。
- **错误处理**：不适用
- **幂等/并发/事务要求**：不适用

### Step 6 — 更新 Settings loader 单元测试

- **文件**：`tests/unit/test_settings_loader.py`
- **变更**：默认/加载 `prompt_version` 断言改为 `memory_extraction_v3`
- **错误处理**：不适用
- **幂等/并发/事务要求**：不适用

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/services/extraction_llm_service.py` | 修改 | Output Schema + 字段规则写入 `EXTRACTION_SYSTEM_PROMPT`；强化 `SCHEMA_CORRECTION_INSTRUCTION` |
| `configs/base.yaml` | 修改 | `memory_extraction.prompt_version: memory_extraction_v3` |
| `src/memory_system/settings/models.py` | 修改 | `MemoryExtractionSettings.prompt_version` 默认值 `memory_extraction_v3` |
| `tests/contract/test_ext003_contract.py` | 修改 | C7 v3；C11 schema/correction contract |
| `tests/unit/test_extraction_system_prompt.py` | 修改 | Unit：output schema、字段规则、保留 EXT-010 断言 |
| `tests/unit/test_extraction_schema_correction_prompt.py` | 创建（可选） | Unit：`SCHEMA_CORRECTION_INSTRUCTION` retry 关键字 |
| `tests/unit/test_settings_loader.py` | 修改 | settings 默认 prompt_version v3 |

**实施白名单（IMPLEMENTATION_RELEASE 精确路径，不得超出）：**

```yaml
implementation_whitelist:
  - "src/memory_system/domain/services/extraction_llm_service.py"
  - "configs/base.yaml"
  - "src/memory_system/settings/models.py"
  - "tests/contract/test_ext003_contract.py"
  - "tests/unit/test_extraction_system_prompt.py"
  - "tests/unit/test_extraction_schema_correction_prompt.py"
  - "tests/unit/test_settings_loader.py"
  - "02_开发管理/tasks/EXT-011-extraction-prompt-output-schema.md"
  - "02_开发管理/progress.md"
```

**规划轮白名单（本轮 Planner 已用）：**

```yaml
planning_whitelist:
  - "02_开发管理/tasks/EXT-011-extraction-prompt-output-schema.md"
  - "02_开发管理/progress.md"
  - "02_开发管理/master_plan.md"
```

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 无 multi-document 事务；prompt/config 为静态部署变更 |
| 幂等 | 适用（replay） | 已有 `extraction_result` 的任务 replay 仍跳过 LLM；新 LLM 调用使用 v3 prompt + v3 Evidence.prompt_version |
| 并发 | 不适用 | 无共享 mutable 状态 |
| 版本冲突 | 低影响 | 同一 archive 首次 extraction 用 v3；历史 v1/v2 Evidence 保留；不做混版本 reconcile |
| 用户隔离 | 不适用 | prompt 全局一致，无 per-user 差异 |
| 部分失败 | 不适用 | 常量级变更，无 partial write |
| 进程异常恢复 | 不适用 | 与 EXT-003 replay 语义一致；processing + persisted result 仍复用旧 result |

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| U1 `test_extraction_system_prompt_contains_output_schema_keys` | prompt 含 `entities`、`memories` 及 memories 授权字段名 |
| U2 `test_extraction_system_prompt_xor_rule` | prompt 说明 `object_entity_id` 与 `object_value` 互斥 |
| U3 `test_extraction_system_prompt_non_event_null_rule` | 非 event 时四个 event 相关字段须 null |
| U4 `test_extraction_system_prompt_entity_and_event_enums` | entity type / event_status 枚举与 `ENTITY_TYPES`/`EVENT_STATUSES` 一致 |
| U5 `test_extraction_system_prompt_preserves_ext010_content` | EXT-010 分类顺序与 memory type 定义仍保留 |
| U6 `test_schema_correction_instruction_required_keys` | correction 含 `entities`、`memory_type`、禁止 `category` 语义 |
| U7 `test_settings_loader_prompt_version_default` | `get_settings().memory_extraction.prompt_version == "memory_extraction_v3"` |

### Contract Test

| 场景 | 预期 |
|---|---|
| C7 provider settings matrix | `prompt_version == memory_extraction_v3`；其余 LLM 矩阵不变 |
| C11 retry contract literals | system prompt 前缀与 schema 段；correction 含 retry 关键字 |

### Integration Test

| 场景 | 预期 |
|---|---|
| — | **本任务不新增**；既有 EXT-003/009 integration 回归即可 |

### E2E Test

| 场景 | 预期 |
|---|---|
| — | **本任务不新增** |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| — | **不适用** |

### scoped 验证命令（Developer 实施后）

```bash
uv run pytest tests/unit/test_extraction_system_prompt.py tests/unit/test_extraction_schema_correction_prompt.py tests/unit/test_settings_loader.py tests/contract/test_ext003_contract.py -q
uv run ruff check src/memory_system/domain/services/extraction_llm_service.py src/memory_system/settings/models.py tests/unit/test_extraction_system_prompt.py tests/unit/test_extraction_schema_correction_prompt.py tests/unit/test_settings_loader.py tests/contract/test_ext003_contract.py
uv run mypy src/memory_system/domain/services/extraction_llm_service.py src/memory_system/settings/models.py
```

## 9. 验收标准

- [ ] `EXTRACTION_SYSTEM_PROMPT` 含 §2.1.6 Output Schema 结构（`entities` + `memories` 字段列表与示例）
- [ ] System prompt 含 xor、non-event null、entity type enum、event_status enum 规则
- [ ] `SCHEMA_CORRECTION_INSTRUCTION` 强化 `entities` 必填、`memory_type` 非 `category`、授权键提醒
- [ ] `configs/base.yaml` 与 `MemoryExtractionSettings` 默认 `prompt_version=memory_extraction_v3`
- [ ] `validate_extraction_payload` **零 diff**
- [ ] `tests/unit/test_extraction_system_prompt.py`（及可选 correction 测试）通过
- [ ] `tests/contract/test_ext003_contract.py` C7/C11 通过
- [ ] `tests/unit/test_settings_loader.py` 通过
- [ ] 无 Schema/API/error code/dependency 变更
- [ ] Ruff 通过（scoped files）
- [ ] Mypy 通过（scoped files）
- [ ] Review 无 P0/P1

## 10. 风险与阻塞项

- **设计文档冲突**：规格 §1446/§1850 示例仍为 `memory_extraction_v1`；本任务仅升运行时配置至 v3，**不**改规格正文；Evidence 代际共存属预期。
- **当前代码冲突**：planning 时 working tree dirty；实施前须干净 feat 分支，避免混入 LoCoMo/debug diff。
- **Token 占用**：Output Schema 段增加 prompt 长度；仍在 `max_archive_estimated_tokens` 门禁内，不分块策略不变；需关注极端长 archive 边界（与 EXT-003 一致）。
- **前置任务**：EXT-003/EXT-010 completed — **SATISFIED**
- **未批准依赖**：NONE
- **API/Schema 变化**：NONE（显式禁止修改 `validate_extraction_payload`）
- **其他风险**：不同 LLM 仍可能偶发违规；本任务仅改善 prompt，不放宽校验。

## 11. Git 计划

```yaml
branch: "feat/EXT-011-extraction-prompt-output-schema"
expected_commits:
  - "docs(plan): add EXT-011 extraction prompt output schema"
  - "feat(extraction): embed output schema in system prompt v3"
out_of_scope_changes:
  - "LoCoMo eval / debug 脚本与 src/memory_system/debug/**"
  - "validate_extraction_payload 及 extraction_llm.py 模型/枚举变更"
  - "unrelated extraction pipeline / graph write 逻辑"
  - "规格正文 01_技术规格/**"
  - "pyproject.toml / uv.lock 依赖变更"
  - "tests/unit/test_graph_write_plan_builder.py 中显式 fixture prompt_version 字面（除非 CI 失败且仅同步常量）"
```

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
|  |  |  |  |  |

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
