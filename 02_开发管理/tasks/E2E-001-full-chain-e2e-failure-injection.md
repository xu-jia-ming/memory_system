# E2E-001 全链路 E2E 与全部失败注入

## 1. 任务信息

```yaml
task_id: E2E-001
task_name: 全链路 E2E 与全部失败注入
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "bb0d387f509c38194cf511f580b98cf86f44b5a7"
branch: "feat/E2E-001-full-chain-e2e-failure-injection"
milestone: "v0.9.0-mvp-rc1 (E2E suite delivery only; RC checklist = REL-001 OUT OF SCOPE)"
created_at: "2026-08-15 02:10 UTC"
updated_at: "2026-08-15 03:55 UTC"
plan_amendment: "001 — Round 1 PLAN_REJECTED remediation (session 570cb388); Round 2 PLAN_APPROVED (session 20220a4e-dd78-4a44-b130-9eeec0b11d74)"
spec_sections:
  - "§3.28 测试策略（E2E 层；独立 DB/Index/Topic/Volume；Fake LLM 默认；CI 不计费 API；失败注入五条；合并前 Unit+Contract+Integration；发布前完整 E2E）"
  - "§3.32 MVP 开发完成验收标准 #4 全链路；#5 幂等无重复；#6 失败注入+原文不丢+人工恢复；#7 CPU embedding 必测；#8 HTTP 统一错误/user_id 隔离/敏感日志（E2E 断言子集）"
  - "§3.32 #1/#2/#3/#9 — 消费 OPS-003/004 前置；本任务不重做"
  - "§1.2.3 Session Close 部分归档成功 / close_incomplete / archive_batch_key 复用（#8–#11；INJ-5 锁定 #11）"
  - "§1.2.6 #10 Kafka 发布失败不阻塞压缩；保存点为 Mongo Archive 非 Redis WM；STM-011 republish 人工恢复（对照 I-I / U12）"
  - "§1.2.4 Kafka Event 设计（context.archive.created；人工补发工具）"
  - "§2.1.13 Worker 在 Neo4j Commit 后退出；§2.1.14/§2.1.15 Admin retry 仅适用于 status=failed（INJ-2/INJ-3）；INJ-4 走 EXT-009 F1 二次 run_worker_once"
  - "§2.2.3 Elasticsearch Bulk 部分失败 + Upsert 收敛"
  - "§3.3 / §3.4 compose.test 隔离；§3.23 统一 HTTP 包络（E2E 断言）"
prerequisites:
  formal:
    - "OPS-003 — SATISFIED/completed（PR #57 MERGED @ 89912ec）；master_plan Phase 5 正式前置"
    - "OPS-004 — SATISFIED/completed（PR #58 MERGED @ 3e6f8fa）；§3.32 #3 Unit+Contract+Integration + 80% 已交付；默认 CI 不含 E2E"
    - "OPS-001 — SATISFIED/completed（PR #55）；Compose SIGTERM / 全链路 timeout 注入 DEFERRED → 本任务"
    - "OPS-002 — SATISFIED/completed（PR #56）；本任务不重审计，仅 E2E 断言 #8 子集"
    - "STM-001..013 — SATISFIED/completed（STM-013 PR #30；垂直切片 Session→Archive→Compression→Close）"
    - "EXT-001..009 — SATISFIED/completed（EXT-009 PR #43；Archive→Extraction→Neo4j→ES）"
    - "RET-001..006 — SATISFIED/completed（RET-006 PR #49；Retrieval 垂直切片 + 通道失败注入）"
    - "CON-001..005 — SATISFIED/completed（CON-005 PR #54；Consolidation 垂直切片）"
    - "STM-011 republish — SATISFIED/completed（PR #33）；人工恢复路径"
    - "EXT-008 Admin retry/rebuild — SATISFIED/completed（PR #42）；人工恢复路径"
  implementation_reuse:
    - "tests/e2e/conftest.py — infra_stack / hybrid_api_client / ext009_runtime；compose.sh --stack=test --embedding=none"
    - "tests/e2e/helpers/stm_e2e_helpers.py — HTTP session/message/close + archive/kafka 断言"
    - "tests/e2e/helpers/ext009_e2e_helpers.py — build_pipeline / run_worker_once / BeforeRetrievalSyncHook / Fake LLM JSON"
    - "tests/e2e/helpers/ret006_e2e_helpers.py — retrieval HTTP client 模式（本任务经同一 in-process app 调用，不重写通道矩阵）"
    - "tests/e2e/helpers/con005_e2e_helpers.py — build_production_run_service"
    - "tests/support/fake_retrieval_index_embedding_client.py — FakeEmbeddingClient"
    - "tests/support/fake_retrieval_index_write_repository.py — Unit/INT 模式；**禁止**作为 E2E INJ-3 注入体（Amendment 001：包装生产 RetrievalIndexWriteRepository）"
    - "memory_system.infrastructure.llm.FakeLlmClient — success / timeout"
    - "scripts/republish_archive_event.py — STM-011 人工补发（测试经既有 service 调用，禁止新 HTTP）"
    - "EXT-008 POST retry/rebuild — 既有 Admin HTTP"
  baseline_evidence:
    branch: "main"
    head: "bb0d387f509c38194cf511f580b98cf86f44b5a7"
    head_short: "bb0d387"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=bb0d387f509c38194cf511f580b98cf86f44b5a7"
approval_gates:
  planning: "approved"
  human_plan_approved: true
  human_plan_approved_at: "2026-08-15 02:38 UTC"
  plan_review_round: 2
  plan_review_status: "Round 2 PLAN_APPROVED (session 20220a4e-dd78-4a44-b130-9eeec0b11d74; BLOCKER=0 MUST_FIX=0); Amendment 001 absorbed; Round 1 PLAN_REJECTED (session 570cb388) retained as history"
  plan_commit: "c2afaaa576107329ca6153a846fcb071c9383445"
  plan_landing_completed_at: "2026-08-15 02:42 UTC"
  developer_authorized: true
  reviewer_authorized: true
  release_operator_authorized: true
  next_action: "REL-001 planned / NOT AUTO-STARTED"
  post_human_plan_approved_state_machine: |
    Human PLAN_APPROVED received. status=approved; next_action=PLAN_LANDING then Developer on feat.
    developer_authorized=false until exact feat/E2E-001-full-chain-e2e-failure-injection exists.
    Do not start Developer on main. Developer starts only after PLAN_LANDING creates the feat branch.
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator lands this plan on main and creates exact feat/E2E-001-full-chain-e2e-failure-injection"
  IMPLEMENTATION_RELEASE: "feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "after verified MERGED PR; exact feat branch cleanup"
dependency_changes_expected: NONE
migration_changes_expected: NONE
production_file_whitelist_default: NONE
test_file_whitelist_default: "see §12"
```

### 1.1 本轮门禁

```yaml
phase: completed
must_not_this_round:
  - "编写业务实现或测试实现（Developer 仅在 feat 存在后启动）"
  - "在 main 上启动 Developer / Code Reviewer / Commit Recorder"
  - "IMPLEMENTATION_RELEASE / POST_MERGE_CLEANUP 命令"
  - "修改权威规格正文"
  - "读取 .env 或提交 Secret"
  - "触碰 DEV-006 / PR #13"
  - "吸收 REL-001 RC 清单或 05_测试与验收/mvp_acceptance_checklist.md 逐项勾选"
  - "将 E2E 纳入 OPS-004 默认 merge-gate / GitHub Actions PR 阻塞 job"
  - "启动真实计费 DeepSeek / SiliconFlow / TEI API"
stop_if:
  - "任何实现步骤需要改变 API Contract / Schema / 错误码 / 状态机 / 幂等或恢复语义"
  - "E2E 暴露生产缺陷时在本任务内修复（须 HALT → 报告 owning task）"
  - "默认 E2E 需要真实计费 LLM/Embedding API Key"
  - "需要新依赖或 Migration（dependency_changes_expected / migration_changes_expected 必须保持 NONE）"
  - "需要把 Fake LLM 做成生产 worker 默认或改 Settings Contract 才能跑全链"
blocking_open_issues: []
nonblocking_open_issues:
  - "OI-E2E1-VOL — tests/e2e/conftest.py 当前 down 无 -v；§3.28 #2 要求删除测试 Volume。Amendment 001：infra_stack 起止两次 down 均加 -v，仍 --stack=test / project memory-system-test only；禁止 down 开发 Volume"
  - "OI-E2E1-SIGTERM — extraction-worker 容器默认 DeepSeekLlmClient；共享 infra_stack 上 leftover context.archive.created 会被生产 group 消费并打 DeepSeek。Amendment 001：启动前 idle（consumer lag 0 / 无待消费事件）+ docker stop 后容器未运行 + 无 LLM HTTP；in-flight Neo4j-commit = INJ-4 hook。禁止为 SIGTERM 改生产 LLM 接线"
```

---

## 2. 任务目标

交付 **全链路 E2E 测试套件**（`tests/e2e/test_e2e001_*`），在 **compose.test 真实基础设施** + **Fake LLM / Fake Embedding / Fake Tokenize** 下，把既有垂直切片 **组合** 为规格 §3.32 #4 完整链，并覆盖 §3.28 五条失败注入与 §3.32 #5/#6 幂等/恢复。本任务 **默认零 `src/**` 生产变更**。

**可验证交付**：

1. **E2E-HP 全链路 happy path**（单测试、同一 `user_id`/`session_id`，禁止用预置 ES/Neo4j 种子替代 STM 产出）：
   `Session → Message → Archive → Compression → Extraction → Elasticsearch Sync → Retrieval → Consolidation → Session Close`
2. **§3.32 #5 幂等**：重复 `message_id`、重复 Kafka Event、Worker 重启、Extraction retry → 不产生重复 Message / Archive / Memory / Evidence / ES Document。
3. **§3.28 五条失败注入**（E2E 层，非仅 Unit）：Archive 已写入但 Kafka 发布失败；LLM 超时；Elasticsearch Bulk 部分失败；Worker 在 Neo4j Commit 后退出；Session Close 部分归档成功。任何失败不得丢失已成功写入的原始消息。恢复路径按注入分流，**不得**把 EXT-008 Admin retry 写成覆盖全部五条：
   - INJ-1：STM-011 `republish_archive_created_event` → `run_worker_once`（§1.2.6 #10 / I-I）
   - INJ-2：EXT-008 Admin retry（Extraction LLM timeout → `status=failed`）
   - INJ-3：EXT-008 Admin retry（ES bulk 部分失败 → `status=failed` + `retrieval_index_write_failed`）
   - INJ-4：二次 `run_worker_once`（新 `event_id`；任务保持 `processing`；EXT-009 F1；Admin retry 不适用）
   - INJ-5：第二次 close **去掉** terminal 注入（§1.2.3 #11）
4. **§3.32 #7**：fixture 锁定 `EMBEDDING_EFFECTIVE_RUNTIME_MODE=cpu`；Fake Embedding；GPU 不阻塞。真实 BGE-M3 **不是**本任务（既有 e2e harness 为 `--embedding=none` + Fake）。
5. **§3.32 #8 子集**：全链 HTTP 至少对 Session / Retrieval / Close 断言 §3.23 包络与 `X-Request-ID`；至少一场景 `user_id` 隔离；失败注入路径 **不得**把完整用户消息 / Prompt / LLM Response / API Key 写入断言日志。不重做 OPS-002 全仓审计。
6. **§3.28 #2**：E2E module teardown 对 `memory-system-test` 执行 `compose down -v --remove-orphans`；不得删除开发 Volume。
7. **发布阻塞**：本任务 scoped E2E 命令全绿是 E2E-001 完成与后续 REL-001 的前置；**不**修改 OPS-004 默认 CI（§3.28 #6：合并前 Unit+Contract+Integration；发布前完整 E2E）。

---

## 3. 非目标

- REL-001 MVP RC Review / `05_测试与验收/mvp_acceptance_checklist.md` 逐项勾选 / 打 `v0.9.0-mvp-rc1` tag
- 将 `tests/e2e/` 纳入 `.github/workflows/ci.yml` 或 `scripts/ci/run_merge_gate.sh` 默认 PR 阻塞路径
- 重写或再实现 STM-013 / EXT-009 / RET-006 / CON-005 垂直切片矩阵（通道降级、ACT-R、cursor 分页、mutex 等）
- 修改 STM/EXT/RET/CON 生产语义、API Contract、Schema、错误码、状态机、幂等或恢复语义
- DEV-006 / PR #13；真实 TEI / 真实 BGE-M3 E2E；真实 DeepSeek / SiliconFlow 计费 API
- GPU E2E（§3.32 #7：无 GPU 不阻塞 CPU MVP）
- OPS-003 空白环境 bootstrap / Migration checksum（§3.32 #1/#2/#9 已由 OPS-003/004 覆盖）
- OPS-004 80% 覆盖率或 CI workflow 变更
- 启动 `memory-extraction-worker` / `memory-consolidation-worker` 容器作为 happy-path 驱动（容器默认真实 LLM；见 §5.2）
- APScheduler wall-clock / `consolidation-worker` 长运行 E2E（CON-005 LD-2 仍 DEFERRED）
- `05_测试与验收/test_matrix.md` 中 **超出** §3.28 五条的条目（Extraction 非法 JSON、Finalize 锁失效、Retrieval 单通道/总超时、Consolidation 批次写失败等）——垂直切片已覆盖；本任务不重测；**DEFERRED → REL-001** 清单对照
- OpenTelemetry、镜像签名、生产 Secrets Manager（§3.30 P2）
- 新依赖、Migration、Settings 新字段

---

## 4. 当前代码状态

### 4.1 Git 与前置（规划时只读）

| 检查 | 结果 |
|---|---|
| 分支 | `main`（与 `origin/main` 同步） |
| HEAD | `bb0d387f509c38194cf511f580b98cf86f44b5a7`（`docs(status): complete OPS-004 after PR merge`） |
| working tree | clean |
| `02_开发管理/tasks/E2E-001-*` | **不存在** — 本任务创建 |
| OPS-003 | completed；PR #57 MERGED `89912ec` |
| OPS-004 | completed；PR #58 MERGED `3e6f8fa`；默认 CI 跑 `tests/unit`+`tests/contract`+`tests/integration`，**不含** `tests/e2e/` |
| STM/EXT/RET/CON/OPS-001/002 | 全部 completed |

### 4.2 已存在垂直切片 E2E（必须组合，禁止重写）

| 切片 | 路径 | 覆盖 | 缺口（相对 §3.32 #4） |
|---|---|---|---|
| STM-013 | `tests/e2e/test_stm013_short_term_memory_e2e.py` | HTTP Session→Message→Compression→Archive→Close；E2 重复 message_id；E4 LLM timeout（in-process） | 不进入 Extraction/ES/Retrieval/Consolidation |
| EXT-009 | `tests/e2e/test_ext009_extraction_e2e.py` | 种子 Mongo Archive + Kafka → pipeline → Neo4j+ES；F1 Neo4j-commit 后退出；retry 收敛 | **不**从 HTTP Session 产生 Archive |
| RET-006 | `tests/e2e/test_ret006_retrieval_e2e.py` | 预置 ES+Neo4j 或 EXT-007 sync → Retrieval HTTP；通道失败/超时 | **不**从 Session/Extraction 全链进入 |
| CON-005 | `tests/e2e/test_con005_consolidation_e2e.py` | Neo4j 种子 → `ConsolidationRunService.execute_run` | **不**从 Extraction 写入的 Memory 进入 |

**权威结论**：E2E-001 新增 **组合测试**；既有四文件保持原语义（`conftest.py` teardown 除外，见 §5.6）。

### 4.3 Compose / Fake / Volume 事实

| 项 | 事实 |
|---|---|
| 入口 | `scripts/compose.sh --stack=test --embedding=none`；project `memory-system-test`；独立 `*-data-test` volumes（`compose.test.yaml`） |
| `infra_stack` | 启动 redis/mongodb/kafka/neo4j/elasticsearch + `init-infra`；**不**启动三应用 worker 容器 |
| `full_container_stack` | 另启 `memory-api`；`create_app` 默认 `FakeLlmClient()` |
| `hybrid_api_client` | ASGI in-process + 真实后端；可注入 Fake LLM |
| `ext009_runtime` | in-process Neo4j/ES + `build_pipeline(..., llm_client=FakeLlmClient)` |
| extraction-worker 容器 | `create_production_extraction_pipeline` 默认 `DeepSeekLlmClient` — **happy path 不得启动该容器** |
| E2E teardown | `down --remove-orphans` **无 `-v`**（起止各一次）— 违反 §3.28 #2。Amendment 001：起止均 `_compose("down", "-v", "--remove-orphans")`；仍 `--stack=test` / project `memory-system-test`。Integration `tests/integration/support/compose_stack.py` 已用 `down -v` |
| 默认 CI | 不收集 `tests/e2e/`（pytest 路径为 unit/contract/integration） |
| pytest e2e marker | **无**；既有 e2e 用 `@pytest.mark.integration`。本任务沿用，**不**改 `pyproject.toml` |

### 4.4 失败注入已有层 vs §3.28 E2E 层缺口

| §3.28 场景 | 已有 | E2E-001 缺口 |
|---|---|---|
| Archive 已写入但 Kafka 发布失败 | compression_coordinator U12 + `test_message_write_coordinator_kafka.py` I-I：`compression_status=completed` 且 `pending_archive_id is None`（Kafka 失败不阻塞压缩；保存点 Mongo Archive） | **无** HTTP 全链 → STM-011 republish → Extraction 继续。**禁止**断言 WM 仍持有已归档消息 |
| LLM 超时 | STM-013 E4 compression；EXT-003/extraction unit | **无** 全链 Extraction timeout → 原文保留 → Admin retry 继续 |
| ES Bulk 部分失败 | EXT-007 Unit/I3；`FakeRetrievalIndexWriteRepository` 仅 Unit/INT 模式 | **无** 全链包 **生产** `RetrievalIndexWriteRepository`（真实 ES bulk）一次失败 → Mongo `failed` + `retrieval_index_write_failed` → EXT-008 retry → 真实 upsert、稳定 `_id` |
| Worker 在 Neo4j Commit 后退出 | EXT-009 F1 `BeforeRetrievalSyncHook`（种子 Archive）：任务 `processing`、offset 未提交、Neo4j 保留、ES 空；二次 `run_worker_once`（新 `event_id`）收敛 | **无** HTTP 产出 Archive 上的 F1；恢复路径 **不是** EXT-008（要求 `status=failed`） |
| Session Close 部分归档成功 | STM-010 Unit `close_incomplete`；STM-013 E3 并发仅作结果之一 | **无** 至少一 Archive 已持久化后 terminal 失败 → 503 `closing` → **第二次 close 无注入** → 200 `closed`、同 `archive_batch_key`、无重复 Archive、Redis WM 删除 |

### 4.5 先前任务明确 DEFERRED → 本任务

| 来源 | 延后项 | 本任务处置 |
|---|---|---|
| CON-005 CL-14 / e2e_boundary | Session→Archive→Extraction→Consolidation | **拥有**（E2E-HP） |
| RET-006 LD-8 / CL-10 | Session→Archive→Extraction→Retrieval | **拥有**（E2E-HP） |
| EXT-009 非目标 | Session→Consolidation 全链 | **拥有** |
| STM-013 非目标 | Extraction→ES→Retrieval→Consolidation | **拥有** |
| OPS-001 | Compose SIGTERM 真容器注入 | **拥有（收窄）**：idle worker `docker stop`（SIGTERM）；in-flight Neo4j-commit = INJ-4 hook。禁止计费 API |
| OPS-001 | 全链路 timeout 注入 | **拥有**：INJ-2 Fake LLM timeout 贯穿 Archive 已存在之后的 Extraction |
| OPS-003/004 非目标 | 全链路 E2E | **拥有** |
| test_matrix 超额条目 | 非法 JSON / 单通道 / Finalize 锁 等 | **DEFERRED REL-001**（垂直切片已测） |

### 4.6 与规格不一致之处（分类）

| ID | 发现 | 分类 | 本任务 |
|---|---|---|---|
| GAP-VOL | E2E teardown 不删测试 Volume | 测试基础设施；§3.28 #2 | **in-scope** 改 `tests/e2e/conftest.py` |
| GAP-CHAIN | 无单测贯穿 §3.32 #4 全链 | 本任务目标 | **in-scope** 新测试 |
| GAP-INJ-E2E | 五条注入未在全链 E2E 组合 | 本任务目标 | **in-scope** 新测试 |
| — | 生产 Contract / 状态机 | 未发现需改 Contract 的冲突 | 保持；缺陷 → HALT |

无规格冲突需改 Contract。`dependency_changes_expected=NONE`；`migration_changes_expected=NONE`。

---

## 5. 实现方案

> **原则：TEST / E2E FIRST。默认 `production_file_whitelist=NONE`。** 若 E2E 暴露 STM/EXT/RET/CON/OPS 生产缺陷 → Developer **HALT**，不得在 E2E-001 内修 `src/**`。

### 5.1 e2e_boundary

| 项 | 结论 |
|---|---|
| 权威链 | §3.32 #4 字面：`Session → Message → Archive → Compression → Extraction → Elasticsearch Sync → Retrieval → Consolidation → Session Close` |
| 驱动 | **公共 HTTP** 驱动 Session / Message / Retrieval / Close；Extraction 用 in-process `run_worker_once`（EXT-009）；Consolidation 用 in-process `ConsolidationRunService.execute_run`（CON-005） |
| 禁止 | 用预置 ES/Neo4j fixture **替代** HTTP Session 产出作为 E2E-HP 主路径（RET-006/CON-005 种子模式不得充当本任务 happy path） |
| 禁止 | 测试主路径直接调用 `write_message` / `close_session` 领域服务（断言层可读 Redis/Mongo/Neo4j/ES/Kafka） |
| Fake | `FakeLlmClient`（compression + extraction JSON）；`FakeTokenizeClient`；`FakeEmbeddingClient`；`--embedding=none` |
| 计费 API | **禁止** |
| 生产零 diff | 默认；缺陷 → HALT |

#### 5.1.1 垂直切片 vs 全链（reuse 表）

| 能力 | 复用 | 本任务新建 |
|---|---|---|
| HTTP session/message/close helpers | `stm_e2e_helpers.py` **import** | 组合编排 wrapper |
| Extraction pipeline + worker once + F1 hook | `ext009_e2e_helpers.py` **import** | 从 STM Kafka/Mongo archive 接入，不 `seed_archive` 作为 HP |
| Retrieval HTTP | 同一 `hybrid`/`create_app` 客户端 `POST /api/v1/memory/retrieval` | 查询词来自 Fake extraction JSON 的唯一 keyword；**不**复制 RET-006 E2E-3..5 矩阵 |
| Consolidation | `con005_e2e_helpers.build_production_run_service` | `evaluation_time` > Memory `created_time`；断言 importance / `last_consolidated_time` |
| 失败 doubles | EXT-009 hook、**生产** `RetrievalIndexWriteRepository` 一次性 bulk 失败包装、FakeLlm timeout、patch kafka `send_and_wait` | `tests/support/e2e001_failure_doubles.py`：Kafka / 生产 ES repo wrap / close terminal fail。**禁止**以 `FakeRetrievalIndexWriteRepository` 作为 E2E INJ-3 注入体 |

### 5.2 进程模型（锁定）

```text
compose.test infra (redis, mongodb, kafka, neo4j, elasticsearch) + init-infra
        |
        +-- in-process FastAPI (hybrid_api_client / e2e001_app_client)
        |     FakeLlmClient + 真实 Redis/Mongo/Kafka producer
        |     HTTP: session, working/message, retrieval, session close
        |
        +-- in-process ProductionExtractionPipeline + run_worker_once
        |     FakeLlmClient(success_content=extraction JSON w/ unique keyword)
        |     FakeTokenizeClient + FakeEmbeddingClient
        |
        +-- in-process ConsolidationRunService.execute_run(fixed_evaluation_time)
```

| 决策 | 理由 |
|---|---|
| 不用 extraction-worker 容器跑 HP | 默认 `DeepSeekLlmClient` → 计费 API（§3.28 #3） |
| 不用 consolidation-worker 容器 | CON-005：in-process 生产接线足够；wall-clock DEFERRED |
| 不用 memory-api 容器作为 HP 主路径 | STM-013 已证明容器路径；全链需要同一进程注入 Fake extraction/embedding |
| INJ-SIGTERM | 单独场景：仅当 idle（`memory-extraction-group` 对 `context.archive.created` consumer lag=0 / 无待消费事件）后 `compose up -d memory-extraction-worker`，再 `docker stop`（SIGTERM）。断言容器未运行且窗口内无 LLM HTTP。**禁止**在有 leftover 事件时启动该容器（会消费并打 DeepSeek）。**不**与 HP 共用 worker 容器 |

### 5.3 Step 1 — Fixture 与 Volume 隔离

- **文件**：`tests/e2e/conftest.py`（修改）；`tests/e2e/helpers/e2e001_helpers.py`（创建）
- **输入**：既有 `infra_stack` / `ext009_runtime`
- **输出**：
  - teardown：**起止两次**均改为 `_compose("down", "-v", "--remove-orphans")`（`infra_stack` 当前 start 与 end 各一次 `down --remove-orphans`）。命令仍经 `_compose` → `--stack=test --embedding=none`；project 必须为 `memory-system-test`。禁止对非 test project / 开发 Volume 执行 `down -v`
  - `e2e001_app_client`：in-process app + Fake compression LLM + 真实基础设施（可参数化 LLM mode / kafka producer wrapper）
  - `e2e001_extraction_pipeline`：`build_pipeline` 包装，默认 `success_content` 含唯一检索词 `e2e001fullchainkeyword`（写入 Fake extraction memory `content` / `search_text` 来源）
- **错误处理**：Docker 不可用 → module skip（与现 e2e 一致）；health 超时 → hard fail
- **幂等/隔离**：每测独立 `user_id`/`session_id`；cleanup 调用既有 `cleanup_session_data` / `cleanup_ext009_data` 扩展（Neo4j DETACH 限本 user + ES 删本 user docs）

### 5.4 Step 2 — E2E-HP 全链路 happy path

- **文件**：`tests/e2e/test_e2e001_full_chain.py`；编排 helper `tests/e2e/helpers/e2e001_helpers.py`
- **类/场景**：`test_hp_session_to_close_full_chain`
- **输入**：HTTP create session → `write_until_compression_trigger`（STM helper，**仅驱动写入直到压缩被调用**）
- **Compression 成功锁定（MF-2；§3.32 #4 将 Archive 与 Compression 列为独立步骤；Archive 在 Compression LLM 之前创建）**：
  - **禁止**把 `write_until_compression_trigger` 的返回当作 HP 成功。该 helper 将 `FAILED` 视为 triggered；Archive+Kafka 可在 `compression_status=failed` 时已存在。
  - 触发响应返回后 **必须额外断言**（STM-013 HP 风格，`tests/e2e/test_stm013_short_term_memory_e2e.py` E1）：
    - HTTP `compression_status` ∈ `{completed, partial_completed}`（**排除** `failed` / `not_triggered`）
    - Redis WM `compressed_context` **非空**（`strip()` 后 truthy）
    - `pending_archive_id is None`（压缩 finalize 已清空 Pending）
  - 然后才断言 Mongo Archive（含 `messages`）+ Kafka `context.archive.created`
- **处理**：`run_worker_once` 消费该事件 → 断言 Extraction `completed`、Neo4j Memory/Evidence、ES `_id=memory_id`
- **检索**：`POST /api/v1/memory/retrieval` query 含 `e2e001fullchainkeyword`；断言返回该 `memory_id`；`user_id` 过滤
- **巩固**：`execute_run(evaluation_time=FIXED_NOW+large)`；断言该 Memory `last_consolidated_time` 更新且 `memory_version` 不变（CON-003 语义，只断言）
- **关闭**：`POST .../close` → 200 `closed`；Redis WM 删除；Close 产生的 Archive 持久化（§3.32 #4 末端）
- **HP 链上每段均须发生**：HTTP Session；至少一条 Message；Mongo Archive；**Compression succeeded**；Kafka event；Extraction `completed`；ES document；Retrieval 命中；Consolidation 写回；Session Close
- **#8 子集**：Session/Retrieval/Close 均 200 + `X-Request-ID`；另用户检索不得命中本 Memory
- **错误处理**：任一步失败即测失败；禁止 skip 断言
- **幂等**：本场景不重复写入；幂等见 Step 3

### 5.5 Step 3 — §3.32 #5 幂等四场景

- **文件**：`tests/e2e/test_e2e001_idempotency.py`
- **场景**：

| ID | 操作 | 预期 |
|---|---|---|
| IDEM-1 | 同一 `message_id` 重复 POST | HTTP 幂等成功；Redis/Mongo Message/Archive 计数不增（复用 STM-013 E2 断言风格，然后 **继续** Extraction 一次，Memory/ES 仍 1） |
| IDEM-2 | 同一 Kafka Archive Event 再 publish + `run_worker_once` | 无第二 Memory/Evidence/ES doc（EXT-009 completed replay 语义） |
| IDEM-3 | INJ-4 风格中断后第二次 `run_worker_once` | graph/index identity 稳定；无重复节点/文档 |
| IDEM-4 | EXT-008 Admin retry 已 completed 或可重试失败任务 | 无重复 Memory/Evidence/ES |

### 5.6 Step 4 — §3.28 失败注入 + 人工恢复

- **文件**：`tests/e2e/test_e2e001_failure_injection.py`；`tests/support/e2e001_failure_doubles.py`
- **注入点**：仅测试 doubles / monkeypatch / 既有 `BeforeRetrievalSyncHook`；**禁止**新生产 hook、新 Settings、新错误码
- **doubles 文件仍需要**：路径不变（`tests/support/e2e001_failure_doubles.py`）。INJ-3 在此包装 **生产** `RetrievalIndexWriteRepository`（真实 ES `bulk`），不把 in-memory `FakeRetrievalIndexWriteRepository` 接到 E2E pipeline。

| ID | 注入 | 原文不丢 / 已写状态 | 人工恢复（规格已有；按条分流） |
|---|---|---|---|
| INJ-1 | patch Kafka `send_and_wait` 在 Mongo Archive 成功后失败 | **锁定（MF-1；§1.2.6 #10 / I-I / U12）**：Mongo Archive 在且 `archive.messages` 保留。Kafka 失败 **不**阻塞压缩；压缩 **可以** `completed`/`partial_completed` 并 LTRIM WM / 清空 `pending_archive_id`。**禁止**要求 WM 仍持有已归档消息。保存点是 Mongo Archive，不是 Redis WM。 | STM-011 `republish_archive_created_event`；再 `run_worker_once` → Extraction `completed`。**不是** EXT-008 |
| INJ-2 | Extraction `FakeLlmClient(mode="timeout")`（Archive 已由 HTTP 压缩成功写入） | Mongo Archive + 原始消息在 `archive.messages` | 任务 `status=failed` 后 EXT-008 Admin retry；第二次 pipeline 用 success Fake → `completed` |
| INJ-3 | **包装生产** `RetrievalIndexWriteRepository`：第一次真实 ES `bulk` 失败（一次性注入），不替换为 `FakeRetrievalIndexWriteRepository` | Neo4j 已 commit；Archive/消息在 | 第一次后 Mongo `status=failed` + `last_error.error_code=retrieval_index_write_failed`（EXT-007 I3）。然后 EXT-008 retry → 真实 upsert、稳定 `_id`。**禁止**用 Fake 作为 E2E 注入体 |
| INJ-4 | `BeforeRetrievalSyncHook` 在 graph 成功后抛（EXT-009 F1） | Neo4j 保留；Archive 在；ES 空 | **锁定（EXT-009 F1）**：hook crash → 任务保持 `processing`、Kafka offset **未**提交、Neo4j 保留、ES 空。**第二次** `run_worker_once`（**新 `event_id`**）收敛 index。EXT-008 retry 要求 `status=failed`，**不是**本条主路径 |
| INJ-5 | Close：至少一 **本次关闭新增** Archive 已 Mongo 持久化后，注入 Redis terminal 删除失败 | 已写入 Archive 不丢 | **锁定（MF-3；§1.2.3 #11）**：第一次 close（带 terminal-delete 注入）→ HTTP **503** `close_incomplete`；Session 保持 `closing`；close 创建的 Archive 已持久化。**第二次 close（去掉注入）** → HTTP **200** `status=closed`；同一 `archive_batch_key` / **无重复 Archive**；Redis WM 已删除。**禁止**「最终 closed 或再次 incomplete」这种非客观析取 |
| INJ-SIGTERM | idle 确认后启动 extraction-worker 容器再 `docker stop` | 无业务数据（本场景不投递待消费事件） | 见下方客观检查；不替代 INJ-4 |
| INJ-TIMEOUT-CHAIN | 同 INJ-2（闭合 OPS-001「全链路 timeout」） | 同 INJ-2 | 同 INJ-2；可与 INJ-2 合并为同一测试以免重复 |

**INJ-SIGTERM 客观检查（SF-3；取代「无 LLM__API_KEY 网络」）**：

1. **启动前 idle**：对生产 consumer group `memory-extraction-group`、topic `context.archive.created` 断言 consumer lag = 0（committed offset == high watermark）**或** 该 group 无待消费事件。若存在 leftover 事件：**不得** `compose up memory-extraction-worker`（会消费并打 DeepSeek）；本测 FAIL 或先由 in-process unique group drain 后再测。
2. `docker stop`（SIGTERM）目标容器后：`docker inspect` `State.Running=false` 或 `docker ps` 无该容器。
3. **无 LLM HTTP**：该窗口内 worker 日志 / 出站请求 **不得**出现对 `LLM__BASE_URL`（`https://api.deepseek.com`）或 chat completions 的 HTTP。禁止用「环境无 API Key」代替观测。
4. 本场景结束后立即确认容器未运行，不得把生产 worker 留在共享 `infra_stack` 上给后续测试。

Compression-path LLM timeout（STM-013 E4）**不重写**；INJ-2 覆盖 **Extraction** timeout（全链已有 Archive）。若 Developer 将 compression timeout 与 extraction timeout 拆成两测，须均断言原文不丢。

### 5.7 Step 5 — Scope-boundary contract

- **文件**：`tests/contract/test_e2e001_scope_boundaries.py`
- **标记**：`@pytest.mark.task_scope_boundary`（默认 CI 排除，与 CON-005/OPS-004 一致）
- **断言**：`src/**` diff 相对 plan_commit 为空（或仅 HALT 后经 Amendment 追加的白名单）；测试变更 ⊆ §12 白名单

### 5.8 Step 6 — 静态检查

- scoped ruff 仅白名单新/改测试文件（§9.1 命令）
- `uv run mypy src` 保持 0（本任务不改 src；§9.1 canonical）
- **不**对 `tests/` 跑 mypy 作为本任务验收（OPS-004 BL-MYPY-001：`tests/scripts` mypy 为已登记债务，非本任务门禁）

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/e2e/helpers/e2e001_helpers.py` | 创建 | 全链编排：HTTP→wait archive event→**assert compression succeeded + compressed_context**→worker once→retrieval→consolidation→close；唯一 keyword JSON |
| `tests/support/e2e001_failure_doubles.py` | 创建 | Kafka `send_and_wait` fail；**生产** `RetrievalIndexWriteRepository` 一次性 bulk 失败 wrap（真实 ES）；close terminal fail。不引入 Fake ES repo 作为 E2E 注入 |
| `tests/e2e/test_e2e001_full_chain.py` | 创建 | E2E-HP + #8 隔离子集 |
| `tests/e2e/test_e2e001_idempotency.py` | 创建 | IDEM-1..4 |
| `tests/e2e/test_e2e001_failure_injection.py` | 创建 | INJ-1..5 + INJ-SIGTERM |
| `tests/e2e/conftest.py` | 修改 | `infra_stack` **起止两次** `down -v --remove-orphans`；可选 `e2e001_*` fixture；仍 `--stack=test` / `memory-system-test` |
| `tests/contract/test_e2e001_scope_boundaries.py` | 创建 | 白名单 + 零 src diff |
| `02_开发管理/progress.md` | 修改 | 规划/实施态（本轮仅规划态） |
| `02_开发管理/master_plan.md` | 修改 | E2E-001 专节 + CHANGE-079 |
| `02_开发管理/tasks/E2E-001-full-chain-e2e-failure-injection.md` | 创建 | 本计划 |

**禁止修改（除非 HALT+Amendment）**：`src/**`；既有 `test_stm013_*` / `test_ext009_*` / `test_ret006_*` / `test_con005_*` 断言语义；`.github/workflows/ci.yml`；`scripts/ci/run_merge_gate.sh`；`pyproject.toml`；Migration；DEV-006。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 适用（跨存储窗口，规格已定义） | 测试断言窗口行为，不发明新事务；Kafka 失败不回滚 Mongo Archive；Close 过门后不可 revert active |
| 幂等 | 适用 | IDEM-1..4；`archive_batch_key` / `memory_id` ES upsert / completed replay |
| 并发 | 有限 | 不重做 STM-013 E3 write-vs-close 矩阵；INJ-5 为单连接 close 重试 |
| 版本冲突 | 不适用（全链 HP） | Consolidation 版本冲突已由 CON-005 E2E-4 覆盖；DEFERRED 不重测 |
| 用户隔离 | 适用 | E2E-HP 第二 `user_id` 检索不得命中 |
| 部分失败 | 适用 | INJ-1..5；原文/已写 Archive/已 commit Neo4j 不丢。INJ-1 允许 WM LTRIM（保存点 Mongo）。INJ-4 任务保持 `processing` |
| 进程异常恢复 | 适用 | INJ-4 = EXT-009 F1（二次 `run_worker_once` + 新 `event_id`）；INJ-SIGTERM idle 容器。禁止新补偿事务；禁止用 EXT-008 覆盖 INJ-4 |
| Volume 隔离 | 适用 | test project 起止 `-v`；禁止删 dev volumes |

---

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
| 无新增业务 Unit | 垂直切片 Unit 已覆盖公式/Lua/pipeline；本任务不新增 `tests/unit/**` |

### Contract Test

| 场景 | 预期 |
|---|---|
| C1 零 `src/**` diff | `test_e2e001_scope_boundaries.py` PASS（`task_scope_boundary`） |
| C2 测试白名单 | 仅 §12 路径出现在 feat diff |

### Integration Test

| 场景 | 预期 |
|---|---|
| 无新增 `tests/integration/**` | 全链属 E2E 层；不重复 STM-006/EXT-007 Integration |

### E2E Test

| ID | 场景 | 预期 |
|---|---|---|
| E2E-HP | §3.32 #4 全链 | 见 §5.4；Compression **succeeded** + `compressed_context` 非空；Docker 可用时 PASS |
| IDEM-1..4 | §3.32 #5 | 无重复 Message/Archive/Memory/Evidence/ES |
| #8 HTTP | 统一包络 + Request ID | Session/Retrieval/Close |
| #8 隔离 | 跨 user 检索 | 空或其他用户 memories 不含本 `memory_id` |
| #7 CPU | env | `EMBEDDING_EFFECTIVE_RUNTIME_MODE=cpu`；Fake embed |

### 失败注入与并发测试

| ID | 场景 | 预期 |
|---|---|---|
| INJ-1 | Archive 写入、Kafka 失败 | Mongo Archive + `messages` 在；压缩 **可以**完成且 WM 可被 LTRIM；STM-011 republish 后 Extraction `completed`（§1.2.6 #10 / I-I） |
| INJ-2 / INJ-TIMEOUT-CHAIN | Extraction LLM timeout | Archive/消息在；任务 `failed`；EXT-008 retry 完成 |
| INJ-3 | 生产 ES Bulk 部分失败 | Neo4j 在；Mongo `failed` + `retrieval_index_write_failed`；EXT-008 retry → 真实 upsert、稳定 `_id` |
| INJ-4 | Neo4j commit 后退出 | 任务 `processing`；offset 未提交；graph 在；ES 空；二次 `run_worker_once`（新 `event_id`）index 收敛（EXT-009 F1） |
| INJ-5 | Close 部分归档成功 | 第一次 503 `close_incomplete` + `closing` + Archive 已持久化；第二次无注入 200 `closed` + 同 `archive_batch_key` + Redis WM 删除（§1.2.3 #11） |
| INJ-SIGTERM | idle extraction-worker SIGTERM | 启动前 lag=0；`docker stop` 后容器未运行；窗口内无 LLM HTTP |

---

## 9. 验收标准

- [x] `uv run pytest tests/e2e/test_e2e001_full_chain.py tests/e2e/test_e2e001_idempotency.py tests/e2e/test_e2e001_failure_injection.py -q` — Docker 可用时全部 PASS（skip 仅当 Docker 不可用，与既有 e2e 一致）
- [x] E2E-HP 单测断言链上 **每段** 均发生：HTTP session；至少一条 message；Mongo archive；**Compression succeeded**（`completed` 或 `partial_completed`）且 WM `compressed_context` 非空（STM-013 HP）；Kafka event；extraction `completed`；Neo4j Memory；ES document；retrieval 命中；consolidation 写回；session close。**不得**仅凭 `write_until_compression_trigger` 返回判定 HP 成功
- [x] IDEM-1..4 无重复五类实体
- [x] INJ-1..5 全绿；原文/已写 Archive 不丢；恢复路径按条分流（INJ-1 STM-011；INJ-2/INJ-3 EXT-008；INJ-4 二次 `run_worker_once`；INJ-5 第二次 close 无注入）；**无**新 HTTP 恢复端点
- [x] INJ-1：Kafka 失败后 Mongo Archive + `messages` 保留；**不**要求 WM 仍持有已归档消息；republish → Extraction `completed`（§1.2.6 #10 / I-I）
- [x] INJ-5：第一次 close 503 `close_incomplete` + `closing` + Archive 持久化；第二次 close 无注入 200 `closed` + 同 `archive_batch_key` + Redis WM 删除（§1.2.3 #11）
- [x] INJ-SIGTERM：启动前 `memory-extraction-group` lag=0 / 无待消费 `context.archive.created`；`docker stop` 后容器未运行；窗口内无 LLM HTTP（不以「无 API Key」代替）
- [x] `tests/e2e/conftest.py` `infra_stack` **起止两次** teardown 含 `down -v`；compose 命令含 `--stack=test`；不得出现对非 test project 的 `down -v`
- [x] `uv run pytest tests/contract/test_e2e001_scope_boundaries.py -q` PASS
- [x] `uv run ruff check tests/e2e/helpers/e2e001_helpers.py tests/support/e2e001_failure_doubles.py tests/e2e/test_e2e001_full_chain.py tests/e2e/test_e2e001_idempotency.py tests/e2e/test_e2e001_failure_injection.py tests/e2e/conftest.py tests/contract/test_e2e001_scope_boundaries.py`
- [x] `uv run mypy src` PASS（0 errors）。**不对** `tests/` 跑 mypy 作为本任务验收（OPS-004 BL-MYPY-001）
- [x] **零** `src/**` diff；`dependency_changes_expected: NONE`；`migration_changes_expected: NONE`
- [x] 未修改 `.github/workflows/ci.yml` / `scripts/ci/run_merge_gate.sh` / OPS-004 默认门禁
- [x] 未触碰 DEV-006 / PR #13；未提交 Secret
- [ ] Review 无 P0/P1

### 9.1 Scoped 运行命令（实施验收 canonical）

```bash
uv run pytest tests/e2e/test_e2e001_full_chain.py \
  tests/e2e/test_e2e001_idempotency.py \
  tests/e2e/test_e2e001_failure_injection.py -q

uv run pytest tests/contract/test_e2e001_scope_boundaries.py -q

uv run ruff check tests/e2e/helpers/e2e001_helpers.py \
  tests/support/e2e001_failure_doubles.py \
  tests/e2e/test_e2e001_full_chain.py \
  tests/e2e/test_e2e001_idempotency.py \
  tests/e2e/test_e2e001_failure_injection.py \
  tests/e2e/conftest.py \
  tests/contract/test_e2e001_scope_boundaries.py

uv run mypy src
```

---

## 10. 风险与阻塞项

- **设计文档冲突**：无（§3.28 与 §3.32 #4 链表述略有压缩词差异：§3.28 写 `Session → Archive → Extraction → Retrieval → Consolidation`，§3.32 #4 含 Message/Compression/ES Sync/Session Close）。**以 §3.32 #4 为 HP 权威序列**；§3.28 为层定义 + 五条注入。不改规格。
- **当前代码冲突**：E2E teardown 缺 `-v` — 测试内起止两次修复。extraction-worker 真实 LLM — 不启动该容器跑 HP；INJ-SIGTERM 仅 idle 后短生命周期。
- **前置任务**：OPS-003 SATISFIED；STM/EXT/RET/CON/OPS-001..004 SATISFIED。
- **未批准依赖**：无。
- **API/Schema 变化**：禁止。
- **其他风险**：
  - Fake extraction JSON 与 STM `bbbb` 消息内容无关 — 锁定 Fake `success_content` 含可检索 keyword（不依赖真实 LLM 理解消息）。
  - FakeEmbeddingClient 恒定向量可能导致 vector 通道噪声 — HP 检索以 **BM25/search_text 关键词命中** 为权威断言。
  - Close 在 Extraction 之后：close 新 Archive 不要求本测再跑第二轮 Extraction（#4 要求 Close 步骤发生并持久化 Archive，不要求 close-archive 再萃取）。
  - 共享 `infra_stack` 与 STM-013 同 module 可能互相污染 — E2E-001 测试应 per-test cleanup；若 flaky → 独立 module fixture，仍 `--stack=test`。
  - `write_until_compression_trigger` 将 `FAILED` 视为 triggered — HP 必须额外断言 Compression succeeded（MF-2）。
  - 共享 stack leftover `context.archive.created`：启动 `memory-extraction-worker` 会按 `memory-extraction-group` 消费并打 DeepSeek — INJ-SIGTERM 启动前 lag=0 硬门。
- **HARD_BLOCK**：DEV-006/PR#13；REL-001；改 Contract；默认 CI 扩 E2E；计费 API；删断言。

---

## 11. Git 计划

```yaml
branch: "feat/E2E-001-full-chain-e2e-failure-injection"
workflow_mode: NORMAL
post_human_plan_approved: |
  After human PLAN_APPROVED: status=approved; next_action=PLAN_LANDING;
  developer_authorized=false until exact feat exists. Do not start Developer on main.
  Only Release Operator PLAN_LANDING creates feat/E2E-001-full-chain-e2e-failure-injection.
release_phases:
  PLAN_LANDING:
    allowed_on: main
    commands:
      - "git add 02_开发管理/tasks/E2E-001-full-chain-e2e-failure-injection.md 02_开发管理/progress.md 02_开发管理/master_plan.md"
      - "git commit -m \"docs(plan): add E2E-001 full-chain e2e and failure injection plan\""
      - "git pull --ff-only"
      - "git push origin main"
      - "git checkout -b feat/E2E-001-full-chain-e2e-failure-injection"
  IMPLEMENTATION_RELEASE:
    allowed_on: feat/E2E-001-full-chain-e2e-failure-injection
    commands:
      - "git add tests/e2e/helpers/e2e001_helpers.py tests/support/e2e001_failure_doubles.py tests/e2e/test_e2e001_full_chain.py tests/e2e/test_e2e001_idempotency.py tests/e2e/test_e2e001_failure_injection.py tests/e2e/conftest.py tests/contract/test_e2e001_scope_boundaries.py"
      - "git add 02_开发管理/progress.md 02_开发管理/master_plan.md 02_开发管理/tasks/E2E-001-full-chain-e2e-failure-injection.md"
      - "git commit -m \"test(e2e): add full-chain e2e and failure injection suite\""
      - "git push -u origin feat/E2E-001-full-chain-e2e-failure-injection"
      - "gh pr create --title \"test(e2e): E2E-001 full-chain and failure injection\" --body \"...\""
  POST_MERGE_CLEANUP:
    allowed_on: main
    precondition: "PR MERGED verified"
    commands:
      - "git fetch && git checkout main && git pull --ff-only"
      - "git add 02_开发管理/progress.md 02_开发管理/master_plan.md 02_开发管理/tasks/E2E-001-full-chain-e2e-failure-injection.md"
      - "git commit -m \"docs(status): complete E2E-001 after PR merge\""
      - "git push origin main"
      - "git branch -d feat/E2E-001-full-chain-e2e-failure-injection"
      - "git push origin --delete feat/E2E-001-full-chain-e2e-failure-injection"
expected_commits:
  - "docs(plan): add E2E-001 full-chain e2e and failure injection plan"
  - "test(e2e): add full-chain e2e and failure injection suite"
out_of_scope_changes:
  - "src/**"
  - "REL-001 / mvp_acceptance_checklist.md"
  - "DEV-006 / PR #13"
  - ".github/workflows/ci.yml / scripts/ci/run_merge_gate.sh / pyproject.toml coverage"
  - "scripts/migrations/001..004"
  - "依赖版本 / 镜像 Tag"
  - "API Contract / Schema / 错误码 / 状态机"
  - "重写 STM-013 / EXT-009 / RET-006 / CON-005 测试语义"
  - ".cursor/**"
```

---

## 12. production_file_whitelist / test_file_whitelist

```yaml
production_file_whitelist: []   # NONE — 默认禁止 src/** 与 CI/workflow/pyproject

test_file_whitelist:
  - "tests/e2e/helpers/e2e001_helpers.py"
  - "tests/support/e2e001_failure_doubles.py"
  - "tests/e2e/test_e2e001_full_chain.py"
  - "tests/e2e/test_e2e001_idempotency.py"
  - "tests/e2e/test_e2e001_failure_injection.py"
  - "tests/e2e/conftest.py"
  - "tests/contract/test_e2e001_scope_boundaries.py"

# 治理（各 RELEASE_PHASE 另列，非业务生产）：
#   02_开发管理/tasks/E2E-001-full-chain-e2e-failure-injection.md
#   02_开发管理/progress.md
#   02_开发管理/master_plan.md
```

Fail-closed：白名单外路径不得 `git add`。

---

## 13. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001 — Round 2 PLAN REMEDIATION（MF-1..3 + SF-1..8）

- **日期**：2026-08-15 02:25 UTC
- **原因**：Independent Plan Reviewer session `570cb388-890e-4bdf-9d9d-08700377f471` Round 1 **PLAN_REJECTED**（BLOCKER=0，MUST_FIX=3）。人类 re-invoke `/orchestrate-task` 授权规划修订，非实施。
- **是否影响技术规格 / Contract**：否。仅锁测试断言与恢复路径，对齐既有规格与生产测试。
- **审批状态**：Round 2 PLAN_APPROVED（session `20220a4e-dd78-4a44-b130-9eeec0b11d74`；BLOCKER=0 MUST_FIX=0）；人类 `PLAN_APPROVED`；`human_plan_approved=true` @ 2026-08-15 02:38 UTC；`status=approved`；`developer_authorized=false` 直至 feat 存在；`next_action=PLAN_LANDING then Developer on feat`。
- **原计划（Round 1 保留，禁止当作现行锁定）**：
  - INJ-1：Kafka 失败后「Mongo Archive 在；**WM 消息仍在**」；引用「§1126」
  - E2E-HP：`write_until_compression_trigger` → Mongo Archive + Kafka，未强制 Compression succeeded / `compressed_context`
  - INJ-5：「最终 `closed` 或再次 incomplete」非客观析取
  - INJ-3 允许 Fake ES repo；INJ-4 笼统「第二次 worker/retry」；INJ-SIGTERM「无 LLM__API_KEY 网络」；teardown 仅写结束 `-v`；YAML `see §6 / §19`；§9 要求 tests mypy
- **修改内容**：

| ID | 来源 | 修订 |
|---|---|---|
| MF-1 | MUST_FIX INJ-1 | §5.6/§8/§9：Kafka 失败不阻塞压缩（§1.2.6 #10 / I-I / U12）。保存点 Mongo Archive + `messages`；压缩 MAY complete 并 LTRIM WM / 清空 pending。**禁止**要求 WM 仍持有已归档消息。恢复 = STM-011 republish → `run_worker_once`。YAML 去掉「§1126」 |
| MF-2 | MUST_FIX E2E-HP Compression | §5.4/§8/§9：HP 必须断言 Compression **succeeded**（`completed`/`partial_completed`）且 WM `compressed_context` 非空（STM-013 HP），外加 Archive/Kafka/Extraction/ES/Retrieval/Consolidation/Close。**禁止**把 `write_until_compression_trigger`（含 FAILED）当 HP 成功 |
| MF-3 | MUST_FIX INJ-5 | §5.6/§8/§9：第一次 close + terminal-delete 注入 → HTTP 503 `close_incomplete`、session `closing`、close Archive 已持久化；第二次 close **无注入** → HTTP 200 `closed`、同 `archive_batch_key`、无重复 Archive、Redis WM 删除。引用 §1.2.3 #11 |
| SF-1 | SHOULD_FIX INJ-3 | 包装 **生产** `RetrievalIndexWriteRepository`（真实 ES bulk），不用 `FakeRetrievalIndexWriteRepository` 作 E2E 注入。失败后 Mongo `failed` + `retrieval_index_write_failed`；EXT-008 retry → 真实 upsert、稳定 `_id`。doubles 路径仍 `tests/support/e2e001_failure_doubles.py` |
| SF-2 | SHOULD_FIX INJ-4 | 跟随 EXT-009 F1：hook crash → `processing`、offset 未提交、Neo4j 保留、ES 空；二次 `run_worker_once`（新 `event_id`）收敛。EXT-008 要求 `failed`，不是本条主路径。目标 #3 按条分流恢复，Admin retry 不覆盖五条 |
| SF-3 | SHOULD_FIX INJ-SIGTERM | 客观检查：启动前 `memory-extraction-group` lag=0 / 无待消费 `context.archive.created`；`docker stop` 后容器未运行；窗口内无 LLM HTTP。禁止 leftover 事件上启动生产 worker |
| SF-4 | SHOULD_FIX Volume | `infra_stack` 起止两次 `down` 均加 `-v`；仍 `--stack=test` / project `memory-system-test` |
| SF-5 | SHOULD_FIX 状态机 | `approval_gates` / §11：人类 PLAN_APPROVED 后 `status=approved`、`next_action=PLAN_LANDING`、`developer_authorized=false` 直至 feat 存在；**禁止**在 main 上启动 Developer。本轮不置 approved |
| SF-6 | SHOULD_FIX dangling §19 | YAML `test_file_whitelist_default` 与 C2 指向 §12（白名单所在）；无 §19 |
| SF-7 | SHOULD_FIX HP helper | 由 MF-2 覆盖 |
| SF-8 | SHOULD_FIX §9 mypy | 删除「白名单测试文件 mypy 无新增错误」。§9.1 仅 `uv run mypy src`。`tests/` mypy = OPS-004 BL-MYPY-001 债务 |

`plan_review_round: 2`。Round 1 已锁定且未驳回的决策保持：`production_file_whitelist=NONE`；测试白名单路径不变；不扩 OPS-004 CI；不吸收 REL-001；不计费 API；不改 Contract；HP 不用 extraction-worker 容器。

计划批准后如需进一步修改，新增 Amendment 记录，禁止覆盖本修订。

---

## 14. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-15 02:10 UTC | Planner Round 1 | 创建本计划 | 未实施 | AWAIT_PLAN_REVIEW |
| 2026-08-15 02:25 UTC | Planner Amendment 001 | Round 1 PLAN_REJECTED 修订 MF-1..3 + SF-1..8；progress/master_plan 规划态 | 未实施 | `plan_review_round=2`；`next_action=计划审查`；Developer NOT authorized |
| 2026-08-15 02:38 UTC | Human PLAN_APPROVED + PLAN_LANDING | status=approved；Round 2 PLAN_APPROVED session 20220a4e；human_plan_approved=true；developer_authorized=false until feat exists | 未实施 | next_action=PLAN_LANDING then Developer on feat；不得在 main 上启动 Developer |
| 2026-08-15 02:50 UTC | Developer start | status=in_progress；kept PLAN_LANDING fields (feat branch, plan_commit, developer_authorized=true) | 实施中 | next_action=implement whitelist tests; no src/** |
| 2026-08-15 03:00 UTC | Developer implemented | whitelist tests + conftest `-v` both downs；zero `src/**` | 待跑 §9.1 | Fake extraction JSON 用 Archive 真实 user `message_id`（EXT-003 source 校验）；非 Contract 变更 |
| 2026-08-15 03:05 UTC | Developer tested | 同上 | E2E 11 passed / 502.16s；contract 3 passed；ruff PASS；mypy src 0 | READY_FOR_CODE_REVIEW；未 commit |
| 2026-08-15 03:45 UTC | IMPLEMENTATION_RELEASE | implementation `4a44e99009e04bcbce5717df0a3073fffff9faf0` pushed feat；PR #59 OPEN；docs(status): record on feat | 见 §15 | phase=IMPLEMENTATION_RELEASE；WAITING_FOR_PR_MERGE；禁 push main |
| 2026-08-15 03:55 UTC | POST_MERGE_CLEANUP | status=completed；PR #59 MERGED `43b6975a5dc4a92cde2f898acacd73a508831a48` mergedAt `2026-08-15T03:53:42Z`；docs(status): complete on main；exact feat 删除 | 见 §15 | next_action=REL-001 planned / NOT AUTO-STARTED；不得自动启动 REL-001；不得触碰 DEV-006/PR#13 |

---

## 15. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `tests/e2e/helpers/e2e001_helpers.py` | 创建 — HTTP 压缩成功断言、extraction JSON keyword、in-process app、worker/consolidation/SIGTERM helpers |
| `tests/support/e2e001_failure_doubles.py` | 创建 — Kafka send_and_wait fail；生产 ES bulk 一次性失败 wrap；close terminal fail |
| `tests/e2e/test_e2e001_full_chain.py` | 创建 — E2E-HP + #8 隔离 |
| `tests/e2e/test_e2e001_idempotency.py` | 创建 — IDEM-1..4 |
| `tests/e2e/test_e2e001_failure_injection.py` | 创建 — INJ-1..5 + INJ-SIGTERM |
| `tests/e2e/conftest.py` | 修改 — `infra_stack` 起止两次 `_compose("down", "-v", "--remove-orphans")` |
| `tests/contract/test_e2e001_scope_boundaries.py` | 创建 — 零 src diff + 测试白名单 |
| `02_开发管理/progress.md` / `master_plan.md` / 本计划 | 修改 — in_progress → implemented → tested 执行记录；保留 PLAN_LANDING 字段 |

### 与原计划的差异

- Fake extraction `success_content` 必须使用 HTTP Archive 中真实 user `message_id`（EXT-003 `source_message_id not in archive` 否则 `llm_invalid_output`）。Keyword 仍锁定 `e2e001fullchainkeyword`。非 Contract 变更。
- `e2e001_app_client` 实现为 helpers 中 `build_e2e001_app_client` 上下文管理器，而非 conftest fixture（conftest 仅改 `-v`）。
- INJ-SIGTERM 在启动生产 worker 前如有 leftover 则用 `memory-extraction-group` in-process drain 至 lag=0（计划允许）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | 不适用（无新增） | N/A |
| Contract | `uv run pytest tests/contract/test_e2e001_scope_boundaries.py -q` | 3 passed in 0.04s |
| Integration | 不适用（无新增） | N/A |
| E2E | `uv run pytest tests/e2e/test_e2e001_full_chain.py tests/e2e/test_e2e001_idempotency.py tests/e2e/test_e2e001_failure_injection.py -q` | 11 passed in 502.16s (0:08:22) |
| Ruff | 见 §9.1 | All checks passed |
| Mypy | `uv run mypy src` | Success: no issues found in 197 source files |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 0
review_report: "CODE_REVIEW_APPROVED session b8f90d2d; P0=0 P1=0"
```

### Git 记录

```yaml
branch: feat/E2E-001-full-chain-e2e-failure-injection
plan_commit: c2afaaa576107329ca6153a846fcb071c9383445
implementation_commit: 4a44e99009e04bcbce5717df0a3073fffff9faf0
implementation_commit_message: "test(e2e): add full-chain e2e and failure injection suite"
status_record_committed: 526c8403cff8b05d05ca73b1d513aeb30e7dea76
pr: "#59"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/59"
pr_state: MERGED
pr_base: main
pr_head: feat/E2E-001-full-chain-e2e-failure-injection
pr_head_sha: 526c8403cff8b05d05ca73b1d513aeb30e7dea76
merge_commit: 43b6975a5dc4a92cde2f898acacd73a508831a48
merged_at: "2026-08-15T03:53:42Z"
feat_branch: deleted
working_tree: clean
```

### 最终状态

`completed`
