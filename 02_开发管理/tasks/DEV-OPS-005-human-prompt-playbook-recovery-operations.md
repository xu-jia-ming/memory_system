# DEV-OPS-005 Human Prompt Playbook and Recovery Operations Manual

## 1. 任务信息

```yaml
task_id: DEV-OPS-005
task_name: Human Prompt Playbook and Recovery Operations Manual
status: reviewed
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "非业务规格任务：人类可操作的仓库本地 Prompt Playbook / Recovery 操作手册；不修改技术规格正文、业务 Contract、Orchestrator/Subagent 设计、NORMAL/STRICT 语义"
prerequisites:
  - "DEV-004 completed（PR #10 MERGED；docs(status) complete on main：4a5cbc2）"
  - "DEV-OPS-003 completed（NORMAL/STRICT）；DEV-OPS-004 completed（Mihomo §18）"
  - "基线：main @ 4a5cbc2e9a7f5472749cc0181b7f91153b91479d；与 origin/main 同步；工作区干净（规划轮次只读验证通过）"
  - "本任务为用户显式插入/覆盖：在 DEV-005 业务规划/实施之前执行；不得开始 DEV-005 业务实施"
branch: "feat/DEV-OPS-005-human-prompt-playbook-recovery-operations"
created_at: "2026-08-08 10:20 UTC"
updated_at: "2026-08-08 10:48 UTC"
approval_gates:
  planning_docs: "approved；人工 PLAN_APPROVED 2026-08-08 10:30 UTC；吸收 SHOULD_FIX 1–3；PLAN_LANDING 完成"
  implementation_plan: "status=reviewed；CODE_REVIEW_APPROVED（P0=0/P1=0/P2=0/P3=3 残余不阻塞）；Commit Recorder READY_FOR_HUMAN_COMMIT；进入 IMPLEMENTATION_RELEASE"
insertion_override:
  prior_current_task: "DEV-005"
  prior_current_task_status: "planned"
  prior_next_action: "进入 DEV-005（通用 API 壳、鉴权、Request ID、日志与指标）业务规划；本 Commit 不得开始 DEV-005 实施"
  override_by: "用户本轮显式字段 TASK_ID=DEV-OPS-005 + WORKFLOW_MODE=NORMAL(explicit) + Orchestrator 规划轮次"
  effect: "current_task 切换为 DEV-OPS-005；DEV-005 保持 planned 且本任务期间不得启动业务实施；完成后 next_action 恢复 DEV-005 业务规划（仍不得实施至另一次显式编排）"
```

### 1.1 权威源与读者

| 项 | 决定 |
|---|---|
| 权威文档（单一） | `03_AI_Prompts/01_项目日常操作手册.md`（新建；人类面向 Playbook） |
| 契约测试 | `tests/unit/test_project_operations_playbook_contract.py`（新建；静态子串/存在性） |
| 读者 | 人类操作者（会话历史不可用时仍能继续项目）；Agent 可引用但**不**改 Orchestrator 设计 |
| 与既有 `01_初始化与Backlog.md` | **共存、职责分离**（不同文件名）：`01_初始化与Backlog.md` = AI/角色向「初始化与 Backlog」Prompt；`01_项目日常操作手册.md` = **人类**日常粘贴/恢复/失败处置 Playbook。本任务**不**重命名/删除既有 `01_初始化与Backlog.md`，也**不**把其正文并入 Playbook |
| 与 `00_全局开发规则.md` | **不修改**（DD-003）；Playbook 仅引用 §17–§18；发现入口用 README 短指针，**不**改 `00_` 作入口 |
| 与 `09_会话恢复.md` | 保留既有 Prompt；Playbook 可交叉引用，但**不**把会话恢复 Prompt 全文复制进手册 |

---

## 2. 任务目标

在会话历史不可用时，人类仅凭仓库内文档仍能安全继续 Memory System MVP 开发工作流。

完成后应具备：

1. **权威人类操作手册**：新建 `03_AI_Prompts/01_项目日常操作手册.md`，作为本仓库「日常如何粘贴/恢复/失败处置」的唯一权威 Playbook（文档任务；非业务代码）。
2. **文首必含「我以后只需要记住什么？」**：用极短清单回答人类最小记忆负担（例如：看 `progress.md` / 当前 Task Plan / 选对模板粘贴 / 两门禁 / 禁止危险 Git）。
3. **六模板（强制；模板名锁定英文标识）**：

| 模板 ID | 用途（摘要） | 粘贴块必填字段（实施锁定） |
|---|---|---|
| `START_EXISTING_TASK` | 从干净/已知状态继续已登记任务。**首轮仅规划**：Orchestrator 只调度 Planner→Plan Reviewer→等待人工 `PLAN_APPROVED`；**禁止**根据人类短描述发明实现；实施内容须从仓库权威源（`progress.md` / 当前 Task Plan / 规格 / 既有代码）推导 | `TASK_ID`；`WORKFLOW_MODE`（及 source：explicit/default）；「首轮 planning-only」声明；「禁止从短描述发明实现」声明；权威源核对清单（progress / plan / git status） |
| `PLAN_APPROVED` | 人工确认计划批准后的续跑口令/粘贴块（NORMAL **常规人工门禁 #1**）。其后 **NORMAL 自动链**（见 MF-3 / §2.1），**无**第二次手工 `PLAN_LANDING` 门 | `TASK_ID`；`PLAN_APPROVED` 字面口令；确认指向的 plan 文件路径 |
| `AFTER_PR_MERGE` | 人工 Merge PR 后恢复编排（NORMAL **常规人工门禁 #2** → 期望自动 `POST_MERGE_CLEANUP`） | `TASK_ID`；PR 号或 merge 证据提示；「已人工 Merge、禁止 Agent `gh pr merge`」声明 |
| `RECOVERY_MODE` | 会话丢失 / 状态不明：先只读核对再决定；禁止盲目重试 | `TASK_ID`（若已知）；「先只读」声明；核对清单（progress / plan / `git status` / branch） |
| `NEW_UNPLANNED_FEATURE` | 未规划新需求：必须先规划（Task Plan → Plan Review → `PLAN_APPROVED`），禁止直接编码 | 需求短名；「先规划、禁止直接编码」声明；期望 `WORKFLOW_MODE` |
| `FAILURE_AND_RECOVERY` | 失败分类、fix≠retry、HALT 条件、何时开 follow-up / 记 governance deviation | 失败现象摘要；已尝试步骤；「fix≠retry / 禁止盲重试」声明；分类码（若已知） |

4. **规则 A–E（强制落入手册；可检索标签 + 契约锁定）**：

手册中每条规则须有**可检索标题/锚点标签**（契约按字面锁定）：`规则 A`、`规则 B`、`规则 C`、`规则 D`、`规则 E`（可并列英文短名，但中文「规则 X」标签必现）。

| 可检索标签 | 强制内容 |
|---|---|
| **规则 A**（no blind retry） | 禁止盲目重试同一失败命令；先分类再行动；有界重试预算；耗尽 → HALT + 报告 |
| **规则 B**（Docker / Mihomo） | **引用** `03_AI_Prompts/00_全局开发规则.md` §18（DEV-OPS-004）；手册**不**全文复制 Mihomo 策略；点名：daemon≠BuildKit 临时 proxy；`7890`≠Mihomo（SSH forwarding）；本机 Mihomo=`17890` |
| **规则 C**（self-ref SHA） | 回写/记录 commit 时禁止把「即将产生的自身 SHA」当成已存在事实；`latest_commit` / 治理字段须为真实已存在 HEAD 或明确 `null`/待填 |
| **规则 D**（WAITING clean） | 进入/恢复 `WAITING_FOR_PR_MERGE`（及同类 pause）前工作树须干净（或仅含已批准白名单内预期变更）；unexpected dirty → fail-closed |
| **规则 E**（governance deviation） | 发现治理偏差须记录（如 GD-*）；接受偏差≠放宽 fail-closed；未来失败仍须报告+授权；不得用 deviation 掩盖盲重试 |

5. **NORMAL 常规人工门禁 = 恰好两扇（MF-1）**：仅 `PLAN_APPROVED` 与 Human PR Merge。`READY_FOR_HUMAN_COMMIT` 是 Commit Recorder **兼容边界标记**（boundary + message 草稿就绪），**不是**第三扇常规人工门；NORMAL 在该标记后 **自动**调度 `IMPLEMENTATION_RELEASE`（fail-closed 例外除外）。
6. **强制静态契约测试**：存在性 + 必含子串/模板 ID / 规则 A–E 可检索标签 / 下列 invariants（§8）；防止手册被删空或关键门禁回退。
7. **完成后** `next_action` 指向 DEV-005 业务规划；**本任务期间与完成 Commit 均不得开始 DEV-005 实施**。

### 2.1 NORMAL 自动链与两门禁（MF-1 / MF-3；手册必须写清）

**常规人工门禁（恰好两扇）**：

1. 人工 `PLAN_APPROVED`（门禁 #1）
2. 人工 Human PR Merge（门禁 #2）

**兼容标记（非门禁）**：Commit Recorder 输出字面 `READY_FOR_HUMAN_COMMIT` → Orchestrator 在 NORMAL 下据此自动进入 `IMPLEMENTATION_RELEASE`；人类**不**需再点一次「批准 commit/Release」。

**人工 `PLAN_APPROVED` 之后的 NORMAL 自动链（无第二次手工 `PLAN_LANDING` 门）**：

```text
PLAN_LANDING
→ Developer
→ tests
→ Code Reviewer
→ Commit Recorder（输出 READY_FOR_HUMAN_COMMIT）
→ IMPLEMENTATION_RELEASE（自动；push/PR）
→ WAITING_FOR_PR_MERGE
```

其后：人工 Merge → 自动 `POST_MERGE_CLEANUP`（仍无第三次批准门）。任一环节 fail-closed 例外 → HALT/报告，不得盲续跑。

### 2.2 关键设计决策

#### DD-001 — 单一权威 Playbook（人类面向）

**选择**：新建 `03_AI_Prompts/01_项目日常操作手册.md` 为人类日常操作唯一权威源。

**理由**：

1. 目标读者是人类（会话丢失场景）；与 AI 固定约束 `00_全局开发规则.md` 职责分离。
2. 既有 `09_会话恢复.md` 仅覆盖「恢复上下文」Prompt，不含六模板与 NORMAL 两门禁操作剧本。
3. 双源漂移风险：Mihomo/网络细节继续以 `00_全局开发规则.md` §18 为权威；Playbook **只引用**。

**拒绝**：把完整操作手册塞进 `00_全局开发规则.md`；或另增 `02_开发管理/ops_*.md` 第二真相源。

#### DD-002 — 文档/契约 only；零编排与业务变更

本任务只改：Playbook + 契约测试 + 开发管理回写 +（可选）发现入口短指针。  
**禁止**：改 Orchestrator / Subagents / permissions / 五命令正文 / NORMAL·STRICT 语义 / 业务 `src/**` / migrate / compose / Dockerfile。

#### DD-003 — 发现入口最小化（README 短指针；不改 `00_`）

**选择（保持）**：在 `README.md` 增加**极短**发现指针（路径 + 一句话用途），**不**全文复制 Playbook。  
**明确不采用**：修改 `03_AI_Prompts/00_全局开发规则.md` 作为发现入口或塞入人类操作剧本（避免 AI 约束块膨胀；人类入口以 README + `03_AI_Prompts/01_项目日常操作手册.md` 为准）。本任务**零编辑** `00_全局开发规则.md`。

若后续 Reviewer 要求取消 README 改动：可降级为「仅 Playbook + 契约 + 治理三文件」，不阻塞目标；但**仍禁止**改 `00_` 作替代入口。

#### DD-004 — 真实缺陷记 follow-up；本任务不改 mode 语义

手册描述**现行** DEV-OPS-003 NORMAL/STRICT 行为（含两门禁、`READY_FOR_HUMAN_COMMIT` 兼容语义、`PLAN_APPROVED` 后自动链）。若实施中发现 Orchestrator/文档不一致：记入 Task Plan follow-up / `open_issues` 风格条目，**不**在本任务修改 mode 实现或放宽门禁。

#### DD-005 — 文件名 `01_` 前缀共存与职责澄清

与既有 `01_初始化与Backlog.md` 并存；不重编号历史 Prompt 文件（非本任务范围）。Playbook 文首或「权威源」小节须用一两句区分：Backlog Prompt ≠ 人类日常操作手册（见 §1.1）。

---

## 3. 非目标

- 开始或实施 **DEV-005**（通用 API 壳等）业务代码/业务规划实施。
- 修改 Orchestrator 设计（`.cursor/commands/orchestrate-task.md` 行为语义）。
- 修改 NORMAL / STRICT 模式实现或契约语义（真实缺陷仅记 follow-up）。
- 扩大 `.cursor/permissions.json` / CLI 权限；修改五条 DEV-OPS-001 命令正文。
- 修改 `.cursor/agents/**`、fallback 命令正文。
- 修改 `scripts/migrate.py`、Migration、`compose*.yaml`、`Dockerfile`、`.env.example`。
- 修改业务代码 `src/**` 或既有业务测试语义。
- 修改技术规格正文 / API Contract / Schema / 错误码 / 状态机。
- 全文复制 Mihomo §18 进 Playbook（仅引用）。
- 自动 Push/Merge/Rebase/Force Push；`gh pr merge`；`git reset --hard`；`git clean -fd`；`git branch -D`。
- 提交 Secret、真实用户数据、完整 Prompt/Response 日志。
- 真实基础设施 Integration/E2E（本任务无运行时依赖）。

---

## 4. 当前代码状态

- **已存在**：
  - `03_AI_Prompts/00_全局开发规则.md`（含 Release 窄例外 + Mihomo §18）。
  - `03_AI_Prompts/01_初始化与Backlog.md` … `10_Bug修复.md`（角色 Prompt；**无**人类六模板 Playbook）。
  - `03_AI_Prompts/09_会话恢复.md`（只读恢复 Prompt；范围窄于本任务）。
  - NORMAL/STRICT 权威行为：`.cursor/commands/orchestrate-task.md` + `tests/unit/test_cursor_workflow_modes_contract.py`。
  - Mihomo 契约：`tests/unit/test_mihomo_network_fallback_contract.py`。
  - `README.md`：工程/Compose 说明；**无**人类工作流 Playbook 入口。
- **可复用组件**：既有 unit 契约测试风格（`Path` 读文本、`assert "…" in text`）；DEV-OPS-004 合同模式。
- **当前缺失**：`03_AI_Prompts/01_项目日常操作手册.md`；`tests/unit/test_project_operations_playbook_contract.py`。
- **与技术规格不一致之处**：无（非业务规格任务）。
- **前置任务检查**：DEV-004 `completed`；main @ `4a5cbc2` == `origin/main`；工作区干净（规划时验证）。`progress.md` 在插入前仍指向 DEV-005 `planned`（本轮覆盖）。

---

## 5. 实现方案

### Step 1 — 新建权威 Playbook

- **文件**：`03_AI_Prompts/01_项目日常操作手册.md`（创建）
- **类/函数/Schema**：不适用（人类操作文档）
- **输入**：现行 NORMAL/STRICT 行为（DEV-OPS-003）、Release 三相、全局规则 §17–§18、本 Task Plan §2 / §2.2
- **输出结构（强制）**：
  1. 文首章节标题或等价显著段落：**「我以后只需要记住什么？」**（含：看 progress/plan、选对模板、**恰好两扇常规人工门**、禁危险 Git；并点名 `READY_FOR_HUMAN_COMMIT` ≠ 第三门）
  2. **权威源澄清（SHOULD_FIX）**：一两句区分本 Playbook（人类日常）与 `01_初始化与Backlog.md`（AI/初始化 Prompt）；声明**不**改 `00_全局开发规则.md`
  3. 六模板章节，每个模板以英文 ID 作为可检索标题/锚点：`START_EXISTING_TASK`、`PLAN_APPROVED`、`AFTER_PR_MERGE`、`RECOVERY_MODE`、`NEW_UNPLANNED_FEATURE`、`FAILURE_AND_RECOVERY`；每模板含：
     - 前置条件 / 下一步
     - **可复制粘贴块**，且粘贴块含 §2 表「粘贴块必填字段」
     - 模板专属硬约束（见下）
  4. **`START_EXISTING_TASK` 硬约束（MF-2）**：粘贴块与正文须写明——首轮 **planning-only**（Planner→Plan Reviewer→人工 `PLAN_APPROVED`）；**禁止**从人类短描述发明实现；须从仓库权威源推导任务内容
  5. **`PLAN_APPROVED` / NORMAL 链硬约束（MF-1 / MF-3）**：写明门禁 #1 后 NORMAL **自动** `PLAN_LANDING`→Developer→tests→Code Reviewer→Commit Recorder→`IMPLEMENTATION_RELEASE`→push/PR→`WAITING_FOR_PR_MERGE`；**无**手工第二次 `PLAN_LANDING` 门；`READY_FOR_HUMAN_COMMIT` 仅为兼容标记并触发自动 Release（非第三门）
  6. **规则 A–E** 独立可检索小节：标题须含字面 **`规则 A`** … **`规则 E`**（可并列英文短名）；契约按标签锁定
  7. **Invariants 摘要**（与 §8 契约对齐；可用表格）：至少覆盖 §8 全部 invariants（含 MF-1/2/3 新增行）
  8. Mihomo/Docker：**链接/引用** `00_全局开发规则.md`，不复制全文；本任务不编辑该文件
- **错误处理**：文案不得含 Secret；不得教人执行永久禁止命令
- **幂等**：单一权威文件；不另增第二 Playbook

### Step 2 — 强制契约测试

- **文件**：`tests/unit/test_project_operations_playbook_contract.py`（创建）
- **输入**：读取 `03_AI_Prompts/01_项目日常操作手册.md`
- **输出/断言**（最小必含；实施可拆多 test 函数）：见 §8 Contract 表
- **禁止**：真实网络、改 Orchestrator、降断言绕过

### Step 3 — 可选发现入口

- **文件**：`README.md`（修改；可选但本计划默认纳入白名单）
- **内容**：新增短节（建议 ≤10 行）：指向 `03_AI_Prompts/01_项目日常操作手册.md`，说明「会话历史不可用时的人类操作入口」
- **禁止**：粘贴六模板全文进 README

### Step 4 — 开发管理回写（实施阶段）

- **文件**：本 Task Plan；`02_开发管理/progress.md`；`02_开发管理/master_plan.md`
- **目的**：状态机推进；**不得**开始 DEV-005
- **完成后 next_action**：进入 DEV-005 业务规划（仍不得实施至另一次显式编排）

### Step 5 — 质量门禁

- `uv run pytest tests/unit/test_project_operations_playbook_contract.py -q`
- `uv run pytest tests/unit -q`（全 unit 保持通过）
- 既有 cursor / mihomo 契约保持通过
- `uv run ruff check .`；`uv run mypy src tests scripts`（新测试须符合）

---

## 6. 文件变更清单

### 6.1 精确白名单（实施可写；exact paths）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `03_AI_Prompts/01_项目日常操作手册.md` | 创建 | 权威人类 Playbook（六模板 + 规则 A–E + invariants） |
| `tests/unit/test_project_operations_playbook_contract.py` | 创建 | 强制静态契约 |
| `README.md` | 修改 | 可选发现入口（短指针；默认纳入） |
| `02_开发管理/tasks/DEV-OPS-005-human-prompt-playbook-recovery-operations.md` | 修改 | 执行记录 / 状态 |
| `02_开发管理/progress.md` | 修改 | 规划态→实施态回写；插入覆盖；完成后推迟 DEV-005 |
| `02_开发管理/master_plan.md` | 修改 | Phase 0 补充登记 DEV-OPS-005；CHANGE-009 |

### 6.2 明确不采用的可选路径

| 路径 | 决策 |
|---|---|
| `03_AI_Prompts/00_全局开发规则.md` 作为发现入口 | **本计划不采用**（DD-003）；Mihomo 仍只被 Playbook 引用 |
| 额外 `02_开发管理/ops_*.md` / 第二 Playbook | **不采用**（DD-001） |
| 重命名 `01_初始化与Backlog.md` | **不采用**（DD-005） |

### 6.3 黑名单（禁止）

- `src/**`
- `01_技术规格/**`
- `.cursor/commands/**`（含 `orchestrate-task.md`）
- `.cursor/agents/**`
- `.cursor/permissions.json` / CLI 权限
- `scripts/migrate.py` / `scripts/migrations/**`
- `compose*.yaml` / `Dockerfile` / `.env.example`
- `02_开发管理/tasks/DEV-005-*.md`（不得创建/修改 DEV-005 计划）
- 既有业务/Integration/E2E 测试语义改写
- `03_AI_Prompts/00_全局开发规则.md` 全文策略改写（本任务不改；仅引用）

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 文档任务：Playbook 与契约测试须同一实现 Commit 内同时落地 | 有手册无测试或测试红灯 → 不可 `tested` |
| 幂等 | 重复应用同一文案不产生第二真相源 | DD-001 单文件；契约锁定模板 ID |
| 并发 | 不适用多写者业务并发 | 单任务单分支；不并行 DEV-005 |
| 版本冲突 | 不适用业务乐观锁 | Git 冲突按正常分支；禁止 force push |
| 用户隔离 | 不适用多租户数据 | 禁止提交真实用户/Secret |
| 部分失败 | 仅改了手册未加测试、或测试红灯 | 不得标 tested；不得降断言 |
| 进程异常恢复 | 手册本身教 RECOVERY_MODE / FAILURE_AND_RECOVERY | 规则 A：no blind retry；先只读 |

**一致性补充**：Playbook 对 NORMAL **恰好两扇**常规人工门 / `READY_FOR_HUMAN_COMMIT` 兼容语义 / `PLAN_APPROVED` 后自动链 / POST_MERGE 自动 / 禁令命令的描述必须与现行 DEV-OPS-003 文档一致；若发现不一致 → HALT 记 follow-up（DD-004），不在本任务改 Orchestrator。

---

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 新建契约模块可被 pytest 收集 | import/收集成功 |
| 无业务纯函数 | 声明：本任务无业务纯函数；unit 层以契约文件承载 |

### Contract Test（强制；本任务主门禁）

权威文件：`03_AI_Prompts/01_项目日常操作手册.md`

| 场景 / invariant | 预期（子串或等价落盘锁定） |
|---|---|
| 文件存在 | `is_file` |
| 文首记忆负担 | 含「我以后只需要记住什么？」 |
| 六模板 ID | 含 `START_EXISTING_TASK`、`PLAN_APPROVED`、`AFTER_PR_MERGE`、`RECOVERY_MODE`、`NEW_UNPLANNED_FEATURE`、`FAILURE_AND_RECOVERY` |
| 规则 A–E 可检索标签 | 含字面 `规则 A`、`规则 B`、`规则 C`、`规则 D`、`规则 E`；并分别锁定 no blind retry；Docker/Mihomo 引用全局规则；self-ref SHA；WAITING clean；governance deviation |
| NORMAL 恰好两扇常规人工门（MF-1） | 明确常规人工门禁**恰好两扇**：`PLAN_APPROVED` + Human PR Merge（或等价「人工 Merge」/`Human PR`）；不得暗示第三扇常规人工门 |
| `READY_FOR_HUMAN_COMMIT` 兼容标记（MF-1） | 含字面 `READY_FOR_HUMAN_COMMIT`；说明其为 Commit Recorder 兼容边界标记、**非**第三扇常规人工门；NORMAL 在其后**自动** `IMPLEMENTATION_RELEASE` |
| `START_EXISTING_TASK` 首轮 planning-only（MF-2） | 在 `START_EXISTING_TASK` 语境：首轮仅 Planner→Plan Reviewer→人工 `PLAN_APPROVED`；禁止从人类短描述发明实现；须从仓库权威源推导 |
| `PLAN_APPROVED` 后 NORMAL 自动链（MF-3） | 人工 `PLAN_APPROVED` 后自动：`PLAN_LANDING`→Developer→tests→Code Reviewer→Commit Recorder→`IMPLEMENTATION_RELEASE`→push/PR→`WAITING_FOR_PR_MERGE`（fail-closed 例外除外）；**无**手工第二次 `PLAN_LANDING` 门 |
| 先规划 | 含编码前须 Task Plan / `PLAN_APPROVED`（或「先规划」）意图 |
| 无手工 commit 门（NORMAL） | 说明 NORMAL 下实现 Commit/PR 由 Release Operator 自动（非人类手工 `git commit` 门禁） |
| PR merge 人工 | 明确 PR Merge **人工**；禁止 Agent `gh pr merge` |
| POST_MERGE 自动 | NORMAL 在验证 MERGED 后自动 `POST_MERGE_CLEANUP`（无需第三次批准门） |
| recovery 先只读 | `RECOVERY_MODE`：先只读核对（progress/plan/git status）再行动 |
| no blind retry | 明确禁止盲目重试 |
| fix≠retry | 明确「修复 ≠ 重试同一失败命令」或等价 `fix≠retry` / 「fix != retry」 |
| 永久禁令命令 | 锁定禁止：`gh pr merge`、`force` push / `--force`、`reset --hard`、`clean -fd`、`branch -D` |
| self-ref SHA | 禁止把尚未产生的自身 commit SHA 当作已存在事实 |
| daemon≠BuildKit proxy | 点名 Docker daemon 代理 ≠ BuildKit/临时 ad-hoc proxy（或等价；并引用全局规则） |
| 7890≠Mihomo | `7890` 非 Mihomo；Mihomo/`17890` 引用全局规则 |
| secrets | 禁止提交 Secret / 真实用户数据 |
| WAITING 需 clean WT | `WAITING_FOR_PR_MERGE`（或 WAITING）恢复/进入前工作树干净要求 |
| Playbook≠Backlog Prompt（SHOULD_FIX） | 点名区分本手册与 `01_初始化与Backlog.md`（或等价「初始化与Backlog」）职责 |

### Integration Test

| 场景 | 预期 |
|---|---|
| 不适用 | 无真实基础设施要求 |

### E2E Test

| 场景 | 预期 |
|---|---|
| 不适用 | 无（不跑真实编排冒烟；本任务为文档契约） |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 不适用真实失败注入 | Playbook 描述 FAILURE_AND_RECOVERY 即可 |
| 并发 | 不适用 |

### 静态质量

| 检查 | 预期 |
|---|---|
| Ruff | 全仓通过（含新测试） |
| Mypy | `src tests scripts` 通过 |
| 既有 unit / cursor / mihomo 契约 | 保持通过 |

---

## 9. 验收标准

- [x] `03_AI_Prompts/01_项目日常操作手册.md` 存在，且含「我以后只需要记住什么？」+ 六模板 ID + 可检索 `规则 A`…`规则 E`
- [x] 手册锁定 MF-1/MF-2/MF-3：恰好两扇常规人工门；`READY_FOR_HUMAN_COMMIT` 非第三门；`START_EXISTING_TASK` planning-only；`PLAN_APPROVED` 后自动链且无第二次手工 `PLAN_LANDING` 门
- [x] `tests/unit/test_project_operations_playbook_contract.py` 存在且 §8 invariants 全部断言通过（含 MF/SHOULD_FIX 新增行）
- [x] README 发现入口已加短指针（若 Reviewer 批准取消则更新本条为 N/A，且白名单同步）；**未**编辑 `00_全局开发规则.md`
- [x] **未**修改 Orchestrator / agents / permissions / migrate / compose / Dockerfile / 业务 `src/**`
- [x] **未**开始 DEV-005 实施；DEV-005 仍为 `planned`（推迟）
- [x] `uv run pytest tests/unit -q` 通过
- [x] Ruff 通过
- [x] Mypy 通过
- [x] Review 无 P0/P1（P0=0；P1=0；P2=0；P3=3 残余不阻塞）
- [ ] 完成后 `next_action` = DEV-005 业务规划（不得实施；本轮 next_action=IMPLEMENTATION_RELEASE/PR）

---

## 10. 风险与阻塞项

- **设计文档冲突**：若 Playbook 与 Orchestrator 现行行为不一致 → 停止改 mode；记 follow-up（DD-004）。
- **当前代码冲突**：无业务冲突；`01_` 文件名共存可能造成人类目录混淆 → DD-005 接受；README 指针降低发现成本。
- **前置任务**：DEV-004 / DEV-OPS-003 / DEV-OPS-004 completed（满足）。
- **未批准依赖**：无。
- **API/Schema 变化**：无。
- **其他风险**：
  - 手册过长 → 文首「只需要记住什么」+ 模板表压缩；细节用链接引用全局规则。
  - Agent/人类忽略手册 → 契约防回退；不能替代运行时强制。
  - 误把可选 README 写成全文复制 → 白名单与验收明确禁止。

---

## 11. Git 计划

```yaml
workflow_mode: NORMAL
workflow_mode_source: explicit
branch: "feat/DEV-OPS-005-human-prompt-playbook-recovery-operations"
expected_commits:
  - "docs(plan): add DEV-OPS-005 human prompt playbook recovery operations plan"
  - "docs(ai): add human project operations playbook and contract tests"
  - "docs(status): record DEV-OPS-005 implementation commit and PR"  # feat 上；IMPLEMENTATION_RELEASE 可选
  - "docs(status): complete DEV-OPS-005 after PR merge"  # POST_MERGE_CLEANUP on main
out_of_scope_changes:
  - "DEV-005 API 壳任何业务文件"
  - "src/** 业务代码"
  - "Orchestrator / agents / permissions / 五命令正文"
  - "migrate / compose / Dockerfile"
  - "NORMAL/STRICT 语义实现变更"
  - "第二份 ops Playbook"
release_phases:
  PLAN_LANDING: "main: docs(plan) + ff-only + 创建 exact feat"
  IMPLEMENTATION_RELEASE: "仅 feat: 白名单 add/commit/push/PR；禁 push main"
  POST_MERGE_CLEANUP: "PR MERGED 后：ff-only main + docs(status) complete + 删 exact feat"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 002

- 日期：2026-08-08 10:30 UTC
- 原计划：Amendment 001 后 §2.2（自动链）出现在 §2.1（设计决策）之前。
- 修改内容：仅交换/重编号为 §2.1=NORMAL 自动链与两门禁、§2.2=关键设计决策；不改变 scope/contract。同步人工批准吸收 SHOULD_FIX 1–3（STRICT 对照由实施手册+契约完成；progress 时间线已补记）。
- 修改原因：人工 PLAN_APPROVED 要求吸收 Plan Reviewer SHOULD_FIX 2（章节编号）。
- 是否影响技术规格：否
- 审批状态：随人工 PLAN_APPROVED 吸收

### Amendment 001

- 日期：2026-08-08 10:25 UTC
- 原计划：初版 Task Plan（2026-08-08 10:20 UTC）已含六模板、规则 A–E、NORMAL 两门禁与契约表，但未把 Plan Reviewer Round 1 的 MF-1/MF-2/MF-3 与 SHOULD_FIX 锁进 §2 模板表、§5 Step1、§8 契约行。
- 修改内容：
  1. **MF-1**：§2 / §2.2 写明 NORMAL **恰好两扇**常规人工门（`PLAN_APPROVED` + Human PR Merge）；字面 `READY_FOR_HUMAN_COMMIT` = Commit Recorder 兼容标记、**非**第三门；NORMAL 其后自动 `IMPLEMENTATION_RELEASE`。§8 新增对应契约行（含字面 `READY_FOR_HUMAN_COMMIT`）。
  2. **MF-2**：`START_EXISTING_TASK` 模板强制「首轮 planning-only」（Planner→Plan Reviewer→人工 `PLAN_APPROVED`）；禁止从短描述发明实现；须从仓库权威源推导。§5 Step1 + §8 绑定该模板锁定。
  3. **MF-3**：§2.2 / §5 Step1 写明人工 `PLAN_APPROVED` 后 NORMAL 自动链 `PLAN_LANDING`→Developer→tests→Code Reviewer→Commit Recorder→`IMPLEMENTATION_RELEASE`→push/PR→`WAITING_FOR_PR_MERGE`（fail-closed 例外）；**无**手工第二次 `PLAN_LANDING` 门。§8 新增 invariant 行。
  4. **SHOULD_FIX**：规则 A–E 强制可检索字面标签 `规则 A`…`规则 E`；六模板粘贴块必填字段写入 §2 表；§1.1/DD-005 澄清 Playbook vs `01_初始化与Backlog.md`；保持 README 短指针、**不**编辑 `00_全局开发规则.md`（DD-003）。
- 修改原因：吸收独立 Plan Reviewer Round 1 MUST_FIX MF-1 / MF-2 / MF-3 与 SHOULD_FIX；防止手册把兼容标记误写成第三人工门、或允许短描述直写实现、或插入第二次 PLAN_LANDING 人工门。
- 是否影响技术规格：否（非业务；不改 Orchestrator/mode 实现；仅收紧本任务 Playbook/契约验收文案）。
- 审批状态：待 Plan Review Round 2（本 Amendment 落盘后 `status` 仍为 `planned`）。

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-08 10:20 UTC | Planner 初版计划 | 创建本 Task Plan；progress/master_plan 规划态登记（插入覆盖 DEV-005） | 未实施 | 基线 main@4a5cbc2 干净；未 Git 写；未开始 DEV-005 |
| 2026-08-08 10:25 UTC | Planner Amendment 001 | 吸收 MF-1/MF-2/MF-3 + SHOULD_FIX 入 §1.1/§2/§2.2/§5 Step1/§8/Amendment 001；status 保持 planned | 未实施 | 未 Git 写；未开始 DEV-005；未改 Playbook 实现 |
| 2026-08-08 10:28 UTC | Plan Review Round 2 | `PLAN_APPROVED`；MUST_FIX=0；SHOULD_FIX=STRICT对照/章节编号/progress时间线 | 未实施 | 等待人工确认 |
| 2026-08-08 10:30 UTC | 人工 PLAN_APPROVED + Amendment 002 | status→approved；理顺 §2.1/§2.2；progress 补记 Round1/Amd001/Round2 | 未实施 | 进入 PLAN_LANDING；不得开始 DEV-005 |
| 2026-08-08 10:31 UTC | PLAN_LANDING | docs(plan) on main；创建 feat/DEV-OPS-005-human-prompt-playbook-recovery-operations | n/a | plan_commit=a601a3ba569b12b8fc0ae8ff913f66927381af19；等待 Developer；不得开始 DEV-005 |
| 2026-08-08 10:40 UTC | Developer 开工 | status→in_progress；开始白名单实施（Playbook+契约+README+治理回写） | 待跑 | 未 Git 写；不得开始 DEV-005 |
| 2026-08-08 10:45 UTC | Developer implemented→tested | Playbook+契约+README 落盘；质量门禁全绿 | Contract 28 passed；unit 156 passed；ruff/mypy exit=0 | 未 Git 写；等待 Code Review；不得开始 DEV-005 |
| 2026-08-08 10:46 UTC | Code Review | `CODE_REVIEW_APPROVED`；P0=0；P1=0；P2=0；P3=3（残余不阻塞） | n/a（Reviewer 静态交叉核对契约） | 未 Git 写；不得开始 DEV-005 |
| 2026-08-08 10:47 UTC | Commit Recorder | `READY_FOR_HUMAN_COMMIT`（NORMAL 兼容边界标记） | n/a | 白名单 6 路径；无 Secret；建议 status→reviewed |
| 2026-08-08 10:48 UTC | Release Operator pre-commit | status→reviewed；Review 结果回写；next_action→IMPLEMENTATION_RELEASE/PR | n/a | 即将实现 Commit；不得开始 DEV-005 |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `03_AI_Prompts/01_项目日常操作手册.md` | 新建：文首记忆负担；六模板粘贴块；规则 A–E；NORMAL/STRICT 对照；invariants |
| `tests/unit/test_project_operations_playbook_contract.py` | 新建：§8 + SHOULD_FIX1 静态契约（28 tests） |
| `README.md` | 短发现入口（指向 Playbook；无全文复制） |
| 本 Task Plan | 执行记录 / status=`reviewed` |
| `02_开发管理/progress.md` | 实施态回写 + 测试结果 + reviewed |
| `02_开发管理/master_plan.md` | Phase 0 补充状态→`reviewed` |

### 与原计划的差异

暂无。SHOULD_FIX 1（NORMAL vs STRICT 对照）已落入手册与契约。P3=3 残余（契约 `tests` 字面、host OR 分支偏松、对照表措辞）不阻塞本轮。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Contract | `uv run pytest tests/unit/test_project_operations_playbook_contract.py -q` | **28 passed**；exit=0 |
| Unit | `uv run pytest tests/unit -q` | **156 passed**；exit=0 |
| Integration | N/A |  |
| E2E | N/A |  |
| Ruff | `uv run ruff check .` | All checks passed；exit=0 |
| Mypy | `uv run mypy src tests scripts` | Success: 61 source files；exit=0 |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 3
review_verdict: CODE_REVIEW_APPROVED
review_report: "P3 residual: (1) MF-3 auto-chain test omits literal tests step; (2) host-workaround OR branch loose; (3) Human PR Review/Merge vs Human PR Merge wording. Non-blocking."
```

### Git 记录

```yaml
branch: feat/DEV-OPS-005-human-prompt-playbook-recovery-operations
plan_commit: a601a3ba569b12b8fc0ae8ff913f66927381af19
implementation_commit: null
implementation_commit_message: "docs(ai): add human project operations playbook and contract tests"
pr: null
pr_url: null
pr_status: null
```

### 最终状态

`reviewed`
