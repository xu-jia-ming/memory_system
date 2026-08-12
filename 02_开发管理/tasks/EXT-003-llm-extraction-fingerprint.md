# EXT-003 LLM Extraction + Fingerprint

## 1. 任务信息

```yaml
task_id: EXT-003
task_name: LLM Extraction + Fingerprint
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "f112d12d28d34de18c637a661a857fcb9f0a401f"
branch: "feat/EXT-003-llm-extraction-fingerprint"
created_at: "2026-08-12 03:05 UTC"
updated_at: "2026-08-12 14:30 UTC"
spec_sections:
  - "§1.2.1 记忆萃取整体流程与 Context Archive 唯一原始来源"
  - "§1.2.3 memory_extraction_task.extraction_result"
  - "§2.1.3 Memory Extraction Task 数据库设计"
  - "§2.1.4 Kafka 消费与任务幂等（仅复用既有边界）"
  - "§2.1.5 Context Archive 读取与预处理（ExtractionReadyArchive 输入）"
  - "§2.1.6 LLM Structured Extraction 设计"
  - "§2.1.7 抽取结果校验与标准化"
  - "§2.1.8 时间标准化（仅消费已定义字段，不实现图谱语义）"
  - "§2.1.15 失败处理"
  - "§2.1.16 MVP 实现边界（本任务仅实现 LLM/结果边界）"
  - "§3.9 DeepSeek LLM / Structured Output / AsyncOpenAI"
  - "Appendix A Amendment EXT-002-004（first-person deferred; ExtractionReadyArchive handoff）"
  - "Appendix B Amendment EXT-003（authoritative MVP contract closure）"
prerequisites:
  formal:
    - "EXT-002 — SATISFIED/completed; merge 59e9f7f0cf6effd34d1f13ad022f9b9eb00b8f2d; normalized+redacted ExtractionReadyArchive handoff"
    - "STM-007 — SATISFIED/completed; merge 7a72b3a4c159032a411bd48dc920e52973ddab3e; existing LLMClient/DeepSeek/Fake conventions"
    - "EXT-001 — SATISFIED/completed; merge ae346dd27cda39f93fa38b7316ec17559df217ef; task idempotency, PipelineTerminalDecision, terminal persistence/offset gate"
  implementation_reuse:
    - "Existing ExtractionReadyArchive and EXT-002 strict read/preprocess/redaction boundary"
    - "Existing LLMClient protocol, AsyncOpenAI DeepSeek client conventions, LlmServiceError, FakeLlmClient"
    - "Existing memory_extraction settings and LLM extraction settings; no second config stack"
    - "Existing memory_extraction_task extraction_result field and repository mapping"
  baseline_evidence:
    branch: "main"
    head: "f112d12d28d34de18c637a661a857fcb9f0a401f"
    working_tree_at_planning_start: "clean before planning whitelist writes"
approval_gates:
  planning: "PLAN_APPROVED"
  approval_posture: "Round 2 Plan Review PLAN_APPROVED (BLOCKER=0 MUST_FIX=0 SHOULD_FIX=1); human PLAN_APPROVED granted; SF-1 MVP_LOCAL_DECISION recorded; Developer authorized post-PLAN_LANDING"
  amendment_recorded: true
  amendment_id: "EXT-003-002"
  human_plan_approved: true
  developer_authorized: true
  reviewer_authorized: false
  release_operator_authorized: false
release_phases:
  PLAN_LANDING: "NORMAL only; after PLAN_APPROVED, Release Operator may land approved planning files on main and create the exact feature branch"
  IMPLEMENTATION_RELEASE: "only after all blocking Open Issues are resolved and implementation is approved; feature branch whitelist only; no push to main"
  POST_MERGE_CLEANUP: "only after a verified MERGED PR; exact feature branch cleanup and status completion on main"
```

### 1.1 本轮门禁与停止条件

```yaml
phase: planning_only
must_not_this_round:
  - "编写业务实现、测试实现、Migration、配置或依赖"
  - "进入 Developer、Code Reviewer、Commit Recorder 或 Release Operator"
  - "修改 EXT-001 Kafka topic、consumer group、partition、offset、task state 或 terminal persistence semantics"
  - "修改 `PipelineTerminalDecision` 模型以供未来 EXT-004 编排"
  - "实现 EXT-004 entity alignment、Neo4j、reconciliation、retrieval indexing 或 Evidence graph write"
stop_if:
  - "任何实现步骤需要改变业务 Schema、error code、state machine、retry/recovery contract 或 dependency"
  - "任何实现步骤需要把 raw/pre-redaction content 放入 prompt、日志、exception、fixture 或 durable result"
  - "public `LLMClient` contract 变更不可避免且未获 authoritative amendment"
```

## 2. 任务目标

在 EXT-002 已完成的 `ExtractionReadyArchive` 边界之后，提供一次长期记忆 Structured Extraction 的严格、可追溯、可重放的应用能力，并在进入后续实体对齐之前产生 durable `extraction_result` 所需的候选结果和确定性 `candidate_fingerprint`。

本任务的可验证目标：

1. 消费且只消费 `ExtractionReadyArchive` 的精确输入字段：`archive_id`、`user_id`、`session_id`、按 Archive 原顺序排列的 messages；每条 message 只有 `message_id`、`role`、normalized+redacted `content`、`timestamp`。
2. 保留消息来源、`message_id`、role、timestamp 和数组顺序；first-person binding 不在本任务实现或依赖，沿用 Amendment EXT-002-004 的 deferred/out-of-scope 结论。
3. 在 `memory_extraction` 的既有配置下执行 LLM Structured Output：`memory_extraction_v1`、120 秒、8000 estimated tokens、最多 50 memories/100 entities、既有 DeepSeek/OpenAI 约定、`json_object`、temperature 0、thinking disabled、stream false、extraction `max_output_tokens=8192`。
4. 对返回 JSON 执行应用层结构、引用、枚举、来源、时间字段约束、计数和 Unicode Code Point 字符上限校验；不静默截断，不使用未授权的推断或字段。
5. 对每条合法候选应用计算 `candidate_source_time`，随后按规范固定字段顺序和排序后的 `source_message_ids` 计算 SHA-256 fingerprint；该字段不进入 fingerprint。
6. 在结果足够进入后续阶段前，先将完整、通过校验的 `extraction_result` 持久化到既有 `memory_extraction_task`；后续 replay 复用该结果，不再次调用 LLM。
7. 将 LLM timeout、request failure、invalid structured output 映射到 §2.1.15 已有错误码，并维持 EXT-001 的 `PipelineTerminalDecision`、终态 Mongo 成功后 Offset 才可提交的门禁。
8. 空 Archive 不调用 LLM，沿用 EXT-002/EXT-001 的正常 `completed` 路径；非空 Archive 的 both-empty legal output（`entities=[]`, `memories=[]`）持久化空结果后 `completed` 并提交 Offset；任一非空 `extraction_result` 持久化后任务保持 `processing` 且不得提交 Offset。

本任务拥有 handoff → LLM → validation → duplicate normalization → fingerprint → `candidate_source_time` → persist 边界。EXT-003→EXT-004 continuation 编排 `DEFERRED_FOR_MVP`；不得修改 `PipelineTerminalDecision`；EXT-004 消费已持久化结果。非空 extraction-only success 不得映射为 whole-task `complete`；worker `main()` 在 EXT-004 编排落地前保持 refusal-only。

## 3. 非目标与黑名单

- EXT-004 Entity Alignment、数据库 Entity ID 分配、跨用户对齐、模糊匹配、aliases 持久化合并。
- Neo4j Entity/Memory/Evidence 节点、约束、`SUBJECT`/`OBJECT`/`SUPPORTS` 关系、图谱事务。
- EXT-005 Reconciliation、duplicate/update/conflict/supersede/merge 语义、`aligned_memory_key`。
- Retrieval indexing、Elasticsearch、Embedding、`search_text` 生成和 1024-token 检索门禁。
- `evidence_id` 的生产使用和 Evidence 写入；规格公式可作为后续 handoff 记录，但本任务只产出 `candidate_fingerprint`。`evidence_id = SHA256(archive_id + ":" + candidate_fingerprint)` 属后续 Evidence 阶段。
- 重新读取 raw `context_archive`、修改 EXT-002 normalization/redaction、first-person identity binding、相对时间猜测或 worker-clock 时间转换。
- 改动 EXT-001 Kafka topic、六字段 event、message key、consumer group、Partition serialism、offset commit、task state machine、`PipelineTerminalDecision` 基础模型或已执行 Migration。
- 自动重试、Retry Topic、DLT、Outbox、transport retry、provider failover、多模型路由、streaming、tool calling。
- DEV-006、PR #13，以及任何 TEI、SiliconFlow embedding 或无关 runtime 工作。
- 新 API、HTTP route、admin retry endpoint、跨服务拆分或第二套 Settings/config stack。
- raw content、pre-redaction content、secret、完整 prompt、完整 response、真实用户数据、模型缓存或数据库 dump 的日志、fixture、异常和提交。

## 4. 当前代码状态与前置检查

### 4.1 Git 和前置任务证据

| 检查 | 结果 |
|---|---|
| `git branch --show-current` | `main` |
| planning baseline | `f112d12d28d34de18c637a661a857fcb9f0a401f`（用户显式提供） |
| `git status --short` | 规划开始前无业务 dirty；本轮仅允许规划白名单变更 |
| EXT-001 | completed；`archive_id` 唯一任务、`ExtractionPipelinePort`、terminal persistence before offset 已合并 |
| EXT-002 | completed；严格 raw validation → normalization → deterministic content-only redaction → `ExtractionReadyArchive` |
| STM-007 | completed；`LLMClient.generate_structured` 单 transport call、`DeepSeekLlmClient`、`FakeLlmClient`、脱敏错误 convention |
| `formal_EXT-003_prerequisite_status` | SATISFIED — EXT-002 and STM-007 completed |
| workflow | `NORMAL`，explicit |

### 4.2 可复用代码

| 组件 | 路径 | 本任务约束 |
|---|---|---|
| `ExtractionReadyArchive` | `src/memory_system/domain/models/extraction_preprocessing.py` | 只读消费；字段精确为 archive/user/session/messages；不得添加 first-person 或 durable field |
| EXT-002 preparation | `src/memory_system/domain/services/extraction_archive_preprocessing_service.py` | 只读复用其 prepare/read/redaction 结果；不得重新读取 raw Archive 或复制 redaction |
| `LLMClient` | `src/memory_system/infrastructure/llm/protocol.py` | 优先复用既有 raw-content async call boundary；parse/validate/retry 在 extraction domain service |
| DeepSeek client | `src/memory_system/infrastructure/llm/deepseek_client.py` | 复用 `AsyncOpenAI`、`LlmServiceError`、无 transport retry、secret-safe error；必须使用 extraction settings 而非误用 compression settings |
| Fake client | `src/memory_system/infrastructure/llm/fake_client.py` | 注入 success、timeout、provider failure、malformed JSON、schema-invalid 和 retry sequence；默认无网络 |
| Settings | `settings/models.py`, `configs/base.yaml` | extraction 值已存在且与规格一致；不新增字段、不改版本、不改默认值 |
| Extraction task | `domain/models/extraction_task.py`, `infrastructure/mongodb/extraction_task_repository.py` | `extraction_result: dict | null` 已存在；增加最小条件写入 helper 时不得改变字段全集或 task state semantics |
| Pipeline boundary | `domain/services/extraction_pipeline_port.py`, `extraction_task_consumer_service.py` | 只复用既有 terminal decision/offset gate；不得发明 continuation decision |

### 4.3 已确认的配置与依赖

当前 `configs/base.yaml` 和 Settings 已包含：

```yaml
memory_extraction:
  prompt_version: "memory_extraction_v1"
  llm_timeout_seconds: 120
  max_archive_estimated_tokens: 8000
  max_memory_candidates_per_archive: 50
  max_entity_candidates_per_archive: 100
  max_memory_content_characters: 512
  max_entity_name_characters: 128
  max_entity_alias_count_per_candidate: 32
  max_entity_alias_characters: 128
  max_predicate_characters: 64
  max_object_value_characters: 256
  max_original_time_text_characters: 128

llm:
  extraction:
    model: "deepseek-v4-flash"
    thinking: "disabled"
    response_format: "json_object"
    temperature: 0
    max_output_tokens: 8192
```

`openai>=2.46,<3` 和当前 `AsyncOpenAI` convention 已存在。`dependency_changes_expected: NONE`；若实现需要新增依赖或修改版本，必须停止并报告，不得修改 manifest/lockfile。

## 5. Exact Contract 闭合

### 5.1 ExtractionReadyArchive input

输入必须是 EXT-002 finalized internal handoff，不是 raw Archive、typed raw document、Redis WM、`compressed_context` 或事件完整 payload：

```text
ExtractionReadyArchive {
  archive_id: str
  user_id: str
  session_id: str
  messages: [
    {
      message_id: str
      role: "user" | "assistant"
      content: str       # normalized + redacted only
      timestamp: int
    }
  ]
}
```

硬性规则：

- `archive_id`/`user_id`/`session_id` 仅作为当前 Archive 的 provenance/context；不把 task metadata、`event_id`、`event_type`、`created_time`、`archive_batch_key`、`base_compression_version`、lock token 或 Kafka metadata 放进 prompt。
- messages 按 Archive 数组原顺序序列化；相同 timestamp 不重新排序；每条来源 message 的 `message_id`、role、timestamp 原样保留。
- prompt 只包含当前 `user_id` 和 ordered normalized+redacted messages；不包含 raw/pre-redaction content、secret、完整 task 文档或无关 metadata。
- first-person binding 仍 deferred：保留 role/provenance，不新增 identity field，不将 `"I"`/`"my"` 绑定语义写入 durable schema，不依赖该能力判定实体。
- 空 `messages`：零 LLM call，沿用现有 EXT-001 terminal completion path；不能用 fake empty candidate 调用替代。
- 非空消息即使内容为空字符串，也必须按既有 EXT-002 handoff 规则保留；本任务不得猜测或补充 minimal-archive 语义。Minimal/non-empty archive 的可处理性由现有 strict handoff 和本节候选来源校验决定；不满足 user-source/time/reference contract 时 fail-closed，不猜测。

### 5.2 Size, token, and candidate limits

- `memory_extraction.llm_timeout_seconds = 120`，作为每次 provider request timeout。
- `max_archive_estimated_tokens = 8000`：使用既有字符比例 `estimate_tokens` 对全部 Archive message content 估算；EXT-002 已在 handoff 前拦截超限为 `archive_too_large`。
- 不分块、不截断、不舍弃消息、不把超限 Archive 拆成多次 extraction call。
- `max_memory_candidates_per_archive = 50`；`max_entity_candidates_per_archive = 100`。
- Unicode Code Point 字符上限：memory content 512；entity name 128；每 candidate aliases 数量 32；单 alias 128；predicate 64；object_value 256；original_time_text 128。
- 应用层只拒绝超限，不静默截断；超过限制进入一次 schema correction retry，第二次仍无效为 `llm_invalid_output`。
- `max_stored_entity_alias_count=50`、`max_search_text_tokens=1024` 属后续 alignment/retrieval contract，不在 EXT-003 执行。
- `max_output_tokens` 使用现有 extraction setting 8192；不新造 token setting，不把 compression 的 2048 错用于 extraction。
- 合法非空 Archive 的 both-empty output (`entities=[]`, `memories=[]`) 是正常完成结果：持久化 exact empty result，任务 `completed`，终态持久化后提交 Offset；不是 `llm_invalid_output`。
- 任一非空 `extraction_result`（存在 entity 或 memory 候选）持久化后任务保持 `processing`，不得提交 Offset。
- 空 Archive 与 both-empty legal output 必须在测试中区分：前者零 LLM call；后者一次成功 Structured Output 后持久化并完成。

### 5.3 Exact prompt and provider contract

Prompt version 必须取既有 `settings.memory_extraction.prompt_version`，值为 `memory_extraction_v1`。首次调用的 system prompt 必须逐字对应规格：

```text
You are a long-term memory extraction engine.

Your task is to extract only durable and reusable memories from archived conversation messages.

Requirements:
1. Extract only memories supported by the provided messages.
2. Every memory must include at least one source message whose role is user.
3. Assistant messages may provide context, but must never be the only evidence.
4. Classify each memory as fact, preference, event, or profile.
5. Each memory must express one atomic meaning. Split unrelated information into separate memories.
6. Resolve first-person references such as "I" and "my" to the current user entity.
7. Preserve explicit corrections, negations, temporal order, event status and unresolved conflicts.
8. Preserve the original time expression. Resolve relative time only when the source timestamp and timezone are both available.
9. For non-event memories, set all event-related fields to null.
10. Do not infer hidden attributes, intentions, diagnoses or relationships.
11. Do not extract greetings, temporary formatting requests, unsupported assistant suggestions, secrets or authentication credentials.
12. Use lower_snake_case for predicate.
13. Return only valid JSON matching the required schema.
```

首次 user prompt 必须逐字对应规格：

```text
Current user ID:
{user_id}

Archived conversation messages:
{messages}

Extract durable long-term memory candidates.
```

`{messages}` 是稳定 JSON array，按输入顺序只含 `message_id`, `role`, normalized+redacted `content`, `timestamp`。Prompt tests 必须断言 exact required text and assert forbidden raw/secret/task fields absent.

Provider call contract：

| 参数 | Extraction 值 |
|---|---|
| client | existing `LLMClient` / `DeepSeekLlmClient`; `openai.AsyncOpenAI` |
| model | `settings.llm.extraction.model` = `deepseek-v4-flash` |
| response_format | `{"type": "json_object"}` |
| temperature | `0` |
| thinking | `{"type": "disabled"}` |
| stream | `False` |
| max_tokens | `settings.llm.extraction.max_output_tokens` = `8192` |
| timeout | `settings.memory_extraction.llm_timeout_seconds` = `120` |
| transport retry | `0`; no 429/5xx/connection auto-retry |

Existing protocol is preferred. The implementation may add only an internal task-settings selection/constructor path so `DeepSeekLlmClient` uses `llm.extraction` for extraction and preserves existing compression behavior (MF-001); it must not add a public business contract or a second config stack. If the existing protocol cannot support this without changing its authorized contract, halt and request authoritative amendment rather than silently changing it. Tests must cover both extraction and compression paths.

No prompt, response body, message content, API key, secret, or sanitized exception containing user data may be logged. Failure logs must include `task_id`, `archive_id`, `user_id`, `failed_stage`, and `attempt_count` (MF-002). Allowed observability is otherwise limited to request/task identifiers where already authorized, model, prompt_version, duration, outcome, error_code, and provider usage metadata without content.

### 5.4 Structured output schema

The LLM JSON top level is exactly conceptually:

```json
{
  "entities": [
    {
      "local_entity_id": "entity_1",
      "name": "Agent Memory System",
      "type": "project",
      "aliases": ["记忆系统项目"]
    }
  ],
  "memories": [
    {
      "memory_type": "event",
      "content": "用户正在开发 Agent Memory System",
      "subject_entity_id": "user",
      "predicate": "works_on",
      "object_entity_id": "entity_1",
      "object_value": null,
      "event_status": "ongoing",
      "start_time": null,
      "end_time": null,
      "original_time_text": "正在",
      "confidence": 0.95,
      "source_message_ids": ["msg_000001"]
    }
  ]
}
```

Required/nullable/type/enums/reference semantics:

| Object | Field | Contract |
|---|---|---|
| top-level | `entities` | required JSON array; empty array allowed |
| top-level | `memories` | required JSON array; empty array allowed |
| entity | `local_entity_id` | required non-empty string; unique in this result; LLM-local only, never a database ID |
| entity | `name` | required non-empty string; ≤128 Unicode Code Points |
| entity | `type` | required enum: `person`, `organization`, `product`, `project`, `location`, `concept`, `other` |
| entity | `aliases` | required string array; no aliases = `[]`; each ≤128 Code Points; candidate count ≤32 |
| memory | `memory_type` | required enum: `fact`, `preference`, `event`, `profile` |
| memory | `content` | required non-empty string; ≤512 Unicode Code Points |
| memory | `subject_entity_id` | required string; must reference an entity in this result or reserved `user` |
| memory | `predicate` | required non-empty lower_snake_case string; ≤64 Code Points |
| memory | `object_entity_id` | required nullable string; entity reference or `null` |
| memory | `object_value` | required nullable string; ordinary value or `null` |
| memory | object choice | exactly one of `object_entity_id` and `object_value` is non-null |
| memory | `event_status` | event: required enum `occurred`, `ongoing`, `planned`, `cancelled`, `unknown`; non-event: required `null` |
| memory | `start_time`/`end_time` | nullable string; only authorized ISO 8601 UTC, `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` forms where applicable; unresolved = `null`; no invented current time |
| memory | `original_time_text` | nullable string; original user time expression; ≤128 Code Points |
| memory | `confidence` | required JSON number in inclusive `[0.0, 1.0]`; no clamping |
| memory | `source_message_ids` | required array of current Archive message IDs; at least one `role=user` source; every ID must exist in current Archive |

The application must validate every entity reference against this result’s `local_entity_id` set or reserved `user`; never resolve to a database ID. It must validate every source ID against the current Archive and calculate the user-source requirement from preserved input roles. It must not output/persist `entity_relations`, database IDs, `memory_id`, `entity_id`, `aligned_memory_key`, `evidence_id`, `abstraction_level`, or any EXT-004+ field.

**Unknown-field policy (Appendix B §B.1 / OI-EXT-003-001 resolved):** unknown top-level/entity/memory fields may be ignored during parse but must be stripped before persistence. Only authorized fields may appear in durable `extraction_result`. Unknown fields must not influence persist, fingerprint, or duplicate/equivalence processing.

### 5.5 Application validation and normalization

After JSON parse, validate in this order:

1. top-level object and required arrays;
2. entity fields, strict types, enums, non-empty values, character limits, and unique local IDs;
3. memory fields, strict types, enums, nullability, character limits, confidence range, object XOR;
4. all subject/object references against local IDs or `user`;
5. all source IDs against current Archive: each `source_message_ids` must be non-empty; every ID must exist in the current Archive; at least one `role=user` source per memory; violations map to `llm_invalid_output` / `llm_extraction` with schema correction retry — not `invalid_archive`;
6. event/non-event time field nullability and existing §2.1.8 time representation;
7. candidate counts;
8. duplicate/equivalence normalization per §5.6;
9. `[REDACTED_SECRET]` must not occur in durable `content` or `object_value`; reject such candidate rather than persist a redaction marker.
10. null/blank/whitespace-only provider output maps to `llm_invalid_output` (not `llm_empty_output`); one correction retry then terminal failed.

No partial JSON, partial entities, partial memories, silently clamped confidence, silently truncated strings, inferred source IDs, inferred user identity, relations, IDs, or time values are persisted.

For each accepted memory:

```text
candidate_source_time = max(
    timestamp of messages in source_message_ids
    whose role is "user"
)
```

This is application-derived from the current immutable Archive input, never LLM output and never server current time. Invalid source references are `llm_invalid_output` / `llm_extraction`, not `invalid_archive`. Persist `candidate_source_time` in each durable candidate before writing `extraction_result`. It is explicitly excluded from fingerprint because sorted `source_message_ids` already participate.

### 5.6 Candidate duplicate/equivalence and order boundary (Appendix B §B.8 / OI-EXT-003-002 resolved)

Authoritative rules:

- `entities` preserve provider array order; no deduplication.
- `memories` preserve first-occurrence order after duplicate merge.
- “Fully identical” means all durable LLM memory fields are equal **except** `source_message_ids`.
- On merge: dedupe `source_message_ids`, lexicographically sort, retain one memory; no confidence aggregation.
- SHA-256 collision handling is `DEFERRED_FOR_MVP` (OI-EXT-003-005); ordinary SHA-256 identity comparison only; no collision error code or fallback.

### 5.7 Fingerprint contract

For each validated candidate, compute exactly:

```text
candidate_fingerprint = SHA256(
    UTF-8 bytes of compact JSON array [
        memory_type,
        content,
        subject_entity_id,
        predicate,
        object_entity_id,
        object_value,
        event_status,
        start_time,
        end_time,
        original_time_text,
        deduped_lex_sorted(source_message_ids)
    ]
)
```

Implementation requirements (Appendix B §B.7 / OI-EXT-003-002 resolved):

- fixed field order exactly: `memory_type`, `content`, `subject_entity_id`, `predicate`, `object_entity_id`, `object_value`, `event_status`, `start_time`, `end_time`, `original_time_text`, `source_message_ids`;
- UTF-8 bytes of compact JSON array (not object);
- `ensure_ascii=false`; JSON `null` for nullable fields;
- no extra whitespace;
- before serialization: dedupe `source_message_ids` and lexicographically sort;
- exclude `candidate_source_time`, prompt/version, archive/user/session/task IDs, aliases/entities, confidence, database IDs, and `evidence_id`;
- do not add Unicode NFKC, whitespace folding, case folding, numeric normalization, string trimming, locale ordering, JSON key sorting, or other canonicalization not stated by the spec;
- `evidence_id` is a later handoff only: `SHA256(archive_id + ":" + candidate_fingerprint)` belongs to Evidence/graph work and is not produced or persisted as an EXT-003 implementation behavior.

## 6. Failure, terminal, persistence, and replay semantics

### 6.1 Authorized failure mapping

Only these extraction-stage codes are permitted:

| Condition | `error_code` | `failed_stage` | Retry |
|---|---|---|---|
| Archive missing | `archive_not_found` | `archive_read` | no; existing EXT-002 mapping |
| ownership/ID mismatch | `archive_ownership_mismatch` | existing authorized validation stage | no; existing EXT-002 mapping |
| structural/source/timestamp invalid Archive | `invalid_archive` | `archive_validate` | no |
| estimated token sum >8000 | `archive_too_large` | existing archive validation stage | no; no chunking |
| HTTP read timeout / provider timeout | `llm_timeout` | `llm_extraction` | no transport/schema retry |
| connection, 429/5xx, other provider request failure | `llm_request_failed` | `llm_extraction` | no transport retry |
| null/blank/whitespace provider output | `llm_invalid_output` | `llm_extraction` | one schema correction retry |
| malformed JSON, schema/reference/count/limit/source-ref failure after two total attempts | `llm_invalid_output` | `llm_extraction` | one schema correction retry |

Extraction must not add `llm_empty_output`, `invalid_extraction_input`, `fingerprint_collision`, `entity_alignment_failed`, graph, reconciliation, or retrieval codes. A null/blank/whitespace assistant content is invalid Structured Output for this extraction contract and follows the one schema retry, then `llm_invalid_output`; it must not import STM-007’s compression-only `llm_empty_output` meaning into §2.1.15.

Unexpected nondeterministic infrastructure/internal failures remain `abort_without_terminal` with no `last_error`, no terminal write, and no Offset commit, following EXT-002/EXT-001 behavior. If a recognized permanent/transient extraction failure is returned, it must flow through `PipelineTerminalDecision.fail(ExtractionLastError(...))`; the consumer persists failed state and `last_error` before committing Offset. If that terminal persistence fails, `TerminalPersistError`/existing consumer behavior leaves Offset uncommitted.

### 6.2 Schema retry and provider behavior (Appendix B §B.4–B.5 / OI-EXT-003-003 resolved)

1. Build exact first system/user prompt from §5.3.
2. Call provider once with extraction settings.
3. Parse and validate.
4. On blank output, JSON/schema/application validation failure, or invalid source refs only, call exactly once more with the same redacted Archive input and the exact correction instruction below. Do not include the prior invalid response in the prompt.
5. On second failure return `llm_invalid_output`; no third call.
6. Do not retry timeout, connection/provider/429/5xx failures; map immediately.
7. Do not log either prompt or response.

Exact correction instruction (verbatim):

```text
The previous response was invalid.
Return exactly one valid JSON object matching the required extraction schema, using only source_message_ids from the provided archive.
Return JSON only.
```

### 6.3 Durable result, terminal, and replay semantics (Appendix B §B.2, §B.10 / OI-EXT-003-004 resolved)

`memory_extraction_task.extraction_result` remains the existing task field; the result written by this task contains only the validated extraction result plus application-derived `candidate_source_time` and `candidate_fingerprint` fields authorized by §2.1.7. It must not contain raw messages, prompt/response, secrets, database IDs, entity relations, Neo4j records, or future stage outputs.

The result write must happen before any later graph/alignment stage and before the task can reach a terminal `completed` state. On write failure, return `abort_without_terminal` or the already authorized persistence-failure behavior without committing Offset; do not report success with an unpersisted result.

**Legal empty and terminal mapping:**

| Scenario | `extraction_result` | Task status after persist | Offset |
|---|---|---|---|
| Empty Archive (`messages=[]`) | N/A (zero LLM) | `completed` via existing EXT-001/EXT-002 path | after terminal persist |
| Non-empty Archive, both-empty (`entities=[]`, `memories=[]`) | persisted empty result | `completed` | after terminal persist |
| Non-empty Archive, any non-empty result | persisted complete validated result | `processing` | do **not** commit |

On a later task replay:

- `status=completed`: EXT-001 early commits and skips all LLM calls.
- `status=failed`: ordinary duplicate event early commits and does not retry; manual retry semantics remain outside this task.
- `status=processing` with non-null `extraction_result`: pipeline implementation must reuse the saved result and skip LLM; it must not recompute `candidate_source_time` using current server time or regenerate fingerprints.
- `status=processing` with null result: a fresh attempt may call LLM once under the above retry rules.

**Pipeline boundary:** EXT-003 owns handoff → LLM → validation → duplicate normalization → fingerprint → `candidate_source_time` → persist. EXT-003→EXT-004 continuation orchestration is `DEFERRED_FOR_MVP`. Do **not** modify `PipelineTerminalDecision` for future orchestration; EXT-004 consumes persisted `extraction_result`. Non-empty extraction-only success must not map to whole-task `complete`. Worker `main()` remains refusal-only until a later authorized plan owns EXT-004 wiring.

### 6.4 Determinism and replay guarantees

- Same validated input and same Fake response produce the same validated result and fingerprint.
- `temperature=0`/thinking disabled are provider settings, not a guarantee of bitwise equality across fresh real DeepSeek calls.
- The application-side fingerprint is deterministic for identical canonical candidate values once the canonicalization ambiguity is resolved.
- A fresh real LLM call may vary candidate wording/order; EXT-003 does not claim cross-call real-LLM deterministic extraction.
- Replay after result persistence does not call the LLM and reuses exact durable result/fingerprint/time.
- EXT-004/EXT-005 may later consume the result; they are not implemented or semantically simulated here.

## 7. Implementation plan

Implementation is conditional on PLAN_APPROVED after Amendment 002 Plan Review.

### Step 1 — Strict domain models and bounded result shape

- Files: `src/memory_system/domain/models/extraction_llm.py`.
- Define input/result types for prepared `ExtractionReadyArchive`, entity candidate, memory candidate, validated extraction result, failure/success outcome, and durable candidate metadata.
- Preserve strict primitive types and exact enums; do not create database-ID types, relation models, Evidence models, or alignment models.
- Parse may ignore unknown fields; durable models strip unknown fields before persistence; unknown fields must not affect fingerprint or duplicate merge.
- Encode character/count constraints from `Settings.memory_extraction`; no truncation.
- Ensure `candidate_source_time` and `candidate_fingerprint` are application-owned and cannot be accepted as LLM fields.

### Step 2 — Prompt rendering and extraction LLM service

- Files: `src/memory_system/domain/services/extraction_llm_service.py`, and only the minimum authorized updates to `src/memory_system/infrastructure/llm/deepseek_client.py` / `fake_client.py`.
- Serialize only the exact ordered handoff messages.
- Render the exact first prompt and the exact §6.2 correction instruction on retry.
- Call existing protocol with `llm.extraction` model/settings (MF-001), 120-second timeout, `json_object`, temperature 0, thinking disabled, stream false, max output 8192; preserve compression path unchanged.
- Parse JSON, validate full schema and semantic references, derive `candidate_source_time`, perform authorized duplicate handling, compute fingerprints, and return all-or-nothing validated result.
- Map known failures to only §2.1.15 codes; catch unexpected nondeterministic faults as abort without terminal.
- Emit only allowed metadata logs including MF-002 required fields on failure.

### Step 3 — Fingerprint helper

- File: `src/memory_system/domain/services/extraction_fingerprint.py`.
- Implement fixed field-order JSON array, deduped+lex-sorted source IDs, `ensure_ascii=false`, compact JSON, UTF-8 SHA-256.
- Do not normalize Unicode/numbers/strings beyond the explicit specification.
- Collision handling remains ordinary SHA-256 identity comparison; OI-EXT-003-005 deferred/non-blocking.

### Step 4 — Persist validated extraction result

- File: `src/memory_system/infrastructure/mongodb/extraction_task_repository.py`.
- Add only a conditional update helper for `processing` task `extraction_result`, preserving `archive_id` uniqueness, all task fields, status transitions, and existing `mark_failed` result-preservation behavior.
- Persist the complete validated result atomically as one task field before downstream stages; never persist partial candidate arrays.
- Both-empty result: after persist, transition to `completed` and allow Offset commit under existing gate.
- Non-empty result: after persist, task remains `processing`; do not commit Offset.
- If the conditional write does not apply, fail closed and do not allow Offset commit.
- Do not add `session_id`, `event_id`, prompt, response, database IDs, graph fields, or a second collection.

### Step 5 — Pipeline handoff (Appendix B §B.10)

**SF-1 MVP_LOCAL_DECISION (human PLAN_APPROVED; no new Plan Review):**

- Single orchestration owner: `src/memory_system/domain/services/extraction_llm_service.py`.
- This module owns Step 5 pipeline handoff (terminal mapping, persist triggers, replay skip-LLM) in addition to LLM/validate/fingerprint orchestration in Steps 2–4.
- `extraction_archive_preprocessing_service.py` remains EXT-002 compose-only; **not** a second orchestration layer.
- No new files; no whitelist expansion; no competing orchestration layer.

Implementation notes:

- Extend `extraction_llm_service.py` with pipeline handoff methods; `extraction_pipeline_port.py` unchanged; `extraction_worker.py` unchanged (refusal-only).
- Preserve EXT-002 empty Archive `complete` behavior.
- For non-empty both-empty success: persist empty result then `complete` with Offset after terminal persist.
- For non-empty extraction result: persist then leave `processing`; no Offset commit; no `PipelineTerminalDecision` modification.
- For failure, return existing `PipelineTerminalDecision.fail`; for nondeterministic failure, return `abort_without_terminal`.
- Test handoff as isolated library service methods on `extraction_llm_service.py`; EXT-004 continuation `DEFERRED_FOR_MVP`.

### Step 6 — Tests and quality gates

- Add the exact tests in §8; default all external provider tests to skip unless explicit opt-in, with no real call in normal CI.
- Run only after plan approval and OI closure; this planning round runs no tests.

## 8. Production and test file whitelist

### 8.1 Planning whitelist used in this round

- `02_开发管理/tasks/EXT-003-llm-extraction-fingerprint.md`
- `02_开发管理/progress.md`
- `02_开发管理/master_plan.md`
- `02_开发管理/open_issues.md`
- `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`（Appendix B only）

### 8.2 Conditional implementation whitelist

Production:

- `src/memory_system/domain/models/extraction_llm.py` — create strict extraction input/output/result models.
- `src/memory_system/domain/services/extraction_llm_service.py` — create prompt/parse/validate/retry/source-time/fingerprint orchestration.
- `src/memory_system/domain/services/extraction_fingerprint.py` — create exact canonical fingerprint helper.
- `src/memory_system/infrastructure/llm/deepseek_client.py` — minimum extraction-settings selection only; preserve compression behavior and transport retry=0.
- `src/memory_system/infrastructure/llm/fake_client.py` — only if needed to expose extraction response sequences through the existing protocol.
- `src/memory_system/infrastructure/mongodb/extraction_task_repository.py` — minimum conditional `extraction_result` persistence helper only.
- `src/memory_system/domain/services/extraction_pipeline_port.py` — explicitly unchanged; do not modify `PipelineTerminalDecision`.
- `src/memory_system/domain/services/extraction_archive_preprocessing_service.py` — only to compose the already existing ready handoff with the approved extraction stage; no EXT-002 behavior change.
- `src/memory_system/entrypoints/extraction_worker.py` — explicitly unchanged in the default EXT-003 plan; any future change requires a separate authorized completion-gate decision.

Tests:

- `tests/unit/test_extraction_llm_service.py` — extraction happy path, empty/minimal, validation, retry, error mapping, privacy.
- `tests/unit/test_extraction_fingerprint.py` — fixed order, UTF-8, compact JSON, sorted source IDs, candidate_source_time exclusion, no invented normalization.
- `tests/unit/test_deepseek_llm_client.py` — extraction settings parameter matrix, timeout/provider mapping, no transport retry, no secret/content logging.
- `tests/contract/test_ext003_contract.py` — input envelope, output fields/types/enums/reference rules, limits, prompt exactness, error-code set, fingerprint field order.
- `tests/contract/helpers/extraction_llm_fake.py` — only if existing Fake helper cannot express the required sequence without changing production semantics.
- `tests/integration/test_extraction_llm_fake.py` — end-to-end domain service with Fake; no network.
- `tests/integration/test_ext003_extraction_mongo.py` — real Mongo `extraction_result` write/reload/replay reuse, only if existing integration fixtures support it.
- `tests/unit/test_extraction_task_consumer_service.py` — extend only with replay/result-preservation assertions that do not change EXT-001 Kafka semantics.
- `tests/unit/test_extraction_pipeline_ext002.py` — extend only to prove empty Archive remains zero-LLM/normal completion and ready input has no raw leakage.

Explicitly not whitelisted:

- `pyproject.toml`, `uv.lock`, migrations, `configs/base.yaml`, `settings/models.py` and settings validators (unless a specification-proven mismatch is found; current evidence says none).
- `src/memory_system/infrastructure/kafka/**`, `archive_created_consumer.py`, publisher, consumer group, worker offset code.
- `src/memory_system/domain/models/archive_created_event.py`, `extraction_task.py` schema field set, `extraction_task_consumer_service.py` semantics.
- `src/memory_system/infrastructure/neo4j/**`, `infrastructure/elasticsearch/**`, `domain/services/entity_alignment*`, reconciliation, retrieval, embedding.
- `tests/e2e/**`, STM tests, EXT-004+ tests, DEV-006 paths, PR #13 artifacts.
- raw Archive fixtures, real user data, full prompt/response fixtures containing secrets or unredacted content.

## 9. Data consistency, idempotency, concurrency, and recovery

| Dimension | Conclusion | Required handling |
|---|---|---|
| Atomicity | LLM call is external and not transactional; task result is one Mongo field update | Validate all output first; persist one complete `extraction_result`; no partial candidates |
| Idempotency | `archive_id` remains task key; result persistence is conditional on the same task | `$setOnInsert` and existing unique task semantics unchanged; repeated event never creates another task |
| Replay | Result persisted before downstream continuation | `processing + extraction_result != null` skips LLM and reuses exact source times/fingerprints |
| Completed task | Existing EXT-001 early branch | No LLM, no graph, no result rewrite, Offset commit only under existing branch |
| Failed task | Existing EXT-001 early branch | No automatic retry; manual retry remains EXT-008 |
| Concurrent calls | Same Partition is serial; external duplicate workers are not made exactly-once | Conditional Mongo write and immutable result reuse; no claim of cross-system exactly-once |
| Version conflict | No new version field authorized | Do not add extraction version/cursor/lease; failed conditional write aborts or uses existing terminal failure path |
| User isolation | Input/archive/task user IDs already validated by EXT-002/EXT-001 | Prompt uses only current handoff user ID; references are local to current Archive; no cross-user lookup |
| Partial provider output | Forbidden | JSON/schema failure returns no partial durable result |
| Timeout/provider failure | No transport retry | Map to existing code and terminal decision; result remains null; terminal persistence precedes Offset |
| Terminal persistence failure | Existing consumer gate | No Offset commit; Kafka replay remains possible |
| Process crash after result write | Result is durable, task may remain processing | Replay skips LLM and uses exact saved result; downstream handoff must be resolved before implementation |
| Process crash before result write | No durable result | Replay may call LLM again; real provider may vary; no bitwise repeat guarantee is claimed |
| Fingerprint collision | SHA-256 output is identity material only | No invented collision error or fallback; any required collision policy needs authoritative amendment |
| Privacy | Raw/pre-redaction/secrets never enter this service | Only normalized+redacted content is prompt input; logs/fixtures/responses are content-free |

## 10. Test plan

Real DeepSeek/SiliconFlow calls are `false` by default and skipped unless an explicit opt-in environment gate is added and authorized; the specification does not require a real external call for EXT-003. Normal CI uses Fake/transport mocks and must not incur provider charges.

### 10.1 Unit tests

| ID | Scenario | Expected |
|---|---|---|
| U1 | Valid non-empty ready archive and valid entity/memory output | Complete validated result; provenance/order retained; source time and fingerprint added |
| U2 | Empty Archive messages | Zero LLM calls; existing normal `complete` path; no fake output |
| U3 | Minimal non-empty message with no durable fact | LLM may return legal empty `{entities:[], memories:[]}`; persist normal empty result; no invented candidate |
| U4 | Non-empty message with empty normalized content | Input remains exact EXT-002 handoff; no raw leakage; behavior follows provider/result validation, no guessed summary |
| U5 | Ordered messages/equal timestamps | Prompt order and source lookup preserve Archive order; no timestamp resort |
| U6 | Missing/unknown input metadata or raw/pre-redaction content injected into handoff | Reject test fixture at handoff boundary; no provider call or leakage |
| U7 | local entity IDs duplicate | `llm_invalid_output` after correction retry; no persistence |
| U8 | invalid entity reference / invalid source ID / no user source | `llm_invalid_output` after retry; no partial persistence |
| U9 | object entity/value both null or both non-null | `llm_invalid_output`; no clamping or repair |
| U10 | event/non-event nullability and event-status enum violations | `llm_invalid_output` |
| U11 | confidence below/above range | `llm_invalid_output`; no silent clamp |
| U12 | each character/count limit at boundary and over boundary | Inclusive boundary succeeds; over-limit retries then fails; no truncation |
| U13 | `[REDACTED_SECRET]` in candidate content/object_value | Invalid output; no durable candidate |
| U14 | malformed JSON first, valid correction second | Success; exactly two provider calls; correction prompt contains no raw/secret |
| U15 | schema-invalid first, valid correction second | Success; exact retry count and persisted result |
| U16 | malformed/schema-invalid both attempts | `llm_invalid_output`; exactly two calls; no result |
| U17 | timeout | `llm_timeout`; exactly one provider call; no schema retry |
| U18 | provider/connection/429/5xx failure | `llm_request_failed`; exactly one provider call; no transport retry |
| U19 | blank/null assistant content | Extraction mapping uses only authorized `llm_invalid_output` after one correction attempt; no compression-only error code |
| U20 | exact system/user prompt | Prompt literal matches §2.1.6; only user ID and ordered normalized+redacted messages appear |
| U21 | duplicate/equivalent candidate fixtures | Merge identical memories except source IDs; dedupe+lex sort source IDs; preserve first occurrence order; no confidence aggregation |
| U22 | fingerprint repeated same validated candidate | Same bytes and digest after canonicalization resolution; `candidate_source_time` excluded |
| U23 | source IDs different order | Fingerprint uses sorted source IDs; candidate provenance remains input/result semantics |
| U24 | Unicode, numbers, strings | `ensure_ascii=false`; no NFKC/trim/case/number rewrite |
| U25 | secret/content/prompt/response logging capture | No raw, redacted secret value, full prompt, full response, or API key in logs/exceptions |

### 10.2 Contract tests

| ID | Scenario | Expected |
|---|---|---|
| C1 | ExtractionReadyArchive field set | Exact archive/user/session/messages envelope; message field set and order match EXT-002 |
| C2 | Structured top-level schema | Required `entities`/`memories` arrays; empty arrays valid; unknown fields stripped before persistence |
| C3 | Entity fields/enums/limits | Exact local-only ID, type enum, alias types/count/length, non-empty name |
| C4 | Memory fields/nullability/enums | Exact four memory types, event statuses, object XOR, non-event null event fields |
| C5 | References and source provenance | local IDs or `user`; source IDs current Archive; at least one user message |
| C6 | Candidate counts and Code Point limits | 50/100 and all §2.1.6 limits; no truncation |
| C7 | Prompt/provider matrix | `memory_extraction_v1`, DeepSeek extraction model, json_object, temperature 0, thinking disabled, stream false, max_output 8192, timeout 120 |
| C8 | Error-code whitelist | Only `llm_timeout`, `llm_request_failed`, `llm_invalid_output` for LLM stage; archive codes remain existing EXT-002 mapping; no new codes |
| C9 | Fingerprint bytes | Fixed field-order JSON array, `ensure_ascii=false`, compact JSON, UTF-8, deduped+lex-sorted source IDs, no candidate_source_time/evidence_id |
| C10 | Durable result schema | Validated candidates plus app-derived source time/fingerprint only; no DB IDs, relations, graph fields, raw content, prompt, response, or secret |
| C11 | Retry contract | Schema failure one correction retry; transport failure no retry; no third call |
| C12 | Pipeline decision boundary | Both-empty → `complete`+Offset; non-empty result → `processing` no Offset; failures map to existing `PipelineTerminalDecision`; empty archive completion remains EXT-001; no `PipelineTerminalDecision` modification |

### 10.3 Integration tests with Fake

| ID | Scenario | Expected |
|---|---|---|
| I1 | `ExtractionReadyArchive` → service → Fake valid output | Complete validated in-memory result; no external network |
| I2 | Fake timeout/provider failure | Exact error mapping; no retry outside schema retry |
| I3 | Fake malformed/schema-invalid sequence | First failure correction success and exhaustion paths |
| I4 | Fake valid legal empty output | Mongo result persistence path stores empty result; no Neo4j/EXT-004 collaborator |
| I5 | Fake input with credential marker/raw injection | No secret/raw reaches Fake prompt capture or logs |
| I6 | Replay with persisted result | LLM Fake call count remains zero; exact persisted fingerprint/source time reused |
| I7 | Fresh same input with deterministic Fake | Same fingerprint/result; separately document real LLM may vary |
| I8 | Duplicate/equivalent candidate behavior | Identical memories merged; source IDs deduped+lex sorted; entities preserve provider order |
| I9 | Terminal failure persistence injection | `PipelineTerminalDecision.fail` reaches existing consumer; failed state/last_error must persist before Offset; persistence failure leaves Offset uncommitted |

### 10.4 Mongo/consumer contract integration

- Use existing test Mongo fixtures only; no new migration.
- Persist one validated result under the existing `archive_id` task; reload exact result.
- Verify a second processing replay with non-null result does not invoke Fake/LLM.
- Verify `mark_failed` preserves an already persisted result.
- Verify completed/failed early branches remain unchanged.
- Do not claim Mongo+Kafka atomicity or alter consumer offset tests.

### 10.5 E2E and real provider

| Scenario | Expected |
|---|---|
| Full Kafka → Archive → LLM → Neo4j/ES | Not applicable; full extraction E2E is EXT-009 and graph stages are out of scope |
| Real DeepSeek call | Optional, explicit opt-in only; default skipped and not a PR blocker; no real user data or secrets in fixtures |
| SiliconFlow call | Not applicable to EXT-003; no embedding behavior |

### 10.6 Failure injection and concurrency

| Scenario | Expected |
|---|---|
| Provider timeout/request failure | One provider call; exact failure code; no schema retry |
| First schema failure/second success | Two calls maximum; durable write only after second success |
| Both schema attempts invalid | No durable result; existing failure terminal path |
| Result Mongo write failure | No success terminal/Offset commit; replay remains possible |
| Crash after result write before downstream handoff | Replay reuses result, zero LLM calls; task remains `processing` for non-empty result; EXT-004 continuation deferred |
| Concurrent same archive task | Existing unique `archive_id` and conditional result write prevent duplicate task/result overwrite; no exactly-once claim |
| Duplicate/equivalent candidates | Dedupe+lex sort source IDs on merge; preserve first occurrence memory order; no confidence aggregation |

## 11. Acceptance criteria

- [ ] Plan Review and human approval completed after Amendment 002; authoritative Appendix B contracts are explicit in plan.
- [ ] Only `ExtractionReadyArchive` exact fields are consumed; raw/pre-redaction content, secrets, task metadata and unrelated event metadata never enter prompt/log/fixture.
- [ ] Archive order/provenance is preserved; first-person binding remains deferred and no identity field is added.
- [ ] Empty Archive produces zero LLM calls and normal existing EXT-001 completion; non-empty both-empty output persists and completes with Offset; non-empty result persists and leaves task `processing` without Offset commit.
- [ ] 8000 token limit, no chunking, 50/100 candidate limits, 8192 extraction output cap and all character limits are enforced without truncation.
- [ ] Structured schema, strict application validation, references, enums, nullability, user-source requirement, event/time rules and redaction-marker prohibition are covered by tests.
- [ ] Unknown fields stripped before persistence; no influence on fingerprint or duplicate merge.
- [ ] Invalid source refs map to `llm_invalid_output`/`llm_extraction`, not `invalid_archive`.
- [ ] Blank/null/whitespace output maps to `llm_invalid_output`, not `llm_empty_output`.
- [ ] `candidate_source_time` is application-derived from user-source timestamps and durable; it never uses worker current time and is excluded from fingerprint.
- [ ] Fingerprint uses exact fixed field-order JSON array, deduped+lex-sorted source IDs, `ensure_ascii=false`, UTF-8 compact JSON, and no unauthorized canonicalization.
- [ ] Duplicate memories merged per §5.6; entities preserve provider order.
- [ ] No `entity_relations`, database IDs, `evidence_id` production behavior, Neo4j, alignment, reconciliation, retrieval or graph write is implemented.
- [ ] Provider call uses `memory_extraction_v1`, `llm.extraction` settings (MF-001), existing DeepSeek/OpenAI conventions, json_object, temperature 0, thinking disabled, stream false, extraction max_output_tokens, 120 seconds; compression path unchanged; transport retry is zero.
- [ ] Schema validation retries exactly once with the exact §6.2 correction instruction; timeout/provider failure does not retry; exhaustion maps to `llm_invalid_output`.
- [ ] LLM failure mappings use only `llm_timeout`, `llm_request_failed`, `llm_invalid_output` at `llm_extraction`; failure logs include MF-002 metadata.
- [ ] Validated result is persisted before downstream continuation; replay with non-null result skips LLM and reuses exact result/fingerprint/source time.
- [ ] `PipelineTerminalDecision` unchanged; no false non-empty final completion; worker refusal-only until EXT-004 orchestration plan.
- [ ] Exact production/test whitelist only; dependency changes `NONE`; default CI makes no real external provider call.
- [ ] Unit, Contract, Fake Integration, and required Mongo/replay tests pass; Ruff and Mypy pass; Review has no P0/P1.

## 12. 风险与阻塞项

### 12.1 Resolved Open Issues (Appendix B / Amendment 002)

| ID | Resolution |
|---|---|
| OI-EXT-003-001 | **RESOLVED** — ignore unknown fields during parse; strip before persistence; only authorized fields in `extraction_result`; no persist/fingerprint/duplicate influence |
| OI-EXT-003-002 | **RESOLVED** — fingerprint JSON array, `ensure_ascii=false`, deduped+lex-sorted source IDs; duplicate/equivalence/order per §5.6 |
| OI-EXT-003-003 | **RESOLVED** — exact correction instruction in §6.2 |
| OI-EXT-003-004 | **RESOLVED** — EXT-003 boundary owns handoff→persist; both-empty completes; non-empty stays `processing` no Offset; EXT-004 continuation deferred; `PipelineTerminalDecision` unchanged |

### 12.2 Deferred / non-blocking

| ID | Status | Note |
|---|---|---|
| OI-EXT-003-005 | `DEFERRED_FOR_MVP` | SHA-256 collision handling owned by later Evidence/reconciliation; non-blocking |
| OI-EXT-002-003 | deferred/out-of-scope | first-person binding; EXT-003 cannot depend on it |
| OI-006, OI-007, OI-008 | unrelated | future-task issues |

### 12.3 Dependency/API/schema risk

- Expected dependency changes: `NONE`.
- No new task collection, top-level task field, migration, event field, status, error code, database ID, or relation schema.
- Any need to change the public `LLMClient` contract, `PipelineTerminalDecision` contract, task schema, or Settings must halt and request an authoritative amendment (MF-001).

## 13. Git 计划

```yaml
workflow_mode: NORMAL
branch: "feat/EXT-003-llm-extraction-fingerprint"
baseline_main: "f112d12d28d34de18c637a661a857fcb9f0a401f"
expected_commits:
  - "docs(plan): add EXT-003 llm extraction fingerprint plan"
  - "feat(ext): add llm extraction and candidate fingerprint"
  - "docs(status): record EXT-003 implementation commit and PR"
  - "docs(status): complete EXT-003 after PR merge"
release_phases:
  PLAN_LANDING: "main: approved planning whitelist only; after PLAN_APPROVED; exact branch creation; no implementation"
  IMPLEMENTATION_RELEASE: "feature branch only; exact production/test whitelist; add/commit/push/PR only after implementation approval; no main write/push"
  POST_MERGE_CLEANUP: "NORMAL only after verified MERGED PR; complete governance on main; delete only exact planned branch"
out_of_scope_changes:
  - "authoritative specification"
  - "EXT-001 Kafka/topic/group/offset/task status semantics"
  - "EXT-002 raw validation/normalization/redaction/first-person semantics"
  - "EXT-004 entity alignment or database IDs"
  - "EXT-005 reconciliation/duplicate merge/conflict"
  - "EXT-006 Neo4j graph transaction"
  - "EXT-007 retrieval indexing/Embedding/Elasticsearch"
  - "EXT-008 retry/admin API"
  - "EXT-009 full E2E"
  - "DEV-006 / PR #13"
  - "dependencies, migrations, settings Contract expansion, secrets, real user data"
```

## 14. Plan Amendment

Future changes require an appended amendment and a new Plan Review. No approved plan text may be silently overwritten.

### Amendment 001

- 日期：null
- 原计划：Initial fail-closed plan (Round 1)
- 修改内容：null
- 修改原因：null
- 是否影响技术规格：null
- 审批状态：superseded by Amendment 002

### Amendment 002 — AUTHORIZED_EXT_003_MVP_AMENDMENT (authoritative contract closure)

- 日期：2026-08-12
- 原计划：Round 1 plan + PLAN_REJECTED Round 1 review (BLOCKER=7, MUST_FIX=2, SHOULD_FIX=3)
- 修改内容：Incorporates all 13 human/spec-owner decisions into §5–§7 contracts; records Appendix B Amendment EXT-003; resolves OI-EXT-003-001/002/003/004; adds deferred OI-EXT-003-005; unblocks fingerprint, duplicate merge, correction prompt, legal-empty terminal mapping, source-ref error mapping, blank-output mapping, MF-001/MF-002, and pipeline boundary without modifying `PipelineTerminalDecision`.
- 修改原因：Human `AUTHORIZED_EXT_003_MVP_AMENDMENT` after Round 1 Plan Review rejection.
- 是否影响技术规格：**是** — authoritative append-only Appendix B recorded in specification; dependency changes `NONE`.
- 审批状态：PLAN_APPROVED（Round 2 Plan Review + human PLAN_APPROVED）

## 15. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
| 2026-08-12 03:05 UTC | Planner created fail-closed plan | Planning whitelist only; no business code or tests | N/A | OI-EXT-003-001/002/003/004 blocking; awaiting Plan Review |
| 2026-08-12 03:06 UTC | Independent Plan Review | No file changes by reviewer | N/A | PLAN_REJECTED; BLOCKER=7, MUST_FIX=2, SHOULD_FIX=3; collision policy, legal-empty terminal handling, source-reference mapping, and blank-output mapping also require authoritative closure |
| 2026-08-12 05:35 UTC | Planner Amendment 002 remediation | Appendix B recorded; Task Plan/open_issues/progress/master_plan synchronized; no business code or tests | N/A | All 13 authorized decisions incorporated; OI-EXT-003-001/002/003/004 resolved; OI-EXT-003-005 deferred; `approval_posture=AWAIT_PLAN_REVIEW`; `amendment_recorded=true` |
| 2026-08-12 13:45 UTC | Human PLAN_APPROVED + SF-1 MVP_LOCAL_DECISION | Task Plan Step 5 orchestration owner=`extraction_llm_service.py`; approval_gates updated; progress/master_plan synchronized; no business code or tests | N/A | Round 2 SHOULD_FIX=1 resolved without new Plan Review; `extraction_archive_preprocessing_service.py` compose-only; no whitelist expansion |
| 2026-08-12 14:10 UTC | Developer implementation Steps 1-6 | Created extraction_llm models/service/fingerprint; DeepSeek extraction profile; repository set_extraction_result; preprocessing compose_extraction_pipeline; full scoped tests | 58 passed; ruff PASS; mypy PASS | SF-1 orchestration in extraction_llm_service.py; PipelineTerminalDecision/worker unchanged; EXT-004 deferred |
| 2026-08-12 14:30 UTC | Developer P1 remediation (CODE_REVIEW_REJECTED) | P1-1: non-event memories require null start_time/end_time/original_time_text; U10 parametrized test added; P1-2: reverted `.cursor/commands/orchestrate-task.md` to main | 63 passed; ruff PASS; mypy PASS | Minimal scope; P2/P3 untouched |
| null | Code Review | null | null | null |
| null | Release | null | null | null |

## 16. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
| `src/memory_system/domain/models/extraction_llm.py` | created — strict extraction input/output/result models |
| `src/memory_system/domain/services/extraction_llm_service.py` | created — LLM/validate/fingerprint/pipeline handoff orchestration |
| `src/memory_system/domain/services/extraction_fingerprint.py` | created — SHA-256 fingerprint helper |
| `src/memory_system/infrastructure/llm/deepseek_client.py` | modified — internal `settings_profile` extraction/compression selection |
| `src/memory_system/infrastructure/llm/fake_client.py` | modified — prompt capture and kwargs passthrough for tests |
| `src/memory_system/infrastructure/mongodb/extraction_task_repository.py` | modified — `set_extraction_result` conditional helper |
| `src/memory_system/domain/services/extraction_archive_preprocessing_service.py` | modified — `compose_extraction_pipeline` compose-only wiring |
| `tests/unit/test_extraction_llm_service.py` | created |
| `tests/unit/test_extraction_fingerprint.py` | created |
| `tests/unit/test_deepseek_llm_client.py` | modified — extraction profile test |
| `tests/contract/test_ext003_contract.py` | created |
| `tests/contract/helpers/extraction_llm_fake.py` | created |
| `tests/integration/test_extraction_llm_fake.py` | created |
| `tests/unit/test_extraction_task_repository.py` | modified — set_extraction_result tests |
| `tests/unit/test_extraction_pipeline_ext002.py` | modified — empty archive zero-LLM via composed pipeline |

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit | `uv run pytest tests/unit/test_extraction_fingerprint.py tests/unit/test_extraction_llm_service.py tests/unit/test_deepseek_llm_client.py tests/unit/test_extraction_task_repository.py tests/unit/test_extraction_pipeline_ext002.py::test_ext003_empty_archive_pipeline_zero_llm -q` | 63 passed |
| Contract | `uv run pytest tests/contract/test_ext003_contract.py -q` | PASS (included above) |
| Integration | `uv run pytest tests/integration/test_extraction_llm_fake.py -q` | PASS (included above) |
| E2E | N/A; out of scope | Not run |
| Ruff | scoped touched files | PASS |
| Mypy | scoped production files | PASS |

### Review 结果

```yaml
plan_review: PLAN_APPROVED
plan_review_round: 2
plan_review_blocker: 0
plan_review_must_fix: 0
plan_review_should_fix: 1
plan_review_prior_result: "Round 1 PLAN_REJECTED; BLOCKER=7, MUST_FIX=2, SHOULD_FIX=3"
human_plan_approved: true
sf1_mvp_local_decision: "orchestration owner extraction_llm_service.py; preprocessing compose-only"
amendment_recorded: true
amendment_id: EXT-003-002
code_review: CODE_REVIEW_APPROVED
code_review_round: 2
blocker: 0
must_fix: 0
should_fix: 1
p2: 1
p3: 1
review_report: CODE_REVIEW_APPROVED
```

### Git 记录

```yaml
branch: "feat/EXT-003-llm-extraction-fingerprint"
plan_commit: "81cf1adf21bf39d2980af41ee171a8bf646f018e"
implementation_commit: "7c6309ee68b01a6604b79253cea65be6fa26a0c6"
implementation_commit_message: "feat(ext): add llm extraction and candidate fingerprint"
status_record_committed: "7073811e4160e0f0fa2398b2b2b7414bdbe82c87"
pr: "#37"
pr_url: "https://github.com/xu-jia-ming/memory_system/pull/37"
pr_state: OPEN
merge_commit: null
```

### 最终状态

`committed` — IMPLEMENTATION_RELEASE complete; PR #37 OPEN; awaiting human merge
