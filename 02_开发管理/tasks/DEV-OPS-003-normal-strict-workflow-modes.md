# DEV-OPS-003 Add NORMAL / STRICT workflow modes and reduce routine human gates

## 1. 任务信息

```yaml
task_id: DEV-OPS-003
task_name: Add NORMAL / STRICT workflow modes and reduce routine human gates
status: reviewed
spec_sections:
  - "非业务规格任务：扩展 DEV-OPS-002 Orchestrator/Subagent 工作流；不修改技术规格正文与业务 Contract"
prerequisites:
  - "DEV-OPS-002 completed（Orchestrator + 六 Subagent + Release Operator 窄例外 + 契约测试已在 main）"
  - "DEV-003 completed（PR #6 merged；docs(status) complete 已在 main：c1234c5）"
  - "基线：main @ c1234c5b28373f57c118d0afc9442a90dee8cd51；与 origin/main 同步；工作区干净（规划轮次只读验证）"
  - "本任务为人工显式插入：在 DEV-004 业务规划之前执行；不得开始 DEV-004"
branch: "feat/DEV-OPS-003-normal-strict-workflow-modes"
created_at: "2026-08-07 15:22 UTC"
updated_at: "2026-08-08 01:15 UTC"
approval_gates:
  planning_docs: "Round 1 PLAN_REJECTED（MF-001）；Amendment 001；Round 2 Plan Reviewer = PLAN_APPROVED（BLOCKER 0 / MUST_FIX 0 / SHOULD_FIX SF-R2-001–002 非阻塞）；人工确认 PLAN_APPROVED 2026-08-07 15:39 UTC"
  implementation_plan: "status=reviewed；P2 CLOSED（角色段 mode-conditional）；复审 CODE_REVIEW_APPROVED（P0=0/P1=0/P2=0/P3=2）；plan_commit=d45ea2f；Commit Recorder 边界 PASS；未 Git 写；未开始 DEV-004；STRICT 不自动 Release"
insertion_override:
  prior_next_action: "进入 DEV-004（Migration Runner 与基础设施初始化）业务规划；…不得插入 DEV-OPS-003…"
  override_by: "用户本轮显式字段 + Orchestrator 调用（TASK_ID=DEV-OPS-003）"
  effect: "current_task 切换为 DEV-OPS-003；DEV-004 保持 planned 但不得在本任务期间启动"
```

## 2. 任务目标

在保留 DEV-OPS-002 六 Subagent 架构与 fail-closed 安全模型的前提下，引入两种显式工作流模式，降低常规任务的机械人工门禁次数。

完成后应具备：

1. **两种显式模式**：`NORMAL`（默认，常规任务）与 `STRICT`（高风险 / debug / E2E；保留 DEV-OPS-002 行为）。
2. **Orchestrator 任务开始时必须声明所选 mode**（用户显式字段优先；缺省 `NORMAL`）。
3. **NORMAL 仅两个常规人工门禁**：
   - `PLAN_APPROVED`（人工确认）
   - Human PR Review / Merge
4. **NORMAL 期望流**（Orchestrator **仅调度**；全部 Git 写由 Release Operator 执行；异常一律 HALT）：

```text
Planner
→ Plan Reviewer
→ HUMAN PLAN_APPROVED
→ Orchestrator 自动调用 Release Operator RELEASE_PHASE=PLAN_LANDING
     （record approved；docs(plan) commit + push origin main；create/switch feat 分支）
→ Developer
→ Code Reviewer
→ Commit Recorder
→ Orchestrator 自动调用 Release Operator RELEASE_PHASE=IMPLEMENTATION_RELEASE
     （仅在 feat 分支：stage exact whitelist → implementation commit →
      push origin <feature> → gh pr create；
      可选：同 feat 上追加 docs(status): record 治理 commit + push origin <feature>；
      永久禁止本 phase 对 main 的 commit/push）
→ WAITING_FOR_PR_MERGE（halt；无需 webhook）
→ 人工 review/merge PR
→ 同一编排会话恢复后：Orchestrator 只读验证 PR 已真正 MERGED
→ Orchestrator 自动调用 Release Operator RELEASE_PHASE=POST_MERGE_CLEANUP
     （ff-only 更新 main；docs(status): complete commit + push origin main；
      仅 exact planned feat：git branch -d + git push origin --delete；最终干净同步核对）
→ COMPLETED
```

5. **STRICT** 保留现有 DEV-OPS-002 行为：显式人工 Release 批准与更细粒度 Git 门禁（人工 `docs(plan)` / 建分支 / 可选人工确认 reviewed / 人工触发 Release / 人工 post-merge 清理）。
6. **既有 fallback**：五条 DEV-OPS-001 手工命令继续可用；`/orchestrate-task` 仍为正常入口。
7. **强制契约测试**：NORMAL / STRICT 行为合同 + 异常 Git/review/PR 状态 fail-closed negatives；既有 DEV-OPS-002 契约保持通过，或有意修订并写明 rationale。

### 2.1 关键设计决策（最小变更偏好）

#### DD-001 — Git 写权威（强制）

**选择**：Release Operator **仍是唯一 Git 写 Subagent**。  
Orchestrator **自身永不执行** `git add` / `commit` / `push` / `branch` / `gh pr create` 等 Git/GitHub 写。

**NORMAL 下的编排机制**：在**已批准的转换点**，Orchestrator **自动 Foreground 调用** Release Operator，并传入显式 `RELEASE_PHASE`（见 §2.4）。Orchestrator 只做：状态识别 → 门禁校验 → 调用 Release Operator → 解析结束标记 → 决定继续或 HALT/PAUSE。

**拒绝的替代方案**：

| 方案 | 拒绝理由 |
|---|---|
| Orchestrator 直接执行 Git 写 | 破坏 DEV-OPS-002「唯一候选 Git 写角色」；扩大不可审计表面 |
| 新增第七个 Git 写 Subagent | 非最小变更；重复门禁逻辑 |
| 取消 Release Operator，改 hooks/脚本全自动 | 超出 Cursor Agent 工作流范围；削弱人工可审计性 |

**理由**：最小变更且保留 DEV-OPS-002 安全模型——Git 写权限仍窄定义、可审计、集中于单一角色；NORMAL 仅减少「人工再次批准去调用 Release Operator」的机械门禁，不把写权限散到 Orchestrator。

#### DD-002 — NORMAL 人工门禁集合（仅两个常规门禁）

| 门禁 | 谁确认 | 之后允许什么 |
|---|---|---|
| `PLAN_APPROVED` | 人工确认 Plan Reviewer 输出 | NORMAL 可自动调用 Release Operator `PHASE=PLAN_LANDING` |
| Human PR Review / Merge | 人工在 GitHub Merge PR | 恢复编排后自动调用 `PHASE=POST_MERGE_CLEANUP`（**无需**再一次批准门禁） |

**明确不再作为 NORMAL 常规人工门禁**（仍保留为审查/核对步骤，但成功后自动继续）：

- 人工 `docs(plan)` on main / 手工建 feat 分支
- 人工二次确认 `CODE_REVIEW_APPROVED` → `reviewed`（Code Reviewer 成功标记 + P0/P1=0 后自动记录并继续）
- 人工触发 Release / 二次批准 implementation commit
- 人工 post-merge `docs(status)` / 删分支（改为 Release Operator `POST_MERGE_CLEANUP`）

**任何异常仍须 HALT + 人工干预**（见 §2.6）；异常路径**不是**「减少审查」，而是 fail-closed。

#### DD-003 — STRICT = DEV-OPS-002 行为基线

STRICT 必须显式选择（用户字段 `WORKFLOW_MODE=STRICT` 或等价）。行为对齐 DEV-OPS-002：

- Orchestrator **不得**在成功标记后自动链式调用下一角色（保留「人工或新一轮显式调用继续」）
- 人工确认 `PLAN_APPROVED` 后，**不**自动 `PLAN_LANDING`；提示人工 `docs(plan)` + 建分支
- `approved` 且实施前置满足后，仍须显式调用才进入 Developer
- Commit Recorder 之后，须显式批准/调用才进入 Release Operator（implementation release）
- Release Operator **仅**允许既有 `IMPLEMENTATION_RELEASE` 操作集（功能分支 add/commit/push/PR；可选 feat 上 `docs(status): record`；**禁止** push/commit main——DD-006）；**不**开放 `PLAN_LANDING` / `POST_MERGE_CLEANUP`
- 人工 Merge + 人工删分支 + 人工最终 docs(status)

#### DD-004 — 模式选择与声明

```text
1) 用户消息显式字段优先：
   - WORKFLOW_MODE: NORMAL | STRICT
   - 或 MODE: NORMAL | STRICT
2) 若缺失：默认 NORMAL
3) Orchestrator 在本轮首次编排输出中必须声明：
   workflow_mode=<NORMAL|STRICT>
   以及选择来源（explicit|default）
4) 任务中途不得静默切换 mode；若用户显式要求切换 → ORCHESTRATOR_PAUSED_FOR_HUMAN 并要求确认
5) STRICT 必须可被显式选择；不得因「省事」把高风险任务默认为 NORMAL
```

#### DD-005 — Post-merge 恢复模型（无 webhook）

- NORMAL 在 PR 创建成功后进入 `WAITING_FOR_PR_MERGE`，输出 `ORCHESTRATOR_PAUSED_FOR_HUMAN`
- **不**引入 webhook / 后台自动化 / 轮询守护进程
- 同一编排会话（或用户再次 `/orchestrate-task` 且 `TASK_ID` 相同、mode=NORMAL、状态为 waiting）在人工 merge 后恢复时：
  1. 只读验证 PR **真实** `state=MERGED`（`gh pr view --json …`）
  2. 验证 merge commit / base=main / head=功能分支事实
  3. 自动调用 Release Operator `PHASE=POST_MERGE_CLEANUP`
  4. **不再**要求第三次人工批准门禁
- 若 PR 未 merged / 冲突 / 状态不符 → `ORCHESTRATOR_HALTED`

#### DD-006 — `IMPLEMENTATION_RELEASE` committed 治理边界（MF-001；方案 A）

**选择：方案 A（最小变更；封闭 MF-001）**。不采用方案 B（不为 committed 治理新增仅 NORMAL 的独立 phase）。

| 约束 | 强制规则 |
|---|---|
| 共用 phase | `IMPLEMENTATION_RELEASE` 为 NORMAL 与 STRICT **共用**，命令集严格对齐 DEV-OPS-002 功能分支模型 |
| 禁止 main 写 | 本 phase **永久禁止** `git push origin main`、在 `main` 上 `git commit`、`git switch/checkout main` 后的任何写操作 |
| committed 成立时机 | 须在**人工 Merge 之前**成立（满足 `04_Git规范/git_workflow.md` §6「Merge 前 Task 状态为 committed」） |
| committed 落盘位置 | **仅功能分支**：白名单治理文件回写 +（如需）feat 上追加 `docs(status): record …` commit，并 **仅** `git push origin <exact feature branch>` |
| 禁止自动上 main | `docs(status): record` **不得**经本 phase（或任何 STRICT 路径）自动 push 到 `main` |
| completed 上 main | 仅 NORMAL 的 `POST_MERGE_CLEANUP` 允许 `docs(status): complete …` 的 main commit/push |

**拒绝方案 B 的理由**：新增 `COMMITTED_STATUS_LANDING` 扩大 phase 面与编排复杂度，且对 STRICT 无收益；方案 A 用「仅 feat ref」即可同时满足 Merge 前 `committed` 与「STRICT 不碰 main」。

### 2.2 NORMAL 不得削弱的安全属性（强制）

下列能力在 NORMAL 下**必须保持或加强**，不得以「减少门禁」为由削弱：

1. Planner / Plan Reviewer 独立审查
2. Code Reviewer 独立审查（P0/P1=0）
3. Commit Recorder boundary verification（精确白名单边界）
4. tests / lint / type checks 绿灯
5. writable-scope 三方交集（Orchestrator）
6. exact staged-path verification（Release Operator）
7. branch / base verification
8. PR base/head verification
9. protected operations policy（永久禁止 force push / hard reset / clean -fd / gh pr merge / 实现 Commit 直接上 main 等）
10. fail-closed（缺标记、双标记、非零退出、无法解析、范围外路径 → HALT）

### 2.3 状态机对比（NORMAL vs STRICT）

```text
共用前缀：
  planned → Plan Review → PLAN_APPROVED
         → 人工确认 PLAN_APPROVED → approved
```

| 阶段 | NORMAL | STRICT（DEV-OPS-002） |
|---|---|---|
| plan 落盘 + feat 分支 | Release Operator `PLAN_LANDING` **自动** | 人工 `docs(plan)` + 人工建分支 |
| 实施 | Developer（前置满足后 **自动**调用） | 显式调用 Developer |
| Code Review | Code Reviewer **自动**；通过后记录 `reviewed` 并继续 | 显式调用；可另需人工确认 `reviewed` |
| Commit 核对 | Commit Recorder **自动** | 显式调用 |
| Implementation Git/PR | Release Operator `IMPLEMENTATION_RELEASE` **自动**（门禁全过） | 显式人工触发 Release Operator |
| 等 Merge | `WAITING_FOR_PR_MERGE` pause | pause；人工 Merge + 人工清理 |
| Post-merge | Release Operator `POST_MERGE_CLEANUP` **自动**（验证 merged 后） | 人工 docs(status) + 删分支 |
| 常规人工门禁数 | **2**（PLAN_APPROVED + PR Merge） | **更多**（含 Release 触发与 post-merge） |

状态字段语义澄清（NORMAL）：

| 字段 | 谁写入 | 触发条件 |
|---|---|---|
| `approved` | 人工确认后由 Orchestrator/治理回写（非 Orchestrator 伪造批准） | 人工确认 `PLAN_APPROVED` |
| `reviewed` | Code Reviewer 成功后由编排回写（无需第二次人工口令） | `CODE_REVIEW_APPROVED` 且 P0/P1=0 |
| `committed` | Release Operator 在 `IMPLEMENTATION_RELEASE` 成功且事实核对后（**仅 feat 分支**回写/可选 `docs(status): record`；见 DD-006） | 真实 implementation Hash + PR OPEN 存在；**Merge 前**状态必须为 `committed`；**不**要求 record commit 已在 main |
| `completed` | Release Operator 在 `POST_MERGE_CLEANUP` 成功且事实核对后 | PR 真实 MERGED + completed 治理已 push **main** + 本任务 feat 已安全删除 + main 同步 |

### 2.4 Release Operator 扩展：分阶段操作包（NORMAL）

Release Operator 仍是唯一 Git 写角色，但按 `RELEASE_PHASE` 收窄允许命令集。每个 phase **独立**门禁；不得跨 phase 夹带命令。

#### PHASE=PLAN_LANDING（仅 NORMAL；人工 PLAN_APPROVED 之后）

**前置**：

1. Plan Reviewer 已输出 `PLAN_APPROVED` 且人工已确认 `approved`
2. 当前在 `main`，与 `origin/main` 同步（fast-forward 可拉；分歧 → FAIL）
3. 工作区干净（无 unexpected dirty / 无白名单外 staged）
4. 目标 feat 分支尚不存在（本地与远程）
5. 待提交路径 ⊆ Task Plan 计划文档白名单（通常：Task Plan、`progress.md`、`master_plan.md` 本任务登记）

**允许（逐条检查退出码）**：

- 只读：`git status` / `diff` / `log` / `branch` / `rev-parse` / `fetch`（只读事实）
- `git checkout main` 或 `git switch main`
- `git pull --ff-only origin main`（非 ff → FAIL；禁止 merge pull）
- `git add -- <exact plan whitelist paths>`
- `git commit`（message 必须匹配已批准的 `docs(plan): …` 约定）
- `git push origin main`（**禁止** force / force-with-lease）
- `git switch -c <exact planned feature branch>`（或 `git checkout -b …`）从**已更新**的 `main` 创建
- 只读核对：当前分支名、`git rev-parse HEAD`、与 plan_commit 一致性

**禁止**：实现文件 add；在 feat 分支上提前编码；删分支；`gh pr merge`；任何 force。

**成功标记**：`RELEASE_COMPLETED`（正文须声明 `phase=PLAN_LANDING` + 真实 `plan_commit` + `feature_branch`）。  
**失败标记**：`RELEASE_OPERATOR_FAILED`。

#### PHASE=IMPLEMENTATION_RELEASE（NORMAL 与 STRICT；对齐 DEV-OPS-002；MF-001 方案 A）

**前置**（全部满足）：

1. `approved` 已成立；feat 分支存在且为当前分支（**非** `main`）
2. `tested`；自动测试 / ruff / mypy 绿灯
3. `CODE_REVIEW_APPROVED`；P0/P1=0；状态允许 `reviewed`
4. Commit Recorder 已输出 `READY_FOR_HUMAN_COMMIT`（NORMAL 下该标记语义保留为「boundary 已核对、message 草稿就绪」；不要求再一次人工点头）
5. `git status` / staged/unstaged 路径 ⊆ Task Plan §5 实施白名单

**允许（仅当前 exact feature branch / ref=`origin/<feature>`）**：

- 只读：`git status` / `diff` / `log` / `branch` / `rev-parse` / `git fetch`（只读事实；不改变 ref 语义以外的写）
- `git add -- <exact whitelist paths>`
- `git commit`（implementation message 来自 Commit Recorder / 已批准计划）
- `git push origin <exact feature branch>`（**禁止** force / force-with-lease；**禁止** push 到 `main`）
- `gh pr create`（base=`main`；head=当前 feat）
- `gh pr view --json number,state,baseRefName,headRefName,url`
- **可选 committed 治理（仍仅 feat）**：在实现 Commit 与 PR 事实存在后，于**同一 feat 分支**回写 Task Plan / `progress.md` 的 committed 字段；若需 Git 落盘，追加 `docs(status): record …` commit，并 **仅** `git push origin <exact feature branch>`

**本 phase 永久禁止（NORMAL 与 STRICT 同等生效）**：

- `git push origin main` / 任何以 `main` 为 push 目标的写
- 在 `main` 上 `git commit` / `git add`（含「先 checkout main 再写治理」）
- 将 `docs(status): record` **自动**推到 `main`
- `PLAN_LANDING` / `POST_MERGE_CLEANUP` 专属命令（删分支、main 上 complete 文档 Commit 等）
- `gh pr merge`、force、hard reset、clean -fd、`git branch -D`

**成功**：`RELEASE_COMPLETED`（必须声明 `phase=IMPLEMENTATION_RELEASE` + implementation Hash + PR number/url/state + 当前 branch 名；若做了 record commit 须附其 Hash，且确认其 branch ≠ `main`）。  
其后 Orchestrator（NORMAL）进入 `WAITING_FOR_PR_MERGE`。  
**说明**：此时 progress/Task Plan 状态字段必须为 `committed`（Merge 前硬前置）；record 文档是否已在 **main** 无关。

#### PHASE=POST_MERGE_CLEANUP（仅 NORMAL；恢复编排且 PR 已验证 MERGED）

**前置**：

1. `gh pr view --json number,state,baseRefName,headRefName,mergedAt,mergeCommit` 显示 `state=MERGED`，`baseRefName=main`，`headRefName=<exact feature branch>`
2. 本地可 `git fetch origin`；`main` 可 fast-forward 到含 merge 的远程
3. 工作区干净或仅含本 phase 白名单治理文件变更
4. 当前任务状态已为 `committed`（来自先前 `IMPLEMENTATION_RELEASE`；不得用本 phase「补标」committed 来绕过 Merge 前要求）

**允许**：

- `git fetch origin`
- `git switch main` + `git pull --ff-only origin main`
- `git add -- <exact completed-status whitelist paths>`
- `git commit`（**仅** `docs(status): complete …` 约定消息；禁止实现 Commit）
- `git push origin main`（无 force）
- **有条件删除本任务已完成功能分支（SF-004）**：仅当上述 MERGED 前置全部为真时，允许  
  `git branch -d <exact planned feature branch>`（禁止 `-D`）与  
  `git push origin --delete <exact planned feature branch>`  
  **仍禁止**：删除任何非本任务计划分支、tags、无关远程分支；禁止在未 MERGED 时删除
- 只读最终核对：`main`==`origin/main`；本任务功能分支本地/远程不存在；工作区干净

**永久仍禁止**：`gh pr merge`、`git merge`（内容合并）、`git push --force*`、`git reset --hard`、`git clean -fd`、`git branch -D`、删除非本任务分支、向 `main` 提交**实现** Commit。
### 2.5 Orchestrator 编排变更点（实施时写入 `orchestrate-task.md`）

1. **Mode 声明**：§2.1 DD-004。
2. **自动续跑（仅 NORMAL）**：当前 Subagent 结束标记为**唯一成功标记**且通过校验后，Orchestrator **可以**在同一轮或紧接调用中 Foreground 调用下一映射角色 / 下一 Release phase；**不得**在失败、双标记、缺标记、非零退出时继续。
3. **STRICT / 失败路径**：保留「不得自动调用下一角色」；须人工或新一轮显式继续。
4. **契约测试有意修订**：现有强制子串 `不得自动调用下一角色` 改为**模式条件化**表述（见 §8），并保留 fail-closed 语义子串。
5. **人工暂停点（NORMAL）**：仅 `PLAN_APPROVED` 确认前、以及 `WAITING_FOR_PR_MERGE`；外加任何 HALT。
6. **Orchestrator 仍禁止**：亲自规划/开发/审查/批准；执行任何 Git 写；输出 `PLAN_APPROVED` / `CODE_REVIEW_APPROVED` 作为自身批准。
7. **可写交集规则不变**（三方交集 fail-closed）；不得为记编排态扩大白名单。
8. **五命令降级路径不变**；不得修改五命令正文（除非本计划白名单显式允许——默认**禁止修改**五命令正文）。

### 2.6 异常 → HALT（NORMAL 与 STRICT 共用；示例非穷尽）

任一触发 → `ORCHESTRATOR_HALTED` 或 `RELEASE_OPERATOR_FAILED`，**不得**自动续跑：

- dirty / unexpected working tree
- staged paths outside approved boundary
- branch mismatch（含误在 `main` 上做 implementation release）
- `main` / `origin/main` 分歧且无法 ff-only
- failed tests / ruff / mypy
- P0/P1 findings 或未解决 blocking review finding
- unexpected Git state / 非零 shell 退出码
- PR creation failure / PR base|head 不符
- PR 声称完成但 `gh pr view` 显示未 MERGED
- merge conflict / remote branch mismatch
- governance state mismatch（progress/Task Plan 与 Git 事实不一致）
- 试图在 STRICT 下执行 `PLAN_LANDING` / `POST_MERGE_CLEANUP`
- Release Operator 被非 Orchestrator 门禁路径误用扩大命令集

### 2.7 与 DEV-OPS-002 / 治理文件的兼容性

| 项 | 策略 |
|---|---|
| 六 Subagent 架构 | **保留**；不合并、不删除 |
| `/orchestrate-task` | **保留**为正常入口；扩展 mode / phase 编排 |
| 五 fallback 命令 | **保留**；默认**不改正文** |
| Release Operator 唯一 Git 写 | **保留**（DD-001） |
| 治理窄例外 | **修订**（实施阶段）：允许 NORMAL 下分 phase 的 main **文档** Commit（仅 `PLAN_LANDING` / `POST_MERGE_CLEANUP`）、ff-only pull、有条件删已完成 feat 分支；`IMPLEMENTATION_RELEASE` **永不** push main（DD-006）；仍禁止 force / hard reset / clean / `gh pr merge` / 实现 Commit 上 main |
| `04_Git规范/git_workflow.md`「禁止自动 Push」（SF-002） | **张力说明**：该文件对一般 AI 会话仍写「禁止自动 Push / Merge」。DEV-OPS-002/003 的 **Release Operator 治理窄例外优先**，不因 git_workflow 字面反向收紧已批准的受控 push。实施阶段**允许**最小修订 `git_workflow.md`（见 §5.2）：注明「一般禁止自动 Push；例外仅 Release Operator 按 Task Plan `RELEASE_PHASE`」。**不得**用 git_workflow 否定窄例外；也不得把例外扩大到 Orchestrator/其他角色 |
| DEV-OPS-002 契约测试 | **保持通过**或**有意修订**并在本计划 §8 / Amendment 写明 rationale（尤其：mode 条件化「自动调用下一角色」；Release 允许子串可能增加 `git branch -d` / `git push origin --delete` / `pull --ff-only` / `git fetch`，但**必须仍包含**对 `git branch -D` / force / `gh pr merge` / `IMPLEMENTATION_RELEASE` 下 `git push origin main` 的禁止断言） |
| `permissions.json` / `cli.json` | 最小必要扩展 allow 前缀（**必须显式含** `git fetch`，以及 `git switch`、`git pull`、`git branch` 等）；`block_instructions` 改写「Never delete remote branches」口径（SF-004）：默认禁止删远程分支/tags；**仅** `POST_MERGE_CLEANUP` + PR 已 MERGED + exact planned feat 允许 `--delete`；**仍声明非安全边界** |
| 技术规格 / 业务代码 | **不修改** |
## 3. 非目标

- 开始或实施 **DEV-004**（或任何 Phase 0+ 业务任务）的业务规划/编码。
- 修改 `src/**`、业务 `scripts/**`（非本任务白名单）、`pyproject.toml` 依赖、`uv.lock`（预期不改）。
- 修改 `01_技术规格/**` 正文或业务 API/Schema/状态机 Contract。
- 引入 webhook、CI bot 自动 merge、后台守护进程或 Cursor SDK 外部编排服务。
- Orchestrator 亲自执行 Git 写，或把 Git 写权限授予 Planner/Developer/Reviewer/Commit Recorder。
- 取消 Code Review / Commit Recorder / 测试门禁。
- 自动 `gh pr merge` / 自动 merge 到 `main` 的内容合并（PR Merge 仍为人工）。
- `git push --force*`、`git reset --hard`、`git clean -fd`、`git branch -D`。
- 删除六 Subagent 或合并为超级 Agent。
- 删除或改写五条 fallback 命令为不可用（默认不改其正文）。
- 配置 Custom Modes / 新增 `.cursor/skills/` 作为本任务交付核心。
- 本规划轮次实施代码、创建功能分支、或任何 Git 写。

## 4. 当前代码状态

- 已存在（只读核实）：
  - `.cursor/commands/orchestrate-task.md`（Orchestrator；含「不得自动调用下一角色」、可写交集、fail-closed）
  - 六个 `.cursor/agents/*.md`
  - `.cursor/permissions.json`、`.cursor/cli.json`
  - 治理窄例外：`.cursor/rules/00-memory-system-governance.mdc`、`03_AI_Prompts/00_全局开发规则.md`
  - 契约：`tests/unit/test_cursor_orchestrator_contract.py`、`tests/unit/test_cursor_commands_contract.py`
  - DEV-OPS-001 五命令仍在
- 可复用：DEV-OPS-002 状态机、结束标记、Release 退出码/事实核对模式、writable-scope 交集
- 当前缺失：
  - `WORKFLOW_MODE` / `NORMAL` / `STRICT` 显式合同
  - Release Operator 分 phase 操作包（`PLAN_LANDING` / `POST_MERGE_CLEANUP`）
  - Orchestrator NORMAL 自动续跑与 `WAITING_FOR_PR_MERGE` 恢复合同
  - NORMAL/STRICT + fail-closed negatives 契约测试
- 与技术规格不一致之处：无（非业务任务）
- 前置任务：DEV-OPS-002 = completed；DEV-003 = completed
- **Git 只读验证（规划时）**：
  - 分支：`main`
  - `git status --short`：空（干净）
  - `HEAD` == `origin/main` == `c1234c5`（`docs(status): complete DEV-003 after PR merge`）
  - 本地无 `feat/DEV-003-*`；远程无残留 DEV-003 feat head（`git ls-remote` 空）
  - 工作区适合规划；**本轮禁止**创建分支与 Git 写
- **progress.md 覆盖说明**：用户已显式覆盖「不得插入 DEV-OPS-003」；当前 `current_task=DEV-OPS-003` / `planned`（见 §15）

## 5. 文件白名单（实施阶段允许创建/修改的全部路径）

实施时**仅允许**下列路径。禁止通配为“整个 `.cursor/`”。

### 5.1 Orchestrator / Agents / 权限（修改）

| 路径 | 操作 | 目的 |
|---|---|---|
| `.cursor/commands/orchestrate-task.md` | 修改 | mode 声明；NORMAL 自动续跑；STRICT 保留；`WAITING_FOR_PR_MERGE`；phase 调度；fail-closed；人工门禁差异 |
| `.cursor/agents/release-operator.md` | 修改 | 分 `RELEASE_PHASE` 门禁与允许/禁止命令集；退出码/事实核对；成功须声明 phase |
| `.cursor/agents/commit-recorder.md` | 修改（最小） | NORMAL 下澄清结束标记不阻止自动 Release；STRICT 下仍为显式人工/编排触发前置；**仍禁止 Git 写** |
| `.cursor/agents/planner.md` | 修改（可选最小） | 若需在规划态提示默认 mode；不得改变 Planner 唯一角色 |
| `.cursor/agents/plan-reviewer.md` | 修改（可选最小） | 审查清单增加 mode 字段存在性（若 Task Plan 声明）；不得批准实施 |
| `.cursor/agents/developer.md` | 修改（可选最小） | 前置检查与 mode 无关的安全约束保持 |
| `.cursor/agents/code-reviewer.md` | 修改（可选最小） | 保持独立审查；NORMAL 不削弱 P0/P1 |
| `.cursor/permissions.json` | 修改（最小必要） | allow 前缀须显式包含 `git fetch`（SF-003），以及 `git switch` / `git pull` / `git branch` 等；改写 remote-delete 口径（SF-004）；仍禁裸 `"git"` |
| `.cursor/cli.json` | 修改（最小必要） | deny/allow 与危险操作对齐；显式允许/覆盖 `git fetch` 所需前缀；仍禁止 force / hard reset / `gh pr merge` 等 |

### 5.2 治理例外与 Git 规范（实施阶段修订；规划轮次不改）

| 路径 | 操作 | 目的 |
|---|---|---|
| `.cursor/rules/00-memory-system-governance.mdc` | 修改 | 将 Release Operator 窄例外扩展为「唯一 Git 写 + 分 phase」；写明 NORMAL 允许 main 文档 Commit（仅 PLAN_LANDING/POST_MERGE_CLEANUP）/ 有条件删已完成 feat；`IMPLEMENTATION_RELEASE` 禁 push main；保留永久禁止项 |
| `03_AI_Prompts/00_全局开发规则.md` | 修改 | 与治理规则对齐的同一窄例外说明 |
| `04_Git规范/git_workflow.md` | 修改（最小；SF-002） | 在「禁止自动 Push」旁增加指针：一般会话禁止；**仅** Release Operator 按已批准 Task Plan `RELEASE_PHASE` 的受控 push 为例外；不扩大到其他角色；不反向收紧治理窄例外 |
### 5.3 契约测试（强制）

| 路径 | 操作 | 目的 |
|---|---|---|
| `tests/unit/test_cursor_orchestrator_contract.py` | 修改 | 保留 DEV-OPS-002 安全断言；**有意修订** mode 条件化自动续跑；新增 NORMAL/STRICT / phase / fail-closed negatives |
| `tests/unit/test_cursor_workflow_modes_contract.py` | **新建** | NORMAL vs STRICT 行为合同、人工门禁差异、Release phase 允许/禁止子串、异常 HALT 子串 |
| `tests/unit/test_cursor_commands_contract.py` | 修改（仅当必要） | 不得削弱五命令+orchestrator 存在性/隔离；默认尽量不改 |

### 5.4 开发管理文档

| 路径 | 操作 | 目的 |
|---|---|---|
| `02_开发管理/tasks/DEV-OPS-003-normal-strict-workflow-modes.md` | 创建/回写 | 本 Task Plan 与执行记录 |
| `02_开发管理/master_plan.md` | 修改 | Phase 0 补充区登记 DEV-OPS-003 + CHANGE 记录 |
| `02_开发管理/progress.md` | 修改 | 规划态/实施态回写；记录对 DEV-004 next_action 的用户覆盖 |

### 5.5 明确不在白名单（默认禁止）

- `.cursor/commands/{plan-task,review-plan,develop-task,review-code,close-task}.md`（五命令正文**禁止修改**）
- `01_技术规格/**`、`src/**`、业务 Migration/Compose 等
- DEV-004 Task Plan（不得创建/开始）

## 6. 文件黑名单

| 路径 / 模式 | 原因 |
|---|---|
| `src/**` | 业务代码 |
| `scripts/migrate.py`、`scripts/migrations/**` | DEV-004 |
| `01_技术规格/**` | 禁止改规格 |
| 五命令正文（上表） | 降级路径稳定性 |
| `02_开发管理/tasks/DEV-004-*.md` | **禁止本任务启动 DEV-004** |
| 任意 webhook/bot 自动 merge 脚本 | 非目标 |
| 用户主目录 `~/.cursor/**` 作为交付物 | 不提交 |

## 7. 实现方案

### Step 0 — 状态与覆盖关系（贯穿）

| 触发 | 状态 |
|---|---|
| 本规划轮次 | `planned` |
| 独立 Plan Review `PLAN_APPROVED` + 人工确认 | `approved`（不得实施至 docs(plan)/分支前置满足） |
| Developer 开始 | `in_progress` |
| 白名单落地 | `implemented` |
| 契约 + ruff/mypy 通过 | `tested` |
| Code Review 通过 | `reviewed` |
| Implementation release + PR | `committed` |
| PR merged + post-merge cleanup | `completed` |
| `completed` 后 | `next_action` 指向 **DEV-004** 业务规划（恢复被插入打断的业务主线） |

**覆盖记录（强制写入 progress）**：用户显式插入 DEV-OPS-003，覆盖先前「不得插入 DEV-OPS-003 / 立即 DEV-004」的 next_action；DEV-004 仍为 Phase 0 下一业务任务，但本任务完成前不得开始。

### Step 1 — 扩展 Orchestrator 合同

修订 `.cursor/commands/orchestrate-task.md`：

1. 解析 `WORKFLOW_MODE` / 默认 NORMAL；强制声明。
2. 状态→角色映射表增加 mode 列与 Release phase 列。
3. NORMAL：成功标记校验后允许自动调用下一角色/phase；在 `PLAN_APPROVED` 等待与 `WAITING_FOR_PR_MERGE` pause。
4. STRICT：禁止自动续跑；禁止调度 `PLAN_LANDING` / `POST_MERGE_CLEANUP`。
5. 保留 writable-scope 交集与 `ORCHESTRATOR_HALTED` / `ORCHESTRATOR_PAUSED_FOR_HUMAN`。
6. 明确 Orchestrator 永不 Git 写；仅调度 Release Operator。

### Step 2 — 扩展 Release Operator 分 phase

修订 `.cursor/agents/release-operator.md`：

1. 要求输入/识别 `RELEASE_PHASE`。
2. 按 §2.4 / DD-006 写清三 phase 的前置、允许命令、禁止命令、成功/失败标记；`IMPLEMENTATION_RELEASE` 必须含「禁止 `git push origin main` / main 上 commit」字面合同。
3. 保留：每条命令检查退出码；不得假设成功；Hash/PR 事实来源；`permissions.json` 非安全边界。
4. STRICT 调用若带 `PLAN_LANDING`/`POST_MERGE_CLEANUP` → 立即 `RELEASE_OPERATOR_FAILED`。
5. `IMPLEMENTATION_RELEASE` 若检测到当前分支为 `main` 或命令目标为 `main` → 立即 `RELEASE_OPERATOR_FAILED`。

### Step 3 — Commit Recorder / 其他 Agent 最小对齐

- Commit Recorder：NORMAL 下 `READY_FOR_HUMAN_COMMIT` 表示 boundary+message 就绪，供 Orchestrator 自动调度 `IMPLEMENTATION_RELEASE`；文案避免「必须等待另一次人工 Git 批准」与 NORMAL 冲突，但 **STRICT / 五命令路径**仍可解释为人工提交核对完成。
- 其他 Agent：仅当合同测试需要时做最小文字对齐；不得改变唯一角色与结束标记集合（除 Release 成功须带 phase 声明外）。

### Step 4 — 治理窄例外与 git_workflow 修订

更新 `.cursor/rules/00-memory-system-governance.mdc` 与 `03_AI_Prompts/00_全局开发规则.md`：

- 唯一 Git 写角色 = Release Operator
- 允许操作按 phase 列表（引用本 Task Plan §2.4 / DD-006）
- **明确**：`IMPLEMENTATION_RELEASE` 永久禁止 `git push origin main` / 在 main 上 commit；committed/`docs(status): record` 仅 feat
- 永久禁止列表保留并强调：`gh pr merge`、force、hard reset、clean -fd、`git branch -D`、实现 Commit 直接上 main
- 明确 `git branch -d` 与 `git push origin --delete` **仅** `POST_MERGE_CLEANUP` + PR 已 MERGED + exact planned feat

最小修订 `04_Git规范/git_workflow.md`（SF-002）：在「禁止自动 Push」处增加 Release Operator 窄例外指针；权威次序为治理窄例外 ⊇ git_workflow 一般禁令的字面收紧解释。

### Step 5 — permissions / cli 最小调整

- IDE `terminalAllowlist`：**必须显式包含** `git fetch`（SF-003），以及 `git switch`、`git pull`、`git branch`、`git checkout` 等必要前缀；**仍禁止**裸 `"git"`
- `autoRun.block_instructions`（SF-004）：将绝对句「Never delete remote branches or tags」改写为：  
  「Do not delete remote branches or tags, except when acting as Release Operator in `POST_MERGE_CLEANUP` after the task PR is verified MERGED, and only `git push origin --delete <exact planned feature branch>` (never unrelated branches/tags; never `git branch -D`).」
- CLI deny：保持 force / merge / 读 `.env*`；delete 相关若需 allow，必须伴有 prompt 门禁且与上款一致
### Step 6 — 契约测试

见 §8。先保证既有测试语义不静默变绿；凡修订 DEV-OPS-002 断言须在测试注释 + 本计划写明 rationale。

### Step 7 — 受监督冒烟（实施后；非本规划轮次）

- STRICT：短路径确认仍 pause 在原人工点
- NORMAL：低风险 docs-only 或既有 OPS 回放级冒烟至 `WAITING_FOR_PR_MERGE`（**不**自动 merge）；人工 merge 后恢复跑完 cleanup
- UI：`/orchestrate-task` 与六 Subagent / 五命令仍可发现

## 8. 测试计划

### Unit / Contract（强制；静态文件合同）

| 场景 | 预期 |
|---|---|
| 六 Agent 文件仍在且角色一一对应 | 既有断言通过 |
| Orchestrator 仍禁止自批准 | 不得以自身输出 `PLAN_APPROVED`/`CODE_REVIEW_APPROVED` 作为批准 |
| writable-scope 交集规则仍在 | 既有 10 条规则保持（`manual_gates_unchanged` 如需修订：改为「NORMAL 仅放宽机械 Git 门禁，不放宽审查/测试/白名单」并更新 pattern + rationale） |
| Mode 声明合同 | orchestrate-task 含 `WORKFLOW_MODE`/`NORMAL`/`STRICT`/默认 NORMAL/必须声明 |
| NORMAL 自动续跑合同 | 成功标记校验后可自动调用下一角色；失败路径仍「不得自动调用」 |
| STRICT 禁止自动续跑 / 禁止 PLAN_LANDING&POST_MERGE_CLEANUP | 可 grep 的强制子串 |
| Release phase 合同 | 三 phase 名称与允许/禁止命令子串；成功须含 phase |
| 永久禁止仍在 | `git push --force`、`git reset --hard`、`git clean -fd`、`git branch -D`、`gh pr merge` 仍为禁止断言 |
| Orchestrator 禁止 Git 写 | 明确子串：Orchestrator 不得执行 git add/commit/push |
| 五命令不退化 | commands contract 通过 |

### Fail-closed negatives（新建/扩展）

| 场景 | 预期 |
|---|---|
| 缺结束标记 / 成功失败双标记 | HALT；不得续跑 |
| dirty tree / 路径越界 | Release FAIL / Orchestrator HALT |
| branch mismatch / main 分歧 | FAIL |
| PR not merged 时调用 POST_MERGE_CLEANUP | FAIL |
| STRICT 请求 PLAN_LANDING 或 POST_MERGE_CLEANUP | FAIL |
| **MF-001**：`IMPLEMENTATION_RELEASE` 正文/合同允许 `git push origin main` 或在 main 上 commit | **测试失败**（必须禁止） |
| **MF-001**：`IMPLEMENTATION_RELEASE` 将 `docs(status): record` 描述为自动上 main | **测试失败** |
| **MF-001**：STRICT 路径出现 main push（除只读外） | FAIL / 合同禁止 |
| `IMPLEMENTATION_RELEASE` 当前分支为 `main` 仍继续写 | FAIL |
| 未 MERGED 时 `git push origin --delete` | FAIL |
| 非零退出 | 立即停止后续 Git 步骤 |
### Integration / E2E

| 场景 | 预期 |
|---|---|
| 真实基础设施 Integration | **不适用**（无业务服务变更） |
| 受监督 E2E 冒烟 | 实施后：NORMAL 至 WAITING_FOR_PR_MERGE；恢复后 cleanup；STRICT 抽检人工门禁；契约-only 不计 E2E |

### 失败注入与并发

| 场景 | 预期 |
|---|---|
| 模拟 gh 返回非 MERGED | HALT/FAIL |
| 并发多任务编排 | **非目标**；仍单任务 |

### DEV-OPS-002 契约有意修订清单（实施时必须逐项注释）

| 原断言 | 修订方向 | Rationale |
|---|---|---|
| 无条件 `不得自动调用下一角色` | 改为 STRICT 无条件禁止 + NORMAL 仅成功校验后允许 + 失败仍禁止 | 实现 NORMAL 减门禁且保留 fail-closed |
| `不放宽 approved/reviewed/committed/completed` | 细化为：不放宽审查/测试/白名单；NORMAL 允许机械状态推进由 Release 事实驱动 | 与两门禁模型一致 |
| Release 禁止串含 `git merge` | **保留**禁止 `git merge`/`gh pr merge`；**不**把 `git pull --ff-only` 写成 merge | 避免误伤 ff-only |
| 无 `git branch -d` 允许 | 新增：仅 POST_MERGE_CLEANUP + MERGED + exact feat 允许 `-d`/`--delete`；仍禁 `-D` 与无关删除 | NORMAL 自动清理（SF-004） |
| `IMPLEMENTATION_RELEASE` 含糊「write/push committed governance」 | 改为：仅 feat 上 record；显式禁止 `git push origin main` | 封闭 MF-001 方案 A |
## 9. 验收标准

- [x] Task Plan 已批准且人工确认 `PLAN_APPROVED` 后才实施
- [x] Orchestrator 启动时声明 `workflow_mode`；缺省 NORMAL；STRICT 可显式选择
- [x] NORMAL 常规人工门禁仅为 `PLAN_APPROVED` + Human PR Merge；其余机械步骤由 Orchestrator 调度 Release Operator 完成
- [x] STRICT 行为与 DEV-OPS-002 对齐（无自动 PLAN_LANDING/POST_MERGE_CLEANUP；无成功后自动续跑）
- [x] Release Operator 仍为唯一 Git 写角色；Orchestrator 无 Git 写
- [x] **MF-001 / DD-006**：`IMPLEMENTATION_RELEASE` 永久禁止 push/commit main；committed/`docs(status): record` 仅 feat；Merge 前状态可为 `committed`
- [x] NORMAL 不削弱 §2.2 安全属性
- [x] 异常路径 HALT/FAIL 且需人工干预
- [x] 五命令仍可用；六 Subagent 仍在；`/orchestrate-task` 仍为入口
- [x] 契约测试：既有 + 新增 NORMAL/STRICT/negatives（含 MF-001）全部通过
- [x] permissions/cli 显式含 `git fetch`；remote-delete 口径符合 SF-004
- [x] `uv run ruff check .` 通过
- [x] `uv run mypy src tests` 通过
- [ ] Code Review 无 P0/P1
- [x] **未**创建或实施 DEV-004
- [ ] `completed` 后 `next_action` 回到 DEV-004 业务规划

## 10. 风险与阻塞项

### 10.1 风险

| ID | 风险 | 缓解 |
|---|---|---|
| R1 | NORMAL 自动续跑被模型误用为跳过审查 | 合同测试强制「仅成功标记后续跑」；缺/双标记 HALT；审查角色结束标记不变 |
| R2 | main 上文档 Commit 被滥用为实现 Commit | PLAN_LANDING/POST_MERGE 路径白名单仅治理文档；implementation 仅 feat 分支 |
| R3 | 删分支误删 | 仅 exact planned feature branch；先验证 PR MERGED；禁 `-D` |
| R4 | `git pull` 非 ff 导致隐式 merge | 强制 `--ff-only`；失败即 FAIL |
| R5 | IDE permissions 非安全边界（继承 OI-OPS-011） | prompt 门禁 + 退出码 + 契约；不把 permissions 当硬保证 |
| R6 | 与「不得自动调用下一角色」旧契约冲突 | 有意修订并写 rationale（§8） |
| R7 | progress 曾禁止插入本任务 | 用户显式覆盖已记录；master_plan/progress 登记插入关系 |

### 10.2 Open Issues（流程；不写入业务规格 Contract）

| ID | 问题 | 默认立场（本计划） |
|---|---|---|
| OI-OPS-014 | NORMAL 是否允许 Orchestrator 在同一 Foreground 轮次内连续调度多角色直至 pause | **允许**，但每个 Subagent 仍须独立 Foreground 调用并校验结束标记；禁止并行冲突审查对 |
| OI-OPS-015 | `READY_FOR_HUMAN_COMMIT` 命名在 NORMAL 下是否易误解 | **保留标记字符串**（兼容契约）；正文澄清语义；若改名须 Amendment |
| OI-OPS-016 | Post-merge 是否允许 `git push origin --delete` 在 CLI deny 下运行 | 实施时以最小 allow + prompt 门禁验证；若产品限制导致无法删远程分支 → HALT 并改人工删，记 Amendment |
| OI-OPS-017 | DEV-OPS-002 完成后曾禁止插入本任务 | **已由用户显式覆盖**；本任务完成后必须回到 DEV-004 |

### 10.3 阻塞

- 无规格阻塞。
- 实施前须：独立 Plan Review + 人工 `PLAN_APPROVED` +（按当时 mode）plan 落盘与分支前置。

## 11. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用业务事务 | 每个 Git 命令独立；非零即停，不继续后续写 |
| 幂等 | 部分适用 | PLAN_LANDING：分支已存在 → FAIL（不覆盖）；POST_MERGE：分支已删且治理已写 → 只读核对后可视为完成或 FAIL 待人工 |
| 并发 | 不适用多任务 | 仍单 Task；禁止并行冲突审查 |
| 版本冲突 | main 分歧 | `--ff-only` 失败 → FAIL |
| 用户隔离 | 不适用 | 无多租户业务数据 |
| 部分失败 | 适用 | 任一步失败不标记 completed/committed |
| 进程异常恢复 | 适用 | 无 webhook；依靠 progress/Task Plan 状态 + 只读 Git/PR 事实恢复；不可猜测 |

## 12. 风险与 DEV-004 边界（强制）

- **本任务 = DEV-OPS-003 only**
- **禁止**在本任务中启动 DEV-004 规划实施以外的「顺便做 Migration」
- DEV-004 在 master_plan 中保持 `planned`；`next_action` 仅在 DEV-OPS-003 `completed` 后切回 DEV-004

## 13. Git 计划

```yaml
branch: "feat/DEV-OPS-003-normal-strict-workflow-modes"
expected_commits:
  - "docs(plan): add DEV-OPS-003 normal and strict workflow modes plan"
  - "chore(cursor): add NORMAL/STRICT workflow modes and release phases"
  # 可选治理：
  - "docs(status): record DEV-OPS-003 implementation commit and PR"
  - "docs(status): complete DEV-OPS-003 after PR merge"
out_of_scope_changes:
  - "DEV-004 Migration Runner / 任何业务代码"
  - "修改五条 fallback 命令正文"
  - "技术规格正文"
  - "自动 gh pr merge / force push / 删无关分支"
```

规划轮次：**禁止**创建分支、禁止 Git 写。  
实施时 Git 顺序（在本任务自身 STRICT 或人工流程下）：Plan Review → `PLAN_APPROVED` → `approved` → `docs(plan)` on main → feat 分支 → Developer → Review → Release → 人工 Merge → completed → **next_action=DEV-004**。

> 注：若 DEV-OPS-003 自身实施时已可用 NORMAL mode，允许按 NORMAL 机械门禁执行；但**引导实施本任务的编排在模式落地前**仍按 STRICT/人工流程，避免未定义行为。

## 14. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。  
（注：本 Amendment 001 发生于首次 `PLAN_APPROVED` 之前，用于回应 Round 1 `PLAN_REJECTED`。）

### Amendment 001

- 日期：2026-08-07 15:35 UTC
- 原计划：初版 `IMPLEMENTATION_RELEASE` 写「门禁满足后的 committed 治理回写」且期望流含含糊的 `write/push committed-status governance if required`，未显式禁止 push main，存在泄漏进 STRICT 的风险（MF-001）
- 修改内容：
  1. **MF-001 → 方案 A（偏好）**：新增 DD-006；重写 §2.4 `IMPLEMENTATION_RELEASE`——永久禁止 `git push origin main` / main 上 commit；committed 与可选 `docs(status): record` **仅** feat 分支 commit/push；明确 Merge 前 `committed` 状态仍须成立且不得塞进 `POST_MERGE_CLEANUP`
  2. **SF-001**：§2 NORMAL 期望流点名 Orchestrator 调度 + `RELEASE_PHASE=…`，消除「Orchestrator 亲自 Git 写」歧义
  3. **SF-002**：§2.7 / §5.2 / Step 4 说明与 `04_Git规范/git_workflow.md`「禁止自动 Push」的张力；治理窄例外优先；白名单纳入最小修订该文件
  4. **SF-003**：permissions/cli 允许前缀**显式**列入 `git fetch`
  5. **SF-004**：改写 remote-delete 口径——默认禁删；仅 `POST_MERGE_CLEANUP` + 已 MERGED + exact planned feat 允许 `--delete`
  6. §8 增加 MF-001 fail-closed negatives；验收标准增加对应勾选
- 修改原因：回应 Round 1 `PLAN_REJECTED`（BLOCKER 0 / MUST_FIX MF-001 / SHOULD_FIX SF-001–SF-004）
- 是否影响技术规格：**否**
- 审批状态：`planned`；等待 Round 2 Plan Review（尚未 `PLAN_APPROVED`）

## 15. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-07 15:22 UTC | Planner 起草 Task Plan | 新建本文件；回写 progress/master_plan 规划态 | 未跑（规划 only） | 用户显式覆盖 progress 中「不得插入 DEV-OPS-003」；未实施、未 Git 写、未开始 DEV-004 |
| 2026-08-07 15:35 UTC | Planner Amendment 001（回应 PLAN_REJECTED） | 封闭 MF-001 方案 A；采纳 SF-001–SF-004；同步 progress 规划态为再审 | 未跑（规划 only） | 状态保持 `planned`；未实施、未 Git 写、未开始 DEV-004 |
| 2026-08-07 15:39 UTC | Round 2 批准回写（人工 PLAN_APPROVED） | status=`planned` → `approved`；同步 progress / master_plan；记录 Round 2 Plan Reviewer = `PLAN_APPROVED`；保留 Amendment 001 原文；仅 hygiene 修正 SF-R2-002 checklist 换行 | 未跑 | SF-R2-001（`expected_commits` 分支标注）未改合同表达，仅报告；未实施、未创建 feat、未 Git 写；本任务自身 STRICT；NORMAL 自动 phase 尚未可用；下一步人工 `docs(plan)` on main |
| 2026-08-07 15:49 UTC | Developer 开始（STRICT） | status=`approved` → `in_progress`；只读核对分支 `feat/DEV-OPS-003-normal-strict-workflow-modes`、HEAD=`d45ea2f`、工作区干净 | 未跑 | 前置满足；禁止 Git 写；不得开始 DEV-004 |
| 2026-08-07 15:55 UTC | Developer 白名单落地 + 契约测试 | §5 路径全部落地；新建 `test_cursor_workflow_modes_contract.py`；修订 orchestrator 契约（mode 条件化自动续跑 + MF-001）；回写 progress/master_plan | 见 §16 | status=`in_progress` → `implemented` → `tested`；Step 7 受监督冒烟 pending；待独立 Code Review |
| 2026-08-08 00:58 UTC | Orchestrator 复测 | 复跑核心契约 + 全量 unit + ruff + mypy | 49 / 101 / ruff / mypy 通过 | 与 Developer §16 一致；未 Git 写 |
| 2026-08-08 01:00 UTC | 独立 Code Review | 只读审查；回写 `tested` → `reviewed` | CODE_REVIEW_APPROVED；P0=0 P1=0 P2=1 P3=2 | P2/P3 非阻塞；下一步 Commit Recorder；STRICT 不自动 IMPLEMENTATION_RELEASE |
| 2026-08-08 01:05 UTC | Commit Recorder | 精确边界核对；输出 implementation commit 草稿 | 边界 PASS；13 路径 ⊆ §5 | `READY_FOR_HUMAN_COMMIT`；未 Git 写；须另一次显式 STRICT Release |
| 2026-08-08 01:15 UTC | Developer P2 最小修正 | 角色段 mode-conditional 自动续跑；modes 契约新增 `test_role_section_mode_conditional_auto_continue`；commands 共享子串保留 | 见 §16 复测 | status 保持 `reviewed`（P2 fix pending re-review）；未改五命令/src/DEV-004；未 Git 写 |
| 2026-08-08 01:20 UTC | P2 复审 + Commit Recorder | Code Reviewer 确认 P2 CLOSED；边界再核对 | CODE_REVIEW_APPROVED；P0=0 P1=0 P2=0 P3=2；契约 50 / unit 102 | `READY_FOR_HUMAN_COMMIT`；STRICT 不自动 Release；未 Git 写 |
## 16. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `.cursor/commands/orchestrate-task.md` | 已修订：mode 声明；NORMAL 自动续跑；STRICT 保留；WAITING_FOR_PR_MERGE；phase 调度；fail-closed；Orchestrator 永不 Git 写；**P2**：角色段「不得自动切换到下一角色」澄清为不得变身/兼任 + mode-conditional 自动调用 |
| `.cursor/agents/release-operator.md` | 已修订：三分 phase；DD-006；STRICT 误调 FAIL；退出码；成功须声明 phase |
| `.cursor/agents/commit-recorder.md` | 已修订（最小）：NORMAL 不阻止自动 Release；STRICT 仍可作显式前置；仍禁 Git 写 |
| `.cursor/permissions.json` | 已修订：显式 `git fetch`/`switch`/`pull`/`checkout`；SF-004 remote-delete 口径 |
| `.cursor/cli.json` | 已修订：allow 对齐；仍禁 force / hard reset / gh pr merge |
| `.cursor/rules/00-memory-system-governance.mdc` | 已修订：分 phase 窄例外 + DD-006 |
| `03_AI_Prompts/00_全局开发规则.md` | 已修订：同上对齐 |
| `04_Git规范/git_workflow.md` | 已修订（最小 SF-002）：Release Operator 例外指针 |
| `tests/unit/test_cursor_orchestrator_contract.py` | 已修订：mode 条件化 + permissions/cli 断言扩展 + rationale（本轮未再改） |
| `tests/unit/test_cursor_workflow_modes_contract.py` | **新建** + P2：`test_role_section_mode_conditional_auto_continue` |
| `tests/unit/test_cursor_commands_contract.py` | 未改（保留共享子串「不得自动切换到下一角色」；五命令未被削弱） |
| `02_开发管理/tasks/DEV-OPS-003-normal-strict-workflow-modes.md` | 执行记录与状态回写 |
| `02_开发管理/progress.md` | 实施态回写 |
| `02_开发管理/master_plan.md` | 状态与 CHANGE 备注回写 |

### 与原计划的差异

- 未修改可选 Agent（planner/plan-reviewer/developer/code-reviewer）：合同测试不要求额外对齐。
- Step 7 受监督冒烟：未执行（pending；契约-only 不计 E2E）。
- P2 最小修正：未改 commands contract 共享子串策略；仅角色段语义澄清 + modes 契约收紧。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit/Contract（核心） | `uv run pytest tests/unit/test_cursor_orchestrator_contract.py tests/unit/test_cursor_workflow_modes_contract.py tests/unit/test_cursor_commands_contract.py -q` | 50 passed（P2 复测） |
| Unit（全量） | `uv run pytest tests/unit -q` | 102 passed |
| Ruff | `uv run ruff check .` | All checks passed |
| Mypy | `uv run mypy src tests` | Success: 47 source files |
| E2E 冒烟（Step 7） | — | **pending**（未伪造） |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 2
verdict: CODE_REVIEW_APPROVED
review_report: |
  先前 P2 CLOSED（2026-08-08 复审）：角色段「不得自动切换」= 不得变身/兼任；
  自动调用 = mode-conditional（NORMAL 唯一成功标记+门禁；STRICT 禁续跑；异常 HALT）。
  P3 残余：Step 7 冒烟 pending；CHANGE-006 卫生（非阻塞）。
```

### Git 记录

```yaml
branch: feat/DEV-OPS-003-normal-strict-workflow-modes
plan_commit: d45ea2faf3b057c9e8ca0cf8699c0a973fe2e638
implementation_commit: null
implementation_commit_message: null
pr: null
```

### 最终状态

`reviewed`（P2 CLOSED；复审通过；未进入 Release）
