# DEV-005 通用 API 壳、鉴权、Request ID、日志与指标

## 1. 任务信息

```yaml
task_id: DEV-005
task_name: 通用 API 壳、鉴权、Request ID、日志与指标
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§3.4 单仓库目录结构（api/、observability/、infrastructure/security/）"
  - "§3.7 Web 服务与应用生命周期（FastAPI Lifespan、Client 创建与释放）"
  - "§3.16 健康检查与就绪规则（memory-api Readiness 边界；Embedding 非阻塞）"
  - "§3.21 Memory API 鉴权与接口暴露"
  - "§3.23 统一 API 响应与 Request ID"
  - "§3.25 优雅关闭（Uvicorn --timeout-graceful-shutdown 450）"
  - "§3.26 Schema Migration（Readiness 须确认 Migration 已应用）"
  - "§3.27 日志、指标与敏感信息保护"
prerequisites:
  - "DEV-001 completed（FastAPI/uvicorn/structlog/prometheus-client 依赖；entrypoints/api.py 占位）"
  - "DEV-002 completed（get_settings()、MEMORY_API_KEY/MEMORY_ADMIN_API_KEY SecretStr、shutdown 校验）"
  - "DEV-003 completed（memory-api Compose command、stop_grace_period=480s、端口 8000）"
  - "DEV-004 completed（Migration Runner + ES Mapping/Alias；infra_schema_migrations）"
  - "DEV-OPS-003 completed（NORMAL/STRICT 工作流）"
  - "实施编码前须 PLAN_APPROVED；本轮仅规划，不得实施"
branch: "feat/DEV-005-api-shell-auth-request-id-logging-metrics"
created_at: "2026-08-08 11:20 UTC"
updated_at: "2026-08-08 11:20 UTC"
approval_gates:
  planning_docs: "PLAN_APPROVED（Plan Reviewer + 人工确认 2026-08-08）"
  implementation_plan: "status=approved；等待 PLAN_LANDING（docs(plan) on main → feat 分支）"
```

## 2. 任务目标

本任务交付 **memory-api 可启动的 FastAPI 应用壳**（不含 STM/Retrieval/Extraction 业务路由），并实现规格要求的横切能力：鉴权、统一错误包络、Request ID、structlog JSON 日志、Prometheus 指标、Liveness/Readiness 结构。

完成后应具备：

1. **FastAPI 应用工厂与 Lifespan（§3.7）**：加载并校验 Settings；创建 Redis、MongoDB、Neo4j、Elasticsearch、HTTP Client 与 Kafka Producer；启动时执行依赖连接检查；关闭时按相反顺序释放资源；`memory_system.entrypoints.api` 通过 Uvicorn 启动（`--timeout-graceful-shutdown 450`，绑定 `0.0.0.0:8000`）。
2. **鉴权（§3.21）**：`X-API-Key` 头；`secrets.compare_digest` 常量时间比较；缺失/错误统一 `401` + `invalid_api_key`；普通 Key 与 Admin Key 分级依赖；Health 免 Key；`/internal/metrics` 仅 Admin Key。
3. **Request ID 与错误包络（§3.23）**：`X-Request-ID` 中间件（客户端合法 UUID4 或缺省生成）；响应 Header 与错误 Body 同一 `request_id`；全局异常处理输出 `{success:false, error:{code,message,details}, request_id}`；`422` → `validation_error`；禁止 FastAPI 默认校验 JSON。
4. **结构化日志（§3.27）**：`structlog` + JSON Renderer；每条日志含规格最小字段集；禁止记录 API Key、Authorization、完整消息/LLM 内容等敏感信息。
5. **指标（§3.27）**：`prometheus-client`；`GET /internal/metrics`（Admin Key）；注册规格列出的全部指标名（业务尚未接入时允许计数为 0，但须可 scrape）。
6. **健康检查（§3.16 / §3.21 / §3.26）**：
   - `GET /health/live`：仅进程存活；免 Key。
   - `GET /health/ready`：返回各依赖 `ready`/`not_ready` 名称列表；**不得**返回连接地址或堆栈；免 Key；阻塞项含 Redis/Mongo/Neo4j/ES 版本+Mapping/Migration 记录/Kafka Producer；Embedding **非阻塞**（单独暴露状态，不影响总体 `ready`）。
7. **测试**：Unit/Contract 覆盖鉴权、错误形状、Request ID、敏感日志断言、指标端点门禁；可选 Integration 在 compose.test 栈验证 Readiness（非发布阻塞时可标记为可选，但 Unit/Contract 必须全绿）。

**边界声明（与 master_plan 一致）**：本任务交付 Readiness **结构**与 §3.16 所列阻塞探针的首次实现；**不宣称**后续业务任务才完善的降级矩阵、Embedding 向量探针、Worker 健康端点或 OPS-002 全量审计完成。

## 3. 非目标

- STM / Retrieval / Extraction / Consolidation **业务 HTTP 路由**（`POST /api/v1/memory/*` 等属 STM-002+ / RET-005 / EXT-008）。
- **DEV-006** TEI Embedding Client 与 Token Budget。
- OpenTelemetry Trace（§3.27 明确后置）。
- 修改 `settings/**`、`.env.example`、`configs/*.yaml` Contract（除非 Plan Review 认定缺键并走 Amendment）。
- 修改 Migration 文件或 Runner 语义（DEV-004）。
- 修改 Compose 拓扑、镜像版本、Preflight、五命令/Orchestrator 正文。
- 实现完整 `infrastructure/redis|mongodb|...` 业务 Repository（仅允许 Lifespan 级 **最小** 连接/探针 Client，供 Health 与后续任务复用）。
- Worker Entrypoint 启动逻辑（extraction/consolidation 仍保持「not ready」占位，本任务只改 `entrypoints/api.py`）。
- JWT/OAuth/用户登录。
- 将 `scripts/migrate` 或 `republish_archive_event` 暴露为 HTTP。
- 真实 E2E 全链路或 CI workflow（OPS-004）。

## 4. 当前代码状态

### 4.1 已存在代码

- **DEV-001**：`pyproject.toml` 含 `fastapi`、`uvicorn[standard]`、`structlog`、`prometheus-client`；`src/memory_system/entrypoints/api.py` 占位（`main()` 打印 not ready 并 `exit 1`）。
- **DEV-002**：`get_settings()`；`memory_api_key` / `memory_admin_api_key`（`SecretStr`）；`shutdown.memory_api_timeout_seconds=450`；`required_env_keys()` 含两 API Key。
- **DEV-003**：`compose.yaml` `memory-api` → `python -m memory_system.entrypoints.api`；`stop_grace_period: 480s`；`compose.override.yaml` 绑定 `127.0.0.1:8000:8000`。
- **DEV-004**：`scripts/migrate.py` + `001`–`004`；`infra_schema_migrations`；ES Alias `memory_retrieval_current` + Mapping 契约测试。

### 4.2 可复用组件

- `memory_system.settings.get_settings()` 与 `tests/unit/test_settings_validation.py` 的合法 env fixture 模式。
- `tests/unit/test_elasticsearch_mapping_contract.py` 中 §2.2.4 Mapping 常量（Readiness ES 探针可复用断言逻辑，不得复制第二套 Mapping 定义）。
- `scripts/migrate.py` 中 `migration_id` 列表与 checksum 语义（Readiness 仅 **读取** Record，不执行 migrate）。
- DEV-004 Integration 模式：`compose.sh --stack=test` 启动基础设施。

### 4.3 当前缺失

- **整个 `src/memory_system/api/` 树**（`dependencies.py`、`middleware.py`、`error_handlers.py`、`routes/`）——DEV-001 白名单曾列 `api/__init__.py`，但仓库当前 **不存在** `api/` 目录，本任务 **创建并实现**。
- **`src/memory_system/observability/`**（DEV-001 白名单占位未落盘）——本任务创建 logging/metrics/context 模块。
- **`src/memory_system/infrastructure/security/`**（同上）——本任务创建 API Key 比较模块。
- FastAPI `create_app()`、Lifespan、Health/Metrics 路由、全局异常处理、structlog 配置。
- `entrypoints/api.py` 仍为 not-ready 桩。
- 相关 Unit/Contract 测试。

### 4.4 与技术规格不一致之处

- §3.4 要求的 `api/`、`observability/`、`infrastructure/security/` 路径尚未存在（DEV-001 子集未完全落盘）；本任务按规格补齐 **本任务范围内** 的路径与实现。
- §3.7 / §3.21 / §3.23 / §3.27 横切能力尚未接线。
- `tests/unit/test_entrypoints_import.py` 仍断言 `entrypoints.api` 子进程 `not ready`——实施后须 **按 §8.10 修订**（属本任务白名单）。

### 4.5 前置任务检查

| 前置 | 状态 | 证据 |
|---|---|---|
| DEV-001 | completed | PR #1 |
| DEV-002 | completed | PR #5 |
| DEV-003 | completed | PR #6 |
| DEV-004 | completed | PR #10 MERGED `206b7a6` |
| DEV-OPS-003 | completed | PR #7 + SMOKE #8 |
| DEV-OPS-005 | completed | PR #11 MERGED `0239c28` |
| Git | `main` @ `bf537d8` 干净 | 用户只读验证 + `git status` 空 |

### 4.6 规格未写明 URL 的处理

§3.21 / §3.16 定义 **接口类别与响应语义**，未给出 Health 路径字面量。本计划在 §8.5 冻结工程路径（`/health/live`、`/health/ready`）；**不**扩展业务 API Contract。若 Plan Review 要求修订路径，走 Amendment，不得静默改名。

## 5. 实现方案

### Step 1 — 包结构与 API Key 安全原语

- **文件**：
  - `src/memory_system/api/__init__.py`（导出 `create_app`）
  - `src/memory_system/infrastructure/__init__.py`（若缺失则创建空包标记）
  - `src/memory_system/infrastructure/security/__init__.py`
  - `src/memory_system/infrastructure/security/api_key.py`
  - `src/memory_system/observability/__init__.py`
- **职责**：
  - `verify_api_key(provided: str | None, expected: SecretStr) -> bool`：`secrets.compare_digest`；长度不等时仍走常量时间路径（先 hash 或 `hmac.compare_digest` 对固定长度编码比较，禁止短路 `==`）。
  - `class ApiKeyRole`：`memory` | `admin`。
  - 不记录 provided/expected 明文。

### Step 2 — 可观测性基础（structlog + Prometheus）

- **文件**：
  - `src/memory_system/observability/logging.py` — `configure_logging(settings)`：stdlib logging + structlog JSON；绑定 `service_name="memory-api"`、`environment=settings.app_env`。
  - `src/memory_system/observability/request_context.py` — `contextvars` 持有 `request_id`、可选 `user_id`/`session_id` 等（HTTP 阶段至少 `request_id`）。
  - `src/memory_system/observability/metrics.py` — 注册 §3.27 全部指标（`Counter`/`Histogram`）；提供 `observe_http_request(method, path_template, status, duration_seconds)` 辅助函数。
- **规则**：日志与指标 label **禁止**含 API Key、完整 URI 凭证、原始路径参数中的敏感正文。

### Step 3 — 统一错误模型与异常处理

- **文件**：
  - `src/memory_system/api/errors.py`（或 `domain/errors/http.py` 若坚持分层——**优先** `api/errors.py` 避免过早建 domain 树）
  - `src/memory_system/api/error_handlers.py`
- **类型**：
  - `AppError(Exception)`：`code: str`, `message: str`, `status_code: int`, `details: dict`
  - `build_error_response(code, message, details, request_id) -> JSONResponse`
- **注册处理器**：
  - `AppError` → 映射 status + 统一 Body
  - `RequestValidationError` / `ValidationError` → `422` + `validation_error` + Pydantic 错误摘要入 `details`（**不得**泄漏 Secret 字段值）
  - `HTTPException` → 转换为统一结构（若 code 未指定，使用 `http_error` 或规格既有 code）
  - 未捕获异常 → `503` + `internal_error`（message 泛化；**不得**把堆栈写入 Body；堆栈仅写内部日志且受敏感规则约束）

### Step 4 — Request ID 与 HTTP 中间件

- **文件**：`src/memory_system/api/middleware.py`
- **中间件顺序**（外→内）：RequestId → AccessLog/Metrics → （路由）
- **RequestIdMiddleware**：
  - 读取 `X-Request-ID`；若缺失或非合法 UUID4 字符串则生成 `uuid4()`（非法入参 **丢弃** 并生成新 ID，不 400）。
  - 写入 `request.state.request_id` 与 `observability.request_context`。
  - 响应 Header `X-Request-ID` 回传。
- **MetricsMiddleware**：统计 `http_requests_total`、`http_request_duration_seconds`（path 使用路由 template，非原始 URL，避免高基数）。

### Step 5 — FastAPI 依赖（鉴权）

- **文件**：`src/memory_system/api/dependencies.py`
- **依赖**：
  - `get_settings_dep` → `get_settings()`
  - `get_request_id` → 从 `request.state`
  - `require_memory_api_key`：接受 `MEMORY_API_KEY` 或 `MEMORY_ADMIN_API_KEY`；失败抛 `AppError(invalid_api_key, 401)`
  - `require_admin_api_key`：仅 Admin；失败同样 `401` + `invalid_api_key`（**不得**区分缺失/错误/权限不足对外语义——Admin 路由错误 Key 仍用 `invalid_api_key`；规格 §3.21 针对缺失/错误 Key；Admin **专用**路由在 Key 有效但非 Admin 时可用 `403` + `forbidden` **仅当** Plan Review 认定需要；**默认**统一 `401`/`invalid_api_key` 以保守对齐「不得区分缺失与错误」，Admin 路由错误类型也走 `invalid_api_key`）
- **说明**：Admin 路由在 Key 为普通 Memory Key 时返回 `403` + `forbidden` 会区分「有效普通 Key」与「无效 Key」。规格仅禁止区分「缺失」与「错误」。实施时：**无效/缺失** → `401 invalid_api_key`；**有效普通 Key 访问 Admin 路由** → `403 forbidden`（不泄露 Key 是否存在以外的信息）。须在测试中覆盖。

### Step 6 — Lifespan 与应用状态

- **文件**：
  - `src/memory_system/infrastructure/runtime.py`（或 `api/lifespan.py`）— `AppState` dataclass 持有 clients/producer
  - `src/memory_system/api/app.py` — `create_app(settings: Settings | None = None) -> FastAPI`
- **Lifespan 创建（§3.7）**：
  1. `settings = settings or get_settings()`
  2. `configure_logging(settings)`
  3. 创建 `redis.asyncio.Redis`（from_url，`decode_responses` 按驱动默认）
  4. 创建 `motor` 或 `pymongo` Async — **规格全异步**：优先 `pymongo` Async API（已在依赖中）或 `motor`（**禁止**新增未批准依赖）→ 使用 `pymongo` `AsyncMongoClient`
  5. 创建 `neo4j.AsyncGraphDatabase.driver`
  6. 创建 `elasticsearch.AsyncElasticsearch`
  7. 创建共享 `httpx.AsyncClient`（超时读 `settings.http_client`）
  8. 创建 `AIOKafkaProducer` 并 `start()`
  9. 连接检查（ping/command）：失败 → Lifespan 启动失败，进程退出（非零）
- **关闭**：逆序 `stop` producer → close es/neo4j/mongo/redis/http client
- **`app.state`**：挂载 `AppState` 供 Health 与后续路由复用

### Step 7 — Health 与 Internal 路由

- **文件**：
  - `src/memory_system/api/routes/__init__.py`
  - `src/memory_system/api/routes/health.py`
  - `src/memory_system/api/routes/internal_metrics.py`
- **路由**：
  - `GET /health/live` → `200` `{"status":"alive"}`
  - `GET /health/ready` → 见 §8.5；总体 `not_ready` 时 `503`
  - `GET /internal/metrics` → `require_admin_api_key`；`prometheus_client.generate_latest`；`Content-Type` 来自 `CONTENT_TYPE_LATEST`
- **Readiness 探针逻辑**（每项返回 `ready`|`not_ready`，异常 swallow 为 `not_ready`，日志记录 `error_code` 不含堆栈到响应）：
  - `redis`：`PING`
  - `mongodb`：`ping` admin
  - `neo4j`：`RETURN 1`
  - `elasticsearch`：集群健康 + 版本等于 `settings.memory_retrieval.elasticsearch_version` + Alias `settings.memory_retrieval.index_name` 存在且 Mapping 兼容（复用 mapping contract 校验函数）
  - `kafka_producer`：producer 已 start 且 `bootstrap_connected`（或等价探针）
  - `migrations`：`infra_schema_migrations` 含 `001`–`004` 四条记录
  - `embedding`（**非阻塞**）：对 `settings.embedding.base_url` HTTP GET `/health` 或轻量探针；失败标记 `not_ready` 但 **不**导致总体 `not_ready`

### Step 8 — Entrypoint 接线

- **文件**：`src/memory_system/entrypoints/api.py`
- **行为**：
  - `main()`：`get_settings()` → `create_app()` → `uvicorn.run(app, host="0.0.0.0", port=8000, timeout_graceful_shutdown=settings.shutdown.memory_api_timeout_seconds)`（450）
  - Settings 加载失败：stderr 明确错误；`exit 1`
  - **禁止** import 时启动 Uvicorn

### Step 9 — 测试（见 §8）

与实现同步提交；失败不得跳过。

### Step 10 — 治理回写（实施阶段）

Developer 更新本 Plan 执行记录与 `progress.md`；本规划轮次仅 `planned`。

## 6. 文件变更清单（精确白名单）

禁止使用 `src/memory_system/**`、`tests/**` 通配作为变更描述。实施时 **仅允许** 触及下列路径：

### 6.1 API 壳与横切

| 路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/api/__init__.py` | 创建 | 包标记；导出 `create_app` |
| `src/memory_system/api/app.py` | 创建 | FastAPI 工厂、Lifespan 注册、路由挂载 |
| `src/memory_system/api/dependencies.py` | 创建 | Settings/鉴权/Request ID 依赖 |
| `src/memory_system/api/middleware.py` | 创建 | Request ID、访问日志、HTTP 指标 |
| `src/memory_system/api/error_handlers.py` | 创建 | 统一异常处理注册 |
| `src/memory_system/api/errors.py` | 创建 | `AppError` 与错误响应构建 |
| `src/memory_system/api/routes/__init__.py` | 创建 | 路由包 |
| `src/memory_system/api/routes/health.py` | 创建 | Liveness/Readiness |
| `src/memory_system/api/routes/internal_metrics.py` | 创建 | Prometheus scrape |

### 6.2 基础设施与安全（最小）

| 路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/infrastructure/__init__.py` | 创建（若缺失） | 包标记 |
| `src/memory_system/infrastructure/security/__init__.py` | 创建 | 包标记 |
| `src/memory_system/infrastructure/security/api_key.py` | 创建 | 常量时间 Key 比较 |
| `src/memory_system/infrastructure/runtime.py` | 创建 | `AppState`、client 工厂、shutdown |

### 6.3 可观测性

| 路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/observability/__init__.py` | 创建 | 包标记 |
| `src/memory_system/observability/logging.py` | 创建 | structlog JSON 配置 |
| `src/memory_system/observability/request_context.py` | 创建 | contextvars |
| `src/memory_system/observability/metrics.py` | 创建 | Prometheus 指标注册 |

### 6.4 Entrypoint

| 路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/entrypoints/api.py` | 修改 | Uvicorn 启动与 not-ready 移除 |

### 6.5 测试

| 路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_api_key_security.py` | 创建 | 常量时间比较；不泄露 |
| `tests/unit/test_error_envelope.py` | 创建 | 错误 JSON 形状 |
| `tests/unit/test_request_id.py` | 创建 | 生成/透传/非法入参 |
| `tests/contract/test_api_shell_contract.py` | 创建 | TestClient：鉴权、metrics、health、validation_error |
| `tests/unit/test_entrypoints_import.py` | 修改 | api entrypoint 行为更新（§8.10） |
| `tests/integration/test_api_readiness.py` | 创建（可选） | compose.test 栈 Readiness；见 §8.9 |

### 6.6 文档（最小）

| 路径 | 创建/修改 | 目的 |
|---|---|---|
| `README.md` | 修改 | memory-api 本地启动说明（经 `uv run` + test env）；**禁止**裸 docker compose |

### 6.7 治理文档（本规划轮次）

| 路径 | 创建/修改 | 目的 |
|---|---|---|
| `02_开发管理/tasks/DEV-005-api-shell-auth-request-id-logging-metrics.md` | 创建 | 本 Task Plan |
| `02_开发管理/progress.md` | 修改 | 规划态字段 |
| `02_开发管理/master_plan.md` | 修改 | DEV-005 登记 + CHANGE-010 |

## 7. 文件黑名单（禁止本任务创建或修改）

| 路径 / 模式 | 归属 / 原因 |
|---|---|
| `01_技术规格/**` | 规格正文不可改 |
| `03_AI_Prompts/**` 五命令与全局规则正文 | DEV-OPS-* |
| `.cursor/commands/**`、`.cursor/agents/**`、`.cursor/permissions.json` | DEV-OPS |
| `src/memory_system/settings/**` | DEV-002；除非 Amendment |
| `.env.example`、`configs/*.yaml` | DEV-002；默认不改 |
| `scripts/**`（含 migrate） | DEV-004 / DEV-003 |
| `compose*.yaml`、`versions.*`、`Dockerfile` | DEV-003/004；默认不改 |
| `src/memory_system/domain/**`、`application/**` | 业务任务 |
| `src/memory_system/infrastructure/redis/**` 等业务仓储 | 后续任务（本任务仅 `runtime.py` + `security/`） |
| `src/memory_system/infrastructure/embedding/**`、`llm/**` | DEV-006+ |
| `entrypoints/extraction_worker.py`、`consolidation_worker.py` | 后续任务 |
| `pyproject.toml` / `uv.lock` 依赖变更 | 禁止（所需库已在 §3.5） |
| `tests/conftest.py` | DEV-001 约定；fixture 写入本任务测试文件 |
| DEV-006、STM-*、RET-*、EXT-* 业务文件 | 禁止提前实施 |
| `.env`、Secret、真实用户数据 | 永不提交 |

## 8. 关键行为规格（硬性合同）

### 8.1 鉴权（§3.21）

| 场景 | HTTP | `error.code` | 说明 |
|---|---|---|---|
| 受保护路由无 `X-API-Key` | 401 | `invalid_api_key` | 与错误 Key 相同响应 |
| 受保护路由错误 Key | 401 | `invalid_api_key` | 常量时间比较 |
| 普通 Key 访问 Admin 路由（如 `/internal/metrics`） | 403 | `forbidden` | 不替代 invalid 语义 |
| Admin Key 访问 Admin 路由 | 200 | — | |
| Memory 或 Admin Key 访问未来业务路由 | 200/业务错误 | 业务码 | 本任务仅 metrics 可测 |
| `/health/live`、`/health/ready` | 200/503 | — | 免 Key |
| Key 不得出现在日志/响应/指标 label | — | — | 强制 |

环境变量：`MEMORY_API_KEY`、`MEMORY_ADMIN_API_KEY`（已由 DEV-002 建模）。

### 8.2 统一错误包络（§3.23）

所有 HTTP 错误 Body **必须**为：

```json
{
  "success": false,
  "error": {
    "code": "<snake_case_code>",
    "message": "<human readable>",
    "details": {}
  },
  "request_id": "<uuid>"
}
```

- 响应 Header 含 `X-Request-ID`，与 Body 中 `request_id` 一致。
- `422` Pydantic 校验：`code=validation_error`；**禁止** FastAPI 默认 `detail` 数组裸返回。
- 成功响应：本任务 Health/Metrics 可使用简单 JSON 或 Prometheus 文本；**未来**业务成功体不受 `success:true` 包裹（规格：成功响应继续用各业务 Schema）。

### 8.3 Request ID（§3.23）

1. 客户端可传 `X-Request-ID`（合法 UUID4 字符串）。
2. 缺省或非法 → 服务端生成 UUID4。
3. Worker 任务 **不** 在本任务实现；不得将 HTTP `request_id` 当作 Kafka `task_run_id`。

### 8.4 日志（§3.27）

- 渲染：JSON；UTC 时间戳。
- 最小字段：`timestamp`、`level`、`service_name`、`environment`、`request_id`（HTTP）或 `task_run_id`（Worker 后续）、可选 `user_id`/`session_id`/`archive_id`/`task_id`、`error_code`（错误时）、`duration_ms`（完成时）。
- **禁止**：完整用户消息、完整 LLM Prompt/Response、API Key、Authorization、DB 密码、连接串凭证。

### 8.5 健康检查路径与响应（§3.16 / §3.21 / §3.26）

**路径（工程冻结）**：

| 路径 | 鉴权 | 说明 |
|---|---|---|
| `GET /health/live` | 无 | 进程存活 |
| `GET /health/ready` | 无 | 依赖就绪 |
| `GET /internal/metrics` | Admin Key | Prometheus |

**Liveness Body**：`{"status":"alive"}`，HTTP `200`。

**Readiness Body**（示例形状；`checks` 键名固定）：

```json
{
  "status": "ready",
  "checks": {
    "redis": "ready",
    "mongodb": "ready",
    "neo4j": "ready",
    "elasticsearch": "ready",
    "kafka_producer": "ready",
    "migrations": "ready",
    "embedding": "ready"
  }
}
```

- 任一 **阻塞** 项为 `not_ready` → 顶层 `status=not_ready`，HTTP `503`。
- **阻塞项**：`redis`、`mongodb`、`neo4j`、`elasticsearch`、`kafka_producer`、`migrations`。
- **非阻塞项**：`embedding`（单独暴露；总体可为 `ready` 而 embedding 为 `not_ready`）。
- 响应 **不得** 含连接 URI、主机、端口、异常堆栈、内部错误字符串。
- `migrations`：`001_initial_mongodb`、`002_initial_neo4j`、`003_elasticsearch_memory_v1`、`004_initial_kafka_topics` 均存在 Record。
- `elasticsearch`：版本匹配 + Alias/Mapping 兼容（§2.2.4 / DEV-004）。

**本任务不宣称**：Compose 对 `memory-api` 增加 `healthcheck`（可后续 OPS）；Worker Readiness；完整 Embedding `/v1/embeddings` 向量探针（属 §3.10.8 TEI Readiness，非 memory-api 阻塞项）。

### 8.6 指标（§3.27）

- 路径：`/internal/metrics`；仅 Admin Key。
- 必须注册（名称一致）：`http_requests_total`、`http_request_duration_seconds`、`compression_total`、`extraction_tasks_total`、`extraction_task_duration_seconds`、`retrieval_requests_total`、`retrieval_duration_seconds`、`kafka_consumer_lag`（可选暴露，无数据时可不出现 series）、`consolidation_runs_total`。
- 本任务 HTTP 中间件至少写入 `http_*` 两个指标；其余允许保持 0 series 直至业务任务接入。

### 8.7 Lifespan 与优雅关闭（§3.7 / §3.25）

- 启动顺序：Settings → Logging → Clients → Producer start →（可选启动探针）→ 接受流量。
- 关闭：`timeout_graceful_shutdown=450`；逆序释放；Signal 处理遵循 Uvicorn/FastAPI 标准（不在 handler 内做重 DB 逻辑）。
- 配置非法 → 启动失败，非零退出。

### 8.8 与 DEV-004 Migration 的边界

- Readiness **只读** `infra_schema_migrations`；**不**调用 `scripts.migrate`。
- 不得修改 Migration 文件与 Runner。

### 8.9 测试策略摘要

| 层级 | 文件 | 要点 |
|---|---|---|
| Unit | `test_api_key_security.py` | `compare_digest` 路径；timing-safe |
| Unit | `test_error_envelope.py` | 形状、字段、request_id |
| Unit | `test_request_id.py` | 透传/生成/非法 |
| Contract | `test_api_shell_contract.py` | TestClient + lifespan override/fake state；401/403/422；metrics Content-Type；health 无 Key |
| Contract | `test_api_shell_contract.py` | 日志捕获：鉴权失败不输出 Key 子串 |
| Integration（可选） | `test_api_readiness.py` | test 栈 migrate 后 ready；未 migrate 时 migrations not_ready |
| 修订 | `test_entrypoints_import.py` | 见 §8.10 |

### 8.10 Entrypoint 测试修订

- 保留三模块 import 成功。
- 将 `test_entrypoint_module_run_exits_nonzero_when_not_ready` **仅针对** `extraction_worker` 与 `consolidation_worker` 保留 `not ready` 断言。
- 对 `memory_system.entrypoints.api`：新增 `test_api_entrypoint_exits_nonzero_without_env`（缺 env 时非零）；**不再**要求 api 模块永久 `not ready`。

## 9. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 无跨存储业务写入；Lifespan 创建客户端为进程级 |
| 幂等 | 适用（只读探针） | Health 探针只读；重复请求不改变存储 |
| 并发 | 适用 | 每 worker 单进程；AppState 只读探针可并发；Kafka Producer 单实例 |
| 版本冲突 | 不适用 | 无业务资源版本 |
| 用户隔离 | 不适用 | 本任务无业务资源路由；日志中 `user_id` 仅预留字段 |
| 部分失败 | 适用（Readiness） | 分项 `not_ready` 聚合；Lifespan 启动任一连线失败则整体启动失败 |
| 进程异常恢复 | 适用 | 依赖 Compose 重启；Migration 状态以 Mongo Record 为准；无本地可变业务状态 |

## 10. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| API Key 比较相等/不等 | 布尔结果；使用 `secrets.compare_digest` 代码路径 |
| API Key 长度不同 | 仍走安全比较；不抛异常泄露 |
| `build_error_response` | 含 `success:false`、嵌套 `error`、`request_id` |
| Request ID 合法透传 | 响应 Header/Body 一致 |
| Request ID 缺失 | 生成 UUID4 格式 |
| Request ID 非法字符串 | 丢弃并生成新 ID |
| Metrics 注册 | 指标名存在于 REGISTRY |

### Contract Test

| 场景 | 预期 |
|---|---|
| `GET /health/live` 无 Key | 200；`status=alive` |
| `GET /health/ready` 无 Key（fake 全 ready） | 200；`status=ready` |
| `GET /internal/metrics` 无 Key | 401；`invalid_api_key` |
| `GET /internal/metrics` 错误 Key | 401；`invalid_api_key` |
| `GET /internal/metrics` 普通 Key | 403；`forbidden` |
| `GET /internal/metrics` Admin Key | 200；Prometheus 文本；含 `http_requests_total` 类型 |
| 触发 `422`（测试用临时路由或无效 query） | `validation_error`；统一包络；非 FastAPI 默认 |
| 错误响应含 `X-Request-ID` | Header 与 Body 匹配 |
| 鉴权失败日志 | 不包含 `MEMORY_API_KEY` 明文子串 |

### Integration Test（可选，非阻塞 P2）

| 场景 | 预期 |
|---|---|
| test 栈 migrate 后启动 TestClient/HTTP 探针 | `ready` 阻塞项均为 `ready` |
| 未 migrate 的干净 ES/Mongo | `migrations` 为 `not_ready`；HTTP 503 |

### E2E Test

不适用（无业务链路）。

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| Lifespan Redis 连接失败 | 进程启动失败；非零退出 |
| Readiness 单依赖失败 | 对应 `checks.*=not_ready`；总体 503 |
| 并发 10 次 `/health/live` | 均 200；无竞态崩溃 |

## 11. 验收标准

- [x] 白名单文件齐套；黑名单无触碰
- [x] `uv run python -m memory_system.entrypoints.api` 在合法 test env 下可启动（人工或测试验证）；非法 env 非零退出
- [x] `GET /health/live`、`GET /health/ready`、`GET /internal/metrics` 行为符合 §8
- [x] 鉴权：401 `invalid_api_key`；Admin 路由 403 `forbidden`；常量时间实现存在
- [x] 错误包络与 `validation_error` 契约测试通过
- [x] structlog JSON 输出含最小字段；敏感信息断言通过
- [x] Prometheus 指标名与 §3.27 一致；`http_*` 有样本
- [x] `uv run pytest` 相关测试全绿；`uv run ruff check .`；`uv run mypy src tests scripts` 通过
- [x] 未开始 DEV-006 / STM / RET 业务实现
- [ ] Review 无 P0/P1

## 12. 风险与阻塞项

| 类别 | 说明 |
|---|---|
| 设计文档冲突 | Health URL 规格未写明——本计划 §8.5 已冻结；若与人肉规格解释冲突须 STOP + open_issues |
| 当前代码冲突 | DEV-001 部分 `__init__.py` 未落盘；本任务仅补 api/observability/security 范围 |
| 前置任务 | DEV-002/004 已完成 |
| 未批准依赖 | 禁止新增 motor 等；使用现有 pymongo async / redis / neo4j / es / aiokafka |
| API/Schema 变化 | 仅运维路径冻结；业务 `/api/v1` 不在本任务 |
| Lifespan 过重 | 避免在本任务实现业务 Repository；探针保持最小 |
| 测试脆弱性 | Integration 依赖 compose.test；标为可选 |
| entrypoint 测试 | 必须修订 `test_entrypoints_import.py` 避免与 DEV-005 冲突 |

## 13. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/DEV-005-api-shell-auth-request-id-logging-metrics"
release_phases:
  PLAN_LANDING:
    allowed_on: main
    commands:
      - "git pull --ff-only"
      - "git add 02_开发管理/tasks/DEV-005-api-shell-auth-request-id-logging-metrics.md 02_开发管理/progress.md 02_开发管理/master_plan.md"
      - "git commit -m \"docs(plan): add DEV-005 api shell auth request id logging metrics plan\""
      - "git push origin main"
      - "git checkout -b feat/DEV-005-api-shell-auth-request-id-logging-metrics"
  IMPLEMENTATION_RELEASE:
    allowed_on: feat/DEV-005-api-shell-auth-request-id-logging-metrics
    commands:
      - "git add <whitelist paths only>"
      - "git commit -m \"feat(api): add fastapi shell auth observability and health endpoints\""
      - "git push -u origin feat/DEV-005-api-shell-auth-request-id-logging-metrics"
      - "gh pr create --title \"feat(api): DEV-005 API shell, auth, request ID, logging and metrics\" --body \"...\""
      - "optional: docs(status): record on feat"
    forbidden:
      - "git push origin main"
      - "git commit on main"
  POST_MERGE_CLEANUP:
    allowed_on: main
    when: "PR MERGED"
    commands:
      - "git fetch && git pull --ff-only"
      - "docs(status): complete DEV-005 on main"
      - "git branch -d feat/DEV-005-api-shell-auth-request-id-logging-metrics"
      - "git push origin --delete feat/DEV-005-api-shell-auth-request-id-logging-metrics"
expected_commits:
  - "docs(plan): add DEV-005 api shell auth request id logging metrics plan"
  - "feat(api): add fastapi shell auth observability and health endpoints"
  - "docs(status): record DEV-005 implementation commit and PR"
  - "docs(status): complete DEV-005 after PR merge"
out_of_scope_changes:
  - "STM/Retrieval/Extraction 路由"
  - "DEV-006 TEI Client"
  - "settings/pyproject/compose/migrate 变更"
  - "五命令与 Orchestrator 正文"
```

## 14. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

（空）

## 15. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-08 11:20 UTC | 规划 | 创建 Task Plan；progress/master_plan 规划态 | 未实施 | 无 |
| 2026-08-08 11:35 UTC | 实施 | API 壳、鉴权、Request ID、structlog、Prometheus、Health、entrypoint | Unit 30 / Contract 12 / ruff / mypy 全绿 | Integration 可选跳过（无运行中 API） |
| 2026-08-08 19:45 UTC | P1 修复 | `metrics.py` 注册 `kafka_consumer_lag` Gauge 并加入 `ALL_METRICS`；contract 断言 `ALL_METRICS` 含该指标 | Contract 12 / ruff / mypy 全绿 | 无 series 时不强制 scrape 文本出现 |
| 2026-08-08 19:50 UTC | IMPLEMENTATION_RELEASE | 实现 Commit + push feat + PR #12；本 docs(status): record | 门禁已绿 | implementation=`d32ddc70b5b8b772e9f27a84988b778c226dd2c5`；仅 feat；等待人工 Merge |

## 16. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/api/**` | 已创建（app、middleware、errors、routes） |
| `src/memory_system/infrastructure/runtime.py` | 已创建 |
| `src/memory_system/infrastructure/security/api_key.py` | 已创建 |
| `src/memory_system/observability/**` | 已创建 |
| `src/memory_system/entrypoints/api.py` | 已修改（Uvicorn 启动） |
| `tests/unit/test_api_key_security.py` 等 | 已创建/修订 |
| `tests/contract/test_api_shell_contract.py` | 已创建 |
| `tests/integration/test_api_readiness.py` | 已创建（可选） |
| `README.md` | 已更新 memory-api 本地启动说明 |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit/test_api_key_security.py tests/unit/test_error_envelope.py tests/unit/test_request_id.py tests/unit/test_entrypoints_import.py -q` | PASS (18) |
| Contract | `uv run pytest tests/contract/test_api_shell_contract.py -q` | PASS (12) |
| Integration | `uv run pytest tests/integration/test_api_readiness.py -q` | 可选；未阻塞 |
| E2E | — | N/A |
| Ruff | `uv run ruff check .` | PASS |
| Mypy | `uv run mypy src tests scripts` | PASS |

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
branch: feat/DEV-005-api-shell-auth-request-id-logging-metrics
plan_commit: 2548c9a5f99c833e6347b93484c562e86f25f605
implementation_commit: d32ddc70b5b8b772e9f27a84988b778c226dd2c5
implementation_commit_message: "feat(api): add fastapi shell auth observability and health endpoints"
pr: "#12"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/12"
pr_state: OPEN
pr_base: main
pr_head: feat/DEV-005-api-shell-auth-request-id-logging-metrics
status_record_commit_committed: null  # record commit SHA filled after push
status_record_commit_committed_message: "docs(status): record DEV-005 implementation commit and PR"
status_record_commit_completed: null  # filled after docs(status): complete commit
feature_branch_deleted: pending
```

### 最终状态

`committed`（PR #12 OPEN；等待人工 Merge；`next_action`→WAITING_FOR_PR_MERGE）
