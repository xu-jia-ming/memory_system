# OPS-003 Full Migration, Compose & Blank-Environment Validation

## 1. 任务信息

```yaml
task_id: OPS-003
task_name: Full Migration, Compose & Blank-Environment Validation
status: committed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "93ffefdcbba8fc74a45842b956185bee8d0f2004"
branch: "feat/OPS-003-full-migration-compose-blank-environment-validation"
created_at: "2026-08-14 03:48 UTC"
updated_at: "2026-08-14 04:30 UTC"
spec_sections:
  - "§3.3 Docker Compose 服务拓扑"
  - "§3.12 基础设施初始化"
  - "§3.17 MVP 部署与开发命令"
  - "§3.26 Schema Migration"
  - "§3.32 MVP 开发完成验收标准 #1 / #2 / #9"
  - "§3.32.2（交叉引用 DEV-004：首次成功 / 重复幂等 / checksum 篡改失败）"
prerequisites:
  formal:
    - "OPS-001 — completed（PR #55 MERGED @ 9749bd6）"
    - "OPS-002 — completed（PR #56 MERGED @ fef784d）"
    - "DEV-003 — compose wrapper / embedding / preflight"
    - "DEV-004 — migration runner + 001–004 + init-infra alignment"
    - "DEV-005 — readiness migration 只读检查"
    - "DEV-OPS-008 — compose test-stack runtime compatibility"
    - "CON-001..005 — completed；v0.5.0-consolidation closed"
    - "STM-001..013 — completed"
    - "EXT-001..009 — completed"
    - "RET-001..006 — completed"
  baseline_evidence:
    branch: "main"
    head: "93ffefdcbba8fc74a45842b956185bee8d0f2004"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=93ffefd"
approval_gates:
  planning: "PLAN_APPROVED"
  human_plan_approved: true
  plan_review_round: 2
  plan_review_blocker: 0
  plan_review_must_fix: 0
  plan_review_should_fix: 0
  human_plan_approved_at: "2026-08-14 03:57 UTC"
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator lands this plan on main and creates exact feat/OPS-003-full-migration-compose-blank-environment-validation"
  IMPLEMENTATION_RELEASE: "feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "after verified MERGED PR; exact feat branch cleanup"
dependency_changes_expected: NONE
migration_changes_expected: NONE
production_file_whitelist_default: "see §19（规划态 preliminary；Phase A 只读审计后确认；默认 NONE 或 docs/scripts 最小修复）"
test_file_whitelist_default: "see §20"
```

> **Baseline 注记**：`planning_baseline_main=93ffefdcbba8fc74a45842b956185bee8d0f2004`（`docs(status): complete OPS-002 after PR merge`）。

### 1.1 本轮门禁

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现或测试实现"
  - "进入 Developer / Code Reviewer / Release Operator"
  - "执行 Git 写"
  - "修改权威规格正文"
  - "读取 .env 或提交 Secret"
  - "触碰 DEV-006 / PR #13"
  - "新增 Migration 005+ 或改写已执行 001–004 内容"
stop_if:
  - "审计发现需要改变 API Contract / Schema / 错误码 / 状态机"
  - "空白环境验证需要新依赖或 TEI 模型变更"
  - "修复已执行 Migration 脚本内容（须 HALT；仅允许 runner 逻辑修复）"
blocking_open_issues: []
```

## 2. 任务目标

完成 MVP **全量 Migration Runner + Compose 空白环境** 只读审计与 **最小必要修复**：对照 §3.12 / §3.26 / §3.17 / §3.32 #1/#2/#9，验证 `python -m scripts.migrate` / `init-infra`、Compose Wrapper、`start_embedding.sh`、README 与既有 DEV-004 测试基线；对 **真实违规** 做聚焦修复与可客观断言的 contract/integration tests（**非** E2E-001 / **非** OPS-004 CI 80% 门禁）。

**可验证交付**：

1. 完整审计矩阵（§4–§11）与 Findings 表（§12）。
2. 每项发现分类：`COMPLIANT` / `HARD_BLOCK` / `SAFE_AUTO_REMEDIATION` / `DEFERRED_FOR_MVP`。
3. 仅对 `HARD_BLOCK` / 必要 `SAFE_AUTO_REMEDIATION` 实施白名单内修复。
4. 新增 focused contract/integration tests，覆盖 §3.32 #1/#2 与空白环境 bootstrap 关键路径。
5. 实施后可在 **isolated test stack** 上客观复现：fresh volumes → infra healthy → `init-infra` success → 三应用容器启动 → `/health/ready` 反映 migration 就绪。

## 3. 非目标

- OPS-004 CI 门禁 / `check_env_example.py` CI 接线 / 80% 覆盖率阻塞
- E2E-001 全链路 Session→Consolidation 与失败注入全集
- REL-001 MVP RC 验收清单逐项勾选
- 业务 Domain/Application 语义变更
- 新增或修改已执行 Migration 文件 `001`–`004` 内容（checksum 语义；runner 除外）
- DEV-006 / PR #13
- GPU MVP 阻塞验收（§3.32 #7：GPU 不阻塞 CPU MVP；GPU 路径仅 contract 回归若环境可用）
- 修改 Compression / Extraction / Retrieval / Consolidation 业务路由
- 镜像版本升级（§3.18 规则 2）
- `scripts/preflight/lib_tei_probe.sh` OI-011  characterization bare compose 例外（已锁定）

## 4. 当前代码状态（规划时只读事实）

| 维度 | 事实 |
|---|---|
| Git baseline | `main @ 93ffefdcbba8fc74a45842b956185bee8d0f2004` clean；OPS-002 completed |
| Migration Runner | `scripts/migrate.py` — discover `0*.py`、SHA256 checksum、`infra_schema_migrations`、dependency precheck、Kafka v4 marker |
| Migration scripts | `001_initial_mongodb` … `004_initial_kafka_topics`（4 文件；DEV-004 交付） |
| init-infra | `compose.yaml` → `python -m scripts.migrate`；contract `test_init_infra_command_and_one_shot` PASS |
| 唯一入口 | `test_migrate_paths_contract` 禁止第二套 init 脚本；README 含 `python -m scripts.migrate` |
| Unit 基线 | `tests/unit/test_migrate_runner.py` — checksum/order/skip/conflict/precheck |
| Integration 基线 | `tests/integration/test_migrate_infra.py` — **test stack only**；first run + idempotent + checksum conflict + Mongo/Neo4j/ES/Kafka 断言；**不含 redis**；**不含三应用启动** |
| Compose contract | `tests/contract/test_compose_config_contract.py` — 服务集、grace、init-infra env、test volume 隔离 |
| Wrapper contract | `tests/unit/test_compose_wrapper_contract.py` — bare `docker compose` 扫描 + OI-011 allowlist |
| Readiness INT | `tests/integration/test_api_readiness.py` — **optional/skip-heavy**；未强制 blank bootstrap |
| README | §3.17 标准启动段落存在；经 `compose.sh`；无 “尚未可用” 占位 |
| Preflight | `scripts/preflight/check_linux_host.sh` 存在；**未**纳入自动化 blank-env integration |
| §3.32 #1 | **无**单一 integration 测试覆盖完整 §3.17 序列（infra → migrate → 三应用 → readiness） |
| §3.32 #2 |  largely covered by `test_migrate_infra` + unit tests |
| §3.32 #9 | 部分 covered by compose/migrate contracts；**全量 engineering consistency 审计待 Phase A** |

## 5. 审计方法论

### 5.1 总流程

```text
Phase A — 只读清单化（Developer Step 0，实施前）
  1. 冻结 audit inventory（§6–§10）
  2. 对照 §3.12 / §3.26 / §3.17 / §3.32 逐条 grep + 人工阅读
  3. 复跑既有 DEV-004 migrate + DEV-003 compose 测试（只读 baseline）
  4. 填充 Findings 表（§12）；标注证据（文件:行 / 测试名 / compose config key）
  5. 确认 §19/§20 白名单（仅追加 HARD_BLOCK 路径，不可删 preliminary）

Phase B — 分类决策
  HARD_BLOCK       → 阻塞 §3.32 #1/#2/#9 或 blank bootstrap
  SAFE_AUTO        → 白名单内 docs/scripts/runner 最小修复
  COMPLIANT        → 仅文档化 + 回归
  DEFERRED_FOR_MVP → 记录 rationale；不得静默忽略 HARD_BLOCK

Phase C — 最小修复 + focused tests
  仅改 §19 production whitelist
  仅增 §20 test whitelist
  不得降低既有 migrate/compose contract 断言

Phase D — 回归
  scoped OPS-003 tests + 既有 migrate/compose/readiness 相关 tests
  ruff / mypy scoped PASS
```

### 5.2 Migration Runner 审计规则（§3.12 / §3.26 / §3.32 #2）

| 检查 ID | 规则 | 方法 |
|---|---|---|
| MIG-01 | 唯一入口 `python -m scripts.migrate` | `test_migrate_paths_contract` + grep |
| MIG-02 | `init-infra` 执行同一 runner（§3.26.6） | compose config `command` |
| MIG-03 | 001–004 顺序与 `migration_id` stem | `discover_migrations` + contract |
| MIG-04 | 首次执行 exit 0 + 记录写入 Mongo | `test_migrate_infra` first run |
| MIG-05 | 重复执行幂等 | second `init-infra` + record count |
| MIG-06 | 已执行 checksum 篡改 fail-closed | tamper + non-zero exit（§3.32.2） |
| MIG-07 | ES 版本化 index + alias | `memory_retrieval_v1` / `memory_retrieval_current` curl |
| MIG-08 | Mapping 与规格一致（1024 dim / int8_hnsw / cjk） | integration mapping assert |
| MIG-09 | Mongo / Neo4j 索引与 constraint 名称 | integration mongosh/cypher |
| MIG-10 | Kafka topic 关键配置校验 | 004 migration + integration（若覆盖） |
| MIG-11 | 依赖服务版本 precheck | unit `verify_dependency_versions` |
| MIG-12 | Readiness migration 只读检查（§3.26.5） | `runtime.collect_readiness_checks` + health route |
| MIG-13 | 禁止第二套 init 实现 | grep scripts + contract |
| MIG-14 | Migration 文件只增不改（已执行） | **本任务禁止改 001–004 内容** |

### 5.3 Compose & §3.17 空白环境审计规则

| 检查 ID | 规则 | 方法 |
|---|---|---|
| CMP-01 | §3.3 服务全集存在 | compose config services keys |
| CMP-02 | 应用三容器同镜像不同 command | Dockerfile + compose |
| CMP-03 | 禁止 bare `docker compose`（allowlist 除外） | `test_compose_wrapper_contract` |
| CMP-04 | 全部命令经 `scripts/compose.sh` | README + 03_AI_Prompts 扫描 |
| CMP-05 | test stack 项目名与 volume 隔离 | `memory-system-test` + `*-data-test` |
| CMP-06 | `down -v` 仅显式人工（§3.17） | README 文案；脚本不得默认 `-v` |
| CMP-07 | env 加载顺序 `.env` → versions → lock → embedding.env | `compose.sh` 源码 |
| CMP-08 | `--embedding=none|cpu|gpu|current` 语义 | compose contract + README |
| CMP-09 | `start_embedding.sh auto` 写 `.runtime/embedding.env` | script 源码 + optional INT |
| CMP-10 | infra healthcheck + app depends_on | compose.yaml healthcheck 块 |
| CMP-11 | §3.17 标准序列步骤完整且顺序正确 | README vs spec  diff 表（§7） |
| CMP-12 | fresh blank test volumes bootstrap 可自动化 | **GAP** — 新 integration |
| CMP-13 | migrate 后三应用 `up -d` 成功 | **GAP** — 新 integration |
| CMP-14 | `/health/ready` migrations=ready + status=ready | **GAP** — 强化 readiness INT |
| CMP-15 | stop_grace_period 与 shutdown settings 一致 | compose contract（OPS-001 已覆盖） |

**BLANK-ENV-001（本计划锁定）**：自动化 blank-environment 验收使用 **`--stack=test`** + **固定** `--embedding=cpu` **或** `--embedding=none`（Phase A 二选一锁定；写入 test module docstring 与 Amendment 001）；**禁止**在 INT 中使用 `--embedding=current` 或 `start_embedding.sh auto`（§3.17 人工步骤 5/6 的 `current` 语义由 **C-OPS3-01** README inventory 与 **C-OPS3-03** `start_embedding.sh` 静态审计覆盖，非 I-OPS3-01 运行时路径）；**禁止**使用 dev stack / dev volumes；**禁止**读取真实 `.env` Secret（测试从 `.env.example` 复制 + fixture env）。

**§3.17 Embedding 模式解析（Amendment 001 澄清）**：

| 上下文 | 模式 | 说明 |
|---|---|---|
| 人工 §3.17 序列 | `none` → build → infra → `start_embedding.sh auto` → `--embedding=current` | README 与 spec 对齐；C-OPS3-01 子串 inventory |
| 自动化 INT（I-OPS3-01） | **固定** `cpu` **或** `none` | Phase A 选定；全程同一 flag；不调用 `start_embedding.sh` |
| `start_embedding.sh` / `.runtime/embedding.env` | 人工路径 + 静态审计 | C-OPS3-03 脚本结构；F-013 Phase A 证实 race 才修 |

### 5.4 工程一致性审计规则（§3.32 #9）

| 检查 ID | 规则 | 方法 |
|---|---|---|
| ENG-01 | README 启动命令与 §3.17 一致 | 静态 diff |
| ENG-02 | `.env.example` 存在且无 Secret | 只读结构扫描（**CI 接线 → OPS-004 DEFERRED**） |
| ENG-03 | `versions.env` / `versions.lock.env` 与 compose images 一致 | compose config image fields |
| ENG-04 | YAML defaults 与 Pydantic Settings 一致 | 既有 settings contract 回归 |
| ENG-05 | 无影响主流程 TODO / 占位 | grep `TODO`/`pass`/`NotImplemented` in scripts/README |
| ENG-06 | Migration / compose / README 交叉引用一致 | contract inventory test |
| ENG-07 | `05_测试与验收/mvp_acceptance_checklist.md` A 节与测试映射 | 文档化映射表（§10） |

## 6. Migration 组件清单

| 组件 | 路径 | 规格 | 既有测试 |
|---|---|---|---|
| Runner | `scripts/migrate.py` | §3.26 | unit + integration |
| 001 Mongo | `scripts/migrations/001_initial_mongodb.py` | §3.12 | integration indexes |
| 002 Neo4j | `scripts/migrations/002_initial_neo4j.py` | §3.12 | integration constraints |
| 003 ES | `scripts/migrations/003_elasticsearch_memory_v1.py` | §3.12.5 / alias | integration mapping |
| 004 Kafka | `scripts/migrations/004_initial_kafka_topics.py` | §3.19 | integration（partial） |
| Record store | Mongo `infra_schema_migrations` | §3.12.2 | integration |
| Readiness | `runtime.collect_readiness_checks` → `migrations` | §3.26.5 | DEV-005 contract + weak INT |

## 7. §3.17 标准命令清单（spec vs README）

| Step | §3.17 要求 | README 当前 | 规划态 |
|---|---|---|---|
| 1 | `cp .env.example .env` | ✓ documented | COMPLIANT |
| 2 | `compose.sh --embedding=none pull` | ✓ | COMPLIANT |
| 3 | `compose.sh --embedding=none build` | ✓ | COMPLIANT |
| 4 | `up -d redis mongodb kafka neo4j elasticsearch` | ✓ | COMPLIANT |
| 5 | `start_embedding.sh auto` | ✓ | **AUDIT REQUIRED**（test 路径可 stub `.runtime/embedding.env`） |
| 6 | `compose.sh --embedding=current run --rm init-infra` | ✓ | COMPLIANT |
| 7 | `up -d memory-api + two workers` | ✓ | **AUDIT REQUIRED**（自动化 INT 缺失） |
| 8 | `ps` / `logs` / `down` / `down -v` | ✓ | COMPLIANT |
| 9 | 禁止 bare compose | ✓ README 声明 | COMPLIANT |

## 8. Compose 服务与健康检查清单

| 服务 | 空白环境角色 | Health / depends | 审计焦点 |
|---|---|---|---|
| redis | infra | healthcheck | app readiness 依赖 |
| mongodb | infra + migration record | healthcheck | migrate + readiness |
| kafka | infra + topic init | healthcheck | 004 migration |
| neo4j | infra | healthcheck | 002 migration |
| elasticsearch | infra + ES init | healthcheck | 003 migration |
| embedding-service | §3.17 step 5 | healthcheck | CPU 模式；test stack pull 体积 |
| init-infra | one-shot migrate | restart=no | MIG-02 |
| memory-api | app | depends_on healthy | CMP-13/14 |
| memory-extraction-worker | app | depends_on | 启动不阻塞 readiness |
| memory-consolidation-worker | app | depends_on | 启动不阻塞 readiness |

## 9. 既有测试基线 inventory（只读）

| 区域 | 测试文件 | 覆盖 | OPS-003 关系 |
|---|---|---|---|
| Migrate unit | `tests/unit/test_migrate_runner.py` | checksum/order/conflict | 回归 |
| Migrate contract | `tests/contract/test_migrate_paths_contract.py` | paths/唯一入口 | 回归 + 扩展 inventory |
| Migrate integration | `tests/integration/test_migrate_infra.py` | §3.32 #2 core | 回归；**不含 apps** |
| Compose contract | `tests/contract/test_compose_config_contract.py` | topology/env/grace | 回归 |
| Wrapper unit | `tests/unit/test_compose_wrapper_contract.py` | bare compose ban | 回归 |
| Readiness INT | `tests/integration/test_api_readiness.py` | optional skip | **REPLACE/EXTEND** |
| API readiness contract | `tests/contract/test_api_shell_contract.py` | shape | 回归 |

## 10. MVP Checklist A 节映射（`05_测试与验收/mvp_acceptance_checklist.md`）

| Checklist 项 | OPS-003 覆盖方式 | 备注 |
|---|---|---|
| Linux Preflight 通过 | DEFERRED（人工 / 可选 script invoke） | 非阻塞 automated INT |
| Docker + Compose v2 | module-level `pytest.skip` if unavailable | 见 INT-SKIP-001 |
| CPU Embedding 可启动 | INT bootstrap（cpu mode）或 contract stub | GPU 不阻塞 |
| Migration 首次成功 | 既有 + OPS-003 INT | §3.32 #2 |
| Migration 重复幂等 | 既有 + OPS-003 INT | §3.32 #2 |
| Checksum 篡改失败 | 既有 + OPS-003 INT | §3.32 #2 |
| 三 Entrypoint 启动 | **新 INT** | §3.32 #1 |
| Readiness 反映依赖 | **新 INT** | §3.32 #1 |

## 11. Findings 表（规划态 preliminary — Phase A 须验证）

| ID | 组件 | 当前行为 | 要求 | 状态 | Remediation | Tests | Owning files |
|---|---|---|---|---|---|---|---|
| F-001 | Migration 001–004 + runner | DEV-004 交付 + tests | §3.26 / §3.32 #2 | COMPLIANT | none | 回归 migrate unit/INT | `scripts/migrate.py`, `scripts/migrations/0*.py` |
| F-002 | init-infra = migrate | compose command | §3.26.6 | COMPLIANT | none | compose contract | `compose.yaml` |
| F-003 | 无第二 init 脚本 | single entry | §3.12 | COMPLIANT | none | migrate paths contract | `scripts/` |
| F-004 | test stack 隔离 | `memory-system-test` volumes | §3.28.2 | COMPLIANT | none | compose + migrate INT | `compose.test.yaml` |
| F-005 | §3.17 全序列自动化 | 无单一 INT | §3.32 #1 | **HARD_BLOCK** → **REMEDIATED** | I-OPS3-01 bootstrap INT | I-OPS3-01 | `tests/integration/test_ops003_blank_environment_bootstrap.py` |
| F-006 | migrate 后三应用启动 | 未 INT 验证 | §3.32 #1 | **HARD_BLOCK** → **REMEDIATED** | 同上 | I-OPS3-01 | `compose.yaml` (no change) |
| F-007 | readiness migrations=ready | weak optional INT | §3.26.5 / §3.32 #1 | **HARD_BLOCK** → **REMEDIATED** | bootstrap INT poll + I-OPS3-02 | I-OPS3-01/02 | `runtime.py` (no change) |
| F-008 | README vs §3.17 | 表面一致 | §3.32 #9 | **COMPLIANT** | C-OPS3-01 inventory | C-OPS3-01 | `README.md` (no change) |
| F-009 | `.env.example` CI 校验 | script 存在未 CI | §3.30 P1 | DEFERRED_FOR_MVP | OPS-004 | — | `scripts/check_env_example.py` |
| F-010 | Preflight 自动化 | manual script | Checklist A | DEFERRED_FOR_MVP | 文档映射 | optional | `scripts/preflight/` |
| F-011 | Kafka topic 配置断言 | partial | §3.12.6 | **COMPLIANT** | `test_migrate_infra` covers partitions | I-OPS3-03 deferred | — | `004_initial_kafka_topics.py` (no change) |
| F-012 | bare compose 禁令 | allowlist locked | §3.10.2 | COMPLIANT | none | wrapper contract | — |
| F-013 | start_embedding atomic fallback | script exists | §3.17 / §3.10.5 | **COMPLIANT** | C-OPS3-03 static audit | C-OPS3-03 | `start_embedding.sh` (no change) |
| F-014 | 修改已执行 migration 内容 | 禁止 | §3.26.1 | COMPLIANT（流程） | HALT if needed | — | — |
| F-015 | dev volumes 污染风险 | test isolation fail-closed | safety | COMPLIANT | none | migrate INT guards | — |
| F-016 | embedding none vs current 测试策略 | inconsistent across tests | BLANK-ENV-001 | **SAFE_AUTO** → **REMEDIATED** | locked `none` in I-OPS3-01 | I-OPS3-01 | test fixtures |
| F-017 | check_env_example completeness | not OPS-003 gate | OPS-004 | DEFERRED | none | — | — |

## 12. 实现方案（仅 HARD_BLOCK + 必要 SAFE_AUTO）

### Step 0 — 只读审计确认（Developer 首日）

- 执行 §5 Phase A；更新 §11 Findings 与 §19/§20 白名单。
- 手工对照 §7 逐步执行 **test stack** 等价路径（不读 Secret）；记录 stdout/exit code 证据。
- 若 F-008/F-011/F-013 全部为 COMPLIANT → 收缩 production whitelist 至 tests + docs none。
- 若 F-007 根因为 readiness 逻辑缺陷（非测试缺口）→ 追加 exact `runtime.py` / `health.py` 路径到 §19（Amendment 记录）。

### Step 1 — Migration / Compose inventory contracts

**文件（新建）**：`tests/contract/test_ops003_migration_compose_inventory.py`

- 静态断言 §6 组件存在性；§3.17 README 必含子串清单；MVP checklist A 映射文档化（§10 条目以 test docstring/metadata 固化）。
- 交叉引用：`EXPECTED_MIGRATIONS` 与 `test_migrate_paths_contract` 一致（不重复语义冲突）。
- compose init-infra / app services / test isolation 键名 inventory。

### Step 2 — Blank-environment bootstrap integration（F-005/F-006/F-007）

**文件（新建）**：`tests/integration/test_ops003_blank_environment_bootstrap.py`

**强制约束**：

```text
ONLY: ./scripts/compose.sh --stack=test --embedding=<cpu|none>  # Phase A 锁定；禁止 current
NEVER: --stack=dev
NEVER: read production .env secrets
NEVER: call start_embedding.sh in automated INT
Fixture: copy .env.example → .env if missing; PROXY__HTTP_URL="" (align test_migrate_infra)
Teardown: compose down -v (explicit in fixture finally)
```

**INT-SKIP-001（Amendment 001）**：Docker daemon 或 `docker compose` 不可用 → **module-level** `pytest.skip`（`pytestmark` 或 `conftest` 在收集期检测）；**禁止** per-test 部分 skip。**栈已 up 但** infra health 或 readiness poll 超时 → **hard fail**（`pytest.fail` / `assert False`），**不得** skip。

**流程（I-OPS3-01）**：

1. `_assert_test_isolation()`（复用/共享 migrate INT 逻辑）
2. `down -v` → `up -d --build` infra：`redis mongodb kafka neo4j elasticsearch`（+ `embedding-service` 仅当 BLANK-ENV-001 选 `cpu`）
3. 等待 infra health healthy（≤180s；**栈已 up 则超时 hard fail，非 skip**）
4. `run --rm init-infra` → assert exit 0
5. 第二次 `init-infra` → exit 0 + migration record count unchanged
6. `up -d memory-api memory-extraction-worker memory-consolidation-worker`
7. Poll `http://127.0.0.1:<test_api_port>/health/ready` until HTTP 200 **或** 超时 **hard fail**（非 skip）
8. Assert payload：`status==ready`；`checks.migrations==ready`；必要 checks 不含 URI/secret（OPS-002 回归）

**端口**：从 `compose.sh --stack=test config` 读取 memory-api published port（禁止硬编码假设 dev 8000 若 test override 不同）。

**可选 I-OPS3-03**：Kafka topic describe 断言 partitions/retention 与 §3.19（仅当 Phase A 标记 F-011 GAP）。

### Step 2b — Migrate-before-api failure injection（INJ-OPS3-01）

**文件**：`tests/integration/test_ops003_blank_environment_bootstrap.py`（首选）或 `tests/integration/test_api_readiness.py`（扩展）

1. 复用 test stack fixture；**跳过** `init-infra`
2. `up -d memory-api`（infra healthy 后、migrate **前**）
3. Poll `/health/ready` → assert HTTP **503** 或 `status!=ready` 且 `checks.migrations==not_ready`（与 DEV-005 readiness contract 一致；**不得** 200 ready）
4. Teardown `down -v`

**INJ-OPS3-02**：不新建测试；验收时复跑 `test_migrate_infra.py` checksum tamper 用例（§16 锚点）。

### Step 3 — Readiness / docs / scripts 最小修复

- **F-008**：README §3.17 与 spec 对齐（仅文案/命令顺序/embedding 说明）。
- **F-013**：`start_embedding.sh` 失败清理 + atomic `.runtime/embedding.env`（仅当 Phase A 证实违规）。
- **F-007**：若 readiness 逻辑缺陷 → 最小 fix `runtime.py` migration check（**不得**改 Contract JSON shape）。
- **F-016**：统一 bootstrap fixture embedding mode/documented in test module docstring.

** deprecate / narrow**：`tests/integration/test_api_readiness.py` — 允许 **修改** 为调用 shared helper 或 mark 为 superseded by OPS-003（**不得**删除 migrate-not-ready 语义；可合并到 I-OPS3-02）。

### Step 4 — Focused regression

- 全量复跑 §16 scoped 命令块。
- 不得修改 `test_migrate_infra.py` 断言语义（可抽取 shared isolation helper 到 `tests/integration/_compose_test_helpers.py` **仅当** 两文件重复 >30 行且 Reviewer 要求 — 默认 **不新建 helper**，测试内 inline 复制 migrate INT 模式）。

## 13. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/contract/test_ops003_migration_compose_inventory.py` | 创建 | §3.17/§3.32 inventory contract |
| `tests/integration/test_ops003_blank_environment_bootstrap.py` | 创建 | §3.32 #1 blank bootstrap INT |
| `tests/integration/test_api_readiness.py` | 修改（可选） | 去除 skip-heavy；对齐 OPS-003 bootstrap |
| `README.md` | 修改（若 F-008） | §3.17 / §3.32 #9 对齐 |
| `scripts/start_embedding.sh` | 修改（若 F-013） | embedding.env 原子更新 |
| `scripts/compose.sh` | 修改（若 Phase A GAP） | wrapper 行为修复 |
| `scripts/migrate.py` | 修改（若 runner bug） | **非** 001–004 内容 |
| `src/memory_system/infrastructure/runtime.py` | 修改（若 F-007） | readiness migration check |
| `compose.yaml` / `compose.test.yaml` | 修改（若 depends/health GAP） | Phase A 精确追加 |
| `02_开发管理/progress.md` | 修改 | 实施态字段 |
| `02_开发管理/master_plan.md` | 修改 | OPS-003 状态备注 |

## 14. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用（infra init） | migrate 各 store 独立；失败 exit non-zero |
| 幂等 | **核心** | second init-infra 不增 record；schema exists no-op |
| 并发 | 不适用 | init-infra one-shot；测试串行 |
| 版本冲突 | 不适用 | checksum 篡改 fail-closed |
| 用户隔离 | 不适用 | 无业务数据 |
| 部分失败 | 适用 | init 失败 → apps must not mark ready；INT assert |
| 进程异常恢复 | 部分适用 | migrate 可重跑；测试 teardown `down -v` |

## 15. 测试计划

### Unit Test

| ID | 场景 | 预期 |
|---|---|---|
| U-OPS3-01 | 复跑 `test_migrate_runner.py` 全套 | PASS（无回归） |
| U-OPS3-02 | 复跑 `test_compose_wrapper_contract.py` | bare compose 禁令仍 PASS |

### Contract Test

| ID | 场景 | 预期 |
|---|---|---|
| C-OPS3-01 | README 含 §3.17 逐步命令 + compose.sh 唯一入口 | 子串 inventory PASS |
| C-OPS3-02 | Migration/Compose 组件 inventory | §6 路径存在；init-infra command |
| C-OPS3-03 | `start_embedding.sh` 写入 runtime env 键 | 脚本静态结构（若未 INT） |
| C-OPS3-04 | 复跑 migrate paths + compose config contracts | PASS |

### Integration Test

| ID | 场景 | 预期 |
|---|---|---|
| I-OPS3-01 | test stack blank bootstrap 全序列 | init-infra×2 + 三应用 up + readiness 200 |
| I-OPS3-02 | readiness checks 无敏感 URI | OPS-002 回归 |
| I-OPS3-03 | Kafka topic 配置（若 F-011 GAP） | 与 §3.19 一致 |
| I-OPS3-04 | 复跑 `test_migrate_infra.py` | PASS（无回归） |

### E2E Test

不适用（E2E-001）。

### 失败注入与并发

| ID | 场景 | 实施步骤 | 预期 |
|---|---|---|---|
| INJ-OPS3-01 | migrate 前启动 memory-api | **Step 2b**（`test_ops003_blank_environment_bootstrap.py` 或 `test_api_readiness.py`） | `/health/ready`：`checks.migrations==not_ready` 或 HTTP 503；**不得** ready |
| INJ-OPS3-02 | checksum 篡改 | 复用 `test_migrate_infra.py` tamper 逻辑（**不修改**其断言语义） | `init-infra` non-zero exit |

### Scoped 运行命令（实施验收）

```bash
# OPS-003 contract
uv run pytest tests/contract/test_ops003_migration_compose_inventory.py -q

# OPS-003 integration（需 Docker；daemon 不可用则 module-level skip）
uv run pytest tests/integration/test_ops003_blank_environment_bootstrap.py -q

# Migrate / compose 回归
uv run pytest tests/unit/test_migrate_runner.py \
  tests/contract/test_migrate_paths_contract.py \
  tests/contract/test_compose_config_contract.py \
  tests/unit/test_compose_wrapper_contract.py -q

uv run pytest tests/integration/test_migrate_infra.py -q

# Readiness（若修改）
uv run pytest tests/integration/test_api_readiness.py \
  tests/contract/test_api_shell_contract.py -q

# Lint（scoped production whitelist — Phase A 后精确化）
uv run ruff check scripts/migrate.py scripts/compose.sh scripts/start_embedding.sh README.md

uv run mypy scripts/migrate.py \
  src/memory_system/infrastructure/runtime.py \
  tests/contract/test_ops003_migration_compose_inventory.py \
  tests/integration/test_ops003_blank_environment_bootstrap.py
```

## 16. 验收标准

- [x] §4–§11 审计矩阵与 Findings 表完整，每项有分类与证据
- [x] 所有 `HARD_BLOCK` 已修复或 Reviewer 书面接受（不得静默遗留）
- [x] §3.32 #2：首次 migrate 成功、重复幂等、checksum 篡改失败（既有 + OPS-003 回归）
- [x] §3.32 #1：test stack 空白环境可完成 infra → migrate → 三应用 → `/health/ready` ready（I-OPS3-01）
- [x] **INJ-OPS3-01**：migrate 前启动 memory-api → `checks.migrations==not_ready` 或 HTTP 503（Step 2b）
- [x] **INJ-OPS3-02**：checksum 篡改 → `init-infra` non-zero（复用 `test_migrate_infra` 回归）
- [x] §3.32 #9：README / compose / migration 交叉引用一致（C-OPS3-01/02）；无影响主流程 TODO
- [x] `migration_changes_expected: NONE` 保持；未修改 001–004 已执行脚本内容
- [x] 既有 migrate/compose wrapper contracts 无回归
- [x] scoped `ruff check` / `mypy` PASS
- [x] `progress.md` / `master_plan.md` 实施态同步
- [ ] Review 无 P0/P1

## 17. 风险与阻塞项

| 风险 | 级别 | 缓解 |
|---|---|---|
| Docker daemon 不可用 | 高 | **module-level** `pytest.skip`（INT-SKIP-001）；禁止 fallback dev stack |
| Docker 可用但 infra/readiness 超时 | 高 | **hard fail**（非 skip）；暴露真实 bootstrap 缺口 |
| TEI 镜像拉取失败（cpu 模式） | 中 | Phase A 可改选 `none`；Amendment 记录 |
| INT 运行时间过长 | 中 | module scope fixture；health poll 上限 180s |
| 修复需改 001–004 migration | 高 | **HALT**；runner-only 或新 005（out of scope） |
| readiness 依赖 live embedding | 中 | BLANK-ENV-001；embedding non-blocking per DEV-005 |
| 与 OPS-004 CI 范围重叠 | 低 | F-009/F-017 明确 DEFERRED |
| 触碰 DEV-006/PR#13 | — | 禁止 |
| `.env` Secret 泄露到测试日志 | 中 | 仅 `.env.example` 复制；禁止读取/打印 Secret |

## 18. Git 计划

```yaml
branch: "feat/OPS-003-full-migration-compose-blank-environment-validation"
workflow_mode: NORMAL
release_phases:
  PLAN_LANDING:
    allowed_on: main
    commands:
      - "git add 02_开发管理/tasks/OPS-003-full-migration-compose-blank-environment-validation.md 02_开发管理/progress.md 02_开发管理/master_plan.md"
      - "git commit -m \"docs(plan): add OPS-003 full migration compose blank environment validation plan\""
      - "git pull --ff-only"
      - "git push origin main"
      - "git checkout -b feat/OPS-003-full-migration-compose-blank-environment-validation"
  IMPLEMENTATION_RELEASE:
    allowed_on: feat/OPS-003-full-migration-compose-blank-environment-validation
    commands:
      - "git add <§19 production whitelist exact paths>"
      - "git add <§20 test whitelist exact paths>"
      - "git commit -m \"fix(ops): OPS-003 migration compose blank environment validation remediations\""
      - "git commit -m \"test(ops): add OPS-003 blank environment bootstrap tests\"  # 可与上合并若原子"
      - "git push -u origin feat/OPS-003-full-migration-compose-blank-environment-validation"
      - "gh pr create --title \"fix(ops): OPS-003 full migration compose blank environment validation\" --body \"...\""
  POST_MERGE_CLEANUP:
    allowed_on: main
    precondition: "PR MERGED verified"
    commands:
      - "git fetch && git checkout main && git pull --ff-only"
      - "git commit -m \"docs(status): complete OPS-003 after PR merge\"  # progress/master_plan only"
      - "git push origin main"
      - "git branch -d feat/OPS-003-full-migration-compose-blank-environment-validation"
      - "git push origin --delete feat/OPS-003-full-migration-compose-blank-environment-validation"
expected_commits:
  - "docs(plan): add OPS-003 full migration compose blank environment validation plan"
  - "fix(ops): OPS-003 migration compose blank environment validation remediations"
  - "test(ops): add OPS-003 blank environment bootstrap tests"
out_of_scope_changes:
  - "OPS-004+ / E2E-001 / REL-001"
  - "DEV-006 / PR #13"
  - "scripts/migrations/001..004 内容变更"
  - "业务 Domain/Application 语义"
  - "依赖版本 / 镜像 Tag 升级"
  - "API Contract / Schema / 错误码变更"
  - ".cursor/**"
```

## 19. production_file_whitelist

```yaml
# Phase A 确认后不得超出此列表
production_file_whitelist_default: NONE

production_file_whitelist:
  - "README.md"
  - "scripts/compose.sh"
  - "scripts/start_embedding.sh"
  - "scripts/migrate.py"
  - "src/memory_system/infrastructure/runtime.py"
  - "compose.yaml"
  - "compose.test.yaml"

# 条件追加（Phase A 仅可 append exact paths + Amendment 记录）：
#   - "src/memory_system/api/routes/health.py"  # 仅 F-007 readiness 逻辑
#   - 其他 scripts 路径

# 永久禁止本任务修改：
forbidden_production_paths:
  - "scripts/migrations/001_initial_mongodb.py"
  - "scripts/migrations/002_initial_neo4j.py"
  - "scripts/migrations/003_elasticsearch_memory_v1.py"
  - "scripts/migrations/004_initial_kafka_topics.py"
  - "src/memory_system/domain/**"
  - "src/memory_system/application/**"
```

## 20. test_file_whitelist

```yaml
test_file_whitelist:
  - "tests/contract/test_ops003_migration_compose_inventory.py"
  - "tests/integration/test_ops003_blank_environment_bootstrap.py"
  - "tests/integration/test_api_readiness.py"

# 可抽取 shared helper 仅当 Amendment 批准：
#   - "tests/integration/_compose_test_helpers.py"

# 不得修改既有断言语义（仅可 refactor import）：
protected_regression_tests:
  - "tests/integration/test_migrate_infra.py"
  - "tests/unit/test_migrate_runner.py"
  - "tests/contract/test_migrate_paths_contract.py"
  - "tests/contract/test_compose_config_contract.py"
  - "tests/unit/test_compose_wrapper_contract.py"
```

## 21. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- **日期**：2026-08-14 04:00 UTC
- **触发**：Plan Review Round 1 PLAN_REJECTED（BLOCKER=0 MUST_FIX=1 SHOULD_FIX=4）
- **原计划**：白名单交叉引用 §20/§21；INT health 超时可能 skip；INJ-OPS3-01 未映射实施步骤；embedding `current`/start_embedding 与 INT 边界不清
- **修改内容**：
  1. **MF-1**：全文白名单交叉引用对齐 Git 计划 §18 结构 — production=**§19**、test=**§20**、Amendment=**§21**（§1 YAML、§5.1、§12 Step 0、§18 git add、F-007 追加路径）
  2. **SF-1**：INJ-OPS3-01 映射至 **Step 2b**（migrate 前 up memory-api → not_ready/503）；§16 验收锚点
  3. **SF-2**：BLANK-ENV-001 + §3.17 embedding 模式表 — INT **固定** `cpu|none`；`current`/`start_embedding.sh` 由 C-OPS3-01/03 人工审计覆盖
  4. **SF-3**：INT-SKIP-001 — Docker 不可用 → module-level skip；栈 up 但 health/readiness 超时 → hard fail
  5. **SF-4**：§16 新增 INJ-OPS3-01/02 验收 checklist 项
- **修改原因**：Reviewer 指出 §18–§21 节号错位导致 IMPLEMENTATION_RELEASE git add 引用错误；失败注入与 skip/fail 语义需可客观验收
- **是否影响技术规格**：**否**（澄清测试与审计边界，不改 Contract）
- **审批状态**：Round 2 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0 SHOULD_FIX=0；human PLAN_APPROVED 2026-08-14）

## 22. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-14 03:48 UTC | planning | 创建本 Task Plan；preliminary Findings §11；progress/master_plan 规划态 | 未实施 | 17 preliminary findings；3 HARD_BLOCK；4 DEFERRED；BLANK-ENV-001 locked test stack |
| 2026-08-14 04:00 UTC | planning (Amendment 001) | Round 1 PLAN_REJECTED 修订：§19/§20 白名单对齐；INJ-OPS3-01 Step 2b；INT-SKIP-001；embedding 模式澄清 | 未实施 | MF-1 + SF-1～4 已落实；等待 Round 2 Review |
| 2026-08-14 03:57 UTC | planning (Round 2) | Plan Review Round 2 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0）；human PLAN_APPROVED 2026-08-14；status=approved | 未实施 | PLAN_LANDING pending |
| 2026-08-14 04:05 UTC | PLAN_LANDING | Release Operator；plan_commit `6d007ea` pushed main；feat branch created | N/A | phase=PLAN_LANDING RELEASE_COMPLETED |
| 2026-08-14 04:12 UTC | Step 0 Phase A | 只读审计确认 F-008/F-011/F-013 COMPLIANT；BLANK-ENV-001 锁定 `none`；production whitelist 收缩为 NONE | contract inventory 7 pass | 3 HARD_BLOCK 仅需测试 remediations |
| 2026-08-14 04:15 UTC | Step 1–3 implement | 新建 C-OPS3 inventory + I-OPS3 bootstrap/INJ；对齐 test_api_readiness INT-SKIP-001 | 见 §23 | 无 production 文件变更 |
| 2026-08-14 04:18 UTC | Step 4 regression | scoped §16 全套 PASS | 53 pass / 1 skip (legacy readiness) | ruff/mypy scoped PASS |
| 2026-08-14 04:30 UTC | IMPLEMENTATION_RELEASE | implementation `978ae9c` pushed feat；docs(status): record on feat | scoped 53 pass / 1 skip | phase=IMPLEMENTATION_RELEASE；WAITING_FOR_PR_MERGE |

## 23. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `tests/contract/test_ops003_migration_compose_inventory.py` | 新建 — C-OPS3-01/02/03 inventory |
| `tests/integration/test_ops003_blank_environment_bootstrap.py` | 新建 — I-OPS3-01/02 + INJ-OPS3-01 |
| `tests/integration/test_api_readiness.py` | 修改 — INT-SKIP-001 module skip；superseded 注记 |
| `02_开发管理/progress.md` | 修改 — tested 态同步 |
| `02_开发管理/tasks/OPS-003-full-migration-compose-blank-environment-validation.md` | 修改 — 执行记录 + Findings 确认 |

### 与原计划的差异

Phase A 审计确认 F-008/F-011/F-013 COMPLIANT；production_file_whitelist 实际为 NONE（无 README/scripts/runtime/compose 变更）。BLANK-ENV-001 选定 `--embedding=none`（与 `test_migrate_infra` 对齐，避免 TEI pull）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Contract OPS-003 | `uv run pytest tests/contract/test_ops003_migration_compose_inventory.py -q` | 7 passed |
| Integration OPS-003 | `uv run pytest tests/integration/test_ops003_blank_environment_bootstrap.py -q` | 3 passed (~132s) |
| Migrate/compose regression | `uv run pytest tests/unit/test_migrate_runner.py tests/contract/test_migrate_paths_contract.py tests/contract/test_compose_config_contract.py tests/unit/test_compose_wrapper_contract.py -q` | 31 passed |
| Migrate INT regression | `uv run pytest tests/integration/test_migrate_infra.py -q` | 1 passed |
| Readiness regression | `uv run pytest tests/integration/test_api_readiness.py tests/contract/test_api_shell_contract.py -q` | 12 passed, 1 skipped |
| Ruff | `uv run ruff check scripts/migrate.py tests/contract/test_ops003_migration_compose_inventory.py tests/integration/test_ops003_blank_environment_bootstrap.py tests/integration/test_api_readiness.py` | PASS |
| Mypy | `uv run mypy scripts/migrate.py src/memory_system/infrastructure/runtime.py tests/contract/test_ops003_migration_compose_inventory.py tests/integration/test_ops003_blank_environment_bootstrap.py` | PASS |

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
branch: feat/OPS-003-full-migration-compose-blank-environment-validation
plan_commit: 6d007ea00dfd565b5e3ac0f193de4b18867ba336
implementation_commit: 978ae9ccaf80a87c772a6691a7f1b66db2b3c846
implementation_commit_message: "test(ops): add OPS-003 blank environment bootstrap tests"
```

### 最终状态

`committed`
