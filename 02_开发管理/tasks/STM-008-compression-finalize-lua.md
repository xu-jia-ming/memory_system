# STM-008 Compression Finalize Lua

## 1. 任务信息

```yaml
task_id: STM-008
task_name: Compression Finalize Lua
status: completed
plan_review_round: 2
workflow_mode: NORMAL
workflow_mode_source: explicit
spec_sections:
  - "§1.2.1 Working Memory（规则 4–6：压缩流程、锁、Finalize 步骤与失败保留语义）"
  - "§1.2.5 Compression Update Flow（§991–1018：token 公式、Lua 步骤、消息边界、version bump、pending 清理、锁释放）"
  - "§1.2.6 Context Compression Trigger Strategy（锁内多轮；Finalize 为单轮原子写回）"
  - "§1.2.7 Session 生命周期（closing 与 Pending 复用；§5845 关停 in-flight 完成）"
  - "§3.28 Graceful Shutdown（§5845：关停时允许完成 Redis Finalize）"
prerequisites:
  formal:
    - "STM-006 — SATISFIED（compression lock + pending_archive_* Lua + lock key/repository；PR #25 MERGED）"
    - "STM-007 — SATISFIED（CompressionFinalizeLlmPayload + CompressionLlmService；PR #26 MERGED）"
  implementation_reuse:
    - "STM-001 — SATISFIED（estimate_tokens heuristic；WorkingMemoryMeta / codec 空值编码）"
    - "STM-002 — SATISFIED（Session 创建；WM Hash 初始化）"
    - "STM-003 — SATISFIED（messages List RPUSH 头部语义；message JSON codec）"
    - "STM-004 — SATISFIED（context read Lua 只读模式参考）"
    - "STM-005 — SATISFIED（archive_batch_key = session_id:first_message_id:last_message_id）"
  baseline:
    - "Authoritative baseline：main == origin/main == ff9a609009f2a151f2e1a4bf41e24be3bc3a2467；working tree clean；FULL_RUFF PASS；mypy PASS"
    - "本任务需要真实 Redis（compose test 栈）；不需要 Kafka broker / Mongo / LLM / HTTP"
branch: "feat/STM-008-compression-finalize-lua"
created_at: "2026-08-10 23:01 UTC"
updated_at: "2026-08-10 23:50 UTC"
approval_gates:
  planning_docs: "Round 2 PLAN_APPROVED; Human PLAN_APPROVED Amendment 001; plan_commit fa3e1bf33e889dbb6180315eda896b954a02df8f"
  implementation_plan: "status=completed; PR #27 MERGED; merge ac61680098d2ae2644bc8b990f057816c3218fca"
```

### 1.1 编排与门禁（本轮）

```yaml
start_existing_task: true
phase: planning_only
must_not_this_round:
  - "进入 Developer / 编写业务实现或测试语义"
  - "git add / commit / push / merge / rebase"
  - "触碰 DEV-006 / PR #13"
  - "实现 Compression LLM / Kafka publish / Mongo archive / Coordinator / HTTP / Session Close / STM-011"
  - "私自关闭 OI-004 / OI-005"
  - "声称跨系统原子事务或 exactly-once"
```

---

## 2. 任务目标

交付 **压缩结果原子写回（Finalize）** 能力：在 STM-006 已写入 `pending_archive_*` 且 STM-007 已产出 `CompressionFinalizeLlmPayload` 之后，通过 **单个 Redis Lua** 原子完成 §1.2.5 规定的校验、token 重算、`compressed_context` 写回、`compression_version` +1、`LTRIM` 头部消息、清空 pending、更新 `updated_time`、**compare-and-delete 释放压缩锁**。

可验证交付：

1. **Finalize 领域层**：稳定结果枚举、`CompressionFinalizeInput`/`CompressionFinalizeResult`、领域服务 `finalize_compression(...)`（进程内 API；无 HTTP）。
2. **`compression_finalize.lua`**：单脚本原子执行全部 mutation；ownership / version / pending 四字段 / 消息边界校验同窗；**禁止** Python `GET lock` → later write TOCTOU。
3. **STM-007 直接 handoff**：仅消费既有 `CompressionFinalizeLlmPayload`（`compressed_context` + `new_compressed_context_tokens`）；空字符串合法。
4. **Token 公式（权威 §1000–1006）**：`new = max(0, current - archived_message_tokens - old_compressed_context_tokens + new_compressed_context_tokens)`；**无 tokenizer**；`archived_message_tokens` 由调用方按 §987 传入，Lua 内与 Redis `pending_archive_estimated_tokens` **精确匹配**校验。
5. **测试**：Unit + Contract + Redis Integration（**27 场景**，含 token 数值证明（I18 Case A 分解表）、负值 clamp Case B（I27）、M1–M4 边界、畸形 Redis 整数字面（I24–I25）、畸形 message JSON（I26）、并发 duplicate、失败零副作用、retry 不 double-trim/bump、无 Kafka/Mongo/LLM 副作用）。

概念链（本任务止点）：

```text
STM-006 pending + lock held
        → STM-007 CompressionFinalizeLlmPayload
        → STM-008 single Lua: validate → mutate → release lock
        → WM ready for next compression round / STM-009 Coordinator
```

**本任务不得**调用 LLM、发布 Kafka、读写 Mongo、实现 Coordinator HTTP、Session Close、STM-011 republish。

---

## 3. 非目标（必须坚持；黑名单语义）

- Compression LLM / prompt / `run_compression_llm`（**STM-007** 已完成）。
- Kafka `context.archive.created` publish / republish（**STM-006** 已完成；**STM-011** 补发脚本）。
- Mongo `context_archive` create/reuse / mutation（**STM-005**）。
- Compression Coordinator 多轮策略、消息头部选择、`POST /api/v1/memory/working/message` HTTP（**STM-009**）。
- Session Close 状态机 / Redis 全量删除（**STM-010**）。
- `scripts/republish_archive_event.py`（**STM-011**）。
- Extraction / Retrieval / embedding / TEI / SiliconFlow（**DEV-006/PR#13** 等）。
- 消息 ID Set `SADD`/`SREM`（§1016：压缩时不裁剪 message_ids）。
- 锁续期、Redlock、第二套 lock 实现（复用 `compression_lock_repository` / `compression_lock_key`）。
- Outbox / 自动补偿 / 跨 Redis+Mongo+Kafka 伪原子事务。
- 自动 Push / Merge / Rebase / Force Push。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `ff9a609009f2a151f2e1a4bf41e24be3bc3a2467` |
| `git status --short` | clean（规划轮次允许本 Task Plan + progress + master_plan dirty） |
| formal STM-006 | `completed`（PR #25 MERGED） |
| formal STM-007 | `completed`（PR #26 MERGED） |
| FULL_RUFF / mypy | PASS（baseline 声明） |

### 4.2 可复用组件审计

| 交付物 | 路径 | STM-008 用法 |
|---|---|---|
| `CompressionFinalizeLlmPayload` | `domain/models/compression_llm.py` | **直接 handoff**；禁止第二套 payload 模型 |
| `compression_lock_key` | `infrastructure/redis/keys.py` | lock KEYS[3] |
| `compression_lock_repository` | `infrastructure/redis/compression_lock_repository.py` | compare-and-del 模式参考；**Finalize Lua 内释放**，不在 Python 二次 DEL |
| `working_memory_codec` | `infrastructure/redis/working_memory_codec.py` | pending 空值 `""`/`"0"`；清空 pending 编码 |
| `pending_archive_write.lua` | `infrastructure/redis/scripts/pending_archive_write.lua` | precondition 顺序 / 畸形 pending / lock ownership 同窗模式 |
| `prepare_pending_archive_and_publish` + Integration | `tests/integration/test_compression_preparation_redis.py` | 种子 session / pending / lock / messages fixture 模式 |
| `estimate_tokens` | STM-001 | Python 层计算 `old_compressed_context_tokens` / 校验输入（**Lua 不算 tokenizer**） |
| `build_archive_batch_key` | `domain/services/context_archive_service.py` | Integration 构造 `archive_batch_key` 与 M1–M4 边界 |

### 4.3 当前缺失

- `CompressionFinalizeStatus` 枚举与 Input/Result 模型
- `compression_finalize.lua` + script wrapper + repository
- `compression_finalize_service.py` 领域编排
- Unit / Contract / Redis Integration 全套测试

### 4.4 与技术规格一致性

- §1.2.5 §991–1014 Lua 步骤为 Finalize **权威**清单；**未列出** session `status` 校验 → Finalize Lua **不以 active-only 作为硬门禁**（区别于 STM-006 pending write）。
- §1.2.7 #3 + §5845：closing / shutdown 场景下 **in-flight** Finalize（持锁 + 非空 pending）须允许完成；无 in-flight 时 `session_closing`。
- §1.2.1 规则 4 步骤 4：Finalize 后释放锁 → **同一 Lua 末尾 compare-and-delete**（§1.2.1 规则 6 owner 校验）。
- §1016：不裁剪 `message_ids` Set。
- OI-004：`archived_message_tokens` 由调用方供给（§987）；**不得** Mongo 重算或扩展 Archive schema。

### 4.5 前置任务检查

| 前置 | 状态 |
|---|---|
| STM-006 | **SATISFIED** |
| STM-007 | **SATISFIED** |
| OI-004 | **open** — acknowledged；**不阻塞**；**不得关闭** |
| OI-005 | **open** — partial STM-006 evidence；acknowledged；**不得关闭** |
| STM-009 | **blocked** — 需要 STM-008 completed |

---

## 5. 实现方案

### 5.0 十六项 Contract 闭合（Planner 权威结论；规格字面）

#### C1 — Finalize preconditions（session / identity / status）

| 项 | 结论 |
|---|---|
| Session 存在 | meta Hash `EXISTS` → 否则 `session_not_found` |
| 身份 | `HGET user_id` / `session_id` 与 ARGV 精确匹配 → 否则 `session_not_found` |
| Session status | **非 STM-006 active-only**：§1.2.5 §991–1014 Lua 清单 **无 status 步骤**；Planner 闭合：<br>• `status == active` → 允许（正常压缩完成）<br>• `status == closing` **且** Redis `pending_archive_id` 非空（`""` 以外）→ 允许 in-flight 完成（§733 关闭前 Pending 复用；§5845 关停 in-flight Finalize）<br>• `status == closing` **且** pending 空 → `session_closing`（§732 普通压缩不得再执行）<br>• 畸形 status 字面 → `invalid_session_state` |
| compression_version | `HGET compression_version` 须为可解析非负整数字面；**畸形**（非整数、空、浮点等）→ `invalid_session_state`（**不是** `version_conflict`）；可解析整数须 **精确等于** `expected_compression_version` → 否则 `version_conflict` |
| Lock ownership | `GET lock_key` 存在且 **完全等于** `lock_owner_token` → 否则 `lock_not_acquired` + **ZERO_SIDE_EFFECT** |
| Pending 四字段 | Redis 四字段与 ARGV **逐项精确匹配**（见 C4）→ 否则 `pending_conflict` |
| 消息边界 | List 长度 ≥ `pending_archive_message_count`；头部首尾 `message_id` 与 ARGV 一致 → 否则 `message_boundary_mismatch`；**畸形 message JSON**（无法解析、缺 `message_id` 字段等）→ `message_boundary_mismatch`（显式；非 `invalid_session_state`） |

**禁止**：Python `GET lock` → 后续独立 `HSET`/`LTRIM` 多 round-trip。

#### C2 — Lock ownership（同窗于 mutation）

| 项 | 结论 |
|---|---|
| Key | `memory:compression:lock:{user_id}:{session_id}`（`compression_lock_key`） |
| 校验时机 | **同一 Lua** 内、任何 mutation 之前 |
| 失败 | `lock_not_acquired`；零副作用 |
| 释放 | **成功 mutation 后** 同一 Lua 内 compare-and-delete（`GET == token` 则 `DEL`）；失败路径 **不** 释放 |
| TOCTOU | **禁止** Python 侧 ownership GET 作为写回依据 |

#### C3 — compression_version（exact match + single +1）

| 项 | 结论 |
|---|---|
| 前置 | `HGET compression_version` 可解析为非负整数；畸形 → `invalid_session_state`；可解析值 `== expected_compression_version`（精确） |
| 成功 | `compression_version` 单次 +1（`INCR` 或 `HSET current+1`） |
| 幂等 / 重试 | 已成功后 `current_version == expected + 1` 且 pending 已清空 → 再次以 **旧** `expected_compression_version` 重试 → `version_conflict`（**不得** double-trim / double-bump） |
| Stale vs finalized | `current > expected`（已 finalize 或并发抢先）→ `version_conflict`；`current < expected` → `version_conflict`（数据异常，fail-closed） |
| STM-006 | STM-006 **不** bump version；首次 Finalize 通常 `expected=0` 或协调层读取值 |

#### C4 — compressed_context + STM-007 payload

| 项 | 结论 |
|---|---|
| Handoff | **仅** `CompressionFinalizeLlmPayload`：`compressed_context`（str）、`new_compressed_context_tokens`（int ≥ 0） |
| 空字符串 | **合法**（§951）；`new_compressed_context_tokens` 可为 `0` |
| Python 校验 | `compressed_context` 非 `null`、非非 str 类型 → **ValidationError**（不进 Lua）；**不**映射 `invalid_session_state` |
| Lua | `ARGV compressed_context` 原样 `HSET`；不做 LLM 重算 |

#### C5 — estimated_tokens 公式（§1000–1006 权威）

**5. 最终唯一公式（规格字面；§1000–1006）**

```
new_estimated_tokens = max(
    0,
    current_estimated_tokens
    - archived_message_tokens
    - old_compressed_context_tokens
    + new_compressed_context_tokens
)
```

**五项变量权威定义（Planner 闭合；Amendment 001）**

| # | 变量 | 权威来源 | 说明 |
|---|---|---|---|
| 1 | `current_estimated_tokens` | Redis `HGET estimated_tokens`（Lua 执行时刻快照；§996、§1015） | 含 **当前** `compressed_context` token + **List 内全部消息** token（§182：`compressed_context` 与近期消息总量）。畸形 Redis 字面（非整数）→ `invalid_session_state`（mutation 前；**不是** `version_conflict`） |
| 2 | `archived_message_tokens` / `pending_archive_estimated_tokens` | 调用方按 §987 计算 archive messages 求和；STM-006 写入 Redis `pending_archive_estimated_tokens` | **必须精确相等**。Lua：pending 四字段校验含 tokens；**额外 defense-in-depth**：`ARGV[11] == ARGV[7]`（`archived_message_tokens == pending_archive_estimated_tokens`）不等 → `pending_conflict`（mutation 前）。Python 预检不一致 → **ValidationError**（不进 Lua） |
| 3 | `old_compressed_context_tokens` | **调用方**在 Lua 前用 STM-001 `estimate_tokens(redis compressed_context)` 计算（§989） | **不**持久化于 Redis meta；**无 schema 变更**；作为 `ARGV[12]` 传入 Lua。权威来源为 Python 对 **Finalize 前** Redis `compressed_context` 文本的估算 |
| 4 | `new_compressed_context_tokens` | STM-007 `CompressionFinalizeLlmPayload.new_compressed_context_tokens` | 直接 handoff；作为 `ARGV[13]` |
| 5 | 公式 | §1000–1006 上文块 | Lua mutation 内唯一实现；**禁止** tokenizer |

**负值与 clamp 语义（Amendment 001；HM-2）**

| 场景 | 行为 | 结果码 |
|---|---|---|
| **Case A** 合法正值 | `raw = current - archived - old_C + new_C` ≥ 0 → `new = raw` | `success`；`HSET estimated_tokens = new` |
| **Case B** 负 raw 值 | `raw < 0` → **`max(0, raw) = 0`**（§1000–1006 **显式**要求） | `success`；`HSET estimated_tokens = 0`；**不是** `invalid_session_state` |
| **Case C** `archived_message_tokens > current_estimated_tokens` | 规格 **未** 要求 fail-closed；仍走公式 + `max(0,…)` | 若 raw < 0 → clamp 0 后 **仍 success**（与 Case B 一致） |
| **输入前置失败**（mutation 前） | 畸形整数 ARGV/Redis 字面、半填充 pending、`archived != pending`（四字段或 ARGV[11]≠ARGV[7]）、畸形 message JSON | `invalid_session_state` / `pending_conflict` / `message_boundary_mismatch`；**ZERO_MUTATION** |

**Case A 数值证明（Integration I18；分解表）**

种子态（Finalize 前 Redis）：

| 分量 | token |
|---|---|
| `old_compressed_context`（Redis 文本；Python `estimate_tokens` → ARGV[12]） | 50 |
| pending archive 头部消息（即将 LTRIM；= `archived_message_tokens` = `pending_archive_estimated_tokens`） | 300 |
| List 剩余尾部消息（LTRIM 后保留） | 420 |
| **Redis `estimated_tokens`（current）** | **770** (= 50 + 300 + 420) |

Finalize 入参：`archived_message_tokens=300`（ARGV[11]），`old_compressed_context_tokens=50`（ARGV[12]），`new_compressed_context_tokens=80`（ARGV[13]，来自 STM-007 payload）。

```
new = max(0, 770 - 300 - 50 + 80) = max(0, 500) = 500
```

事后校验：`remaining_msgs(420) + new_compressed(80) = 500` ✓

| 项 | 结论 |
|---|---|
| Tokenizer | **禁止** Lua/Python Finalize 路径调用模型 tokenizer |
| 负值保护 | `max(0, …)` 在 Lua 内实现；负 raw → **0**，非错误码 |

#### C6 — Message trimming（LTRIM 头部）

| 项 | 结论 |
|---|---|
| 数量来源 | **Redis** `pending_archive_message_count`（经 precondition 与 ARGV 精确匹配后使用）；**禁止**仅信任 caller count 而不读 Redis |
| 操作 | `LTRIM messages_key N -1`，其中 `N = pending_archive_message_count`（移除索引 `0..N-1`，保留尾部） |
| 顺序语义 | messages List：`RPUSH` 追加 → **头部 = 最旧**；Archive `first_message_id` = List 头；`last_message_id` = 第 `N` 条（索引 `N-1`） |
| 边界校验 | `LLEN >= N`；`LRANGE 0 0` 解析 JSON `message_id` == `expected_first_message_id`；`LRANGE N-1 N-1` == `expected_last_message_id`（与 STM-005 `archive_batch_key` 首尾一致） |
| message_ids Set | **不修改**（§1016） |

#### C7 — Atomic mutation（单 Lua）

单次 `EVAL`/`EVALSHA` 内完成 **全部** mutation；禁止 Python 多步 Redis 写回。

#### C8 — Precondition 顺序（固定 12 步）+ Mutation 顺序

**Preconditions（失败即返回；mutation 前零副作用）：**

1. `EXISTS meta` → `session_not_found`
2. `user_id` / `session_id` 匹配 → `session_not_found`
3. `status` 规则（C1）→ `session_closing` / `invalid_session_state`
4. `GET lock == lock_owner_token` → `lock_not_acquired`
5. `HGET compression_version` 可解析为非负整数 → 畸形 `invalid_session_state`；可解析值 `== expected` → 否则 `version_conflict`
6. 读 pending 四字段；畸形/半填充 → `invalid_session_state`；与 ARGV 四字段 **逐项精确不等** → `pending_conflict`
7. `ARGV[11] == ARGV[7]`（`archived_message_tokens == pending_archive_estimated_tokens`）→ 不等 `pending_conflict`（defense-in-depth；与步骤 6 冗余但 **必须实现**）
8. `archived_message_tokens` / `old_compressed_context_tokens` / `new_compressed_context_tokens` ARGV 可解析为非负整数 → 否则 `invalid_session_state`
9. `HGET estimated_tokens` 可解析为非负整数 → 畸形 `invalid_session_state`
10. `LLEN messages >= pending_count` → 否则 `message_boundary_mismatch`
11. 首尾 `message_id` 边界（C6）：`LRANGE` 解析 JSON；畸形 JSON / 缺 `message_id` → `message_boundary_mismatch`；id 不匹配 → `message_boundary_mismatch`
12. （implicit）全部 precondition 通过 → 进入 mutation

**Mutations（严格顺序）：**

1. 读取 `current_estimated_tokens`；计算 `new_estimated_tokens`（C5 公式）
2. `HSET compressed_context`
3. `HSET compression_version` = `expected + 1`（或 `INCR`）
4. `LTRIM messages N -1`
5. `HSET estimated_tokens` = `new_estimated_tokens`
6. 清空 pending 四字段 → codec 空：`pending_archive_id=""`, `pending_archive_batch_key=""`, `pending_archive_message_count="0"`, `pending_archive_estimated_tokens="0"`
7. `HSET updated_time` = ARGV `updated_time`
8. compare-and-delete lock（C2）
9. return `success`

#### C9 — Pending cleanup

| 场景 | 行为 |
|---|---|
| success | 四字段清空为 `""`/`"0"`（对齐 codec） |
| 任意 failure | **不** 提前清空；**不** `DEL` 整个 meta Hash |
| 半清空 | **禁止**（失败路径零 mutation） |

#### C10 — Lock release（§1.2.1 规则 4 步骤 4）

- 仅在 **mutation 全部成功** 后于 **同一 Lua** 释放锁。
- 模式：与 `compression_lock_repository` `_RELEASE_LUA` 相同语义（`GET == token` → `DEL`）。
- 失败 / `version_conflict` / `pending_conflict` 等：**不** 释放（协调层 `finally` 仍可尝试 release — 但 Finalize 失败时锁应保留给重试；与 STM-006 一致）。

#### C11 — Idempotency / Retry（场景 A–E）

| 场景 | 行为 | 结果码 |
|---|---|---|
| **A** 首次 success | version +1；trim 一次；pending 清空；锁释放 | `success` |
| **B** success 后以 **相同旧** `expected_compression_version` 重试 | version 已 +1；**不得** 再 trim / bump | `version_conflict` |
| **C** 并发 duplicate finalize（同 version + 同 pending） | Redis 单线程 Lua → **恰好一次** version 迁移 | 一方 `success`；另一方 `version_conflict` |
| **D** 任意 precondition 失败 | **零 mutation**（含 version、trim、pending、锁） | 对应失败码 |
| **E** 客户端 outcome unknown | 安全重试：以 version 检查区分「未完成」vs「已 finalize」 | 未完成可重试 success；已 finalize → `version_conflict` |

#### C12 — Crash model

- Lua 原子：要么全 mutation + 锁释放，要么全不执行。
- 进程崩溃在 Lua 外：Redis 状态未知 → 协调层读 `compression_version` + pending 决定重试；**不得** double-trim（version gate）。

#### C13 — Session status（active vs closing）

见 C1；**证据**：§991–1014 无 status 步骤；§732 vs §733/§5845 in-flight 例外。

#### C14 — STM-007 payload handoff

- 领域服务入参：`llm_payload: CompressionFinalizeLlmPayload`（或嵌套于 `CompressionFinalizeInput`）。
- **禁止** 在 STM-008 内调用 `run_compression_llm`。

#### C15 — No Kafka

- 默认 **无** 事件发布；Integration 断言 **零** Kafka producer 调用（无 broker fixture）。

#### C16 — No Mongo mutation

- **无** Mongo client 调用；**无** archive 文档更新。

### Step 1 — 结果枚举与领域模型

- **文件**：
  - `src/memory_system/domain/enums/compression_finalize.py`（创建）
  - `src/memory_system/domain/models/compression_finalize.py`（创建）
- **枚举** `CompressionFinalizeStatus`（C11 + 稳定字面量）：
  - `success`
  - `session_not_found`
  - `session_closing`
  - `lock_not_acquired`
  - `version_conflict`
  - `pending_conflict`
  - `invalid_session_state`
  - `message_boundary_mismatch`
- **输入** `CompressionFinalizeInput`：
  - `user_id`, `session_id`
  - `expected_compression_version`（int ≥ 0）
  - `pending_archive_id`, `pending_archive_batch_key`（非空）
  - `pending_archive_message_count`（int > 0）
  - `pending_archive_estimated_tokens`（int ≥ 0）
  - `expected_first_message_id`, `expected_last_message_id`（非空）
  - `archived_message_tokens`（int ≥ 0；须与 `pending_archive_estimated_tokens` 一致 → ValidationError）
  - `old_compressed_context_tokens`（int ≥ 0）
  - `lock_owner_token`（非空 str）
  - `llm_payload: CompressionFinalizeLlmPayload`（STM-007 handoff）
  - 可选 `updated_time` / clock 注入
- **输出** `CompressionFinalizeResult`：`status`、可选 `new_compression_version`、`new_estimated_tokens`（success 时）、诊断字段
- **Python 校验（fail-closed，不进 Lua）**：
  - `llm_payload.compressed_context` 类型
  - `archived_message_tokens == pending_archive_estimated_tokens`
  - 空 token / 空 archive_id 等 → **ValidationError**

### Step 2 — `compression_finalize.lua` + script + repository

- **文件**：
  - `src/memory_system/infrastructure/redis/scripts/compression_finalize.lua`（创建）
  - `src/memory_system/infrastructure/redis/compression_finalize_script.py`（创建）
  - `src/memory_system/infrastructure/redis/compression_finalize_repository.py`（创建）

**KEYS（exact）：**

| Index | Key | 用途 |
|---|---|---|
| `KEYS[1]` | `working_memory_meta_key(user_id, session_id)` | meta Hash |
| `KEYS[2]` | `working_memory_messages_key(user_id, session_id)` | messages List |
| `KEYS[3]` | `compression_lock_key(user_id, session_id)` | compression lock |

**ARGV（exact；类型/校验）：**

| Index | 名称 | 类型 | 校验 |
|---|---|---|---|
| `ARGV[1]` | `expected_user_id` | string | 非空 |
| `ARGV[2]` | `expected_session_id` | string | 非空 |
| `ARGV[3]` | `expected_compression_version` | int string | `^-?%d+$`；≥ 0 |
| `ARGV[4]` | `pending_archive_id` | string | 非空 |
| `ARGV[5]` | `pending_archive_batch_key` | string | 非空 |
| `ARGV[6]` | `pending_archive_message_count` | int string | `> 0` |
| `ARGV[7]` | `pending_archive_estimated_tokens` | int string | ≥ 0 |
| `ARGV[8]` | `lock_owner_token` | string | 非空 |
| `ARGV[9]` | `expected_first_message_id` | string | 非空 |
| `ARGV[10]` | `expected_last_message_id` | string | 非空 |
| `ARGV[11]` | `archived_message_tokens` | int string | ≥ 0；**必须** `== ARGV[7]`（Lua defense-in-depth；不等 → `pending_conflict`） |
| `ARGV[12]` | `old_compressed_context_tokens` | int string | ≥ 0 |
| `ARGV[13]` | `new_compressed_context_tokens` | int string | ≥ 0 |
| `ARGV[14]` | `compressed_context` | string | 允许 `""` |
| `ARGV[15]` | `updated_time` | int string | Unix 秒 |

- **Repository**：`finalize_compression_in_redis(redis, input, updated_time) -> CompressionFinalizeStatus`
- **禁止**：`message_ids` key 进入 KEYS；**禁止** Kafka/Mongo import

### Step 3 — Compression finalize 领域服务

- **文件**：`src/memory_system/domain/services/compression_finalize_service.py`（创建）
- **`finalize_compression(*, redis, input, clock) -> CompressionFinalizeResult`**：
  1. Pydantic / 领域 **ValidationError**（C4、tokens 一致性）
  2. 单 repository 调用 → 单 Lua
  3. 映射 Lua 字面量 → `CompressionFinalizeStatus`
  4. **不** 调用 `release_compression_lock` Python 路径（成功释放已在 Lua）；失败时 **不** 自动 release（锁保留给协调层重试）
- **禁止**：LLM / Kafka / Mongo

### Step 4 — 导出与测试

- 最小修改：`domain/enums/__init__.py`、`domain/models/__init__.py`、`domain/services/__init__.py`、`infrastructure/redis/__init__.py`（仅生产 import 需要时）
- 测试见 §8

---

## 6. 文件变更清单（exact writable whitelist）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/enums/compression_finalize.py` | 创建 | `CompressionFinalizeStatus` |
| `src/memory_system/domain/models/compression_finalize.py` | 创建 | Input/Result |
| `src/memory_system/domain/services/compression_finalize_service.py` | 创建 | Finalize 编排 |
| `src/memory_system/infrastructure/redis/scripts/compression_finalize.lua` | 创建 | 原子 Finalize Lua |
| `src/memory_system/infrastructure/redis/compression_finalize_script.py` | 创建 | 加载/执行 Lua |
| `src/memory_system/infrastructure/redis/compression_finalize_repository.py` | 创建 | repository 封装 |
| `src/memory_system/domain/enums/__init__.py` | 修改 | 最小导出 |
| `src/memory_system/domain/models/__init__.py` | 修改 | 最小导出（若需要） |
| `src/memory_system/domain/services/__init__.py` | 修改 | 最小导出 |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 | 最小导出 |
| `tests/unit/test_compression_finalize_models.py` | 创建 | Input 校验 / payload handoff |
| `tests/unit/test_compression_finalize_lua_mapping.py` | 创建 | Lua 字面量映射 |
| `tests/unit/test_compression_finalize_service.py` | 创建 | 服务编排 / ValidationError |
| `tests/contract/test_stm008_contract.py` | 创建 | 枚举 / TOCTOU guard / payload 字段 |
| `tests/integration/test_compression_finalize_redis.py` | 创建 | **27** Redis Integration 场景 |
| `02_开发管理/tasks/STM-008-compression-finalize-lua.md` | 修改 | 本 Task Plan |
| `02_开发管理/progress.md` | 修改 | 规划态字段 |
| `02_开发管理/master_plan.md` | 修改 | STM-008 登记 + CHANGE-045 |

**明确不在白名单：**

- `src/memory_system/domain/models/compression_llm.py`（**不修改**；仅 import `CompressionFinalizeLlmPayload`）
- `compression_lock_repository.py`（**不修改**；Finalize Lua 内释放）
- `pending_archive_write.lua` / preparation service
- `infrastructure/kafka/**`、`mongodb/**`、`infrastructure/llm/**`
- `api/routes/**`、Coordinator、Close、STM-011 脚本
- `settings/**`、`runtime.py`（默认）

**白名单外禁止修改**（含但不限于）：DEV-006/PR#13、五命令正文、STM-006/007 既有测试语义。

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 | **适用** | 单 Lua：校验 + 全部 mutation + 锁释放 |
| 幂等 | **适用** | version gate；成功后再试旧 version → `version_conflict`；无 double-trim |
| 并发 | **适用** | 并发 duplicate Lua → 单次 version 迁移；Integration 证明 |
| 版本冲突 | **适用** | `expected_compression_version` 精确匹配；冲突 fail-closed |
| 用户隔离 | **适用** | meta/messages/lock key 含 `user_id`+`session_id` |
| 部分失败 | **适用** | precondition 失败零 mutation；无 partial trim |
| 进程异常恢复 | **适用** | Lua 原子 + version 重试（C11 E / C12） |

---

## 8. 测试计划

### 8.1 Unit Test

| 场景 | 预期 |
|---|---|
| U1 `archived_message_tokens != pending_archive_estimated_tokens` | **ValidationError**；不调 Redis |
| U1b Lua mock：`ARGV[11] != ARGV[7]` | `pending_conflict` |
| U2 空 `lock_owner_token` / 非法 count | **ValidationError** |
| U3 STM-007 payload handoff | `CompressionFinalizeLlmPayload` 嵌入 Input；空 `compressed_context` 合法 |
| U4 Lua 映射 | 各 Lua 字面量 → 枚举 |
| U5 malformed token ARGV（unit 层 repository mock） | `invalid_session_state` |
| U6 service 成功路径 | 返回 `success` + `new_compression_version` |

### 8.2 Contract Test

| 场景 | 预期 |
|---|---|
| C1 `CompressionFinalizeStatus` 字面量集合稳定 | 与 §5.0 C11 一致 |
| C2 TOCTOU guard | production Finalize 路径 **单 Lua**（KEYS 含 meta+messages+lock）；**无** Python GET-lock-then-write |
| C3 `CompressionFinalizeLlmPayload` 仅两字段 | 与 STM-007 contract 一致 |
| C4 Lua 源码哨兵 | 含 `LTRIM`；**不含** `SREM`/`message_ids`；成功路径含 lock `DEL` |

### 8.3 Redis Integration（27 场景；仅 Redis；无 Kafka/Mongo/LLM）

复用 `test_compression_preparation_redis.py` compose fixture 模式；种子：session + messages + pending + lock。

| # | 场景 | 预期 |
|---|---|---|
| I1 | 合法 success 全路径 | version+1；trim；pending 清空；锁删除；`compressed_context` 更新 |
| I2 | `session_not_found` | 无 meta |
| I3 | `session_closing` 无 pending | status=closing，pending 空 |
| I4 | `closing` + in-flight pending + 有效锁 | **success**（§733/§5845） |
| I5 | `lock_not_acquired` 错误 token | 零 mutation |
| I6 | `lock_not_acquired` 锁缺失 | 零 mutation |
| I7 | `version_conflict` expected 不匹配（可解析整数） | 零 mutation |
| I8 | success 后旧 version 重试 | `version_conflict`；无二次 trim/bump |
| I9 | `pending_conflict` archive_id 不匹配 | 零 mutation |
| I10 | `pending_conflict` batch_key 不匹配 | 零 mutation |
| I11 | `pending_conflict` message_count 不匹配 | 零 mutation |
| I12 | `pending_conflict` estimated_tokens 不匹配 | 零 mutation |
| I13 | `invalid_session_state` 半填充 pending | 零 mutation |
| I14 | **M1** `message_boundary_mismatch` 首条 message_id 错误 | 零 mutation |
| I15 | **M2** `message_boundary_mismatch` 末条 message_id 错误 | 零 mutation |
| I16 | **M3** List 长度 < pending_count | `message_boundary_mismatch` |
| I17 | **M4** 首尾与 `archive_batch_key` 不一致 | `message_boundary_mismatch` |
| I18 | **Token 数值证明 Case A**：current=770（50+300+420），archived=300，old_C=50，new_C=80 → `new=500`；事后 420+80=500 | `HGET estimated_tokens` == 500 |
| I19 | 空 `compressed_context` + `new_tokens=0` | success；公式仍正确 |
| I20 | 失败路径零副作用（version fail） | messages 长度、version、pending、锁不变 |
| I21 | retry outcome unknown：首次 success 后读 state | pending 空；version 已增；重试旧 version → conflict |
| I22 | 并发 duplicate finalize（asyncio gather 同输入） | **恰好一次** version `0→1`（非仅无异常） |
| I23 | `message_ids` Set 不变 | LTRIM 后 Set 成员与 cardinality 不变 |
| I24 | Redis `compression_version` 畸形字面（如 `"abc"`） | `invalid_session_state`；零 mutation；**不是** `version_conflict` |
| I25 | Redis `estimated_tokens` 畸形字面（如 `"12.5"` / `""`） | `invalid_session_state`；零 mutation |
| I26 | List 头部消息 **畸形 JSON**（无法解析 / 缺 `message_id`） | `message_boundary_mismatch`；零 mutation |
| I27 | **Token clamp Case B**：current=100，archived=80，old_C=50，new_C=10 → raw=-20 → **0** | `success`；`HGET estimated_tokens` == 0；**不是** `invalid_session_state` |

**副作用负向断言（贯穿 I1–I27）：**

- 无 Kafka producer 调用（无 mock broker 或 assert 未调用）
- 无 Mongo client 调用
- 无 LLM client 调用

### 8.4 E2E Test

| 场景 | 预期 |
|---|---|
| 本任务 | **不适用**（无 HTTP Coordinator E2E；属 STM-013） |

### 8.5 失败注入与并发

| 场景 | 预期 |
|---|---|
| F1 | I5–I7、I20 failure zero mutation |
| F2 | I22 并发 duplicate → 单次 version 迁移 |
| F3 | I8/I21 retry 不 double-trim |

---

## 9. 验收标准

- [ ] 单 Lua 原子完成 §1.2.5 §991–1014 全部 mutation + 锁释放；禁止 TOCTOU
- [ ] `CompressionFinalizeStatus` 字面量稳定且与 §5.0 一致
- [ ] STM-007 `CompressionFinalizeLlmPayload` 直接 handoff；空字符串合法
- [ ] Token 公式 §1000–1006 在 Lua 内实现；Integration I18 Case A（500）与 I27 Case B（clamp 0）数值证明
- [ ] 畸形 Redis `compression_version` / `estimated_tokens` → `invalid_session_state`（I24–I25）；畸形 message JSON → `message_boundary_mismatch`（I26）
- [ ] `archived_message_tokens` 与 `pending_archive_estimated_tokens` 一致（Python ValidationError + Lua 四字段匹配 + `ARGV[11]==ARGV[7]` defense-in-depth）
- [ ] `LTRIM` 头部 `pending_archive_message_count`；M1–M4 边界证明
- [ ] `closing` + in-flight pending 允许 success；无 pending 的 closing → `session_closing`
- [ ] success 后旧 version 重试 → `version_conflict`；无 double-trim/bump
- [ ] 失败路径零 mutation；pending 不清空；失败不释放锁（Lua 内）
- [ ] 不修改 `message_ids` Set；不调用 Kafka/Mongo/LLM
- [ ] Unit + Contract + Redis Integration **27** 场景通过
- [ ] `uv run ruff check .` PASS；`uv run mypy src tests scripts` PASS
- [ ] 白名单外零业务 diff；不触碰 DEV-006/PR#13
- [ ] Review 无 P0/P1
- [ ] OI-004 / OI-005 仍为 open（不假装关闭）

---

## 10. 风险与阻塞项

### 10.1 OI-004（OPEN — 不阻塞 STM-008）

```yaml
id: OI-004
status: open
blocks_stm008: false
planner_rule: |
  archived_message_tokens 由调用方按 §987 从 archive messages（或 STM-006 写入时 WM 消息求和）供给；
  Lua 与 pending_archive_estimated_tokens 精确匹配；禁止 Mongo 重算 / 扩展 Archive schema。
  本任务不关闭 OI-004。
```

### 10.2 OI-005（OPEN — partial evidence）

```yaml
id: OI-005
status: open
blocks_stm008: false
planner_rule: |
  STM-006 提供进程内 Kafka 发布 partial evidence；STM-008 明确无 Kafka。
  不扩展为独立 Context Archive Service；不关闭 OI-005。
```

### 10.3 其他风险

| 风险 | 缓解 |
|---|---|
| §1.2.5 未写 status 步骤 vs §732 closing 禁压缩 | C1：`closing` 仅 in-flight（非空 pending）允许 |
| LTRIM 索引与 message JSON 解析 | Integration M1–M4 + 与 STM-005 batch_key 对齐 |
| 锁在 Lua 内释放 vs 协调层 `finally` | 成功仅 Lua 释放；失败保留锁给 STM-009 重试 |
| 设计文档冲突 | **BLOCKER**：无（公式 §1000–1006 明确；Amendment 001 闭合 I18 算术） |
| MUST_FIX 哨兵 | Round 1 HM-1/HM-2 **已闭合**（Amendment 001）；若实施中发现规格要求 Finalize 后 **不** 释放锁，或要求 Mongo 同步更新 — **停止并报告** |

### 10.4 OPEN_ISSUE / BLOCKER 清单

| 级别 | ID | 说明 |
|---|---|---|
| OPEN_ISSUE | OI-004 | open；不阻塞；不得私解 |
| OPEN_ISSUE | OI-005 | open；partial evidence；不得私解 |
| BLOCKER | — | **无** |
| MUST_FIX | — | Round 1 **已闭合**（Amendment 001）；待 Round 2 Plan Review |

---

## 11. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/STM-008-compression-finalize-lua"
expected_commits:
  - "docs(plan): add STM-008 compression finalize lua plan"
  - "feat(stm): add compression finalize lua and domain service"
  - "docs(status): record STM-008 implementation commit and PR"
  - "docs(status): complete STM-008 after PR merge"
out_of_scope_changes:
  - "STM-009 Coordinator / HTTP / STM-010 Close / STM-011"
  - "DEV-006 / PR #13"
  - "Kafka / Mongo / LLM 路径修改"
  - "compression_llm.py 修改"
  - "五命令正文"
release_phases:
  PLAN_LANDING: "main: docs(plan) + ff-only + create exact feat（PLAN_APPROVED 后 Release Operator）"
  IMPLEMENTATION_RELEASE: "feat only: whitelist add/commit/push/PR；禁 push main"
  POST_MERGE_CLEANUP: "PR MERGED 后 main docs(status): complete；删 exact feat"
```

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001（2026-08-10；Plan Review Round 2 remediation）

**触发**：Round 1 Plan Review `PLAN_REJECTED`；Human MUST_FIX HM-1（I18 算术与 §1000–1006 不一致）、HM-2（负值 clamp 语义）；吸收 Round 1 SHOULD_FIX。

**修订摘要**：

1. **HM-1 Token 公式闭合（§5.0 C5）**：新增五项变量权威定义表；修正 I18 Case A：`current=770, archived=300, old_C=50, new_C=80 → **new=500**（分解：50+300+420；事后 420+80=500）；引用 §182、§987–990、§1000–1006。
2. **HM-2 负值语义**：保留 `max(0,…)`（§1000–1006 权威）；Case B/I27：负 raw → clamp 0 仍 `success`；输入前置失败（畸形整数、半填充 pending、ARGV 不一致）与公式结果分离；`archived > current` 仍走 clamp，非 `invalid_session_state`。
3. **吸收 SHOULD_FIX**：
   - 畸形 Redis `compression_version` / `estimated_tokens` → `invalid_session_state`（非 `version_conflict`）；Integration I24–I25。
   - Lua `ARGV[11] == ARGV[7]` defense-in-depth；C8 步骤 7；Unit U1b。
   - 畸形 message JSON 于边界 → `message_boundary_mismatch`（显式）；Integration I26。
4. **测试计数**：Integration 23 → **27**（+I24–I27）；验收标准同步。
5. **保留**：单 Lua、同窗 lock、version +1 一次、无 double trim/bump、success 才清 pending、compare-and-delete 释锁、Redis-only、无 Kafka/Mongo/LLM/HTTP/STM-009。

**状态**：`planned`；`plan_review_round: 2`；待 Round 2 Plan Review。

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-10 23:01 UTC | Planner 初版 | 创建 Task Plan；progress/master_plan 规划态回写 | 未运行（规划-only） | OI-004/OI-005 open acknowledged；待 Plan Review |
| 2026-08-10 23:30 UTC | Planner Amendment 001 | HM-1/HM-2 + SHOULD_FIX；I18 修正；Integration 27 场景；`plan_review_round: 2` | 未运行（规划-only） | Round 1 MUST_FIX 闭合；待 Round 2 Plan Review |
| 2026-08-10 15:48 UTC | POST_MERGE_CLEANUP | PR #27 MERGED（`ac61680098d2ae2644bc8b990f057816c3218fca` mergedAt `2026-08-10T15:48:17Z`）；docs(status): complete on main；删 exact feat | n/a（治理） | STM-009 READY_FOR_PLANNING only；STM-011 READY_FOR_PLANNING only；STM-010 NOT ready；OI-004/OI-005 remain open |
| 2026-08-10 23:50 UTC | IMPLEMENTATION_RELEASE | implementation `d619ca2f7e2e20d2d944794c2ca21e8e6d5752ef`；PR #27 OPEN | scoped unit 20 / contract 4 / integration 27；full unit 393 / contract 80；ruff PASS；mypy PASS | 仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE` |
| 2026-08-10 23:45 UTC | Developer 实施 | 枚举/模型/服务；`compression_finalize.lua`（12 precondition + 9 mutation）；script + repository；unit 13 + contract 4 + integration 27 | unit+contract PASS；integration 27 PASS（Docker Redis）；full unit 393 / contract 80；ruff PASS；mypy PASS | C8 标题 10→12 步修正；无 Kafka/Mongo/LLM；OI-004/OI-005 remain open |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/domain/enums/compression_finalize.py` | 创建 |
| `src/memory_system/domain/models/compression_finalize.py` | 创建 |
| `src/memory_system/domain/services/compression_finalize_service.py` | 创建 |
| `src/memory_system/infrastructure/redis/scripts/compression_finalize.lua` | 创建 |
| `src/memory_system/infrastructure/redis/compression_finalize_script.py` | 创建 |
| `src/memory_system/infrastructure/redis/compression_finalize_repository.py` | 创建 |
| `src/memory_system/domain/enums/__init__.py` | 修改 |
| `src/memory_system/domain/models/__init__.py` | 修改 |
| `src/memory_system/domain/services/__init__.py` | 修改 |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 |
| `tests/unit/test_compression_finalize_models.py` | 创建 |
| `tests/unit/test_compression_finalize_lua_mapping.py` | 创建 |
| `tests/unit/test_compression_finalize_service.py` | 创建 |
| `tests/contract/test_stm008_contract.py` | 创建 |
| `tests/integration/test_compression_finalize_redis.py` | 创建 |
| `02_开发管理/tasks/STM-008-compression-finalize-lua.md` | 修改（C8 标题 + 执行记录） |
| `02_开发管理/progress.md` | 修改 |
| `02_开发管理/master_plan.md` | 修改 |

### 与原计划的差异

- C8 标题由「固定 10 步」修正为「固定 12 步」（与正文 12 precondition 一致）。
- 无业务语义偏差。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit/test_compression_finalize_*.py -q` | **PASS**（13） |
| Contract | `uv run pytest tests/contract/test_stm008_contract.py -q` | **PASS**（4） |
| Integration | `uv run pytest tests/integration/test_compression_finalize_redis.py -q` | **PASS**（27；Docker Redis） |
| E2E | — | **N/A** |
| Full unit | `uv run pytest tests/unit -q` | **PASS**（393） |
| Full contract | `uv run pytest tests/contract -q` | **PASS**（80） |
| Ruff | `uv run ruff check .` | **PASS** |
| Mypy | `uv run mypy src tests scripts` | **PASS** |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 2
review_report: null
```

### Git 记录

```yaml
branch: "feat/STM-008-compression-finalize-lua"
plan_commit: "fa3e1bf33e889dbb6180315eda896b954a02df8f"
implementation_commit: "d619ca2f7e2e20d2d944794c2ca21e8e6d5752ef"
implementation_commit_message: "feat(stm): add compression finalize lua and domain service"
status_record_committed: "a938220f8937b0e8af7e52dd34019ad1b558e789"
status_record_completed: "bdc2429fe63b9852de28e73cbd840de5c9d999d3"
pr: "#27"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/27"
pr_state: MERGED
merge_commit: "ac61680098d2ae2644bc8b990f057816c3218fca"
merged_at: "2026-08-10T15:48:17Z"
```

### 最终状态

`completed` — POST_MERGE_CLEANUP；单 Lua Finalize（12 precondition + 9 mutation）；token 公式 §1000–1006（I18 Case A new=500；I27 clamp 0）；safety/idempotency（precondition 零 mutation、version gate、无 double-trim/bump）；STM-007 `CompressionFinalizeLlmPayload` handoff；无 Kafka/Mongo/LLM；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2；OI-004/OI-005 remain open；feat 分支待删；**STM-009 READY_FOR_PLANNING only**（prerequisites SATISFIED；不得自动开始）。
