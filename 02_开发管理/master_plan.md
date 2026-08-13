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
| DEV-OPS-008 | Compose test-stack runtime compatibility (aiokafka 0.13 + ES 9.4 mapping API) | 非业务：C1 runtime kafka readiness + C2 ES mapping readback compat；blocks STM-013 | STM-010 | completed |
| DEV-OPS-009 | Restore authoritative Kafka LZ4 runtime support for memory-api test/runtime image | 非业务：cramjam 生产依赖闭合权威 lz4；unblocks DEV-OPS-008 authoritative validation | main | completed |

#### DEV-OPS-009 Restore authoritative Kafka LZ4 runtime support for memory-api test/runtime image

- **目标**：在保持权威 `kafka_producer.compression_type=lz4` 前提下，补齐 aiokafka 0.13 LZ4 后端（`cramjam>=2.8`），使 memory-api runtime/test 镜像内 `AIOKafkaProducer` 可初始化、lifespan 可启动、`/health/ready` 可达且可向 test Kafka 真实发送 lz4 记录。
- **根因**：**A** — `pyproject.toml`/`uv.lock` 仅声明 `aiokafka>=0.13,<0.14`，未安装 aiokafka `lz4` extra 解析的 `cramjam`；Dockerfile runtime 完整复制 `.venv`，非 stage 遗漏。
- **非目标**：改 gzip/null 压缩；修改 `configs/base.yaml`；吸收 DEV-OPS-008 C1/C2；修改 STM-006/PR #30；merge PR #30/#31。
- **阻塞关系**：**blocks DEV-OPS-008 authoritative-runtime validation**；**blocks STM-013**（lz4 维度）；merge 顺序：DEV-OPS-009 → DEV-OPS-008 revalidate/merge → STM-013 sync main → E1–E4 → new Code Review。
- **关键修复**：`pyproject.toml` 追加 `cramjam>=2.8,<3` + `uv lock`；lz4 codec/producer init 单测 + Kafka lz4 发送集成测。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-009-kafka-lz4-runtime-support.md`
- **插入说明**：用户显式 NEW_TASK；`workflow_mode=NORMAL`（explicit）；分支必须从 **main** 创建（NOT feat/STM-013；NOT feat/DEV-OPS-008）。
- **状态备注**：`completed`（plan_commit `8367e7b6953fe6776d35865375a9aa48b02877f0`；implementation `90cd79cbc7235cc444b8ff67357a4d229399af1f`；governance completion `e5ed43bee0310f3c42d977d5bd109f96d7522cb2`；PR #32 MERGED `f754db8a9b406f62180f33d8a09e412ccc7c605b` mergedAt `2026-08-11T09:36:27Z`；cramjam>=2.8,<3 + lz4 unit/integration tests；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；`workflow_mode=NORMAL`；feat 分支已删）；**unblocks DEV-OPS-008 authoritative-runtime validation**；STM-013 lz4 维度 SATISFIED。

#### DEV-OPS-008 Compose test-stack runtime compatibility (aiokafka 0.13 + Elasticsearch 9.4 mapping API)

- **目标**：修复 compose test stack 上 `memory-api` lifespan/readiness 与 pinned **aiokafka 0.13.0** / **Elasticsearch 9.4.4** 不兼容（C1 `bootstrap_connected` AttributeError；C2 `element_type` GET mapping 省略导致 `assert_mapping_compatible` ValueError）；**SOURCE-ALIGNED fresh image** 可审计验证。
- **根因**：C1 — aiokafka 0.13 移除 `AIOKafkaClient.bootstrap_connected`；C2 — ES 9.4 GET mapping 省略默认 `element_type`。
- **非目标**：修改 `MEMORY_RETRIEVAL_V1_MAPPINGS` CREATE schema；Kafka producer 配置/生命周期/STM-006 publish；`tests/e2e/**`；merge PR #30；DEV-006/PR#13。
- **阻塞关系**：**blocks STM-013**（`release_gate=BLOCKED_BY_DEFECT_FIX`；PR #30 OPEN MUST NOT MERGE）。
- **关键修复**：`runtime.py` hasattr guard + start() fallback；`assert_mapping_compatible` element_type 仅双方非 None 且不等时 fail-closed（prototype 975e6029 evidence）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-008-compose-test-stack-runtime-compatibility.md`
- **插入说明**：用户显式 NEW_TASK；`workflow_mode=NORMAL`（explicit）；分支必须从 **main @ 390af52** 创建（**NOT** feat/STM-013）；STM-013 保持 blocked。
- **状态备注**：`completed`（plan_commit `a464952021e3778bb8f29b96f867fc61619b8f76`；implementation `b2f29ee5eab17c02983ce5c041c7c821b8db8318`；PR #31 MERGED `49719b91e4be6c552c342fef45504166c919febd` mergedAt `2026-08-11T10:32:18Z`；POST_DEV-OPS-009 authoritative lz4 revalidation PASS；scoped C1 5 / C2 7 / unit 459 / contract 101；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；`workflow_mode=NORMAL`；feat 分支已删）；**C1/C2 blocker SATISFIED**；STM-013 pending sync/revalidation；**不得 merge PR #30** until revalidated。

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
| STM-011 | `republish_archive_event.py` 补发脚本 | §1.2.4, §3.4 | STM-006 | completed |
| STM-012 | 补发事件消费验证 | §1.2.4, §2.1.4 | STM-011, EXT-001 | completed |
| STM-013 | 短期记忆阶段 E2E + 关键失败注入 | §1, §3.28 | STM-010 | completed |

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

- **目标**：`scripts/republish_archive_event.py` 发布侧人工补发：按 `--archive-id` 从 Mongo 只读加载 Archive，生成 **新** `event_id`，经 `ArchiveCreatedEvent` + `publish_archive_created_event` 发布 `context.archive.created`（key=`user_id`；六字段）；at-least-once；exit 0/1/2；可选 `--user-id` ownership 校验；**不**使用 Redis/`compression_version`；**不**含 `base_compression_version` 于 Kafka。
- **非目标**：STM-012 消费验证；EXT-001 / `memory_extraction_task` 扫描（§836 批量扫描见 OI-STM-011-001）；HTTP Endpoint（OI-007 CLI-only）；Redis pending/lock；Mongo 写入；修改六字段 Contract。
- **规格章节**：§1.2.2、§1.2.4（§836）、§2.1.14 规则 6、§3.4。
- **正式前置依赖**：STM-006 — **SATISFIED**；STM-005（Mongo archive 模型）— **SATISFIED**。
- **计划文件**：`02_开发管理/tasks/STM-011-republish-archive-event.md`
- **规划备注**：Round 1；单 `archive_id` CLI MVP；`created_time` 取 Mongo `archive.created_time`（OI-STM-011-002）；复用 STM-006 publisher；新增 `find_context_archive_by_id` + `archive_event_republish_service`；测试 Unit/Contract/Kafka Integration；**无** EXT consumer 断言。
- **状态备注**：`completed`（plan_commit `68cee46011f011f3074662f846c64da670741cb3`；implementation `23939a3f3d25f5243978e967949beb4fe6282e2f`；PR #33 MERGED https://github.com/xu-jia-ming/memory_system/pull/33 merge `19fdb55359acd97380a8b5f0d8ae788134f75307` mergedAt `2026-08-11T12:17:49Z`；`workflow_mode=NORMAL`）；`scripts/republish_archive_event.py` + `archive_event_republish_service`；`find_context_archive_by_id`；`ArchiveCreatedEvent` + `publish_archive_created_event`；exit 0/1/2；scoped unit 16 / contract 3 / kafka int 5；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3；feat 分支待删；**STM-012 NOT ready**（needs EXT-001）；**不得触碰 DEV-006/PR#13**。
- **测试**：Unit（malformed input / not found / ownership / invalid / success / publish fail / payload exactness / exit codes）+ Contract（枚举/六字段）+ Kafka Integration；不依赖 EXT-001。

#### STM-012

- **目标**：补发事件被 Extraction Consumer 消费的 Integration/E2E 验证（任务幂等创建等）；主路径为真实 STM-011 CLI → Kafka → EXT-001 consumer adapter → Mongo。
- **前置**：STM-011 — **SATISFIED**；EXT-001 — **SATISFIED**。
- **非目标**：修改补发脚本业务语义、EXT-001/STM-011 Contract、生产 Extraction Pipeline；不要求 EXT-002；不触碰 DEV-006/PR#13。
- **计划文件**：`02_开发管理/tasks/STM-012-republish-extraction-consumer-integration.md`
- **规格章节**：§1.2.4、§2.1.1、§2.1.3–§2.1.5、§3.4、§3.6、§3.19–§3.20、§3.32。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；baseline `d6e7941eeaa2a8409b09eaf181d2924eb3865138`；production delta **NONE**；Round 2 remediation（prior review BLOCKER=0 / MUST_FIX=1 / SHOULD_FIX=3）固定 CLI `uv run python scripts/republish_archive_event.py --archive-id <id> --user-id <id>`；test-only subprocess env 显式覆盖 `APP_ENV=test`、Mongo `<mongo_ip>:27017`、Kafka `<kafka_ip>:9092`、DB `memory_system`、topic `context.archive.created`、non-secret runtime settings，并明确覆盖 Docker-internal `mongodb`/`kafka` names；EXT-001 `group_id` 显式注入唯一 test group，production default 保持 `memory-extraction-group`；真实 Mongo/Kafka 与 STM-011 CLI；EXT-001 library consumer；test-only `ExtractionPipelinePort` Fake 仅返回 `PipelineTerminalDecision.complete()`；首次/重复补发断言新 event_id、稳定 archive_id、topic/key/精确六字段、单 task、非破坏性重复；offset 仅证明 valid event consumed、terminal Mongo state exists、that record commit passed，不声明 Mongo/Kafka atomicity；malformed/key-mismatch 不复制 EXT-001 suite；exact whitelist 未扩展；PLAN_REVIEW + human PLAN_APPROVED 后方可实施。
- **Amendment 002 规划登记（Round 3）**：实际 `Settings` env names 为 `_REQUIRED_ENV_KEYS` 加 `KAFKA__TOPIC`，precedence 为 `env > dotenv > YAML > init/defaults`；CLI 固定为 repository-root `python scripts/republish_archive_event.py --archive-id <id> --user-id <id>`，sanitized subprocess env 仅允许 `PATH`/`PYTHONPATH` 与 exact pinned non-secret application values，禁止 `os.environ.copy()`；host-reachable Mongo/Kafka endpoints、finite timeout、captured diagnostics、unique bounded raw reader、exact test-only `ExtractionPipelinePort` Fake（first=1，duplicate total=1）均为实施门禁；baseline、exact whitelist、production delta **NONE** 不变。
- **状态备注**：`completed`（plan_commit `b0cc223c60d0d8a1011a7a92e8f705285726792d`；implementation `26aa710d62123d341fb79349c9ad86fc5d58c0a6`；record `c99dcf45189da1f5779bda6bf6d35d5853d8bc1b`；PR #35 MERGED https://github.com/xu-jia-ming/memory_system/pull/35 merge `d73207752bbf004a4b20bf8fff00720cc0ca456b` mergedAt `2026-08-11T15:20:30Z`；`workflow_mode=NORMAL`）；integration **1 passed**（59.97s）；ruff **PASS**；mypy **PASS**；production delta **NONE**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=2；feat 分支已删；**EXT-002 remains planned** — **NOT auto-started**；**不得触碰 DEV-006/PR#13**。

#### STM-013

- **目标**：STM 阶段端到端（**公共 HTTP API** 驱动）：Session Create → Message Write → Archive → Compression（Coordinator + FakeLlmClient）→ 压缩后继续写入 → Session Close；含 §3.28 STM 子集失败注入（E2 幂等 / E3 并发 write-vs-close / E4 LLM 失败 HTTP 200）；跨 HTTP + Redis + Mongo + Kafka 断言；**闭合 `v0.2.0-short-term-memory` 里程碑**。
- **非目标**：修改 STM-001~010 核心 Contract；STM-011 republish；STM-012 EXT 消费；§3.32 全链路 EXT/RET E2E；真实 DeepSeek/SiliconFlow/TEI；默认 **无** `src/**` 生产变更（缺陷 HALT）。
- **计划文件**：`02_开发管理/tasks/STM-013-short-term-memory-e2e.md`
- **规格章节**：§1.2.1–§1.2.7、§1.2.4、§3.23、§3.28（STM 子集）、§3.32（STM 垂直切片）。
- **正式前置依赖**：**STM-010** — **SATISFIED**。
- **非 blocker**：STM-011（republish 非 E2E 前提）；STM-012（需 EXT-001）。
- **测试**：E2E only（`tests/e2e/test_stm013_short_term_memory_e2e.py`）；`@pytest.mark.integration`；scoped `pytest tests/e2e/...`（**非** `-m e2e`）；E1–E4；compose.test.yaml + memory-api；E4 hybrid in-process `FakeLlmClient(mode=timeout)`。
- **规划备注**：TEST/E2E FIRST；`plan_review_round: 2`（MF-1 OPTION 2 + SF-1 config parity + SF-2 Kafka 矩阵 + SF-3 compose 启动序）；Fixture A settings == memory-api runtime；test 栈 HTTP 经 container IP；bounded Kafka poll 过滤 `user_id`/`session_id`/`archive_id`；`workflow_mode=NORMAL`。
- **状态备注**：`completed`（plan_commit `39fab9e564d005d7a8c6409c7b293a6d337741f8`；implementation `91f8fd1c147e370b8b264b8b896163047df77163`；PR #30 MERGED `f473c194dd092fe3b30be5cf356ec533fc32fef8` mergedAt `2026-08-11T11:17:33Z`；final image `sha256:fa55a730…`；authoritative lz4；E1–E4 PASS；scoped E2E 4 / unit 459 / contract 101；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；shim removed；`workflow_mode=NORMAL`；feat 分支已删）；**closes `v0.2.0-short-term-memory` milestone**；**STM-012 NOT ready**（needs EXT-001）。

---

### Phase 2：长期记忆萃取

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| EXT-001 | Task Schema + Kafka Consumer 幂等/Offset | §2.1.3, §2.1.4 | STM-006, DEV-004 | completed |
| EXT-002 | Archive 读取/预处理/脱敏 | §2.1.5 | EXT-001 | completed |
| EXT-003 | LLM Extraction + Fingerprint | §2.1.6–2.1.8 | EXT-002, STM-007 | completed |
| EXT-004 | Entity Alignment + Neo4j 模型基础 | §2.1.9, §2.1.10 | EXT-003, DEV-004 | completed |
| EXT-005 | Reconciliation + 聚合门禁 | §2.1.11 | EXT-004 | completed |
| EXT-006 | Neo4j 图谱事务写入 | §2.1.12, §2.1.13 | EXT-005 | completed |
| EXT-007 | Retrieval Document 同步 | §2.2.3, §2.2.4 | EXT-006, DEV-007, DEV-004 | completed |
| EXT-008 | Extraction 管理 GET/Retry | §2.1.14 | EXT-007, DEV-005 | completed |
| EXT-009 | Extraction E2E + 失败注入 | §2.1.15, §3.28 | EXT-008 | completed |

#### EXT-001

- **目标**：`memory_extraction_task` Schema（§2.1.3 字段全集）+ Kafka Consumer 幂等 Upsert（`$setOnInsert` / `archive_id` unique）+ §2.1.4 状态分支与 Offset 门禁（`enable_auto_commit=false`；终态 Mongo 成功后才 Commit；group=`memory-extraction-group`）；可注入 `ExtractionPipelinePort`（真实 Pipeline 属 EXT-002+）。
- **非目标**：STM-012；EXT-002+ Archive/LLM/Neo4j/ES；人工重试 API；修改 Migration 001/004；发明 task 字段（`session_id`/`event_id` 落库）；DEV-006/PR#13。
- **计划文件**：`02_开发管理/tasks/EXT-001-task-schema-kafka-consumer-idempotency-offset.md`
- **正式前置依赖**：STM-006 — **SATISFIED**；DEV-004 — **SATISFIED**（001 indexes + 004 topic 复核 MATCH；migrate 测试补 `memory_extraction_task` 索引断言）。
- **规划备注**：Round 2 remediation（Amendment 001）；`workflow_mode=NORMAL`（explicit）；baseline `f4015cdca8694c3c2be96992a4957b2838c873e4`；MF-001 consumer-boundary exact six-key（不改 `ArchiveCreatedEvent`）；MF-002 key≠user_id fail-closed；SF-001 `main()` exit≠0；OI-001/002/003 open；OI-004 plan-resolved；C6 四类幂等语义保留。
- **状态备注**：`completed`（Human PLAN_APPROVED Round 2；plan_commit `6f716946638d9585f0aa53854723559b9f8044bb`；implementation `afd8b64dfd4856b4a2f00f82846dace76617e0d1`；record `b16c2e05c351cf5402489262a601f9e3afcd20ba`；PR #34 MERGED https://github.com/xu-jia-ming/memory_system/pull/34 merge `ae346dd27cda39f93fa38b7316ec17559df217ef` mergedAt `2026-08-11T13:57:07Z`；`workflow_mode=NORMAL`）；ExtractionTask schema + Mongo upsert by `archive_id` + Kafka consumer exact six-key validation + key mismatch fail-closed + Offset 门禁；scoped 61 passed（unit/contract 49、Mongo/migration 5、Kafka 8）；Ruff/Mypy PASS；CODE_REVIEW_APPROVED Round 2 P0=0 P1=0 P2=0 P3=1；feat 分支待删；STM-012 prerequisites **SATISFIED** — **READY_FOR_PLANNING only**；**不得**自动启动 STM-012；**不得**触碰 DEV-006/PR#13）。

#### EXT-002–EXT-006（摘要）

- 各自单 Commit：预处理；LLM；实体对齐；和解；图谱事务（在 EXT-001 任务状态机与 Offset 之后）。
- **风险**：~~OI-006~~ → EXT-008 Plan 以 LD-1 `POST .../rebuild` 闭合（MVP_LOCAL_DECISION；非规格正文变更）。

#### EXT-002

- **目标**：读取不可变 `context_archive`（按事件 `archive_id`），在预处理前区分缺失 Archive、结构损坏、有效文档中的消息级无效数据和有效可预处理 Archive；严格无 coercion、结构损坏不做部分预处理；保留 Archive 顺序/来源并构建临时标准化输入；空 Archive 通过既有 EXT-001 终态/Offset 门禁完成；在 LLM 前执行 Amendment 004 固定的凭证脱敏门禁。`ExtractionReadyArchive` 仅在 raw validation PASS → preprocessing PASS → redaction PASS 后最终化为内部、非持久化 handoff，不是本任务新增的公开/持久化 Schema。
- **计划文件**：`02_开发管理/tasks/EXT-002-archive-read-preprocess-redact.md`
- **规格章节**：§1.2.2、§1.2.4、§2.1.1、§2.1.3–§2.1.6、§2.1.15、§2.1.16、§3.6、§3.19、§3.20、§3.27、§3.28。
- **正式前置依赖**：EXT-001 — **SATISFIED/completed**（PR #34 MERGED；`archive_id` 幂等、`ExtractionPipelinePort`、终态持久化/Offset 门禁已合并）。
- **状态备注**：`completed`（implementation `7fdf84827b2c253a6e6734b8051467f3ec1151f1`；amendment `985613be08814b1e9eea521888b61dd5cb8d94ff`；record `036d770268c3a3bbb95fe4687fd0007805e284a4`；completion `cd0b1a33848b294b5b068891f2a02422767becf1`；PR #36 MERGED `59e9f7f0cf6effd34d1f13ad022f9b9eb00b8f2d`；RAW-01..12 PASS；RED-01..27 PASS；mandatory skips=0；scoped rerun=165 passed；Ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=0；Amendment 004 effective behavior, terminal/offset gate, privacy and production scope verified；STM-007 completed；EXT-003 prerequisites SATISFIED — planned / NOT AUTO-STARTED；feat 分支 cleanup pending；不得触碰 DEV-006/PR#13）。
- **规划备注**：Round 4 / Amendment 004；`workflow_mode=NORMAL`（explicit）；baseline `13e1dae36a0b0d94415d9581b2a5fe53c990545f` MATCH；本轮仅更新 Task Plan、open_issues、progress、master_plan，未修改规格正文。EXT-002 只允许新增 `find_context_archive_document_by_id(mongodb, archive_id)` 这一 read-only raw BSON mapping lookup；不得写入、修复、迁移、复制持久化模型或改变既有 typed `find_context_archive_by_id` 语义。RAW-01..RAW-12 与 RED-01..RED-27 覆盖严格七字段/四字段消息验证、未知字段、`_id` 例外、无 coercion、无部分输出及全部脱敏正负/跨度/失败/泄漏/来源/顺序场景。缺失映射为 `archive_not_found/archive_read`；结构或嵌套/消息无效映射为 `invalid_archive/archive_validate`；redaction failure 为 `redaction_failed/redaction`；非确定性基础设施/内部失败为 `abort_without_terminal`；终态持久化成功后才提交 Offset。确定性本地 redaction 仅作用 `messages[].content`，精确类别/优先级/span 合并/Luhn/marker 规则已由 authoritative Amendment EXT-002-004 固定。first-person deferred/out-of-scope；`ExtractionReadyArchive` 仅在 raw validation → deterministic preprocessing → deterministic redaction 后最终化；dependency_changes_expected=NONE。
- **阻塞项**：无 EXT-002 blocking Open Issue；OI-EXT-002-001/002/004/005 resolved，OI-EXT-002-003 deferred/out-of-scope。可实施范围仍不含 EXT-003/LLM/Neo4j/Elasticsearch；不得扩展到 Kafka/task status/STM-011/012、DEV-006 或 PR #13。
- **非目标**：Kafka/EXT-001 Contract、offset/state 语义、`context_archive` schema/repository 与 STM 写入、EXT-003 LLM/Prompt/Structured Output、EXT-004+、Neo4j/Elasticsearch、Migration/Settings/dependency、DEV-006、PR #13、E2E。

#### EXT-003

- **目标**：在 EXT-002 finalized `ExtractionReadyArchive` 之后执行 `memory_extraction_v1` Structured Extraction；严格消费 `archive_id/user_id/session_id` 和 ordered `message_id/role/normalized-redacted content/timestamp`；不依赖 first-person binding；复用 STM-007 `LLMClient`/DeepSeek/OpenAI/Fake conventions（MF-001：`llm.extraction` 路径，compression 不变）；应用层校验 §2.1.6–§2.1.7 + Appendix B schema、references、source user requirement、limits、event/time nullability；unknown fields parse 忽略、持久化前 strip；duplicate merge 与 fingerprint 按 Appendix B §B.7–B.8；由应用计算 `candidate_source_time` 并生成 exact `candidate_fingerprint`；将完整 validated result 持久化至既有 `memory_extraction_task.extraction_result`。
- **非目标**：EXT-004 entity alignment/数据库 IDs/relations/Neo4j；EXT-005 reconciliation；EXT-006 graph write；EXT-007 retrieval/Elasticsearch/Embedding；Evidence/evidence_id 生产写入；EXT-001 Kafka/task/offset semantics；EXT-002 redaction/first-person；`PipelineTerminalDecision` 修改；EXT-004 continuation 编排（`DEFERRED_FOR_MVP`）；DEV-006/PR #13；新依赖/新 config stack；默认真实 DeepSeek call；SHA-256 collision recovery（OI-EXT-003-005 deferred）。
- **计划文件**：`02_开发管理/tasks/EXT-003-llm-extraction-fingerprint.md`（Amendment 002）
- **规格章节**：§1.2.1、§2.1.3–§2.1.8、§2.1.15–§2.1.16、§3.9、Appendix A Amendment EXT-002-004、**Appendix B Amendment EXT-003**。
- **正式前置依赖**：EXT-002 — **SATISFIED/completed**（PR #36 MERGED）；STM-007 — **SATISFIED/completed**（PR #26 MERGED）；EXT-001 — **SATISFIED/completed**（PR #34 MERGED）。
- **状态备注**：`completed`（implementation `7c6309ee68b01a6604b79253cea65be6fa26a0c6`；record `b14d53d840e7ba69139ce050a5225eae92def220`；PR #37 MERGED `0eb45e20c64777a03dc770be70cba2316b47fdf6` mergedAt `2026-08-12T06:06:31Z`；scoped 63 passed；Ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=1 non-blocking；Appendix B behavior、terminal/offset gate、privacy and production scope verified；OI-EXT-003-005 **deferred_for_mvp**；EXT-004 prerequisites **PARTIAL**（EXT-003 completed；DEV-004 completed）— **planned / NOT AUTO-STARTED**；feat 分支 cleanup complete；不得触碰 DEV-006/PR#13）。
- **配置/依赖结论**：当前 `memory_extraction` limits、120-second timeout、`memory_extraction_v1`、DeepSeek extraction model、json_object、temperature=0、thinking disabled、stream=false、max_output_tokens=8192 和 `openai>=2.46,<3` 已存在；`dependency_changes_expected=NONE`；不得修改 Settings/manifest/lockfile。
- **关键门禁**：空 Archive 零 LLM call 并沿用 EXT-001 normal completion；非空 both-empty output 持久化后 `completed`+Offset；非空 `extraction_result` 持久化后 `processing` 不提交 Offset；invalid source refs → `llm_invalid_output`/`llm_extraction`（非 `invalid_archive`）；blank output → `llm_invalid_output`（非 `llm_empty_output`）；exact correction prompt §6.2；8000 token 不分块/不截断；LLM timeout/request/invalid output 仅使用 §2.1.15 codes at `llm_extraction`；schema failure 一次 correction retry、transport retry=0；failure logs 含 MF-002 metadata；无 prompt/response/raw/secret logging。
- **幂等/恢复**：completed task 跳过 LLM；processing 且已有 `extraction_result` 复用并跳过 LLM；source time/fingerprint 不用 server current time 重算；both-empty result write → complete+Offset；non-empty result write → processing no Offset；real LLM fresh calls may vary。
- **Open Issues**：OI-EXT-003-001/002/003/004 **resolved** by Appendix B；OI-EXT-003-005 **deferred_for_mvp**（SHA-256 collision，non-blocking）；无 blocking Open Issue；Round 2 Plan Review **PLAN_APPROVED**（BLOCKER=0 MUST_FIX=0 SHOULD_FIX=1）；human PLAN_APPROVED granted；SF-1 MVP_LOCAL_DECISION：`extraction_llm_service.py` orchestration owner；`approval_posture=PLAN_APPROVED`；`developer_authorized=true` post-PLAN_LANDING。
- **测试**：Unit（schema/reference/limits/prompt/retry/errors/fingerprint/privacy/empty/both-empty/duplicate）；Contract（input/output/provider/error/fingerprint/durable result/terminal boundary/legal-empty）；Integration(fake)（happy/both-empty/non-empty-processing/timeout/provider/malformed/retry/replay/no leakage）；Mongo/replay integration（result persistence/reuse）；real provider false/default skipped；无 EXT-004+ behavior。

#### EXT-004

- **目标**：在 EXT-003 已持久化 `extraction_result` 之后，实现 §2.1.10 的**纯确定性**实体对齐（S0–S6）与 §2.1.9 中对齐实际需要的 Neo4j Entity 模型基础；产出 `local_entity_id -> entity_id` 对齐映射、计划态新实体创建记录与计划态别名合并记录，供 EXT-005/EXT-006 消费。
- **非目标**：任何 Neo4j 写入（Entity/Memory/Evidence 节点、`SUBJECT`/`OBJECT`/`SUPPORTS`/`SUPERSEDES`/`CONFLICTS_WITH` 关系、别名落盘、写事务）；§2.1.11 已有 Memory 召回与 LLM Reconciliation、`aligned_memory_key`、候选聚合、`reconciliation_plan_conflict`；§2.1.12 置信度/重要性；§2.1.13 事务内写入与 `referenced_entity_write_set`；`memory_id` / `evidence_id` 生产写入；Retrieval/`core_search_text`/Elasticsearch/Embedding；EXT-005+；EXT-003→EXT-004 生产 continuation 编排（Appendix B §B.10.4 `DEFERRED_FOR_MVP`）；EXT-001/EXT-002/EXT-003 语义；Migration/依赖/配置/Settings；新错误码或新 `failed_stage` 字面量；DEV-006 / PR #13。
- **计划文件**：`02_开发管理/tasks/EXT-004-entity-alignment-neo4j-model-basis.md`（Round 2；Amendment 002）
- **规格章节**：§1.2.1、§2.1.3、§2.1.4、§2.1.6–§2.1.7（仅消费）、**§2.1.9**、**§2.1.10**、§2.1.13（事务前准备第 2 步与写入禁令）、§2.1.15–§2.1.16、§3.6、§3.24、§3.26–§3.28、Appendix A、Appendix B（§B.1/§B.2/§B.10/§B.11）。
- **正式前置依赖**：EXT-003 — **SATISFIED/completed**（PR #37 MERGED）；DEV-004 — **SATISFIED/completed**（§2.1.9 约束/索引已存在）；EXT-001/EXT-002 — **SATISFIED/completed**。
- **关键门禁**：持久化 `extraction_result` 为唯一抽取输入且零 LLM 调用；对齐阶段只读 Neo4j 且零写入（集成测试断言 Entity 节点/property/aliases 前后逐字不变）；所有 Cypher 显式 `user_id` 过滤并批量 `UNWIND`；对齐输出瞬态不持久化（`AUTHORIZED_ENTITY_FIELDS`/`AUTHORIZED_MEMORY_FIELDS` 零变更）；别名合并仅计划态（既有 alias 零删除、50 上限、`canonical_name` 永不替换、不发 `memory_entity_alias_omitted_total`）；失败仅映射 `entity_alignment_failed` 且**禁用** `graph_query_failed` 与全部 EXT-005+/EXT-003/EXT-002 码；`PipelineTerminalDecision` / consumer / `extraction_llm_service` / `extraction_worker` / Settings / metrics / 全部 Migration 零 diff。
- **幂等/恢复**：EXT-004 无任何副作用与自有状态，天然幂等；replay 以相同持久化输入与相同图谱状态得到相同匹配判定；图谱事务已提交的 replay 通过 `entity_key` 精确匹配复用既有节点，不重复计划创建；任务保持 `processing`，EXT-004 不执行状态迁移、不提交 Offset。
- **配置/依赖结论**：`dependency_changes_expected=NONE`（`neo4j>=5.28,<6`、§3.24 `Neo4jSettings`、`AppState.neo4j` 已存在）；**无** Migration/Schema 产物需求（DEV-004 已建 §2.1.9 约束/索引并有断言）；沿用既有 `max_entity_candidates_per_archive=100` / `max_stored_entity_alias_count=50`。
- **Open Issues**：~~blocking `OI-EXT-004-001`、`OI-EXT-004-002`~~ → Round 2 `resolved_by_plan`（MVP_LOCAL_DECISION）；非阻塞 `OI-EXT-004-003`、`OI-EXT-004-004`。
- **状态备注**：`completed`（PR #38 MERGED `229f5e960f51e55a7389599eeccdf650a9a7beff` mergedAt `2026-08-12T07:49:18Z`；implementation `0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c`；scoped 53 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2 non-blocking；read-only Neo4j alignment only；feat 分支已删；EXT-005 prerequisites **SATISFIED** — planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。
- **测试**：Unit（归一化向量/`entity_key`/用户实体固定字段；全部对齐分支、别名合并计划、失败映射、零 LLM 依赖、零写入、用户隔离、privacy 日志）；Contract（输入/输出契约、§2.1.9 property 集合、错误码白名单与 `failed_stage`、不持久化、只读 Cypher 文本、无 EXT-005+ 字段、上游/Migration/依赖零变更）；Integration（真实 Neo4j：命中/未命中/用户实体/跨用户隔离/零写入/查询失败注入/100 候选批量；真实 Mongo：持久化结果加载、Fake LLM 调用计数 0、replay 幂等、任务文档零变更）；无 E2E、无真实外部 provider 调用。

#### EXT-005

- **目标**：在 EXT-003 已持久化 `extraction_result` 且 EXT-004 已产出瞬态 `EntityAlignmentOutcome` 之后，实现 §2.1.11 只读 Memory 候选召回（确定性 `ORDER BY` + `LIMIT 20`）、逐候选 LLM Reconciliation（`CREATE`/`MERGE`/`SUPERSEDE`/`CONFLICT`/`SKIP` + `reason_code` + `merged_content` 校验）、`aligned_memory_key` 计算、Archive 内候选聚合与 `reconciliation_plan_conflict` 门禁；产出 §2.1.12 置信度/重要性计划值、§2.1.13 事务前准备第 1 步（`evidence_id` + 只读 Evidence 存在性 SKIP）、第 6 步（`increment_memory_version` 布尔）、第 7 步（预生成 `memory_id`）；形成瞬态非持久化 Reconciliation Plan 供 EXT-006 消费（Amendment 001：全部新 Memory 以自包含 `PlannedMemoryCreate` 行输出，`create_kind` + 链接字段）。
- **非目标**：任何 Neo4j/Mongo 写入；`referenced_entity_write_set`、`core_search_text`、TEI `/tokenize`、`memory_search_text_too_long`（EXT-006）；Retrieval/Elasticsearch/Embedding（EXT-007）；任务 `status` 变更与 Kafka Offset 提交；`PipelineTerminalDecision` / consumer / `extraction_llm_service` / `extraction_worker` / `entity_alignment_service` 语义变更；EXT-004→EXT-005 生产 continuation 编排（`DEFERRED_FOR_MVP`）；EXT-006+；EXT-003/EXT-004 语义变更；新错误码（优先 §2.1.15 既有码）；Migration/依赖/Settings 变更；DEV-006 / PR #13。
- **计划文件**：`02_开发管理/tasks/EXT-005-reconciliation-aggregation-gate.md`（Round 2；Amendment 001）
- **规格章节**：§1.2.1、§2.1.3–§2.1.4、§2.1.6–§2.1.7（仅消费）、§2.1.9（Memory/Evidence 只读快照）、**§2.1.11**、**§2.1.12**（计划输出）、**§2.1.13**（事务前准备第 1/3–7 步）、§2.1.15–§2.1.16、§3.6、§3.24、§3.26–§3.28、Appendix B（§B.7/§B.8/§B.10/§B.11/§B.12）。
- **正式前置依赖**：EXT-004 — **SATISFIED/completed**（PR #38 MERGED）；EXT-003 — **SATISFIED/completed**；DEV-004 — **SATISFIED/completed**（§2.1.9 约束/索引）；EXT-001/EXT-002 — **SATISFIED/completed**。
- **关键门禁**：持久化 `extraction_result` + `EntityAlignmentSuccess` 为唯一输入；只读 Neo4j（Memory 召回 + Evidence 存在性）且零写入；reconciliation LLM 复用 `LLMClient` + `settings.llm.extraction`（MF-001）；`failed_stage=reconciliation`（LD-10）；零召回确定性 `CREATE` 不调 LLM（LD-1）；输出瞬态不持久化；`new_memory_create_plans[]` 为全部新 Memory 自包含行（MF-001：`create_kind` + `supersedes_target_memory_id`/`conflicts_with_target_memory_id`）；`session_id` 不在 reconciliation 输出（SF-003）；失败码仅 `graph_query_failed`/`reconciliation_plan_conflict`/`llm_*`；`entity_alignment_failed` 禁用；任务保持 `processing`、不提交 Offset；上游 pipeline/alignment 零 diff。
- **幂等/恢复**：无副作用 → 天然幂等；Evidence 已存在 → SKIP；replay 相同输入+图谱状态 → 相同计划；崩溃后任务仍 `processing`。
- **配置/依赖结论**：`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；沿用 `memory_extraction.llm_timeout_seconds=120`、`max_memory_candidates_per_archive=50`；不新增 `llm.reconciliation` Settings。
- **Open Issues**：非阻塞 `OI-006`（`reconciliation_plan_conflict` 运维清理属 EXT-008）；无 blocking Open Issue。
- **状态备注**：`completed`（PR #39 MERGED `638598080b2d24e9291933c5ef92d3e4d65a0612` mergedAt `2026-08-12T09:47:46Z`；implementation `c6e619d312bfd83fef30c9f394e16b42a65cba81`；record `775992943ae0eb349301defb990c59c7089cf32e`；scoped 63 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=0 non-blocking；read-only reconciliation only；zero Mongo/Neo4j writes；OI-006 non-blocking；feat 分支已删；EXT-006 prerequisites **SATISFIED** — planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。
- **测试**：Unit（evidence_id、aligned_memory_key、聚合/conflict、LLM 校验、MF-001 create_kind 链接、SF-002 SKIP 排除、SF-004 mixed merged_content、失败映射、零写入、privacy）；Contract（输入/输出、无 session_id 于输出、MF-001 自包含新侧、错误码白名单、只读 Cypher、无 EXT-006+ 字段、上游零变更）；Integration（真实 Neo4j 召回/隔离/零写入/Evidence SKIP；真实 Mongo replay/任务零变更）；无 E2E、无默认真实 provider。

#### EXT-006

- **目标**：在 EXT-003 已持久化 `extraction_result`、EXT-004 已产出瞬态 `EntityAlignmentSuccess`、EXT-005 已产出瞬态 `ReconciliationSuccess` 之后，实现 §2.1.13 **第 8–10 步事务前准备**（`referenced_entity_write_set`、`planned_index_sync_memory_set`、`core_search_text`、TEI `/tokenize` 门禁、`memory_search_text_too_long`）与**单 Archive 原子 Neo4j 写事务**（Entity `MERGE`、Memory 创建/字段级更新、`SUPERSEDES`/`CONFLICTS_WITH`/`SUBJECT`/`OBJECT`/`SUPPORTS`、Evidence `MERGE`）；应用 §2.1.12 计划态置信度/重要性；产出瞬态 `index_sync_memory_set` 供 EXT-007。
- **非目标**：Elasticsearch/Embedding/`search_text` alias 扩展（EXT-007）；任务 `completed`/Kafka Offset（EXT-007）；重调 extraction/reconciliation/alignment LLM；`PipelineTerminalDecision`/consumer/worker/alignment/reconciliation 语义变更；EXT-003→EXT-006 continuation 编排（`DEFERRED_FOR_MVP`）；EXT-007+；DEV-006/PR#13；新错误码；Migration/依赖/Settings 变更。
- **计划文件**：`02_开发管理/tasks/EXT-006-neo4j-graph-transaction-write.md`（Round 1）
- **规格章节**：§1.2.1、§2.1.3–§2.1.4、§2.1.6–§2.1.7（Evidence 字段来源）、§2.1.9–§2.1.10、**§2.1.12**、**§2.1.13**（第 8–10 步 + 事务内写入）、§2.1.15–§2.1.16、§2.2.3（`core_search_text` 校验语义）、§3.6、§3.10、§3.24、§3.26–§3.28、Appendix B。
- **正式前置依赖**：EXT-005 — **SATISFIED/completed**（PR #39 MERGED）；EXT-004/EXT-003/EXT-001/EXT-002 — **SATISFIED/completed**；DEV-004 — **SATISFIED/completed**。
- **关键门禁**：三阶段成功输出 + 任务元数据为唯一输入；单 Neo4j 写事务；`evidence_id`/`entity_key`/`memory_id` MERGE 幂等；全 Evidence 已处理 SKIP；`failed_stage=graph_write`；`graph_write_failed`/`memory_search_text_too_long` 仅授权码；任务保持 `processing`、不提交 Offset；上游零 diff。
- **幂等/恢复**：写事务失败无部分图谱；replay 通过 Evidence SKIP 或 MERGE；成功图谱写入后仍 `processing` 待 EXT-007。
- **配置/依赖结论**：`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；最小 TEI `/tokenize` 端口（LD-4）。
- **Open Issues**：非阻塞 `OI-006`；无 blocking Open Issue。
- **状态备注**：`completed`（PR #40 MERGED `372e0232c1e5cfa1d71e2bb0152a22f59e60cd03` mergedAt `2026-08-12T12:12:38Z`；implementation `b19e913af3848e932b8adb404dc5d5304167fb73`；record `eafc07a3e01f376f4bd2c6c658c1dd5536c3b61f`；scoped 44 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2 non-blocking；atomic Neo4j graph write + `index_sync_memory_set` handoff；zero task completed/offset；OI-006 non-blocking；feat 分支已删；EXT-007 prerequisites **PARTIAL**（EXT-006 **completed**；DEV-007 **completed**；DEV-004 **completed**）— planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。
- **测试**：Unit（referenced_entity_write_set、core_search_text、plan builder、service 路径、幂等、失败映射、privacy）；Contract（输入/输出、错误码白名单、无 EXT-007+ 字段、上游零变更）；Integration（真实 Neo4j 写入/回滚/隔离/replay；Mongo 任务零变更）；无 E2E。

#### EXT-007 Retrieval Document 同步

- **目标**：在 EXT-006 Neo4j 提交后，按 §2.2.3 **扩展** `index_sync_memory_set`（闭合 EXT-006 LD-8 种子 handoff）、从 Neo4j 加载 Memory/Entity、构建含 alias 预算的 `search_text`（TEI `/tokenize`）、经 `create_embedding_client`（默认 SiliconFlow / DEV-007）生成 Embedding、Bulk Upsert 至 Alias `memory_retrieval_current`（`refresh=wait_for`、Document ID=`memory_id`）；全部成功后 **首次** `mark_completed`；失败 `mark_failed(retrieval_index_write_failed, failed_stage=retrieval_index)`。
- **非目标**：**不创建/修改** Mapping 或 Alias（DEV-004 已完成；缺失则失败）；**不**提交 Kafka Offset（EXT-001 consumer）；**不**修改 `PipelineTerminalDecision`/consumer/worker/EXT-001–006 服务；pipeline continuation `DEFERRED_FOR_MVP`；RET-* API；EXT-008/009；DEV-006/PR#13。
- **前置**：EXT-006（`GraphWriteSuccess.index_sync_memory_set` handoff）、DEV-007（`create_embedding_client`）、DEV-004（alias `memory_retrieval_current`）。
- **规格章节**：§2.1.3–§2.1.4、§2.1.13（完成顺序）、§2.1.15–§2.1.16、**§2.2.3**、**§2.2.4**、§3.6、§3.10、§3.24、§3.27–§3.28、Appendix B §B.10–§B.11。
- **分支**：`feat/EXT-007-retrieval-document-sync`。
- **依赖/Migration**：`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`。
- **幂等/恢复**：ES Upsert by `memory_id`；`status=completed` skip；Neo4j durable + 索引重试；Bulk 部分失败 → `failed` 直至重试全成功。
- **状态备注**：`completed`（PR #41 MERGED `afb2fee9ca6f7a5e049f0d9b1b22825de4c665dd` mergedAt `2026-08-12T13:27:51Z`；implementation `2cf93ec5bcb03daae6e266984df2804a09f19a0c`；record `d385f4b3553d310f89b17e832ea07c29b50d9761`；scoped 30 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=2 non-blocking；§2.2.3 index sync invariants + completed-before-offset gate preserved；ES bulk upsert + first `mark_completed` gate；zero upstream/offset diff；OI-006 non-blocking；feat 分支已删；EXT-008 prerequisites **SATISFIED**（EXT-007 **completed**；DEV-005 **completed**）— planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。
- **测试**：Unit（search_text alias 预算、集合扩展、失败映射、completed skip）；Contract（错误码/`failed_stage` 白名单、ES Document 形状、零上游 diff）；Integration（Neo4j+ES 真实写入、bulk 部分失败、replay upsert）；无 E2E（RET-006）。

#### EXT-008 Extraction 管理 GET/Retry/Rebuild

- **目标**：实现 §2.1.14 **Admin HTTP**：`GET /api/v1/memory/extraction/{user_id}/{archive_id}` 状态查询；`POST .../retry` 人工重试（仅 §2.1.15 可重试码、`failed` 态、保留 `extraction_result`）；闭合 **OI-006** 的 `POST .../rebuild`（MVP_LOCAL_DECISION LD-1：仅 `reconciliation_plan_conflict` → 清 `extraction_result` → `pending` + STM-011 Kafka republish）；Admin Key only（§3.21）；§3.23 错误包络；Mongo **唯一** durable 写入；**零** Offset / Neo4j / ES；consumer/worker/pipeline **零 diff**。
- **非目标**：通用 Admin 平台；HTTP 暴露 republish CLI / migrate；Pipeline 接线（`DEFERRED_FOR_MVP`）；EXT-009 E2E；DEV-006/PR#13。
- **计划文件**：`02_开发管理/tasks/EXT-008-extraction-admin-api.md`
- **规格章节**：§2.1.3–§2.1.4、**§2.1.14**、**§2.1.15**、§2.1.16、**§3.21**、**§3.23**。
- **正式前置依赖**：EXT-007 — **SATISFIED/completed**；EXT-001 — **SATISFIED/completed**；DEV-005 — **SATISFIED/completed**；STM-011 — **SATISFIED/completed**（`republish_archive_created_event`）。
- **关键门禁**：`user_id+archive_id` 404 `extraction_task_not_found`；永久错误/reconciliation_plan_conflict 误 retry → 409 `retry_not_allowed`；Kafka 失败 → `kafka_publish_failed` + `failed_stage=extraction_admin`（LD-2）；GET 不返回 `extraction_result`（LD-5）。
- **Open Issues**：**OI-006 resolved_by_task**（rebuild 窄契约）；无 blocking Open Issue。
- **依赖/Migration**：`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`。
- **分支**：`feat/EXT-008-extraction-admin-api`。
- **状态备注**：`completed`（PR #42 MERGED `8bee66be25e140cd59a8dd74faa733211ab44382` mergedAt `2026-08-12T14:07:04Z`；implementation `e8f15b458a6f1fa6e204393d5300a018bfc5c27b`；record `eefb52edea62c1d1a917f2393ff157c64421a2b0`；scoped 25 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=3 non-blocking；GET/retry/rebuild Admin HTTP；OI-006 resolved_by_task；LD-3 Mongo before Kafka；zero consumer/worker/pipeline diff；feat 分支已删；EXT-009 prerequisites **SATISFIED**（EXT-008 **completed**）— planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。
- **测试**：Unit（retry 表/rebuild 门禁/Kafka 失败回写）；Contract（路由/错误码/零 upstream diff）；Integration（TestClient + Mongo/Kafka fake）；无 E2E（EXT-009）。

#### EXT-009 Extraction E2E + Pipeline Wiring

- **目标**：闭合 EXT-003→EXT-007 **生产 pipeline continuation**（权威 owner）；`ProductionExtractionPipeline` 实现 `ExtractionPipelinePort` 串联 LLM（可跳过）→ Alignment → Reconciliation → Graph Write → Retrieval Index Sync；`extraction_worker.main()` 替换 exit 1 stub 接入 Kafka consumer loop；consumer **窄补丁** LD-1：COMPLETE/FAIL 前 reload，若 EXT-007 已 `mark_completed`/`mark_failed` 则 commit offset 无重复 `mark_*`（§2.1.13）；`extraction_result` 非空跳过 LLM 继续 alignment→index；E2E-1..4（happy / index fail after graph / replay idempotency / admin retry/rebuild）；compose.test Mongo/Kafka/Neo4j/ES + Fake LLM/Embedding/Tokenize（§3.28）；**零** EXT-002..007 阶段服务语义 diff。
- **非目标**：修改 `PipelineTerminalDecision` / 阶段库内部；RET-*；E2E-001 全链路；DEV-006/PR#13；新依赖/Migration。
- **计划文件**：`02_开发管理/tasks/EXT-009-extraction-e2e-pipeline-wiring.md`
- **规格章节**：§2.1.3–§2.1.4、**§2.1.13**、§2.1.14–§2.1.16、§2.2.3、**§3.28**、Appendix B §B.10。
- **正式前置依赖**：EXT-008 — **SATISFIED/completed**；EXT-007 — **SATISFIED/completed**；EXT-001..006 — **SATISFIED/completed**；DEV-005 — **SATISFIED/completed**。
- **关键门禁**：completed-before-offset；Evidence MERGE 幂等；index 失败 `retrieval_index_write_failed` + admin retry；`reconciliation_plan_conflict` → rebuild 非 retry。
- **Open Issues**：无 blocking。
- **依赖/Migration**：`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`。
- **分支**：`feat/EXT-009-extraction-e2e-pipeline-wiring`。
- **状态备注**：`completed`（implementation `d6a4bf596b78275ce3e8644a79e2dc8d218675d4`；record `ddfb89ca8e466e0802d9e98177295a9effb41725`；PR #43 MERGED `c05691144b650b22be714736de3c200076c340c3` mergedAt `2026-08-13T01:11:57Z`；scoped 33 passed；E2E 4 passed；Ruff PASS；Mypy remediation files PASS，full-repository baseline 143 errors；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0；ProductionExtractionPipeline 闭合 EXT-003→007 continuation；terminal Mongo 持久化先于 Kafka Offset；extraction_result replay 跳过 LLM，Retrieval ES upsert 收敛且无重复 Memory/Evidence/ES 文档；EXT-002..007 阶段语义零 diff；SAFE_AUTO_REMEDIATION 已按 ff-only 完成；feat 分支已删；RET-001 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。
- **测试**：Unit（pipeline 编排 + consumer LD-1）；Contract（零 upstream diff）；Integration（compose.test）；E2E（E2E-1..4 + F1 失败注入）。

---

### Phase 3：长期记忆检索

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| RET-001 | BM25 查询 | §2.2.7 | DEV-004, DEV-007 | completed |
| RET-002 | Vector 召回 + RRF | §2.2.6, §2.2.8, §2.2.9 | RET-001, DEV-007 | completed |
| RET-003 | Neo4j 权威回读 + 一跳扩展 + MGET | §2.2.10 | RET-002 | completed |
| RET-004 | ACT-R 评分 + Evidence 聚合 | §2.2.11, §2.2.12 | RET-003 | completed |
| RET-005 | Retrieval API、降级/超时、统计更新 | §2.2.5, §2.2.13–2.2.15 | RET-004, DEV-005 | completed |
| RET-006 | Retrieval 阶段 E2E + 失败注入 | §2.2.16, §3.28 | RET-005, EXT-007 | completed |

#### RET-001 BM25 查询

- **目标**：对已存在 Alias 执行 BM25；过滤器与字段权重按规格。
- **非目标**：创建 Mapping/Alias；Vector/RRF；硬依赖 EXT-007。
- **前置**：**DEV-004, DEV-007**（BM25 可不调用 Embedding；Vector 依赖 DEV-007，见 RET-002）。
- **测试**：Integration —— Migration 后**直接写入固定 ES Fixture 文档**，再断言 BM25；**不**将 EXT-007 列为硬前置。
- **E2E 协作**：与 EXT-007 的写入→可检索 放到 RET-006 / E2E-001。
- **Task Plan**：`02_开发管理/tasks/RET-001-bm25-retrieval.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=a780bb2d6ae6d0e47d22f508326aed8f0e4fb7ab` MATCH；内部 Service/Repository（非 HTTP）；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `3f7e333132a6c1bc013eeb5ac0b5b47954734aab`；implementation `fc435db722ed29c05980d6a1a60d9f57fda80968`；PR #44 MERGED `a4dda57366b9e0cb2a1fb34b6526a07daa30ed31` mergedAt `2026-08-13T02:29:09Z`；scoped 33 passed（25 unit + 8 integration）；Ruff PASS；Mypy remediation files PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2 non-blocking；§2.2.7 BM25 internal channel read-only；Integration ES Fixture not EXT-007 pipeline；feat 分支已删；RET-002 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。

#### RET-002 Vector 召回 + RRF

- **目标**：检索路径 Query 标准化 + 单条 Embedding；ES kNN Vector 召回；与 RET-001 BM25 并行编排；RRF 融合输出 `retrieval_mode`、候选 rank/score/normalized_retrieval_score。
- **非目标**：HTTP API/Warning；Neo4j 读回；ACT-R；ES 写入；TEI tokenize；硬依赖 EXT-007 pipeline。
- **前置**：**RET-001, DEV-007**（BM25 经 RET-001 服务；Embedding 经 `create_embedding_client`）。
- **测试**：Unit（RRF 精确算例、并行编排、filter builder）；Integration — Migration 后**直接写入固定 ES Fixture**（差异化 embedding）+ Fake Embedding；RET-001 回归全通过。
- **Task Plan**：`02_开发管理/tasks/RET-002-vector-retrieval-rrf.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=e5f5c9de9883d04759f19080c01f1f50d2c62513` MATCH；内部 Service/Repository；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；LD-1 SiliconFlow 无本地 `skipped_query_too_long` 预检；共享 `retrieval_filter_builder` 最小重构 BM25 repo；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `da1736925b767777bd8f538d5719d5821bebc017`；implementation `3bf3a1b760080d4f581ab53dad0961a28dfb63a4`；PR #45 MERGED `2bfc2b2ddbd5ef69a2a3f473722b32a9ead3d461` mergedAt `2026-08-13T03:13:39Z`；scoped 71 passed（31 RET-002 unit + 7 integration + 33 RET-001 regression）；Ruff PASS；Mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 non-blocking；§2.2.6/§2.2.8/§2.2.9 Vector+RRF internal path；共享 `retrieval_filter_builder`；Integration ES Fixture + Fake embed；feat 分支已删；RET-003 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。

#### RET-003 Neo4j 权威回读 + 一跳扩展 + MGET

- **目标**：RRF 候选 Neo4j 权威批量加载 Memory + subject/object Entity；再校验 user_id/memory_types/status；`graph_expand=true` 时一跳图扩展 + `graph_retrieval_score`；扩展候选 ES MGET 存在性校验；内部 `dirty_index_document` / `stale_index_document` / `graph_expansion_failed` Warning 种类。
- **非目标**：HTTP API/Warning HTTP 字段；ACT-R/Evidence；`retrieval_count` 统计；修改 RET-002 RRF 或 EXT-007 索引同步扩展语义。
- **前置**：**RET-002, EXT-006, EXT-007, DEV-004**（Integration 直接 Neo4j+ES Fixture；非 EXT-007 pipeline 硬前置）。
- **测试**：Unit（status 矩阵、tier 排序、decay、重叠、failure mapping）；Integration — Neo4j 图关系 Fixture + ES MGET Fixture。
- **Task Plan**：`02_开发管理/tasks/RET-003-neo4j-graph-expansion-mget.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=21a99a5b217f45cd4e4c67b8758bf1705d9d0a74` MATCH；新建 `retrieval_memory_read_repository` + `mget_retrieval_repository`（禁止混用 EXT-007 扩展 Cypher）；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `144844295bbd98b962e269e870e57685c2af9fe4`；implementation `64f71690d6c7ac08762b45d76a34158b49570e24`；PR #46 MERGED `3746f1bce38b4f6e4c0ab4d7899eff5622cc21c0` mergedAt `2026-08-13T05:03:28Z`；scoped 53 passed（30 RET-003 unit + 7 integration + 16 RET-002 regression）；Ruff PASS；Mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 non-blocking；§2.2.10 Neo4j authoritative recall + one-hop expansion + ES MGET read-only internal path；新建 `retrieval_memory_read_repository` + `mget_retrieval_repository`；Integration Neo4j+ES Fixture；feat 分支已删；RET-004 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。

#### RET-004 ACT-R 评分 + Evidence 聚合

- **目标**：消费 RET-003 `AuthoritativeRecallSuccess`；§2.2.11 ACT-R 五分量 + status 惩罚 + 6 位小数 `final_score`；确定性排序 + `top_k` 截断；§2.2.12 Top-K 后 Neo4j 批量 Evidence 读 + `evidence_count` / `source_message_ids` 确定性聚合；内部 `graph_load_failed`；透传 RET-003 warnings。
- **非目标**：HTTP API/Response DTO；`retrieval_count`/`last_retrieved_time` 更新；修改 RET-001/002/003/EXT-005 生产语义。
- **前置**：**RET-003, EXT-005, EXT-006**（Integration Neo4j Evidence Fixture；非 EXT-007 pipeline 硬前置）。
- **测试**：Unit（NC-1..NC-8 数值算例、排序 tie-break、failure mapping）；Integration — Neo4j Evidence SUPPORTS Fixture。
- **Task Plan**：`02_开发管理/tasks/RET-004-act-r-scoring-evidence-aggregation.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=c8d9d38d92414b9e041dd3d97dcbfd17b9e61582` MATCH；新建 `act_r_scoring` + `retrieval_scoring_service` + `retrieval_evidence_read_repository`（禁止混用 EXT-005）；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `e3e98eeec645ed759fd90579149fae3e3420214c`；implementation `e631d206b26175d341602ffdfd42a3d8f43edd3f`；PR #47 MERGED `f505c25572f5695a772ac8598be9c8602b36aa9e` mergedAt `2026-08-13T06:47:29Z`；scoped 52 passed（unit 47 + integration 5）；Ruff PASS；Mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2 non-blocking；§2.2.11 ACT-R scoring；Top-K before Evidence；Evidence does not affect final_score；新建 `act_r_scoring` + `retrieval_scoring_service` + `retrieval_evidence_read_repository` + `evidence_aggregation`（禁止混用 EXT-005）；Integration Neo4j Evidence Fixture；零 durable write；feat 分支已删；RET-005 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。

#### RET-005 Retrieval API、降级/超时、统计更新

- **目标**：`POST /api/v1/memory/retrieval`（§2.2.5）；Request 校验与 `require_memory_api_key`；HTTP 层 TEI tokenize gate + 编排 BM25/Vector/`fuse_rrf`（synthetic `skipped_query_too_long`）；消费 RET-003/004 Outcome；§2.2.12 Response DTO（`score`←`final_score`）；§2.2.13 Top-K Neo4j `retrieval_count`/`last_retrieved_time` 批量更新；§2.2.15 全量 Warning/致命码与 `retrieval_total_timeout_seconds` 超时矩阵；闭合 OI-008 canonical DR 编号映射。
- **非目标**：修改 RET-001..004 生产语义；RET-006 E2E；cache/reranking/pagination/streaming；ES/Mongo/Kafka 写入。
- **前置**：**RET-004, DEV-005**（RET-001..003 经 RET-004 传递）。
- **测试**：Unit（warning mapper、response mapper、编排、tokenize gate、超时分支）；Contract（路由/错误码/白名单）；Integration（TestClient + Neo4j stats Fixture）。
- **Task Plan**：`02_开发管理/tasks/RET-005-retrieval-api-degradation-statistics.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=c086b9953829d0ca19e930cde9b1c64dadde5fb9` MATCH；新建 `RetrievalApiService` + `RetrievalStatisticsRepository` + HTTP routes/schemas；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；`durable_write_scope=Neo4j stats only`；OI-008 `resolved_by_plan`；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `a6b0884f9cc6489f009d3d02a68a422dba88574b`；implementation `9baf16a7c6f7b0ad3cec8155b54c9fdeeb8c4250`；PR #48 MERGED `5b577d6e04c8b1e0a7336169a18855c66e4a2a3a` mergedAt `2026-08-13T07:42:25Z`；scoped 48 passed（unit 34 + contract 8 + integration HTTP 8）；Ruff PASS；Mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=2 non-blocking（P2 remediated pre-commit）；§2.2.5 POST /api/v1/memory/retrieval + §2.2.12 Response DTO + §2.2.13 Neo4j stats + §2.2.15 degradation/timeout；OI-008 resolved_by_task（canonical DR-1..DR-10）；零 RET-001..004 production semantic diff；feat 分支已删；RET-006 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13）。

#### RET-006 Retrieval 阶段 E2E + 失败注入

- **目标**：交付 Retrieval 阶段 E2E（§2.2.16 HTTP 边界 + §3.28 失败注入）；闭合 EXT-007 write→retrieve 延后验证；**不**实现 Session→Consolidation 全链路。
- **非目标**：修改 RET-001..005 / EXT-007 生产语义；E2E-001 全链；真实 SiliconFlow/TEI 计费 API；新 retry 框架。
- **前置**：**RET-005, EXT-007**（RET-001..004 经 RET-005 传递）。
- **Fixture 策略**：**Both** — A pre-seeded ES+Neo4j（E2E-1,3..6）；B EXT-007 `RetrievalIndexSyncService` write→retrieve（E2E-2 **REQUIRED**）。
- **基础设施**：`compose.test` ES + Neo4j（+Mongo 仅 E2E-2）；in-process ASGI；`--embedding=none`；Fake Embedding/Tokenize。
- **测试**：E2E-1 happy+stats；E2E-2 EXT-007 sync→retrieve；E2E-3/4a 通道降级；**E2E-4b 双通道 503 retrieval_unavailable**；E2E-5 超时/降级；E2E-6 用户隔离。
- **生产白名单**：**NONE**（默认零 `src/**` diff；缺陷暴露 → HALT）。
- **Task Plan**：`02_开发管理/tasks/RET-006-retrieval-e2e-failure-injection.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=538cf13ac3d33d1f337a9e5f5b450626ddd6529d` MATCH；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；`durable_write_scope=existing RET-005 stats + EXT-007 ES upsert only`；里程碑 `v0.4.0-memory-retrieval`；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `e1abc1ca77566da645a8087844d0da28cd8c87fe`；implementation `6e5517c11f0c7b6417264064d718937dd0aca62b`；record `4637279313e2fac61b986bbe45be8dfb847318b2`；PR #49 MERGED `295c5faa3b0160db349b926dc8eb0a001d67c7ce` mergedAt `2026-08-13T08:48:22Z`；scoped 9 passed（E2E-1,2,3,4a,4b,5a,5b,6 + auth）；Ruff PASS；Mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=2 non-blocking；§2.2.16 Retrieval stage E2E + §3.28 failure injection；EXT-007 write→retrieve（E2E-2）；零 `src/**` diff；feat 分支已删）；**closes `v0.4.0-memory-retrieval` milestone**；`next_action=CON-001 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13）。

---

### Phase 4：巩固与遗忘

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| CON-001 | Importance/衰减/保护公式纯函数 | §2.3.5–2.3.8 | EXT-004 | completed |
| CON-002 | Cursor 分页批量读取与 Evidence 计数 | §2.3.4 | CON-001 | completed |
| CON-003 | 乐观锁批量更新 | §2.3.9 | CON-002 | completed |
| CON-004 | APScheduler、互斥锁、失败恢复 | §2.3.4, §3.22 | CON-003 | completed |
| CON-005 | Consolidation Integration + E2E | §2.3.11–2.3.13 | CON-004 | approved |

- **非目标（阶段）**：独立 Consolidation HTTP API；ES importance 同步；多实例调度。

#### CON-001 Importance/衰减/保护公式纯函数

- **目标**：§2.3.5–§2.3.7 巩固信号与动态重要性 **纯函数**（`base_importance` / `confidence_score` / `evidence_score` / `recency_score` / `reinforcement_score` / `new_importance`）；`independent_archive_count=0` → `missing_evidence` skip；相同 `evaluation_time` + 相同输入确定性；**不**使用旧 `importance` 或检索统计字段；只读消费 `MemoryConsolidationSettings` 与 `IMPORTANCE_BY_TYPE`。
- **非目标**：Neo4j 读/写；Cursor 分页与 Evidence 计数（CON-002）；乐观锁批量更新（CON-003）；APScheduler/互斥锁/Worker（CON-004）；E2E（CON-005）；ES 同步；HTTP API；修改 `act_r_scoring` / `consolidation_worker` / Settings Contract。
- **前置**：**EXT-004**（登记）；EXT-001..009、RET-001..006 completed。
- **测试**：Unit（NC-1..NC-14 数值算例、missing_evidence、确定性）；Contract（白名单 + 输入契约无旧 importance）；Integration/E2E **DEFERRED**。
- **Task Plan**：`02_开发管理/tasks/CON-001-importance-decay-protection-formulas.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=2159ad6cc5e3f31365677671d9588c69b776e8a0` MATCH；新建 `consolidation_importance` models + services 纯函数（禁止与 RET-004 ACT-R recency 混用）；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；`durable_read_scope=NONE`；`durable_write_scope=NONE`；§2.3.8 文档对齐、不实现软遗忘副作用；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `6f4a35ad28ad90946f74e39bfa567acc71120b12`；implementation `41932b93431e43fa1d134cfed76dfedb9ec7f363`；record `bef3ae23e8b12592cbdfcfb563654fb91c97cea2`；PR #50 MERGED `e9469d8ee61d363d7367a9b17ca2680794ce39f0` mergedAt `2026-08-13T10:24:42Z`；scoped 49 passed；Ruff PASS；Mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=2 non-blocking；§2.3.5–2.3.7 consolidation importance pure functions；零 durable I/O；feat 分支已删）；`next_action=CON-002 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13）。

#### CON-002 Cursor 分页批量读取与 Evidence 计数

- **目标**：§2.3.4 巩固候选 **Cursor 分页** Neo4j 批量只读；`count(DISTINCT e.archive_id)` 作为 `independent_archive_count`；per-user `user_id` + Evidence 双端隔离；组装 `ConsolidationImportanceInput` 并调用 `compute_consolidation_importance`；输出 scored/skip/`next_cursor`/批次元数据；**零** durable 写入。
- **非目标**：`evaluation_time` 生成、调度/互斥锁（CON-004）；Neo4j 乐观锁批量写入（CON-003）；`consolidation_worker` 接线；E2E（CON-005）；ES 同步；HTTP API；修改 CON-001 公式 / Settings Contract。
- **前置**：**CON-001** completed（PR #50 MERGED）；EXT-001..009、RET-001..006 completed。
- **测试**：Unit（U1..U12 分页/隔离/计数/去重/skip/畸形/读失败/handoff/replay/零写）；Contract（C1..C5 白名单+边界）；Integration/E2E **DEFERRED**（CON-005）。
- **Task Plan**：`02_开发管理/tasks/CON-002-cursor-batch-evidence-count.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=85875ff4d86ad39ccff9d4632088713ef8b052af` MATCH；新建 `consolidation_batch` models + `consolidation_batch_service` + `consolidation_memory_read_repository`；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；`durable_read_scope=Neo4j read-only`；`durable_write_scope=NONE`；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `a3d0c26f1864e399d2562f1648c99584fe77d8e4`；implementation `a13ab31bb98598740198001d8bfee3f21d6b565a`；PR #51 MERGED `3b26549c41b91a1bbdd72237865a5d3d4fb5324d` mergedAt `2026-08-13T11:15:50Z`；scoped 39 passed；Ruff PASS；Mypy PASS（3 new src files）；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2 non-blocking（P2-1 C1 untracked blind spot；P2-2 null archive_id test gap）；§2.3.4 read-only cursor batch + `count(DISTINCT archive_id)` + per-user isolation + zero-Evidence→`missing_evidence`；零 durable write；feat 分支已删）；`next_action=CON-003 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13）。

#### CON-003 乐观锁批量更新

- **目标**：§2.3.9 Neo4j **乐观锁批量写入** — 将 CON-002 `scored` 的 `new_importance` 持久化为 `importance`，`last_consolidated_time = evaluation_time`；`expected_memory_version` 谓词；单批 transaction；批内版本冲突部分成功（`version_conflict_count`）；空写跳过；用户隔离。
- **非目标**：`memory_version` 递增 / `updated_time` 写入；CON-002 读路径与 skipped 写入；APScheduler/互斥锁/cursor 循环/指标落盘（CON-004）；ES 同步；`consolidation_worker` 接线；E2E（CON-005）；修改 CON-001/CON-002 已完成语义 / Settings Contract。
- **前置**：**CON-002** completed（PR #51 MERGED）；**CON-001** completed（PR #50 MERGED）；EXT-001..009、RET-001..006 completed。
- **测试**：Unit（U1..U17 乐观锁/隔离/精确字段/replay/冲突/空写/失败）；Contract（C1..C6 白名单+无 memory_version/updated_time SET+无 ES/Mongo）；Integration/E2E **DEFERRED**（CON-005）。
- **Task Plan**：`02_开发管理/tasks/CON-003-optimistic-lock-batch-update.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=cabcc6f98e5cd676b962b49e3b0c943587a11689` MATCH；新建 `consolidation_write` models + `consolidation_write_service` + `consolidation_memory_write_repository`；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；`durable_read_scope=NONE`；`durable_write_scope=Neo4j Memory（importance, last_consolidated_time）`；§2.3.9 权威 Cypher；巩固不递增 `memory_version`；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `0146b5dd53d37dfbdec0ea9bc9e87d6fe373221a`；implementation `8563466feeb8aea38fb6997a3e99d4d54eb3878c`；PR #52 MERGED `7337c861150c9312a7a37b2b884839c186cb43d1` mergedAt `2026-08-13T13:03:22Z`；scoped 35 passed；Ruff PASS；Mypy PASS（3 new src files）；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=2 non-blocking；§2.3.9 optimistic-lock write contract preserved — `expected_memory_version` predicate-only / no `memory_version` increment；partial-success batch semantics（`version_conflict_count`）；SET importance + last_consolidated_time only；不写 updated_time；CON-002 scored handoff only；Integration DEFERRED CON-005；feat 分支已删）；`next_action=CON-004 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13。

#### CON-004 APScheduler、互斥锁、失败恢复

- **目标**：§2.3.11 巩固 **运行编排** — APScheduler `AsyncIOScheduler` + `CronTrigger`（§3.22）；进程内本地互斥锁（§2.3.4）；每轮统一 `evaluation_time` + `run_id`；Neo4j `DISTINCT user_id` 枚举 + per-user `memory_id` cursor 循环；调用 CON-002 读批次 + CON-003 写 `scored`；§2.3.13 失败恢复与运行指标/日志；`consolidation_runs_total{status}`；`consolidation_worker` 生产接线与 graceful shutdown（§3.25）。
- **非目标**：修改 CON-001/002/003 已完成服务语义；CON-005 Integration/E2E；ES/Mongo/Kafka；持久化 cursor/run 表；Redis 分布式锁；多实例调度；独立 Consolidation HTTP API；修改 Settings Contract。
- **前置**：**CON-003** completed（PR #52 MERGED）；**CON-002** completed（PR #51 MERGED）；**CON-001** completed（PR #50 MERGED）；EXT-001..009、RET-001..006 completed。
- **测试**：Unit（U1..U18 编排/互斥/scheduler/枚举/worker + fake CON-002/003 ports）；Contract（C1..C7 白名单+零 CON-001/002/003 diff）；Integration/E2E **DEFERRED**（CON-005）。
- **Task Plan**：`02_开发管理/tasks/CON-004-apscheduler-mutex-failure-recovery.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=8998f627b6cf0c8f5beb103006903d8c3668542a` MATCH；新建 `consolidation_run` models + `consolidation_run_service` + `consolidation_mutex` + `consolidation_scheduler` + `consolidation_user_enumeration_repository` + `consolidation_run_telemetry`；**修改** `consolidation_worker.py`；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；`durable_read_scope=Neo4j DISTINCT user_id enumeration`；`durable_write_scope=NONE（编排层）/ delegated CON-003 Neo4j write`；不得触碰 DEV-006/PR#13。
- **状态备注**：`completed`（plan `e124b23`；implementation `abb2ceaf6579f9dfff9e46f4782d3d9d181d31c1`；PR #53 MERGED `ae70a94fd08382ffd43fbdc0e64ec613423fc403` mergedAt `2026-08-13T13:59:12Z`；scoped 37 passed；Ruff PASS；Mypy PASS（7 new src files）；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=1 non-blocking（P2-1 C1 untracked blind spot；P2-2 Prometheus failure-path assertions；P3-1 telemetry naming）；§2.3.11 run orchestration — one evaluation_time per run；process-local mutex/finally release；per-user cursor orchestration；non-fatal version conflicts；no persistent cursor/run-state；zero CON-001/002/003 semantics diff；Integration DEFERRED CON-005；feat 分支已删）；`next_action=CON-005 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13。

#### CON-005 Consolidation Integration + E2E

- **目标**：§2.3.11–§2.3.13 巩固 **垂直切片 Integration + E2E** — 真实 Neo4j 上证明 CON-001..004 生产栈协同；`ConsolidationRunService` in-process 生产接线（非 fake CON-002/003 ports）；固定 `evaluation_time`；INT-1..6 + E2E-1..6（happy/readback、多页隔离、missing_evidence、version_conflict、失败恢复、部分进度下轮恢复）；闭合 **`v0.5.0-consolidation` 里程碑**。
- **非目标**：修改 CON-001..004 生产语义（`production_file_whitelist=NONE` 默认）；HTTP/API；ES/Mongo/Kafka 写；§2.3.8 软遗忘副作用；Session→Archive→Extraction 全链（E2E-001）；持久化 cursor/run 表；分布式锁/多实例调度长运行证明；APScheduler wall-clock E2E（CON-004 Unit 足够）。
- **前置**：**CON-004** completed（PR #53 MERGED）；**CON-003** completed（PR #52）；**CON-002** completed（PR #51）；**CON-001** completed（PR #50）；EXT-001..009、RET-001..006 completed。
- **测试**：Integration（INT-1..6 — CON-002 read、CON-003 write、enumeration、run smoke）；E2E（E2E-1..6 — 垂直切片 + 失败注入 + mutex 最小子场景）；Contract（零 src diff + 白名单）；Unit **无新增**（CON-001..004 回归）。
- **Task Plan**：`02_开发管理/tasks/CON-005-consolidation-integration-e2e.md`。
- **规划备注**：`workflow_mode=NORMAL`（explicit）；`planning_baseline_main=010d74112fb760907e710f2ba27123e021dd3d61` MATCH；**零** `src/**` 生产变更默认；Neo4j-only `compose.test`；`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`；`durable_read_scope=Neo4j read-only（测试验证）`；`durable_write_scope=Neo4j Memory importance+last_consolidated_time（既有 CON-003 路径）`；E2E-6/INJ-7 Run B@T2>T1（T1 行再 eligible，§6.3）；`pytest_plugins` 显式加载 fixture；取代 CON-004 §15 in-process 范围 only；APScheduler/container wall-clock 仍 DEFERRED；E2E 暴露生产缺陷 → HALT；不得触碰 DEV-006/PR#13。
- **状态备注**：`approved`（Human PLAN_APPROVED @ 2026-08-13T14:37:00Z；Round 2 Amendment 001 PLAN_APPROVED；Planner Amendment 001 Round 2 @ 2026-08-13 14:45 UTC）；`approval_posture=PLAN_APPROVED`；`next_action=Developer on feat/CON-005-consolidation-integration-e2e`；Developer authorized post-PLAN_LANDING；closes `v0.5.0-consolidation` on POST_MERGE_CLEANUP only；不得触碰 DEV-006/PR#13。

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
| `v0.3.0-memory-extraction` | EXT-009 完成（已满足） |
| `v0.4.0-memory-retrieval` | RET-006 完成（已满足） |
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

### CHANGE-052

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-11 |
| 原因 | EXT-001 POST_MERGE_CLEANUP：PR #34 MERGED（`ae346dd27cda39f93fa38b7316ec17559df217ef` mergedAt `2026-08-11T13:57:07Z`）；docs(status): complete on main；删 exact feat |
| 受影响任务 | `EXT-001`（`completed`）；`STM-012` prerequisites **SATISFIED** — `planned` / **READY_FOR_PLANNING only**（**不** 自动启动）；`EXT-002` remains `planned`；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-012 READY_FOR_PLANNING only; do NOT auto-start until explicit human authorization` |

### CHANGE-051

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-11 |
| 原因 | STM-011 POST_MERGE_CLEANUP：PR #33 MERGED（`19fdb55359acd97380a8b5f0d8ae788134f75307` mergedAt `2026-08-11T12:17:49Z`）；docs(status): complete on main；删 exact feat |
| 受影响任务 | `STM-011`（`completed`）；`STM-012` NOT ready（needs EXT-001；STM-011 prerequisite **SATISFIED**）；`EXT-001` `planned`（not started）；**不** 自动启动 STM-012/EXT-001；**不** 触碰 DEV-006/PR #13 |
| 是否改变技术规格 | **否** |
| 审批 | Release Operator POST_MERGE_CLEANUP；`next_action=STM-012 NOT ready; do NOT auto-start STM-012 or EXT-001` |

### CHANGE-050

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-11 |
| 原因 | 用户显式 NEW_TASK：**DEV-OPS-008** Compose test-stack runtime compatibility（C1 aiokafka 0.13 `bootstrap_connected` + C2 ES 9.4 mapping readback `element_type`）；STM-013 scope remediation 已将生产修复移出 PR #30；blocks STM-013 |
| 受影响任务 | 新增 `DEV-OPS-008`（`planned`；plan `02_开发管理/tasks/DEV-OPS-008-compose-test-stack-runtime-compatibility.md`）；`STM-013`（`blocked`；PR #30 OPEN MUST NOT MERGE）；**不** commit `tests/e2e/**`；**不** cherry-pick `975e6029` wholesale；**不** 触碰 DEV-006/PR #13；分支从 main @ `390af52` 创建（NOT feat/STM-013） |
| 是否改变技术规格 | **否**（读回兼容与 runtime 探针对齐 pinned 依赖；CREATE mapping 不变） |
| 审批 | Planner；`next_action=计划审查` |

### CHANGE-053 (historical; superseded by Amendment 004 / CHANGE-055)

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | 用户显式 EXT-002 Planner Round 3 remediation/clarification；raw Archive access、strict validation、terminal mapping、redaction blocker、first-person binding 和 blocked output contract 需要精确化 |
| 受影响任务 | `EXT-002`（`planned`；plan review round 3；Amendment 003；baseline `13e1dae36a0b0d94415d9581b2a5fe53c990545f`）；仅更新规划白名单文件；不实施、不启动 Developer/EXT-003 |
| 规划决议 | 新增唯一 read-only `find_context_archive_document_by_id` raw mapping boundary；严格验证七个 Archive 顶层字段与四字段消息，验证完成前无任何 preprocessing/redaction/handoff；仅使用现有 error_code，未授权 failed_stage 保持 gated；`REDACTION_SPEC_STATUS=BLOCKED_PENDING_SPEC_DECISION`；`output_contract_status=BLOCKED`；OI-EXT-002-001 decision packet 与 OI-002..005 同步 |
| 是否改变技术规格 | **否**；dependency changes **NONE**；不改 Kafka/task schema、STM-011/012、EXT-003+、Neo4j、ES、DEV-006、PR #13 |
| 审批 | Planner；`next_action=计划审查`；等待独立 Plan Reviewer，不得自动进入 Developer |

### CHANGE-054

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | 用户显式 EXT-002 Planner governance amendment；authoritative specification Appendix A / Amendment EXT-002-004 已固定 terminal mappings、strict raw boundary、deterministic content-only redaction、handoff order 与 OI dispositions |
| 受影响任务 | `EXT-002`（`planned`；plan review round 4；Amendment 004；baseline `13e1dae36a0b0d94415d9581b2a5fe53c990545f`）；仅规划白名单与 authoritative specification append-only amendment；不实施、不启动 Developer/EXT-003 |
| 规划决议 | `archive_not_found/archive_read`、`invalid_archive/archive_validate`、`redaction_failed/redaction`；unexpected nondeterministic infrastructure/internal failure = `abort_without_terminal`；terminal persistence before offset; local deterministic redaction only on `messages[].content`, exact category/preference/span/Luhn/marker rules; first-person deferred/out-of-scope; raw validation → preprocessing → redaction → conditional handoff |
| 是否改变技术规格 | **是**，仅追加 authoritative amendment；dependency changes **NONE**；不改 EXT-001 Kafka/task status、STM-011/012、EXT-003+、Neo4j、Elasticsearch、DEV-006、PR #13 |
| Open Issues | OI-EXT-002-001/002/004/005 resolved；OI-EXT-002-003 deferred/out-of-scope；unrelated issues preserved |
| 审批 | Planner；`next_action=计划审查`；等待独立 Plan Reviewer，不得自动进入 Developer |

### CHANGE-055

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-002 Planner Round 4 remediation：将 Amendment 004 作为唯一有效当前状态，清除当前规划段的 Amendment 003 blocker wording，并补齐 RAW-01..RAW-12 与 RED-01..RED-27 conformance matrix |
| 受影响任务 | `EXT-002`（`planned`；plan review round 4；Amendment 004；baseline `13e1dae36a0b0d94415d9581b2a5fe53c990545f`）；仅更新 Task Plan、open_issues、progress、master_plan；不修改已持久化规格、不实施、不启动 Developer/EXT-003 |
| 规划决议 | 当前有效 terminal mapping 为 `archive_not_found/archive_read`、`invalid_archive/archive_validate`、`redaction_failed/redaction`；`abort_without_terminal` 用于非确定性基础设施/内部失败；raw validation PASS → preprocessing PASS → redaction PASS 后才最终化 `ExtractionReadyArchive`；`OI-EXT-002-003=DEFERRED/OUT_OF_SCOPE`，其余 EXT-002 OI 已 resolved；implementation whitelist 精确包含 raw read-only repository method、models/services/conditional worker wiring 与 RAW/RED unit/contract/integration tests；`dependency_changes_expected=NONE` |
| 是否改变技术规格 | 否；Amendment 004 已由规格负责人此前追加持久化，本轮只同步规划治理文件 |
| 审批 | Planner；`next_action=计划审查`；等待独立 Plan Reviewer，不得自动进入 Developer |

### CHANGE-056

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-002 POST_MERGE_CLEANUP：PR #36 MERGED；同步完成治理状态、验收证据、提交链与下游依赖 |
| 受影响任务 | `EXT-002`（`completed`）；`EXT-003` prerequisites **SATISFIED**（`EXT-002` + `STM-007` completed）；`EXT-003` remains `planned` / **NOT AUTO-STARTED**；不改变 Amendment 004、EXT-001 terminal/offset 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 事实记录 | merge `59e9f7f0cf6effd34d1f13ad022f9b9eb00b8f2d`；implementation `7fdf84827b2c253a6e6734b8051467f3ec1151f1`；amendment `985613be08814b1e9eea521888b61dd5cb8d94ff`；record `036d770268c3a3bbb95fe4687fd0007805e284a4`；RAW-01..12 PASS；RED-01..27 PASS；mandatory skips=0；scoped rerun=165 passed；Ruff/mypy PASS；CODE_REVIEW_APPROVED P0/P1/P2/P3=0 |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=EXT-003 planned / NOT AUTO-STARTED` |

### CHANGE-057

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | 用户显式 `TASK_ID=EXT-003`、`WORKFLOW_MODE=NORMAL`、baseline `f112d12d28d34de18c637a661a857fcb9f0a401f`；Planner 仅创建 LLM Extraction + Fingerprint fail-closed Task Plan |
| 受影响任务 | `EXT-003`（`planned`；plan `02_开发管理/tasks/EXT-003-llm-extraction-fingerprint.md`）；仅更新 planning whitelist；不实施业务代码/测试、不启动 Developer/Reviewer/Release Operator |
| 规划决议 | Exact `ExtractionReadyArchive` provenance/order/privacy boundary；8000/no-chunking/50/100/character limits；§2.1.6 schema and §2.1.7 validation；application-owned `candidate_source_time`；fixed-order UTF-8 compact fingerprint with sorted source IDs and no invented normalization; existing STM-007 provider conventions; §2.1.15-only LLM error mappings; terminal persistence/replay constraints; exact production/test whitelist; no EXT-004+ |
| Open Issues | Added blocking `OI-EXT-003-001` unknown-field durable policy; `OI-EXT-003-002` canonical fingerprint/equivalence/order; `OI-EXT-003-003` correction prompt text; `OI-EXT-003-004` terminal-only pipeline handoff |
| 是否改变技术规格 | 否；authoritative specification untouched; unresolved contract ambiguity is fail-closed and requires owner decision/amendment before implementation |
| 审批 | Planner；`next_action=计划审查`；`approval_posture=FAIL_CLOSED_BLOCKED`；不得自动进入 Developer；不得触碰 DEV-006/PR #13 |

### CHANGE-058

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | Human `AUTHORIZED_EXT_003_MVP_AMENDMENT`（items 1–13）；Planner 记录 Appendix B、修订 EXT-003 Task Plan Amendment 002、同步 open_issues/progress/master_plan |
| 受影响任务 | `EXT-003`（`planned`；Amendment 002；baseline `f112d12d28d34de18c637a661a857fcb9f0a401f`）；仅更新规划白名单与 authoritative specification append-only amendment；不实施业务代码/测试、不启动 Developer/Reviewer/Release Operator |
| 规划决议 | Appendix B §B.1–B.13：unknown-field strip；legal-empty terminal mapping（both-empty complete+Offset，non-empty processing no Offset）；source-ref/blank-output/correction-prompt/failure mappings；fingerprint JSON array `ensure_ascii=false`；duplicate merge/order；SHA-256 collision deferred；EXT-003 boundary without `PipelineTerminalDecision` change；MF-001/MF-002 |
| Open Issues | `OI-EXT-003-001/002/003/004` resolved；`OI-EXT-003-005` deferred_for_mvp |
| 是否改变技术规格 | **是**，仅追加 authoritative Appendix B amendment；dependency changes **NONE**；不改 EXT-001 Kafka/task status、STM-011/012、EXT-004+ implementation scope、Neo4j、Elasticsearch、DEV-006、PR #13 |
| 审批 | Planner；`next_action=计划审查`；`approval_posture=AWAIT_PLAN_REVIEW`；`amendment_recorded=true`；`formal_EXT-003_plan_review=pending`；不得自动进入 Developer；不得触碰 DEV-006/PR #13 |

### CHANGE-059

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-003 Amendment 002 独立 Plan Review Round 2 |
| 受影响任务 | `EXT-003`（`planned`；Amendment 002；baseline `f112d12d28d34de18c637a661a857fcb9f0a401f`）；仅同步 progress/master_plan/plan approval gates；不实施、不启动 Developer |
| 审查结论 | **PLAN_APPROVED**；BLOCKER=0；MUST_FIX=0；SHOULD_FIX=1（Step 5 orchestration file path underspecified；non-blocking） |
| 审批 | Plan Reviewer Round 2；`next_action=人工 PLAN_APPROVED 后进入 PLAN_LANDING / Developer`；`formal_EXT-003_plan_review=PLAN_APPROVED`；不得自动进入 Developer；不得触碰 DEV-006/PR #13 |

### CHANGE-060

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | Human PLAN_APPROVED EXT-003 Amendment 002；SAFE_AUTO_REMEDIATION SF-1 MVP_LOCAL_DECISION 记录 Step 5 orchestration owner |
| 受影响任务 | `EXT-003`（`approved`；Amendment 002；baseline `f112d12d28d34de18c637a661a857fcb9f0a401f`）；仅更新规划白名单与 approval gates；PLAN_LANDING pending Release Operator |
| 规划决议 | SF-1：single orchestration owner `extraction_llm_service.py`（LLM/validate/fingerprint + Step 5 pipeline handoff）；`extraction_archive_preprocessing_service.py` compose-only；no new files/whitelist expansion/competing orchestration layer；Round 2 SHOULD_FIX=1 resolved without new Plan Review |
| 审批 | Human PLAN_APPROVED；`human_plan_approved=true`；`developer_authorized=true` post-PLAN_LANDING；`next_action=PLAN_LANDING then Developer on feat/EXT-003-llm-extraction-fingerprint` |

### CHANGE-061

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-003 POST_MERGE_CLEANUP：PR #37 MERGED；同步完成治理状态、验收证据、提交链与下游依赖 |
| 受影响任务 | `EXT-003`（`completed`）；`EXT-004` prerequisites **PARTIAL**（`EXT-003` + `DEV-004` completed）；`EXT-004` remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、EXT-001 terminal/offset 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 事实记录 | merge `0eb45e20c64777a03dc770be70cba2316b47fdf6`；implementation `7c6309ee68b01a6604b79253cea65be6fa26a0c6`；record `b14d53d840e7ba69139ce050a5225eae92def220`；completion `5d9349f7ed6984aee5000422bc55ab5e7031285b`；scoped 63 passed；Ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=1 non-blocking；OI-EXT-003-005 deferred_for_mvp |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=EXT-004 planned / NOT AUTO-STARTED` |

### CHANGE-062

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | 用户显式 `TASK_ID=EXT-004`、`WORKFLOW_MODE=NORMAL`、baseline `8330d42a9f2fe9365e180bdd68c6c9dc7add6e48`；Planner 仅创建 Entity Alignment + Neo4j 模型基础 fail-closed Task Plan |
| 受影响任务 | `EXT-004`（`planned`；plan `02_开发管理/tasks/EXT-004-entity-alignment-neo4j-model-basis.md`）；仅更新规划白名单（Task Plan / open_issues / progress / master_plan）；不实施业务代码/测试、不改配置/依赖/Migration/规格正文、不启动 Developer/Reviewer/Release Operator、不执行 Git 写 |
| 规划决议 | 权威输入 = 已持久化 `extraction_result`（`processing` + 非空则**不得**再调用 LLM、不重读 Archive、不重算 fingerprint/source time）；范围严格为 §2.1.9 Entity 模型基础 + §2.1.10 确定性对齐（S0–S6），MVP 纯确定性、无 LLM、无模糊/全文/向量匹配；`entity_key = SHA256(user_id + ":" + entity_type + ":" + normalized_name)`（UTF-8 + 小写 hex）；用户实体确定性 `entity_id = "user:" + user_id` 与 §2.1.10.1 固定字段；对齐阶段**只读** Neo4j、**禁止**任何 Entity/Memory/Evidence/关系写入（§2.1.13 事务前准备第 2 步）；对齐输出为**瞬态非持久化**返回值（§2.1.3「任务表不保存 Memory、Entity 结果 ID 数组」+ Appendix B §B.1 授权字段不变）；别名合并仅为计划态（既有 alias 零删除、50 上限、`canonical_name` 永不替换、`omitted_alias_count` 仅输出、不发指标）；`entity_alignment_failed` 为 EXT-004 唯一授权终态码，`graph_query_failed` 保留给 §2.1.11 已有 Memory 召回（EXT-005）；不可预期内部/基础设施故障沿用 `abort_without_terminal` 且不提交 Offset；EXT-003→EXT-004 continuation 编排仍 `DEFERRED_FOR_MVP`（Appendix B §B.10.4），`PipelineTerminalDecision` / consumer / `extraction_llm_service` / `extraction_worker` 逐字不变；精确生产/测试白名单四新建生产文件 + 五测试文件 |
| Open Issues | 新增 blocking `OI-EXT-004-001`（§2.1.10 第 4 步次级精确匹配的操作数/比较基准/alias 语义/多命中确定性）、blocking `OI-EXT-004-002`（`entity_alignment_failed` 的 `failed_stage` 字面量 + `graph_query_failed` 归属确认）；新增非阻塞 `OI-EXT-004-003`（`normalized_name` / alias 归一化 micro-semantics，已固定字面读法）、`OI-EXT-004-004`（`canonical_name` 替换判据与用户实体别名非参与，已固定 fail-closed 读法） |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`（`neo4j>=5.28,<6`、`Neo4jSettings` §3.24 固定值、`AppState.neo4j` AsyncDriver 均已存在）；**无** Schema/Constraint/Migration 产物需求——§2.1.9 的 4 约束 + 2 索引已由 DEV-004 `scripts/migrations/002_initial_neo4j.py` 逐字创建并由 `tests/integration/test_migrate_infra.py` 断言；禁止新增或修改 Migration、禁止运行时 DDL |
| 是否改变技术规格 | 否；权威规格正文未改动；未决歧义 fail-closed，实施前需 owner 决议（如需修订则由授权轮次单独追加 Appendix） |
| 审批 | Planner；`next_action=计划审查`；`approval_posture=FAIL_CLOSED_BLOCKED`；`developer_authorized=false`；不得自动进入 Developer；不得触碰 DEV-006 / PR #13 |

### CHANGE-063

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | 用户显式 `TASK_ID=EXT-005`、`WORKFLOW_MODE=NORMAL`、baseline `5deb8949ee5ac367a08f173ef67c0c0689c26f5d`；Planner 仅创建 Reconciliation + 聚合门禁 Task Plan |
| 受影响任务 | `EXT-005`（`planned`；plan `02_开发管理/tasks/EXT-005-reconciliation-aggregation-gate.md`）；仅更新规划白名单（Task Plan / progress / master_plan）；不实施业务代码/测试、不改配置/依赖/Migration/规格正文、不启动 Developer/Reviewer/Release Operator、不执行 Git 写 |
| 规划决议 | 权威输入 = 已持久化 `extraction_result` + 瞬态 `EntityAlignmentSuccess`；范围 = §2.1.11 只读 Memory 召回 + LLM Reconciliation + `aligned_memory_key` + Archive 聚合 + `reconciliation_plan_conflict`；§2.1.12 置信度/重要性计划输出；§2.1.13 事务前第 1/6/7 步（evidence_id SKIP、increment_memory_version、预生成 memory_id）；零 Neo4j/Mongo 写入；瞬态 Reconciliation Plan 供 EXT-006；失败码 `graph_query_failed`/`reconciliation_plan_conflict`/`llm_*` + `failed_stage=reconciliation`；`entity_alignment_failed` 禁用；零召回确定性 CREATE 不调 LLM（LD-1）；reconciliation LLM 复用 `llm.extraction`（LD-3）；EXT-004→EXT-005 continuation `DEFERRED_FOR_MVP`；九新建生产文件 + 八新建测试文件 |
| Open Issues | 非阻塞 `OI-006`（运维清理属 EXT-008） |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否 |
| 审批 | Planner；`next_action=计划审查 Round 2`；`approval_posture=AWAIT_PLAN_REVIEW_ROUND_2`；`developer_authorized=false`；不得触碰 DEV-006 / PR #13 |

### CHANGE-064

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | Plan Review Round 1 `MUST_FIX=1`（MF-001 SUPERSEDE/CONFLICT 新侧输出契约不完整）+ `SHOULD_FIX=4`（SF-001–SF-004）；Planner Amendment 001 |
| 受影响任务 | `EXT-005`（`planned` Round 2）；仅更新 Task Plan §5.7–§5.11/§12.4/测试/验收 + progress/master_plan 规划态；不实施业务代码/测试、不改配置/依赖/Migration/规格正文、不执行 Git 写 |
| 规划决议 | `new_memory_create_plans[]` 为全部新 Memory 自包含 `PlannedMemoryCreate` 行（`create_kind` + 链接字段）；`PlannedExistingMemoryUpdate.planned_new_memory_id` 双向链接；归一化仅 `aligned_memory_key.py`；LLM SKIP 排除聚合；`session_id` 由 EXT-006 从任务文档读取；MERGE 混合 null/非 null merged_content 规则闭合 |
| Open Issues | 非阻塞 `OI-006` 不变 |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否 |
| 审批 | Planner；`next_action=计划审查 Round 2`；`approval_posture=AWAIT_PLAN_REVIEW_ROUND_2`；`developer_authorized=false`；不得触碰 DEV-006 / PR #13 |

### CHANGE-065

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-005 POST_MERGE_CLEANUP：PR #39 MERGED；implementation + record on main；governance completion |
| 受影响任务 | `EXT-005`（`completed`）；`EXT-006` prerequisites **SATISFIED** — remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、pipeline continuation 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 规划决议 | read-only Memory recall + LLM Reconciliation + aggregation + transient reconciliation plan delivered；zero Mongo/Neo4j writes；EXT-004→EXT-005 continuation remains `DEFERRED_FOR_MVP`；MF-001/SF-001–SF-004 verified |
| Open Issues | 非阻塞 `OI-006` 不变 |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=EXT-006 planned / NOT AUTO-STARTED` |

### CHANGE-066

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-006 POST_MERGE_CLEANUP：PR #40 MERGED；implementation + record on main；governance completion |
| 受影响任务 | `EXT-006`（`completed`）；`EXT-007` prerequisites **PARTIAL**（EXT-006 **completed**；DEV-007 **completed**；DEV-004 **completed**）— remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、pipeline continuation 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 规划决议 | atomic Neo4j graph write + `referenced_entity_write_set` + `core_search_text` + TEI token gate + `index_sync_memory_set` handoff delivered；zero task completed/offset；EXT-003→EXT-006 continuation remains `DEFERRED_FOR_MVP`；MF-001/SF-001–SF-004 verified |
| Open Issues | 非阻塞 `OI-006` 不变 |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=EXT-007 planned / NOT AUTO-STARTED` |

### CHANGE-067

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-007 Planner 创建 Task Plan；prerequisites 全部 SATISFIED；同步 progress/master_plan |
| 受影响任务 | `EXT-007`（`planned`）；`next_action=计划审查`；Developer **NOT** authorized；不改变 Appendix B、pipeline continuation 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 规划决议 | §2.2.3 完整 index sync（扩展 LD-8 handoff、Neo4j 加载、search_text+alias、Embedding、ES bulk upsert、completed/failed 门禁）；zero offset；zero upstream EXT-001–006 diff；LD-1–LD-9 recorded |
| Open Issues | 非阻塞 `OI-006` 不变 |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅治理规划文件 |
| 审批 | Planner only；`next_action=计划审查` |

### CHANGE-068

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-007 POST_MERGE_CLEANUP：PR #41 MERGED；implementation + record on main；governance completion |
| 受影响任务 | `EXT-007`（`completed`）；`EXT-008` prerequisites **SATISFIED** — remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、pipeline continuation 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 规划决议 | §2.2.3 full index sync（expand LD-8 handoff、Neo4j load、search_text+alias、Embedding、ES bulk upsert、completed/failed gate）delivered；completed-before-offset gate preserved；zero offset；zero upstream EXT-001–006 diff；EXT-006→EXT-007 continuation remains `DEFERRED_FOR_MVP`；LD-1–LD-9 verified |
| Open Issues | 非阻塞 `OI-006` 不变 |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=EXT-008 planned / NOT AUTO-STARTED` |

### CHANGE-069

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | 用户显式 `TASK_ID=EXT-008`、`WORKFLOW_MODE=NORMAL`、baseline `d55bf53e715378463243fcf80e49277e603c1bb5`；Planner 创建 Extraction Admin API Task Plan 并闭合 OI-006 |
| 受影响任务 | `EXT-008`（`planned`；plan `02_开发管理/tasks/EXT-008-extraction-admin-api.md`）；仅更新规划白名单（Task Plan / progress / master_plan / open_issues）；不实施业务代码/测试、不改配置/依赖/Migration/规格正文、不启动 Developer/Reviewer/Release Operator、不执行 Git 写 |
| 规划决议 | §2.1.14 GET + POST retry（Admin Key；§2.1.15 可重试表；保留 extraction_result；STM-011 republish）；OI-006 → LD-1 POST rebuild（仅 reconciliation_plan_conflict；清 extraction_result）；Mongo-only durable；authorized HTTP codes extraction_task_not_found/retry_not_allowed；zero offset/Neo4j/ES；zero consumer/worker/pipeline diff；六生产 + 三测试文件白名单 |
| Open Issues | **OI-006 resolved_by_plan**（rebuild 窄契约）；无 blocking Open Issue |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否（MVP_LOCAL_DECISION 仅 Plan 层；未改规格正文） |
| 审批 | Planner only；`next_action=计划审查`；`developer_authorized=false`；不得触碰 DEV-006 / PR #13 |

### CHANGE-070

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-008 POST_MERGE_CLEANUP：PR #42 MERGED；implementation + record on main；governance completion |
| 受影响任务 | `EXT-008`（`completed`）；`EXT-009` prerequisites **SATISFIED** — remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、pipeline continuation 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 规划决议 | §2.1.14 GET + POST retry + OI-006 POST rebuild（LD-1）delivered；Mongo-only durable；STM-011 republish reuse；authorized HTTP codes extraction_task_not_found/retry_not_allowed；zero offset/Neo4j/ES；zero consumer/worker/pipeline diff；LD-1–LD-7 verified |
| Open Issues | **OI-006 resolved_by_task** |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=EXT-009 planned / NOT AUTO-STARTED` |

### CHANGE-071

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 原因 | EXT-009 Planner：production extraction pipeline wiring + E2E plan landed |
| 受影响任务 | `EXT-009`（`planned`）；`next_action=计划审查`；Developer **NOT** authorized；不改变 Appendix B 阶段库语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 规划决议 | `ProductionExtractionPipeline` closes EXT-003→EXT-007 `DEFERRED_FOR_MVP`；worker `main()` wiring；consumer LD-1 terminal reload idempotency；E2E-1..4 + §3.28 failure injection；compose.test + Fake LLM/embedding/tokenize；zero EXT-002..007 service semantics diff |
| Open Issues | 无 blocking |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否（MVP_LOCAL_DECISION LD-1..LD-7 仅 Plan 层；未改规格正文） |
| 审批 | Planner only；`next_action=计划审查`；`developer_authorized=false`；不得触碰 DEV-006 / PR #13 |

### CHANGE-072

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-13 |
| 原因 | EXT-009 POST_MERGE_CLEANUP：PR #43 MERGED；implementation + record 已在 main；完成治理状态并清理 exact feature branch |
| 受影响任务 | `EXT-009`（`completed`）；`RET-001` remains `planned` / **NOT AUTO-STARTED**；`v0.3.0-memory-extraction` milestone condition satisfied；不改变 Appendix B、pipeline/terminal-before-offset/retrieval replay 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 事实记录 | implementation `d6a4bf596b78275ce3e8644a79e2dc8d218675d4`；record `ddfb89ca8e466e0802d9e98177295a9effb41725`；PR #43 MERGED `c05691144b650b22be714736de3c200076c340c3`；mergedAt `2026-08-13T01:11:57Z`；CODE_REVIEW_APPROVED P0=0/P1=0/P2=0；fetch stale classified `SAFE_AUTO_REMEDIATION` and resolved with ff-only |
| 交付与不变量 | `ProductionExtractionPipeline` 闭合 EXT-003→007 continuation；terminal Mongo persistence precedes Kafka Offset；`extraction_result` replay skips LLM and Retrieval ES upsert converges without duplicate Memory/Evidence/ES documents；EXT-002..007 service semantics zero diff |
| Open Issues | 无 blocking |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态、里程碑条件与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=RET-001 planned / NOT AUTO-STARTED`；不得自动启动 RET-001 |

### CHANGE-073

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-13 |
| 原因 | RET-001 POST_MERGE_CLEANUP：PR #44 MERGED；implementation 已在 main；完成治理状态并清理 exact feature branch |
| 受影响任务 | `RET-001`（`completed`）；`RET-002` remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、BM25/Vector/RRF 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 事实记录 | plan `3f7e333132a6c1bc013eeb5ac0b5b47954734aab`；implementation `fc435db722ed29c05980d6a1a60d9f57fda80968`；PR #44 MERGED `a4dda57366b9e0cb2a1fb34b6526a07daa30ed31`；mergedAt `2026-08-13T02:29:09Z`；CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=2 non-blocking；fetch stale resolved with ff-only |
| 交付与不变量 | §2.2.7 BM25 internal channel read-only；`Bm25RetrievalService` + ES `multi_match` on alias；user_id isolation；Integration ES Fixture not EXT-007 pipeline；零 durable write |
| Open Issues | OI-008 non-blocking（RET-005 API 编辑性） |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=RET-002 planned / NOT AUTO-STARTED`；不得自动启动 RET-002 |

### CHANGE-074

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-13 |
| 原因 | 用户显式规划 **RET-002**：Vector 召回 + RRF 融合 Task Plan（§2.2.6 检索路径 query norm/embed、§2.2.8 Vector、§2.2.9 RRF）；同步 progress/master_plan 规划态 |
| 受影响任务 | `RET-002`（`planned`）；**不**开始实施直至 `PLAN_APPROVED`；**不**触碰 DEV-006/PR #13；RET-001 保持 `completed` |
| 事实记录 | baseline `e5f5c9de9883d04759f19080c01f1f50d2c62513`；main clean tree；RET-001 PR #44 MERGED；DEV-007 completed |
| 交付范围（计划） | `normalize_retrieval_query`；`VectorRetrievalService` + ES kNN；`HybridRetrievalService` 并行 BM25+Vector；`fuse_rrf`；共享 filter builder；Integration ES Fixture + Fake embed |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | **否**（对齐既有 §2.2.6/§2.2.8/§2.2.9；LD-1 记录 SiliconFlow token 语义） |
| 审批 | Planner 初版；等待独立 Plan Review → `PLAN_APPROVED` |

### CHANGE-075

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-13 |
| 原因 | RET-002 POST_MERGE_CLEANUP：PR #45 MERGED；implementation 已在 main；完成治理状态并清理 exact feature branch |
| 受影响任务 | `RET-002`（`completed`）；`RET-003` remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、Vector/RRF/Neo4j 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 事实记录 | plan `da1736925b767777bd8f538d5719d5821bebc017`；implementation `3bf3a1b760080d4f581ab53dad0961a28dfb63a4`；PR #45 MERGED `2bfc2b2ddbd5ef69a2a3f473722b32a9ead3d461`；mergedAt `2026-08-13T03:13:39Z`；CODE_REVIEW_APPROVED P0=0/P1=0/P2=1 non-blocking；fetch 后 origin/main 领先本地 main，已通过 --ff-only 同步 |
| 交付与不变量 | §2.2.6 query norm + single-query embed；§2.2.8 Vector kNN；§2.2.9 RRF fusion + `retrieval_mode`；`HybridRetrievalService` 并行 BM25+Vector；共享 filter builder；BM25 零语义变更；Integration ES Fixture not EXT-007 pipeline；零 durable write |
| Open Issues | OI-008 non-blocking（RET-005 API 编辑性） |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=RET-003 planned / NOT AUTO-STARTED`；不得自动启动 RET-003 |

### CHANGE-076

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-13 |
| 原因 | RET-003 POST_MERGE_CLEANUP：PR #46 MERGED；implementation 已在 main；完成治理状态并清理 exact feature branch |
| 受影响任务 | `RET-003`（`completed`）；`RET-004` remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、Neo4j/ACT-R/HTTP 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 事实记录 | plan `144844295bbd98b962e269e870e57685c2af9fe4`；implementation `64f71690d6c7ac08762b45d76a34158b49570e24`；PR #46 MERGED `3746f1bce38b4f6e4c0ab4d7899eff5622cc21c0`；mergedAt `2026-08-13T05:03:28Z`；CODE_REVIEW_APPROVED P0=0/P1=0/P2=2 non-blocking；fetch 后 origin/main 领先本地 main，已通过 --ff-only 同步 |
| 交付与不变量 | §2.2.10 Neo4j authoritative recall + one-hop graph expansion + ES MGET existence；内部 `dirty_index_document` / `stale_index_document` / `graph_expansion_failed` Warning 种类；新建 `retrieval_memory_read_repository` + `mget_retrieval_repository`（禁止混用 EXT-007 扩展语义）；RET-002 RRF 零语义变更；Integration Neo4j+ES Fixture；零 durable write |
| Open Issues | OI-008 non-blocking（RET-005 API 编辑性） |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=RET-004 planned / NOT AUTO-STARTED`；不得自动启动 RET-004 |

### CHANGE-077

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-13 |
| 原因 | RET-004 POST_MERGE_CLEANUP：PR #47 MERGED；implementation 已在 main；完成治理状态并清理 exact feature branch |
| 受影响任务 | `RET-004`（`completed`）；`RET-005` remains `planned` / **NOT AUTO-STARTED**；不改变 Appendix B、Neo4j/ACT-R/HTTP 语义或 unrelated issues；不触碰 DEV-006 / PR #13 |
| 事实记录 | plan `e3e98eeec645ed759fd90579149fae3e3420214c`；implementation `e631d206b26175d341602ffdfd42a3d8f43edd3f`；PR #47 MERGED `f505c25572f5695a772ac8598be9c8602b36aa9e`；mergedAt `2026-08-13T06:47:29Z`；CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=2 non-blocking；fetch 后 origin/main 已通过 --ff-only 同步 |
| 交付与不变量 | §2.2.11 ACT-R scoring；Top-K before Evidence；Evidence does not affect final_score；新建 `act_r_scoring` + `retrieval_scoring_service` + `retrieval_evidence_read_repository` + `evidence_aggregation`（禁止混用 EXT-005）；Integration Neo4j Evidence Fixture；零 durable write |
| Open Issues | OI-008 non-blocking（RET-005 API 编辑性） |
| 依赖 / Migration 结论 | `dependency_changes_expected=NONE`；`migration_changes_expected=NONE` |
| 是否改变技术规格 | 否；仅完成治理状态与证据登记 |
| 审批 | Release Operator `POST_MERGE_CLEANUP`；`next_action=RET-005 planned / NOT AUTO-STARTED`；不得自动启动 RET-005 |

Master Plan 如需再变，必须新增变更编号，禁止静默修改任务目标、依赖或验收标准。
