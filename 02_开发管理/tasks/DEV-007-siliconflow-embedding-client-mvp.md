# DEV-007 SiliconFlow Embedding Client MVP

## 1. 任务信息

```yaml
task_id: DEV-007
task_name: SiliconFlow Embedding Client MVP
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§2.2.6 Query 标准化与 Embedding（EmbeddingClient Protocol、SiliconFlowEmbeddingClient）"
  - "§2.2.14 memory_retrieval.embedding_provider 默认 siliconflow"
  - "§3.8 SILICONFLOW_API_KEY（SecretStr；仅 siliconflow 必填）"
  - "§3.10.0 MVP 默认 SiliconFlow 托管 BAAI/bge-m3；dim=1024；batch/retry Contract（M1–M11）"
prerequisites:
  - "OI-012 completed（PR #16 MERGED `003fb43`；最小 Spec-OI 已在 main）"
  - "DEV-002 completed（Settings / YAML / .env.example 基础设施）"
  - "DEV-004 completed（ES mapping dims=1024 已落盘）"
  - "DEV-005 completed（共享 httpx.AsyncClient / AppState / Readiness 非阻塞 embedding 探针）"
  - "DEV-006 PAUSED / SUPERSEDED_FOR_MVP；PR #13 OPEN / DO_NOT_MERGE — 禁止触碰"
branch: "feat/DEV-007-siliconflow-embedding-client-mvp"
created_at: "2026-08-09 15:20 UTC"
updated_at: "2026-08-09 16:00 UTC"
approval_gates:
  planning_docs: "本轮 Planner 输出；等待独立 Plan Review → PLAN_APPROVED"
  implementation_plan: "status=planned；未实施；未 PLAN_LANDING"
dev_006_disposition:
  status: "PAUSED / SUPERSEDED_FOR_MVP"
  pr: "#13"
  pr_status: "OPEN / DO_NOT_MERGE"
  must_not: "merge PR #13；访问 DEV-006 dirty worktree；将 PR #13 设计当作 main 事实"
```

## 2. 任务目标

交付 **最小 SiliconFlow 托管 Embedding Client MVP**，使业务层仅依赖既有 `EmbeddingClient` Protocol，默认经 `SiliconFlowEmbeddingClient`（`httpx`，无 SDK）调用 `BAAI/bge-m3` 并返回 **1024 维**向量。

完成后应具备：

1. **`EmbeddingClient` Protocol + `EmbeddingResult` + 最小 `EmbeddingServiceError` 族**（main 当前缺失；本任务创建）。
2. **`SiliconFlowEmbeddingClient`**：`POST /v1/embeddings`；Bearer 鉴权；有序分批（max 32/request）；响应 index 重排；维度/条数校验；有界重试（最多 3 次 HTTP attempt）；脱敏错误与 observability 最小集。
3. **Settings 最小 pivot**：`memory_retrieval.embedding_provider` 默认 `siliconflow`；`SILICONFLOW_API_KEY`（`SecretStr`）；`provider=siliconflow` 缺 key **fail-fast**；`provider≠siliconflow` 不强制 key；非法 provider **fail-closed**；启动时固定 provider（无请求级热切换）。
4. **`create_embedding_client(settings, http_client)`**：`siliconflow` → `SiliconFlowEmbeddingClient`；`local_tei` → **显式 fail-closed**（**不得**静默回退 siliconflow）；完整 `TEIEmbeddingClient` **DEFERRED**（PR #13 / 后续）。
5. **默认 CI**：unit + mocked HTTP contract（M10 全场景）；**无**公网 SiliconFlow。
6. **Opt-in Integration**（M11）：显式 `SILICONFLOW_API_KEY` + enable flag；验证 `dim==1024`；否则 **HALT 报告**（**不改** ES mapping）。

**边界**：不修改 TEI compose / Preflight / OI-011 12g contract；不接线 STM/EXT/RET；不升级 Readiness 为真实 embed 探针（§3.16 Embedding 仍非阻塞；`check_embedding` 保持 GET `/health` 于 `embedding.base_url`）。

## 3. 非目标

- TEI 429 修复、TEI refactor、compose optionalization、preflight 重写。
- 从 PR #13 / DEV-006 feat 合并或搬运 `TEIEmbeddingClient`（**禁止**访问 dirty worktree）。
- 本地 HF tokenizer 子系统；SiliconFlow count-tokens API（官方无对应能力）。
- Provider 热切换；跨 provider float equality benchmark。
- STM / EXT / RET 业务接线；大型 metrics redesign。
- ES mapping 迁移（DEV-004）；`scripts/migrate.py` 修改。
- 修改 `compose*.yaml`、`scripts/**`、`versions.*`。
- 默认 CI 真实 SiliconFlow 公网调用；load test / rate-limit 探测 / quota burn。
- SiliconFlow SDK 默认路径；L2 归一化语义猜测（规格 **UNKNOWN**）。
- `check_embedding` 升级为 `SiliconFlowEmbeddingClient.embed`（留待后续与 provider 感知 Readiness 一并处理）。

## 4. 当前代码状态（main @ `5ec871e` 只读审计）

### 4.1 EmbeddingClient Protocol

| 项 | main 事实 |
|---|---|
| `src/memory_system/infrastructure/embedding/**` | **不存在** |
| `EmbeddingClient` Protocol | **不存在**（规格 §2.2.6 已定义 Contract；代码未落盘） |
| `EmbeddingResult` | **不存在** |
| `create_embedding_client` | **不存在** |

**结论**：DEV-006（PR #13 OPEN）曾规划上述模块，但 **未 merge**；DEV-007 须在 main 上 **从零创建** Protocol/Result/errors/factory/SiliconFlow client，**不得**读取 PR #13 worktree。

### 4.2 TEIEmbeddingClient

| 项 | main 事实 |
|---|---|
| `TEIEmbeddingClient` | **不存在** |
| TEI 基础设施 | **保留**：`compose.embedding.cpu.yaml`（12g）、`scripts/start_embedding.sh`、`scripts/preflight/*`、`tests/unit/test_tei_*`、OI-011 历史证据 |
| `embedding.base_url` | 默认 Compose TEI：`http://embedding-service:80`（`.env.example` / 测试 fixture） |

**结论**：本 MVP **不实现** `TEIEmbeddingClient`；`local_tei` 枚举保留，factory **fail-closed**。

### 4.3 Embedding errors

| 项 | main 事实 |
|---|---|
| `EmbeddingServiceError` | **不存在** |
| 规格错误语义 | `embedding_input_too_long`（TEI 精确 token）；`embedding_failed`（Retrieval 降级）；空字符串禁止发送 |

**结论**：创建最小 `EmbeddingServiceError` 层次，供 Client 与后续 RET 复用；字段含 `code`、`provider`、`status_code`、`trace_id`、`sanitized_message`（**无** key/auth/全文/vectors）。

### 4.4 AppState / shared httpx client

```40:48:src/memory_system/infrastructure/runtime.py
@dataclass
class AppState:
    settings: Settings
    redis: redis.Redis
    mongodb: AsyncMongoClient[Any]
    neo4j: AsyncDriver
    elasticsearch: AsyncElasticsearch
    http_client: httpx.AsyncClient
    kafka_producer: AIOKafkaProducer
```

- `create_app_state` 创建共享 `httpx.AsyncClient`（超时读 `settings.http_client`）。
- `SiliconFlowEmbeddingClient` **必须**注入该共享 client；单请求超时读 `memory_retrieval.embedding_timeout_seconds` 与/或 `embedding_http_client`（实施时二选一为主、另一为上限，须在代码注释标明）。
- `check_embedding`：GET `{embedding.base_url}/health`；**非阻塞** Readiness；与 SiliconFlow API **无关**（本任务不改）。

### 4.5 Settings models / validators

| 字段 / 行为 | main 值 | 与 OI-012 规格差异 |
|---|---|---|
| `memory_retrieval.embedding_provider` default | `"local_tei"` | 规格要求 `"siliconflow"` |
| `configs/base.yaml` `embedding_provider` | `"local_tei"` | 同上 |
| `SILICONFLOW_API_KEY` | **无字段** | 规格 §3.8 要求 |
| `embedding_provider` 枚举校验 | **无** | 须 fail-closed |
| `siliconflow` 缺 key 校验 | **无** | 须 fail-fast |
| `memory_retrieval.embedding_dimension` | `1024` + validator 硬等于 1024 | **一致** |
| `memory_retrieval.embedding_max_input_tokens` | `1024` | Settings 字段 **保留**（未来 TEI/RET 路径）；**DEV-007 SiliconFlow Client 不得**以其做客户端校验或拒绝 |
| `embedding.base_url` / `model_id` | TEI Compose 语义 | **保留**（local_tei / compose 用） |
| `Settings.required_env_keys()` | **不含** `SILICONFLOW_API_KEY` | 条件必填（见 §5.2） |

### 4.6 configs / .env.example

| 文件 | main 事实 |
|---|---|
| `configs/base.yaml` | `embedding_provider: local_tei`；无 siliconflow 键 |
| `configs/development.yaml` | 仅注释占位 |
| `configs/test.yaml` | 仅 `compression_llm_timeout_seconds` override |
| `.env.example` | `EMBEDDING__BASE_URL=http://embedding-service:80`；**无** `SILICONFLOW_API_KEY` |

### 4.7 现有测试（embedding 相关）

| 层级 | 文件 | 与 DEV-007 关系 |
|---|---|---|
| Unit | `test_settings_loader.py` / `test_settings_validation.py` | `VALID_ENV` 无 `SILICONFLOW_API_KEY`；默认改 siliconflow 后 **须修订** |
| Contract | `test_api_shell_contract.py` | `fake_app_state` mock `http_client.get` → readiness embedding ready |
| Contract | `test_env_example_contract.py` | 断言 `required_env_keys()` 全集 |
| Contract | `test_compose_config_contract.py` | TEI 12g；**不修改** |
| Unit | `test_tei_memory_probe.py` 等 | OI-011 证据；**不修改** |
| Integration | `test_migrate_infra.py` | ES `embedding.dims==1024`；**不修改 mapping** |
| **缺失** | `test_siliconflow_embedding*` / contract / integration | **本任务创建** |

### 4.8 与技术规格不一致之处（本任务须闭合）

1. 代码层无 `EmbeddingClient` / `SiliconFlowEmbeddingClient`（规格 §2.2.6 / §3.10.0 已 pivot）。
2. Settings / YAML 默认 `embedding_provider` 仍为 `local_tei`（规格 §2.2.14 要求 `siliconflow`）。
3. 无 `SILICONFLOW_API_KEY` 与条件校验（规格 §3.8）。

### 4.9 前置任务检查

| 前置 | 状态 | 证据 |
|---|---|---|
| OI-012 | completed | PR #16 MERGED `003fb43` |
| DEV-002 | completed | PR #5 |
| DEV-004 | completed | PR #10；mapping dims=1024 |
| DEV-005 | completed | PR #12；`AppState.http_client` |
| DEV-006 / PR #13 | PAUSED / DO_NOT_MERGE | 禁止触碰 |
| Git | `main` @ `5ec871e` 干净 | 只读验证 |

---

## 5. Official SiliconFlow facts + UNKNOWN

来源：`https://docs.siliconflow.cn/en/api-reference/embeddings/create-embeddings`（2026-08-09 抓取）；`api-docs.siliconflow.cn` 交叉核对。

### 5.1 Confirmed facts

| ID | 事实 |
|---|---|
| F1 | **Endpoint**：`POST https://api.siliconflow.cn/v1/embeddings`（server base `https://api.siliconflow.cn/v1`） |
| F2 | **Authentication**：`Authorization: Bearer <api_key>`（OpenAPI `bearerAuth`） |
| F3 | **Model**：`BAAI/bge-m3` 在官方 model 列表 / 示例中 **可用** |
| F4 | **Request**：`model` + `input` 必填；`input` 为 `string` 或 `string[]` |
| F5 | **Batch limit**：`input` 数组 `minItems=1`，`maxItems=32` |
| F6 | **Per-item token limit（模型表）**：`BAAI/bge-m3` / `Pro/BAAI/bge-m3`：**8192 tokens** |
| F7 | **Response 200**：JSON `object=list`，`model`，`data[{index, object=embedding, embedding: number[]}]`，`usage{prompt_tokens, completion_tokens, total_tokens}` |
| F8 | **Index ordering**：每条 embedding 带 `index`；Client **必须**按 index 排序还原输入顺序 |
| F9 | **Trace ID**：成功响应文档声明响应头 `x-siliconcloud-trace-id`（若存在则记录） |
| F10 | **HTTP 错误**：文档化 `400` BadRequest、`401` Unauthorized、`403` Forbidden、`429` RateLimit、`503` Overloaded、`504` Timeout |
| F11 | **429 body**：`{message, data}` 结构（message 示例含 TPM limit 文案） |
| F12 | **503 body**：`{code, message, data}`（示例 code `50505`） |
| F13 | **`encoding_format`**：可选 `float`（默认）或 `base64`；MVP 使用 `float` |
| F14 | **`dimensions` 参数**：**仅** Qwen/Qwen3 系列；**不支持** `BAAI/bge-m3` |

### 5.2 UNKNOWN_FROM_OFFICIAL_DOCS

| ID | 未知项 | DEV-007 处理 |
|---|---|---|
| U1 | **BAAI/bge-m3 输出向量维度** | **Integration 门禁**：须 `len(embedding)==1024`；若 ≠1024 → **HALT**（测试失败 + 治理报告）；**禁止**改 ES mapping |
| U2 | **文档 array 描述冲突**：模型表写 bge-m3 **8192**，同页 array 描述写「每项不超过 **512** tokens」 | **FLAG**；**不**建 tokenizer 消歧；**不**做客户端 token 长度预判；超长/非法输入 **交由 SiliconFlow API**；HTTP `400` → fail-fast `embedding_failed`（**无**重试） |
| U3 | **Retry-After 头是否保证存在** | **UNKNOWN**；可作可选 hint；**不得**假设保证 |
| U4 | **5xx 精确集合** | 文档列 `503/504`；MVP 将 **500–599** 视为 provider 5xx 可重试（与 OI-012 M8 一致） |
| U5 | **向量 L2 归一化语义** | 规格 **UNKNOWN**；**不得**在 Client 再 normalize；**不得**猜测 |
| U6 | **SiliconFlow embeddings count-tokens API** | **无**；DEV-007 **不**引入大 tokenizer 依赖 |

---

## 6. 实现方案

### Step 1 — 类型、Protocol、错误（`infrastructure/embedding/types.py` + `errors.py`）

- **`EmbeddingResult`**（`dataclass` 或 Pydantic frozen）：
  - `model: str`（来自响应或 settings）
  - `dimension: int`（固定 1024）
  - `vectors: list[list[float]]`（与输入同序）
- **`EmbeddingClient`**（`Protocol`）：
  - `async def embed(self, texts: list[str]) -> EmbeddingResult`
- **`EmbeddingServiceError`**（`Exception`）：
  - 字段：`code`（如 `embedding_failed`、`embedding_input_too_long`、`embedding_auth_failed`）、`provider`、`status_code`、`trace_id`、`sanitized_message`
  - `__str__` / `repr` **禁止**包含 API key、`Authorization`、完整 input、完整 vectors
- **空字符串**：任一 `text == ""` → `EmbeddingServiceError(code=embedding_input_too_long)`；**零** HTTP 调用

### Step 2 — Settings 最小变更（`settings/models.py` + `validators.py`）

- `MemoryRetrievalSettings.embedding_provider`：
  - 默认改为 `"siliconflow"`
  - 类型改为 `Literal["siliconflow", "local_tei"]`（或 validator 拒绝其他值）
- 顶层 `Settings` 新增：
  - `siliconflow_api_key: SecretStr | None = None`（env：`SILICONFLOW_API_KEY`）
- **可选**（避免与 `embedding.base_url` 混淆）：`memory_retrieval.siliconflow_base_url: str = "https://api.siliconflow.cn"`（env：`MEMORY_RETRIEVAL__SILICONFLOW_BASE_URL`）；Client 请求 `{base}/v1/embeddings`
- **`validate_memory_retrieval` 扩展**：
  - `embedding_provider` 非法值 → `ValueError`（fail-closed）
  - `embedding_provider == "siliconflow"` 且 key 缺失/空 → `ValueError`（fail-fast）
  - `embedding_provider != "siliconflow"` → **不**要求 key
- **`required_env_keys()`**：
  - **不**将 `SILICONFLOW_API_KEY` 加入全局元组（避免 `local_tei` 被强制要求）
  - `.env.example` **仍须**含占位 key（见 Step 8）
- **启动时固定 provider**：仅 `get_settings()` / factory 读取；**无**请求级切换

### Step 3 — `SiliconFlowEmbeddingClient`（`siliconflow_client.py`）

**构造**：`settings`、`http_client: httpx.AsyncClient`、`logger`（可选）。

**`embed(texts: list[str])` 流程**：

1. 输入校验：空列表 → `EmbeddingResult(model=..., dimension=1024, vectors=[])`；**零** HTTP 调用。
2. **Validate every input string is non-empty before any provider HTTP call**；空字符串 → 复用现有最小错误模型（`embedding_input_too_long` 若 spec 已规定；**零** HTTP）。
3. **输入校验（Amendment 001 — 无本地精确 token 计数）**：
   - **禁止**：本地 tokenizer；精确 token 计数；以 `embedding_max_input_tokens` 做 SiliconFlow 客户端拒绝（该 Settings 字段可保留供未来 TEI/RET，**本任务不 enforce**）
   - **必须**：非空字符串校验（`text == ""` → `embedding_input_too_long`；**零** HTTP 调用）；Provider 请求 batch **≤ 32**（确定性切分）
   - **主路径**：校验通过后直接发往 API；Provider 实际输入限制由 SiliconFlow 强制执行
   - Provider HTTP `400` → fail-fast `embedding_failed`（**无**重试；见 Step 4）
   - **可选（非 MVP 验收必需）**：极宽松字符/载荷上界（**非** token 语义；**不**绑定 `embedding_max_input_tokens`），仅防意外超大 payload；若实施须单独 optional 测试，**不**计入 §8 必测矩阵
4. **分批**：`SILICONFLOW_MAX_BATCH_SIZE = 32`；按输入顺序确定性切分；合并结果保持顺序。
5. **HTTP 请求**（每批）：
   - `POST {siliconflow_base_url}/v1/embeddings`
   - Headers：`Authorization: Bearer <key>`、`Content-Type: application/json`
   - Body：`{"model": settings.memory_retrieval.embedding_model, "input": batch, "encoding_format": "float"}`
   - Timeout：per-request `httpx.Timeout` 基于 `embedding_timeout_seconds`
6. **响应解析**：
   - JSON 解析失败 → fail-fast `embedding_failed`
   - 校验 `data` 存在；条数 == 批大小
   - 按 `index` 排序；提取 `embedding` 列表
   - 每条 `len(embedding) == 1024`；否则 fail-fast
   - 拒绝 NaN/Inf（规格 §2.2.6）
7. **错误映射**：
   - `400` → fail-fast（含 auth 以外无效请求）
   - `401`/`403` → fail-fast `embedding_auth_failed`
   - `429`/`5xx`/timeout/transient transport → 可重试（见 Step 4）
   - 其他 4xx → fail-fast
8. **日志**：仅 `provider=siliconflow`、`status_code`、`trace_id`（从 `x-siliconcloud-trace-id`）、`sanitized_message`（截断，如 max 200 chars）；**禁止**记录 Authorization、key、完整 input、vectors

### Step 4 — 有界重试（`retry.py` 或 client 内私有方法）

| 项 | 规则 |
|---|---|
| 最大 attempt | **3**（1 初始 + 2 重试） |
| 可重试 | HTTP `429`；HTTP `500–599`；`httpx.TimeoutException`；`httpx.ConnectError`；`httpx.ReadError`；`httpx.WriteError`；`httpx.PoolTimeout` |
| fail-fast | `400`、`401`、`403`、其他 `4xx`；JSON/结构错误；维度/条数不匹配 |
| 退避 | 有界指数退避 + 可选 jitter，例如 `delay = min(0.5 * 2**attempt, 8.0) + uniform(0, 0.1)` |
| Retry-After | 若响应头存在且可解析为秒数 → `delay = min(parsed, max_backoff)`；**不**假设保证存在 |
| 耗尽 | 抛出 `EmbeddingServiceError(embedding_failed)`，含最后 `status_code`/`trace_id` |

### Step 5 — Factory（`factory.py`）

```python
def create_embedding_client(
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> EmbeddingClient:
    provider = settings.memory_retrieval.embedding_provider
    if provider == "siliconflow":
        return SiliconFlowEmbeddingClient(settings, http_client)
    if provider == "local_tei":
        raise NotImplementedError(
            "local_tei embedding client is not implemented in DEV-007 MVP; "
            "use embedding_provider=siliconflow or defer to future TEI task"
        )
    raise ValueError(f"unsupported embedding_provider: {provider!r}")
```

- **禁止** `local_tei` 静默回退 `siliconflow`
- **不**在本任务创建 `TEIEmbeddingClient`

### Step 6 — YAML / env 同步

- `configs/base.yaml`：`memory_retrieval.embedding_provider: "siliconflow"`
- `configs/test.yaml`：可保持最小；测试主要靠 `monkeypatch` env
- `.env.example`：追加 `SILICONFLOW_API_KEY=sk-example-replace-me`（占位；注释说明仅 siliconflow 默认需要）

### Step 7 — 修订既有 Settings 测试 fixture

- `tests/unit/test_settings_validation.py`、`test_settings_loader.py`、`tests/contract/test_api_shell_contract.py` 的 `VALID_ENV` 增加 `SILICONFLOW_API_KEY=sk-example-replace-me`
- 新增用例：`embedding_provider=local_tei` 可无 key；`siliconflow` 缺 key → `ValidationError`；非法 provider → `ValidationError`

### Step 8 — 测试实现（见 §8）

与实现同步提交。

### Step 9 — 治理回写（实施阶段）

Developer 更新本 Plan §13–§14 与 `progress.md`；本规划轮次仅 `planned`。

---

## 7. 文件变更清单（实施阶段精确白名单）

### 7.1 允许写入（CREATE / MODIFY）

| 路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/infrastructure/embedding/__init__.py` | 创建 | 包导出 |
| `src/memory_system/infrastructure/embedding/types.py` | 创建 | `EmbeddingResult`、`EmbeddingClient` |
| `src/memory_system/infrastructure/embedding/errors.py` | 创建 | `EmbeddingServiceError` |
| `src/memory_system/infrastructure/embedding/siliconflow_client.py` | 创建 | `SiliconFlowEmbeddingClient` |
| `src/memory_system/infrastructure/embedding/factory.py` | 创建 | `create_embedding_client` |
| `src/memory_system/infrastructure/embedding/retry.py` | 创建（可选） | 重试/退避 helper |
| `src/memory_system/settings/models.py` | 修改 | provider 默认、key、Literal |
| `src/memory_system/settings/validators.py` | 修改 | provider/key 条件校验 |
| `configs/base.yaml` | 修改 | `embedding_provider: siliconflow` |
| `configs/development.yaml` | 修改（若需） | 注释/无 secret |
| `configs/test.yaml` | 修改（若需） | 测试 override |
| `.env.example` | 修改 | `SILICONFLOW_API_KEY` 占位 |
| `tests/unit/test_siliconflow_embedding_client.py` | 创建 | settings、redaction、空输入校验 |
| `tests/contract/test_siliconflow_embedding_client_contract.py` | 创建 | M10 mocked HTTP 矩阵 |
| `tests/contract/helpers/siliconflow_fake.py` | 创建 | MockTransport / fake 响应 |
| `tests/integration/test_siliconflow_embedding_client_integration.py` | 创建 | opt-in M11 |
| `tests/unit/test_settings_validation.py` | 修改 | provider/key 用例 + VALID_ENV |
| `tests/unit/test_settings_loader.py` | 修改 | VALID_ENV |
| `tests/contract/test_api_shell_contract.py` | 修改 | VALID_ENV（若默认 settings 加载） |
| `tests/contract/test_env_example_contract.py` | 修改（若需） | 占位 key 断言策略 |
| `02_开发管理/tasks/DEV-007-siliconflow-embedding-client-mvp.md` | 修改 | 执行记录 |
| `02_开发管理/progress.md` | 修改 | 状态机 |
| `02_开发管理/master_plan.md` | 修改 | 登记 |

### 7.2 明确禁止（FORBIDDEN）

| 类别 | 路径 / 行为 |
|---|---|
| DEV-006 / PR #13 | `feat/DEV-006-*` worktree；PR #13 任何操作 |
| Compose / TEI infra | `compose*.yaml`、`scripts/**`（含 `start_embedding.sh`、`preflight`、`compose.sh`）、`versions.*` |
| ES / Migration | `scripts/migrate.py`、`scripts/migrations/**` |
| 业务接线 | `src/memory_system/api/routes/**`（除既有 health 外）、STM/EXT/RET |
| 真实 Secret | 真实 `SILICONFLOW_API_KEY` 入 git/configs/tests/fixtures/logs/PR |
| 默认 CI 公网 | 未 skip 的 integration 调用真实 API |
| Readiness 升级 | `runtime.check_embedding` 改为 embed 探针（本任务 **不改**） |
| TEI Client | 实现/合并 `TEIEmbeddingClient` |

---

## 8. 测试计划

### 8.1 Unit Test

| # | 场景 | 预期 |
|---|---|---|
| U1 | 默认 `get_settings()`（siliconflow + 占位 key） | 校验通过；`embedding_provider==siliconflow` |
| U2 | `embedding_provider=siliconflow` 缺 key | `ValidationError` |
| U3 | `embedding_provider=local_tei` 无 key | 校验通过 |
| U4 | 非法 `embedding_provider` | `ValidationError` |
| U5 | `EmbeddingServiceError` str/repr | 不含 key/`Bearer`/长向量 |
| U6 | 空字符串 `embed` | `embedding_input_too_long`；HTTP mock **零**调用 |

**Amendment 001**：原 U7（字符 guard → `embedding_input_too_long`）**移出必测矩阵**。超长/非法输入 **不**客户端预判；Contract **C10**（HTTP `400` → fail-fast `embedding_failed`；**无**重试）覆盖 Provider 拒绝路径。若实施可选极宽松字符/载荷上界，须单独 optional 测试，**不**计入 Release Gate。

### 8.2 Contract Test（mocked HTTP — 默认 CI）

| # | 场景 | 预期 |
|---|---|---|
| C1 | settings → factory 选 siliconflow | 返回 `SiliconFlowEmbeddingClient` |
| C2 | 单条 input 成功 | `EmbeddingResult`；dim=1024；顺序一致 |
| C3 | 多条 input 成功（≤32） | 一批 HTTP；vectors 顺序正确 |
| C4 | 33 条 input | 2 次 HTTP（32+1）；顺序正确 |
| C5 | 响应 index 乱序 | Client 重排后顺序正确 |
| C6 | 响应条数 mismatch | fail-fast `embedding_failed` |
| C7 | 畸形 JSON | fail-fast |
| C8 | 缺 embedding 字段 | fail-fast |
| C9 | 向量维度 ≠1024 | fail-fast |
| C10 | HTTP 400 | fail-fast；**无**重试 |
| C11 | HTTP 401 / 403 | fail-fast `embedding_auth_failed` |
| C12 | HTTP 429 | 重试后成功（attempt≤3） |
| C13 | HTTP 500 | 重试后成功 |
| C14 | timeout | 重试后成功 |
| C15 | 429 持续至耗尽 | `embedding_failed`；attempt==3 |
| C16 | Authorization 未出现在异常/日志 | 断言通过 |
| C17 | `local_tei` factory | `NotImplementedError`（非静默回退） |

**Mock 策略**：`httpx.MockTransport` 或 `respx`（**禁止**新增未批准依赖—优先 `httpx.MockTransport`）；`tests/contract/helpers/siliconflow_fake.py` 统一构造响应。

### 8.3 Integration Test（opt-in only）

| 项 | 规则 |
|---|---|
| Enable | `RUN_SILICONFLOW_EMBEDDING_INTEGRATION=1` **且** 环境变量 `SILICONFLOW_API_KEY` 非空 |
| 默认 | `@pytest.mark.skip` 或 `pytest.skip` when flag/key 缺失 |
| 用例 | 短文本单条；小 batch（2–3 条）；`model` 含 `bge-m3`；`len(vector)==1024` |
| 禁止 | load test、rate-limit 探测、benchmark、quota burn |
| dim≠1024 | 测试 **FAIL** + 明确 HALT 消息；**不改** mapping |

### 8.4 E2E Test

不适用（无业务路由接线）。

### 8.5 失败注入与并发

| 场景 | 预期 |
|---|---|
| 并发 `embed` 两次（mock） | 无共享可变状态；结果正确 |
| 重试计数 | 精确 3 attempt 后失败 |

---

## 9. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 只读 API；无 DB 写入 |
| 幂等 | 适用（只读） | 同输入应稳定；无 Client 侧缓存 |
| 并发 | 适用 | 共享 `httpx.AsyncClient`；Client 无批间可变状态 |
| 版本冲突 | 不适用 | 无资源版本 |
| 用户隔离 | 不适用 | Client 无 user_id |
| 部分失败 | 适用 | 单批失败即整次 `embed` 失败；不返回部分 vectors |
| 进程异常恢复 | 不适用 | 无持久化中间态 |

---

## 10. 验收标准（Release Gate）

- [ ] `EmbeddingClient` / `EmbeddingResult` / `SiliconFlowEmbeddingClient` / `create_embedding_client` 可 import
- [ ] 默认 `embedding_provider=siliconflow`（models + `configs/base.yaml`）
- [ ] `siliconflow` 缺 key → Settings `ValidationError`；`local_tei` 不要求 key
- [ ] 非法 provider → fail-closed
- [ ] Contract 矩阵 C1–C17 **全通过**（默认 CI，无公网）
- [ ] Integration opt-in：有 key 时 `dim==1024`；否则 skip
- [ ] 真实 API key **未**进入 git/configs/tests/fixtures/logs
- [ ] `uv run pytest tests/unit tests/contract -q` 全绿
- [ ] `uv run ruff check .` 通过
- [ ] `uv run mypy src tests scripts` 通过
- [ ] `uv run python scripts/check_env_example.py` 通过（含占位 key 策略）
- [ ] **未**修改 compose/scripts/versions/migration/TEI 12g contract
- [ ] **未**触碰 DEV-006 feat / PR #13
- [ ] Code Review P0/P1=0

**Tests required（实施结束必须执行）**：

```bash
uv run pytest tests/unit/test_siliconflow_embedding_client.py tests/contract/test_siliconflow_embedding_client_contract.py -q
uv run pytest tests/unit/test_settings_validation.py tests/unit/test_settings_loader.py -q
uv run pytest tests/unit tests/contract -q
uv run ruff check .
uv run mypy src tests scripts
uv run python scripts/check_env_example.py
# Opt-in only:
# RUN_SILICONFLOW_EMBEDDING_INTEGRATION=1 SILICONFLOW_API_KEY=<secret> uv run pytest tests/integration/test_siliconflow_embedding_client_integration.py -v
```

---

## 11. 风险与阻塞项

| 风险 | 级别 | 缓解 |
|---|---|---|
| **U1** bge-m3 实际 dim≠1024 | **BLOCKER（若发生）** | Integration HALT；报告；**禁止**改 ES mapping |
| **U2** 官方 token 文档冲突 | 中 | **不**客户端消歧；Provider API `400` fail-fast `embedding_failed`（无重试）；不假装精确 token 计数 |
| 默认 provider 改 siliconflow 破坏本地无 key 开发 | 中 | `.env.example` 占位；文档注释 |
| `VALID_ENV` 漂移导致广泛测试失败 | 低 | Step 7 同步所有 fixture |
| `check_embedding` 仍探测 TEI `/health` | 低 | Readiness 非阻塞；后续任务 provider-aware 探针 |
| PR #13 与 DEV-007 路径冲突 | 中 | 禁止 merge #13；DEV-007 独立实现 Protocol |
| L2 归一化 UNKNOWN | 低 | 不二次 normalize；不跨 provider benchmark |

**Deferred（显式 OUT OF SCOPE）**：

- `TEIEmbeddingClient` 完整实现（PR #13 / 后续任务）
- Provider 热切换；Readiness embed 探针升级
- 本地 HF tokenizer；精确 1024 token 校验（EXT/RET 路径）
- TEI 429 / compose / preflight 改动
- STM/EXT/RET 接线；大型 metrics 改造
- ES mapping 变更；cross-provider cosine benchmark

---

## 12. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/DEV-007-siliconflow-embedding-client-mvp"
expected_commits:
  - "docs(plan): add DEV-007 siliconflow embedding client mvp plan"
  - "feat(embedding): add siliconflow client, settings, and contract tests"
  - "docs(status): record DEV-007 implementation commit and PR"
  - "docs(status): complete DEV-007 after PR merge"
release_phases:
  PLAN_LANDING: "docs(plan) on main → 创建 exact feat 分支"
  IMPLEMENTATION_RELEASE: "feat 上 implementation + tests + optional docs(status): record"
  POST_MERGE_CLEANUP: "main docs(status): complete；删 exact feat"
out_of_scope_changes:
  - "compose/scripts/versions/migration"
  - "DEV-006 feat / PR #13"
  - "STM/EXT/RET 业务代码"
  - "真实 SILICONFLOW_API_KEY"
pr_base: main
pr_title: "feat(DEV-007): SiliconFlow embedding client MVP"
```

---

## 13. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001 — Input Validation Simplification（2026-08-09）

**用户指令摘要**：DEV-007 **不做**本地精确 token 计数。仅保留：(1) 非空输入校验（空字符串拒绝；零 HTTP）；(2) Provider 请求 batch ≤ 32（确定性切分）；(3) **可选**极宽松字符/载荷防御（非 token 语义；非 `embedding_max_input_tokens` 合同）。实际 Provider 输入限制由 SiliconFlow API 强制执行；Provider HTTP `400` → fail-fast `embedding_failed`（无重试）。

**修订章节**：§4.5（`embedding_max_input_tokens` 保留但不用于 SiliconFlow 客户端校验）、§5.2 U2、§6 Step 3、§8 U7（从必测矩阵移除）、§11 U2 缓解、§14 执行记录。

**人工批准**：2026-08-09 `PLAN_APPROVED`（BLOCKER=0；MUST_FIX=0）；吸收 SHOULD_FIX：Step 3 非空校验措辞、§13/§14 修订联动。

---

## 14. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-09 15:20 UTC | Planner 初版 | 创建本 Task Plan；progress/master_plan 规划态 | 未实施 | 无 |
| 2026-08-09 15:30 UTC | Amendment 001 | 输入校验简化：移除字符 guard 合同；API 400 fail-fast；U7 移出必测 | 未实施 | 无 |
| 2026-08-09 16:00 UTC | Developer in_progress | 创建 embedding 包、SiliconFlow client、factory、settings pivot | 未跑 | 无 |
| 2026-08-09 16:15 UTC | Developer implemented | 完成 U1–U6、C1–C17；opt-in integration；修订 VALID_ENV | 新测 54 passed | 无 |
| 2026-08-09 16:45 UTC | POST_MERGE_CLEANUP | PR #17 MERGED `b7916ea`；docs(status): complete | — | Phase 0 bootstrap 就绪 |

---

## 15. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/infrastructure/embedding/**` | 创建 types/errors/retry/siliconflow_client/factory/__init__ |
| `src/memory_system/settings/models.py` | provider 默认 siliconflow；`SILICONFLOW_API_KEY`；`siliconflow_base_url` |
| `src/memory_system/settings/validators.py` | siliconflow 条件 key 校验 |
| `configs/base.yaml` | `embedding_provider: siliconflow` |
| `.env.example` | `SILICONFLOW_API_KEY` 占位 |
| `tests/unit/test_siliconflow_embedding_client.py` | U1–U6 |
| `tests/contract/test_siliconflow_embedding_client_contract.py` | C1–C17 |
| `tests/contract/helpers/siliconflow_fake.py` | MockTransport 辅助 |
| `tests/integration/test_siliconflow_embedding_client_integration.py` | opt-in M11 |
| `tests/unit/test_settings_*.py`、`tests/contract/test_api_shell_contract.py` | VALID_ENV + key |
| `02_开发管理/tasks/DEV-007-*.md`、`progress.md`、`master_plan.md` | 治理回写 |

### 与原计划的差异

- 无业务语义差异；`tests/contract/helpers` 使用 `importlib` 加载以避免 mypy 双模块名（未新增 `__init__.py`）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| 新测 unit+contract | `uv run pytest tests/unit/test_siliconflow_embedding_client.py tests/contract/test_siliconflow_embedding_client_contract.py -q` | 26 passed |
| settings | `uv run pytest tests/unit/test_settings_validation.py tests/unit/test_settings_loader.py -q` | 28 passed |
| 全 unit+contract | `uv run pytest tests/unit tests/contract -q` | 261 passed, 1 failed（`test_compose_wrapper_contract` main 既有） |
| ruff | `uv run ruff check .` | passed |
| mypy | `uv run mypy src tests scripts` | 91 files, no issues |
| env example | `uv run python scripts/check_env_example.py` | passed |
| integration（opt-in） | 人工 evidence PASS（`PYTEST_EXIT=0`；dim=1024） | PASS |

### Review 结果

```yaml
p0: 0
p1: 0
review_report: CODE_REVIEW_APPROVED
```

### Git 记录

```yaml
branch: feat/DEV-007-siliconflow-embedding-client-mvp
plan_commit: 69e4dece8e72acf22828ba5b81682b70ecb34e8b
implementation_commit: 88c442e909c89fe297921f61d6bd6c13ba4b719d
implementation_commit_message: "feat(embedding): add siliconflow client, settings, and contract tests"
status_record_commit_committed: ea58d72690d2e34539cd2eb123e1fedd14c5874f
pr: "#17"
merge_commit: b7916ea79a2d2ec7bf25873ec2ba50ad64041775
```

### 最终状态

`completed`
