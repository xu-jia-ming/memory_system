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
| DEV-001 | 项目骨架、依赖与质量工具 | §3.4, §3.5, §3.2, §3.28 | 无 | reviewed |
| DEV-002 | 配置系统与 `.env.example` | §3.8, §3.30 P1 | DEV-001 | planned |
| DEV-003 | Docker Compose、Embedding 服务、Preflight | §3.3, §3.10–3.18 | DEV-002 | planned |
| DEV-004 | Migration Runner；含 ES Mapping + Alias | §3.12, §3.26, §2.2.4 | DEV-003 | planned |
| DEV-005 | 通用 API 壳、鉴权、Request ID、日志与指标 | §3.7, §3.21, §3.23, §3.27 | DEV-002 | planned |
| DEV-006 | TEI Embedding Client + Token Budget（共享） | §3.2, §3.10, §2.2.6 | DEV-003 | planned |

#### DEV-001 项目骨架、依赖与质量工具

- **目标**：**只创建 DEV-001 白名单内的 §3.4 目录与文件子集**（不宣称完成全部 §3.4 树）；`pyproject.toml` 依赖约束与 §3.5 完全一致，并含固定 `[build-system]`（`requires = ["uv_build>=0.11.32,<0.13"]`，`build-backend = "uv_build"`）；生成 `uv.lock`；ruff/mypy/pytest 可运行；三 Entrypoint **可安全 import**；通过子进程执行三个 `python -m memory_system.entrypoints.*`，未就绪时明确错误并以非零退出。
- **非目标**：完整 §3.4 树；`configs/`；Compose/Dockerfile/`versions.*`；Migration/Preflight/补发等具名脚本；`api/dependencies.py`、`middleware.py`、`error_handlers.py` 与业务路由；将 Build Backend 替换为非 `uv_build`；把 `uv_build` 写入运行时/quality/test 依赖组；伪造成功响应。
- **变更文件（预期）**：仅 Task Plan 白名单枚举路径（根元数据、包内 `__init__.py` 与三入口、`api/__init__.py` + `api/routes/__init__.py`、`scripts/__init__.py` + `scripts/migrations/__init__.py` + `scripts/preflight/.gitkeep`、`tests/unit/test_entrypoints_import.py`、`tests/unit/test_dependency_contract.py` 及测试目录占位）。禁止 `src/memory_system/**` / `scripts/**` 通配描述。
- **测试**：Unit import；三个 `-m` 子进程未就绪非零退出；`tomllib` 依赖契约（`requires-python == ">=3.12,<3.13"`；§3.5 三组依赖逐项一致 + **单独**断言 `[build-system]`，且 `uv_build` 不混入运行时依赖集合 + 无 Poetry/Pipenv/Conda 文件）；Contract/Integration/E2E 不适用真实基础设施。
- **验收**：白名单齐套且黑名单不存在；依赖与 build-system / requires-python 契约测试通过；`uv sync --locked`；ruff/mypy/pytest 通过；分阶段更新 progress/Task Plan 状态。
- **风险**：PRE-ENV-001/002；禁止 import 阶段抛 `SystemExit`/`NotImplementedError`；禁止偏离已决议的 `uv_build`。
- **计划文件**：`02_开发管理/tasks/DEV-001-project-skeleton.md`
- **状态备注**：独立复审 `PLAN_APPROVED`；实现 Code Review `PASS`（P0/P1=0），状态 `reviewed`；等待人工 `build(bootstrap)` Commit（不得自行 Push/Merge/Rebase）。

#### DEV-002 配置系统与 `.env.example`

- **目标**：Pydantic Settings + YAML loader（env > env YAML > base.yaml > defaults）；**创建** `configs/` 与 `base.yaml` / `development.yaml` / `test.yaml`（DEV-001 不创建 configs）；完整 `.env.example`；`scripts/check_env_example.py`。
- **非目标**：Compose、真实客户端连接、业务阈值之外的选型变更。
- **变更文件**：`src/memory_system/settings/`（实现）、`configs/{base,development,test}.yaml`、`.env.example`、`scripts/check_env_example.py`。
- **测试**：Unit（优先级、非法 YAML、跨字段校验）；Contract（示例键完整且无 Secret）。
- **验收**：启动非法配置失败；CI/脚本可校验 `.env.example`。
- **风险**：Secret 写入 YAML/示例。

#### DEV-003 Docker Compose、Embedding、Preflight

- **目标**：`compose*.yaml`、`versions.env`/`versions.lock.env`、`compose.sh`、`start_embedding.sh`、`lock_tei_images.sh`、Preflight、Dockerfile；CPU/GPU Embedding 互斥 Override。
- **非目标**：业务 Migration 逻辑细节（属 DEV-004）；应用业务 API。
- **变更文件**：`Dockerfile`、`compose.yaml`、`compose.override.yaml`、`compose.embedding.{cpu,gpu}.yaml`、`compose.test.yaml`、`versions.env`、`versions.lock.env`、`scripts/compose.sh`、`scripts/start_embedding.sh`、`scripts/lock_tei_images.sh`、`scripts/preflight/check_linux_host.sh`。
- **测试**：Integration（compose config 校验、preflight 脚本在本机条件允许时）；禁止裸 `docker compose`。
- **验收**：经 wrapper 可构建/启动基础设施与 embedding-service（按规格 §3.17）。
- **风险**：版本硬编码漂移；CPU/GPU 同时启用。

#### DEV-004 Migration Runner 与基础设施初始化

- **目标**：`scripts/migrate.py` + `001`–`004`；Mongo `infra_schema_migrations`；**唯一**创建 ES 版本化 Index、Mapping、Alias；Neo4j/Kafka/Mongo 初始化幂等。
- **非目标**：业务 Document 写入；Retrieval/Extraction 逻辑。
- **变更文件**：`scripts/migrate.py`、`scripts/migrations/001_*.py`–`004_*.py`、相关测试。
- **测试**：Integration（首次成功、重复幂等、checksum 篡改失败）；ES alias/mapping 断言。
- **验收**：`python -m scripts.migrate` 符合 §3.26/§3.32。
- **风险**：修改已执行 Migration；与规格 Mapping 不一致。

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

Master Plan 如需再变，必须新增变更编号，禁止静默修改任务目标、依赖或验收标准。
