# Memory System MVP Master Plan

## 1. 文档用途

本文件记录整个 MVP 的阶段、任务、依赖和里程碑。

规则：

1. 技术规格以 `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` 为准。
2. AI 可以补充任务细节，但不得删除规格要求或改变技术路线。
3. 每个任务必须足够小，原则上可以由一个独立 Feature Commit 完成。
4. 每个任务开始前必须创建单独 Task Plan。
5. 任务状态统一为：

```text
planned
→ approved
→ in_progress
→ implemented
→ tested
→ reviewed
→ committed
→ completed
```

6. 双口令门禁：`PLANNING_DOCS_APPROVED` 仅允许更新开发管理文档；`PLAN_APPROVED` 仅用于独立 Reviewer 批准当前 Task 实施。未收到对应口令不得越权。
7. 规格歧义统一记录在 `02_开发管理/open_issues.md`；未解决前不得自行解释为新 Contract。

---

## 2. 强制归属规则

```text
DEV-004  → ES 版本化 Index + Mapping + Alias（唯一创建方）
DEV-007  → SiliconFlow Embedding Client MVP（EXT-007 与 Retrieval 共享前置；OI-012 后）
DEV-006  → TEI Embedding Client（PAUSED / SUPERSEDED_FOR_MVP；PR #13 DO_NOT_MERGE）
EXT-007  → 仅 Retrieval Document 同步；不创建/修改 Mapping 或 Alias
RET-001  → 仅 BM25 查询；Integration 使用 ES Fixture；不硬依赖 EXT-007
RET-006  → E2E 验证 EXT-007 同步结果可被 BM25/检索链路消费
```

应用代码落在**仓库根目录**（规格 §3.4 的 `memory-system/` 为仓库根概念名）。巩固进程以 §3.2 为准：独立容器 `memory-consolidation-worker`。

---

## 3. 开发阶段

### Phase 0：工程基础

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| DEV-001 | 项目骨架、依赖与质量工具 | §3.4, §3.5, §3.2, §3.28 | 无 | completed |
| DEV-002 | 配置系统与 `.env.example` | §3.8, §3.30 P1 | DEV-001 | completed |
| DEV-003 | Docker Compose、Embedding 服务、Preflight | §3.3, §3.10–3.18 | DEV-002 | completed |
| DEV-003-002 | TEI CPU Memory Contract Validation（Preflight Hardening） | §3.10.3, §3.10.8, §3.18 #12 | DEV-003 | completed |
| OI-011 | BAAI/bge-m3 CPU TEI Memory Contract（Spec-OI） | §3.10.3, §3.10.8, §3.18 #12 | DEV-003-002 | completed |
| OI-012 | SiliconFlow Embedding Provider（Spec-OI） | §2.2.6, §2.2.14, §3.1, §3.8, §3.10 | OI-011 | completed |
| DEV-004 | Migration Runner；含 ES Mapping + Alias | §3.12, §3.26, §2.2.4 | DEV-003 | completed |
| DEV-005 | 通用 API 壳、鉴权、Request ID、日志与指标 | §3.7, §3.21, §3.23, §3.27 | DEV-002 | completed |
| DEV-006 | TEI Embedding Client + Token Budget（共享） | §3.2, §3.10, §2.2.6 | DEV-003, DEV-003-002, OI-011 | paused / SUPERSEDED_FOR_MVP |
| DEV-007 | SiliconFlow Embedding Client MVP | §2.2.6, §2.2.14, §3.8, §3.10 | OI-012, DEV-002, DEV-004, DEV-005 | completed |

### Phase 0 补充：开发工作流自动化（非业务规格）

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| DEV-OPS-001 | Cursor Agent 工作流自动化（项目级 Slash Commands） | 非业务：对齐治理与 `03_AI_Prompts` 角色流程 | DEV-001 | completed |
| DEV-OPS-002 | Cursor Orchestrator、可复用 Subagents 与受控 Release Automation | 非业务：扩展 DEV-OPS-001；官方 Subagents / permissions | DEV-OPS-001 | completed |
| DEV-OPS-003 | NORMAL / STRICT 工作流模式；减少常规人工机械门禁 | 非业务：扩展 DEV-OPS-002；保留六 Subagent 与唯一 Git 写角色 | DEV-OPS-002 | completed |
| DEV-OPS-004 | 本机 Mihomo 网络回退策略文档（AI 工作流） | 非业务：全局开发规则 + 契约测试；不改规格/业务代理 Contract | DEV-OPS-003 | completed |
| DEV-OPS-005 | 人类 Prompt Playbook 与 Recovery 操作手册 | 非业务：人类日常操作手册 + 契约测试；不改 Orchestrator/mode/业务 | DEV-OPS-003, DEV-OPS-004, DEV-004 | completed |
| DEV-OPS-006 | Phase 0 Baseline Hygiene Before STM-001 | 非业务：unit compose-wrapper allowlist + progress DOC_CODE_DRIFT hygiene | DEV-007, OI-011 | completed |
| DEV-OPS-007 | Phase 1 Baseline Hygiene Before STM-006 | 非业务：STM-005 orphan SHA metadata 更正 + Ruff E501 torn-read helper 换行 | STM-005 | completed |
| DEV-OPS-008 | Compose test-stack runtime compatibility (aiokafka 0.13 + ES 9.4 mapping API) | 非业务：C1 runtime kafka readiness + C2 ES mapping readback compat；blocks STM-013 | STM-010 | tested |
| DEV-OPS-009 | Restore authoritative Kafka LZ4 runtime support for memory-api test/runtime image | 非业务：cramjam 生产依赖闭合权威 lz4；unblocks DEV-OPS-008 authoritative validation | main | completed |

#### DEV-OPS-009 Restore authoritative Kafka LZ4 runtime support for memory-api test/runtime image

- **目标**：在保持权威 `kafka_producer.compression_type=lz4` 前提下，补齐 aiokafka 0.13 LZ4 后端（`cramjam>=2.8`），使 memory-api runtime/test 镜像内 `AIOKafkaProducer` 可初始化、lifespan 可启动、`/health/ready` 可达且可向 test Kafka 真实发送 lz4 记录。
- **根因**：**A** — `pyproject.toml`/`uv.lock` 仅声明 `aiokafka>=0.13,<0.14`，未安装 aiokafka `lz4` extra 解析的 `cramjam`；Dockerfile runtime 完整复制 `.venv`，非 stage 遗漏。
- **非目标**：改 gzip/null 压缩；修改 `configs/base.yaml`；吸收 DEV-OPS-008 C1/C2；修改 STM-006/PR #30；merge PR #30/#31。
- **阻塞关系**：**blocks DEV-OPS-008 authoritative-runtime validation**；**blocks STM-013**（lz4 维度）；merge 顺序：DEV-OPS-009 → DEV-OPS-008 revalidate/merge → STM-013 sync main → E1–E4 → new Code Review。
- **关键修复**：`pyproject.toml` 追加 `cramjam>=2.8,<3` + `uv lock`；lz4 codec/producer init 单测 + Kafka lz4 发送集成测。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-009-kafka-lz4-runtime-support.md`
- **插入说明**：用户显式 NEW_TASK；`workflow_mode=NORMAL`（explicit）；分支必须从 **main** 创建（NOT feat/STM-013；NOT feat/DEV-OPS-008）。
- **状态备注**：`completed`（plan_commit `8367e7b6953fe6776d35865375a9aa48b02877f0`；implementation `90cd79cbc7235cc444b8ff67357a4d229399af1f`；PR #32 MERGED `f754db8a9b406f62180f33d8a09e412ccc7c605b` mergedAt `2026-08-11T09:36:27Z`；cramjam>=2.8,<3 + lz4 unit/integration tests；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；`workflow_mode=NORMAL`；feat 分支待删）；**unblocks DEV-OPS-008 authoritative-runtime validation**；STM-013 lz4 维度 SATISFIED。

#### DEV-OPS-008 Compose test-stack runtime compatibility (aiokafka 0.13 + Elasticsearch 9.4 mapping API)

- **目标**：修复 compose test stack 上 `memory-api` lifespan/readiness 与 pinned **aiokafka 0.13.0** / **Elasticsearch 9.4.4** 不兼容（C1 `bootstrap_connected` AttributeError；C2 `element_type` GET mapping 省略导致 `assert_mapping_compatible` ValueError）；**SOURCE-ALIGNED fresh image** 可审计验证。
- **根因**：C1 — aiokafka 0.13 移除 `AIOKafkaClient.bootstrap_connected`；C2 — ES 9.4 GET mapping 省略默认 `element_type`。
- **非目标**：修改 `MEMORY_RETRIEVAL_V1_MAPPINGS` CREATE schema；Kafka producer 配置/生命周期/STM-006 publish；`tests/e2e/**`；merge PR #30；DEV-006/PR#13。
- **阻塞关系**：**blocks STM-013**（`release_gate=BLOCKED_BY_DEFECT_FIX`；PR #30 OPEN MUST NOT MERGE）。
- **关键修复**：`runtime.py` hasattr guard + start() fallback；`assert_mapping_compatible` element_type 仅双方非 None 且不等时 fail-closed（prototype 975e6029 evidence）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-008-compose-test-stack-runtime-compatibility.md`
- **插入说明**：用户显式 NEW_TASK；`workflow_mode=NORMAL`（explicit）；分支必须从 **main @ 390af52** 创建（**NOT** feat/STM-013）；STM-013 保持 blocked。
- **状态备注**：`planned` — `next_action=计划审查`；**不得自动开始实施**；**不得 merge PR #30**。

#### DEV-OPS-007 Phase 1 Baseline Hygiene Before STM-006

- **目标**：进入 STM-006 前最小 hygiene——STM-005 `status_record_completed` 与 main lineage 对齐（`b0736431…`）；修复 2 处 pre-existing Ruff E501（`context_read_torn_read_helpers.py` L174–175）；全仓 Ruff PASS；STM-004 torn-read Integration 回归。
- **根因分类**：**A**（治理 metadata 漂移：orphan SHA `301c8d9…` 不在 main 血统）；**B**（pre-existing E501 格式化-only）。
- **非目标**：实现 STM-006；改 STM-005/004 `src/**`；resurrect/cherry-pick orphan；修改 torn-read 并发语义；操作 DEV-006/PR#13。
- **关键修复**：`progress.md` + STM-005 Task Plan §14 将 `status_record_completed` 更正为 `b0736431a636f0ba20a9cf5aad61a2ea8dc365df`；`tests/integration/context_read_torn_read_helpers.py` 换行（零语义变更）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-007-phase1-baseline-hygiene-before-stm006.md`
- **插入说明**：用户显式 START_NEW_TASK；`workflow_mode=NORMAL`（explicit）；STM-006 仍 **READY_FOR_PLANNING only**（不得标 in_progress）。
- **状态备注**：`completed`（plan_commit `f42eaf3190d8fc3600f52c869fc7e8dfbec86cf1`；implementation `1ef8932b87604de9a01dab72e7584a4e7886b155`；record `c48a70d`；PR #24 MERGED `de95f3a2f0107f791f89441177841754b1d4f82c` mergedAt `2026-08-10T11:54:41Z`；orphan SHA metadata 更正 → `b0736431a636f0ba20a9cf5aad61a2ea8dc365df`；Ruff E501 L174–175 换行；ZERO_STALE_AUTHORITATIVE_REFERENCES PASS；FULL_RUFF PASS；integration 14 / unit 323 / contract 68；mypy PASS；`DEV-OPS-007_CHANGED_BEHAVIOR=false`；production `src/**` changes none；`workflow_mode=NORMAL`；feat 分支待删）；**STM-006 READY_FOR_PLANNING only**（不得自动开始规划或实施）。

#### DEV-OPS-006 Phase 0 Baseline Hygiene Before STM-001

- **目标**：进入 STM-001 前最小 hygiene——unit/contract/ruff/mypy baseline 全绿；`progress.md` 治理 metadata 与 main HEAD 一致；修复 `test_no_bare_docker_compose_outside_wrapper`（OI-011 probe 路径）。
- **根因分类**：**A**（批准的 characterization wrapper exception；contract test 缺 exact-path allowlist）。次因：`measure_tei_memory.sh` 为 usage comment 命中（C-like），修复仍走 A。
- **非目标**：实现 STM-001；改 SiliconFlow/TEI 12g/`compose*.yaml`；操作 DEV-006/PR#13；启停 TEI；infrastructure redesign。
- **关键修复**：仅在 `tests/unit/test_compose_wrapper_contract.py` 对 `scripts/preflight/lib_tei_probe.sh` 与 `scripts/diagnostics/measure_tei_memory.sh` 做 exact-path/exact-purpose allowlist；禁止删测/skip/全局放宽。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-006-phase0-baseline-hygiene-before-stm001.md`
- **插入说明**：用户显式 NEW_UNPLANNED_FEATURE；`workflow_mode=NORMAL`（explicit）。
- **状态备注**：`completed`（implementation_commit `b9f049af59d0e904ebee0ce09df13cc383a91b52`；record `6de3f6ac3acd804df1831dcb58a0b3d1ebecf42f`；PR #18 MERGED `3e727b3dc1a168863d7fa6e8d52a175d36de4644`；completed 治理 `7abde48af72ea2d676deed64e1333f3e55d08a51`；plan_commit `09b045be1429716eab184e4565beb30cf2856b28`；baseline GREEN；Phase 0 completed；STM-001 READY_FOR_PLANNING；unit 216 / contract 47 / ruff PASS / mypy PASS；`workflow_mode=NORMAL`；**不得启动 STM-001 实施**）。

#### DEV-OPS-005 Human Prompt Playbook and Recovery Operations Manual

- **目标**：新建权威人类操作手册 `03_AI_Prompts/01_项目日常操作手册.md`（文首「我以后只需要记住什么？」；六模板；规则 A–E），使会话历史不可用时人类仍能继续项目；强制静态契约 `tests/unit/test_project_operations_playbook_contract.py`。
- **非目标**：开始 DEV-005 实施；改 Orchestrator / NORMAL·STRICT 实现；扩大 permissions；改 migrate/compose/Dockerfile/agents；业务 `src/**`；全文复制 Mihomo §18。
- **关键设计决策**：单一人类权威 Playbook（与 `00_全局开发规则.md` 职责分离；网络细节仅引用 §18）；可选 README 短发现指针；真实 mode 缺陷记 follow-up 不改语义。
- **变更文件（预期）**：`03_AI_Prompts/01_项目日常操作手册.md`；`tests/unit/test_project_operations_playbook_contract.py`；可选 `README.md`；本任务开发管理回写。
- **测试**：强制静态契约（存在性 + 六模板 + 规则 A–E + NORMAL 两门禁/禁令/recovery invariants）；无真实 Integration/E2E；ruff/mypy/既有 unit 保持通过。
- **验收**：手册与契约通过；未越权；完成后 `next_action`→DEV-005 规划；**本任务期间不得启动 DEV-005 实施**。
- **插入说明**：**人工显式插入**于 DEV-005 业务规划/实施之前（用户覆盖先前「进入 DEV-005」的 next_action）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-005-human-prompt-playbook-recovery-operations.md`
- **状态备注**：`completed`（implementation_commit `373cd331313e02d053a6b49af11beaa7be02acbc`；committed 治理 `239218432d6b86d4f34d24c248611361df5d5069`；PR #11 MERGED `0239c28281949bedec66dbec1412197c5561a611`；plan_commit `a601a3b`；`workflow_mode=NORMAL`（explicit）；POST_MERGE_CLEANUP 本轮；**下一业务任务 = DEV-005**）。

#### DEV-OPS-004 本机 Mihomo 网络回退策略（AI 面向）

- **目标**：在 `03_AI_Prompts/00_全局开发规则.md` 写入本开发主机 Mihomo 网络回退策略（Docker 行为、诊断分类、健康检查、active/inactive 动作、Never、有界重试、安全边界），使 Orchestrator/Subagents 可自主处理外部网络失败；强制静态契约测试。
- **非目标**：开始 DEV-004；改业务代码/规格 §3.15 / Compose / `.env.example`；改 Mihomo runtime、`/opt/mihomo`、Docker daemon、7890 SSH forwarding；扩大 permissions；新增第二份 ops 文档。
- **关键设计决策**：单一权威源 = 全局开发规则（**不**另增 ops/runtime 文档）；本机 `17890` 与规格字面 `7890` 共存声明（不改 Contract）。
- **环境前提（非机密）**：`mihomo.service`；mixed `127.0.0.1:17890`；controller `127.0.0.1:19090`；Docker daemon 已永久代理至 17890；7890 为 SSH/sshd forwarding（非空闲、非 Mihomo）。
- **变更文件（预期）**：`03_AI_Prompts/00_全局开发规则.md`；`tests/unit/test_mihomo_network_fallback_contract.py`；本任务开发管理回写。
- **测试**：强制静态契约（存在性 + 必含子串；含全部分类码与非 proxy 误判守卫）；无真实基础设施 Integration/E2E；ruff/mypy/既有 unit 保持通过。
- **验收**：策略 1–8 落入全局规则；契约通过；未越权；完成后 `next_action`→DEV-004 规划；**本任务期间不得启动 DEV-004**。
- **插入说明**：**人工显式插入**于 DEV-004 业务规划之前（用户覆盖先前「进入 DEV-004」的 next_action）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-004-mihomo-network-fallback-policy.md`
- **状态备注**：`completed`（implementation_commit `14550dfa8043eb5339b89f1c9f215ae368a6f58d`；committed 治理 `7d2a176170939eefe8a5c933b427021068541880`；PR #9 MERGED `1bc2f499d79301679f373d46c809f1f50e4dad66`；plan_commit `895d7aa`；`workflow_mode=NORMAL`（explicit）；POST_MERGE_CLEANUP 本轮；**下一业务任务 = DEV-004**）。

#### DEV-OPS-003 NORMAL / STRICT 工作流模式

- **目标**：引入 `NORMAL`（默认）与 `STRICT`（显式）两种工作流模式。NORMAL 常规人工门禁仅 `PLAN_APPROVED` + Human PR Merge；机械 Git 步骤由 Orchestrator 在批准转换点**自动调度** Release Operator（分 `PLAN_LANDING` / `IMPLEMENTATION_RELEASE` / `POST_MERGE_CLEANUP`）。STRICT 保留 DEV-OPS-002 行为。Release Operator **仍是唯一 Git 写 Subagent**；Orchestrator 自身不写 Git。
- **非目标**：开始 DEV-004；改业务代码/规格；webhook 自动 merge；Orchestrator 直接 Git 写；取消 Code Review / 测试门禁；删除六 Subagent 或五 fallback 命令；`gh pr merge` / force push / `git branch -D`。
- **关键设计决策**：最小变更保留 DEV-OPS-002 安全模型——Git 写权威仍集中于 Release Operator；NORMAL 仅减少「人工再次批准去调用 Release」的机械门禁。
- **变更文件（预期）**：`orchestrate-task.md`；`release-operator.md`（及最小 Agent 对齐）；治理窄例外两文件；`permissions.json` / `cli.json`；契约测试（含新建 modes contract）；本任务开发管理回写。
- **测试**：NORMAL/STRICT 合同；fail-closed negatives；既有 DEV-OPS-002 契约保持或有意修订并写 rationale；受监督冒烟（实施后）。
- **验收**：mode 声明；NORMAL 两门禁；STRICT 兼容；唯一 Git 写；异常 HALT；完成后 `next_action`→DEV-004；**本任务期间不得启动 DEV-004**。
- **插入说明**：**人工显式插入**于 DEV-004 业务规划之前（用户覆盖先前「不得插入 DEV-OPS-003」的 next_action）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-003-normal-strict-workflow-modes.md`
- **状态备注**：`completed`（implementation_commit `640616b`；committed 治理 `ec47b2a`；PR #7 MERGED `1189447d518b863d469150ead861e85fa5ca86b5`；plan_commit `d45ea2f`；complete 治理 `4e4ad19`；交付 NORMAL/STRICT 工作流模式；Step 7 受监督 NORMAL smoke **PASSED**（DEV-OPS-003-SMOKE PR #8 / merge `e14d71e` / POST_MERGE `45c74f8`）；正式任务自身提供 STRICT 正路径充分证据；正式 feat `feat/DEV-OPS-003-normal-strict-workflow-modes` 仍保留待人工删；**下一业务任务 = DEV-004**）。

#### DEV-OPS-002 Cursor Orchestrator、可复用 Subagents 与受控 Release Automation

- **目标**：建立长期 Memory System Orchestrator；用户提供 `TASK_ID` + 目标后，按状态机调用六个独立角色 Subagent；Orchestrator 只编排且 fail-closed；Release Operator 为唯一候选 Git 写角色（受控 add/commit/push/PR）；`completed` 后**立即**进入 DEV-002。
- **非目标**：改业务代码；实施期间改 DEV-002 业务范围；超级 Agent；自动 Merge / force push / 读 Secret；多任务并行调度；复杂嵌套 Subagent；本规划轮次创建 agents/权限文件；Phase B 排在 DEV-002 之前；插入 DEV-OPS-003。
- **变更文件（预期）**：`.cursor/commands/orchestrate-task.md`；六个 `.cursor/agents/*.md`；`.cursor/permissions.json`；CLI 权限文件；强制契约测试；**实施阶段**修订治理例外文件 `.cursor/rules/00-memory-system-governance.mdc` 与 `03_AI_Prompts/00_全局开发规则.md`（窄例外）；本任务开发管理回写。
- **测试**：静态契约（fail-closed / 退出码 / 角色隔离）；受监督低风险 E2E（全角色链路至 PR create；契约-only 不计）；人工 UI 冒烟。
- **验收**：角色隔离；Orchestrator 不批准/不自写状态；Release 门禁 + 真实退出码；E2E 通过后方可 tested+；`completed` → `next_action=DEV-002`。
- **Git 顺序**：独立 Review → `PLAN_APPROVED` → `approved` → 人工 `docs(plan)` on main → 创建 feat → Developer → Review → Release commit/push/PR → 人工 Merge → `completed` → **立即 DEV-002**。
- **风险**：IDE permissions 非安全边界；`git push` 前缀与 `--force`；结束标记非结构化协议（OI-OPS-006–013）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-002-cursor-orchestrator-subagents-release.md`
- **状态备注**：`completed`（implementation_commit `4943757`；治理 committed `3c63f77`；PR #4 merged `5886cc6`；`mergedAt=2026-08-07T07:11:20Z`；正式功能分支已删；E2E 证据分支保留；`status_record_commit_completed=null`；下一步 docs(status) complete + **立即 DEV-002**）。

#### DEV-OPS-001 Cursor Agent 工作流自动化

- **目标**：在 `.cursor/commands/` 建立五个项目级 Slash Commands（`plan-task` / `review-plan` / `develop-task` / `review-code` / `close-task`），减少长提示词粘贴；每命令内化角色约束、只读检查、可写范围、阶段验证与结束标记；禁止 Agent Git 写；保留五角色隔离；强制新增契约测试。
- **非目标**：改业务代码；改 DEV-001 既有测试语义；开始 DEV-002；改技术规格正文；Custom Modes；自动 Commit/Push/Merge；合并为超级 Agent；创建 `.cursor/skills/`；假设未证实的命令参数/自动角色切换。
- **变更文件（预期）**：五个 `.cursor/commands/*.md`；强制 `tests/unit/test_cursor_commands_contract.py`；本任务开发管理回写。
- **测试**：强制静态契约（存在性 + 最小必含子串 + 角色隔离）；人工 `/` 菜单冒烟；无业务 Contract/Integration/E2E。
- **验收**：白名单恰好五文件；结束标记互不混用；角色一一对应；状态机 `PLAN_APPROVED`→`approved`（不实施）→`/develop-task` 才 `in_progress`。
- **Git 顺序**：独立 Review → `PLAN_APPROVED` → `approved` → 人工 `docs(plan)` on main → 创建 `feat/DEV-OPS-001-cursor-workflow-commands` → Developer 实施。
- **风险**：Commands 为 beta；产品参数机制未证实（见 Task Plan OI-OPS-001–005）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-001-cursor-agent-workflow-commands.md`
- **状态备注**：`completed`。实现 Commit `69fabb7`；治理 committed `5d00a49`；PR #2 merged（`57800c3`）；completed 治理 Commit `5f34ccb`（`docs(status): complete DEV-OPS-001 after PR merge`）。

#### DEV-001 项目骨架、依赖与质量工具

- **目标**：**只创建 DEV-001 白名单内的 §3.4 目录与文件子集**（不宣称完成全部 §3.4 树）；`pyproject.toml` 依赖约束与 §3.5 完全一致，并含固定 `[build-system]`（`requires = ["uv_build>=0.11.32,<0.13"]`，`build-backend = "uv_build"`）；生成 `uv.lock`；ruff/mypy/pytest 可运行；三 Entrypoint **可安全 import**；通过子进程执行三个 `python -m memory_system.entrypoints.*`，未就绪时明确错误并以非零退出。
- **非目标**：完整 §3.4 树；`configs/`；Compose/Dockerfile/`versions.*`；Migration/Preflight/补发等具名脚本；`api/dependencies.py`、`middleware.py`、`error_handlers.py` 与业务路由；将 Build Backend 替换为非 `uv_build`；把 `uv_build` 写入运行时/quality/test 依赖组；伪造成功响应。
- **变更文件（预期）**：仅 Task Plan 白名单枚举路径（根元数据、包内 `__init__.py` 与三入口、`api/__init__.py` + `api/routes/__init__.py`、`scripts/__init__.py` + `scripts/migrations/__init__.py` + `scripts/preflight/.gitkeep`、`tests/unit/test_entrypoints_import.py`、`tests/unit/test_dependency_contract.py` 及测试目录占位）。禁止 `src/memory_system/**` / `scripts/**` 通配描述。
- **测试**：Unit import；三个 `-m` 子进程未就绪非零退出；`tomllib` 依赖契约（`requires-python == ">=3.12,<3.13"`；§3.5 三组依赖逐项一致 + **单独**断言 `[build-system]`，且 `uv_build` 不混入运行时依赖集合 + 无 Poetry/Pipenv/Conda 文件）；Contract/Integration/E2E 不适用真实基础设施。
- **验收**：白名单齐套且黑名单不存在；依赖与 build-system / requires-python 契约测试通过；`uv sync --locked`；ruff/mypy/pytest 通过；分阶段更新 progress/Task Plan 状态。
- **风险**：PRE-ENV-001/002；禁止 import 阶段抛 `SystemExit`/`NotImplementedError`；禁止偏离已决议的 `uv_build`。
- **计划文件**：`02_开发管理/tasks/DEV-001-project-skeleton.md`
- **状态备注**：`completed`。实现 Commit `9fbe899`；治理 `committed` 记录 Commit `753c4e4`；PR #1 merged（Merge Commit `a2673ac`）；completed 治理 Commit `740d821`（`docs(status): complete DEV-001 after PR merge`）已在 main 落盘。

#### DEV-002 配置系统与 `.env.example`

- **目标**：Pydantic Settings + YAML loader（env > env YAML > base.yaml > defaults）；`settings/loader.py` 使用 `yaml.safe_load`；`settings_customise_sources` tuple 顺序 `env → dotenv → yaml → init`（pydantic-settings 2.14：先列出者优先；见 Task Plan Amendment 002）；**创建** `configs/base.yaml` / `development.yaml` / `test.yaml`（含 §1.2.6 `context`、§2.1.4/§2.1.6 `memory_extraction`、§2.2.14 `memory_retrieval`、§2.3.12 `memory_consolidation`、§3.9 `llm`、§3.10 `embedding`、§3.19 `kafka*`、§3.24 连接池、§3.25 `shutdown` 命名空间）；完整 `.env.example`（§7.1 全部必需 env 键）；`scripts/check_env_example.py`（单一 `required_env_keys()` 来源）；`SecretStr` 用于 API Key 与敏感 URI；跨字段校验（context 不等式、consolidation/retrieval 权重、shutdown 与 lock TTL 关系）。
- **非目标**：Compose/Docker/Preflight（DEV-003）；Migration（DEV-004）；API 壳与鉴权接线（DEV-005）；真实基础设施 Client 连接；三 Entrypoint 可启动服务；`pyproject.toml`/`uv.lock` 依赖变更。
- **变更文件（白名单）**：`src/memory_system/settings/__init__.py`、`loader.py`、`sources.py`、`models.py`、`validators.py`；`configs/base.yaml`、`configs/development.yaml`、`configs/test.yaml`；`.env.example`；`scripts/check_env_example.py`；`tests/unit/test_settings_loader.py`、`tests/unit/test_settings_validation.py`；`tests/contract/test_env_example_contract.py`。
- **测试**：Unit（YAML 合并、env>yaml 优先级、非法 YAML 根节点、§1.2.6/§2.3.12/§2.2.14/§3.25 校验失败）；Contract（`check_env_example.py` 退出码 0、必需键完整、无真实 Secret）。
- **验收**：`get_settings()` 非法配置 `ValidationError`；`uv run python scripts/check_env_example.py` 通过；ruff/mypy/pytest 通过；黑名单路径未越权。
- **Git**：`docs(plan)` on `main` → `feat/DEV-002-config-system-env-example` → `feat(settings): add pydantic settings, yaml loader, and env example`。
- **风险**：Secret 误入 YAML/`.env.example`；`check_env_example` 与 Settings 字段漂移。
- **计划文件**：`02_开发管理/tasks/DEV-002-config-system-env-example.md`
- **状态备注**：`completed`（plan_commit `ceff988`；implementation_commit `f55732c`；治理 committed `8c9f9de`；PR #5 merged `7fba54427ead5bcbde4a5e4141d83bec0e7f7477`；`status_record_commit_completed=null`；下一步 docs(status) complete + **立即 DEV-003**）。

#### DEV-003-002 TEI CPU Memory Contract Validation（Preflight Hardening）

- **目标**：交付 TEI CPU runtime validation tooling（MODEL 2）；Preflight Check 13b、`measure_tei_memory.sh`、fail-closed startup；**不**表示 8g contract validated successfully。
- **非目标**：改 `mem_limit` 非 8g（须 Spec-OI）；DEV-006 业务代码/feat 分支；`src/memory_system/**`；16g 未授权实验入库。
- **关键设计决策**：三态分离 `TOOLING_STATUS=VALID` / `RUNTIME_CONTRACT_STATUS=SPEC_RUNTIME_CONTRACT_CONFLICT` / `DEV006_DEPENDENCY_STATUS=BLOCKED`；Layer A/B 测试分层；默认 CI 不含 runtime_contract_gate。
- **变更文件（预期）**：`scripts/diagnostics/measure_tei_memory.sh`；`scripts/preflight/lib_tei_probe.sh`；`scripts/preflight/check_linux_host.sh`；`scripts/start_embedding.sh`；相关 unit/contract/runtime_contract_gate 测试；`README.md`；本任务开发管理回写。
- **测试**：Layer A mock；Layer B reference gate（独立）；Contract（`mem_limit: 8g` 静态）。
- **验收**：DEV-003-002 `completed`；DEV-006 仅 R1 满足；R2–R4 待 Spec-OI 后新 contract validation。
- **插入说明**：**人工显式插入**于 DEV-006 实施/PR 恢复之前（TEI CPU OOM 阻塞 §8.8）。
- **计划文件**：`02_开发管理/tasks/DEV-003-002-tei-cpu-memory-contract-validation.md`
- **状态备注**：`completed`（plan_commit `7172e91`；implementation_commit `715e985`；PR #14 merged `4d894cc`；`TOOLING_STATUS=VALID`；`RUNTIME_CONTRACT_STATUS=SPEC_RUNTIME_CONTRACT_CONFLICT`；DEV-006 R1 satisfied，R2–R4 BLOCKED pending **OI-011**）。

#### OI-011 BAAI/bge-m3 CPU TEI Memory Contract（Spec-OI）

- **目标**：对 bge-m3 float32 ONNX CPU TEI 做有限 characterization matrix（cgroup ∈ {8g,10g,12g,16g}；每档 2 clean formal runs；≤8 有效；每档 ≤1 invalid）；按 decision rule + safety margin 选定 **model-runtime-profile-specific 固定** `mem_limit`；同步规格 §3.10.3（含 SF-2）/§3.18 #8 方案 A/#12、`compose.embedding.cpu.yaml`、Check 13a 公式/13b/probe/`start_embedding`/contract；关闭 `SPEC_RUNTIME_CONTRACT_CONFLICT`。
- **非目标**：改 DEV-006 / Merge PR #13；改 `scripts/compose.sh`；docker update 正式 evidence；无限扫描 / 20g+；改 GPU mem_limit / model / dtype；`src/memory_system/**`。
- **关键设计决策**：唯一变量 = cgroup limit；正式注入 = characterization overlay + probe 内显式多 `-f`（**含 8g 一律 helper**；**不改 compose.sh**）；env-file 对齐 compose.sh（`.env` 必选；其余仅存在时）；Check 13a = `2+TEI_LIMIT_GIB`；MemAvailable 方案 A（公式权威 `CPU_MIN/REC=12/16+(D-8)`）；Layer B 保留 CONFLICT + 新增 PASS fixture；safety margin = `max(1.5GiB, 15%×limit)`；NON_VIABLE 含 peak≥limit；§3.10.3 fixed contract + `NON_SPEC_COMPLIANT`。
- **变更文件（预期）**：见 Task Plan §6 白名单（含 `fixtures/**`、`start_embedding.sh` 必改；黑名单含 `compose.sh`）。
- **测试**：Unit（多档参数/13a/#8 公式）；Contract（新 mem_limit / SF-2）；Layer B 双 fixture；真实 matrix 受监督归档。
- **验收**：`MEMORY_LIMIT_DECISION` 落盘；规格/compose/preflight 对齐；R2–R4 技术门可满足；OI-011 resolved；**未**触碰 DEV-006 / compose.sh。
- **插入说明**：**人工显式 NEW_UNPLANNED_FEATURE**；在 DEV-003-002 completed 之后、DEV-006 恢复之前插入。
- **计划文件**：`02_开发管理/tasks/OI-011-bge-m3-cpu-tei-memory-contract.md`
- **绑定 OI**：`OI-011`（`02_开发管理/open_issues.md`）
- **状态备注**：`completed`（plan_commit `bda5018`；implementation_commit `131a2e9`；committed 治理 `8a595b8`；PR #15 MERGED `7cc020a97b0373579a91e620fcdef90976193c8c`；`MEMORY_LIMIT_DECISION=12g`；`RUNTIME_CONTRACT_STATUS=PASS`；historical 8g `SPEC_RUNTIME_CONTRACT_CONFLICT` 保留；OI-011 resolved；DEV-006 OI-011 dependency **SATISFIED**；DEV-006 仍 **PAUSED**（R5–R7 pending）；**不得** Merge PR #13）。

#### DEV-003 Docker Compose、Embedding、Preflight

- **目标**：`compose*.yaml`、`versions.env`/`versions.lock.env`、`compose.sh`（唯一 Wrapper，`--embedding=none|cpu|gpu|current`，`--stack=dev|test`）、`start_embedding.sh`（`cpu`/`gpu`/`auto` → `.runtime/embedding.env`）、`lock_tei_images.sh`（TEI 1.9.3 Digest 锁）、`preflight/check_linux_host.sh`（§3.18 全文：GPU-first `auto`、硬失败/Warning 表、Digest 诊断）、多阶段 `Dockerfile`；§3.3 全拓扑；三应用容器 §7.6 确定性 `required_env_keys()` 注入（`env_file` + `environment:`，禁止隐式继承）。
- **非目标**：`scripts/migrate.py` 与 `001`–`004` Migration 逻辑（DEV-004）；`init-infra` 成功执行验收；FastAPI/鉴权（DEV-005）；`TEIEmbeddingClient`（DEV-006）；修改 `settings/**`；裸 `docker compose`。
- **变更文件（白名单）**：§ Task Plan §5（`Dockerfile`、`compose.yaml`、`compose.override.yaml`、`compose.embedding.{cpu,gpu}.yaml`、`compose.test.yaml`、`versions.env`、`versions.lock.env`、`scripts/compose.sh`、`start_embedding.sh`、`lock_tei_images.sh`、`preflight/check_linux_host.sh`、`.gitignore`、`README.md`、契约/集成测试）。
- **测试**：Unit/Contract（`compose.sh config` 经 Wrapper、裸 `docker compose` 静态禁令、`versions.env` 契约、`required_env_keys` 三容器全覆盖、§3.3 全服务集、test 栈 `-f` 顺序）；Integration（Preflight CPU/GPU/auto 路径、Digest 输出、mode↔budget）；**禁止**测试中裸 `docker compose`。
- **验收**：`versions.lock.env` 含真实 `@sha256:` Digest；`compose.sh config` 可解析全服务；三应用容器 env 覆盖 `required_env_keys()`；Preflight `auto` GPU-first / `gpu` 禁止降级；grace period 480/300/300s；CPU/GPU 双路径 §12；黑名单未越权。
- **Git**：`docs(plan)` on `main` → `feat/DEV-003-docker-compose-embedding-preflight` → `feat(docker): add compose stack, embedding scripts, and preflight`。
- **风险**：TEI 镜像拉取体积/代理；GPU/A5000 环境可选；`init-infra run` 在 DEV-004 前预期失败；`vm.max_map_count` 宿主机要求。
- **计划文件**：`02_开发管理/tasks/DEV-003-docker-compose-embedding-preflight.md`
- **状态备注**：`completed`（plan_commit `1b63d51`；implementation_commit `d366fb6`；治理 committed `ad493be`；PR #6 merged `0ac80e566fdd33c41b813803af43a0b4ca237e9b`；completed 治理 `c1234c5`；P2-001 接受偏差 A；GPU lock `--gpus all`；TEI validate-only passed；业务下一任务原为 DEV-004，**已被用户显式插入的 DEV-OPS-003 暂缓**）

#### DEV-004 Migration Runner 与基础设施初始化

- **目标**：`scripts/migrate.py` + `001`–`004`；Mongo `infra_schema_migrations`；**唯一**创建 ES 版本化 Index、Mapping、Alias；Neo4j/Kafka/Mongo 初始化幂等；闭合 Dockerfile COPY 与 `init-infra` `x-app-env` 缺口。
- **非目标**：业务 Document 写入；Retrieval/Extraction；DEV-005/006；已执行 Migration 改写；v1→v2 蓝绿数据迁移。
- **变更文件（精确白名单见 Task Plan §6）**：`scripts/migrate.py`、`scripts/migrations/001_initial_mongodb.py`–`004_initial_kafka_topics.py`、`Dockerfile`、`compose.yaml`（仅 init-infra env）、`README.md`、相关 unit/contract/integration 测试；治理三文件。
- **测试**：Unit（checksum/顺序/Mapping 常量）；Contract（路径与 init-infra）；Integration（首次成功、重复幂等、checksum 篡改失败；ES alias/mapping 断言）。
- **验收**：`python -m scripts.migrate` 符合 §3.26/§3.32.2；`compose.sh … run --rm init-infra` 可成功。
- **风险**：修改已执行 Migration；与规格 Mapping 不一致；Settings 全量 required_env 对 init-infra 仍生效。
- **计划文件**：`02_开发管理/tasks/DEV-004-migration-runner-es-mapping-alias.md`
- **状态备注**：`completed`（plan_commit `5c2274f`；implementation_commit `d8730a6`；committed 治理 `5246b5d`；PR #10 MERGED `206b7a688cbad3070dc3f1646111efa165f2be87`；`workflow_mode=NORMAL`（explicit）；GD-DEV-004-001 已记录；POST_MERGE_CLEANUP 本轮；**下一业务任务 = DEV-005**）。

#### DEV-005 通用 API、鉴权、Request ID、日志与指标

- **目标**：FastAPI 应用壳 + Lifespan（§3.7）；**创建并实现** `api/dependencies.py`、`middleware.py`、`error_handlers.py`、`routes/health.py`、`routes/internal_metrics.py`（仓库当前无 `api/` 目录）；`X-API-Key` 常量时间比较；统一错误包络（§3.23）；Request ID 中间件；structlog JSON（§3.27）；`GET /internal/metrics`（Admin Key）；`GET /health/live` 与 `GET /health/ready`（路径 §8.5 工程冻结）；Readiness 阻塞项含 Redis/Mongo/Neo4j/ES+Mapping/Migration/Kafka Producer，Embedding 非阻塞；Uvicorn `--timeout-graceful-shutdown 450`。
- **非目标**：STM/Retrieval/Extraction 业务路由；DEV-006 TEI Client；OpenTelemetry；修改 settings/compose/migrate；Worker entrypoint 启动。
- **变更文件（白名单）**：`src/memory_system/api/**`（本任务枚举）、`observability/`、`infrastructure/security/`、`infrastructure/runtime.py`、`entrypoints/api.py`、相关 unit/contract 测试、`test_entrypoints_import.py` 修订、可选 `test_api_readiness.py`、最小 `README.md`。
- **测试**：Unit（api_key、error envelope、request_id）；Contract（TestClient 鉴权 401/403、metrics、health、validation_error、敏感日志）；可选 Integration（compose.test Readiness）。
- **验收**：§3.7/§3.16（边界）/§3.21/§3.23/§3.25/§3.26（Readiness Migration 只读）/§3.27；ruff/mypy/pytest 全绿；未越权黑名单。
- **风险**：Health URL 规格未写明（§8.5 冻结）；DEV-001 部分 `__init__.py` 未落盘；Lifespan 范围膨胀；entrypoint 测试需修订。
- **计划文件**：`02_开发管理/tasks/DEV-005-api-shell-auth-request-id-logging-metrics.md`
- **状态备注**：`completed`（plan_commit `2548c9a`；implementation_commit `d32ddc7`；committed 治理 `76a91ce`；PR #12 MERGED `a68d951c50eaeab66f589e5eff5c55d6611f3f43`；`workflow_mode=NORMAL`（explicit）；POST_MERGE_CLEANUP 本轮；**等待用户显式指定下一任务**；**不得自动启动 DEV-006**）。

#### OI-012 SiliconFlow Embedding Provider（Spec-OI）

- **目标**：**最小 MVP Spec-OI** — 默认 Embedding pivot 至 SiliconFlow 托管 `BAAI/bge-m3`；dim=1024；TEI optional/non-MVP-blocking；`SILICONFLOW_API_KEY`；hosted integration 要求；**单一** downstream **DEV-007**。
- **非目标**：全架构 refactor；DEV-008/009；§3.3/§3.18 大改；TEI refactor；PR #13 处置；业务代码；**本轮不 PLAN_LANDING**。
- **关键设计决策**：`EmbeddingClient` 保留；MVP MUST M1–M11（见 Task Plan §5.4）；retry max **3** HTTP attempts；无 local tokenizer。
- **变更文件（预期）**：规格最小节（§3.1/§2.2.14/§3.8/§3.10/§2.2.6）；治理文档。
- **测试**：OI-012 无代码测试；DEV-007 承担 mocked contract + opt-in integration。
- **验收**：最小 spec + 治理；DEFERRED 清单；Review 无 P0/P1。
- **计划文件**：`02_开发管理/tasks/OI-012-siliconflow-embedding-provider-spec-oi.md`
- **规格章节**：§2.2.6、§2.2.14、§3.1、§3.8、§3.10（最小 pivot；**不含** §3.2/§3.3/§3.18 大改）。
- **状态备注**：`completed`（plan_commit `e122c8a`；implementation commits `bd7529f`（spec）+ `f4d2e61`（governance）；PR #16 MERGED `003fb43e24ab5bb5d2401342a0f466fcbe22ce26`；`workflow_mode=NORMAL`（explicit）；POST_MERGE_CLEANUP 本轮；**下一业务任务 = DEV-007 规划**）。

#### DEV-006 TEI Embedding Client + Token Budget

- **目标**：（原计划）TEIEmbeddingClient + Token Budget。
- **状态备注**：**PAUSED / SUPERSEDED_FOR_MVP**（2026-08-09 Amendment 002）；PR #13 **OPEN / DO_NOT_MERGE**；**禁止** merge/rewrite **本 MVP**；决策 deferred 至 DEV-007 Integration 验证后。原计划：`02_开发管理/tasks/DEV-006-tei-embedding-client-token-budget.md`。

#### DEV-007 SiliconFlow Embedding Client MVP

- **目标**：单一 consolidated 任务 — 在 main **从零创建** `EmbeddingClient` Protocol + `SiliconFlowEmbeddingClient`（httpx；`POST /v1/embeddings`；batch≤32；retry≤3）；`create_embedding_client` factory；Settings 最小 pivot（`embedding_provider=siliconflow` default、`SILICONFLOW_API_KEY` 条件必填）；mocked contract tests（M10 全矩阵）；opt-in integration `dim==1024`（M11）。
- **非目标**：TEI refactor/429/compose/preflight；合并 PR #13 `TEIEmbeddingClient`；STM/EXT/RET 接线；local HF tokenizer；Readiness embed 探针升级；ES mapping 变更。
- **关键设计决策**：main 无 embedding 代码（DEV-006 未 merge）；`local_tei` factory **fail-closed**（`NotImplementedError`）；`SILICONFLOW_API_KEY` **不**入全局 `required_env_keys()`（条件 validator）；bge-m3 输出维度 **Integration 验证**（UNKNOWN_FROM_OFFICIAL_DOCS）；**Amendment 001**：无本地精确 token 计数；输入长度由 API `400` fail-fast；`embedding_max_input_tokens` **不**用于 SiliconFlow 客户端校验。
- **前置**：OI-012 **completed**（PR #16 MERGED `003fb43`）；DEV-002/004/005 completed。
- **计划文件**：`02_开发管理/tasks/DEV-007-siliconflow-embedding-client-mvp.md`
- **规格章节**：§2.2.6、§2.2.14、§3.8、§3.10（OI-012 M1–M11）。
- **分支**：`feat/DEV-007-siliconflow-embedding-client-mvp`
- **状态备注**：`completed`（plan_commit `69e4dec`；implementation `88c442e`；record `ea58d72`；PR #17 MERGED `b7916ea`；`workflow_mode=NORMAL`；REAL_SILICONFLOW_INTEGRATION PASS；`BAAI/bge-m3` dim=1024；Amendment 001；**Phase 0 SiliconFlow MVP bootstrap 就绪**；DEV-006 仍 PAUSED/SUPERSEDED_FOR_MVP；PR #13 DO_NOT_MERGE）。

---

### Phase 1：短期记忆

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| STM-001 | Token 估算、WM Key/字段模型、配置校验 | §1.2.1 | DEV-002 | completed |
| STM-002 | Session 创建 | §1.2.1, §1.2.3, §1.2.7, §3.21, §3.23 | STM-001, DEV-005 | completed |
| STM-003 | 消息写入 Lua（幂等/容量；不含完整压缩） | §1.2.1, §1.2.3 | STM-002 | completed |
| STM-004 | 上下文一致性读取 Lua | §1.2.1, §1.2.3 | STM-002 | completed |
| STM-005 | Mongo `context_archive` create/reuse | §1.2.2 | STM-003, DEV-004 | completed |
| STM-006 | 压缩锁、pending archive、Kafka 发布 | §1.2.4, §1.2.6 | STM-005 | completed |
| STM-007 | Compression LLM Client + Structured Output | §1.2.5, §3.9 | DEV-002 | completed |
| STM-008 | Compression Finalize Lua | §1.2.5, §1.2.6 | STM-006, STM-007 | completed |
| STM-009 | Compression Coordinator + 写入 API 接线 | §1.2.3, §1.2.6 | STM-003, STM-004, STM-008 | completed |
| STM-010 | Session Close | §1.2.3, §1.2.7 | STM-006, STM-009 | completed |
| STM-011 | `republish_archive_event.py` 补发脚本 | §1.2.4, §3.4 | STM-006 | planned |
| STM-012 | 补发事件消费验证 | §1.2.4, §2.1.4 | STM-011, EXT-001 | planned |
| STM-013 | 短期记忆阶段 E2E + 关键失败注入 | §1, §3.28 | STM-010 | blocked |

#### STM-001

- **目标**：字符 Token 估算（§1.2.1 heuristic：中文 ×1.25 + 其他 ×0.25 后 ceil；**非** exact tokenizer）；Redis WM key/字段常量与模型（无 live I/O；禁止 `import redis`）；相关配置不等式校验（复用 DEV-002 `validate_context` + STM-001 定向 Unit 证明 **MANDATORY STARTUP VALIDATION CONTRACT** `max_compressed < trigger` strict `<`）；小 contract 测试（`test_stm001_contract.py`）。
- **非目标**：Redis live write / 真实 Redis I/O / `import redis`；HTTP API；Mongo archive；Kafka；compression；LLM / embedding / extraction / retrieval；操作 DEV-006/PR#13；不因基础设施无认证阻塞；不需要 `SILICONFLOW_API_KEY` / `LLM__API_KEY`。
- **测试**：Unit（中英文边界、ceil 公式；Key/字段模型与 Optional 语义；§1.2.1/§1.2.6 不等式含 mandatory strict `<` 三用例 + 正向四链断言）；Contract（`test_stm001_contract.py`；无网络/无 Redis I/O）；无 Integration Redis I/O。
- **风险**：OI-001/002 不在本任务解释。
- **计划文件**：`02_开发管理/tasks/STM-001-token-estimator-wm-key-model-config-validation.md`
- **状态备注**：`completed`（plan_commit `06c272f25e15fd5c7b4afd6e44257bc164dc83ca`；implementation_commit `66541cf3727d5735dd977e597acd6943fd997fb4`；record `ecc15af80ab18e5fe2905b5f5cd4f371f34127a0`；PR #19 MERGED https://github.com/xu-jia-ming/memory_system/pull/19 merge `6f2081da6266282470948ecac8e62ef3ae969c15` mergedAt `2026-08-10T02:11:17Z`；Amendment 001；`workflow_mode=NORMAL`；STM-001 scoped unit 38 / contract 2；full unit 254 / contract 49；ruff PASS；mypy PASS；`validators.py` 未改）；deterministic heuristic token estimator + WM key/field contract + mandatory ContextSettings strict inequality validation evidence；feat 分支已删；**STM-002 READY_FOR_PLANNING only**（不得自动开始实施）。
#### STM-002

- **目标**：`POST /api/v1/memory/session`；初始化 Working Memory Hash（`status=active`，`compression_version=0`）；复用 STM-001 `WorkingMemoryMeta`/Key helpers 与 DEV-005 API 壳；真实 Redis 写 meta Hash only（不预创建 messages/message_ids；无 TTL）。
- **非目标**：消息写入；压缩；Session Close；Mongo/Kafka；第二套 WM 模型或 Redis 连接管理。
- **计划文件**：`02_开发管理/tasks/STM-002-session-creation.md`
- **规格章节**：§1.2.1、§1.2.3、§1.2.7、§3.21、§3.23。
- **测试**：Unit（codec/service）+ Contract（鉴权/包络/`status=created`）+ Integration（真实 Redis：字段齐全、用户隔离、无消息副作用、TTL=-1）。
- **规划备注**：Amendment 001 已吸收 Human Contract（OI-STM-002-001～004 RESOLVED：每次新建 UUID、user_id min_length=1→422、null↔""、HTTP 200）；§1.2.7 规则 12 禁止 TTL。
- **状态备注**：`completed`（plan_commit `ac84b31210001f22df4a049d28ff1e90618c244d`；implementation_commit `3440048f8a304219ec7bbddf3c192089cac6e8cb`；record `1499fd23ad4aa92c6e9dd89f087d77b007674ff3`；PR #20 MERGED https://github.com/xu-jia-ming/memory_system/pull/20 merge `efb39bf0bbbb408626e3d187d81b889dafc7a351` mergedAt `2026-08-10T03:11:25Z`；Amendment 001 已落实；`workflow_mode=NORMAL`；STM-002 scoped 25 / integration 3；full unit 269 / contract 59；ruff PASS；mypy PASS）；`POST /api/v1/memory/session` + `X-API-Key` + UUID v4 + WM Hash `status=active` `compression_version=0` + HTTP 200；feat 分支已删；**STM-003 READY_FOR_PLANNING only**（不得自动开始实施）。

#### STM-003

- **目标**：消息写入 Lua：`message_id` 幂等、容量校验、`duplicate`/`capacity_exceeded`/`session_closing`/`session_not_found`/`message_too_large` 内部语义；Python 层复用 `estimate_tokens()`；单 Lua 原子 RPUSH/SADD/meta 更新；**不含** HTTP 写入路由与完整压缩协调。
- **非目标**：`POST /api/v1/memory/working/message` HTTP 路由与 `compression_status`（**STM-009**）；Coordinator；Kafka；`compression_trigger_tokens` 检查。
- **计划文件**：`02_开发管理/tasks/STM-003-message-write-lua.md`
- **规格章节**：§1.2.1、§1.2.3（写入流程摘录）、§1.2.6、§1.2.7。
- **测试**：Unit（estimator 复用、消息 JSON codec、Lua 结果映射）+ Contract（`test_stm003_contract.py`：`MessageWriteStatus` 字面量稳定）+ Integration（17 场景：success/duplicate/零副作用/单条超限/WM 超限/精确边界 #14/#15/session 缺失/closing/用户隔离/并发同 id/原子失败无 partial state/malformed token #16/ARGV 校验 #17）。
- **规划备注**：§10.1 OI-STM-003-001/002 已 Planner 决议（Lua 成功返回 `success`；meta 缺失与身份不匹配均 `session_not_found`；身份校验 **先于** `status`）；Amendment 001 落实 Round 1 MF-1 + SF-1～3；HTTP 接线见 STM-009。
- **状态备注**：`completed`（plan_commit `926f37d166089f02b3143470ca74ba1258d48010`；implementation_commit `e1913d17b159d426aadfd54d32e07c84ea61043a`；record `34bbebd`；PR #21 MERGED https://github.com/xu-jia-ming/memory_system/pull/21 merge `3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4` mergedAt `2026-08-10T06:26:37Z`；Amendment 001 已落实；`workflow_mode=NORMAL`）；atomic Redis Lua + `write_message`；`message_id` 幂等；duplicate 零副作用；hard WM capacity；concurrent same `message_id` 单写；malformed `estimated_tokens` fail-closed；STM-003 scoped 21 / integration 11；full unit 287 / contract 62；ruff PASS；mypy PASS（119 files）；无 compression/Kafka/HTTP；feat 分支已删；**STM-004 READY_FOR_PLANNING only**（不得自动开始实施）。

#### STM-004

- **目标**：上下文一致性读取 Lua（`compression_version` + `compressed_context` + `messages` 原子快照）；领域服务 `read_working_memory_context`；Lua **严格只读**（OI-009：不更新 `updated_time`、无 TTL）。
- **非目标**：压缩写回；HTTP `GET /api/v1/memory/working/...`（**STM-009**）；读取 `message_ids`；修改 STM-003 写入语义。
- **计划文件**：`02_开发管理/tasks/STM-004-context-read-lua.md`
- **规格章节**：§1.2.1（规则 7）、§1.2.3（获取当前上下文）、§1.2.7（无 TTL/闲置清理）。
- **正式前置依赖**（`master_plan` 表权威）：**STM-002** — SATISFIED。
- **实现/测试复用**（非正式前置）：STM-001（Key/codec/模型）、STM-003（`write_message` Integration 种子、`json_to_message` 解码）— SATISFIED。
- **测试**：Unit（结果映射、快照解码、`""` 语义、畸形 → `ContextReadFailure`、空 messages 最小 3 元素 Lua 返回）+ Contract（`test_stm004_contract.py`）+ Integration（**13** 场景：空 WM/有消息/有摘要/session 缺失/身份不匹配/closing 可读/畸形 version·**compressed_context 缺失**/message/**I12 `NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID` 三段式 torn-read（原子 mutator + broken split-reader 负对照 + 生产 Lua 正对照）**/只读零写入/确定性重复读）。
- **规划备注**：Amendment 002（2026-08-10 PLAN_REMEDIATION Round 3）：MF-2 吸收 — I12 读者组合 torn-read 三段式；原子 test-only mutator；确定性 barrier 负对照；13 Integration 场景；`ContextReadFailure` HTTP 映射归 STM-009；Amendment 001（OI-009、正式/复用区分）保留。
- **状态备注**：`completed`（plan_commit `c3214164ccbc47ad88b104a0497c6b9020f26ba7`；implementation_commit `3aed60522db64c3b11597e025caa0aae00afaba6`；record `8c050fc0d09523d82eb201b4f03fa87060efd065`；PR #22 MERGED https://github.com/xu-jia-ming/memory_system/pull/22 merge `6a3d09f5bf29ec25c768c6295e2c13adb3ff9a6c` mergedAt `2026-08-10T08:02:11Z`；Amendment 002 已落实；`workflow_mode=NORMAL`）；read-only atomic Redis Lua context snapshot；`read_working_memory_context` + `context_read.lua`；OI-009 resolved（只读 Lua；无 `updated_time` 写；无 TTL）；I12 三段式 torn-read；`compressed_context` 缺失 fail-closed；I13 zero Redis write side effect；STM-004 scoped 15 / contract 3 / integration 14；full unit 300 / contract 65；ruff PASS；mypy PASS；无 HTTP/压缩写回；feat 分支待删；**STM-005 READY_FOR_PLANNING only**（不得自动开始实施）。

#### STM-005

- **目标**：Mongo `context_archive` **create/reuse** 领域服务 + Repository；给定预计算 `archive_batch_key` 与 WM 消息批次 → 幂等获得 `archive_id`（CREATE 或 REUSE）；`messages` 按 §1.2.2 四字段持久化（**不含** `estimated_tokens`）；并发相同 key 至多一条物理文档。
- **非目标**：Kafka；Redis `pending_archive_*`；压缩锁/Coordinator/LLM/Finalize；HTTP；消息批次选择逻辑；**新 migration**（DEV-004 已建索引）。
- **计划文件**：`02_开发管理/tasks/STM-005-context-archive-create-reuse.md`
- **规格章节**：§1.2.2。
- **正式前置依赖**：STM-003、DEV-004 — **SATISFIED**。
- **实现复用**：STM-001（`WorkingMemoryMessage`）、STM-004（分层模式）— **SATISFIED**。
- **测试**：Unit（模型映射、`build_archive_batch_key`、create/reuse 服务、Repository DuplicateKey）+ Contract（`test_stm005_contract.py`）+ Integration（**11** 场景真实 Mongo：首建/reuse/同 id/单文档/并发同 key/不同 key/会话隔离/字段持久化/不覆盖/畸形 fail-closed/唯一索引存在）。
- **规划备注**：OI-004 **acknowledged — 不阻塞** create/reuse；Mongo 不写 `estimated_tokens`；token 边界留给 STM-010；`archive_batch_key` 调用方预计算 + 服务一致性校验；`AppState.mongodb` 复用。
- **状态备注**：`completed`（plan_commit `7b761c35ae8aa83c2b5c909312dd511b863a660c`；implementation_commit `c166be5cd40475a513cede67f53cafec8fc8529a`；record `a52207473534b1667967be32957c9e1f500ac429`；PR #23 MERGED https://github.com/xu-jia-ming/memory_system/pull/23 merge `164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf` mergedAt `2026-08-10T09:16:52Z`；`workflow_mode=NORMAL`）；Mongo context_archive create/reuse；`archive_batch_key` `session_id:first_message_id:last_message_id` + mandatory validation；empty messages fail-closed；DuplicateKey → REUSED no overwrite；concurrent same key → one doc same `archive_id`；message order preserved；archived messages 四字段（无 `estimated_tokens`）；DEV-004 unique index verified；no Kafka/Redis pending/compression/LLM/HTTP；STM-005 scoped unit 26 / contract 3 / integration 12；full unit 323 / contract 68；mypy PASS；ruff baseline E501 pre-existing（非回归）；feat 分支待删；**STM-006 READY_FOR_PLANNING only**（不得自动开始实施）。

#### STM-006

- **目标**：压缩锁（`SET NX EX` + owner token + TTL + token-checked release）；保留 pre-held token path，但 `PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED`（ownership 与 pending mutation 同 Lua）；`pending_archive_*` 写入/幂等/冲突；发布 `context.archive.created`（六字段 schema；key=`user_id`；仅 Lua success 后；失败仅日志不回滚 pending，不阻断后续压缩语义）。
- **非目标**：LLM 压缩（STM-007）；Finalize（STM-008）；Coordinator/HTTP（STM-009）；Close（STM-010）；补发脚本（STM-011）；Mongo create/reuse 重实现；消息批次选择；OI-004 私解；跨系统伪原子事务。
- **计划文件**：`02_开发管理/tasks/STM-006-compression-lock-pending-archive-kafka.md`
- **规格章节**：§1.2.1、§1.2.2、§1.2.4、§1.2.6、§1.2.7。
- **正式前置依赖**：STM-005 — **SATISFIED**。
- **测试**：Unit（lock/pending/pre-held A–C、ValidationError）+ Contract（枚举/六字段/TOCTOU guard D）+ Redis Integration（锁互斥、pending、stale/expired/valid pre-held、无 version bump、无 LTRIM；不依赖 Kafka broker）+ Kafka Integration（topic/schema/key/失败注入/重复允许）+ Recovery R1–R4。
- **规划备注**：Amendment 001（Round 2）；MF-1 方案 A；fresh acquire 与 pre-held 同 pending contract；Kafka **at-least-once**；Redis 内原子 ≠ Redis+Kafka 事务；OI-004 open acknowledged 不阻塞；OI-005 进程内生产者决议；锁过期后既有 pending republish 依赖 STM-011（不实现）；lock 仅 `compression_lock_repository.py`。
- **状态备注**：`completed`（plan_commit `6dd97278ec82ebb24dcb21c2c5a58118a65db0cd`；implementation `683caab306e082d58f577977ba3ecee5c550aa6e`；record `5b9d6cb8125a72b502d93980ae75eb43a3d2fd82`；PR #25 MERGED https://github.com/xu-jia-ming/memory_system/pull/25 merge `d704bc5421d346d46a48cb69a3a7ad956e94dbb8` mergedAt `2026-08-10T13:53:53Z`；`workflow_mode=NORMAL`）；compression lock `memory:compression:lock:{user_id}:{session_id}` SET NX EX TTL default 420s；PREHELD atomic Lua pending；same identity accounting fail-closed `pending_conflict`；Kafka `context.archive.created` 六字段 key=user_id AT_LEAST_ONCE；pending+Kafka fail recovery-visible for STM-011；no compression_version bump/no trim/no compressed_context；authoritative scoped unit 26 / contract 4 / redis int 16 / kafka int 4；full unit 349 / contract 72；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3；OI-004 remains open；OI-005 partial evidence；feat 分支待删；**STM-007 READY_FOR_PLANNING only**

#### STM-007

- **目标**：纯 LLM 压缩能力：`CompressionLlmService` + `LLMClient`/`DeepSeekLlmClient`；`deepseek-v4-flash`；`json_object` + Pydantic 校验；`estimate_tokens` 输出边界；`compression_output_too_large` / `llm_empty_output` / `llm_invalid_output` fail-closed；`FakeLlmClient` 供 CI。
- **非目标**：Redis lock / pending / Kafka / Mongo archive I/O；Finalize Lua（STM-008）；Coordinator / HTTP（STM-009）；prompt 截断与 archive 选择。
- **规格章节**：§1.2.5、§1.2.6（`compression_llm_timeout_seconds`）、§3.9。
- **正式前置依赖**：DEV-002 — **SATISFIED**；STM-001 — **SATISFIED**；STM-006 — **SATISFIED**。
- **测试**：Unit 13 + Contract 4 + Integration(fake) 5；opt-in 真实 DeepSeek（`RUN_COMPRESSION_LLM_INTEGRATION=1`）；默认 CI 禁止计费调用。
- **计划文件**：`02_开发管理/tasks/STM-007-compression-llm-client-structured-output.md`
- **状态备注**：`completed`（plan_commit `c5c54c53ae04e323b70c8648c88e0e09b41ede2b`；implementation `87dc9c4a442aff113ac220b9604010aa135f721e`；record `357893a75fe6c95950c6e55d17ef4354194dfc20`；PR #26 MERGED https://github.com/xu-jia-ming/memory_system/pull/26 merge `7a72b3a4c159032a411bd48dc920e52973ddab3e` mergedAt `2026-08-10T14:45:58Z`；`workflow_mode=NORMAL`）；CompressionLlmService + DeepSeekLlmClient + FakeLlmClient；public API `run_compression_llm(...)`；CompressionLlmInput/Output strict structured-output validation；client single provider call `json_object` transport retry=0；service validation/parse/bounded schema retry max 2/token estimation/`compression_output_too_large`；provider `deepseek-v4-flash` temperature=0 thinking=disabled stream=false DEV-002 LLMSettings；STM-008 handoff `CompressionFinalizeLlmPayload`；scoped unit 20 / contract 4 / integration(fake) 5 / total 29；full unit 369 / contract 76；ruff PASS；mypy PASS；real integration SKIPPED；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1；OI-004 remains open；OI-005 remains open（partial evidence only from STM-006）；NOT implemented: Redis lock/pending/Kafka/Mongo/compression_version/trim/Finalize Lua/STM-009 Coordinator；feat 分支待删；**STM-008 READY_FOR_PLANNING only**（prerequisites STM-006+STM-007 SATISFIED；不得自动开始）；**不得触碰 DEV-006/PR#13**。

#### STM-008

- **目标**：单 Redis Lua 原子 Finalize：校验压缩锁 owner、`compression_version` 精确匹配后 +1、pending 四字段精确匹配、List 头部首尾 `message_id` 边界、`estimated_tokens` 按 §1000–1006 公式重算、写 `compressed_context`、按 `pending_archive_message_count` `LTRIM` 头部、清空 pending 四字段（codec `""`/`"0"`）、更新 `updated_time`、compare-and-delete 释放锁；领域服务消费 STM-007 `CompressionFinalizeLlmPayload`。
- **非目标**：Compression LLM；Kafka publish；Mongo archive mutation；Coordinator / HTTP；Session Close；STM-011 republish；message_ids Set 裁剪；多轮压缩策略；DEV-006/PR#13。
- **计划文件**：`02_开发管理/tasks/STM-008-compression-finalize-lua.md`
- **规格章节**：§1.2.1（规则 4–6）、§1.2.5（§991–1018）、§1.2.6、§1.2.7、§3.28（§5845 in-flight）。
- **正式前置依赖**：STM-006、STM-007 — **SATISFIED**。
- **测试**：Unit（Input/payload handoff/ValidationError/Lua 映射）+ Contract（枚举/TOCTOU/无 message_ids SREM）+ Redis Integration **27 场景**（I18 Case A token 分解证明 new=500、I27 clamp 0、M1–M4 边界、畸形 Redis 整数 I24–I25、畸形 message JSON I26、closing in-flight、并发 duplicate 单次 version 迁移、失败零 mutation、retry 无 double-trim、无 Kafka/Mongo/LLM 副作用）。
- **规划备注**：§5.0 十六项 Contract 闭合；Amendment 001（`plan_review_round: 2`）：HM-1 五项 token 变量 + I18 算术修正；HM-2 `max(0,…)` clamp 语义；畸形 `compression_version`/`estimated_tokens` → `invalid_session_state`；`ARGV[11]==ARGV[7]` defense；`closing` + 非空 pending 允许 in-flight Finalize（§733/§5845）；`archived_message_tokens` 调用方供给（OI-004 open）；OI-005 partial evidence acknowledged；成功路径锁在 Lua 内释放。
- **状态备注**：`completed`（plan_commit `fa3e1bf33e889dbb6180315eda896b954a02df8f`；implementation `d619ca2f7e2e20d2d944794c2ca21e8e6d5752ef`；record `a938220f8937b0e8af7e52dd34019ad1b558e789`；PR #27 MERGED https://github.com/xu-jia-ming/memory_system/pull/27 merge `ac61680098d2ae2644bc8b990f057816c3218fca` mergedAt `2026-08-10T15:48:17Z`；`workflow_mode=NORMAL`）；单 Lua 12 precondition + 9 mutation；token 公式 §1000–1006（I18 Case A new=500；I27 clamp 0）；safety/idempotency：precondition 失败零 mutation、success 后旧 version 重试 version_conflict、无 double-trim/bump、closing in-flight 允许；STM-007 `CompressionFinalizeLlmPayload` handoff；scoped unit 20 / contract 4 / integration 27；full unit 393 / contract 80；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2；无 Kafka/Mongo/LLM；OI-004/OI-005 remain open；feat 分支待删；**STM-009 READY_FOR_PLANNING only**（prerequisites STM-003+STM-004+STM-008 **SATISFIED**；不得自动开始）；**不得触碰 DEV-006/PR#13**。

#### STM-009

- **目标**：`CompressionCoordinatorService` 编排 STM-004/005/006/007/008 公共边界；`POST /api/v1/memory/working/message` HTTP 接线；`compression_status` 七值；容量背压（先协调再重试写入）与触发后同步压缩（§479）；消息头部选择（§1113–1118）；Pending 复用；默认 `FakeLlmClient`。
- **非目标**：重写 STM-003–008 底层；`GET` 读上下文 HTTP；STM-010 Close；STM-011 republish；STM-013 全 E2E；DEV-006/PR#13。
- **计划文件**：`02_开发管理/tasks/STM-009-compression-coordinator-message-write-api.md`
- **规格章节**：§1.2.1–§1.2.3、§1.2.6、§1.2.4、§1.2.5、§3.9、§3.23。
- **正式前置依赖**：STM-003、STM-004、STM-005、STM-006、STM-007、STM-008、DEV-005 — **SATISFIED**。
- **规划备注**：§5.0 二十三项 Contract 闭合；OI-001/OI-002 Planner 决议 §10.1–10.2；OI-004 局部不阻塞；OI-005 进程内生产者闭合；成功响应仅 `message_id`/`status`/`compression_status`；触发 `estimated_tokens >= compression_trigger_tokens`；Kafka `publish_failed` 不阻断 LLM；MUST_FIX=0。
- **测试**：Unit 20（Coordinator）+ Contract 10（HTTP）+ Integration A–L（Redis/Mongo/Kafka + FakeLlmClient）。
- **状态备注**：`completed`（plan_commit `8609f15b47a318e885fab9cd073b616863b8d5b5`；implementation `1b6270b663b6326efb32f096a0e67e2742bb6794`；record `63232d837add2b4a6c6918d145f115f4762b88f7`；PR #28 MERGED https://github.com/xu-jia-ming/memory_system/pull/28 merge `924ca8c8af94793e76be9376c4514ef417ce5e33` mergedAt `2026-08-11T01:17:29Z`；`workflow_mode=NORMAL`）；CompressionCoordinatorService 编排 STM-004/005/006/007/008 公共边界；`POST /api/v1/memory/working/message` HTTP 接线；`compression_status` 七值；容量背压先协调再同 `message_id` 重试；触发 `estimated_tokens>=compression_trigger_tokens`；Archive 头部前缀选择+Pending 复用；Kafka `publish_failed` 继续 LLM；消息已写入后压缩失败 HTTP 200 不回滚；多轮 `partial_completed`；FakeLlmClient 默认注入；scoped unit 21 / contract 10 / redis int 10 / kafka int 2；full unit 410 / contract 90；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3；OI-001/OI-002/OI-005 resolved；OI-004 remains open；NOT implemented: STM-010 Close / STM-011 republish / STM-013 E2E；feat 分支待删；**STM-010 READY_FOR_PLANNING only**（STM-006+STM-009 **SATISFIED**；不得自动开始）；**不得触碰 DEV-006/PR#13**。

#### STM-010

- **目标**：Session Close 状态机 + 关闭路径 Archive 协调 + `POST /api/v1/memory/session/{user_id}/{session_id}/close`；原子 `active→closing`（`session_close_enter.lua`）；早失败 `revert_active`；`ClosePlan.base_compression_version` 在 `enter_closing` 后单次快照并冻结（§331/§735）；suffix Archive 全部使用冻结值；`split_close_suffix_batches` 归档 **全部** 后缀（`max_archive_estimated_tokens`；**不** 应用 `absolute_min_recent_messages`）；复用 Pending + STM-005 create/reuse + Kafka publish（`publish_failed` 不阻断 terminal）；`session_close_terminal.lua` 原子删 meta/messages/message_ids；复用 STM-006 压缩锁；**不** 调用 Coordinator/LLM/Finalize；OI-003/OI-004 Planner 决议见 Task Plan §10.3/§10.4。
- **非目标**：STM-011 republish；STM-012/013 E2E；Extraction/Retrieval；重写 STM-003–009 核心 Contract；第二套 close 锁；STM-008 token 公式修改；Mongo 写入 `estimated_tokens`；Redis `status=closed`。
- **计划文件**：`02_开发管理/tasks/STM-010-session-close.md`
- **规格章节**：§1.2.1、§1.2.2（§331 `base_compression_version`）、§1.2.3（Close API §651–755）、§1.2.4、§1.2.6、§1.2.7（§1183–1185）、§3.23。
- **正式前置依赖**：STM-006、STM-009 — **SATISFIED**。
- **测试**：Unit 22 + Contract 10 + Integration A–R + OI-004 专用 OI4；含 `base_compression_version` 快照/冻结/REUSED；失败注入/并发 write-vs-close；**无** STM-013 全 E2E。
- **规划备注**：`plan_review_round: 2`（MF-1 `base_compression_version` 闭合；吸收 SF-1–SF-4）；同步 HTTP 200 `closed` / 503 `close_incomplete`（OI-003 决议）；`closing` 重试恢复非 409；终端重复 404 `session_not_found`；STM-011 **非** blocker；`pr_sizing: single PR, medium-sized scoped change`。
- **状态备注**：`completed`（plan_commit `abd6d8be7d3807710a3cc24d65d2af81576a482d`；implementation `ebb90e49c4eed8b7fd64a35611d7af87521d3d5a`；PR #29 MERGED https://github.com/xu-jia-ming/memory_system/pull/29 merge `722e42d9e24d085b0ed671478730952ef7c92ad6` mergedAt `2026-08-11T02:14:24Z`；`workflow_mode=NORMAL`）；Session Close enter/revert/terminal Lua + `close_session` 编排 + `ClosePlan.base_compression_version` 快照/冻结；`POST /api/v1/memory/session/{user_id}/{session_id}/close`；HTTP 200 `closed` / 503 `close_incomplete`（OI-003）；suffix 全归档 `split_close_suffix_batches`；不复用 Coordinator/LLM/Finalize；OI-004 resolved（OI4 test PASS）；scoped unit 36 / contract 11 / integration 19；full unit 446 / contract 101；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=3；whitelist drift `session_close_script.py` P2 approved；feat 分支待删；**STM-011 READY_FOR_PLANNING only**；**STM-013 READY_FOR_PLANNING only**（STM-010 **SATISFIED**）；**STM-012 NOT ready**（needs STM-011 + EXT-001）；**不得触碰 DEV-006/PR#13**。

#### STM-011

- **目标**：实现 `scripts/republish_archive_event.py`（发布侧）。
- **非目标**：消费侧任务创建断言（属 STM-012）。
- **前置**：**仅 STM-006** — **SATISFIED**。
- **状态备注**：`planned` — **READY_FOR_PLANNING only**（STM-006 satisfied；**不得自动开始**）。
- **测试**：Unit/脚本级；不依赖 EXT-001。

#### STM-012

- **目标**：补发事件被 Extraction Consumer 消费的 Integration/E2E 验证（任务幂等创建等）。
- **前置**：STM-011, EXT-001 — **NOT ready**（needs STM-011 + EXT-001 completed）。
- **非目标**：修改补发脚本业务语义（除非缺陷修复）。
- **状态备注**：`planned` — **NOT ready**（needs STM-011 + EXT-001）。

#### STM-013

- **目标**：STM 阶段端到端（**公共 HTTP API** 驱动）：Session Create → Message Write → Archive → Compression（Coordinator + FakeLlmClient）→ 压缩后继续写入 → Session Close；含 §3.28 STM 子集失败注入（E2 幂等 / E3 并发 write-vs-close / E4 LLM 失败 HTTP 200）；跨 HTTP + Redis + Mongo + Kafka 断言；**闭合 `v0.2.0-short-term-memory` 里程碑**。
- **非目标**：修改 STM-001~010 核心 Contract；STM-011 republish；STM-012 EXT 消费；§3.32 全链路 EXT/RET E2E；真实 DeepSeek/SiliconFlow/TEI；默认 **无** `src/**` 生产变更（缺陷 HALT）。
- **计划文件**：`02_开发管理/tasks/STM-013-short-term-memory-e2e.md`
- **规格章节**：§1.2.1–§1.2.7、§1.2.4、§3.23、§3.28（STM 子集）、§3.32（STM 垂直切片）。
- **正式前置依赖**：**STM-010** — **SATISFIED**。
- **非 blocker**：STM-011（republish 非 E2E 前提）；STM-012（需 EXT-001）。
- **测试**：E2E only（`tests/e2e/test_stm013_short_term_memory_e2e.py`）；`@pytest.mark.integration`；scoped `pytest tests/e2e/...`（**非** `-m e2e`）；E1–E4；compose.test.yaml + memory-api；E4 hybrid in-process `FakeLlmClient(mode=timeout)`。
- **规划备注**：TEST/E2E FIRST；`plan_review_round: 2`（MF-1 OPTION 2 + SF-1 config parity + SF-2 Kafka 矩阵 + SF-3 compose 启动序）；Fixture A settings == memory-api runtime；test 栈 HTTP 经 container IP；bounded Kafka poll 过滤 `user_id`/`session_id`/`archive_id`；`workflow_mode=NORMAL`。
- **状态备注**：`blocked` — `release_gate=BLOCKED_BY_DEFECT_FIX`；blocking task **DEV-OPS-008**；PR #30 OPEN **MUST NOT MERGE**；scope remediation 已将 C1/C2 生产修复移出 PR #30 effective diff；E2E 在 feat 保留；**DEV-OPS-008 merge + revalidation + CODE_REVIEW 后**方可继续 release。

---

### Phase 2：长期记忆萃取

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| EXT-001 | Task Schema + Kafka Consumer 幂等/Offset | §2.1.3, §2.1.4 | STM-006, DEV-004 | planned |
| EXT-002 | Archive 读取/预处理/脱敏 | §2.1.5 | EXT-001 | planned |
| EXT-003 | LLM Extraction + Fingerprint | §2.1.6–2.1.8 | EXT-002, STM-007 | planned |
| EXT-004 | Entity Alignment + Neo4j 模型基础 | §2.1.9, §2.1.10 | EXT-003, DEV-004 | planned |
| EXT-005 | Reconciliation + 聚合门禁 | §2.1.11 | EXT-004 | planned |
| EXT-006 | Neo4j 图谱事务写入 | §2.1.12, §2.1.13 | EXT-005 | planned |
| EXT-007 | Retrieval Document 同步 | §2.2.3 | EXT-006, DEV-007, DEV-004 | planned |
| EXT-008 | Extraction 管理 GET/Retry | §2.1.14 | EXT-007, DEV-005 | planned |
| EXT-009 | Extraction E2E + 失败注入 | §2.1.15, §3.28 | EXT-008 | planned |

#### EXT-001–EXT-006（摘要）

- 各自单 Commit：任务状态机与 Offset；预处理；LLM；实体对齐；和解；图谱事务。
- **风险**：OI-006（`reconciliation_plan_conflict` 运维清理无 Contract）——EXT-008 前需规格确认，不得自行发明 API。

#### EXT-007 Retrieval Document 同步

- **目标**：search_text、经 `create_embedding_client` 调用 Embedding（**默认 SiliconFlow / DEV-007**）、Bulk upsert（`refresh=wait_for`）；作为 Extraction 完成门禁之一。
- **非目标**：**不创建/修改** Mapping 或 Alias（缺失则失败）。
- **前置**：EXT-006, **DEV-007**, DEV-004。
- **测试**：Integration（部分 bulk 失败、Neo4j 成功后 ES 失败恢复路径按规格）。

#### EXT-008 / EXT-009

- 管理接口与阶段 E2E/失败注入（含 Worker 在 Neo4j commit 后退出等）。

---

### Phase 3：长期记忆检索

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| RET-001 | BM25 查询 | §2.2.7 | DEV-004, DEV-007 | planned |
| RET-002 | Vector 召回 + RRF | §2.2.8, §2.2.9 | RET-001, DEV-007 | planned |
| RET-003 | Neo4j 权威回读 + 一跳扩展 + MGET | §2.2.10 | RET-002 | planned |
| RET-004 | ACT-R 评分 + Evidence 聚合 | §2.2.11, §2.2.12 | RET-003 | planned |
| RET-005 | Retrieval API、降级/超时、统计更新 | §2.2.5, §2.2.13–2.2.15 | RET-004, DEV-005 | planned |
| RET-006 | Retrieval 阶段 E2E + 失败注入 | §2.2.16, §3.28 | RET-005, EXT-007 | planned |

#### RET-001 BM25 查询

- **目标**：对已存在 Alias 执行 BM25；过滤器与字段权重按规格。
- **非目标**：创建 Mapping/Alias；Vector/RRF；硬依赖 EXT-007。
- **前置**：**DEV-004, DEV-007**（BM25 可不调用 Embedding；Vector 依赖 DEV-007，见 RET-002）。
- **测试**：Integration —— Migration 后**直接写入固定 ES Fixture 文档**，再断言 BM25；**不**将 EXT-007 列为硬前置。
- **E2E 协作**：与 EXT-007 的写入→可检索 放到 RET-006 / E2E-001。

#### RET-002–RET-005

- Vector+RRF；图扩展；评分与 Evidence；API 与降级矩阵（见 OI-008 编辑性问题，不阻塞实现规格正文）。

#### RET-006

- 阶段 E2E：**包含** EXT-007 同步文档可被 BM25/检索链路消费的验证；失败注入（单通道失败、总超时、Embedding 不可用等）。

---

### Phase 4：巩固与遗忘

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| CON-001 | Importance/衰减/保护公式纯函数 | §2.3.5–2.3.8 | EXT-004 | planned |
| CON-002 | Cursor 分页批量读取与 Evidence 计数 | §2.3.4 | CON-001 | planned |
| CON-003 | 乐观锁批量更新 | §2.3.9 | CON-002 | planned |
| CON-004 | APScheduler、互斥锁、失败恢复 | §2.3.4, §3.22 | CON-003 | planned |
| CON-005 | Consolidation Integration + E2E | §2.3.11–2.3.13 | CON-004 | planned |

- **非目标（阶段）**：独立 Consolidation HTTP API；ES importance 同步；多实例调度。

---

### Phase 5：最终工程与发布候选

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| OPS-001 | Graceful Shutdown、连接池、Timeout 与 Retry 总检 | §3.24, §3.25 | 前述全部业务阶段 | planned |
| OPS-002 | 日志、指标、敏感信息与用户隔离审计 | §3.27, §3.21 | 前述全部 | planned |
| OPS-003 | 全量 Migration、Compose 与空白环境验证 | §3.17, §3.32 | 前述全部 | planned |
| OPS-004 | CI 门禁（§3.28 + 80% 覆盖率） | §3.28, §3.30 P1 | OPS-003 | planned |
| E2E-001 | 全链路 E2E 与全部失败注入 | §3.28, §3.32 | OPS-003 | planned |
| REL-001 | MVP RC Review 与验收清单 | `05_测试与验收/mvp_acceptance_checklist.md` | E2E-001 | planned |

---

## 4. 里程碑

| Tag | 条件 |
|---|---|
| `v0.1.0-bootstrap` | Phase 0 完成（含 **DEV-007** SiliconFlow MVP；DEV-006 TEI **非** bootstrap 阻塞） |
| `v0.2.0-short-term-memory` | STM-013 完成 |
| `v0.3.0-memory-extraction` | EXT-009 完成 |
| `v0.4.0-memory-retrieval` | RET-006 完成 |
| `v0.5.0-consolidation` | CON-005 完成 |
| `v0.9.0-mvp-rc1` | E2E-001 与审查完成 |
| `v1.0.0-mvp` | MVP 验收清单全部通过 |

---

## 5. 变更记录

### CHANGE-001

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-06 |
| 原因 | 对照规格细化 Backlog：拆分过大任务；固化 ES/Embedding/补发脚本归属；双口令门禁 |
| 受影响任务 | Phase 0–5 全表（相对初始骨架 Master Plan 增补 DEV-006，重编号 STM/RET，拆分 STM-011/012/013 等） |
| 是否改变技术规格 | **否** |
| 审批 | 规划最终修订版；落盘依据 `PLANNING_DOCS_APPROVED` |

### CHANGE-002

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-06 |
| 原因 | 登记非业务任务 DEV-OPS-001：项目级 Cursor Slash Commands，降低长提示词重复粘贴；不改变 Phase 0–5 业务任务目标与依赖 |
| 受影响任务 | 新增 `DEV-OPS-001`（Phase 0 补充）；**不**修改 DEV-001 完成状态；**不**改变 DEV-002+ 业务范围 |
| 是否改变技术规格 | **否** |
| 审批 | 初版曾 `PLAN_REJECTED`；Amendment 001 后 Round 2 复审通过（`PLAN_APPROVED`）；实现 Commit `69fabb7`；治理 committed `5d00a49`；PR #2 merged（`57800c3`）；最终 docs(status) `5f34ccb`；状态 `completed` |

### CHANGE-003

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-06 |
| 原因 | 登记非业务任务 DEV-OPS-002：Orchestrator + 可复用 Subagents + 受控 Release Automation；降低多会话手工编排成本；不改变 Phase 0–5 业务任务目标与依赖 |
| 受影响任务 | 新增 `DEV-OPS-002`（Phase 0 补充）；**不**修改 DEV-OPS-001 / DEV-001 完成状态；**不**改变 DEV-002+ 业务范围 |
| 是否改变技术规格 | **否** |
| 审批 | Round 1 曾 `PLAN_REJECTED`；Amendment 001 后 Round 2 通过（`PLAN_APPROVED`）；状态 `approved`；未实施 |

### CHANGE-004

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-07 |
| 原因 | 登记 DEV-002 初版 Task Plan：配置系统、YAML 命名空间、`.env.example` 与 `check_env_example.py`；细化白/黑名单与规格章节映射 |
| 受影响任务 | DEV-002（`approved`）；**不**修改 DEV-001 / DEV-OPS-* 完成状态；**不**改变 DEV-003+ 业务范围 |
| 是否改变技术规格 | **否** |
| 审批 | Round 1 `PLAN_REJECTED`；Amendment 001；Round 2 `PLAN_APPROVED`；人工确认 2026-08-07 08:03 UTC；plan_commit `ceff988`；implementation `f55732c`；PR #5 merged `7fba544`；状态 `completed` |

### CHANGE-005

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-07 |
| 原因 | 登记 DEV-003 初版 Task Plan：Docker Compose 全拓扑、TEI Embedding 部署链（1.9.3 Digest 锁）、Preflight、与 DEV-002 Settings/`.env.example` 衔接；细化白/黑名单、`compose.sh` 唯一 Wrapper 与测试策略 |
| 受影响任务 | DEV-003（`planned`）；**不**修改 DEV-001 / DEV-OPS-* / DEV-002 完成状态；**不**改变 DEV-004+ 业务范围 |
| 是否改变技术规格 | **否** |
| 审批 | Round 1 `PLAN_REJECTED`（MF-001、MF-002、SF-001–005）；Amendment 001；Round 2 `PLAN_APPROVED`；人工确认 2026-08-07 10:33 UTC；状态 `approved`；`plan_commit=null`（待 docs(plan) on main） |

### CHANGE-005 Amendment 001

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-07 |
| 原因 | Round 1 Plan Review 拒绝项修订：闭合三应用容器 `required_env_keys()` 确定性注入（§7.6）；Preflight §3.18 全文（GPU-first `auto`、内存门槛、Digest 输出、mode↔budget）；回滚步骤、契约测试全服务集、test 栈 `-f` 顺序、治理文档入 §9 |
| 受影响任务 | DEV-003（`approved`）；**不**改变 DEV-004+ 业务范围 |
| 是否改变技术规格 | **否**（对齐既有 §3.10.5、§3.18 字面要求） |
| 审批 | Round 2 `PLAN_APPROVED`（BLOCKER 0 / MUST_FIX 0 / SHOULD_FIX 5 非阻塞）；人工确认 2026-08-07 10:33 UTC；状态 `approved` |

### CHANGE-006

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-07 |
| 原因 | **人工显式插入**非业务任务 DEV-OPS-003：NORMAL/STRICT 工作流模式，减少常规机械人工门禁；覆盖先前 progress「不得插入 DEV-OPS-003 / 立即 DEV-004」next_action；不改变 Phase 0–5 业务任务目标与依赖 |
| 受影响任务 | 新增 `DEV-OPS-003`（Phase 0 补充，现 `completed`）；DEV-004 保持 `planned` 且为下一业务任务；**不**修改 DEV-OPS-001/002 / DEV-001–003 完成状态；**不**改变 DEV-004+ 业务范围正文 |
| 是否改变技术规格 | **否** |
| 审批 | Round 1 `PLAN_REJECTED`（MF-001）；Amendment 001；Round 2 `PLAN_APPROVED`；人工确认 2026-08-07 15:39 UTC；plan_commit `d45ea2f`；implementation `640616b`；record `ec47b2a`；PR #7 MERGED `1189447`；Step 7 NORMAL smoke PASSED（PR #8 / `e14d71e` / POST_MERGE `45c74f8`）；正式 `completed`（complete 治理 `4e4ad19`） |

### CHANGE-007

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-08 |
| 原因 | **人工显式插入**非业务任务 DEV-OPS-004：文档化本开发主机 Mihomo 网络回退策略（AI 面向）；覆盖先前 progress「进入 DEV-004 业务规划」next_action；不改变 Phase 0–5 业务任务目标与依赖；不改规格 §3.15 Contract |
| 受影响任务 | 新增 `DEV-OPS-004`（Phase 0 补充，现 `completed`）；DEV-004 保持 `planned` 且为下一业务任务；**不**修改 DEV-OPS-001/002/003 / DEV-001–003 完成状态；**不**改变 DEV-004+ 业务范围正文 |
| 是否改变技术规格 | **否** |
| 审批 | Planner 初版；独立 Plan Review → `PLAN_APPROVED`；人工确认 approved；PLAN_LANDING 完成（plan_commit `895d7aa`）；Developer tested；CODE_REVIEW_APPROVED；IMPLEMENTATION_RELEASE（implementation `14550df`；record `7d2a176`）；PR #9 MERGED `1bc2f499d79301679f373d46c809f1f50e4dad66`；POST_MERGE_CLEANUP 本轮 |

### CHANGE-008

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-08 |
| 原因 | 登记 DEV-004 初版 Task Plan：Migration Runner、`001`–`004`、ES Mapping/Alias 唯一创建方；闭合 Dockerfile COPY 与 init-infra `x-app-env`；细化白/黑名单、幂等/顺序/失败重试与测试策略 |
| 受影响任务 | DEV-004（`completed`）；**不**修改 DEV-001–003 / DEV-OPS-* 完成状态；**不**开始 DEV-005/006 实施；**不**改变后续业务任务范围正文 |
| 是否改变技术规格 | **否** |
| 审批 | Planner 初版；独立 Plan Review → `PLAN_APPROVED`；人工确认 approved；PLAN_LANDING 完成（plan_commit `5c2274f`）；Developer tested；GD-DEV-004-001 治理记录；CODE_REVIEW_APPROVED；IMPLEMENTATION_RELEASE（implementation `d8730a6`；record `5246b5d`）；PR #10 MERGED `206b7a688cbad3070dc3f1646111efa165f2be87`；POST_MERGE_CLEANUP 本轮 |

### CHANGE-009

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-08 |
| 原因 | **人工显式插入**非业务任务 DEV-OPS-005：人类 Prompt Playbook 与 Recovery 操作手册；覆盖先前 progress「进入 DEV-005 业务规划」next_action；不改变 Phase 0–5 业务任务目标与依赖；不改 Orchestrator / NORMAL·STRICT 实现 |
| 受影响任务 | 新增 `DEV-OPS-005`（Phase 0 补充，现 `completed`）；DEV-005 保持 `planned` 且为下一业务任务；**不**修改 DEV-OPS-001–004 / DEV-001–004 完成状态；**不**改变 DEV-005+ 业务范围正文 |
| 是否改变技术规格 | **否** |
| 审批 | Planner 初版；独立 Plan Review Round 2 → `PLAN_APPROVED`；人工确认；PLAN_LANDING 完成（plan_commit `a601a3b`）；Developer `tested`；Code Review `CODE_REVIEW_APPROVED`（P0/P1=0；P3=3）；IMPLEMENTATION_RELEASE（implementation `373cd33`；record `2392184`）；PR #11 MERGED `0239c28281949bedec66dbec1412197c5561a611`；POST_MERGE_CLEANUP 本轮 |

### CHANGE-010

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-08 |
| 原因 | 登记 DEV-005 初版 Task Plan：FastAPI 应用壳、鉴权、Request ID、structlog、Prometheus、Liveness/Readiness 结构；细化白/黑名单、§8 行为合同、测试策略与 NORMAL 三相 Git 计划 |
| 受影响任务 | DEV-005（`completed`）；**不**修改 DEV-001–004 / DEV-OPS-* 完成状态；**不**开始 DEV-006/STM/Retrieval 实施；**不**改变后续业务任务范围正文 |
| 是否改变技术规格 | **否**（Health 路径为工程冻结，见 Task Plan §8.5；不扩展业务 API Contract） |
| 审批 | Planner 初版；独立 Plan Review → `PLAN_APPROVED`；人工确认；PLAN_LANDING 完成（plan_commit `2548c9a`）；Developer `tested`；Code Review `CODE_REVIEW_APPROVED`（P0/P1=0）；IMPLEMENTATION_RELEASE（implementation `d32ddc7`；record `76a91ce`）；PR #12 MERGED `a68d951c50eaeab66f589e5eff5c55d6611f3f43`；POST_MERGE_CLEANUP 本轮 |

### CHANGE-011

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-08 |
| 原因 | 登记 DEV-006 初版 Task Plan：TEI Embedding Client + Token Budget（EXT-007 与 Retrieval 共享）；细化白/黑名单、§8 行为合同（1024 硬限制、CPU/GPU budget 分批、/tokenize + /v1/embeddings、1024 维）、Contract Fake TEI + Integration 真实 TEI 测试策略与 NORMAL 三相 Git 计划 |
| 受影响任务 | DEV-006（`planned`）；**不**修改 DEV-001–005 / DEV-OPS-* 完成状态；**不**开始 STM/EXT/RET 实施；**不**改变后续业务任务范围正文 |
| 是否改变技术规格 | **否** |
| 审批 | Planner 初版；等待独立 Plan Review → `PLAN_APPROVED` |

### CHANGE-012

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-08 |
| 原因 | **人工显式插入** DEV-003 follow-up DEV-003-002：TEI CPU `mem_limit=8g` warm-up OOM（exit 137）阻塞 DEV-006 §8.8 Integration；闭合 DEV-003 Preflight Check 13（P2-001 Verdict A）与 §3.18 #12 字面差距；不改规格 8g Contract |
| 受影响任务 | 新增 `DEV-003-002`（`approved`）；DEV-006 改为 `paused` 并增加前置 `DEV-003-002`；**不**修改 DEV-001–005 / DEV-OPS-* 完成状态；**不**改变 STM/EXT/RET 业务范围 |
| 是否改变技术规格 | **否**（若实测 8g 不足则走 Spec-OI，本 CHANGE 不预批准提限） |
| 审批 | Planner 初版；独立 Plan Review → `PLAN_APPROVED`（2026-08-08） |

### CHANGE-013

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-09 |
| 原因 | **人工显式 NEW_UNPLANNED_FEATURE**：基于 DEV-003-002 `RUNTIME_CONTRACT_STATUS=SPEC_RUNTIME_CONTRACT_CONFLICT`，启动 Spec-OI **OI-011**（bge-m3 CPU TEI memory contract characterization + 规格/compose/preflight 修订规划） |
| 受影响任务 | 新增 `OI-011`（`approved`）；DEV-006 前置增加 `OI-011` 并保持 `paused`；**不**修改 DEV-001–005 / DEV-003-002 / DEV-OPS-* 完成状态；**不**改 DEV-006 计划正文 / feat / PR #13 |
| 是否改变技术规格 | **是（预期，批准后实施）**：§3.10.3（含 SF-2）/ §3.18 #8 方案 A / §3.18 #12 CPU TEI `mem_limit` 字面及对齐文案；须 `PLAN_APPROVED` + 实施白名单后方可改规格正文 |
| 审批 | Round 1 `PLAN_REJECTED`（MF-1～MF-4；SF-1～SF-4）；Amendment 001 已修订；Round 3：**Amendment 002**（MF-3 查表 + R2 SF-1～SF-4）；Round 3 → `PLAN_APPROVED`（BLOCKER=0；MUST_FIX=0；2026-08-09 人工确认） |

### CHANGE-014

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-09 |
| 原因 | **人工显式 NEW_UNPLANNED_FEATURE**：MVP 默认 Embedding pivot 至 SiliconFlow；初始 OI-012 规划（后被 Amendment 002 简化） |
| 受影响任务 | 新增 `OI-012`；DEV-006 初始 superseded 登记；DEV-007/008/009 占位（**CHANGE-015 移除 008/009**） |
| 是否改变技术规格 | **是（预期）** |
| 审批 | Planner 初版 + Amendment 001；**superseded partially by CHANGE-015** |

### CHANGE-015

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-09 |
| 原因 | **Amendment 002 MVP_SIMPLIFICATION**：OI-012 缩减为最小 Spec-OI；取消 DEV-008/009；**单一 DEV-007** consolidated SiliconFlow MVP；DEV-006→PAUSED/SUPERSEDED_FOR_MVP；最小 master_plan retarget |
| 受影响任务 | OI-012（planned，Amendment 002）；DEV-006（paused/SUPERSEDED_FOR_MVP）；DEV-007（planned consolidated）；**移除** DEV-008/009 占位；EXT-007/RET-001/RET-002/v0.1.0-bootstrap 最小 retarget |
| 是否改变技术规格 | **是（预期，最小）**：默认 provider SiliconFlow；TEI optional 叙事 |
| 审批 | Amendment 002 pending plan review；**本轮不 PLAN_LANDING** |

### CHANGE-016

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-09 |
| 原因 | 登记 **DEV-007** 初版 Task Plan：SiliconFlow Embedding Client MVP（Protocol + Client + Settings + mocked tests + opt-in integration）；OI-012 完成后单一 downstream 实施任务 |
| 受影响任务 | DEV-007（`planned`）；**不**修改 DEV-006/PR #13；**不**开始实施直至 `PLAN_APPROVED` |
| 是否改变技术规格 | **否**（对齐 OI-012 已 merge 的最小 Contract） |
| 审批 | Planner 初版；等待独立 Plan Review → `PLAN_APPROVED` |

### CHANGE-017

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-09 |
| 原因 | **DEV-007 Amendment 001**（Input Validation Simplification）：移除字符 guard / 本地 token 计数合同；超长输入交由 SiliconFlow API `400` fail-fast；U7 移出必测矩阵 |
| 受影响任务 | DEV-007（`planned`；Amendment 001 待 Plan Review） |
| 是否改变技术规格 | **否**（简化客户端校验策略；对齐 OI-012 已 merge Contract） |
| 审批 | Amendment 001 pending plan review |

### CHANGE-018

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-09 |
| 原因 | **DEV-007 completed**：SiliconFlow Embedding Client MVP merged（PR #17 `b7916ea`）；`EmbeddingClient` + `SiliconFlowEmbeddingClient`；Settings pivot `siliconflow`；mocked contract + human opt-in integration PASS dim=1024 |
| 受影响任务 | DEV-007（`completed`）；Phase 0 bootstrap（`v0.1.0-bootstrap`）就绪；EXT-007 / RET-001 / RET-002 embedding 前置满足；DEV-006 仍 PAUSED |
| 是否改变技术规格 | **否**（实现 OI-012 已批准 Contract） |
| 审批 | POST_MERGE_CLEANUP `docs(status): complete` |

### CHANGE-019

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-09 |
| 原因 | 用户显式 NEW_UNPLANNED_FEATURE：**DEV-OPS-006** Phase 0 Baseline Hygiene Before STM-001（unit compose-wrapper allowlist + progress DOC_CODE_DRIFT）；根因分类 **A** |
| 受影响任务 | 新增 `DEV-OPS-006`（现 `completed`；PR #18 MERGED `3e727b3dc1a168863d7fa6e8d52a175d36de4644`）；**不**实现 STM-001；**不**触碰 DEV-006/PR #13；**不**改 TEI 12g / SiliconFlow / compose*.yaml |
| 是否改变技术规格 | **否** |
| 审批 | Plan Reviewer PLAN_APPROVED（BLOCKER=0 MUST_FIX=0）；人工确认 PLAN_APPROVED；PLAN_LANDING 完成；CODE_REVIEW_APPROVED（P0=0 P1=0）；IMPLEMENTATION_RELEASE 完成；PR #18 MERGED；POST_MERGE_CLEANUP 本轮 |

### CHANGE-020

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | 用户显式 `START_EXISTING_TASK=STM-001` + `WORKFLOW_MODE=NORMAL`：登记 STM-001 Task Plan（Token heuristic + WM Key/字段模型 + 配置不等式定向 Unit）；Phase 0 gates GO；DEV-002 SATISFIED |
| 受影响任务 | `STM-001` → `planned`（计划文件 `02_开发管理/tasks/STM-001-token-estimator-wm-key-model-config-validation.md`）；**不**扩大为 STM-002+；**不**触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner 初版；Round 1 PLAN_REJECTED（MUST_FIX=1）；Amendment 001 PLAN_REMEDIATION；待 Plan Review Round 2 → 人工确认；确认前不得 PLAN_LANDING / Developer |

### CHANGE-021

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-001 Plan Review Round 1 `PLAN_REJECTED`（MUST_FIX=1）：`max_compressed < trigger` 须为 MANDATORY STARTUP VALIDATION CONTRACT；吸收 SHOULD_FIX 1–4 |
| 受影响任务 | `STM-001` 保持 `planned`；Amendment 001 修订 Task Plan；**不**扩大 scope；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Planner Amendment 001；待 Plan Review Round 2 → 人工确认 |

### CHANGE-022

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | **STM-001 completed**：Token heuristic estimator + WM key/field models + ContextSettings strict inequality validation evidence merged（PR #19 `6f2081da6266282470948ecac8e62ef3ae969c15`） |
| 受影响任务 | `STM-001`（`completed`）；`STM-002`（`planned`；prerequisites satisfied — **READY_FOR_PLANNING only**）；**不**开始 STM-002 实施；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否**（实现 §1.2.1 / §1.2.6 既有 Contract；`validators.py` 未改） |
| 审批 | POST_MERGE_CLEANUP `docs(status): complete` |

### CHANGE-023

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | 用户显式 `START_EXISTING_TASK=STM-002` + `WORKFLOW_MODE=NORMAL`：登记 STM-002 Task Plan（Session 创建 API + Redis WM meta 初始化）；复用 STM-001 模型与 DEV-005 API 壳 |
| 受影响任务 | `STM-002` → `planned`（计划文件 `02_开发管理/tasks/STM-002-session-creation.md`）；**不**扩大为 STM-003+；**不**触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner 初版；待 Plan Review → 人工确认；确认前不得 PLAN_LANDING / Developer |

### CHANGE-024

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | **STM-002 completed**：Session 创建 API + Redis WM meta 初始化 merged（PR #20 `efb39bf0bbbb408626e3d187d81b889dafc7a351`） |
| 受影响任务 | `STM-002`（`completed`）；`STM-003`/`STM-004`（prerequisites STM-002 **SATISFIED** — **READY_FOR_PLANNING only**）；**不**开始 STM-003 实施；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否**（实现 §1.2.3 / §1.2.7 / §3.21 既有 Contract；Amendment 001 Human Contract 已落实） |
| 审批 | POST_MERGE_CLEANUP `docs(status): complete` |

### CHANGE-025

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | 用户显式 `START_EXISTING_TASK=STM-003` + `WORKFLOW_MODE=NORMAL`：登记 STM-003 Task Plan（消息写入 Lua + 领域服务；不含 HTTP/压缩） |
| 受影响任务 | `STM-003` → `planned`（计划文件 `02_开发管理/tasks/STM-003-message-write-lua.md`）；**不**扩大为 STM-009 HTTP/Coordinator；**不**触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner 初版；待 Plan Review → 人工确认；确认前不得 PLAN_LANDING / Developer |

### CHANGE-026

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-003 Plan Review Round 1 `PLAN_REJECTED`（MF-1：Lua 步骤顺序与 §10.1 OI-STM-003-002 矛盾）；Planner Amendment 001 修订 |
| 受影响任务 | `STM-003`（`planned`；Amendment 001：§4.4/§5 Step 3 Lua 重排 EXISTS→身份→status→duplicate→容量→写入；`ARGV[7]=message_id`；Integration #14/#15 精确边界；`test_stm003_contract.py` 白名单）；**不**扩大 STM-009 范围；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否**（对齐已决议 OI-STM-003-002） |
| 审批 | Amendment 001；待 Plan Review Round 2 → 人工确认；确认前不得 PLAN_LANDING / Developer |

### CHANGE-027

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-003 Developer 实施完成（未 commit）：消息写入领域服务 + Redis Lua；Human 约束 malformed `estimated_tokens` fail-closed + Integration #16/#17 |
| 受影响任务 | `STM-003`（`tested`；scoped 21 / integration 11 / full unit 287 / contract 62；ruff/mypy PASS）；**不**扩大 STM-009 HTTP/Coordinator；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否**（实现 §1.2.1 写入 Lua 语义；新增内部 `invalid_session_state`） |
| 审批 | Developer tested；`next_action=Code Review`；未 commit |

### CHANGE-028

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-003 IMPLEMENTATION_RELEASE：implementation commit + PR #21 OPEN |
| 受影响任务 | `STM-003`（`committed`；implementation `e1913d17b159d426aadfd54d32e07c84ea61043a`；PR #21 OPEN）；**不**扩大 STM-009 HTTP/Coordinator；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator IMPLEMENTATION_RELEASE；`next_action=Human PR merge` |

### CHANGE-029

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-003 POST_MERGE_CLEANUP：PR #21 MERGED；docs(status): complete on main；删 exact feat |
| 受影响任务 | `STM-003`（`completed`；merge `3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4`）；`STM-004`/`STM-005`（prerequisites **SATISFIED** — **READY_FOR_PLANNING only**）；**不**扩大 STM-009 HTTP/Coordinator；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-004 READY_FOR_PLANNING only` |

### CHANGE-030

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | 用户显式 `START_EXISTING_TASK=STM-004` + `WORKFLOW_MODE=NORMAL`：登记 STM-004 Task Plan（上下文一致性只读 Lua + 领域服务；不含 HTTP/压缩写回） |
| 受影响任务 | `STM-004` → `planned`（计划文件 `02_开发管理/tasks/STM-004-context-read-lua.md`）；§10.1 OI-009 Planner 决议（读路径不更新 `updated_time`）；**不**扩大 STM-009 HTTP/Coordinator；**不**触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否**（OI-009 为 Planner 读路径语义决议；不修订规格正文） |
| 审批 | Planner 初版；待 Plan Review → 人工确认；确认前不得 PLAN_LANDING / Developer |

### CHANGE-031

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-004 Plan Review Round 1 `PLAN_REJECTED`（MF-1：I11 torn-read 空洞）；Planner Amendment 001 PLAN_REMEDIATION |
| 受影响任务 | `STM-004` → `planned`（Amendment 001）：I11 `NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID` 对抗性 torn-read；正式前置 STM-002 vs 实现复用 STM-001/003 区分；`ContextReadFailure`；空 messages 最小 3 元素 Lua 返回；**不**改 master_plan 表 STM-002 正式依赖；**不**扩大 STM-009；**不**触碰 DEV-006/PR #13；本轮只修订计划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner Amendment 001；待 Plan Review Round 2 → 人工确认；确认前不得 PLAN_LANDING / Developer |

### CHANGE-032

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-004 Plan Review Round 2 `PLAN_REJECTED`（MF-2：非原子 mutator 与 OLD/NEW-only 断言冲突）；Planner Amendment 002 PLAN_REMEDIATION Round 3 |
| 受影响任务 | `STM-004` → `planned`（Amendment 002）：I12 三段式 reader-composed torn-read（原子 test-only mutator + broken split-reader 确定性负对照 + 生产 Lua 正对照）；I10 `compressed_context` 缺失 fail-closed；13 Integration 场景；`__init__.py` 白名单；`ContextReadFailure` HTTP 映射归 STM-009；test-only helpers 仅 `tests/integration/**`；**不**扩大 STM-009；**不**触碰 DEV-006/PR #13；本轮只修订计划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner Amendment 002；待 Plan Review Round 3 → 人工确认；确认前不得 PLAN_LANDING / Developer |

### CHANGE-033

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-004 IMPLEMENTATION_RELEASE：implementation commit + PR #22 OPEN |
| 受影响任务 | `STM-004`（`committed`；implementation `3aed60522db64c3b11597e025caa0aae00afaba6`；PR #22 OPEN）；**不**扩大 STM-009 HTTP/Coordinator；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator IMPLEMENTATION_RELEASE；`next_action=Human PR merge` |

### CHANGE-034

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-004 POST_MERGE_CLEANUP：PR #22 MERGED；docs(status): complete on main；删 exact feat；OI-009 resolved |
| 受影响任务 | `STM-004`（`completed`；merge `6a3d09f5bf29ec25c768c6295e2c13adb3ff9a6c`）；`OI-009`（`resolved`）；`STM-005`（prerequisites **SATISFIED** — **READY_FOR_PLANNING only**）；**不**扩大 STM-009 HTTP/Coordinator；**不**触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否**（OI-009 为 Planner 读路径语义决议；不修订规格正文） |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-005 READY_FOR_PLANNING only` |

### CHANGE-035

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-005 Planner 初版：Mongo `context_archive` create/reuse Task Plan；progress 规划态回写 |
| 受影响任务 | `STM-005`（`planned`；plan `02_开发管理/tasks/STM-005-context-archive-create-reuse.md`）；OI-004 acknowledged 不阻塞；11 Integration 场景含并发同 key；**不** 新 migration；**不** Kafka/Redis pending；**不** 触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner；`next_action=计划审查` |

### CHANGE-036

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-005 POST_MERGE_CLEANUP：PR #23 MERGED；docs(status): complete on main；删 exact feat；OI-004 partial evidence（status remains open） |
| 受影响任务 | `STM-005`（`completed`；merge `164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf`）；`STM-006`（prerequisites **SATISFIED** — **READY_FOR_PLANNING only**）；**不** Kafka/Redis pending/compression/LLM/HTTP；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否**（OI-004 token-boundary 完整决议 deferred to STM-010） |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-006 READY_FOR_PLANNING only` |

### CHANGE-037

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | 用户显式 START_NEW_TASK：**DEV-OPS-007** Phase 1 Baseline Hygiene Before STM-006（orphan SHA `301c8d9…` metadata 更正 → main-lineage `b0736431…`；Ruff E501 `context_read_torn_read_helpers.py` L174–175 格式化-only） |
| 受影响任务 | 新增 `DEV-OPS-007`（`planned`；plan `02_开发管理/tasks/DEV-OPS-007-phase1-baseline-hygiene-before-stm006.md`）；**不** 实现 STM-006；**不** 改 STM-005/004 `src/**`；**不** resurrect orphan；**不** 触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner；`next_action=计划审查` |

### CHANGE-038

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | 用户显式 START_EXISTING_TASK：**STM-006** Compression Lock / Pending Archive / Kafka `context.archive.created`；Planner 初版 Task Plan |
| 受影响任务 | `STM-006`（`planned`；plan `02_开发管理/tasks/STM-006-compression-lock-pending-archive-kafka.md`）；OI-004 open acknowledged 不阻塞；OI-005 进程内生产者决议；**不** LLM/Finalize/HTTP/STM-011；**不** 触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner；`next_action=计划审查` |

### CHANGE-039

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-006 Plan Review Round 1 `PLAN_REJECTED`（MF-1）；用户选定方案 A；Planner Amendment 001 / Round 2 remediation |
| 受影响任务 | `STM-006`（`planned`；Amendment 001：`PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED`；SF-1–5 已吸收；plan `02_开发管理/tasks/STM-006-compression-lock-pending-archive-kafka.md`）；**不** 实施；**不** PLAN_LANDING；**不** Git 写；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否**（收紧实现约束；不改 API/Schema） |
| 审批 | Planner；`next_action=计划审查`（Round 2） |

### CHANGE-040

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-006 Round 2 Plan Reviewer `PLAN_APPROVED`（BLOCKER=0 MUST_FIX=0）；Human `PLAN_APPROVED` Amendment 001；进入 PLAN_LANDING |
| 受影响任务 | `STM-006`（`approved`；plan `02_开发管理/tasks/STM-006-compression-lock-pending-archive-kafka.md`；feat `feat/STM-006-compression-lock-pending-archive-kafka`）；**不** 业务实施直至 Developer；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Human PLAN_APPROVED；Release Operator PLAN_LANDING |

### CHANGE-041

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-006 Developer 实施完成：compression lock + pending Lua（PREHELD atomic）+ Kafka `context.archive.created`；status→`tested` |
| 受影响任务 | `STM-006`（`tested`；feat `feat/STM-006-compression-lock-pending-archive-kafka`）；Human SF same-identity accounting fail-closed；**不** LLM/Finalize/HTTP/STM-011；**不** 触碰 DEV-006/PR #13；未 commit |
| 是否改变技术规格 | **否** |
| 审批 | Developer tested；`next_action=Code Review` |

### CHANGE-042

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-006 POST_MERGE_CLEANUP：PR #25 MERGED（`d704bc5421d346d46a48cb69a3a7ad956e94dbb8`）；docs(status): complete on main；删 exact feat |
| 受影响任务 | `STM-006`（`completed`）；`STM-007`（prerequisites **SATISFIED** for planning — **READY_FOR_PLANNING only**）；`STM-008`（prerequisite STM-006 **SATISFIED**；仍须 STM-007）；`STM-011`（prerequisite STM-006 **SATISFIED** — **READY_FOR_PLANNING only**）；**不** 自动启动 STM-007/008/011；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-007 READY_FOR_PLANNING only` |

### CHANGE-043

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | 用户显式 START_EXISTING_TASK=STM-007 + WORKFLOW_MODE=NORMAL；Planner 初版 Task Plan |
| 受影响任务 | `STM-007`（`planned`；plan `02_开发管理/tasks/STM-007-compression-llm-client-structured-output.md`）；baseline `dc74311d6658c87cb164283f9ec775e012aa93f5`；OI-004/OI-005 OUT OF SCOPE；**不** Redis/Mongo/Kafka/Finalize/Coordinator；**不** 触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner；`next_action=计划审查` |

### CHANGE-044

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-007 POST_MERGE_CLEANUP：PR #26 MERGED（`7a72b3a4c159032a411bd48dc920e52973ddab3e` mergedAt `2026-08-10T14:45:58Z`）；docs(status): complete on main；删 exact feat |
| 受影响任务 | `STM-007`（`completed`）；`STM-008`（prerequisites STM-006+STM-007 **SATISFIED** — **READY_FOR_PLANNING only**）；`STM-011`（prerequisite STM-006 **SATISFIED** — **READY_FOR_PLANNING only**）；`STM-009` NOT ready（needs STM-008）；OI-004/OI-005 remain open；**不** 自动启动 STM-008/011；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-008 READY_FOR_PLANNING only` |

### CHANGE-045

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | 用户显式 START_EXISTING_TASK=STM-008 + WORKFLOW_MODE=NORMAL；Planner 初版 Task Plan |
| 受影响任务 | `STM-008`（`planned`；plan `02_开发管理/tasks/STM-008-compression-finalize-lua.md`）；baseline `ff9a609009f2a151f2e1a4bf41e24be3bc3a2467`；OI-004/OI-005 OUT OF SCOPE（remain open）；**不** LLM/Kafka/Mongo/Coordinator/HTTP/Close/STM-011；**不** 触碰 DEV-006/PR #13；本轮只规划不实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner；`next_action=计划审查` |

### CHANGE-046

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-008 Plan Review Round 1 `PLAN_REJECTED`；Planner Amendment 001（HM-1 token 公式/I18 算术、HM-2 clamp 语义、吸收 SHOULD_FIX） |
| 受影响任务 | `STM-008`（`planned`；`plan_review_round: 2`；Integration **27** 场景；I18 new=500；I27 clamp 0）；OI-004/OI-005 remain open；**不** 实施；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Planner；`next_action=计划审查 Round 2` |

### CHANGE-047

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-10 |
| 原因 | STM-008 POST_MERGE_CLEANUP：PR #27 MERGED（`ac61680098d2ae2644bc8b990f057816c3218fca` mergedAt `2026-08-10T15:48:17Z`）；docs(status): complete on main；删 exact feat |
| 受影响任务 | `STM-008`（`completed`）；`STM-009`（prerequisites STM-003+STM-004+STM-008 **SATISFIED** — **READY_FOR_PLANNING only**）；`STM-011`（prerequisite STM-006 **SATISFIED** — **READY_FOR_PLANNING only**）；`STM-010` NOT ready（needs STM-009）；OI-004/OI-005 remain open；**不** 自动启动 STM-009/011；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-009 READY_FOR_PLANNING only` |

### CHANGE-048

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-11 |
| 原因 | STM-010 POST_MERGE_CLEANUP：PR #29 MERGED（`722e42d9e24d085b0ed671478730952ef7c92ad6` mergedAt `2026-08-11T02:14:24Z`）；docs(status): complete on main；删 exact feat；OI-004 resolved |
| 受影响任务 | `STM-010`（`completed`）；`STM-011`（prerequisite STM-006 **SATISFIED** — **READY_FOR_PLANNING only**）；`STM-013`（prerequisite STM-010 **SATISFIED** — **READY_FOR_PLANNING only**）；`STM-012` NOT ready（needs STM-011 + EXT-001）；OI-003/OI-004 resolved；**不** 自动启动 STM-011/013；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-011 READY_FOR_PLANNING only; STM-013 READY_FOR_PLANNING only` |

### CHANGE-049

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-11 |
| 原因 | STM-013 Plan Remediation Round 2：MF-1（`tests/e2e/` + `@pytest.mark.integration`；禁 `e2e` marker / `pyproject.toml`）；SF-1 Fixture A config parity；SF-2 Kafka 矩阵 §5.0#6=§8.4；SF-3 compose test 栈启动序与 container IP |
| 受影响任务 | `STM-013`（`planned`；`plan_review_round: 2`；`next_action=计划审查`）；**不** 自动实施 |
| 是否改变技术规格 | **否** |
| 审批 | Planner Round 2 remediation |

### CHANGE-050

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-11 |
| 原因 | 用户显式 NEW_TASK：**DEV-OPS-008** Compose test-stack runtime compatibility（C1 aiokafka 0.13 `bootstrap_connected` + C2 ES 9.4 mapping readback `element_type`）；STM-013 scope remediation 已将生产修复移出 PR #30；blocks STM-013 |
| 受影响任务 | 新增 `DEV-OPS-008`（`planned`；plan `02_开发管理/tasks/DEV-OPS-008-compose-test-stack-runtime-compatibility.md`）；`STM-013`（`blocked`；PR #30 OPEN MUST NOT MERGE）；**不** commit `tests/e2e/**`；**不** cherry-pick `975e6029` wholesale；**不** 触碰 DEV-006/PR #13；分支从 main @ `390af52` 创建（NOT feat/STM-013） |
| 是否改变技术规格 | **否**（读回兼容与 runtime 探针对齐 pinned 依赖；CREATE mapping 不变） |
| 审批 | Planner；`next_action=计划审查` |

### CHANGE-051

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-11 |
| 原因 | 用户显式 NEW_TASK：**DEV-OPS-009** Restore authoritative Kafka LZ4 runtime support；权威 lz4 配置下 fresh image `RuntimeError: Compression library for lz4 not found`；根因缺失 `cramjam`（aiokafka 0.13 lz4 extra） |
| 受影响任务 | 新增 `DEV-OPS-009`（`planned`；plan `02_开发管理/tasks/DEV-OPS-009-kafka-lz4-runtime-support.md`）；`DEV-OPS-008` authoritative validation **BLOCKED_BY_DEFECT_FIX** pending DEV-OPS-009；`STM-013`（`blocked`；blocking_task→DEV-OPS-009；PR #30 OPEN MUST NOT MERGE）；**不** 修改 PR #30/#31；分支从 main 创建 |
| 是否改变技术规格 | **否**（补齐运行时依赖以兑现 §3.19 lz4 配置；不改 API/Schema/压缩 Contract） |
| 审批 | Planner；`next_action=计划审查` |

Master Plan 如需再变，必须新增变更编号，禁止静默修改任务目标、依赖或验收标准。
