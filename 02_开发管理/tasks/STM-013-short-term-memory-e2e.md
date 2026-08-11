# STM-013 Short-Term Memory E2E

## 1. 任务信息

```yaml
task_id: STM-013
task_name: Short-Term Memory E2E
status: planned
plan_review_round: 2
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.1–§1.2.7 Working Memory / Compression / Session Close"
  - "§1.2.4 Kafka context.archive.created"
  - "§3.23 统一 API 响应与 Request ID"
  - "§3.28 测试策略（STM 子集失败注入）"
  - "§3.32 MVP 验收（STM 垂直切片；非 EXT/RET 全链路）"
prerequisites:
  formal:
    - "STM-010 — SATISFIED（Session Close；PR #29 MERGED）"
  non_blockers:
    - "STM-011 — READY_FOR_PLANNING only（republish 脚本；E2E 不依赖）"
    - "STM-012 — NOT ready（需 STM-011 + EXT-001；本任务 OUT OF SCOPE）"
  baseline:
    - "Authoritative baseline：main == origin/main == 390af52f58509e323dd6500e77524033e0b5dcbf；working tree clean"
branch: "feat/STM-013-short-term-memory-e2e"
milestone: "v0.2.0-short-term-memory"
created_at: "2026-08-11 02:30 UTC"
updated_at: "2026-08-11 10:35 UTC"
approval_gates:
  planning_docs: pending
  implementation_plan: pending
```

### 1.1 编排与门禁（本轮）

```yaml
start_existing_task: true
phase: planning_only
must_not_this_round:
  - "进入 Developer / 编写业务实现或测试语义"
  - "git add / commit / push / merge / rebase"
  - "修改 STM-001~010 核心 Contract / Lua / Coordinator 语义"
  - "实现 STM-011 republish / STM-012 EXT 消费验证"
  - "触碰 DEV-006 / PR #13"
  - "E2E 暴露生产缺陷时在本任务内修复（须 HALT）"
```

---

## 2. 任务目标

交付 **STM 阶段端到端测试套件**（`tests/e2e/`），通过 **公共 HTTP API** 驱动完整短期记忆垂直切片，在 **真实 Redis + Mongo + Kafka + memory-api** 环境下验证 STM-001~010 已交付能力，并含规格 §3.28 要求的 **STM 相关失败注入子集**。

**本任务完成即闭合 `v0.2.0-short-term-memory` 里程碑**（`master_plan` §4）；**不**等同于 Phase 1 表内全部任务完成（STM-011/012 仍独立）。

可验证交付：

1. **E1 Happy Path**：Session Create → Message Write（含触发压缩）→ Coordinator 全链路（STM-004~008）→ 压缩后 Redis 状态 → 压缩后继续写入 → Session Close → Mongo 持久化 + Kafka 可观测。
2. **E2**：`message_id` 重复幂等（HTTP + Redis 零副作用）。
3. **E3**：并发 write-vs-close（真实 Redis；HTTP 双通道）。
4. **E4**：代表性失败注入（§3.28 STM 子集；**单选** LLM 失败 → HTTP 200 `compression_status=failed`；见 §8.5）。
5. **跨层断言**：每层场景均覆盖 HTTP + Redis + Mongo + Kafka（Kafka 矩阵见 §5.0 #6 与 §8.4；E2/E3/E4 按场景收窄，禁止脆弱全局计数）。
6. **默认零生产代码变更**；仅测试与 E2E 辅助模块。

---

## 3. 非目标（必须坚持）

- **修改** STM-001~010 业务实现、Lua 脚本、Coordinator/Close 核心 Contract（缺陷暴露 → **HALT**，不开 STM-013 修复）。
- STM-011 `republish_archive_event.py` 实现或验证。
- STM-012 Extraction Consumer 消费补发事件。
- EXT / RET / CON 任意阶段逻辑或 E2E。
- 规格 §3.32 #4 **全链路** E2E（`Extraction → Elasticsearch → Retrieval → Consolidation`）——留待 EXT-009 / E2E-001。
- 真实 DeepSeek / SiliconFlow / TEI 网络调用；CI 默认 **不得** 依赖 `LLM__API_KEY` / `SILICONFLOW_API_KEY` 计费。
- 新增 HTTP 端点；直接调用 `write_message` / `close_session` / `write_working_message_with_coordination` 驱动主流程（断言层允许直连 Redis/Mongo/Kafka）。
- `tests/e2e/devops003_normal_workflow_smoke.txt` 语义变更。
- DEV-006 / PR#13。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `390af52f58509e323dd6500e77524033e0b5dcbf` |
| `git status --short` | clean（规划轮次允许 Task Plan + progress + master_plan dirty） |
| formal STM-001 ~ STM-010 | `completed` |
| `tests/e2e/` Python | **无**（仅 `devops003_normal_workflow_smoke.txt`） |
| `create_app` 默认 LLM | `FakeLlmClient()`（`app.py` L55） |
| FULL_RUFF / mypy（STM-010 证据） | PASS |

### 4.2 可复用组件审计

| 组件 | 路径 | STM-013 用法 |
|---|---|---|
| Compose 测试栈 | `compose.test.yaml` + `scripts/compose.sh --stack=test` | E2E 基础设施；`TEST_PROJECT=memory-system-test` |
| Integration fixture 模式 | `test_message_write_coordinator_kafka.py` 等 | `_compose`、`_container_ip`、Kafka topic、bounded poll |
| Token 估算 | `domain/services/token_estimator.py` | 构造消息内容达 trigger |
| WM Key helpers | `infrastructure/redis/keys.py` | 断言层禁止硬编码 key |
| WM meta codec | `working_memory_codec.hash_fields_to_meta` | Redis 字段断言 |
| Archive collection | `CONTEXT_ARCHIVE_COLLECTION` | Mongo 查询 |
| Kafka event schema | `ARCHIVE_CREATED_EVENT_FIELD_NAMES` | 事件字段断言 |
| API 路由 | `memory_session.py` / `memory_message.py` | E2E HTTP 驱动 |
| Readiness | `test_api_readiness.py` | memory-api 健康检查模式 |
| Fake LLM | `infrastructure/llm/fake_client.py` | 默认成功；E4 注入 `mode="timeout"` |

### 4.3 当前缺失

- `tests/e2e/` 下 STM-013 Python 测试与共享 fixture/helpers
- E2E 专用 compose 启动序（含 `init-infra` + `memory-api`）
- 跨 HTTP/Redis/Mongo/Kafka 断言工具函数
- E4 失败注入 fixture（in-process app + 真实后端）

### 4.4 前置任务检查

| 前置 | 状态 |
|---|---|
| STM-010 | **SATISFIED** |
| STM-011 | **NOT prerequisite**（§10.2） |
| STM-012 | **OUT OF SCOPE** |
| OI-001~005 | **resolved**（STM-009/010 已闭合） |

---

## 5. 实现方案

> **原则：TEST / E2E FIRST**。默认 **不** 修改 `src/**`。若 E2E 暴露 STM-001~010 真实缺陷 → Developer **HALT** 并报告 Orchestrator，**不得** 在 STM-013 内修复。

### 5.0 十六项 Contract 闭合（Planner 权威结论；#0–#15）

#### 0 — E2E 范围与里程碑边界

| 项 | 结论 |
|---|---|
| 规格依据 | `master_plan` STM-013；§3.28 E2E 层；§3.32 #4 全链路 **不** 属本任务 |
| 本任务闭合 | `Session → Message → Archive → Compression → Session Close`（STM 垂直切片） |
| 里程碑 | `v0.2.0-short-term-memory` = **STM-013 completed** |
| Phase 1 表 | STM-011/012 仍 `planned`；与里程碑解耦 |
| 驱动方式 | **仅** 公共 HTTP：`POST /api/v1/memory/session`、`POST /api/v1/memory/working/message`、`POST /api/v1/memory/session/{user_id}/{session_id}/close` |
| 禁止 | 测试主流程直接 import 领域服务写路径 |

#### 1 — 环境与基础设施

| 项 | 结论 |
|---|---|
| Compose | `./scripts/compose.sh --stack=test --embedding=none`（与 Integration 一致） |
| 隔离 | `memory-system-test` project；独立 volume；`down` 清理 |
| 启动序 | 见 §5.2 / §5.3 Step 1（repo 事实：`compose.yaml` + `compose.test.yaml`；**禁止** sleep 猜就绪） |
| 端口 | **test 栈无** `compose.override.yaml` 端口绑定；HTTP 经 `_container_ip(memory-system-api-test):8000`（**非** `127.0.0.1:8000`）；Redis/Mongo/Kafka 同理经 container IP |
| 鉴权 | `X-API-Key: dev-memory-api-key-change-me`（`.env.example`） |
| 网络 | 测试进程经 `_container_ip` 连 Redis/Mongo/Kafka；Kafka 可复用 `socket.getaddrinfo` patch 模式 |
| 秘密 | 禁止真实 `LLM__API_KEY` / `SILICONFLOW_API_KEY`；FakeLlmClient 默认 |

#### 2 — 压缩触发构造数学（配置驱动；Fixture A 配置同源性）

| 项 | 结论 |
|---|---|
| **Invariant** | E2E 期望 `ContextSettings` **==** memory-api 容器运行时 `ContextSettings`；**禁止** host/container 分叉；**禁止** 重复常量 |
| 权威配置源 | memory-api 容器经 `x-app-env` 加载 **同一** `.env`（`compose.sh` env-file 链：`.env` → `versions.env` → `versions.lock.env` → `.runtime/embedding.env`） |
| 写入时机 | **Fixture A 启动 memory-api 之前**：向 repo 根 `.env` 写入 **协调 bundle**（须满足 `validators.py` 严格不等式；对齐 `test_message_write_coordinator_kafka.py` `test_settings`）；**非** `src` 变更；**非** 改 `pyproject.toml` |
| 协调 bundle 示例 | `CONTEXT__COMPRESSION_TRIGGER_TOKENS=200`；`CONTEXT__COMPRESSION_TARGET_TOKENS=80`；`CONTEXT__MAX_COMPRESSED_CONTEXT_ESTIMATED_TOKENS=100`（**必须** `< trigger`）；`CONTEXT__PREFERRED_RECENT_MESSAGES=2`；`CONTEXT__ABSOLUTE_MIN_RECENT_MESSAGES=2`；**禁止** 仅写 trigger 导致 `max_compressed >= trigger` 启动失败 |
| `.env` 生命周期 | conftest Step 0 **备份** 现有 `.env`（若存在）→ 写入 bundle → teardown **恢复** 备份（或删除测试写入项）；**禁止** 仅 `compose down` 留下加速配置污染后续本地运行 |
| 读取权威值（任选其一，须与容器一致） | (a) `docker exec memory-system-api-test python -c "from memory_system.settings import get_settings; print(get_settings().context.compression_trigger_tokens)"`；(b) `./scripts/compose.sh --stack=test --embedding=none config` 解析 `memory-api` 有效 env 后经 **同一** `get_settings()` 路径加载；(c) host 侧 `_ensure_dotenv()` 后 `get_settings().context.compression_trigger_tokens` **仅当** 与 (a) 输出一致 |
| E1 trigger 构造 | `trigger =` 上述权威 `compression_trigger_tokens`；循环 POST 累加 Redis `estimated_tokens` 直至触发 |
| Token 公式 | `estimate_tokens(text) = ceil(chinese×1.25 + other×0.25)`（STM-001） |
| ASCII 快捷 | `content_for_tokens(n) = "b" * max(n * 4, 4)` → `estimate_tokens(content) >= n` |
| 触发判定 | Coordinator：`meta.estimated_tokens >= compression_trigger_tokens`（**含等于**；STM-009） |
| OI-004 | 断言 **仅** 使用 Redis `estimated_tokens` 与 message 级 `estimated_tokens` 求和；禁止 Mongo 推导 token |
| Fixture B (E4) | hybrid in-process `create_app` 的 `settings` 须与 Fixture A **同一** `.env` 源加载；`llm_client` 单独注入 |

#### 3 — compression_version 生命周期（E1 必断言）

| 阶段 | 期望值 |
|---|---|
| Session Create 后 | `compression_version == 0` |
| 首次压缩 Finalize 后 | `compression_version == 1` |
| 压缩后 `compressed_context` | 非空（FakeLlmClient 默认 JSON） |
| Close 开始时快照 | `ClosePlan.base_compression_version` = 关闭前 Redis `compression_version`（E1 若仅 1 轮压缩则为 `1`） |
| Close suffix Archive | Mongo `base_compression_version` = 关闭快照值（**非** 重读 Redis） |
| Compression Archive | Mongo `base_compression_version` 反映 **该次压缩前** 版本（首次压缩 archive 为 `0`） |
| Close 终端后 | Redis WM keys **不存在** |

#### 4 — E1 Happy Path 逐步 Contract

| Step | HTTP | Redis | Mongo | Kafka |
|---|---|---|---|---|
| 1 Create Session | 200 `status=created`；`session_id` UUID v4 | meta `status=active`，`compression_version=0`，`estimated_tokens=0` | 无 archive | 无 |
| 2 Write until trigger | 200 `status=success`；末次 `compression_status` ∈ `{completed, partial_completed}` | 触发后：`compression_version=1`；`compressed_context` 非空；pending 清空；lock 释放；messages 已 trim | ≥1 compression archive；`archive_batch_key` 区分批次 | ≥1 `context.archive.created`；六字段 schema |
| 3 Post-compression writes | 200 `status=success`；`compression_status=not_triggered`（未再达 trigger） | `estimated_tokens` 增长；`compression_version` 保持 `1` | 无新 archive（未再压缩） | 无新要求 |
| 4 Close | 200 `status=closed`；`archive_ids` 有序 | meta/messages/message_ids keys **不存在** | compression + close suffix 文档可区分（`archive_batch_key` / `base_compression_version`） | 若产生 close suffix archive → `context.archive.created`（过滤 `user_id`/`session_id`/`archive_id`；AT_LEAST_ONCE） |
| 5 Representative auth | E1 子步骤含 `X-API-Key` + `X-Request-ID` 透传；错误包络符合 §3.23 | — | — | — |

#### 5 — Mongo Archive 区分（compression vs close suffix）

| 类型 | 识别 |
|---|---|
| Compression path | 压缩触发产生；`base_compression_version` 为压缩前版本 |
| Close suffix | Close 产生；`archive_batch_key` 覆盖剩余消息；`base_compression_version` = close 入口快照 |
| 断言 | 同一 `session_id` 下两类文档均存在（E1）；`archive_batch_key` 互不相同 |

#### 6 — Kafka 语义与场景矩阵（§2 / §8.4 权威；须完全一致）

| 项 | 结论 |
|---|---|
| 投递 | **AT_LEAST_ONCE**（STM-006）；E2E **不断言 exactly-once** |
| 消费断言 | bounded poll（`getmany` + deadline）；unique `group_id`；**禁止** 裸 `sleep` 作主同步 |
| 字段 | `ARCHIVE_CREATED_EVENT_FIELD_NAMES` 全集；`event_type == context.archive.created` |
| 过滤 | 断言 **必须** 按 `user_id` + `session_id`（+ 已知 `archive_id`）过滤；**禁止** 脆弱全局 topic 计数 |
| **E1** | **MANDATORY**：≥1 `context.archive.created`；六字段 schema 全断言；compression 路径事件 `user_id`/`session_id` 与 HTTP 一致 |
| **E2** | duplicate 请求 **不得** 产生 compression/archive 路径 **新** Kafka 事件；对比 duplicate 前后 **本 session** 过滤后事件集不变（非全局 count） |
| **E3** | 主断言 write-vs-close 互斥（closing 阻断 write）；**若** close suffix archive 产生 → 断言 close 路径 `context.archive.created`（过滤 `user_id`/`session_id`/`archive_id`）；无 suffix 则不硬性要求 Kafka |
| **E4** | 按 STM-006/009 顺序：pending/archive **可在** LLM 失败前已提交；**若** 该 `archive_id` 已 publish → 允许 **≤1** 条匹配事件（过滤 `archive_id`）；**禁止** finalize 后新事件；**无** finalize archive 的 Kafka 补发要求 |

#### 7 — E2 幂等

| 项 | 结论 |
|---|---|
| 操作 | 同一 `message_id` POST 两次 |
| HTTP | 两次均 200；第二次 `status=duplicate`，`compression_status=not_triggered` |
| Redis | `message_ids` 集合大小不变；`messages` 列表长度不变；`estimated_tokens` 第二次不变 |

#### 8 — E3 并发 write-vs-close

| 项 | 结论 |
|---|---|
| 模式 | `asyncio.gather` 或线程池：**同时** POST message 与 POST close（真实 Redis） |
| 合法结果 | (a) write `session_closing` / 409 类 **或** (b) close 200 `closed` 且 write 失败 closed path **或** (c) close 503 `close_incomplete` 且 WM 仍可恢复 |
| 禁止 | 双写成功同一 message；终端后 WM 幽灵数据 |
| 断言 | 终态 Redis 一致：要么 keys 已删（closed），要么 `status=closing/active` 且不变量成立 |

#### 9 — E4 代表性失败（单选）

| 项 | 结论 |
|---|---|
| 选定场景 | **LLM 失败**：消息已写入；HTTP **200** `status=success` `compression_status=failed`（STM-009 §5.0） |
| 理由 | §3.28 要求 LLM 超时/失败；Integration 已覆盖 Kafka/close 部分失败；E2E 补 HTTP 层证据 |
| 实现 | **Hybrid fixture**（§5.2）：compose 真实 Redis/Mongo/Kafka + **in-process** `create_app(..., llm_client=FakeLlmClient(mode="timeout"))` + `httpx.ASGITransport`；**仍走 HTTP 路由** |
| 断言 | HTTP 200 failed；Redis 消息仍在；pending 保留；`compression_version` 未 bump；Kafka 见 §5.0 #6 / §8.4 E4 |
| 生产变更 | **默认无**；hybrid 使用既有 `create_app` `llm_client` 参数 |

#### 10 — HALT 协议

| 条件 | 动作 |
|---|---|
| E1 失败且根因在 `src/**` STM 实现 | **HALT**；输出缺陷报告；**不得** 本任务修复 |
| 需修改 STM-001~010 Contract 才能绿 | **HALT** → 新任务 |
| 仅测试断言/构造错误 | 允许修测试 |

#### 11 — STM-011 边界

| 项 | 结论 |
|---|---|
| 是否前置 | **否** |
| E2E 是否测 republish | **否** |
| Kafka publish_failed 合法态 | E1 不断言补发；允许日志级失败若 LLM 仍完成（Integration 已覆盖） |

#### 12 — 默认生产变更

| 项 | 结论 |
|---|---|
| 默认 | **NONE** |
| 可选 seam（仅 HALT 后 Amendment） | `create_app` 读 `settings.app_env==test` 时 `FakeLlmClient(mode=...)`；**本计划不预批准** |

#### 13 — 测试标记与门禁（MF-1 OPTION 2）

| 项 | 结论 |
|---|---|
| 权威目录 | `tests/e2e/`（**非** `tests/integration/` 冒充 E2E） |
| Marker | `@pytest.mark.integration`（**已** 在 `pyproject.toml` `markers` 注册） |
| **禁止** | `@pytest.mark.e2e`；**禁止** 修改 `pyproject.toml` 增删 marker |
| `--strict-markers` | `pyproject.toml` `addopts` 含 `--strict-markers`；仅使用已注册 `integration` marker → **兼容**；未注册 marker 将导致 collection 失败 |
| 跳过 | 无 Docker → `pytest.skip` |
| Scoped | `uv run pytest tests/e2e/test_stm013_short_term_memory_e2e.py -v`（路径 scoped；**非** `-m e2e`；**非** `-m integration` 单独筛 E2E——本文件即 E2E 全集） |
| Full | unit + contract + ruff + mypy（§9） |

#### 14 — 文件白名单

见 §6；**禁止** 白名单外路径。

#### 15 — pr_sizing

`single PR, test-only, medium`（约 4 场景 + helpers + conftest；无 `src` 变更）。

---

### 5.1 压缩触发构造（开发者算法）

```python
def content_for_tokens(n: int) -> str:
  """ASCII-only; estimate_tokens(result) >= n."""
  return "b" * max(n * 4, 4)

async def write_until_trigger(
  client, *, user_id, session_id, trigger: int, ...
) -> None:
  total = 0
  while total < trigger:
    content = content_for_tokens(trigger - total)  # 或固定块 60 tokens 逐步逼近
    resp = post_message(...)
    assert resp.status_code == 200
    meta = await read_redis_meta(...)
    total = meta.estimated_tokens
  # 最后一次写入应使 compression_status != not_triggered
```

**注意**：必须用 **权威** `trigger`（§5.0 #2 同源读取）；不得写死 `200` 在断言逻辑中（`.env` 仅加速测试）。

### 5.2 E2E 架构（双 fixture + Compose 启动序 SF-3）

#### Compose 启动序（repo 事实；复用 Integration 模式）

`compose.sh --stack=test --embedding=none` 文件序：`compose.yaml` → `compose.test.yaml`（**替换** `compose.override.yaml`；**无** 主机端口绑定）。

| Step | 命令 / 动作 | 依据 |
|---|---|---|
| 0 | `_ensure_dotenv()`；备份 `.env`；写入 §5.0 #2 **协调 bundle**（**先于** memory-api）；teardown 恢复 | `x-app-env` env_file；SF-1；`validators.py` |
| 1 | `_compose("config", "--format", "json")` → `name == memory-system-test` | `test_message_write_coordinator_kafka.py` / `test_api_readiness.py` |
| 2 | `_compose("up", "-d", "redis", "mongodb", "kafka", "neo4j", "elasticsearch")` | `memory-api` `depends_on` healthy：redis/mongodb/neo4j/elasticsearch；`init-infra` 另需 kafka |
| 3 | bounded poll：container IP + kafka broker probe（`docker exec … kafka-broker-api-versions.sh`） | `test_message_write_coordinator_kafka.py` `full_stack`；**非** 固定 sleep |
| 4 | `_compose("run", "--rm", "init-infra")` exit 0 | `compose.yaml` `init-infra` depends_on mongodb/kafka/neo4j/elasticsearch healthy |
| 5 | `_compose("up", "-d", "memory-api")` | E1/E2/E3 Fixture A |
| 6 | bounded poll：`GET http://{api_ip}:8000/health/ready` → `status=ready` 且 `checks.migrations=ready`（deadline 180s） | `test_api_readiness.py` 模式；**非** sleep 猜就绪 |
| 7 | 读取权威 `ContextSettings`（§5.0 #2） | SF-1 config parity |
| 8 | `uv run pytest tests/e2e/...` | MF-1 scoped 路径 |
| teardown | 恢复 `.env` 备份；`_compose("down", check=False)` | Integration 惯例 + SF-1 防污染 |

```text
Fixture A — full_container（E1/E2/E3）
  compose: Step 1–7 全栈（含 init-infra + memory-api）
  HTTP client: httpx → http://{_container_ip("memory-system-api-test")}:8000
  Assert backends: host → container IP（Redis/Mongo/Kafka；Kafka 可复用 socket.getaddrinfo patch）
  Config: 权威 trigger 自容器/同源 .env（§5.0 #2）

Fixture B — hybrid_inprocess（E4 only）
  compose: redis + mongodb + kafka + neo4j + elasticsearch → init-infra（Step 2–4；**无** memory-api 容器）
  app = create_app(settings=..., app_state=await create_app_state(...),
                   llm_client=FakeLlmClient(mode="timeout"))
  HTTP client: httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
  Assert backends: 同 Fixture A container IP 模式
  Config: settings 与 Fixture A **同一** `.env` 源
```

### 5.3 实现步骤

**Step 1 — `tests/e2e/conftest.py`**

- 模块级 `full_stack` fixture：复用 Integration `_compose` / `_container_ip` / §5.2 启动序 Step 0–7 / topic 创建（`docker exec` kafka-topics）。
- `memory_api_base_url`：`_container_ip("memory-system-api-test")` + `:8000`（**非** `127.0.0.1`）。
- `memory_api_client`：bounded poll `GET /health/ready`；注入 `X-API-Key` headers。
- `authoritative_context_settings`：§5.0 #2 同源读取；供 trigger 构造。
- `redis_client` / `mongo_client` / `kafka_consumer`：bounded poll helper；事件过滤 `user_id`/`session_id`/`archive_id`。
- 唯一 ID：`user_id` / `session_id` / `message_id` per test。
- teardown：删 WM keys + 清 Mongo session archives（按 `session_id` 过滤）。
- 全部测试 `@pytest.mark.integration`。

**Step 2 — `tests/e2e/helpers/stm_e2e_helpers.py`**

- `content_for_tokens` / `estimate_tokens` 复用 import。
- `post_create_session` / `post_message` / `post_close` HTTP wrappers。
- `read_wm_meta` / `sum_message_tokens` / `list_archives_for_session` / `consume_kafka_events`。
- 全部 Redis key 经 `keys.py` helpers。

**Step 3 — `tests/e2e/test_stm013_short_term_memory_e2e.py`**

- `test_e1_happy_path_stm_vertical_slice` — §5.0 #4 全表。
- `test_e2_duplicate_message_id_idempotent` — §5.0 #7。
- `test_e3_concurrent_write_vs_close` — §5.0 #8。
- `test_e4_llm_failure_post_write_http_200_compression_failed` — §5.0 #9（Fixture B）。

**Step 4 — 文档化运行命令**

- Task Plan §9 验收命令；**不** 修改 README（非请求）。

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/e2e/__init__.py` | 创建 | 包标记 |
| `tests/e2e/conftest.py` | 创建 | compose fixtures、HTTP clients、backend 连接 |
| `tests/e2e/helpers/__init__.py` | 创建 | helpers 包 |
| `tests/e2e/helpers/stm_e2e_helpers.py` | 创建 | HTTP 封装、跨层断言、token 构造 |
| `tests/e2e/test_stm013_short_term_memory_e2e.py` | 创建 | E1–E4 场景 |

**默认禁止修改**：`src/**`、`tests/integration/**`、`tests/contract/**`、`compose.yaml`、`compose.test.yaml`、`scripts/compose.sh`、STM-001~010 Task Plans。

**条件例外（须 HALT + Amendment + 人工批准）**：`src/memory_system/api/app.py` 仅当 E4 无法通过 `llm_client` 注入完成且 Plan Reviewer 批准最小 seam。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用（测试只读断言） | E2E 验证 STM 已实现原子性 |
| 幂等 | E2 覆盖 | duplicate `message_id` 零副作用 |
| 并发 | E3 覆盖 | write-vs-close 终态一致 |
| 版本冲突 | E1 覆盖 | `compression_version` 0→1；close 快照 |
| 用户隔离 | E1 隐含 | 唯一 `user_id`；keys 含 user_id |
| 部分失败 | E4 覆盖 | LLM 失败消息不丢；pending 保留 |
| 进程异常恢复 | 不适用 | STM-011 范围；Integration 已覆盖 pending+Kafka failed |

---

## 8. 测试计划

### 8.1 Unit Test

| 场景 | 预期 |
|---|---|
| — | **本任务不新增 Unit**；沿用 STM-001~010 |

### 8.2 Contract Test

| 场景 | 预期 |
|---|---|
| — | **本任务不新增 Contract** |

### 8.3 Integration Test

| 场景 | 预期 |
|---|---|
| — | **不修改** 既有 Integration；E2E 与之互补 |

### 8.4 E2E Test — 场景矩阵（与 §5.0 #6 Kafka 矩阵 **完全一致**）

| ID | 场景 | HTTP 断言 | Redis 断言 | Mongo 断言 | Kafka 断言 |
|---|---|---|---|---|---|
| **E1** | STM 垂直 Happy Path | Create/Write/Close 200；`compression_status` 序列；`X-Request-ID` | version 0→1；trim；`compressed_context`；pending 空；lock 无；close 后 key 不存在 | compression + suffix archives；`base_compression_version` 区分 | **MANDATORY**：≥1 `context.archive.created`；`ARCHIVE_CREATED_EVENT_FIELD_NAMES` 全字段；过滤 `user_id`/`session_id`；AT_LEAST_ONCE |
| **E2** | duplicate `message_id` | 200 duplicate + `not_triggered` | 无二次写入 | 无新增 archive | **无新** compression/archive Kafka；duplicate 前后本 session 过滤事件集不变（**非** 全局 count） |
| **E3** | write ∥ close | 合法互斥状态码组合（closing 阻断 write） | 终态 WM 一致 | 无孤儿 incomplete archive | **若** suffix archive 产生 → close 路径事件（过滤 `user_id`/`session_id`/`archive_id`）；否则无硬性要求 |
| **E4** | LLM failure | 200 `success` + `compression_status=failed` | 消息保留；version 不变；pending 保留 | 无 finalize archive | STM-006/009 序：pending/archive 可在 LLM 前提交；**若** 已 publish → 允许 ≤1 条匹配 `archive_id` 事件；**无** finalize 后新事件 |

### 8.5 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| E3 | 并发 write-vs-close 无数据损坏 |
| E4 | LLM timeout；消息已写入不回滚（STM-009） |

**不重复**：Kafka publish_failed（STM-009 I-I）、close_incomplete terminal patch（STM-010 Integration）、Finalize version_conflict（STM-008 Integration）。

---

## 9. 验收标准

- [ ] `tests/e2e/test_stm013_short_term_memory_e2e.py` E1–E4 **全部 PASS**（Docker 可用环境）
- [ ] E1 主流程 **仅** 经公共 HTTP API 驱动；跨 HTTP/Redis/Mongo/Kafka 断言完整
- [ ] Fixture A：`ContextSettings` 与 memory-api 容器运行时 **同源**（§5.0 #2 invariant）
- [ ] 压缩触发使用权威 `compression_trigger_tokens`；构造逻辑含 `estimate_tokens` 数学
- [ ] Kafka 断言按 §5.0 #6 / §8.4 矩阵；过滤 `user_id`/`session_id`/`archive_id`；禁止脆弱全局计数
- [ ] `@pytest.mark.integration`；**无** `@pytest.mark.e2e`；**无** `pyproject.toml` 变更；`--strict-markers` 兼容
- [ ] Compose 启动序符合 §5.2（init-infra → memory-api → readiness poll）；**无** sleep 猜就绪
- [ ] `compression_version` 生命周期与 `base_compression_version` close 快照符合 §5.0 #3
- [ ] Redis key 断言 **仅** 经 `keys.py` helpers
- [ ] OI-004：token 边界断言使用 Redis `estimated_tokens` 求和
- [ ] 默认 **无** `src/**` 变更；若有 seam 须 Amendment 记录
- [ ] `uv run pytest tests/e2e/test_stm013_short_term_memory_e2e.py -v` PASS
- [ ] `uv run pytest tests/unit -q` PASS
- [ ] `uv run pytest tests/contract -q` PASS
- [ ] `uv run ruff check .` PASS
- [ ] `uv run mypy src tests scripts` PASS
- [ ] 白名单外无改动；无 TODO/pass/空实现
- [ ] Review 无 P0/P1

---

## 10. 风险与阻塞项

### 10.1 设计文档冲突

- §3.32 #4 全链路 E2E vs 本任务 STM 切片：**无冲突**——`master_plan` STM-013 权威收窄范围。

### 10.2 STM-011 非 blocker

- republish 脚本 **不** 为 E1 通过前提；Kafka AT_LEAST_ONCE + Mongo 持久化已足够 STM 里程碑。

### 10.3 HALT 风险

| ID | 描述 | 缓解 |
|---|---|---|
| R1 | E1 暴露 STM 缺陷 | HALT；独立修复任务 |
| R2 | compose memory-api 启动慢/不稳 | §5.2 Step 6 readiness poll + 180s deadline；container IP（非 127.0.0.1） |
| R3 | E4 hybrid 与 container E1 双模式维护 | 共用 helpers；文档化 Fixture A/B |
| R4 | 默认 trigger=5000 导致 E1 慢 | `CONTEXT__COMPRESSION_TRIGGER_TOKENS` 测试 env（非 src） |
| R5 | Kafka flake | bounded poll；unique `group_id` |

**BLOCKER**：无。**MUST_FIX（计划审批）**：Round 2 闭合 MUST_FIX-1（协调 `.env` bundle + 恢复）；待 Plan Reviewer Round 2 确认

### 10.4 其他

- **不得** 触碰 DEV-006 / PR #13。
- STM-012 待 EXT-001；本任务 **不** 阻塞 EXT 规划。

---

## 11. Git 计划

```yaml
branch: "feat/STM-013-short-term-memory-e2e"
pr_sizing: "single PR, test-only, medium"
expected_commits:
  - "docs(plan): add STM-013 short term memory e2e plan"
  - "test(e2e): add STM vertical slice end-to-end tests"
out_of_scope_changes:
  - "src/** 业务实现（默认禁止）"
  - "STM-011 republish 脚本"
  - "STM-012 EXT 消费验证"
  - "修改 STM-001~010 核心 Contract"
  - "compose.yaml / compose.test.yaml 语义变更"
  - "DEV-006 / PR #13"
```

```text
1. 独立 Plan Review → PLAN_APPROVED
2. PLAN_LANDING：docs(plan) on main
3. feat/STM-013-short-term-memory-e2e
4. Developer：tests/e2e/** only（默认）
5. Code Review → IMPLEMENTATION_RELEASE → PR
6. POST_MERGE_CLEANUP → v0.2.0-short-term-memory milestone 登记
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 002（Round 2 Plan Remediation）

| MF/SF | 修订 |
|---|---|
| MF-1 | `tests/e2e/` 权威；`@pytest.mark.integration`；禁 `e2e` marker / `pyproject.toml`；scoped `pytest tests/e2e/...`；`--strict-markers` 显式兼容 |
| SF-1 | Fixture A E2E settings == memory-api runtime；同源 `.env`；权威读取路径文档化；禁 host/container 分叉 |
| SF-2 | §5.0 #6 与 §8.4 Kafka 矩阵对齐（E1 mandatory / E2 no-new / E3 suffix-conditional / E4 STM-006/009 ordering） |
| SF-3 | Compose 启动序自 `compose.yaml`+`compose.test.yaml`；复用 `test_api_readiness`/`compose.sh`；test 栈无 override 端口 → container IP |

### Amendment 003（Round 2 Review MUST_FIX-1）

| MF/SF | 修订 |
|---|---|
| MUST_FIX-1 | §5.0 #2 协调 `.env` bundle（含 `MAX_COMPRESSED_CONTEXT_ESTIMATED_TOKENS` 等）；Step 0/teardown `.env` 备份与恢复；对齐 integration `test_settings` 与 `validators.py` |

### Amendment 001

（预留）

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
|  |  |  |  |  |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
|  |  |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| E2E scoped | `uv run pytest tests/e2e/test_stm013_short_term_memory_e2e.py -v` |  |
| Full Unit | `uv run pytest tests/unit -q` |  |
| Full Contract | `uv run pytest tests/contract -q` |  |
| Ruff | `uv run ruff check .` |  |
| Mypy | `uv run mypy src tests scripts` |  |

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
