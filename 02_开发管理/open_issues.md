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
status: open
```

**问题描述：** 规格在容量背压路径要求运行压缩协调；“一次”与 `max_compression_rounds_per_request` 的关系未写死，影响 STM-009 实现与测试断言。

**禁止行为：** 不得在未解决前自行定为新 Contract。

**决议记录：** （空）

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
status: open
```

**问题描述：** 锁被占用导致无法压缩时，容量路径的最终 HTTP/错误语义需要与规格失败矩阵对齐，正文未单独展开该交叉场景。

**禁止行为：** 不得在未解决前自行定为新 Contract。

**决议记录：** （空）

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
status: open
```

**问题描述：** Session Close 在 Redis 删除未确认等情况下返回 `close_incomplete`；§1 未完整映射到 §3.23 的 HTTP 状态表。

**禁止行为：** 不得在未解决前自行定为新 Contract。

**决议记录：** （空）

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
status: open
```

**问题描述：** Mongo Archive 消息 schema 未包含 `estimated_tokens`，但归档选择与 Close 切分依赖 token 边界。

**禁止行为：** 不得在未解决前自行定为新 Contract。

**决议记录：** （空）

---

## OI-005

```yaml
id: OI-005
spec_sections:
  - "§1.2.4"
impact: "文档中的 Context Archive Service 命名与进程内 Archive 逻辑是否仅为称谓"
blocks_current_task: false
resolve_by_task: STM-006
status: open
```

**问题描述：** 事件生产者描述出现 “Memory API / Context Archive Service” 表述，而工程上 Compression/Archive 协调在 `memory-api` 进程内；需确认无额外独立服务 Contract。

**禁止行为：** 不得在未解决前自行拆分未规定的网络服务。

**决议记录：** （空）

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
status: open
```

**问题描述：** 读路径触摸 `updated_time` 已写明；与“不做 idle session 清理”同时存在，实现时不得引申出未规定的 TTL/自动关闭行为。

**禁止行为：** 不得在未解决前增加 Redis TTL 或自动 Close。

**决议记录：** （空）

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

## 索引

| 问题 ID | 最迟解决任务 | 是否阻塞当前任务 | 状态 |
|---|---|---|---|
| OI-001 | STM-009 | 否 | open |
| OI-002 | STM-009 | 否 | open |
| OI-003 | STM-010 | 否 | open |
| OI-004 | STM-005 / STM-010 | 否 | open |
| OI-005 | STM-006 | 否 | open |
| OI-006 | EXT-008 前需规格确认 | 否 | open |
| OI-007 | STM-011 | 否 | open |
| OI-008 | RET-005 | 否 | open |
| OI-009 | STM-004 | 否 | open |
| OI-010 | 已人工决议（uv_build） | 否 | resolved |
| OI-011 | OI-011 | 否 | resolved |
