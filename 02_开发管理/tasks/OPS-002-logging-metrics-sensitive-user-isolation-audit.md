# OPS-002 Logging, Metrics, Sensitive Information & User Isolation Audit

## 1. 任务信息

```yaml
task_id: OPS-002
task_name: Logging, Metrics, Sensitive Information & User Isolation Audit
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "c7011aaac123915976389da8d8f18191269a0313"
branch: "feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
created_at: "2026-08-14 02:17 UTC"
updated_at: "2026-08-14 03:05 UTC"
spec_sections:
  - "§3.21 Memory API 鉴权与接口暴露"
  - "§3.23 Request ID（worker task_run_id 交叉引用）"
  - "§3.27 日志、指标与敏感信息保护"
  - "§3.32 MVP 开发完成验收标准 #8（日志/指标/用户隔离）"
prerequisites:
  formal:
    - "OPS-001 — completed（PR #55 MERGED @ 9749bd6）"
    - "CON-001..005 — completed；v0.5.0-consolidation closed"
    - "STM-001..013 — completed"
    - "EXT-001..009 — completed"
    - "RET-001..006 — completed"
    - "DEV-005 — API shell、structlog、Prometheus 注册、§3.21 鉴权基线"
    - "CON-004 — consolidation_run_telemetry + consolidation_runs_total 接线"
  baseline_evidence:
    branch: "main"
    head: "c7011aaac123915976389da8d8f18191269a0313"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=c7011aaac123915976389da8d8f18191269a0313"
approval_gates:
  planning: "PLAN_APPROVED"
  human_plan_approved: true
  plan_review_round: 2
  plan_review_blocker: 0
  plan_review_must_fix: 0
  plan_review_should_fix: 0
  human_plan_approved_at: "2026-08-14 02:51 UTC"
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator lands this plan on main and creates exact feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
  IMPLEMENTATION_RELEASE: "feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "after verified MERGED PR; exact feat branch cleanup"
dependency_changes_expected: NONE
migration_changes_expected: NONE
production_file_whitelist_default: "see §20（规划态 preliminary；实施前须完成只读审计矩阵并确认）"
test_file_whitelist_default: "see §21"
```

> **Baseline 注记**：`planning_baseline_main=c7011aaac123915976389da8d8f18191269a0313`（`docs(status): complete OPS-001 after PR merge`）。

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
stop_if:
  - "审计发现需要改变 API Contract / Schema / 错误码 / 状态机"
  - "审计发现需要 OpenTelemetry 或新依赖"
  - "用户隔离缺口需要新增 HTTP 路由或改变鉴权分级"
blocking_open_issues: []
```

## 2. 任务目标

完成 MVP 全仓 **只读审计** 与 **最小必要修复**：对照 §3.27（日志、指标、敏感信息）与 §3.21（鉴权与用户隔离），验证三 Entrypoint、API 壳、Domain/Application 服务、Infrastructure 仓储与既有测试基线；对 **真实违规** 做聚焦修复与可客观断言的测试。

**可验证交付**：

1. 完整审计矩阵（§4–§11）与 Findings 表（§12）。
2. 每项发现分类：`COMPLIANT` / `HARD_BLOCK` / `SAFE_AUTO_REMEDIATION` / `DEFERRED_FOR_MVP`。
3. 仅对 `HARD_BLOCK` / 必要 `SAFE_AUTO_REMEDIATION` 实施白名单内修复。
4. 新增 focused contract/unit tests（非 E2E-001 / 非 OPS-004 CI 全量）。

## 3. 非目标

- OPS-003 空白环境 Migration/Compose 认证
- OPS-004 CI / 80% 覆盖率门禁
- E2E-001 全链路失败注入
- REL-001 验收清单
- OpenTelemetry Trace（§3.27 明确 MVP 后置）
- 修改 Compression / Extraction / Retrieval / Consolidation **业务语义**
- 新增 API Gateway / JWT / 租户级授权（§3.21 #5 P2）
- DEV-006 / PR #13
- 通用日志框架替换或 structlog 处理器架构重写
- 将 `kafka_consumer_lag` 扩展为多 consumer 集群级监控（超出 MVP 单 worker）

## 4. 当前代码状态（规划时只读事实）

| 维度 | 事实 |
|---|---|
| Git baseline | `main @ c7011aaac123915976389da8d8f18191269a0313` clean；OPS-001 completed |
| structlog 配置 | `observability/logging.py` — JSON Renderer；`_add_service_context` 注入 `service_name`（**硬编码** `memory-api`）、`environment`、`request_id` |
| Worker logging | `extraction_worker` / `consolidation_worker` 均调用 `configure_logging(settings)` → worker 日志 `service_name=memory-api` |
| stdlib logging 混用 | `compression_llm_service.py`、`extraction_task_consumer_service.py`、`consolidation_run_telemetry.py`、`deepseek_client.py`（可选 logger 参数）、`siliconflow_client.py` 等仍用 `logging.getLogger` |
| request context | `request_context.py` 定义 `user_id_var` / `session_id_var` 但 **无 setter 被路由/中间件调用**；`clear_request_context` 仅清 request_id |
| task_run_id | §3.23 #3 要求 Worker 生成 `task_run_id`；**当前无** context 字段或绑定 |
| 敏感日志基线 | DEV-005 `test_auth_failure_logs_do_not_leak_api_key`；`deepseek_client` error redaction test；EXT/graph/reconciliation/entity_alignment privacy unit tests |
| Prometheus 注册 | `observability/metrics.py` 注册 §3.27 全部指标名 |
| Prometheus 接线 | **已接线**：`http_requests_total`/`http_request_duration_seconds`（middleware）；`consolidation_runs_total`（`consolidation_run_service`） |
| Prometheus 未接线 | `compression_total`、`extraction_tasks_total`、`extraction_task_duration_seconds`、`retrieval_requests_total`、`retrieval_duration_seconds`、`kafka_consumer_lag` — **零** `.labels().inc()`/`.observe()`/`.set()` 生产调用（仅注册） |
| §3.21 鉴权 | `api_key.py` constant-time digest compare；`dependencies.py` 401/403 分级；`internal_metrics.py` Admin Key；health 免 Key |
| Readiness | `health.py` 返回 `checks` 名称 + `ready/not_ready`；无 URI/堆栈 |
| 用户隔离测试 | 多模块 integration/unit 已有 cross-user 用例（Redis context_read、ES RET-001/002、Neo4j EXT-004/005/006/008、RET-003 等） |
| Admin extraction | `extraction_admin_service.get_status` 使用 `find_extraction_task_by_user_and_archive_id`；cross-user → 404 |

## 5. 审计方法论

### 5.1 总流程

```text
Phase A — 只读清单化（Developer Step 0，实施前）
  1. 冻结 audit inventory（§6–§9）
  2. 逐文件 grep + 人工阅读 logging/metrics/auth 调用点
  3. 对照 §3.27 禁止列表与 §3.21 规则 1–8
  4. 填充 Findings 表（§12）；标注证据（文件:行 / 测试名）

Phase B — 分类决策
  HARD_BLOCK       → 必须修复（阻塞 §3.32 #8 / MVP RC）
  SAFE_AUTO        → 白名单内最小修复
  COMPLIANT        → 仅文档化 + 回归测试
  DEFERRED_FOR_MVP → 记录 rationale；不得静默忽略 HARD_BLOCK

Phase C — 最小修复 + focused tests
  仅改 §20 production whitelist
  仅增 §21 test whitelist
  不得降低既有 privacy/isolation 测试断言

Phase D — 回归
  scoped OPS-002 tests + 既有 DEV-005 contract + 相关 privacy/isolation tests
  ruff / mypy scoped PASS
```

### 5.2 日志审计规则（§3.27）

> **structlog 迁移策略（SF-4）**：`configure_logging` 已通过 structlog 处理器链输出 JSON；各模块改用 `structlog.get_logger(__name__)` 而非 stdlib `logging.getLogger`，是为了让业务日志字段走同一 JSON Renderer 与 contextvars 合并路径；stdlib bridge 无法保证 worker/telemetry 路径的字段一致性与 §3.27 最小字段集，故 F-006 对 identified HARD_BLOCK 调用点做逐文件迁移，而非全局 stdlib→structlog 桥接。

| 检查 ID | 规则 | 方法 |
|---|---|---|
| LOG-01 | Python logging + structlog + JSON Renderer | 检查 `configure_logging` 与 worker/API 一致性 |
| LOG-02 | 最小字段：timestamp/level/service_name/environment/request_id 或 task_run_id | 解析 JSON 日志样本（contract test） |
| LOG-03 | 允许字段：user_id/session_id/archive_id/task_id/error_code/duration_ms | 检查 structlog 绑定与 log 调用 kwargs |
| LOG-04 | 禁止：完整用户消息/compressed_context/Memory Content | grep `content`/`prompt`/`response` 入 log；读 LLM/compression/extraction 服务 |
| LOG-05 | 禁止：完整 LLM Prompt/Response | 读 `deepseek_client`、`*_llm_service` log 路径 |
| LOG-06 | 禁止：API Key/Authorization/DB 凭证 | 读 auth/error/validation 路径；复跑 DEV-005 contract |
| LOG-07 | 禁止：原始 Token/私钥/验证码 | 读 redaction 测试 + error string 化路径 |
| LOG-08 | Worker 使用 `task_run_id`（§3.23 #3） | 读 extraction/consolidation worker 与 consumer 日志 |
| LOG-09 | `service_name` 按进程区分 | api / extraction-worker / consolidation-worker |
| LOG-10 | `logger.exception` / `exc_info` 不泄露禁止内容 | 审计 internal_error 与 worker unhandled 路径 |

### 5.3 指标审计规则（§3.27）

| 检查 ID | 指标 | 预期接线点 | 方法 |
|---|---|---|---|
| MET-01 | `http_requests_total` | `AccessLogMetricsMiddleware` | contract 已有 |
| MET-02 | `http_request_duration_seconds` | 同上 | contract 已有 |
| MET-03 | `compression_total{status}` | `compression_coordinator_service` 终态 | grep + unit |
| MET-04 | `extraction_tasks_total{status}` | extraction terminal（completed/failed/…） | grep consumer/pipeline |
| MET-05 | `extraction_task_duration_seconds` | extraction 任务 wall-clock | 同上 |
| MET-06 | `retrieval_requests_total{mode,status}` | `retrieval_api_service` | grep |
| MET-07 | `retrieval_duration_seconds{mode}` | 同上 | grep |
| MET-08 | `kafka_consumer_lag` | extraction consumer（**可获取时**） | 评估 aiokafka lag API；不可则 DEFERRED + 文档 |
| MET-09 | `consolidation_runs_total{status}` | `consolidation_run_service` | CON-004 已有；回归 |
| MET-10 | Admin Key scrape | `/internal/metrics` | DEV-005 contract 已有 |

**DEV-005 边界**：注册允许计数为 0；OPS-002 验收要求 **业务路径已存在处必须 increment/observe**（非仅注册）。

### 5.4 敏感信息审计规则

| 检查 ID | 范围 | 方法 |
|---|---|---|
| SEN-01 | HTTP 错误 Body | 不得含 Key/堆栈/连接串；`error_handlers.py` |
| SEN-02 | Readiness | 不得含 URI/异常详情；`runtime.collect_readiness_checks` |
| SEN-03 | Validation errors | `_sanitize_validation_errors` 仅 redact `secret` key — 审计是否足够 |
| SEN-04 | LLM/Embedding 错误对象 | `__str__`/`repr` redaction tests |
| SEN-05 | Extraction redaction | EXT-002 RED-* tests 回归；日志不得含 match 值（Appendix A.3） |
| SEN-06 | Prometheus labels | 不得含 user_id 作为高基数或敏感 payload |

### 5.5 用户隔离审计规则（§3.21）

| 检查 ID | 规则 | 审计范围 |
|---|---|---|
| ISO-01 | Constant-time Key compare | `api_key.verify_api_key` |
| ISO-02 | 缺失/错误 Key 统一 401 | `dependencies.py` |
| ISO-03 | Admin 路由仅 Admin Key | `require_admin_api_key` + extraction admin routes |
| ISO-04 | Metrics Admin Key + 内部网络（部署层） | HTTP 401/403；Compose 网络不在本任务改 |
| ISO-05 | 业务 HTTP 必须以 `user_id` 过滤 | 路由 → 服务 → 仓储链路表（§7） |
| ISO-06 | Admin extraction 路径 `user_id` 与资源归属一致 | `extraction_admin_service` + repo |
| ISO-07 | 信任 Agent 不得省略隔离 | Redis Lua `expected_user_id`；Neo4j/ES/Mongo 查询 |
| ISO-08 | CLI 不暴露为 HTTP | 无 `/migrate`/`republish` HTTP route |

**隔离审计方法**：

1. 构建 HTTP 端点清单（§7.1）→ 追踪 `user_id` 来源（body/path）→ 仓储过滤断言。
2. 构建 Worker/内部路径清单（§7.2）→ Kafka event `user_id` 与 repo key 一致性。
3. 对照既有 cross-user integration tests（§7.3）→ 标记 **COVERED** / **GAP**。
4. GAP 仅通过 **最小仓储/服务断言 + 测试** 修复；不改变 API Contract。

## 6. 进程与服务清单（日志 + 指标）

| 进程 | service_name（§3.27 预期） | 当前 configure_logging | request_id / task_run_id | 指标暴露 |
|---|---|---|---|---|
| memory-api | `memory-api` | ✓ 名称正确 | `request_id` via middleware | `/internal/metrics` scrape |
| memory-extraction-worker | `memory-extraction-worker`（预期） | ✗ 仍为 `memory-api` | 无 `task_run_id` | 无 HTTP metrics（进程内 registry 未 scrape — **预期**；指标计数须在生产路径 increment，由 api scrape 仅见 api 进程 — **审计确认**） |
| memory-consolidation-worker | `memory-consolidation-worker`（预期） | ✗ 仍为 `memory-api` | 无 `task_run_id` | 同左 |

> **MET-AUDIT-001（解释 A — 本计划锁定；SF-1）**：Prometheus metrics 注册在 **进程内全局 REGISTRY**。Worker 内 increment 的 counter **不会**出现在 memory-api `/internal/metrics`，除非共享 pushgateway（MVP 无）。
>
> - **解释 A（本任务验收口径）**：
>   - **api scrape（`/internal/metrics`）**：断言 **memory-api 进程**内已注册且已接线的 series 非零或存在（`http_*`、`compression_total`、`retrieval_*`、`consolidation_runs_total` 等 api 路径）；**不要求** extraction/consolidation worker series 出现在 api scrape。
>   - **worker 进程**：extraction/consolidation 指标在 **各自 worker REGISTRY** 接线；验收以 **unit test 非零样本**（`U-OPS2-11` 等）为准，而非 api scrape。
>   - **C-OPS2-02**：同时断言 api scrape 边界（worker-only series 不在 api registry）+ worker unit 非零样本；二者分工明确，不混为一谈。
> - **解释 B**：若 Reviewer 要求 api scrape 可见全系统指标 → **HALT**（需 Contract 变更/Pushgateway，超出本任务）。
>
> 默认按 **解释 A** 继续；Findings 表 F-018 / C-OPS2-02 须明确记录。

## 7. HTTP 与用户隔离链路清单

### 7.1 HTTP 端点（§3.21 业务面）

| 路由 | 文件 | Key | user_id 来源 | 隔离 enforcement |
|---|---|---|---|---|
| `POST /api/v1/memory/session` | `memory_session.py` | Memory/Admin | body | WM meta key(`user_id`,`session_id`) |
| `POST .../working/message` | `memory_message.py` | Memory/Admin | body | Redis Lua + compression coord |
| `POST .../session/{user_id}/{session_id}/close` | `memory_session.py` | Memory/Admin | path | session_close Lua |
| `POST .../memory/retrieval` | `memory_retrieval.py` | Memory/Admin | body | ES/Neo4j query filters |
| `GET/POST .../extraction/{user_id}/{archive_id}*` | `memory_extraction_admin.py` | **Admin only** | path | `find_extraction_task_by_user_and_archive_id` |
| `GET /health/live` | `health.py` | 无 | N/A | N/A |
| `GET /health/ready` | `health.py` | 无 | N/A | N/A |
| `GET /internal/metrics` | `internal_metrics.py` | Admin | N/A | N/A |

> Working Context **无独立 HTTP 路由**（经 compression coordinator 内部 `context_read_service`）；隔离审计归入 Redis Lua（§7.2）。

### 7.2 Worker / 内部 durable 路径

| 路径 | user_id 来源 | 隔离点 |
|---|---|---|
| Kafka archive_created consumer | event.user_id | consumer key match；Mongo task；pipeline |
| Extraction pipeline stages | task.user_id | Neo4j/ES writes scoped |
| Consolidation run | per-user enumeration | Neo4j read/write repos |
| Context read (internal) | caller input | Redis `expected_user_id` |

### 7.3 既有 cross-user 测试基线（只读 inventory）

| 区域 | 测试文件 | 场景 |
|---|---|---|
| Redis context read | `tests/integration/test_context_read_redis.py` | wrong user_id |
| Extraction admin HTTP | `tests/integration/test_ext008_extraction_admin_http.py` | cross-user GET 404 |
| ES BM25/Vector | `tests/integration/test_ret001_bm25_retrieval.py`, `test_ret002_*` | cross-user |
| Neo4j graph/recall/alignment | `tests/integration/test_ext004_*`, `ext005_*`, `ext006_*`, `ret003_*` | cross-user |
| Kafka consumer | `tests/integration/test_extraction_consumer_kafka.py` | wrong user key |
| Unit guards | `test_authoritative_recall_service`, `test_graph_write_service` | wrong user / privacy logs |

**规划态 GAP 候选**（待 Phase A 确认）：无独立 HTTP context-read 路由 → N/A；Mongo `find_extraction_task_by_archive_id` 内部 worker 用法 → COMPLIANT if admin HTTP never uses it alone。

## 8. 日志字段矩阵（§3.27）

| 字段 | API 请求 | Extraction worker | Consolidation worker | 规划态 |
|---|---|---|---|---|
| timestamp | ✓ structlog | ✓ | ✓ | COMPLIANT |
| level | ✓ | ✓ | ✓ | COMPLIANT |
| service_name | ✓ `memory-api` | ✗ `memory-api` | ✗ `memory-api` | **HARD_BLOCK** (LOG-09) |
| environment | ✓ | ✓ | ✓ | COMPLIANT |
| request_id | ✓ middleware | ✗ | ✗ | PARTIAL（worker 应 task_run_id） |
| task_run_id | N/A | ✗ 缺失 | ✗ 缺失 | **HARD_BLOCK** (LOG-08) |
| user_id | 部分 route kwargs 未 bind | 部分 stdlib logs | batch logs | **SAFE_AUTO** |
| session_id | 未 bind | 部分 | rare | SAFE_AUTO |
| archive_id / task_id | N/A | stdlib format logs | N/A | SAFE_AUTO（改 structlog + 字段） |
| error_code | 部分 structlog | 部分 | consolidation_run | COMPLIANT/PARTIAL |
| duration_ms | middleware | 部分 | run_duration_ms | COMPLIANT/PARTIAL |
| JSON structlog | API 路径 | 混用 stdlib（见 F-006 inventory） | telemetry/worker/consumer 用 stdlib | **HARD_BLOCK**（F-006 identified 调用点须迁移；其余见 DEFERRED inventory） |

## 9. 指标接线矩阵（§3.27）

| 指标 | 规格 | 当前 | 建议接线点 | 规划态 |
|---|---|---|---|---|
| `http_requests_total` | MVP | middleware ✓ | — | COMPLIANT |
| `http_request_duration_seconds` | MVP | middleware ✓ | — | COMPLIANT |
| `compression_total{status}` | MVP | 未 increment | `compression_coordinator_service` 每次协调终态 `CompressionStatus` | **HARD_BLOCK** |
| `extraction_tasks_total{status}` | MVP | 未 increment | terminal persist success/fail in consumer/pipeline | **HARD_BLOCK** |
| `extraction_task_duration_seconds` | MVP | 未 observe | task processing wall-clock | **HARD_BLOCK** |
| `retrieval_requests_total{mode,status}` | MVP | 未 increment | `retrieval_api_service` success/degraded/error | **HARD_BLOCK** |
| `retrieval_duration_seconds{mode}` | MVP | 未 observe | 同上 | **HARD_BLOCK** |
| `kafka_consumer_lag` | 可获取时 | 未 set | consumer loop lag probe | **DEFERRED** 或 SAFE_AUTO |
| `consolidation_runs_total{status}` | MVP | ✓ | — | COMPLIANT |

## 10. 敏感信息矩阵（§3.27 禁止列表）

| 禁止项 | 审计焦点 | 规划态 |
|---|---|---|
| 完整用户消息 / compressed_context / Memory Content | message_write/compression/extraction/retrieval logs | COMPLIANT（spot check + 既有 privacy tests） |
| 完整 LLM Prompt/Response | `compression_llm_service`, `extraction_llm_service`, `deepseek_client` | COMPLIANT（无 content in logs） |
| API Key / Authorization | auth middleware, dependencies, metrics | COMPLIANT（contract test） |
| DB 密码 / 连接串 | readiness, error logs, validation | COMPLIANT（readiness 无 URI） |
| 原始 Token / 私钥 / 验证码 | redaction + error repr | COMPLIANT（EXT-002 RED + client tests） |
| `logger.exception` 堆栈 | `error_handlers.handle_unexpected_error`, `log_unhandled_run_error` | **SAFE_AUTO** — 确保堆栈不进入 HTTP；日志允许 stack 但不得含 message content（审计确认） |

## 11. §3.21 鉴权与用户隔离矩阵

| 规则 # | 要求 | 规划态 | 证据 |
|---|---|---|---|
| 1 | Constant-time compare | COMPLIANT | `secrets.compare_digest` on SHA256 digest |
| 2 | 401 不区分缺失/错误 | COMPLIANT | dependencies |
| 3 | Key 不入日志 | COMPLIANT | `test_auth_failure_logs_do_not_leak_api_key` |
| 4 | Key 不携带终端用户身份 | COMPLIANT（设计） | user_id 由 Agent 传入 |
| 5 | 不直接暴露浏览器 | 部署层 | 不在代码任务改 |
| 6 | 业务资源强制 user_id 过滤 | **AUDIT REQUIRED** | §7 + 既有 INT tests |
| 7 | Admin Key 仅管理 HTTP | COMPLIANT | extraction admin + metrics |
| 8 | CLI 不包装 HTTP | COMPLIANT | 无 migrate/republish routes |

## 12. Findings 表（规划态 preliminary — Phase A 须验证）

| ID | 组件 | 当前行为 | 要求 | 状态 | Remediation | Tests | Owning files |
|---|---|---|---|---|---|---|---|
| F-001 | API structlog JSON | middleware/error_handlers 用 structlog | §3.27 JSON | COMPLIANT | none | C-OPS2-01 | `api/middleware.py` |
| F-002 | API Key 日志泄露 | auth 失败不 log key | §3.21 #3 | COMPLIANT | none | 既有 DEV-005 | `dependencies.py` |
| F-003 | Readiness 敏感信息 | 仅 check 名 | §3.21 | COMPLIANT | none | DEV-005 | `health.py`, `runtime.py` |
| F-004 | worker service_name | 一律 `memory-api` | 按进程名 | **HARD_BLOCK** | `configure_logging(settings, service_name=...)` | U-OPS2-01 | `observability/logging.py`, entrypoints |
| F-005 | worker task_run_id | 未生成/绑定 | §3.23 #3 | **HARD_BLOCK** | worker 启动/每任务 UUID；bind contextvars | U-OPS2-02 | entrypoints, `request_context.py` |
| F-006 | stdlib logging 混用 | 7 文件 identified HARD_BLOCK 调用点（§13 Step 2 inventory） | structlog JSON（identified 路径） | **HARD_BLOCK** | 逐文件 `structlog.get_logger`；禁止 log content | U-OPS2-03..05, U-OPS2-03b | §13 Step 2 inventory + §20 |
| F-006-D | stdlib logging 余量 | `session_close_service` 等 4 文件（§13 Step 2 DEFERRED） | structlog JSON | **DEFERRED_FOR_MVP** | 无生产日志路径阻塞 §3.32 #8；Phase A grep 无新增 HARD_BLOCK 则保持 DEFERRED | 回归既有 privacy tests | 见 §13 Step 2 DEFERRED |
| F-007 | user_id context bind | contextvars 未设置 | §3.27 允许字段 | SAFE_AUTO（**可选**） | route/service 层 bind（仅标识符）；未实现不阻塞验收 | U-OPS2-06（**optional**） | `request_context.py`；`api/middleware.py` **仅当实现 F-007** |
| F-008 | compression_total | 未 increment | §3.27 MVP | **HARD_BLOCK** | coordinator 终态 inc | U-OPS2-10 | `compression_coordinator_service.py` |
| F-009 | extraction_tasks_total | 未 increment | §3.27 MVP | **HARD_BLOCK** | terminal status inc | U-OPS2-11 | consumer/pipeline |
| F-010 | extraction_task_duration_seconds | 未 observe | §3.27 MVP | **HARD_BLOCK** | wall-clock observe | U-OPS2-11 | 同上 |
| F-011 | retrieval_requests_total | 未 increment | §3.27 MVP | **HARD_BLOCK** | mode+status inc | U-OPS2-12 | `retrieval_api_service.py` |
| F-012 | retrieval_duration_seconds | 未 observe | §3.27 MVP | **HARD_BLOCK** | mode observe | U-OPS2-12 | 同上 |
| F-013 | kafka_consumer_lag | 未 set | 可获取时 | DEFERRED_FOR_MVP | 若 aiokafka 无稳定 lag API则文档化 | optional U-OPS2-13 | `archive_created_consumer.py` |
| F-014 | consolidation_runs_total | wired | §3.27 | COMPLIANT | regression | CON-004 tests | `consolidation_run_service.py` |
| F-015 | HTTP user isolation | 多模块 INT 覆盖 | §3.21 #6 | **AUDIT REQUIRED** | GAP→最小 fix | I-OPS2-* / 复跑 INT | repos/services |
| F-016 | Admin extraction isolation | user+archive lookup | §3.21 | COMPLIANT | none | EXT-008 INT | `extraction_admin_service.py` |
| F-017 | validation ctx redaction | 仅 `secret` in key | 凭证不入 details | SAFE_AUTO | 扩展 redact 规则（若审计发现 gap） | U-OPS2-07 | `error_handlers.py` |
| F-018 | Worker metrics scrape | worker registry 不可 api scrape | §3.27 | COMPLIANT（解释 A） | C-OPS2-02：api scrape 见 api series；worker 非零样本见 unit | C-OPS2-02 + U-OPS2-11 | N/A |
| F-019 | OpenTelemetry | 未实现 | MVP 后置 | DEFERRED | none | N/A | — |

## 13. 实现方案（仅 HARD_BLOCK + 必要 SAFE_AUTO）

### Step 0 — 只读审计确认（Developer 首日）

- 执行 §5 方法论 Phase A；更新 §12 Findings 状态与 §20/§21 白名单（仅追加，不删 preliminary 条目）。
- 若 F-015 全部为 COMPLIANT → `production_file_whitelist` 可不含 isolation fix 文件。
- 若 MET-AUDIT-001 需解释 B → **HALT** 报告 Orchestrator。

### Step 1 — Logging 基础设施

**文件**：`src/memory_system/observability/logging.py`, `src/memory_system/observability/request_context.py`, `src/memory_system/api/app.py`

- `configure_logging(settings, *, service_name: str)` — 去掉硬编码 `SERVICE_NAME`；entrypoints / `create_app` 传入：
  - `memory-api`（`api/app.py` `create_app` 调用 `configure_logging(resolved_settings, service_name="memory-api")`）
  - `memory-extraction-worker` / `memory-consolidation-worker`（各 entrypoint）
- 扩展 contextvars：`task_run_id`；helpers `set_task_run_id` / `bind_log_context(**kwargs)`（user_id/session_id/archive_id/task_id — **仅标识符**）
- `_add_service_context` 合并 contextvars 中允许字段

### Step 2 — 迁移 stdlib → structlog（F-006；Amendment 001 方案 A）

**验收口径**：§17「三进程 structlog JSON」= **本 inventory 全部 HARD_BLOCK 调用点** remediated；余量 stdlib 模块按 DEFERRED inventory 记录 rationale（方案 B 窄化验收 **不采用**）。

**HARD_BLOCK inventory（实施必改；Phase A grep 仅可追加，不可删 preliminary 条目）**：

| 文件 | 变更 |
|---|---|
| `domain/services/compression_llm_service.py` | structlog；保留 outcome 元数据；**禁止** message/prompt/content |
| `domain/services/extraction_task_consumer_service.py` | structlog；保留 SF-004 五字段；JSON |
| `observability/consolidation_run_telemetry.py` | structlog；`consolidation_run` 字段改 kwargs 非 opaque extra blob |
| `domain/services/extraction_llm_service.py` | structlog；outcome/error 元数据；**禁止** prompt/response content |
| `entrypoints/extraction_worker.py` | `_logger` → structlog；配合 Step 3 `service_name` + `task_run_id` |
| `entrypoints/consolidation_worker.py` | 同上 |
| `infrastructure/kafka/archive_created_consumer.py` | `log = logger or logging.getLogger` → structlog；lag/metrics 路径同文件 |

**DEFERRED_FOR_MVP inventory（不阻塞 §3.32 #8；Phase A 无新增 HARD_BLOCK 则保持）**：

| 文件 | Rationale |
|---|---|
| `domain/services/session_close_service.py` | 可选 logger 注入；既有 privacy 测试覆盖；无 identified 敏感泄漏 |
| `domain/services/compression_coordinator_service.py` | 传入 stdlib logger 给 LLM 子服务；协调层日志非 worker 主路径 |
| `domain/services/compression_preparation_service.py` | 同上；prep 路径无 content 日志 |
| `domain/services/archive_event_republish_service.py` | CLI/运维路径；非三 entrypoint 热路径；MVP 后置 |

### Step 3 — Worker task_run_id（F-005）

**文件**：`entrypoints/extraction_worker.py`, `entrypoints/consolidation_worker.py`

- 每个 consumer record / consolidation run 生成 UUID4 `task_run_id`
- `bind_log_context(task_run_id=..., user_id=..., archive_id=..., task_id=...)`
- 任务结束 clear/isolate context（避免 task 间泄漏）

### Step 4 — 指标接线（F-008..F-012）

**文件**：

- `domain/services/compression_coordinator_service.py` — `COMPRESSION_TOTAL.labels(status=...).inc()` 于每个返回/raise 前的终态 `CompressionStatus`（映射为 stable lowercase label）
- `domain/services/extraction_task_consumer_service.py` 和/或 `domain/services/production_extraction_pipeline.py` — extraction terminal metrics + duration
- `domain/services/retrieval_api_service.py` — mode=`hybrid|bm25|vector|...`（以实际 orchestration 分支为准）；status=`success|error|degraded`

**可选**：`observability/metrics.py` 新增小 helper（`record_compression(status)`, `observe_extraction(...)`, `observe_retrieval(...)`）避免重复 — 若新增仅改此文件，须列入 whitelist。

### Step 5 — 用户隔离 GAP 修复（仅 F-015 审计后）

- 若发现 repo 查询缺少 `user_id` filter → 最小 Cypher/Mongo/ES/Lua 修复
- 若仅缺测试 → 只增 integration/unit test，不改生产

### Step 6 — Focused tests（§18）

- 不修改 DEV-005 既有 contract 语义（可新增 OPS-002 文件）

## 14. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/api/app.py` | 修改 | `configure_logging(..., service_name="memory-api")` |
| `src/memory_system/observability/logging.py` | 修改 | 参数化 service_name；context 合并 |
| `src/memory_system/observability/request_context.py` | 修改 | task_run_id + bind helpers |
| `src/memory_system/observability/consolidation_run_telemetry.py` | 修改 | structlog JSON |
| `src/memory_system/observability/metrics.py` | 修改（可选） | record/observe helpers |
| `src/memory_system/domain/services/compression_llm_service.py` | 修改 | structlog 迁移 |
| `src/memory_system/domain/services/extraction_llm_service.py` | 修改 | structlog 迁移（F-006 inventory） |
| `src/memory_system/domain/services/extraction_task_consumer_service.py` | 修改 | structlog + extraction metrics |
| `src/memory_system/domain/services/compression_coordinator_service.py` | 修改 | compression_total |
| `src/memory_system/domain/services/retrieval_api_service.py` | 修改 | retrieval metrics |
| `src/memory_system/entrypoints/extraction_worker.py` | 修改 | service_name + task_run_id + structlog |
| `src/memory_system/entrypoints/consolidation_worker.py` | 修改 | service_name + task_run_id + structlog |
| `src/memory_system/api/error_handlers.py` | 修改（若 F-017） | validation redaction 加固 |
| `src/memory_system/api/middleware.py` | 修改（**仅若实现 F-007**） | optional user_id bind |
| `src/memory_system/infrastructure/kafka/archive_created_consumer.py` | 修改 | structlog（F-006）；kafka lag gauge（若 F-013 SAFE） |
| `tests/unit/test_ops002_logging_context.py` | 创建 | service_name/task_run_id/JSON 字段 |
| `tests/unit/test_ops002_metrics_wiring.py` | 创建 | compression/extraction/retrieval metrics |
| `tests/unit/test_ops002_sensitive_log_guards.py` | 创建 | 禁止 content/key 泄漏 |
| `tests/contract/test_ops002_observability_contract.py` | 创建 | MET-AUDIT-001 文档化断言 + scrape 边界 |
| `tests/contract/test_ops002_user_isolation_inventory.py` | 创建 | 静态清单：端点→user_id enforcement |
| `02_开发管理/progress.md` | 修改 | 实施态字段 |
| `02_开发管理/master_plan.md` | 修改 | OPS-002 状态备注 |

## 15. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | metrics/logging 为观测副作用 |
| 幂等 | 不适用 | counter inc 重复可接受（terminal 一次） |
| 并发 | 低 | Prometheus client 线程/async 安全；contextvars per task |
| 版本冲突 | 不适用 | — |
| 用户隔离 | **审计核心** | 修复不得 weakening 既有 filter |
| 部分失败 | 适用 | metrics 在 terminal outcome inc；非 success 也计数 |
| 进程异常恢复 | 不适用 | — |

## 16. 测试计划

### Unit Test

| ID | 场景 | 预期 |
|---|---|---|
| U-OPS2-01 | 三 entrypoint `configure_logging` service_name | api / extraction / consolidation 各自正确 |
| U-OPS2-02 | extraction worker 处理单 record | JSON 含 task_run_id + archive_id + user_id |
| U-OPS2-03 | compression_llm outcome log | structlog JSON；无 prompt/content 子串 |
| U-OPS2-03b | extraction_llm outcome log | structlog JSON；无 prompt/response content |
| U-OPS2-04 | extraction consumer failed log | SF-004 字段 + JSON |
| U-OPS2-05 | consolidation telemetry completed | structlog JSON + run_duration_ms |
| U-OPS2-06 | API route bind user_id（**optional**；仅当实现 F-007） | access log JSON 含 user_id |
| U-OPS2-07 | validation error 含 api_key 字段名 | details 中 redacted |
| U-OPS2-10 | compression coordinator 终态 | `compression_total{status}` inc |
| U-OPS2-11 | extraction terminal | tasks_total + duration observe |
| U-OPS2-12 | retrieval 请求 | requests_total + duration by mode |
| U-OPS2-13 | kafka lag（若实现） | gauge set 非负 |

### Contract Test

| ID | 场景 | 预期 |
|---|---|---|
| C-OPS2-01 | `/health/live` 访问后 JSON log | timestamp/level/service_name/environment/request_id |
| C-OPS2-02 | metrics 注册 + MET-AUDIT-001 解释 A | api scrape：http + consolidation + compression/retrieval（api 路径）可见；**不含** worker-only extraction series；worker unit（`U-OPS2-11`）断言 extraction metrics 非零 |
| C-OPS2-03 | auth failure | key 不在 log（回归 DEV-005 行为） |
| C-OPS2-04 | registered metric names | §3.27 名称全部仍注册 |

### Integration Test

| ID | 场景 | 预期 |
|---|---|---|
| I-OPS2-01 | 复跑 EXT-008 cross-user GET | 仍 404 |
| I-OPS2-02 | 复跑 RET-001/002 cross-user | 仍隔离 |
| I-OPS2-03 | 复跑 context_read wrong user | 仍失败 |
| I-OPS2-04 | （仅 GAP 时新增）新 isolation 场景 | 按 Findings |

### E2E Test

不适用（E2E-001）。

### 失败注入与并发

| ID | 场景 | 预期 |
|---|---|---|
| INJ-OPS2-01 | extraction terminal failed | metrics failed label inc；日志 error_code；无 content |
| INJ-OPS2-02 | retrieval embedding failure | metrics error status；无 credential in log |

### Scoped 运行命令（SF-3；实施验收）

```bash
# OPS-002 unit
uv run pytest tests/unit/test_ops002_logging_context.py \
  tests/unit/test_ops002_metrics_wiring.py \
  tests/unit/test_ops002_sensitive_log_guards.py -q

# OPS-002 contract
uv run pytest tests/contract/test_ops002_observability_contract.py \
  tests/contract/test_ops002_user_isolation_inventory.py -q

# 既有 observability / privacy 回归
uv run pytest tests/contract/test_api_shell_contract.py -q
uv run pytest tests/integration/test_ext008_extraction_admin_http.py \
  tests/integration/test_context_read_redis.py -q

# Lint（scoped production whitelist）
uv run ruff check src/memory_system/api/app.py \
  src/memory_system/observability/ \
  src/memory_system/domain/services/compression_llm_service.py \
  src/memory_system/domain/services/extraction_llm_service.py \
  src/memory_system/domain/services/extraction_task_consumer_service.py \
  src/memory_system/domain/services/compression_coordinator_service.py \
  src/memory_system/domain/services/retrieval_api_service.py \
  src/memory_system/entrypoints/extraction_worker.py \
  src/memory_system/entrypoints/consolidation_worker.py \
  src/memory_system/infrastructure/kafka/archive_created_consumer.py

uv run mypy src/memory_system/api/app.py \
  src/memory_system/observability/ \
  src/memory_system/domain/services/compression_llm_service.py \
  src/memory_system/domain/services/extraction_llm_service.py \
  src/memory_system/domain/services/extraction_task_consumer_service.py \
  src/memory_system/domain/services/compression_coordinator_service.py \
  src/memory_system/domain/services/retrieval_api_service.py \
  src/memory_system/entrypoints/extraction_worker.py \
  src/memory_system/entrypoints/consolidation_worker.py \
  src/memory_system/infrastructure/kafka/archive_created_consumer.py \
  tests/unit/test_ops002_*.py tests/contract/test_ops002_*.py
```

## 17. 验收标准

- [ ] §4–§12 审计矩阵与 Findings 表完整，每项有分类与证据
- [ ] 所有 `HARD_BLOCK` 已修复或 Reviewer 书面接受（不得静默遗留）
- [ ] §3.27 列出的 MVP 指标在对应业务路径 increment/observe（MET-AUDIT-001 解释 A：api scrape 见 api 路径 series；worker 系列以 unit 非零样本为准）
- [ ] 三进程 structlog JSON：**F-006 HARD_BLOCK inventory（§13 Step 2，7 文件）** 全部 remediated；DEFERRED inventory 有书面 rationale
- [ ] worker 含 `task_run_id`；`service_name` 按进程正确（含 `api/app.py` 传入 `memory-api`）
- [ ] 禁止敏感内容不入日志（自动化 grep/断言测试）
- [ ] §3.21 用户隔离审计完成；GAP 已修复或新增测试覆盖
- [ ] 既有 DEV-005 contract + privacy/isolation tests 无回归
- [ ] scoped `ruff check` / `mypy` PASS
- [ ] `progress.md` / `master_plan.md` 实施态同步
- [ ] Review 无 P0/P1

## 18. 风险与阻塞项

| 风险 | 级别 | 缓解 |
|---|---|---|
| MET-AUDIT-001 worker metrics 不可 api scrape | 中 | 解释 A + contract 文档；若需 B则 HALT |
| structlog 迁移遗漏模块 | 中 | grep `logging.getLogger` 清单 + Phase A |
| metrics label 高基数 | 低 | 禁止 path 原始 URL / message_id 作 label |
| F-015 发现需改 Cypher/Schema | 高 | HALT — 不得自行改 Contract |
| kafka_consumer_lag 不可用 | 低 | DEFERRED + §12 F-013 |
| 触碰 DEV-006/PR#13 | — | 禁止 |

## 19. Git 计划

```yaml
branch: "feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
workflow_mode: NORMAL
release_phases:
  PLAN_LANDING:
    allowed_on: main
    commands:
      - "git add 02_开发管理/tasks/OPS-002-logging-metrics-sensitive-user-isolation-audit.md 02_开发管理/progress.md 02_开发管理/master_plan.md"
      - "git commit -m \"docs(plan): add OPS-002 logging metrics sensitive user isolation audit plan\""
      - "git pull --ff-only"
      - "git push origin main"
      - "git checkout -b feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
  IMPLEMENTATION_RELEASE:
    allowed_on: feat/OPS-002-logging-metrics-sensitive-user-isolation-audit
    commands:
      - "git add <§20 production whitelist exact paths>"
      - "git add <§21 test whitelist exact paths>"
      - "git commit -m \"fix(ops): wire observability metrics and structured logging audit remediations\""
      - "git commit -m \"test(ops): add OPS-002 observability and isolation audit tests\"  # 可与上合并若原子"
      - "git push -u origin feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
      - "gh pr create --title \"fix(ops): OPS-002 logging metrics sensitive info user isolation audit\" --body \"...\""
  POST_MERGE_CLEANUP:
    allowed_on: main
    precondition: "PR MERGED verified"
    commands:
      - "git fetch && git checkout main && git pull --ff-only"
      - "git commit -m \"docs(status): complete OPS-002 after PR merge\"  # progress/master_plan only"
      - "git push origin main"
      - "git branch -d feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
      - "git push origin --delete feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
expected_commits:
  - "docs(plan): add OPS-002 logging metrics sensitive user isolation audit plan"
  - "fix(ops): wire observability metrics and structured logging audit remediations"
  - "test(ops): add OPS-002 observability and isolation audit tests"
out_of_scope_changes:
  - "OPS-003+"
  - "DEV-006 / PR #13"
  - "OpenTelemetry"
  - "API Contract / Schema / 错误码变更"
  - ".cursor/**"
  - "compose.yaml / migrations / dependencies"
```

## 20. production_file_whitelist

```yaml
# Phase A 确认后不得超出此列表（Amendment 001 对齐）
production_file_whitelist:
  - "src/memory_system/api/app.py"
  - "src/memory_system/observability/logging.py"
  - "src/memory_system/observability/request_context.py"
  - "src/memory_system/observability/consolidation_run_telemetry.py"
  - "src/memory_system/observability/metrics.py"
  - "src/memory_system/domain/services/compression_llm_service.py"
  - "src/memory_system/domain/services/extraction_llm_service.py"
  - "src/memory_system/domain/services/extraction_task_consumer_service.py"
  - "src/memory_system/domain/services/compression_coordinator_service.py"
  - "src/memory_system/domain/services/retrieval_api_service.py"
  - "src/memory_system/domain/services/production_extraction_pipeline.py"
  - "src/memory_system/entrypoints/extraction_worker.py"
  - "src/memory_system/entrypoints/consolidation_worker.py"
  - "src/memory_system/api/error_handlers.py"
  - "src/memory_system/infrastructure/kafka/archive_created_consumer.py"

# 条件追加（仅当 Developer 实现 F-007 user_id bind）：
#   - "src/memory_system/api/middleware.py"

# F-015 若审计发现 isolation 生产缺口，仅可追加 exact repo/service 路径（Amendment 记录）
# Phase A grep 可追加 F-006 新 HARD_BLOCK 路径（不可删 preliminary inventory）
# 若全部为 COMPLIANT 且仅增测试：production_file_whitelist 可收缩为 logging/metrics 子集
```

## 21. test_file_whitelist

```yaml
test_file_whitelist:
  - "tests/unit/test_ops002_logging_context.py"
  - "tests/unit/test_ops002_metrics_wiring.py"
  - "tests/unit/test_ops002_sensitive_log_guards.py"
  - "tests/contract/test_ops002_observability_contract.py"
  - "tests/contract/test_ops002_user_isolation_inventory.py"

# F-015 GAP 修复时仅可追加 exact 新测试文件路径
# 不得修改既有 privacy/isolation 测试断言语义（仅可追加 case）
```

## 22. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：2026-08-14 10:29 UTC
- 原计划：Round 1 preliminary plan（`updated_at=2026-08-14 02:17 UTC`）
- 修改内容：
  - **MF-1**：§20 追加 `api/app.py`；§14 Step 1 明确 `create_app` 调用 `configure_logging(..., service_name="memory-api")`
  - **MF-2**：F-006 采用 **方案 A** — 扩展 HARD_BLOCK inventory 至 7 文件（含 `extraction_llm_service.py`、`archive_created_consumer.py`、两 entrypoint）；§17/§8 与 §13 Step 2 对齐；4 文件 DEFERRED inventory + rationale
  - **SF-1**：MET-AUDIT-001 / C-OPS2-02 锁定解释 A — api scrape vs worker unit 非零样本分工
  - **SF-2**：F-007 / U-OPS2-06 标为 optional；`api/middleware.py` 条件白名单
  - **SF-3**：§16 追加 scoped `uv run pytest` / `ruff` / `mypy` 命令块
  - **SF-4**：§5.2 追加 per-file structlog 迁移 vs stdlib bridge 一句 rationale
- 修改原因：Round 1 Plan Review `PLAN_REJECTED`（BLOCKER=0，MUST_FIX=2，SHOULD_FIX=4）
- 是否影响技术规格：**否**（验收口径与 inventory 澄清；不修改 §3.27 Contract）
- 审批状态：Round 2 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0 SHOULD_FIX=0）；human PLAN_APPROVED 2026-08-14

## 23. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-14 02:17 UTC | planning | 创建本 Task Plan；preliminary Findings §12；progress/master_plan 规划态 | 未实施 | 19 preliminary findings；6 HARD_BLOCK；2 DEFERRED；MET-AUDIT-001 待 Step 0 确认 |
| 2026-08-14 10:29 UTC | planning (Amendment 001) | Round 1 PLAN_REJECTED 修订：MF-1 `api/app.py`；MF-2 F-006 方案 A（7-file inventory）；SF-1..SF-4 | 未实施 | MUST_FIX #1/#2 + SHOULD_FIX 已落实；`next_action=计划审查 Round 2` |
| 2026-08-14 02:51 UTC | plan review Round 2 | PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=0；human PLAN_APPROVED；治理回写 approved | 未实施 | `next_action=PLAN_LANDING` → Developer on feat post-landing |
| 2026-08-14 03:05 UTC | Step 0 audit confirm | Phase A：F-015→COMPLIANT（§7.3 INT + C-OPS2 inventory）；F-013/F-006-D 保持 DEFERRED；MET-AUDIT-001 解释 A 确认 | 未改代码 | 无新增 HARD_BLOCK |
| 2026-08-14 03:05 UTC | Steps 1-4 implement | logging service_name/task_run_id；7-file structlog；metrics F-008..F-012；F-017 validation redact | OPS-002 unit+contract 21 passed | 无 Contract 变更 |
| 2026-08-14 03:05 UTC | Step 6 + regression | scoped ruff/mypy PASS；DEV-005 contract 12 passed；EXT-008 INT 7 passed | 40 passed scoped | context_read INT 需 Redis（环境不可用 SKIP） |

## 24. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/observability/logging.py` | 参数化 `service_name`；合并 contextvars 允许字段 |
| `src/memory_system/observability/request_context.py` | `task_run_id` + `bind_log_context` / `clear_task_context` |
| `src/memory_system/observability/metrics.py` | `record_compression` / `record_extraction_terminal` / `record_retrieval` |
| `src/memory_system/observability/consolidation_run_telemetry.py` | structlog JSON kwargs |
| `src/memory_system/api/app.py` | `configure_logging(..., service_name="memory-api")` |
| `src/memory_system/api/error_handlers.py` | validation `api_key`/`secret` loc+ctx redaction (F-017) |
| `src/memory_system/domain/services/compression_llm_service.py` | structlog 迁移 |
| `src/memory_system/domain/services/extraction_llm_service.py` | structlog 迁移 |
| `src/memory_system/domain/services/extraction_task_consumer_service.py` | structlog + extraction metrics |
| `src/memory_system/domain/services/compression_coordinator_service.py` | `compression_total` 接线 |
| `src/memory_system/domain/services/retrieval_api_service.py` | `retrieval_*` metrics 接线 |
| `src/memory_system/entrypoints/extraction_worker.py` | service_name + structlog |
| `src/memory_system/entrypoints/consolidation_worker.py` | service_name + task_run_id + structlog |
| `src/memory_system/infrastructure/kafka/archive_created_consumer.py` | structlog + per-record `task_run_id` bind |
| `tests/unit/test_ops002_logging_context.py` | 新建 U-OPS2-01..05 |
| `tests/unit/test_ops002_metrics_wiring.py` | 新建 U-OPS2-10..12 |
| `tests/unit/test_ops002_sensitive_log_guards.py` | 新建 U-OPS2-07 + guards |
| `tests/contract/test_ops002_observability_contract.py` | 新建 C-OPS2-01..04 |
| `tests/contract/test_ops002_user_isolation_inventory.py` | 新建 isolation inventory |

### 与原计划的差异

- F-007（API `user_id` bind）未实现（optional；不阻塞验收）。
- F-013 `kafka_consumer_lag` 保持 DEFERRED_FOR_MVP。
- `test_context_read_redis` 回归需 live Redis；本环境连接拒绝，未计入 scoped PASS。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit (OPS-002) | `uv run pytest tests/unit/test_ops002_*.py -q` | 14 passed |
| Contract (OPS-002) | `uv run pytest tests/contract/test_ops002_*.py -q` | 7 passed |
| Regression DEV-005 | `uv run pytest tests/contract/test_api_shell_contract.py -q` | 12 passed |
| Regression EXT-008 INT | `uv run pytest tests/integration/test_ext008_extraction_admin_http.py -q` | 7 passed |
| Regression context_read | `uv run pytest tests/integration/test_context_read_redis.py -q` | SKIP（Redis 不可用） |
| Ruff | scoped §16 whitelist | PASS |
| Mypy | scoped §16 whitelist | PASS |

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
branch: feat/OPS-002-logging-metrics-sensitive-user-isolation-audit
plan_commit: f79f81537f55b4e28bc07b55a0aff1cd5864b72a
implementation_commit: 7ddcf9234bbc56e227db956b83ecc38c73d1aa90
implementation_commit_message: "fix(ops): OPS-002 logging metrics sensitive info user isolation audit"
```

### 最终状态

`committed`
