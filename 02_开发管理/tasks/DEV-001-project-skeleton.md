# DEV-001 项目骨架、依赖与质量工具

## 1. 任务信息

```yaml
task_id: DEV-001
task_name: 项目骨架、依赖与质量工具
status: reviewed
spec_sections:
  - "§3.4 单仓库目录结构（仅本任务白名单子集）"
  - "§3.5 Python 与依赖管理"
  - "§3.2 应用容器与进程边界（入口模块占位）"
  - "§3.28 测试策略（目录与质量工具配置）"
prerequisites:
  - "无代码前置任务"
  - "实施编码前必须满足 PRE-ENV-001（已安装 uv）"
  - "实施编码前必须满足 PRE-ENV-002（Python 3.12.13 via uv）"
branch: "feat/DEV-001-project-skeleton"  # 实施分支；计划 Commit 在 main，见 §13
created_at: "2026-08-06 07:25 UTC"
updated_at: "2026-08-06 10:30 UTC"
approval_gates:
  planning_docs: "PLANNING_DOCS_APPROVED"
  implementation_plan: "PLAN_APPROVED；实现 Code Review 通过（reviewed）；等待人工 build(bootstrap) Commit"
```

## 2. 任务目标

本任务**只创建 DEV-001 范围内的 §3.4 目录与文件子集**（见下文白名单），**不**宣称完成本规格 §3.4 全部固定目录树。

完成后应具备：

1. 白名单内的 `memory_system` 包目录与三 Entrypoint 模块（可安全 `import`）。
2. `.python-version` 为 `3.12.13`；`pyproject.toml` 的 `project.dependencies` / `quality` / `test` 版本约束字符串与规格 §3.5 **完全一致**；且必须包含规格固定的 `[build-system]`（`requires = ["uv_build>=0.11.32,<0.13"]`，`build-backend = "uv_build"`）；由 `uv lock` 生成并提交 `uv.lock`。
3. ruff、mypy、pytest（含 asyncio、cov 插件声明，**不新增**测试依赖包）项目配置可运行。
4. 三入口通过子进程执行规格启动命令；未就绪时非零退出并输出明确错误。
5. `.gitignore` / `.dockerignore` / `README.md` 按白名单创建；README 不宣称 Compose/业务可用。

## 3. 非目标

- 完成规格 §3.4 **全部**固定目录树。
- 创建黑名单中的任何路径（含空实现）。
- `configs/` 目录或任何 YAML（统一 DEV-002）。
- `.env.example`、Settings 加载逻辑（DEV-002）。
- Dockerfile、Compose、`versions.*`、Preflight 脚本实现（DEV-003）。
- Migration Runner 与 `001_`–`004_` 迁移模块（DEV-004）。
- `api/dependencies.py`、`middleware.py`、`error_handlers.py` 及业务路由（由 **DEV-005 创建并实现**）。
- TEI Embedding Client（DEV-006）。
- 将 Build Backend 替换为 Hatchling、Setuptools、Poetry Backend 或其他非规格后端；将 `uv_build` 写入 `project.dependencies`、`quality` 或 `test` 组；放宽/抬高 `uv_build` 版本上界。
- 伪造 HTTP/业务成功响应；import 阶段抛出 `NotImplementedError` 或 `SystemExit`。
- 放宽/抬高 §3.5 运行时/质量/测试依赖版本上界；引入 Poetry / Pipenv / Conda。
- Git Commit/Push/分支操作（人工按 `progress.md` 流程执行）。

## 4. 当前代码状态

- 已存在代码：无业务或工程代码；仅有 AI 开发文档包。
- 可复用组件：无。
- 当前缺失：白名单所列全部工程文件。
- 与技术规格不一致之处：仓库根尚无工程树；`master` 尚无 Commit（目标默认分支 `main`）。OI-010 已决议，§3.5 已固定 `uv_build`。
- 前置任务检查：无代码前置；实施前须满足 PRE-ENV-001/002。

## 5. 文件白名单（本任务允许创建的全部路径）

禁止使用 `src/memory_system/**`、`scripts/**` 等不可审查通配作为变更描述。实施时**仅允许**创建下列路径：

### 5.1 根与工程元数据

| 路径 | 必选属性 / 说明 |
|---|---|
| `pyproject.toml` | 含 `requires-python = ">=3.12,<3.13"`；含 §3.5 三组依赖；含 `[build-system] requires = ["uv_build>=0.11.32,<0.13"]` 与 `build-backend = "uv_build"`；`uv_build` 不得出现在 dependencies/quality/test |
| `uv.lock` | 由 `uv lock` 生成 |
| `.python-version` | `3.12.13` |
| `.gitignore` | 排除 Secret/缓存/运行时等 |
| `.dockerignore` | 构建上下文排除 |
| `README.md` | 引导；不宣称 Compose/业务完成 |

### 5.2 `src/memory_system` 包（仅下列文件）

| 路径 |
|---|
| `src/memory_system/__init__.py` |
| `src/memory_system/entrypoints/__init__.py` |
| `src/memory_system/entrypoints/api.py` |
| `src/memory_system/entrypoints/extraction_worker.py` |
| `src/memory_system/entrypoints/consolidation_worker.py` |
| `src/memory_system/api/__init__.py` |
| `src/memory_system/api/routes/__init__.py` |
| `src/memory_system/domain/__init__.py` |
| `src/memory_system/domain/models/__init__.py` |
| `src/memory_system/domain/enums/__init__.py` |
| `src/memory_system/domain/errors/__init__.py` |
| `src/memory_system/domain/services/__init__.py` |
| `src/memory_system/application/__init__.py` |
| `src/memory_system/application/short_term_memory/__init__.py` |
| `src/memory_system/application/compression/__init__.py` |
| `src/memory_system/application/extraction/__init__.py` |
| `src/memory_system/application/retrieval/__init__.py` |
| `src/memory_system/application/consolidation/__init__.py` |
| `src/memory_system/infrastructure/__init__.py` |
| `src/memory_system/infrastructure/redis/__init__.py` |
| `src/memory_system/infrastructure/mongodb/__init__.py` |
| `src/memory_system/infrastructure/kafka/__init__.py` |
| `src/memory_system/infrastructure/neo4j/__init__.py` |
| `src/memory_system/infrastructure/elasticsearch/__init__.py` |
| `src/memory_system/infrastructure/llm/__init__.py` |
| `src/memory_system/infrastructure/embedding/__init__.py` |
| `src/memory_system/infrastructure/security/__init__.py` |
| `src/memory_system/settings/__init__.py` |
| `src/memory_system/observability/__init__.py` |
| `src/memory_system/utils/__init__.py` |

### 5.3 `scripts/`（仅下列文件）

| 路径 |
|---|
| `scripts/__init__.py` |
| `scripts/migrations/__init__.py` |
| `scripts/preflight/.gitkeep` |

### 5.4 测试

| 路径 |
|---|
| `tests/unit/test_entrypoints_import.py` |
| `tests/unit/test_dependency_contract.py` |
| `tests/unit/.gitkeep`（若目录需占位且无其它文件时可不重复） |
| `tests/integration/.gitkeep` |
| `tests/contract/.gitkeep` |
| `tests/e2e/.gitkeep` |
| `tests/conftest.py`（可选；不得引入额外测试依赖） |

## 6. 文件黑名单（禁止本任务创建，含空实现）

| 路径 / 模式 | 归属 |
|---|---|
| `configs/`（目录及任何 YAML） | DEV-002 |
| `.env.example` | DEV-002 |
| `Dockerfile`、`compose.yaml`、`compose.override.yaml`、`compose.embedding.cpu.yaml`、`compose.embedding.gpu.yaml`、`compose.test.yaml` | DEV-003 |
| `versions.env`、`versions.lock.env` | DEV-003 |
| `scripts/compose.sh`、`scripts/start_embedding.sh`、`scripts/lock_tei_images.sh` | DEV-003 |
| `scripts/preflight/check_linux_host.sh` | DEV-003 |
| `scripts/check_env_example.py` | DEV-002 |
| `scripts/migrate.py` | DEV-004 |
| `scripts/migrations/001_initial_mongodb.py` | DEV-004 |
| `scripts/migrations/002_initial_neo4j.py` | DEV-004 |
| `scripts/migrations/003_elasticsearch_memory_v1.py` | DEV-004 |
| `scripts/migrations/004_initial_kafka_topics.py` | DEV-004 |
| `scripts/republish_archive_event.py` | STM-011 |
| `src/memory_system/api/dependencies.py` | DEV-005（创建并实现） |
| `src/memory_system/api/middleware.py` | DEV-005（创建并实现） |
| `src/memory_system/api/error_handlers.py` | DEV-005（创建并实现） |
| `src/memory_system/api/routes/` 下除 `__init__.py` 外的任何业务路由模块 | DEV-005 及后续业务任务 |

## 7. 实现方案

### Step 0 — 状态回写（强制，贯穿全程）

- 实施开始前：将本 Task Plan 与 `progress.md` 的 `current_task_status` 更新为 `in_progress`。
- 实现完成后：`implemented`（同步 progress 与本文件 §13/§14）。
- 测试通过后：`tested`。
- 审查通过后：`reviewed`。
- 实现 Commit 完成后：`committed`。
- **禁止**仅在任务结束时一次性补写上述状态。

### Step 1 — 白名单目录与 `__init__.py`

- 仅创建 §5 白名单中的包路径与空 `__init__.py`（及 `scripts/preflight/.gitkeep`）。
- 不得创建黑名单路径。

### Step 2 — 三 Entrypoint（安全导入 + 规格启动命令）

- 文件：白名单中的三个 `entrypoints/*.py`。
- 模块级只做符号定义；`import` 不得抛出 `NotImplementedError`、`SystemExit`。
- 作为 `python -m memory_system.entrypoints.*` 执行且未就绪时：明确错误信息 + **非零**退出。
- 禁止伪造成功启动或假业务返回。

### Step 3 — 依赖与锁定

- `pyproject.toml`：`requires-python` 与 `project.dependencies` / `dependency-groups.quality` / `dependency-groups.test` 字符串与规格 §3.5 **逐字一致**。
- `pyproject.toml` 必须包含规格固定的：

```toml
[build-system]
requires = ["uv_build>=0.11.32,<0.13"]
build-backend = "uv_build"
```

- `uv_build` 仅为 Build System Requirement，**不得**写入三组依赖。
- 禁止替换为其它 Build Backend。
- `uv.lock`：在 PRE-ENV 满足后由 `uv lock` 生成；禁止手改 lockfile。
- 禁止 Poetry/Pipenv/Conda 文件。

### Step 4 — 质量工具配置

- 在 `pyproject.toml` 配置 ruff、mypy、pytest（含已在 §3.5 test 组声明的 asyncio、cov）。
- 不得新增 §3.5 以外的测试/质量依赖。

### Step 5 — 忽略规则与 README

- 按白名单创建 `.gitignore`、`.dockerignore`、`README.md`。
- README 指向规格 §3.17，并声明 Phase 0 后续任务边界；注明 Build Backend 为规格固定的 `uv_build`。

### Step 6 — 测试实现

- `tests/unit/test_entrypoints_import.py`：见 §10。
- `tests/unit/test_dependency_contract.py`：见 §10（仅用 `tomllib`）。

## 8. 文件变更清单

与 §5 白名单完全一致；创建/目的如下摘要：

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `pyproject.toml` | 创建 | §3.5 三组依赖 + 固定 `[build-system]`（uv_build） |
| `uv.lock` | 创建 | 精确锁定 |
| `.python-version` | 创建 | 3.12.13 |
| `.gitignore` / `.dockerignore` / `README.md` | 创建 | 忽略规则与引导 |
| §5.2 全部路径 | 创建 | 包骨架与三入口 |
| §5.3 全部路径 | 创建 | scripts 最小占位 |
| `tests/unit/test_entrypoints_import.py` | 创建 | import + `python -m` 子进程 |
| `tests/unit/test_dependency_contract.py` | 创建 | §3.5 依赖契约 + build-system 契约 |
| `tests/{integration,contract,e2e}/.gitkeep` | 创建 | 目录占位 |

## 9. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 无跨存储业务写入 |
| 幂等 | 不适用 | 无业务写路径；`uv sync --locked` 可重复 |
| 并发 | 不适用 | 无共享可变业务状态 |
| 版本冲突 | 不适用 | 无乐观锁业务字段 |
| 用户隔离 | 不适用 | 无用户资源 |
| 部分失败 | 不适用 | 无多步骤业务事务 |
| 进程异常恢复 | 不适用 | 入口未就绪仅非零退出 |

## 10. 测试计划

### Unit Test — Entrypoint

| 场景 | 预期 |
|---|---|
| `import memory_system.entrypoints.api` | 成功，无 SystemExit |
| `import memory_system.entrypoints.extraction_worker` | 成功，无 SystemExit |
| `import memory_system.entrypoints.consolidation_worker` | 成功，无 SystemExit |
| 子进程：`python -m memory_system.entrypoints.api`（未就绪） | 非零退出；stdout/stderr 含明确错误；无假成功 |
| 子进程：`python -m memory_system.entrypoints.extraction_worker`（未就绪） | 同上 |
| 子进程：`python -m memory_system.entrypoints.consolidation_worker`（未就绪） | 同上 |

### Unit Test — Dependency Contract（`tests/unit/test_dependency_contract.py`）

| 场景 | 预期 |
|---|---|
| 使用标准库 `tomllib` 解析 `pyproject.toml` | 成功 |
| `project.requires-python` | 精确等于 `">=3.12,<3.13"`（与规格 §3.5 一致） |
| `project.dependencies` 每一项名称与版本约束字符串 | 与规格 §3.5 列表**完全一致**（集合与字符串均一致）；**不含** `uv_build` |
| `dependency-groups.quality` | 与 §3.5 **完全一致**；**不含** `uv_build` |
| `dependency-groups.test` | 与 §3.5 **完全一致**；**不含** `uv_build` |
| `[build-system].requires` | 等于 `["uv_build>=0.11.32,<0.13"]`（与规格一致） |
| `[build-system].build-backend` | 等于 `"uv_build"` |
| 仓库不存在 `poetry.lock`、`Pipfile`、`Pipfile.lock`、`environment.yml`、`conda-lock.yml` 等并行依赖管理文件 | 断言不存在 |
| 本测试不得新增测试依赖 | 仅使用 stdlib + 已声明的 pytest |

### Contract / Integration / E2E / 失败注入

| 层级 | 本任务 |
|---|---|
| Contract（外部 LLM/TEI/Kafka） | 不适用 |
| Integration（Docker 基础设施） | 不适用 |
| E2E | 不适用 |
| 失败注入与并发 | 不适用 |

### 质量门禁

| 检查 | 预期 |
|---|---|
| `uv sync --locked` | 退出码 0（PRE-ENV 满足后） |
| Ruff | 通过 |
| Mypy | 通过 |
| Pytest（本任务 Unit） | 通过 |

## 11. 验收标准（与白名单逐项对应）

### 白名单存在性

- [x] §5.1 全部根文件已创建且内容符合本计划
- [x] §5.2 全部包路径已创建；除三入口外仅为 `__init__.py`
- [x] §5.3 仅含允许的三个 scripts 路径；无黑名单脚本/迁移叶文件
- [x] §5.4 测试文件与目录占位已创建
- [x] 黑名单路径均**不存在**

### 行为与依赖

- [x] `.python-version` 为 `3.12.13`
- [x] `project.requires-python` 精确为 `">=3.12,<3.13"`（由 `test_dependency_contract.py` 断言）
- [x] `pyproject.toml` 含固定 `[build-system]`（`uv_build>=0.11.32,<0.13` / `build-backend = "uv_build"`）
- [x] `test_dependency_contract.py` 全部断言通过（`requires-python`；三组依赖与 §3.5 一致；build-system 单独断言通过；`uv_build` 未混入运行时/quality/test；无并行依赖工具文件）
- [x] 三入口模块 **import 成功**
- [x] 三个 `python -m memory_system.entrypoints.{api,extraction_worker,consolidation_worker}` 子进程在未就绪时非零退出且有明确错误
- [x] 无伪造业务成功返回；无 import 阶段 `SystemExit`/`NotImplementedError`
- [x] `uv.lock` 存在且 `uv sync --locked` 成功
- [x] Ruff、Mypy、本任务 Pytest 通过
- [x] Review 无 P0/P1
- [x] 未实现 DEV-002+ 黑名单范围内功能
- [x] 状态已按 Step 0 分阶段写入，非一次性补写

## 12. 风险与阻塞项

- 设计文档冲突：无。OI-010 已决议并写入规格 §3.5。
- 当前代码冲突：无。
- 前置任务：无代码前置。
- **实施前置条件：**
  - PRE-ENV-001：安装 `uv`
  - PRE-ENV-002：Python 3.12.13 via uv
- 未批准依赖：禁止新增 §3.5 以外运行时/质量/测试依赖；禁止偏离固定 `uv_build` Build Backend。
- API/Schema 变化：不涉及。
- 其他风险：误建黑名单空实现；README 夸大完成度；手改 `uv.lock`；将 `uv_build` 误写入 dependencies。

## 13. Git 计划

```yaml
# 顶部 branch 字段表示实施分支（本任务编码所在分支）
implementation_branch: "feat/DEV-001-project-skeleton"
expected_commits:
  - branch: "main"
    message: "docs(plan): add DEV-001 project skeleton plan"
  - branch: "feat/DEV-001-project-skeleton"
    message: "build(bootstrap): add project skeleton, uv lock, and quality tooling"
out_of_scope_changes:
  - "黑名单路径与业务逻辑"
  - "替换 Build Backend 或将 uv_build 写入运行时依赖"
  - "规格正文修改（已由独立规划文档变更完成）"
  - "放宽 §3.5 版本上界"
  - "为 Amendment 001/002 分别创建历史计划 Commit"
```

说明：

1. 仓库目前尚无任何 Commit。§14 中的 Amendment 001 / Amendment 002 / Amendment 003 **仅作为本文档内历史记录保留**，不分别创建额外计划 Commit。
2. **`docs(plan): add DEV-001 project skeleton plan` 在 `main` 分支提交**，包含当前最终版 Task Plan（含文内全部 Amendment）以及相关规划状态（如 master_plan / progress 中与本计划相关的 approved 状态更新，按人工基线流程）。
3. **`build(bootstrap): add project skeleton, uv lock, and quality tooling` 在 `feat/DEV-001-project-skeleton` 分支提交**（从 `main` 切出后实施）；仅在计划已 `PLAN_APPROVED`、状态进入实施、实现与测试完成后提交。
4. 本文档顶部 `branch` 字段表示**实施分支**，不是计划 Commit 所在分支。

人工基线顺序见 `progress.md`。当前状态为 **`reviewed`**；独立 Code Review 已通过。本审查会话不执行 Git Commit/Push/Merge/Rebase；`build(bootstrap)` Commit 由人工执行。

## 14. Plan Amendment

### Amendment 001

- 日期：2026-08-06 07:50 UTC
- 原计划：宣称接近完整 §3.4；`scripts/**` / `src/memory_system/**` 通配；configs 可选；api 具名文件边界不清；缺 dependency contract 与强制 `python -m` 子进程测试；缺分阶段状态回写；未将 Build Backend 升为开放问题。
- 修改内容：改为 §3.4 子集；完整白/黑名单；scripts/api/configs 边界；`tomllib` 依赖契约测试；三入口子进程测试；Step 0 状态回写；OI-010 阻塞实施；不自选 Build Backend。
- 修改原因：独立计划审查 MF-001–MF-004、SF-002–SF-004；SF-001 转 OI-010。
- 是否影响技术规格：否（当时 Build Backend 待人工决议）。
- 审批状态：已纳入后续 Amendment 002。

### Amendment 002

- 日期：2026-08-06 08:11 UTC
- 原计划：OI-010 阻塞实施；不得写入 Build Backend。
- 修改内容：删除 OI-010 阻塞；固定 `[build-system]` 为 `uv_build>=0.11.32,<0.13` / `build-backend = "uv_build"`；dependency contract 单独断言 build-system，且不将 `uv_build` 混入三组依赖；验收与白名单属性同步。
- 修改原因：人工正式决议 OI-010；规格 §3.5 已同步。
- 是否影响技术规格：是（§3.5 增补 Build System，已由人工批准并落盘）。
- 审批状态：已纳入 Amendment 003 / PLAN_APPROVED。

### Amendment 003

- 日期：2026-08-06 08:30 UTC
- 原计划：dependency contract 未断言 `requires-python`；Git 计划未区分 `main` 与实施分支上的两次 Commit。
- 修改内容：
  - SF-A：`test_dependency_contract.py` 增加 `project.requires-python == ">=3.12,<3.13"` 精确断言，并同步验收项。
  - SF-B：统一 Git 分支语义——`docs(plan): …` 在 `main` 提交；`build(bootstrap): …` 在 `feat/DEV-001-project-skeleton` 提交；顶部 `branch` 表示实施分支。
  - 状态：`planned` → `approved`（**不**进入 `in_progress`）。
- 修改原因：独立复审已通过（最后一行 `PLAN_APPROVED`）；采纳非阻塞 SHOULD_FIX（SF-A、SF-B）；属验收增强与 Git 流程澄清。
- 是否影响技术规格：否。
- 是否改变范围/技术选型/审批结论：否。
- 审批状态：`PLAN_APPROVED`
- 复审结果：`BLOCKER 0`，`MUST_FIX 0`，`SHOULD_FIX 2`

## 15. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-06 07:25 UTC | 计划落盘 | 创建初版 Task Plan | 无 | 初审未通过 |
| 2026-08-06 07:50 UTC | 计划修订 | Amendment 001：MF/SF 修复 | 无 | OI-010 曾阻塞 |
| 2026-08-06 08:11 UTC | 计划修订 | Amendment 002：uv_build / 关闭 OI-010 | 无 | 等待复审 |
| 2026-08-06 08:30 UTC | 复审通过 | Amendment 003：SF-A/SF-B；status=approved | 无 | 未实施、未 Git |
| 2026-08-06 09:54 UTC | Step 0 状态回写 | status=approved → in_progress；同步 progress / master_plan；PRE-ENV-001/002=satisfied | 无 | 开始白名单实施 |
| 2026-08-06 09:56 UTC | Step 1–5 白名单落地 | 创建 §5 全部包/scripts/测试目录、三入口、pyproject/.python-version/ignore/README | 待跑 | 未创建黑名单路径 |
| 2026-08-06 09:56 UTC | Step 6 测试实现 | 创建 test_entrypoints_import.py、test_dependency_contract.py、conftest.py | 待跑 | 仅 stdlib + 已声明 pytest |
| 2026-08-06 10:12 UTC | Step 3 依赖锁定 | `uv lock` + `uv sync --locked`（经 127.0.0.1:7890 代理访问 PyPI）生成并安装 | sync OK | 未手改 lockfile；status→implemented |
| 2026-08-06 10:14 UTC | 质量门禁 | 微调 pyproject tool 配置（cov 改 `[tool.coverage.*]`，去掉 unused mypy override） | pytest/ruff/mypy 全通过 | status→tested；未 Commit |
| 2026-08-06 10:30 UTC | 独立 Code Review | 对照白名单/§3.2/3.4/3.5/3.28 只读审查；复跑质量门禁 | pytest 12 passed；ruff/mypy/sync 通过 | P0/P1=0；status→reviewed；未 Commit |

## 16. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `pyproject.toml` | 已创建；§3.5 三组依赖 + 固定 `[build-system]` + ruff/mypy/pytest/coverage 配置 |
| `uv.lock` | 已由 `uv lock` 生成（代理 `127.0.0.1:7890`） |
| `.python-version` | `3.12.13` |
| `.gitignore` / `.dockerignore` / `README.md` | 已创建 |
| `src/memory_system/**`（白名单 §5.2） | 包骨架 + 三入口已创建 |
| `scripts/__init__.py` / `scripts/migrations/__init__.py` / `scripts/preflight/.gitkeep` | 已创建 |
| `tests/unit/test_entrypoints_import.py` | 已创建并通过 |
| `tests/unit/test_dependency_contract.py` | 已创建并通过 |
| `tests/conftest.py` | 已创建（无额外依赖） |
| `tests/{integration,contract,e2e}/.gitkeep` | 已创建 |
| `02_开发管理/tasks/DEV-001-project-skeleton.md` | 状态分阶段回写 |
| `02_开发管理/master_plan.md` / `02_开发管理/progress.md` | 状态同步 |

### 与原计划的差异

- 无范围差异。`pytest-cov` 以 `[tool.coverage.*]` 配置，未作为 Unit 默认 `addopts` 强制启用（避免空 domain/application 噪声警告）；插件仍在 §3.5 `test` 组。
- `uv lock`/`uv sync` 通过本机 HTTP 代理 `127.0.0.1:7890` 访问 PyPI。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit` | 通过（12 passed） |
| Contract | N/A（本任务不适用） | N/A |
| Integration | N/A（本任务不适用） | N/A |
| E2E | N/A（本任务不适用） | N/A |
| Ruff | `uv run ruff check .` | 通过（All checks passed） |
| Mypy | `uv run mypy src tests` | 通过（Success: no issues found in 33 source files） |
| Lock sync | `uv sync --locked` | 通过（exit 0） |

### Review 结果

```yaml
# 计划复审（历史）
plan_review:
  blocker: 0
  must_fix: 0
  should_fix: 2
  should_fix_ids:
    - SF-A  # requires-python 精确断言（已纳入 Amendment 003）
    - SF-B  # Git 分支语义澄清（已纳入 Amendment 003）
  review_verdict: PLAN_APPROVED
# 实现 Code Review（本轮）
implementation_review:
  p0: 0
  p1: 0
  p2: 0
  p3: 1
  p3_notes:
    - ".dockerignore 提及 04_评审记录/（本仓库为 04_Git规范/）；非阻塞，Docker 属 DEV-003"
  allow_commit: true
  review_verdict: PASS
  review_report: "白名单齐套、无黑名单越权、§3.5 依赖与 build-system 契约一致、入口与测试符合计划；质量门禁复跑通过"
```

### Git 记录

```yaml
branch: feat/DEV-001-project-skeleton
plan_commit: fd14372
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`reviewed`
