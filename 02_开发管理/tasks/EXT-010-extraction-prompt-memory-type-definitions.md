# EXT-010 Extraction Prompt Memory Type Definitions

## 1. 任务信息

```yaml
task_id: EXT-010
task_name: Extraction Prompt Memory Type Definitions
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "94633ef85ca613f90b66518ce8dfcf96a7eebe21"
branch: "feat/EXT-010-extraction-prompt-memory-type-definitions"
created_at: "2026-08-25 06:36 UTC"
updated_at: "2026-08-25 06:36 UTC"
spec_sections:
  - "§2.1.2 记忆萃取范围与类型定义"
  - "§2.1.6 LLM Structured Extraction 设计（System Prompt）"
prerequisites:
  formal:
    - "EXT-003 — SATISFIED/completed; EXTRACTION_SYSTEM_PROMPT + validate_extraction_payload + prompt_version from settings"
    - "EXT-009 — SATISFIED/completed; production extraction pipeline wired; replay skips LLM when extraction_result exists"
  implementation_reuse:
    - "Existing EXTRACTION_SYSTEM_PROMPT constant and extraction_llm_service orchestration"
    - "Existing settings.memory_extraction.prompt_version consumed by LLM call and Evidence write path"
    - "Existing EXT-003 contract tests in tests/contract/test_ext003_contract.py"
  baseline_evidence:
    branch: "main"
    head: "94633ef85ca613f90b66518ce8dfcf96a7eebe21"
    working_tree_at_planning_start: "dirty — 本地 LoCoMo/debug 实验改动与 extraction_llm_service.py 未提交改动并存；实施前须在干净 feat/EXT-010 分支起步，且不得混入无关 diff"
approval_gates:
  planning: "PLAN_APPROVED"
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feat/EXT-010-extraction-prompt-memory-type-definitions"
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
  - "触碰 DEV-006 / PR #13"
stop_if:
  - "任何实现步骤需要新 Python 依赖或 lockfile 变更"
  - "任何实现步骤需要修改 extraction JSON Schema、Appendix B 授权字段、error code 或 task state machine"
  - "任何实现步骤需要修改 HTTP API Contract 或 Kafka event Contract"
  - "实现被要求同步修改 spec §1446/§1850 示例 YAML 中的 prompt_version（本任务仅改运行时配置与代码常量，不改规格正文）"
blocking_open_issues: []
nonblocking_open_issues: []
```

## 2. 任务目标

在既有 §2.1.6 Structured Extraction System Prompt 基础上，**补充** §2.1.2 的四类 `memory_type` 定义、示例与分类优先级规则，并将运行时 `prompt_version` 从 `memory_extraction_v1` 升级为 `memory_extraction_v2`，以便 Evidence 与后续运维可区分 prompt 代际。

本任务的可验证目标：

1. `EXTRACTION_SYSTEM_PROMPT` 保留 §2.1.6 既有 Requirements 1–13 的语义与顺序；在 Requirement 4 之后（或将其扩展为带细则的小节）新增 **Memory type definitions** 段，覆盖四类定义、每类至少一个示例、以及 preference → event → profile → fact 的判定顺序。
2. 可选但推荐：纳入 §2.1.2 末段「同一消息可同时产生 event 与 fact、不得语义完全重复」规则（英文表述，与现有 prompt 语言一致）。
3. `configs/base.yaml` 与 `MemoryExtractionSettings.prompt_version` 默认值同步为 `memory_extraction_v2`；LLM 调用与 Evidence 写入继续**只读**消费 `settings.memory_extraction.prompt_version`（行为不变，仅版本字符串变更）。
4. Contract/Unit 测试断言新 prompt 含分类规则关键字，且 settings 默认/加载值为 `memory_extraction_v2`。
5. **零** extraction JSON Schema、validation 逻辑、API、error code、Kafka、task state machine、pipeline continuation 语义变更；已完成任务的 `extraction_result` replay 路径不受影响（仍跳过 LLM）。

## 3. 非目标

- 修改 Appendix B extraction output schema、`memory_type` 枚举集合或 `validate_extraction_payload` 校验规则。
- 修改 User Prompt、`SCHEMA_CORRECTION_INSTRUCTION`、LLM provider 参数矩阵（model/temperature/thinking/max_output_tokens/timeout）。
- 修改 Neo4j Evidence 节点 schema 或 graph write 语义（仅随 settings 写入新 `prompt_version` 字符串）。
- 对已持久化 `memory_extraction_v1` Evidence 做回填或迁移。
- 修改规格正文、Migration、依赖 manifest/lockfile。
- LoCoMo eval 脚本、debug 工具、unrelated service refactors。
- DEV-006、PR #13、RET-*、CON-*、OPS-* 任务范围。

## 4. 当前代码状态

### 4.1 Git 和前置任务证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| planning baseline HEAD | `94633ef`（`docs(status): complete RET-007...`） |
| `git status --short` | **dirty** — 含 LoCoMo/debug 实验与 `extraction_llm_service.py` 等待确认改动；实施前须基于 PLAN_LANDING 后 main 创建干净 feat 分支 |
| EXT-003 | completed |
| EXT-009 | completed |
| workflow | `NORMAL`，explicit |

### 4.2 已存在代码

- `EXTRACTION_SYSTEM_PROMPT`（`extraction_llm_service.py` L55–79）逐字实现 §2.1.6 Requirements 1–13，**未**包含 §2.1.2 类型定义表与分类顺序。
- Requirement 4 仅一句 “Classify each memory as fact, preference, event, or profile.”，缺少判定细则。
- `settings.memory_extraction.prompt_version` 默认与 `configs/base.yaml` 均为 `memory_extraction_v1`。
- `tests/contract/test_ext003_contract.py` C7/C11 断言 v1 与 prompt 前缀。

### 4.3 可复用组件

- `EXTRACTION_SYSTEM_PROMPT` 常量模式（与 `SCHEMA_CORRECTION_INSTRUCTION` 并列）。
- `get_settings()` / `MemoryExtractionSettings` 加载链。
- EXT-003 contract 测试矩阵（C7 provider settings、C11 retry literals）。

### 4.4 当前缺失

- System Prompt 中 §2.1.2 memory type 定义、示例、分类顺序。
- `memory_extraction_v2` 配置默认值与对应测试断言。
- 针对 prompt 分类规则的 dedicated unit test。

### 4.5 与技术规格不一致之处

| 项 | 规格 | 当前代码 | 本任务处理 |
|---|---|---|---|
| System Prompt 类型细则 | §2.1.2 + §2.1.6 | 仅有 §2.1.6 摘要 Requirement 4 | 补充 §2.1.2 内容到 prompt |
| `prompt_version` 示例值 | §1446 仍写 `memory_extraction_v1` | 运行时 v1 | 运行时升至 v2；**不改**规格正文 |
| fingerprint / schema | Appendix B | 已对齐 | 不变 |

### 4.6 前置任务检查

- EXT-003 LLM extraction：**SATISFIED**
- EXT-009 pipeline wiring：**SATISFIED**
- 无 blocking Open Issue

## 5. 实现方案

### Step 1 — 扩展 `EXTRACTION_SYSTEM_PROMPT`

- **文件**：`src/memory_system/domain/services/extraction_llm_service.py`
- **类/函数/Schema**：模块常量 `EXTRACTION_SYSTEM_PROMPT`
- **输入**：无（静态常量）
- **输出**：更新后的多行英文字符串
- **内容要求**：
  1. 保留现有 opening、Requirements 1–3 不变。
  2. 将 Requirement 4 扩展或在 Requirements 段后插入 **Memory type definitions** 子段，语义对齐 §2.1.2：
     - 四类表格语义：`fact` / `preference` / `event` / `profile` 各含 definition + example（示例可英译，语义等价规格示例）。
     - 分类顺序四条：preference → event → profile → fact（与规格编号 1–4 一致）。
     - 推荐包含：同一 utterance 可产出 event + 派生 fact，但不得语义完全重复。
  3. Requirements 5–13 保持原有语义与编号（若插入新段，确保编号连续或采用子标题而不破坏 5–13 字面顺序）。
  4. 语言：**English**（与 §2.1.6 System Prompt 一致）。
- **错误处理**：不适用（常量）
- **幂等/并发/事务要求**：不适用

### Step 2 — 升级 `prompt_version` 配置

- **文件**：`configs/base.yaml`、`src/memory_system/settings/models.py`
- **类/函数/Schema**：`MemoryExtractionSettings.prompt_version` 字段默认值
- **输入**：无
- **输出**：`memory_extraction_v2`
- **错误处理**：不适用
- **幂等/并发/事务要求**：新 extraction 调用写入 v2；历史 Evidence 保持 v1，不回填

### Step 3 — 更新 Contract 测试

- **文件**：`tests/contract/test_ext003_contract.py`
- **变更**：
  - `test_c7_provider_settings_matrix`：`prompt_version == "memory_extraction_v2"`
  - `test_c11_retry_contract_literals`：保留 `EXTRACTION_SYSTEM_PROMPT.startswith(...)`；可追加断言 prompt 含四类 memory type 名称
- **错误处理**：测试失败即阻塞合并
- **幂等/并发/事务要求**：不适用

### Step 4 — 新增 Unit 测试（prompt 分类规则）

- **文件**：`tests/unit/test_extraction_system_prompt.py`（新建）
- **场景**：导入 `EXTRACTION_SYSTEM_PROMPT`，断言至少包含：
  - 四类 type 标识：`fact`、`preference`、`event`、`profile`
  - 分类顺序语义：preference 优先于 event；event 优先于 profile；profile 优先于 fact（可通过顺序子串或结构化段落断言）
  - 每类至少一个示例性短语（与 prompt 内嵌示例一致）
  - 保留 §2.1.6 核心约束（如 “Return only valid JSON matching the required schema.”）
- **错误处理**：不适用
- **幂等/并发/事务要求**：不适用

### Step 5 — 更新 Settings loader 单元测试

- **文件**：`tests/unit/test_settings_loader.py`
- **变更**：默认/加载 `prompt_version` 断言改为 `memory_extraction_v2`
- **错误处理**：不适用
- **幂等/并发/事务要求**：不适用

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/services/extraction_llm_service.py` | 修改 | 补充 §2.1.2 memory type 定义与分类顺序到 `EXTRACTION_SYSTEM_PROMPT` |
| `configs/base.yaml` | 修改 | `memory_extraction.prompt_version: memory_extraction_v2` |
| `src/memory_system/settings/models.py` | 修改 | `MemoryExtractionSettings.prompt_version` 默认值 `memory_extraction_v2` |
| `tests/contract/test_ext003_contract.py` | 修改 | C7 v2 断言；C11 prompt 字面/分类规则 contract |
| `tests/unit/test_settings_loader.py` | 修改 | settings 默认 prompt_version v2 |
| `tests/unit/test_extraction_system_prompt.py` | 创建 | Unit：prompt 含四类定义、顺序与示例 |

**实施白名单（IMPLEMENTATION_RELEASE 精确路径，不得超出）：**

```yaml
implementation_whitelist:
  - "src/memory_system/domain/services/extraction_llm_service.py"
  - "configs/base.yaml"
  - "src/memory_system/settings/models.py"
  - "tests/contract/test_ext003_contract.py"
  - "tests/unit/test_settings_loader.py"
  - "tests/unit/test_extraction_system_prompt.py"
  - "02_开发管理/tasks/EXT-010-extraction-prompt-memory-type-definitions.md"
  - "02_开发管理/progress.md"
```

**规划轮白名单（本轮 Planner 已用）：**

```yaml
planning_whitelist:
  - "02_开发管理/tasks/EXT-010-extraction-prompt-memory-type-definitions.md"
  - "02_开发管理/progress.md"
  - "02_开发管理/master_plan.md"
```

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 无 multi-document 事务；prompt/config 为静态部署变更 |
| 幂等 | 适用（replay） | 已有 `extraction_result` 的任务 replay 仍跳过 LLM；新 LLM 调用使用 v2 prompt + v2 Evidence.prompt_version |
| 并发 | 不适用 | 无共享 mutable 状态 |
| 版本冲突 | 低影响 | 同一 archive 首次 extraction 用 v2；历史 v1 Evidence 保留；不做混版本 reconcile |
| 用户隔离 | 不适用 | prompt 全局一致，无 per-user 差异 |
| 部分失败 | 不适用 | 常量级变更，无 partial write |
| 进程异常恢复 | 不适用 | 与 EXT-003 replay 语义一致；processing + persisted result 仍复用旧 result |

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| U1 `test_extraction_system_prompt_contains_memory_types` | prompt 含 `fact`/`preference`/`event`/`profile` |
| U2 `test_extraction_system_prompt_classification_order` | prompt 中分类顺序与 §2.1.2 一致（preference → event → profile → fact） |
| U3 `test_extraction_system_prompt_examples_present` | 每类至少一个示例性描述存在 |
| U4 `test_extraction_system_prompt_preserves_core_requirements` | 仍含 JSON schema 返回要求及 user-evidence 约束 |
| U5 `test_settings_loader_prompt_version_default` | `get_settings().memory_extraction.prompt_version == "memory_extraction_v2"` |

### Contract Test

| 场景 | 预期 |
|---|---|
| C7 provider settings matrix | `prompt_version == memory_extraction_v2`；其余 LLM 矩阵不变 |
| C11 retry contract literals | `EXTRACTION_SYSTEM_PROMPT` 前缀不变；含分类类型关键字 |

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

###  scoped 验证命令（Developer 实施后）

```bash
uv run pytest tests/unit/test_extraction_system_prompt.py tests/unit/test_settings_loader.py tests/contract/test_ext003_contract.py -q
uv run ruff check src/memory_system/domain/services/extraction_llm_service.py src/memory_system/settings/models.py tests/unit/test_extraction_system_prompt.py tests/unit/test_settings_loader.py tests/contract/test_ext003_contract.py
uv run mypy src/memory_system/domain/services/extraction_llm_service.py src/memory_system/settings/models.py
```

## 9. 验收标准

- [ ] `EXTRACTION_SYSTEM_PROMPT` 含 §2.1.2 四类定义、示例与 classification order（preference → event → profile → fact）
- [ ] §2.1.6 Requirements 1–13 核心约束保留（user evidence、JSON-only、predicate snake_case 等）
- [ ] `configs/base.yaml` 与 `MemoryExtractionSettings` 默认 `prompt_version=memory_extraction_v2`
- [ ] `tests/unit/test_extraction_system_prompt.py` 通过
- [ ] `tests/contract/test_ext003_contract.py` C7/C11 通过
- [ ] `tests/unit/test_settings_loader.py` 通过
- [ ] 无 Schema/API/error code/dependency 变更
- [ ] Ruff 通过（scoped files）
- [ ] Mypy 通过（scoped files）
- [ ] Review 无 P0/P1

## 10. 风险与阻塞项

- **设计文档冲突**：规格 §1446/§1850 示例仍为 `memory_extraction_v1`；本任务仅升运行时配置，**不**改规格正文；Evidence 代际共存属预期行为。
- **当前代码冲突**：planning 时 working tree dirty；实施前须干净 feat 分支，避免混入 LoCoMo/debug diff。
- **前置任务**：EXT-003/EXT-009 completed — **SATISFIED**
- **未批准依赖**：NONE
- **API/Schema 变化**：NONE（显式禁止）
- **其他风险**：prompt 变长略增 token 占用；仍在 `max_archive_estimated_tokens` 门禁内，且不分块策略不变。

## 11. Git 计划

```yaml
branch: "feat/EXT-010-extraction-prompt-memory-type-definitions"
expected_commits:
  - "docs(plan): add EXT-010 extraction prompt memory type definitions"
  - "feat(extraction): add memory type definitions to system prompt v2"
out_of_scope_changes:
  - "LoCoMo eval / debug 脚本与 src/memory_system/debug/**"
  - "unrelated extraction pipeline / validation / graph write 逻辑"
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
| 2026-08-25 | Step 1–5 | prompt v2 + tests | 52 scoped pytest PASS | clean whitelist only |
| 2026-08-25 07:01 UTC | POST_MERGE_CLEANUP | fetch + ff-only main sync；验证 PR #67 MERGED 与 implementation/merge facts；更新 progress.md 与 task plan；创建 `docs(status): complete EXT-010`；删除 exact feature branch local/remote | CODE_REVIEW_APPROVED P0=0 P1=0 P2=0；§2.1.2 memory type definitions + prompt_version v2；scoped 52 passed；ruff PASS；mypy PASS | `status=completed`；仅治理白名单；`next_action=EXT-010 completed — NO AUTO-START`；不得触碰 DEV-006/PR#13 |

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/domain/services/extraction_llm_service.py` | 修改 — §2.1.2 memory type definitions in prompt |
| `configs/base.yaml` | 修改 — `prompt_version: memory_extraction_v2` |
| `src/memory_system/settings/models.py` | 修改 — default `memory_extraction_v2` |
| `tests/contract/test_ext003_contract.py` | 修改 — C7/C11 v2 |
| `tests/unit/test_settings_loader.py` | 修改 — v2 assert |
| `tests/unit/test_extraction_system_prompt.py` | 创建 — prompt content unit tests |

### 与原计划的差异

无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit + Contract | `uv run pytest tests/unit/test_extraction_system_prompt.py tests/unit/test_settings_loader.py tests/contract/test_ext003_contract.py tests/unit/test_extraction_llm_service.py -q` | 52 passed |
| Ruff | scoped files | PASS |
| Mypy | scoped files | PASS |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 0
review_report: pending re-review after P1 cleanup
```

### Git 记录

```yaml
branch: feat/EXT-010-extraction-prompt-memory-type-definitions
plan_commit: "e56c69ca6721f5ad039010eaa85f5fe7e4e16d1c"
implementation_commit: "ce6de2e16dd560e8b07ad807f7d68cd133926cc5"
implementation_commit_message: "feat(extraction): add memory type definitions to system prompt v2"
record_commit: null  # pending this docs(status): complete commit SHA
merge_commit: "1ccd78a7c96e9908ebdb86a1ceb65729848029b0"
merged_at: "2026-08-25T07:01:02Z"
pr: "#67"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/67"
pr_state: MERGED
pr_base: main
pr_head: feat/EXT-010-extraction-prompt-memory-type-definitions
next_action: "EXT-010 completed — NO AUTO-START"
```

### 最终状态

`completed` — POST_MERGE_CLEANUP；implementation `ce6de2e16dd560e8b07ad807f7d68cd133926cc5`；PR #67 MERGED（`https://github.com/xu-jia-ming/memory_system/pull/67`；merge `1ccd78a7c96e9908ebdb86a1ceb65729848029b0`；mergedAt `2026-08-25T07:01:02Z`）；scoped 52 passed；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0/P1=0/P2=0；§2.1.2 memory type definitions + prompt_version v2；feat 分支本地/远程已删除；`next_action=EXT-010 completed — NO AUTO-START`；**不得触碰 DEV-006/PR#13**。

## 15. merge_record（POST_MERGE_CLEANUP 2026-08-25）

```yaml
status: completed
plan_commit: "e56c69ca6721f5ad039010eaa85f5fe7e4e16d1c"
implementation_commit: "ce6de2e16dd560e8b07ad807f7d68cd133926cc5"
implementation_commit_message: "feat(extraction): add memory type definitions to system prompt v2"
pr: "#67"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/67"
pr_state: MERGED
pr_base: main
pr_head: "feat/EXT-010-extraction-prompt-memory-type-definitions"
merge_commit: "1ccd78a7c96e9908ebdb86a1ceb65729848029b0"
merged_at: "2026-08-25T07:01:02Z"
verification: "scoped 52 passed; ruff PASS; mypy PASS"
feat_branch: deleted
next_action: "EXT-010 completed — NO AUTO-START"
```
