# OI-012 SiliconFlow Embedding Provider Spec-OI

## 1. 任务信息

```yaml
task_id: OI-012
task_name: "SiliconFlow Embedding Provider Spec-OI (MVP Minimal Pivot)"
status: committed
task_class: Spec-OI
open_issue_id: OI-012
spec_sections:
  - "§2.2.6 EmbeddingClient Protocol（最小增补 SiliconFlow）"
  - "§2.2.14 memory_retrieval.embedding_provider 默认 siliconflow"
  - "§3.1 Embedding 默认部署（SiliconFlow 托管）"
  - "§3.8 SILICONFLOW_API_KEY Secret 契约"
  - "§3.10 最小 pivot 句（默认 provider + TEI 可选/非阻塞）"
spec_sections_deferred:
  - "§3.3 Compose 拓扑大规模改写 → DEFERRED"
  - "§3.18 Preflight 改写 → DEFERRED"
  - "§3.2 进程边界大段重写 → DEFERRED"
prerequisites:
  - "DEV-002 completed"
  - "DEV-004 completed（ES dims=1024）"
  - "DEV-005 completed（共享 httpx.AsyncClient）"
  - "OI-011 completed（TEI 12g contract 保留；本任务不修改）"
  - "DEV-006：PAUSED / SUPERSEDED_FOR_MVP；PR #13：OPEN / DO_NOT_MERGE（仅记录；不得触碰）"
  - "main @ c8c03db4b984a1e65b7d2d46b392f87a938c8eec；规划态治理文件未 commit（**本轮不 PLAN_LANDING**）"
branch: "feat/OI-012-siliconflow-embedding-provider-spec-oi"
created_at: "2026-08-09 05:30 UTC"
updated_at: "2026-08-09 06:15 UTC"
plan_review:
  round_1: "PLAN_REJECTED（BLOCKER=0；MUST_FIX=3）"
  amendment_001: "Amendment 001 — Plan Remediation Round 1（已吸收；Amendment 002 部分 supersede）"
  amendment_002: "Amendment 002 — MVP_SIMPLIFICATION（用户显式 directive）"
  round_2: "PLAN_REJECTED（MUST_FIX=1；SHOULD_FIX=4）→ Amendment 002.1"
  amendment_002_1: "Amendment 002.1 — MF-1 HEAD SHA + SF-1～4（已吸收）"
  round_3: "PLAN_APPROVED（BLOCKER=0；MUST_FIX=0）"
workflow_mode_for_this_task: NORMAL
workflow_mode_source: explicit
insertion_reason: "NEW_UNPLANNED_FEATURE：MVP 默认 Embedding pivot 至 SiliconFlow BAAI/bge-m3；最小 Spec-OI + 单一下游 DEV-007"
bound_open_issue: "02_开发管理/open_issues.md#OI-012"
dev006_disposition: "PAUSED / SUPERSEDED_FOR_MVP"
pr13_disposition: "OPEN / DO_NOT_MERGE — 决策 deferred 至 SiliconFlow MVP 路径验证后"
downstream_dev_task: DEV-007
changes_technical_spec: true
```

---

## 2. 任务目标

**最小 MVP Provider Pivot**：仅解决「默认 Embedding 从 local TEI 切换为 SiliconFlow 托管 `BAAI/bge-m3`」。**不**一次性重构整个 embedding 架构。

OI-012（Spec-OI）完成后，仓库具备：

1. **最小规格修订**：默认 provider=`siliconflow`、model=`BAAI/bge-m3`、dimension=1024、TEI=可选自托管/非 MVP 阻塞、`SILICONFLOW_API_KEY` 与 hosted integration 要求。
2. **架构决策记录**：保留 `EmbeddingClient` 抽象；新增 `SiliconFlowEmbeddingClient` Contract（httpx；无 SDK）。
3. **单一下游 DEV 任务定义**：**DEV-007**（合并原 DEV-007/008/009 意图）承载全部 SiliconFlow MVP 实现。
4. **DEFERRED 清单**：明确本 OI **不做**的事项，避免 scope creep。

**本轮：仅 Task Plan + 规划态治理；不 PLAN_LANDING；不改业务代码；不 Git 写。**

---

## 3. 非目标

- 实施 `SiliconFlowEmbeddingClient` 或任何 `src/**` 代码（属 **DEV-007**）。
- DEV-007/008/009 三路拆分（**已取消**；合并为 **DEV-007**）。
- 重构 `TEIEmbeddingClient`、修复 TEI HTTP 429、改 TEI compose、改 OI-011 contract。
- 本地 HF tokenizer 新体系（**DEFERRED**）。
- §3.3 Compose 大规模改写、§3.18 Preflight 改写（**DEFERRED**）。
- Provider 热切换、Index 重建系统、跨 provider cosine benchmark、大型 metrics  redesign。
- STM/EXT/RET 业务代码、ES mapping 变更。
- 访问 DEV-006 dirty worktree、merge/close/rewrite PR #13。
- 真实 SiliconFlow API 调用（OI-012 阶段）。
- PLAN_LANDING（用户 explicit）。

完整 **DEFERRED** 清单见 §5.5。

---

## 4. 当前代码状态

### 4.1 已存在

| 区域 | 现状 |
|---|---|
| `memory_retrieval.embedding_provider` | 默认 `"local_tei"`（须改为 `siliconflow`） |
| ES Mapping | `dims: 1024`（**不改**） |
| TEI / OI-011 | 12g contract 保留；**本任务不修改** |
| DEV-005 | 共享 `httpx.AsyncClient` |
| main | **无** `infrastructure/embedding/`（DEV-006 未 merge） |

### 4.2 缺失

- 规格默认 provider = SiliconFlow 的最小条文。
- `SiliconFlowEmbeddingClient` 实现（DEV-007）。
- `SILICONFLOW_API_KEY` Settings Contract（DEV-007）。

### 4.3 预期最小规格差异

| 项 | 现状 | OI-012 目标 |
|---|---|---|
| 默认 provider | `local_tei` | **`siliconflow`** |
| 默认 model | `BAAI/bge-m3` | 保持 |
| dimension | 1024 | 保持（Integration 门禁） |
| TEI | 隐含必选 | **可选自托管；非 MVP 阻塞** |

### 4.4 前置任务检查

| 前置 | 状态 |
|---|---|
| DEV-002 / DEV-004 / DEV-005 / OI-011 | completed |
| git HEAD | `main` @ `c8c03db4b984a1e65b7d2d46b392f87a938c8eec` |
| git 工作区 | **非干净**：`M` master_plan/open_issues/progress；`??` 本 Task Plan；**规划态未 commit；本轮不 PLAN_LANDING** |
| DEV-006 | **PAUSED / SUPERSEDED_FOR_MVP**；PR #13 **OPEN / DO_NOT_MERGE**；不得触碰 feat/worktree |
| embedding infra on main | 不存在 |

---

## 5. 实现方案（批准后分相；本轮不执行）

### 5.0 Reduced scope summary（Amendment 002）

| 维度 | OI-012（Spec-OI） | DEV-007（单一实现任务） |
|---|---|---|
| 目的 | 最小架构决策 + 规格 pivot 句 | SiliconFlow MVP Client + Settings + 测试 |
| 规格改动 | §3.1 / §2.2.14 / §3.8 / §3.10 最小句；§2.2.6 增补 SiliconFlow | 按 OI-012 已批准 Contract 编码 |
| TEI | 保留现状 + 规格标注 optional | **不** refactor TEI；PR #13 不动 |
| 下游任务数 | 定义 **1** 个 DEV-007 | 无 DEV-008/009 |
| master_plan | DEV-006→SUPERSEDED_FOR_MVP；DEV-007 登记；**最小** retarget | — |

---

### 5.1 Minimal target architecture

```text
Application (STM/EXT/RET)
    └── EmbeddingClient Protocol（保留）
            └── create_embedding_client(settings)
                    ├── SiliconFlowEmbeddingClient  ← MVP 默认（DEV-007 实现）
                    └── TEIEmbeddingClient          ← 保留历史/OI-011；本 MVP 不 refactor
```

**MVP 不变量：**

- 业务层 **不得** 直接依赖 SiliconFlow SDK 或 TEI SDK。
- 默认 `memory_retrieval.embedding_provider=siliconflow`。
- 输出 `EmbeddingResult`：`model=BAAI/bge-m3`，`dimension=1024`，`vectors` 与输入同序。

---

### 5.2 Official SiliconFlow facts（verified；摘要）

| # | 事实 |
|---|---|
| F1 | `POST https://api.siliconflow.cn/v1/embeddings` |
| F2 | `Authorization: Bearer <api_key>` |
| F3 | Model `BAAI/bge-m3` 可用 |
| F4 | `input`: string \| array；array **maxItems=32** |
| F6 | `dimensions` **不支持** bge-m3 → 输出维度 **UNKNOWN_FROM_OFFICIAL_DOCS** |
| F7 | Response: `data[{index, embedding[]}]` + `usage` |
| F11–F13 | 429 rate limit；400/401/403/503/504 文档化 |
| F12 | `x-siliconcloud-trace-id` 响应头（若存在） |

F9/F10 token 注释冲突 → **FLAG**；MVP **不** 建 tokenizer 体系消歧（见 §5.5 DEFERRED）。

---

### 5.3 Unknown facts（honest）

| ID | 未知 | MVP 处理 |
|---|---|---|
| U1 | bge-m3 输出维度 | **Integration 门禁**：须 `dim==1024`；否则 **HALT**；**不改** ES mapping |
| U2 | F9 vs F10 token 冲突 | 不猜测；MVP 可依赖 API 400 拒绝超长 + 最小字符 guard（**非**精确 tokenizer） |
| U3 | Retry-After | 不使用 |

---

### 5.4 MVP MUST contract（DEV-007 须实现；OI-012 写入规格）

| # | Contract |
|---|---|
| M1 | 保留 `EmbeddingClient` Protocol |
| M2 | `SiliconFlowEmbeddingClient`：`POST /v1/embeddings`，model=`BAAI/bge-m3`，**httpx**（无 SDK） |
| M3 | `SILICONFLOW_API_KEY`：`SecretStr`；禁止真实 key 入 git/logs/tests |
| M4 | 默认 provider：`memory_retrieval.embedding_provider=siliconflow` |
| M5 | local TEI：保留现有代码/历史/OI-011 contract；**不** delete/refactor/**不** fix TEI 429 **本 MVP** |
| M6 | Batch：`input: list[str]`；**每 HTTP 请求 max 32 条** |
| M7 | Response 校验：`data` 存在；按 `index` 排序；条数匹配；**每向量 dim==1024**；Integration ≠1024 → **HALT**（不改 ES mapping） |
| M8 | HTTP：400/401/403 **fail-fast**；429/5xx/timeout **有界重试**：**1 次初始 + 最多 2 次重试 = 最多 3 次 HTTP attempt**；简单指数退避；**无**完整 retry 框架 |
| M9 | Observability **最小**：`provider`、`status_code`、`trace_id`（若有）、bounded sanitized error；**禁止** key/auth/全文/vectors |
| M10 | 测试：默认 CI = unit + mocked HTTP contract（success、batch 32、ordering、wrong dim、count mismatch、401、429 exhausted、500 retry、timeout、secret redaction）；真实 SiliconFlow = **opt-in smoke**（显式 API key） |
| M11 | Integration gate（opt-in）：一次证明 success + dim==1024 + 短 batch；**无** cross-provider float equality |

**空字符串：** 任一 `text==""` → Client 拒绝；**零** HTTP 调用（两 provider 同等语义；DEV-007 实现 SiliconFlow 路径）。

**Token 超长（MVP 诚实策略）：** **不** 引入本地 HF tokenizer（DEFERRED）。MVP 可：(a) 最小字符长度 guard（非精确 token）；(b) 依赖 API 400。规格须写明 **非** TEI `/tokenize` 级精确校验；EXT/RET 精确 1024 token 路径 **DEFERRED** 至后续任务。

---

### 5.5 DEFERRED items（显式 OUT OF SCOPE）

| ID | 项 | 理由 |
|---|---|---|
| D1 | DEV-008 / DEV-009 拆分 | 合并为单一 **DEV-007** |
| D2 | TEIEmbeddingClient refactor | 保留现状；PR #13 不动 |
| D3 | TEI HTTP 429 修复 | 非 SiliconFlow MVP |
| D4 | TEI compose / Preflight / §3.3 大规模改写 | TEI optional 仅叙事；infra 保持 |
| D5 | OI-011 contract 变更 | 冻结 |
| D6 | 本地 HF tokenizer 体系 | MVP 不建 |
| D7 | Provider 热切换 | 后续 |
| D8 | Index 重建系统 | 后续 |
| D9 | Cross-provider cosine benchmark | 后续 |
| D10 | 大型 metrics / observability redesign | MVP 仅 M9 最小集 |
| D11 | STM/EXT/RET 业务接线 | 后续 |
| D12 | ES mapping 变更 | 禁止 |
| D13 | §3.x 大段重写 | OI-012 最小句 only |
| D14 | DEV-006 worktree / PR #13 extract-close-rewrite | 决策 deferred |
| D15 | Amendment 001 的 B1–B9 全量 master_plan retarget | 简化为 DEV-006 SUPERSEDED_FOR_MVP + DEV-007 + 最小 EXT/RET 前置 |
| D16 | Amendment 001 retry 4 attempts | **Superseded**：M8 = **3 attempts** |

---

### 5.6 Minimal spec changes（Phase A 白名单内容）

**仅修改必要章节：**

| 章节 | 最小改动 |
|---|---|
| **§3.1** | Embedding 默认 = SiliconFlow 托管 API；TEI = 可选自托管 |
| **§2.2.14** | `embedding_provider: siliconflow`（默认）；`local_tei` 保留枚举 |
| **§3.8** | `SILICONFLOW_API_KEY`（SecretStr；仅 siliconflow 必填） |
| **§3.10** | 新增/修订 **最小 pivot 段**：默认 hosted SiliconFlow `BAAI/bge-m3`；dim=1024；TEI optional & non-MVP-blocking；**provider-specific batch limits**（SiliconFlow **32**/request；TEI **64**/request，各自 Contract 内分片）；指向 DEV-007 实现 Contract（M1–M11） |
| **§2.2.6** | 增补 `SiliconFlowEmbeddingClient` 一句 + `EmbeddingClient` 仍为唯一业务边界；**不** 重写 TEI 规则 |

**明确不改（DEFERRED）：** §3.3 服务列表字面、§3.18 Preflight、§3.2 大段、ES mapping、错误码/状态机。

---

### 5.7 DEV-006 / PR #13 disposition（record only）

| 项 | 状态 | 说明 |
|---|---|---|
| DEV-006 | **PAUSED / SUPERSEDED_FOR_MVP** | 槽位让位于 **DEV-007**；原计划文件保留只读 |
| PR #13 | **OPEN / DO_NOT_MERGE** | **不得** merge/close/rewrite/extract **本 MVP** |
| 决策时机 | **Deferred** | SiliconFlow MVP 路径（DEV-007 Integration gate PASS）验证后再议 PR #13 |
| Worktree | **禁止访问** | 含 uncommitted Amendment 003/004 的 DEV-006 worktree |

---

### 5.8 Single downstream DEV task — **DEV-007**

```yaml
task_id: DEV-007
task_name: "SiliconFlow Embedding Client MVP"
status: planned  # Task Plan 待 OI-012 merged 后编写
prerequisites:
  - "OI-012 completed（Spec-OI merged）"
  - "DEV-002, DEV-004, DEV-005 completed"
spec_sections:
  - "§2.2.6, §2.2.14, §3.8, §3.10（OI-012 已修订最小 Contract）"
scope:
  implement:
    - "EmbeddingClient Protocol + EmbeddingResult + errors（若 main 尚无）"
    - "SiliconFlowEmbeddingClient（httpx；M2–M8）"
    - "create_embedding_client factory（dispatch by memory_retrieval.embedding_provider）"
    - "Settings: embedding_provider default siliconflow; SILICONFLOW_API_KEY SecretStr; base_url"
    - "configs/base.yaml, .env.example（占位 key）"
    - "Unit + mocked HTTP contract tests（M10 全场景）"
    - "Opt-in Integration smoke（M11；无 key → skip）"
  local_tei_dispatch:
    behavior: "若 `embedding_provider=local_tei`：`create_embedding_client` **不得** 静默回退 siliconflow"
    mvp_outcome: "raise `NotImplementedError`（或 Settings 校验错误）；完整 TEI Client 实现 **DEFERRED**（PR #13 / 后续任务）"
    note: "规格保留 `local_tei` 枚举；MVP 默认 siliconflow 即可跑通 hosted 路径"
  explicit_non_goals:
    - "TEIEmbeddingClient refactor / TEI 429 / compose / preflight"
    - "STM/EXT/RET wiring"
    - "PR #13 merge or DEV-006 feat reuse"
    - "Local HF tokenizer"
    - "Large metrics redesign"
    - "local_tei 完整实现（本 DEV 仅 siliconflow 路径 + 显式 fail-fast）"
branch: "feat/DEV-007-siliconflow-embedding-client-mvp"
whitelist:
  - "src/memory_system/infrastructure/embedding/**"
  - "src/memory_system/settings/{models,validators}.py"
  - "configs/base.yaml"
  - "configs/development.yaml"
  - "configs/test.yaml"
  - ".env.example"
  - "tests/unit/test_siliconflow_embedding*.py"
  - "tests/contract/test_siliconflow_embedding_client_contract.py"
  - "tests/contract/helpers/siliconflow_fake.py"
  - "tests/integration/test_siliconflow_embedding_client_integration.py"
  - "02_开发管理/tasks/DEV-007-siliconflow-embedding-client-mvp.md"
  - "02_开发管理/progress.md"
  - "02_开发管理/master_plan.md"
blacklist:
  - "compose*.yaml, scripts/**, versions.*"
  - "feat/DEV-006-*, PR #13"
  - "STM/EXT/RET src/**"
  - "ES migrations"
acceptance_gate:
  - "Mocked contract tests green in default CI"
  - "Opt-in Integration: dim==1024 or HALT report"
  - "No real API key in git"
```

---

### Step A1 — Phase A Spec（OI-012 实施）

- 文件：`01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`
- 范围：**仅** §5.6 最小改动
- **不**改 §3.3 / §3.18 字面

### Step B1 — Phase B 治理（OI-012 实施）

- `open_issues.md`：OI-012 → resolved（追加决议）
- `master_plan.md` **最小**更新：
  - DEV-006 → `paused / SUPERSEDED_FOR_MVP`
  - 登记 **DEV-007**（移除 DEV-008/009 占位）
  - §2 归属：`DEV-007 → SiliconFlow Embedding Client MVP（EXT-007 与 Retrieval 共享前置）`
  - EXT-007 前置：`DEV-007` 替换 `DEV-006`
  - RET-001 前置：`DEV-004, DEV-007`（BM25 可不调用 embed）
  - RET-002 前置：`RET-001, DEV-007`
  - `v0.1.0-bootstrap`：含 **DEV-007**（非 DEV-006）
- `progress.md`：OI-012 completed → `next_action` DEV-007 规划

---

## 6. 文件变更清单

### OI-012 Spec-OI 白名单

| 文件 | 创建/修改 | 目的 |
|---|---|---|
| `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` | 修改 | §5.6 最小 spec pivot |
| `02_开发管理/tasks/OI-012-siliconflow-embedding-provider-spec-oi.md` | 修改 | 本计划 |
| `02_开发管理/open_issues.md` | 修改 | OI-012 决议 |
| `02_开发管理/master_plan.md` | 修改 | 最小 DEV-006/007 retarget |
| `02_开发管理/progress.md` | 修改 | 状态机 |

### OI-012 黑名单

`src/**`、`tests/**` 实现、`compose*`、`scripts/**`、DEV-006 feat、PR #13、`.env` 真实 key。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 适用 | Phase A 最小 spec 句 + Phase B 治理同 PR |
| 幂等 | 适用（API 只读） | SiliconFlow embed 同输入应稳定 |
| 并发 | 适用 | 共享 httpx；DEV-007 实现无批间可变状态 |
| 版本冲突 | 不适用 | 无持久化 embedding 版本 |
| 用户隔离 | 不适用 | |
| 部分失败 | 适用 | 子批失败 → 整次 embed 失败 |
| 进程异常恢复 | 不适用 | |

---

## 8. 测试计划

### OI-012（Spec-OI）

无代码测试。验收 = 规格最小修订 + 治理闭合。

### DEV-007（M10 默认 CI — mocked）

| 场景 | 预期 |
|---|---|
| 成功 1 条 | 1024 维；ordering 正确 |
| batch 32 | 单次 HTTP；33 条拆 2 请求 |
| wrong dim | `EmbeddingValidationError` |
| count mismatch | 拒绝 |
| 401 | fail-fast；无重试 |
| 429 ×3 attempts | 第 3 次仍失败 → error |
| 500 → retry → success | ≤3 attempts |
| timeout | 有界失败 |
| secret redaction | 日志/异常无 key |
| 空字符串 | 零 HTTP |

### DEV-007（M11 opt-in Integration）

| 场景 | 预期 |
|---|---|
| 短 batch embed | success；**dim==1024** |
| dim≠1024 | **HALT**；报告；不改 ES mapping |
| 无 `SILICONFLOW_API_KEY` | skip |

### E2E

不适用（OI-012 / DEV-007 MVP）。

---

## 9. 验收标准

- [x] Amendment 002/002.1 已吸收；scope = **minimal MVP pivot**
- [x] git HEAD SHA = **`c8c03db4b984a1e65b7d2d46b392f87a938c8eec`**（无混缀）
- [x] §5.4 M1–M11 写入规格（Phase A 后；§3.10.0）
- [x] §5.5 DEFERRED 清单完整；**无** DEV-008/009
- [x] **单一** downstream **DEV-007** 定义含 whitelist/blacklist
- [x] DEV-006 = **PAUSED/SUPERSEDED_FOR_MVP**；PR #13 = **DO_NOT_MERGE**（仅记录）
- [x] Retry = **1 + 2 = max 3 HTTP attempts**（非 Amendment 001 的 4）
- [x] **无** local tokenizer proposal；**无** §3.3/§3.18 大规模改写
- [x] master_plan **最小** retarget（非 B1–B9 全量）
- [x] **未** PLAN_LANDING；**未**改 `src/**`；**未**碰 DEV-006 feat
- [ ] Review 无 P0/P1

---

## 10. 风险与阻塞项

| 风险 | 缓解 |
|---|---|
| U1 dim unknown | Integration gate；HALT 不改 mapping |
| MVP 无精确 token 计数 | 规格诚实标注；EXT token 路径 DEFERRED |
| PR #13 误 merge | DO_NOT_MERGE 三重记录 |
| Scope creep | DEFERRED 清单 + 单一 DEV-007 |

---

## 11. Git 计划

```yaml
branch: "feat/OI-012-siliconflow-embedding-provider-spec-oi"
workflow_mode: NORMAL
note: "Amendment 002/002.1 — **本轮不 PLAN_LANDING**；规划态治理文件保持工作区未 commit；待 PLAN_APPROVED 后由人类/Release 触发 PLAN_LANDING"
expected_commits:
  PLAN_LANDING: "（非本轮）main 上 docs(plan) + 创建 exact feat 分支"
  IMPLEMENTATION_RELEASE:
    - "feat/OI-012-* 上 docs(spec): minimal pivot default embedding to siliconflow"
    - "feat/OI-012-* 上 docs(governance): OI-012 open_issues/master_plan/progress 回写"
    - "禁止 main 上 IMPLEMENTATION commit；禁止 force push"
  POST_MERGE_CLEANUP: "PR MERGED 后 main docs(status): complete"
out_of_scope_changes:
  - "src/**, tests/** 实现"
  - "DEV-006 feat, PR #13"
  - "compose/scripts"
  - "本轮任何 git add/commit/push"
```

---

## 12. Plan Amendment

### Amendment 001 — Plan Remediation Round 1

```yaml
date: "2026-08-09 05:45 UTC"
trigger: "Round 1 MUST_FIX=3 + SHOULD_FIX=6"
status: superseded_partially_by_amendment_002
note: "MF-1 git 前提仍有效；MF-2 §3.3 大规模改写、MF-3 B1–B9 全量 retarget → Amendment 002 DEFERRED/简化"
```

### Amendment 002 — MVP_SIMPLIFICATION

```yaml
amendment_id: Amendment-002
date: "2026-08-09 06:00 UTC"
trigger: "用户显式 directive — Reduce OI-012 to minimal MVP Provider Pivot"
status: pending_plan_review
affects_technical_spec: true
```

#### Reduced scope summary

- **Goal**：仅「默认 Embedding → SiliconFlow BAAI/bge-m3」；**不** one-shot 重构 embedding 架构。
- **Downstream**：**DEV-007 单一任务**；移除 DEV-008/009。
- **Spec**：§3.1 / §2.2.14 / §3.8 / §3.10 / §2.2.6 最小句；**DEFERRED** §3.3/§3.18 大改。
- **Retry**：**1 initial + 2 retries = max 3 HTTP attempts**（撤销 A001 的 4）。
- **Token**：**DEFERRED** local HF tokenizer；MVP 诚实策略见 §5.4。
- **DEV-006/PR#13**：PAUSED/SUPERSEDED_FOR_MVP + DO_NOT_MERGE；决策 deferred。
- **PLAN_LANDING**：**本轮禁止**。

#### Exact files

| 层 | 文件 |
|---|---|
| OI-012 | 规格最小节；本 Task Plan；open_issues；master_plan（最小）；progress |
| DEV-007 | 见 §5.8 whitelist |

#### Deferred items

见 §5.5 D1–D16。

#### DEV-006 / PR #13

见 §5.7（record only）。

### Amendment 002.1 — Round 2 Plan Remediation

```yaml
amendment_id: Amendment-002.1
date: "2026-08-09 06:15 UTC"
trigger: "Round 2 MUST_FIX=1（MF-1 corrupted HEAD SHA）+ SHOULD_FIX=4"
status: pending_plan_review
```

| ID | 修复 |
|---|---|
| **MF-1** | `latest_commit` / git 前提：`c8c03db97b0373579a91e620fcdef90976193c8c`（混缀）→ **`c8c03db4b984a1e65b7d2d46b392f87a938c8eec`**（`git rev-parse HEAD` 验证） |
| **SF-1** | `master_plan.md` OI-012 `spec_sections` 对齐最小节（§2.2.6/§2.2.14/§3.1/§3.8/§3.10；移除 §3.2） |
| **SF-2** | DEV-007 §5.8：`local_tei` → `NotImplementedError` 或 Settings 校验错误；完整 TEI 实现 DEFERRED |
| **SF-3** | §3.10 pivot 句补充 provider batch limits：SiliconFlow 32、TEI 64 |
| **SF-4** | §11 Git 计划：明确本轮不 PLAN_LANDING；IMPLEMENTATION_RELEASE 仅在 feat 分支 commit |

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-09 05:30 UTC | Planner 初版 | 创建计划；治理规划态 | 无 | 未实施 |
| 2026-08-09 05:45 UTC | Amendment 001 | MF-1～3 + SF-1～6 | 无 | 待 Round 2 |
| 2026-08-09 06:00 UTC | Amendment 002 | MVP 简化；单一 DEV-007；DEFERRED 清单；retry=3 | 无 | **不 PLAN_LANDING**；待 Round 2 审查 |
| 2026-08-09 06:15 UTC | Amendment 002.1 | MF-1 HEAD SHA 修正；SF-1～4 | 无 | **不 PLAN_LANDING**；待 Round 2 复审 |
| 2026-08-09 06:52 UTC | Round 3 PLAN_APPROVED | Amendment 002 MVP Simplification；BLOCKER=0；MUST_FIX=0 | 无 | 进入 Developer 实施 |
| 2026-08-09 06:55 UTC | Phase A Spec | §3.1/§2.2.14/§3.8/§3.10.0/§2.2.6 最小 pivot | grep 一致性 | 未改 §3.3/§3.18 |
| 2026-08-09 06:55 UTC | Phase B 治理 | open_issues OI-012 resolved；master_plan/progress 回写 | 无 | `plan_commit=e122c8a` |
| 2026-08-09 07:00 UTC | Code Review | P0=0；P1=0；CODE_REVIEW_APPROVED | grep 一致性复核 | 无 |
| 2026-08-09 07:05 UTC | IMPLEMENTATION_RELEASE | docs(spec) + docs(governance) 双 commit；PR 创建 | 无 | `plan_commit=e122c8a` 可追溯 |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` | §3.1/§2.2.14/§3.8/§3.10.0/§2.2.6 最小 pivot |
| `02_开发管理/open_issues.md` | OI-012 → resolved + Amendment 002.1 决议 |
| `02_开发管理/master_plan.md` | DEV-006 SUPERSEDED；DEV-007 §2.2.14；OI-012 tested |
| `02_开发管理/progress.md` | in_progress → tested；plan_commit=e122c8a |
| `02_开发管理/tasks/OI-012-siliconflow-embedding-provider-spec-oi.md` | 本计划回写 |

### 与原计划的差异

无 scope 偏差；严格按 Amendment 002/002.1 最小 pivot 实施。

### 测试结果

Spec-OI 无代码测试；grep 一致性验证通过（默认 siliconflow、batch limits、retry=3、无 DEV-008/009）。

### Review 结果

```yaml
p0: 0
p1: 0
review_report: null
plan_review_round_1: "PLAN_REJECTED（MUST_FIX=3）"
amendment_002: "absorbed"
amendment_002_1: "absorbed"
plan_review_round_2: "PLAN_REJECTED（MUST_FIX=1；SHOULD_FIX=4）"
plan_review_round_3: "PLAN_APPROVED（BLOCKER=0；MUST_FIX=0）"
code_review: CODE_REVIEW_APPROVED
```

### Git 记录

```yaml
branch: feat/OI-012-siliconflow-embedding-provider-spec-oi
plan_commit: e122c8ab840720a4f86cffda5a58e5f9e6f34944
implementation_commit: null
```

### 最终状态

`committed`

---

## 15. Planner 摘要（Orchestrator 用）

- **OI-012** = **minimal MVP Spec-OI** only（默认 SiliconFlow BAAI/bge-m3；dim=1024；TEI optional/non-blocking）
- **Downstream** = **single DEV-007**（SiliconFlow client + settings + mocked tests + opt-in integration）
- **DEFERRED** = TEI refactor, compose/preflight rewrite, tokenizer, DEV-008/009, PR#13 decision, large §3.x rewrites
- **DEV-006** = PAUSED/SUPERSEDED_FOR_MVP；**PR#13** = DO_NOT_MERGE
- **Retry** = max **3** HTTP attempts；**No PLAN_LANDING** this round
- **Honest gap** = no precise token count for SiliconFlow MVP
