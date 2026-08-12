# Memory System MVP Open Issues

本文件登记技术规格中的歧义与未决项。

规则：

1. 唯一规格来源仍是 `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`。
2. **未解决前不得自行解释为新的 API Contract、Schema、错误码、状态机或恢复语义。**
3. 每项决议必须写明日期、结论、是否修订规格、审批人；禁止覆盖历史，只能追加决议记录。
4. `是否阻塞当前任务` 相对于仓库当前任务（见 `progress.md` 的 `current_task`）。

---

## OI-001

```yaml
id: OI-001
spec_sections:
  - "§1.2.3"
  - "§1.2.6"
impact: "capacity_exceeded 后触发的「压缩协调一次」指整次多轮 Coordinator 还是单轮压缩"
blocks_current_task: false
resolve_by_task: STM-009
status: resolved
resolved_at: "2026-08-11T01:17:29Z"
resolved_by_task: STM-009
```

**问题描述：** 规格在容量背压路径要求运行压缩协调；“一次”与 `max_compression_rounds_per_request` 的关系未写死，影响 STM-009 实现与测试断言。

**禁止行为：** 不得在未解决前自行定为新 Contract。

**决议记录：**

- **2026-08-11** — STM-009 PR #28 MERGED（merge `924ca8c8af94793e76be9376c4514ef417ce5e33`）
- **Planner 决议（STM-009 Task Plan §10.1）**：「一次压缩协调流程」= 单次 `run_compression_coordination(...)` 调用，其内部可执行至多 `context.max_compression_rounds_per_request` 轮；容量路径与触发路径共用该函数
- **验收证据**：Unit U5/U20；Integration I-B（可配置 `max_compression_rounds_per_request`）
- **status**: resolved

---

## OI-002

```yaml
id: OI-002
spec_sections:
  - "§1.2.3"
  - "§1.2.6"
impact: "容量路径遇到压缩锁被其他持有者占用时，是否在重试后直接返回 working_memory_full"
blocks_current_task: false
resolve_by_task: STM-009
status: resolved
resolved_at: "2026-08-11T01:17:29Z"
resolved_by_task: STM-009
```

**问题描述：** 锁被占用导致无法压缩时，容量路径的最终 HTTP/错误语义需要与规格失败矩阵对齐，正文未单独展开该交叉场景。

**禁止行为：** 不得在未解决前自行定为新 Contract。

**决议记录：**

- **2026-08-11** — STM-009 PR #28 MERGED（merge `924ca8c8af94793e76be9376c4514ef417ce5e33`）
- **Planner 决议（STM-009 Task Plan §10.2）**：容量路径必须先调用 `run_compression_coordination`；压缩侧 `skipped_lock`/`failed` 等仍必须用相同 `message_id` 重试 STM-003；仅当 retry 仍 `capacity_exceeded` 时返回 HTTP 503 `working_memory_full`
- **验收证据**：Unit U6；Integration lock scenario（锁占用 + 满 WM → 503 且消息未写入）
- **status**: resolved

---

## OI-003

```yaml
id: OI-003
spec_sections:
  - "§1.2.3"
  - "§3.23"
impact: "close_incomplete 的 HTTP 状态码与统一错误码映射未在 §1 写死"
blocks_current_task: false
resolve_by_task: STM-010
status: resolved
resolved_at: "2026-08-11T09:30:00Z"
resolved_by_task: STM-010
```

**问题描述：** Session Close 在 Redis 删除未确认等情况下返回 `close_incomplete`；§1 未完整映射到 §3.23 的 HTTP 状态表。

**禁止行为：** 不得在未解决前自行定为新 Contract。

**决议记录：**

- **2026-08-11** — STM-010 Task Plan §10.3 Planner 决议
- **HTTP 映射**：`close_incomplete` → HTTP **503** + `error.code=close_incomplete`（§3.23 503 = 基础设施不可用或外部依赖暂时失败；与 `working_memory_full` 同类可重试语义）
- **语义**：Redis 终端删除失败或结果不可确认；Session 保持 `status=closing`；客户端可安全重试 close
- **规格依据**：§750–751（错误码字面量）；§3.23 HTTP 映射表
- **验收证据**：STM-010 Contract C9；Integration terminal 失败注入
- **status**: resolved（Contract 定义；实现验收归属 STM-010）

---

## OI-004

```yaml
id: OI-004
spec_sections:
  - "§1.2.2"
  - "§1.2.6"
impact: "Archive 文档未持久化 estimated_tokens 时，选择/切分所用 token 应从 Redis 消息还是重算"
blocks_current_task: false
resolve_by_task: "STM-005 / STM-010"
status: resolved
resolved_at: "2026-08-11T02:14:24Z"
resolved_by_task: STM-010
```

**问题描述：** Mongo Archive 消息 schema 未包含 `estimated_tokens`，但归档选择与 Close 切分依赖 token 边界。

**禁止行为：** 不得在未解决前自行定为新 Contract。

**决议记录：**

- **2026-08-10** — STM-005 POST_MERGE_CLEANUP evidence：Mongo archive messages persist 4 fields only（no `estimated_tokens`）；create/reuse contract delivered；full token-boundary resolution deferred to STM-010。
- **2026-08-11** — STM-009 POST_MERGE_CLEANUP evidence：Coordinator 侧所有 token 边界计算仅使用 Redis WM `WorkingMemoryMessage.estimated_tokens` 求和；Mongo 四字段不含 tokens；Finalize `archived_message_tokens == pending_archive_estimated_tokens`。
- **2026-08-11** — STM-010 Task Plan §10.4：七项 resolution criteria 已映射至 `split_close_suffix_batches`（Redis `estimated_tokens` 精确和）、Pending `pending_archive_estimated_tokens`、后缀全归档、OI4 Integration 验收。
- **2026-08-11** — STM-010 POST_MERGE_CLEANUP evidence（PR #29 MERGED merge `722e42d9e24d085b0ed671478730952ef7c92ad6`；implementation on main `ebb90e49c4eed8b7fd64a35611d7af87521d3d5a`；`test_oi4_token_boundary_closure` PASS）：
  1. Mongo 4-field only — I-C
  2. Token from Redis WM — U14, I-D, OI4
  3. No Mongo content re-estimate — Unit + OI4
  4. `archived_message_tokens` = Redis sum — OI4
  5. Final archive boundary closed — U6, U15, OI4
  6. Finalize consistency（close no Finalize）— I-L
  7. Post-close no token ambiguity — I-A, I-H
- **status**: resolved

---

## OI-005

```yaml
id: OI-005
spec_sections:
  - "§1.2.4"
impact: "文档中的 Context Archive Service 命名与进程内 Archive 逻辑是否仅为称谓"
blocks_current_task: false
resolve_by_task: STM-006
status: resolved
resolved_at: "2026-08-11T01:17:29Z"
resolved_by_task: STM-009
```

**问题描述：** 事件生产者描述出现 “Memory API / Context Archive Service” 表述，而工程上 Compression/Archive 协调在 `memory-api` 进程内；需确认无额外独立服务 Contract。

**禁止行为：** 不得在未解决前自行拆分未规定的网络服务。

**决议记录：**

- **2026-08-10** — STM-006 POST_MERGE_CLEANUP partial evidence：`archive_created_publisher` 与 `compression_preparation_service` 均在 `memory-api` 进程内；未创建独立 Context Archive Service 网络组件；Kafka publish 复用 `AppState.kafka_producer`。**status remains open**（正式治理落盘 OI-005 决议段待人工/后续 OI task 闭合）。
- **2026-08-11** — STM-009 PR #28 MERGED（merge `924ca8c8af94793e76be9376c4514ef417ce5e33`）+ STM-006 partial evidence：`compression_coordinator_service` 在 `memory-api` 进程内编排；`AppState.kafka_producer`；**无**独立 Context Archive Service 网络组件；**status**: resolved

---

## OI-006

```yaml
id: OI-006
spec_sections:
  - "§2.1.11"
  - "§2.1.14"
impact: "reconciliation_plan_conflict 的特殊运维清理路径无 API Contract"
blocks_current_task: false
resolve_by_task: "EXT-008 前需规格确认"
status: open
```

**问题描述：** 规格提到特殊运维清理，但未定义管理 API 形状；影响失败任务是否可 retry 及人工恢复手册。

**禁止行为：** 不得在未解决前自行新增管理 API 或 Schema。

**决议记录：** （空）

---

## OI-007

```yaml
id: OI-007
spec_sections:
  - "§2.1"
  - "§3.4"
impact: "人工 Archive 事件重放仅有脚本入口，无独立 REST Contract"
blocks_current_task: false
resolve_by_task: STM-011
status: open
```

**问题描述：** `scripts/republish_archive_event.py` 为规格目录要求的运维工具；是否永不提供 HTTP 需在实现 Task Plan 中保持“仅 CLI”除非规格修订。

**禁止行为：** 不得在未解决前自行增加 REST 重放 API。

**决议记录：** （空）

---

## OI-008

```yaml
id: OI-008
spec_sections:
  - "§2.2.15"
impact: "失败处理条目编号笔误（重复编号/跳号），属编辑性问题"
blocks_current_task: false
resolve_by_task: RET-005
status: open
```

**问题描述：** §2.2.15 列表编号存在两个 “5.” 及跳号；不改变正文失败/降级语义，但影响引用准确性。

**禁止行为：** 不得借编号问题改写降级语义。

**决议记录：** （空）

---

## OI-009

```yaml
id: OI-009
spec_sections:
  - "§1.2.3"
impact: "GET 上下文更新 updated_time 与 MVP 无 idle 清理并存的意图说明"
blocks_current_task: false
resolve_by_task: STM-004
status: resolved
resolved_at: "2026-08-10T08:02:11Z"
resolved_by_task: STM-004
```

**问题描述：** 读路径触摸 `updated_time` 已写明；与“不做 idle session 清理”同时存在，实现时不得引申出未规定的 TTL/自动关闭行为。

**禁止行为：** 不得在未解决前增加 Redis TTL 或自动 Close。

**决议记录：**

- 日期：2026-08-10 08:02 UTC
- 审批：STM-004 POST_MERGE_CLEANUP（PR #22 MERGED）
- Planner 决议（Task Plan §10.1）：上下文读取 Lua **严格只读** — **不** `HSET updated_time`；**不** 引入 Redis TTL/EXPIRE/闲置扫描/自动关闭；`updated_time` 仅由写入（STM-003）与未来压缩写回（STM-008）更新
- 验收证据：Integration I13 — `updated_time` 读前后不变；全 Key `TTL=-1`
- merge_commit：`6a3d09f5bf29ec25c768c6295e2c13adb3ff9a6c`；implementation：`3aed60522db64c3b11597e025caa0aae00afaba6`

---

## OI-010

```yaml
id: OI-010
spec_sections:
  - "§3.5"
impact: "Python 项目 Build Backend 未在技术规格 §3.5 中固定，但 DEV-001 当前目标要求项目可安装（src layout + uv）"
blocks_current_task: false
resolve_by_task: "DEV-001 再次计划审查前须由人工决议"
status: resolved
```

**问题描述：** 规格 §3.5 固定了 `uv`、`pyproject.toml`、`uv.lock` 与运行时/质量/测试依赖范围，但未指定 `[build-system]` / Build Backend（例如是否使用 Hatchling、Setuptools、uv_build 或其他）。DEV-001 需要生成可安装包与 `uv sync --locked`，缺少该决议则无法在不擅自选型的前提下完成可安装闭环。

**是否阻塞当前任务：** **否**（已决议）。

**禁止行为：** 不得偏离已决议的 Build Backend；禁止替换为 Hatchling、Setuptools、Poetry Backend 或其他构建后端；禁止放宽或抬高 `uv_build>=0.11.32,<0.13` 上界；禁止将 `uv_build` 写入 `project.dependencies`、`quality` 或 `test` 组。

**决议记录：**

- 日期：2026-08-06 08:11 UTC
- 审批：人工正式决议
- 选择：`uv_build` 作为 Python Build Backend
- 版本范围：`requires = ["uv_build>=0.11.32,<0.13"]`，`build-backend = "uv_build"`
- 理由：与既定 `uv` 工具链一致；`uv_build` 作为 Build System Requirement，与运行时/质量/测试依赖分离
- 技术规格：§3.5 已同步写入上述 `[build-system]` 固定配置与禁令

---

## OI-011

```yaml
id: OI-011
spec_sections:
  - "§3.10.3"
  - "§3.10.8"
  - "§3.18 #12"
impact: "CPU TEI mem_limit=8g 与 BAAI/bge-m3 float32 ONNX CPU warm-up 峰值冲突；须 Spec-OI 选定新 profile-specific 固定 mem_limit 并同步 compose/preflight"
blocks_current_task: false
resolve_by_task: OI-011
status: resolved
task_plan: 02_开发管理/tasks/OI-011-bge-m3-cpu-tei-memory-contract.md
```

**问题描述：** DEV-003-002 正式 runtime probe（§13）在 spec-compliant `mem_limit=8g` 下确认 `OOMKilled=true`、`exit_code=137`、`health_ready=false`、`rss_peak_warmup_bytes` 触顶；分类 A（container cgroup limit 不足；宿主机物理内存充足）。当前规格 §3.10.3 / §3.18 #12 / `compose.embedding.cpu.yaml` 字面 8g 与该 model-runtime profile 不可同时成立。`MEMORY_LIMIT_DECISION` 尚未经有限 characterization matrix 批准。

**是否阻塞当前任务：** **否**（OI-011 completed；PR #15 merged；DEV-006 R2–R4 satisfied on main；R5–R7 pending DEV-006 单独恢复；**不得** Merge PR #13）。

**禁止行为：**

- 不得将 `docker update --memory=…` 结果作为正式 evidence 或默认 Contract
- 不得无限扫描 mem_limit / dtype / model
- 不得在未完成 OI-011 前恢复 DEV-006 §8.8 或 Merge PR #13
- 不得把 limit 做成无 Spec-OI 的自由 configurable 旋钮绕过可复现合同
- 不得修改 GPU `mem_limit`（无本 OI 授权）

**规划态备注（非决议）：** Round 1 Plan Review = `PLAN_REJECTED`（BLOCKER=0；MUST_FIX=4；SHOULD_FIX=4）。Task Plan **Amendment 001** / **Amendment 002** 已吸收全部 MF/SF。Round 3 = `PLAN_APPROVED`（BLOCKER=0；MUST_FIX=0；2026-08-09 人工确认）。Phase A–C 已完成；`status=resolved`。

**决议记录：**

- **2026-08-09**：有限 matrix `{8g,10g,12g,16g}`×2 正式 clean runs（无 docker update；probe 显式多 `-f`）。8g/10g = NON_VIABLE（8g OOM；10g peak≥limit）。12g/16g = Viable + safety margin；按最小充分原则选定 **`MEMORY_LIMIT_DECISION=12g`**（P=10919954350；headroom=1964947538≥required 1932735284）。规格 §3.10.3 改为 profile-specific fixed contract + `NON_SPEC_COMPLIANT`；§3.18 #8 方案 A → CPU_MIN/REC=16/20；Check 13a=14；compose/preflight/start_embedding/contract/Layer B PASS@12g 对齐。`status`→`resolved`。
- **2026-08-09 02:42 UTC**：PR #15 MERGED 至 main（Merge Commit `7cc020a97b0373579a91e620fcdef90976193c8c`）；implementation `131a2e994690adb4b06b4d0fa299b229e88ca7d3`；`RUNTIME_CONTRACT_STATUS=PASS`；historical 8g `SPEC_RUNTIME_CONTRACT_CONFLICT` 证据保留（`archived_conflict_evidence_v1.json`；禁止覆盖）。DEV-006 OI-011 dependency **SATISFIED**；`dev006_dependency_status=READY_FOR_RESUME_AFTER_OI011_MERGE`；DEV-006 仍 **PAUSED**（R5–R7 pending）；**不得** Merge PR #13。

---

## OI-012

```yaml
id: OI-012
spec_sections:
  - "§2.2.6（最小 SiliconFlow 增补）"
  - "§2.2.14 embedding_provider 默认 siliconflow"
  - "§3.1 Embedding 默认 SiliconFlow"
  - "§3.8 SILICONFLOW_API_KEY"
  - "§3.10 最小 pivot 句"
impact: "最小 MVP：默认 Embedding pivot 至 SiliconFlow BAAI/bge-m3（dim=1024）；TEI optional/non-MVP-blocking；单一 downstream DEV-007 实现"
blocks_current_task: false
resolve_by_task: OI-012
downstream_dev_task: DEV-007
status: resolved
task_plan: 02_开发管理/tasks/OI-012-siliconflow-embedding-provider-spec-oi.md
amendment: "Amendment 002 MVP_SIMPLIFICATION + Amendment 002.1（Round 2 MF-1/SF-1～4）"
resolved_at: "2026-08-09 06:55 UTC"
resolved_by_task: OI-012
```

**问题描述：** MVP 须将默认 Embedding 从 `local_tei` pivot 至 SiliconFlow 托管 `BAAI/bge-m3`。Amendment 002 将 OI-012 **缩减为最小 Spec-OI**（架构决策记录 + 最小规格句），**不**一次性重构 embedding 架构。实现合并为 **单一 DEV-007**（取消 DEV-008/009）。官方未知：bge-m3 输出维度（Integration 须验证 dim=1024 否则 HALT）。DEV-006/PR#13：**PAUSED/SUPERSEDED_FOR_MVP** + **DO_NOT_MERGE**（决策 deferred）。

**是否阻塞当前任务：** **否**（PR#13 处置 deferred）。

**禁止行为：**

- 不得猜测 SiliconFlow bge-m3 输出维度（须 Integration 验证）
- 不得 merge/rewrite PR #13 **本 MVP**
- 不得访问 DEV-006 dirty worktree
- 不得在本 OI 引入 local HF tokenizer 或 §3.3/§3.18 大规模改写
- 不得让 STM/EXT/RET 直接依赖 SiliconFlow SDK

**决议记录（2026-08-09；Amendment 002/002.1 吸收；Round 3 PLAN_APPROVED）：**

1. **默认 Provider**：`memory_retrieval.embedding_provider=siliconflow`（`local_tei` 枚举保留，可选自托管，非 MVP 阻塞）。
2. **模型与维度**：`BAAI/bge-m3`；`dimension=1024`；Integration gate：`dim≠1024` → **HALT**（不改 ES mapping）。
3. **Secret Contract**：`SILICONFLOW_API_KEY`（`SecretStr`）；仅 `siliconflow` provider 必填（§3.8）。
4. **规格最小 pivot**：§3.1 / §2.2.14 / §3.8 / §3.10.0 / §2.2.6（SiliconFlowEmbeddingClient 一句；`EmbeddingClient` 唯一业务边界）；§3.3/§3.18 **未**大规模改写。
5. **Batch limits**：SiliconFlow **32**/request；TEI **64**/request（各自 Client Contract 内分片）。
6. **Retry（DEV-007 Contract 引用）**：**1 次初始 + 最多 2 次重试 = 最多 3 次 HTTP attempt**。
7. **L2 归一化**：SiliconFlow 向量 L2 归一化语义 **UNKNOWN / DEV-007 规划决策**（不得猜测）。
8. **下游**：**单一 DEV-007**（合并原 DEV-007/008/009 意图）；**无** DEV-008/009。
9. **DEV-006 / PR #13**：**PAUSED / SUPERSEDED_FOR_MVP**；PR #13 **OPEN / DO_NOT_MERGE**；决策 deferred 至 DEV-007 Integration gate PASS。
10. **Amendment 002.1 traceability（SHOULD_FIX SF-R3-001）**：`latest_commit`/`git` 前提 SHA = `c8c03db4b984a1e65b7d2d46b392f87a938c8eec`（`git rev-parse HEAD` 验证；禁混缀）；`plan_commit` = `e122c8ab840720a4f86cffda5a58e5f9e6f34944`。

---

---

## Historical pre-Amendment 004 EXT-002 issue records

The following issue descriptions and interim behaviors are append-only historical evidence from before authoritative Amendment 004. They are not effective current blockers or implementation instructions. The effective dispositions are recorded in the Amendment EXT-002-004 resolution record below.

## OI-EXT-002-001
```yaml
id: OI-EXT-002-001
title: "Credential detection and redaction rules are undefined"
spec_sections: ["§2.1.5", "§2.1.15"]
ambiguity: "§2.1.5 specifies only that detected sensitive credentials are replaced before LLM use by [REDACTED_SECRET] and raw Archive is unchanged; credential classes/rules, boundaries, ordering, overlap or multiple-match precedence, malformed/partial-match, detector failure, and normalization/redaction order are unspecified."
affected_contract_behavior: "Cannot safely construct an LLM-facing content field, claim privacy completion, or declare ExtractionReadyArchive EXT-003-ready."
currently_specified_token_behavior: "Detected sensitive credential -> exact [REDACTED_SECRET] before LLM; raw Archive unchanged."
privacy_risk: "Guessed rules can leak credentials through false negatives or destroy legitimate content through false positives; no-detection is not evidence of safety."
downstream_ext003_impact: "No ExtractionReadyArchive handoff, LLM call, prompt input, or EXT-003-ready claim."
safe_interim_behavior: "Historical pre-Amendment 004 only: REDACTION_SPEC_STATUS=BLOCKED_PENDING_SPEC_DECISION; fail closed before LLM handoff; no fake/minimal regex, heuristic, dependency, scanner, alternative marker, or invented terminal mapping."
blocking: false
decision_needed: "Authoritative specification amendment defining one deterministic secret-detection/redaction policy: credential classes, patterns/boundaries, rule order, overlap/multiple-match behavior, malformed/partial-match behavior, normalization order, detector failure handling, and conformance fixtures. Do not choose arbitrary regex defaults."
status: resolved
```

**决策包：** 标题、受影响规格章节、当前已规定的 token 行为、缺失语义、隐私风险及 EXT-003 下游影响如上。实现所需的精确决策是该权威确定性 secret-detection/redaction policy；在决议前不得把“未检测到”解释为安全。

## OI-EXT-002-002
```yaml
id: OI-EXT-002-002
title: "Normalized versus redacted content handoff semantics are undefined"
spec_sections: ["§2.1.5"]
ambiguity: "normalized_content is temporary while the example exposes content; replacement ownership and normalization/redaction order are unstated."
affected_contract_behavior: "ExtractionReadyArchive content shape and privacy boundary."
safe_interim_behavior: "No LLM-facing handoff and no durable raw/normalized/redacted field."
blocking: false
decision_needed: "Specify exact normalization/redaction order, field replacement ownership, consumer reliance, overlap/multiple-match behavior, and partial-failure semantics."
status: resolved
```

## OI-EXT-002-003
```yaml
id: OI-EXT-002-003
title: "First-person binding representation and lifecycle are undefined"
spec_sections: ["§2.1.5", "§2.1.6"]
ambiguity: "Representation, ownership/provenance, EXT-003 consumption, and persistence/non-persistence for first-person binding are not defined."
affected_contract_behavior: "Output/data shape and provenance; no identity representation can be safely synthesized."
safe_interim_behavior: "Preserve original role/provenance; synthesize no identity, add no durable field, and leave unresolved references unknown."
blocking: false
decision_needed: "Authoritative citation defining representation, ownership/provenance, EXT-003 use, and persistence."
status: deferred_out_of_scope
```

## OI-EXT-002-004
```yaml
id: OI-EXT-002-004
title: "Unexpected redaction/configuration failure has no authorized mapping"
spec_sections: ["§2.1.15", "§2.1.16"]
ambiguity: "No redaction-specific error code or failed_stage mapping is authorized for unexpected gate/configuration failures."
affected_contract_behavior: "Terminal failed behavior and Kafka offset consequence."
safe_interim_behavior: "Historical pre-Amendment 004 only: REDACTION_SPEC_STATUS=BLOCKED_PENDING_SPEC_DECISION; remain gated/abort_without_terminal and do not commit an offset."
blocking: false
decision_needed: "Specify whether and how unexpected redaction/configuration failures map to already authorized error_code and failed_stage fields; no new mapping may be invented."
status: resolved
```

## OI-EXT-002-005
```yaml
id: OI-EXT-002-005
title: "Raw-document versus message-validation boundary and failed_stage vocabulary are undefined"
spec_sections: ["§2.1.5", "§2.1.15"]
ambiguity: "The specification does not explicitly distinguish structurally corrupt documents from valid documents with invalid message elements, does not define failed_stage values, and the existing typed repository lookup coercively maps BSON values."
affected_contract_behavior: "Exact invalid_archive mapping, no-partial-preprocessing boundary, terminal persistence, and offset commit."
safe_interim_behavior: "Use only a read-only raw mapping lookup by archive_id; strict no-coercion validation; no partial preprocessing; only existing error codes; no undocumented failed_stage literal."
blocking: false
decision_needed: "Authorize the four-way boundary and exact failed_stage values for missing, structurally corrupt, message-level invalid, and valid Archive outcomes, or leave unauthorized paths non-terminal until amended."
status: resolved
```

**Amendment EXT-002-004 resolution record (2026-08-12; human/spec owner decision):**

- `OI-EXT-002-001` resolved: deterministic local, content-only secret detection/redaction categories, precedence, span handling, exact marker, no-match success, and failure behavior are authoritative.
- `OI-EXT-002-002` resolved: complete validation → deterministic normalization → deterministic redaction; only normalized+redacted `messages[].content` is eligible for handoff.
- `OI-EXT-002-003` **DEFERRED / OUT_OF_SCOPE**: preserve role/provenance; no identity representation or durable field; EXT-003 cannot rely on first-person binding; this is not an unresolved EXT-002 blocker.
- `OI-EXT-002-004` resolved: redaction failure is `redaction_failed` at `redaction`; nondeterministic infrastructure/internal failure is `abort_without_terminal`, with no commit.
- `OI-EXT-002-005` resolved: missing Archive is `archive_not_found` at `archive_read`; structural/nested/message invalidity is `invalid_archive` at `archive_validate`; terminal persistence precedes Offset commit.
- Effective EXT-002 state: no blocking Open Issue remains; `REDACTION_SPEC_STATUS=SPECIFIED`; raw validation, redaction, and `ExtractionReadyArchive` handoff are authorized only by the Amendment 004 contract.
- Unrelated Open Issues remain unchanged. Specification amendment: `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`, Appendix A, Amendment `EXT-002-004`.

---

## OI-EXT-003-001
```yaml
id: OI-EXT-003-001
title: "Structured Extraction unknown-field policy conflicts with strict durable validation"
spec_sections:
  - "§2.1.6"
  - "§2.1.7"
  - "Appendix B Amendment EXT-003 §B.1"
impact: "The LLM output durable schema cannot be implemented safely: §2.1.7 says unknown fields can be ignored, while strict application validation and extraction_result persistence require an explicit reject/strip/admit policy."
blocks_current_task: false
resolve_by_task: EXT-003
status: resolved
```

**问题描述：** §2.1.6 presents a fixed Structured Output shape, while §2.1.7 says unknown fields “可以忽略” and separately requires application validation. It is not defined whether unknown top-level/entity/memory fields are rejected, stripped before durable persistence, retained in a bounded non-durable parse, or allowed to affect duplicate/equivalence/fingerprint processing.

**禁止行为：** 不得自行选择 Pydantic `extra="forbid"`、`extra="ignore"` 或 `extra="allow"` 作为 durable Contract；不得把未知字段静默写入 `memory_extraction_task.extraction_result`；不得让未知字段影响 fingerprint。

**安全中间行为（历史）：** EXT-003 implementation remained blocked until authoritative decision was recorded.

**Amendment EXT-003 resolution record (2026-08-12; human/spec owner decision):**

- **RESOLVED** — unknown fields: ignore during parse; strip before persistence; only authorized fields in `extraction_result`; no persist/fingerprint/duplicate influence.
- Effective contract: Appendix B §B.1; Task Plan Amendment 002.

---

## OI-EXT-003-002
```yaml
id: OI-EXT-003-002
title: "Fingerprint canonical bytes and candidate equivalence/order are underspecified"
spec_sections:
  - "§2.1.7"
  - "§2.1.8"
  - "Appendix B Amendment EXT-003 §B.7–B.8"
impact: "Durable candidate_fingerprint and extraction_result replay identity are not fully reproducible without Unicode JSON escaping, number/string serialization, duplicate source-ID, candidate equivalence, and candidate-array ordering rules."
blocks_current_task: false
resolve_by_task: EXT-003
status: resolved
```

**问题描述：** §2.1.7 fixes field order, UTF-8, no extra whitespace, and sorted `source_message_ids`, but does not define JSON Unicode escaping (`ensure_ascii` versus literal UTF-8), number serialization, string canonicalization, duplicate source-ID handling, whether “完全相同” candidate equivalence includes source IDs, or how merged candidates/entities are ordered in the durable result. These choices can change SHA-256 bytes or durable replay content.

**禁止行为：** 不得私自加入 Unicode NFKC、trim、whitespace folding、case folding、locale ordering、JSON key sorting、number normalization、source-ID deduplication、candidate reordering、collision error code或fallback；不得在未决议前声明 fingerprint deterministic。

**安全中间行为（历史）：** 仅记录规范明确的 fixed field order、UTF-8、compact/no-whitespace、sorted source IDs；暂停 fingerprint implementation and duplicate/equivalence persistence behavior.

**Amendment EXT-003 resolution record (2026-08-12; human/spec owner decision):**

- **RESOLVED** — fingerprint: SHA-256 UTF-8 compact JSON array of fields in exact order; before serialization dedupe+lex sort `source_message_ids`; `ensure_ascii=false`; JSON null; no extra trimming/normalization; `candidate_source_time` excluded.
- **RESOLVED** — duplicates/ordering: entities preserve provider order, no dedup; memories preserve first occurrence; fully identical = all durable LLM memory fields except `source_message_ids` equal; merge source IDs dedupe+lex sort; one memory; no confidence aggregation.
- Effective contract: Appendix B §B.7–B.8; Task Plan Amendment 002.

---

## OI-EXT-003-003
```yaml
id: OI-EXT-003-003
title: "Stricter Structured Output correction prompt is not textually specified"
spec_sections:
  - "§2.1.6"
  - "§2.1.7"
  - "§3.9"
  - "Appendix B Amendment EXT-003 §B.5"
impact: "The required one-time schema retry cannot be reproduced or contract-tested without the exact correction prompt; copying Compression behavior would change the extraction contract."
blocks_current_task: false
resolve_by_task: EXT-003
status: resolved
```

**问题描述：** 规格要求第一次 Structured Output 校验失败后，用相同 Archive 和“更严格的纠错 Prompt”重试一次，但没有给出该 retry system/user prompt 的精确文字、变量、是否保留原 prompt 或允许哪些 correction instruction。

**禁止行为：** 不得静默复用首次 prompt、复制 STM-007 Compression 的相同-prompt retry、追加未授权的自然语言、把完整失败 response 放入 prompt，或改变一次 retry/无 transport retry 语义。

**安全中间行为（历史）：** 只可固定首次 §2.1.6 system/user prompt；retry prompt implementation、prompt contract tests 和生产 LLM extraction remained blocked.

**Amendment EXT-003 resolution record (2026-08-12; human/spec owner decision):**

- **RESOLVED** — one retry for blank/invalid JSON/schema/source refs/other validation failures; no retry for timeout/provider/429/5xx; same redacted input; no prior invalid response in prompt.
- Exact correction instruction:

```text
The previous response was invalid.
Return exactly one valid JSON object matching the required extraction schema, using only source_message_ids from the provided archive.
Return JSON only.
```

- No third call. Effective contract: Appendix B §B.5; Task Plan Amendment 002 §6.2.

---

## OI-EXT-003-004
```yaml
id: OI-EXT-003-004
title: "EXT-003 extraction-result success has no authorized handoff in terminal-only PipelineTerminalDecision"
spec_sections:
  - "§2.1.1"
  - "§2.1.3"
  - "§2.1.4"
  - "§2.1.6"
  - "§2.1.15"
  - "Appendix B Amendment EXT-003 §B.2, §B.10"
impact: "Existing EXT-001 ExtractionPipelinePort exposes only complete/fail/abort_without_terminal, but EXT-003 stops before EXT-004 alignment/graph/index completion. Mapping non-empty LLM success to complete would falsely commit the task; mapping it to abort would create a replay loop."
blocks_current_task: false
resolve_by_task: EXT-003
status: resolved
```

**问题描述：** EXT-001's `PipelineTerminalDecision` is terminal-only. The authoritative flow requires validated `extraction_result` persistence before entity alignment and later Neo4j/Elasticsearch gates, while EXT-003 explicitly must not implement those later stages. The current Contract has no “stage success/continue” outcome or ownership rule for wiring the next stage.

**禁止行为：** 不得在 EXT-003 将非空 Archive 的 extraction-only success 映射为 whole-task `complete`；不得把 `abort_without_terminal` 当作正常 continuation；不得修改 existing decision/state/offset semantics without authoritative approval；不得启动 production worker before all completion gates exist.

**安全中间行为（历史）：** 保留 EXT-001 terminal and offset semantics；保留 EXT-002 empty-Archive normal completion；worker `main()` remains refusal-only；EXT-003 may be planned as an isolated LLM/result service but no production non-empty pipeline wiring is authorized.

**Amendment EXT-003 resolution record (2026-08-12; human/spec owner decision):**

- **RESOLVED** — EXT-003 owns handoff→LLM→validation→dup norm→fingerprint→source_time→persist; replay `processing`+non-null result skips LLM.
- **RESOLVED** — both-empty (`entities=[]`, `memories=[]`): persist empty result, `completed`, Offset after persistence.
- **RESOLVED** — ANY non-empty `extraction_result`: persist complete validated result, task remains `processing`, do NOT commit Offset.
- **RESOLVED** — EXT-004 continuation `DEFERRED_FOR_MVP`; do NOT modify `PipelineTerminalDecision`; EXT-004 consumes persisted result.
- Effective contract: Appendix B §B.2, §B.10; Task Plan Amendment 002.

---

## OI-EXT-003-005
```yaml
id: OI-EXT-003-005
title: "SHA-256 fingerprint collision handling deferred for MVP"
spec_sections:
  - "§2.1.7"
  - "Appendix B Amendment EXT-003 §B.9"
impact: "No authoritative collision recovery, deduplication fallback, or collision error code for candidate_fingerprint SHA-256 collisions in MVP."
blocks_current_task: false
resolve_by_task: "later Evidence/reconciliation"
status: deferred_for_mvp
```

**问题描述：** Appendix B §B.9 defers SHA-256 collision handling for MVP. EXT-003 uses ordinary SHA-256 identity comparison only; any collision policy belongs to later Evidence/reconciliation work.

**禁止行为：** 不得在 EXT-003 发明 `fingerprint_collision` error code、fallback field 或 collision recovery behavior。

**安全中间行为：** EXT-003 implements fingerprint as SHA-256 identity material; collision handling is non-blocking and owned by later tasks.

**所需决议：** Deferred — owner by later Evidence/reconciliation; non-blocking for EXT-003 MVP.

---

## OI-EXT-004-001
```yaml
id: OI-EXT-004-001
title: "§2.1.10 step 4 secondary exact-match operands, comparison basis, and multi-match determinism are undefined"
spec_sections:
  - "§2.1.10"
  - "§2.1.9"
  - "§2.1.6"
impact: "Entity identity assignment cannot be determined. Different readings bind candidates to different entity_id values, which changes the durable Memory subject_entity_id/object_entity_id and the pre-transaction aligned_memory_key. This is irreversible durable graph identity, not a reversible internal choice."
blocks_current_task: false
resolve_by_task: EXT-004
status: resolved_by_plan
resolution: "Amendment 002 MVP_LOCAL_DECISION — Task Plan §5.2.2 + LD-7/LD-8; non-blocking"
round_1_blocks_current_task: true
```

**问题描述：** §2.1.10 第 4 步规定「若未匹配，查询当前用户、相同 `entity_type` 下 `canonical_name` 或 `aliases` 完全相同的实体」，但未定义：

1. 比较操作数集合：仅候选 `name`，还是同时包含候选 `aliases`？
2. 比较基准：候选 `name` 原文与既有 `canonical_name` 原文精确比较，还是使用第 2 步产出的 `normalized_name`？
3. alias 侧语义：既有 `aliases` 数组元素精确相等，还是其他匹配方式？
4. 多命中：同一 `user_id + entity_type` 下 ≥2 个不同实体命中时，是确定性择一（依据哪个排序键）还是 fail-closed？若 fail-closed，使用哪个已授权错误码——`entity_alignment_failed` 的规格语义为「实体对齐执行失败 / 可人工重试」，与不可重试的数据歧义不符。
5. 候选经第 3 步 `entity_key` 精确匹配解析到用户实体节点时是否特殊处理，其别名是否必须保持不变（§2.1.10.1「用户实体不参与普通名称和别名对齐」）。

`entity_key_unique` 仅保证同一 `(user_id, entity_type, normalized_name)` 唯一，不阻止不同实体的 `aliases` 出现相同值，因此多命中在 MVP 数据中真实可发生。

**禁止行为：** 不得先实现「猜测版」第 4 步；不得以任意排序静默取首条；不得引入模糊/相似度/全文/向量匹配；不得新造歧义错误码（如 `entity_alignment_ambiguous`）；不得把数据歧义映射为可重试的执行失败而未获授权。

**安全中间行为（Round 1）：** 第 1–3 步语义明确，但第 4 步未决即无法确定第 5 步边界，故 Round 1 将 EXT-004 标为 blocking。

**Round 2 闭合（Amendment 002；非 Spec Amendment）：** Task Plan §5.2.2 固定：S4 候选操作数仅 `normalized_name`；既有侧 `normalized_name` + `normalize_entity_alias(aliases[])`；`user_id` + `entity_type` 过滤；零命中→S5；单命中→`canonical_or_alias_exact`；多命中→**`entity_id ASC` 择一**（LD-8，不 fail-closed）。`blocks_current_task: false`。

**所需决议：** ~~权威 owner 决议~~ → **已由 Task Plan Amendment 002 闭合**（MVP_LOCAL_DECISION）。

---

## OI-EXT-004-002
```yaml
id: OI-EXT-004-002
title: "No authorized failed_stage literal exists for entity_alignment_failed"
spec_sections:
  - "§2.1.3"
  - "§2.1.15"
  - "Appendix A Amendment EXT-002-004 §A.1, §A.2"
  - "Appendix B Amendment EXT-003 §B.6"
impact: "last_error.failed_stage is a durable contract field. Existing authorized literals are only archive_read, archive_validate, redaction, and llm_extraction; the entity-alignment stage has none, so EXT-004 cannot express a terminal alignment failure without inventing vocabulary."
blocks_current_task: false
resolve_by_task: EXT-004
status: resolved_by_plan
resolution: "Amendment 002 MVP_LOCAL_DECISION — failed_stage=entity_alignment (LD-9); non-blocking"
round_1_blocks_current_task: true
```

**问题描述：** §2.1.15 授权了错误码 `entity_alignment_failed`（「实体对齐执行失败」；可人工重试=是），但 `failed_stage` 字面量词表只在 Appendix A/B 中被逐项授权，且不含实体对齐阶段。同时需要确认 `graph_query_failed`（「查询已有记忆失败」）的归属边界：其规格含义指向 §2.1.11 已有 Memory 候选召回（EXT-005），而非 EXT-004 的 Entity 只读查询。

**需决议：**

1. `entity_alignment_failed` 对应的 `failed_stage` 精确字面量（建议 `entity_alignment`）。
2. 确认 `graph_query_failed` 保留给 §2.1.11 已有 Memory 召回（EXT-005）；EXT-004 的 Neo4j 只读实体查询失败必须映射为 `entity_alignment_failed`。
3. 确认图谱 Entity 数据结构异常（property 缺失或类型非法，无法映射为授权只读快照）归入 `entity_alignment_failed`，而非新码。

**禁止行为：** 不得发明 `failed_stage` 字面量；不得复用 `llm_extraction` 或 `graph_write`；不得在 EXT-004 使用 `graph_query_failed`；不得新增错误码。

**安全中间行为（Round 1）：** 未决前不实现 EXT-004 失败映射。

**Round 2 闭合（Amendment 002；非 Spec Amendment）：** `entity_alignment_failed` → `failed_stage="entity_alignment"`（LD-9）；`graph_query_failed` 仍保留 EXT-005；Entity 结构异常同映射。`blocks_current_task: false`。

**所需决议：** ~~权威 owner 授权字面量~~ → **已由 Task Plan Amendment 002 闭合**（MVP_LOCAL_DECISION）。

---

## OI-EXT-004-003
```yaml
id: OI-EXT-004-003
title: "normalized_name and candidate alias normalization micro-semantics are not fully pinned"
spec_sections:
  - "§2.1.10"
  - "§2.1.6"
impact: "entity_key is durable identity material; residual normalization choices (lower vs casefold, whitespace class, alias 去空白 scope) can change entity_key for edge-case inputs."
blocks_current_task: false
resolve_by_task: EXT-004
status: open
```

**问题描述：** §2.1.10 第 2 步列明四项操作（Unicode NFKC、转小写、去除首尾空格、连续空白标准化），§2.1.6 列明候选 aliases「先执行 NFKC、去空白、去重并排序」，但未定义 `str.lower()` 与 `str.casefold()` 的取舍、空白字符集合，以及 alias「去空白」是仅去首尾还是同时压缩内部空白。

**禁止行为：** 不得追加规格未写明的 canonicalization（标点剥离、同义词映射、locale 排序、数字归一、case folding 之外的大小写规则）。

**安全中间行为（本计划固定读法）：** `normalized_name` = NFKC → `str.lower()` → 连续 Unicode 空白压缩为单个 `U+0020` → 去首尾空白（顺序不可换）；候选 alias = NFKC → 连续空白压缩 → 去首尾空白 → 精确去重 → 按 code point 字典序排序。以固定测试向量锁定；`entity_key` 采用仓库既有 SHA-256 约定（UTF-8 编码 + 小写 hexdigest）。

**所需决议：** owner 可确认或修订上述字面读法；非阻塞。

---

## OI-EXT-004-004
```yaml
id: OI-EXT-004-004
title: "canonical_name replacement criterion has no deterministic MVP basis; user entity alias non-participation needs confirmation"
spec_sections:
  - "§2.1.10"
impact: "Alias merge planning must decide whether canonical_name may be replaced and whether the user entity participates in alias merge."
blocks_current_task: false
resolve_by_task: EXT-004
status: open
```

**问题描述：** §2.1.10 允许在「新名称是用户明确给出的正式名称」时替换 `canonical_name`，但 MVP 没有确定性判据（该判定需语义能力，属 §2.1.11 之后）。同时 §2.1.10.1 规定「用户实体不参与普通名称和别名对齐」，其对别名合并的含义需确认。

**禁止行为：** 不得用启发式或 LLM 判定「正式名称」；不得自动把候选 `name` 加入既有实体 aliases；不得因 50 上限删除既有 alias。

**安全中间行为（本计划固定读法）：** MVP 恒不替换 `canonical_name`；解析到 `entity_id = "user:" + user_id` 的对齐条目不执行别名合并（`planned_aliases` 等于既有 aliases，或计划创建时为 `[]`）。

**所需决议：** owner 可确认或修订；非阻塞。

---

## 索引

| 问题 ID | 最迟解决任务 | 是否阻塞当前任务 | 状态 |
|---|---|---|---|
| OI-001 | STM-009 | 否 | resolved |
| OI-002 | STM-009 | 否 | resolved |
| OI-003 | STM-010 | 否 | resolved |
| OI-004 | STM-005 / STM-010 | 否 | resolved |
| OI-005 | STM-006 | 否 | resolved |
| OI-006 | EXT-008 前需规格确认 | 否 | open |
| OI-007 | STM-011 | 否 | open |
| OI-008 | RET-005 | 否 | open |
| OI-009 | STM-004 | 否 | resolved |
| OI-010 | 已人工决议（uv_build） | 否 | resolved |
| OI-011 | OI-011 | 否 | resolved |
| OI-012 | OI-012 | 否（PR#13 deferred） | resolved |
| OI-EXT-002-001 | EXT-002 | 否 | resolved |
| OI-EXT-002-002 | EXT-002 | 否 | resolved |
| OI-EXT-002-003 | EXT-002 | 否 | deferred_out_of_scope |
| OI-EXT-002-004 | EXT-002 | 否 | resolved |
| OI-EXT-002-005 | EXT-002 | 否 | resolved |
| OI-EXT-003-001 | EXT-003 | 否 | resolved |
| OI-EXT-003-002 | EXT-003 | 否 | resolved |
| OI-EXT-003-003 | EXT-003 | 否 | resolved |
| OI-EXT-003-004 | EXT-003 | 否 | resolved |
| OI-EXT-003-005 | later Evidence/reconciliation | 否 | deferred_for_mvp |
| OI-EXT-004-001 | EXT-004 | 否（Round 2 `resolved_by_plan`） | resolved_by_plan |
| OI-EXT-004-002 | EXT-004 | 否（Round 2 `resolved_by_plan`） | resolved_by_plan |
| OI-EXT-004-003 | EXT-004 | 否 | open |
| OI-EXT-004-004 | EXT-004 | 否 | open |
