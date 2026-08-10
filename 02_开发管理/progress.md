# Memory System MVP Progress

## 当前状态

```yaml
project: Memory System MVP
spec_version: 9
current_phase: Phase 1 — STM-007 completed
phase0_baseline: GREEN
phase0_readiness: PASS
phase0_secret_readiness: PASS
stm_001_entry_gate: GO
stm_001_secret_gate: GO
current_task: STM-007
current_task_status: completed
current_branch: main
formal_DEV-003-002_status: completed
formal_OI-011_status: completed
formal_OI-012_status: completed
tooling_status: VALID
runtime_contract_status: PASS
dev006_dependency_status: SUPERSEDED_FOR_MVP
target_default_branch: main
current_plan_file: 02_开发管理/tasks/STM-007-compression-llm-client-structured-output.md
workflow_mode_for_this_task: NORMAL
formal_STM-007_status: completed
formal_STM-007_plan_file: 02_开发管理/tasks/STM-007-compression-llm-client-structured-output.md
formal_STM-007_plan_commit: c5c54c53ae04e323b70c8648c88e0e09b41ede2b
formal_STM-007_implementation_commit: 87dc9c4a442aff113ac220b9604010aa135f721e
formal_STM-007_implementation_commit_message: "feat(stm): add compression llm client and structured output service"
formal_STM-007_status_record_committed: 357893a75fe6c95950c6e55d17ef4354194dfc20
formal_STM-007_status_record_completed: 713eead86039151648dbc9a6f9448ad5af911786
formal_STM-007_branch: feat/STM-007-compression-llm-client-structured-output
formal_STM-007_pr: "#26"
formal_STM-007_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/26"
formal_STM-007_pr_state: MERGED
formal_STM-007_merge_commit: 7a72b3a4c159032a411bd48dc920e52973ddab3e
formal_STM-007_merged_at: "2026-08-10T14:45:58Z"
formal_STM-007_p2: 1
formal_STM-007_p2_note: "User prompt JSON literal — non-blocking"
formal_STM-007_real_integration: SKIPPED (opt-in, non-blocking)
formal_STM-007_scoped_unit: "20 passed (authoritative STM-007 scoped unit per Task Plan §测试结果)"
formal_STM-007_scoped_contract: "4 passed"
formal_STM-007_integration_fake: "5 passed"
formal_STM-007_scoped_total: "29 passed"
formal_STM-007_full_unit: "369 passed"
formal_STM-007_full_contract: "76 passed"
formal_STM-007_ruff: PASS
formal_STM-007_mypy: PASS
formal_STM-007_code_review: CODE_REVIEW_APPROVED
formal_STM-007_p0: 0
formal_STM-007_p1: 0
formal_STM-007_prerequisite: SATISFIED  # DEV-002 + STM-001 + STM-006 completed
formal_STM-007_workflow_mode: NORMAL
formal_STM-007_note: "POST_MERGE_CLEANUP；CompressionLlmService + DeepSeekLlmClient + FakeLlmClient；public API run_compression_llm(...)；CompressionLlmInput(existing_compressed_context, archived_messages, max_compressed_context_estimated_tokens, optional tracing)；Output {\"compressed_context\":\"...\"} Pydantic extra=forbid（empty string valid）；STM-008 handoff CompressionFinalizeLlmPayload(compressed_context, new_compressed_context_tokens)；client 单次 provider call json_object transport retry=0；service validation/parse/bounded schema retry max 2/token estimation/compression_output_too_large；provider deepseek-v4-flash temperature=0 thinking=disabled stream=false DEV-002 LLMSettings；scoped unit 20 / contract 4 / integration(fake) 5 / total 29；full unit 369 / contract 76；ruff PASS；mypy PASS；real integration SKIPPED；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1；OI-004 remains open；OI-005 remains open（partial evidence only from STM-006）；NOT implemented: Redis lock/pending/Kafka/Mongo/compression_version/trim/Finalize Lua/STM-009 Coordinator；feat 分支待删；不得触碰 DEV-006/PR#13"
planning_baseline_head: dc74311d6658c87cb164283f9ec775e012aa93f5
workflow_mode_source: explicit
formal_STM-006_status: completed
formal_STM-006_plan_file: 02_开发管理/tasks/STM-006-compression-lock-pending-archive-kafka.md
formal_STM-006_prerequisite: SATISFIED  # STM-005 completed
formal_STM-006_workflow_mode: NORMAL
formal_STM-006_plan_commit: 6dd97278ec82ebb24dcb21c2c5a58118a65db0cd
formal_STM-006_implementation_commit: 683caab306e082d58f577977ba3ecee5c550aa6e
formal_STM-006_implementation_commit_message: "feat(stm): add compression lock pending archive and kafka publish"
formal_STM-006_status_record_committed: 5b9d6cb8125a72b502d93980ae75eb43a3d2fd82
formal_STM-006_status_record_completed: null  # pending this docs(status): complete commit SHA
formal_STM-006_branch: feat/STM-006-compression-lock-pending-archive-kafka
formal_STM-006_pr: "#25"
formal_STM-006_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/25"
formal_STM-006_pr_state: MERGED
formal_STM-006_merge_commit: d704bc5421d346d46a48cb69a3a7ad956e94dbb8
formal_STM-006_merged_at: "2026-08-10T13:53:53Z"
formal_STM-006_scoped_unit: "26 passed (authoritative STM-006 scoped suite per Task Plan §测试结果)"
formal_STM-006_scoped_unit_related_reverification: "30 passed (orchestrator re-run included contract stm006 file; not authoritative scoped count)"
formal_STM-006_scoped_contract: "4 passed"
formal_STM-006_integration_redis: "16 passed"
formal_STM-006_integration_kafka: "4 passed"
formal_STM-006_full_unit: "349 passed"
formal_STM-006_full_contract: "72 passed"
formal_STM-006_ruff: PASS
formal_STM-006_mypy: PASS
formal_STM-006_code_review: CODE_REVIEW_APPROVED
formal_STM-006_p0: 0
formal_STM-006_p1: 0
formal_STM-006_p2: 3
formal_STM-006_p2_note: "R2/R3 naming cases; negative pending boundary; Contract D assertion — non-blocking"
formal_STM-006_delivery_semantics: AT_LEAST_ONCE
formal_STM-006_recovery_note: "pending committed + Kafka failed/unknown = legal recovery-visible state; STM-011 republish path; STM-006 did not implement STM-011"
formal_STM-006_lock_key: "memory:compression:lock:{user_id}:{session_id}"
formal_STM-006_lock_ttl: "ContextSettings.compression_lock_ttl_seconds (default 420s)"
formal_STM-006_note: "POST_MERGE_CLEANUP pending；compression lock SET NX EX + PREHELD atomic Lua pending + Kafka context.archive.created six-field at-least-once；no compression_version bump/no trim/no compressed_context write；OI-004 remains open；OI-005 partial evidence in-process producer；不得触碰 DEV-006/PR#13"
formal_DEV-002_prerequisite: SATISFIED
planning_baseline_head_stm006: e53a0f1e2e448a6a40445768f30c902173dd0921
# STM-001 completed evidence（POST_MERGE_CLEANUP；PR #19 MERGED）
formal_STM-001_status: completed
formal_STM-001_plan_file: 02_开发管理/tasks/STM-001-token-estimator-wm-key-model-config-validation.md
formal_STM-001_plan_commit: 06c272f25e15fd5c7b4afd6e44257bc164dc83ca
formal_STM-001_implementation_commit: 66541cf3727d5735dd977e597acd6943fd997fb4
formal_STM-001_status_record_committed: ecc15af80ab18e5fe2905b5f5cd4f371f34127a0
formal_STM-001_status_record_completed: null  # pending this docs(status): complete commit SHA
formal_STM-001_pr: "#19"
formal_STM-001_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/19"
formal_STM-001_pr_state: MERGED
formal_STM-001_merge_commit: 6f2081da6266282470948ecac8e62ef3ae969c15
formal_STM-001_merged_at: "2026-08-10T02:11:17Z"
formal_STM-001_workflow_mode: NORMAL
formal_STM-001_note: "POST_MERGE_CLEANUP；deterministic heuristic token estimator；WM key/field contract；mandatory ContextSettings strict inequality validation evidence；STM-001 scoped unit 38 / contract 2；full unit 254 / contract 49；ruff PASS；mypy PASS；validators.py 未改；feat 分支待删"
# DEV-OPS-006 completed evidence（POST_MERGE_CLEANUP；PR #18 MERGED）
formal_DEV-OPS-006_status: completed
formal_DEV-OPS-006_plan_file: 02_开发管理/tasks/DEV-OPS-006-phase0-baseline-hygiene-before-stm001.md
formal_DEV-OPS-006_plan_commit: 09b045be1429716eab184e4565beb30cf2856b28
formal_DEV-OPS-006_implementation_commit: b9f049af59d0e904ebee0ce09df13cc383a91b52
formal_DEV-OPS-006_status_record_committed: 6de3f6ac3acd804df1831dcb58a0b3d1ebecf42f
formal_DEV-OPS-006_status_record_completed: 7abde48af72ea2d676deed64e1333f3e55d08a51
formal_DEV-OPS-006_pr: "#18"
formal_DEV-OPS-006_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/18"
formal_DEV-OPS-006_pr_state: MERGED
formal_DEV-OPS-006_merge_commit: 3e727b3dc1a168863d7fa6e8d52a175d36de4644
formal_DEV-OPS-006_merged_at: "2026-08-09T12:44:26Z"
formal_DEV-OPS-006_workflow_mode: NORMAL
formal_DEV-OPS-006_root_cause_classification: A
formal_DEV-OPS-006_note: "Phase 0 baseline hygiene before STM-001 completed；baseline GREEN；STM-001 已进入规划（planned）"
# Verified baseline（DEV-OPS-006 tested / merge evidence；STM-001 规划轮次 HEAD）
latest_commit: 3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4
main_tip_at_tested: 09b045be1429716eab184e4565beb30cf2856b28
planning_baseline_head: 5be0f07b7a5183aedc9ff2c67abc8e9cea8b0031
verified_unit: "323 passed (uv run pytest tests/unit -q @ 2026-08-10 DEV-OPS-007 tested)"
verified_contract: "68 passed (uv run pytest tests/contract -q @ 2026-08-10 DEV-OPS-007 tested)"
verified_ruff: "PASS — All checks passed (uv run ruff check . @ 2026-08-10 DEV-OPS-007 tested)"
verified_mypy: "PASS — Success: no issues found in 139 source files (uv run mypy src tests scripts @ 2026-08-10 DEV-OPS-007 tested)"
verified_integration_context_read: "14 passed (uv run pytest tests/integration/test_context_read_redis.py -q @ 2026-08-10 DEV-OPS-007 tested)"
planning_unit_collect: 216
planning_unit_known_failure: "RESOLVED by DEV-OPS-006 allowlist + invariant"
planning_contract_verified: "47 passed (uv run pytest tests/contract -q @ planning)"
# DEV-007 formal completion evidence (retained)
formal_DEV-007_status: completed
formal_DEV-007_plan_file: 02_开发管理/tasks/DEV-007-siliconflow-embedding-client-mvp.md
formal_DEV-007_plan_commit: 69e4dece8e72acf22828ba5b81682b70ecb34e8b
formal_DEV-007_implementation_commit: 88c442e909c89fe297921f61d6bd6c13ba4b719d
formal_DEV-007_status_record_committed: ea58d72690d2e34539cd2eb123e1fedd14c5874f
formal_DEV-007_status_record_completed: ce461229fd3c997d5ebe237127d849c547462481
formal_DEV-007_pr: "#17"
formal_DEV-007_pr_state: MERGED
formal_DEV-007_merge_commit: b7916ea79a2d2ec7bf25873ec2ba50ad64041775
formal_DEV-007_workflow_mode: NORMAL
formal_DEV-007_real_integration: PASS
formal_DEV-007_embedding_model: "BAAI/bge-m3"
formal_DEV-007_embedding_dimension: 1024
memory_limit_decision: 12g
cpu_tei_profile: "BAAI/bge-m3 float32 ONNX CPU mem_limit=12g"
historical_8g_runtime_contract_status: SPEC_RUNTIME_CONTRACT_CONFLICT
# OI-011 formal completion evidence
formal_OI-011_plan_file: 02_开发管理/tasks/OI-011-bge-m3-cpu-tei-memory-contract.md
formal_OI-011_plan_commit: bda5018a712766a5981f8e1a19940132a56de536
formal_OI-011_implementation_commit: 131a2e994690adb4b06b4d0fa299b229e88ca7d3
formal_OI-011_status_record_committed: 8a595b8507050f75c740b3a0629fddba61563536
formal_OI-011_status_record_completed: null
formal_OI-011_pr: "#15"
formal_OI-011_pr_state: MERGED
formal_OI-011_merge_commit: 7cc020a97b0373579a91e620fcdef90976193c8c
formal_OI-011_workflow_mode: NORMAL
# OI-012 formal completion evidence
formal_OI-012_plan_file: 02_开发管理/tasks/OI-012-siliconflow-embedding-provider-spec-oi.md
formal_OI-012_plan_commit: e122c8ab840720a4f86cffda5a58e5f9e6f34944
formal_OI-012_implementation_commit_spec: bd7529f455ab0c34dc03a6659e1850a5eab189f7
formal_OI-012_implementation_commit: f4d2e614773f7bcdf8b45b39e3e1c438d282b410
formal_OI-012_status_record_committed: f4d2e614773f7bcdf8b45b39e3e1c438d282b410
formal_OI-012_status_record_completed: a338dbc344579326a2edb0090d4562033bbab2b0
formal_OI-012_pr: "#16"
formal_OI-012_pr_state: MERGED
formal_OI-012_merge_commit: 003fb43e24ab5bb5d2401342a0f466fcbe22ce26
formal_OI-012_workflow_mode: NORMAL
# Retained DEV-003-002 completion evidence
formal_DEV-003-002_plan_file: 02_开发管理/tasks/DEV-003-002-tei-cpu-memory-contract-validation.md
formal_DEV-003-002_plan_commit: 7172e918647c1853d0982ce979b299920d96a0cb
formal_DEV-003-002_implementation_commit: 715e985e4e4fee35a3b12f4517af445081b2c5d7
formal_DEV-003-002_pr: "#14"
formal_DEV-003-002_merge_commit: 4d894cc61d0fdd4e12149cd86f2ab55072deb8b5
# STM-002 completed evidence（POST_MERGE_CLEANUP；PR #20 MERGED）
formal_STM-002_status: completed
formal_STM-002_plan_file: 02_开发管理/tasks/STM-002-session-creation.md
formal_STM-002_plan_commit: ac84b31210001f22df4a049d28ff1e90618c244d
formal_STM-002_implementation_commit: 3440048f8a304219ec7bbddf3c192089cac6e8cb
formal_STM-002_implementation_commit_message: "feat(stm): add session creation API and redis working memory init"
formal_STM-002_status_record_committed: 1499fd23ad4aa92c6e9dd89f087d77b007674ff3
formal_STM-002_status_record_completed: 033e05ac23acd72f17458cdb701ddc37d28799bf
formal_STM-002_pr: "#20"
formal_STM-002_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/20"
formal_STM-002_pr_state: MERGED
formal_STM-002_merge_commit: efb39bf0bbbb408626e3d187d81b889dafc7a351
formal_STM-002_merged_at: "2026-08-10T03:11:25Z"
formal_STM-002_branch: feat/STM-002-session-creation
formal_STM-002_workflow_mode: NORMAL
formal_STM-002_scoped_unit: "25 passed (test_session_create_service + test_working_memory_redis_codec)"
formal_STM-002_scoped_contract: "10 passed (test_stm002_contract)"
formal_STM-002_integration: "3 passed (test_session_create_redis)"
formal_STM-002_full_unit: "269 passed"
formal_STM-002_full_contract: "59 passed"
formal_STM-002_ruff: PASS
formal_STM-002_mypy: "PASS — 108 source files"
formal_STM-002_note: "POST_MERGE_CLEANUP；POST /api/v1/memory/session；X-API-Key；UUID v4；WM Hash status=active compression_version=0；HTTP 200 status=created；Amendment 001 四项落实；STM-002 scoped 25 / integration 3 / full unit 269 / contract 59；ruff PASS；mypy PASS；feat 分支已删"
# STM-003 completed evidence（POST_MERGE_CLEANUP；PR #21 MERGED）
formal_STM-003_status: completed
formal_STM-003_plan_file: 02_开发管理/tasks/STM-003-message-write-lua.md
formal_STM-003_plan_commit: 926f37d166089f02b3143470ca74ba1258d48010
formal_STM-003_implementation_commit: e1913d17b159d426aadfd54d32e07c84ea61043a
formal_STM-003_implementation_commit_message: "feat(stm): add message write lua and domain service"
formal_STM-003_status_record_committed: 34bbebd
formal_STM-003_status_record_completed: null  # pending this docs(status): complete commit SHA
formal_STM-003_branch: feat/STM-003-message-write-lua
formal_STM-003_workflow_mode: NORMAL
formal_STM-003_pr: "#21"
formal_STM-003_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/21"
formal_STM-003_pr_state: MERGED
formal_STM-003_merge_commit: 3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4
formal_STM-003_merged_at: "2026-08-10T06:26:37Z"
formal_STM-003_scoped: "21 passed (unit 18 + contract 3)"
formal_STM-003_scoped_unit: "18 passed (test_message_write_service + test_working_memory_message_codec + test_message_write_status_mapping)"
formal_STM-003_scoped_contract: "3 passed (test_stm003_contract)"
formal_STM-003_integration: "11 passed (test_message_write_redis — 17 scenarios)"
formal_STM-003_full_unit: "287 passed"
formal_STM-003_full_contract: "62 passed"
formal_STM-003_ruff: PASS
formal_STM-003_mypy: "PASS — 119 source files"
formal_STM-003_note: "POST_MERGE_CLEANUP；atomic Redis Lua；message_id idempotency；duplicate zero side-effect；hard WM capacity；concurrent same message_id one write；malformed estimated_tokens fail-closed；no compression/Kafka/HTTP；STM-003 scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS；feat 分支待删"
# STM-004 completed evidence（POST_MERGE_CLEANUP；PR #22 MERGED）
formal_STM-004_status: completed
formal_STM-004_plan_file: 02_开发管理/tasks/STM-004-context-read-lua.md
formal_STM-004_plan_commit: c3214164ccbc47ad88b104a0497c6b9020f26ba7
formal_STM-004_implementation_commit: 3aed60522db64c3b11597e025caa0aae00afaba6
formal_STM-004_implementation_commit_message: "feat(stm): add context read lua and domain service"
formal_STM-004_status_record_committed: 8c050fc0d09523d82eb201b4f03fa87060efd065
formal_STM-004_status_record_completed: null  # pending this docs(status): complete commit SHA
formal_STM-004_branch: feat/STM-004-context-read-lua
formal_STM-004_workflow_mode: NORMAL
formal_STM-004_pr: "#22"
formal_STM-004_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/22"
formal_STM-004_pr_state: MERGED
formal_STM-004_merge_commit: 6a3d09f5bf29ec25c768c6295e2c13adb3ff9a6c
formal_STM-004_merged_at: "2026-08-10T08:02:11Z"
formal_STM-004_scoped_unit: "15 passed (test_context_read_service + test_context_read_status_mapping)"
formal_STM-004_scoped_contract: "3 passed (test_stm004_contract)"
formal_STM-004_integration: "14 passed (test_context_read_redis — 13 scenarios)"
formal_STM-004_full_unit: "300 passed"
formal_STM-004_full_contract: "65 passed"
formal_STM-004_ruff: PASS
formal_STM-004_mypy: PASS
formal_STM-004_note: "POST_MERGE_CLEANUP；read-only atomic Redis Lua context snapshot；compression_version + compressed_context + ordered messages；malformed state fail-closed；I12 deterministic torn-read negative control；production single-Lua canonical snapshot；zero Redis write side effect（I13）；OI-009 resolved；scoped 15 / contract 3 / integration 14 / full unit 300 / contract 65；ruff PASS；mypy PASS；feat 分支待删"
# STM-005 completed evidence（POST_MERGE_CLEANUP；PR #23 MERGED）
formal_STM-005_status: completed
formal_STM-005_plan_file: 02_开发管理/tasks/STM-005-context-archive-create-reuse.md
formal_STM-005_plan_commit: 7b761c35ae8aa83c2b5c909312dd511b863a660c
formal_STM-005_implementation_commit: c166be5cd40475a513cede67f53cafec8fc8529a
formal_STM-005_implementation_commit_message: "feat(stm): add context archive mongo create reuse service"
formal_STM-005_status_record_committed: a52207473534b1667967be32957c9e1f500ac429
formal_STM-005_status_record_completed: b0736431a636f0ba20a9cf5aad61a2ea8dc365df
formal_STM-005_branch: feat/STM-005-context-archive-create-reuse
formal_STM-005_workflow_mode: NORMAL
formal_STM-005_pr: "#23"
formal_STM-005_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/23"
formal_STM-005_pr_state: MERGED
formal_STM-005_merge_commit: 164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf
formal_STM-005_merged_at: "2026-08-10T09:16:52Z"
formal_STM-005_scoped_unit: "26 passed (test_context_archive_batch_key + test_context_archive_models + test_context_archive_repository + test_context_archive_service)"
formal_STM-005_scoped_contract: "3 passed (test_stm005_contract)"
formal_STM-005_integration: "12 passed (test_context_archive_mongo — 11 scenarios)"
formal_STM-005_full_unit: "323 passed"
formal_STM-005_full_contract: "68 passed"
formal_STM-005_ruff: PRE_EXISTING_BASELINE_RUFF_FAILURE
formal_STM-005_ruff_note: "2x E501 tests/integration/context_read_torn_read_helpers.py:174:101,175:101 — identical at plan_commit and HEAD; STM-005 changed files Ruff PASS; STM005_REGRESSION=false"
formal_STM-005_mypy: PASS
formal_STM-005_note: "POST_MERGE_CLEANUP；Mongo context_archive create/reuse；archive_batch_key session_id:first_message_id:last_message_id + mandatory validation；empty messages fail-closed；DuplicateKey → REUSED no overwrite；concurrent same key → one doc same archive_id；message order preserved；DEV-004 unique index verified；no Kafka/Redis pending/compression/LLM/HTTP；scoped unit 26 / contract 3 / integration 12 / full unit 323 / contract 68；mypy PASS；feat 分支待删"
# DEV-OPS-007 completed evidence（POST_MERGE_CLEANUP；PR #24 MERGED）
formal_DEV-OPS-007_status: completed
formal_DEV-OPS-007_plan_file: 02_开发管理/tasks/DEV-OPS-007-phase1-baseline-hygiene-before-stm006.md
formal_DEV-OPS-007_plan_commit: f42eaf3190d8fc3600f52c869fc7e8dfbec86cf1
formal_DEV-OPS-007_implementation_commit: 1ef8932b87604de9a01dab72e7584a4e7886b155
formal_DEV-OPS-007_implementation_commit_message: "chore(hygiene): fix STM-005 governance SHA and ruff E501 in torn-read helpers"
formal_DEV-OPS-007_status_record_committed: c48a70d
formal_DEV-OPS-007_status_record_completed: null  # pending this docs(status): complete commit SHA
formal_DEV-OPS-007_branch: feat/DEV-OPS-007-phase1-baseline-hygiene-before-stm006
formal_DEV-OPS-007_workflow_mode: NORMAL
formal_DEV-OPS-007_pr: "#24"
formal_DEV-OPS-007_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/24"
formal_DEV-OPS-007_pr_state: MERGED
formal_DEV-OPS-007_merge_commit: de95f3a2f0107f791f89441177841754b1d4f82c
formal_DEV-OPS-007_merged_at: "2026-08-10T11:54:41Z"
formal_DEV-OPS-007_authoritative_stm005_governance_sha: b0736431a636f0ba20a9cf5aad61a2ea8dc365df
formal_DEV-OPS-007_orphan_sha_not_in_main_lineage: "301c8d9ff873ba826b122f6cbb34a3dc0d2aa40b exit 1"
formal_DEV-OPS-007_zero_stale_authoritative_references: PASS
formal_DEV-OPS-007_full_ruff: PASS
formal_DEV-OPS-007_integration_context_read: "14 passed"
formal_DEV-OPS-007_mypy: PASS
formal_DEV-OPS-007_changed_behavior: false
formal_DEV-OPS-007_production_src_changes: none
formal_DEV-OPS-007_note: "POST_MERGE_CLEANUP；Phase 1 baseline hygiene before STM-006 completed；orphan SHA metadata 更正 → b0736431…；Ruff E501 L174–175 换行；integration 14 / unit 323 / contract 68；ruff PASS；mypy PASS；feat 分支待删；STM-006 READY_FOR_PLANNING only"
previous_task: STM-004
previous_task_status: completed
previous_implementation_commit: 66541cf3727d5735dd977e597acd6943fd997fb4
previous_implementation_commit_message: "feat(stm): add token estimator, wm key/field models, context inequality tests"
previous_status_record_commit_committed: ecc15af80ab18e5fe2905b5f5cd4f371f34127a0
previous_status_record_commit_committed_message: "docs(status): record STM-001 implementation commit and PR"
previous_pr: "#19"
previous_pr_status: MERGED
previous_merge_commit: 6f2081da6266282470948ecac8e62ef3ae969c15
previous_status_record_commit_completed: null  # pending this docs(status): complete commit SHA
# DEV-OPS-005 formal completion evidence
formal_DEV-OPS-005_status: completed
formal_DEV-OPS-005_plan_file: 02_开发管理/tasks/DEV-OPS-005-human-prompt-playbook-recovery-operations.md
formal_DEV-OPS-005_plan_commit: a601a3ba569b12b8fc0ae8ff913f66927381af19
formal_DEV-OPS-005_implementation_commit: 373cd331313e02d053a6b49af11beaa7be02acbc
formal_DEV-OPS-005_status_record_committed: 239218432d6b86d4f34d24c248611361df5d5069
formal_DEV-OPS-005_status_record_completed: null  # pending this docs(status): complete commit SHA
formal_DEV-OPS-005_pr: "#11"
formal_DEV-OPS-005_pr_state: MERGED
formal_DEV-OPS-005_merge_commit: 0239c28281949bedec66dbec1412197c5561a611
formal_DEV-OPS-005_workflow_mode: NORMAL
# DEV-005 formal completion evidence
formal_DEV-005_status: completed
formal_DEV-005_plan_file: 02_开发管理/tasks/DEV-005-api-shell-auth-request-id-logging-metrics.md
formal_DEV-005_plan_commit: 2548c9a5f99c833e6347b93484c562e86f25f605
formal_DEV-005_implementation_commit: d32ddc70b5b8b772e9f27a84988b778c226dd2c5
formal_DEV-005_status_record_committed: 76a91ce8b0281c03f6587a8ade19c02bc1952c91
formal_DEV-005_status_record_completed: b340f3fd15086db560a01b54d01b5f08695d1e47
formal_DEV-005_pr: "#12"
formal_DEV-005_pr_state: MERGED
formal_DEV-005_merge_commit: a68d951c50eaeab66f589e5eff5c55d6611f3f43
formal_DEV-005_workflow_mode: NORMAL
# DEV-004 formal completion evidence (retained)
formal_DEV-004_status: completed
formal_DEV-004_plan_file: 02_开发管理/tasks/DEV-004-migration-runner-es-mapping-alias.md
formal_DEV-004_plan_commit: 5c2274fb2da77e7eaf1ab5df248fcf8a64a95d9a
formal_DEV-004_implementation_commit: d8730a670d577c1f9acb75ebb112fc8f88ea6662
formal_DEV-004_status_record_committed: 5246b5d3ba6a78c940f4469bbba2356005a41f29
formal_DEV-004_status_record_completed: 4a5cbc2e9a7f5472749cc0181b7f91153b91479d
formal_DEV-004_pr: "#10"
formal_DEV-004_pr_state: MERGED
formal_DEV-004_merge_commit: 206b7a688cbad3070dc3f1646111efa165f2be87
formal_DEV-004_workflow_mode: NORMAL
formal_DEV-004_governance_deviation: GD-DEV-004-001
# DEV-OPS-004 formal completion evidence (retained)
formal_DEV-OPS-004_status: completed
formal_DEV-OPS-004_plan_file: 02_开发管理/tasks/DEV-OPS-004-mihomo-network-fallback-policy.md
formal_DEV-OPS-004_plan_commit: 895d7aaccc6c194105275e0688527d780907933f
formal_DEV-OPS-004_implementation_commit: 14550dfa8043eb5339b89f1c9f215ae368a6f58d
formal_DEV-OPS-004_status_record_committed: 7d2a176170939eefe8a5c933b427021068541880
formal_DEV-OPS-004_status_record_completed: d5db474ea7b11c05ff9d0a137c3f9c16f3d8dd50
formal_DEV-OPS-004_pr: "#9"
formal_DEV-OPS-004_pr_state: MERGED
formal_DEV-OPS-004_merge_commit: 1bc2f499d79301679f373d46c809f1f50e4dad66
formal_DEV-OPS-004_workflow_mode: NORMAL
# DEV-OPS-003 formal completion evidence (retained)
formal_DEV-OPS-003_status: completed
formal_DEV-OPS-003_plan_file: 02_开发管理/tasks/DEV-OPS-003-normal-strict-workflow-modes.md
formal_plan_commit: d45ea2faf3b057c9e8ca0cf8699c0a973fe2e638
formal_implementation_commit: 640616b3e4d9556c7d1bf2f81271ba62bc12cbe7
formal_status_record_committed: ec47b2ae3f42ed32fd33a53440a831e70226db33
formal_status_record_completed: 4e4ad1966e3c8cdbc015a2f7b343ed68f2c02702
formal_pr: "#7"
formal_pr_state: MERGED
formal_merge_commit: 1189447d518b863d469150ead861e85fa5ca86b5
formal_workflow_mode: STRICT
formal_feat_retained_pending_cleanup: feat/DEV-OPS-003-normal-strict-workflow-modes
# Step 7 smoke evidence
step7_smoke_task: DEV-OPS-003-SMOKE
step7_smoke_verdict: PASSED
step7_workflow_mode: NORMAL
step7_workflow_mode_source: default
step7_two_human_gates_validated: true
step7_smoke_pr: "#8"
step7_smoke_merge_commit: e14d71e8955a312f7c77c6d42c8f624cf3694563
step7_smoke_completed_governance: 45c74f8a988170929d003f72cedcd48b8944f7c0
step7_marker: tests/e2e/devops003_normal_workflow_smoke.txt
# Next business task / STM-002 readiness
deferred_business_task: STM-008
deferred_business_task_status: READY_FOR_PLANNING only
deferred_business_task_note: "STM-007 completed；STM-008 prerequisites STM-006+STM-007 SATISFIED — READY_FOR_PLANNING only；不得自动开始"
next_action: STM-008 READY_FOR_PLANNING only（do NOT auto-start）
last_role_result: RELEASE_COMPLETED
blocking_reason: null
# note: human confirmed PLAN_APPROVED for Amendment 001；Orchestrator records approved only
human_plan_approved_at: "2026-08-10T12:35:00Z"
human_plan_approved_note: "Human PLAN_APPROVED STM-006 Amendment 001；Round 2 Plan Reviewer PLAN_APPROVED BLOCKER=0 MUST_FIX=0；absorb R2 SHOULD_FIX count/tokens fail-closed；scope lock+pending+Kafka only"
oi012_amendment: "Amendment 002.1（Round 2 MF-1 SHA + SF-1～4；Round 3 PLAN_APPROVED）"
insertion_override:
  prior_current_task: DEV-OPS-007
  prior_current_task_status: completed
  prior_next_action: "STM-006 READY_FOR_PLANNING only（do NOT auto-start）"
  override_by: "用户显式 START_EXISTING_TASK=STM-006 + WORKFLOW_MODE=NORMAL(explicit)；STM-005 completed；main @ e53a0f1"
  effect: "current_task=STM-006 planned；compression lock + pending_archive_* + Kafka context.archive.created；next_action=计划审查；本轮只规划不实施；OI-004 不得私解；不得触碰 DEV-006/PR#13"
  overridden_at: "2026-08-10 12:14 UTC"
# DEV-006 / PR #13 disposition (record only)
dev_006_disposition:
  status: "PAUSED / SUPERSEDED_FOR_MVP"
  plan_file: 02_开发管理/tasks/DEV-006-tei-embedding-client-token-budget.md
  pr: "#13"
  pr_status: "OPEN / DO_NOT_MERGE"
  pr13_decision: "deferred；DEV-OPS-006 不得操作 dirty worktree / Merge PR #13"
  must_not: "merge PR #13; modify DEV-006 feat; access DEV-006 dirty worktree"
# Retained DEV-004 governance deviation evidence (historical)
governance_deviation:
  id: GD-DEV-004-001
  type: NON_BLOCKING_GOVERNANCE_DEVIATION
  audited_at: "2026-08-08 09:48 UTC"
  human_accepted_at: "2026-08-08 09:52 UTC"
  human_acceptance: GOVERNANCE_DEVIATION_ACCEPTED
  violations:
    - GD-001
    - GD-002
  remediation: "Governance record only; no test re-run; no status revert; no implementation rollback"
  future_rule: "Acceptance does not relax fail-closed; future failures require report + authorization"
  ready_for_code_review: true
```
## 测试状态

| 测试层级 | 状态 | 最近命令 | 最近结果 |
|---|---|---|---|
| Unit | **passed** | `uv run pytest tests/unit -q` | **216 passed** in 4.06s；exit=0（2026-08-09 12:32 UTC；含 OI-011 allowlist + 存在性断言） |
| Contract（业务） | **passed** | `uv run pytest tests/contract -q` | **47 passed**, 1 warning；exit=0（2026-08-09 12:32 UTC） |
| Contract（Playbook DEV-OPS-005） | passed（历史） | `uv run pytest tests/unit/test_project_operations_playbook_contract.py -q` | **28 passed**（历史；计入 unit collect） |
| Contract（Cursor 工作流） | passed（历史） | `uv run pytest tests/unit/test_cursor_orchestrator_contract.py tests/unit/test_cursor_workflow_modes_contract.py tests/unit/test_cursor_commands_contract.py -q` | 50 passed（既有） |
| Contract（Mihomo 网络回退） | passed（历史） | `uv run pytest tests/unit/test_mihomo_network_fallback_contract.py -q` | 15 passed（DEV-OPS-004） |
| Integration | passed（历史） | `uv run pytest tests/integration/test_migrate_infra.py -v` | **1 passed**（79s；compose test 栈） |
| TEI lock validate | passed（历史） | `timeout 600 ./scripts/lock_tei_images.sh` | CPU+GPU 1.9.3（DEV-003） |
| E2E | passed（DEV-OPS-003 Step 7） | DEV-OPS-003-SMOKE NORMAL 受监督全链路 | **PASSED**（PR #8 MERGED） |
| Ruff | **passed** | `uv run ruff check .` | All checks passed；exit=0（2026-08-09 12:32 UTC） |
| Mypy | **passed** | `uv run mypy src tests scripts` | Success: no issues found in 91 source files；exit=0（2026-08-09 12:32 UTC） |
| UI discovery（§9 / OI-OPS-005 延续） | passed（DEV-OPS-002） | 人工 `/` 菜单 | 七项均可发现（2026-08-07 02:40 UTC） |
| E2E 冒烟（§9） | passed（DEV-OPS-002） | 受监督完整编排链路 | PR #3；E2E 分支保留 |

## 已完成任务

| Task ID | 任务名称 | 完成时间 (UTC) | 实现 Commit | Merge Commit | PR |
|---|---|---|---|---|---|
| DEV-001 | 项目骨架、依赖与质量工具 | 2026-08-06 13:20 | `9fbe899` | `a2673ac` | #1 merged |
| DEV-OPS-001 | Cursor Agent 工作流自动化 | 2026-08-06 15:30 | `69fabb7` | `57800c3` | #2 merged |
| DEV-OPS-002 | Cursor Orchestrator、Subagents 与 Release Automation | 2026-08-07 07:11 | `4943757` | `5886cc6` | #4 merged |
| DEV-002 | 配置系统与 `.env.example` | 2026-08-07 09:44 | `f55732c` | `7fba544` | #5 merged |
| DEV-003 | Docker Compose、Embedding 服务与 Preflight | 2026-08-07 15:10 | `d366fb6` | `0ac80e5` | #6 merged |
| DEV-OPS-003 | NORMAL / STRICT 工作流模式 | 2026-08-08 05:12 | `640616b` | `1189447d518b863d469150ead861e85fa5ca86b5` | #7 merged |
| DEV-OPS-003-SMOKE | NORMAL workflow supervised smoke | 2026-08-08 05:05 | `3a3c7c7` | `e14d71e8955a312f7c77c6d42c8f624cf3694563` | #8 merged |
| DEV-OPS-004 | 本机 Mihomo 网络回退策略文档 | 2026-08-08 06:18 | `14550df` | `1bc2f499d79301679f373d46c809f1f50e4dad66` | #9 merged |
| DEV-004 | Migration Runner；ES Mapping + Alias | 2026-08-08 10:07 | `d8730a6` | `206b7a688cbad3070dc3f1646111efa165f2be87` | #10 merged |
| DEV-OPS-005 | 人类 Prompt Playbook 与 Recovery 操作手册 | 2026-08-08 10:53 | `373cd33` | `0239c28281949bedec66dbec1412197c5561a611` | #11 merged |
| DEV-005 | 通用 API 壳、鉴权、Request ID、日志与指标 | 2026-08-08 12:00 | `d32ddc7` | `a68d951c50eaeab66f589e5eff5c55d6611f3f43` | #12 merged |
| DEV-003-002 | TEI CPU Memory Contract Validation | 2026-08-09 01:30 | `715e985` | `4d894cc61d0fdd4e12149cd86f2ab55072deb8b5` | #14 merged |
| OI-011 | BAAI/bge-m3 CPU TEI Memory Contract（Spec-OI） | 2026-08-09 02:42 | `131a2e9` | `7cc020a97b0373579a91e620fcdef90976193c8c` | #15 merged |
| OI-012 | SiliconFlow Embedding Provider（Spec-OI） | 2026-08-09 07:02 | `f4d2e61` | `003fb43e24ab5bb5d2401342a0f466fcbe22ce26` | #16 merged |
| DEV-007 | SiliconFlow Embedding Client MVP | 2026-08-09 08:24 | `88c442e` | `b7916ea79a2d2ec7bf25873ec2ba50ad64041775` | #17 merged |
| DEV-OPS-006 | Phase 0 Baseline Hygiene Before STM-001 | 2026-08-09 12:44 | `b9f049a` | `3e727b3dc1a168863d7fa6e8d52a175d36de4644` | #18 merged |
| STM-001 | Token 估算、WM Key/字段模型、配置校验 | 2026-08-10 02:11 | `66541cf` | `6f2081da6266282470948ecac8e62ef3ae969c15` | #19 merged |
| STM-002 | Session 创建 | 2026-08-10 03:11 | `3440048` | `efb39bf0bbbb408626e3d187d81b889dafc7a351` | #20 merged |
| STM-003 | 消息写入 Lua | 2026-08-10 06:26 | `e1913d1` | `3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4` | #21 merged |
| STM-004 | 上下文一致性读取 Lua | 2026-08-10 08:02 | `3aed605` | `6a3d09f5bf29ec25c768c6295e2c13adb3ff9a6c` | #22 merged |
| STM-005 | Mongo context_archive create/reuse | 2026-08-10 09:16 | `c166be5` | `164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf` | #23 merged |
| DEV-OPS-007 | Phase 1 Baseline Hygiene Before STM-006 | 2026-08-10 11:54 | `1ef8932` | `de95f3a2f0107f791f89441177841754b1d4f82c` | #24 merged |
| STM-006 | 压缩锁、pending archive、Kafka 发布 | 2026-08-10 13:53 | `683caab` | `d704bc5421d346d46a48cb69a3a7ad956e94dbb8` | #25 merged |
| STM-007 | Compression LLM Client + Structured Output | 2026-08-10 14:45 | `87dc9c4` | `7a72b3a4c159032a411bd48dc920e52973ddab3e` | #26 merged |

## 规格阻塞项

**STM-002**：**completed** — `POST /api/v1/memory/session` + Redis WM meta 初始化；implementation `3440048f8a304219ec7bbddf3c192089cac6e8cb`；record `1499fd23ad4aa92c6e9dd89f087d77b007674ff3`；PR [#20](https://github.com/xu-jia-ming/memory_system/pull/20) **MERGED**（merge `efb39bf0bbbb408626e3d187d81b889dafc7a351` mergedAt `2026-08-10T03:11:25Z`）；STM-002 scoped **25 passed** / integration **3 passed**；full unit **269 passed** / contract **59 passed**；ruff **PASS**；mypy **PASS**；`POST /api/v1/memory/session` + `X-API-Key` + UUID v4 + WM Hash `status=active` `compression_version=0` + HTTP 200；Phase 1 STM-002 **completed**。

**STM-001**：**completed** — deterministic heuristic token estimator；WM key/field contract；mandatory ContextSettings strict inequality validation evidence；implementation `66541cf3727d5735dd977e597acd6943fd997fb4`；record `ecc15af80ab18e5fe2905b5f5cd4f371f34127a0`；PR [#19](https://github.com/xu-jia-ming/memory_system/pull/19) **MERGED**（merge `6f2081da6266282470948ecac8e62ef3ae969c15`）；STM-001 scoped unit **38 passed** / contract **2 passed**；full unit **254 passed** / contract **49 passed**；ruff **PASS**；mypy **PASS**；`validators.py` 未改；Phase 1 STM-001 **completed**。

**DEV-OPS-006**：**completed** — Phase 0 baseline hygiene；baseline **GREEN**；implementation `b9f049af59d0e904ebee0ce09df13cc383a91b52`；record `6de3f6ac3acd804df1831dcb58a0b3d1ebecf42f`；PR [#18](https://github.com/xu-jia-ming/memory_system/pull/18) **MERGED**（merge `3e727b3dc1a168863d7fa6e8d52a175d36de4644`）；unit **216 passed / 0 failed**；contract **47 passed**；ruff **PASS**；mypy **PASS**；Phase 0 **completed**。

**OI-012（Amendment 002/002.1）**：**completed**（PR #16 MERGED `003fb43e24ab5bb5d2401342a0f466fcbe22ce26`）。

**DEV-007**：**completed**（PR #17 MERGED `b7916ea79a2d2ec7bf25873ec2ba50ad64041775`；SiliconFlow MVP 在 main）。

**DEV-006 / PR #13**：**PAUSED / SUPERSEDED_FOR_MVP**；PR #13 **OPEN / DO_NOT_MERGE**；不得操作。

**OI-011 / TEI**：已完成（12g contract 保留；本 hygiene 不修改）。

**STM-003**：**completed** — atomic Redis Lua + `write_message` 领域服务；`message_id` 幂等；duplicate 零副作用；hard WM capacity；concurrent same `message_id` 单写；malformed `estimated_tokens` fail-closed；implementation `e1913d17b159d426aadfd54d32e07c84ea61043a`；record `34bbebd`；PR [#21](https://github.com/xu-jia-ming/memory_system/pull/21) **MERGED**（merge `3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4` mergedAt `2026-08-10T06:26:37Z`）；STM-003 scoped **21 passed** / integration **11 passed**；full unit **287 passed** / contract **62 passed**；ruff **PASS**；mypy **PASS**；无 compression/Kafka/HTTP；Phase 1 STM-003 **completed**。

**STM-004**：**completed** — read-only atomic Redis Lua context snapshot；`read_working_memory_context` + `context_read.lua`；`compression_version` + `compressed_context` + ordered messages；malformed state fail-closed；I12 deterministic torn-read negative control；production single-Lua canonical snapshot guarantee；zero Redis write side effect（I13）；OI-009 resolved；implementation `3aed60522db64c3b11597e025caa0aae00afaba6`；record `8c050fc0d09523d82eb201b4f03fa87060efd065`；PR [#22](https://github.com/xu-jia-ming/memory_system/pull/22) **MERGED**（merge `6a3d09f5bf29ec25c768c6295e2c13adb3ff9a6c` mergedAt `2026-08-10T08:02:11Z`）；scoped unit **15 passed** / contract **3 passed** / integration **14 passed**（13 scenarios）；full unit **300 passed** / contract **65 passed**；ruff **PASS**；mypy **PASS**；无 HTTP/压缩写回；Phase 1 STM-004 **completed**。

**STM-005**：**completed** — Mongo `context_archive` create/reuse；`archive_batch_key` `session_id:first_message_id:last_message_id` + mandatory validation；empty messages fail-closed；DuplicateKey → REUSED no overwrite；concurrent same key → one doc same `archive_id`；message order preserved；DEV-004 unique index verified；no Kafka/Redis pending/compression/LLM/HTTP；implementation `c166be5cd40475a513cede67f53cafec8fc8529a`；record `a52207473534b1667967be32957c9e1f500ac429`；PR [#23](https://github.com/xu-jia-ming/memory_system/pull/23) **MERGED**（merge `164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf` mergedAt `2026-08-10T09:16:52Z`）；scoped unit **26 passed** / contract **3 passed** / integration **12 passed**；full unit **323 passed** / contract **68 passed**；mypy **PASS**；ruff baseline E501 pre-existing（非回归）；Phase 1 STM-005 **completed**。

**DEV-OPS-007**：**completed** — Phase 1 baseline hygiene before STM-006；orphan SHA metadata 更正 → `b0736431a636f0ba20a9cf5aad61a2ea8dc365df`；Ruff E501 L174–175 换行（零语义变更）；implementation `1ef8932b87604de9a01dab72e7584a4e7886b155`；record `c48a70d`；PR [#24](https://github.com/xu-jia-ming/memory_system/pull/24) **MERGED**（merge `de95f3a2f0107f791f89441177841754b1d4f82c` mergedAt `2026-08-10T11:54:41Z`）；ZERO_STALE_AUTHORITATIVE_REFERENCES **PASS**；FULL_RUFF **PASS**；integration context-read **14 passed**；mypy **PASS**；`DEV-OPS-007_CHANGED_BEHAVIOR=false`；production `src/**` changes **none**；Phase 1 DEV-OPS-007 **completed**。

**下游**：**STM-008** `READY_FOR_PLANNING only` — prerequisites STM-006+STM-007 **SATISFIED**；**不得自动开始**；**STM-011** `READY_FOR_PLANNING only`（STM-006 satisfied）；**STM-009** NOT ready（needs STM-008）；**不得触碰 DEV-006/PR#13**。

## 实施前置条件

| ID | 项 | 说明 | 状态 |
|---|---|---|---|
| PRE-ENV-001 | 缺少 `uv` | DEV-001 **实施编码前**必须安装 `uv` | satisfied（uv 0.12.2） |
| PRE-ENV-002 | 主机 Python 3.13.9 | DEV-001 **实施编码前**必须使用 Python 3.12.13（经 uv） | satisfied（uv python find 3.12.13 成功；.venv 为 3.12.13） |

## 规格歧义

见 `02_开发管理/open_issues.md`。OI-009、OI-010、**OI-011**、**OI-012** 为 `resolved`；未解决项不得自行解释为新 Contract。

DEV-OPS-001 产品/流程未决项见其 Task Plan §12.2（OI-OPS-001–005）；**不**写入规格 Contract。

DEV-OPS-002 产品/流程未决项见其 Task Plan §11.2（OI-OPS-006–013）；**不**写入规格 Contract。

## 已知风险

- 所有依赖和基础设施版本必须按技术规格锁定（含 `[build-system]` 的 `uv_build`）。
- DEV-OPS-001：Cursor Commands 为 beta；不得假设未证实的参数替换或自动角色切换。
- DEV-OPS-002：Subagent 继承父工具；IDE `permissions.json` 无硬 deny；`git push` 前缀与 `--force` 区分未证实为硬保证；结束标记无官方结构化协议。
- 本开发主机：宿主机侧外部网络经 Mihomo mixed proxy `127.0.0.1:17890`（`mihomo.service`）；`7890` 为既有 SSH/sshd forwarding listener（非空闲、非 Mihomo），AI 不得占用/修改/停止/干扰。Docker daemon 已永久代理至 `17890`。宿主机工具（如 `uv`）经 `17890`，不得误写为经 `7890`。规格 §3.15 / Compose `PROXY__HTTP_URL` 业务字面仍为 `7890`（Contract 不因本机环境改写）。权威 AI 回退策略见 `03_AI_Prompts/00_全局开发规则.md` §18（DEV-OPS-004）。
- **OI-011 / DEV-003-002**：TEI CPU 正式 contract 现为 **12g**（`MEMORY_LIMIT_DECISION=12g`；BAAI/bge-m3 float32 ONNX CPU）。历史 8g `SPEC_RUNTIME_CONTRACT_CONFLICT` 证据保留（分类 A；禁止覆盖）。禁止 docker update 作为正式 evidence。

## 双口令门禁

| 口令 | 状态 |
|---|---|
| PLANNING_DOCS_APPROVED | 已用于规划文档落盘/修订 |
| PLAN_APPROVED（DEV-001 计划） | **已通过**（历史；DEV-001 已 completed） |
| PLAN_APPROVED（DEV-OPS-001 计划） | **已通过**（Round 2）；plan Commit `48a7525`；状态 `completed` |
| CODE_REVIEW_APPROVED（DEV-OPS-001 实现） | **已通过**（P0=0 / P1=0 / P2=1 / P3=1；P2/P3 已接受残余、本轮不修复） |
| PLAN_APPROVED（DEV-OPS-002 计划） | **已通过**（Round 2）；plan Commit `261daa2`；状态 `completed` |
| CODE_REVIEW_APPROVED（DEV-OPS-002 实现） | **已通过**（P0=0 / P1=0 / P2=4 / P3=3；P2/P3 为 residual/backlog，不阻塞） |
| RELEASE_COMPLETED（DEV-OPS-002 实现） | **已完成**；implementation_commit `4943757`；PR #4 merged（`5886cc6`） |
| PLAN_APPROVED（DEV-OPS-003 计划） | **已通过**（Round 1 `PLAN_REJECTED` / MF-001；Amendment 001；Round 2 `PLAN_APPROVED`）；人工确认 2026-08-07 15:39 UTC；`plan_commit=d45ea2f`；implementation=`640616b`；record=`ec47b2a`；PR #7 **MERGED**（`1189447`）；Step 7 smoke **PASSED**；状态 **`completed`**（completed 治理 Commit 待本 docs(status) 落盘） |
| CODE_REVIEW_APPROVED（DEV-OPS-003 实现） | **已通过**（P0=0 / P1=0 / P2=0 / P3 残余；P2 已 CLOSED） |
| RELEASE_COMPLETED（DEV-OPS-003 IMPLEMENTATION_RELEASE） | **已完成**（STRICT）；implementation `640616b`；PR #7 MERGED |
| PLAN_APPROVED（DEV-OPS-003-SMOKE 计划） | **已通过**；人工确认；plan_commit `ba0d827` |
| CODE_REVIEW_APPROVED（DEV-OPS-003-SMOKE 实现） | **已通过**（P0=0 / P1=0） |
| RELEASE_COMPLETED（DEV-OPS-003-SMOKE IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `3a3c7c7`；PR #8 MERGED（`e14d71e8955a312f7c77c6d42c8f624cf3694563`） |
| RELEASE_COMPLETED（DEV-OPS-003-SMOKE POST_MERGE_CLEANUP） | **已完成**；smoke completed governance `45c74f8`；smoke feat 已删；正式 feat 保留 |
| PLAN_APPROVED（DEV-002 计划） | **已通过**（Round 2；Amendment 001）；plan_commit `ceff988` |
| PLAN_APPROVED（DEV-003 计划） | **已通过**（Round 1 `PLAN_REJECTED`；Amendment 001；Round 2 `PLAN_APPROVED`）；plan_commit `1b63d51`；人工确认 2026-08-07 10:33 UTC |
| CODE_REVIEW_APPROVED（DEV-002 实现） | **已通过**（P0=0 / P1=0 / P2=2 / P3=2；P2-001 由 Amendment 002 关闭；不阻塞 Release） |
| RELEASE_COMPLETED（DEV-002 实现） | **已完成**；implementation_commit `f55732c`；PR #5 merged（`7fba544`） |
| CODE_REVIEW_APPROVED（DEV-003 实现） | **已通过**（P0=0 / P1=0 / P2=0 / P3=2；P2-001 Verdict A 接受偏差；GPU lock 修复后复审） |
| RELEASE_COMPLETED（DEV-003 实现） | **已完成**；implementation_commit `d366fb6`；PR #6 merged（`0ac80e5`） |
| PLAN_APPROVED（DEV-OPS-004 计划） | **已通过**；plan_commit `895d7aa`；`workflow_mode=NORMAL`（explicit） |
| CODE_REVIEW_APPROVED（DEV-OPS-004 实现） | **已通过**（P0=0 / P1=0 / P2=0 / P3=0） |
| RELEASE_COMPLETED（DEV-OPS-004 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `14550dfa8043eb5339b89f1c9f215ae368a6f58d`；PR #9 MERGED（`1bc2f499d79301679f373d46c809f1f50e4dad66`） |
| RELEASE_COMPLETED（DEV-OPS-004 POST_MERGE_CLEANUP） | **已完成**；completed 治理 `d5db474`；exact feat 已删 |
| PLAN_APPROVED（DEV-004 计划） | **已通过**；plan_commit `5c2274f`；Amendment 001–002（含 GD-DEV-004-001）；`workflow_mode=NORMAL`（explicit） |
| CODE_REVIEW_APPROVED（DEV-004 实现） | **已通过**（P0=0 / P1=0 / P2=0 / P3=4） |
| RELEASE_COMPLETED（DEV-004 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `d8730a670d577c1f9acb75ebb112fc8f88ea6662`；PR #10 MERGED（`206b7a688cbad3070dc3f1646111efa165f2be87`） |
| RELEASE_COMPLETED（DEV-004 POST_MERGE_CLEANUP） | **已完成**；completed 治理 `4a5cbc2`；exact feat 已删 |
| PLAN_APPROVED（DEV-OPS-005 计划） | **已通过**（Round 1 `PLAN_REJECTED` / MF-1–3；Amendment 001；Round 2 `PLAN_APPROVED`；Amendment 002 章节编号）；人工确认 2026-08-08 10:30 UTC；吸收 SHOULD_FIX 1–3；`workflow_mode=NORMAL`（explicit）；plan_commit `a601a3ba569b12b8fc0ae8ff913f66927381af19` |
| PLAN_APPROVED（DEV-OPS-006 计划） | **已通过**（Plan Reviewer BLOCKER=0 MUST_FIX=0）；人工确认 PLAN_APPROVED；`workflow_mode=NORMAL`（explicit）；plan_commit `09b045be1429716eab184e4565beb30cf2856b28`；PLAN_LANDING 完成 |
| CODE_REVIEW_APPROVED（DEV-OPS-006 实现） | **已通过**（P0=0 / P1=0）；`CODE_REVIEW_APPROVED` |
| RELEASE_COMPLETED（DEV-OPS-006 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `b9f049af59d0e904ebee0ce09df13cc383a91b52`；record `6de3f6ac3acd804df1831dcb58a0b3d1ebecf42f`；PR #18 曾 OPEN 后已 MERGED |
| RELEASE_COMPLETED（DEV-OPS-006 POST_MERGE_CLEANUP） | **已完成**；PR #18 MERGED（`3e727b3dc1a168863d7fa6e8d52a175d36de4644`）；completed 治理 `7abde48af72ea2d676deed64e1333f3e55d08a51`；exact feat 待删 |
| CODE_REVIEW_APPROVED（DEV-OPS-005 实现） | **已通过**（P0=0 / P1=0 / P2=0 / P3=3；P3 残余不阻塞） |
| RELEASE_COMPLETED（DEV-OPS-005 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `373cd331313e02d053a6b49af11beaa7be02acbc`；PR #11 MERGED（`0239c28281949bedec66dbec1412197c5561a611`）；committed 治理 `239218432d6b86d4f34d24c248611361df5d5069` |
| RELEASE_COMPLETED（DEV-OPS-005 POST_MERGE_CLEANUP） | **已完成**（本轮）；completed 治理待本 docs(status) 落盘；exact feat 待删 |
| RELEASE_COMPLETED（DEV-005 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `d32ddc70b5b8b772e9f27a84988b778c226dd2c5`；PR #12 MERGED（`a68d951c50eaeab66f589e5eff5c55d6611f3f43`）；committed 治理 `76a91ce8b0281c03f6587a8ade19c02bc1952c91` |
| RELEASE_COMPLETED（DEV-005 POST_MERGE_CLEANUP） | **已完成**（本轮）；completed 治理待本 docs(status) 落盘；exact feat 待删 |
| RELEASE_COMPLETED（OI-011 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `131a2e994690adb4b06b4d0fa299b229e88ca7d3`；PR #15 MERGED（`7cc020a97b0373579a91e620fcdef90976193c8c`）；committed 治理 `8a595b8507050f75c740b3a0629fddba61563536` |
| RELEASE_COMPLETED（OI-011 POST_MERGE_CLEANUP） | **待本 docs(status): complete 落盘**；exact feat 待删 |
| RELEASE_COMPLETED（OI-012 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `f4d2e614773f7bcdf8b45b39e3e1c438d282b410`；spec commit `bd7529f455ab0c34dc03a6659e1850a5eab189f7`；PR #16 MERGED（`003fb43e24ab5bb5d2401342a0f466fcbe22ce26`） |
| RELEASE_COMPLETED（OI-012 POST_MERGE_CLEANUP） | **本轮**；completed 治理待本 docs(status) 落盘；exact feat 待删 |
| CODE_REVIEW_APPROVED（STM-001 实现） | **已通过**（P0=0 / P1=0）；`CODE_REVIEW_APPROVED` |
| RELEASE_COMPLETED（STM-001 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `66541cf3727d5735dd977e597acd6943fd997fb4`；record `ecc15af80ab18e5fe2905b5f5cd4f371f34127a0`；PR #19 MERGED（`6f2081da6266282470948ecac8e62ef3ae969c15`） |
| RELEASE_COMPLETED（STM-002 POST_MERGE_CLEANUP） | **本轮**；completed 治理待本 docs(status): complete 落盘；exact feat 待删 |
| RELEASE_COMPLETED（STM-003 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `e1913d17b159d426aadfd54d32e07c84ea61043a`；record `34bbebd`；PR #21 MERGED（`3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4`） |
| RELEASE_COMPLETED（STM-004 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `3aed60522db64c3b11597e025caa0aae00afaba6`；record `8c050fc0d09523d82eb201b4f03fa87060efd065`；PR #22 MERGED（`6a3d09f5bf29ec25c768c6295e2c13adb3ff9a6c`） |
| RELEASE_COMPLETED（STM-004 POST_MERGE_CLEANUP） | **本轮**；completed 治理待本 docs(status): complete 落盘；exact feat 待删 |
| RELEASE_COMPLETED（STM-005 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `c166be5cd40475a513cede67f53cafec8fc8529a`；record `a52207473534b1667967be32957c9e1f500ac429`；PR #23 MERGED（`164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf`） |
| RELEASE_COMPLETED（STM-005 POST_MERGE_CLEANUP） | **本轮**；completed 治理待本 docs(status): complete 落盘；exact feat 待删 |
| RELEASE_COMPLETED（DEV-OPS-007 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `1ef8932b87604de9a01dab72e7584a4e7886b155`；record `c48a70d`；PR #24 MERGED（`de95f3a2f0107f791f89441177841754b1d4f82c`） |
| RELEASE_COMPLETED（DEV-OPS-007 POST_MERGE_CLEANUP） | **本轮**；completed 治理待本 docs(status): complete 落盘；exact feat 待删 |
| RELEASE_COMPLETED（STM-006 IMPLEMENTATION_RELEASE） | **已完成**；implementation_commit `683caab306e082d58f577977ba3ecee5c550aa6e`；record `5b9d6cb8125a72b502d93980ae75eb43a3d2fd82`；PR #25 MERGED（`d704bc5421d346d46a48cb69a3a7ad956e94dbb8`） |
| RELEASE_COMPLETED（STM-006 POST_MERGE_CLEANUP） | **本轮**；completed 治理待本 docs(status): complete 落盘；exact feat 待删 |
| RELEASE_COMPLETED（STM-003 POST_MERGE_CLEANUP） | **本轮**；completed 治理待本 docs(status): complete 落盘；exact feat 待删 |

## 固定 Git 初始化流程（DEV-001 历史）

```text
1. 人工将默认分支规范为 main
2. docs(project): add MVP specification and development governance（main）
3. docs(plan): add DEV-001 project skeleton plan（main；含最终版 Task Plan 与 Amendment 001–003）
4. 从 main 创建 feat/DEV-001-project-skeleton
5. 实施会话：状态改为 in_progress 后编码；完成后 build(bootstrap) Commit 在 feat 分支
6. 推送功能分支并创建 GitHub PR
7. docs(status): record DEV-001 implementation commit and PR（feat；治理状态 committed）
8. 人工合并 PR #1（feat → main）
9. docs(status): complete DEV-001 after PR merge（main；治理状态 completed）
```

DEV-001：步骤 1–9 均已完成（实现 Commit `9fbe899`；治理 committed `753c4e4`；PR #1 Merge `a2673ac`；completed 治理 Commit `740d821`）。功能分支本地与远程已删除。当前分支 `main`，与 `origin/main` 同步，工作区干净。

## DEV-OPS-001 Git 流程（已完成）

```text
1. 独立 Plan Review
2. PLAN_APPROVED
3. 状态更新为 approved（Task Plan / master_plan / progress；此时不得实施）
4. 人工在 main 提交 docs(plan): add DEV-OPS-001 cursor agent workflow commands plan
5. 从 main 创建 feat/DEV-OPS-001-cursor-workflow-commands
6. /develop-task：approved → in_progress；实施五个 .cursor/commands/*.md + 强制契约测试
7. 人工实现 Commit `69fabb7` + PR #2
8. docs(status) 治理 Commit `5d00a49`（committed 状态落盘）
9. PR #2 merged → main（Merge Commit `57800c3`）；状态 completed
10. docs(status): complete DEV-OPS-001 after PR merge（main Commit `5f34ccb`）
```

DEV-OPS-001：步骤 1–10 均已完成（实现 Commit `69fabb7`；治理 committed `5d00a49`；PR #2 Merge `57800c3`；completed 治理 Commit `5f34ccb`）。

## DEV-OPS-002 Git 流程（已完成）

```text
1. 独立 Plan Review（Round 2 已通过）
2. PLAN_APPROVED
3. 状态更新为 approved（不得实施）
4. 人工在 main 提交 docs(plan): add DEV-OPS-002 cursor orchestrator subagents plan（`261daa2`）
5. 从 main 创建 feat/DEV-OPS-002-cursor-orchestrator-subagents
6. Developer 实施 Orchestrator + Subagents + permissions + 治理窄例外 + 契约测试
7. Code Review → Commit Recorder → Release Operator push/PR
8. docs(status) 治理 Commit `3c63f77`（committed 状态落盘）
9. PR #4 merged → main（Merge Commit `5886cc6`）；状态 completed
10. docs(status): complete DEV-OPS-002 after PR merge（main；待提交）
11. 立即进入 DEV-002（next_action 必须为 DEV-002 业务规划/实施）
   — Phase B / DEV-OPS-003 不得插队
```

DEV-OPS-002：步骤 1–10 均已完成（实现 Commit `4943757`；治理 committed `3c63f77`；PR #4 Merge `5886cc6`；completed 治理 Commit `f4fab24`）。正式功能分支本地与远程已删除。E2E 证据分支保留。

## DEV-002 Git 流程（已完成）

```text
1. 独立 Plan Review Round 1 → PLAN_REJECTED（MF-001 + SF-001–SF-006）
2. Planner Amendment 001 修订
3. 独立 Plan Review Round 2 → PLAN_APPROVED
4. 人工确认 PLAN_APPROVED → approved
5. 人工在 main 提交 docs(plan): add DEV-002 config system and env example plan（ceff988）
6. 从 main 创建 feat/DEV-002-config-system-env-example
7. Developer 实施：approved → in_progress → tested → reviewed
8. Amendment 002（pydantic-settings 2.14 tuple 语义纠正）
9. Release Operator：implementation commit `f55732c` + PR #5
10. feat 分支 docs(status) committed 治理 `8c9f9de`
11. 人工 Merge PR #5 → main（Merge Commit `7fba544`）
12. docs(status): complete DEV-002 after PR merge（main；治理状态 completed）← 待人工提交
```

DEV-002：步骤 1–12 均已完成（实现 Commit `f55732c`；治理 committed `8c9f9de`；PR #5 Merge `7fba544`；completed 治理 Commit `0b91a34`）。功能分支删除待人工执行。

## DEV-003 Git 流程（已完成）

```text
1. 独立 Plan Review Round 1 → PLAN_REJECTED（MF-001 + MF-002 + SF-001–005）
2. Planner Amendment 001 修订
3. 独立 Plan Review Round 2 → PLAN_APPROVED
4. 人工确认 PLAN_APPROVED → approved（2026-08-07 10:33 UTC）
5. 人工在 main 提交 docs(plan)（`1b63d51`）
6. 从 main 创建 feat/DEV-003-docker-compose-embedding-preflight
7. Developer 实施 → tested → reviewed（GPU lock 修复 + P2-001 Verdict A）
8. Release Operator：implementation commit `d366fb6` + PR #6 open
9. feat 分支 docs(status) committed 治理 `ad493be`
10. 人工 Merge PR #6 → main（Merge Commit `0ac80e5`）
11. docs(status): complete DEV-003 after PR merge（main Commit `c1234c5`）
```

DEV-003：步骤 1–11 均已完成（实现 Commit `d366fb6`；治理 committed `ad493be`；PR #6 Merge `0ac80e5`；completed 治理 `c1234c5`）。功能分支本地与远程已不存在。`main` 与 `origin/main` 同步于 `c1234c5`。

## 最近执行记录

| 日期时间 | Task | 状态变化 | 说明 |
|---|---|---|---|
| 2026-08-06 07:25 UTC | planning | 四文档初版落盘 | 初审未通过（MF/SF） |
| 2026-08-06 07:50 UTC | DEV-001 plan | planned（修订） | 按 MF-001–004、SF-002–004 修订；新增 OI-010 |
| 2026-08-06 08:11 UTC | OI-010 | resolved | 人工决议 uv_build；规格 §3.5 与计划文档同步 |
| 2026-08-06 08:30 UTC | DEV-001 | planned → approved | PLAN_APPROVED；Amendment 003（SF-A/SF-B）；未实施、未 Git |
| 2026-08-06 09:54 UTC | DEV-001 | approved → in_progress | PRE-ENV-001/002 satisfied；当前分支 feat/DEV-001-project-skeleton；开始白名单实施 |
| 2026-08-06 10:12 UTC | DEV-001 | in_progress → implemented | 白名单文件已创建；`uv lock`/`uv sync --locked` 成功（代理 7890） |
| 2026-08-06 10:14 UTC | DEV-001 | implemented → tested | pytest 12 passed；ruff/mypy 通过；停止等待 Code Review |
| 2026-08-06 10:30 UTC | DEV-001 | tested → reviewed | 独立 Code Review PASS（P0/P1=0）；复跑门禁通过 |
| 2026-08-06 12:55 UTC | DEV-001 | reviewed → committed | 人工 Commit `9fbe899`（build(bootstrap): add project skeleton, uv lock, and quality tooling）；分支已推送；PR #1 open 尚未 merge |
| 2026-08-06 13:06 UTC | DEV-001 | Git 计划增补 | Amendment 004：§13 增加两条 `docs(status)` 治理 Commit；同步 Git 流程与 next_action |
| 2026-08-06 13:20 UTC | DEV-001 | committed → completed | PR #1 merged 至 main（Merge Commit `a2673ac`）；治理 committed Commit `753c4e4`；实现 Commit `9fbe899` |
| 2026-08-06 | DEV-001 | completed 落盘 | main 治理 Commit `740d821`：`docs(status): complete DEV-001 after PR merge`；功能分支已删；main 已同步远程 |
| 2026-08-06 14:03 UTC | DEV-OPS-001 | planned | 创建 Task Plan；master_plan CHANGE-002 登记；等待独立 Plan Reviewer；未创建 `.cursor/commands/`；未 Git 写 |
| 2026-08-06 14:16 UTC | DEV-OPS-001 | planned（Amendment 001） | 首轮 PLAN_REJECTED（BLOCKER 0 / MUST_FIX 4 / SHOULD_FIX 6）；已落实全部修订；状态仍 planned；等待同一 Reviewer 复审；未实施、未 Git 写 |
| 2026-08-06 14:25 UTC | DEV-OPS-001 | planned → approved | Round 2 PLAN_APPROVED（BLOCKER 0 / MUST_FIX 0 / SHOULD_FIX 0）；状态回写为 approved；未实施、未创建 `.cursor/commands/`、未 Git 写 |
| 2026-08-06 | DEV-OPS-001 | docs(plan) + feat 分支 | 人工 Commit `48a7525`（`docs(plan): add DEV-OPS-001 cursor agent workflow commands plan`）；已切到 `feat/DEV-OPS-001-cursor-workflow-commands` |
| 2026-08-06 14:42 UTC | DEV-OPS-001 | approved → in_progress | `/develop-task` 前置检查通过（分支/干净工作区/PLAN_APPROVED/plan Commit `48a7525`）；开始白名单实施 |
| 2026-08-06 14:45 UTC | DEV-OPS-001 | in_progress → implemented | 五个 `.cursor/commands/*.md` + `tests/unit/test_cursor_commands_contract.py` 已创建 |
| 2026-08-06 14:46 UTC | DEV-OPS-001 | implemented → tested | 契约 8 passed；unit 20 passed；ruff/mypy 通过；UI `/` 冒烟待人工；停止等待 Code Review |
| 2026-08-06 14:51 UTC | DEV-OPS-001 | tested（保持） | OI-OPS-005 人工 UI 冒烟通过：`plan-task`/`review-plan`/`develop-task`/`review-code`/`close-task` 均可见且可加载；仅验证发现与加载；未改命令/测试；未 Git 写 |
| 2026-08-06 15:03 UTC | DEV-OPS-001 | tested → reviewed | 独立 Code Review：P0=0/P1=0/P2=1/P3=1；`CODE_REVIEW_APPROVED`；复跑契约 8/unit 20/ruff/mypy 通过；P2/P3 已接受残余、本轮不修复实现；仅改治理文档；未 Git 写 |
| 2026-08-06 15:23 UTC | DEV-OPS-001 | reviewed → committed | 人工实现 Commit `69fabb7`（`chore(cursor): add project slash commands and command contract tests`）；GitHub PR #2 已创建（open，base main，未 merge）；治理 docs(status) 待人工提交 |
| 2026-08-06 15:28 UTC | DEV-OPS-001 | committed（治理落盘） | 人工 Commit `5d00a49`（`docs(status): record DEV-OPS-001 implementation commit and PR`）；feat 分支已推送 |
| 2026-08-06 15:30 UTC | DEV-OPS-001 | committed → completed | PR #2 merged 至 main（Merge Commit `57800c3`）；治理 committed Commit `5d00a49`；实现 Commit `69fabb7` |
| 2026-08-06 | DEV-OPS-001 | completed 落盘 | main 治理 Commit `5f34ccb`：`docs(status): complete DEV-OPS-001 after PR merge` |
| 2026-08-06 15:50 UTC | DEV-OPS-002 | planned | 创建 Task Plan；master_plan CHANGE-003 登记；等待独立 Plan Review；未创建 Subagent/Orchestrator/权限；未 Git 写；未改 DEV-002 |
| 2026-08-07 02:05 UTC | DEV-OPS-002 | planned（Planner 复核） | `/plan-task` 复核官方 Subagents/permissions；补强归档/降级/五命令不可改；状态仍 planned；未实施、未 Git 写 |
| 2026-08-07 02:12 UTC | DEV-OPS-002 | planned（Amendment 001） | Round 1 PLAN_REJECTED（BLOCKER 0 / MUST_FIX 5 / SHOULD_FIX 3）；已落实治理例外/fail-closed/退出码/E2E/完成后进 DEV-002；治理文件尚未改；待 Round 2 |
| 2026-08-07 02:18 UTC | DEV-OPS-002 | planned → approved | Round 2 PLAN_APPROVED（BLOCKER 0 / MUST_FIX 0 / SHOULD_FIX 0）；状态回写为 approved；未实施、未创建 agents/permissions、未改治理/五命令、未 Git 写 |
| 2026-08-07 | DEV-OPS-002 | docs(plan) + feat 分支 | 人工 Commit `261daa2`；已切到 `feat/DEV-OPS-002-cursor-orchestrator-subagents` |
| 2026-08-07 02:32 UTC | DEV-OPS-002 | approved → in_progress | `/develop-task` 前置检查通过；开始白名单实施 |
| 2026-08-07 02:36 UTC | DEV-OPS-002 | in_progress → implemented | 六 Subagent + Orchestrator + 权限 + 治理例外 + 契约测试已创建 |
| 2026-08-07 02:38 UTC | DEV-OPS-002 | implemented → tested（误标） | 契约 18/unit 30/ruff/mypy 通过；E2E 未完成即标 tested（不符合 §9） |
| 2026-08-07 02:40 UTC | DEV-OPS-002 | tested → implemented | UI discovery 人工通过（七项）；完整 E2E pending；不得 Code Review；仅改治理文档 |
| 2026-08-07 04:13 UTC | DEV-OPS-002 | 受监督 E2E 首轮 | Composer 2.5 Developer 成功；Orchestrator 越权写 progress.md | E2E **失败**；MUST_FIX；状态保持 implemented |
| 2026-08-07 04:13 UTC | DEV-OPS-002 | MUST_FIX 最小修复 | 修订 orchestrate-task 可写交集 + 契约测试 | 契约 21/unit 42/ruff/mypy 通过；E2E pending 重跑 |
| 2026-08-07 04:56 UTC | DEV-OPS-002 | implemented → tested | 受监督完整 E2E passed；PR #3 创建后停止 | 允许 Code Review（尚未执行）；E2E 分支保留；仅改治理文档 |
| 2026-08-07 05:05 UTC | DEV-OPS-002 | tested → reviewed | 独立 Code Review CODE_REVIEW_APPROVED；P0/P1=0；P2/P3 已记录 | 下一步 Commit Recorder；implementation_commit=null；仅改治理文档 |
| 2026-08-07 07:00 UTC | DEV-OPS-002 | reviewed → committed | Release Operator RELEASE_COMPLETED；PR #4 open（base=main） | implementation_commit `4943757`；runtime note 已记录 |
| 2026-08-07 07:00 UTC | DEV-OPS-002 | committed（治理落盘） | 人工 Commit `3c63f77`（`docs(status): record DEV-OPS-002 implementation commit and PR`） | PR #4 待人工 merge |
| 2026-08-07 07:11 UTC | DEV-OPS-002 | committed → completed | PR #4 merged 至 main（Merge Commit `5886cc6`）；`mergedAt=2026-08-07T07:11:20Z` | 正式功能分支本地/远端已删除；E2E 证据分支保留 |
| 2026-08-07 07:16 UTC | DEV-OPS-002 | completed（治理回写） | 仅改治理文档；`current_task` → DEV-002 | status_record_commit_completed=null；下一步 docs(status) complete |
| 2026-08-07 07:32 UTC | DEV-002 | planned（Round 1 规划） | 创建 Task Plan `02_开发管理/tasks/DEV-002-config-system-env-example.md`；master_plan CHANGE-004；progress 规划态回写 | 未实施、未 Git 写；等待独立 Plan Review |
| 2026-08-07 08:00 UTC | DEV-002 | planned（Amendment 001 / Round 2） | Round 1 PLAN_REJECTED（MF-001 + SF-001–SF-006）；已修订 Task Plan（settings_customise_sources 顺序、shutdown/retrieval 校验、EMBEDDING_* env 决策、conftest 禁止改、§7.2 九字段、pytest -k 引号）；progress/master_plan 同步 | 未实施、未 Git 写；status 保持 planned；等待 Plan Review Round 2 |
| 2026-08-07 08:15 UTC | DEV-002 | in_progress → tested | Developer 实施 settings/configs/.env.example/测试；质量门禁全通过 | settings_customise_sources 顺序调整见 Task Plan §17；未 Git 写；待 Code Review |
| 2026-08-07 08:25 UTC | DEV-002 | tested → reviewed | 独立 Code Review CODE_REVIEW_APPROVED；P0/P1=0；P2=3/P3=2 已记录 | Commit Recorder READY_FOR_HUMAN_COMMIT；implementation_commit=null；未 Git 写 |
| 2026-08-07 08:52 UTC | DEV-002 | reviewed（Amendment 002） | 纠正 pydantic-settings 2.14 tuple 语义文档；新增 Amendment 002；未改业务实现 | CODE_REVIEW_APPROVED 仍有效；P2-001 关闭；待 Release Operator |
| 2026-08-07 09:00 UTC | DEV-002 | reviewed → committed | Release Operator RELEASE_COMPLETED；PR #5 open（base=main） | implementation_commit `f55732c`；治理 committed `8c9f9de` |
| 2026-08-07 09:44 UTC | DEV-002 | committed → completed | PR #5 merged 至 main（Merge Commit `7fba544`）；`current_task` → DEV-003 | status_record_commit_completed=null；下一步 docs(status) complete + DEV-003 规划 |
| 2026-08-07 10:30 UTC | DEV-003 | planned（Amendment 001 / Round 2） | Round 1 PLAN_REJECTED（MF-001 env 注入、MF-002 Preflight §3.18、SF-001–005）；已修订 Task Plan §7.6/Step 10/§11–§13/Amendment 001；progress/master_plan 同步 | 未实施、未 Git 写；status 保持 planned；等待 Plan Review Round 2 |
| 2026-08-07 10:33 UTC | DEV-003 | planned → approved | Round 2 PLAN_APPROVED（BLOCKER 0 / MUST_FIX 0 / SHOULD_FIX 5 非阻塞）；人工确认 PLAN_APPROVED；治理回写 Task Plan / progress / master_plan | 未实施、未创建 feat 分支、未 Git 写；下一步人工 docs(plan) on main |
| 2026-08-07 12:05 UTC | DEV-003 | approved → in_progress → tested | Developer 实施 §5 白名单：Compose 拓扑、Embedding 脚本、Preflight、测试；94 passed / 2 skipped；ruff/mypy 通过 | 未 Git 写；`versions.lock.env` digests 经 manifest inspect；待 Code Review |
| 2026-08-07 14:48 UTC | DEV-003 | tested → reviewed | GPU lock `--gpus all` 修复；pytest 96 passed / 2 skipped；`lock_tei_images.sh` validate passed | P2-001 Verdict A 记入 §17 |
| 2026-08-07 15:00 UTC | DEV-003 | reviewed → committed | Release Operator RELEASE_COMPLETED；PR #6 open（base=main）；implementation_commit `d366fb6` | 治理 docs(status) committed 待提交 |
| 2026-08-07 15:05 UTC | DEV-003 | committed（治理准备） | 回写 progress / Task Plan / master_plan 为 committed 态；记录 PR #6 OPEN | 未 Git 写；待人工 `docs(status): record DEV-003 implementation commit and PR` |
| 2026-08-07 15:08 UTC | DEV-003 | committed（治理落盘） | 人工 Commit `ad493be`（`docs(status): record DEV-003 implementation commit and PR`） | PR #6 待人工 merge |
| 2026-08-07 15:10 UTC | DEV-003 | committed → completed | PR #6 merged 至 main（Merge Commit `0ac80e5`）；`current_task` → DEV-004 | `status_record_commit_completed=null`；下一步 docs(status) complete |
| 2026-08-07 15:10 UTC | DEV-003 | completed（治理准备） | 回写 progress / Task Plan / master_plan 为 completed 态 | 未 Git 写；待人工 `docs(status): complete DEV-003 after PR merge` |
| 2026-08-07 | DEV-003 | completed（治理落盘） | 人工 Commit `c1234c5`（`docs(status): complete DEV-003 after PR merge`） | `main`==`origin/main`；feat 分支已清理 |
| 2026-08-07 15:22 UTC | DEV-OPS-003 | planned（人工插入覆盖） | 用户显式覆盖先前「不得插入 DEV-OPS-003 / 立即 DEV-004」next_action；创建 Task Plan；master_plan CHANGE-006 登记 | 未实施、未 Git 写、未创建分支；**不得开始 DEV-004**；等待独立 Plan Review |
| 2026-08-07 15:35 UTC | DEV-OPS-003 | planned（Amendment 001） | Round 1 `PLAN_REJECTED`（MF-001）；封闭方案 A：`IMPLEMENTATION_RELEASE` 禁 push/commit main；committed/record 仅 feat；采纳 SF-001–SF-004 | 状态保持 planned；未实施、未 Git 写；等待 Round 2 Plan Review |
| 2026-08-07 15:39 UTC | DEV-OPS-003 | planned → approved | Round 2 Plan Reviewer = `PLAN_APPROVED`（BLOCKER 0 / MUST_FIX 0；SF-R2-001/002 非阻塞）；人工确认 `PLAN_APPROVED`；治理回写 Task Plan / progress / master_plan；SF-R2-002 checklist 换行 hygiene；Amendment 001 原文保留 | 未实施、未创建 feat、未 Git 写；本任务自身 STRICT；NORMAL 自动 phase 尚未可用；下一步人工 docs(plan) on main |
| 2026-08-07 | DEV-OPS-003 | docs(plan) + feat 分支 | 人工 Commit `d45ea2f`（`docs(plan): add DEV-OPS-003 normal and strict workflow modes plan`）；已切到 `feat/DEV-OPS-003-normal-strict-workflow-modes` | plan_commit 已落盘 |
| 2026-08-07 15:49 UTC | DEV-OPS-003 | approved → in_progress | Developer 只读核对通过（分支/干净工作区/`d45ea2f`）；开始 §5 白名单实施 | 禁止 Git 写；不得开始 DEV-004 |
| 2026-08-07 15:55 UTC | DEV-OPS-003 | in_progress → implemented → tested | Orchestrator/Release/Commit Recorder/permissions/cli/治理/git_workflow + 契约测试落地；49 契约 + 101 unit + ruff/mypy 通过 | Step 7 冒烟 pending；待独立 Code Review（STRICT）；未 Git 写 |
| 2026-08-08 01:00 UTC | DEV-OPS-003 | tested → reviewed | 独立 Code Reviewer = `CODE_REVIEW_APPROVED`（P0=0/P1=0/P2=1/P3=2）；Orchestrator 复测 49/101/ruff/mypy 通过 | 下一步 Commit Recorder；STRICT 不自动 IMPLEMENTATION_RELEASE；未 Git 写 |
| 2026-08-08 01:15 UTC | DEV-OPS-003 | reviewed（P2 fix pending re-review） | 角色段 mode-conditional 自动续跑；modes 契约新增角色段断言；commands 共享子串保留；50/102/ruff/mypy 通过 | 未改五命令/src/DEV-004；未 Git 写；不进入 Release |
| 2026-08-08 01:25 UTC | DEV-OPS-003 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation_commit `640616b`；PR #7 OPEN（base=main，head=feat） | 仅 feat push；禁 push main；Step 7 冒烟 pending；等待人工 Merge |
| 2026-08-08 | DEV-OPS-003 | PR #7 MERGED | Merge Commit `1189447`；main 含实现 | 正式任务**尚未 completed**；正式 feat 仍保留；不得开始 DEV-004 |
| 2026-08-08 01:26 UTC | DEV-OPS-003-SMOKE | planned | 新建 Task Plan `DEV-OPS-003-SMOKE-normal-workflow.md`；progress 临时指向 smoke；**未改 master_plan** | 等待计划审查 / PLAN_APPROVED；本轮禁止 PLAN_LANDING / Git 写 / 建分支 |
| 2026-08-08 01:30 UTC | DEV-OPS-003-SMOKE | planned → approved | PLAN_LANDING：docs(plan) `ba0d827`；exact feat `feat/DEV-OPS-003-SMOKE-normal-workflow` 已创建 | 人工 PLAN_APPROVED 已确认 |
| 2026-08-08 01:32 UTC | DEV-OPS-003-SMOKE | approved → in_progress → implemented → tested | Developer 创建 `tests/e2e/devops003_normal_workflow_smoke.txt`（恰好一行 marker）；白名单三路径；marker 自检通过 | 未 Git 写；未改 master_plan；正式 DEV-OPS-003 未 completed；待 Code Review |
| 2026-08-08 01:35 UTC | DEV-OPS-003-SMOKE | tested → reviewed → committed | IMPLEMENTATION_RELEASE：implementation `3a3c7c7`；PR #8 OPEN；docs(status): record on feat | 仅 feat push；禁 push main；未 merge；正式 feat 未删 |
| 2026-08-08 05:05 UTC | DEV-OPS-003-SMOKE | committed → completed | POST_MERGE_CLEANUP：PR #8 MERGED（`e14d71e`）；docs(status): complete on main；仅删 smoke feat | progress 恢复 `current_task=DEV-OPS-003`；正式未 completed；正式 feat 保留；未开始 DEV-004 |
| 2026-08-08 05:12 UTC | DEV-OPS-003 | committed → completed | 正式治理回写：PR #7 MERGED / Step 7 PASSED / STRICT 证据充分；同步 Task Plan / progress / master_plan | 本轮未 Git 写；正式 feat 仍保留待人工删；`next_action`→DEV-004 规划；本 Commit 不得开始 DEV-004 实施 |
| 2026-08-08 | DEV-OPS-003 | completed（治理落盘） | `docs(status): complete DEV-OPS-003 after PR merge and smoke`（`4e4ad19`） | `main`==`origin/main`；工作区曾干净 |
| 2026-08-08 05:52 UTC | DEV-OPS-004 | planned（人工插入覆盖） | 用户显式覆盖先前「进入 DEV-004 业务规划」；创建 Task Plan；master_plan CHANGE-007 登记 | 未实施、未 Git 写、未创建分支；**不得开始 DEV-004**；等待独立 Plan Review |
| 2026-08-08 05:57 UTC | DEV-OPS-004 | planned → approved | PLAN_LANDING：docs(plan) on main；创建 exact feat `feat/DEV-OPS-004-mihomo-network-fallback-policy` | 人工 PLAN_APPROVED 已确认；未实施；**不得开始 DEV-004** |
| 2026-08-08 06:01 UTC | DEV-OPS-004 | approved → in_progress | Developer 开始白名单实施：全局规则 §18 + 契约测试 | plan_commit `895d7aa`；未 Git 写；不得开始 DEV-004 |
| 2026-08-08 06:03 UTC | DEV-OPS-004 | in_progress → implemented → tested | §18 策略（Docker/分类/健康检查/active·inactive/Never/有界重试/安全边界/working tree）；契约 15；unit 117；ruff/mypy 通过 | SHOULD_FIX 已落实（7890 SSH/sshd；全部分类；unexpected dirty）；未 Git 写；待 Code Review |
| 2026-08-08 06:07 UTC | DEV-OPS-004 | tested → reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `14550df`；PR #9 OPEN；docs(status): record on feat | 仅 feat push；禁 push main；等待人工 Merge；不得开始 DEV-004 |
| 2026-08-08 06:15 UTC | DEV-OPS-004 | PR #9 MERGED | Merge Commit `1bc2f499d79301679f373d46c809f1f50e4dad66`；main 含 §18 + 契约 | 等待自动 POST_MERGE_CLEANUP |
| 2026-08-08 06:18 UTC | DEV-OPS-004 | committed → completed | POST_MERGE_CLEANUP：docs(status): complete on main；删 exact feat；`current_task` → DEV-004 planned | 未开始 DEV-004 实施；`next_action`→DEV-004 业务规划 |
| 2026-08-08 07:39 UTC | DEV-004 | planned（Planner 初版） | 创建 Task Plan `DEV-004-migration-runner-es-mapping-alias.md`；master_plan CHANGE-008；progress 规划态回写 | 未实施、未 Git 写、未建分支；`next_action=计划审查`；不得开始 DEV-005/006 |
| 2026-08-08 07:46 UTC | DEV-004 | planned → approved | 人工 PLAN_APPROVED；Plan Reviewer BLOCKER/MUST_FIX=0；Amendment 001 吸收 SHOULD_FIX | 等待 Release Operator PLAN_LANDING；不得实施直至 feat 就绪 |
| 2026-08-08 07:47 UTC | DEV-004 | approved（PLAN_LANDING） | docs(plan) `5c2274fb2da77e7eaf1ab5df248fcf8a64a95d9a`；创建 `feat/DEV-004-migration-runner-es-mapping-alias` | `next_action`→Developer 实施；未实施 |
| 2026-08-08 09:20 UTC | DEV-004 | in_progress → tested | 白名单实现完成；SAFE_RESIDUAL_CLEANUP；Stage6 host-proxy build；Stage7 init-infra；Stage8 integration；ruff/mypy/unit/contract 全绿 | 等待独立 Code Review；未 Git 写；未 READY 前不得 Commit |
| 2026-08-08 09:48 UTC | DEV-004 | tested（保持） | 独立治理审计 GD-DEV-004-001：NON_BLOCKING（GD-001 Stage6b→6c；GD-002 Stage7→6d→7） | 要求 Amendment 002 + progress 记录后方可 Code Review |
| 2026-08-08 09:55 UTC | DEV-004 | tested → reviewed | 独立 Code Review `CODE_REVIEW_APPROVED`；P0=0/P1=0/P2=0/P3=4 | Commit Recorder → IMPLEMENTATION_RELEASE；未 Git 写 |
| 2026-08-08 09:58 UTC | DEV-004 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `d8730a6`；PR #10 OPEN；docs(status): record on feat | 仅 feat push；禁 push main；等待人工 Merge |
| 2026-08-08 10:07 UTC | DEV-004 | PR #10 MERGED | Merge Commit `206b7a688cbad3070dc3f1646111efa165f2be87`；main 含 Migration Runner + ES Mapping/Alias | 等待自动 POST_MERGE_CLEANUP |
| 2026-08-08 10:10 UTC | DEV-004 | committed → completed | POST_MERGE_CLEANUP：main docs(status): complete；删 exact feat | `current_task`→DEV-005 planned；未开始 DEV-005 实施 |
| 2026-08-08 10:20 UTC | DEV-OPS-005 | planned（人工插入覆盖） | 用户显式覆盖先前「进入 DEV-005 业务规划」；创建 Task Plan；master_plan CHANGE-009 登记 | 未实施、未 Git 写、未创建分支；**不得开始 DEV-005**；等待独立 Plan Review |
| 2026-08-08 10:22 UTC | DEV-OPS-005 | Plan Review Round 1 | 独立 Plan Reviewer：`PLAN_REJECTED`；BLOCKER=0；MUST_FIX=MF-1/MF-2/MF-3（READY_FOR_HUMAN_COMMIT 非第三门、START_EXISTING_TASK planning-only、PLAN_APPROVED 后 NORMAL 自动链） | 未实施；等待 Planner Amendment |
| 2026-08-08 10:25 UTC | DEV-OPS-005 | Amendment 001 | Planner 吸收 MF-1/MF-2/MF-3 + SHOULD_FIX 入 §2/§5/§8；status 保持 planned | 未实施、未 Git 写 |
| 2026-08-08 10:28 UTC | DEV-OPS-005 | Plan Review Round 2 | 独立 Plan Reviewer：`PLAN_APPROVED`；BLOCKER=0；MUST_FIX=0；SHOULD_FIX=STRICT 对照/章节编号/progress 时间线 | 等待人工确认 |
| 2026-08-08 10:30 UTC | DEV-OPS-005 | approved（人工 PLAN_APPROVED） | 用户确认批准 Task Plan；要求吸收 SHOULD_FIX 1–3；NORMAL 自动续跑 | 进入 PLAN_LANDING；**不得开始 DEV-005** |
| 2026-08-08 10:31 UTC | DEV-OPS-005 | approved（PLAN_LANDING） | docs(plan) `a601a3ba569b12b8fc0ae8ff913f66927381af19`；创建 `feat/DEV-OPS-005-human-prompt-playbook-recovery-operations` | `next_action`→Developer 实施；未实施；**不得开始 DEV-005** |
| 2026-08-08 10:40 UTC | DEV-OPS-005 | approved → in_progress | Developer 开工：Playbook + 契约测试 + README 短入口；治理回写 | 未 Git 写；**不得开始 DEV-005** |
| 2026-08-08 10:45 UTC | DEV-OPS-005 | in_progress → tested | Playbook+契约+README 完成；Contract 28 / unit 156 / ruff / mypy 全绿 | 等待独立 Code Review；未 Git 写；**不得开始 DEV-005** |
| 2026-08-08 10:46 UTC | DEV-OPS-005 | tested → reviewed | 独立 Code Review `CODE_REVIEW_APPROVED`；P0=0/P1=0/P2=0/P3=3 | Commit Recorder READY_FOR_HUMAN_COMMIT；进入 IMPLEMENTATION_RELEASE；**不得开始 DEV-005** |
| 2026-08-08 10:50 UTC | DEV-OPS-005 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `373cd331313e02d053a6b49af11beaa7be02acbc`；PR #11 OPEN | 仅 feat push；禁 push main；等待人工 Merge；**不得开始 DEV-005** |
| 2026-08-08 10:53 UTC | DEV-OPS-005 | PR #11 MERGED | Merge Commit `0239c28281949bedec66dbec1412197c5561a611`；main 含 Playbook + 契约 | 等待自动 POST_MERGE_CLEANUP |
| 2026-08-08 10:55 UTC | DEV-OPS-005 | committed → completed | POST_MERGE_CLEANUP：main docs(status): complete；删 exact feat | `current_task`→DEV-005 planned；未开始 DEV-005 实施 |
| 2026-08-08 11:20 UTC | DEV-005 | planned（Planner 初版） | 创建 Task Plan `DEV-005-api-shell-auth-request-id-logging-metrics.md`；master_plan CHANGE-010；progress 规划态回写 | 未实施、未 Git 写、未建分支；`next_action=计划审查`；不得开始 DEV-006/STM/Retrieval |
| 2026-08-08 11:35 UTC | DEV-005 | approved → in_progress → tested | FastAPI 壳、鉴权、Request ID、structlog、Prometheus、Health；entrypoint 接线；Unit 18 + Contract 12；ruff/mypy 全绿 | 等待独立 Code Review；未 Git 写 |
| 2026-08-08 19:45 UTC | DEV-005 | tested（P1 修复） | P1-001：`kafka_consumer_lag` Gauge 注册并加入 `ALL_METRICS`；Contract 12 / ruff / mypy 全绿 | 等待 Code Review 复审；未 Git 写 |
| 2026-08-08 19:50 UTC | DEV-005 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `d32ddc70b5b8b772e9f27a84988b778c226dd2c5`；PR #12 OPEN | 仅 feat push；禁 push main；等待人工 Merge |
| 2026-08-08 12:00 UTC | DEV-005 | PR #12 MERGED | Merge Commit `a68d951c50eaeab66f589e5eff5c55d6611f3f43`；main 含 API 壳 + 鉴权 + 可观测性 | 等待 POST_MERGE_CLEANUP |
| 2026-08-08 12:05 UTC | DEV-005 | committed → completed | POST_MERGE_CLEANUP：main docs(status): complete；删 exact feat | `next_action`→等待用户显式指定下一任务；**不得启动 DEV-006** |
| 2026-08-08 20:06 UTC | DEV-006 | planned（Planner 初版） | 创建 Task Plan `DEV-006-tei-embedding-client-token-budget.md`；master_plan CHANGE-011；progress 规划态回写 | 未实施、未 Git 写、未建分支；`next_action=计划审查`；不得开始 STM/EXT/RET 实施 |
| 2026-08-08 20:30 UTC | DEV-006 | planned（Amendment 001） | Round 1 `PLAN_REJECTED`（MF-001/MF-002）；吸收方案 A + api_shell 必改；修订 §3/§5/§6/§7/§10/§14 | 未实施、未 Git 写；status 保持 planned；`next_action=计划审查 Round 2` |
| 2026-08-08 14:52 UTC | DEV-003-002 | planned（Planner 初版） | 创建 Task Plan `02_开发管理/tasks/DEV-003-002-tei-cpu-memory-contract-validation.md`；master_plan CHANGE-012；progress 插入覆盖 DEV-006 PAUSED | 未实施、未 Git 写、未建分支；`next_action=计划审查`；**不得触碰 DEV-006 feat / PR #13** |
| 2026-08-09 | DEV-003-002 | completed | PR #14 MERGED `4d894cc`；docs(status) complete `2356a85`；`TOOLING_STATUS=VALID`；`RUNTIME_CONTRACT_STATUS=SPEC_RUNTIME_CONTRACT_CONFLICT` | DEV-006 R1 satisfied；R2–R4 BLOCKED pending Spec-OI |
| 2026-08-09 01:30 UTC | OI-011 | planned（Planner 初版） | 创建 Task Plan `02_开发管理/tasks/OI-011-bge-m3-cpu-tei-memory-contract.md`；master_plan CHANGE-013；open_issues OI-011；progress 插入覆盖刷新 | 未实施、未 Git 写、未建分支；`next_action=计划审查`；DEV-006 保持 PAUSED；**不得触碰 DEV-006 feat / Merge PR #13** |
| 2026-08-09 01:45 UTC | OI-011 | planned（Amendment 001） | Round 1 `PLAN_REJECTED`（BLOCKER=0；MUST_FIX=4；SHOULD_FIX=4）；吸收 MF-1～MF-4 + SF-1～SF-4：§5.3 overlay+显式 `-f`、§5.7 Check 13a 公式、§5.8 MemAvailable 方案 A、§5.9 双 fixture、compose.sh 黑名单、start_embedding 必改 | 未实施、未 Git 写；status 保持 planned；`next_action=计划审查 Round 2`；DEV-006 保持 PAUSED |
| 2026-08-09 01:55 UTC | OI-011 | planned（Amendment 002） | Round 3 remediation：MF-3 查表 `D=12→CPU_MIN=16/REC=20`（公式权威）；吸收 R2 SF-1～SF-4（单一 helper 含 8g、§3.10.3 唯一句式/`NON_SPEC_COMPLIANT`、peak≥limit NON_VIABLE、env-file 对齐 compose.sh） | 未实施、未 Git 写、未 TEI probe；status 保持 planned；`next_action=计划审查 Round 3`；DEV-006 保持 PAUSED |
| 2026-08-09 02:00 UTC | OI-011 | approved（PLAN_LANDING） | Round 3 `PLAN_APPROVED`（BLOCKER=0；MUST_FIX=0）；人工确认；docs(plan) on main；创建 `feat/OI-011-bge-m3-cpu-tei-memory-contract`；Amendment 001/002→approved | `plan_commit` 禁 self-ref（报告给出真实 SHA）；`next_action`→Developer 实施；DEV-006 仍 PAUSED；**不得触碰 DEV-006 feat / Merge PR #13** |
| 2026-08-09 02:10 UTC | OI-011 | in_progress（Phase A1） | overlays + probe `--mem-limit` helper；unit `test_tei_memory_probe`/`test_tei_probe_mocked_paths` 34 passed；下一步 Phase A2 串行 matrix | 未改正式 mem_limit；未伪造测量；DEV-006 仍 PAUSED |
| 2026-08-09 02:35 UTC | OI-011 | tested | matrix→`MEMORY_LIMIT_DECISION=12g`；规格/compose/preflight/start_embedding/Layer B 落地；formal measure PASS；OI resolved | 待 Code Review；未 Git 写；compose.sh 未改；DEV-006 仍 PAUSED 至 OI-011 merge |
| 2026-08-09 02:36 UTC | OI-011 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `131a2e994690adb4b06b4d0fa299b229e88ca7d3`；PR #15 OPEN；docs(status): record on feat | 仅 feat push；禁 push main；MEMORY_LIMIT_DECISION=12g；保留 CONFLICT@8g；**不得触碰 DEV-006 / Merge PR #13** |
| 2026-08-09 02:42 UTC | OI-011 | committed → completed | PR #15 MERGED 至 main（Merge Commit `7cc020a`）；`RUNTIME_CONTRACT_STATUS=PASS`；`dev006_dependency_status=READY_FOR_RESUME_AFTER_OI011_MERGE` | POST_MERGE_CLEANUP 本轮；**不得 Merge PR #13** |
| 2026-08-09 06:00 UTC | OI-012 | Amendment 002 MVP_SIMPLIFICATION | 缩减为最小 Spec-OI；单一 DEV-007；DEFERRED 清单；retry=3；不 PLAN_LANDING | 无 | 待 Round 2 计划审查 |
| 2026-08-09 06:15 UTC | OI-012 | Amendment 002.1 | MF-1 HEAD SHA 修正；SF-1 master_plan spec_sections；SF-2 local_tei fail-fast；SF-3 batch limits；SF-4 §11 git plan | 无 | 待 Round 2 复审 |
| 2026-08-09 06:52 UTC | OI-012 | Round 3 PLAN_APPROVED | Amendment 002 MVP Simplification；BLOCKER=0；MUST_FIX=0 | 无 | 进入 Developer 实施 |
| 2026-08-09 07:05 UTC | OI-012 | reviewed → committed | IMPLEMENTATION_RELEASE；PR #16 OPEN；docs(spec)+docs(governance) 双 commit | 无 | `plan_commit=e122c8a`；`next_action=等待 PR Merge` |
| 2026-08-09 07:02 UTC | OI-012 | committed → completed | PR #16 MERGED（`003fb43`）；POST_MERGE_CLEANUP 本轮 | main 含最小 Spec-OI pivot | `next_action`→DEV-007 规划；feat 待删；**不得启动 DEV-007 实施** |
| 2026-08-09 15:20 UTC | DEV-007 | planned（Planner 初版） | 创建 Task Plan `02_开发管理/tasks/DEV-007-siliconflow-embedding-client-mvp.md`；master_plan CHANGE-016；progress 规划态回写 | 未实施、未 Git 写、未建 feat 分支；`next_action=计划审查`；**不得触碰 DEV-006 feat / PR #13** |
| 2026-08-09 16:20 UTC | DEV-007 | approved → in_progress → tested | SiliconFlow client MVP 实施完成；U1–U6/C1–C17 通过；ruff/mypy/env check 通过 | unit+contract 261 passed（1 main 既有 compose wrapper 失败） | `next_action=Code Review`；未 commit；integration opt-in 未跑 |
| 2026-08-09 08:24 UTC | DEV-007 | committed → completed | PR #17 MERGED（`b7916ea`）；POST_MERGE docs(status) complete；HEAD 后续含 `524786a` record SHA | main 同步；SiliconFlow MVP 在 main | `next_action` 曾为等待下一任务 |
| 2026-08-09 10:42 UTC | DEV-OPS-006 | planned（Planner 初版） | 创建 Task Plan `DEV-OPS-006-phase0-baseline-hygiene-before-stm001.md`；master_plan CHANGE-019；progress 规划态回写 | 只读诊断：分类 **A**；contract 47 passed；unit 215 collected / 1 fail | `next_action=计划审查`；**不得实现 STM-001**；**不得触碰 DEV-006/PR#13** |
| 2026-08-09 12:29 UTC | DEV-OPS-006 | approved（PLAN_LANDING） | docs(plan) `09b045be1429716eab184e4565beb30cf2856b28`；创建 `feat/DEV-OPS-006-phase0-baseline-hygiene-before-stm001` | n/a | `next_action`→Developer 实施；未实施；**不得实现 STM-001**；**不得触碰 DEV-006/PR#13** |
| 2026-08-09 12:33 UTC | DEV-OPS-006 | approved → in_progress → tested | exact-path allowlist + SHOULD_FIX 存在性断言；progress/master_plan hygiene | unit **216 passed**；contract **47 passed**；ruff PASS；mypy PASS | `next_action`→代码审查；未 Git 写；**不得实现 STM-001**；**不得触碰 DEV-006/PR#13** |
| 2026-08-09 12:40 UTC | DEV-OPS-006 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `b9f049af59d0e904ebee0ce09df13cc383a91b52`；PR #18 OPEN；docs(status): record on feat | 仅 feat push；禁 push main；`next_action`→WAITING_FOR_PR_MERGE；**不得自动 merge**；**不得实现 STM-001** |
| 2026-08-09 12:44 UTC | DEV-OPS-006 | committed → completed | PR #18 MERGED（`3e727b3dc1a168863d7fa6e8d52a175d36de4644`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | baseline GREEN；Phase 0 completed；STM-001 READY_FOR_PLANNING；**不得启动 STM-001 实施** |
| 2026-08-10 09:55 UTC | STM-001 | planned → approved | Round 2 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0）；人工确认 PLAN_APPROVED；progress 回写 approved | PLAN_LANDING 进行中；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 10:10 UTC | STM-001 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `66541cf3727d5735dd977e597acd6943fd997fb4`；PR #19 OPEN；docs(status): record on feat | 仅 feat push；禁 push main；`next_action`→WAITING_FOR_PR_MERGE；**不得自动 merge**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 02:11 UTC | STM-001 | committed → completed | PR #19 MERGED（`6f2081da6266282470948ecac8e62ef3ae969c15`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | STM-002 READY_FOR_PLANNING only；**不得启动 STM-002 实施**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 02:38 UTC | STM-002 | planned（Amendment 001） | Planner 吸收 Human Contract 四项决议 + Plan Review SHOULD_FIX；§5/§7/§8/§10 修订；§5 Step 6 与 §6.1 测试路径统一 | 未实施、未 Git 写；`next_action=计划审查 Round 2`；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 02:52 UTC | STM-002 | tested | Developer 实施 Session Create API + Redis WM meta；Unit/Contract/Integration PASS | 未 commit；`next_action=Code Review` |
| 2026-08-10 03:03 UTC | STM-002 | committed | IMPLEMENTATION_RELEASE；implementation `3440048f8a304219ec7bbddf3c192089cac6e8cb`；PR #20 OPEN | 待人工 merge |
| 2026-08-10 04:17 UTC | STM-003 | planned | 创建 Task Plan `STM-003-message-write-lua.md`；master_plan CHANGE-025；progress 规划态回写 | 未实施、未 Git 写；`next_action=计划审查`；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 04:30 UTC | STM-003 | planned（Amendment 001） | Round 1 `PLAN_REJECTED` MF-1：§4.4/§5 Step 3 Lua 步骤重排对齐 OI-STM-003-002；吸收 SF-1 ARGV[7]、SF-2 精确边界 #14/#15、SF-3 contract 白名单 | 未实施、未 Git 写；`next_action=计划审查 Round 2`；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 06:10 UTC | STM-003 | approved → in_progress → tested | Developer：消息写入服务 + Lua；malformed token fail-closed；Integration 17 场景 | scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS | 未 commit；`next_action=Code Review`；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 14:12 UTC | STM-003 | tested（P1-1 修复） | Code Review P1-1：`git checkout --` 回滚 17 条越权路径；白名单外变更清零 | scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS | 未 commit；`next_action=Code Review`；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 14:20 UTC | STM-003 | committed | IMPLEMENTATION_RELEASE；implementation `e1913d17b159d426aadfd54d32e07c84ea61043a`；PR #21 OPEN | scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS | 待人工 merge；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 06:26 UTC | STM-003 | committed → completed | PR #21 MERGED（`3a08a8040a429e5f5ccb3e143b5cce7cb7ee7bf4`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | scoped 21 / integration 11 / full unit 287 / contract 62；ruff PASS；mypy PASS | STM-004 READY_FOR_PLANNING only；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 08:02 UTC | STM-004 | committed → completed | PR #22 MERGED（`6a3d09f5bf29ec25c768c6295e2c13adb3ff9a6c`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | scoped 15 / contract 3 / integration 14 / full unit 300 / contract 65；ruff PASS；mypy PASS；OI-009 resolved | STM-005 READY_FOR_PLANNING only；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 14:05 UTC | STM-007 | planned | 创建 Task Plan `02_开发管理/tasks/STM-007-compression-llm-client-structured-output.md`；master_plan CHANGE-043；progress 规划态回写 | baseline `dc74311`；§5.0 十六项 Contract 闭合；OI-004/OI-005 OUT OF SCOPE | `next_action=计划审查`；未实施、未 Git 写；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 22:40 UTC | STM-007 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `87dc9c4a442aff113ac220b9604010aa135f721e`；PR #26 OPEN；docs(status): record on feat | scoped 29 / full unit 369 / contract 76；ruff PASS；mypy PASS | 仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 14:45 UTC | STM-007 | committed → completed | PR #26 MERGED（`7a72b3a4c159032a411bd48dc920e52973ddab3e` mergedAt `2026-08-10T14:45:58Z`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | scoped unit 20 / contract 4 / integration(fake) 5 / total 29；full unit 369 / contract 76；ruff PASS；mypy PASS；real integration SKIPPED；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 | STM-008 READY_FOR_PLANNING only；STM-011 READY_FOR_PLANNING only；STM-009 NOT ready（needs STM-008）；OI-004/OI-005 remain open；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 13:40 UTC | STM-006 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `683caab306e082d58f577977ba3ecee5c550aa6e`；PR #25 OPEN；docs(status): record on feat | scoped unit 26 / contract 4 / redis int 16 / kafka int 4；full unit 349 / contract 72；ruff PASS；mypy PASS | 仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 12:35 UTC | STM-006 | planned → approved | Human PLAN_APPROVED Amendment 001；Round 2 BLOCKER=0 MUST_FIX=0；治理回写 Task Plan / progress / master_plan | 未运行（治理） | **next_action=PLAN_LANDING**；仍不得业务实施；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 12:40 UTC | STM-006 | planned（Round 2 Plan Review） | Plan Reviewer `PLAN_APPROVED`；BLOCKER=0 MUST_FIX=0；SHOULD_FIX=1（幂等 count/tokens 非阻塞） | MF-1 已闭合；未实施、未 Git 写 | **等待人工确认 PLAN_APPROVED**；其后才可 PLAN_LANDING；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 12:30 UTC | STM-006 | planned（Amendment 001 / Round 2） | Round 1 `PLAN_REJECTED` MF-1；用户选定方案 A；修订 Task Plan：`PREHELD_TOKEN_MUST_BE_ATOMICALLY_VERIFIED` + SF-1–5；progress/master_plan 同步 | 未运行（规划-only） | `next_action=计划审查`（Round 2）；**不得实施**；**不得 PLAN_LANDING**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 12:14 UTC | STM-006 | planned | 创建 Task Plan `02_开发管理/tasks/STM-006-compression-lock-pending-archive-kafka.md`；master_plan CHANGE-038；progress 规划态回写 | 未运行（规划-only） | OI-004 open acknowledged；OI-005 进程内决议；Kafka at-least-once；`next_action=计划审查`；**不得实施**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 12:00 UTC | DEV-OPS-007 | committed → completed | PR #24 MERGED（`de95f3a2f0107f791f89441177841754b1d4f82c`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | ruff PASS；mypy PASS；orphan exit 1 / authoritative exit 0；ZERO_STALE_AUTHORITATIVE_REFERENCES PASS | STM-006 READY_FOR_PLANNING only；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 11:42 UTC | DEV-OPS-007 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `1ef8932b87604de9a01dab72e7584a4e7886b155`；PR #24 OPEN；docs(status): record on feat | 仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；**不得实现 STM-006** |
| 2026-08-10 10:30 UTC | DEV-OPS-007 | approved → in_progress → tested | Developer：orphan SHA metadata 更正（`b0736431…`）；Ruff E501 L174–175 换行 | integration 14 / unit 323 / contract 68；ruff PASS；mypy PASS；orphan exit 1 / authoritative exit 0 | 未 commit；`next_action=Code Review`；**不得实现 STM-006**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 10:14 UTC | DEV-OPS-007 | planned | 创建 Task Plan `02_开发管理/tasks/DEV-OPS-007-phase1-baseline-hygiene-before-stm006.md`；master_plan CHANGE-037；progress 规划态回写 | 只读确认：orphan `301c8d9…` exit 1 / `b0736431…` exit 0；Ruff E501 L174–175 | `next_action=计划审查`；**不得实现 STM-006**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 09:16 UTC | STM-005 | committed → completed | PR #23 MERGED（`164dc1a529fd265cb82f3a78cadbb8bc65b2dfbf`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | scoped unit 26 / contract 3 / integration 12 / full unit 323 / contract 68；mypy PASS；ruff baseline E501 pre-existing（非回归）；OI-004 partial evidence status remains open | STM-006 READY_FOR_PLANNING only；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 07:55 UTC | STM-004 | committed | IMPLEMENTATION_RELEASE；implementation `3aed60522db64c3b11597e025caa0aae00afaba6`；PR #22 OPEN | scoped 15 / contract 3 / integration 14 / full unit 300 / contract 65；ruff PASS；mypy PASS | 待人工 merge；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 07:38 UTC | STM-004 | approved → in_progress → tested | Developer：只读 context read Lua + `read_working_memory_context`；I12 三段式 torn-read；13 Integration 场景 | scoped 15 / contract 3 / integration 14 / full unit 300 / contract 65；ruff PASS；mypy PASS | 未 commit；`next_action=Code Review`；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 07:18 UTC | STM-004 | planned（Amendment 002） | Round 2 `PLAN_REJECTED` MF-2（非原子 mutator）；Amendment 002：三段式 I12 torn-read（原子 mutator + broken reader 负对照 + 生产 Lua 正对照）；I10 compressed_context 缺失；__init__.py 白名单；ContextReadFailure→STM-009 | 未实施、未 Git 写；`next_action=计划审查 Round 3`；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 07:10 UTC | STM-004 | planned（Amendment 001） | Round 1 `PLAN_REJECTED` MF-1（I11 空洞）；Amendment 001：对抗性 torn-read + `NO_STALE_SUMMARY_TRIMMED_LIST_HYBRID`；正式前置 STM-002 vs 实现复用 STM-001/003；`ContextReadFailure`；空 messages 3 元素 Lua | 未实施、未 Git 写；`next_action=计划审查 Round 2`；**不得触碰 DEV-006/PR#13** |

## DEV-OPS-003 Git 流程（正式任务；已完成；STRICT）

```text
1. 独立 Plan Review Round 1 → PLAN_REJECTED（MF-001）
2. Planner Amendment 001
3. 独立 Plan Review Round 2 → PLAN_APPROVED
4. 人工确认 PLAN_APPROVED → approved（2026-08-07 15:39 UTC）
5. 人工在 main 提交 docs(plan)（d45ea2f）并 push
6. 从 main 创建 feat/DEV-OPS-003-normal-strict-workflow-modes
7. Developer 实施 → tested
8. Code Review → reviewed（P2 CLOSED）
9. Commit Recorder → READY_FOR_HUMAN_COMMIT
10. 显式 RELEASE_APPROVED → IMPLEMENTATION_RELEASE（640616b；PR #7；record ec47b2a）
11. 人工 Merge PR #7 → main（1189447）
12. Step 7 = DEV-OPS-003-SMOKE NORMAL smoke → PASSED（PR #8 / e14d71e / POST_MERGE 45c74f8）
13. 正式 completed 治理准备（本轮）→ 待人工 docs(status): complete DEV-OPS-003 after PR merge and smoke
14. 正式 feat 删除 ← 仍待人工；next_action=DEV-004 规划
```

## DEV-OPS-003-SMOKE Git 流程（已完成；NORMAL / default；两人工门验证）

```text
1. 人工 PLAN_APPROVED（门禁 #1）
2. 自动 PLAN_LANDING → Developer → Code Review → Commit Recorder → IMPLEMENTATION_RELEASE → PR #8
   （无中间人工 Git/Release 批准门）
3. WAITING_FOR_PR_MERGE → 人工 Merge PR #8（门禁 #2）
4. 自动 POST_MERGE_CLEANUP（无再一次批准）→ smoke completed；删 smoke feat；恢复 current_task=DEV-OPS-003
```

## 下一任务

1. **STM-008**：`READY_FOR_PLANNING only` — prerequisites STM-006+STM-007 **SATISFIED**；Compression Finalize Lua；`next_action=等待用户显式启动规划`；**不得自动开始**；**不得触碰 DEV-006/PR#13**。
2. **STM-011**：`READY_FOR_PLANNING only` — prerequisite STM-006 **SATISFIED**；`republish_archive_event.py`；**不得自动开始**。
3. **STM-009**：NOT ready — needs STM-008 completed；Compression Coordinator + HTTP 接线。
4. **STM-007**：`completed`（PR #26 MERGED `7a72b3a4c159032a411bd48dc920e52973ddab3e` mergedAt `2026-08-10T14:45:58Z`；implementation `87dc9c4a442aff113ac220b9604010aa135f721e`；record `357893a75fe6c95950c6e55d17ef4354194dfc20`；scoped unit **20** / contract **4** / integration(fake) **5** / total **29**；full unit **369** / contract **76**；ruff **PASS**；mypy **PASS**；real integration **SKIPPED**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1；OI-004/OI-005 remain open；feat 分支待删）。
5. **STM-006**：`completed`（PR #25 MERGED `d704bc5421d346d46a48cb69a3a7ad956e94dbb8`；implementation `683caab306e082d58f577977ba3ecee5c550aa6e`）。
6. **DEV-006**：`PAUSED / SUPERSEDED_FOR_MVP`；PR #13 **DO_NOT_MERGE**；不得触碰。
