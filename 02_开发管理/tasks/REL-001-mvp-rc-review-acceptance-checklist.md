# REL-001 MVP RC Review 与验收清单

## 1. 任务信息

```yaml
task_id: REL-001
task_name: MVP RC Review 与验收清单
status: completed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "412fb7b858120927aecad63962990587038df340"
branch: "feat/REL-001-mvp-rc-review-acceptance-checklist"
milestone_rc1: "v0.9.0-mvp-rc1 — 条件=E2E-001 与审查完成（已满足）；本任务拥有打 tag，但 tag 超出自动 Release Operator 命令集 → HALT/人工"
milestone_v1: "v1.0.0-mvp — 条件=MVP 验收清单全部阻塞项通过；未全绿不得创建"
created_at: "2026-08-15 04:15 UTC"
updated_at: "2026-08-15 06:05 UTC"
spec_sections:
  - "05_测试与验收/mvp_acceptance_checklist.md（A–F 阻塞项；文首：只有全部阻塞项通过才可创建 v1.0.0-mvp）"
  - "§3.32 MVP 开发完成验收标准 #1–#9"
  - "§3.17 MVP 部署与开发命令（交叉 A / §3.32 #1）"
  - "§3.28 测试策略（交叉 D / §3.32 #3–#6；五条失败注入已由 E2E-001 拥有）"
  - "§3.23 统一 API 响应与 Request ID（交叉 E / §3.32 #8）"
  - "§3.21 Memory API 鉴权与接口暴露（交叉 E）"
  - "§3.27 日志、指标与敏感信息保护（交叉 E / §3.32 #8）"
  - "§3.30 P1/P2（P1 CI/.env.example 已由 OPS-004；P2 OpenTelemetry/镜像签名/Secrets Manager 非本任务）"
  - "master_plan.md §4 里程碑 v0.9.0-mvp-rc1 / v1.0.0-mvp"
  - "05_测试与验收/test_matrix.md 超额条目 — 仅清单对照，禁止重测"
prerequisites:
  formal:
    - "E2E-001 — SATISFIED/completed（PR #59 MERGED @ 43b6975a5dc4a92cde2f898acacd73a508831a48；CODE_REVIEW_APPROVED P0=0/P1=0）"
    - "OPS-004 — SATISFIED/completed（PR #58 MERGED @ 3e6f8fa；CI run 31857428972）"
    - "OPS-003 — SATISFIED/completed（PR #57 MERGED @ 89912ec）"
    - "OPS-002 — SATISFIED/completed（PR #56 MERGED）"
    - "OPS-001 — SATISFIED/completed（PR #55 MERGED）"
    - "STM-001..013 / EXT-001..009 / RET-001..006 / CON-001..005 — SATISFIED/completed"
  baseline_evidence:
    branch: "main"
    head: "412fb7b858120927aecad63962990587038df340"
    head_short: "412fb7b"
    head_subject: "docs(status): complete E2E-001 after PR merge"
    working_tree_at_planning_start: "clean"
    origin_sync: "main...origin/main (up to date)"
    verification: "git branch --show-current=main; git status --short empty; git log --oneline -10 starts 412fb7b; git rev-parse HEAD=412fb7b858120927aecad63962990587038df340"
    planner_git_log_oneline_10:
      - "412fb7b docs(status): complete E2E-001 after PR merge"
      - "43b6975 Merge pull request #59 from xu-jia-ming/feat/E2E-001-full-chain-e2e-failure-injection"
      - "526c840 docs(status): record E2E-001 implementation commit and PR"
      - "4a44e99 test(e2e): add full-chain e2e and failure injection suite"
      - "c2afaaa docs(plan): add E2E-001 full-chain e2e and failure injection plan"
      - "bb0d387 docs(status): complete OPS-004 after PR merge"
      - "3e6f8fa Merge pull request #58 from xu-jia-ming/feat/OPS-004-ci-gates-coverage-threshold"
      - "780359a fix(ci): stop pytest_plugins from loading test modules"
      - "dd349a5 fix(ci): isolate Kafka consume and harden isolated-stack rebuild"
      - "d30015d fix(ci): block shared-stack teardown and align test deps contract"
approval_gates:
  planning: "approved"
  human_plan_approved: true
  human_plan_approved_at: "2026-08-15 04:25 UTC"
  developer_authorized: true
  approval_posture: "POST_MERGE_CLEANUP — completed"
  plan_review_round: 1
  plan_review_status: "Round 1 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=5 (implementation Step 0; no Amendment this phase)"
  code_review: CODE_REVIEW_APPROVED
  p0: 0
  p1: 0
  p2: 0
  p3: 1
  next_action: "REL-001 completed — NO AUTO-START (Phase 5 has no subsequent Task); HUMAN: annotated tag v0.9.0-mvp-rc1 only (suggested object 412fb7b858120927aecad63962990587038df340); DO NOT create v1.0.0-mvp (A.1 Preflight still unchecked)"
  post_human_plan_approved_state_machine: |
    Human PLAN_APPROVED received. status=approved; next_action=PLAN_LANDING then Developer on feat.
    developer_authorized=false until exact feat/REL-001-mvp-rc-review-acceptance-checklist exists.
    Do not start Developer on main. Developer starts only after PLAN_LANDING creates the feat branch.
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator lands this plan on main and creates exact feat/REL-001-mvp-rc-review-acceptance-checklist"
  IMPLEMENTATION_RELEASE: "feature branch whitelist only; no push to main; no git tag"
  POST_MERGE_CLEANUP: "after verified MERGED PR; exact feat branch cleanup; no git tag"
dependency_changes_expected: NONE
migration_changes_expected: NONE
production_file_whitelist_default: NONE
test_file_whitelist_default: NONE
acceptance_artifact_whitelist_default: "05_测试与验收/mvp_acceptance_checklist.md（仅证据满足后勾选）"
```

### 1.1 本轮门禁（planning-only）

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现或测试实现"
  - "在 main 上启动 Developer / Code Reviewer / Commit Recorder / Release Operator"
  - "PLAN_LANDING 本身（本轮只出待审计划）"
  - "IMPLEMENTATION_RELEASE / POST_MERGE_CLEANUP"
  - "读取 .env 或提交 Secret"
  - "触碰 DEV-006 / PR #13"
  - "启动真实计费 DeepSeek / SiliconFlow / TEI API"
  - "把未证明项勾成通过（规划阶段不得改 mvp_acceptance_checklist.md 勾选）"
  - "git tag / push tag（任何角色）"
stop_if:
  - "任何实现步骤需要改变 API Contract / Schema / 错误码 / 状态机 / 幂等或恢复语义"
  - "证据审计发现 HARD_BLOCK 且规格要求改 Contract 才能勾选"
  - "需要新依赖或 Migration（必须保持 NONE）"
  - "需要把真实 BGE-M3 / GPU / 计费 API 写成 CPU MVP 阻塞"
  - "需要将 E2E 纳入 OPS-004 默认 CI"
blocking_open_issues: []
nonblocking_open_issues:
  - "OI-REL1-TAG — git tag 不在 DEV-OPS-002/003 Release Operator 三 phase 命令集内；v0.9.0-mvp-rc1 与 v1.0.0-mvp 均为 HALT/人工 annotated tag，禁止 Orchestrator/Developer/RO 自动打 tag 或 push tag"
  - "OI-REL1-TEI — test_matrix.md §4「发布验收必须至少运行真实 CPU TEI + BGE-M3 Contract/E2E」与唯一规格 §3.28 #4（真实 BGE-M3 为可选本地测试）+ §3.32 #7（CPU 模式必测；无 GPU 不阻塞）+ E2E-001 Fake CPU 路径张力；本任务不把真实 TEI 写成阻塞；不改规格正文"
```

---

## 2. 任务目标

交付 **MVP RC Review 与验收清单证据化**：对照 `05_测试与验收/mvp_acceptance_checklist.md` A–F 与规格 §3.32 #1–#9，把既有 **completed** 任务 / 测试 / CI / 文档映射为可追溯证据；仅在证据满足后勾选清单；按 master_plan §4 处理两个 **互不混同** 的 tag。本任务 **不是新业务功能**。

**可验证交付**：

1. **A–F 证据映射表**（本计划 §4.4；实施时在执行记录中逐项确认分类）：每项必须为 `SATISFIED_BY_EVIDENCE` / `NEEDS_REL001_ARTIFACT` / `DEFERRED_WITH_AUTHORITY` / `HARD_BLOCK` 之一。禁止口头宣称通过。
2. **清单勾选**：仅对实施阶段确认 `SATISFIED_BY_EVIDENCE`（或已完成的 `NEEDS_REL001_ARTIFACT`）的阻塞项，在 `05_测试与验收/mvp_acceptance_checklist.md` 将 `- [ ]` 改为 `- [x]`，并在 Task Plan 执行记录引用证据（任务 ID / 测试路径 / CI run / commit SHA）。规划阶段 **不得**勾选。
3. **`v0.9.0-mvp-rc1`**：条件 =「E2E-001 与审查完成」。E2E-001 已 `completed` 且 `CODE_REVIEW_APPROVED`。E2E-001 非目标把打 tag 推迟到本任务。执行者 = **人类**；不在任何 `RELEASE_PHASE` 自动执行；**禁止** Orchestrator / Developer / Release Operator `git tag` / push tag。
4. **`v1.0.0-mvp`**：条件 = 清单全部阻塞项通过。文首禁止未全绿时创建。未全绿 → **不得**打该 tag。同样仅为 HALT/人工。
5. **test_matrix 超额条目**：只做清单对照（引用 STM/EXT/RET/CON 既有测试路径）。禁止本任务重跑、重写或再实现那些矩阵。
6. **默认零生产代码、零新测试、零依赖、零 Migration。**

---

## 3. 非目标

- 新业务功能；改 API / Schema / 错误码 / 状态机 / 幂等 / 恢复语义
- 重测或重写 STM-013 / EXT-009 / RET-006 / CON-005 / E2E-001 垂直切片或全链套件
- 将 `tests/e2e/` 纳入 `.github/workflows/ci.yml` 或 `scripts/ci/run_merge_gate.sh` 默认 PR 阻塞路径
- DEV-006 / PR #13
- 真实计费 DeepSeek / SiliconFlow / TEI；真实 BGE-M3 作为 CPU MVP 阻塞；GPU E2E
- OpenTelemetry / 镜像签名 / 生产 Secrets Manager（§3.30 P2）
- 修改已执行 Migration `001`–`004` 内容
- APScheduler wall-clock / consolidation-worker 长运行 E2E（CON-005 LD-2 仍 DEFERRED_WITH_AUTHORITY）
- OPS-002 F-013 `kafka_consumer_lag` / F-006-D stdlib 余量 / F-019 OpenTelemetry（保持 DEFERRED_WITH_AUTHORITY）
- OPS-004 BL-MYPY-001（`tests`/`scripts` mypy 债务；CI 门禁仍为 `uv run mypy src`）
- Orchestrator / Developer / Release Operator 执行 `git tag` 或 push tag
- 在阻塞项未全绿时创建 `v1.0.0-mvp`
- 规划阶段勾选 `mvp_acceptance_checklist.md`

---

## 4. 当前代码状态

### 4.1 Git 与前置（规划时只读复核）

| 检查 | 结果 |
|---|---|
| 分支 | `main`（与 `origin/main` 同步） |
| HEAD | `412fb7b858120927aecad63962990587038df340` |
| working tree | clean |
| `02_开发管理/tasks/REL-001-*` | **不存在** — 本任务创建 |
| E2E-001 | `completed`；PR #59 MERGED；feat 已删；`CODE_REVIEW_APPROVED` P0=0/P1=0 |
| OPS-001..004 | 全部 `completed` |
| `progress.md` 规划前 | `current_task=E2E-001` / `current_task_status=completed` / `next_action=REL-001 planned / NOT AUTO-STARTED` |

与 Orchestrator 本轮只读表一致；无 dirty；无规格 Contract 冲突需停止（OI-REL1-TEI 为文档张力，见 §1.1 / §10，不改规格）。

### 4.2 已存在代码 / 可复用证据（禁止再实现）

| 区域 | 证据位置 | 本任务关系 |
|---|---|---|
| 空白环境 A / §3.32 #1#2#9 | OPS-003 PR #57；`tests/integration/test_ops003_blank_environment_bootstrap.py`；`tests/contract/test_ops003_migration_compose_inventory.py`；`tests/integration/test_migrate_infra.py`；`scripts/preflight/check_linux_host.sh` | 对照；Preflight 需本任务记录一次脚本退出码 |
| 业务链路 B / §3.32 #4 | E2E-001 `tests/e2e/test_e2e001_full_chain.py::test_hp_session_to_close_full_chain` | 对照，不重写 |
| 一致性 C / §3.32 #5#6 | E2E-001 idempotency + failure_injection；STM-011 / EXT-008 恢复路径 | 对照 |
| 测试门禁 D / §3.32 #3 | OPS-004 CI run 31857428972；`scripts/ci/run_merge_gate.sh`；E2E-001 11 passed | 对照；不扩默认 CI |
| 安全可观测 E / §3.32 #8 | OPS-002 / OPS-001 / DEV-005；`tests/unit/test_api_key_security.py` | 对照 |
| 工程一致性 F | OPS-003 ENG-*；OPS-004 `check_env_example.py` CI；README / versions.env | 对照 + 本任务 grep TODO/占位 + 干净工作区 |
| test_matrix 超额 | 见 §4.5 | **仅引用路径** |

### 4.3 当前缺失

- REL-001 Task Plan（本文件；规划产出）
- `mvp_acceptance_checklist.md` A–F **全部未勾选**（规划时必须保持未勾；实施时按证据勾选）
- `v0.9.0-mvp-rc1` / `v1.0.0-mvp` annotated tag **尚未创建**（且不能由自动 Release 创建）

### 4.4 A–F 规划态证据映射（实施 Step 0 必须逐项确认；禁止把规划分类当成已勾选）

分类码：`SATISFIED_BY_EVIDENCE` / `NEEDS_REL001_ARTIFACT` / `DEFERRED_WITH_AUTHORITY` / `HARD_BLOCK`。

#### A. 空白环境 ↔ §3.32 #1 #2 #7（模式）#9

| 清单项 | 规划分类 | 权威证据（completed 任务 / 路径） | 本任务动作 |
|---|---|---|---|
| Linux Preflight 通过 | `NEEDS_REL001_ARTIFACT` | OPS-003 F-010 将 **自动化** DEFERRED；脚本已存在 `scripts/preflight/check_linux_host.sh` | 实施时只读执行 `--mode=cpu`（或文档默认）；记录 exit 0；**禁止**改脚本语义；禁止读 `.env` Secret |
| Docker Engine 和 Compose v2 可用 | `SATISFIED_BY_EVIDENCE` | OPS-003 INT-SKIP-001 + I-OPS3-01 bootstrap 已在 Docker 上跑通 | 引用 OPS-003 执行记录；不重写 INT |
| CPU Embedding 模式可启动 | `SATISFIED_BY_EVIDENCE` | E2E-001 HP 断言 `EMBEDDING_EFFECTIVE_RUNTIME_MODE=cpu` + Fake；OPS-003 C-OPS3-03 `start_embedding.sh` 静态审计；Compose cpu overlay 既有 contract。真实 TEI/BGE-M3 **不是** CPU MVP 阻塞（§3.32 #7 / §3.28 #4 可选） | 对照；不启动计费/真实 TEI |
| Migration 首次执行成功 | `SATISFIED_BY_EVIDENCE` | `tests/integration/test_migrate_infra.py` + OPS-003 I-OPS3-01 `init-infra` | 对照 |
| Migration 重复执行幂等 | `SATISFIED_BY_EVIDENCE` | 同上 second run | 对照 |
| 修改已执行 Migration Checksum 后失败 | `SATISFIED_BY_EVIDENCE` | `test_migrate_infra` tamper + `tests/unit/test_migrate_runner.py` | 对照 |
| 三个应用 Entrypoint 启动 | `SATISFIED_BY_EVIDENCE` | OPS-003 I-OPS3-01 三容器 `up -d` | 对照 |
| Readiness 正确反映依赖状态 | `SATISFIED_BY_EVIDENCE` | OPS-003 I-OPS3-01/02 + `tests/integration/test_api_readiness.py` | 对照 |

#### B. 业务链路 ↔ §3.32 #4

全部规划分类 `SATISFIED_BY_EVIDENCE`。链上 Session→Close 权威测试：`tests/e2e/test_e2e001_full_chain.py::test_hp_session_to_close_full_chain`（E2E-001 PR #59；11 E2E passed）：Session 创建 → Message 写入 → Archive → Compression（succeeded + 非空 `compressed_context`）→ Extraction → Neo4j → ES exists → Retrieval HTTP 200 → Consolidation writeback → Session Close。**B.「重复 Message 幂等」不得按 HP 口头勾选**（SHOULD_FIX-1 / Step 0）：权威=`tests/e2e/test_e2e001_idempotency.py::test_idem_1_duplicate_message_id_then_single_extraction`（IDEM-1）。

#### C. 一致性与恢复 ↔ §3.32 #5 #6 #8 隔离

| 清单项 | 规划分类 | 权威证据 | 本任务动作 |
|---|---|---|---|
| Pending Archive 可恢复 | `SATISFIED_BY_EVIDENCE` | E2E-001 INJ-1 `test_inj_1_kafka_publish_fail_then_stm011_republish`；STM-011 republish | 对照 |
| 压缩失败不丢消息 | `SATISFIED_BY_EVIDENCE` | **权威（SHOULD_FIX-2 / Step 0）**：STM-013 `tests/e2e/test_stm013_short_term_memory_e2e.py::test_e4_llm_failure_post_write_http_200_compression_failed`（压缩 LLM 失败、HTTP 200、消息不丢）。E2E-001 INJ-1 `test_inj_1_kafka_publish_fail_then_stm011_republish` 是 Kafka 发布失败而非压缩 LLM 失败，不得作为本行权威 | 对照；不重测 STM-013 |
| 重复 Kafka Event 不重复写入 | `SATISFIED_BY_EVIDENCE` | E2E-001 IDEM-2 `test_idem_2_replay_same_archive_event_no_duplicate_entities` | 对照 |
| Worker 重启不重复 Memory/Evidence | `SATISFIED_BY_EVIDENCE` | E2E-001 IDEM-3 `test_idem_3_crash_after_graph_second_worker_stable_identity` | 对照 |
| Neo4j Commit 后异常可恢复 Elasticsearch | `SATISFIED_BY_EVIDENCE` | E2E-001 INJ-4 `test_inj_4_neo4j_commit_then_exit_second_worker_converges` | 对照 |
| Session Close 部分成功可继续 | `SATISFIED_BY_EVIDENCE` | E2E-001 INJ-5 `test_inj_5_close_incomplete_then_retry_without_injection` | 对照 |
| Version Conflict 不覆盖新状态 | `SATISFIED_BY_EVIDENCE` | CON-005 `tests/e2e/test_con005_consolidation_e2e.py::test_e2e4_version_conflict_partial_success`；STM-008 侧（SHOULD_FIX-4 / Step 0）：`tests/integration/test_compression_finalize_redis.py::test_i7_version_conflict` | **清单对照**；禁止本任务重跑 CON/STM 矩阵 |
| 所有用户资源强制 `user_id` 隔离 | `SATISFIED_BY_EVIDENCE` | E2E-001 HP `other_user_id` retrieval 不含本 `memory_id`；OPS-002 F-015/F-016 + `tests/contract/test_ops002_user_isolation_inventory.py` | 对照 |

#### D. 测试门禁 ↔ §3.32 #3 #4 #6

| 清单项 | 规划分类 | 权威证据 | 本任务动作 |
|---|---|---|---|
| Unit 全部通过 | `SATISFIED_BY_EVIDENCE` | OPS-004 CI 1399 unit+contract passed；run `31857428972` | 引用 CI；不改门禁 |
| Contract 全部通过 | `SATISFIED_BY_EVIDENCE` | 同上 | 引用 |
| Integration 全部通过 | `SATISFIED_BY_EVIDENCE` | OPS-004 246 passed / 4 skipped / 4 deselected（opt-in/host；STRICT_SKIPS 未失败） | 引用；跳过语义不得在本任务放宽 |
| 完整 E2E 通过 | `SATISFIED_BY_EVIDENCE` | E2E-001 11 passed（§3.28 #6：发布前完整 E2E；**不**纳入默认 CI） | 对照；禁止扩 CI |
| 失败注入全部通过 | `SATISFIED_BY_EVIDENCE` | E2E-001 INJ-1..5 + INJ-SIGTERM；§3.28 五条已覆盖 | 超额条目见 §4.5 对照 |
| `domain`/`application` 行覆盖率 ≥ 80% | `SATISFIED_BY_EVIDENCE` | OPS-004 91.26% domain+application；`fail_under=80` | 引用 |
| Ruff 通过 | `SATISFIED_BY_EVIDENCE` | OPS-004 / E2E-001 `uv run ruff check src tests scripts` PASS | 实施回归：同命令，不得改断言 |
| Mypy 通过 | `SATISFIED_BY_EVIDENCE` | CI 锁定 `uv run mypy src` = 0；BL-MYPY-001 tests/scripts **DEFERRED_WITH_AUTHORITY** | 不把全量 mypy 债务升级为阻塞 |

#### E. 安全与可观测性 ↔ §3.21 #1 / §3.23 / §3.27 / §3.25 / §3.32 #8

| 清单项 | 规划分类 | 权威证据 | 本任务动作 |
|---|---|---|---|
| API Key 比较使用 constant-time | `SATISFIED_BY_EVIDENCE` | OPS-002；`tests/unit/test_api_key_security.py::test_verify_api_key_uses_compare_digest` | 对照 |
| Secret 不出现在日志 | `SATISFIED_BY_EVIDENCE` | OPS-002 F-002；DEV-005 auth failure logs；`tests/unit/test_ops002_sensitive_log_guards.py` | 对照 |
| 完整用户消息不出现在日志 | `SATISFIED_BY_EVIDENCE` | OPS-002 privacy tests + E2E-001 失败路径禁令 | 对照 |
| 完整 Prompt/Response 不出现在日志 | `SATISFIED_BY_EVIDENCE` | OPS-002；EXT-003 U14 校正 prompt 不含 raw | 对照 |
| 统一错误响应 | `SATISFIED_BY_EVIDENCE` | DEV-005 / E2E-001 HTTP 包络断言 | 对照 |
| Request ID 全链路一致 | `SATISFIED_BY_EVIDENCE` | E2E-001 `assert_request_id_echo` Session/Retrieval/Close；Worker 用 `task_run_id`（§3.23 #3，OPS-002 F-005） | 对照；不要求 Worker 复用 HTTP request_id |
| Metrics 暴露并受保护 | `SATISFIED_BY_EVIDENCE` | DEV-005 `tests/contract/test_api_shell_contract.py` Admin Key；OPS-002 业务指标接线。`kafka_consumer_lag` F-013 **DEFERRED_WITH_AUTHORITY**（规格「可获取时」） | 对照；不实现 OpenTelemetry |
| Graceful Shutdown 验证 | `SATISFIED_BY_EVIDENCE` | OPS-001 shared 270s；`tests/unit/test_ops001_*`；E2E-001 INJ-SIGTERM idle worker | 对照 |

#### F. 工程一致性 ↔ §3.32 #9 / §3.30 P1

| 清单项 | 规划分类 | 权威证据 | 本任务动作 |
|---|---|---|---|
| `.env.example` 完整且无 Secret | `SATISFIED_BY_EVIDENCE` | OPS-004 `scripts/check_env_example.py` CI | 对照 |
| `versions.env` 和 `versions.lock.env` 与运行镜像一致 | `SATISFIED_BY_EVIDENCE` | OPS-003 ENG-03 / compose image contracts | 对照 |
| YAML 与 Pydantic Settings 一致 | `SATISFIED_BY_EVIDENCE` | 既有 settings/compose contract（DEV-003 / OPS-001） | 对照 |
| Compose 命令统一经过 Wrapper | `SATISFIED_BY_EVIDENCE` | `tests/unit/test_compose_wrapper_contract.py` | 对照 |
| README 启动命令有效 | `SATISFIED_BY_EVIDENCE` | OPS-003 C-OPS3-01 README vs §3.17 | 对照 |
| 无影响主流程的 TODO | `NEEDS_REL001_ARTIFACT` | OPS-003 ENG-05 规划时扫描；需在 **本 baseline HEAD** 再确认 | 实施 **Step 3**（SHOULD_FIX-5；§5 grep=Step 3，非 Step 6）：`rg` `src/` `scripts/` 主流程 `TODO`/`NotImplemented`/`pass`；发现主流程占位 → `HARD_BLOCK` **停止并报告**，禁止顺手改 Contract |
| 无占位实现 | `NEEDS_REL001_ARTIFACT` | 同上 | 同上 |
| Git 工作区干净 | `NEEDS_REL001_ARTIFACT` | 规划时 clean；实施完成与 POST_MERGE 时再确认 | 记录 `git status --short` 为空 |
| Review 无 P0/P1 | `NEEDS_REL001_ARTIFACT` | 前置任务均 CODE_REVIEW_APPROVED P0=0/P1=0；**本任务**自身 Code Review 必须 P0=0/P1=0 | 勾选不得早于本任务 CODE_REVIEW_APPROVED |

### 4.5 test_matrix.md 超额条目（DEFERRED → REL-001 **清单对照 only**）

E2E-001 非目标：超出 §3.28 五条的矩阵条目垂直切片已覆盖，E2E-001 不重测。本任务 **禁止重跑/重写**。对照表：

| test_matrix 条目 | 对照证据路径 | 分类 |
|---|---|---|
| Extraction LLM 非法 JSON | EXT-003：`tests/unit/test_extraction_llm_service.py` `test_u14_malformed_then_valid_succeeds` / `test_u16_both_attempts_invalid`；`tests/integration/test_extraction_llm_fake.py::test_i3_fake_retry_sequence` | `SATISFIED_BY_EVIDENCE`（对照） |
| Redis Finalize 前锁失效 | STM-008：`tests/integration/test_compression_finalize_redis.py` `test_i5_lock_not_acquired_wrong_token` / `test_i6_lock_not_acquired_missing` | 对照 |
| Retrieval 单通道失败 | RET-006：`tests/e2e/test_ret006_retrieval_e2e.py::test_e2e4a_single_channel_bm25_degradation` | 对照 |
| Retrieval 总超时 | RET-006：`test_e2e5a_total_timeout_before_response` / `test_e2e5b_total_timeout_degraded_after_response` | 对照 |
| Consolidation 批次写入失败 | CON-005：`tests/e2e/test_con005_consolidation_e2e.py::test_e2e5_write_read_failure_mutex_overlap_and_release`；`tests/unit/test_consolidation_run_service.py` batch write failed | 对照 |
| Worker 在 Task completed 后、Offset commit 前退出 | EXT-009（SHOULD_FIX-3 / Step 0）：`tests/e2e/test_ext009_extraction_e2e.py::test_e2e1_happy_path_commits_after_terminal`；交叉 `tests/unit/test_extraction_pipeline_ext002.py::test_RED_19_terminal_persistence_failure_prevents_offset_commit` | 对照；非本任务重测 |
| Embedding 服务不可用 | RET-006 E2E-3 通道/embedding 失败降级 | 对照 |
| Version Conflict | 见 C 行 CON-005 E2E-4 | 对照 |
| §4 禁止行为「发布验收必须真实 CPU TEI + BGE-M3」 | 与唯一规格 §3.28 #4 可选本地测试、§3.32 #7、E2E-001 Fake CPU **张力** | `DEFERRED_WITH_AUTHORITY`（OI-REL1-TEI）；**不**作为 CPU MVP 阻塞；**不**改规格正文 |

### 4.6 与技术规格不一致之处

- **无 Contract 冲突需停止。** OI-REL1-TEI 为 `test_matrix.md` 与唯一规格文档的验收口径张力；锁定唯一规格 `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md` + E2E-001 已批准边界。不得在本任务「补跑真实 TEI」或改 Contract 来消解。
- `04_Git规范/git_workflow.md` §7 写「AI 可以创建本地 Tag，但不得 Push」。现行 DEV-OPS-002/003 Release Operator 三 phase **没有** `git tag` 授权。本计划锁定：**任何自动角色不得 tag**；tag = HALT/人工（OI-REL1-TAG）。不把 git_workflow 旧句解读为 Developer 可本地 tag。

### 4.7 前置任务检查

E2E-001 正式前置 **SATISFIED**。master_plan Phase 5 REL-001 行状态 `planned`。不得自动把 REL-001 标 completed/approved。

---

## 5. 实现方案

默认 `production_file_whitelist=NONE`、`test_file_whitelist=NONE`、`dependency_changes_expected=NONE`、`migration_changes_expected=NONE`。实施唯一业务旁路产物是验收清单勾选（证据满足后）。

### Step 0 — 冻结证据 inventory（Developer 首日；只读）

- 文件：本 Task Plan §4.4–§4.5；`progress.md` E2E/OPS formal 字段；已 completed Task Plan
- 类/函数/Schema：无
- 输入：`planning_baseline_main` 起的 main 只读树；禁止读 `.env`
- 输出：§13 执行记录「Step 0 confirmed / 分类变更」；分类只许 `HARD_BLOCK` 升级或证据 SHA 补全，不许无证据把 `NEEDS_*` 改成 SATISFIED
- 错误处理：发现须改 API/Schema/错误码/状态机/幂等/恢复 → **HALT 并报告**，不得写入修复步骤
- 幂等/并发/事务：不适用

### Step 1 — 收集 A 节剩余产物（Preflight）

- 文件：只读执行 `scripts/preflight/check_linux_host.sh --mode=cpu`（脚本已存在；**不修改**）
- 输入：无 Secret；不读 `.env`
- 输出：exit code + 非机密摘要写入本计划 §13（允许 warnings；exit 1 → 该项保持未勾选并 HALT 报告，禁止改 preflight 阈值来通过）
- 错误处理：脚本 HARD_FAILURE → 不勾选 A.1；不改规格
- 幂等：可重复执行同一脚本

### Step 2 — 确认 B/C/D/E 映射（不重跑超额矩阵）

- 文件：只读打开 §4.4 所列测试与 CI URL / SHA
- 输出：每项在 §13 记 `SATISFIED_BY_EVIDENCE` + 证据指针
- 允许：为确认 D.Ruff/Mypy 在 feat 上复跑 `uv run ruff check src tests scripts` 与 `uv run mypy src`（**不改**测试）
- 禁止：重跑 RET-006/CON-005/STM-008/EXT-003 矩阵并当作本任务新测试；禁止 `pytest` 改写；禁止把 E2E 加入默认 CI
- 可选：若 Docker 可用，**允许**复跑既有 E2E-001 三文件作为发布前确认（§3.28 #6）；失败 → HALT，禁止删断言

### Step 3 — F 节 grep 与干净工作区

- 文件：只读 `rg` 范围限 `src/` `scripts/`（排除测试夹具中的字面 `TODO` 文档）
- 输出：无主流程 TODO/占位 → 记 SATISFIED；有主流程占位 → `HARD_BLOCK` 停止
- Git 干净：`git status --short` 仅含本任务白名单实施文件

### Step 4 — 勾选清单（唯一验收文件写）

- 文件：`05_测试与验收/mvp_acceptance_checklist.md`
- 输入：§13 已确认分类
- 输出：仅将已确认项 `- [ ]` → `- [x]`；`DEFERRED_WITH_AUTHORITY` **保持未勾选** 并在本计划注明不阻塞 CPU MVP / 不创建 `v1.0.0-mvp` 若该行被权威定义为阻塞——**本计划锁定**：OI-REL1-TEI 与 OPS-002 F-013 / BL-MYPY-001 / CON-005 LD-2 **不是** checklist 独立行，故不阻止在 A–F 清单行全绿时申请 `v1.0.0-mvp` 人工 tag
- 错误处理：任何清单行仍为 `HARD_BLOCK` 或未完成的 `NEEDS_REL001_ARTIFACT` → **不得**勾选该行；**不得**打 `v1.0.0-mvp`
- 幂等：勾选可重复；禁止把未证明项勾上

### Step 5 — Tag 门禁（HALT/人工；超出自动 Release）

- `v0.9.0-mvp-rc1`：条件已满足（E2E-001 completed + CODE_REVIEW_APPROVED）。建议 annotated tag 指向 E2E-001 完成点 `412fb7b858120927aecad63962990587038df340`（`docs(status): complete E2E-001 after PR merge`）。**谁执行**：人类。**哪一 RELEASE_PHASE**：**无** — 不在 PLAN_LANDING / IMPLEMENTATION_RELEASE / POST_MERGE_CLEANUP 命令集。Developer/RO 遇 tag 步骤 → 输出 HALT，等待人类。
- `v1.0.0-mvp`：仅当 Step 4 后 A–F **全部** `- [x]` 且本任务 CODE_REVIEW_APPROVED P0=0/P1=0。否则禁止。同样仅人类 annotated tag（建议指向含勾选清单的 merge/complete commit）。禁止 force 改 tag。

### Step 6 — 治理回写

- 文件：本 Task Plan §13–§15；`progress.md`；`master_plan.md` REL-001 状态备注（实施/完成时，非本规划轮次）
- 禁止改规格正文、五命令、Migration、未批准路径

---

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 | 阶段 |
|---|---|---|---|
| `02_开发管理/tasks/REL-001-mvp-rc-review-acceptance-checklist.md` | 创建 | 本计划 | 规划（本轮）+ 实施回写执行记录 |
| `02_开发管理/progress.md` | 修改 | 规划态 REL-001 字段；不得破坏 E2E-001 completed 事实 | 规划（本轮） |
| `02_开发管理/master_plan.md` | 修改 | REL-001 规划备注 + CHANGE-086 | 规划（本轮） |
| `05_测试与验收/mvp_acceptance_checklist.md` | 修改 | **仅实施阶段**证据满足后勾选 | IMPLEMENTATION（PLAN_APPROVED 且 feat 存在后） |
| `src/**` | **禁止** | production whitelist = NONE | — |
| `tests/**` | **禁止** | test whitelist = NONE | — |
| `scripts/migrations/001`–`004` | **禁止** | — | — |
| `.github/workflows/**` | **禁止** | 不扩 CI | — |

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 本任务不改业务多存储写入 |
| 幂等 | 不适用（业务） | 清单勾选以证据为准，可重复确认；不得重复宣称未证明项 |
| 并发 | 不适用 | 无新共享状态写入 |
| 版本冲突 | 不适用（本任务） | 对照 CON-005/STM-008 既有证据 |
| 用户隔离 | 不适用（本任务不改查询） | 对照 E2E-001 / OPS-002 既有证据 |
| 部分失败 | 不适用（本任务） | 对照 E2E-001 INJ-5 / CON-005 E2E-5 |
| 进程异常恢复 | 不适用（本任务） | 对照 E2E-001 INJ-4 / IDEM-3 / OPS-001 |

不适用的维度原因：REL-001 为 RC Review + 清单证据化，不引入新的业务事务路径。

---

## 8. 测试计划

本任务 **不新增** Unit / Contract / Integration / E2E / 失败注入测试。`test_file_whitelist=NONE`。下列表格为 **对照既有套件** 的发布确认计划，禁止改测试语义。

### Unit Test

| 场景 | 预期 |
|---|---|
| 无新增 unit | 不创建 `tests/unit/test_rel001_*` |
| 对照 | `tests/unit/test_api_key_security.py`；OPS-001/002 unit；EXT-003 malformed JSON unit（对照超额矩阵，不重跑为门禁） |
| 实施回归 | `uv run ruff check src tests scripts`；`uv run mypy src` |

### Contract Test

| 场景 | 预期 |
|---|---|
| 无新增 contract | 不创建 `tests/contract/test_rel001_*` |
| 对照 | OPS-003 inventory；OPS-004 CI workflow contract；OPS-002 observability / isolation inventory；DEV-005 metrics Admin Key |

### Integration Test

| 场景 | 预期 |
|---|---|
| 无新增 integration | 不创建 `tests/integration/test_rel001_*` |
| 对照 | OPS-003 blank bootstrap；`test_migrate_infra` checksum/幂等 |

### E2E Test

| 场景 | 预期 |
|---|---|
| 无新增 e2e 文件 | 禁止新 `tests/e2e/test_rel001_*` |
| 对照 HP | `tests/e2e/test_e2e001_full_chain.py` 已通过 |
| 可选复跑 | 仅既有 E2E-001 三文件；失败 HALT；禁止 skip/删断言 |
| 禁止 | 重跑 RET-006 / CON-005 / STM-013 / EXT-009 全矩阵作为本任务交付 |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
| §3.28 五条 | 已由 E2E-001 INJ-1..5 覆盖；对照勾选 D/C |
| test_matrix 超额 | **只引用路径**（§4.5）；禁止本任务重写/重跑作为新交付 |
| 并发 | 无新并发测试；CON-005 mutex 仅对照 |

---

## 9. 验收标准

- [x] A–F 每项在 §14 Step 0 inventory 有分类与证据指针；无口头通过
- [x] `mvp_acceptance_checklist.md` 仅对已确认项勾选；规划轮次文件保持未勾（本轮已满足）
- [x] `production_file_whitelist=NONE`；`test_file_whitelist=NONE`；无 `src/**` / 无新测试 / 无 Migration / 无新依赖
- [x] 未将 E2E 纳入 OPS-004 默认 CI
- [x] 未触碰 DEV-006/PR#13；未读/提交 Secret；未启动计费 API
- [x] `v0.9.0-mvp-rc1` 仅人类 annotated tag；RO 三 phase 无 tag 命令；未全绿不得 `v1.0.0-mvp`
- [x] test_matrix 超额条目仅对照，未重测重写
- [x] 对应测试：无新增；可选既有 E2E-001 / ruff / mypy src 回归通过
- [x] Ruff 通过（`uv run ruff check src tests scripts`）
- [x] Mypy 通过（`uv run mypy src`）
- [x] Review 无 P0/P1

---

## 10. 风险与阻塞项

- 设计文档冲突：OI-REL1-TEI（test_matrix §4 真实 TEI vs 唯一规格可选本地测试）。**处理**：锁定规格 + E2E-001 Fake CPU；不改规格；不作为 HARD_BLOCK 停写计划。
- Git tag 规范冲突：git_workflow「AI 可本地 tag」vs RO 无 tag 授权。**处理**：OI-REL1-TAG；一律 HALT/人工。
- 当前代码冲突：规划时未发现须改 Contract 的缺口。Step 0/3 若发现主流程 TODO → HARD_BLOCK 停止。
- 前置任务：E2E-001 completed — SATISFIED。
- 未批准依赖：NONE。
- API/Schema 变化：**禁止**。需要时停止并报告。
- 其他风险：把「对照」写成「重测」导致范围膨胀；把 `DEFERRED_WITH_AUTHORITY` 勾成通过；RO 误执行 `git tag`。

---

## 11. Git 计划

```yaml
branch: "feat/REL-001-mvp-rc-review-acceptance-checklist"
planning_baseline_main: "412fb7b858120927aecad63962990587038df340"
this_round: "tested; CODE_REVIEW_APPROVED P0=0 P1=0 P3=1; IMPLEMENTATION_RELEASE on feat; implementation_commit=703bb105fa18cc0814bd750843295c7044c6d4b9; PR #60 OPEN; next_action=WAITING_FOR_PR_MERGE"
developer_authorized: true
human_plan_approved: true
release_phases:
  PLAN_LANDING:
    allowed_on: main
    workflow: NORMAL
    commands:
      - "git add 02_开发管理/tasks/REL-001-mvp-rc-review-acceptance-checklist.md 02_开发管理/progress.md 02_开发管理/master_plan.md"
      - "git commit -m \"docs(plan): add REL-001 MVP RC review and acceptance checklist plan\""
      - "git pull --ff-only"
      - "git push origin main"
      - "git checkout -b feat/REL-001-mvp-rc-review-acceptance-checklist"
    forbidden:
      - "git tag"
      - "implementation files"
  IMPLEMENTATION_RELEASE:
    allowed_on: feat/REL-001-mvp-rc-review-acceptance-checklist
    commands:
      - "git add 05_测试与验收/mvp_acceptance_checklist.md"
      - "git add 02_开发管理/progress.md 02_开发管理/master_plan.md 02_开发管理/tasks/REL-001-mvp-rc-review-acceptance-checklist.md"
      - "git commit -m \"docs(rel): record MVP RC evidence and acceptance checklist\""
      - "git push -u origin feat/REL-001-mvp-rc-review-acceptance-checklist"
      - "gh pr create --title \"docs(rel): REL-001 MVP RC review and acceptance checklist\" --body \"...\""
    forbidden:
      - "git push origin main"
      - "git tag / git push --tags"
      - "src/** tests/** scripts/migrations/**"
  POST_MERGE_CLEANUP:
    allowed_on: main
    precondition: "PR MERGED verified"
    commands:
      - "git fetch && git checkout main && git pull --ff-only"
      - "git add 02_开发管理/progress.md 02_开发管理/master_plan.md 02_开发管理/tasks/REL-001-mvp-rc-review-acceptance-checklist.md"
      - "git commit -m \"docs(status): complete REL-001 after PR merge\""
      - "git push origin main"
      - "git branch -d feat/REL-001-mvp-rc-review-acceptance-checklist"
      - "git push origin --delete feat/REL-001-mvp-rc-review-acceptance-checklist"
    forbidden:
      - "git tag"
      - "git branch -D"
      - "delete unrelated branches/tags"
tag_policy:
  v0.9.0-mvp-rc1:
    condition: "E2E-001 与审查完成（已满足）"
    executor: human
    release_phase: NONE
    suggested_object: "412fb7b858120927aecad63962990587038df340"
    auto_roles: HALT
  v1.0.0-mvp:
    condition: "mvp_acceptance_checklist.md 全部阻塞项 [x]"
    executor: human
    release_phase: NONE
    if_incomplete: "DO NOT CREATE"
    auto_roles: HALT
expected_commits:
  - "docs(plan): add REL-001 MVP RC review and acceptance checklist plan"
  - "docs(rel): record MVP RC evidence and acceptance checklist"
out_of_scope_changes:
  - "src/**"
  - "tests/**"
  - "DEV-006 / PR #13"
  - ".github/workflows/ci.yml / scripts/ci/run_merge_gate.sh / pyproject.toml"
  - "scripts/migrations/001..004"
  - "依赖版本 / 镜像 Tag"
  - "API Contract / Schema / 错误码 / 状态机"
  - "重写 STM/EXT/RET/CON/E2E-001 测试语义"
  - ".cursor/**"
  - "git tag by Agent"
```

---

## 12. production_file_whitelist / test_file_whitelist

```yaml
production_file_whitelist: []   # NONE — 禁止 src/**

test_file_whitelist: []         # NONE — 禁止新测试与改既有测试语义

acceptance_artifact_whitelist:
  - "05_测试与验收/mvp_acceptance_checklist.md"  # 仅实施阶段、证据满足后勾选

# 治理（各 RELEASE_PHASE 另列，非业务生产）：
#   02_开发管理/tasks/REL-001-mvp-rc-review-acceptance-checklist.md
#   02_开发管理/progress.md
#   02_开发管理/master_plan.md
```

Fail-closed：白名单外路径不得 `git add`。

---

## 13. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

---

## 14. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-15 06:05 UTC | POST_MERGE_CLEANUP | status=`completed`；PR #60 MERGED `4e8ceff74b95880b1c035d518bf2be43d2bbc907` mergedAt `2026-08-15T06:01:06Z`；docs(status): complete on main；exact feat 删除；POST_MERGE 后工作树干净 | N/A | 未 git tag；未勾 A.1；清单 F.Git干净保持未勾（POST_MERGE 不 add `mvp_acceptance_checklist.md`）；Phase 5 无后续 Task，不得自动启动下一任务；HUMAN `v0.9.0-mvp-rc1` 仅人工 tag（建议对象 `412fb7b858120927aecad63962990587038df340`）；`v1.0.0-mvp` 不得创建 |
| 2026-08-15 04:55 UTC | IMPLEMENTATION_RELEASE (record) | 回写 implementation `703bb105fa18cc0814bd750843295c7044c6d4b9`；PR #60 OPEN；status `reviewed`→`committed` | N/A | record 仅 feat；未 push main；未 git tag；A.1/F.Git干净仍未勾 |
| 2026-08-15 04:52 UTC | IMPLEMENTATION_RELEASE (pre-commit) | 回写 CODE_REVIEW_APPROVED P0=0 P1=0 P3=1；§11 this_round（P3-001）；F.Review 勾选；status `tested`→`reviewed` | N/A | A.1/F.Git干净未勾；未宣称 v1.0.0-mvp；未 git tag；implementation_commit 待 rev-parse |
| 2026-08-15 04:50 UTC | Step 6 | 回写本计划 §14–§15、progress.md、master_plan.md CHANGE-088；status `in_progress`→`implemented`→`tested`；`next_action=Code Review` | ruff PASS；mypy src 0 | 未 commit；developer_authorized=true 保持；A.1/F.Git干净/F.Review 未勾 |
| 2026-08-15 04:48 UTC | Step 5 | Tag 门禁 HALT/人工；**未**执行 `git tag` | N/A | v0.9.0-mvp-rc1 条件已满足；v1.0.0-mvp 因 A.1 与 F 两行未勾 **不得**宣称可打 |
| 2026-08-15 04:47 UTC | Step 4 | `mvp_acceptance_checklist.md` 仅勾选 §14 已确认 SATISFIED 行 | N/A | A.1 / F.Git干净 / F.Review 保持 `- [ ]`；OI-REL1-TEI 等 DEFERRED 非独立清单行 |
| 2026-08-15 04:40 UTC | Step 3 | 只读 `rg` `src/` `scripts/`（TODO/FIXME/NotImplemented/bare pass） | 无主流程占位 | local_tei `NotImplementedError` 非 CPU 主流程（OI-REL1-TEI/DEV-007）；`pass` 均为 except 空分支；F.TODO/占位 → SATISFIED |
| 2026-08-15 04:37 UTC | Step 2 | 只读确认 B/C/D/E 指针；feat 复跑 ruff/mypy | ruff All checks passed；mypy 197 files 0 issues | Docker 可用；可选 E2E-001 三文件 **未复跑**（对照 E2E-001 completed 11 passed）；禁止扩 CI |
| 2026-08-15 04:37 UTC | Step 1 | 只读 `scripts/preflight/check_linux_host.sh --mode=cpu`；未改脚本；未 Read `.env` | exit **1** | HARD_FAILURE=`vm.max_map_count=65530 (< 1048576)`；A.1 **不勾选**；不改阈值；非 Contract 停写 |
| 2026-08-15 04:35 UTC | Step 0 | 冻结 A–F / §4.5 inventory；吸收 SHOULD_FIX=5（函数名补全；无 Amendment） | 所列测试文件/函数均存在 | A.1 仍 NEEDS 直至 Step 1；分类未无证据改 SATISFIED |
| 2026-08-15 04:32 UTC | Developer start | status `approved`→`in_progress`；exact feat HEAD=`04c4a7e8` | 门禁复核 | 工作树仅白名单治理 dirty（PLAN_LANDING leftover） |
| 2026-08-15 04:25 UTC | PLAN_LANDING | Human PLAN_APPROVED；status=approved；docs(plan) on main then create exact feat | 未实施 | developer_authorized=false until feat exists；SHOULD_FIX=5 deferred to implementation Step 0；no Amendment |
| 2026-08-15 04:15 UTC | planning | 创建本 Task Plan；progress/master_plan 规划态 | 未实施 | baseline `412fb7b`；production/test whitelist=NONE；tag=HALT/人工 |

### Step 0 证据精度修正（吸收 Plan Reviewer SHOULD_FIX=5；不改 Contract；无 Amendment）

1. B.「重复 Message 幂等」权威=`tests/e2e/test_e2e001_idempotency.py::test_idem_1_duplicate_message_id_then_single_extraction`（IDEM-1）。**不得**按 HP 口头勾选。文件/函数已打开确认存在（L84）。
2. C.「压缩失败不丢消息」权威=`tests/e2e/test_stm013_short_term_memory_e2e.py::test_e4_llm_failure_post_write_http_200_compression_failed`（STM-013 E4，L352）。INJ-1=`test_inj_1_kafka_publish_fail_then_stm011_republish` 是 Kafka 发布失败，不是压缩 LLM 失败。
3. §4.5 offset-after-terminal 精确路径=`tests/e2e/test_ext009_extraction_e2e.py::test_e2e1_happy_path_commits_after_terminal`（L44）；交叉=`tests/unit/test_extraction_pipeline_ext002.py::test_RED_19_terminal_persistence_failure_prevents_offset_commit`（L181）。
4. C. Version Conflict STM-008 侧=`tests/integration/test_compression_finalize_redis.py::test_i7_version_conflict`（L381）；CON-005=`tests/e2e/test_con005_consolidation_e2e.py::test_e2e4_version_conflict_partial_success`（L175）已正确。
5. grep 执行步骤按 §5 = **Step 3**（规划表曾误写 Step 6）。已在 §4.4 F 行改为 Step 3。

### Step 0 confirmed inventory（文件真实存在；分类）

SHA 锚点：`planning_baseline_main=412fb7b858120927aecad63962990587038df340`；E2E-001 implementation `4a44e99009e04bcbce5717df0a3073fffff9faf0`；PR #59 merge `43b6975a5dc4a92cde2f898acacd73a508831a48`；OPS-004 CI run `31857428972` merge `3e6f8fa`；OPS-003 merge `89912ec`。

#### A. 空白环境

| 清单项 | 确认分类 | 证据指针 | 勾选 |
|---|---|---|---|
| Linux Preflight 通过 | Step 0=`NEEDS_REL001_ARTIFACT`；Step 1 后 **HARD_BLOCK（host sysctl，非 Contract）** | `scripts/preflight/check_linux_host.sh --mode=cpu` exit=1；`hard_failures=1 warnings=0`；FAIL `vm.max_map_count=65530 (< 1048576)`；其余 PASS（OS/Docker/Compose v2/socket/Mem/13a/13b TEI warmup/lock digests）。禁止改脚本阈值。Developer 未 Read `.env`（脚本内部仅探测 PROXY__HTTP_URL 是否设置，未记录 Secret） | **否** |
| Docker Engine 和 Compose v2 可用 | `SATISFIED_BY_EVIDENCE` | OPS-003 I-OPS3-01；本机 Step 1 `PASS: docker info` + `PASS: Compose v2 plugin`；`docker compose version` = v2.35.1 | 是 |
| CPU Embedding 模式可启动 | `SATISFIED_BY_EVIDENCE` | E2E-001 HP `assert get_settings().embedding_effective_runtime_mode == "cpu"`；OPS-003 C-OPS3-03 `scripts/start_embedding.sh`；真实 TEI/BGE-M3 **非** CPU MVP 阻塞（OI-REL1-TEI） | 是 |
| Migration 首次执行成功 | `SATISFIED_BY_EVIDENCE` | `tests/integration/test_migrate_infra.py::test_migrate_first_run_idempotent_checksum_and_stores`；OPS-003 I-OPS3-01 | 是 |
| Migration 重复执行幂等 | `SATISFIED_BY_EVIDENCE` | 同上 second run | 是 |
| 修改已执行 Migration Checksum 后失败 | `SATISFIED_BY_EVIDENCE` | 同上 tamper + `tests/unit/test_migrate_runner.py` | 是 |
| 三个应用 Entrypoint 启动 | `SATISFIED_BY_EVIDENCE` | OPS-003 I-OPS3-01 三容器 `up -d`；`tests/integration/test_ops003_blank_environment_bootstrap.py::test_blank_environment_full_bootstrap_readiness` | 是 |
| Readiness 正确反映依赖状态 | `SATISFIED_BY_EVIDENCE` | OPS-003 I-OPS3-01/02；`test_readiness_migrations_not_ready_before_init_infra`；`tests/integration/test_api_readiness.py` | 是 |

#### B. 业务链路

| 清单项 | 确认分类 | 证据指针 | 勾选 |
|---|---|---|---|
| Session / Message / Archive / Compression / Extraction / Neo4j / ES / Retrieval / Consolidation / Close | `SATISFIED_BY_EVIDENCE` | `tests/e2e/test_e2e001_full_chain.py::test_hp_session_to_close_full_chain`（L50）；`drive_compression_succeeded`；`run_extraction_for_archive`；Neo4j `graph_memory_ids`；ES `exists`；Retrieval HTTP 200；close `assert_request_id_echo` | 是 |
| 重复 Message 幂等 | `SATISFIED_BY_EVIDENCE` | **IDEM-1** `tests/e2e/test_e2e001_idempotency.py::test_idem_1_duplicate_message_id_then_single_extraction`（L84） | 是 |

#### C. 一致性与恢复

| 清单项 | 确认分类 | 证据指针 | 勾选 |
|---|---|---|---|
| Pending Archive 可恢复 | `SATISFIED_BY_EVIDENCE` | `tests/e2e/test_e2e001_failure_injection.py::test_inj_1_kafka_publish_fail_then_stm011_republish`（L63）+ STM-011 republish | 是 |
| 压缩失败不丢消息 | `SATISFIED_BY_EVIDENCE` | STM-013 `test_e4_llm_failure_post_write_http_200_compression_failed`（L352） | 是 |
| 重复 Kafka Event 不重复写入 | `SATISFIED_BY_EVIDENCE` | IDEM-2 `test_idem_2_replay_same_archive_event_no_duplicate_entities`（L176） | 是 |
| Worker 重启不重复 Memory/Evidence | `SATISFIED_BY_EVIDENCE` | IDEM-3 `test_idem_3_crash_after_graph_second_worker_stable_identity`（L253） | 是 |
| Neo4j Commit 后异常可恢复 ES | `SATISFIED_BY_EVIDENCE` | INJ-4 `test_inj_4_neo4j_commit_then_exit_second_worker_converges`（L363） | 是 |
| Session Close 部分成功可继续 | `SATISFIED_BY_EVIDENCE` | INJ-5 `test_inj_5_close_incomplete_then_retry_without_injection`（L487） | 是 |
| Version Conflict 不覆盖新状态 | `SATISFIED_BY_EVIDENCE` | CON-005 `test_e2e4_version_conflict_partial_success`（L175）+ STM-008 `test_i7_version_conflict`（L381） | 是 |
| 所有用户资源强制 user_id 隔离 | `SATISFIED_BY_EVIDENCE` | HP `other_user_id` retrieval（L58/L137）；OPS-002 F-015/F-016；`tests/contract/test_ops002_user_isolation_inventory.py` | 是 |

#### D. 测试门禁

| 清单项 | 确认分类 | 证据指针 | 勾选 |
|---|---|---|---|
| Unit 全部通过 | `SATISFIED_BY_EVIDENCE` | OPS-004 CI run 31857428972：1399 unit+contract passed | 是 |
| Contract 全部通过 | `SATISFIED_BY_EVIDENCE` | 同上 | 是 |
| Integration 全部通过 | `SATISFIED_BY_EVIDENCE` | OPS-004 246 passed / 4 skipped / 4 deselected；STRICT_SKIPS 未失败 | 是 |
| 完整 E2E 通过 | `SATISFIED_BY_EVIDENCE` | E2E-001 11 passed（implementation `4a44e99` / PR #59）。本任务 Docker 可用但 **未复跑** 三文件（计划允许对照 completed 证据） | 是 |
| 失败注入全部通过 | `SATISFIED_BY_EVIDENCE` | INJ-1..5 + `test_inj_sigterm_idle_extraction_worker`（L557） | 是 |
| domain/application 覆盖率 ≥ 80% | `SATISFIED_BY_EVIDENCE` | OPS-004 91.26%；`fail_under=80` | 是 |
| Ruff 通过 | `SATISFIED_BY_EVIDENCE` | 本 feat 复跑 `uv run ruff check src tests scripts` → All checks passed | 是 |
| Mypy 通过 | `SATISFIED_BY_EVIDENCE` | 本 feat 复跑 `uv run mypy src` → Success, 197 files, 0 issues。BL-MYPY-001 tests/scripts **DEFERRED_WITH_AUTHORITY** | 是 |

#### E. 安全与可观测性

| 清单项 | 确认分类 | 证据指针 | 勾选 |
|---|---|---|---|
| API Key constant-time | `SATISFIED_BY_EVIDENCE` | `tests/unit/test_api_key_security.py::test_verify_api_key_uses_compare_digest`（L29） | 是 |
| Secret 不出现在日志 | `SATISFIED_BY_EVIDENCE` | OPS-002 F-002；`tests/unit/test_ops002_sensitive_log_guards.py` | 是 |
| 完整用户消息不出现在日志 | `SATISFIED_BY_EVIDENCE` | OPS-002 privacy tests + E2E-001 失败路径禁令 | 是 |
| 完整 Prompt/Response 不出现在日志 | `SATISFIED_BY_EVIDENCE` | OPS-002；EXT-003 U14 `test_u14_malformed_then_valid_succeeds` | 是 |
| 统一错误响应 | `SATISFIED_BY_EVIDENCE` | DEV-005 / E2E-001 HTTP 包络断言 | 是 |
| Request ID 全链路一致 | `SATISFIED_BY_EVIDENCE` | HP `assert_request_id_echo` Session/Retrieval/Close；Worker 用 `task_run_id`（§3.23 #3） | 是 |
| Metrics 暴露并受保护 | `SATISFIED_BY_EVIDENCE` | DEV-005 `tests/contract/test_api_shell_contract.py` Admin Key；OPS-002 接线。F-013 `kafka_consumer_lag` **DEFERRED_WITH_AUTHORITY**（非独立清单行） | 是 |
| Graceful Shutdown 验证 | `SATISFIED_BY_EVIDENCE` | OPS-001 shared 270s；`tests/unit/test_ops001_*`；E2E-001 INJ-SIGTERM | 是 |

#### F. 工程一致性

| 清单项 | 确认分类 | 证据指针 | 勾选 |
|---|---|---|---|
| `.env.example` 完整且无 Secret | `SATISFIED_BY_EVIDENCE` | OPS-004 `scripts/check_env_example.py` CI | 是 |
| versions.env / versions.lock.env 与运行镜像一致 | `SATISFIED_BY_EVIDENCE` | OPS-003 ENG-03 / compose image contracts；Step 1 PASS TEI CPU/GPU `@sha256` digest | 是 |
| YAML 与 Pydantic Settings 一致 | `SATISFIED_BY_EVIDENCE` | DEV-003 / OPS-001 settings/compose contract | 是 |
| Compose 命令统一经过 Wrapper | `SATISFIED_BY_EVIDENCE` | `tests/unit/test_compose_wrapper_contract.py` | 是 |
| README 启动命令有效 | `SATISFIED_BY_EVIDENCE` | OPS-003 C-OPS3-01 README vs §3.17 | 是 |
| 无影响主流程的 TODO | Step 0=`NEEDS_REL001_ARTIFACT`；Step 3 后 **`SATISFIED_BY_EVIDENCE`** | `rg` `src/` `scripts/`：无主流程 `TODO`/`FIXME`。`scripts/` 无 TODO。`compression_prompts.py` 「placeholder」= prompt `{messages}` 模板槽，非未实现 | 是 |
| 无占位实现 | Step 0=`NEEDS_REL001_ARTIFACT`；Step 3 后 **`SATISFIED_BY_EVIDENCE`** | `src/.../embedding/factory.py` `local_tei` `NotImplementedError` = 非 CPU 主流程显式拒绝（OI-REL1-TEI / DEV-007），非静默占位。三处 `pass`：DuplicateKeyError upsert、JSONDecodeError、CancelledError shutdown。`extraction_worker`/`consolidation_worker` catch `NotImplementedError` = 信号处理器平台差异。`scripts/start_embedding.sh` placeholder digest = **失败守卫** | 是 |
| Git 工作区干净 | `NEEDS_REL001_ARTIFACT`（清单未勾） | POST_MERGE 后工作树干净（`git status --short` 空）。POST_MERGE 命令集不含清单文件，**不**为勾选去 add `05_测试与验收/mvp_acceptance_checklist.md`；清单勾选保持原样 | **否** |
| Review 无 P0/P1 | `SATISFIED_BY_EVIDENCE` | 本任务 `CODE_REVIEW_APPROVED` P0=0 P1=0 P3=1（非阻塞；§11 this_round 滞后已吸收）。前置 E2E/OPS 审查不代替本任务 Review | **是** |

#### §4.5 test_matrix 超额（对照 only；未重跑）

| 条目 | 确认路径存在 | 分类 |
|---|---|---|
| Extraction LLM 非法 JSON | `test_u14_malformed_then_valid_succeeds` / `test_u16_both_attempts_invalid` / `test_i3_fake_retry_sequence` | `SATISFIED_BY_EVIDENCE`（对照） |
| Redis Finalize 前锁失效 | `test_i5_lock_not_acquired_wrong_token` / `test_i6_lock_not_acquired_missing` | 对照 |
| Retrieval 单通道失败 | `test_e2e4a_single_channel_bm25_degradation` | 对照 |
| Retrieval 总超时 | `test_e2e5a_total_timeout_before_response` / `test_e2e5b_total_timeout_degraded_after_response` | 对照 |
| Consolidation 批次写入失败 | `test_e2e5_write_read_failure_mutex_overlap_and_release` | 对照 |
| Offset after terminal | `test_e2e1_happy_path_commits_after_terminal` + `test_RED_19_terminal_persistence_failure_prevents_offset_commit` | 对照 |
| Embedding 服务不可用 | `tests/e2e/test_ret006_retrieval_e2e.py::test_e2e3_embedding_unavailable_degradation` | 对照 |
| Version Conflict | CON-005 E2E-4 + STM-008 I7 | 对照 |
| 真实 CPU TEI + BGE-M3 | OI-REL1-TEI | `DEFERRED_WITH_AUTHORITY`；**不**阻塞 CPU MVP；**不**改规格 |

### Step 1 Preflight 非机密摘要

```text
command: bash scripts/preflight/check_linux_host.sh --mode=cpu
PREFLIGHT_EXIT=1
hard_failures=1 warnings=0
mode=cpu resolved_mode=cpu resolved_budget=4096
FAIL: vm.max_map_count=65530 (< 1048576)
PASS: OS Linux; docker info; Compose v2; docker socket; 127.0.0.1:7890 reachable (PROXY__HTTP_URL set, value not recorded);
      filesystem 7092 GiB; cpu MemAvailable=894.04 GiB; Check 13a MemTotal 1008 GiB;
      Check 13b TEI CPU warm-up within 12g mem_limit (script-owned probe; not REL-001 billing API start);
      TEI_CPU_IMAGE / TEI_GPU_IMAGE valid @sha256; resolved mode/budget consistent
SKIP: NVIDIA checks skipped in cpu mode
HALT for A.1 checkoff only. Did not change script thresholds. Did not check A.1.
```

Check 13b 为既有 preflight 脚本行为（最长 ~300s）；Developer 未另行启动计费 DeepSeek/SiliconFlow API。`.runtime/` 在 `.gitignore`，未引入白名单外 dirty。

### Step 3 rg 结论

无主流程 TODO/占位 → F.TODO / F.无占位 **SATISFIED_BY_EVIDENCE**。未把 `local_tei` 显式拒绝升级为 HARD_BLOCK（非 CPU 主流程；与 OI-REL1-TEI 一致）。

### Step 5 Tag 门禁（HALT/人工；未执行 git tag）

- `v0.9.0-mvp-rc1`：条件已满足（E2E-001 completed + CODE_REVIEW_APPROVED P0=0/P1=0）。执行者=**人类**。建议 annotated tag 对象=`412fb7b858120927aecad63962990587038df340`（`docs(status): complete E2E-001 after PR merge`）。RELEASE_PHASE=**NONE**。本角色 **HALT**，未 `git tag` / push tag。
- `v1.0.0-mvp`：**不得宣称可打** / **不得创建**。A–F 仍有未勾行：A. Linux Preflight（禁止勾选 A.1）。F. Git 工作区干净清单勾选保持原样（POST_MERGE 后工作树干净，但不 add 清单文件）。F. Review 已勾（CODE_REVIEW_APPROVED P0=0/P1=0）。POST_MERGE 未 `git tag`。

---

## 15. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `05_测试与验收/mvp_acceptance_checklist.md` | 证据满足行 `- [x]`；F.Review 已勾（CODE_REVIEW_APPROVED）；A.1 / F.Git干净保持未勾（POST_MERGE 未 add 本文件） |
| `02_开发管理/tasks/REL-001-mvp-rc-review-acceptance-checklist.md` | Step 0 证据精度修正（SHOULD_FIX 1–5）；§14–§15 执行记录；status `completed` |
| `02_开发管理/progress.md` | REL-001 `completed`；E2E-001 completed 事实未破坏 |
| `02_开发管理/master_plan.md` | REL-001 状态备注 completed + CHANGE-091 |
| `src/**` / `tests/**` | **未修改** |

### 与原计划的差异

- A.1：规划 `NEEDS_REL001_ARTIFACT`；实施收集后 host `vm.max_map_count` HARD_FAILURE → 该项 HARD_BLOCK（host，非 Contract），保持未勾。未改 preflight 阈值。
- 可选 E2E-001 三文件未复跑：Docker 可用；对照 E2E-001 completed 11 passed（计划允许）。
- SHOULD_FIX=5 吸收为证据函数名/步骤编号补全；无 Amendment。
- F.Git干净清单保持未勾（POST_MERGE 工作树干净，但不 add 清单）。F.Review 已勾（CODE_REVIEW_APPROVED P0=0/P1=0 P3=1）。
- 无 API/Schema/错误码/状态机/幂等/恢复变更；无新依赖/Migration；无 `git tag`。A.1 未勾 → **不得**宣称可打 / **不得创建** `v1.0.0-mvp`。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | N/A（无新增；`test_file_whitelist=NONE`） | 未新增；对照 OPS-004 CI 1399 passed |
| Contract | N/A（无新增） | 未新增；对照 OPS-004 |
| Integration | N/A（无新增） | 未新增；对照 OPS-004 246 passed |
| E2E | 可选既有 E2E-001 三文件 | **未复跑**；对照 E2E-001 completed 11 passed @ `4a44e99` / PR #59 |
| Ruff | `uv run ruff check src tests scripts` | **PASS**（All checks passed） |
| Mypy | `uv run mypy src` | **PASS**（Success: no issues found in 197 source files） |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 1
review_report: "CODE_REVIEW_APPROVED session 0d353b11; P0=0 P1=0 P3=1 (this_round lag; absorbed)"
```

### Git 记录

```yaml
branch: "feat/REL-001-mvp-rc-review-acceptance-checklist"
plan_commit: "04c4a7e8f6a49d0092d175b40a98513eadc47e0a"
implementation_commit: "703bb105fa18cc0814bd750843295c7044c6d4b9"
implementation_commit_message: "docs(rel): record MVP RC evidence and acceptance checklist"
status_record_committed: "725c89b237eca07220059b058561fa8afa91894a"
pr: "#60"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/60"
pr_state: MERGED
pr_base: main
pr_head: "feat/REL-001-mvp-rc-review-acceptance-checklist"
pr_head_sha: "725c89b237eca07220059b058561fa8afa91894a"
merge_commit: 4e8ceff74b95880b1c035d518bf2be43d2bbc907
merged_at: "2026-08-15T06:01:06Z"
feat_branch: deleted
working_tree: clean
next_action: "REL-001 completed — NO AUTO-START (Phase 5 has no subsequent Task); HUMAN: annotated tag v0.9.0-mvp-rc1 only (suggested object 412fb7b858120927aecad63962990587038df340); DO NOT create v1.0.0-mvp (A.1 Preflight still unchecked)"
developer_authorized: true
```

### 最终状态

`completed`
