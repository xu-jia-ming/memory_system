# DEV-OPS-002 Cursor Orchestrator、可复用 Subagents 与受控 Release Automation

## 1. 任务信息

```yaml
task_id: DEV-OPS-002
task_name: Cursor Orchestrator、可复用 Subagents 与受控 Release Automation
status: approved
spec_sections:
  - "非业务规格任务：对齐仓库治理与 03_AI_Prompts 角色流程；扩展 DEV-OPS-001 工作流自动化；不修改技术规格正文"
prerequisites:
  - "DEV-OPS-001 completed（五个 Slash Commands + 契约测试已在 main；最终治理 Commit 5f34ccb）"
  - "DEV-001 completed（工程骨架与质量工具就绪；本任务不依赖其业务代码变更）"
  - "基线 Commit 5f34ccbcb7a052131dbeedd17c68dbf6dc30c52d；main 与 origin/main 同步"
  - "规划轮次仅允许三份规划文档未提交变更；不得出现实现文件"
branch: "feat/DEV-OPS-002-cursor-orchestrator-subagents"  # 实施分支；计划 Commit 在 main，见 §13
created_at: "2026-08-06 15:50 UTC"
updated_at: "2026-08-07 02:18 UTC"
approval_gates:
  planning_docs: "Round 2 复审通过；PLAN_APPROVED（BLOCKER 0 / MUST_FIX 0 / SHOULD_FIX 0）"
  implementation_plan: "status=approved；此时不得实施；不得创建 agents/permissions/orchestrate-task；不得改治理规则或既有五命令；下一步人工 docs(plan) 后再切 feat；/develop-task 前置通过前不得 in_progress"
```

## 2. 任务目标

建立一个长期使用的 **Memory System Orchestrator**：用户只需提供 `TASK_ID` 与任务目标，由 Orchestrator 按仓库状态机调用可复用的独立角色 Subagent，减少每个 DEV 任务手工新建多组聊天。

完成后应具备：

1. **一个**项目级 Orchestrator 入口（Slash Command），只负责：识别仓库/任务状态、选择并调用正确角色、收集结束标记、在门禁点暂停；**不得**亲自规划、开发、审查或批准。
2. **六个**项目级可复用 Subagent（Planner / Plan Reviewer / Developer / Code Reviewer / Commit Recorder / Release Operator），各自独立 prompt 与角色边界。
3. **受控**项目级权限配置，使 Release Operator 成为唯一候选 Git 写角色，并尽量收窄可自动运行的终端前缀；**明确** `permissions.json` 非安全边界，真实门禁为运行时状态、路径白名单、命令解析与退出码检查（见 §2.6）。
4. **强制**静态契约测试覆盖：角色文件存在性、frontmatter 最小字段、结束标记、角色隔离、Orchestrator fail-closed 与禁止冒充、Release Operator 退出码/事实核对、危险 Git 操作禁止串、既有五命令契约不退化。
5. **受监督**低风险 E2E 冒烟（§9 全流程；契约-only 不计）；Subagent 无法调用时**安全降级**（停止；主 Agent 不得冒充角色）。
6. **分阶段**上线：本任务仅「受控自主」（含 push / 创建 PR）；**不**授权自动 Merge、不删除分支；Phase B **不得**在 DEV-002 之前安排。

### 2.1 完整状态机（与仓库统一；Orchestrator 必须遵守）

```text
planned
→ PLAN_APPROVED          # 仅独立 Plan Reviewer 会话输出；Orchestrator 不得伪造
→ approved               # 人工确认 PLAN_APPROVED 后回写；此时不得实施
→ 人工 docs(plan)        # 在 main 提交计划文档；仍不得实施
→ 创建 feat 分支         # 从 main 创建实施分支；仍不得编码
→ in_progress            # 仅 Developer 角色开始且前置检查通过后
→ implemented
→ tested
→ CODE_REVIEW_APPROVED   # 仅独立 Code Reviewer 会话输出；Orchestrator 不得伪造
→ reviewed               # 人工确认 CODE_REVIEW_APPROVED 后回写
→ Release Operator commit/push/create PR
→ committed              # Release Operator 在门禁满足后执行已批准的 commit/push/PR；回写真实 Hash/PR
→ 人工 Merge             # 人工 Merge PR + 分支清理 + 最终 docs(status)
→ completed
→ 立即进入 DEV-002       # next_action 必须为 DEV-002 业务规划/实施；不得插入其他任务
```

强制澄清：

1. Orchestrator **不得**输出 `PLAN_APPROVED` / `CODE_REVIEW_APPROVED` 或自行把状态标为 approved/reviewed/committed/completed。
2. Plan Reviewer 与 Code Reviewer 必须与被审角色隔离（独立 Subagent；独立上下文）。
3. `approved` **不等于**允许编码；须完成人工 `docs(plan)` 与创建 feat 分支后，Developer Subagent 在前置通过后才可将状态切到 `in_progress`。
4. Commit Recorder **只**做提交前核对与 Conventional Commit **草稿**；**不**执行 Git 写。
5. Release Operator 是**唯一**候选 Git 写角色；不得审查、批准或绕过门禁。
6. 第一阶段仍由**人工**执行：确认 `PLAN_APPROVED`；Merge Pull Request；删除本地/远程功能分支；高风险或范围异常时的最终决策。
7. **DEV-OPS-002 达到 `completed` 后**：`progress.md` 的 `next_action` **必须**立即指向 DEV-002 业务规划/实施；**不得**在 DEV-002 之前安排 Phase B、DEV-OPS-003 或其他工作流优化任务；本任务价值通过随后推进 DEV-002 验证；非阻塞改进仅记入 backlog，不得打断 DEV-002。

### 2.2 已确认的 Cursor 官方能力边界（本计划唯一产品依据）

下列事实以官方文档为准（核查日期含 2026-08-06 初稿与 2026-08-07 Planner 复核）。**未列入本表的路径/字段/API 一律视为未证实，记入 Open Issues，不得猜测实施。**

| 主题 | 官方依据 | 已确认事实 |
|---|---|---|
| 项目级 Subagent 路径 | [Subagents](https://cursor.com/docs/subagents) | 项目级：`.cursor/agents/`（兼容器 `.claude/agents/` / `.codex/agents/`）；用户级：`~/.cursor/agents/` 等。同名时项目优先；`.cursor/` 优于 `.claude/` / `.codex/` |
| 文件格式 | 同上 | Markdown + YAML frontmatter + prompt 正文 |
| Frontmatter 字段 | 同上 Configuration fields 表 | 已文档化：`name`、`description`、`model`、`readonly`、`is_background`。默认：`model=inherit`，`readonly=false`，`is_background=false` |
| 独立 prompt / model | 同上 | 支持独立 prompt 正文与 `model`（`inherit` 或具体 model ID；可带 `[effort=…]` 等参数括号语法） |
| 工具权限字段 | 同上 FAQ「Can I use MCP tools…」 | **未**在官方 Configuration fields 中提供 `tools:` 白名单字段。文档写明 Subagent **继承父 Agent 全部工具**（含 MCP；Cloud Subagent 例外） |
| `readonly` | 同上 | `readonly: true` → 限制写权限（无文件编辑、无会改变状态的 shell） |
| 发现与调用 | 同上 | 父 Agent 可按 `description` 自动委派；可用 `/name` 显式调用；也可自然语言点名。并行时父 Agent 一次发多个 Task tool calls |
| 同步 / 异步 | 同上 Foreground vs background | Foreground：阻塞至完成并立即返回结果。Background：立即返回；输出/状态可写到 `~/.cursor/subagents/`；可 resume（需 agent ID） |
| 嵌套 | 同上 FAQ | Cursor 2.5+ 允许有限嵌套：主 Agent 与其直接 Subagent 可再启动 Subagent；**由 Subagent 启动的 Subagent 不能再启动更深一层**。还受 Task 工具可用性、hooks/tool policy 约束 |
| 等待与结果 | 同上 | Foreground 阻塞并返回最终消息；失败时向父 Agent 返回 error status；可 resume |
| 官方 Orchestrator 模式叙述 | 同上 Common patterns | 文档描述父 Agent 顺序协调多个 specialist（Planner→Implementer→Verifier）；**这是使用模式，不是单独产品引擎 API** |
| 项目级权限（IDE） | [permissions.json](https://cursor.com/docs/reference/permissions.md) | `<workspace>/.cursor/permissions.json` 与 `~/.cursor/permissions.json`；字段：`mcpAllowlist`、`terminalAllowlist`、`autoRun`；定义后**替换**对应 IDE allowlist；两文件数组合并；支持 JSONC |
| Allow / Deny（IDE） | 同上 Notes | IDE `permissions.json` **只有 allowlist + autoRun 导向**；**无**与 CLI 对等的硬 `deny` 数组。文档明确 allowlist/`autoRun` **不是安全边界** |
| CLI 权限 | [CLI Permissions](https://cursor.com/docs/cli/reference/permissions.md) | CLI 权限系统**独立**；可用 `permissions.allow` / `permissions.deny`（deny 优先）。项目文件路径以 CLI 文档为准（常见为 `.cursor/cli.json`；若实施时与文档不一致须停止并 Amendment，不得猜测） |
| 终端匹配语义 | IDE permissions | IDE `terminalAllowlist` 为**大小写敏感前缀**匹配（例：`git` 匹配一切 `git ...`；`git push` 匹配以 `git push` 开头的命令，**含**带危险旗标的变体风险） |
| Git / GitHub 确定性接口 | 非 Cursor 专有发布 API | 本仓库 MVP 采用 shell：只读 `git status/diff/log/branch/rev-parse`；受控 `git add` / `git commit` / `git push`（无 force）；`gh pr create` / `gh pr view` 查询。**不**发明未证实的 Cursor 内置 Merge API |
| UI / CLI / SDK 适合本 MVP | Subagents + Commands（仓库已有）+ permissions | **本任务 MVP 主路径**：Cursor 编辑器 Agent + 项目 Slash Command 作为 Orchestrator 入口 + 项目 Subagents。CLI 可作为并行验证面，不得假设与 IDE 完全同一行为。Cursor SDK 编程编排**不**纳入本任务交付 |

**明确未证实（不得在实现中当作已支持 API）**：

- Subagent frontmatter 的 `tools:` / 精细 per-agent tool allowlist（官方表未列）
- IDE `permissions.json` 硬 deny 列表
- Orchestrator「产品级」状态机引擎或自动链式切换 API（相对 DEV-OPS-001 的 OI-OPS-002，本任务用**流程约定 + 结束标记解析**，仍非产品 API）
- 未在官方 Subagents 文档确认的额外 frontmatter 键、隐藏参数变量替换、或保证解析结束标记的结构化协议
- 自动 Merge PR、自动删分支的官方一键能力作为本仓库默认门禁替代

### 2.3 任务编号 / 状态解析（沿用 DEV-OPS-001 流程约定；禁止假设产品参数）

```text
1) 若同一条用户消息在选择 /orchestrate-task 之后仍包含显式字段，则优先采用：
   - TASK_ID: <id>
   - TASK_GOAL: <目标文本>（或「任务目标：」）
   - TASK_PLAN: <相对仓库根的路径>（可选）
   - BRANCH: <分支名>（可选；仍须用只读 git 核对）
2) 否则读取 02_开发管理/progress.md 顶部 YAML：
   - current_task / current_plan_file / current_branch / current_task_status
3) 用只读 git 核对：git branch --show-current；git status --short；git log --oneline -10
4) 若缺失、冲突或与 Task Plan 头信息不一致：停止；列出冲突；不得猜测；不得改业务代码
```

说明：此为**流程约定**，不是已证实的产品参数 API（延续 OI-OPS-001）。

### 2.4 Orchestrator 运行时序（受控自主；含人工暂停点）

```text
用户: /orchestrate-task + TASK_ID + 目标
  → Orchestrator 只读解析状态
  → 按需 Foreground 调用一个角色 Subagent（禁止并行调用互相冲突的审查对）
  → 收集该角色结束标记
  → 若标记为暂停门禁或失败：停止并报告，等待人工
  → 若可继续：再调用下一角色
  → 永不在同一上下文中「自己审自己」
```

建议状态 → 角色映射（实现时写入 Orchestrator 正文；可测字符串）：

| 当前状态 / 条件 | 调用角色 | 期望结束标记 | 随后 |
|---|---|---|---|
| 无计划或需规划 | Planner | `READY_FOR_PLAN_REVIEW` | 可接着调 Plan Reviewer，或暂停待人工 |
| 计划待审 | Plan Reviewer | `PLAN_APPROVED` / `PLAN_REJECTED` | **人工确认** `PLAN_APPROVED` 后才回写 `approved` |
| `approved` 且实施前置未满足 | （不调用 Developer） | — | 提示人工 `docs(plan)` / 建分支等 |
| `approved` 且分支/工作区前置满足 | Developer | `READY_FOR_CODE_REVIEW` | 调 Code Reviewer |
| 实现待审 | Code Reviewer | `CODE_REVIEW_APPROVED` / `CODE_REVIEW_REJECTED` | 通过则调 Commit Recorder |
| 待提交核对 | Commit Recorder | `READY_FOR_HUMAN_COMMIT` | 门禁满足后可调 Release Operator |
| 待发布（已批准草稿 + 审查通过） | Release Operator | `RELEASE_COMPLETED` / `RELEASE_OPERATOR_FAILED` | **暂停**：人工 Merge / 删分支 |
| 任一角色失败/拒绝/无法调用 | — | — | **安全停止**；Orchestrator 不得冒充该角色补做 |

### 2.4.1 Orchestrator 失败即停（fail-closed；契约可 grep）

Orchestrator 正文、契约测试与验收标准**必须**包含下列行为；任一触发即输出 `ORCHESTRATOR_HALTED` 并**立即**停止，**不得**猜测阶段已通过、**不得**由主 Agent 冒充失败 Subagent、**不得**自动调用下一角色：

| 条件 | 行为 |
|---|---|
| 缺少期望结束标记 | 立即停止 |
| 成功与失败标记同时出现 | 立即停止 |
| Subagent 超时 / 异常 / 非零退出 | 立即停止 |
| 返回内容无法解析 | 立即停止 |
| 角色返回拒绝或失败标记 | 立即停止；不自动调下一角色 |

**Orchestrator 最小必需子串（`test_cursor_orchestrator_contract.py` 须 grep）**：

```text
不得猜测
不得冒充
ORCHESTRATOR_HALTED
缺少.*结束标记
成功.*失败.*同时
非零退出
无法解析
不得自动调用下一角色
```

### 2.4.2 Orchestrator 可写 vs 禁止自写 progress 字段

Orchestrator **仅可**回写下列编排字段（`02_开发管理/progress.md` 或 Task Plan 执行记录中的编排态）：

| 允许 Orchestrator 记录 | 禁止 Orchestrator 自行写入 |
|---|---|
| `current_stage`（当前编排阶段） | `approved`（仅人工确认 `PLAN_APPROVED` 后） |
| `last_role_result`（上一角色结束标记摘要） | `reviewed`（仅 `CODE_REVIEW_APPROVED` 门禁后） |
| `blocking_reason`（暂停/失败原因） | `committed`（仅 Release Operator 真实 Git/PR 事实后） |
| | `completed`（仅人工 Merge + 最终 docs 后） |

`approved` / `reviewed` / `committed` / `completed` **只能**来自对应角色门禁与真实 Git/PR 只读事实核对，Orchestrator 不得自写这些状态跃迁。

### 2.5 与 DEV-OPS-001 五命令的关系

- **保留**既有五个 Slash Commands，作为人工单角色入口与降级路径。
- Orchestrator 是新增入口；**默认**通过 Subagent 调用角色，而不是改写五个命令为超级命令。
- 既有 `tests/unit/test_cursor_commands_contract.py` 当前断言 `.cursor/commands/` **恰好五文件**；本任务新增 `orchestrate-task.md` 时**必须**同步修订该测试白名单（见 §5.3），否则契约必红。不得删除五命令断言语义，只允许扩展「第六个 Orchestrator 命令」的存在性与隔离断言。

### 2.6 Release Operator Git 写治理窄例外（正式实施时写入 §5.6 文件）

为在门禁满足后由 Release Operator 执行受控 commit/push/PR，本任务在实施阶段**允许**修订 §5.6 两个治理文件，增补下列**窄例外**（不得扩大）：

**谁可以写**：

- **仅** Release Operator Subagent 可执行 Git 写操作。

**何时可以写**（全部满足）：

1. 独立 Plan Reviewer 已输出 `PLAN_APPROVED` 且人工已确认 `approved`
2. 全部自动测试绿灯（`tested`）
3. 独立 Code Reviewer 已输出 `CODE_REVIEW_APPROVED` 且状态为 `reviewed`
4. P0/P1 = 0
5. Commit Recorder 已输出 `READY_FOR_HUMAN_COMMIT` 与经确认的 commit message 草稿

**写到哪里**：

- **仅**当前非 `main` 的功能分支（本 Task Plan 规定的 `implementation_branch`）
- **仅** Task Plan §5 白名单中的**精确路径**（`git add -- <exact whitelist paths>`）

**允许命令**（每条须单独执行并检查真实退出码）：

- `git add -- <exact whitelist paths>`
- `git commit`（message 必须来自已批准 Task Plan 或 Commit Recorder 草稿）
- `git push origin <current feature branch>`（禁止 force）
- `gh pr create`
- `gh pr view`（只读查询）

**永久禁止**（任何角色、任何阶段）：

- `git push --force`、`git push -f`
- `git reset --hard`、`git clean -fd`、`git branch -D`
- `git rebase`、`git merge`
- `gh pr merge`
- 直接向 `main` 提交实现 Commit
- 删除分支/标签

**安全边界声明**：

- `.cursor/permissions.json` **不是**安全边界；真实门禁为：运行时状态核对、路径白名单、`git`/`gh` 命令解析、以及**每条 shell 命令的真实退出码检查**。
- Release Operator **不得**从 stdout 或模型叙述假设成功；非零退出码 → 输出 `RELEASE_OPERATOR_FAILED` 并立即停止，不执行后续 git/PR 步骤。
- Commit Hash **必须**来自 `git rev-parse HEAD`；PR 编号/状态 **必须**来自 `gh pr view --json number,state,baseRefName,headRefName,url`。
- 全部命令退出码为 0 且只读事实核对通过后，**方可**输出成功标记 `RELEASE_COMPLETED`。

**Amendment 001 说明**：上述例外内容**仅**记入本 Task Plan；治理文件（§5.6）**尚未**在本规划轮次修改。

## 3. 非目标

- 修改任何业务代码、`src/**`、`scripts/**`（本任务工程实现范围外）、`pyproject.toml` 依赖集合、`uv.lock`（除非测试新增文件无需改锁；本任务预期不改）。
- 修改技术规格正文 `01_技术规格/**`。
- 把六个角色合并为一个超级 Agent / 单个超级 Subagent。
- Orchestrator 亲自规划、开发、审查、批准。
- Release Operator 审查、批准、Merge PR、删除分支、`git push --force`、`git reset --hard`、`git clean -fd`、`git branch -D`。
- 未经门禁自动 Merge；绕过测试或 Review。
- Agent 审查自己的产出；Agent 自己批准自己。
- 读取 `.env*` 或任何 Secret；提交真实用户数据 / 模型缓存 / 数据库数据。
- 超出当前 Task Plan 白名单的 `git add`；在真实 Hash 产生前猜测回写。
- 直接向 `main` 写实现 Commit。
- 创建 `.cursor/skills/`（本任务不把 Orchestrator 做成 Skill；见 OI-OPS-003 / OI-OPS-010）。
- 配置 Custom Modes。
- 修改 `03_AI_Prompts/**` 中除白名单 `00_全局开发规则.md` 以外的源文件（双源策略见 OI-OPS-004）。
- 修改 `.cursor/rules/**` 中除白名单 `00-memory-system-governance.mdc` 以外的规则文件。
- 使用 Cursor SDK 编写外部编排服务。
- 扩大 Merge 权限或「全自动发布」（属 Phase B 评估；**不得**在 DEV-002 之前安排）。
- 在本规划轮次创建 Subagent、Orchestrator、权限文件或执行任何 Git 写。
- **Phase A 非目标**：多任务并行编排调度；复杂嵌套 Subagent；六个角色 Subagent **不得**再 spawn 更深一层角色 Agent（与 OI-OPS-009 一致）。

**DEV-002 边界澄清**：

- **DEV-OPS-002 实施期间**：不得开始或修改 DEV-002（或任何 Phase 0+ 业务任务）的实施内容 / Task Plan 业务范围。
- **DEV-OPS-002 达到 `completed` 后**：**必须**立即进入 DEV-002 业务规划/实施；不得永久搁置 DEV-002。

## 4. 当前代码状态

- 已存在：
  - DEV-OPS-001：`.cursor/commands/{plan-task,review-plan,develop-task,review-code,close-task}.md`
  - `tests/unit/test_cursor_commands_contract.py`（恰好五命令 + 角色隔离）
  - `.cursor/rules/00-memory-system-governance.mdc`
  - `03_AI_Prompts/` 全套角色提示词
  - 基线 Commit：`5f34ccbcb7a052131dbeedd17c68dbf6dc30c52d`（`docs(status): complete DEV-OPS-001 after PR merge`）；`main` 与 `origin/main` 同步
- 可复用：五命令正文中的角色约束、结束标记、状态机；`03_AI_Prompts/02–08`；官方 Subagents Orchestrator 使用模式叙述（非产品引擎）
- 当前缺失：
  - `.cursor/agents/`（不存在）
  - Orchestrator 入口命令
  - `.cursor/permissions.json` / 项目 CLI 权限文件
  - Orchestrator / Subagent / Release 契约测试
- 与技术规格不一致之处：无（本任务不改规格 Contract）
- 前置任务检查：DEV-OPS-001 = `completed`；DEV-001 = `completed`
- 规划会话工作区说明：相对基线，本轮**仅允许**未提交的三份规划文档变更（Task Plan / master_plan / progress）；**不得**出现 agents/权限/业务实现文件。实施前工作区须回到「仅计划 Commit 已落盘 / 或干净 feat 分支」状态。

## 5. 文件白名单（本任务允许创建/修改的全部路径）

实施时**仅允许**下列路径。禁止通配为“整个 `.cursor/`”。

### 5.1 Orchestrator 入口（实施阶段创建；本规划轮次不得创建）

| 路径 | 唯一角色 | 结束标记要求 |
|---|---|---|
| `.cursor/commands/orchestrate-task.md` | Orchestrator | 阶段暂停/完成时输出明确标记；推荐成功暂停用 `ORCHESTRATOR_PAUSED_FOR_HUMAN`；安全失败用 `ORCHESTRATOR_HALTED`；**禁止**输出 `PLAN_APPROVED` / `CODE_REVIEW_APPROVED` 作为自身批准 |

### 5.2 Subagent 角色文件（实施阶段创建；本规划轮次不得创建）

| 路径 | 唯一角色 | `readonly` 建议 | 结束标记（须在正文强制） |
|---|---|---|---|
| `.cursor/agents/planner.md` | Planner | `false`（需写 Task Plan / progress 规划态） | `READY_FOR_PLAN_REVIEW` |
| `.cursor/agents/plan-reviewer.md` | Plan Reviewer | `true` | `PLAN_APPROVED` / `PLAN_REJECTED` |
| `.cursor/agents/developer.md` | Developer | `false` | `READY_FOR_CODE_REVIEW` |
| `.cursor/agents/code-reviewer.md` | Code Reviewer | `true` | `CODE_REVIEW_APPROVED` / `CODE_REVIEW_REJECTED` |
| `.cursor/agents/commit-recorder.md` | Commit Recorder | `true`（默认只读核对；若计划允许仅在人工提交后回写真实 Hash，须在正文写明且仍禁止 Git 写） | `READY_FOR_HUMAN_COMMIT` |
| `.cursor/agents/release-operator.md` | Release Operator | `false` | 成功：`RELEASE_COMPLETED`（须在全部 shell 退出码为 0 且只读事实核对后输出；正文必须要求附带真实 Commit Hash / PR 编号与状态）；失败：`RELEASE_OPERATOR_FAILED` |

每个 Subagent 文件必须：

1. 含 YAML frontmatter，至少显式设置：`name`、`description`（含何时由 Orchestrator 调用的说明）、`model`（本任务默认 `inherit`，除非 Amendment 另定）、`readonly`（按上表）、`is_background: false`（本任务第一阶段强制 Foreground，便于 Orchestrator 等待结束标记）。
2. Prompt 正文内化对应 `03_AI_Prompts` / 既有命令约束；声明「唯一角色 = …」；禁止切换为其他角色。
3. Plan Reviewer / Code Reviewer 不得修改业务实现文件（与 `readonly: true` 一致）。
4. Release Operator 正文必须列出允许的 Git/GitHub 操作白名单与禁止操作黑名单（见 §7 Step 4）。

### 5.3 权限配置（实施阶段创建；本规划轮次不得创建）

| 路径 | 目的 |
|---|---|
| `.cursor/permissions.json` | 项目级 IDE 权限：收窄 `terminalAllowlist` 前缀；用 `autoRun.block_instructions` 导向拦截危险 Git / 读 Secret（**导向非硬强制**，须在风险中写明） |
| `.cursor/cli.json`（或 CLI 文档确认的项目级权限文件名） | 项目级 CLI 权限：使用官方 `permissions.allow` / `permissions.deny`；**deny** 至少覆盖 `Read(.env*)`、危险 shell；若实施时官方路径/文件名与此不符 → **停止并 Amendment**，不得猜测 |

权限文件内容必须在 Task Plan 实施步骤中给出**可审查的拟稿原则**（见 §7）；不得在未批准前落盘。

### 5.4 契约测试（强制）

| 路径 | 说明 |
|---|---|
| `tests/unit/test_cursor_orchestrator_contract.py` | **必须新建**：断言 §5.1–5.2 文件存在；frontmatter 关键字段；六角色「唯一角色」互斥；Orchestrator 禁止冒充批准标记；Orchestrator §2.4.1 fail-closed 子串；Release Operator 禁止危险 Git 子串 + §7 Step 4 退出码/事实核对子串；permissions/cli 文件存在且含关键拒绝/收窄策略子串 |
| `tests/unit/test_cursor_commands_contract.py` | **允许修改**：将 commands 目录白名单从「恰好五文件」扩展为「五角色命令 + `orchestrate-task.md`」；为 Orchestrator 增加隔离断言；**不得**削弱原五命令的角色/结束标记断言 |

### 5.5 开发管理文档（实施与状态回写允许）

| 路径 | 允许操作 |
|---|---|
| `02_开发管理/tasks/DEV-OPS-002-cursor-orchestrator-subagents-release.md` | 状态机与执行记录回写；Amendment |
| `02_开发管理/master_plan.md` | 仅本任务登记/状态与变更记录追加 |
| `02_开发管理/progress.md` | 当前任务/状态/next_action 等回写；不得抹去已完成任务表行 |

### 5.6 治理例外文件（正式实施阶段修订；本规划轮次不得修改）

下列路径**仅**在实施阶段、且为 Release Operator Git 写治理例外所必需时允许修订；修订范围须限于 §2.6 窄例外条款：

| 路径 | 允许操作 |
|---|---|
| `.cursor/rules/00-memory-system-governance.mdc` | 增补 Release Operator 窄例外条款（见 §2.6） |
| `03_AI_Prompts/00_全局开发规则.md` | 与治理规则对齐的 Release Operator Git 写例外说明 |

**说明**：本规划轮次（Amendment 001）仅在 Task Plan 中记录例外内容；**尚未**修改上述治理文件。

## 6. 文件黑名单（禁止本任务创建或修改）

| 路径 / 模式 | 原因 |
|---|---|
| `src/**`、`scripts/**` | 业务/工程实现 |
| `configs/**`、`.env`、`.env.*`、`.env.example` | Secret / DEV-002 |
| `Dockerfile`、`compose*.yaml`、`versions.*` | DEV-003 |
| `01_技术规格/**` | 禁止改规格正文 |
| `03_AI_Prompts/**` | 默认不改；**例外**：白名单 `03_AI_Prompts/00_全局开发规则.md`（见 §5.6） |
| `.cursor/rules/**` | 默认不改；**例外**：白名单 `.cursor/rules/00-memory-system-governance.mdc`（见 §5.6 / §2.6） |
| `.cursor/skills/**`、`.agents/skills/**` | 非本任务范围 |
| 既有五命令文件正文 | **禁止修改** `.cursor/commands/{plan-task,review-plan,develop-task,review-code,close-task}.md`；仅允许**新增** `orchestrate-task.md` |
| Custom Modes | 非目标 |
| `~/.cursor/**` 用户级配置作为仓库交付物 | 不提交用户主目录配置 |
| DEV-001 既有测试语义/断言 | 禁止修改 `test_entrypoints_import.py` / `test_dependency_contract.py` |
| DEV-002+ 业务 Task Plan 实施内容 | 非目标（**completed 后立即进入 DEV-002 规划/实施**） |
| 任何 Git hooks 自动改写历史 / 自动 merge 脚本 | 禁止绕过门禁 |
| 直接修改 `main` 上的业务实现文件（本任务交付物除外的路径） | 禁止 |

## 7. 实现方案

### Step 0 — 状态回写（强制，贯穿全程）

| 触发条件 | 状态 |
|---|---|
| 本规划轮次 / 未获批 | `planned`（历史） |
| 独立 Plan Reviewer 输出 `PLAN_APPROVED` | → `approved`（回写三文档；**不得实施**；**当前**） |
| `/develop-task` 或 Orchestrator 调用 Developer 且前置通过 | `approved` → `in_progress` |
| 白名单文件已落地 | `implemented` |
| 契约测试与 ruff/mypy 通过 | `tested` |
| 独立 Code Review 通过 | `reviewed` |
| 人工或 Release Operator 完成实现 Commit + PR | `committed` |
| 人工 Merge + 最终治理 | `completed` |
| `completed` 后 | `progress.md` 的 `next_action` **必须**指向 DEV-002 业务规划/实施 |

**禁止**在 `planned`/`approved` 阶段创建 `.cursor/agents/`、Orchestrator 或权限文件。

### Step 1 — 创建六个 Subagent 文件

- 创建目录 `.cursor/agents/`。
- 仅创建 §5.2 六个文件。
- 每个文件 frontmatter + 角色正文；内化必读文件、前置检查、可写范围、阶段验证、结束标记。
- Planner ↔ Plan Reviewer、Developer ↔ Code Reviewer 不得合并。
- `is_background: false`（第一阶段）。
- Plan Reviewer / Code Reviewer / Commit Recorder：`readonly: true`。

### Step 2 — 创建 Orchestrator 入口命令

- 创建 `.cursor/commands/orchestrate-task.md`。
- 六段结构与 DEV-OPS-001 对齐：角色 / 必读文件 / 前置只读检查 / 允许修改范围 / 阶段验证 / 结束标记。
- 明确：只编排；用 Foreground Subagent；解析结束标记；门禁暂停；降级停止；**fail-closed**（见 §2.4.1）。
- 允许修改范围：**仅** §2.4.2 所列编排字段以及调用 Subagent；不得直接改业务白名单外文件；不得自行批准或自写 `approved`/`reviewed`/`committed`/`completed`。
- 必须包含降级条款：若无法发现/调用目标 Subagent，输出 `ORCHESTRATOR_HALTED` 并停止；**禁止**主会话改扮 Planner/Reviewer/Developer/Release Operator。
- 必须包含 §2.4.1 最小必需子串，供契约测试 grep。

### Step 3 — 项目权限配置

`.cursor/permissions.json` 拟稿原则（实施时落盘；审查对照）：

1. **不要**使用裸前缀 `"git"`（过宽，等于放行一切 git 子命令）。
2. `terminalAllowlist` 仅列只读与发布所需的最小前缀集合（示例级原则，实施时写成具体数组并经审查）：如 `git status`、`git diff`、`git log`、`git branch`、`git rev-parse`、`git add`、`git commit`、`git push`、`gh`、以及测试门禁常用的 `uv`。
3. `autoRun.block_instructions` 必须用自然语言导向拦截：`git push --force` / `git reset --hard` / `git clean -fd` / `git branch -D` / 读 `.env*` / merge 到 main / 删除远程分支等。
4. 文档注释（JSONC 允许）中写明：此文件**不是**安全边界；真实门禁为运行时状态、路径白名单、命令解析与退出码检查；Release Operator prompt 黑名单与人工 Merge 仍是补充防线。

`.cursor/cli.json` 拟稿原则：

1. `permissions.deny` 包含 `Read(.env*)` 以及尽可能匹配的危险 Shell 模式。
2. `permissions.allow` 仅列 MVP 所需只读/测试/受控 git/gh。
3. 若官方 CLI 匹配无法可靠区分 `git push` 与 `git push --force`，必须在 Open Issue 记录，并在 Release Operator 正文 + 人工确认流程中补偿（见 OI-OPS-011）。

### Step 4 — Release Operator 行为合同（写入 subagent 正文）

**执行原则（强制）**：

1. **每条** shell 命令须**单独**执行，并检查**真实退出码**。
2. 任一命令非零退出码 → 立即输出 `RELEASE_OPERATOR_FAILED` 并停止；**不得**执行后续 git/PR 步骤。
3. **不得**从 stdout 或模型叙述假设成功。
4. 成功标记 `RELEASE_COMPLETED` **仅**在：全部相关命令退出码为 0 **且**只读事实核对通过后输出。
5. Commit Hash **必须**来自 `git rev-parse HEAD`。
6. PR 编号/状态 **必须**来自 `gh pr view --json number,state,baseRefName,headRefName,url`。
7. **不得**在 Hash/PR 产生前猜测或回写。

**Release Operator 最小必需子串（`test_cursor_orchestrator_contract.py` 须 grep）**：

```text
检查退出码
非零立即停止
不得假设成功
不得猜测
git rev-parse HEAD
gh pr view --json
RELEASE_OPERATOR_FAILED
RELEASE_COMPLETED
```

**允许（门禁全部满足后）**：

- 对**当前 Task Plan 已批准白名单**执行 `git add -- <exact whitelist paths>`（路径必须逐文件对照白名单）
- 使用 Commit Recorder 已给出且经门禁确认的 message 执行 `git commit`
- `git push origin <current feature branch>`（禁止 force）
- `gh pr create`（base 为 `main`；正文含 Task ID）
- `gh pr view --json number,state,baseRefName,headRefName,url` / `git rev-parse HEAD` / `git log -1` 查询并回传**真实** Commit Hash、PR 编号与状态
- 仅在 Hash/PR **真实存在后**回写 Task Plan / progress 的 Git 记录字段

**禁止**：

- `git push --force` / `--force-with-lease`（除非未来 Amendment + 人工书面授权；本任务默认禁止）
- `git reset --hard`、`git clean -fd`、`git branch -D`、删除远程分支
- `git merge`、`gh pr merge`、直接推 `main`
- 审查或批准（不得输出 `PLAN_APPROVED` / `CODE_REVIEW_APPROVED`）
- 跳过测试失败或 Review 未通过
- 读取 `.env*` / Secret
- 白名单外 `git add`
- Hash 产生前猜测回写

**门禁前置（Release Operator 开始前 Orchestrator 必须核对）**：

1. 独立 Code Review 结论为 `CODE_REVIEW_APPROVED`
2. Commit Recorder 已输出 `READY_FOR_HUMAN_COMMIT` 与草稿消息
3. 当前分支为计划实施分支（非 `main`）
4. `git status` / `git diff` 仅含白名单路径
5. 相关自动测试在 Developer 阶段已通过（按 Task Plan 记录；必要时只读复跑）

### Step 5 — 契约测试落地

- 新建 `tests/unit/test_cursor_orchestrator_contract.py`
- 修订 `tests/unit/test_cursor_commands_contract.py`（扩展第六命令）
- 不得新增第三方依赖

### Step 6 — 自动验证与人工冒烟

自动：

```text
uv run pytest tests/unit/test_cursor_commands_contract.py tests/unit/test_cursor_orchestrator_contract.py
uv run pytest tests/unit
uv run ruff check .
uv run mypy src tests
```

人工（不可伪造；记入执行记录）：

1. `/` 菜单可见 `orchestrate-task`
2. `.cursor/agents/` 六文件可被 Agent/Task 发现（按官方：检查目录；显式 `/planner` 等或 Orchestrator 委派）
3. Orchestrator 在缺少 Subagent 时（可在临时分支人为改名验证）安全停止且不冒充
4. Plan Reviewer / Code Reviewer 只读行为冒烟（不写业务文件）
5. Release Operator **不**在冒烟中对 `main` 执行真实推送；须使用 §9 受监督 E2E 流程（专用低风险 feat 分支 + 人工确认 + PR create 后停止）

### Step 7 — 降级与分期策略（写入 Orchestrator / README 式注释于命令正文）

**降级**：

1. Subagent 目录缺失 / 无法调用 / 返回非预期 → `ORCHESTRATOR_HALTED`
2. 回退路径：人工继续使用 DEV-OPS-001 五命令（`/plan-task`、`/review-plan`、`/develop-task`、`/review-code`、`/close-task`）；**禁止** Orchestrator 主会话顶替角色
3. 权限文件未生效（Run Mode 未开等）→ 视为高风险；Release Operator 必须停止并要求人工执行 Git

**分期**：

| 阶段 | 范围 | 本任务 |
|---|---|---|
| Phase A 受控自主 | 编排 + Subagents + 受控 commit/push/PR；**不含**多任务并行调度、复杂嵌套 Subagent、角色再 spawn 更深 Agent | **本任务交付** |
| Phase B 评估 | 是否扩大 Merge 权限、分支清理自动化 | **非本任务**；**不得在 DEV-002 之前安排**；DEV-002 启动后仅可记入 backlog |

## 8. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用经典 DB 事务 | 以 Git Commit / PR 为发布原子单位；Orchestrator 分段暂停 |
| 幂等 | 部分适用 | 重复调用 Orchestrator 必须先读 `progress.md` 状态，避免重复 commit；Release Operator 推送前检查 remote 状态 |
| 并发 | 高风险 | 禁止并行跑两个 Orchestrator 写同一任务；禁止并行 Planner+Developer；审查对不得并行自我覆盖 |
| 版本冲突 | 适用 Git | 以分支 + PR 为准；禁止 force push |
| 用户隔离 | 不适用多租户业务 | 适用「角色隔离」：审查者独立上下文 |
| 部分失败 | 适用 | 任一角色失败即停止；不自动跳过门禁 |
| 进程异常恢复 | 部分适用 | 依赖 progress/Task Plan 状态与 Git 记录恢复；Background Subagent 非本阶段默认 |

## 9. 测试计划

### Unit / 静态契约 Test

| 场景 | 预期 |
|---|---|
| agents 六文件存在且无额外杂文件（或仅允许明确白名单） | pass |
| 每个 agent frontmatter 含 name/description/model/readonly/is_background | pass |
| 六角色「唯一角色 =」互斥 | pass |
| Orchestrator 含禁止自行批准与禁止冒充条款 | pass |
| Orchestrator 含 §2.4.1 fail-closed 最小子串 | pass |
| Release Operator 含危险 Git 禁止子串与允许操作子串 | pass |
| Release Operator 含 §7 Step 4 退出码/事实核对最小子串 | pass |
| permissions.json / cli.json 存在且含关键收窄/deny 子串 | pass |
| commands 目录 = 原五命令 + orchestrate-task.md | pass |
| 原五命令结束标记与角色断言不退化 | pass |

### Contract Test（业务 API）

| 场景 | 预期 |
|---|---|
| 不适用 | 本任务无业务 HTTP/API Contract |

### Integration Test

| 场景 | 预期 |
|---|---|
| 不适用真实基础设施 | 不启动 Compose/DB |

### E2E Test（受监督低风险冒烟；强制）

**不得**将仅契约 grep 或只读 replay 计为完整 E2E。完整 E2E **必须**覆盖下列链路（人工监督一次）：

```text
Orchestrator → Planner → Plan Reviewer → Developer → Code Reviewer
→ Commit Recorder → Release Operator → git commit → push feat 分支 → gh pr create
```

| 要求 | 说明 |
|---|---|
| 专用低风险测试任务 / feat 分支 | 使用独立测试 Task 与精确白名单文件；**不在 main** |
| 无自动 Merge | PR create 后停止；人工 inspect/close/handle |
| 人工确认 | Release Operator 执行前须人工确认一次 |
| 失败即停 | 任一环节失败 → 立即 halt；阻塞 `tested`/`reviewed`/`completed` |
| 降级 | E2E 不可行时回退 DEV-OPS-001 五 Slash Commands |
| 阻塞门禁 | E2E 冒烟未通过 → **不得**标 `tested`/`reviewed`/`completed` |

| 场景 | 预期 |
|---|---|
| 完整受监督 E2E（见上） | pass（人工记录）；PR 创建后停止 |
| 契约-only / 只读 replay | **不计**完整 E2E |
| E2E 中途失败 | halt；不得伪造后续阶段 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 静态断言：Orchestrator 不得同时声明为 Plan Reviewer | pass |
| 静态断言：Orchestrator fail-closed 子串（§2.4.1） | pass |
| 静态断言：Release Operator 退出码/事实核对子串（§7 Step 4） | pass |
| 人工：Subagent 缺失时 Orchestrator halt | 记录结果；不得伪造 |
| 人工：未获 CODE_REVIEW_APPROVED 时不得触发 Release Operator | 记录结果 |
| 人工：受监督 E2E 完整链路（§9） | 记录结果；失败则阻塞 completed |

### 人工 UI 冒烟

| 场景 | 预期 |
|---|---|
| `/orchestrate-task` 可发现可加载 | pass（人工） |
| 显式调用某一 readonly reviewer subagent | 可启动且不改业务文件（人工） |
| 无法调用时的降级 | `ORCHESTRATOR_HALTED`（人工） |

## 10. 验收标准

- [ ] §5 白名单文件齐套（含 §5.6 治理例外文件，若实施阶段修订）；黑名单路径未被本任务越权修改
- [ ] 六个 Subagent 角色隔离（契约测试 + 正文「唯一角色」）；六角色不得 spawn 更深 Subagent
- [ ] Orchestrator 仅编排；契约断言禁止输出自我批准标记；含 §2.4.1 fail-closed 子串
- [ ] Orchestrator 仅写 §2.4.2 允许字段；不自写 approved/reviewed/committed/completed
- [ ] Release Operator 独享候选 Git 写；禁止危险操作条文存在且可测；含退出码检查与 `RELEASE_COMPLETED` 事实核对子串
- [ ] `permissions.json` 与 `cli.json` 已按 §7 原则落盘；明确非安全边界
- [ ] `uv run pytest tests/unit/test_cursor_orchestrator_contract.py` 通过
- [ ] `uv run pytest tests/unit/test_cursor_commands_contract.py` 通过（含第六命令扩展）
- [ ] `uv run pytest tests/unit` 通过（含 DEV-001 既有测试不退化）
- [ ] `uv run ruff check .` 通过
- [ ] `uv run mypy src tests` 通过
- [ ] 受监督 E2E 冒烟已记录（§9）；契约-only/只读 replay **不计**完整 E2E；未完成项如实标注
- [ ] DEV-OPS-002 实施期间未修改 DEV-002 业务内容；**completed 后 next_action 指向 DEV-002**
- [ ] 未改技术规格正文（治理例外文件 §5.6 仅限 §2.6 窄条款）
- [ ] Review 无 P0/P1
- [ ] 状态已按 Step 0 分阶段回写

## 11. 风险与阻塞项

### 11.1 风险

- IDE `permissions.json` 无硬 deny + 前缀匹配 → `git push` allow 可能覆盖 `git push --force`（依赖 prompt + autoRun 导向 + 人工；**非**硬安全边界）。
- Subagent 继承父工具 → Orchestrator 若拥有写权限，理论上被滥用；必须靠角色 prompt、readonly、人工门禁与 Code Review 多层约束。
- Commands / Skills 文档入口变化（官方 Commands 页现转向 Skills 叙述）可能导致长期双轨；本任务仍以仓库已验证的 `.cursor/commands/*.md` 为 Orchestrator 入口（见 OI-OPS-010）。
- 结束标记依赖自然语言遵守；无官方结构化协议保证（OI-OPS-008）。
- 旧 DEV-001 / DEV-OPS-001 多会话仅在新流程验收完成后由**人工**归档；本任务不自动清理历史会话。

### 11.2 Open Issues（未证实项；不得猜测实现）

#### OI-OPS-006 — Subagent 无官方 `tools:` 精细授权

```yaml
id: OI-OPS-006
status: open
blocks_implementation: false
source: "https://cursor.com/docs/subagents Configuration fields"
```

官方仅文档化 `readonly` 等字段，并写明继承父工具。本任务不得伪造 `tools:` 方案；用 readonly + prompt + 权限文件补偿。

#### OI-OPS-007 — IDE permissions 无硬 deny / 非安全边界

```yaml
id: OI-OPS-007
status: open
blocks_implementation: false
source: "https://cursor.com/docs/reference/permissions.md"
```

#### OI-OPS-008 — 结束标记解析无官方结构化协议

```yaml
id: OI-OPS-008
status: open
blocks_implementation: false
```

Foreground「返回最终消息」已确认；但「保证可机读提取最后一行标记」未证实。实现采用约定 + 契约测正文要求 + 人工冒烟；失败则 halt。

#### OI-OPS-009 — 嵌套 Subagent 与 Orchestrator 深度

```yaml
id: OI-OPS-009
status: open
blocks_implementation: false
```

官方限制两层有效派生。本任务要求 Orchestrator 为**父会话**直接启动角色 Subagent，角色不再启动子 Subagent（避免触达嵌套上限与策略阻断）。

#### OI-OPS-010 — Commands 与 Skills 入口演进

```yaml
id: OI-OPS-010
status: open
blocks_implementation: false
```

官方文档导航已强化 Skills；本任务仍使用 `.cursor/commands/orchestrate-task.md`（与 DEV-OPS-001 一致）。若团队决议迁移 Skills，另开任务；不在本任务创建 `.cursor/skills/`。

#### OI-OPS-011 — `git push` 前缀与 `--force` 区分能力

```yaml
id: OI-OPS-011
status: open
blocks_implementation: false
```

IDE allowlist 前缀语义下，允许 `git push` 是否足以排除 `git push --force` **不能**从官方文档得出否定保证。必须：Release Operator 黑名单 + autoRun block + CLI deny 尽力匹配 + 人工监督。

#### OI-OPS-012 — CLI 与 IDE 双权限面一致性

```yaml
id: OI-OPS-012
status: open
blocks_implementation: false
```

CLI 使用独立权限文件与 allow/deny 模型。本任务两者都提交，但不宣称行为完全等价；MVP 验收以编辑器路径为主。

#### OI-OPS-013 — 人工确认 `PLAN_APPROVED` 的产品级钩子

```yaml
id: OI-OPS-013
status: open
blocks_implementation: false
```

无官方「等待人类点击批准再继续」API 被本计划采用。实现为 Orchestrator 输出 `ORCHESTRATOR_PAUSED_FOR_HUMAN` 并结束本轮；人工确认后再次调用 `/orchestrate-task`。

延续未决（不改写编号语义）：OI-OPS-001–005 仍适用于五命令路径；本任务不关闭它们。

### 11.3 其他

- 设计文档冲突：无（非业务规格）
- 当前代码冲突：新增第六 command 与「恰好五文件」测试冲突 → 已纳入白名单修订
- 前置任务：DEV-OPS-001 completed（满足）
- API/Schema 变化：无

## 12. 分阶段上线、安全停止与旧会话归档

### 12.1 分阶段上线

| 阶段 | 范围 | 本任务 |
|---|---|---|
| Phase A 受控自主 | Orchestrator 入口 + 六角色 Subagent + IDE/CLI 权限收窄 + 契约测试 + 受控 commit/push/PR；不含多任务并行、嵌套 Subagent、角色再 spawn | **本任务交付** |
| Phase B 评估 | 是否授予受控 Merge、远程/本地分支清理自动化 | **非本任务**；**不得在 DEV-002 之前安排**；DEV-002 启动后非阻塞项仅记入 backlog |

### 12.2 安全停止与降级（Orchestrator 必须遵守）

1. **Fail-closed**（§2.4.1）：缺少期望结束标记、成功/失败标记同时出现、Subagent 超时/异常/非零退出、无法解析返回 → 输出 `ORCHESTRATOR_HALTED` 并**立即**停止；不得猜测阶段通过、不得冒充失败 Subagent、不得自动调下一角色。
2. 任一角色返回拒绝/失败标记，或无法发现/调用目标 Subagent → 输出 `ORCHESTRATOR_HALTED` 并停止。
3. 遇到人工门禁（`PLAN_APPROVED` 确认、Merge、删分支、范围异常）→ 输出 `ORCHESTRATOR_PAUSED_FOR_HUMAN` 并停止本轮。
4. 降级路径：人工继续使用 DEV-OPS-001 五个 Slash Commands；**禁止** Orchestrator 主会话顶替任一角色。
5. 权限文件未生效或 Run Mode 未开 → Release Operator **不得**执行 Git 写；改为要求人工执行。

### 12.3 旧 Agent 会话归档时机

1. **在本任务（DEV-OPS-002）验收完成（`completed`）之前**：保留旧的多会话手工流程与历史聊天，作为回退路径；Agent **不得**声称已归档或删除历史会话。
2. **验收完成之后**：由**人工**决定是否归档/关闭旧的 Planner/Reviewer/Developer 等多会话聊天；归档动作为人工操作，不纳入 Release Operator 权限。
3. DEV-OPS-001 五命令文件在归档后仍保留为降级入口，直到未来任务明确退役。

## 13. Git 计划

```yaml
implementation_branch: "feat/DEV-OPS-002-cursor-orchestrator-subagents"
expected_sequence:
  - "1. 独立 Plan Review"
  - "2. PLAN_APPROVED"
  - "3. 状态更新为 approved（Task Plan / master_plan / progress；不得实施）"
  - "4. 人工在 main 提交 docs(plan): add DEV-OPS-002 cursor orchestrator subagents plan"
  - "5. 从 main 创建 feat/DEV-OPS-002-cursor-orchestrator-subagents"
  - "6. Developer 实施：approved → in_progress → …"
  - "7. Code Review → Commit Recorder 草稿"
  - "8. Release Operator（或人工）在 feat 分支 commit/push/PR — 不得 merge"
  - "9. 人工 Merge PR；docs(status)；删除分支"
  - "10. status=completed；progress.md next_action 立即指向 DEV-002 业务规划/实施"
  - "11. 不得插入 DEV-OPS-003 或其他工作流优化任务于 DEV-002 之前"
expected_commits:
  - branch: "main"
    message: "docs(plan): add DEV-OPS-002 cursor orchestrator subagents plan"
    after: "PLAN_APPROVED and status=approved"
  - branch: "feat/DEV-OPS-002-cursor-orchestrator-subagents"
    message: "chore(cursor): add orchestrator, role subagents, and release permissions"
  - branch: "feat/DEV-OPS-002-cursor-orchestrator-subagents"
    message: "docs(status): record DEV-OPS-002 implementation commit and PR"
  - branch: "main"
    message: "docs(status): complete DEV-OPS-002 after PR merge"
out_of_scope_changes:
  - "业务代码与 DEV-002+ 实现（completed 后立即进入 DEV-002 规划/实施）"
  - "技术规格正文"
  - "03_AI_Prompts 源文件（白名单例外：00_全局开发规则.md）"
  - ".cursor/rules 除 00-memory-system-governance.mdc 外的文件"
  - ".cursor/skills 或 Custom Modes"
  - "修改 DEV-001 既有测试语义"
  - "自动 Merge / 删分支 / force push"
  - "在 Hash 产生前猜测回写"
```

说明：

1. **禁止**将 `docs(plan)` 放在独立 Plan Review / `PLAN_APPROVED` 之前。
2. 本规划会话禁止任何 Git Add/Commit/Push/Merge/Rebase/删分支。
3. 即使本任务交付 Release Operator，**本任务自身**的首次落地仍建议：Plan 批准 → 人工 docs(plan) → feat → Developer；Release Operator 可在本任务后期门禁满足后试用，但 Merge 仍人工。

## 14. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001 — Plan Review Round 1 修订（2026-08-07 02:12 UTC）

```yaml
amendment_id: Amendment-001
trigger: "Plan Reviewer Round 1 — PLAN_REJECTED"
review_result:
  blocker: 0
  must_fix: 5
  should_fix: 3
status_after_amendment: planned
awaiting: "Plan Reviewer Round 2 复审"
governance_files_modified_this_round: false
```

**MUST_FIX 摘要**：

| ID | 修订 |
|---|---|
| MF-001 | 增补 §2.6 Release Operator Git 写治理窄例外；§5.6 白名单纳入 `00-memory-system-governance.mdc` 与 `00_全局开发规则.md`；明确 permissions.json 非安全边界 |
| MF-002 | §2.4.1 Orchestrator fail-closed 行为与最小 grep 子串；测试/验收同步 |
| MF-003 | §7 Step 4 Release Operator 真实退出码、`RELEASE_COMPLETED`、Hash/PR 事实来源；契约子串 |
| MF-004 | §2.1 / Step 0 / §13：`completed` 后立即 DEV-002；Phase B 不得前置 |
| MF-005 | §9 受监督低风险 E2E 全流程；失败阻塞门禁；契约-only 不计 E2E |

**SHOULD_FIX 摘要**：

| ID | 修订 |
|---|---|
| SF-001 | Phase A 非目标：无多任务并行、无嵌套 Subagent、角色不 spawn 更深 Agent |
| SF-002 | §2.4.2 Orchestrator 可写 vs 禁止自写 progress 字段 |
| SF-003 | §2.1 状态机扩展为完整人工/docs/feat/Release/Merge/DEV-002 链路 |

**说明**：治理例外内容仅记入本 Task Plan；§5.6 治理文件**尚未**修改。Round 2 已 `PLAN_APPROVED`；status 现为 `approved`（仍不得实施）。

## 15. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-06 15:50 UTC | 计划初稿落盘 | 创建本 Task Plan；登记 master_plan CHANGE-003 / progress | 无 | status=planned；未创建 agents/orchestrator/权限；未 Git 写 |
| 2026-08-07 02:05 UTC | Planner 复核 | 按官方 Subagents/permissions 复核能力表；补强归档/降级/五命令不可改；澄清基线与规划脏工作区 | 无 | status 仍 planned；未实施；未 Git 写 |
| 2026-08-07 02:12 UTC | Amendment 001 | Plan Review Round 1 PLAN_REJECTED（BLOCKER 0 / MUST_FIX 5 / SHOULD_FIX 3）；落盘 MF/SF 全部修订；治理例外仅计划内容 | 无 | status 仍 planned；待 Round 2 复审；治理文件未改 |
| 2026-08-07 02:18 UTC | Round 2 批准回写 | status=planned → approved；同步 master_plan / progress | 无 | PLAN_APPROVED；未实施；未创建 agents/permissions；未改治理/五命令；未 Git 写 |

## 16. 实际执行结果

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
plan_review:
  round: 1
  blocker: 0
  must_fix: 5
  should_fix: 3
  verdict: PLAN_REJECTED
  amendment: Amendment-001
  re_review: completed
  round_2:
    blocker: 0
    must_fix: 0
    should_fix: 0
    verdict: PLAN_APPROVED
    reviewed_at: "2026-08-07 02:18 UTC"
implementation_review: null
```

### Git 记录

```yaml
implementation_branch: feat/DEV-OPS-002-cursor-orchestrator-subagents
current_branch: main
baseline_commit: 5f34ccbcb7a052131dbeedd17c68dbf6dc30c52d
plan_commit: null
implementation_commit: null
implementation_commit_message: null
next_git_step: "人工在 main 提交 docs(plan): add DEV-OPS-002 cursor orchestrator subagents plan；随后创建 feat/DEV-OPS-002-cursor-orchestrator-subagents"
```

### 最终状态

`approved`
