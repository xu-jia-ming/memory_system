# EXT-002 Archive 读取 / 预处理 / 脱敏

## 1. 任务信息

```yaml
task_id: EXT-002
task_name: Archive 读取 / 预处理 / 脱敏
status: tested
workflow_mode: NORMAL
workflow_mode_source: explicit
planning_baseline_main: "13e1dae36a0b0d94415d9581b2a5fe53c990545f"
branch: "feat/EXT-002-archive-read-preprocess-redact"
created_at: "2026-08-11 15:36 UTC"
updated_at: "2026-08-12 10:18 UTC"
plan_review_round: 4
amendment: "004 — EXT-002 specification/governance amendment: terminal mappings, strict raw validation, deterministic redaction, and handoff order"
prerequisites:
  - "EXT-001 — SATISFIED/completed; PR #34 MERGED"
  - "Context Archive / STM archive writers — completed and read-only reuse"
blocking_open_issues: []
resolved_open_issues:
  - "OI-EXT-002-001: resolved by authoritative Amendment EXT-002-004"
  - "OI-EXT-002-002: resolved by authoritative Amendment EXT-002-004"
  - "OI-EXT-002-003: deferred/out-of-scope by authoritative Amendment EXT-002-004"
  - "OI-EXT-002-004: resolved by authoritative Amendment EXT-002-004"
  - "OI-EXT-002-005: resolved by authoritative Amendment EXT-002-004"
```

Authoritative specification: `01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`, especially §1.2.2, §1.2.4, §2.1.1, §2.1.3–§2.1.6, §2.1.15, §2.1.16, §3.6, §3.19, §3.20, §3.27, §3.28, and Appendix A Amendment EXT-002-004.

## 2. 任务目标

Implement only the first real `ExtractionPipelinePort` stage:

1. define the minimum read-only raw BSON boundary needed to validate one immutable `context_archive` by the event `archive_id`;
2. validate every consumed Archive field and nested message with exact types and no coercion before normalization, preprocessing, redaction, or handoff;
3. preserve raw Archive data, apply deterministic normalization, and deterministically redact only `messages[].content` before any handoff;
4. use the authoritative EXT-002 terminal mappings and existing EXT-001 terminal-persistence/offset gate;
5. preserve role/provenance, keep first-person binding deferred/out of scope, and do not implement EXT-003 extraction output or persistence.

## 3. 非目标

- EXT-003 Structured Extraction, LLM client/prompt/schema/fingerprint, and `extraction_result` persistence.
- EXT-004–EXT-009 entity alignment, reconciliation, Neo4j, Elasticsearch, retry/status HTTP APIs, E2E.
- Any Kafka consumer event schema, consumer group, partition/offset semantics, task schema/status transition, or `ExtractionPipelinePort` signature change from EXT-001.
- Any `context_archive` schema/index/migration/repository write behavior, STM archive creation, Redis, compression, producer, or republish behavior.
- DEV-006 and PR #13.
- Any redaction package or other dependency addition; settings/configuration expansion; auto retry/DLT/Outbox.
- Semantic summarization, message reordering, inferred entity/relationship/time conversion, content truncation, raw Archive mutation, or logging of raw/normalized/redacted message contents.

## 4. 当前代码状态与已合并 Contract

### 4.1 Baseline and prerequisite evidence

| Check | Result |
|---|---|
| branch | `main` |
| `HEAD` | `13e1dae36a0b0d94415d9581b2a5fe53c990545f` — MATCH |
| planning-start worktree | clean |
| EXT-001 | completed; `archive_id` unique task, consumer boundary and terminal-persist/offset gate already merged |

### 4.2 EXT-001 contracts that EXT-002 must preserve

| Contract | Fixed behavior |
|---|---|
| `memory_extraction_task` | Exact fields: `task_id`, `archive_id`, `user_id`, `status`, `attempt_count`, `extraction_result`, `last_error`, `created_time`, `updated_time`, `completed_time`; no `session_id`, `event_id`, or event payload persistence. |
| Business idempotency | `archive_id` is the sole task uniqueness key. Same Archive with a new `event_id` reuses its task. |
| Event-only fields | `event_id` and `session_id` remain in `ArchiveCreatedEvent`; neither is added to task storage. `session_id` is available to this pipeline through `event`, not through a task field. |
| Pipeline boundary | Preserve `async run(task, event) -> PipelineTerminalDecision`. EXT-002 is its implementation, not a Port redesign. Existing non-null `task.extraction_result` continues to mean a later stage must not call LLM again; EXT-002 does not create or overwrite it. |
| State/offset | Consumer persists `completed` or `failed` and commits only after terminal Mongo success. Pipeline returns `complete`, `fail(last_error)`, or `abort_without_terminal`; it neither commits an offset nor writes a task terminal state itself. |
| Existing early states | Consumer still early-commits already `completed`/`failed` tasks; EXT-002 receives only `pending`/`processing` work. |

### 4.3 `context_archive` and STM archive writer facts

`context_archive` is immutable after creation and contains exactly `archive_id`, `user_id`, `session_id`, `archive_batch_key`, `base_compression_version`, ordered `messages`, and `created_time`. Each persisted message contains only `message_id`, `role`, `content`, and `timestamp`; it intentionally has no `estimated_tokens`. `archive_id` and `archive_batch_key` have unique indexes. The existing typed `find_context_archive_by_id` performs coercive mapping and therefore is not the EXT-002 strict-validation boundary.

STM `create_or_reuse_context_archive` generates/reuses by deterministic `archive_batch_key`; normal compression and Session Close write the same immutable Archive shape, preserve message order, and publish an at-least-once six-field event after persistence. Reused events may receive new `event_id`. EXT-002 uses one new read-only repository method, `find_context_archive_document_by_id`, looked up only by `archive_id`, returning the raw Mongo/BSON mapping (or `None`) without Pydantic/domain coercion. It must not write, repair, migrate, duplicate-persist, or alter the semantics of `find_context_archive_by_id`.

## 5. Exact implementation plan

### Step 1 — Archive read and validation models/service (Amendment 004 effective state)

Allowed production files:

- `src/memory_system/domain/models/extraction_preprocessing.py` — create strict raw/normalized models and finalize only the internal `ExtractionReadyArchive` after validation, preprocessing, and redaction all pass.
- `src/memory_system/domain/services/extraction_archive_preprocessing_service.py` — consume the raw mapping, validate it completely, and gate all later normalization/redaction/handoff.
- `src/memory_system/infrastructure/mongodb/context_archive_repository.py` — add only the read-only `find_context_archive_document_by_id` raw-document method; preserve all existing typed method behavior.
- `src/memory_system/domain/services/extraction_pipeline_port.py` — modify only if required to add a type-only import/export for the already-fixed Port; no signature or decision semantic change.
- `src/memory_system/entrypoints/extraction_worker.py` — replace EXT-001 refusal-only entrypoint only after the complete, approved real pipeline can be constructed without speculative EXT-003 behavior; otherwise it remains refusal-only.

Input receipt is exactly the existing `MemoryExtractionTask` plus `ArchiveCreatedEvent` passed by `ExtractionPipelinePort.run`. Archive lookup is exactly `find_context_archive_document_by_id(mongodb, event.archive_id)`; no Redis, task `session_id`, batch-key lookup, or direct Mongo query elsewhere. The method is read-only, filters only `{"archive_id": archive_id}`, returns the raw Mongo/BSON mapping, and performs no Pydantic/domain conversion. No migration, duplicate persistence model, write, repair, or change to `find_context_archive_by_id` is allowed.

Strict raw validation boundary, before normalization, preprocessing, redaction, token estimation, or handoff. Amendment 004 is the effective contract: storage-only Mongo `_id` is ignored; every other unknown application field at top-level, nested message, or nested object is invalid; no coercion is permitted; all fields and all messages must be validated before constructing any partial model or output.

| Consumed field | Exact required shape | Empty/null behavior | No-coercion rule |
|---|---|---|---|
| `archive_id` | required actual `str`; equals `event.archive_id` | `""` and `null` invalid | reject number/object substitution; do not stringify |
| `user_id` | required actual `str` | `""` and `null` invalid | reject number/object substitution; do not stringify |
| `session_id` | required actual `str` | `""` and `null` invalid | reject number/object substitution; do not stringify |
| `archive_batch_key` | required actual `str` | `""` and `null` invalid | reject number/object substitution; do not stringify |
| `base_compression_version` | required actual `int`; bool is not accepted as integer | `null` invalid; zero is valid | reject numeric strings, floats, decimal-like values, and bool; do not `int()` |
| `messages` | required actual `list` | empty list valid; `null` and non-list invalid | reject object/string/scalar substitution; do not wrap/coerce |
| `created_time` | required actual `int` Unix timestamp; bool is not accepted as integer | `null` invalid | reject numeric strings, floats, datetime-like values, and bool; do not parse |
| each message | required BSON mapping with exactly `message_id`, `role`, `content`, `timestamp` | `null`, scalar, missing field, or partial object invalid | reject nested non-object/partial values; do not construct a partial message |
| message `message_id` | required actual `str` | `""` and `null` invalid | reject number/object substitution; do not stringify |
| message `role` | required actual `str` exactly `user` or `assistant` | `""` and `null` invalid | reject enum-like number/object; do not stringify |
| message `content` | required actual `str` | `null` invalid; empty string valid and preserved | reject number/object/bytes substitution; do not stringify |
| message `timestamp` | required actual `int` Unix timestamp; bool is not accepted as integer | `null` invalid | reject numeric strings, floats, datetime-like values, and bool; do not parse |

Missing fields, nulls, forbidden empty identity strings, invalid extra fields, unknown nested fields, string/number substitutions, invalid datetime-like values, malformed collections, invalid roles, and partially accepted nested objects all fail the gate as `invalid_archive`. Validation must complete over the full document and every message before any output object, normalized field, detector, token estimate, or handoff is constructed. Corrupt archives produce no partial output. The only tolerated unknown field is storage-only `_id`, which is ignored and never exposed.

| Raw input class | Exact boundary and handling | Existing pipeline/terminal/offset consequence |
|---|---|---|
| Missing Archive | Repository lookup by `event.archive_id` returns no document. Do not inspect messages or begin preprocessing. | `PipelineTerminalDecision.fail`, task `failed`, `error_code=archive_not_found`, `failed_stage=archive_read`; EXT-001 persists terminal state before committing the offset; persistence failure leaves the offset uncommitted. |
| Present structurally invalid/corrupt document | Any required top-level field is missing/invalid, `messages` is not an array, or a nested/message structure is not valid. Do not inspect, normalize, redact, count tokens, or partially preprocess. | `PipelineTerminalDecision.fail`, task `failed`, `error_code=invalid_archive`, `failed_stage=archive_validate`; terminal persistence precedes offset commit; persistence failure means no commit. |
| Valid document with message-level structurally invalid data | Top-level shape and array pass, but any message field is missing, invalid, null, forbidden-empty, wrong type, invalid role, or invalid timestamp. Validate all messages before output. | Same `PipelineTerminalDecision.fail`, task `failed`, `error_code=invalid_archive`, `failed_stage=archive_validate`; never partially process preceding valid messages. |
| Valid/preprocessable Archive | All seven top-level fields and every message pass exact validation, ownership checks pass, and token limit/order checks pass. Only now may deterministic normalization and redaction run. Empty `messages` is valid and may return existing `complete` without LLM/EXT-003/Neo4j; EXT-001 persists `completed` before offset commit. | After preprocessing and redaction pass, finalize the internal `ExtractionReadyArchive`; no raw/pre-redaction content is included. |

Ownership mismatch maps to the specified `archive_ownership_mismatch` and performs no preprocessing. Aggregate token overflow maps to specified `archive_too_large` with no chunking/truncation. Unexpected non-deterministic infrastructure/internal failure maps to `abort_without_terminal` with no offset commit. The EXT-001 consumer owns terminal persistence and offset commit.

### Step 2 — Authorized preprocessing and provenance

For every validated non-empty message, retain a raw in-memory message with the original `content` and make a separate temporary `normalized_content`:

1. Unicode NFKC normalization.
2. Compress consecutive spaces to one space and consecutive blank lines to one newline.
3. Strip leading/trailing whitespace.

The raw `content` is never changed, persisted, or logged. `message_id`, `role`, and `timestamp` are copied unchanged, in Archive order. Normalization is deterministic and does not summarize, reorder, delete messages, infer facts, resolve an uncertain relationship, convert relative time, or alter timestamps.

Reference assistance is not implemented or represented while OI-EXT-002-003 is open. Preserve original role and message provenance; synthesize no identity representation, add no durable field, and make no output contract depend on first-person binding. Relative-time metadata may only use its source `timestamp` and an explicit timezone; Archive has no timezone field, so relative expressions remain unresolved/unknown. The worker clock must never be used.

### Step 3 — Deterministic redaction and EXT-003 handoff boundary (Amendment 004 effective state)

Use a deterministic local detector only: no LLM, network, external service, or new third-party dependency. Redact only `messages[].content`; never redact provenance/identity fields and do not implement general PII handling. Categories are exactly labelled passwords, labelled verification/OTP, API keys, access/bearer tokens, private keys, Luhn-valid full card numbers, and labelled CVV/CVC. Labels/context are required for password, verification/OTP, and CVV/CVC; API keys, access/bearer tokens, private-key blocks, and Luhn-valid full card numbers follow their authorized deterministic forms.

After approved normalization, apply precedence in this exact order: private-key blocks; bearer/access-token forms; explicitly labelled credential key/value forms; full payment-card numbers validated with Luhn. Verification codes and CVV/CVC require explicit label/context. Collect spans, sort by source position, merge overlaps, choose the longest span for equivalent starts, and replace every merged span with exact `[REDACTED_SECRET]`; disjoint spans are replaced independently. Never log matched values. No match is success.

If redaction fails, do not handoff and do not return unredacted or partially redacted content: return `PipelineTerminalDecision.fail`, task `failed`, `error_code=redaction_failed`, `failed_stage=redaction`. Terminal persistence must succeed before offset commit; persistence failure means no commit. Unexpected non-deterministic infrastructure/internal failures use `abort_without_terminal` and no offset commit.

Only after raw validation, deterministic preprocessing, and deterministic redaction may the conditional EXT-002 -> EXT-003 handoff use the §2.1.5 LLM-input envelope:

```text
ExtractionReadyArchive (finalized only after raw validation PASS -> preprocessing PASS -> redaction PASS; internal, non-durable, and not an EXT-003 implementation) {
  archive_id: str,
  user_id: str,
  session_id: str,
  messages: [
    {
      message_id: str,
      role: "user" | "assistant",
        content: str,       # authorized normalized+redacted representation only
      timestamp: int
    }
  ]
}
```

The only justified candidate fields are sourced from the immutable Archive/event: `archive_id`, `user_id`, and `session_id` are `str` identifiers; each message carries Archive-sourced `message_id`/`role`/`timestamp` with strict existing types and Archive array ordering; `content` is normalized/redacted text, never raw or pre-redaction, and is consumer-reliant only for a future authorized LLM handoff. No field is persisted by EXT-002, no first-person representation is added, and EXT-003 cannot rely on first-person binding. EXT-002 does not define EXT-003 extraction inputs beyond §2.1.5, call an LLM, build prompts, validate Structured Output, or persist `extraction_result`.

### Step 4 — Wire only the available real stage and observability

Use the existing consumer/service and repository composition. Do not modify six-field event parsing, key validation, group ID, manual commit, serial consumption, `$setOnInsert`, or terminal persistence semantics.

Failure logs must include `task_id`, `archive_id`, `user_id`, `failed_stage`, and `attempt_count`; `session_id` may be included. Logs/metrics must not include complete raw messages, normalized content, redacted content, full prompt/response, credential values, or connection secrets. No new metric name/config/dependency is planned.

## 6. Production and planning whitelist

### 6.1 Plan-landing governance files

- `02_开发管理/tasks/EXT-002-archive-read-preprocess-redact.md`
- `02_开发管理/open_issues.md`
- `02_开发管理/progress.md`
- `02_开发管理/master_plan.md`

### 6.2 Precise implementation whitelist

- `src/memory_system/domain/models/extraction_preprocessing.py` (create)
- `src/memory_system/domain/services/extraction_archive_preprocessing_service.py` (create)
- `src/memory_system/domain/services/extraction_redaction_service.py` (create: deterministic local detector/replacer only)
- `src/memory_system/infrastructure/mongodb/context_archive_repository.py` (modify: one raw read-only lookup method only)
- `src/memory_system/domain/services/extraction_pipeline_port.py` (type-only integration only; no signature/semantic change)
- `src/memory_system/entrypoints/extraction_worker.py` (only real-pipeline wiring after OI resolution; otherwise no change)
- `tests/unit/test_extraction_archive_preprocessing.py` (create)
- `tests/unit/test_extraction_redaction.py` (create)
- `tests/unit/test_extraction_pipeline_ext002.py` (create)
- `tests/contract/test_ext002_contract.py` (create)
- `tests/integration/test_ext002_archive_preprocessing_mongo.py` (create)
- `tests/unit/test_context_archive_repository.py` (extend: raw lookup/no-coercion assertions only)
- `tests/integration/test_context_archive_mongo.py` (extend: raw lookup by archive_id/no-write assertions only)

Explicitly excluded: all migrations; changes to `context_archive` schema, typed model, existing typed repository method semantics, or STM writer; duplicate persistence models; STM services and tests; ArchiveCreatedEvent/publisher/consumer; extraction task model/repository/consumer service; settings/configs/dependency manifests/lockfiles; LLM clients/prompts; EXT-003+; Neo4j/Elasticsearch/Redis; DEV-006; PR #13; all E2E paths.

## 7. 数据一致性与恢复

| Dimension | Conclusion and handling |
|---|---|
| Atomicity | Archive read/preprocess is read-only. Terminal task state and Kafka offset remain EXT-001’s separate, ordered operations. |
| Idempotency | `archive_id` task identity is unchanged; repeated/replayed event re-reads the same immutable Archive. |
| Concurrency | Consumer remains serial per Kafka partition. Archive is immutable; no EXT-002 write race exists. |
| Version conflict | Not applicable: no Archive update/version is introduced. |
| User isolation | Require Archive/event/task `user_id` equality and Archive/event `session_id` equality before handoff. |
| Partial failure | No LLM/graph side effect in this task. Standard permanent validation failure becomes failed only through EXT-001 terminal persistence; that persistence must succeed before offset commit. |
| Process recovery | Before terminal persistence: no commit -> replay and reread. After terminal persistence before commit: replay sees failed/completed and consumer commits without re-running. |
| Privacy | Raw Archive remains Mongo-only and immutable; no raw message is sent to an LLM or log. Amendment 004 redaction validation gates the LLM handoff; only normalized+redacted content may proceed. |

## 8. 测试计划

### Unit

| Scenario | Expected |
|---|---|
| Raw repository method | Query is exactly by `archive_id`; returns the untouched mapping; no typed coercion, write, repair, or duplicate persistence; existing typed lookup tests remain unchanged. |
| Archive absent | `archive_not_found` / `archive_read`; no preprocessing; terminal persistence precedes offset commit and persistence failure leaves offset uncommitted. |
| Each required top-level field | Missing, null, forbidden empty, string/number substitution, float/bool/datetime-like timestamp, extra-invalid shape, and `messages` non-array are rejected before any message/output work. |
| Valid document with invalid message data | Missing/extra field, partial object, null/forbidden empty, wrong type, invalid role, numeric-string/float/bool/datetime-like timestamp rejects as strict `error_code=invalid_archive`, `failed_stage=archive_validate`; no partial preprocessing. |
| Valid empty messages | `complete`; no EXT-003/LLM/Neo4j collaborator call. |
| Ordered messages with equal timestamps | Original array order and IDs are unchanged. |
| Token sum at limit / above limit | Existing estimator, `archive_too_large` only above configured limit; no chunk/truncate. |
| NFKC, whitespace/blank-line compression, trim | Exact deterministic `normalized_content`; raw content unchanged. |
| First person / relative time without timezone / unknown metadata | Preserve role/provenance; synthesize no identity representation or durable field; retain unresolved time and perform no worker-clock conversion or inference. |
| Redaction gate | Only normalized+redacted content may be handed off; raw/pre-redaction content never leaks. |
| Redaction failure | `redaction_failed` / `redaction`; no handoff and no unredacted or partial output; terminal persistence precedes offset commit. Nondeterministic infrastructure/internal failure is `abort_without_terminal` with no offset commit. |
| Pipeline decision integration | Success/standard failure maps only to existing `PipelineTerminalDecision`; no direct task state/offset write. |

### Contract

| Scenario | Expected |
|---|---|
| Raw repository boundary | `find_context_archive_document_by_id(mongodb, archive_id)` is the only EXT-002 lookup; returns raw mapping/`None`, performs no coercion or write, and does not alter `find_context_archive_by_id`. |
| Archive input required fields and roles | Matches §1.2.2/§2.1.5; all seven top-level fields and four message fields use exact strict BSON types; no `estimated_tokens` in persisted messages. |
| Task/event boundary | task remains without session/event IDs; handoff obtains IDs from event and validates ownership. |
| Handoff envelope | exact archive/user/session fields, ordered provenance fields, no raw/normalized dual content disclosure. |
| Error set | specification-authorized `archive_not_found`, `archive_ownership_mismatch`, `invalid_archive`, `archive_too_large`, and `redaction_failed`; mappings are `archive_read`, `archive_validate`, and `redaction` as specified; unexpected nondeterministic infrastructure/internal failure aborts without terminal. |
| Redaction/dependencies | Amendment 004 exact deterministic local rules are effective; no redaction package or dependency manifest change. |
| Scope fence | no EXT-003 LLM/prompt/schema, Kafka semantic, context_archive schema, migration, DEV-006, or PR #13 drift. |

### Mongo integration

Use real compose-test Mongo and existing migrations where warranted:

| Scenario | Expected |
|---|---|
| Read a persisted STM-shape Archive by `archive_id` | Raw mapping is returned by the new read-only method; strict validation can consume it without changing the stored document. |
| Missing Archive | no Archive write; terminal failure decision returned. |
| Directly inserted corrupted documents (missing fields/messages non-array) | fail closed before message processing; `invalid_archive` only under authorized contract; no LLM-facing handoff. |
| Valid document containing wrong-typed or invalid message data | strict no-coercion message validation fails closed; no partial preprocessing or LLM-facing handoff. |
| Empty, ownership-mismatched, oversized Archive | correct standard terminal decision; no mutation of the stored document. |
| Reload after failed/replayed processing | same Archive content/order and same deterministic preprocessing result. |

### E2E and failure injection

No E2E is authorized: full Session -> Extraction is EXT-009, and LLM extraction is EXT-003. Inject repository/terminal-persist failure through EXT-001’s established tests to confirm no offset commit; do not rewrite Kafka tests. Inject handoff collaborator failure before terminal decision to confirm the task remains processing and is replayable. No test may weaken the redaction gate or send Archive content to a real LLM.

### Amendment 004 exact conformance matrix

The following numbered cases are mandatory and belong in the named unit, contract, or integration suites. They are the effective acceptance matrix; no case may be replaced by a weaker aggregate assertion.

#### Raw validation RAW-01 through RAW-12

| ID | Fixture and assertion |
|---|---|
| RAW-01 | Complete valid seven-field Archive plus valid messages passes strict validation; actual `str`/`int`/`list` types, `role` in `user|assistant`, order, and empty `messages` behavior are preserved. |
| RAW-02 | Each required top-level field missing or `null` (`archive_id`, `user_id`, `session_id`, `archive_batch_key`, `base_compression_version`, `messages`, `created_time`) returns `invalid_archive` / `archive_validate`; no preprocessing or output. |
| RAW-03 | Empty identity strings for all four identity fields, and empty `message_id`, return `invalid_archive`; empty message `content` remains valid and preserved. |
| RAW-04 | Top-level wrong types for every field (number/object/list/string substitutions, including `messages` non-list) return `invalid_archive`; no stringify, wrapping, or other coercion. |
| RAW-05 | `base_compression_version` and `created_time` reject bool, float, numeric string, decimal-like, and datetime-like values; actual integers pass. |
| RAW-06 | Message missing/`null`/scalar/partial object, wrong collection shape, or malformed nested object returns `invalid_archive`; preceding valid messages are not processed. |
| RAW-07 | Message field missing/`null`/wrong type, empty identity, bytes-like content, or non-string role returns `invalid_archive`; actual content string, including empty string, is retained only after full validation. |
| RAW-08 | Message role values other than exactly `user` or `assistant` (including case variants, enum-like numbers, and objects) return `invalid_archive`. |
| RAW-09 | Unknown application fields at top-level, message-level, and nested-object level return `invalid_archive`; storage-only Mongo `_id` alone is ignored and never exposed. |
| RAW-10 | Archive ID lookup is the only read, using `find_context_archive_document_by_id(mongodb, event.archive_id)` and raw mapping semantics; existing typed lookup remains unchanged and no write/repair/duplicate model occurs. |
| RAW-11 | Missing lookup result returns `archive_not_found` / `archive_read`; terminal persistence is required before offset commit, and terminal persistence failure leaves the offset uncommitted. |
| RAW-12 | Full-document validation precedes normalization, preprocessing, redaction, token estimation, and handoff; any invalid field yields no partial model, content, detector call, or output. |

#### Redaction RED-01 through RED-27

| ID | Fixture and assertion |
|---|---|
| RED-01 | Labelled password credential is replaced with exact `[REDACTED_SECRET]`; matched value is absent from output and logs. |
| RED-02 | Labelled verification code/OTP is replaced; unlabelled number/code remains unchanged. |
| RED-03 | API key in each authorized API-key form is replaced; ordinary identifier-like text is not. |
| RED-04 | Access/bearer token form is replaced; ordinary prose containing “access” or “bearer” without a token is not. |
| RED-05 | Private-key block is replaced as one span; delimiters and key material are absent from output. |
| RED-06 | Luhn-valid full card number is replaced; card-like number failing Luhn remains unchanged. |
| RED-07 | Labelled CVV/CVC is replaced; unlabelled three/four-digit text remains unchanged. |
| RED-08 | General PII (name, address, email, phone, date, account number without an authorized category) is not redacted. |
| RED-09 | Redaction target is only `messages[].content`; `archive_id`, `user_id`, `session_id`, `archive_batch_key`, `message_id`, `role`, and `timestamp` are unchanged. |
| RED-10 | NFKC and whitespace/blank-line normalization occurs before detection; matching is performed on normalized text and normalized non-secret text is retained. |
| RED-11 | Empty normalized content is retained; no-match content is a successful redaction result, not a failure. |
| RED-12 | Precedence is private-key block, bearer/access token, labelled credential key/value, then Luhn-valid card; overlapping candidates resolve according to that order. |
| RED-13 | Collected spans are sorted by source position; multiple disjoint spans each receive an independent exact marker. |
| RED-14 | Overlapping spans merge into one replacement; equivalent start positions choose the longest span. |
| RED-15 | Boundary, malformed, partial, and near-match negatives do not over-redact; only authorized complete matches are replaced. |
| RED-16 | No matched secret, raw content, pre-redaction content, or full normalized secret is present in return values, logs, metrics, or exceptions. |
| RED-17 | Provenance/order case preserves message array order, message IDs, roles, and timestamps; first-person wording adds no identity field or reliance. |
| RED-18 | Inject detector/redaction failure: return `redaction_failed` / `redaction`, do not handoff, do not output unredacted or partially redacted content, persist terminal state before offset, and do not commit on persistence failure. |
| RED-19 | Inject terminal persistence failure after `redaction_failed`: no Kafka offset commit; replay remains possible and no redacted content is persisted by EXT-002. |
| RED-20 | Inject nondeterministic infrastructure/internal failure: return `abort_without_terminal`, do not terminalize, and do not commit offset. |
| RED-21 | A valid Archive with all messages passing redaction produces `ExtractionReadyArchive` only after validation PASS -> preprocessing PASS -> redaction PASS. |
| RED-22 | `ExtractionReadyArchive` contains exactly ordered `archive_id`, `user_id`, `session_id`, and `messages`; each message contains only `message_id`, `role`, normalized+redacted `content`, and `timestamp` with specified types. |
| RED-23 | Handoff/output contains no raw content, no pre-redaction content, no temporary normalized-only field, no first-person field, and no extra provenance or application field. |
| RED-24 | Redaction service is deterministic across repeated runs and does not use LLM, network, external service, or new dependency. |
| RED-25 | Ownership mismatch and aggregate token overflow fail through their already authorized mappings before redaction; no chunking, truncation, or redaction bypass is introduced. |
| RED-26 | Empty Archive reaches the existing `complete` terminal path without LLM/EXT-003 behavior; terminal persistence precedes offset commit. |
| RED-27 | Contract/integration trace verifies no mutation of the raw Mongo Archive and no change to EXT-001 Kafka/task status, terminal persistence, or offset semantics. |

## 9. 验收标准

- [ ] Baseline and EXT-001 prerequisite are revalidated before implementation.
- [ ] Archive lookup uses only event `archive_id` and the new read-only raw repository boundary; existing typed lookup semantics are unchanged.
- [ ] Ownership triangle and all §2.1.5 message/token/order rules have direct tests.
- [ ] Valid empty Archive reaches `completed` through existing terminal/offset gate, with no LLM/Neo4j invocation.
- [ ] Raw Archive remains unchanged; deterministic normalized temporary data preserves provenance/order.
- [ ] No relative-time conversion without explicit timezone; no semantic compression/inference.
- [ ] Deterministic local redaction implements only the exact Amendment EXT-002-004 categories/rules on `messages[].content`; no new dependency, no matched-value logging, no raw/pre-redaction handoff, and no EXT-003 implementation.
- [ ] No dependency/settings/schema/contract/Kafka/STM/EXT-003+/DEV-006/PR #13 change.
- [ ] Unit, Contract, and required real-Mongo Integration tests pass; Ruff and mypy pass; review has no P0/P1.

## 10. 风险、阻塞项与规格歧义

### Historical Round 3 issue text (superseded by Amendment 004)

The following Round 3 issue descriptions are retained as append-only historical evidence. Their effective state is the Amendment 004 override in §14 and the conformance matrix above; they are not current blockers or implementation instructions.

### OI-EXT-002-001 — credential redaction rules resolved

| Item | Detail |
|---|---|
| Title | Authoritative deterministic secret-detection/redaction policy is missing. |
| Affected spec section | §2.1.5 (credential replacement before LLM; raw Archive unchanged), with downstream failure interaction in §2.1.15. |
| Currently specified token behavior | A detected sensitive credential is replaced before LLM use by exactly `[REDACTED_SECRET]`; raw Archive is not modified. |
| Missing semantics | Credential classes/rules, boundaries/tokenization, rule order, overlap and multiple-match precedence, malformed/partial matches, normalization-versus-redaction order, detector failure behavior, and fixtures. |
| Privacy risk | Guessing can leak credentials through false negatives or destroy legitimate content through false positives; no-detection is not evidence of safety. |
| Downstream EXT-003 impact | No `ExtractionReadyArchive` handoff, LLM call, prompt input, or EXT-003-ready claim is allowed. |
| Exact decision required | An authoritative specification amendment defining one deterministic secret-detection/redaction policy, including classes, patterns/boundaries, ordering, overlap/multiple-match behavior, malformed/partial-match behavior, normalization order, detector failure handling, and conformance fixtures. Do not choose arbitrary regex defaults. |
| Resolution | Amendment EXT-002-004 fixes exact categories, precedence, normalization order, Luhn validation, span merge/longest-start behavior, marker, no-match success, no-value logging, and failure mapping. |
| Release effect | Deterministic local redaction may be implemented after this plan is approved; no LLM/EXT-003 implementation is included. |

### Other specification issue dispositions

| ID | Ambiguity | Blocking effect |
|---|---|---|
| OI-EXT-002-002 | §2.1.5 calls `normalized_content` temporary but its final LLM input example exposes only `content`; it does not define redaction detection/order, whether redacted normalized text replaces `content`, overlap precedence, or partial-failure behavior. | Handoff/privacy boundary; blocking until amendment. Safe interim: no LLM-facing handoff and no durable field. Decision needed: specify exact order, replacement ownership, overlap, and failure semantics. |
| OI-EXT-002-003 | §2.1.5 requires first-person binding and relative-time resolution but does not define representation, ownership/provenance, EXT-003 consumption, or persistence/non-persistence. | Output/data shape; blocking. Safe interim: preserve original role/provenance, synthesize no identity, add no field, and keep unresolved references unknown. Decision needed: exact ephemeral representation and consumer/persistence rules, with citation. |
| OI-EXT-002-004 | The pipeline may encounter unexpected redaction/configuration failure, but §2.1.15 has no redaction-specific error code and forbids invented codes. | Error/terminal/offset behavior; blocking. Safe interim: remain gated/abort-without-terminal and do not commit an offset. Exact authorized error/stage/terminal mapping requires a specification decision; none is invented. |
| OI-EXT-002-005 | §2.1.5 does not define `failed_stage` vocabulary or explicitly distinguish top-level corrupt documents from valid documents with invalid message elements. | Validation boundary and terminal error contract; blocking. Safe interim: strict no-coercion validation, no partial preprocessing, and only existing error codes; no undocumented stage value. Decision needed: exact boundary and authorized `failed_stage` values for `archive_not_found`/`invalid_archive`. |

All five OI-EXT-002 records are dispositioned by authoritative Amendment EXT-002-004; unrelated Open Issues remain unchanged.

Authoritative disposition override for the preceding historical issue descriptions:

- `OI-EXT-002-001`: resolved — exact deterministic local content-only redaction policy is specified.
- `OI-EXT-002-002`: resolved — normalize, then redact, then expose only normalized+redacted `content`.
- `OI-EXT-002-003`: deferred/out-of-scope — preserve role/provenance; no identity representation or durable field; EXT-003 cannot rely on first-person binding.
- `OI-EXT-002-004`: resolved — `redaction_failed`/`redaction`; nondeterministic infrastructure/internal failure is `abort_without_terminal` with no commit.
- `OI-EXT-002-005`: resolved — `archive_not_found`/`archive_read`; `invalid_archive`/`archive_validate`; terminal persistence precedes offset commit.

## 11. Dependency assessment

No dependency change is expected or authorized. Redaction is a deterministic local implementation using existing dependencies; no manifest or lockfile change is allowed.

## 12. Git 计划

```yaml
branch: "feat/EXT-002-archive-read-preprocess-redact"
workflow_mode: NORMAL
expected_commits:
  - "docs(plan): add EXT-002 archive preprocessing plan"
  - "feat(ext): add archive preprocessing pipeline"
  - "docs(status): record EXT-002 implementation"
release_phases:
  PLAN_LANDING: "main: approved planning whitelist only; docs(plan), ff-only, create exact feat branch"
  IMPLEMENTATION_RELEASE: "feat branch: precise implementation whitelist only; no main write/push"
  POST_MERGE_CLEANUP: "only after MERGED: docs(status): complete on main and delete exact feat branch"
out_of_scope_changes:
  - "Kafka/EXT-001 task and offset semantics"
  - "context_archive/STM schema or writes"
  - "EXT-003+ and Neo4j/Elasticsearch"
  - "dependencies/configs/migrations"
  - "DEV-006 / PR #13"
```

## 13. Machine-readable result

```yaml
plan_file: "02_开发管理/tasks/EXT-002-archive-read-preprocess-redact.md"
scope_summary: "Read immutable Context Archive, strictly validate raw data, deterministically normalize and redact messages[].content, and construct only the post-redaction handoff boundary."
archive_input_contract:
  receipt: "ExtractionPipelinePort.run(task, event)"
  lookup: "find_context_archive_document_by_id(mongodb, event.archive_id)"
  required_archive_fields: [archive_id, user_id, session_id, archive_batch_key, base_compression_version, messages, created_time]
  required_nonempty_message_fields: [message_id, role, content, timestamp]
  missing_archive: "archive_not_found"
  corrupt_archive: "invalid_archive / archive_validate; no partial preprocessing"
  message_invalid_archive: "invalid_archive / archive_validate; strict no-coercion"
  failed_stage: "archive_not_found=archive_read; invalid_archive=archive_validate; redaction_failed=redaction"
  kafka_offset: "commit only after EXT-001 terminal Mongo persistence succeeds; persistence failure and abort_without_terminal leave offset uncommitted"
preprocessing_semantics:
  order: "complete raw validation -> NFKC -> collapse consecutive spaces/blank lines -> trim -> deterministic redaction"
  ordering: "Archive array order; equal timestamps are not sorted"
  metadata: "message_id, role, timestamp; original role/provenance preserved; first-person representation not defined and therefore not synthesized; relative time unresolved without explicit timezone"
  deterministic: true
redaction_semantics:
  marker: "[REDACTED_SECRET]"
  target: "messages[].content only"
  raw_archive_mutation: false
  detector: "deterministic local; no LLM/network/external service/new dependency"
  categories: "explicitly labelled passwords; explicitly labelled verification codes/OTP; API keys; access/bearer tokens; private keys; full card numbers; explicitly labelled CVV/CVC"
  precedence: "private-key blocks; bearer/access-token forms; explicitly labelled credential key/value forms; Luhn-validated full payment-card numbers"
  spans: "source-position sort; overlap merge; longest equivalent start; independent disjoint replacement"
  no_match: "success"
  failure: "redaction_failed / redaction; no handoff and no unredacted or partial content"
  status: "SPECIFIED; implementation pending approved plan"
output_contract:
  name: "ExtractionReadyArchive"
  status: "conditional internal handoff only; not EXT-003 implementation or durable schema"
  fields:
    - "archive_id: Archive/event source, str, original identifier, not persisted by EXT-002"
    - "user_id: Archive/event/task ownership source, str, original identifier, not persisted by EXT-002"
    - "session_id: Archive/event source, str, original identifier, event-only, not persisted by EXT-002"
    - "messages: Archive array order; message_id/role/timestamp source and strict types; content only authorized normalized+redacted temporary text"
  allowed_consumer_reliance: "Only post-validation normalized+redacted content; no first-person identity reliance and no raw/pre-redaction content."
  ext003_definition: "No LLM invocation, extraction definition, prompt/schema, or extraction_result persistence is defined here."
dependency_changes_expected: "NONE"
file_whitelist:
  planning:
    - "02_开发管理/tasks/EXT-002-archive-read-preprocess-redact.md"
    - "02_开发管理/open_issues.md"
    - "02_开发管理/progress.md"
    - "02_开发管理/master_plan.md"
  implementation:
    - "src/memory_system/domain/models/extraction_preprocessing.py"
    - "src/memory_system/domain/services/extraction_archive_preprocessing_service.py"
    - "src/memory_system/domain/services/extraction_redaction_service.py"
    - "src/memory_system/infrastructure/mongodb/context_archive_repository.py (one raw read-only method only)"
    - "src/memory_system/domain/services/extraction_pipeline_port.py"
    - "src/memory_system/entrypoints/extraction_worker.py"
    - "tests/unit/test_extraction_archive_preprocessing.py"
    - "tests/unit/test_extraction_redaction.py"
    - "tests/unit/test_extraction_pipeline_ext002.py"
    - "tests/contract/test_ext002_contract.py"
    - "tests/integration/test_ext002_archive_preprocessing_mongo.py"
    - "tests/unit/test_context_archive_repository.py (raw lookup assertions only)"
    - "tests/integration/test_context_archive_mongo.py (raw lookup/no-write assertions only)"
test_plan: "Unit + Contract + real Mongo Integration; no E2E; failure injection preserves EXT-001 terminal/offset semantics."
open_issues: []
issue_dispositions:
  - "OI-EXT-002-001 resolved"
  - "OI-EXT-002-002 resolved"
  - "OI-EXT-002-003 deferred/out-of-scope"
  - "OI-EXT-002-004 resolved"
  - "OI-EXT-002-005 resolved"
```

## 14. Plan Amendment

Future changes require an appended amendment and approval. In particular, resolving any Open Issue requires a specification amendment before implementation-plan revision.

### Amendment 002 — Plan Review Round 2 remediation

- 日期：2026-08-12
- 原计划：Round 1 plan with MF-001/MF-002/MF-003 precision gaps
- 修改内容：Added exact four-way raw Archive/message validation boundary; removed undocumented `failed_stage` mappings; made strict no-coercion and no-partial-preprocessing explicit; separated specified `[REDACTED_SECRET]` literal from blocked detection/order/overlap/partial-failure semantics; gated first-person binding and all unapproved identity fields; re-evaluated `ExtractionReadyArchive` as conditional internal-only; registered OI-EXT-002-005 and synchronized OI-EXT-002-001..005.
- 修改原因：EXT-002 Plan Review Round 2 remediation for MF-001, MF-002, MF-003 and SHOULD_FIX precision.
- 是否影响技术规格：否；unresolved ambiguities remain open and no new Contract, Schema, error code, state, or dependency is introduced.
- 审批状态：PENDING PLAN_REVIEW

### Amendment 003 — Plan Review Round 3 remediation/clarification (historical; superseded by Amendment 004)

- 日期：2026-08-12
- 原计划：Round 2 remediation with typed Archive lookup, conditional handoff wording, and underspecified redaction issue packet.
- 修改内容：Added the minimum raw read-only repository method and exact implementation/test whitelist delta; enumerated all consumed top-level/message fields with strict type, requiredness, empty/null, nested-shape, datetime-like, and no-coercion behavior; required complete validation before any preprocessing or output; pinned existing EXT-001 terminal persistence/offset consequences while leaving unauthorized `failed_stage` mappings open; set `REDACTION_SPEC_STATUS=BLOCKED_PENDING_SPEC_DECISION`; explicitly blocked no-detection-as-safe, fake regex, redaction-dependent implementation, and `ExtractionReadyArchive` handoff; expanded OI-EXT-002-001 decision packet and synchronized all OI records.
- 修改原因：EXT-002 Planner Round 3 remediation/clarification under `WORKFLOW_MODE=NORMAL`, baseline `13e1dae36a0b0d94415d9581b2a5fe53c990545f`.
- 是否影响技术规格：否；no business code, schema, dependency, error code, state, offset, or recovery contract is changed.
- 审批状态：PENDING PLAN_REVIEW

### Amendment 004 — EXT-002 specification/governance amendment and Plan Review Round 4

- 日期：2026-08-12
- 原计划：Round 3 plan with unresolved OI-EXT-002-001..005.
- 修改内容：同步 authoritative specification Amendment EXT-002-004；固定 missing/corrupt/redaction terminal mappings and abort semantics; fixed content-only deterministic local redaction categories, precedence, Luhn validation, span merge/replacement, no-match success, and no-value logging; fixed normalized-then-redacted handoff order; deferred first-person binding; fixed raw read-only lookup and complete strict validation boundary.
- 修改原因：human/spec owner decision; governance-only amendment.
- 是否影响技术规格：是，仅通过 append-only authoritative amendment；不改变 EXT-001/Kafka/task status vocabulary/STM-011/012/EXT-003+/Neo4j/Elasticsearch/DEV-006/PR #13。
- dependency_changes_expected：`NONE`
- exact production whitelist：raw read-only repository method; extraction preprocessing service/models; deterministic redaction service; existing pipeline/worker wiring only as required by approved EXT-002 stage; corresponding unit/contract/integration tests. No implementation status is claimed.
- 审批状态：PENDING PLAN_REVIEW

## 15. 执行记录

| Time | Step | Actual change | Test | Risk/difference |
|---|---|---|---|---|
| 2026-08-11 15:36 UTC | Planner created plan | Planning documents only | N/A | OI-EXT-002-001–004 recorded; implementation is privacy-blocked |
| 2026-08-12 08:41 UTC | Planner Round 2 remediation | Planning documents only; MF-001/MF-002/MF-003 and SHOULD_FIX precision addressed | N/A | OI-EXT-002-001–005 remain open; status planned/PENDING review |
| 2026-08-12 08:48 UTC | Planner Round 3 remediation | Planning documents only; raw boundary delta, strict field matrix, terminal gate, redaction decision packet, blocked output contract, and exact tests documented | N/A | OI-EXT-002-001–005 remain open/blocking; status planned/PENDING review |
| 2026-08-12 09:00 UTC | Planner Round 4 governance amendment | Planning documents only; authoritative Amendment EXT-002-004 synchronized; terminal mappings, strict raw validation, deterministic content-only redaction, handoff order, and OI dispositions recorded | N/A | status remains planned/PENDING review; no business implementation, Developer, EXT-003, or Git write |
| 2026-08-12 09:42 UTC | Developer resumed implementation | Added strict raw BSON validation, deterministic normalization/redaction, internal handoff model, and raw read-only repository boundary; added scoped unit/contract/integration coverage | Initial scoped run exposed stale test fixtures and normalization expectation; fixed without changing EXT-001 semantics | No out-of-whitelist production or test paths; no EXT-003/worker wiring; no Git write |
| 2026-08-12 10:02 UTC | Developer tested implementation | Verified raw validation, no-partial-output gate, terminal decisions/persistence failure behavior, content-only redaction, provenance/order, and raw lookup | `pytest` 40 passed, 1 optional Mongo integration skipped; Ruff PASS; mypy PASS; IDE diagnostics clean | Real Mongo evidence requires explicit `EXT002_MONGO_TEST_URI`; no E2E authorized |
| 2026-08-12 10:30 UTC | Developer remediated P1 findings | Narrowed expected redaction failure to `RedactionFailure`; token-estimator, normalization, helper, model, repository, and unexpected redactor exceptions now abort without terminal/last_error; added explicit RAW-01..RAW-12 and RED-01..RED-27 executable coverage | EXT-002 scoped `133 passed, 1 optional Mongo skipped`; relevant EXT-001/Mongo gates `35 passed`; Ruff PASS; mypy PASS; lints PASS | No contract/spec/EXT-001 semantic change; no Git write |
| 2026-08-12 10:10 UTC | Developer remediation Round 2 started | Reopened only the approved EXT-002 implementation/test state to close P1-001/P1-002; existing unit evidence retained for valid behavior | Pending real-pipeline EXT-001 gate, RAW/RED matrix, and mandatory evidence rerun | No plan/spec/EXT-001 production change; no Git write |
| 2026-08-12 10:16 UTC | Developer remediation Round 2 implemented | Added actual pipeline-bound RAW matrix assertions, real post-redaction/provenance/repeatability coverage, and real Kafka/Mongo RED-18/RED-19 consumer-gate evidence | Unit/contract `172 passed`; RED-18/19 `2 passed`; full EXT-002 Mongo `2 passed, 1 optional skip`; EXT-001 Kafka `8 passed`; Ruff/mypy PASS | Optional URI-only raw lookup remains the sole non-evidence skip; no plan/spec/EXT-001 production change; no Git write |
| 2026-08-12 10:18 UTC | Developer remediation Round 2 tested | Final scoped EXT-002 unit/contract/Mongo suite passed; mandatory RAW/RED behavior and real terminal/offset evidence are green | Final `161 passed, 1 optional URI-only skip`; EXT-001 Kafka `8 passed`; Ruff PASS; mypy PASS; IDE lints clean | No mandatory evidence skipped; no plan/spec/EXT-001 production change; no Git write |

## 16. 实际执行结果

Developer P1 remediation Round 2 is complete and tested after PLAN_APPROVED and PLAN_LANDING. `RAW=12`, `RED=27`; no mandatory evidence skipped; implementation remains within the exact whitelist; no commit performed.
