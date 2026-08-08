# DEV-006 TEI Embedding Client + Token Budget（共享）

## 1. 任务信息

```yaml
task_id: DEV-006
task_name: TEI Embedding Client + Token Budget（共享）
status: approved
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§3.2 巩固进程与基础设施边界（EmbeddingClient Protocol、共享 httpx）"
  - "§3.10 本地 Embedding 部署方式（§3.10.1–3.10.9；尤其 §3.10.6 输入/批量/一致性）"
  - "§2.2.6 Query 标准化与 Embedding（EmbeddingClient、TEIEmbeddingClient 规则）"
prerequisites:
  - "DEV-001 completed（httpx 依赖；infrastructure 包）"
  - "DEV-002 completed（EmbeddingSettings、embedding_effective_runtime_mode、embedding_client_total_token_budget、embedding_http_client）"
  - "DEV-003 completed（TEI Compose、start_embedding.sh、lock_tei_images.sh、versions.lock.env）"
  - "DEV-005 completed（AppState 共享 httpx.AsyncClient；check_embedding 占位 GET /health）"
  - "实施编码前须 PLAN_APPROVED；本轮仅规划，不得实施"
branch: "feat/DEV-006-tei-embedding-client-token-budget"
created_at: "2026-08-08 20:06 UTC"
updated_at: "2026-08-08 20:30 UTC"
approval_gates:
  planning_docs: "Round 1 PLAN_REJECTED（MF-001/MF-002）；Amendment 001 已吸收；等待 Round 2 Plan Review → PLAN_APPROVED"
  implementation_plan: "status=planned；Round 2 PLAN_APPROVED 前不得实施或 PLAN_LANDING"
```

## 2. 任务目标

本任务交付 **EXT-007 与 Retrieval 共享** 的 TEI HTTP Embedding 适配层，严格对齐规格 §2.2.6、§3.10.6。

完成后应具备：

1. **`EmbeddingClient` Protocol** 与 **`EmbeddingResult`** 应用内部 Contract（`model`、`dimension=1024`、`vectors` 顺序与输入一致）。
2. **`TEIEmbeddingClient`**：通过共享 `httpx.AsyncClient` 调用同一 TEI 实例的 `POST /tokenize` 与 `POST /v1/embeddings`；**不得**依赖 TEI Python SDK。
3. **1024 Token 硬限制**：每条文本在 `/v1/embeddings` 前经 `/tokenize` 精确计数；单条 `> 1024` → `embedding_input_too_long`；**禁止**静默截断；**禁止**向 TEI 发送空字符串。
4. **CPU/GPU Token Budget 确定性分批**：First-Fit-In-Order；`len(sub_batch) <= 64` 且 `sum(token_count) <= EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET`（CPU `4096` / GPU `16384`）；子批次失败则整次 `embed` 失败，不返回部分向量。
5. **输出校验**：配置模型 `BAAI/bge-m3`；返回条数与输入一致；每向量 **严格 1024** 维；拒绝零向量、NaN、Inf；应用层 **不** 再次 L2 Normalize。
6. **工厂/构造**：`create_embedding_client(settings, http_client)`（或等价）供 memory-api / extraction-worker 后续复用。
7. **测试**：Contract（Fake TEI，无真实容器）；Integration（真实 TEI **CPU 模式发布阻塞**）；一致性 Fixture（≥20 条中英文；CPU 向量维度/范数/有限性；GPU 对比可选非阻塞）。
8. **（窄范围）Readiness 探针升级**：将 `runtime.check_embedding` 从 GET `/health` 升级为通过 `TEIEmbeddingClient` 对固定短文本执行 embed，确认 1024 维有限向量（§3.10.8 #2）；仍 **非** memory-api Readiness 阻塞项。

**边界声明**：本任务 **不** 实现 Retrieval Vector 通道降级逻辑（`vector_skipped_query_too_long` / `embedding_failed` Warning）、**不** 实现 EXT-007 索引同步、**不** 接线 extraction-worker Lifespan。

## 3. 非目标

- Elasticsearch 写入、BM25、RRF、图谱扩展、Retrieval HTTP API（RET-*）。
- Extraction 索引同步、`core_search_text` 构建、`memory_search_text_too_long` 业务路径（EXT-007）。
- 修改 Embedding **模型**、Revision、TEI 引擎版本、镜像 Digest、`versions.*`。
- 修改 `compose*.yaml`、`Dockerfile`、`scripts/start_embedding.sh`、`scripts/lock_tei_images.sh`、`scripts/compose.sh`（DEV-003 已交付）。
- 修改 `settings/models.py` 字段/默认值/导入结构（DEV-002 Contract）；**窄例外（Amendment 001 MF-001）**：仅 `_validate_cross_field_constraints` 追加一行 `validate_embedding_runtime(self, info)`；**允许**在 `validators.py` **追加** `validate_embedding_runtime`（§3.10.5/§3.10.6，不改动义）。
- 修改 `.env.example`、`configs/*.yaml`（除非 Plan Review 认定缺键并走 Amendment）。
- STM-*、Worker entrypoint 启动、Kafka 消费、Neo4j 写事务。
- OpenTelemetry；自定义 Embedding HTTP Wrapper。
- 运行时 GPU/CPU 热切换、请求级路由、动态修改 Token Budget。
- `domain/**`、`application/**` 业务编排层（本任务仅 `infrastructure/embedding/**`）。
- 五命令正文、Orchestrator、permissions 变更。

## 4. 当前代码状态

### 4.1 已存在代码

- **DEV-002**：`EmbeddingSettings`（`max_client_batch_size=64`、`per_input_token_limit=1024`、cpu/gpu budget）；顶层 `embedding_effective_runtime_mode`、`embedding_client_total_token_budget`；`embedding_http_client` 超时；`memory_retrieval.embedding_*` 元数据。
- **DEV-003**：`compose.embedding.{cpu,gpu}.yaml`（`AUTO_TRUNCATE=false`、`max-batch-tokens` 8192/16384）；`start_embedding.sh` 写入 `.runtime/embedding.env`（mode + budget）；`lock_tei_images.sh`；契约测试覆盖 Compose/Wrapper。
- **DEV-005**：`AppState.http_client`（共享 `httpx.AsyncClient`）；`check_embedding()` 仅 GET `{base_url}/health`；Readiness 中 `embedding` **非阻塞**。
- **configs/base.yaml**：`embedding.cpu/gpu.client_total_token_budget` 与规格一致。

### 4.2 可复用组件

- `get_settings()` 与 `tests/unit/test_settings_validation.py` 合法 env fixture。
- `AppState` 与 `create_app_state()` 中的共享 `httpx.AsyncClient`。
- DEV-003 Integration 模式：`compose.sh --stack=test --embedding=cpu` + `start_embedding.sh`。
- `tests/unit/test_compose_wrapper_contract.py`、`tests/contract/test_compose_config_contract.py` 中 embedding 栈启动语义。

### 4.3 当前缺失

- **整个 `src/memory_system/infrastructure/embedding/` 树**（Protocol、TEI 适配、分批、错误类型）。
- **`EmbeddingResult`** 与 **`embedding_input_too_long`** 异常/错误码。
- **Contract Fake TEI** 测试夹具与 HTTP 录制/模拟层。
- **Integration** 真实 TEI 测试（CPU 发布阻塞）。
- **≥20 条**一致性 Fixture 文本文件。
- **`validators.py`** 中 `embedding_effective_runtime_mode` ↔ `embedding_client_total_token_budget` 交叉校验（规格要求 compose `current` 硬失败；Settings 层宜对称校验）。

### 4.4 与技术规格不一致之处

- §2.2.6 / §3.10.6 要求 `/tokenize` + `/v1/embeddings` 与 Token Budget 分批 — **尚未实现**。
- §3.10.8 Readiness 建议 `/v1/embeddings` 短文本探针 — DEV-005 仅用 `/health`；本任务 **窄范围** 升级 `check_embedding`，不扩大 Readiness 阻塞范围。

### 4.5 前置任务检查

| 前置 | 状态 | 证据 |
|---|---|---|
| DEV-001 | completed | PR #1 |
| DEV-002 | completed | PR #5 |
| DEV-003 | completed | PR #6；TEI lock validate passed |
| DEV-005 | completed | PR #12 MERGED `a68d951` |
| Git | `main` @ `b340f3f` 干净 | 用户只读验证 + `git status` 空 |

## 5. 实现方案

### Step 1 — 包结构与内部 Contract 类型

- **文件**：
  - `src/memory_system/infrastructure/embedding/__init__.py`
  - `src/memory_system/infrastructure/embedding/types.py`
  - `src/memory_system/infrastructure/embedding/errors.py`
- **类型**：
  - `EmbeddingResult`：`model: str`、`dimension: int`、`vectors: list[list[float]]`
  - `EmbeddingClient`：`Protocol`，`async def embed(self, texts: list[str]) -> EmbeddingResult`
  - `EmbeddingError` 基类；`EmbeddingInputTooLongError`（`code="embedding_input_too_long"`）；`EmbeddingServiceError`；`EmbeddingValidationError`（维度/NaN/Inf/模型不匹配）
- **规则**：Domain/Application **不得**依赖 TEI 原生 JSON Schema；仅 `infrastructure/embedding` 解析 TEI 响应。

### Step 2 — Token 计数（`/tokenize`）

- **文件**：`src/memory_system/infrastructure/embedding/tei_transport.py`（或合入 `tei_client.py`）
- **行为**：
  - `POST {base_url}/tokenize`，Body 对齐 TEI `1.9.3` 原生 API（`inputs` 为字符串列表）。
  - 解析响应得到与 `inputs` **同序** 的 `token_count` 列表（每条 `int`）。
  - 超时：读 `settings.embedding_http_client`；连接可复用传入 `httpx.AsyncClient` 的 pool，单次请求 timeout 覆盖 embedding 读超时。
  - HTTP 非 2xx / 解析失败 → `EmbeddingServiceError`；**不**伪造计数。
- **日志**：禁止记录完整待嵌入文本（§3.10.8 #9）。

### Step 3 — 确定性分批（First-Fit-In-Order）

- **文件**：`src/memory_system/infrastructure/embedding/batching.py`
- **函数**：`split_into_batches(token_counts: list[int], *, max_batch_size: int, max_batch_tokens: int) -> list[list[int]]`
  - 输入为与原始 `texts` 对齐的下标序列；返回每个子批次的 **原始下标列表**。
  - 算法：从第一条累加；下一条使 `len>max_batch_size` 或 `sum>max_batch_tokens` 时切开新批；**禁止**重排以提高装箱率（§3.10.6 #6）。
- **预算来源**：`settings.embedding_client_total_token_budget`（**运行时**自 `.runtime/embedding.env` 注入，CPU `4096` / GPU `16384`）；**不得**从请求动态修改（§3.10.6 #8）。
- **条数上限**：`settings.embedding.max_client_batch_size`（64）为单次 `embed()` 接受的 **总输入**上限；子批次同样 `<= 64`。

### Step 4 — `TEIEmbeddingClient.embed` 主路径

- **文件**：`src/memory_system/infrastructure/embedding/tei_client.py`
- **输入校验**（在 `/tokenize` 之前）：
  - `len(texts) == 0` → `EmbeddingValidationError` 或 `ValueError`（禁止空批次调用 TEI）。
  - `len(texts) > 64` → 拒绝（可在 Client 层或调用方；Client 层 **必须**拒绝 `> 64`）。
  - 任一 `text == ""` → 拒绝，**不**调用 TEI（§2.2.6 #7）。
- **流程**：
  1. `/tokenize` 全部文本。
  2. 任一 `token_count > settings.embedding.per_input_token_limit`（1024）→ 抛 `EmbeddingInputTooLongError`；**不**调用 `/v1/embeddings`。
  3. `split_into_batches` 使用 `embedding_client_total_token_budget`。
  4. 对每个子批次：`POST /v1/embeddings`，OpenAI-compatible Body：`model`、`input`（子批次文本子集）、`encoding_format: "float"`。
  5. 校验响应 `model` 为 `BAAI/bge-m3`（或 `settings.embedding.model_id` / `memory_retrieval.embedding_model` 一致）；`data` 条数与子批次一致；按 `index` 或顺序合并向量。
  6. 每向量：`len==1024`；无 NaN/Inf；非全零（§2.2.6 #4、#6）。
  7. 按 **原始下标** 合并为 `EmbeddingResult`；任子批次失败 → 整次失败。
- **Normalization**：**禁止**应用层 L2 Normalize（§2.2.6 #5）。

### Step 5 — 工厂与 Settings 交叉校验

- **文件**：
  - `src/memory_system/infrastructure/embedding/factory.py` — `def create_embedding_client(settings: Settings, http_client: httpx.AsyncClient) -> EmbeddingClient`
  - `src/memory_system/settings/validators.py` — 新增 `validate_embedding_runtime(settings, info)`：
    - `cpu` → `embedding_client_total_token_budget == embedding.cpu.client_total_token_budget`（4096）
    - `gpu` → `embedding_client_total_token_budget == embedding.gpu.client_total_token_budget`（16384）
    - 不匹配 → `ValueError`（与 compose `current` 硬失败语义对齐）
  - `src/memory_system/settings/models.py` — **窄例外（MF-001）**：
    - 在 `validators` 导入块追加 `validate_embedding_runtime`
    - 在 `_validate_cross_field_constraints` **仅追加一行**：`validate_embedding_runtime(self, info)  # type: ignore[arg-type]`
    - **禁止**：改字段/默认值/`settings_customise_sources`/`required_env_keys`/`get_settings`；禁止重构或改动其他 validator 调用顺序语义
- **禁止**：除上述一行与对应 import 外修改 `models.py`；修改无关 settings 行为。

### Step 6 — Readiness 探针窄升级 + API Shell Contract 同步

- **文件（实现）**：`src/memory_system/infrastructure/runtime.py`（**仅** `check_embedding` 及相关私有辅助）
- **行为**：使用 `create_embedding_client` + 固定短文本（如 `"health probe"`，**不得**为空）；`embed([probe])`；成功且 `len(vectors[0])==1024` 且有限 → `ready`；否则 `not_ready`。
- **不变**：`embedding` 仍 **非** `BLOCKING_READINESS_CHECKS` 成员；不修改 `aggregate_readiness_status` 阻塞集合。
- **文件（Contract 测试，必改 MF-002）**：`tests/contract/test_api_shell_contract.py`
  - **修改原因**：`check_embedding` 从 `http_client.get("{base_url}/health")` 升级为 `TEIEmbeddingClient.embed` 探针；现有 `fake_app_state` 仅 mock `http_client.get` 返回 200，升级后 readiness 路径不再调用 GET `/health`，现有 mock **不足**会导致 `embedding` 误判 `not_ready` 或测试挂起。
  - **Mock 策略**（二选一，Developer 择一实现，**不得**弱化断言）：
    1. **推荐**：在 `fake_app_state` fixture 中 `monkeypatch` `memory_system.infrastructure.embedding.factory.create_embedding_client`，返回 stub `EmbeddingClient`，其 `embed` 为 `AsyncMock` 返回合法 `EmbeddingResult`（`model="BAAI/bge-m3"`、`dimension=1024`、单条 1024 维有限向量）。
    2. **备选**：保留真实 `create_embedding_client`，在 `http_client` 上 mock `post`，按 URL 后缀区分 `/tokenize` 与 `/v1/embeddings`，返回 TEI 兼容 JSON（须与 Contract Fake TEI 响应形状一致）。
  - **须锁定的 Contract**（**不得**删除或降级）：
    - `test_health_ready_without_api_key_all_ready`：`payload["status"] == "ready"` 且 `payload["checks"]["embedding"] == "ready"`（全绿路径）。
    - **新增或补强**：embed 探针失败时 `checks["embedding"] == "not_ready"`，但 `payload["status"]` 仍为 `"ready"`（Embedding 非阻塞，§3.16 / DEV-005 Contract）。
    - 其余鉴权/metrics/错误包络/structlog 用例 **不变**；不得将 embedding 加入阻塞集合断言。
  - **禁止**：直接 `patch(check_embedding)` 跳过 embed 逻辑（会弱化 §8.9 探针 Contract）；不得删除 `embedding == "ready"` 断言改为仅测 overall status。

### Step 7 — 测试与 Fixture（见 §8、§10）

- Contract Fake TEI；Unit 分批/校验；Integration 真实 CPU TEI。

## 6. 文件变更清单（精确白名单）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/infrastructure/embedding/__init__.py` | 创建 | 包导出 |
| `src/memory_system/infrastructure/embedding/types.py` | 创建 | `EmbeddingResult`、`EmbeddingClient` Protocol |
| `src/memory_system/infrastructure/embedding/errors.py` | 创建 | 错误类型与 `embedding_input_too_long` |
| `src/memory_system/infrastructure/embedding/batching.py` | 创建 | First-Fit-In-Order 分批 |
| `src/memory_system/infrastructure/embedding/tei_client.py` | 创建 | `TEIEmbeddingClient` |
| `src/memory_system/infrastructure/embedding/factory.py` | 创建 | `create_embedding_client` |
| `src/memory_system/infrastructure/runtime.py` | 修改 | `check_embedding` 升级为 embed 探针 |
| `src/memory_system/settings/validators.py` | 修改 | 新增 `validate_embedding_runtime` |
| `src/memory_system/settings/models.py` | 修改（窄例外 MF-001） | `_validate_cross_field_constraints` 追加一行 `validate_embedding_runtime`；禁止其他改动 |
| `tests/fixtures/embedding_consistency_texts.json` | 创建 | ≥20 条中英文 Fixture |
| `tests/contract/helpers/tei_fake.py` | 创建 | Fake TEI HTTP 处理器/Transport |
| `tests/contract/test_tei_embedding_client_contract.py` | 创建 | Contract（Fake TEI） |
| `tests/unit/test_embedding_batching.py` | 创建 | 分批算法 Unit |
| `tests/unit/test_tei_embedding_client_unit.py` | 创建 | Mock Transport Unit |
| `tests/integration/test_tei_embedding_client_integration.py` | 创建 | 真实 TEI Integration（CPU 阻塞） |
| `tests/unit/test_settings_validation.py` | 修改 | 追加 budget/mode 校验用例（若改 validators） |
| `tests/contract/test_api_shell_contract.py` | **必改**（MF-002） | `check_embedding` embed 探针后更新 mock；锁定 embedding ready/not_ready 与 overall readiness 非阻塞语义 |
| `02_开发管理/tasks/DEV-006-tei-embedding-client-token-budget.md` | 创建/更新 | 本 Task Plan |
| `02_开发管理/progress.md` | 修改 | 规划态字段 |
| `02_开发管理/master_plan.md` | 修改 | DEV-006 登记 + CHANGE |

**可选（仅当 Contract 测试需修订且属白名单内）**：

| `tests/unit/test_settings_loader.py` | 修改 | 与 validation 用例对齐 |

## 7. 文件黑名单（禁止本任务创建或修改）

| 路径/范围 | 原因 |
|---|---|
| `src/memory_system/domain/**`、`application/**` | 业务任务 |
| `src/memory_system/api/**`（除黑名单未列的 `runtime` 外） | DEV-005 范围 |
| `src/memory_system/observability/**` | DEV-005 |
| `src/memory_system/entrypoints/**` | 后续 Worker 任务 |
| `src/memory_system/settings/loader.py`、`sources.py` | DEV-002 Contract |
| `src/memory_system/settings/models.py`（**窄例外外**） | DEV-002 Contract；**仅允许** `_validate_cross_field_constraints` 追加一行 `validate_embedding_runtime` + 对应 import；禁止字段/默认值/结构变更 |
| `configs/**`、`.env.example` | DEV-002；默认不改 |
| `compose*.yaml`、`Dockerfile`、`versions.*` | DEV-003 |
| `scripts/**`（migrate、compose、embedding、preflight、lock） | DEV-003/004 |
| `pyproject.toml`、`uv.lock` | 依赖已满足 |
| `tests/conftest.py` | DEV-001 约定 |
| STM-*、RET-*、EXT-* 业务测试与实现 | 禁止提前 |
| `.cursor/**`、五命令正文 | DEV-OPS |
| `.env`、Secret、模型缓存数据 | 永不提交 |

## 8. 关键行为规格（硬性合同）

### 8.1 EmbeddingClient 逻辑 Contract（§2.2.6）

| 字段/规则 | 要求 |
|---|---|
| 输入 | `texts: list[str]`，单次 `1..64` 条 |
| 输出 `model` | `BAAI/bge-m3`（与配置一致） |
| 输出 `dimension` | `1024` |
| 输出 `vectors` | 与输入 **同序**；每向量 **恰好 1024** `float` |
| 空字符串 | **禁止**发送至 TEI；Client 层拒绝 |
| L2 Normalize | **禁止**应用层再次归一化 |
| TEI Response | 仅 Infrastructure 层解析；上层只见 `EmbeddingResult` |

### 8.2 `/tokenize` 与 1024 Token 硬限制（§2.2.6 #3、§3.10.6 #1–2）

| 场景 | 行为 |
|---|---|
| 调用 `/v1/embeddings` 前 | **必须先** `/tokenize` 全部输入 |
| 单条 `token_count > 1024` | 抛 `EmbeddingInputTooLongError`；`code=embedding_input_too_long`；**不**调用 `/v1/embeddings` |
| 单条 `token_count == 0`（空文本 tokenize 结果） | 视为非法输入；**不**调用 `/v1/embeddings` |
| `AUTO_TRUNCATE=false` | 依赖 DEV-003 TEI 配置；Client **不得**静默截断补救 |
| 日志 | **不得**记录完整待嵌入文本 |

### 8.3 CPU/GPU Token Budget 分批（§3.10.6 #4–8）

| 模式 | `EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET` | 子批次 `sum(token_count)` 上限 |
|---|---|---|
| `cpu` | `4096` | `<= 4096` |
| `gpu` | `16384` | `<= 16384` |

| 规则 | 要求 |
|---|---|
| 子批次条数 | `len(sub_batch) <= 64` |
| 算法 | **First-Fit-In-Order**；禁止重排 |
| 动态预算 | **禁止**按请求/GPU 利用率/延迟修改 |
| 子批次失败 | 整次 `embed` 失败；**不**返回部分向量 |
| 合并顺序 | 最终 `vectors[i]` 对应原始 `texts[i]` |

**分批示例（CPU，budget=4096）**：输入 token 序列 `[800, 800, 800, 800, 800]`（5 条）→ 批 1 `[800,800,800,800]`（3200），批 2 `[800]`；**不得**为装箱把第 5 条提前。

### 8.4 `/v1/embeddings` HTTP Contract

| 项 | 要求 |
|---|---|
| URL | `{EMBEDDING__BASE_URL}/v1/embeddings` |
| Method | `POST` |
| Body | OpenAI-compatible：`model`、`input`（字符串列表）、`encoding_format: "float"` |
| 成功校验 | 记录数 = 子批次大小；`model` 匹配；向量维度 1024 |
| 非法向量 | 零向量、NaN、Inf → `EmbeddingValidationError` |
| HTTP 错误 | 映射为 `EmbeddingServiceError`（上层 Retrieval 后续映射 `embedding_failed`；本任务 Client 只抛异常） |

### 8.5 Query 超长与 Retrieval 边界（§2.2.6 #8）

本任务 **仅** 在 Client 层实现 `embedding_input_too_long`。

| 场景 | 本任务 | 后续 RET-* |
|---|---|---|
| Query `> 1024` Token | Client 抛 `embedding_input_too_long` | 捕获后 `vector_skipped_query_too_long` Warning，BM25 继续 |
| TEI 服务异常 | Client 抛 `EmbeddingServiceError` | 捕获后 `embedding_failed` Warning |

**禁止**在本任务实现 Warning 降级或 BM25 逻辑。

### 8.6 一致性 Fixture（§3.10.6 #10–13）

| 项 | 要求 |
|---|---|
| Fixture 数量 | ≥20 条中英文文本（`tests/fixtures/embedding_consistency_texts.json`） |
| CPU Integration | 维度 1024；L2 Norm ≈ 1；无 NaN/Inf |
| GPU vs CPU Cosine | `>= embedding.consistency.minimum_cosine_similarity`（0.999）；**Integration 可选**；无 GPU 时 `pytest.skip`；**不**降低阈值 |
| 失败后果（规格） | 禁止混写 ES Index — 本任务仅测 Client；不写 ES |

### 8.7 Contract Fake TEI 必覆盖场景（§3.10.6 #15）

| # | 场景 | 预期 |
|---|---|---|
| 1 | 正常 1 条短文本 | `/tokenize` → `/v1/embeddings`；1024 维 |
| 2 | 65 条输入 | Client 拒绝；**零** TEI 调用 |
| 3 | 空字符串输入 | Client 拒绝；**零** TEI 调用 |
| 4 | `/tokenize` 返回 1025 | `embedding_input_too_long`；**无** `/v1/embeddings` |
| 5 | 多批输入（触发 budget 切批） | `/v1/embeddings` 调用次数 = 批次数；顺序保持 |
| 6 | 子批次 `/v1/embeddings` 500 | 整次失败；无部分结果 |
| 7 | 返回 1023 维向量 | `EmbeddingValidationError` |
| 8 | 返回 NaN 向量 | `EmbeddingValidationError` |
| 9 | Fake TEI 对超长直连 `/v1/embeddings` 返回 4xx | Contract 断言 **错误**而非截断成功（绕过 Client 的 TEI 行为） |

### 8.8 Integration 真实 TEI（发布阻塞 CPU）

| 项 | 要求 |
|---|---|
| 前置 | `versions.lock.env` 有效 Digest；`./scripts/start_embedding.sh cpu` 或测试内启动 embedding-service |
| 模式 | **CPU** 为 **发布阻塞** |
| 命令 | `uv run pytest tests/integration/test_tei_embedding_client_integration.py -q` |
| 断言 | embed 短文本；分批场景（构造总 token >4096 的多条）；一致性 Fixture 子集；维度/有限性 |
| GPU 一致性 | 有 A5000 + `start_embedding.sh gpu` 时可跑；**非**阻塞；skip 须显式 reason |
| 时长 | 允许标记 `@pytest.mark.integration`；CI 未就绪时本地发布前人工跑 |

### 8.9 Readiness 探针（窄升级）

| 项 | 要求 |
|---|---|
| 实现 | `check_embedding` 使用 `TEIEmbeddingClient.embed(["…"])`) |
| 阻塞性 | **仍非** Readiness 阻塞项 |
| 与 DEV-005 差异 | 从 GET `/health` 升级为 `/v1/embeddings` 向量探针 |

## 9. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用（无 DB 事务） | Client 单次 `embed` 为逻辑原子：失败不返回部分向量 |
| 幂等 | 适用（只读 TEI） | 相同输入应得相同向量（模型确定性）；Integration 断言稳定性 |
| 并发 | 适用 | 共享 `httpx.AsyncClient`；`TEIEmbeddingClient` 无可变批间状态；并发 `embed` 调用安全 |
| 版本冲突 | 不适用 | 无持久化版本 |
| 用户隔离 | 不适用 | Embedding 无 user_id |
| 部分失败 | 适用 | 子批次失败 → 整次失败；不合并部分向量 |
| 进程异常恢复 | 不适用 | 无本地状态机；依赖 TEI 容器健康 |

## 10. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| `split_into_batches` 边界：空、单条、刚好满 budget、需切批、64 条上限 | 确定性下标分组符合 §8.3 |
| `split_into_batches` 禁止重排 | 输入顺序变化不影响「同内容不同顺序」的切分语义（用 token 序列测） |
| `TEIEmbeddingClient` + MockTransport：正常 embed | `EmbeddingResult` 形状正确 |
| 空列表 / 空字符串 / 65 条 | 拒绝；无 HTTP 调用 |
| token_count=1025 | `EmbeddingInputTooLongError` |
| 错误维度 / NaN / Inf 响应 | `EmbeddingValidationError` |
| `validate_embedding_runtime` cpu/gpu budget | 错 budget 加载 Settings 失败 |

### Contract Test

| 场景 | 预期 |
|---|---|
| Fake TEI §8.7 全表 | 全部通过 |
| `/tokenize` 与 `/v1/embeddings` 调用顺序与次数 | 由 Fake 记录并断言 |
| 超长直连 TEI（不经 Client 长度检查） | Fake 返回错误状态 |
| `test_api_shell_contract`（**必改 MF-002**） | `fake_app_state` mock 适配 embed 探针；`embedding==ready` 全绿；embed 失败时 `embedding==not_ready` 且 overall 仍 `ready`；鉴权/metrics 用例不退化 |

### Integration Test

| 场景 | 预期 |
|---|---|
| CPU 真实 TEI embed 短文本 | 1024 维、有限、Norm≈1 |
| CPU 多批（总 token>4096） | 多次 HTTP 成功；顺序正确 |
| 一致性 Fixture（≥20 条） | 维度/有限性；CPU 阻塞 |
| GPU 同 Fixture Cosine ≥0.999 | 可选；无 GPU skip |

### E2E Test

| 场景 | 预期 |
|---|---|
| — | 本任务 **不适用**（无端到端业务路由） |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| Fake TEI `/v1/embeddings` 超时/500 | `EmbeddingServiceError` |
| 并发 8 路 `embed`（Contract Mock） | 无竞态；结果正确 |

## 11. 验收标准

- [ ] 白名单文件齐套；黑名单无触碰
- [ ] `EmbeddingClient` / `TEIEmbeddingClient` / `EmbeddingResult` 可供 EXT-007 与 RET-* import
- [ ] §8.2–§8.4 行为可通过 Contract 断言验证
- [ ] `embedding_input_too_long` 在 `>1024` Token 时可观测；且无 `/v1/embeddings` 调用
- [ ] CPU Token Budget 分批符合 First-Fit-In-Order（Unit + Contract）
- [ ] Integration CPU 真实 TEI 通过（**发布阻塞**）
- [ ] `uv run pytest tests/unit tests/contract -q` 全绿
- [ ] `uv run ruff check .` 通过
- [ ] `uv run mypy src tests scripts` 通过
- [ ] Review 无 P0/P1
- [ ] **未**开始 STM/EXT/RET 业务任务

## 12. 风险与阻塞项

| 类型 | 说明 |
|---|---|
| 设计文档冲突 | 无已知冲突；Health 仍非阻塞与 §3.16 一致 |
| 当前代码冲突 | DEV-005 `check_embedding` 需窄升级；**必改** `test_api_shell_contract` mock（MF-002 已入白名单） |
| 前置任务 | 均已 completed |
| TEI `/tokenize` 响应格式 | 以 TEI 1.9.3 运行实例为准；Integration 校验；Fake 与真服务对齐 |
| Integration 时长/模型下载 | 首次 CPU TEI 启动可能 >120s；测试须等待 health；依赖 DEV-003 缓存 Volume |
| GPU 一致性 0.999 | 可能需人工验收报告；**禁止** AI 自行降阈值 |
| 热切换 | MVP 禁止；CPU/GPU 一致性测为发布前检查，非运行时切换 |

## 13. Git 计划（NORMAL 三相）

```yaml
branch: "feat/DEV-006-tei-embedding-client-token-budget"
workflow_mode: NORMAL
release_phases:
  PLAN_LANDING:
    allowed_on: main
    commits:
      - "docs(plan): add DEV-006 tei embedding client token budget plan"
    then: "创建 exact feat 分支"
  IMPLEMENTATION_RELEASE:
    allowed_on: feat
    commits:
      - "feat(embedding): add TEI client token budget and contract tests"
      - "docs(status): record DEV-006 implementation commit and PR"
    push: "origin feat only"
    pr: "gh pr create → 人工 Merge"
  POST_MERGE_CLEANUP:
    allowed_on: main
    after: "PR MERGED verified"
    commits:
      - "docs(status): complete DEV-006 after PR merge"
    then: "git branch -d feat/DEV-006-tei-embedding-client-token-budget && git push origin --delete feat/DEV-006-tei-embedding-client-token-budget"
expected_commits:
  - "docs(plan): add DEV-006 tei embedding client token budget plan"
  - "feat(embedding): add TEI client token budget and contract tests"
  - "docs(status): record DEV-006 implementation commit and PR"
  - "docs(status): complete DEV-006 after PR merge"
out_of_scope_changes:
  - "STM/Retrieval/Extraction 业务"
  - "compose/scripts/versions 变更"
  - "settings models 结构变更（窄例外外）"
  - "五命令与 Orchestrator"
```

**NORMAL 人工门**：`PLAN_APPROVED` + Human PR Merge；机械 Git 由 Release Operator 自动调度。

## 14. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-08 UTC |
| 触发 | Round 1 Plan Review：`PLAN_REJECTED`（BLOCKER 0 / MUST_FIX 2）；用户批准 MF-001 方案 A、MF-002 全文；**不做人工覆盖** |
| 范围 | 修订 §3、§5 Step 5–7、§6、§7、§10、§12、§13 `out_of_scope`；不实施代码 |
| status | 保持 `planned`；Round 2 `PLAN_APPROVED` 前 **不得** 改 `approved` |

#### Round 1 审查结论（保留，不得删除）

- **BLOCKER**: 0
- **MUST_FIX**: 2（MF-001、MF-002）
- **SHOULD_FIX**: （本轮无阻塞性 SHOULD_FIX 记入 Amendment）
- **Verdict**: `PLAN_REJECTED`

#### MF-001：`models.py` 窄例外 — **已吸收**（用户批准方案 A）

| 项 | 内容 |
|---|---|
| 问题 | Step 5 要求在 Settings 加载期校验 `embedding_effective_runtime_mode` ↔ `embedding_client_total_token_budget`，但 `validators.py` 交叉校验须由 `models.py` 的 `_validate_cross_field_constraints` 调用；初版白名单禁止改 `models.py`，与 DEV-002 既有模式（`validate_context` 等）矛盾 |
| 方案 A（已批准） | narrowly 将 `src/memory_system/settings/models.py` 加入 §6 白名单；**仅允许**在 `_validate_cross_field_constraints` 增加一行 `validate_embedding_runtime(self, info)` 及对应 import |
| 禁止 | 重构 `models.py`；改字段/默认值/`settings_customise_sources`/`required_env_keys`；改无关 settings 行为 |
| 实现锚点 | `validators.py` 新增 `validate_embedding_runtime`；`models.py` 第 315–321 行区域追加调用，与 `validate_shutdown` 同级 |

#### MF-002：`test_api_shell_contract.py` 必改 — **已吸收**（用户批准）

| 项 | 内容 |
|---|---|
| 问题 | 初版 §6 将 `tests/contract/test_api_shell_contract.py` 标为「仅当需要」；`check_embedding` 升级为 embed 探针后，现有 `fake_app_state` 只 mock `http_client.get` → `/health`，不足以支撑 readiness |
| 修订 | §6 白名单改为 **必改**；Step 6 写明修改原因、mock 策略、须锁定 Contract、禁止弱化断言 |
| 修改原因 | `runtime.check_embedding` 从 GET `/health` 改为 `TEIEmbeddingClient.embed(["health probe"])`；readiness 路径不再依赖 GET mock |
| Mock 策略 | 优先 `monkeypatch create_embedding_client` 返回 stub `EmbeddingClient`（`AsyncMock embed` → 合法 `EmbeddingResult`）；或 mock `http_client.post` 区分 `/tokenize`/`/v1/embeddings` |
| 须锁定 Contract | 全绿：`status==ready` 且 `checks.embedding==ready`；探针失败：`checks.embedding==not_ready` 且 overall `status` 仍 `ready`（非阻塞）；其余 DEV-005 鉴权/metrics/错误包络用例不变 |
| 禁止 | `patch(check_embedding)` 跳过探针；删除 `embedding==ready` 断言；将 embedding 升格为阻塞项 |

#### 修订摘要（before → after）

| ID | 修订前 | 修订后 |
|---|---|---|
| **MF-001** | §6 无 `models.py`；§7 黑名单禁止整个 `models.py`；Step 5 写「禁止修改 models.py 字段定义」 | §6 白名单增加 `models.py`（窄例外）；§7 改为「窄例外外禁止」；Step 5 明确仅一行 `validate_embedding_runtime` + import |
| **MF-002** | §6 `test_api_shell_contract.py`「仅当需要」；Step 6 未列 Contract 测试；§10 无 api_shell 行 | §6 **必改**；Step 6 合并 api_shell mock 策略与 Contract 表；§10 Contract 表增补 api_shell 场景 |
| §12 风险 | 「可能牵动 test_api_shell_contract」 | 明确 **必改** 且已入白名单 |
| §13 out_of_scope | 「settings models 结构变更」 | 增补「窄例外外」 |

#### Round 2 Plan Review（待执行）

- 独立 Plan Reviewer 复审 Amendment 001 全文；预期 `PLAN_APPROVED` 后方可 `approved` + PLAN_LANDING。

## 15. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-08 20:06 UTC | 规划 | 创建 Task Plan；progress/master_plan 规划态 | 未实施 | 无 |
| 2026-08-08 20:30 UTC | Amendment 001 | 吸收 Round 1 MF-001/MF-002；修订 §3/§5/§6/§7/§10/§12/§14 | 未实施 | status 保持 planned；等待 Round 2 |

## 16. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| — | 规划轮未实施 |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | — | 未运行 |
| Contract | — | 未运行 |
| Integration | — | 未运行 |
| E2E | — | N/A |
| Ruff | — | 未运行 |
| Mypy | — | 未运行 |

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
branch: null
plan_commit: null
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`planned`
