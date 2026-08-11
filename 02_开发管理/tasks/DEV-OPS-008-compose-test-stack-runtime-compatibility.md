# DEV-OPS-008 Compose test-stack runtime compatibility (aiokafka 0.13 + Elasticsearch 9.4 mapping API)

## 1. 任务信息

```yaml
task_id: DEV-OPS-008
task_name: Compose test-stack runtime compatibility (aiokafka 0.13 + Elasticsearch 9.4 mapping API)
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§2.2.4 Elasticsearch Mapping（DEV-004 assert_mapping_compatible 读回兼容）"
  - "§3.4 Compose test stack（compose.test.yaml + memory-api 启动/readiness）"
  - "DEV-005 readiness：`kafka_producer` / `elasticsearch` blocking checks"
  - "非业务规格：compose test-stack 运行时与 pinned 依赖（aiokafka 0.13 / ES 9.4）对齐"
prerequisites:
  - "main @ 390af52f58509e323dd6500e77524033e0b5dcbf == origin/main（用户声明 authoritative baseline；规划轮次 Orchestrator 只读：feat/STM-013 分支存在但本任务分支必须从 clean main 创建）"
  - "STM-010 completed（PR #29 MERGED）；STM-013 blocked — BLOCKED_BY_DEFECT_FIX；PR #30 OPEN 不得 merge"
  - "pinned：aiokafka 0.13.0（uv.lock）；elasticsearch[async] 9.4.1（uv.lock）；ELASTICSEARCH_IMAGE 9.4.4（versions.env）"
  - "缺陷 provenance：STM-013 scope remediation 记入 progress.md stm_013_scope_remediation；prototype evidence 975e6029（不得 cherry-pick 整 commit）"
branch: "feat/DEV-OPS-008-compose-test-stack-runtime-compatibility"
branch_provenance:
  base: "main @ 390af52f58509e323dd6500e77524033e0b5dcbf"
  forbidden_base: "feat/STM-013-short-term-memory-e2e（不得从 STM-013 feat 创建）"
  creation_timing: "PLAN_LANDING after PLAN_APPROVED（Release Operator on main）"
created_at: "2026-08-11 12:30 UTC"
updated_at: "2026-08-11 12:30 UTC"
blocking_relationship:
  blocks: STM-013
  stm_013_pr: "#30 OPEN — MUST NOT MERGE until DEV-OPS-008 merged + STM-013 revalidation"
  stm_013_release_gate: BLOCKED_BY_DEFECT_FIX
approval_gates:
  planning_docs: "PLAN_APPROVED"
  human_plan_approved_at: "2026-08-11T12:28:00+08:00"
  human_amendments:
    - "C1 client is None → fail-closed (kafka_ready=False); never kafka_ready=True without valid client or bootstrap_connected probe"
    - "C1-U5: client is None → not ready"
    - "STM-013 shim cleanup record in governance post-merge"
    - "Single implementation commit preferred (C1+C2)"
  implementation_plan: "tested pending"
insertion_override:
  prior_current_task: STM-013
  prior_current_task_status: blocked
  prior_next_action: "DEV-OPS-008 PLANNING (human explicit); STM-013 revalidate after DEV-OPS-008 merge"
  override_by: "用户显式 NEW_TASK=DEV-OPS-008 + WORKFLOW_MODE=NORMAL(explicit)"
  effect: "current_task=DEV-OPS-008 planned；修复 C1/C2 compose runtime blockers；STM-013 保持 blocked 直至本任务 merge + 下游 revalidation"
```

---

## 2. 任务目标

修复 compose **test stack** 上 `memory-api` 因 **pinned 运行时依赖** 与 **生产 readiness 探针** 不兼容导致的启动/lifespan 失败，使：

1. **C1（aiokafka 0.13）**：`create_app_state` 在 `AIOKafkaProducer.start()` 成功后不再调用已移除的 `AIOKafkaClient.bootstrap_connected()`；`kafka_producer_ready` 与后续 `check_kafka_producer` 语义保持 fail-closed。
2. **C2（Elasticsearch 9.4）**：`assert_mapping_compatible` 对 ES 9.4 `GET mapping` 省略默认 `element_type` 的读回兼容；**索引创建**仍显式写入 `element_type: float`；`dims` / `similarity` / 必填字段 / `index_options` 仍严格 fail-closed。
3. **可审计镜像验证（SOURCE-ALIGNED IMAGE REBUILD）**：自 main（无修复）可复现 FAIL；自 DEV-OPS-008 feat（有修复）+ **fresh image** 可验证 PASS；记录 build 命令、source commit、image/container identity、readiness 结果。
4. **回归套件全绿**：新增/扩展 C1/C2 unit tests；compose `memory-api` 启动 + `/health/ready`；full unit / contract / FULL_RUFF / mypy。

完成后 **解除 STM-013 的 C1/C2 blocker**（STM-013 仍须独立 revalidation + CODE_REVIEW；不得通过本任务 merge PR #30）。

---

## 3. 非目标

- 修改 **STM-013** Task Plan、`tests/e2e/**`、PR #30 其余 diff（E2E 实现保留在 feat/STM-013；**不得** commit 到 DEV-OPS-008 白名单）。
- Cherry-pick 整 commit `975e6029`（仅借鉴 C1/C2 生产路径补丁思路）。
- 修改 `MEMORY_RETRIEVAL_V1_MAPPINGS` **索引创建 schema**（§2.2.4 结构不变；`element_type: float` 保持显式）。
- 修改 Kafka producer **生命周期、配置、topic、acks、idempotence、compression** 或 STM-006 publish 行为。
- 修改 `compose*.yaml`、`versions.env`、Dockerfile、`.env.example`（除非 Plan Reviewer 裁定镜像标签漂移；默认不碰）。
- 操作 **DEV-006 / PR #13**（DO_NOT_MERGE）。
- 自动 Push / Merge / Rebase / Force Push；`gh pr merge`。
- 将 STM-013 标为 completed 或 merge PR #30。

---

## 4. 当前代码状态

### 4.1 只读确认（Planner 规划轮次已验证）

#### Git / 基线

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `feat/STM-013-short-term-memory-e2e`（**非**本任务工作分支） |
| main authoritative baseline | `390af52f58509e323dd6500e77524033e0b5dcbf`（`docs(status): complete STM-010 after PR merge`） |
| STM-013 feat HEAD | `8061e6c`（C1/C2 已于 `aa636ad` 从 effective diff 移除） |
| `git status --short` | clean（规划轮次） |
| 分支创建要求 | **必须从 clean main 创建** `feat/DEV-OPS-008-compose-test-stack-runtime-compatibility` |

#### Pinned 依赖

| 包 | pyproject.toml | uv.lock | 备注 |
|---|---|---|---|
| aiokafka | `>=0.13,<0.14` | **0.13.0** | `uv run python -c` 确认 `aiokafka.__version__ == 0.13.0` |
| elasticsearch[async] | `>=9.4,<9.5` | **9.4.1** | Python client |
| ES container image | — | — | `versions.env`：`ELASTICSEARCH_IMAGE=docker.elastic.co/elasticsearch/elasticsearch:9.4.4` |
| ES version check | — | — | `settings.memory_retrieval.elasticsearch_version = "9.4.4"`（`models.py`） |

#### C1 — aiokafka 0.13 API 契约（Planner 闭合）

| # | 契约项 | 结论 |
|---|---|---|
| 1 | 精确安装版本 | **0.13.0**（`uv.lock` + runtime 验证） |
| 2 | `AIOKafkaProducer.start()` 成功契约 | `await start()` 成功返回 `None`；失败抛异常（连接/bootstrap 失败时 lifespan 应 fail-fast，与现行为一致） |
| 3 | 0.13 权威 readiness 信号 | **`bootstrap_connected` 已移除**；`AIOKafkaClient` 仅有 `bootstrap` 方法（async 内部）；**无**等价公共同步探针 |
| 4 | 公共 API 替代 | **无**直接替代 `bootstrap_connected()` 的公共 API；旧版 aiokafka 曾有该方法 |
| 5 | `start()` 成功 → `kafka_ready=True` fallback | **允许**：`start()` 成功即表示 producer 已 bootstrap；与 DEV-005 readiness 语义一致 |
| 6 | `_closed` / 后续 health check | `check_kafka_producer`：`kafka_producer_ready and not kafka_producer._closed` → `ready`；shutdown 后 `_closed` 保护 |
| 7 | 向后兼容 | `hasattr(kafka_client, "bootstrap_connected")` 时仍调用；仅 0.13+ 走 fallback |

**Invariant**：不改 producer 构造参数、`settings.kafka*`、`settings.kafka_producer*`、topic 名、STM-006 publish 路径。

**缺陷代码**（main @ 390af52，`runtime.py` L114）：

```python
kafka_ready = kafka_producer.client is not None and kafka_producer.client.bootstrap_connected()
```

→ `AttributeError: 'AIOKafkaClient' object has no attribute 'bootstrap_connected'`

**Prototype 评估**（975e6029，`runtime.py`）：**REUSE** — `hasattr` guard + else `kafka_ready=True`；注释说明 0.13 移除原因。无需调整逻辑。

#### C2 — Elasticsearch 9.4 mapping 读回契约（Planner 闭合）

| # | 契约项 | 结论 |
|---|---|---|
| 1 | Compose ES 精确版本 | Image **9.4.4**（`versions.env`）；runtime version check **9.4.4**（settings） |
| 2 | Index create 仍显式 `element_type=float` | `MEMORY_RETRIEVAL_V1_MAPPINGS` L34：`"element_type": "float"` — **不变** |
| 3 | 持久化行为仍为 float 默认 | CREATE 显式写入；存储为 float dense_vector |
| 4 | GET mapping 省略 `element_type` 原因 | ES 9.4 Mapping API **省略与默认值相同的字段**；float 为 `dense_vector.element_type` 默认 → GET 响应可为 `None`/缺失 |
| 5 | 仍须 strict 的字段 | 全部 property `type`；text `analyzer`；dense_vector **`dims`**、**`similarity`**；`index==True`；`index_options.{type,m,ef_construction}`；全部 mandatory top-level fields 存在 |
| 6 | `element_type` 何时 fail-closed | **仅当** `expected_element` 与 `actual_element` **均非 None** 且 **不相等** 时 `ValueError`；一方为 None → 视为默认兼容 |

**Invariant**：不修改 `MEMORY_RETRIEVAL_V1_MAPPINGS`；仅调整 `assert_mapping_compatible` **读回兼容检查**。

**缺陷代码**（`003_elasticsearch_memory_v1.py` L74–78）：循环比较 `dims, element_type, similarity` 严格相等 → `None != "float"` → `ValueError` → `check_elasticsearch` → `/health/ready` 503。

**Prototype 评估**（975e6029）：**REUSE** — `dims`/`similarity` 保持严格循环；`element_type` 独立三元条件比较。无需调整。

#### 既有测试

| 文件 | 现状 | 本任务 |
|---|---|---|
| `tests/unit/test_elasticsearch_mapping_contract.py` | 常量结构 + `wrong_dims` 拒绝 | 扩展 C2-U3～U5 |
| Contract tests | mock `bootstrap_connected` on kafka client | 保持；不依赖生产路径修复 |
| `tests/e2e/conftest.py` | `_patch_aiokafka_bootstrap_connected` shim（STM-013 only） | **NOT in whitelist** |
| Runtime kafka unit tests | **缺失** | 新增 `tests/unit/test_runtime_kafka_readiness.py`（C1-U1～U4） |

#### 前置任务检查

| 任务 | 状态 |
|---|---|
| DEV-004（ES mapping migration） | completed |
| STM-006（Kafka publish） | completed — 本任务不改 publish |
| STM-013 | **blocked** — `blocking_task=DEV-OPS-008`；PR #30 OPEN |

---

## 5. 实现方案

### Step 1 — C1：`runtime.py` aiokafka 0.13 readiness guard

- **文件**：`src/memory_system/infrastructure/runtime.py`
- **函数**：`create_app_state`（L112–114 区域）
- **输入**：`kafka_producer` 已完成 `await start()`
- **输出**（Human PLAN_APPROVED + Plan Reviewer SHOULD_FIX 吸收）：
  ```python
  kafka_client = kafka_producer.client
  if kafka_client is None:
      kafka_ready = False  # fail-closed; never mark ready without client
  elif hasattr(kafka_client, "bootstrap_connected"):
      kafka_ready = kafka_client.bootstrap_connected()
  else:
      # aiokafka >=0.13 removed bootstrap_connected; start() success is sufficient.
      kafka_ready = True
  ```
- **错误处理**：`start()` 异常仍向上传播（lifespan fail-fast）；不吞异常
- **幂等/并发**：无共享可变状态；只读 client 探针
- **禁止**：修改 producer 构造、`shutdown_app_state`、`check_kafka_producer` 逻辑（除非 Reviewer 要求统一注释）

### Step 2 — C2：`assert_mapping_compatible` ES 9.4 读回兼容

- **文件**：`scripts/migrations/003_elasticsearch_memory_v1.py`
- **函数**：`assert_mapping_compatible` dense_vector 分支（L73–91 区域）
- **输入**：ES `GET mapping` 返回的 `actual_mappings`
- **输出**：
  - `dims`、`similarity`：保持严格 `actual.get(key) != expected.get(key)` → `ValueError`
  - `element_type`：仅当 `expected_element is not None and actual_element is not None and actual_element != expected_element` → `ValueError`
  - `index`、`index_options`：保持现有严格检查
- **错误处理**：不 silent overwrite；不 catch-and-ignore
- **禁止**：修改 `MEMORY_RETRIEVAL_V1_MAPPINGS`；修改 `upgrade()` create 路径

### Step 3 — Unit tests（C1 + C2）

- **文件**：
  - **新建** `tests/unit/test_runtime_kafka_readiness.py`（C1-U1～U5）
  - **修改** `tests/unit/test_elasticsearch_mapping_contract.py`（C2-U1～U5）
- **C1-U1**：mock producer，`client` 无 `bootstrap_connected`，`client` 非 None，`start` 成功 → `kafka_producer_ready is True`
- **C1-U2**：mock `bootstrap_connected` 返回 `False` → `kafka_producer_ready is False`
- **C1-U3**：mock `bootstrap_connected` 返回 `True` → `kafka_producer_ready is True`
- **C1-U4**：`check_kafka_producer`：`kafka_producer_ready=True` 且 `_closed=True` → `not_ready`
- **C1-U5**：`client is None` → `kafka_producer_ready is False`（fail-closed；不得错误 ready）
- **C2-U3**：`element_type` 从 embedding 拷贝后 **del/pop** → `assert_mapping_compatible` **不抛**
- **C2-U4**：`element_type="byte"`（显式错误）→ **ValueError**
- **C2-U5**：`similarity="dot_product"` → **ValueError**
- **保留**：现有 `wrong_dims`（C2-U2）与常量测试（C2-U1）

### Step 4 — SOURCE-ALIGNED IMAGE REBUILD 与 baseline/fix 验证

#### 4.1 镜像来源对齐（强制）

| 项 | 要求 |
|---|---|
| Build 命令 | `./scripts/compose.sh --stack=test --embedding=none build --no-cache memory-api` |
| Source commit 记录 | baseline：`390af52`（main，无 C1/C2 修复）；fix：`DEV-OPS-008 implementation commit` |
| Image identity | `docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedAt}}' \| grep memory-system` + `docker inspect memory-system-api-test --format '{{.Image}}'` |
| Container identity | `docker ps -a --filter name=memory-system-api-test --format '{{.ID}} {{.Image}} {{.Status}}'` |
| 禁止 | 使用 stale cached image 未 `--no-cache` rebuild 即宣称 PASS |

#### 4.2 Baseline 复现（isolated worktree from main，无修复）

```bash
# 1. Isolated worktree at main baseline（不得混入 STM-013 feat）
git worktree add /tmp/ms-dev-ops-008-baseline 390af52f58509e323dd6500e77524033e0b5dcbf
cd /tmp/ms-dev-ops-008-baseline
cp .env.example .env  # if needed

# 2. Fresh image + stack
./scripts/compose.sh --stack=test --embedding=none build --no-cache memory-api
./scripts/compose.sh --stack=test --embedding=none up -d mongodb kafka neo4j elasticsearch redis init-infra
./scripts/compose.sh --stack=test --embedding=none up -d memory-api

# 3. 记录 FAIL 证据
docker logs memory-system-api-test 2>&1 | tail -50   # expect AttributeError (C1) and/or ES not_ready (C2)
curl -sS http://127.0.0.1:8000/health/ready         # expect 503 or container restart

# 4. Teardown + worktree cleanup
./scripts/compose.sh --stack=test --embedding=none down
git worktree remove /tmp/ms-dev-ops-008-baseline
```

**预期**：C1 lifespan `AttributeError` **和/或** C2 `elasticsearch not_ready`（取决于 init-infra 与启动顺序）；**不得** stale image false PASS。

#### 4.3 Fix 验证（DEV-OPS-008 feat + fresh image）

```bash
# On feat/DEV-OPS-008-compose-test-stack-runtime-compatibility after implementation
./scripts/compose.sh --stack=test --embedding=none build --no-cache memory-api
./scripts/compose.sh --stack=test --embedding=none up -d
# wait healthchecks
curl -sS http://127.0.0.1:8000/health/ready | jq .
# expect status=ready; kafka_producer=ready; elasticsearch=ready
docker inspect memory-system-api-test --format '{{.Image}}'  # record image ID
./scripts/compose.sh --stack=test --embedding=none down
```

**验收记录写入**：本 Task Plan §13 执行记录 + `progress.md` verified 字段（实施后）。

### Step 5 — 全量回归

| 层级 | 命令 | 预期 |
|---|---|---|
| Scoped unit C1 | `uv run pytest tests/unit/test_runtime_kafka_readiness.py -q` | 全绿 |
| Scoped unit C2 | `uv run pytest tests/unit/test_elasticsearch_mapping_contract.py -q` | 全绿 |
| Full unit | `uv run pytest tests/unit -q` | 全绿 |
| Full contract | `uv run pytest tests/contract -q` | 全绿 |
| Integration readiness | `uv run pytest tests/integration/test_api_readiness.py -q`（若 memory-api 在栈上） | 不回归 |
| Ruff | `uv run ruff check .` | FULL_RUFF PASS |
| Mypy | `uv run mypy src tests scripts` | PASS |

### Step 6 — 治理回写

- **文件**：`02_开发管理/progress.md`、`02_开发管理/master_plan.md`、本 Task Plan §13–§14
- **STM-013**：保持 `blocked`；更新 `formal_DEV-OPS-008_status`；**不** merge PR #30
- **STM-013 shim cleanup record**（Human PLAN_APPROVED）：DEV-OPS-008 merge 后，STM-013 revalidation 须检查 `tests/e2e/conftest.py` 等是否仍有 C1/C2 prototype shim（如 `_patch_aiokafka_bootstrap_connected`）；若存在，由 STM-013 在其 approved scope 内清理；**不得**在 DEV-OPS-008 修改 `tests/e2e/**`；若不存在则记录 `NONE`

---

## 6. 文件变更清单

### 6.1 Exact writable whitelist（实施阶段允许路径）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/infrastructure/runtime.py` | 修改 | C1 aiokafka 0.13 readiness guard |
| `scripts/migrations/003_elasticsearch_memory_v1.py` | 修改 | C2 ES 9.4 mapping readback compat |
| `tests/unit/test_runtime_kafka_readiness.py` | **创建** | C1-U1～U5 |
| `tests/unit/test_elasticsearch_mapping_contract.py` | 修改 | C2-U3～U5 |
| `02_开发管理/tasks/DEV-OPS-008-compose-test-stack-runtime-compatibility.md` | 修改 | 执行记录 / 镜像 provenance |
| `02_开发管理/progress.md` | 修改 | DEV-OPS-008 治理字段 |
| `02_开发管理/master_plan.md` | 修改 | DEV-OPS-008 状态回写 |

### 6.2 Exact forbidden paths（命中即越权）

| 路径/范围 | 原因 |
|---|---|
| `tests/e2e/**` | STM-013 scope；非本任务白名单 |
| `tests/e2e/conftest.py` shim | STM-013 only |
| `tests/__init__.py` | STM-013 adjunct |
| `02_开发管理/tasks/STM-013-*.md` | STM-013 Task Plan |
| PR #30 其余文件 | E2E 实现不得混入 |
| `compose*.yaml`、`versions.env`、`Dockerfile` | 默认不碰 |
| `src/**` 除 `runtime.py` | 范围外 |
| `scripts/**` 除 `003_elasticsearch_memory_v1.py` | 范围外 |
| DEV-006 feat / PR #13 | DO_NOT_MERGE |
| `01_技术规格/**`、五命令正文 | 禁改规格 |

**期望规模**：2 生产文件 + 1～2 测试文件 + 3 治理文档；≤8 文件。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 只读 readiness 探针与 mapping 断言；无多写事务 |
| 幂等 | 适用 | `assert_mapping_compatible` 纯函数；readiness guard 无副作用 |
| 并发 | 不适用 | 启动时单次探针；health check 读 `_closed` |
| 版本冲突 | 不适用 | 无业务版本字段 |
| 用户隔离 | 不适用 | 基础设施层 |
| 部分失败 | 适用 | C1/C2 任一未修复 → compose readiness FAIL；不得标 tested |
| 进程异常恢复 | 适用 | `check_kafka_producer` 依赖 `_closed`；producer stop 后 not_ready |

---

## 8. 测试计划

### Unit Test

| 场景 | ID | 预期 |
|---|---|---|
| 常量 `MEMORY_RETRIEVAL_V1_MAPPINGS` 结构 | C2-U1 | 现有测试保持 PASS |
| `wrong_dims` 拒绝 | C2-U2 | 现有测试保持 PASS |
| GET mapping 省略 `element_type` 兼容 | C2-U3 | `assert_mapping_compatible` 不抛 |
| 显式错误 `element_type` | C2-U4 | `ValueError` |
| 错误 `similarity` | C2-U5 | `ValueError` |
| 无 `bootstrap_connected` + valid client + start 成功 | C1-U1 | `kafka_producer_ready=True` |
| `client is None` | C1-U5 | `kafka_producer_ready=False` |
| `bootstrap_connected()` 返回 False | C1-U2 | `kafka_producer_ready=False` |
| `bootstrap_connected()` 返回 True | C1-U3 | `kafka_producer_ready=True` |
| `_closed` 后 health check | C1-U4 | `check_kafka_producer` → `not_ready` |

### Contract Test

| 场景 | 预期 |
|---|---|
| 既有 contract mock `bootstrap_connected` | 不修改语义；full contract 回归 PASS |

### Integration Test

| 场景 | 预期 |
|---|---|
| compose test stack + fresh image + `memory-api` up | 容器 lifespan 成功；无 AttributeError |
| `GET /health/ready` | `status=ready`；`kafka_producer=ready`；`elasticsearch=ready` |
| `tests/integration/test_api_readiness.py` | 不回归（可选/条件跳过保持） |

### E2E Test

| 场景 | 预期 |
|---|---|
| STM-013 E2E（`tests/e2e/**`） | **NOT in DEV-OPS-008 scope**；可作为 **下游证据**（isolated worktree feat/STM-013 **或** post-merge revalidation）；Plan Reviewer 裁定 governance-safe 路径 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| Baseline main worktree + fresh image | 复现 C1/C2 FAIL（auditable logs） |
| Explicit wrong `element_type` in mapping fixture | C2-U4 ValueError |
| Producer `_closed` after shutdown | C1-U4 not_ready |

### STM-013 下游验证（正式记录）

| 选项 | 说明 | Governance |
|---|---|---|
| A — isolated worktree | feat/STM-013 + merged DEV-OPS-008 main；跑 `tests/e2e/test_stm013_*.py` | 不得将 e2e 文件 commit 到 DEV-OPS-008 |
| B — post-merge revalidation | DEV-OPS-008 merge 后 STM-013 feat rebase/revalidate | PR #30 仍须 CODE_REVIEW + human merge |
| 禁止 | 在 DEV-OPS-008 PR 中包含 `tests/e2e/**` | 白名单外 |

**Plan Reviewer 须裁定**：验收阶段是否强制选项 A 作为 merge 前证据，或选项 B  suffices 作为 STM-013 unblock 条件。

---

## 9. 验收标准

- [ ] `runtime.py`：`hasattr(bootstrap_connected)` guard + 0.13 fallback；**无** producer 配置/生命周期变更
- [ ] `003_elasticsearch_memory_v1.py`：`MEMORY_RETRIEVAL_V1_MAPPINGS` **未改**；`assert_mapping_compatible` C2 逻辑与 prototype 一致
- [ ] C1-U1～U4、C2-U1～U5 全部 PASS
- [ ] Baseline worktree `390af52` + `--no-cache build` 复现 FAIL（日志/503 证据记入 §13）
- [ ] DEV-OPS-008 feat + `--no-cache build`：`memory-api` up；`/health/ready` → `ready`；image/container ID 记入 §13
- [ ] `uv run pytest tests/unit -q` 全绿
- [ ] `uv run pytest tests/contract -q` 全绿
- [ ] `uv run ruff check .` → FULL_RUFF PASS
- [ ] `uv run mypy src tests scripts` → PASS
- [ ] 白名单外零 diff（尤其 `tests/e2e/**`、STM-013 plan、PR #30）
- [ ] Review 无 P0/P1
- [ ] STM-013 保持 `blocked` 直至 Orchestrator 显式 revalidation；PR #30 未 merge

---

## 10. 风险与阻塞项

| 类别 | 内容 |
|---|---|
| 设计文档冲突 | **无** — §2.2.4 CREATE 仍显式 float；读回兼容为 ES API 行为对齐 |
| 当前代码冲突 | feat/STM-013 与 main 分叉；**必须从 main 建分支** |
| 前置任务 | STM-013 blocked on 本任务；不阻塞本任务实施 |
| 未批准依赖 | 无新依赖 |
| API/Schema 变化 | **无** HTTP/Schema 变更 |
| 镜像 provenance | stale image 可能导致 false PASS — **强制 `--no-cache build`** |
| STM-013 PR #30 | OPEN — **MUST NOT MERGE** 直至 revalidation |
| DEV-006 / PR #13 | DO_NOT_MERGE — 不得触碰 |
| Plan Reviewer 裁定 | STM-013 E2E 下游验证路径（选项 A vs B） |

---

## 11. Git 计划

```yaml
workflow_mode: NORMAL
authoritative_main_baseline: "390af52f58509e323dd6500e77524033e0b5dcbf"
branch: "feat/DEV-OPS-008-compose-test-stack-runtime-compatibility"
branch_from: "main @ 390af52（clean；NOT feat/STM-013）"
RELEASE_PHASE_sequence:
  PLAN_LANDING:
    when: "PLAN_APPROVED 后"
    on: main
    actions:
      - "git pull --ff-only"
      - "docs(plan): add DEV-OPS-008 implementation plan — commit on main"
      - "git push origin main"
      - "git checkout -b feat/DEV-OPS-008-compose-test-stack-runtime-compatibility"
  IMPLEMENTATION_RELEASE:
    when: "CODE_REVIEW_APPROVED 后"
    on: feat branch
    actions:
      - "git add（白名单精确路径 only）"
      - "fix(ops): compose test-stack aiokafka 0.13 and ES 9.4 mapping readback compat"
      - "git push origin feat/DEV-OPS-008-compose-test-stack-runtime-compatibility"
      - "gh pr create"
      - "optional: docs(status): record on feat"
  POST_MERGE_CLEANUP:
    when: "PR MERGED 后"
    on: main
    actions:
      - "git fetch; ff-only pull main"
      - "docs(status): complete DEV-OPS-008"
      - "git push origin main"
      - "git branch -d feat/DEV-OPS-008-compose-test-stack-runtime-compatibility"
      - "git push origin --delete feat/DEV-OPS-008-compose-test-stack-runtime-compatibility"
expected_commits:
  - "docs(plan): add DEV-OPS-008 compose test-stack runtime compatibility plan"
  - "fix(ops): aiokafka 0.13 readiness and ES 9.4 mapping readback compat"
  - "test(ops): unit coverage for kafka readiness and ES mapping compat"
out_of_scope_changes:
  - "tests/e2e/**"
  - "tests/__init__.py"
  - "STM-013 task plan / PR #30 files"
  - "compose*.yaml / versions.env / Dockerfile"
  - "DEV-006 / PR #13"
  - "cherry-pick 975e6029 wholesale"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-11 05:10 UTC | PLAN_LANDING | plan_commit `a464952` on main；feat 分支创建 | — | progress stash conflict resolved |
| 2026-08-11 05:16 UTC | Baseline reproduction | 无代码变更 | baseline image `fa1c24f18550` @ source `a464952`；container `db6c92e25d51`；**C1 AttributeError** `bootstrap_connected` | 本地 ephemeral `KAFKA_PRODUCER__COMPRESSION_TYPE=gzip` 仅用于绕过镜像缺 lz4 原生库以到达 C1 路径；**非 repo 变更** |
| 2026-08-11 05:16 UTC | C1/C2 implementation | `runtime.py`；`003_elasticsearch_memory_v1.py`；unit tests | C1-U1～U5 + C2-U1～U5 PASS；full unit 455；contract 101；FULL_RUFF PASS；mypy PASS | client=None fail-closed |
| 2026-08-11 05:16 UTC | Fixed image validation | 无额外 prod 变更 | image `b2d94086f63c`；container `0875143c22ff`；`/health/ready` HTTP 200；kafka_producer=ready；elasticsearch=ready | 同上 ephemeral gzip compression 仅本地验证 |
| 2026-08-11 09:55 UTC | POST_DEV-OPS-009 revalidation sync | cherry-pick `90cd79c`（cramjam lz4）onto feat → `9f47597` | — | 无 merge/rebase；DEV-OPS-009 task doc 保留 main 态（feat 上 absent 为 sync artifact） |
| 2026-08-11 09:56 UTC | Authoritative lz4 runtime validation | 无 prod 变更 | image `memory-api:devops008-revalidated` / `sha256:bf1edf179be9…`；container `7dbc9f5a2226`；compression_type=lz4；**无 gzip override** | startup PASS；C1/C2 PASS；`/health/ready` HTTP 200；kafka_producer=ready；elasticsearch=ready |
| 2026-08-11 09:58 UTC | Regression gates + Code Review | — | C1 5 / C2 7 / unit 459 / contract 101 / ruff PASS / mypy PASS / kafka lz4 integration 2 | CODE_REVIEW_APPROVED P0=0 P1=0；release_gate=WAITING_FOR_PR_MERGE |

### 镜像 provenance（SOURCE-ALIGNED）

| 阶段 | source commit | image tag / ID | container ID | 结果 |
|---|---|---|---|---|
| Baseline（无 C1/C2 fix） | `a464952021e3778bb8f29b96f867fc61619b8f76` | `devops008-baseline-a464952` / `sha256:fa1c24f18550…` | `db6c92e25d51` | C1 `AttributeError: bootstrap_connected`；lifespan startup failed |
| Fixed（C1+C2 实施） | `a464952` + uncommitted impl（待 commit） | `devops008-fixed-a464952-uncommitted` / `sha256:b2d94086f63c…` | `0875143c22ff` | `/health/ready` 200；`kafka_producer=ready`；`elasticsearch=ready`（ephemeral gzip 时代） |
| Revalidated（main+DEV-OPS-009 lz4） | `9f47597abeb0b69930f1cd18734049c2ee5a4497` | `memory-api:devops008-revalidated` / `sha256:bf1edf179be9babd435a390f84c7862c9e745f08b77110690baed240b5aef176` | `7dbc9f5a2226` | authoritative lz4；`/health/ready` 200；kafka_producer=ready；elasticsearch=ready |

**本地 build 参数（ephemeral；非 repo 变更）**：`docker build --network=host --no-cache --build-arg HTTP_PROXY=http://127.0.0.1:17890 --build-arg HTTPS_PROXY=http://127.0.0.1:17890`

**STM-013 shim cleanup note**：merge 后 STM-013 revalidation 须检查 `tests/e2e/conftest.py::_patch_aiokafka_bootstrap_connected`；若存在由 STM-013 scope 清理；DEV-OPS-008 不修改 `tests/e2e/**`

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/infrastructure/runtime.py` | C1 aiokafka 0.13 readiness guard |
| `scripts/migrations/003_elasticsearch_memory_v1.py` | C2 ES 9.4 element_type readback compat |
| `tests/unit/test_runtime_kafka_readiness.py` | 新建 C1-U1～U5 |
| `tests/unit/test_elasticsearch_mapping_contract.py` | C2-U3～U5 扩展 |

### 与原计划的差异

POST_DEV-OPS-009 revalidation：feat 分支 cherry-pick `90cd79c` 集成 cramjam（content identical to main）；权威 lz4 下 fresh image 验证 PASS（无 gzip override）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit C1 | `uv run pytest tests/unit/test_runtime_kafka_readiness.py -q` | 5 passed |
| Unit C2 | `uv run pytest tests/unit/test_elasticsearch_mapping_contract.py -q` | 7 passed |
| Full unit | `uv run pytest tests/unit -q` | 459 passed |
| Contract | `uv run pytest tests/contract -q` | 101 passed |
| Compose readiness | authoritative lz4 compose test stack | HTTP 200 ready |
| Baseline FAIL evidence | worktree `390af52` / `a464952` | C1 AttributeError recorded |
| Ruff | `uv run ruff check .` | PASS |
| Mypy | `uv run mypy src tests scripts` | PASS |

### Image provenance（实施后填写）

```yaml
baseline_worktree_commit: a464952021e3778bb8f29b96f867fc61619b8f76
baseline_image_id: sha256:fa1c24f18550f1e776b0a900d7e22c4b175aa3dd9df9b2b571476b8a37e956
baseline_readiness_result: C1 AttributeError bootstrap_connected
fix_commit: b2f29ee5eab17c02983ce5c041c7c821b8db8318
revalidated_source_sha: 9f47597abeb0b69930f1cd18734049c2ee5a4497
fix_image_id: sha256:bf1edf179be9babd435a390f84c7862c9e745f08b77110690baed240b5aef176
fix_container_id: 7dbc9f5a222659d1ca4eb427fbbeeb68072ff69a0ed37ff0dd84752317e8f84e
fix_readiness_result: HTTP 200; kafka_producer=ready; elasticsearch=ready; compression_type=lz4
gzip_override_used: false
build_command: "docker build --progress=plain --no-cache --network=host --build-arg HTTP_PROXY=... -t memory-api:devops008-revalidated ."
```

### Review 结果

```yaml
p0: 0
p1: 0
p2: 4
p3: 2
review_report: CODE_REVIEW_APPROVED (revalidation round POST_DEV-OPS-009)
```

### Git 记录

```yaml
branch: feat/DEV-OPS-008-compose-test-stack-runtime-compatibility
plan_commit: a464952021e3778bb8f29b96f867fc61619b8f76
implementation_commit: b2f29ee5eab17c02983ce5c041c7c821b8db8318
sync_commit: 9f47597abeb0b69930f1cd18734049c2ee5a4497
implementation_commit_message: "fix(ops): aiokafka 0.13 readiness and ES 9.4 mapping readback compat"
main_base: e5ed43bee0310f3c42d977d5bd109f96d7522cb2
pr: "#31 MERGED"
merge_commit: 49719b91e4be6c552c342fef45504166c919febd
merged_at: "2026-08-11T10:32:18Z"
```

### 最终状态

`completed`
