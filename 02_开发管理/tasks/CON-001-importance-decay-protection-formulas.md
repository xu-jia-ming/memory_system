# CON-001 Importance/衰减/保护公式纯函数

## 1. 任务信息

```yaml
task_id: CON-001
task_name: Importance/衰减/保护公式纯函数
status: committed
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "2159ad6cc5e3f31365677671d9588c69b776e8a0"
branch: "feat/CON-001-importance-decay-protection-formulas"
created_at: "2026-08-13 08:57 UTC"
updated_at: "2026-08-13 10:02 UTC"
implementation_commit: 41932b93431e43fa1d134cfed76dfedb9ec7f363
implementation_commit_message: "feat(con): add consolidation importance pure functions"
pr: "#50"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/50"
pr_state: OPEN
pr_base: main
pr_head: "feat/CON-001-importance-decay-protection-formulas"
status_record_committed: bef3ae23e8b12592cbdfcfb563654fb91c97cea2
code_review: CODE_REVIEW_APPROVED
p0: 0
p1: 0
next_action: WAITING_FOR_PR_MERGE
spec_sections:
  - "§2.3.2 MVP 范围与基本规则（规则 3、6、7、10 — 本任务仅引用与公式相关的只读语义）"
  - "§2.3.3 Memory 字段补充（importance / last_consolidated_time 语义引用；本任务不写入）"
  - "§2.3.5 巩固信号计算（本任务唯一权威公式范围 — 信号分量）"
  - "§2.3.6 时间衰减设计（recency_score / half_life）"
  - "§2.3.7 动态重要性计算（reinforcement / raw / new_importance）"
  - "§2.3.8 强化与软遗忘规则（文档引用；本任务不实现额外状态机或删除逻辑）"
  - "§2.3.12 memory_consolidation 配置默认值（只读消费 MemoryConsolidationSettings；不修改 Settings Contract）"
prerequisites:
  formal:
    - "EXT-004 — SATISFIED/completed（Neo4j Entity 模型与对齐基础；CON-001 不读 Neo4j，仅登记 master_plan 前置）"
    - "EXT-001..009 — SATISFIED/completed"
    - "RET-001..006 — SATISFIED/completed（v0.4.0-memory-retrieval closed）"
  implementation_reuse:
    - "MemoryConsolidationSettings（settings/models.py）— 全部公式常量已存在"
    - "validate_memory_consolidation（settings/validators.py）— 启动时已校验权重/半衰期/边界"
    - "IMPORTANCE_BY_TYPE（reconciliation_plan_builder.py）— 与 §2.3.5 base_importance / §2.1.12 初始值同表；只读 import，禁止修改 EXT-005 文件"
    - "act_r_scoring.py 纯函数模块模式 — 新建 consolidation_importance.py 同级纯函数"
  baseline_evidence:
    branch: "main"
    head: "2159ad6cc5e3f31365677671d9588c69b776e8a0"
    working_tree_at_planning_start: "clean"
    verification: "git branch --show-current=main; git status --short empty; git rev-parse HEAD=2159ad6cc5e3f31365677671d9588c69b776e8a0"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: PLAN_APPROVED
  amendment_recorded: false
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create exact feature branch feat/CON-001-importance-decay-protection-formulas"
  IMPLEMENTATION_RELEASE: "only after implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
dependency_changes_expected: NONE
migration_changes_expected: NONE
durable_read_scope: NONE
durable_write_scope: NONE
```

### 1.1 本轮门禁与停止条件

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现、测试实现、Migration、配置或依赖"
  - "进入 Developer、Code Reviewer、Commit Recorder 或 Release Operator"
  - "执行任何 Git 写命令"
  - "修改权威规格正文"
  - "触碰 DEV-006 / PR #13"
  - "修改 EXT/RET 已完成阶段生产语义"
  - "接线 consolidation_worker / APScheduler / Neo4j 读写"
stop_if:
  - "任何实现步骤需要 Neo4j 查询、批量分页、乐观锁写入或 ES 同步"
  - "任何实现步骤需要 durable 读/写"
  - "任何实现步骤需要新依赖、Migration 或 Settings Contract 变更"
  - "任何实现步骤需要把 retrieval_count / last_retrieved_time 纳入公式"
blocking_open_issues: []
nonblocking_open_issues: []
```

## 2. authoritative_scope

本任务 **仅** 拥有 §2.3.5–§2.3.7 巩固重要性公式的 **纯函数** 实现与单元测试；**不** 拥有 Neo4j 扫描、Evidence 计数查询、批量更新、调度、Worker 接线或 HTTP API。

| 维度 | 归属 CON-001 | 非 CON-001（显式排除） |
|---|---|---|
| `base_importance` 按 `memory_type` 查表 | **是** — §2.3.5 #1 | — |
| `confidence_score` clamp | **是** — §2.3.5 #2 | — |
| `evidence_score`（`independent_archive_count` 入参） | **是** — §2.3.5 #3 | Neo4j Evidence 计数查询 — **CON-002** |
| `reference_time` / `inactive_days` / `recency_score` | **是** — §2.3.5 #4 + §2.3.6 | ACT-R `recency_score`（`last_retrieved_time`）— **RET-004** |
| `reinforcement_score` / `raw_importance` / `new_importance` | **是** — §2.3.7 | — |
| `conflicted` 最低值保护 / `superseded` 更短半衰期 | **是** — §2.3.6–7 | 状态机变更 / 物理删除 — **非 MVP** |
| `independent_archive_count=0` → `missing_evidence` 跳过 | **是** — 纯函数 outcome | 指标/日志落盘 — **CON-004** |
| 相同输入 + `evaluation_time` 确定性 | **是** | — |
| 不使用旧 `importance` | **是** — 输入契约禁止 | — |
| §2.3.8 软遗忘 **业务行为**（降权外副作用） | **否** — 仅文档对齐 | ES 删文档 / 改 status — **阶段非目标** |
| `last_consolidated_time` / `memory_version` 读写 | **否** | **CON-003** |
| Cursor 分页批量读 | **否** | **CON-002** |
| APScheduler / 互斥锁 / 恢复 | **否** | **CON-004** |
| Consolidation E2E | **否** | **CON-005** |
| `consolidation_worker` 接线 | **否** | **CON-004**；当前 stub 禁止修改 |
| ES importance 同步 | **否** | **阶段非目标** |
| 独立 Consolidation HTTP API | **否** | **阶段非目标** |

## 3. input_contract

### 3.1 单条 Memory 纯函数入参

下游（CON-002 批量读）在调用前组装；本任务 **不** 访问数据库。

```text
ConsolidationImportanceInput {
  memory_type: Literal["profile", "fact", "preference", "event"]
  confidence: float
  status: Literal["active", "conflicted", "superseded"]
  created_time: int                          # Unix epoch 秒；非负
  latest_source_time: int | None             # 用户来源证据时间；null 见 LD-3
  independent_archive_count: int             # ≥0；来自 CON-002 Neo4j 查询；本任务只消费数值
  evaluation_time: int                       # 本轮统一评估时间；非负；注入式
}
```

**显式禁止出现在输入或公式中的字段**（§2.3.2 规则 6、§2.3.7 规则 7）：

- `importance`（旧值）
- `retrieval_count`
- `last_retrieved_time`
- `user_id`（纯函数层不读取；用户隔离由调用方按 Memory 独立调用保证 — 见 §11）

### 3.2 字段校验（纯函数边界）

| 字段 | 校验 | 失败动作 |
|---|---|---|
| `memory_type` | 四枚举之一 | `ValueError` |
| `status` | `active` / `conflicted` / `superseded` | `ValueError` |
| `created_time` | `>= 0` | `ValueError` |
| `evaluation_time` | `>= 0` | `ValueError` |
| `independent_archive_count` | `>= 0` | `ValueError`；`== 0` → **skip**（非 ValueError） |
| `confidence` | 任意 float | defensive clamp 到 `[0,1]`（LD-4） |

### 3.3 Settings 入参

```text
settings: MemoryConsolidationSettings   # 来自 get_settings().memory_consolidation；禁止本任务修改 models/validators
```

消费字段（与 §2.3.12 / `MemoryConsolidationSettings` 默认一致）：

| 字段 | 默认 | 用途 |
|---|---|---|
| `evidence_saturation_count` | 5 | evidence_score 饱和 |
| `profile_half_life_days` | 365 | recency 半衰期 |
| `fact_half_life_days` | 180 | recency 半衰期 |
| `preference_half_life_days` | 120 | recency 半衰期 |
| `event_half_life_days` | 60 | recency 半衰期 |
| `superseded_half_life_days` | 30 | superseded 更短半衰期 |
| `confidence_weight` | 0.55 | reinforcement |
| `evidence_weight` | 0.45 | reinforcement |
| `reinforcement_bonus_weight` | 0.35 | raw_importance bonus |
| `min_importance` | 0.05 | clamp 下限（非 conflicted） |
| `conflicted_min_importance` | 0.30 | clamp 下限（conflicted） |
| `max_importance` | 1.00 | clamp 上限 |

**禁止**消费：`batch_size`、`schedule_cron`、`enabled` 等调度字段（归属 CON-004）。

### 3.4 `base_importance` 来源

- 查表值与 §2.3.5 / `reconciliation_plan_builder.IMPORTANCE_BY_TYPE` 一致：
  - profile `0.75`；fact `0.70`；preference `0.65`；event `0.55`
- 实现：**只读 import** `IMPORTANCE_BY_TYPE` 或等价局部函数；**禁止**修改 `reconciliation_plan_builder.py`。

## 4. output_contract

### 4.1 Outcome 类型

```text
ConsolidationImportanceOutcome =
  ConsolidationImportanceSuccess | ConsolidationImportanceSkip

ConsolidationImportanceSuccess {
  new_importance: float    # round(clamp(raw, effective_min, max), 4)
}

ConsolidationImportanceSkip {
  reason: Literal["missing_evidence"]   # independent_archive_count == 0
}
```

### 4.2 公式（权威 — 与规格字面一致）

**confidence_score**：

```text
confidence_score = clamp(confidence, 0.0, 1.0)
```

**evidence_score**（仅当 `independent_archive_count > 0`）：

```text
evidence_score = min(
  1.0,
  ln(1 + independent_archive_count) / ln(1 + evidence_saturation_count)
)
```

**reference_time / inactive_days**：

```text
reference_time = max(latest_source_time or 0, created_time)

inactive_days = max(0, (evaluation_time - reference_time) / 86400)
```

若 `reference_time > evaluation_time`（来源时间晚于评估时间）→ `inactive_days = 0`（规格：不产生负衰减）。

**recency_score**：

```text
half_life_days = type_half_life(memory_type, settings)
if status == "superseded":
    half_life_days = min(half_life_days, superseded_half_life_days)

recency_score = 2 ** (-inactive_days / half_life_days)
```

**reinforcement_score**：

```text
reinforcement_score =
    confidence_weight * confidence_score
  + evidence_weight * evidence_score
```

**raw_importance / new_importance**：

```text
raw_importance =
    base_importance * recency_score
  + reinforcement_bonus_weight * reinforcement_score

effective_min_importance =
    conflicted_min_importance  if status == "conflicted"
    else min_importance

new_importance = round(
    clamp(raw_importance, effective_min_importance, max_importance),
    4
)
```

### 4.3 中间分量（可选暴露）

为单元测试与 CON-002 编排可读性，允许在 `ConsolidationImportanceComponents` 中暴露中间值（`base_importance`、`confidence_score`、`evidence_score`、`inactive_days`、`recency_score`、`reinforcement_score`、`raw_importance`）；**不得**作为 durable 字段或 HTTP 字段。

主入口函数：

```text
compute_consolidation_importance(
    input: ConsolidationImportanceInput,
    settings: MemoryConsolidationSettings,
) -> ConsolidationImportanceOutcome
```

可选分解纯函数（与 `act_r_scoring.py` 同级风格）：

| 函数 | 职责 |
|---|---|
| `base_importance_for_type(memory_type) -> float` | §2.3.5 #1 |
| `compute_confidence_score(confidence) -> float` | clamp |
| `compute_evidence_score(count, saturation_count) -> float` | §2.3.5 #3；`count<=0` 禁止调用 |
| `compute_reference_time(latest_source_time, created_time) -> int` | §2.3.5 #4 |
| `compute_inactive_days(reference_time, evaluation_time) -> float` | §2.3.5 #4 |
| `half_life_days_for(memory_type, status, settings) -> int` | §2.3.6 |
| `compute_recency_score(inactive_days, half_life_days) -> float` | §2.3.6 |
| `compute_reinforcement_score(confidence_score, evidence_score, settings) -> float` | §2.3.7 |
| `compute_effective_min_importance(status, settings) -> float` | §2.3.7 |
| `compute_raw_importance(...) -> float` | §2.3.7 |
| `compute_new_importance(raw, status, settings) -> float` | clamp + round(4) |

## 5. failure_mapping

| 条件 | Outcome / 异常 | 是否更新 importance（下游 CON-003） | 规格指标名（CON-004 落盘） |
|---|---|---|---|
| `independent_archive_count == 0` | `Skip(reason="missing_evidence")` | **否** | `missing_evidence` |
| 非法 `memory_type` / `status` / 负时间 | `ValueError` | — | — |
| `independent_archive_count > 0` 且输入合法 | `Success(new_importance=...)` | **是**（由 CON-003 写入） | — |
| Neo4j 读失败 / 版本冲突 | — | — | **CON-002/003** |
| 调度重入 / 锁失败 | — | — | **CON-004** |

**禁止**：在 `missing_evidence` 时返回伪造的 `new_importance`；禁止用旧 `importance` 作为 fallback。

## 6. durable_read_scope / durable_write_scope

```yaml
durable_read_scope: NONE
durable_write_scope: NONE
```

- **零** Mongo / Neo4j / ES / Kafka 读或写。
- **零** `importance` / `last_consolidated_time` / `memory_version` 突变。
- **零** `retrieval_count` / `last_retrieved_time` 读写。

## 7. replay_idempotency

| 场景 | 预期行为 |
|---|---|
| 相同 `ConsolidationImportanceInput` + 相同 `settings` 重复调用 | 完全相同 `ConsolidationImportanceOutcome` |
| 相同 Memory 字段但不同 `evaluation_time` | `inactive_days` / `recency_score` / `new_importance` 可能变化；测试分开断言 |
| 进程重启 / 并发纯函数调用 | 无共享可变状态；结果一致 |
| 巩固任务重跑（CON-004） | 相同 `evaluation_time` + 相同图数据 → 相同 `new_importance`（§2.3.4 规则 6 确定性） |
| `independent_archive_count=0` 重跑 | 始终 `missing_evidence` skip；不累积衰减 |

## 8. user_isolation

| # | 规则 | Enforcement | 测试 ID |
|---|---|---|---|
| UISO-1 | 每条 Memory **独立**计算；纯函数无跨 Memory 聚合 | 函数签名仅单条 input | U8 |
| UISO-2 | 纯函数层 **不** 接收 `user_id`；无用户上下文 | 类型/签名契约 | U8 |
| UISO-3 | 不同 Memory 相同数值输入 → 相同输出（与用户无关） | 单元测试双实例 | U8 |
| UISO-4 | CON-002 批量读须按用户过滤 — **本任务仅文档引用** | CON-002 计划 | — |

## 9. preserve boundaries

| 边界 | 要求 |
|---|---|
| `act_r_scoring.py` / RET-004 | **禁止**修改；巩固 recency 与检索 recency **不得**混用 |
| `reconciliation_plan_builder.py` | **禁止**修改；允许只读 import 常量表 |
| `consolidation_worker.py` | **禁止**修改 stub |
| `settings/models.py` / `validators.py` | **禁止**修改 Contract |
| EXT-001..009 / RET-001..006 生产语义 | **禁止**修改 |
| DEV-006 / PR #13 | **永久禁止** |
| Neo4j / ES / Scheduler | **禁止**在本任务触碰 |

## 10. numerical_correctness_test_cases

以下算例 **必须**作为单元测试精确断言（`final` 类结果允许 `pytest.approx` ±1e-6；`round(,4)` 结果用精确小数）。

默认 `settings` = `get_settings().memory_consolidation`（或测试 fixture 构造默认等价对象）。

### NC-1 — base_importance 查表

| memory_type | base_importance |
|---|---|
| profile | 0.75 |
| fact | 0.70 |
| preference | 0.65 |
| event | 0.55 |

### NC-2 — confidence_score clamp

| confidence | confidence_score |
|---|---|
| -0.2 | 0.0 |
| 0.0 | 0.0 |
| 0.85 | 0.85 |
| 1.0 | 1.0 |
| 1.5 | 1.0 |

### NC-3 — evidence_score 饱和（`evidence_saturation_count=5`）

| independent_archive_count | evidence_score |
|---|---|
| 0 | **不计算** → skip |
| 1 | ln(2)/ln(6) ≈ 0.386853 |
| 5 | 1.0 |
| 10 | 1.0 |

### NC-4 — reference_time / inactive_days

设 `created_time=1_000_000`，`evaluation_time=1_000_000 + 86400`（+1 天）：

| latest_source_time | reference_time | inactive_days |
|---|---|---|
| None | 1_000_000 | 1.0 |
| 2_000_000 | 2_000_000 | 0.0（来源晚于 evaluation） |
| 500_000 | 1_000_000 | 1.0 |

### NC-5 — recency_score 半衰期（fact, active, `half_life=180`）

设 `inactive_days=180` → `recency_score=0.5`；`inactive_days=0` → `1.0`。

### NC-6 — superseded 更短半衰期

`memory_type=event`（type half-life 60），`status=superseded` → 使用 `min(60,30)=30`；`inactive_days=30` → `recency_score=0.5`。

### NC-7 — reinforcement_score（默认权重）

`confidence_score=1.0`，`evidence_score=1.0` → `reinforcement_score=1.0`。

`confidence_score=0.0`，`evidence_score=1.0` → `0.45`。

### NC-8 — 完整合成（active fact，可控分量）

构造：`base=0.70`，`recency_score=1.0`，`reinforcement_score=1.0`，`reinforcement_bonus_weight=0.35`：

```text
raw_importance = 0.70 * 1.0 + 0.35 * 1.0 = 1.05
new_importance = round(clamp(1.05, 0.05, 1.0), 4) = 1.0
```

### NC-9 — conflicted 最低值保护

`status=conflicted`，构造 `raw_importance=0.10` → `new_importance=0.30`（`conflicted_min_importance`）。

### NC-10 — 非 conflicted 最低值

`status=active`，`raw_importance=0.01` → `new_importance=0.05`。

### NC-11 — round 4 位小数

`raw_importance=0.712345678`（active，在 clamp 内）→ `new_importance=0.7123` 或 `0.7124`（按 Python `round(x, 4)` 精确断言）。

### NC-12 — missing_evidence

`independent_archive_count=0` → `Skip(missing_evidence)`；**不**调用 evidence_score。

### NC-13 — 确定性重放

同一 input 调用 `compute_consolidation_importance` 两次 → 深度相等 outcome。

### NC-14 — 旧 importance 不在契约

`ConsolidationImportanceInput` 类型 **无** `importance` 字段；静态/契约测试确认。

## 11. minimum_test_plan

### 11.1 Unit Test

| ID | 场景 | 预期 |
|---|---|---|
| U1 | NC-1..NC-14 | 精确数值 / skip / 确定性 |
| U2 | 四 `memory_type` × `active` 最低衰减路径 | 单调性：更长 `inactive_days` → 不增 `new_importance`（固定其他输入） |
| U3 | `status=superseded` vs `active` 同输入 | superseded `new_importance` ≤ active（典型长期 inactive） |
| U4 | 非法 `memory_type` | `ValueError` |
| U5 | 非法 `status` | `ValueError` |
| U6 | 负 `created_time` / `evaluation_time` | `ValueError` |
| U7 | injectable `evaluation_time` | 无 wall-clock 依赖 |
| U8 | 两 Memory 独立 input 同参 → 同 outcome | UISO-1..3 |
| U9 | `half_life_days<=0` defensive（不应由 validator 产生） | `recency_score=0.0`（LD-5） |

### 11.2 Contract Test

| ID | 场景 | 预期 |
|---|---|---|
| C1 | 白名单外无 `src/**` 生产变更 | git diff 门禁 |
| C2 | `ConsolidationImportanceInput` 无 `importance`/`retrieval_count`/`last_retrieved_time` | 类型/字段断言 |
| C3 | 不修改 `act_r_scoring.py`、`reconciliation_plan_builder.py`、`consolidation_worker.py`、`settings/` | diff 断言 |

### 11.3 Integration Test

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — Neo4j 读与 Evidence 计数归属 **CON-002** |

### 11.4 E2E Test

| 场景 | 预期 |
|---|---|
| 无 | **DEFERRED** — **CON-005** |

### 11.5 失败注入与并发

| ID | 场景 | 预期 |
|---|---|---|
| F1 | `independent_archive_count=0` | `missing_evidence` skip（边缘失败语义） |
| F2 | 并发 100 路相同纯函数调用 | 无异常；结果一致 |
| F3 | 极大 `inactive_days` | `recency_score` 趋近 0；`new_importance` 仍 ≥ effective_min |

## 12. production_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/consolidation_importance.py` | 创建 | `ConsolidationImportanceInput` / Outcome / Components |
| `src/memory_system/domain/services/consolidation_importance.py` | 创建 | §2.3.5–2.3.7 纯函数 + `compute_consolidation_importance` |

**白名单外任何 `src/**` 生产代码变更 → FAIL**（含 `reconciliation_plan_builder.py`、`act_r_scoring.py`、`consolidation_worker.py`、`settings/`、EXT/RET 已完成文件、DEV-006）。

## 13. test_file_whitelist

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `tests/unit/test_consolidation_importance.py` | 创建 | NC-1..NC-14 + U1..U9 + F1..F3 |
| `tests/contract/test_con001_scope_boundaries.py` | 创建 | C1..C3 白名单与输入契约 |

**白名单外任何 `tests/**` 变更 → FAIL**（运行 EXT/RET 回归但不在白名单内编辑）。

### 13.1 governance_file_whitelist（Release Operator 各 phase）

| Phase | 允许路径 | 目的 |
|---|---|---|
| `PLAN_LANDING` | `02_开发管理/tasks/CON-001-importance-decay-protection-formulas.md` | 已批准 Task Plan |
| `PLAN_LANDING` | `02_开发管理/progress.md` | 规划态登记 |
| `PLAN_LANDING` | `02_开发管理/master_plan.md` | CON-001 规划登记 |
| `IMPLEMENTATION_RELEASE` | §12 production_file_whitelist 全部 | 实现 |
| `IMPLEMENTATION_RELEASE` | §13 test_file_whitelist 全部 | 测试 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/tasks/CON-001-importance-decay-protection-formulas.md` | 执行记录 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/progress.md` | 状态登记 |
| `IMPLEMENTATION_RELEASE` | `02_开发管理/master_plan.md` | 状态备注 |
| `POST_MERGE_CLEANUP` | 上述三份治理文件 | 完成登记 |

**永久禁止**（所有 phase）：DEV-006、PR #13；规格正文；EXT/RET 已完成生产语义。

### 13.2 PLAN_LANDING commit contract

`PLAN_LANDING` 的 `docs(plan)` commit **必须**同时包含且仅包含：

1. `02_开发管理/tasks/CON-001-importance-decay-protection-formulas.md`
2. `02_开发管理/progress.md`
3. `02_开发管理/master_plan.md`

Commit message（精确）：

```text
docs(plan): add CON-001 importance decay protection formulas plan
```

随后从更新后的 `main` 创建 exact feature branch `feat/CON-001-importance-decay-protection-formulas`。

## 14. NORMAL classification（HARD_BLOCK / SAFE_AUTO / MVP_LOCAL / DEFERRED）

| ID | 项 | 分类 | 说明 |
|---|---|---|---|
| CL-1 | 公式与 §2.3.5–2.3.7 不一致 | **HARD_BLOCK** | 规格唯一权威 |
| CL-2 | 使用旧 `importance` 或 `retrieval_count`/`last_retrieved_time` | **HARD_BLOCK** | §2.3.7 规则 6–7 |
| CL-3 | `missing_evidence` 时返回数值 importance | **HARD_BLOCK** | §2.3.5 #3 |
| CL-4 | 修改 Settings Contract / validators | **HARD_BLOCK** | dependency_changes_expected=NONE |
| CL-5 | Neo4j/ES/Worker/Scheduler 接线 | **HARD_BLOCK** | CON-002..004 |
| CL-6 | 与 `act_r_scoring` 合并或改写 RET-004 | **HARD_BLOCK** | 独立巩固 recency |
| CL-7 | DEV-006 / PR #13 | **HARD_BLOCK** | 治理永久禁止 |
| CL-8 | `latest_source_time null → 0` in reference_time | **MVP_LOCAL_DECISION** | LD-3；与规格 `or 0` 一致 |
| CL-9 | 非法枚举 `ValueError` | **MVP_LOCAL_DECISION** | LD-1 |
| CL-10 | injectable `evaluation_time` | **SAFE_AUTO_REMEDIATION** | LD-2；测试确定性 |
| CL-11 | defensive confidence clamp | **SAFE_AUTO_REMEDIATION** | LD-4 |
| CL-12 | 拆分 `models/` + `services/` 两文件 | **SAFE_AUTO_REMEDIATION** | 与 RET-004 结构一致 |
| CL-13 | `half_life_days<=0` → `recency_score=0` | **SAFE_AUTO_REMEDIATION** | LD-5 |
| CL-14 | 只读 import `IMPORTANCE_BY_TYPE` | **SAFE_AUTO_REMEDIATION** | 避免重复常量表 |
| CL-15 | §2.3.8 软遗忘文档行为（删 ES/改 status） | **DEFERRED** | 本任务仅公式；§2.3.8 文档对齐 |
| CL-16 | Neo4j Evidence 计数 | **DEFERRED** | CON-002 |
| CL-17 | 乐观锁批量写 `importance` | **DEFERRED** | CON-003 |
| CL-18 | APScheduler / mutex / recovery | **DEFERRED** | CON-004 |
| CL-19 | Consolidation Integration/E2E | **DEFERRED** | CON-005 |
| CL-20 | Integration Neo4j Fixture | **DEFERRED** | CON-002+ |
| CL-21 | 共享 `base_importance` 模块重构 EXT-005 | **DEFERRED** | 禁止本任务重构 EXT |

## 15. deferred_for_mvp（本任务显式不交付）

- CON-002：Cursor 分页、Neo4j 批量读、`independent_archive_count` 查询
- CON-003：乐观锁批量更新 `importance` / `last_consolidated_time`
- CON-004：APScheduler、本地互斥锁、失败恢复、`missing_evidence` 指标落盘
- CON-005：Consolidation Integration + E2E
- §2.3.8 所列软遗忘 **副作用**（改 status、删 ES、清 content）— 仅通过公式降权体现
- ES importance 同步；独立 Consolidation HTTP API；多实例调度（Phase 4 阶段非目标）
- `consolidation_worker` 启动与调度接线
- 将 `IMPORTANCE_BY_TYPE` 提取为共享模块并修改 EXT-005

## 16. mvp_local_decisions

| ID | 决策 | 理由 |
|---|---|---|
| LD-1 | 非法 `memory_type` / `status` / 负时间戳 → `ValueError` | 纯函数层 fail-fast；Neo4j 脏数据由 CON-002 过滤 |
| LD-2 | `evaluation_time` 由调用方注入，单元测试禁止 wall-clock | 与 RET-004 `current_time` 注入一致 |
| LD-3 | `latest_source_time is None` → `reference_time` 使用 `max(0, created_time)` | 规格 `latest_source_time or 0` |
| LD-4 | `confidence` defensive clamp 到 `[0,1]` 再计分 | 与 ACT-R 分量 clamp 一致 |
| LD-5 | `half_life_days <= 0` → `recency_score = 0.0` | validator 已保证正数；防御 Neo4j 脏数据 |
| LD-6 | 只读 import `reconciliation_plan_builder.IMPORTANCE_BY_TYPE` | 与 §2.1.12/§2.3.5 同表；不修改 EXT-005 |

## 17. open_issues

- `02_开发管理/open_issues.md`：**无** blocking CON-001 的 open issue。
- `blocking_open_issues: []`；`nonblocking_open_issues: []`。

## 18. 任务目标

交付 §2.3.5–§2.3.7 巩固重要性计算的 **确定性纯函数** 模块：消费单条 Memory 字段 + `independent_archive_count` + 统一 `evaluation_time`，输出 `new_importance` 或 `missing_evidence` skip；**零** durable 读写；为 CON-002 批量读与 CON-003 写入提供唯一公式实现。

可验证目标：

1. **`consolidation_importance.py`** 纯函数覆盖全公式与 NC 算例。
2. **`ConsolidationImportanceInput`** 契约 **不含** 旧 `importance` / 检索统计字段。
3. **`missing_evidence`** skip 与成功路径单元测试分离。
4. Contract：白名单 + 输入字段边界（C1..C3）。
5. Ruff / Mypy 通过；Review 无 P0/P1。

## 19. 非目标与黑名单（must_not）

- Neo4j 读/写、Evidence 查询、Cursor 分页 — **CON-002**。
- `importance` / `last_consolidated_time` / `memory_version` 更新 — **CON-003**。
- APScheduler / 互斥锁 / Worker main — **CON-004**；**禁止**修改 `consolidation_worker.py`。
- Consolidation E2E — **CON-005**。
- ES importance 同步；HTTP API；Dashboard。
- 修改 `act_r_scoring.py`、RET-004 检索 recency 语义。
- 修改 `reconciliation_plan_builder.py` 或抽取共享常量（本任务仅 import）。
- 修改 `MemoryConsolidationSettings` / validators / 默认配置 YAML。
- DEV-006 / PR #13 — **永久禁止**。

## 20. 当前代码状态

- **已存在**：`MemoryConsolidationSettings` 含全部公式默认；`validate_memory_consolidation` 已校验权重与半衰期；`IMPORTANCE_BY_TYPE` 与 base_importance 表一致；`act_r_scoring.py` 提供纯函数模式参考；`consolidation_worker.py` 为 refusal-only stub。
- **可复用**：只读 import `IMPORTANCE_BY_TYPE`；`get_settings().memory_consolidation`。
- **当前缺失**：`consolidation_importance` 模型与服务纯函数；对应单元/契约测试。
- **与技术规格不一致之处**：无（规划基线 clean）；巩固公式尚未实现。
- **前置任务检查**：EXT-004 completed；EXT-001..009 completed；RET-001..006 completed；v0.3.0 / v0.4.0 milestones closed。

## 21. 实现方案

### Step 1 — 领域模型

- **文件**：`src/memory_system/domain/models/consolidation_importance.py`
- **类**：`ConsolidationImportanceInput`；`ConsolidationImportanceSuccess`；`ConsolidationImportanceSkip`；`ConsolidationImportanceOutcome`（Union 或 tagged）；可选 `ConsolidationImportanceComponents`
- **输入**：§3.1 字段
- **输出**：§4.1 Outcome 类型
- **错误处理**：构造时由 Pydantic **不**使用（frozen dataclass）；校验在 service 纯函数
- **幂等/并发**：frozen dataclass；无状态

### Step 2 — 纯函数模块

- **文件**：`src/memory_system/domain/services/consolidation_importance.py`
- **函数**：§4.3 分解函数 + `compute_consolidation_importance`
- **输入**：`ConsolidationImportanceInput` + `MemoryConsolidationSettings`
- **输出**：`ConsolidationImportanceOutcome`
- **错误处理**：§5 failure_mapping
- **幂等**：确定性纯函数；`count=0` → skip 非异常

### Step 3 — 单元与契约测试

- **文件**：§13 test_file_whitelist
- **覆盖**：§10 NC + §11 minimum_test_plan
- **错误处理**：F1..F3
- **幂等**：NC-13 + F2

## 22. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/models/consolidation_importance.py` | 创建 | 输入/输出契约 |
| `src/memory_system/domain/services/consolidation_importance.py` | 创建 | 公式纯函数 |
| `tests/unit/test_consolidation_importance.py` | 创建 | 单元测试 |
| `tests/contract/test_con001_scope_boundaries.py` | 创建 | 白名单/契约 |

## 23. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | 不适用 | 纯函数；无事务 |
| 幂等 | 适用 | 相同输入 → 相同输出；见 §7 |
| 并发 | 适用 | 无共享可变状态；F2 并发测试 |
| 版本冲突 | 不适用 | 无 `memory_version` 读写（CON-003） |
| 用户隔离 | 适用 | 单 Memory 独立计算；见 §8 |
| 部分失败 | 不适用 | 无批量；单条 skip 由 outcome 表达 |
| 进程异常恢复 | 不适用 | 无持久化状态 |

## 24. 测试计划（模板 §8 映射）

### Unit Test — 见 §11.1

### Contract Test — 见 §11.2

### Integration Test — **DEFERRED**（§11.3）

### E2E Test — **DEFERRED**（§11.4）

### 失败注入与并发 — 见 §11.5

## 25. 验收标准

- [ ] `pytest tests/unit/test_consolidation_importance.py tests/contract/test_con001_scope_boundaries.py` 全部通过
- [ ] NC-1..NC-14 精确断言通过
- [ ] `missing_evidence` skip 与 `ValueError` 路径分离断言
- [ ] `ConsolidationImportanceInput` 无 `importance` / `retrieval_count` / `last_retrieved_time`
- [ ] 白名单外零 `src/**` 生产 diff
- [ ] Ruff 通过
- [ ] Mypy 通过（新增文件）
- [ ] Review 无 P0/P1

## 26. 风险与阻塞项

- **设计文档冲突**：无；公式与 §2.3.5–2.3.7 字面一致。
- **当前代码冲突**：无；`IMPORTANCE_BY_TYPE` 与规格 base_importance 一致。
- **前置任务**：EXT-004 completed；登记满足 master_plan。
- **未批准依赖**：`dependency_changes_expected=NONE`。
- **API/Schema 变化**：无 HTTP；仅内部 dataclass。
- **其他风险**：与 `act_r_scoring` 公式混淆 — 通过独立模块名与测试 NC 隔离。

## 27. Git 计划

```yaml
branch: "feat/CON-001-importance-decay-protection-formulas"
expected_commits:
  - "docs(plan): add CON-001 importance decay protection formulas plan"
  - "feat(con): add consolidation importance pure functions"
out_of_scope_changes:
  - "DEV-006 / PR #13"
  - "consolidation_worker.py"
  - "act_r_scoring.py / retrieval 模块"
  - "reconciliation_plan_builder.py 修改"
  - "settings/models.py / validators.py"
  - "Neo4j / ES / Scheduler 任何接线"
  - "CON-002..005 范围"
```

## 28. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

## 29. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-13 10:02 UTC | IMPLEMENTATION_RELEASE | implementation `41932b93431e43fa1d134cfed76dfedb9ec7f363`; PR #50 OPEN; docs(status): record on feat | 49 passed; ruff PASS; mypy PASS | CODE_REVIEW_APPROVED P0=0 P1=0; feat push only; 不得自动 merge; 不得触碰 DEV-006/PR#13 |
| 2026-08-13 10:00 UTC | implementation | 创建 consolidation_importance 模型/服务 + 单元/契约测试 | 49 passed; ruff PASS; mypy PASS | NC-1..NC-14 + U1..U9 + F1..F3 + C1..C3; SHOULD_FIX SF-1..SF-3 absorbed; zero durable I/O |
| 2026-08-13 09:40 UTC | planning | Human PLAN_APPROVED; Release Operator PLAN_LANDING | N/A | baseline `2159ad6` verified |
| 2026-08-13 08:57 UTC | planning | 创建 Task Plan；同步 progress/master_plan | N/A（规划-only） | baseline `2159ad6` verified；`approval_posture=AWAIT_PLAN_REVIEW`；Developer NOT authorized |

## 30. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/domain/models/consolidation_importance.py` | 创建 — Input/Outcome/Components frozen dataclasses |
| `src/memory_system/domain/services/consolidation_importance.py` | 创建 — §2.3.5–2.3.7 纯函数 + `compute_consolidation_importance` |
| `tests/unit/test_consolidation_importance.py` | 创建 — NC-1..NC-14 + U1..U9 + F1..F3 + SF-1..SF-3 |
| `tests/contract/test_con001_scope_boundaries.py` | 创建 — C1..C3 白名单与输入契约 |

### 与原计划的差异

无。SHOULD_FIX SF-1..SF-3 已吸收（4 位小数边界、负 count ValueError、§2.3.8 文档说明）。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit + Contract | `uv run pytest tests/unit/test_consolidation_importance.py tests/contract/test_con001_scope_boundaries.py -q` | 49 passed |
| Ruff | `uv run ruff check`（4 新文件） | PASS |
| Mypy | `uv run mypy`（2 生产文件） | PASS |
| Integration | — | DEFERRED |
| E2E | — | DEFERRED |

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
branch: "feat/CON-001-importance-decay-protection-formulas"
plan_commit: "6f4a35ad28ad90946f74e39bfa567acc71120b12"
implementation_commit: 41932b93431e43fa1d134cfed76dfedb9ec7f363
implementation_commit_message: "feat(con): add consolidation importance pure functions"
```

### 最终状态

`committed`
