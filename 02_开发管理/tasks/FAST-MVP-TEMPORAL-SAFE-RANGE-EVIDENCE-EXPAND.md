# FAST-MVP-TEMPORAL-SAFE-RANGE-EVIDENCE-EXPAND

## 1. 任务信息

```yaml
task_id: FAST-MVP-TEMPORAL-SAFE-RANGE-EVIDENCE-EXPAND
task_name: Temporal SAFE_RANGE + NO_INFO Evidence Expand (retry once)
status: completed
spec_sections:
  - "§2.2 记忆检索 (source_message_ids / evidence_count)"
  - "LoCoMo eval adapter (scripts/locomo_eval, 非规格 Contract 变更)"
prerequisites:
  - "conv-30 冻结评测栈可运行 (evaluate.py / full_locomo_final_eval.py)"
  - "Mongo context_archive 可通过 SourceMessageIndex 加载"
branch: "feat/fast-mvp-temporal-safe-range-evidence-expand"
created_at: "2026-08-23 11:35 UTC"
updated_at: "2026-08-23 04:42 UTC"
next_action: "FAST-MVP completed — NO AUTO-START"
```

## 2. 任务目标

在 **不修改 memory schema、不引入 Agent loop、不大改架构** 的前提下，于 LoCoMo 答题链路完成：

1. **A. Temporal SAFE_RANGE**：对 `next/last/this month|week` 做确定性日期**范围**解析，并注入 Supporting evidence。
2. **B. NO_INFO Evidence Expand**：首次正常答题后，若回答为 `No information available` 且存在可展开的 `source_message_ids`，补充原文 evidence 后 **retry 一次**。

## 3. 非目标

- LLM 自主 tool call / 多轮 Agent
- planned/completed event ontology
- temporal reranking
- 默认展开整个 session
- Memory API 新增 archive 读取 endpoint（本轮）
- 修改 Neo4j / ES / memory schema
- 将 `scripts/locomo_eval/` 模块迁入 `src/`（可记为后续）
- Answer Contract v2 / prompt 大改（除非 expand retry 需一行说明「已补充 evidence」）

## 4. Current State（代码审计）

### 4.1 已有能力

| 组件 | 位置 | 说明 |
|------|------|------|
| Temporal resolver | `scripts/locomo_eval/deterministic_temporal_resolver.py` | SAFE 点日期：today/yesterday/tomorrow/N days |
| Prompt 注入 | `memory_evidence_context._format_supporting_evidence()` | `enable_deterministic_temporal_resolver=True` 时调用 `resolve_temporal_expression()` |
| Memory 格式化 | `memory_evidence_context.format_memories()` | Top-N evidence 选择 + Supporting evidence 块 |
| Source 原文索引 | `SourceMessageIndex.from_mongo()` / `from_docker_mongosh()` | 从 `context_archive.messages[]` 按 `message_id` 查找 |
| Retrieval API | `src/.../memory_retrieval.py` | 返回 `source_message_ids`（最多 `max_source_message_ids=20`） |
| QA 主链路 | `scripts/locomo_eval/evaluate.py::evaluate_questions()` | retrieve → format_memories → LLM answer → judge |
| Full eval | `scripts/locomo_eval/full_locomo_final_eval.py` | 冻结 `top_k=10`, `max_evidence=1`, resolver enabled |
| NO_INFO 短语 | `scripts/locomo_eval/prompts.py` | 精确短语 `"No information available"` |
| Grounding | `ANSWER_SYSTEM_PROMPT` (= grounding only) | 已要求检查 Supporting Evidence |
| Unit tests | `tests/unit/test_deterministic_temporal_resolver.py` | 覆盖 SAFE 点日期 + `last week → AMBIGUOUS`（将更新） |

### 4.2 调用链（真实路径）

```
evaluate.py / full_locomo_final_eval.py
  → adapter.retrieve(top_k=10)          # HTTP → memory-api
  → format_memories(
        retrieval,
        source_index,                   # Mongo context_archive
        max_evidence_per_memory=1,      # frozen
        enable_deterministic_temporal_resolver=True,
     )
  → _format_supporting_evidence()
       → resolve_temporal_expression(evidence_text, record.timestamp)
       → resolution.to_metadata_lines()  # 仅 SAFE 点日期写入 prompt
  → llm.complete(ANSWER_SYSTEM_PROMPT, memories_text)
  → (无 retry)
```

### 4.3 `next month / last week` 为何不解析

`deterministic_temporal_resolver.py` 中：

1. `_UNSUPPORTED_PERIOD_RE` **显式包含** `next/last/this month|week|year`
2. `_is_safe_expression()` 对匹配 `_UNSUPPORTED_PERIOD_RE` 的表达式返回 **False**
3. `resolve_temporal_expression()` 因此返回 `status=AMBIGUOUS`, `reason="expression not in SAFE rule set"`
4. `to_metadata_lines()` 对非 SAFE 返回 `[]` → **prompt 中无任何解析结果**

测试 `test_last_week_not_resolved` 当前断言 AMBIGUOUS，实现后需改为 SAFE_RANGE。

### 4.4 Resolver 输出如何进入 prompt

```text
- Date: 2023-01-20
  Speaker: Jon
  Text: ... next month ...
  Resolved event date: 2023-01-21        # 仅 SAFE 点日期；范围尚未支持
  Temporal basis: "yesterday" relative to evidence date 2023-01-20
```

由 `TemporalResolution.to_metadata_lines()` 生成，在 `_format_supporting_evidence()` 中 append 到每条 evidence 块。

### 4.5 `source_message_ids` 能否恢复原文

**可以（评测路径）**：

- Retrieval 响应含 `source_message_ids`（`retrieval_response_mapper.py`）
- `SourceMessageIndex.get(message_id)` 从 `context_archive.messages` 取 `content` + `timestamp`
- `build_evidence_candidates()` / `_format_supporting_evidence()` 已使用该索引

**限制**：

- 生产 `memory-api` **无**按 `message_id` 读 archive 的 HTTP API；Agent 侧需自接 Mongo 或未来 endpoint
- 若 `source_index=None`（未传 `--mongo-uri`），`format_memories` 退化为仅 `[type] content`，**无 expand 能力**

### 4.6 Production vs Evaluation 差异

| 维度 | Production (`src/`) | Evaluation (`scripts/locomo_eval/`) |
|------|---------------------|-------------------------------------|
| 答题 LLM | ❌ 无 | ✅ evaluate / ablation scripts |
| Temporal resolver | ❌ 不在 src | ✅ answer-time only |
| Evidence enrich | ❌ | ✅ SourceMessageIndex |
| NO_INFO retry | ❌ | ❌（本轮新增） |

**结论**：本轮 MVP **仅落在 LoCoMo eval 答题链路**；不阻塞，但需在 Task Plan 注明 production 尚未等价。

### 4.7 NO_INFO retry 最佳插入点

**推荐**：在 `evaluate_questions()` 与 `full_locomo_final_eval.evaluate_with_context_capture()` 的 **首次 `llm.complete` 之后、judge 之前**。

抽取共享函数（建议新文件，避免双份逻辑）：

```text
scripts/locomo_eval/answer_pipeline.py
  is_no_info(answer) -> bool
  answer_with_optional_evidence_expand(...) -> AnswerOutcome
```

`AnswerOutcome` 字段：`generated`, `retry_attempted`, `expand_applied`, `expanded_message_ids`, `memories_text_initial`, `memories_text_final`。

### 4.8 审计重要发现（影响预期收益）

`rank1_m2_evidence_sufficiency_audit_conv30.json`：

- conv-30 的 M2 错题中，**24/24 金标 memory 仅 1 个 `source_message_id`**
- 冻结配置 `max_evidence_per_memory=1` 时，Top-1 **已等于全量 provenance**

因此 **Evidence Expand 在 conv-30 上可能收益有限**（仅当 `len(source_message_ids)>1` 时才有新内容）。  
Temporal SAFE_RANGE 对 `conv-30_v3:6`（"next month"）类错题 **更直接**。

仍须做 ablation：Full LoCoMo / 未来多 provenance memory 可能受益。

## 5. Gap

| ID | 缺口 |
|----|------|
| G1 | month/week 表达式被 `_UNSUPPORTED_PERIOD_RE` 拒绝 |
| G2 | `to_metadata_lines()` 不支持日期范围展示 |
| G3 | `ResolutionStatus` 无 SAFE_RANGE（可用 SAFE + `granularity="range"` + 不同 start/end，small diff） |
| G4 | `evaluate_questions` 无 NO_INFO → expand → retry 逻辑 |
| G5 | 无统一 `is_no_info()`（分散在多个 ablation 脚本） |
| G6 | 无 Temporal-only / Expand-only / Combined ablation 脚本 |
| G7 | `soon` 未列入模糊词表（应 AMBIGUOUS，不解析） |

## 6. Implementation

### A. Temporal SAFE_RANGE

#### A1. `deterministic_temporal_resolver.py`（small diff）

1. 从 `_UNSUPPORTED_PERIOD_RE` **移除** `month|week` 六项；**保留** `last/next/this year` 为 unsupported。
2. 将 `soon` 加入 `_UNSUPPORTED_VAGUE_RE`。
3. 在 `_is_safe_expression()` 中识别 6 个 month/week 表达式为 safe。
4. 在 `_resolve_safe_single()` 新增规则（`rule_id` 建议）：

| 表达式 | rule_id | 范围计算（anchor = mention_date） |
|--------|---------|-----------------------------------|
| this month | `this_month_range` | 当月 1 日 ~ 当月最后一天 |
| next month | `next_month_range` | 下月 1 日 ~ 下月最后一天 |
| last month | `last_month_range` | 上月 1 日 ~ 上月最后一天 |
| this week | `this_week_range` | 含 mention 的 ISO 周（周一~周日） |
| next week | `next_week_range` | 下一 ISO 周 |
| last week | `last_week_range` | 上一 ISO 周 |

使用 `datetime.date` + 手动月边界（不引入新依赖）；周界采用 **ISO 周一始**（在测试中固定）。

5. 返回 `TemporalResolution`：
   - `status=SAFE`（或新增 `SAFE_RANGE` enum 值；优先 **SAFE + granularity="range"** 以复用 telemetry）
   - `resolved_event_start` / `resolved_event_end` 为范围两端
   - `rule_id` 如上

6. 更新 `to_metadata_lines()`：

```text
  Resolved event date range: 2023-02-01 ~ 2023-02-28
  Temporal basis: "next month" relative to evidence date 2023-01-20
```

点日期规则保持 `Resolved event date: YYYY-MM-DD` 不变。

#### A2. 测试更新

`tests/unit/test_deterministic_temporal_resolver.py`：

- 新增：next/last/this month、next/last/this week、跨月（Jan→Feb）、跨年（Dec→Jan）
- 保持：a few years ago / recently / soon → AMBIGUOUS
- 更新：`test_last_week_not_resolved` → 期望 SAFE range
- 新增：`format_memories` 集成断言 range 行出现在 prompt

### B. NO_INFO Evidence Expand + retry once

#### B1. `memory_evidence_context.py`

新增：

```python
def collect_shown_source_message_ids(
    retrieval, *, question, max_evidence_per_memory
) -> set[str]: ...

def expandable_source_message_ids(
    retrieval, shown_ids: set[str]
) -> list[str]:
    """Union of memory.source_message_ids not in shown_ids, stable order."""

def format_memories_expand_retry(
    retrieval, source_index, question, *,
    initial_max_evidence: int = 1,
    expand_message_ids: set[str] | None = None,
    enable_deterministic_temporal_resolver: bool = True,
) -> str:
    """
    Retry 模式：对每条 memory，shown ids 保留；
    额外 append expand_message_ids 中属于该 memory 的 ids（去重）。
    或直接：retry 时 max_evidence_per_memory=None（全 provenance），
    但跳过已在 initial pass 展示的 id（避免重复块）。
    """
```

**推荐 MVP 策略（最小且满足需求）**：

- Pass-1：`max_evidence_per_memory=1`（不变）
- Pass-2（仅当 NO_INFO 且 `expandable_ids` 非空）：对 top-k memories 使用 **该 memory 的全部 `source_message_ids`**（上限 `MAX_SUPPORTING_EVIDENCE_PER_MEMORY=20`），**跳过 pass-1 已展示的 message_id**

#### B2. `answer_pipeline.py`（新文件）

```python
NO_INFO_PHRASE = "No information available"

async def answer_with_no_info_expand_retry(
    llm, *, retrieval, source_index, question, reference_date,
    max_evidence_per_memory: int = 1,
    enable_temporal_resolver: bool = True,
) -> AnswerOutcome:
    # pass 1
    # if is_no_info and expandable: pass 2 (max 1 retry)
    # else return
```

在 user prompt retry 时可加一行固定说明（非 Agent）：

```text
Additional supporting evidence was retrieved from original messages.
```

#### B3. 接入点

| 文件 | 改动 |
|------|------|
| `evaluate.py` | `evaluate_questions()` 改用 `answer_with_no_info_expand_retry` |
| `full_locomo_final_eval.py` | 同上；统计 `retry_attempted`, `expand_applied`, `retry_recovered` |
| `prompts.py` | 导出 `is_no_info()` / `NO_INFO_PHRASE` |

**不改**：retrieval API、Neo4j、extraction pipeline。

#### B4. Feature flags（ablation 用）

```python
ENABLE_TEMPORAL_SAFE_RANGE = True   # 控制新 rules（或总是 on，ablation 用脚本开关）
ENABLE_NO_INFO_EVIDENCE_EXPAND = True
```

可在 ablation 脚本用参数控制，不必写入 production settings。

## 7. 文件变更清单

| 文件 | 操作 | 目的 |
|------|------|------|
| `scripts/locomo_eval/deterministic_temporal_resolver.py` | 修改 | SAFE_RANGE rules |
| `scripts/locomo_eval/memory_evidence_context.py` | 修改 | range 展示 + expand formatting |
| `scripts/locomo_eval/answer_pipeline.py` | **新增** | NO_INFO retry 共享逻辑 |
| `scripts/locomo_eval/evaluate.py` | 修改 | 接入 retry |
| `scripts/locomo_eval/full_locomo_final_eval.py` | 修改 | 接入 retry + stats |
| `scripts/locomo_eval/prompts.py` | 修改 | 统一 `is_no_info` |
| `scripts/locomo_eval/temporal_evidence_expand_ab_conv30.py` | **新增** | 4-way ablation |
| `tests/unit/test_deterministic_temporal_resolver.py` | 修改 | temporal range tests |
| `tests/unit/test_answer_pipeline_evidence_expand.py` | **新增** | expand/retry unit tests |
| `tests/unit/test_memory_evidence_selection.py` | 修改 | expand dedupe 集成 |

## 8. Tests

### Unit — Temporal

| 场景 | 预期 |
|------|------|
| mention 2023-01-20 + "next month" | SAFE, 2023-02-01 ~ 2023-02-28 |
| mention 2023-01-20 + "last month" | 2022-12-01 ~ 2022-12-31 |
| mention 2023-03-01 + "last month" | 2023-02-01 ~ 2023-02-28（跨月） |
| mention 2023-12-15 + "next month" | 2024-01-01 ~ 2024-01-31（跨年） |
| mention 2023-01-20 + "next week" | ISO 下一周 Mon~Sun |
| mention 2023-01-20 + "last week" | ISO 上一周 Mon~Sun |
| "a few years ago" / "recently" / "soon" | AMBIGUOUS, 无 resolved 字段 |
| "last year" / "next year" | AMBIGUOUS（本轮不做） |
| format_memories 集成 | prompt 含 `Resolved event date range:` |

### Unit — Evidence Expand

| 场景 | 预期 |
|------|------|
| 正常回答（非 NO_INFO） | `retry_attempted=False` |
| NO_INFO + memory 有 3 个 source_ids 仅展示 1 个 | expand 2 条新 evidence；retry 一次 |
| NO_INFO + 仅 1 个 source_id 已展示 | `expandable_ids` 空；不 retry |
| retry 后仍 NO_INFO | 停止；不第三次调用 |
| 已展示 id | retry prompt 不重复同一条 evidence 块 |

### Integration（可选，不强制起全栈）

- Mock `LlmHelper`：第一次返回 NO_INFO，第二次返回事实 → 断言 `expand_applied=True`

## 9. Evaluation（conv-30 ablation）

新增 `temporal_evidence_expand_ab_conv30.py`，使用已有 retrieval cache（若存在）或 live retrieve，跑 4 arms：

| Arm | Temporal SAFE_RANGE | NO_INFO Expand |
|-----|--------------------|--------------------|
| Baseline | off（或当前 production frozen：旧 resolver） | off |
| Temporal only | on | off |
| Expand only | off | on |
| Combined | on | on |

输出 `data/locomo/conv30/ablations/temporal_evidence_expand_ab_conv30.json`：

```json
{
  "overall_j": ...,
  "temporal_j": ...,
  "false_no_info_count": ...,
  "retry_attempted": ...,
  "retry_recovered": ...,
  "retry_still_no_info": ...
}
```

**验收参考**（非硬性 contract）：

- Temporal arm：`temporal_j` ≥ baseline；`conv-30_v3:6` 类题不再 NO_INFO
- Combined ≥ max(single arms) 或说明负交互

## 10. MVP 验收条件（对照 Prompt §6）

| # | 条件 | 验证方式 |
|---|------|----------|
| 1-3 | month/week SAFE_RANGE；模糊词不解析 | unit tests |
| 4 | 范围进入 answer prompt | `format_memories` integration test |
| 5 | NO_INFO 时按 source_message_ids 补充 | unit + ablation `expand_applied` |
| 6 | 最多 retry 1 次 | unit assert call count ≤ 2 |
| 7-8 | 正常题不 expand；不读整 session | unit：非 NO_INFO 无 retry；仅用 memory 的 ids |
| 9 | 无 schema 变更 | code review |
| 10 | unit tests | CI |
| 11 | 4-way ablation | conv-30 script output |

## 11. 数据一致性 / 风险

| 维度 | 结论 |
|------|------|
| 原子性 | 不适用（只读 Mongo + 无写入） |
| 幂等 | retry 确定性：同输入同 expand 集 |
| 并发 | 不适用 |
| 用户隔离 | SourceMessageIndex 按 user_id 加载 |
| 部分失败 | source_id 在 index 缺失 → 跳过该条，不 fail |

## 12. 后续优化（非本轮）

- planned/completed event disambiguation（C5 时间版本干扰）
- 生产侧 `GET /archive/messages?ids=` endpoint
- 将 resolver + evidence 模块迁入 `src/memory_system/domain/` 供 Agent SDK 复用
- NO_INFO 且 single-provenance 仍失败 → Answer Contract v2（与 expand 正交）

## 13. 架构阻碍评估

| 阻碍 | 严重度 | 说明 |
|------|--------|------|
| 逻辑仅在 `scripts/locomo_eval/` | 低 | 与现网一致；本轮目标就是 eval 答题 |
| 无生产 archive read API | 低 | MVP 范围外；expand 依赖 eval 的 Mongo index |
| conv-30 多数为单 provenance | 中 | expand 收益可能小；temporal 收益更确定 |
| evaluate / full_eval 双入口 | 低 | 用 `answer_pipeline.py` 去重 |

**结论：无阻塞性架构阻碍，可进入 Developer 阶段。**

---

## 审计摘要（给 Orchestrator）

1. **已具备**：完整 eval 答题链、deterministic temporal（点日期）、SourceMessageIndex、grounding prompt、source_message_ids 从 archive 恢复原文。
2. **Temporal 最小改动**：扩展 resolver 规则 + `to_metadata_lines()` 范围展示；从 unsupported 列表移除 month/week。
3. **Expand 最小改动**：`answer_pipeline.py` + `format_memories` expand 模式 + evaluate 单点 retry。
4. **预计文件**：见 §7（~9 个文件，2 新增）。
5. **架构阻碍**：无阻塞；注意 production 无答题链、conv-30 expand 收益可能有限。
6. **可进入 Developer**：是，待 `PLAN_APPROVED`。

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-23 04:42 UTC | POST_MERGE_CLEANUP | status=committed → completed；PR #65 MERGED `87519f28ec406a29f141f6d7fb226ca07b8b612e` mergedAt `2026-08-23T04:40:37Z`；implementation `58c20e6770015776280c52ce924c29f16d6e0bef`；ci fix `b698c4df35e14b62e5f2dac0774e40004201efba`；docs(status): complete on main；exact feat `feat/fast-mvp-temporal-safe-range-evidence-expand` 删除 | unit 31 passed；CI green（static, unit-contract-coverage, integration） | `next_action=FAST-MVP completed — NO AUTO-START`；未 git tag |
