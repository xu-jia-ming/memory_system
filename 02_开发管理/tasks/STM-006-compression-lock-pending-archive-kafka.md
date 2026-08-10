# STM-006 Compression Lock / Pending Archive / Kafka Publish

## 1. 任务信息

```yaml
task_id: STM-006
task_name: Compression Lock, Pending Archive, Kafka context.archive.created
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
plan_review_round: 2
remediation: "Amendment 001 — Round 1 PLAN_REJECTED MF-1 Scheme A (PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED) + absorb SHOULD_FIX 1–5"
spec_sections:
  - "§1.2.1 Working Memory（pending_archive_* 字段；压缩锁 Key/SET NX EX/owner token/TTL/释放校验；压缩协调摘录中的 pending 写入与 Kafka 发布）"
  - "§1.2.2 Context Archive 生命周期（pending 复用；Archive 后发布事件；重复 archive_id 发布允许）"
  - "§1.2.4 Kafka Event 设计（topic/schema/Message Key/发布失败仅日志/人工补发依赖）"
  - "§1.2.6 Context Compression Trigger Strategy（锁获取；pending 复用与重发；Kafka 失败不阻塞压缩）"
  - "§1.2.7 Session 生命周期（closing 后普通压缩不得再执行；pending 保留语义）"
prerequisites:
  formal:
    - "STM-005 — SATISFIED（Mongo context_archive create/reuse；archive_id / archive_batch_key；PR #23 MERGED）"
  implementation_reuse:
    - "STM-001 — SATISFIED（WorkingMemoryMeta pending_archive_* 字段模型与 codec；compression_lock_ttl_seconds 配置校验）"
    - "STM-002 — SATISFIED（Session 创建；WM Hash 初始化 pending 为空/0；status=active）"
    - "STM-003 — SATISFIED（Redis Lua 模式；Integration 种子/compose test Redis）"
    - "DEV-002/DEV-005 — SATISFIED（KafkaSettings / KafkaProducerSettings；AppState.kafka_producer lifecycle）"
  baseline:
    - "Authoritative baseline（Orchestrator）：main == origin/main == e53a0f1e2e448a6a40445768f30c902173dd0921；working tree 仅规划文档 dirty（plan + progress + master_plan）允许；FULL_RUFF PASS；mypy PASS"
    - "本任务需要真实 Redis + 真实 Kafka（compose test 栈）；不需要 LLM / Finalize / HTTP / STM-011 脚本实现"
branch: "feat/STM-006-compression-lock-pending-archive-kafka"
created_at: "2026-08-10 12:14 UTC"
updated_at: "2026-08-10 13:25 UTC"
approval_gates:
  planning_docs: "Round 2 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0）；Human PLAN_APPROVED Amendment 001"
  implementation_plan: "status=tested；next_action=Code Review"
```

### 1.1 编排与门禁（本轮）

```yaml
start_existing_task: true
phase: plan_landing
plan_remediation_round: 2
human_gate_after_plan_review: satisfied
human_plan_approved: true
must_not_this_round:
  - "进入 Developer / 编写业务实现或测试语义（本 phase 仅 docs(plan) + feat 分支）"
  - "触碰 DEV-006 / PR #13"
  - "实现 STM-007 LLM / STM-008 Finalize / STM-009 Coordinator HTTP / STM-010 Close / STM-011 republish"
  - "私自解决 OI-004（Mongo estimated_tokens / token-boundary Contract）"
  - "声称 exactly-once Kafka delivery"
  - "把 Redis lock+pending + Kafka publish 伪装成跨系统原子事务"
```

---

## 2. 任务目标

交付 **压缩准备中间态** 能力：在已存在的 STM-005 Archive 与后续 STM-008 Finalize 之间，建立 **Working Memory pending 状态 + 压缩锁所有权 + `context.archive.created` 事件** 的可靠桥梁。

可验证交付：

1. **Compression lock**（§1.2.1 规则 6 / §1.2.6）：
   - Key：`memory:compression:lock:{user_id}:{session_id}`
   - Fresh acquisition：**仅** `SET key value NX EX`（value = 唯一 owner token；EX = `context.compression_lock_ttl_seconds`）
   - Pre-held token path：**保留**（方案 A），但受 `PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED` 约束（§5.0 C1 / C4）
   - 释放：校验 owner token 后删除（误删防护）；**MVP 不实现锁续期**
   - 已锁定 / 校验失败：稳定结果 `lock_not_acquired`（对应规格协调层 `skipped_lock` 语义；本任务不返回 HTTP）+ **ZERO_SIDE_EFFECT**
2. **`pending_archive_*` 写入**（复用 STM-001 既有四字段；**禁止**第二套 pending schema）：
   - `pending_archive_id` / `pending_archive_batch_key` / `pending_archive_message_count` / `pending_archive_estimated_tokens`
   - **必须**经 **单个 Redis Lua** 原子完成：**lock ownership 校验 + pending 前置条件 + 四字段 mutation**（禁止 Python `GET lock` → later write pending 的 TOCTOU）
3. **Kafka publish**（§1.2.4）— 仅在 Redis Lua **成功提交 pending** 之后允许：
   - Topic：`context.archive.created`（复用 `settings.kafka.topic`）
   - Message Key：`user_id`
   - Body **仅**规格六字段：`event_id`、`event_type`、`archive_id`、`user_id`、`session_id`、`created_time`
   - 发布失败：记录错误日志（含 `archive_id`）；**不**回滚 pending；**不**清 pending；**不**回滚 Mongo；**不**阻断后续压缩路径语义（§1.2.6 #10）
4. **领域编排服务**（进程内）：fresh acquire **或** pre-held token 校验通过后，进入**同一套** pending-state transition contract + 事件发布；返回稳定内部结果枚举 + `lock_owner_token`（成功/软失败路径 **不**自动释放锁，供后续 STM-007/008/009 继续；硬失败路径必须释放**本调用新获取**的锁）。
5. **测试**：Unit + Contract + Redis Integration + Kafka Integration/Contract + 失败注入 + pre-held token A/B/C/D + 恢复导向断言（见 §8）。

概念链（本任务止点）：

```text
STM-005 archive exists (archive_id / archive_batch_key)
        → fresh SET NX EX  OR  pre-held token (validated in Lua)
        → single Lua: ownership + pending_archive_* transition
        → ONLY IF Lua success: publish context.archive.created
        → leave Redis pending + lock ownership ready for STM-008 finalize
        → Redis→Kafka is NOT one distributed transaction (at-least-once / STM-011)
```

**本任务不得**完成 compression result writeback / `compression_version` bump / `LTRIM` / 清 pending。

---

## 3. 非目标（必须坚持；黑名单语义）

- Compression LLM / summary generation（**STM-007**）。
- Finalize Lua：`compression_version` bump、LTRIM、清 pending、写 `compressed_context`（**STM-008**）。
- Compression Coordinator 多轮策略、消息头部选择窗口、`POST /api/v1/memory/working/message` HTTP 接线（**STM-009**）。
- Session Close / Extraction / Retrieval / embedding。
- `scripts/republish_archive_event.py`（**STM-011**）——仅记录 **dependency**，不得提前实现；锁丢失后的既有 pending 补发留给 STM-011。
- Mongo `context_archive` create/reuse 重实现（**STM-005** 已完成）；本任务 **输入** 为已创建/复用的 archive 身份与 pending 元数据。
- 消息批次选择 / `max_archive_estimated_tokens` 切分算法。
- 重新 tokenize Mongo archive messages；扩展 Mongo archive schema 写入 `estimated_tokens`（**OI-004 仍 open — 不得私自解决**）。
- Outbox、独立 Event Publisher 服务、指数退避、DLT、自动补偿（§1.2.4 明确不实现）。
- 第二套 Kafka producer lifecycle（禁止绕开 `AppState.kafka_producer` / 既有 settings）。
- 跨系统「伪原子」：不得把 Redis ownership/pending + Kafka publish 伪装成单一事务。
- 操作 **DEV-006** / **PR #13**。
- 自动 Push / Merge / Rebase / Force Push。

---

## 4. 当前代码状态

### 4.1 前置只读证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `e53a0f1e2e448a6a40445768f30c902173dd0921` |
| `git rev-parse origin/main` | `e53a0f1e2e448a6a40445768f30c902173dd0921`（一致） |
| `git status --short` | 规划文档 dirty：`M progress.md` / `M master_plan.md` / `??` 本 Task Plan（允许） |
| formal STM-005 | `completed`（PR #23 MERGED） |
| formal DEV-OPS-007 | `completed`（PR #24 MERGED；baseline hygiene） |
| Plan Review Round 1 | `PLAN_REJECTED`；BLOCKER=0；MUST_FIX=1（MF-1 pre-held ownership）；用户选定方案 A |

### 4.2 可复用组件审计

| 交付物 | 路径 | STM-006 用法 |
|---|---|---|
| `WorkingMemoryMeta` pending 四字段 | `domain/models/working_memory.py` | **唯一** pending schema；Lua/HSET 字段名必须一致 |
| Redis codec | `infrastructure/redis/working_memory_codec.py` | **权威空值编码**：id/batch `""`↔`null`；count/tokens `"0"`↔`0`；Lua「pending 空」必须对齐 |
| WM keys | `infrastructure/redis/keys.py` | 扩展 **仅**增加 compression lock key helper |
| Session / message seed | STM-002/003 repository + Integration 模式 | Redis Integration 种子 |
| `create_or_reuse_context_archive` | STM-005 service | **不**在 STM-006 内调用生产路径必需；Integration 可选用其准备 archive 身份，或直接注入假 `archive_id` |
| `AppState.kafka_producer` | `infrastructure/runtime.py` | **唯一** producer；`acks=all` + `enable_idempotence=True`（settings 已有） |
| `KafkaSettings.topic` | `settings/models.py` | 默认 `context.archive.created`；**不**改 settings Contract |
| `context.compression_lock_ttl_seconds` | ContextSettings（420）+ validators | TTL 来源；**不**改校验公式 |
| Lua 加载模式 | `message_write_script.py` / `context_read_script.py` | 复制同构：load script text + `evalsha`/`eval` |

### 4.3 当前缺失

- compression lock key helper / acquire / release（**仅** repository 层 — 见 §6）
- pending_archive 写入 Lua（含 **同窗** lock ownership 校验）+ repository
- `context.archive.created` 事件模型与 publisher adapter
- compression preparation 领域服务与稳定结果枚举
- Redis/Kafka Integration 与失败注入 / pre-held token A–D 测试

### 4.4 与技术规格一致性

- 规格锁算法为 `SET NX EX` + owner token；**不得**发明 Redlock / fencing token 体系 / 续期。
- 规格流程图将 **Acquire Lock** 与 **Persist pending_archive_*** 分为两步：**fresh acquire** 仍为独立 `SET NX EX`；但 **任何** `pending_archive_*` mutation 前的 ownership 证明必须与 mutation 同属 **单个 Lua execution window**（Amendment 001 / MF-1）。禁止 Python 多 round-trip ownership check。
- §1.2.4 事件 schema **不含** `archive_batch_key` / `base_compression_version` / schema_version — **禁止**自行增加字段。
- `closing` 后「普通上下文压缩也不得再执行」（§1.2.3 / §1.2.7）— STM-006 preparation **仅**允许 `status=active`。
- Redis 内 ownership+pending 原子 ≠ Redis→Kafka 原子；跨系统 failure window 按 at-least-once / STM-011 处理。

### 4.5 前置任务检查

| 前置 | 状态 |
|---|---|
| STM-005 | **SATISFIED** |
| OI-004 | **open / unresolved** — acknowledged；**不阻塞** STM-006（token 来源见 §5.4 / §10.1） |
| OI-005 | **open** — 本任务 Planner 决议关闭命名歧义（§10.2）；**不**拆独立网络服务 |
| STM-011 | **planned** dependency only（补发路径；锁丢失后既有 pending 的 republish） |

---

## 5. 实现方案

### 5.0 十二项 Contract 闭合（Planner 权威结论；Amendment 001 修订）

#### C1 — Compression lock + `PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED`

| 项 | 结论（规格字面 + MF-1 方案 A） |
|---|---|
| Key | `memory:compression:lock:{user_id}:{session_id}` |
| Value | 唯一 owner token（UUID v4 字符串） |
| Fresh acquire | `SET key token NX EX ttl`；`ttl = context.compression_lock_ttl_seconds`；失败 → `lock_not_acquired`；**零** pending/Kafka 副作用 |
| Pre-held path | **保留**：调用方传入非空 `lock_owner_token` 时 **跳过** fresh `SET NX EX`，但 **必须**在 pending-state Lua 内验证 `GET lock == lock_owner_token` |
| Atomic verify | **PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED**：非空 token 时，在**任何** `pending_archive_*` mutation 前，于**同一个 Redis Lua atomic execution** 中验证 `current Redis lock value == lock_owner_token`；仅完全相等才允许继续 |
| Verify failure | lock key missing / TTL 已过期 / lock value 不同 / 不可解析 lock state → `lock_not_acquired` + **ZERO_SIDE_EFFECT**（不得写 pending、不得 publish Kafka、不得改 `compression_version`、不得 trim messages） |
| TOCTOU 禁止 | **禁止** Python `GET lock` → later Redis write pending（多 round-trip ownership check）。ownership validation 与 pending mutation preconditions **必须**位于同一 Lua execution window |
| TTL expiry | pre-held token ≠ 永久 ownership；仅当 Redis **当前** lock value == token 时有效。「caller 持有旧 token」不构成 ownership evidence；TTL 过期后旧 token **必须**失效；**不得**用旧 token 自动重新获取 ownership |
| Release | 仅当当前 value == owner token 时删除；否则不删；推荐 **单 Lua compare-and-del** |
| TTL / stale | 依赖 EX 过期；**不**续期（规格：MVP 不实现锁续期） |
| Crash / retry | 见 C10 / C12：锁丢失后可被他方 `SET NX`；旧 token 释放/校验失败（安全）；**不得**因旧 token 过期而破坏已存在 pending identity |

#### C2 — pending_archive_* fields

| 项 | 结论 |
|---|---|
| Schema | **仅** STM-001 四字段；禁止第二套 |
| 空值编码（对齐 codec） | `pending_archive_id` / `pending_archive_batch_key`：Redis `""` = null；`pending_archive_message_count` / `pending_archive_estimated_tokens`：`"0"` = 空；**半填充**（例如 id 非空但 batch 空，或 count 非 0 但 id 空）或非整数字面 → `invalid_session_state` |
| 何时写入 | Archive 已创建/复用后、Kafka 发布前；无 pending 时 Lua 写入全部四字段 |
| 已有 pending | **禁止**重新选择/覆盖为不同 Archive；相同 `pending_archive_id` + `pending_archive_batch_key` → 幂等成功（可跳过重写或写相同值）；冲突 → `pending_conflict` 零副作用 |
| 与 compression_version | **STM-006 不修改** `compression_version`（bump 属 Finalize / STM-008） |

#### C3 — Archive identity

| 项 | 结论 |
|---|---|
| 身份 | 复用 STM-005：`archive_id`、`archive_batch_key` |
| 输入 | **已创建/复用的 archive result 元数据**（调用方供给）；STM-006 **不**调用 Mongo create/reuse 作为必需路径 |
| 禁止 | 本任务内再实现第二套 Archive 持久化 |

#### C4 — Redis atomicity（lock ownership ∪ pending）

| 项 | 结论 |
|---|---|
| Fresh acquire vs pending Lua | **分两步但同 contract**：fresh = `SET NX EX`（Python/repository）；随后 **同一套** pending-state transition Lua（KEYS 含 meta + lock）校验 ownership + mutate pending。pre-held 跳过 SET，直接进入**同一 Lua** |
| 禁止双语义 | fresh 与 pre-held **不得**两套不同 pending semantics；最终都进入同一 pending-state transition contract |
| 禁止 | Python `GET`→`HSET` 拼 pending；Python `GET lock`→later pending write（TOCTOU） |
| Lua KEYS | `[meta_key, lock_key]` |
| Lua ARGV | expected_user_id, expected_session_id, archive_id, archive_batch_key, message_count, estimated_tokens, **expected_lock_owner_token** |
| **Lua precondition order（权威）** | 见下方固定顺序；失败按 approved result code；mutation 前零副作用 |
| 不在 Lua 内 | Kafka publish；`compression_version`；messages List；session `estimated_tokens`；`LTRIM` |
| Cross-system | Redis 内 ownership+pending 原子；**不**声称 Redis+Kafka 原子事务 |

**单个 Redis state-transition Lua 检查顺序（固定）：**

1. session meta EXISTS → 否则 `session_not_found`
2. user_id / session_id 身份匹配 → 否则 `session_not_found`
3. allowed session status：`status == active` → 否则 `session_closing`
4. **lock ownership**：`GET lock_key` 存在且 value **完全等于** `expected_lock_owner_token` → 否则 `lock_not_acquired`（含 missing / expired / mismatch）
5. current pending state：读四字段；畸形/半填充 → `invalid_session_state`；判定空（`""`/`0` 对齐 codec）或已占用
6. archive identity / batch consistency：若 pending 非空 → 同 id+batch 幂等 `success`，否则 `pending_conflict`
7. mutation：pending 空则 `HSET` 四字段 → `success`；幂等路径可不重写或写相同值

#### C5 — Session state

| 状态 | STM-006 preparation |
|---|---|
| `active` | **允许** |
| `closing` | **拒绝** → `session_closing`（规格：普通压缩不得再执行） |
| meta 缺失 / 身份不匹配 | `session_not_found` |

#### C6 — compression_version

- **读**：允许（例如日志/调用方已在 Archive 上记录 `base_compression_version`）；本服务 **不** bump、不校验写回条件（写回属 STM-008）。
- **写**：禁止修改 Hash 中的 `compression_version`。

#### C7 — estimated token accounting（OI-004）

| 项 | 结论 |
|---|---|
| `pending_archive_estimated_tokens` 来源 | **调用方供给**的 WM 消息级 `estimated_tokens` 求和（Redis 侧已有消息字段）；**不是** Mongo archive 重算 |
| 禁止 | 重新 tokenize Mongo messages；扩展 Mongo schema |
| OI-004 | **保持 open**；完整 token-boundary 留给 STM-010；本任务不关闭 OI-004 |

#### C8 — Kafka event schema

**仅** §1.2.4：

```json
{
  "event_id": "<uuid-v4>",
  "event_type": "context.archive.created",
  "archive_id": "<archive_id>",
  "user_id": "<user_id>",
  "session_id": "<session_id>",
  "created_time": <unix_ts>
}
```

| 项 | 结论 |
|---|---|
| Topic | `context.archive.created` |
| Message Key | `user_id`（bytes/string 按既有 aiokafka 用法） |
| **不包含** | `archive_batch_key`、`base_compression_version`、额外 schema/version 字段 |

#### C9 — Kafka publish semantics（最高风险）

| 场景 | MVP 语义 |
|---|---|
| Gate | **仅** Redis Lua pending transition **成功之后**才允许 Kafka publish |
| A pending 成功 → Kafka 成功 | `success`；pending 保留；锁保持 |
| B pending 成功 → Kafka 失败 | **记录错误日志（含 archive_id）**；pending **保留**；返回 `publish_failed`；**不**回滚 pending；**不**清 pending；**不**回滚 Mongo；**不**阻断后续压缩；恢复靠 **approved retry**（持有效锁）/ **STM-011** republish |
| C 重试（持有效锁 + 同 pending 身份） | 允许再次 publish 同一 `archive_id`（§1.2.2 #4 明确允许重复） |
| D ack 不确定 | 按 **at-least-once** 处理；可能重复；consumer/萃取幂等 + STM-011；**禁止**声称 exactly-once |
| Producer idempotence | settings 已 `enable_idempotence=True` + `acks=all` — 仅降低 producer 会话内重复，**不是**端到端 exactly-once |
| Outbox / DLT / 自动补偿 | **禁止实现**（§1.2.4） |
| Cross-system clarification | **不得**把 Redis lock validation/pending write + Kafka publish 伪装成一个原子事务；本任务只保证 Redis 内部 ownership validation + pending mutation 原子；Redis→Kafka 跨系统 failure window 按 at-least-once / recovery 处理 |

#### C10 — Idempotency / Retry / Ownership vs Recovery

| 维度 | 行为 |
|---|---|
| Lock NX | 同 session 并发：仅一个 `SET NX` 成功 |
| Pending create/modify | **需要**有效 ownership（fresh 成功 acquire **或** pre-held token Lua exact match） |
| Pending 同身份幂等 | 持有效锁时：幂等 `success`；可再 publish |
| Pending 冲突 | 不同 archive 撞现有 pending：`pending_conflict` |
| Kafka | 重复 publish **允许**（在 Lua 已成功 / pending 已就绪前提下） |
| Stale token after pending written | 旧 token → Lua `lock_not_acquired`；**ZERO_SIDE_EFFECT**（**不得**破坏已存在 pending identity）；**不得**跳过 ownership 校验去「直接 publish」 |
| Lock expired + pending exists | 区分：**创建/修改 pending 所需 ownership** vs **既有相同 pending archive 的恢复/republish**。STM-006 **不**实现无锁 republish；无有效锁时的补发留给 **STM-011**；本任务只保证 pending 字段足以被后续恢复识别 |
| Retry with fresh lock | 调用方可重新 `SET NX EX` 获得新 token，再走同套 pending Lua（同身份幂等）+ publish |

#### C11 — Failure result contract

稳定内部枚举（`StrEnum` 字面量；禁止自由文本成为业务 contract）：

| 字面量 | 含义 |
|---|---|
| `success` | pending 已就绪（新写或同身份幂等）且 Kafka publish 成功 |
| `publish_failed` | pending 已就绪但 Kafka 失败/异常；pending 保留；锁保持（若已持有） |
| `lock_not_acquired` | 未获得锁 **或** pre-held/ownership Lua 校验失败；零 pending/Kafka 副作用 |
| `session_not_found` | meta 缺失或身份不匹配 |
| `session_closing` | `status != active` |
| `pending_conflict` | 已存在不同 pending archive 身份 |
| `invalid_session_state` | Redis pending 字段畸形/半填充等 fail-closed（**不是**调用方输入 ValidationError） |

**输入校验 vs 枚举（SHOULD_FIX-5）：**

- 非法 `pending_archive_message_count`（≤0）、空 `archive_id` / `archive_batch_key`、空非 None token 字符串等 → **领域 `ValidationError`（或项目既有等价输入异常）**；**不**映射为 `invalid_session_state`
- `invalid_session_state` **仅**留给 Redis 态畸形（半填充 pending、非整数字面等）

#### C12 — Crash recovery（≥5 点）

| # | Crash point | Redis/Mongo | Retry | Duplicate risk | Recovery |
|---|---|---|---|---|---|
| 1 | Archive 已存在，未获锁 | Mongo 有 archive；无 pending；无锁 | 重试 acquire | 无 | 正常重试 |
| 2 | 获锁未写 pending | 锁存在；无 pending | 持锁方继续走 Lua；若进程死且 TTL 过期，他方获取锁 | 无 pending 重复 | 同请求 finally 释放或 TTL |
| 3 | pending 已写，未 publish | pending 完整；可能无事件 | **持有效锁**重试：幂等 pending + 再 publish；锁已过期 → STM-011 | 事件可能从未发出 | **STM-011** / 持新锁重试 |
| 4 | publish outcome unknown | pending 完整；事件可能已有 | 持有效锁再 publish | **at-least-once 重复允许** | 萃取幂等 + STM-011 |
| 5 | publish 成功但 caller 未收到成功 | pending + 事件均可能已存在 | 重试 → 幂等 pending + 重复事件允许 | 重复事件允许 | caller 以 Redis pending / 枚举为准；STM-011 兜底 |
| 6 | stale pre-held token | pending 可能已存在（他方或本方先前写入） | 旧 token → `lock_not_acquired`；pending **不变** | 无错误覆盖 | 新 acquire 或 STM-011 |

### Step 1 — 结果枚举与领域模型

- **文件**：
  - `src/memory_system/domain/enums/compression_preparation.py`（创建）
  - `src/memory_system/domain/models/compression_preparation.py`（创建）
  - `src/memory_system/domain/models/archive_created_event.py`（创建）
- **枚举**：`CompressionPreparationStatus`（§5.0 C11 字面量）。
- **输入** `CompressionPreparationInput`：
  - `user_id`, `session_id`
  - `archive_id`, `archive_batch_key`（非空；否则 ValidationError）
  - `pending_archive_message_count`（`int > 0`；否则 ValidationError）
  - `pending_archive_estimated_tokens`（`int >= 0`；调用方供给；OI-004）
  - `lock_owner_token: str | None` — `None` = fresh acquire；非空 = pre-held path（须 Lua atomic verify；空字符串非法 → ValidationError）
  - 可选 `event_created_time` / clock 注入
- **输出** `CompressionPreparationResult`：`status`、`lock_owner_token: str | None`、`event_id: str | None`、可选诊断字段（不得替代 status 枚举）。
- **事件模型** `ArchiveCreatedEvent`：严格六字段；`event_type` 常量字面量 `context.archive.created`。

### Step 2 — Compression lock helpers（白名单分层写死）

**SHOULD_FIX-1 决议（写死）：**

- **唯一** Redis lock 实现层：`src/memory_system/infrastructure/redis/compression_lock_repository.py`
- **不创建** `domain/services/compression_lock_service.py`（避免双实现）
- preparation service **直接**调用 repository 的 acquire / release

- **文件**：
  - `src/memory_system/infrastructure/redis/keys.py`（修改：新增 `compression_lock_key`）
  - `src/memory_system/infrastructure/redis/compression_lock_repository.py`（创建）
- **`acquire_compression_lock(redis, user_id, session_id, ttl_seconds, token_factory) -> str | None`**：
  - `SET lock_key token NX EX ttl`；成功返回 token；失败返回 `None`
- **`release_compression_lock(redis, user_id, session_id, token) -> bool`**：
  - **单 Lua compare-and-del**（防 TOCTOU）；规格要求校验 owner token — 非新锁算法
- **禁止**：锁续期、Redlock、把 fresh `SET NX EX` 合并进 pending Lua 冒充新 acquire 算法（acquire 与 ownership-in-pending-Lua 职责分离，但 pending Lua **必须**含 ownership 校验）。

### Step 3 — Pending archive Lua + repository（含 ownership 同窗校验）

- **文件**：
  - `src/memory_system/infrastructure/redis/scripts/pending_archive_write.lua`（创建）
  - `src/memory_system/infrastructure/redis/pending_archive_script.py`（创建）
  - `src/memory_system/infrastructure/redis/pending_archive_repository.py`（创建）
- **KEYS**：`[meta_key, lock_key]`
- **ARGV**：expected_user_id, expected_session_id, archive_id, archive_batch_key, message_count, estimated_tokens, expected_lock_owner_token
- **逻辑（必须；顺序 = §5.0 C4）**：
  1. EXISTS meta → 否则 `session_not_found`
  2. HGET user_id/session_id 匹配 → 否则 `session_not_found`
  3. status == `active` → 否则 `session_closing`
  4. GET lock == expected_lock_owner_token → 否则 `lock_not_acquired`
  5. 读现有 pending 四字段；畸形/半填充 → `invalid_session_state`
  6. 若 `pending_archive_id` 非空（非 `""`）：
     - 与 ARGV archive_id **且** batch_key 一致 → `success`（幂等）
     - 否则 → `pending_conflict`（零写）
  7. 若 pending 空（id/batch `""` 且 count/tokens `0`）：`HSET` 四字段 → `success`
  8. **禁止** 修改 `compression_version` / messages / session `estimated_tokens` / `compressed_context`；**不**更新 `updated_time`
- **Python**：解析 Lua 字面量 → `CompressionPreparationStatus` 子集映射。

### Step 4 — Kafka event publisher adapter

- **文件**：`src/memory_system/infrastructure/kafka/archive_created_publisher.py`（创建）；必要时 `src/memory_system/infrastructure/kafka/__init__.py`
- **依赖注入**：`AIOKafkaProducer`（来自 `AppState.kafka_producer` 或测试 fixture）；`topic: str`（`settings.kafka.topic`）
- **`publish_archive_created_event(producer, topic, event: ArchiveCreatedEvent) -> None`**：
  - `key = event.user_id.encode("utf-8")`
  - `value = JSON bytes`（六字段；紧凑稳定序列化）
  - `await producer.send_and_wait(topic, key=..., value=...)`
  - 异常向上抛或由服务捕获映射为 `publish_failed` + **error log 含 archive_id**
- **禁止**：新建 producer；改 `runtime.py` lifecycle（除非白名单证明必要 — **默认不改** `runtime.py`）。

### Step 5 — Compression preparation 领域服务

- **文件**：`src/memory_system/domain/services/compression_preparation_service.py`（创建）
- **`prepare_pending_archive_and_publish(*, redis, kafka_producer, topic, input, lock_ttl_seconds, clock, logger) -> CompressionPreparationResult`**：

  固定顺序（Amendment 001）：

  1. **输入校验**（ValidationError）：空 archive_id/batch_key、count≤0、token 为 `""` 等 — **不**进 Redis；**不**映射 `invalid_session_state`
  2. **锁 token 解析**：
     - `lock_owner_token is None` → `acquire_compression_lock`；失败 → `lock_not_acquired`（零副作用）；成功得到 `token`，标记 `acquired_in_this_call=True`
     - 非空 → 使用该 token；`acquired_in_this_call=False`（**不做**独立 Python GET；ownership 留给 Lua）
  3. **单 Lua pending transition**（传入 `expected_lock_owner_token=token`）→ 映射状态：
     - `lock_not_acquired` / `session_*` / `pending_conflict` / `invalid_session_state`：若 `acquired_in_this_call` 则 **release** 后返回；**禁止** Kafka
     - `success`（新写或幂等）→ 继续 publish
  4. **Kafka publish**（仅 Lua success 后）：
     - 构造 `ArchiveCreatedEvent`（`event_id=uuid4`，`created_time=clock()`）
     - 成功 → `success` + token + event_id（**不** release）
     - 失败 → log `archive_id` → `publish_failed` + token（**不** rollback pending；**不** release）
  5. **禁止**调用 Compression LLM / Finalize / Mongo insert；**禁止**无锁跳过校验的「恢复 publish」捷径（属 STM-011）

### Step 6 — 导出与测试

- 最小修改：`domain/enums/__init__.py`、`domain/services/__init__.py`、`infrastructure/redis/__init__.py`（仅当生产 import 需要）。
- 测试见 §8（含 A–D / Recovery 加厚 / Redis↔Kafka 隔离）。

---

## 6. 文件变更清单（exact writable whitelist）

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
| `src/memory_system/domain/enums/compression_preparation.py` | 创建 | `CompressionPreparationStatus` |
| `src/memory_system/domain/models/compression_preparation.py` | 创建 | Input/Result |
| `src/memory_system/domain/models/archive_created_event.py` | 创建 | Kafka 六字段事件模型 |
| `src/memory_system/domain/services/compression_preparation_service.py` | 创建 | pending + publish 编排 |
| `src/memory_system/infrastructure/redis/keys.py` | 修改 | `compression_lock_key` |
| `src/memory_system/infrastructure/redis/compression_lock_repository.py` | 创建 | SET NX EX / compare-and-del（**唯一** lock 实现层） |
| `src/memory_system/infrastructure/redis/scripts/pending_archive_write.lua` | 创建 | ownership 同窗校验 + 原子 pending 四字段 |
| `src/memory_system/infrastructure/redis/pending_archive_script.py` | 创建 | 加载/执行 Lua |
| `src/memory_system/infrastructure/redis/pending_archive_repository.py` | 创建 | repository 封装 |
| `src/memory_system/infrastructure/kafka/__init__.py` | 创建 | 包初始化（若需要） |
| `src/memory_system/infrastructure/kafka/archive_created_publisher.py` | 创建 | publisher adapter |
| `src/memory_system/domain/enums/__init__.py` | 修改 | 最小导出 |
| `src/memory_system/domain/models/__init__.py` | 修改 | 最小导出（若需要） |
| `src/memory_system/domain/services/__init__.py` | 修改 | 最小导出 |
| `src/memory_system/infrastructure/redis/__init__.py` | 修改 | 最小导出 lock key / helpers |
| `tests/unit/test_compression_lock.py` | 创建 | lock acquire/release/token mismatch |
| `tests/unit/test_pending_archive_lua_mapping.py` | 创建 | Lua 结果映射 / 畸形 / ownership fail |
| `tests/unit/test_archive_created_event.py` | 创建 | 序列化六字段；禁止多余字段 |
| `tests/unit/test_compression_preparation_service.py` | 创建 | 编排：成功/锁失败/冲突/publish 失败/pre-held A–C / ValidationError |
| `tests/contract/test_stm006_contract.py` | 创建 | 枚举字面量 + 事件 schema + **TOCTOU guard（D）** |
| `tests/integration/test_compression_preparation_redis.py` | 创建 | 真实 Redis Integration（**不依赖 Kafka broker**） |
| `tests/integration/test_archive_created_kafka.py` | 创建 | 真实 Kafka topic/schema/key + 失败注入 |
| `02_开发管理/tasks/STM-006-compression-lock-pending-archive-kafka.md` | 修改 | 本 Task Plan（Amendment 001） |
| `02_开发管理/progress.md` | 修改 | 规划态字段 |
| `02_开发管理/master_plan.md` | 修改 | STM-006 登记 + CHANGE-038/039 |
| `02_开发管理/open_issues.md` | 修改（可选） | **仅**当 Plan Review / 人工批准后落盘 OI-005 决议；本规划轮次 **可不改**；若改则仅 OI-005 决议段 |

**明确不在白名单（写死）：**

- `src/memory_system/domain/services/compression_lock_service.py` — **不创建**（SHOULD_FIX-1）

**白名单外禁止修改**（含但不限于）：

- `src/memory_system/infrastructure/runtime.py`（默认）
- `src/memory_system/settings/**`（TTL/topic 已存在）
- STM-003/004/005 业务文件与既有测试语义
- `api/routes/**`、Finalize Lua、LLM client、`scripts/republish_archive_event.py`
- `scripts/migrations/**`、compose、`.env.example`、五命令正文、DEV-006/PR#13

---

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性（Redis） | **适用（收窄）** | ownership 校验 + pending 四字段 mutation **同 Lua**；fresh `SET NX EX` 与 pending Lua 分步但同 contract |
| 原子性（跨系统） | **不适用** | pending 与 Kafka **非**分布式事务；failure window 显式承认 |
| 幂等 | **适用** | 同 pending 身份 + 有效锁 → success；Kafka 重复允许 |
| 并发 | **适用** | 锁 NX 互斥；并发 contenders 仅一方获锁；Integration 证明 |
| 版本冲突 | **不适用（本任务）** | 不 bump `compression_version`；写回冲突属 STM-008 |
| 用户隔离 | **适用** | lock/meta key 含 `user_id`+`session_id`；Kafka key=`user_id` |
| 部分失败 | **适用** | Kafka 失败保留 pending（`publish_failed`）；硬失败释放本调用新获锁；stale token 不破坏 pending |
| 进程异常恢复 | **适用** | 见 §5.0 C12；依赖 TTL + 持锁重试 + STM-011；无自动 Outbox |

---

## 8. 测试计划

### 8.1 Unit Test

| 场景 | 预期 |
|---|---|
| U1 输入校验 | 非法 count / 空 archive_id → **ValidationError**；不调用 Redis/Kafka |
| U2 lock 结果映射 | SET 成功/失败 → token / `lock_not_acquired` |
| U3 release token mismatch | 不删除他人锁 |
| U4 pending 状态映射 | success / conflict / closing / not_found / invalid / **lock_not_acquired（Lua ownership）** |
| U5 事件序列化 | 仅六字段；`event_type` 字面量正确 |
| U6 publish 失败映射 | fake producer raise → `publish_failed`；pending 不被服务回滚（mock 断言无 clear 调用） |
| U7 重试幂等 | 已有相同 pending + 有效 token → success 路径；再 publish 可调用 |
| U8 畸形 Redis 字段 | 半填充/非整数 → `invalid_session_state`（非 ValidationError） |
| U9 **A stale pre-held** | mock：lock value=token_B，caller token_A → `lock_not_acquired`；无 pending 写；无 publish |
| U10 **B expired pre-held** | mock：lock missing + 旧 token → `lock_not_acquired`；ZERO_SIDE_EFFECT |
| U11 **C valid pre-held** | mock：lock value==token → pending transition + publish 路径 |

### 8.2 Contract Test

| 场景 | 预期 |
|---|---|
| C1 `CompressionPreparationStatus` 字面量集合稳定 | 与 §5.0 C11 一致 |
| C2 `ArchiveCreatedEvent` JSON keys 恰好六字段 | 无 `archive_batch_key` / `base_compression_version` |
| C3 topic 默认名 | `context.archive.created` 与 settings 默认一致（读常量/模型默认，不改 settings） |
| C4 **D TOCTOU guard** | 源码/契约断言：production pending transition 路径为 **single Lua**（KEYS 含 lock+meta）；ownership check 与 pending mutation **非**两个独立 Redis round-trip；禁止 preparation service 在 pending 写前单独 `GET` lock 作为所有权依据 |

### 8.3 Redis Integration（**不依赖 Kafka broker** — SHOULD_FIX-4）

本文件 fixture **仅**真实 Redis；Kafka publisher 用 fake/mock（断言 publish 调用与否）。真实 Kafka 场景集中在 §8.4。

| 场景 | 预期 |
|---|---|
| I1 合法 session lock+pending success | 锁存在；pending 四字段精确；mock publish 被调用 |
| I2 missing session | `session_not_found`；无锁残留（或未获锁） |
| I3 status=closing | `session_closing`；无 pending 写 |
| I4 lock contention | 仅一方进入 pending success；另一方 `lock_not_acquired` |
| I5 同 archive 重复准备 | 幂等 success；pending 不被破坏 |
| I6 冲突 pending | `pending_conflict`；原 pending 不变 |
| I7 畸形/半填充 pending | `invalid_session_state` |
| I8 success 后精确字段 | id/batch_key/count/tokens 与输入一致；空值编码对齐 codec |
| I9 **无** `compression_version` bump | version 与准备前相同 |
| I10 **无** message trimming | List 长度不变 |
| I11 失败零副作用 | lock_not_acquired / conflict 不写 pending；不调 publish |
| I12 并发 contenders | 仅一个 ownership（lock value 唯一） |
| I13 **A stale pre-held** | owner A token_A → 过期/替换为 owner B token_B → caller A 用 token_A → `lock_not_acquired`；pending unchanged；**no** Kafka publish |
| I14 **B expired pre-held** | lock key 不存在 + 旧 token → `lock_not_acquired` + ZERO_SIDE_EFFECT |
| I15 **C valid pre-held** | Redis value == token → pending transition 成功；mock publish 调用 |

### 8.4 Kafka Integration / Contract

依赖真实 Kafka（及按需 Redis）。与 §8.3 文件隔离，避免 Redis-only 门禁被 Kafka 可用性绑架。

| 场景 | 预期 |
|---|---|
| K1 exact topic | 消费/检查 `settings.kafka.topic` |
| K2 exact schema | 六字段；类型正确 |
| K3 archive identity | `archive_id` 匹配 |
| K4 event key | `user_id` |
| K5 publish success | `success` + 可消费到消息 |
| K6 publish failure | 可控注入 → `publish_failed`；pending 仍在 |
| K7 duplicate/retry | 再次 publish 允许（可观测两条或 mock 两次 send） |
| K8 无无关 topic | 不写入其他 topic 名 |
| K9 Lua 未成功时 | ownership/pending 失败路径 **零** Kafka 消息 |

### 8.5 Recovery-oriented（加厚 — SHOULD_FIX-3）

| 场景 | 预期 |
|---|---|
| R1 pending 已写 + Kafka 失败 | Redis 仍可读到 archive_id/batch_key；状态可被后续补发/重试识别；**不**丢失 archive identity |
| R2 publish_failed + **同有效 token** 重试 | 再次 publish 可成功（或再次失败仍保留 pending）；pending 不被清 |
| R3 publish_failed + **stale token** | `lock_not_acquired`；pending **不变**；**不得**跳过 ownership 校验直接 publish |
| R4 pending 存在 + lock TTL 过期 | STM-006 不实现无锁 republish；pending 仍完整可读（供 STM-011） |

### 8.6 失败注入与并发

| 场景 | 预期 |
|---|---|
| F1 fake/mock producer 抛错（Unit） | `publish_failed` |
| F2 真实 Kafka success（Integration） | K5 |
| F3 注入 publish exception（Integration：wrapper/monkeypatch `send_and_wait`） | 不得仅靠「关掉 Kafka」作为唯一手段 |
| F4 并发双准备 | I4/I12 |

### 8.7 E2E Test

| 场景 | 预期 |
|---|---|
| 本任务 | **不适用**（无 HTTP/Coordinator E2E；属 STM-013） |

### 8.8 Kafka runtime 约束（测试与实现）

- 复用 `AIOKafkaProducer` 配置：`acks` / `enable_idempotence` / compression / timeouts（settings）。
- Integration：compose test 栈启动 `kafka`（及 Redis）；producer start/stop 在 fixture 内管理，或复用 runtime helpers —— **禁止**第二套长期全局 producer 单例分叉。
- Topic 由既有 migration `004_initial_kafka_topics` 创建；本任务 **不** 新 migration。
- Redis Integration（§8.3）与 Kafka Integration（§8.4）**文件与依赖隔离**。

---

## 9. 验收标准

- [ ] Compression lock：`SET NX EX` + owner token + TTL + token-checked release；无续期
- [ ] Pre-held path 保留且满足 `PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED`；TTL 过期旧 token 失效
- [ ] pending 四字段经 **单 Lua**（含 lock ownership 同窗校验）写入/幂等/冲突；无第二 schema；空值对齐 STM-001 codec
- [ ] **禁止 TOCTOU**：production path 无 Python GET-lock-then-write-pending；Contract D 通过
- [ ] fresh 与 pre-held 进入**同一套** pending-state transition contract
- [ ] 输入为已有 archive 身份；无 Mongo create/reuse 重实现；无 Finalize/LLM/HTTP/STM-011
- [ ] Kafka 事件：仅 Lua success 后 publish；exact topic + 六字段 schema + key=`user_id`
- [ ] `publish_failed` 保留 pending；日志含 `archive_id`；不声称 exactly-once；不伪装 Redis+Kafka 原子事务
- [ ] stale/expired pre-held：`lock_not_acquired` + ZERO_SIDE_EFFECT；不破坏已有 pending
- [ ] 不修改 `compression_version`；不 LTRIM；不清 pending（成功路径）
- [ ] 仅 `active` 可准备；`closing` → `session_closing`
- [ ] ValidationError vs `invalid_session_state` 边界正确
- [ ] Unit / Contract / Redis Integration / Kafka Integration 计划场景通过（含 A–D / R1–R4）
- [ ] `uv run ruff check .` PASS；`uv run mypy src tests scripts` PASS
- [ ] 白名单外零业务 diff；无 `compression_lock_service.py`；不触碰 DEV-006/PR#13
- [ ] Review 无 P0/P1
- [ ] OI-004 仍为 open（不假装关闭）

---

## 10. 风险与阻塞项

### 10.1 OI-004（OPEN — 不阻塞 STM-006）

```yaml
id: OI-004
status: open
blocks_stm006: false
planner_rule: |
  pending_archive_estimated_tokens 由调用方从 WM 消息 estimated_tokens 求和供给；
  禁止 Mongo 重算 / 扩展 Archive schema；完整 token-boundary 留 STM-010。
```

### 10.2 OI-005（Planner 决议 — 命名；建议随实现/完成治理关闭）

```yaml
id: OI-005
status: open  # 文档状态本轮可不改；决议如下
blocks_stm006: false
planner_resolution: |
  §1.2.4「Memory API / Context Archive Service」为生产者称谓；
  MVP 事件发布在 memory-api 进程内完成（与 §1.2.5 Compression Service 进程内一致）；
  不创建独立网络「Context Archive Service」进程或 HTTP。
  是否改变技术规格: 否（澄清工程落点，不改 Contract 字段）。
```

### 10.3 依赖（非阻塞实现，但是恢复模型一部分）

| ID | 说明 |
|---|---|
| STM-011 | `republish_archive_event.py` — pending 成功但事件丢失、**或锁已过期无法再经 STM-006 publish** 时的人工补发；本任务 **不实现** |
| STM-007/008/009 | 消费本任务留下的 lock token + pending 态 |

### 10.4 其他风险

- Round 1 已拒绝「pre-held 可跳过 ownership 校验」— Amendment 001 闭合。
- 设计文档：fresh acquire 与 pending 分步 vs ownership+pending 同 Lua — **已按 MF-1 闭合**；不要求把 `SET NX EX` 并入 pending Lua。
- 当前代码冲突：无（功能缺失）。
- API/Schema 变化：无 HTTP；Kafka schema 不扩展。
- **BLOCKER**：无（在遵守 OI-004 不关闭、Kafka at-least-once、跨系统非原子前提下）。
- **MUST_FIX（预置哨兵）**：若实施中发现规格要求事件必须含 `archive_batch_key`，或要求无锁 republish 必须在 STM-006 内实现 — **停止并报告**，不得猜。

### 10.5 OPEN_ISSUE / MUST_FIX / BLOCKER 清单（供 Plan Reviewer Round 2）

| 级别 | ID | 说明 |
|---|---|---|
| OPEN_ISSUE | OI-004 | 仍 open；不阻塞；不得私解 |
| OPEN_ISSUE | OI-005 | 命名；Planner 决议进程内；建议后续治理落盘 resolved |
| BLOCKER | — | **无** |
| MUST_FIX | MF-1（Round 1） | **已在 Amendment 001 闭合（方案 A）** — 待 Round 2 复审确认 |
| SHOULD_FIX | SF-1–5（Round 1） | **已吸收**（lock 分层写死；codec 空值；Recovery 加厚；Redis/Kafka 隔离；ValidationError vs enum） |

---

## 11. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/STM-006-compression-lock-pending-archive-kafka"
expected_commits:
  - "docs(plan): add STM-006 compression lock pending archive kafka plan"
  - "feat(stm): add compression lock pending archive and kafka publish"
  - "docs(status): record STM-006 implementation commit and PR"
  - "docs(status): complete STM-006 after PR merge"
out_of_scope_changes:
  - "STM-007/008/009/010/011 实现"
  - "DEV-006 / PR #13"
  - "settings/runtime lifecycle 无必要修改"
  - "五命令正文"
  - "OI-004 Contract 臆造关闭"
  - "compression_lock_service.py（明确不创建）"
release_phases:
  PLAN_LANDING: "main: docs(plan) + ff-only + create exact feat（仅 Release Operator；PLAN_APPROVED 后）"
  IMPLEMENTATION_RELEASE: "feat only: add/commit/push/PR；禁 push main"
  POST_MERGE_CLEANUP: "PR MERGED 后 main docs(status): complete；删 exact feat"
```

Release Operator：**PLAN_LANDING**（main `docs(plan)` + ff-only + create exact feat）；plan_commit 以落地后 `git rev-parse HEAD` 为准。

---

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- **日期**：2026-08-10 12:30 UTC
- **原计划**：Round 1 初版（`updated_at=2026-08-10 12:14 UTC`）— pre-held `lock_owner_token` 可「视为已持有」且「本任务可不做 GET 校验」；lock 与 pending 「不要求同 Lua」仅约束 pending 四字段单 Lua；lock 层 `compression_lock_service.py` vs repository 二选一未写死。
- **修改内容**：
  1. **MF-1 方案 A**：引入 `PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED`；pending Lua KEYS=`[meta, lock]`；ownership 与 pending mutation 同窗；禁止 TOCTOU；TTL 语义收紧；fresh 与 pre-held 同 pending contract。
  2. 固定 Lua precondition 顺序（meta → identity → status → lock → pending state → archive consistency → mutation）。
  3. Cross-system：显式声明 Redis 内原子 ≠ Redis+Kafka 事务；Kafka 仅 Lua success 后。
  4. Retry：区分 ownership（创建/修改 pending）与既有 pending 恢复/republish（STM-011）；stale token 不破坏 pending。
  5. 测试：强制 A/B/C/D + Recovery R1–R4。
  6. **吸收 SHOULD_FIX 1–5**：lock 仅 repository；codec 空值对齐；Recovery 加厚；Redis/Kafka Integration 隔离；ValidationError vs `invalid_session_state`。
  7. 白名单删除 `compression_lock_service.py`；Step 2/5/§6/§8/§9/§10 同步。
- **修改原因**：Plan Review Round 1 = `PLAN_REJECTED`（MUST_FIX=1）；用户选定方案 A。
- **是否影响技术规格**：**否**（收紧实现约束以符合规格 lock owner 校验 + Lua pending 写入；不改 API/Schema/错误码字面）。
- **审批状态**：Round 2 Plan Reviewer `PLAN_APPROVED`（BLOCKER=0 MUST_FIX=0）；Human `PLAN_APPROVED`（2026-08-10T12:35:00Z）

---

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-10 12:14 UTC | Planner 初版 | 创建 Task Plan；progress/master_plan 规划态回写 | 未运行（规划-only） | OI-004 open acknowledged；OI-005 进程内决议；Kafka at-least-once；待 Plan Review |
| 2026-08-10 12:30 UTC | Planner Amendment 001（Round 2 remediation） | 修订 Task Plan（MF-1 方案 A + SF-1–5）；progress/master_plan 规划态同步 | 未运行（规划-only） | Round 1 PLAN_REJECTED 闭合中；待 Round 2 复审；零 Git 写；未实施 |
| 2026-08-10 12:35 UTC | Human + Plan Review Round 2 | status→approved；Human PLAN_APPROVED Amendment 001；Round 2 BLOCKER=0 MUST_FIX=0 | 未运行（治理） | 待 Release Operator PLAN_LANDING；仍不得实施 |
| 2026-08-10 12:40 UTC | Developer start | status→in_progress；分支 `feat/STM-006-compression-lock-pending-archive-kafka`；HEAD=`6dd97278ec82ebb24dcb21c2c5a58118a65db0cd` | 未运行（实施开始） | 按白名单实施；Human SF：same identity + inconsistent count/tokens → fail-closed `pending_conflict` |
| 2026-08-10 13:25 UTC | Developer implement+test | 白名单内实现 lock/pending Lua/Kafka/service + unit/contract/integration；status→implemented→tested | 见 §14 | Human SF accounting fail-closed；无 compression_lock_service.py；未改 runtime/settings；未 commit |

---

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/domain/enums/compression_preparation.py` | 创建 |
| `src/memory_system/domain/models/compression_preparation.py` | 创建 |
| `src/memory_system/domain/models/archive_created_event.py` | 创建 |
| `src/memory_system/domain/services/compression_preparation_service.py` | 创建 |
| `src/memory_system/infrastructure/redis/keys.py` | 修改（`compression_lock_key`） |
| `src/memory_system/infrastructure/redis/compression_lock_repository.py` | 创建 |
| `src/memory_system/infrastructure/redis/scripts/pending_archive_write.lua` | 创建 |
| `src/memory_system/infrastructure/redis/pending_archive_script.py` | 创建 |
| `src/memory_system/infrastructure/redis/pending_archive_repository.py` | 创建 |
| `src/memory_system/infrastructure/kafka/__init__.py` | 修改导出 |
| `src/memory_system/infrastructure/kafka/archive_created_publisher.py` | 创建 |
| `src/memory_system/domain/enums/__init__.py` | 最小导出 |
| `src/memory_system/domain/models/__init__.py` | 最小导出 |
| `src/memory_system/domain/services/__init__.py` | 最小导出 |
| `src/memory_system/infrastructure/redis/__init__.py` | 最小导出 |
| `tests/unit/test_compression_lock.py` | 创建 |
| `tests/unit/test_pending_archive_lua_mapping.py` | 创建 |
| `tests/unit/test_archive_created_event.py` | 创建 |
| `tests/unit/test_compression_preparation_service.py` | 创建 |
| `tests/contract/test_stm006_contract.py` | 创建 |
| `tests/integration/test_compression_preparation_redis.py` | 创建 |
| `tests/integration/test_archive_created_kafka.py` | 创建 |
| `02_开发管理/tasks/STM-006-compression-lock-pending-archive-kafka.md` | 执行记录 |
| `02_开发管理/progress.md` | 状态回写 |
| `02_开发管理/master_plan.md` | 状态回写 |

### 与原计划的差异

见 §12 Amendment 001（相对 Round 1 初版）。

**Human Round 2 / SF 幂等闭合（执行证据）**：Lua step 6 在 same `archive_id`+`archive_batch_key` 时仍须校验 `pending_archive_message_count` 与 `pending_archive_estimated_tokens`；不一致 → `pending_conflict`（不覆盖旧值；不新增枚举）。规格要求复用既有 Pending 绑定（含 count 用于后续 LTRIM），故 accounting 不一致 fail-closed。Integration：`test_i5b_same_identity_inconsistent_accounting_fail_closed` PASS。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| STM-006 scoped unit | `uv run pytest tests/unit/test_compression_lock.py tests/unit/test_pending_archive_lua_mapping.py tests/unit/test_archive_created_event.py tests/unit/test_compression_preparation_service.py -q` | **26 passed** |
| STM-006 contract | `uv run pytest tests/contract/test_stm006_contract.py -q` | **4 passed** |
| Redis integration | `uv run pytest tests/integration/test_compression_preparation_redis.py -q` | **16 passed** |
| Kafka integration | `uv run pytest tests/integration/test_archive_created_kafka.py -q` | **4 passed** |
| Full unit | `uv run pytest tests/unit -q` | **349 passed** |
| Full contract | `uv run pytest tests/contract -q` | **72 passed** |
| Ruff | `uv run ruff check .` | **PASS** (All checks passed) |
| Mypy | `uv run mypy src tests scripts` | **PASS** (Success: no issues found in 154 source files) |
| E2E | N/A | 不适用（本任务无 HTTP E2E） |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 0
review_report: null
plan_review_round_1: PLAN_REJECTED
plan_review_round_1_must_fix: MF-1
plan_review_round_2: PLAN_APPROVED
plan_review_round_2_blocker: 0
plan_review_round_2_must_fix: 0
human_plan_approved: true
human_plan_approved_at: "2026-08-10T12:35:00Z"
```

### Git 记录

```yaml
branch: "feat/STM-006-compression-lock-pending-archive-kafka"
plan_commit: "6dd97278ec82ebb24dcb21c2c5a58118a65db0cd"
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`tested`
