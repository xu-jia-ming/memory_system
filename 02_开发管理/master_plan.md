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
DEV-006  → TEI Embedding Client（EXT-007 与 Retrieval 共享）
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
| DEV-004 | Migration Runner；含 ES Mapping + Alias | §3.12, §3.26, §2.2.4 | DEV-003 | planned |
| DEV-005 | 通用 API 壳、鉴权、Request ID、日志与指标 | §3.7, §3.21, §3.23, §3.27 | DEV-002 | planned |
| DEV-006 | TEI Embedding Client + Token Budget（共享） | §3.2, §3.10, §2.2.6 | DEV-003 | planned |

### Phase 0 补充：开发工作流自动化（非业务规格）

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| DEV-OPS-001 | Cursor Agent 工作流自动化（项目级 Slash Commands） | 非业务：对齐治理与 `03_AI_Prompts` 角色流程 | DEV-001 | completed |
| DEV-OPS-002 | Cursor Orchestrator、可复用 Subagents 与受控 Release Automation | 非业务：扩展 DEV-OPS-001；官方 Subagents / permissions | DEV-OPS-001 | completed |
| DEV-OPS-003 | NORMAL / STRICT 工作流模式；减少常规人工机械门禁 | 非业务：扩展 DEV-OPS-002；保留六 Subagent 与唯一 Git 写角色 | DEV-OPS-002 | approved |

#### DEV-OPS-003 NORMAL / STRICT 工作流模式

- **目标**：引入 `NORMAL`（默认）与 `STRICT`（显式）两种工作流模式。NORMAL 常规人工门禁仅 `PLAN_APPROVED` + Human PR Merge；机械 Git 步骤由 Orchestrator 在批准转换点**自动调度** Release Operator（分 `PLAN_LANDING` / `IMPLEMENTATION_RELEASE` / `POST_MERGE_CLEANUP`）。STRICT 保留 DEV-OPS-002 行为。Release Operator **仍是唯一 Git 写 Subagent**；Orchestrator 自身不写 Git。
- **非目标**：开始 DEV-004；改业务代码/规格；webhook 自动 merge；Orchestrator 直接 Git 写；取消 Code Review / 测试门禁；删除六 Subagent 或五 fallback 命令；`gh pr merge` / force push / `git branch -D`。
- **关键设计决策**：最小变更保留 DEV-OPS-002 安全模型——Git 写权威仍集中于 Release Operator；NORMAL 仅减少「人工再次批准去调用 Release」的机械门禁。
- **变更文件（预期）**：`orchestrate-task.md`；`release-operator.md`（及最小 Agent 对齐）；治理窄例外两文件；`permissions.json` / `cli.json`；契约测试（含新建 modes contract）；本任务开发管理回写。
- **测试**：NORMAL/STRICT 合同；fail-closed negatives；既有 DEV-OPS-002 契约保持或有意修订并写 rationale；受监督冒烟（实施后）。
- **验收**：mode 声明；NORMAL 两门禁；STRICT 兼容；唯一 Git 写；异常 HALT；完成后 `next_action`→DEV-004；**本任务期间不得启动 DEV-004**。
- **插入说明**：**人工显式插入**于 DEV-004 业务规划之前（用户覆盖先前「不得插入 DEV-OPS-003」的 next_action）。
- **计划文件**：`02_开发管理/tasks/DEV-OPS-003-normal-strict-workflow-modes.md`
- **状态备注**：`approved`（2026-08-07 15:22 UTC 初版；15:35 UTC Amendment 001 回应 Round 1 `PLAN_REJECTED` / MF-001 方案 A + SF-001–004；Round 2 Plan Reviewer = `PLAN_APPROVED`；人工确认 2026-08-07 15:39 UTC）；未实施；未创建 feat；未 Git 写；本任务自身 STRICT（NORMAL 自动 phase 尚未可用）；`plan_commit=null`（待人工 docs(plan) on main）。

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

- **目标**：`scripts/migrate.py` + `001`–`004`；Mongo `infra_schema_migrations`；**唯一**创建 ES 版本化 Index、Mapping、Alias；Neo4j/Kafka/Mongo 初始化幂等。
- **非目标**：业务 Document 写入；Retrieval/Extraction 逻辑。
- **变更文件**：`scripts/migrate.py`、`scripts/migrations/001_*.py`–`004_*.py`、相关测试。
- **测试**：Integration（首次成功、重复幂等、checksum 篡改失败）；ES alias/mapping 断言。
- **验收**：`python -m scripts.migrate` 符合 §3.26/§3.32。
- **风险**：修改已执行 Migration；与规格 Mapping 不一致。
- **调度备注**：状态仍 `planned`；**因用户显式插入 DEV-OPS-003 而暂缓启动**；不得在 DEV-OPS-003 完成前开始 DEV-004 规划/实施。

#### DEV-005 通用 API、鉴权、Request ID、日志与指标

- **目标**：FastAPI 应用壳；**创建并实现** `api/dependencies.py`、`middleware.py`、`error_handlers.py`（DEV-001 仅保留 `api/__init__.py` 与 `api/routes/__init__.py`）；`X-API-Key` constant-time；统一错误包络；Request ID；structlog JSON；`/internal/metrics`；liveness；readiness 结构（完整探针可随后续客户端补全，本任务不宣称 §3.16 全部完成）。
- **非目标**：STM/Retrieval 业务路由实现；OpenTelemetry。
- **变更文件**：上述 api 具名模块、`entrypoints/api.py` 接线、`observability/`、`infrastructure/security/`。
- **测试**：Unit/Contract（鉴权 401、错误形状、Request ID 回传）；敏感日志断言。
- **验收**：符合 §3.21/§3.23/§3.27。
- **风险**：非 constant-time 比较；日志泄漏。

#### DEV-006 TEI Embedding Client + Token Budget

- **目标**：共享 `EmbeddingClient` Protocol + TEI HTTP 适配；`/tokenize` 与 `/v1/embeddings`；1024 token 硬限制；CPU/GPU Token Budget 确定性分批；输出维度 1024。
- **非目标**：ES 写入；BM25；改模型/Revision/引擎版本。
- **变更文件**：`src/memory_system/infrastructure/embedding/`、Contract fixtures。
- **测试**：Contract（Fake TEI）；Integration（真实 TEI，发布阻塞 CPU 模式）。
- **验收**：供 EXT-007 与 Retrieval 复用；规格 §3.10/§2.2.6。
- **风险**：热切换；维度漂移；超长输入未拒绝。

---

### Phase 1：短期记忆

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| STM-001 | Token 估算、WM Key/字段模型、配置校验 | §1.2.1 | DEV-002 | planned |
| STM-002 | Session 创建 | §1.2.1, §1.2.3 | STM-001, DEV-005 | planned |
| STM-003 | 消息写入 Lua（幂等/容量；不含完整压缩） | §1.2.1, §1.2.3 | STM-002 | planned |
| STM-004 | 上下文一致性读取 Lua | §1.2.1, §1.2.3 | STM-002 | planned |
| STM-005 | Mongo `context_archive` create/reuse | §1.2.2 | STM-003, DEV-004 | planned |
| STM-006 | 压缩锁、pending archive、Kafka 发布 | §1.2.4, §1.2.6 | STM-005 | planned |
| STM-007 | Compression LLM Client + Structured Output | §1.2.5, §3.9 | DEV-002 | planned |
| STM-008 | Compression Finalize Lua | §1.2.5, §1.2.6 | STM-006, STM-007 | planned |
| STM-009 | Compression Coordinator + 写入 API 接线 | §1.2.3, §1.2.6 | STM-003, STM-004, STM-008 | planned |
| STM-010 | Session Close | §1.2.3, §1.2.7 | STM-006, STM-009 | planned |
| STM-011 | `republish_archive_event.py` 补发脚本 | §1.2.4, §3.4 | STM-006 | planned |
| STM-012 | 补发事件消费验证 | §1.2.4, §2.1.4 | STM-011, EXT-001 | planned |
| STM-013 | 短期记忆阶段 E2E + 关键失败注入 | §1, §3.28 | STM-010 | planned |

#### STM-001

- **目标**：字符 Token 估算；Redis key/字段常量与模型；相关配置不等式校验。
- **非目标**：Redis 写入；HTTP API。
- **测试**：Unit（中英文边界、ceil 公式）。
- **风险**：OI-001/002 不在本任务解释。

#### STM-002

- **目标**：`POST /api/v1/memory/session`；初始化 Working Memory Hash（`status=active`，`compression_version=0`）。
- **非目标**：消息写入；压缩。
- **测试**：Integration（用户隔离、字段齐全）。

#### STM-003

- **目标**：消息写入 Lua：`message_id` 幂等、容量校验、`duplicate`/`capacity_exceeded` 内部语义；**不含**完整多轮压缩协调。
- **非目标**：Coordinator；Kafka。
- **测试**：Unit/Integration（重复 id、容量、并发写入）；用户隔离。

#### STM-004

- **目标**：上下文一致性读取 Lua（version + compressed_context + messages 原子快照）。
- **非目标**：压缩写回。
- **测试**：Integration；参见 OI-009（不得自行定 Contract）。

#### STM-005

- **目标**：`context_archive` 集合与唯一索引；按 `archive_batch_key` create/reuse。
- **非目标**：Kafka；pending Redis 字段（STM-006）。
- **测试**：Integration（唯一键冲突复用）；参见 OI-004。

#### STM-006

- **目标**：压缩锁（NX+owner token）；pending_archive_*；发布 `context.archive.created`（失败仅日志，不阻断后续压缩语义按规格）。
- **非目标**：LLM 压缩；Finalize；补发脚本（STM-011）。
- **测试**：Integration（锁互斥、pending 写入、Kafka 契约字段）。

#### STM-007

- **目标**：DeepSeek Compression Client；`deepseek-v4-flash`；json_object + Pydantic 校验；超时/非法输出错误。
- **非目标**：Finalize Lua；Coordinator。
- **测试**：Contract（Fake LLM）；禁止 CI 真实计费调用。

#### STM-008

- **目标**：Finalize Lua：锁 owner、`compression_version`、pending/head 校验、更新摘要、LTRIM、清 pending。
- **非目标**：多轮策略。
- **测试**：Integration（version_conflict、pending 不匹配）。

#### STM-009

- **目标**：多轮 Compression Coordinator；写入 API 接线与 `compression_status`；容量路径触发压缩（语义待 OI-001/002 决议前按规格字面实现并在 Task Plan 标注开放问题）。
- **非目标**：Session Close。
- **测试**：Integration/失败注入（LLM 超时、锁占用）。

#### STM-010

- **目标**：Close 状态机、切分、resume、早失败回滚、原子删 Redis；`close_incomplete`（HTTP 映射见 OI-003，不得臆造）。
- **非目标**：Extraction。
- **测试**：Integration/E2E 片段；部分失败与恢复。

#### STM-011

- **目标**：实现 `scripts/republish_archive_event.py`（发布侧）。
- **非目标**：消费侧任务创建断言（属 STM-012）。
- **前置**：**仅 STM-006**。
- **测试**：Unit/脚本级；不依赖 EXT-001。

#### STM-012

- **目标**：补发事件被 Extraction Consumer 消费的 Integration/E2E 验证（任务幂等创建等）。
- **前置**：STM-011, EXT-001。
- **非目标**：修改补发脚本业务语义（除非缺陷修复）。

#### STM-013

- **目标**：STM 阶段端到端：Session → Message → Archive → Compression → Close；含规格要求的 STM 相关失败注入。
- **前置**：STM-010。
- **测试**：E2E。

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
| EXT-007 | Retrieval Document 同步 | §2.2.3 | EXT-006, DEV-006, DEV-004 | planned |
| EXT-008 | Extraction 管理 GET/Retry | §2.1.14 | EXT-007, DEV-005 | planned |
| EXT-009 | Extraction E2E + 失败注入 | §2.1.15, §3.28 | EXT-008 | planned |

#### EXT-001–EXT-006（摘要）

- 各自单 Commit：任务状态机与 Offset；预处理；LLM；实体对齐；和解；图谱事务。
- **风险**：OI-006（`reconciliation_plan_conflict` 运维清理无 Contract）——EXT-008 前需规格确认，不得自行发明 API。

#### EXT-007 Retrieval Document 同步

- **目标**：search_text、调用 DEV-006 Embedding、Bulk upsert（`refresh=wait_for`）；作为 Extraction 完成门禁之一。
- **非目标**：**不创建/修改** Mapping 或 Alias（缺失则失败）。
- **前置**：EXT-006, DEV-006, DEV-004。
- **测试**：Integration（部分 bulk 失败、Neo4j 成功后 ES 失败恢复路径按规格）。

#### EXT-008 / EXT-009

- 管理接口与阶段 E2E/失败注入（含 Worker 在 Neo4j commit 后退出等）。

---

### Phase 3：长期记忆检索

| Task ID | Task | 规格章节 | 前置依赖 | 状态 |
|---|---|---|---|---|
| RET-001 | BM25 查询 | §2.2.7 | DEV-004, DEV-006 | planned |
| RET-002 | Vector 召回 + RRF | §2.2.8, §2.2.9 | RET-001, DEV-006 | planned |
| RET-003 | Neo4j 权威回读 + 一跳扩展 + MGET | §2.2.10 | RET-002 | planned |
| RET-004 | ACT-R 评分 + Evidence 聚合 | §2.2.11, §2.2.12 | RET-003 | planned |
| RET-005 | Retrieval API、降级/超时、统计更新 | §2.2.5, §2.2.13–2.2.15 | RET-004, DEV-005 | planned |
| RET-006 | Retrieval 阶段 E2E + 失败注入 | §2.2.16, §3.28 | RET-005, EXT-007 | planned |

#### RET-001 BM25 查询

- **目标**：对已存在 Alias 执行 BM25；过滤器与字段权重按规格。
- **非目标**：创建 Mapping/Alias；Vector/RRF；硬依赖 EXT-007。
- **前置**：**仅 DEV-004, DEV-006**（DEV-006 为共享客户端就绪；本任务查询路径可不调用 Embedding）。
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
| `v0.1.0-bootstrap` | Phase 0 完成（含 DEV-006） |
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
| 受影响任务 | 新增 `DEV-OPS-003`（Phase 0 补充，现 `approved`）；DEV-004 保持 `planned` 但**延后至 DEV-OPS-003 completed 之后**；**不**修改 DEV-OPS-001/002 / DEV-001–003 完成状态；**不**改变 DEV-004+ 业务范围正文 |
| 是否改变技术规格 | **否** |
| 审批 | Round 1 `PLAN_REJECTED`（MF-001）；Amendment 001；Round 2 Plan Reviewer = `PLAN_APPROVED`（BLOCKER 0 / MUST_FIX 0）；人工确认 2026-08-07 15:39 UTC；状态 `approved`；`plan_commit=null`（待 docs(plan) on main） |

Master Plan 如需再变，必须新增变更编号，禁止静默修改任务目标、依赖或验收标准。
