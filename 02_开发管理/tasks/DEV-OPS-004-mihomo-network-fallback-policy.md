# DEV-OPS-004 Document local Mihomo network fallback policy for AI development workflows

## 1. 任务信息

```yaml
task_id: DEV-OPS-004
task_name: Document local Mihomo network fallback policy for AI development workflows
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "非业务规格任务：本机 AI 开发工作流网络回退策略文档/治理；不修改技术规格正文、业务 Contract、Compose/Docker 业务代理语义"
prerequisites:
  - "DEV-OPS-003 completed（NORMAL/STRICT 工作流；PR #7 MERGED；docs(status) complete on main：4e4ad19）"
  - "基线：main @ 4e4ad1966e3c8cdbc015a2f7b343ed68f2c02702；与 origin/main 同步；工作区干净（规划轮次只读验证通过）"
  - "本任务为用户显式插入/覆盖：在 DEV-004 业务规划之前执行；不得开始 DEV-004"
branch: "feat/DEV-OPS-004-mihomo-network-fallback-policy"
created_at: "2026-08-08 05:52 UTC"
updated_at: "2026-08-08 06:03 UTC"
approval_gates:
  planning_docs: "PLAN_APPROVED；人工已确认 approved"
  implementation_plan: "status=tested；PLAN_LANDING 已成功；Developer 实施完成；等待 Code Review"
insertion_override:
  prior_current_task: "DEV-004"
  prior_current_task_status: "planned"
  prior_next_action: "进入 DEV-004（Migration Runner 与基础设施初始化）业务规划；本 Commit 不得开始 DEV-004 实施；…"
  override_by: "用户本轮显式字段 TASK_ID=DEV-OPS-004 + Orchestrator NORMAL 规划轮次"
  effect: "current_task 切换为 DEV-OPS-004；DEV-004 保持 planned 但本任务期间不得启动；完成后 next_action 恢复 DEV-004 业务规划"
```

### 1.1 环境前提（用户已验证主机事实；可写入策略正文；禁止 secrets）

以下为本开发主机已验证事实，作为 AI 策略的**环境前提**写入 `03_AI_Prompts/00_全局开发规则.md`（仅端口/单元名/行为，不含凭据/节点/订阅）：

| 项 | 值 / 事实 |
|---|---|
| systemd 单元 | `mihomo.service`（enabled + active） |
| Mixed proxy | `http://127.0.0.1:17890` |
| Controller | `127.0.0.1:19090`（仅诊断可达性；不得记录 API secret） |
| Docker daemon | 已永久配置 `HTTP_PROXY`/`HTTPS_PROXY` → `17890`；`live-restore`；真实 `docker pull` 经 Mihomo→GHCR 已验证 |
| 端口 7890 | 被既有 SSH forwarding 占用；**不得**复用、修改、抢占或要求迁到 7890 |
| Mihomo 配置路径 | `/opt/mihomo`（宿主机）；**永不**复制进仓库 |

**与规格 §3.15 的关系（强制澄清，非 Contract 变更）**：

- 技术规格 §3.15 / Compose `PROXY__HTTP_URL` 仍以规格字面 `7890`（容器侧常见 `host.docker.internal:7890`）为 MVP **业务/Compose Contract**，本任务**不得**修改规格正文、`.env.example`、Compose 代理注入语义。
- 本任务仅文档化：**本开发主机**上 AI Agent 处理「宿主机侧外部网络失败」时的 Mihomo/`17890` 回退策略；Docker **daemon** 已指向 `17890`，故 `docker pull` 等 daemon 级流量不依赖 ad-hoc 命令代理。
- 不得将本机 `17890` 事实静默改写成规格 Contract；若未来要对齐规格端口，须另开任务并经规格流程——**超出本任务范围**。

---

## 2. 任务目标

教会未来 Orchestrator / Subagents 在本开发主机上自主处理外部网络失败，无需反复请人临时配代理。

完成后应具备：

1. **权威 AI 面向策略**：在 `03_AI_Prompts/00_全局开发规则.md` 的固定约束块内，新增简洁、可执行的「本机 Mihomo 网络回退」条款（编号续接现有条目或独立小节，保持可读）。
2. **完整策略行为（实施时必须落入全局规则；下列 1–8 条为强制内容）**：

### 策略条款 1 — Docker 行为

- 假定 Docker daemon 已永久经 Mihomo `17890` 代理（本机已验证）；`docker pull` / 镜像相关失败时**优先**按条款 2–5 诊断 Mihomo/网络，而不是给单条 `docker` / `docker compose` / `./scripts/compose.sh` 命令临时加 `-e HTTP_PROXY` / 环境前缀。
- **禁止**为「让这次 docker 命令过一下」而 ad-hoc 注入代理环境变量。
- **禁止**因主观感觉慢而 `systemctl restart docker` / 重配 daemon 代理 / 改 `live-restore`。
- 本任务**不**修改 Docker daemon 配置；策略正文须写明「daemon 代理已由人工永久配置，Agent 不得改」。

### 策略条款 2 — 失败诊断分类

外部网络失败时，Agent 须先分类再行动（不得盲目重试/重启）：

| 分类 | 典型信号 | 下一步 |
|---|---|---|
| `PROXY_DOWN` | `mihomo.service` inactive/failed；`17890` 无监听 | 走条款 5（inactive） |
| `PROXY_UP_STILL_FAILING` | mihomo active 且 `17890` 可连，但拉取/PyPI 仍失败 | 有界重试（条款 7）；仍失败 → HALT 并报告分类，**不**因慢而重启 |
| `TRANSIENT` | 超时/连接重置/偶发 DNS | 有界重试（条款 7） |
| `NON_PROXY_APP_ERROR` | 401/404/契约失败/业务断言失败 | **不**走代理修复；按任务失败处理 |
| `AUTH_BLOCKED` | `sudo` 交互授权失败/拒绝 | **立即 HALT**；请人授权或手工启动 |
| `PORT_CONFLICT_HINT` | 有人提议改用/修改 `7890` | **拒绝**；7890 为 SSH forwarding，不可动 |

### 策略条款 3 — 健康检查（只读优先）

在任务**确实需要**外部网络且出现失败时，允许只读检查（示例意图，实施时写成简洁命令指引）：

1. `systemctl is-active mihomo`（或等价 status；不得刷屏完整敏感日志）
2. 确认 mixed 端口 `127.0.0.1:17890` 可连（例如短超时连通性探测；**不得**输出订阅/节点）
3. 可选：controller `127.0.0.1:19090` 可达性（**禁止**记录/提交 API secret、面板 token、配置全文）

### 策略条款 4 — `active` 时动作

- 保持服务运行；**不**因主观慢而 `restart` / `stop`。
- **非 Docker** 宿主机工具（如 `uv`、`curl`、`pip` 偶发、`gh` 若走代理等）可在**单条命令作用域**设置：
  - `HTTP_PROXY=http://127.0.0.1:17890`
  - `HTTPS_PROXY=http://127.0.0.1:17890`
- 不得把代理凭据写入仓库文件；不得 export 到长期 shell 配置并提交。
- Docker 相关命令：遵循条款 1（依赖 daemon；无 ad-hoc）。

### 策略条款 5 — `inactive` 时动作

- 仅当：**当前任务明确需要外部网络**，且健康检查已验证 `mihomo` **inactive**（或等价未运行）。
- 允许尝试：`sudo systemctl start mihomo`（**start**，非盲目 restart）。
- 若 sudo 需要交互授权且失败/无法完成 → **HALT**，向人工报告 `AUTH_BLOCKED`；不得循环尝试、不得改 sudoers、不得关认证。
- 启动成功后回到条款 3 复核，再继续原命令（纳入条款 7 重试预算）。
- **禁止**：`disable`/`mask` 单元；编辑 unit 文件；修改 `/opt/mihomo`；`restart` 仅因「感觉慢」。

### 策略条款 6 — Never 列表（强制）

Agent **Never**：

1. 提交或复制 `/opt/mihomo` 配置、订阅、凭据、节点信息、controller secret 进仓库或 Task Plan/progress。
2. 复用、修改、关闭或抢占宿主机 `7890` SSH forwarding。
3. 修改 Docker daemon 代理、`live-restore`，或要求人工重装代理栈（除非用户显式另开运维任务）。
4. 给 `docker` / `docker compose` / `compose.sh` **临时**加 ad-hoc `HTTP_PROXY`/`HTTPS_PROXY`。
5. 因主观慢而 `systemctl restart mihomo` / `restart docker`。
6. 将本机 `17890` 策略写成对规格 §3.15 / `.env.example` / Compose Contract 的静默修改。
7. 扩大 `.cursor/permissions.json` / CLI 权限，或以 permissions 代替真实门禁。
8. 在本任务或任意任务中把网络修复当作开始 **DEV-004** 的借口。

### 策略条款 7 — 有界重试

- 对 `TRANSIENT` / 启动后重试：同一网络操作最多有界次数（建议 **≤3** 次或等价短退避），记录分类。
- 耗尽预算仍失败 → HALT + 分类报告；**禁止**无限重试；**禁止**用重启代替分类。
- 不因重试而放宽测试断言或跳过门禁。

### 策略条款 8 — 安全边界（可写 vs 不可写）

| 可写入仓库 / 全局规则的内容 | 不可写入（绝对禁止） |
|---|---|
| 单元名 `mihomo.service`；端口 `17890` / controller `19090`；行为条款 1–7；Never 列表；HALT 条件 | 订阅 URL、节点列表、代理密码、controller secret、`/opt/mihomo` 文件内容、真实用户流量日志 |
| progress 已知风险中「本机宿主机工具经 17890」的非机密说明 | 任何 Secret、完整 Prompt/Response、真实用户数据 |

3. **强制静态契约测试**：存在性 + 必含子串（见 §8），防止策略回退或被删空。
4. **完成后** `next_action` 指向 DEV-004 业务规划；**本任务期间与完成 Commit 均不得开始 DEV-004 实施**。

### 2.1 关键设计决策

#### DD-001 — 单一权威文档（不另增 ops 文档）

**选择**：**不**新增第二份仓库内 ops/runtime 文档。

**理由**：

1. 目标读者是 Orchestrator/Subagents；`03_AI_Prompts/00_全局开发规则.md` 已是会话级固定约束入口。
2. 第二文件必然产生双源漂移（端口/Never/诊断分类不一致）。
3. 环境前提已在本 Task Plan §1.1 固化；契约测试可直接锚定全局规则文件。
4. 用户允许「仅在有清晰理由时才可提议一份额外文档」——当前无清晰理由。

**拒绝**：`02_开发管理/ops_*.md`、`docs/runtime-proxy.md`、复制 `/opt/mihomo` 说明进仓等。

#### DD-002 — 文档/治理 only；零运行时变更

本任务只改：全局开发规则 + 契约测试 + 开发管理回写。  
**禁止**：改 Mihomo runtime、`/opt/mihomo`、Docker daemon、业务 `src/**`、规格、五命令正文、permissions 扩大。

#### DD-003 — 规格 7890 vs 主机 17890 共存声明

策略必须显式区分「规格 Compose/业务代理 Contract（7890 字面）」与「本机 AI 宿主机回退（17890 + daemon）」；禁止把后者写成前者的取代。

---

## 3. 非目标

- 开始或规划实施 **DEV-004**（Migration Runner）。
- 修改技术规格 §3.15 / 任何业务 Contract、Schema、错误码、状态机。
- 修改 `.env.example`、`compose*.yaml`、`PROXY__HTTP_URL` 默认值、Preflight 7890 检查语义。
- 修改 `/opt/mihomo`、systemd unit 文件、Docker daemon.json、SSH forwarding（7890）。
- 扩大 `.cursor/permissions.json` / CLI 权限；修改五条 DEV-OPS-001 命令正文。
- 新增第二份 ops/runtime 文档（见 DD-001）。
- 真实基础设施 Integration/E2E（不得要求 CI 连真实 Mihomo/GHCR）。
- 提交 Secret、订阅、节点、controller 凭据。
- 自动 Push/Merge/Rebase/Force Push（仅 Release Operator 按 NORMAL phase 执行）。
- 修改业务代码 `src/**` 或既有业务测试语义。

---

## 4. 当前代码状态

- **已存在**：
  - `03_AI_Prompts/00_全局开发规则.md`：AI 固定约束（含 DEV-OPS-002/003 Release 窄例外）；**无** Mihomo/`17890` 回退策略。
  - `progress.md` 已知风险仍写「`uv` 经 `127.0.0.1:7890`」——与本机已验证 Mihomo `17890`（7890 被 SSH forwarding 占用）**不一致**，实施时应在治理回写中更正为非机密的本机说明。
  - 规格 §3.15 / Compose 契约仍假设业务侧 `7890`（保持不动）。
  - Cursor 契约测试族：`tests/unit/test_cursor_*_contract.py`（可复用「读文件 + 子串断言」模式）。
- **可复用组件**：既有 unit 契约测试风格（Path 读文本、`assert "…" in text`）。
- **当前缺失**：全局规则中的本机网络回退条款；对应契约测试。
- **与技术规格不一致之处**：无规格冲突；仅存在**本机环境**与规格示例端口的差异——用 DD-003 文档化，不改规格。
- **前置任务检查**：DEV-OPS-003 `completed`；main @ `4e4ad19` == `origin/main`；工作区干净（规划时验证）。

---

## 5. 实现方案

### Step 1 — 更新全局开发规则（权威策略）

- **文件**：`03_AI_Prompts/00_全局开发规则.md`
- **类/函数/Schema**：不适用（Prompt 约束文本）
- **输入**：§1.1 环境前提 + §2 策略条款 1–8
- **输出**：在 ````text` 固定约束块内追加简洁条款（建议作为第 18 条或「本机网络回退（DEV-OPS-004）」小节段落），必须覆盖：
  - `17890`、`mihomo`（单元名）
  - Docker 行为（daemon 已代理；禁止 docker 命令 ad-hoc proxy）
  - 失败诊断分类（至少点名条款 2 的分类名或等价中文标签）
  - 健康检查要点
  - active：非 Docker 工具命令作用域 `HTTP_PROXY`/`HTTPS_PROXY`
  - inactive：条件化 `sudo systemctl start mihomo`；授权失败 HALT
  - Never 列表关键项（含不提交 secrets、不动 7890、不因慢重启）
  - 有界重试
  - 安全边界（可写/不可写）
  - 不修改规格 §3.15 Contract 的共存声明（简短）
- **错误处理**：文案不得包含 secrets；不得粘贴 `/opt/mihomo` 内容
- **幂等**：同一策略只保留一处权威表述（DD-001）

### Step 2 — 强制契约测试

- **文件**：`tests/unit/test_mihomo_network_fallback_contract.py`（新建）
- **输入**：读取 `03_AI_Prompts/00_全局开发规则.md`
- **输出/断言**（最小必含；实施可细化为多个 test 函数）：
  - 文件存在
  - 含子串：`17890`、`mihomo`（大小写按落盘文案固定并在测试中一致）
  - 诊断分类相关子串（如 `PROXY_DOWN` 或计划落盘的中文等价标签——**计划要求实施时选定一种并在测试锁定**；推荐保留英文分类码便于契约稳定）
  - Never 相关：禁止提交 secrets / `/opt/mihomo`；禁止 ad-hoc docker proxy；禁止因慢重启；7890 不可改（或等价 Never 文案）
  - `systemctl start mihomo` 或等价 inactive 动作；`HALT`（授权失败）
  - 有界重试意图（如「有界」/`≤3`/`最多` 等落盘固定词）
- **禁止**：测试中连接真实网络、读取 `/opt/mihomo`、调用 docker pull

### Step 3 — 开发管理回写（实施阶段）

- **文件**：本 Task Plan 执行记录；`02_开发管理/progress.md`；`02_开发管理/master_plan.md`
- **目的**：状态机推进；更正「uv 经 7890」已知风险为「本机宿主机工具经 Mihomo `17890`；7890 为 SSH forwarding」；**不得**开始 DEV-004
- **完成后 next_action**：进入 DEV-004 业务规划（仍不得实施至另一次显式编排）

### Step 4 — 质量门禁

- `uv run pytest tests/unit/test_mihomo_network_fallback_contract.py -q`
- `uv run pytest tests/unit -q`（全 unit 保持通过）
- 既有 cursor 契约：`tests/unit/test_cursor_*.py` 保持通过
- `uv run ruff check .`；`uv run mypy src tests`（未改业务 py 逻辑则应保持通过；新建测试须符合 ruff/mypy）

---

## 6. 文件变更清单

### 6.1 精确白名单（实施可写；exact paths）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `03_AI_Prompts/00_全局开发规则.md` | 修改 | 落入策略条款 1–8（权威 AI 面向） |
| `tests/unit/test_mihomo_network_fallback_contract.py` | 创建 | 强制静态契约 |
| `02_开发管理/tasks/DEV-OPS-004-mihomo-network-fallback-policy.md` | 修改 | 执行记录 / 状态 |
| `02_开发管理/progress.md` | 修改 | 规划态→实施态回写；覆盖关系；已知风险更正 |
| `02_开发管理/master_plan.md` | 修改 | Phase 0 补充登记 DEV-OPS-004；CHANGE-007 |

### 6.2 明确不采用的可选路径

| 路径 | 决策 |
|---|---|
| 任何额外 `02_开发管理/**/ops*proxy*.md` / `docs/**` runtime 代理说明 | **不采用**（DD-001） |

### 6.3 黑名单（禁止）

- `src/**`
- `01_技术规格/**`
- `.cursor/commands/**` 五命令正文
- `.cursor/permissions.json` / CLI 权限扩大
- `/opt/mihomo/**`（任何复制进仓）
- `02_开发管理/tasks/DEV-004-*.md`（不得创建/修改 DEV-004 计划）
- Compose / `.env.example` / Docker daemon 配置
- 业务 Integration/E2E 测试改语义

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 文档任务：策略与契约测试须同一实现 Commit 内同时落地 | 无策略文件却有测试、或有策略无测试 → 不可 `tested` |
| 幂等 | 重复应用同一文案不产生第二真相源 | DD-001 单文件；契约锁定子串 |
| 并发 | 不适用多写者业务并发 | 单任务单分支；不并行 DEV-004 |
| 版本冲突 | 不适用业务乐观锁 | Git 冲突按正常分支解决；禁止 force push |
| 用户隔离 | 不适用多租户数据 | 禁止提交真实用户/节点数据 |
| 部分失败 | 仅改了规则未加测试、或测试红灯 | 不得标 tested；不得降断言 |
| 进程异常恢复 | 网络策略本身含 HALT/有界重试 | 条款 2/5/7；不把重启当恢复默认手段 |

**策略层「一致性」补充（对应 §2 条款，写入全局规则）**：诊断分类 → 动作映射必须一致；Never 与条款 1/4/5 不得互相矛盾（例如一边允许 docker ad-hoc proxy、一边 Never 禁止）。

---

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 新建契约模块可被 pytest 收集 | import/收集成功 |
| （若无可测纯函数则）无额外业务 unit | 声明：本任务无业务纯函数；unit 层以契约文件承载 |

### Contract Test（强制；本任务主门禁）

| 场景 | 预期 |
|---|---|
| 全局规则文件存在 | `03_AI_Prompts/00_全局开发规则.md` is_file |
| 含 `17890` | pass |
| 含 `mihomo` | pass |
| 含诊断分类标识 | 至少 `PROXY_DOWN` 与 `AUTH_BLOCKED`（或实施锁定的全部分类码集合） |
| Never：secrets / `/opt/mihomo` | 文案禁止提交配置/凭据 |
| Never：docker ad-hoc proxy | 文案禁止 |
| Never：因慢重启 | 文案禁止 |
| Never：7890 不可改 | 文案禁止复用/修改 7890 forwarding |
| inactive 启动与 HALT | 含 `systemctl start mihomo`（或等价）与授权失败 HALT |
| 有界重试 | 含有界/次数上限意图 |
| 安全边界 | 含不可写 secrets 类约束 |

### Integration Test

| 场景 | 预期 |
|---|---|
| 不适用 | 无真实 Mihomo/Docker daemon/GHCR 要求 |

### E2E Test

| 场景 | 预期 |
|---|---|
| 不适用 | 无 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| 不适用真实失败注入 | 策略正文描述 HALT/分类即可；不做运行时注入框架 |
| 并发 | 不适用 |

### 静态质量

| 检查 | 预期 |
|---|---|
| Ruff | 全仓通过（含新测试） |
| Mypy | `src tests` 通过 |
| 既有 unit/cursor 契约 | 保持通过 |

---

## 9. 验收标准

- [x] `03_AI_Prompts/00_全局开发规则.md` 含 §2 策略条款 1–8 的可执行摘要（含环境前提非机密端口/单元名）
- [x] **未**新增第二份 ops/runtime 代理文档（DD-001）
- [x] `tests/unit/test_mihomo_network_fallback_contract.py` 存在且断言通过
- [x] 白名单外路径无变更（`src/**`、规格、五命令、permissions、`/opt/mihomo` 未入仓）
- [x] 未开始 DEV-004；DEV-004 仍为 `planned`
- [x] `uv run pytest tests/unit -q` 通过
- [x] Ruff 通过
- [x] Mypy 通过
- [ ] Review 无 P0/P1
- [ ] 完成后 `next_action` = DEV-004 业务规划（不得实施）

---

## 10. 风险与阻塞项

- **设计文档冲突**：规格 §3.15 写 7890 vs 本机 17890 —— 以 DD-003 文档共存，**不**改规格；若 Reviewer 要求改规格 → 停止并升级人工（超出范围）。
- **当前代码冲突**：无。
- **前置任务**：DEV-OPS-003 completed（满足）。
- **未批准依赖**：无。
- **API/Schema 变化**：无。
- **其他风险**：
  - 文案过长导致全局规则膨胀 → 保持简洁条目，细节以分类表压缩。
  - Agent 仍可能忽略 Prompt → 契约测试防回退；不能替代运行时强制。
  - `sudo` 交互在非交互 Agent 会话失败 → 策略已要求 HALT（预期行为，非缺陷）。
  - progress 旧「7890」风险描述误导 → 实施时更正。

---

## 11. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/DEV-OPS-004-mihomo-network-fallback-policy"
expected_commits:
  - "docs(plan): add DEV-OPS-004 mihomo network fallback policy plan"
  - "docs(ai): document local mihomo network fallback for agents"
  - "docs(status): record DEV-OPS-004 implementation commit and PR"  # feat 上；IMPLEMENTATION_RELEASE 可选
  - "docs(status): complete DEV-OPS-004 after PR merge"  # POST_MERGE_CLEANUP on main
out_of_scope_changes:
  - "DEV-004 Migration Runner 任何文件"
  - "src/** 业务代码"
  - "技术规格 / Compose / .env.example 代理 Contract"
  - "/opt/mihomo 或宿主机代理配置"
  - "permissions / 五命令正文"
  - "第二份 ops runtime 文档"
release_phases:
  PLAN_LANDING: "main: docs(plan) + ff-only + 创建 exact feat"
  IMPLEMENTATION_RELEASE: "仅 feat: 白名单 add/commit/push/PR；禁 push main"
  POST_MERGE_CLEANUP: "PR MERGED 后：ff-only main + docs(status) complete + 删 exact feat"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-08 05:52 UTC | Planner 初版计划 | 创建本 Task Plan；progress/master_plan 规划态登记（插入覆盖 DEV-004） | 未实施 | 基线 main@4e4ad19 干净；未 Git 写；未开始 DEV-004 |
| 2026-08-08 05:57 UTC | planned → approved（PLAN_LANDING） | 状态回写 approved；progress/master_plan 同步；docs(plan) on main；创建 exact feat | 未实施 | 人工 PLAN_APPROVED 已确认；不得开始 DEV-004 |
| 2026-08-08 06:01 UTC | approved → in_progress | 全局规则 §18 策略条款；新建契约测试；progress/master_plan 回写 | 契约进行中 | SHOULD_FIX：7890=SSH/sshd；全部分类码；working tree 澄清 |
| 2026-08-08 06:03 UTC | in_progress → implemented → tested | 白名单 5 路径落地；质量门禁全绿 | 契约 15 passed；unit 117 passed；ruff/mypy 通过 | 未 Git 写；未开始 DEV-004；等待 Code Review |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `03_AI_Prompts/00_全局开发规则.md` | 新增 §18 本机 Mihomo 网络回退（条款 1–9；含分类码、Never、有界重试、7890 SSH/sshd 事实、working tree 澄清） |
| `tests/unit/test_mihomo_network_fallback_contract.py` | 新建；15 项静态契约断言 |
| `02_开发管理/tasks/DEV-OPS-004-mihomo-network-fallback-policy.md` | 状态/执行记录回写 |
| `02_开发管理/progress.md` | in_progress→tested；已知风险更正；plan_commit 回填 |
| `02_开发管理/master_plan.md` | Phase 0 补充状态 → tested；CHANGE-007 回写 |

### 与原计划的差异

- SHOULD_FIX 落实：7890 明确为 SSH/sshd forwarding（非空闲/非 Mihomo）；契约锁定全部失败信号短语与「不得误判为 proxy failure」；§18(9) 区分 PLAN_LANDING 白名单治理变更 vs unexpected dirty fail-closed。
- 未新增第二份 ops 文档（符合 DD-001）。
- 未改规格 / Compose / src / permissions / 五命令。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit -q` | 117 passed |
| Contract | `uv run pytest tests/unit/test_mihomo_network_fallback_contract.py -q` | 15 passed |
| Integration | N/A | |
| E2E | N/A | |
| Ruff | `uv run ruff check .` | All checks passed |
| Mypy | `uv run mypy src tests` | Success: 48 source files |

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
branch: "feat/DEV-OPS-004-mihomo-network-fallback-policy"
plan_commit: "895d7aaccc6c194105275e0688527d780907933f"
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`tested`
