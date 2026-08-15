# Memory System MVP Progress

## 当前状态

```yaml
project: Memory System MVP
spec_version: 9
current_phase: Phase 5 follow-up — DEV-010 completed
phase0_baseline: GREEN
phase0_readiness: PASS
phase0_secret_readiness: PASS
stm_001_entry_gate: GO
stm_001_secret_gate: GO
current_task: DEV-010
current_task_status: completed
current_branch: main
formal_DEV-003-002_status: completed
formal_OI-011_status: completed
formal_OI-012_status: completed
tooling_status: VALID
runtime_contract_status: PASS
dev006_dependency_status: SUPERSEDED_FOR_MVP
target_default_branch: main
current_plan_file: 02_开发管理/tasks/DEV-010-siliconflow-embedding-token-estimation-routing.md
planning_baseline_main: "fc3fbd0fdc410aef2e21e6e3932cc6b9f7560a8a"
workflow_mode_for_this_task: NORMAL
workflow_mode_source: explicit
formal_DEV-010_plan_file: 02_开发管理/tasks/DEV-010-siliconflow-embedding-token-estimation-routing.md
formal_DEV-010_status: completed
formal_DEV-010_workflow_mode: NORMAL
formal_DEV-010_workflow_mode_source: explicit
formal_DEV-010_baseline: "fc3fbd0fdc410aef2e21e6e3932cc6b9f7560a8a"
formal_DEV-010_branch: "feat/DEV-010-siliconflow-embedding-token-estimation-routing"
formal_DEV-010_prerequisite: "SATISFIED — REL-001 completed (PR #60 MERGED); DEV-007/STM-001/OI-012/EXT-006/007/RET-005 completed; DEV-006 PAUSED / PR #13 DO_NOT_MERGE"
formal_DEV-010_scope: "provider-aware tokenize count-source routing (siliconflow=STM-001 estimate_tokens heuristic; local_tei=TeiTokenizeClient); minimal spec delta; NOT new tokenizer; NOT extraction schema; NOT OI-012 exact 1024 expansion; NOT TEIEmbeddingClient"
formal_DEV-010_insertion_reason: NEW_UNPLANNED_FEATURE
formal_DEV-010_changes_technical_spec: true
formal_DEV-010_blocking_open_issues: []
formal_DEV-010_nonblocking_open_issues:
  - "OI-DEV010-ITEM9 — spec tokenize mandate is §2.1.13 prep item 9 (brief said #4)"
  - "OI-DEV010-TEI-CHAPTERS — leftover TEIEmbeddingClient /tokenize sentences in §2.2.6/§3.2/§3.10 not rewritten"
  - "OI-DEV010-HEURISTIC-GAP — estimate_tokens vs BGE-M3 tokenizer at 1024 boundary accepted"
  - "OI-DEV010-LOCAL-TEI-SPLIT — local_tei tokenize still TeiTokenizeClient; embedding factory still NotImplementedError"
formal_DEV-010_dependency_changes_expected: NONE
formal_DEV-010_migration_changes_expected: NONE
formal_DEV-010_settings_fields_expected: NONE
formal_DEV-010_production_file_whitelist: "src/memory_system/infrastructure/tokenize/__init__.py; src/memory_system/infrastructure/tokenize/factory.py; src/memory_system/infrastructure/tokenize/heuristic_token_count_adapter.py; src/memory_system/domain/ports/tokenize_client.py; src/memory_system/domain/services/production_extraction_pipeline.py; src/memory_system/domain/services/retrieval_api_service.py"
formal_DEV-010_test_file_whitelist: "tests/unit/test_heuristic_token_count_adapter.py; tests/unit/test_tokenize_client_factory.py; tests/contract/test_dev010_tokenize_provider_routing.py; tests/e2e/helpers/e2e001_helpers.py"
formal_DEV-010_spec_file_whitelist: "01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md"
formal_DEV-010_human_plan_approved: true
formal_DEV-010_human_plan_approved_at: "2026-08-15 08:03 UTC"
formal_DEV-010_developer_authorized: true
formal_DEV-010_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_DEV-010_plan_review_round: 1
formal_DEV-010_plan_review: "Round 1 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=2 (implementation Step 0; no Amendment this phase)"
formal_DEV-010_plan_commit: "a55f99167863f508ef09033e13134348ab5e8b60"
formal_DEV-010_code_review: CODE_REVIEW_APPROVED
formal_DEV-010_code_review_session: "93de8d64-bcaf-478c-8c57-f0c77c8e8670"
formal_DEV-010_p0: 0
formal_DEV-010_p1: 0
formal_DEV-010_p2: 0
formal_DEV-010_p3: 2
formal_DEV-010_commit_recorder_session: "44cb5320-381f-4ebe-95ac-b46b9f74c9ab"
formal_DEV-010_implementation_commit: "7bf341ee7cd988d5a1f728ad138c38bbc4f31932"
formal_DEV-010_implementation_commit_message: "feat(tokenize): route siliconflow token counts through estimate_tokens"
formal_DEV-010_pr: "#61"
formal_DEV-010_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/61"
formal_DEV-010_pr_state: MERGED
formal_DEV-010_pr_base: main
formal_DEV-010_pr_head: "feat/DEV-010-siliconflow-embedding-token-estimation-routing"
formal_DEV-010_merge_commit: 29e4a3d7d747d2ec80d4a345da55e70f11076cf1
formal_DEV-010_merged_at: "2026-08-15T08:41:28Z"
formal_DEV-010_status_record_committed: 83f3443aff413b458c900c3f59ee4a63384676bc
formal_DEV-010_next_action: "DEV-010 completed — NO AUTO-START (no subsequent Task unless human starts one)"
formal_DEV-010_release_gate: COMPLETED
formal_DEV-010_note: "POST_MERGE_CLEANUP completed；plan a55f99167863f508ef09033e13134348ab5e8b60；implementation 7bf341ee7cd988d5a1f728ad138c38bbc4f31932；record 83f3443aff413b458c900c3f59ee4a63384676bc；PR #61 MERGED（base=main，head=feat/DEV-010-siliconflow-embedding-token-estimation-routing，merge 29e4a3d7d747d2ec80d4a345da55e70f11076cf1，mergedAt=2026-08-15T08:41:28Z）；CODE_REVIEW_APPROVED P0=0 P1=0 P3=2；unit+contract 18 passed；ruff PASS；mypy src 0；feat 分支本地/远程已删除；next_action=DEV-010 completed — NO AUTO-START；未 git tag；REL-001 completed 事实不变；不得触碰 DEV-006/PR#13；不得创建 OI-013"
formal_REL-001_plan_file: 02_开发管理/tasks/REL-001-mvp-rc-review-acceptance-checklist.md
formal_REL-001_status: completed
formal_REL-001_workflow_mode: NORMAL
formal_REL-001_workflow_mode_source: explicit
formal_REL-001_baseline: "412fb7b858120927aecad63962990587038df340"
formal_REL-001_branch: "feat/REL-001-mvp-rc-review-acceptance-checklist"
formal_REL-001_prerequisite: "SATISFIED — E2E-001 completed (PR #59 MERGED); OPS-001..004 completed; STM/EXT/RET/CON all completed"
formal_REL-001_scope: "MVP RC Review + mvp_acceptance_checklist.md A–F evidence mapping; production_file_whitelist=NONE; test_file_whitelist=NONE; checklist checkoff only after evidence; v0.9.0-mvp-rc1 and v1.0.0-mvp HALT/human tags (not RO); NOT retest vertical slices; NOT Contract changes"
formal_REL-001_blocking_open_issues: []
formal_REL-001_nonblocking_open_issues:
  - "OI-REL1-TAG — git tag outside Release Operator command set; human annotated tags only"
  - "OI-REL1-TEI — test_matrix real TEI vs spec optional local BGE-M3; not CPU MVP blocking"
formal_REL-001_dependency_changes_expected: NONE
formal_REL-001_migration_changes_expected: NONE
formal_REL-001_production_file_whitelist: NONE
formal_REL-001_test_file_whitelist: NONE
formal_REL-001_acceptance_artifact_whitelist: "05_测试与验收/mvp_acceptance_checklist.md (checkoff only after evidence; planning round must not check boxes)"
formal_REL-001_human_plan_approved: true
formal_REL-001_human_plan_approved_at: "2026-08-15 04:25 UTC"
formal_REL-001_developer_authorized: true
formal_REL-001_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_REL-001_plan_review_round: 1
formal_REL-001_plan_review: "Round 1 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=5 (implementation Step 0; no Amendment this phase)"
formal_REL-001_plan_commit: "04c4a7e8f6a49d0092d175b40a98513eadc47e0a"
formal_REL-001_code_review: CODE_REVIEW_APPROVED
formal_REL-001_p0: 0
formal_REL-001_p1: 0
formal_REL-001_p2: 0
formal_REL-001_p3: 1
formal_REL-001_implementation_commit: "703bb105fa18cc0814bd750843295c7044c6d4b9"
formal_REL-001_implementation_commit_message: "docs(rel): record MVP RC evidence and acceptance checklist"
formal_REL-001_pr: "#60"
formal_REL-001_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/60"
formal_REL-001_pr_state: MERGED
formal_REL-001_pr_base: main
formal_REL-001_pr_head: "feat/REL-001-mvp-rc-review-acceptance-checklist"
formal_REL-001_pr_head_sha: "725c89b237eca07220059b058561fa8afa91894a"
formal_REL-001_merge_commit: 4e8ceff74b95880b1c035d518bf2be43d2bbc907
formal_REL-001_merged_at: "2026-08-15T06:01:06Z"
formal_REL-001_status_record_committed: 725c89b237eca07220059b058561fa8afa91894a
formal_REL-001_next_action: "REL-001 completed — NO AUTO-START (Phase 5 has no subsequent Task); HUMAN: annotated tag v0.9.0-mvp-rc1 only (suggested object 412fb7b858120927aecad63962990587038df340); DO NOT create v1.0.0-mvp (A.1 Preflight still unchecked)"
formal_REL-001_release_gate: COMPLETED
formal_REL-001_note: "POST_MERGE_CLEANUP completed；plan 04c4a7e8f6a49d0092d175b40a98513eadc47e0a；implementation 703bb105fa18cc0814bd750843295c7044c6d4b9；PR head/record 725c89b237eca07220059b058561fa8afa91894a；PR #60 MERGED（base=main，head=feat/REL-001-mvp-rc-review-acceptance-checklist，merge 4e8ceff74b95880b1c035d518bf2be43d2bbc907，mergedAt=2026-08-15T06:01:06Z）；CODE_REVIEW_APPROVED P0=0/P1=0 P3=1；A.1 still unchecked (preflight exit 1 vm.max_map_count)；F.Git干净 checklist box unchanged (POST_MERGE 不 add 清单；POST_MERGE 后工作树干净)；not all-green so 不得 v1.0.0-mvp；no git tag；feat 分支本地/远程已删除；next_action=本任务完成 / NOT AUTO-STARTED（Phase 5 无后续 Task）；HUMAN v0.9.0-mvp-rc1 仅人工 tag（建议对象 412fb7b858120927aecad63962990587038df340）；不得触碰 DEV-006/PR#13"
formal_E2E-001_plan_file: 02_开发管理/tasks/E2E-001-full-chain-e2e-failure-injection.md
formal_E2E-001_status: completed
formal_E2E-001_workflow_mode: NORMAL
formal_E2E-001_workflow_mode_source: explicit
formal_E2E-001_baseline: "bb0d387f509c38194cf511f580b98cf86f44b5a7"
formal_E2E-001_branch: "feat/E2E-001-full-chain-e2e-failure-injection"
formal_E2E-001_prerequisite: "SATISFIED — OPS-003 completed (PR #57 MERGED); OPS-004 completed (PR #58 MERGED); OPS-001/002 completed; STM/EXT/RET/CON all completed"
formal_E2E-001_scope: "§3.28/§3.32 #4 full-chain E2E compose of STM-013+EXT-009+RET-006+CON-005 slices; §3.28 five failure injections; §3.32 #5 idempotency; #6 recovery; #7 CPU Fake embedding; #8 HTTP/isolation subset; production_file_whitelist=NONE; NOT OPS-004 CI expansion; NOT REL-001"
formal_E2E-001_blocking_open_issues: []
formal_E2E-001_nonblocking_open_issues:
  - "OI-E2E1-VOL — e2e conftest down missing -v; Amendment 001: -v on infra_stack start AND end; --stack=test / memory-system-test only"
  - "OI-E2E1-SIGTERM — worker container defaults to real LLM; leftover events on shared stack can hit DeepSeek; Amendment 001: lag=0 idle + docker stop not-running + no LLM HTTP; in-process F1 = INJ-4"
formal_E2E-001_dependency_changes_expected: NONE
formal_E2E-001_migration_changes_expected: NONE
formal_E2E-001_production_file_whitelist: NONE
formal_E2E-001_test_file_whitelist: "tests/e2e/helpers/e2e001_helpers.py; tests/support/e2e001_failure_doubles.py; tests/e2e/test_e2e001_full_chain.py; tests/e2e/test_e2e001_idempotency.py; tests/e2e/test_e2e001_failure_injection.py; tests/e2e/conftest.py; tests/contract/test_e2e001_scope_boundaries.py"
formal_E2E-001_human_plan_approved: true
formal_E2E-001_human_plan_approved_at: "2026-08-15 02:38 UTC"
formal_E2E-001_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_E2E-001_plan_review_round: 2
formal_E2E-001_plan_review: "Round 2 PLAN_APPROVED (session 20220a4e-dd78-4a44-b130-9eeec0b11d74; BLOCKER=0 MUST_FIX=0); Amendment 001 absorbed; Round 1 PLAN_REJECTED (session 570cb388) retained as history"
formal_E2E-001_amendment: "001 — MF-1 INJ-1 §1.2.6 #10/I-I Mongo Archive not WM; MF-2 HP compression succeeded + compressed_context; MF-3 INJ-5 two-step close §1.2.3 #11; SF-1 production ES wrap; SF-2 INJ-4 F1 second run_worker_once; SF-3 SIGTERM lag=0; SF-4 -v both downs; SF-5 PLAN_LANDING before Developer; SF-6 whitelist §12; SF-8 mypy src only"
formal_E2E-001_developer_authorized: true
formal_E2E-001_plan_commit: "c2afaaa576107329ca6153a846fcb071c9383445"
formal_E2E-001_implementation_commit: "4a44e99009e04bcbce5717df0a3073fffff9faf0"
formal_E2E-001_implementation_commit_message: "test(e2e): add full-chain e2e and failure injection suite"
formal_E2E-001_code_review: CODE_REVIEW_APPROVED
formal_E2E-001_p0: 0
formal_E2E-001_p1: 0
formal_E2E-001_pr: "#59"
formal_E2E-001_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/59"
formal_E2E-001_pr_state: MERGED
formal_E2E-001_pr_base: main
formal_E2E-001_pr_head: "feat/E2E-001-full-chain-e2e-failure-injection"
formal_E2E-001_pr_head_sha: "526c8403cff8b05d05ca73b1d513aeb30e7dea76"
formal_E2E-001_merge_commit: 43b6975a5dc4a92cde2f898acacd73a508831a48
formal_E2E-001_merged_at: "2026-08-15T03:53:42Z"
formal_E2E-001_status_record_committed: 526c8403cff8b05d05ca73b1d513aeb30e7dea76
formal_E2E-001_next_action: "REL-001 planned / NOT AUTO-STARTED"
formal_E2E-001_release_gate: COMPLETED
formal_E2E-001_note: "POST_MERGE_CLEANUP completed；plan c2afaaa576107329ca6153a846fcb071c9383445；implementation 4a44e99009e04bcbce5717df0a3073fffff9faf0；PR head 526c8403cff8b05d05ca73b1d513aeb30e7dea76；PR #59 MERGED（base=main，head=feat/E2E-001-full-chain-e2e-failure-injection，merge 43b6975a5dc4a92cde2f898acacd73a508831a48，mergedAt=2026-08-15T03:53:42Z）；CODE_REVIEW_APPROVED P0=0/P1=0；E2E 11 passed / contract 3 passed / ruff PASS / mypy src 0；zero src/**；feat 分支本地/远程已删除；next_action=REL-001 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13；不得自动启动 REL-001"
formal_OPS-004_plan_file: 02_开发管理/tasks/OPS-004-ci-gates-coverage-threshold.md
formal_OPS-004_status: completed
formal_OPS-004_workflow_mode: NORMAL
formal_OPS-004_workflow_mode_source: explicit
formal_OPS-004_baseline: "85c1470417c27c4d2c688f22db7a36775b0aef79"
formal_OPS-004_branch: "feat/OPS-004-ci-gates-coverage-threshold"
formal_OPS-004_prerequisite: "SATISFIED — OPS-003 completed (PR #57 MERGED); OPS-001/002 completed; DEV-003-002 runtime_contract_gate layering; CON/STM/EXT/RET all completed"
formal_OPS-004_scope: "§3.28 Unit+Contract+Integration CI gates + §3.30 P1 check_env_example.py CI + 80% domain/application coverage threshold; GitHub Actions workflow(s); task_scope_boundary marker layering (NOT E2E-001/REL-001)"
formal_OPS-004_blocking_open_issues: []
formal_OPS-004_nonblocking_open_issues:
  - "BL-MYPY-001 — tests/scripts mypy 207 errors DEFERRED (optional follow-up; not CI-blocking)"
formal_OPS-004_dependency_changes_expected: NONE
formal_OPS-004_migration_changes_expected: NONE
formal_OPS-004_production_file_whitelist: ".github/workflows/ci.yml; scripts/ci/run_merge_gate.sh; pyproject.toml; README.md"
formal_OPS-004_test_file_whitelist: "tests/contract/test_ops004_ci_workflow_contract.py; tests/contract/test_con001..005_scope_boundaries.py; tests/contract/test_ext009_extraction_pipeline_contract.py; tests/unit/test_extraction_llm_service.py; tests/unit/test_extraction_task_consumer_service.py; tests/integration/test_ret005_retrieval_http.py; tests/unit/test_consolidation_run_service.py; tests/unit/test_consolidation_scheduler.py; tests/unit/test_ops002_logging_context.py; tests/unit/test_ops002_metrics_wiring.py; tests/unit/test_ops002_sensitive_log_guards.py; tests/unit/test_retrieval_api_service.py; tests/unit/test_retrieval_response_mapper.py"
formal_OPS-004_scoped_tests: "CI GREEN run 31857428972 — unit-contract 1399 passed, 1 skipped, 33 deselected, 91.26% coverage; integration 246 passed, 4 skipped, 4 deselected (opt-in/host skips; STRICT_SKIPS did not fail); static PASS"
formal_OPS-004_baseline_audit: "BL-001..002 task_scope_boundary marker; BL-003/004 test mock fixed; BL-005 integration PASS (Docker available)"
formal_OPS-004_ruff: "PASS — uv run ruff check src tests scripts (BL-RUFF-001 8-file auto-fix Amendment 002)"
formal_OPS-004_mypy: "PASS — uv run mypy src = 0 errors (CI gate); BL-MYPY-001 DEFERRED — tests/scripts 207 errors optional follow-up"
formal_OPS-004_merge_gate: "static PASS; unit-contract 1399 passed / 1 skipped / 91.26% cov; integration 246 passed / 4 skipped / 4 deselected; CI https://github.com/xu-jia-ming/memory_system/actions/runs/31857428972"
formal_OPS-004_note: "POST_MERGE_CLEANUP completed；plan 4d5d5199f071d4205d7ce7c4aa3d67efe9ef5436；implementation 599650108a3441f92e9fd586a9ae7ac020c81548；PR head 780359a6bc34253aa62b3266ba990e2b1d3edb23；PR #58 MERGED（base=main，head=feat/OPS-004-ci-gates-coverage-threshold，merge 3e6f8fa2b7c1bf36a332e28f027fe79445bcf1ec，mergedAt=2026-08-15T01:56:08Z）；CI green 1399 unit+contract / 246 integration run 31857428972；CODE_REVIEW_APPROVED P0=0/P1=0；feat 分支本地/远程已删除；next_action=E2E-001 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13；不得自动启动 E2E-001"
formal_OPS-004_amendment: "002 — mypy CI scope narrowed to `uv run mypy src`; BL-RUFF-001 ruff auto-fix 8 whitelist files (18 errors); BL-MYPY-001 tests/scripts mypy debt DEFERRED; C-OPS4-01/§5.2/§5.6/§10/§11 aligned"
formal_OPS-004_plan_review_round: 2
formal_OPS-004_plan_review: PLAN_APPROVED
formal_OPS-004_human_plan_approved: true
formal_OPS-004_human_plan_approved_at: "2026-08-14 06:06 UTC"
formal_OPS-004_plan_commit: "4d5d5199f071d4205d7ce7c4aa3d67efe9ef5436"
formal_OPS-004_plan_landing_completed_at: "2026-08-14 06:06 UTC"
formal_OPS-004_implementation_commit: "599650108a3441f92e9fd586a9ae7ac020c81548"
formal_OPS-004_implementation_commit_message: "ci(ops): add GitHub Actions merge-gate and coverage threshold"
formal_OPS-004_code_review: CODE_REVIEW_APPROVED
formal_OPS-004_p0: 0
formal_OPS-004_p1: 0
formal_OPS-004_pr: "#58"
formal_OPS-004_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/58"
formal_OPS-004_pr_state: MERGED
formal_OPS-004_pr_base: main
formal_OPS-004_pr_head: "feat/OPS-004-ci-gates-coverage-threshold"
formal_OPS-004_pr_head_sha: "780359a6bc34253aa62b3266ba990e2b1d3edb23"
formal_OPS-004_merge_commit: 3e6f8fa2b7c1bf36a332e28f027fe79445bcf1ec
formal_OPS-004_merged_at: "2026-08-15T01:56:08Z"
formal_OPS-004_next_action: "E2E-001 planned / NOT AUTO-STARTED"
formal_OPS-004_release_gate: COMPLETED
formal_OPS-004_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_OPS-003_plan_file: 02_开发管理/tasks/OPS-003-full-migration-compose-blank-environment-validation.md
formal_OPS-003_status: completed
formal_OPS-003_workflow_mode: NORMAL
formal_OPS-003_workflow_mode_source: explicit
formal_OPS-003_baseline: "93ffefdcbba8fc74a45842b956185bee8d0f2004"
formal_OPS-003_branch: "feat/OPS-003-full-migration-compose-blank-environment-validation"
formal_OPS-003_prerequisite: "SATISFIED — OPS-001 completed (PR #55 MERGED); OPS-002 completed (PR #56 MERGED); DEV-003/004/005 completed; DEV-OPS-008 completed; CON-001..005 completed; v0.5.0-consolidation closed; STM/EXT/RET all completed"
formal_OPS-003_scope: "§3.12/§3.26 full migration runner audit + §3.17/§3.3 compose blank-environment validation + §3.32 #1/#2/#9 engineering consistency; focused contract/integration tests (NOT E2E-001/OPS-004 CI 80%)"
formal_OPS-003_blocking_open_issues: []
formal_OPS-003_nonblocking_open_issues: []
formal_OPS-003_dependency_changes_expected: NONE
formal_OPS-003_migration_changes_expected: NONE
formal_OPS-003_production_file_whitelist: "NONE (Phase A audit clean — no production remediations)"
formal_OPS-003_test_file_whitelist: "tests/contract/test_ops003_migration_compose_inventory.py; tests/integration/test_ops003_blank_environment_bootstrap.py; tests/integration/test_api_readiness.py"
formal_OPS-003_audit_summary: "17 findings — 8 COMPLIANT; 3 HARD_BLOCK REMEDIATED (I-OPS3-01/02 + INJ-OPS3-01); 1 SAFE_AUTO REMEDIATED (BLANK-ENV-001 none); 4 DEFERRED"
formal_OPS-003_note: "POST_MERGE_CLEANUP completed；implementation 978ae9ccaf80a87c772a6691a7f1b66db2b3c846；record 815da73b4207c4972d19a7de59b9c3ff4c28c902；complete 13bd4f2d7b72046439846d48848a5fed4bba2be5；PR #57 MERGED（base=main，head=feat/OPS-003-full-migration-compose-blank-environment-validation，merge 89912ec53d802dc527a32e3c132737c01197897f，mergedAt=2026-08-14T04:31:53Z）；CODE_REVIEW_APPROVED P0=0/P1=0；BLANK-ENV-001 locked --embedding=none；production NONE；scoped 53 pass / 1 skip；ruff/mypy PASS；feat 分支本地/远程已删除；next_action=OPS-004 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_OPS-003_plan_review: PLAN_APPROVED
formal_OPS-003_plan_review_round: 2
formal_OPS-003_plan_review_blocker: 0
formal_OPS-003_plan_review_must_fix: 0
formal_OPS-003_plan_review_should_fix: 0
formal_OPS-003_human_plan_approved: true
formal_OPS-003_human_plan_approved_at: "2026-08-14 03:57 UTC"
formal_OPS-003_amendment: "001 — §19/§20 whitelist alignment; INJ-OPS3-01 Step 2b; INT-SKIP-001; embedding mode clarification"
formal_OPS-003_plan_commit: "6d007ea00dfd565b5e3ac0f193de4b18867ba336"
formal_OPS-003_plan_landing_completed_at: "2026-08-14 04:05 UTC"
formal_OPS-003_scoped_tests: "53 passed / 1 skipped (legacy readiness host:8000)"
formal_OPS-003_ruff: PASS
formal_OPS-003_mypy: PASS
formal_OPS-003_implementation_commit: "978ae9ccaf80a87c772a6691a7f1b66db2b3c846"
formal_OPS-003_implementation_commit_message: "test(ops): add OPS-003 blank environment bootstrap tests"
formal_OPS-003_record_commit: "815da73b4207c4972d19a7de59b9c3ff4c28c902"
formal_OPS-003_code_review: CODE_REVIEW_APPROVED
formal_OPS-003_p0: 0
formal_OPS-003_p1: 0
formal_OPS-003_p2: 0
formal_OPS-003_p3: 0
formal_OPS-003_pr: "#57"
formal_OPS-003_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/57"
formal_OPS-003_pr_state: MERGED
formal_OPS-003_pr_base: main
formal_OPS-003_pr_head: "feat/OPS-003-full-migration-compose-blank-environment-validation"
formal_OPS-003_merge_commit: 89912ec53d802dc527a32e3c132737c01197897f
formal_OPS-003_merged_at: "2026-08-14T04:31:53Z"
formal_OPS-003_status_record_committed: 815da73b4207c4972d19a7de59b9c3ff4c28c902
formal_OPS-003_status_record_completed: 13bd4f2
formal_OPS-003_release_gate: COMPLETED
formal_OPS-003_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_OPS-003_next_action: "OPS-004 planned / NOT AUTO-STARTED"
planning_baseline_EXT-009: "779963257e33a93ad02ef4e3f997b3c9f6706802"
formal_EXT-009_plan_file: 02_开发管理/tasks/EXT-009-extraction-e2e-pipeline-wiring.md
formal_EXT-009_status: completed
formal_EXT-009_workflow_mode: NORMAL
formal_EXT-009_workflow_mode_source: explicit
formal_EXT-009_baseline: 779963257e33a93ad02ef4e3f997b3c9f6706802
formal_EXT-009_branch: "feat/EXT-009-extraction-e2e-pipeline-wiring"
formal_EXT-009_prerequisite: "SATISFIED — EXT-008 completed (PR #42 MERGED); EXT-007 completed; EXT-001..006 completed; DEV-005 completed; STM-011 republish"
formal_EXT-009_scope: "§2.1.13 production pipeline wiring (closure of EXT-003→007 DEFERRED_FOR_MVP); ProductionExtractionPipeline; extraction_worker.main(); consumer LD-1 terminal reload; E2E-1..4 compose.test + Fake LLM/embedding/tokenize; zero EXT-002..007 service semantics diff"
formal_EXT-009_blocking_open_issues: []
formal_EXT-009_nonblocking_open_issues: []
formal_EXT-009_dependency_changes_expected: NONE
formal_EXT-009_migration_changes_expected: NONE
formal_EXT-009_pipeline_handoff: "ProductionExtractionPipeline + worker consumer loop; EXT-003→007 continuation CLOSED; consumer narrow LD-1 terminal idempotency"
formal_EXT-009_note: "POST_MERGE_CLEANUP；implementation d6a4bf596b78275ce3e8644a79e2dc8d218675d4；record ddfb89ca8e466e0802d9e98177295a9effb41725；PR #43 MERGED（base=main，head=feat/EXT-009-extraction-e2e-pipeline-wiring，merge c05691144b650b22be714736de3c200076c340c3，mergedAt=2026-08-13T01:11:57Z）；SAFE_AUTO_REMEDIATION：fetch 后 origin/main 领先本地 main，已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=0；ProductionExtractionPipeline 闭合 EXT-003→007 continuation；terminal Mongo 持久化先于 Kafka Offset；extraction_result replay 跳过 LLM，Retrieval ES upsert 收敛且无重复 Memory/Evidence/ES 文档；EXT-002..007 阶段语义零 diff；feat 分支本地/远程已删除；next_action=RET-001 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_EXT-009_scoped_tests: "33 passed; E2E 4 passed"
formal_EXT-009_ruff: PASS
formal_EXT-009_mypy: "PASS（remediation files；full-repository baseline 143 errors）"
formal_EXT-009_code_review: CODE_REVIEW_APPROVED
formal_EXT-009_p0: 0
formal_EXT-009_p1: 0
formal_EXT-009_p2: 0
formal_EXT-009_implementation_commit: d6a4bf596b78275ce3e8644a79e2dc8d218675d4
formal_EXT-009_implementation_commit_message: "feat(ext): wire production extraction pipeline and worker"
formal_EXT-009_pr: "#43"
formal_EXT-009_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/43"
formal_EXT-009_pr_state: MERGED
formal_EXT-009_pr_base: main
formal_EXT-009_pr_head: "feat/EXT-009-extraction-e2e-pipeline-wiring"
formal_EXT-009_merge_commit: c05691144b650b22be714736de3c200076c340c3
formal_EXT-009_merged_at: "2026-08-13T01:11:57Z"
formal_EXT-009_status_record_committed: ddfb89ca8e466e0802d9e98177295a9effb41725
formal_EXT-009_release_gate: COMPLETED
formal_EXT-009_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_EXT-009_next_action: "RET-001 planned / NOT AUTO-STARTED"
formal_EXT-008_plan_file: 02_开发管理/tasks/EXT-008-extraction-admin-api.md
formal_EXT-008_status: completed
formal_EXT-008_workflow_mode: NORMAL
formal_EXT-008_workflow_mode_source: explicit
formal_EXT-008_baseline: d55bf53e715378463243fcf80e49277e603c1bb5
formal_EXT-008_branch: "feat/EXT-008-extraction-admin-api"
formal_EXT-008_prerequisite: "SATISFIED — EXT-007 completed (PR #41 MERGED); EXT-001 completed; DEV-005 completed; STM-011 republish service"
formal_EXT-008_scope: "§2.1.14 GET status + POST retry (Admin Key); OI-006 POST rebuild for reconciliation_plan_conflict; Mongo-only durable writes; STM-011 republish; zero offset; zero consumer/worker/pipeline diff"
formal_EXT-008_blocking_open_issues: []
formal_EXT-008_nonblocking_open_issues: []
formal_EXT-008_resolved_open_issues: [OI-006]
formal_EXT-008_dependency_changes_expected: NONE
formal_EXT-008_migration_changes_expected: NONE
formal_EXT-008_authorized_http_error_codes: "extraction_task_not_found, retry_not_allowed (+ DEV-005 cross-cutting invalid_api_key/forbidden/validation_error/internal_error)"
formal_EXT-008_pipeline_handoff: "HTTP + ExtractionAdminService + Mongo admin repo; worker/consumer unchanged; pipeline continuation DEFERRED_FOR_MVP"
formal_EXT-008_note: "POST_MERGE_CLEANUP；implementation e8f15b458a6f1fa6e204393d5300a018bfc5c27b；record eefb52edea62c1d1a917f2393ff157c64421a2b0；PR #42 MERGED merge 8bee66be25e140cd59a8dd74faa733211ab44382 mergedAt 2026-08-12T14:07:04Z；scoped 25 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=3 non-blocking；GET/retry/rebuild Admin HTTP；OI-006 resolved_by_task；LD-3 Mongo before Kafka；zero consumer/worker/pipeline diff；feat 分支已删；不得触碰 DEV-006/PR#13"
formal_EXT-008_scoped_tests: "25 passed"
formal_EXT-008_ruff: PASS
formal_EXT-008_mypy: PASS
formal_EXT-008_code_review: CODE_REVIEW_APPROVED
formal_EXT-008_p0: 0
formal_EXT-008_p1: 0
formal_EXT-008_p2: 1
formal_EXT-008_p3: 3
formal_EXT-008_implementation_commit: e8f15b458a6f1fa6e204393d5300a018bfc5c27b
formal_EXT-008_implementation_commit_message: "feat(ext): add extraction admin get retry rebuild api"
formal_EXT-008_pr: "#42"
formal_EXT-008_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/42"
formal_EXT-008_pr_state: MERGED
formal_EXT-008_merge_commit: 8bee66be25e140cd59a8dd74faa733211ab44382
formal_EXT-008_merged_at: "2026-08-12T14:07:04Z"
formal_EXT-008_status_record_committed: eefb52edea62c1d1a917f2393ff157c64421a2b0
formal_EXT-008_release_gate: COMPLETED
formal_EXT-008_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_EXT-008_next_action: "EXT-009 planned / NOT AUTO-STARTED"
next_action: "DEV-010 completed — NO AUTO-START (no subsequent Task unless human starts one)"
last_role_result: POST_MERGE_CLEANUP DEV-010 completed; PR #61 MERGED merge 29e4a3d7d747d2ec80d4a345da55e70f11076cf1; record 83f3443aff413b458c900c3f59ee4a63384676bc; feat deleted; NO AUTO-START
blocking_reason: null
formal_OPS-002_plan_file: 02_开发管理/tasks/OPS-002-logging-metrics-sensitive-user-isolation-audit.md
formal_OPS-002_status: completed
formal_OPS-002_workflow_mode: NORMAL
formal_OPS-002_workflow_mode_source: explicit
formal_OPS-002_baseline: "c7011aaac123915976389da8d8f18191269a0313"
formal_OPS-002_branch: "feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
formal_OPS-002_prerequisite: "SATISFIED — OPS-001 completed (PR #55 MERGED); CON-001..005 completed; v0.5.0-consolidation closed; STM/EXT/RET all completed; DEV-005 completed"
formal_OPS-002_scope: "§3.27 logging/metrics/sensitive info + §3.21 auth/user isolation MVP-wide audit; wire missing Prometheus business metrics; structlog JSON + task_run_id; focused tests (NOT E2E-001/OPS-004)"
formal_OPS-002_blocking_open_issues: []
formal_OPS-002_nonblocking_open_issues: []
formal_OPS-002_dependency_changes_expected: NONE
formal_OPS-002_migration_changes_expected: NONE
formal_OPS-002_production_file_whitelist: "api/app.py; observability/logging.py; request_context.py; consolidation_run_telemetry.py; metrics.py; compression_llm_service.py; extraction_llm_service.py; extraction_task_consumer_service.py; compression_coordinator_service.py; retrieval_api_service.py; production_extraction_pipeline.py; entrypoints extraction/consolidation_worker.py; error_handlers.py; archive_created_consumer.py; middleware.py conditional (F-007 only); Phase A may append F-006/F-015"
formal_OPS-002_test_file_whitelist: "tests/unit/test_ops002_logging_context.py; test_ops002_metrics_wiring.py; test_ops002_sensitive_log_guards.py; tests/contract/test_ops002_observability_contract.py; test_ops002_user_isolation_inventory.py"
formal_OPS-002_audit_summary: "20 preliminary findings — 6 COMPLIANT baseline; 6 HARD_BLOCK (service_name/task_run_id/F-006 7-file inventory/metrics wiring); 3 DEFERRED (F-006-D 4 stdlib modules + kafka_consumer_lag/OpenTelemetry); MET-AUDIT-001 解释 A locked (api scrape vs worker unit samples)"
formal_OPS-002_note: "Round 2 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=0; human PLAN_APPROVED 2026-08-14; Amendment 001 MF-1 api/app.py MF-2 F-006 scheme A; MET-AUDIT-001 interpretation A; baseline c7011aa; PLAN_LANDING pending;不得触碰 DEV-006/PR#13"
formal_OPS-002_amendment: "001 — api/app.py; F-006 7-file HARD_BLOCK inventory; MET-AUDIT-001 interpretation A; scoped test commands"
formal_OPS-002_plan_review: PLAN_APPROVED
formal_OPS-002_plan_review_round: 2
formal_OPS-002_plan_review_blocker: 0
formal_OPS-002_plan_review_must_fix: 0
formal_OPS-002_plan_review_should_fix: 0
formal_OPS-002_human_plan_approved: true
formal_OPS-002_human_plan_approved_at: "2026-08-14 02:51 UTC"
formal_OPS-002_next_action: "OPS-003 planned / NOT AUTO-STARTED"
formal_OPS-002_plan_commit: "f79f81537f55b4e28bc07b55a0aff1cd5864b72a"
formal_OPS-002_implementation_commit: "7ddcf9234bbc56e227db956b83ecc38c73d1aa90"
formal_OPS-002_implementation_commit_message: "fix(ops): OPS-002 logging metrics sensitive info user isolation audit"
formal_OPS-002_status_record_committed: f2e95ca97fb5472838859886bac8db85c8697735
formal_OPS-002_code_review: CODE_REVIEW_APPROVED
formal_OPS-002_p0: 0
formal_OPS-002_p1: 0
formal_OPS-002_p2: 0
formal_OPS-002_p3: 0
formal_OPS-002_scoped_tests: "OPS-002 unit 14 + contract 7 + DEV-005 12 + EXT-008 INT 7; ruff/mypy scoped PASS"
formal_OPS-002_pr: "#56"
formal_OPS-002_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/56"
formal_OPS-002_pr_state: MERGED
formal_OPS-002_pr_base: main
formal_OPS-002_pr_head: "feat/OPS-002-logging-metrics-sensitive-user-isolation-audit"
formal_OPS-002_merge_commit: fef784dbae4de421507eb9dbe5b7ac7f94588b0d
formal_OPS-002_merged_at: "2026-08-14T03:43:24Z"
formal_OPS-002_release_gate: COMPLETED
formal_OPS-002_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_OPS-002_note: "POST_MERGE_CLEANUP；implementation 7ddcf9234bbc56e227db956b83ecc38c73d1aa90；record f2e95ca97fb5472838859886bac8db85c8697735；PR #56 MERGED（base=main，head=feat/OPS-002-logging-metrics-sensitive-user-isolation-audit，merge fef784dbae4de421507eb9dbe5b7ac7f94588b0d，mergedAt=2026-08-14T03:43:24Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0；F-007 optional skipped；F-013 DEFERRED；scoped unit+contract+regression passed；ruff/mypy PASS；Amendment 001；feat 分支本地/远程已删除；next_action=OPS-003 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_OPS-001_plan_file: 02_开发管理/tasks/OPS-001-graceful-shutdown-pools-timeout-retry.md
formal_OPS-001_status: completed
formal_OPS-001_plan_commit: "1ce8b65feaf8569c971e93c1b33ef7a4e9cafb5d"
formal_OPS-001_workflow_mode: NORMAL
formal_OPS-001_workflow_mode_source: explicit
formal_OPS-001_baseline: "8fb64f10255add1a57404f6894cc374780d33413"
formal_OPS-001_branch: "feat/OPS-001-graceful-shutdown-pools-timeout-retry"
formal_OPS-001_prerequisite: "SATISFIED — CON-001..005 completed; v0.5.0-consolidation closed; STM/EXT/RET all completed"
formal_OPS-001_scope: "§3.24 pools/timeouts/retry + §3.25 graceful shutdown MVP-wide audit; Kafka extraction offset ordering; settings consistency; entrypoint lifecycle; focused failure tests (NOT E2E-001)"
formal_OPS-001_blocking_open_issues: []
formal_OPS-001_nonblocking_open_issues: []
formal_OPS-001_dependency_changes_expected: NONE
formal_OPS-001_migration_changes_expected: NONE
formal_OPS-001_production_file_whitelist: "src/memory_system/entrypoints/extraction_worker.py; src/memory_system/infrastructure/kafka/archive_created_consumer.py; src/memory_system/entrypoints/consolidation_worker.py (Amendment 001 shared 270s budget; else NONE)"
formal_OPS-001_test_file_whitelist: "tests/unit/test_ops001_extraction_worker_shutdown.py; tests/unit/test_ops001_consolidation_worker_shutdown.py; tests/unit/test_ops001_runtime_pools_timeouts.py; tests/unit/test_ops001_kafka_offset_shutdown.py"
formal_OPS-001_audit_summary: "21 findings — 17 COMPLIANT; 2 HARD_BLOCK (F-008/F-011 §3.25#8 shared 270s total budget in-flight+close); 2 DEFERRED (F-015/F-016)"
formal_OPS-001_note: "Amendment 001 @ planning; Round 1 PLAN_REJECTED revised — shared shutdown budget; archive_created_consumer.py in whitelist; current_run_task tracking + mutex defensive release; U10a/b/c; planning only @ main 8fb64f1;不得触碰 DEV-006/PR#13"
formal_OPS-001_amendment: "001 — shared 270s budget; consumer whitelist; F-011 run task tracking"
formal_OPS-001_plan_review: PLAN_APPROVED
formal_OPS-001_plan_review_round: 2
formal_OPS-001_plan_review_blocker: 0
formal_OPS-001_plan_review_must_fix: 0
formal_OPS-001_plan_review_should_fix: 3
formal_OPS-001_human_plan_approved_at: "2026-08-14 08:53 UTC"
formal_OPS-001_next_action: "OPS-002 planned / NOT AUTO-STARTED"
formal_OPS-001_implementation_commit: "61afe0d9fc44116e8a8f08b1058840a3d3f4701c"
formal_OPS-001_implementation_commit_message: "fix(ops): bound worker shutdown shared 270s budget"
formal_OPS-001_plan_landing_completed_at: "2026-08-14 09:11 UTC"
formal_OPS-001_code_review: CODE_REVIEW_APPROVED
formal_OPS-001_code_review_round: 2
formal_OPS-001_p0: 0
formal_OPS-001_p1: 0
formal_OPS-001_p2: 2
formal_OPS-001_p3: 2
formal_OPS-001_scoped_tests: "20 OPS-001 unit + entrypoint regression; kafka INT 8; settings/compose contract 5; ruff/mypy PASS"
formal_OPS-001_pr: "#55"
formal_OPS-001_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/55"
formal_OPS-001_pr_state: MERGED
formal_OPS-001_pr_base: main
formal_OPS-001_pr_head: "feat/OPS-001-graceful-shutdown-pools-timeout-retry"
formal_OPS-001_merge_commit: 9749bd6a86d94919daf4a59be4035872d070fe1e
formal_OPS-001_merged_at: "2026-08-14T02:04:00Z"
formal_OPS-001_status_record_committed: 70b5084cc67251dbfb193459b3840a6fb52141e7
formal_OPS-001_release_gate: COMPLETED
formal_OPS-001_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_OPS-001_note: "POST_MERGE_CLEANUP；implementation 61afe0d9fc44116e8a8f08b1058840a3d3f4701c；record 70b5084cc67251dbfb193459b3840a6fb52141e7；PR #55 MERGED（base=main，head=feat/OPS-001-graceful-shutdown-pools-timeout-retry，merge 9749bd6a86d94919daf4a59be4035872d070fe1e，mergedAt=2026-08-14T02:04:00Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED R2 P0=0/P1=0/P2=2/P3=2 non-blocking；F-008/F-011 shared 270s budget；scoped 20 unit + entrypoint regression passed；ruff/mypy PASS；Amendment 001；feat 分支本地/远程已删除；next_action=OPS-002 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_CON-005_plan_file: 02_开发管理/tasks/CON-005-consolidation-integration-e2e.md
formal_CON-005_status: completed
formal_CON-005_workflow_mode: NORMAL
formal_CON-005_workflow_mode_source: explicit
formal_CON-005_baseline: "010d74112fb760907e710f2ba27123e021dd3d61"
formal_CON-005_branch: "feat/CON-005-consolidation-integration-e2e"
formal_CON-005_milestone: "v0.5.0-consolidation"
formal_CON-005_prerequisite: "SATISFIED — CON-004 completed (PR #53 MERGED); CON-003 completed (PR #52 MERGED); CON-002 completed (PR #51 MERGED); CON-001 completed (PR #50 MERGED); EXT-001..009 completed; RET-001..006 completed"
formal_CON-005_scope: "§2.3.11–13 consolidation vertical slice Integration + E2E on real Neo4j; in-process ConsolidationRunService production wiring; INT-1..6 + E2E-1..6; zero CON-001..004 production semantics diff default; closes v0.5.0-consolidation"
formal_CON-005_blocking_open_issues: []
formal_CON-005_nonblocking_open_issues:
  - "P3-1: C1 contract test untracked-file blind spot"
  - "P3-2: E2E-4 omits conflict-row importance unchanged assertion at E2E layer"
  - "P3-3: E2E-2 no explicit trailing empty-page assertion"
formal_CON-005_dependency_changes_expected: NONE
formal_CON-005_migration_changes_expected: NONE
formal_CON-005_durable_read_scope: "Neo4j read-only — CON-002 batch + CON-004 user enumeration (test verification)"
formal_CON-005_durable_write_scope: "Neo4j Memory — importance, last_consolidated_time (via existing CON-003 path; test verification only)"
formal_CON-005_production_file_whitelist: NONE
formal_CON-005_test_file_whitelist: "tests/support/con005_neo4j_fixtures.py; tests/support/con005_failure_doubles.py; tests/integration/conftest_con005_neo4j.py; tests/integration/test_con005_consolidation_read_neo4j.py; tests/integration/test_con005_consolidation_write_neo4j.py; tests/integration/test_con005_consolidation_run_neo4j.py; tests/e2e/helpers/con005_e2e_helpers.py; tests/e2e/test_con005_consolidation_e2e.py; tests/contract/test_con005_scope_boundaries.py"
formal_CON-005_scoped_tests: "Integration 6 passed; E2E 6 passed; CON-001..004 unit 92 passed; contract 4 passed"
formal_CON-005_ruff: PASS
formal_CON-005_mypy: PASS
formal_CON-005_note: "POST_MERGE_CLEANUP；implementation a8625ea81f21a686f2c84a0a9e204e313c4e95c9；record 7875e92feb417e6e9705c90396ba6e7d5d2e3034；PR #54 MERGED（base=main，head=feat/CON-005-consolidation-integration-e2e，merge 8427868a2448fe11c9af64e3faedf5752badf8e9，mergedAt=2026-08-13T15:35:15Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED R2 P0=0/P1=0/P2=0/P3=3 non-blocking（P3-1 C1 untracked blind spot；P3-2 E2E-4 conflict importance；P3-3 E2E-2 trailing empty page）；production src/** diff=NONE；real Neo4j INT 6 + E2E 6 passed；CON-001..004 regression 92 passed；contract 4 passed；ruff/mypy PASS；Amendment 001 recovery semantics preserved — Run A@T1 partial+fail；Run B@T2>T1 full rescan；T1 rows re-eligible；last_consolidated_time=T2；no checkpoint；in-process ConsolidationRunService + real Neo4j；closes v0.5.0-consolidation milestone ONLY（NOT v0.9/v1.0）；feat 分支本地/远程已删除；next_action=OPS-001 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_CON-005_plan_commit: "2862b7a"
formal_CON-005_plan_review: PLAN_APPROVED
formal_CON-005_code_review: CODE_REVIEW_APPROVED
formal_CON-005_p0: 0
formal_CON-005_p1: 0
formal_CON-005_p2: 0
formal_CON-005_p3: 3
formal_CON-005_implementation_commit: a8625ea81f21a686f2c84a0a9e204e313c4e95c9
formal_CON-005_implementation_commit_message: "test(con): add consolidation neo4j integration and e2e suite"
formal_CON-005_pr: "#54"
formal_CON-005_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/54"
formal_CON-005_pr_state: MERGED
formal_CON-005_pr_base: main
formal_CON-005_pr_head: "feat/CON-005-consolidation-integration-e2e"
formal_CON-005_merge_commit: 8427868a2448fe11c9af64e3faedf5752badf8e9
formal_CON-005_merged_at: "2026-08-13T15:35:15Z"
formal_CON-005_status_record_committed: 7875e92feb417e6e9705c90396ba6e7d5d2e3034
formal_CON-005_milestone_status: closed
formal_CON-005_release_gate: COMPLETED
formal_CON-005_human_plan_approved: true
formal_CON-005_human_plan_approved_at: "2026-08-13T14:37:00Z"
formal_CON-005_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_CON-005_next_action: "OPS-001 planned / NOT AUTO-STARTED"
formal_CON-004_plan_file: 02_开发管理/tasks/CON-004-apscheduler-mutex-failure-recovery.md
formal_CON-004_status: completed
formal_CON-004_workflow_mode: NORMAL
formal_CON-004_workflow_mode_source: explicit
formal_CON-004_baseline: "8998f627b6cf0c8f5beb103006903d8c3668542a"
formal_CON-004_branch: "feat/CON-004-apscheduler-mutex-failure-recovery"
formal_CON-004_prerequisite: "SATISFIED — CON-003 completed (PR #52 MERGED); CON-002 completed (PR #51 MERGED); CON-001 completed (PR #50 MERGED); EXT-001..009 completed; RET-001..006 completed"
formal_CON-004_scope: "§2.3.11 run orchestration + §3.22 APScheduler + §2.3.4 process-local mutex + §2.3.13 failure recovery/metrics + consolidation_worker wiring; reuse CON-002 read + CON-003 write; zero CON-001/002/003 semantics diff"
formal_CON-004_blocking_open_issues: []
formal_CON-004_nonblocking_open_issues:
  - "P2-1: C1 contract test untracked-file blind spot"
  - "P2-2: Prometheus failure-path assertions gap"
  - "P3-1: telemetry naming consistency"
formal_CON-004_dependency_changes_expected: NONE
formal_CON-004_migration_changes_expected: NONE
formal_CON-004_durable_read_scope: "Neo4j read-only — DISTINCT user_id enumeration"
formal_CON-004_durable_write_scope: "NONE at orchestration layer — delegated to CON-003 Neo4j write"
formal_CON-004_production_file_whitelist: "src/memory_system/domain/models/consolidation_run.py; src/memory_system/domain/services/consolidation_run_service.py; src/memory_system/infrastructure/consolidation_mutex.py; src/memory_system/infrastructure/scheduling/consolidation_scheduler.py; src/memory_system/infrastructure/neo4j/consolidation_user_enumeration_repository.py; src/memory_system/observability/consolidation_run_telemetry.py; src/memory_system/entrypoints/consolidation_worker.py"
formal_CON-004_test_file_whitelist: "tests/unit/test_consolidation_run_service.py; tests/unit/test_consolidation_mutex.py; tests/unit/test_consolidation_scheduler.py; tests/unit/test_consolidation_user_enumeration_repository.py; tests/unit/test_consolidation_worker_entrypoint.py; tests/contract/test_con004_scope_boundaries.py"
formal_CON-004_note: "POST_MERGE_CLEANUP；implementation abb2ceaf6579f9dfff9e46f4782d3d9d181d31c1；PR #53 MERGED（base=main，head=feat/CON-004-apscheduler-mutex-failure-recovery，merge ae70a94fd08382ffd43fbdc0e64ec613423fc403，mergedAt=2026-08-13T13:59:12Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=1 non-blocking（P2-1 C1 untracked blind spot；P2-2 Prometheus failure-path assertions；P3-1 telemetry naming）；scoped 37 passed；ruff/mypy PASS；§2.3.11 run orchestration — one evaluation_time per run；process-local mutex/finally release；per-user cursor orchestration；non-fatal version conflicts；no persistent cursor/run-state；zero CON-001/002/003 semantics diff；Integration DEFERRED CON-005；feat 分支本地/远程已删除；next_action=CON-005 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_CON-004_plan_commit: "e124b23"
formal_CON-004_code_review: CODE_REVIEW_APPROVED
formal_CON-004_p0: 0
formal_CON-004_p1: 0
formal_CON-004_p2: 2
formal_CON-004_p3: 1
formal_CON-004_scoped_tests: "37 passed"
formal_CON-004_ruff: PASS
formal_CON-004_mypy: "PASS（7 new src files）"
formal_CON-004_implementation_commit: abb2ceaf6579f9dfff9e46f4782d3d9d181d31c1
formal_CON-004_implementation_commit_message: "feat(con): add consolidation scheduler run orchestration and worker"
formal_CON-004_pr: "#53"
formal_CON-004_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/53"
formal_CON-004_pr_state: MERGED
formal_CON-004_pr_base: main
formal_CON-004_pr_head: "feat/CON-004-apscheduler-mutex-failure-recovery"
formal_CON-004_merge_commit: ae70a94fd08382ffd43fbdc0e64ec613423fc403
formal_CON-004_merged_at: "2026-08-13T13:59:12Z"
formal_CON-004_status_record_committed: null
formal_CON-004_release_gate: COMPLETED
formal_CON-004_next_action: "CON-005 planned / NOT AUTO-STARTED"
formal_CON-004_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_CON-004_human_plan_approved: true
formal_CON-003_plan_file: 02_开发管理/tasks/CON-003-optimistic-lock-batch-update.md
formal_CON-003_status: completed
formal_CON-003_workflow_mode: NORMAL
formal_CON-003_workflow_mode_source: explicit
formal_CON-003_baseline: "cabcc6f98e5cd676b962b49e3b0c943587a11689"
formal_CON-003_branch: "feat/CON-003-optimistic-lock-batch-update"
formal_CON-003_prerequisite: "SATISFIED — CON-002 completed (PR #51 MERGED); CON-001 completed (PR #50 MERGED); EXT-001..009 completed; RET-001..006 completed"
formal_CON-003_scope: "§2.3.9 Neo4j optimistic-lock batch write — SET importance + last_consolidated_time only; expected_memory_version predicate; batch transaction; version_conflict_count; zero memory_version/updated_time mutation; CON-002 scored handoff only"
formal_CON-003_blocking_open_issues: []
formal_CON-003_nonblocking_open_issues: []
formal_CON-003_dependency_changes_expected: NONE
formal_CON-003_migration_changes_expected: NONE
formal_CON-003_durable_read_scope: NONE
formal_CON-003_durable_write_scope: "Neo4j Memory — importance, last_consolidated_time"
formal_CON-003_production_file_whitelist: "src/memory_system/domain/models/consolidation_write.py; src/memory_system/domain/services/consolidation_write_service.py; src/memory_system/infrastructure/neo4j/consolidation_memory_write_repository.py"
formal_CON-003_test_file_whitelist: "tests/unit/test_consolidation_memory_write_repository.py; tests/unit/test_consolidation_write_service.py; tests/contract/test_con003_scope_boundaries.py"
formal_CON-003_note: "POST_MERGE_CLEANUP；implementation 8563466feeb8aea38fb6997a3e99d4d54eb3878c；PR #52 MERGED（base=main，head=feat/CON-003-optimistic-lock-batch-update，merge 7337c861150c9312a7a37b2b884839c186cb43d1，mergedAt=2026-08-13T13:03:22Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=1/P3=2 non-blocking；scoped 35 passed；ruff/mypy PASS；§2.3.9 optimistic-lock write contract preserved — expected_memory_version predicate-only / no memory_version increment；partial-success batch semantics（version_conflict_count）；SET importance + last_consolidated_time only；不写 updated_time；CON-002 scored handoff only；Integration DEFERRED CON-005；feat 分支本地/远程已删除；next_action=CON-004 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_CON-003_plan_commit: "0146b5dd53d37dfbdec0ea9bc9e87d6fe373221a"
formal_CON-003_plan_review: PLAN_APPROVED
formal_CON-003_code_review: CODE_REVIEW_APPROVED
formal_CON-003_p0: 0
formal_CON-003_p1: 0
formal_CON-003_p2: 1
formal_CON-003_p3: 2
formal_CON-003_scoped_tests: "35 passed"
formal_CON-003_ruff: PASS
formal_CON-003_mypy: "PASS（3 new src files）"
formal_CON-003_human_plan_approved: true
formal_CON-003_developer_authorized: true
formal_CON-003_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_CON-003_implementation_commit: 8563466feeb8aea38fb6997a3e99d4d54eb3878c
formal_CON-003_implementation_commit_message: "feat(con): add consolidation optimistic lock batch write"
formal_CON-003_pr: "#52"
formal_CON-003_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/52"
formal_CON-003_pr_state: MERGED
formal_CON-003_pr_base: main
formal_CON-003_pr_head: "feat/CON-003-optimistic-lock-batch-update"
formal_CON-003_merge_commit: 7337c861150c9312a7a37b2b884839c186cb43d1
formal_CON-003_merged_at: "2026-08-13T13:03:22Z"
formal_CON-003_status_record_committed: null
formal_CON-003_release_gate: COMPLETED
formal_CON-003_next_action: "CON-004 planned / NOT AUTO-STARTED"
formal_CON-002_plan_file: 02_开发管理/tasks/CON-002-cursor-batch-evidence-count.md
formal_CON-002_status: completed
formal_CON-002_workflow_mode: NORMAL
formal_CON-002_workflow_mode_source: explicit
formal_CON-002_baseline: "85875ff4d86ad39ccff9d4632088713ef8b052af"
formal_CON-002_branch: "feat/CON-002-cursor-batch-evidence-count"
formal_CON-002_prerequisite: "SATISFIED — CON-001 completed (PR #50 MERGED); EXT-001..009 completed; RET-001..006 completed"
formal_CON-002_scope: "§2.3.4 cursor pagination Neo4j batch read + independent_archive_count + per-user isolation + CON-001 handoff; zero durable write; §2.3.4 read-only boundary preserved"
formal_CON-002_blocking_open_issues: []
formal_CON-002_nonblocking_open_issues:
  - "P2-1: C1 contract test untracked-file blind spot"
  - "P2-2: null archive_id Evidence distinct-count explicit test gap (LD-2 documented)"
formal_CON-002_dependency_changes_expected: NONE
formal_CON-002_migration_changes_expected: NONE
formal_CON-002_durable_read_scope: "Neo4j read-only — consolidation candidate batch scan"
formal_CON-002_durable_write_scope: NONE
formal_CON-002_production_file_whitelist: "src/memory_system/domain/models/consolidation_batch.py; src/memory_system/domain/services/consolidation_batch_service.py; src/memory_system/infrastructure/neo4j/consolidation_memory_read_repository.py"
formal_CON-002_test_file_whitelist: "tests/unit/test_consolidation_memory_read_repository.py; tests/unit/test_consolidation_batch_service.py; tests/contract/test_con002_scope_boundaries.py"
formal_CON-002_note: "POST_MERGE_CLEANUP；implementation a13ab31bb98598740198001d8bfee3f21d6b565a；PR #51 MERGED（base=main，head=feat/CON-002-cursor-batch-evidence-count，merge 3b26549c41b91a1bbdd72237865a5d3d4fb5324d，mergedAt=2026-08-13T11:15:50Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=2 non-blocking（P2-1 C1 untracked blind spot；P2-2 null archive_id test gap）；scoped 39 passed；ruff/mypy PASS；§2.3.4 read-only cursor batch + count(DISTINCT archive_id) + per-user isolation + zero-Evidence→missing_evidence；零 durable write；feat 分支本地/远程已删除；next_action=CON-003 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_CON-002_plan_commit: "a3d0c26f1864e399d2562f1648c99584fe77d8e4"
formal_CON-002_plan_review: PLAN_APPROVED
formal_CON-002_code_review: CODE_REVIEW_APPROVED
formal_CON-002_p0: 0
formal_CON-002_p1: 0
formal_CON-002_p2: 2
formal_CON-002_p3: 2
formal_CON-002_implementation_commit: a13ab31bb98598740198001d8bfee3f21d6b565a
formal_CON-002_implementation_commit_message: "feat(con): add consolidation cursor batch read and evidence count"
formal_CON-002_pr: "#51"
formal_CON-002_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/51"
formal_CON-002_pr_state: MERGED
formal_CON-002_pr_base: main
formal_CON-002_pr_head: "feat/CON-002-cursor-batch-evidence-count"
formal_CON-002_merge_commit: 3b26549c41b91a1bbdd72237865a5d3d4fb5324d
formal_CON-002_merged_at: "2026-08-13T11:15:50Z"
formal_CON-002_status_record_committed: null
formal_CON-002_release_gate: COMPLETED
formal_CON-002_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_CON-002_human_plan_approved: true
formal_CON-002_developer_authorized: true
formal_CON-002_scoped_tests: "39 passed"
formal_CON-002_ruff: PASS
formal_CON-002_mypy: "PASS（3 new src files）"
formal_CON-002_next_action: "CON-003 planned / NOT AUTO-STARTED"
formal_CON-001_plan_file: 02_开发管理/tasks/CON-001-importance-decay-protection-formulas.md
formal_CON-001_status: completed
formal_CON-001_workflow_mode: NORMAL
formal_CON-001_workflow_mode_source: explicit
formal_CON-001_baseline: "2159ad6cc5e3f31365677671d9588c69b776e8a0"
formal_CON-001_branch: "feat/CON-001-importance-decay-protection-formulas"
formal_CON-001_prerequisite: "SATISFIED — EXT-004 completed; EXT-001..009 completed; RET-001..006 completed; v0.3.0 and v0.4.0 milestones closed"
formal_CON-001_scope: "§2.3.5–2.3.7 consolidation importance pure functions; consume MemoryConsolidationSettings; missing_evidence skip; zero durable read/write; §2.3.8 documentation-only"
formal_CON-001_blocking_open_issues: []
formal_CON-001_nonblocking_open_issues: []
formal_CON-001_dependency_changes_expected: NONE
formal_CON-001_migration_changes_expected: NONE
formal_CON-001_durable_read_scope: NONE
formal_CON-001_durable_write_scope: NONE
formal_CON-001_production_file_whitelist: "src/memory_system/domain/models/consolidation_importance.py; src/memory_system/domain/services/consolidation_importance.py"
formal_CON-001_test_file_whitelist: "tests/unit/test_consolidation_importance.py; tests/contract/test_con001_scope_boundaries.py"
formal_CON-001_note: "POST_MERGE_CLEANUP；implementation 41932b93431e43fa1d134cfed76dfedb9ec7f363；record bef3ae23e8b12592cbdfcfb563654fb91c97cea2；PR #50 MERGED（base=main，head=feat/CON-001-importance-decay-protection-formulas，merge e9469d8ee61d363d7367a9b17ca2680794ce39f0，mergedAt=2026-08-13T10:24:42Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=1/P3=2 non-blocking；scoped 49 passed；ruff/mypy PASS；§2.3.5–2.3.7 consolidation importance pure functions；零 durable I/O；feat 分支本地/远程已删除；next_action=CON-002 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_CON-001_scoped_tests: "49 passed"
formal_CON-001_ruff: PASS
formal_CON-001_mypy: PASS
formal_CON-001_plan_commit: "6f4a35ad28ad90946f74e39bfa567acc71120b12"
formal_CON-001_plan_review: PLAN_APPROVED
formal_CON-001_code_review: CODE_REVIEW_APPROVED
formal_CON-001_p0: 0
formal_CON-001_p1: 0
formal_CON-001_p2: 1
formal_CON-001_p3: 2
formal_CON-001_implementation_commit: 41932b93431e43fa1d134cfed76dfedb9ec7f363
formal_CON-001_implementation_commit_message: "feat(con): add consolidation importance pure functions"
formal_CON-001_pr: "#50"
formal_CON-001_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/50"
formal_CON-001_pr_state: MERGED
formal_CON-001_pr_base: main
formal_CON-001_pr_head: "feat/CON-001-importance-decay-protection-formulas"
formal_CON-001_merge_commit: e9469d8ee61d363d7367a9b17ca2680794ce39f0
formal_CON-001_merged_at: "2026-08-13T10:24:42Z"
formal_CON-001_status_record_committed: bef3ae23e8b12592cbdfcfb563654fb91c97cea2
formal_CON-001_release_gate: COMPLETED
formal_CON-001_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_CON-001_human_plan_approved: true
formal_CON-001_developer_authorized: true
formal_CON-001_next_action: "CON-002 planned / NOT AUTO-STARTED"
formal_RET-006_plan_file: 02_开发管理/tasks/RET-006-retrieval-e2e-failure-injection.md
formal_RET-006_status: completed
formal_RET-006_workflow_mode: NORMAL
formal_RET-006_workflow_mode_source: explicit
formal_RET-006_baseline: 538cf13ac3d33d1f337a9e5f5b450626ddd6529d
formal_RET-006_branch: "feat/RET-006-retrieval-e2e-failure-injection"
formal_RET-006_milestone: "v0.4.0-memory-retrieval"
formal_RET-006_prerequisite: "SATISFIED — RET-001..005 completed (PR #44..#48 MERGED); EXT-007 completed (PR #41 MERGED); OI-008 resolved_by_task=RET-005"
formal_RET-006_scope: "§2.2.16 Retrieval stage E2E + §3.28 failure injection; EXT-007 write→retrieve (E2E-2); real ES+Neo4j; in-process ASGI; zero production diff default"
formal_RET-006_fixture_strategy: "BOTH — A pre-seeded fixtures (E2E-1,3..6) + B EXT-007 sync path (E2E-2 REQUIRED)"
formal_RET-006_write_to_retrieve: REQUIRED
formal_RET-006_blocking_open_issues: []
formal_RET-006_nonblocking_open_issues: []
formal_RET-006_dependency_changes_expected: NONE
formal_RET-006_migration_changes_expected: NONE
formal_RET-006_durable_write_scope: "existing RET-005 Neo4j stats + EXT-007 ES upsert (E2E-2 only)"
formal_RET-006_production_file_whitelist: NONE
formal_RET-006_note: "POST_MERGE_CLEANUP；implementation 6e5517c11f0c7b6417264064d718937dd0aca62b；record 4637279313e2fac61b986bbe45be8dfb847318b2；PR #49 MERGED（base=main，head=feat/RET-006-retrieval-e2e-failure-injection，merge 295c5faa3b0160db349b926dc8eb0a001d67c7ce，mergedAt=2026-08-13T08:48:22Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=1/P3=2 non-blocking；scoped 9 passed（E2E-1,2,3,4a,4b,5a,5b,6 + auth）；§2.2.16 Retrieval stage E2E + §3.28 failure injection；EXT-007 write→retrieve（E2E-2）；零 src/** diff；feat 分支本地/远程已删除；closes v0.4.0-memory-retrieval milestone；next_action=CON-001 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_RET-006_plan_review_round: 2
formal_RET-006_plan_review: PLAN_APPROVED
formal_RET-006_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_RET-006_human_plan_approved: true
formal_RET-006_human_plan_approved_at: "2026-08-13T08:08:00Z"
formal_RET-006_developer_authorized: true
formal_RET-006_next_action: "CON-001 planned / NOT AUTO-STARTED"
formal_RET-006_scoped_tests: "9 passed (E2E-1,2,3,4a,4b,5a,5b,6 + auth)"
formal_RET-006_ruff: PASS
formal_RET-006_mypy: PASS
formal_RET-006_production_diff: "src/** empty"
formal_RET-006_code_review: CODE_REVIEW_APPROVED
formal_RET-006_p0: 0
formal_RET-006_p1: 0
formal_RET-006_p2: 1
formal_RET-006_p3: 2
formal_RET-006_plan_commit: e1abc1ca77566da645a8087844d0da28cd8c87fe
formal_RET-006_implementation_commit: 6e5517c11f0c7b6417264064d718937dd0aca62b
formal_RET-006_implementation_commit_message: "test(ret): add retrieval stage e2e with failure injection"
formal_RET-006_pr: "#49"
formal_RET-006_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/49"
formal_RET-006_pr_state: MERGED
formal_RET-006_pr_base: main
formal_RET-006_pr_head: "feat/RET-006-retrieval-e2e-failure-injection"
formal_RET-006_merge_commit: 295c5faa3b0160db349b926dc8eb0a001d67c7ce
formal_RET-006_merged_at: "2026-08-13T08:48:22Z"
formal_RET-006_status_record_committed: 4637279313e2fac61b986bbe45be8dfb847318b2
formal_RET-006_milestone_status: closed
formal_RET-006_release_gate: COMPLETED
formal_RET-005_plan_file: 02_开发管理/tasks/RET-005-retrieval-api-degradation-statistics.md
formal_RET-005_status: completed
formal_RET-005_workflow_mode: NORMAL
formal_RET-005_workflow_mode_source: explicit
formal_RET-005_baseline: c086b9953829d0ca19e930cde9b1c64dadde5fb9
formal_RET-005_branch: "feat/RET-005-retrieval-api-degradation-statistics"
formal_RET-005_prerequisite: "SATISFIED — RET-001..004 completed (PR #44..#47 MERGED); DEV-005 completed"
formal_RET-005_scope: "§2.2.5 HTTP Retrieval API; §2.2.12 Response DTO; §2.2.13 Neo4j retrieval_count/last_retrieved_time; §2.2.15 degradation/timeout; tokenize gate orchestration; zero RET-001..004 semantic diff"
formal_RET-005_blocking_open_issues: []
formal_RET-005_nonblocking_open_issues: []
formal_RET-005_resolved_open_issues: [OI-008]
formal_RET-005_dependency_changes_expected: NONE
formal_RET-005_migration_changes_expected: NONE
formal_RET-005_durable_write_scope: "Neo4j Memory.retrieval_count + last_retrieved_time ONLY"
formal_RET-005_note: "POST_MERGE_CLEANUP；implementation 9baf16a7c6f7b0ad3cec8155b54c9fdeeb8c4250；plan a6b0884f9cc6489f009d3d02a68a422dba88574b；PR #48 MERGED（base=main，head=feat/RET-005-retrieval-api-degradation-statistics，merge 5b577d6e04c8b1e0a7336169a18855c66e4a2a3a，mergedAt=2026-08-13T07:42:25Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=3/P3=2 non-blocking（P2 remediated pre-commit）；§2.2.5 POST /api/v1/memory/retrieval + §2.2.12 Response DTO + §2.2.13 Neo4j stats + §2.2.15 degradation/timeout；OI-008 resolved_by_task（canonical DR-1..DR-10）；零 RET-001..004 production semantic diff；feat 分支本地/远程已删除；next_action=RET-006 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_RET-005_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_RET-005_plan_review: PLAN_APPROVED
formal_RET-005_scoped_tests: "48 passed (unit 34 + contract 8 + integration HTTP 8)"
formal_RET-005_ruff: PASS
formal_RET-005_mypy: PASS
formal_RET-005_code_review: CODE_REVIEW_APPROVED
formal_RET-005_p0: 0
formal_RET-005_p1: 0
formal_RET-005_p2: 3
formal_RET-005_p3: 2
formal_RET-005_plan_commit: a6b0884f9cc6489f009d3d02a68a422dba88574b
formal_RET-005_implementation_commit: 9baf16a7c6f7b0ad3cec8155b54c9fdeeb8c4250
formal_RET-005_implementation_commit_message: "feat(ret): add memory retrieval api with degradation and statistics"
formal_RET-005_pr: "#48"
formal_RET-005_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/48"
formal_RET-005_pr_state: MERGED
formal_RET-005_pr_base: main
formal_RET-005_pr_head: "feat/RET-005-retrieval-api-degradation-statistics"
formal_RET-005_merge_commit: 5b577d6e04c8b1e0a7336169a18855c66e4a2a3a
formal_RET-005_merged_at: "2026-08-13T07:42:25Z"
formal_RET-005_status_record_committed: null
formal_RET-005_release_gate: COMPLETED
formal_RET-005_next_action: "RET-006 planned / NOT AUTO-STARTED"
formal_RET-004_plan_file: 02_开发管理/tasks/RET-004-act-r-scoring-evidence-aggregation.md
formal_RET-004_status: completed
formal_RET-004_workflow_mode: NORMAL
formal_RET-004_workflow_mode_source: explicit
formal_RET-004_baseline: c8d9d38d92414b9e041dd3d97dcbfd17b9e61582
formal_RET-004_branch: "feat/RET-004-act-r-scoring-evidence-aggregation"
formal_RET-004_prerequisite: "SATISFIED — RET-001 completed; RET-002 completed (PR #45 MERGED); RET-003 completed (PR #46 MERGED); EXT-005 completed; EXT-006 completed"
formal_RET-004_scope: "§2.2.11 ACT-R scoring + §2.2.12 Evidence batch read/aggregation; top_k ordering; read-only Neo4j Evidence; internal graph_load_failed; zero durable writes; no HTTP/retrieval_count"
formal_RET-004_blocking_open_issues: []
formal_RET-004_nonblocking_open_issues: [OI-008]
formal_RET-004_dependency_changes_expected: NONE
formal_RET-004_migration_changes_expected: NONE
formal_RET-004_note: "POST_MERGE_CLEANUP；implementation e631d206b26175d341602ffdfd42a3d8f43edd3f；plan e3e98eeec645ed759fd90579149fae3e3420214c；PR #47 MERGED（base=main，head=feat/RET-004-act-r-scoring-evidence-aggregation，merge f505c25572f5695a772ac8598be9c8602b36aa9e，mergedAt=2026-08-13T06:47:29Z）；fetch 后 origin/main 已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=2 non-blocking；§2.2.11 ACT-R scoring；Top-K before Evidence；Evidence does not affect final_score；零 durable write；新建 act_r_scoring + retrieval_scoring_service + retrieval_evidence_read_repository + evidence_aggregation（禁止混用 EXT-005）；Integration Neo4j Evidence Fixture；feat 分支本地/远程已删除；next_action=RET-005 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_RET-004_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_RET-004_plan_review: PLAN_APPROVED
formal_RET-004_plan_review_blocker: 0
formal_RET-004_plan_review_must_fix: 0
formal_RET-004_plan_review_should_fix: 3
formal_RET-004_scoped_tests: "52 passed (unit 47 + integration 5)"
formal_RET-004_ruff: PASS
formal_RET-004_mypy: PASS
formal_RET-004_next_action: "RET-005 planned / NOT AUTO-STARTED"
formal_RET-004_code_review: CODE_REVIEW_APPROVED
formal_RET-004_p0: 0
formal_RET-004_p1: 0
formal_RET-004_p2: 2
formal_RET-004_p3: 2
formal_RET-004_plan_commit: e3e98eeec645ed759fd90579149fae3e3420214c
formal_RET-004_implementation_commit: e631d206b26175d341602ffdfd42a3d8f43edd3f
formal_RET-004_implementation_commit_message: "feat(ret): add act-r scoring, top-k ordering, and evidence aggregation"
formal_RET-004_pr: "#47"
formal_RET-004_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/47"
formal_RET-004_pr_state: MERGED
formal_RET-004_pr_base: main
formal_RET-004_pr_head: "feat/RET-004-act-r-scoring-evidence-aggregation"
formal_RET-004_merge_commit: f505c25572f5695a772ac8598be9c8602b36aa9e
formal_RET-004_merged_at: "2026-08-13T06:47:29Z"
formal_RET-004_status_record_committed: null
formal_RET-004_release_gate: COMPLETED
formal_RET-003_plan_file: 02_开发管理/tasks/RET-003-neo4j-graph-expansion-mget.md
formal_RET-003_status: completed
formal_RET-003_workflow_mode: NORMAL
formal_RET-003_workflow_mode_source: explicit
formal_RET-003_baseline: 21a99a5b217f45cd4e4c67b8758bf1705d9d0a74
formal_RET-003_branch: "feat/RET-003-neo4j-graph-expansion-mget"
formal_RET-003_prerequisite: "SATISFIED — RET-001 completed; RET-002 completed (PR #45 MERGED); EXT-006 completed; EXT-007 completed; DEV-004 completed"
formal_RET-003_scope: "§2.2.10 Neo4j authoritative recall + one-hop graph expansion + ES MGET existence; internal dirty_index/stale_index/graph_expansion_failed warnings; read-only; no HTTP/ACT-R/Evidence/retrieval_count"
formal_RET-003_blocking_open_issues: []
formal_RET-003_nonblocking_open_issues: [OI-008]
formal_RET-003_dependency_changes_expected: NONE
formal_RET-003_migration_changes_expected: NONE
formal_RET-003_note: "POST_MERGE_CLEANUP；implementation 64f71690d6c7ac08762b45d76a34158b49570e24；plan 144844295bbd98b962e269e870e57685c2af9fe4；PR #46 MERGED（base=main，head=feat/RET-003-neo4j-graph-expansion-mget，merge 3746f1bce38b4f6e4c0ab4d7899eff5622cc21c0，mergedAt=2026-08-13T05:03:28Z）；fetch 后 origin/main 领先本地 main，已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=2 non-blocking（U16 user-entity unit；I3 OBJECT tier integration）；§2.2.10 Neo4j authoritative recall + one-hop graph expansion + ES MGET read-only internal path；新建 retrieval_memory_read_repository + mget_retrieval_repository（禁止混用 EXT-007 扩展语义）；Integration Neo4j+ES Fixture；feat 分支本地/远程已删除；next_action=RET-004 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_RET-003_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_RET-003_plan_review: PLAN_APPROVED
formal_RET-003_plan_review_blocker: 0
formal_RET-003_plan_review_must_fix: 0
formal_RET-003_plan_review_should_fix: 3
formal_RET-003_next_action: "RET-004 planned / NOT AUTO-STARTED"
formal_RET-003_scoped_tests: "53 passed (30 RET-003 unit + 7 integration + 16 RET-002 regression)"
formal_RET-003_ruff: PASS
formal_RET-003_mypy: PASS
formal_RET-003_code_review: CODE_REVIEW_APPROVED
formal_RET-003_p0: 0
formal_RET-003_p1: 0
formal_RET-003_p2: 2
formal_RET-003_p3: 0
formal_RET-003_plan_commit: 144844295bbd98b962e269e870e57685c2af9fe4
formal_RET-003_implementation_commit: 64f71690d6c7ac08762b45d76a34158b49570e24
formal_RET-003_implementation_commit_message: "feat(ret): add neo4j authoritative recall, one-hop graph expansion, and es mget"
formal_RET-003_pr: "#46"
formal_RET-003_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/46"
formal_RET-003_pr_state: MERGED
formal_RET-003_pr_base: main
formal_RET-003_pr_head: "feat/RET-003-neo4j-graph-expansion-mget"
formal_RET-003_merge_commit: 3746f1bce38b4f6e4c0ab4d7899eff5622cc21c0
formal_RET-003_merged_at: "2026-08-13T05:03:28Z"
formal_RET-003_status_record_committed: null
formal_RET-003_release_gate: COMPLETED
formal_RET-001_plan_file: 02_开发管理/tasks/RET-001-bm25-retrieval.md
formal_RET-001_status: completed
formal_RET-001_workflow_mode: NORMAL
formal_RET-001_workflow_mode_source: explicit
formal_RET-001_baseline: a780bb2d6ae6d0e47d22f508326aed8f0e4fb7ab
formal_RET-001_branch: "feat/RET-001-bm25-retrieval"
formal_RET-001_prerequisite: "SATISFIED — DEV-004 completed; DEV-007 completed; EXT-007 completed (write path; not hard test prereq)"
formal_RET-001_scope: "§2.2.7 BM25 internal channel only; ES search on alias memory_retrieval_current; filters user_id/memory_type/status; multi_match field weights; output memory_id+rank+score; read-only; no HTTP/embedding/vector/RRF/Neo4j/ACT-R"
formal_RET-001_blocking_open_issues: []
formal_RET-001_nonblocking_open_issues: [OI-008]
formal_RET-001_dependency_changes_expected: NONE
formal_RET-001_migration_changes_expected: NONE
formal_RET-001_note: "POST_MERGE_CLEANUP；implementation fc435db722ed29c05980d6a1a60d9f57fda80968；plan 3f7e333132a6c1bc013eeb5ac0b5b47954734aab；PR #44 MERGED（base=main，head=feat/RET-001-bm25-retrieval，merge a4dda57366b9e0cb2a1fb34b6526a07daa30ed31，mergedAt=2026-08-13T02:29:09Z）；fetch 后 origin/main 领先本地 main，已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=2 non-blocking；§2.2.7 BM25 internal channel read-only；Integration ES Fixture not EXT-007 pipeline；feat 分支本地/远程已删除；next_action=RET-002 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_RET-001_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_RET-001_scoped_tests: "33 passed (25 unit + 8 integration)"
formal_RET-001_ruff: PASS
formal_RET-001_mypy: "PASS（remediation files）"
formal_RET-001_code_review: CODE_REVIEW_APPROVED
formal_RET-001_p0: 0
formal_RET-001_p1: 0
formal_RET-001_p2: 2
formal_RET-001_p3: 2
formal_RET-001_plan_commit: 3f7e333132a6c1bc013eeb5ac0b5b47954734aab
formal_RET-001_implementation_commit: fc435db722ed29c05980d6a1a60d9f57fda80968
formal_RET-001_implementation_commit_message: "feat(ret): add bm25 keyword retrieval channel"
formal_RET-001_pr: "#44"
formal_RET-001_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/44"
formal_RET-001_pr_state: MERGED
formal_RET-001_pr_base: main
formal_RET-001_pr_head: "feat/RET-001-bm25-retrieval"
formal_RET-001_merge_commit: a4dda57366b9e0cb2a1fb34b6526a07daa30ed31
formal_RET-001_merged_at: "2026-08-13T02:29:09Z"
formal_RET-001_status_record_committed: null
formal_RET-001_release_gate: COMPLETED
formal_RET-001_next_action: "RET-002 planned / NOT AUTO-STARTED"
formal_RET-002_plan_file: 02_开发管理/tasks/RET-002-vector-retrieval-rrf.md
formal_RET-002_status: completed
formal_RET-002_workflow_mode: NORMAL
formal_RET-002_workflow_mode_source: explicit
formal_RET-002_baseline: e5f5c9de9883d04759f19080c01f1f50d2c62513
formal_RET-002_branch: "feat/RET-002-vector-retrieval-rrf"
formal_RET-002_prerequisite: "SATISFIED — RET-001 completed (PR #44 MERGED); DEV-007 completed; DEV-004 completed; EXT-007 completed (write path; not hard test prereq)"
formal_RET-002_scope: "§2.2.6 retrieval-path query norm + single-query embed; §2.2.8 Vector kNN; §2.2.9 RRF fusion + retrieval_mode; HybridRetrievalService parallel BM25+Vector; internal retrieval_unavailable; read-only; no HTTP/Neo4j/ACT-R"
formal_RET-002_blocking_open_issues: []
formal_RET-002_nonblocking_open_issues: [OI-008]
formal_RET-002_dependency_changes_expected: NONE
formal_RET-002_migration_changes_expected: NONE
formal_RET-002_note: "POST_MERGE_CLEANUP；implementation 3bf3a1b760080d4f581ab53dad0961a28dfb63a4；plan da1736925b767777bd8f538d5719d5821bebc017；PR #45 MERGED（base=main，head=feat/RET-002-vector-retrieval-rrf，merge 2bfc2b2ddbd5ef69a2a3f473722b32a9ead3d461，mergedAt=2026-08-13T03:13:39Z）；fetch 后 origin/main 领先本地 main，已通过 --ff-only 同步；CODE_REVIEW_APPROVED P0=0/P1=0/P2=1 non-blocking；§2.2.6/§2.2.8/§2.2.9 Vector+RRF internal path；共享 retrieval_filter_builder；Integration ES Fixture + Fake embed；feat 分支本地/远程已删除；next_action=RET-003 planned / NOT AUTO-STARTED；不得触碰 DEV-006/PR#13"
formal_RET-002_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_RET-002_next_action: "RET-003 PLAN_REVIEW_APPROVED — awaiting human PLAN_APPROVED"
formal_RET-002_scoped_tests: "71 passed (31 RET-002 unit + 7 integration + 33 RET-001 regression)"
formal_RET-002_ruff: PASS
formal_RET-002_mypy: PASS
formal_RET-002_code_review: CODE_REVIEW_APPROVED
formal_RET-002_p0: 0
formal_RET-002_p1: 0
formal_RET-002_p2: 1
formal_RET-002_p3: 0
formal_RET-002_plan_commit: da1736925b767777bd8f538d5719d5821bebc017
formal_RET-002_implementation_commit: 3bf3a1b760080d4f581ab53dad0961a28dfb63a4
formal_RET-002_implementation_commit_message: "feat(ret): add vector retrieval, query embedding path, and RRF fusion"
formal_RET-002_pr: "#45"
formal_RET-002_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/45"
formal_RET-002_pr_state: MERGED
formal_RET-002_pr_base: main
formal_RET-002_pr_head: "feat/RET-002-vector-retrieval-rrf"
formal_RET-002_merge_commit: 2bfc2b2ddbd5ef69a2a3f473722b32a9ead3d461
formal_RET-002_merged_at: "2026-08-13T03:13:39Z"
formal_RET-002_status_record_committed: null
formal_RET-002_release_gate: COMPLETED
planning_baseline_RET-001: "a780bb2d6ae6d0e47d22f508326aed8f0e4fb7ab"
planning_baseline_RET-002: "e5f5c9de9883d04759f19080c01f1f50d2c62513"
planning_baseline_RET-003: "21a99a5b217f45cd4e4c67b8758bf1705d9d0a74"
planning_baseline_RET-004: "c8d9d38d92414b9e041dd3d97dcbfd17b9e61582"
planning_baseline_RET-005: "c086b9953829d0ca19e930cde9b1c64dadde5fb9"
planning_baseline_EXT-007: "2db6f5a8957e26a672aa4fcba3bf69eb65b0de1e"
planning_baseline_EXT-006: "59281d1e8d6e3fabfc0fe55f70b3fa50ac44bac2"
formal_EXT-006_plan_file: 02_开发管理/tasks/EXT-006-neo4j-graph-transaction-write.md
formal_EXT-006_status: completed
formal_EXT-006_developer_evidence: "scoped 44 passed; ruff/mypy PASS; 10 production + 7 test files; zero upstream/pipeline diff"
formal_EXT-006_workflow_mode: NORMAL
formal_EXT-006_workflow_mode_source: explicit
formal_EXT-006_baseline: 59281d1e8d6e3fabfc0fe55f70b3fa50ac44bac2
formal_EXT-006_branch: "feat/EXT-006-neo4j-graph-transaction-write"
formal_EXT-006_prerequisite: "SATISFIED — EXT-005 completed (PR #39 MERGED); EXT-004 completed (PR #38 MERGED); EXT-003 completed (PR #37 MERGED); DEV-004 completed"
formal_EXT-006_scope: "§2.1.12 apply planned confidence/importance; §2.1.13 steps 8–10 pre-transaction (referenced_entity_write_set, core_search_text, TEI /tokenize, memory_search_text_too_long gate) + single atomic Neo4j write transaction (Entity/Memory/Evidence + SUBJECT/OBJECT/SUPPORTS/SUPERSEDES/CONFLICTS_WITH); evidence_id/entity_key/memory_id MERGE idempotency; index_sync_memory_set handoff for EXT-007; zero task completed/offset; zero upstream LLM re-call"
formal_EXT-006_plan_review_round: 2
formal_EXT-006_amendment: "Amendment 001 — Round 1 remediation MF-001 + SF-001–SF-004"
formal_EXT-006_amendment_recorded: true
formal_EXT-006_blocking_open_issues: []
formal_EXT-006_nonblocking_open_issues: [OI-006]
formal_EXT-006_dependency_changes_expected: NONE
formal_EXT-006_migration_changes_expected: NONE
formal_EXT-006_authorized_error_codes: "graph_write_failed, memory_search_text_too_long; failed_stage=graph_write (LD-1); entity_alignment_failed/graph_query_failed/reconciliation_plan_conflict/llm_*/archive_*/retrieval_index_write_failed forbidden"
formal_EXT-006_pipeline_handoff: "isolated library service; EXT-003→EXT-006 continuation DEFERRED_FOR_MVP; index_sync_memory_set transient output for EXT-007; PipelineTerminalDecision / consumer / extraction_llm_service / extraction_worker / entity_alignment_service / reconciliation_service unchanged"
formal_EXT-006_note: "POST_MERGE_CLEANUP；implementation b19e913af3848e932b8adb404dc5d5304167fb73；record eafc07a3e01f376f4bd2c6c658c1dd5536c3b61f；PR #40 MERGED merge 372e0232c1e5cfa1d71e2bb0152a22f59e60cd03 mergedAt 2026-08-12T12:12:38Z；scoped 44 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2 non-blocking；zero upstream pipeline/consumer/alignment/reconciliation diff；no task completed/offset writes；OI-006 non-blocking；feat 分支已删；不得触碰 DEV-006/PR#13"
formal_EXT-006_scoped_tests: "44 passed"
formal_EXT-006_ruff: PASS
formal_EXT-006_mypy: PASS
formal_EXT-006_code_review: CODE_REVIEW_APPROVED
formal_EXT-006_p0: 0
formal_EXT-006_p1: 0
formal_EXT-006_p2: 0
formal_EXT-006_p3: 2
formal_EXT-006_implementation_commit: b19e913af3848e932b8adb404dc5d5304167fb73
formal_EXT-006_implementation_commit_message: "feat(ext): add neo4j graph transaction write"
formal_EXT-006_pr: "#40"
formal_EXT-006_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/40"
formal_EXT-006_pr_state: MERGED
formal_EXT-006_merge_commit: 372e0232c1e5cfa1d71e2bb0152a22f59e60cd03
formal_EXT-006_merged_at: "2026-08-12T12:12:38Z"
formal_EXT-006_status_record_committed: eafc07a3e01f376f4bd2c6c658c1dd5536c3b61f
formal_EXT-006_status_record_completed: 6b00287e663f96d0729a2474a678fa5e960cd051
formal_EXT-006_release_gate: COMPLETED
formal_EXT-006_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_EXT-006_next_action: "EXT-007 planned / NOT AUTO-STARTED"
formal_EXT-007_plan_file: 02_开发管理/tasks/EXT-007-retrieval-document-sync.md
formal_EXT-007_status: completed
formal_EXT-007_workflow_mode: NORMAL
formal_EXT-007_workflow_mode_source: explicit
formal_EXT-007_baseline: 2db6f5a8957e26a672aa4fcba3bf69eb65b0de1e
formal_EXT-007_branch: "feat/EXT-007-retrieval-document-sync"
formal_EXT-007_prerequisite: "SATISFIED — EXT-006 completed (PR #40 MERGED); DEV-007 completed; DEV-004 completed"
formal_EXT-007_scope: "§2.2.3 expand index_sync_memory_set via Neo4j; load Memory+Entity; search_text with alias budget (TEI /tokenize); embedding via create_embedding_client; ES bulk upsert memory_retrieval_current refresh=wait_for; mark_completed on success; mark_failed retrieval_index_write_failed; zero offset; zero upstream pipeline/consumer/EXT-001-006 diff; pipeline continuation DEFERRED_FOR_MVP"
formal_EXT-007_blocking_open_issues: []
formal_EXT-007_nonblocking_open_issues: [OI-006]
formal_EXT-007_dependency_changes_expected: NONE
formal_EXT-007_migration_changes_expected: NONE
formal_EXT-007_authorized_error_codes: "retrieval_index_write_failed; failed_stage=retrieval_index (LD-1); graph_write_failed/memory_search_text_too_long/llm_*/archive_*/entity_alignment_failed forbidden"
formal_EXT-007_pipeline_handoff: "isolated library service; EXT-006→EXT-007 continuation DEFERRED_FOR_MVP; first stage to mark task completed; consumer offset after terminal Mongo unchanged"
formal_EXT-007_note: "POST_MERGE_CLEANUP；implementation 2cf93ec5bcb03daae6e266984df2804a09f19a0c；record d385f4b3553d310f89b17e832ea07c29b50d9761；PR #41 MERGED merge afb2fee9ca6f7a5e049f0d9b1b22825de4c665dd mergedAt 2026-08-12T13:27:51Z；scoped 30 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=2 non-blocking；§2.2.3 index sync invariants + completed-before-offset gate preserved；zero upstream pipeline/consumer/EXT-001-006 diff；no offset writes；first mark_completed gate；OI-006 non-blocking；feat 分支已删；不得触碰 DEV-006/PR#13"
formal_EXT-007_scoped_tests: "30 passed"
formal_EXT-007_ruff: PASS
formal_EXT-007_mypy: PASS
formal_EXT-007_code_review: CODE_REVIEW_APPROVED
formal_EXT-007_p0: 0
formal_EXT-007_p1: 0
formal_EXT-007_p2: 3
formal_EXT-007_p3: 2
formal_EXT-007_implementation_commit: 2cf93ec5bcb03daae6e266984df2804a09f19a0c
formal_EXT-007_implementation_commit_message: "feat(ext): add retrieval index document sync"
formal_EXT-007_pr: "#41"
formal_EXT-007_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/41"
formal_EXT-007_pr_state: MERGED
formal_EXT-007_merge_commit: afb2fee9ca6f7a5e049f0d9b1b22825de4c665dd
formal_EXT-007_merged_at: "2026-08-12T13:27:51Z"
formal_EXT-007_status_record_committed: d385f4b3553d310f89b17e832ea07c29b50d9761
formal_EXT-007_release_gate: COMPLETED
formal_EXT-007_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_EXT-007_next_action: "EXT-008 planned / NOT AUTO-STARTED"
planning_baseline_EXT-005: "5deb8949ee5ac367a08f173ef67c0c0689c26f5d"
formal_EXT-005_plan_file: 02_开发管理/tasks/EXT-005-reconciliation-aggregation-gate.md
formal_EXT-005_status: completed
formal_EXT-005_workflow_mode: NORMAL
formal_EXT-005_workflow_mode_source: explicit
formal_EXT-005_baseline: 5deb8949ee5ac367a08f173ef67c0c0689c26f5d
formal_EXT-005_branch: "feat/EXT-005-reconciliation-aggregation-gate"
formal_EXT-005_prerequisite: "SATISFIED — EXT-004 completed (PR #38 MERGED); EXT-003 completed (PR #37 MERGED); DEV-004 completed"
formal_EXT-005_scope: "§2.1.11 read-only Memory recall + LLM Reconciliation + aligned_memory_key + Archive aggregation + reconciliation_plan_conflict gate; §2.1.12 confidence/importance planning output; §2.1.13 pre-transaction steps 1/6/7; transient non-persisted reconciliation plan for EXT-006 (MF-001: PlannedMemoryCreate self-contained rows for create/supersede_new/conflict_new); zero Neo4j/Mongo writes"
formal_EXT-005_plan_review_round: 2
formal_EXT-005_amendment: "Amendment 001 — Round 2 MF-001 + SF-001–SF-004"
formal_EXT-005_amendment_recorded: true
formal_EXT-005_blocking_open_issues: []
formal_EXT-005_nonblocking_open_issues: [OI-006]
formal_EXT-005_dependency_changes_expected: NONE
formal_EXT-005_migration_changes_expected: NONE
formal_EXT-005_authorized_error_codes: "graph_query_failed, reconciliation_plan_conflict, llm_timeout, llm_request_failed, llm_invalid_output; failed_stage=reconciliation (LD-10); graph_query_failed forbidden in EXT-004"
formal_EXT-005_pipeline_handoff: "isolated library service; EXT-004→EXT-005 continuation DEFERRED_FOR_MVP; PipelineTerminalDecision / consumer / extraction_llm_service / extraction_worker / entity_alignment_service unchanged"
formal_EXT-005_note: "POST_MERGE_CLEANUP；implementation c6e619d312bfd83fef30c9f394e16b42a65cba81；record 775992943ae0eb349301defb990c59c7089cf32e；PR #39 MERGED merge 638598080b2d24e9291933c5ef92d3e4d65a0612 mergedAt 2026-08-12T09:47:46Z；scoped 63 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=0；zero Mongo/Neo4j writes；OI-006 non-blocking；EXT-004→EXT-005 continuation DEFERRED_FOR_MVP；feat 分支已删；不得触碰 DEV-006/PR#13"
formal_EXT-005_human_plan_approved: true
formal_EXT-005_human_plan_approved_at: "2026-08-12T08:35:00Z"
formal_EXT-005_approval_posture: "POST_MERGE_CLEANUP — completed"
formal_EXT-005_scoped_tests: "63 passed"
formal_EXT-005_ruff: PASS
formal_EXT-005_mypy: PASS
formal_EXT-005_code_review: CODE_REVIEW_APPROVED
formal_EXT-005_p0: 0
formal_EXT-005_p1: 0
formal_EXT-005_p2: 0
formal_EXT-005_p3: 0
formal_EXT-005_implementation_commit: c6e619d312bfd83fef30c9f394e16b42a65cba81
formal_EXT-005_implementation_commit_message: "feat(ext): add reconciliation plan and read-only recall"
formal_EXT-005_pr: "#39"
formal_EXT-005_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/39"
formal_EXT-005_pr_state: MERGED
formal_EXT-005_merge_commit: 638598080b2d24e9291933c5ef92d3e4d65a0612
formal_EXT-005_merged_at: "2026-08-12T09:47:46Z"
formal_EXT-005_status_record_committed: 775992943ae0eb349301defb990c59c7089cf32e
formal_EXT-005_release_gate: COMPLETED
formal_EXT-005_status_record_completed: fe48dfcafe3f301005a631b3dec8b06272d6d109
formal_EXT-005_next_action: "EXT-006 planned / NOT AUTO-STARTED"
formal_EXT-005_production_scope: "VERIFIED — read-only reconciliation only; zero Mongo/Neo4j writes; upstream zero diff; EXT-004→EXT-005 continuation DEFERRED_FOR_MVP; no EXT-006+, dependency/schema/migration, DEV-006, or PR #13 drift"
formal_EXT-005_implementation_evidence: "src/memory_system/domain/models/reconciliation.py; domain/services/reconciliation_service.py; domain/services/reconciliation_plan_builder.py; domain/services/reconciliation_llm_service.py; infrastructure/neo4j/memory_recall_repository.py; infrastructure/neo4j/evidence_lookup_repository.py; tests/unit+contract+integration per whitelist; pytest 63 passed; ruff+mypy PASS"
planning_baseline_EXT-004: "8330d42a9f2fe9365e180bdd68c6c9dc7add6e48"
formal_EXT-004_plan_file: 02_开发管理/tasks/EXT-004-entity-alignment-neo4j-model-basis.md
formal_EXT-004_status: completed
formal_EXT-004_workflow_mode: NORMAL
formal_EXT-004_workflow_mode_source: explicit
formal_EXT-004_baseline: 8330d42a9f2fe9365e180bdd68c6c9dc7add6e48
formal_EXT-004_branch: "feat/EXT-004-entity-alignment-neo4j-model-basis"
formal_EXT-004_plan_review_round: 2
formal_EXT-004_amendment: "002 — Round 2 plan remediation"
formal_EXT-004_amendment_recorded: true
formal_EXT-004_plan_review: PLAN_APPROVED
formal_EXT-004_plan_review_blocker: 0
formal_EXT-004_plan_review_must_fix: 0
formal_EXT-004_plan_review_should_fix: 1
formal_EXT-004_plan_review_note: "SF-R2-001: Q3 example Cypher uses raw alias IN; implementation must follow §5.2.2 normalize_entity_alias semantics"
formal_EXT-004_human_plan_approved: true
formal_EXT-004_human_plan_approved_at: "2026-08-12T15:06:00Z"
formal_EXT-006_plan_review: PLAN_APPROVED
formal_EXT-006_plan_review_blocker: 0
formal_EXT-006_plan_review_must_fix: 0
formal_EXT-006_plan_review_should_fix: 5
formal_EXT-006_human_plan_approved: true
formal_EXT-006_human_plan_approved_at: "2026-08-12T18:32:00Z"
current_task_approval_posture: AWAIT_PLAN_REVIEW
formal_EXT-004_scoped_tests: "53 passed"
formal_EXT-004_ruff: PASS
formal_EXT-004_mypy: PASS
formal_EXT-004_code_review: CODE_REVIEW_APPROVED
formal_EXT-004_p0: 0
formal_EXT-004_p1: 0
formal_EXT-004_p2: 2
formal_EXT-004_p3: 2
formal_EXT-004_implementation_commit: 0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c
formal_EXT-004_implementation_commit_message: "feat(ext): add deterministic entity alignment and neo4j read model"
formal_EXT-004_pr: "#38"
formal_EXT-004_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/38"
formal_EXT-004_pr_state: MERGED
formal_EXT-004_merge_commit: 229f5e960f51e55a7389599eeccdf650a9a7beff
formal_EXT-004_merged_at: "2026-08-12T07:49:18Z"
formal_EXT-004_status_record_committed: c975394369d2f0f64c973cc8aa701cded6b2c54d
formal_EXT-004_status_record_sha_backfill: 22ff20af43dbb1ddd851ac5c1477aad30bb0c950
formal_EXT-004_release_gate: COMPLETED
formal_EXT-004_status_record_completed: db8945596e316727ec35de20830db6c31c714dfc
formal_EXT-004_next_action: "EXT-005 planned / NOT AUTO-STARTED"
formal_EXT-004_production_scope: "VERIFIED — read-only Neo4j alignment only; zero Neo4j writes; no EXT-005+, dependency/schema/migration, pipeline/consumer/llm/worker semantic, DEV-006, or PR #13 drift"
formal_EXT-004_implementation_evidence: "src/memory_system/domain/models/entity_alignment.py; domain/services/entity_key.py; domain/services/entity_alignment_service.py; infrastructure/neo4j/entity_alignment_repository.py; tests/unit+contract+integration per whitelist; pytest 53 passed; ruff+mypy PASS"
formal_EXT-004_prerequisite: "SATISFIED — EXT-003 completed (PR #37 MERGED); DEV-004 completed (§2.1.9 constraints/indexes exist via migration 002); EXT-001/EXT-002 completed"
formal_EXT-004_prerequisite_evidence: "persisted extraction_result / candidate_fingerprint / candidate_source_time verified in domain/models/extraction_llm.py; non-empty result stays processing via abort_without_terminal; PipelineTerminalDecision and extraction_worker verified unchanged"
formal_EXT-004_scope: "§2.1.9 Entity model basis + §2.1.10 deterministic entity alignment; read-only Neo4j queries; transient (non-persisted) local_entity_id -> entity_id map and planned entity create / planned alias merge records"
formal_EXT-004_blocking_open_issues: []
formal_EXT-004_nonblocking_open_issues: [OI-EXT-004-001, OI-EXT-004-002, OI-EXT-004-003, OI-EXT-004-004]
formal_EXT-004_resolved_open_issues: [OI-EXT-004-001, OI-EXT-004-002]
formal_EXT-004_dependency_changes_expected: NONE
formal_EXT-004_migration_changes_expected: NONE
formal_EXT-004_authorized_error_codes: "entity_alignment_failed only; graph_query_failed reserved for §2.1.11 memory recall (EXT-005) and forbidden in EXT-004; failed_stage=entity_alignment (LD-9)"
formal_EXT-004_pipeline_handoff: "isolated library service; EXT-003→EXT-004 continuation orchestration remains DEFERRED_FOR_MVP (Appendix B §B.10.4); PipelineTerminalDecision / consumer / extraction_llm_service / extraction_worker unchanged"
formal_EXT-004_note: "POST_MERGE_CLEANUP；implementation 0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c；record c975394；sha_backfill 22ff20a；PR #38 MERGED merge 229f5e9 mergedAt 2026-08-12T07:49:18Z；scoped 53 passed；ruff+mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2 non-blocking；read-only Neo4j alignment only；OI-EXT-004-003/004 non-blocking；EXT-003→EXT-004 continuation DEFERRED_FOR_MVP；feat 分支已删；不得触碰 DEV-006/PR#13"
formal_EXT-003_approval_posture: "PLAN_APPROVED — Amendment 002; Round 2 BLOCKER=0 MUST_FIX=0 SHOULD_FIX=1; human PLAN_APPROVED granted; SF-1 orchestration owner=extraction_llm_service.py; Developer authorized post-PLAN_LANDING"
planning_baseline_EXT-003: "f112d12d28d34de18c637a661a857fcb9f0a401f"
formal_EXT-003_plan_file: 02_开发管理/tasks/EXT-003-llm-extraction-fingerprint.md
formal_EXT-003_workflow_mode: NORMAL
formal_EXT-003_plan_review: PLAN_APPROVED
formal_EXT-003_plan_review_round: 2
formal_EXT-003_plan_review_blocker: 0
formal_EXT-003_plan_review_must_fix: 0
formal_EXT-003_plan_review_should_fix: 1
formal_EXT-003_plan_review_prior_result: "Round 1 PLAN_REJECTED; BLOCKER=7, MUST_FIX=2, SHOULD_FIX=3"
formal_EXT-003_amendment_recorded: true
formal_EXT-003_amendment: "002 — AUTHORIZED_EXT_003_MVP_AMENDMENT (items 1-13); Appendix B recorded"
formal_EXT-003_spec_amendment: "Appendix B Amendment EXT-003"
formal_EXT-003_prerequisite: "SATISFIED — EXT-002 and STM-007 completed"
formal_EXT-003_blocking_open_issues: []
formal_EXT-003_deferred_open_issues: [OI-EXT-003-005]
formal_EXT-002_status: completed
formal_EXT-002_plan_file: 02_开发管理/tasks/EXT-002-archive-read-preprocess-redact.md
formal_EXT-002_prerequisite: "SATISFIED — EXT-001 completed; PR #34 MERGED"
formal_EXT-002_workflow_mode: NORMAL
formal_EXT-002_baseline: 13e1dae36a0b0d94415d9581b2a5fe53c990545f
formal_EXT-002_branch: feat/EXT-002-archive-read-preprocess-redact
formal_EXT-002_plan_review: PLAN_APPROVED
formal_EXT-002_plan_review_round: 4
formal_EXT-002_amendment: "004 — authoritative specification/governance amendment: terminal mappings, strict raw validation, deterministic redaction, and handoff order"
formal_EXT-002_note: "Implemented strict raw BSON validation and read-only archive lookup; storage-only _id is ignored, unknown application fields and coercion are rejected, and complete validation precedes preprocessing/redaction/output. Deterministic NFKC/whitespace normalization and local content-only redaction produce only normalized+redacted ExtractionReadyArchive content while preserving order/provenance; terminal mappings and EXT-001 persistence-before-offset semantics remain unchanged. No EXT-003/LLM/worker wiring, dependency, schema, Kafka, task, or status changes."
formal_EXT-002_amendment_override: "Amendment EXT-002-004 implemented; OI-EXT-002-001/002/004/005 resolved; OI-EXT-002-003 deferred/out-of-scope; dependency_changes_expected=NONE."
formal_EXT-002_scoped_tests: "165 passed"
formal_EXT-002_ruff: PASS
formal_EXT-002_mypy: PASS
formal_EXT-002_lints: PASS
formal_EXT-002_code_review: CODE_REVIEW_APPROVED
formal_EXT-002_p0: 0
formal_EXT-002_p1: 0
formal_EXT-002_p2: 0
formal_EXT-002_p3: 0
formal_EXT-002_implementation_commit: 7fdf84827b2c253a6e6734b8051467f3ec1151f1
formal_EXT-002_pr: "#36"
formal_EXT-002_pr_state: MERGED
formal_EXT-002_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/36"
formal_EXT-002_merge_commit: 59e9f7f0cf6effd34d1f13ad022f9b9eb00b8f2d
formal_EXT-002_merged_at: "2026-08-12T02:45:26Z"
formal_EXT-002_status_record_committed: 036d770268c3a3bbb95fe4687fd0007805e284a4
formal_EXT-002_status_record_completed: cd0b1a33848b294b5b068891f2a02422767becf1
formal_EXT-002_amendment_commit: 985613be08814b1e9eea521888b61dd5cb8d94ff
formal_EXT-002_amendment_commit_verified: true
formal_EXT-002_release_gate: COMPLETED
formal_EXT-002_production_scope: "VERIFIED — exact approved whitelist; no EXT-003+, dependency/schema/migration, EXT-001 semantic, DEV-006, or PR #13 drift"
formal_EXT-002_raw_evidence: "RAW-01..RAW-12 PASS; strict no-coercion/_id exception/unknown-field rejection/full-document gate verified"
formal_EXT-002_redaction_evidence: "RED-01..RED-27 PASS; deterministic content-only redaction/no leakage/provenance/order verified"
formal_EXT-002_terminal_evidence: "exact mappings and abort_without_terminal verified; persistence-before-offset and no commit on persistence failure preserved"
formal_EXT-003_status: completed
formal_EXT-003_next_action: "EXT-004 planned / NOT AUTO-STARTED"
formal_EXT-003_scoped_tests: "63 passed"
formal_EXT-003_ruff: PASS
formal_EXT-003_mypy: PASS
formal_EXT-003_code_review: CODE_REVIEW_APPROVED
formal_EXT-003_p0: 0
formal_EXT-003_p1: 0
formal_EXT-003_p2: 1
formal_EXT-003_p3: 1
formal_EXT-003_implementation_commit: 7c6309ee68b01a6604b79253cea65be6fa26a0c6
formal_EXT-003_implementation_commit_message: "feat(ext): add llm extraction and candidate fingerprint"
formal_EXT-003_pr: "#37"
formal_EXT-003_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/37"
formal_EXT-003_pr_state: MERGED
formal_EXT-003_merge_commit: 0eb45e20c64777a03dc770be70cba2316b47fdf6
formal_EXT-003_merged_at: "2026-08-12T06:06:31Z"
formal_EXT-003_status_record_committed: b14d53d840e7ba69139ce050a5225eae92def220
formal_EXT-003_status_record_completed: 5d9349f7ed6984aee5000422bc55ab5e7031285b
formal_EXT-003_release_gate: COMPLETED
formal_EXT-003_note: "POST_MERGE_CLEANUP；implementation 7c6309e；record b14d53d；PR #37 MERGED merge 0eb45e2 mergedAt 2026-08-12T06:06:31Z；scoped 63 passed；ruff+mypy PASS；CODE_REVIEW_APPROVED Round 2 P0=0 P1=0 P2=1 P3=1 non-blocking；OI-EXT-003-005 DEFERRED_FOR_MVP；EXT-004 continuation deferred；feat 分支已删；不得触碰 DEV-006/PR#13"
formal_EXT-003_implementation_note: "ExtractionLlmService owns LLM/validate/fingerprint/persist/pipeline handoff; preprocessing compose-only; PipelineTerminalDecision and worker unchanged"
formal_EXT-003_human_plan_approved: true
formal_EXT-003_human_plan_approved_at: "2026-08-12T05:45:00Z"
formal_EXT-003_human_plan_approved_note: "Human PLAN_APPROVED EXT-003 Amendment 002; Round 2 Plan Review PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=1; SF-1 MVP_LOCAL_DECISION orchestration owner=extraction_llm_service.py"
formal_EXT-003_sf1_decision: "orchestration owner extraction_llm_service.py; preprocessing compose-only; no whitelist expansion"
formal_EXT-003_branch: feat/EXT-003-llm-extraction-fingerprint
formal_EXT-001_status: completed
formal_EXT-001_plan_file: 02_开发管理/tasks/EXT-001-task-schema-kafka-consumer-idempotency-offset.md
formal_EXT-001_prerequisite: SATISFIED  # STM-006 + DEV-004 completed; DEV-004 index/topic re-verified MATCH
formal_EXT-001_workflow_mode: NORMAL
formal_EXT-001_baseline: f4015cdca8694c3c2be96992a4957b2838c873e4
formal_EXT-001_branch: feat/EXT-001-task-schema-kafka-consumer-idempotency-offset
formal_EXT-001_plan_commit: 6f716946638d9585f0aa53854723559b9f8044bb
formal_EXT-001_implementation_commit: afd8b64dfd4856b4a2f00f82846dace76617e0d1
formal_EXT-001_implementation_commit_message: "feat(ext): add extraction task schema and kafka consumer idempotency"
formal_EXT-001_pr: "#34"
formal_EXT-001_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/34"
formal_EXT-001_pr_state: MERGED
formal_EXT-001_merge_commit: ae346dd27cda39f93fa38b7316ec17559df217ef
formal_EXT-001_merged_at: "2026-08-11T13:57:07Z"
formal_EXT-001_status_record_committed: b16c2e05c351cf5402489262a601f9e3afcd20ba
formal_EXT-001_status_record_completed: 128ab7dcae452561ecedf06aadb88b572fadf0be
formal_EXT-001_note: "POST_MERGE_CLEANUP；implementation afd8b64；record b16c2e0；PR #34 MERGED merge ae346dd mergedAt 2026-08-11T13:57:07Z；CODE_REVIEW_APPROVED Round 2 P0=0 P1=0 P2=0 P3=1；scoped 61 passed；ruff+mypy PASS；feat 分支待删；STM-012 prerequisites SATISFIED but NOT auto-started；不得触碰 DEV-006/PR#13"
formal_EXT-001_code_review: CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=1
formal_EXT-001_p0: 0
formal_EXT-001_p1: 0
formal_EXT-001_p2: 0
formal_EXT-001_p3: 1
formal_EXT-001_scoped_unit_contract: "49 passed"
formal_EXT-001_scoped_total: "61 passed"
formal_EXT-001_integration_mongo_migration: "5 passed"
formal_EXT-001_integration_kafka: "8 passed"
formal_EXT-001_ruff: PASS
formal_EXT-001_mypy: PASS
formal_EXT-001_plan_review: PLAN_APPROVED
formal_EXT-001_plan_review_blocker: 0
formal_EXT-001_plan_review_must_fix: 0
formal_EXT-001_plan_review_should_fix: 1
formal_EXT-001_plan_review_round: 2
formal_EXT-001_plan_review_note: "SF-R2-001: §2 concept chain omits empty session_id vs C4; non-blocking"
formal_EXT-001_remediation: "Amendment 001 — MF-001/MF-002 + SF-001..005"
formal_EXT-001_human_plan_approved: true
formal_EXT-001_human_plan_approved_at: "2026-08-11T12:51:00Z"
formal_STM-012_status: completed
formal_STM-012_plan_file: 02_开发管理/tasks/STM-012-republish-extraction-consumer-integration.md
formal_STM-012_branch: feat/STM-012-republish-extraction-consumer-integration
formal_STM-012_plan_commit: b0cc223c60d0d8a1011a7a92e8f705285726792d
formal_STM-012_prerequisite: "SATISFIED — STM-011 + EXT-001 completed"
formal_STM-012_workflow_mode: NORMAL
formal_STM-012_baseline: d6e7941eeaa2a8409b09eaf181d2924eb3865138
formal_STM-012_production_delta: NONE
formal_STM-012_allowed_paths: "tests/integration/test_stm012_republish_extraction_consumer_integration.py; 02_开发管理/tasks/STM-012-republish-extraction-consumer-integration.md; 02_开发管理/progress.md; 02_开发管理/master_plan.md"
formal_STM-012_plan_review_round: 3
formal_STM-012_plan_review: PLAN_APPROVED
formal_STM-012_plan_review_blocker: 0
formal_STM-012_plan_review_must_fix: 0
formal_STM-012_plan_review_should_fix: 3
formal_STM-012_plan_review_note: "SF-R3-001 §2 python -m stale wording; SF-R3-002 CompleteForBoundaryPipeline naming drift; SF-R3-003 PYTHONPATH/VALID_ENV implementer guidance; non-blocking"
formal_STM-012_plan_review_prior_result: "Round 2 BLOCKER=0 MUST_FIX=1 SHOULD_FIX=3"
formal_STM-012_mf001_status: CLOSED
formal_STM-012_human_plan_approved: true
formal_STM-012_human_plan_approved_at: "2026-08-11T14:55:45Z"
formal_STM-012_implementation_commit: 26aa710d62123d341fb79349c9ad86fc5d58c0a6
formal_STM-012_implementation_commit_message: "test(integration): verify republish event extraction consumer idempotency"
formal_STM-012_pr: "#35"
formal_STM-012_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/35"
formal_STM-012_pr_state: MERGED
formal_STM-012_merge_commit: d73207752bbf004a4b20bf8fff00720cc0ca456b
formal_STM-012_merged_at: "2026-08-11T15:20:30Z"
formal_STM-012_record_commit: c99dcf45189da1f5779bda6bf6d35d5853d8bc1b
formal_STM-012_status_record_committed: c99dcf45189da1f5779bda6bf6d35d5853d8bc1b
formal_STM-012_governance_completion_commit: 3f063674cea49115309a867f98bdbb2610a9ff0a
formal_STM-012_status_record_completed: 3f063674cea49115309a867f98bdbb2610a9ff0a
formal_STM-012_code_review: CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=2
formal_STM-012_p0: 0
formal_STM-012_p1: 0
formal_STM-012_p2: 1
formal_STM-012_p3: 2
formal_STM-012_note: "POST_MERGE_CLEANUP；implementation 26aa710；record c99dcf4；PR #35 MERGED merge d732077 mergedAt 2026-08-11T15:20:30Z；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=2；integration 1 passed (59.97s)；ruff+mypy PASS；production_delta NONE；CLI→Kafka→EXT-001 consumer→Mongo idempotency verified；feat 分支已删；EXT-002 remains planned — NOT auto-started；不得触碰 DEV-006/PR#13"
formal_STM-012_integration: "1 passed"
formal_STM-012_ruff: PASS
formal_STM-012_mypy: PASS
formal_STM-011_status: completed
formal_STM-011_plan_file: 02_开发管理/tasks/STM-011-republish-archive-event.md
formal_STM-011_plan_commit: 68cee46011f011f3074662f846c64da670741cb3
formal_STM-011_implementation_commit: 23939a3f3d25f5243978e967949beb4fe6282e2f
formal_STM-011_implementation_commit_message: "feat(stm): add republish_archive_event CLI and service"
formal_STM-011_branch: feat/STM-011-republish-archive-event
formal_STM-011_pr: "#33"
formal_STM-011_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/33"
formal_STM-011_pr_state: MERGED
formal_STM-011_merge_commit: 19fdb55359acd97380a8b5f0d8ae788134f75307
formal_STM-011_merged_at: "2026-08-11T12:17:49Z"
formal_STM-011_status_record_completed: 7f8fd0a89c28b17984ca5b1bc288166daef39e83
formal_STM-011_baseline: 26f31bdf44e879881c8a160ec3855fab88d4e86e
formal_STM-011_workflow_mode: NORMAL
formal_STM-011_code_review: CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3
formal_STM-011_scoped_unit: "16 passed"
formal_STM-011_scoped_contract: "3 passed"
formal_STM-011_integration_kafka: "5 passed"
formal_STM-011_ruff: PASS
formal_STM-011_mypy: PASS
formal_STM-011_note: "POST_MERGE_CLEANUP；scripts/republish_archive_event.py + archive_event_republish_service；Mongo find_context_archive_by_id；ArchiveCreatedEvent + publish_archive_created_event；exit 0/1/2；unit 16 / contract 3 / integration 5 PASS；ruff+mypy PASS；PR #33 MERGED merge 19fdb55；feat 分支待删；**STM-012 NOT ready**（needs EXT-001）；**不得触碰 DEV-006/PR#13**"
formal_DEV-OPS-009_status: completed
formal_DEV-OPS-009_plan_file: 02_开发管理/tasks/DEV-OPS-009-kafka-lz4-runtime-support.md
formal_DEV-OPS-009_plan_commit: 8367e7b6953fe6776d35865375a9aa48b02877f0
formal_DEV-OPS-009_branch: feat/DEV-OPS-009-kafka-lz4-runtime-support
formal_DEV-OPS-009_branch_from: "main（NOT feat/STM-013；NOT feat/DEV-OPS-008；PLAN_LANDING 后创建）"
formal_DEV-OPS-009_workflow_mode: NORMAL
formal_DEV-OPS-009_note: "POST_MERGE_CLEANUP；cramjam>=2.8,<3 闭合权威 lz4；AIOKafkaProducer lz4 init + Kafka lz4 send 测试；unblocks DEV-OPS-008 authoritative-runtime validation；不吸收 C1/C2；PR #32 MERGED；feat 分支已删"
formal_DEV-OPS-009_root_cause: "A — pyproject/uv.lock 未声明 aiokafka 0.13 LZ4 后端 cramjam>=2.8"
formal_DEV-OPS-009_implementation_commit: 90cd79cbc7235cc444b8ff67357a4d229399af1f
formal_DEV-OPS-009_implementation_commit_message: "fix(ops): add cramjam for authoritative Kafka LZ4 runtime support"
formal_DEV-OPS-009_pr: "#32"
formal_DEV-OPS-009_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/32"
formal_DEV-OPS-009_pr_state: MERGED
formal_DEV-OPS-009_merge_commit: f754db8a9b406f62180f33d8a09e412ccc7c605b
formal_DEV-OPS-009_merged_at: "2026-08-11T09:36:27Z"
formal_DEV-OPS-009_governance_completion_commit: e5ed43bee0310f3c42d977d5bd109f96d7522cb2
formal_DEV-OPS-009_status_record_completed: e5ed43bee0310f3c42d977d5bd109f96d7522cb2
formal_DEV-OPS-009_code_review: CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=2
formal_DEV-OPS-008_status: completed
formal_DEV-OPS-008_plan_file: 02_开发管理/tasks/DEV-OPS-008-compose-test-stack-runtime-compatibility.md
formal_DEV-OPS-008_plan_commit: a464952021e3778bb8f29b96f867fc61619b8f76
formal_DEV-OPS-008_implementation_commit: b2f29ee5eab17c02983ce5c041c7c821b8db8318
formal_DEV-OPS-008_implementation_commit_message: "fix(ops): aiokafka 0.13 readiness and ES 9.4 mapping readback compat"
formal_DEV-OPS-008_branch: feat/DEV-OPS-008-compose-test-stack-runtime-compatibility
formal_DEV-OPS-008_branch_from: "main @ 390af52f58509e323dd6500e77524033e0b5dcbf（NOT feat/STM-013；PLAN_LANDING 后创建）"
formal_DEV-OPS-008_workflow_mode: NORMAL
formal_DEV-OPS-008_note: "POST_MERGE_CLEANUP；C1 aiokafka 0.13 bootstrap_connected guard + C2 ES 9.4 element_type readback compat；POST_DEV-OPS-009 authoritative lz4 revalidation PASS；PR #31 MERGED merge 49719b9；feat 分支已删；C1/C2 blocker SATISFIED；STM-013 pending sync/revalidation"
formal_DEV-OPS-008_pr: "#31"
formal_DEV-OPS-008_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/31"
formal_DEV-OPS-008_pr_state: MERGED
formal_DEV-OPS-008_merge_commit: 49719b91e4be6c552c342fef45504166c919febd
formal_DEV-OPS-008_merged_at: "2026-08-11T10:32:18Z"
formal_DEV-OPS-008_status_record_completed: 37d803c308c2f492637bee6047339cb04a846100
formal_DEV-OPS-008_revalidated_source_sha: 9f47597abeb0b69930f1cd18734049c2ee5a4497
formal_DEV-OPS-008_revalidated_main_base: e5ed43bee0310f3c42d977d5bd109f96d7522cb2
formal_DEV-OPS-008_revalidated_image_id: sha256:bf1edf179be9babd435a390f84c7862c9e745f08b77110690baed240b5aef176
formal_DEV-OPS-008_revalidated_container_id: 7dbc9f5a222659d1ca4eb427fbbeeb68072ff69a0ed37ff0dd84752317e8f84e
formal_DEV-OPS-008_authoritative_compression_type: lz4
formal_DEV-OPS-008_gzip_override_used: false
formal_DEV-OPS-008_code_review: CODE_REVIEW_APPROVED P0=0 P1=0 P2=4 P3=2
formal_STM-013_status: completed
formal_STM-013_implementation_commit: 91f8fd1c147e370b8b264b8b896163047df77163
formal_STM-013_implementation_commit_message: "test(e2e): fix E4 Redis message retention assertion after seed"
formal_STM-013_final_source_sha: 91f8fd1c147e370b8b264b8b896163047df77163
formal_STM-013_final_image_id: sha256:fa55a730a79a2332fffc9baf43691217570034ec7cca48de1355bd5831e252ec
formal_STM-013_authoritative_compression_type: lz4
formal_STM-013_gzip_override_used: false
formal_STM-013_pr: "#30"
formal_STM-013_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/30"
formal_STM-013_pr_state: MERGED
formal_STM-013_merge_commit: f473c194dd092fe3b30be5cf356ec533fc32fef8
formal_STM-013_merged_at: "2026-08-11T11:17:33Z"
formal_STM-013_status_record_completed: bbffc776eac12338461cd94b58a231c8ab99b22c
formal_STM-013_release_gate: WAITING_FOR_PR_MERGE
formal_STM-013_blocking_task: null
formal_STM-013_blocking_reason: null
formal_STM-013_code_review: CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2
formal_STM-013_code_review_required: SATISFIED
formal_STM-013_scoped_e2e: "4 passed"
formal_STM-013_full_unit: "459 passed"
formal_STM-013_full_contract: "101 passed"
formal_STM-013_ruff: PASS
formal_STM-013_mypy: PASS
formal_STM-013_readiness: "HTTP 200; kafka_producer=ready; elasticsearch=ready; compression_type=lz4"
formal_STM-013_e1: PASS
formal_STM-013_e2: PASS
formal_STM-013_e3: PASS
formal_STM-013_e4: PASS
formal_STM-013_shim_cleanup: "_patch_aiokafka_bootstrap_connected REMOVED; no gzip override"
formal_STM-013_tests_init_py: "tests/__init__.py — mypy package resolution only (test-tooling adjunct; not production)"
formal_DEV-OPS-008_candidate_title: "Compose test-stack runtime compatibility (aiokafka 0.13 + ES 9.4 mapping API)"
formal_STM-013_plan_commit: 39fab9e564d005d7a8c6409c7b293a6d337741f8
formal_STM-013_branch: feat/STM-013-short-term-memory-e2e
formal_STM-013_plan_file: 02_开发管理/tasks/STM-013-short-term-memory-e2e.md
formal_STM-013_prerequisite: SATISFIED
formal_STM-013_workflow_mode: NORMAL
formal_STM-013_note: "POST_MERGE_CLEANUP；E2E E1–E4 PASS on source-aligned image fa55a730；scope remediation retained（tests-only）；shim removed；PR #30 MERGED merge f473c19；feat 分支已删；closes v0.2.0-short-term-memory milestone"
formal_STM-013_plan_review_round: 2
formal_STM-010_status: completed
formal_STM-010_plan_file: 02_开发管理/tasks/STM-010-session-close.md
formal_STM-010_plan_commit: abd6d8be7d3807710a3cc24d65d2af81576a482d
formal_STM-010_implementation_commit: ebb90e49c4eed8b7fd64a35611d7af87521d3d5a
formal_STM-010_implementation_commit_message: "feat(stm): add session close state machine and API"
formal_STM-010_branch: feat/STM-010-session-close
formal_STM-010_pr: "#29"
formal_STM-010_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/29"
formal_STM-010_pr_state: MERGED
formal_STM-010_merge_commit: 722e42d9e24d085b0ed671478730952ef7c92ad6
formal_STM-010_merged_at: "2026-08-11T02:14:24Z"
formal_STM-010_status_record_completed: null  # pending this docs(status): complete commit SHA
formal_STM-010_workflow_mode: NORMAL
formal_STM-010_prerequisite: SATISFIED
formal_STM-010_code_review: CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=3
formal_STM-010_note: "POST_MERGE_CLEANUP；Session Close enter/revert/terminal Lua + close_session 编排 + ClosePlan.base_compression_version 快照/冻结 + POST /api/v1/memory/session/{user_id}/{session_id}/close；HTTP 200 closed / 503 close_incomplete（OI-003）；状态机 active→closing→终端删 Key；suffix 全归档 split_close_suffix_batches；不复用 Coordinator/LLM/Finalize；OI-004 resolved（OI4 test PASS）；whitelist drift：session_close_script.py P2 approved loader WHITELIST_DOCUMENTATION_DRIFT_ONLY；scoped unit 36 / contract 11 / integration 19；full unit 446 / contract 101；ruff PASS；mypy PASS；PR #29 MERGED merge 722e42d；feat 分支待删"
formal_STM-010_plan_review_round: 2
formal_STM-010_scoped_unit: "36 passed"
formal_STM-010_scoped_contract: "11 passed"
formal_STM-010_integration_redis: "19 passed"
formal_STM-010_full_unit: "446 passed"
formal_STM-010_full_contract: "101 passed"
formal_STM-010_ruff: PASS
formal_STM-010_mypy: PASS
formal_STM-009_status: completed
formal_STM-009_plan_file: 02_开发管理/tasks/STM-009-compression-coordinator-message-write-api.md
formal_STM-009_plan_commit: 8609f15b47a318e885fab9cd073b616863b8d5b5
formal_STM-009_implementation_commit: 1b6270b663b6326efb32f096a0e67e2742bb6794
formal_STM-009_implementation_commit_message: "feat(stm): add compression coordinator and message write API"
formal_STM-009_branch: feat/STM-009-compression-coordinator-message-write-api
formal_STM-009_pr: "#28"
formal_STM-009_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/28"
formal_STM-009_status_record_committed: 63232d837add2b4a6c6918d145f115f4762b88f7
formal_STM-009_status_record_completed: 302e2b285c0bfa0d3bd925bc98df24a122e5bd35
formal_STM-009_pr_state: MERGED
formal_STM-009_merge_commit: 924ca8c8af94793e76be9376c4514ef417ce5e33
formal_STM-009_merged_at: "2026-08-11T01:17:29Z"
formal_STM-009_scoped_unit: "21 passed"
formal_STM-009_scoped_contract: "10 passed"
formal_STM-009_integration_redis: "10 passed"
formal_STM-009_integration_kafka: "2 passed (I-I mandatory)"
formal_STM-009_full_unit: "410 passed"
formal_STM-009_full_contract: "90 passed"
formal_STM-009_ruff: PASS
formal_STM-009_mypy: PASS
formal_STM-009_prerequisite: SATISFIED
formal_STM-009_workflow_mode: NORMAL
formal_STM-009_code_review: CODE_REVIEW_APPROVED
formal_STM-009_p0: 0
formal_STM-009_p1: 0
formal_STM-009_p2: 2
formal_STM-009_p3: 3
formal_STM-009_note: "POST_MERGE_CLEANUP；CompressionCoordinatorService 编排 STM-004/005/006/007/008 公共边界；POST /api/v1/memory/working/message HTTP 接线（DEV-005 鉴权/Request ID/错误包络）；compression_status 七值；状态机：WRITE_LUA→POST_WRITE_TRIGGER_CHECK→CAPACITY_COMPRESSION_ONCE→run_compression_coordination(≤max_compression_rounds_per_request)；容量路径先协调再同 message_id 重试；触发 estimated_tokens>=compression_trigger_tokens；Archive 头部前缀选择+Pending 复用+Mongo create/reuse；Kafka publish_failed 继续 LLM；消息已写入后压缩失败 HTTP 200 不回滚；多轮 partial_completed；HEAD prefix cap-shrink；FakeLlmClient 默认注入；OI-001/OI-002/OI-005 resolved；OI-004 remains open（Redis estimated_tokens sum only；完整 token-boundary 留给 STM-010）；NOT implemented: STM-010 Close / STM-011 republish / STM-013 E2E；PR #28 MERGED merge 924ca8c；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3；feat 分支待删"
formal_STM-008_status: completed
formal_STM-008_plan_file: 02_开发管理/tasks/STM-008-compression-finalize-lua.md
formal_STM-008_plan_commit: fa3e1bf33e889dbb6180315eda896b954a02df8f
formal_STM-008_implementation_commit: d619ca2f7e2e20d2d944794c2ca21e8e6d5752ef
formal_STM-008_implementation_commit_message: "feat(stm): add compression finalize lua and domain service"
formal_STM-008_status_record_committed: a938220f8937b0e8af7e52dd34019ad1b558e789
formal_STM-008_status_record_completed: bdc2429fe63b9852de28e73cbd840de5c9d999d3
formal_STM-008_branch: feat/STM-008-compression-finalize-lua
formal_STM-008_pr: "#27"
formal_STM-008_pr_url: "https://github.com/xu-jia-ming/memory_system/pull/27"
formal_STM-008_pr_state: MERGED
formal_STM-008_merge_commit: ac61680098d2ae2644bc8b990f057816c3218fca
formal_STM-008_merged_at: "2026-08-10T15:48:17Z"
formal_STM-008_scoped_unit: "20 passed (authoritative STM-008 scoped unit per Task Plan §测试结果)"
formal_STM-008_scoped_contract: "4 passed"
formal_STM-008_integration_redis: "27 passed"
formal_STM-008_full_unit: "393 passed"
formal_STM-008_full_contract: "80 passed"
formal_STM-008_ruff: PASS
formal_STM-008_mypy: PASS
formal_STM-008_code_review: CODE_REVIEW_APPROVED
formal_STM-008_p0: 0
formal_STM-008_p1: 0
formal_STM-008_p2: 0
formal_STM-008_p3: 2
formal_STM-008_prerequisite: SATISFIED  # STM-006 + STM-007 completed
formal_STM-008_workflow_mode: NORMAL
formal_STM-008_note: "POST_MERGE_CLEANUP；单 Lua Finalize：12 precondition + 9 mutation + version bump + LTRIM + pending clear + compare-and-delete lock release；STM-007 CompressionFinalizeLlmPayload handoff；token 公式 §1000–1006（I18 Case A new=500；I27 clamp 0）；safety/idempotency：precondition 失败零 mutation、success 后旧 version 重试 version_conflict、无 double-trim/bump、closing in-flight 允许；无 Kafka/Mongo/LLM；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2；OI-004/OI-005 remain open；feat 分支待删"
formal_STM-008_plan_review_round: 2
planning_baseline_head_stm008: ff9a609009f2a151f2e1a4bf41e24be3bc3a2467
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
planning_baseline_head: a15a2e4cd4b0f937a9f15aa9f4a1481ddb867466
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
deferred_business_task: null
deferred_business_task_status: null
deferred_business_task_note: null
formal_DEV-OPS-008_plan_commit: a464952021e3778bb8f29b96f867fc61619b8f76
formal_DEV-OPS-008_implementation_commit: b2f29ee5eab17c02983ce5c041c7c821b8db8318
formal_DEV-OPS-008_sync_commit: 9f47597abeb0b69930f1cd18734049c2ee5a4497
formal_DEV-OPS-008_baseline_source_sha: a464952021e3778bb8f29b96f867fc61619b8f76
formal_DEV-OPS-008_baseline_image_id: sha256:fa1c24f18550f1e776b0a900d7e22c4b175aa3dd9df9b2b571476b8a37e956
formal_DEV-OPS-008_baseline_container_id: db6c92e25d51
formal_DEV-OPS-008_baseline_failure: "AttributeError AIOKafkaClient bootstrap_connected (C1)"
formal_DEV-OPS-008_fixed_image_id: sha256:bf1edf179be9babd435a390f84c7862c9e745f08b77110690baed240b5aef176
formal_DEV-OPS-008_fixed_container_id: 7dbc9f5a222659d1ca4eb427fbbeeb68072ff69a0ed37ff0dd84752317e8f84e
formal_DEV-OPS-008_readiness: "HTTP 200; kafka_producer=ready; elasticsearch=ready; compression_type=lz4; gzip_override=false"
formal_DEV-OPS-008_scoped_unit_c1: "5 passed"
formal_DEV-OPS-008_scoped_unit_c2: "7 passed"
formal_DEV-OPS-008_full_unit: "459 passed"
formal_DEV-OPS-008_full_contract: "101 passed"
formal_DEV-OPS-008_ruff: PASS
formal_DEV-OPS-008_mypy: PASS
formal_DEV-OPS-008_kafka_lz4_integration: "2 passed"
formal_DEV-OPS-008_stm013_shim_note: "post-merge STM-013 revalidation must check tests/e2e/conftest.py _patch_aiokafka_bootstrap_connected for cleanup"
historical_next_action_EXT-002: "EXT-002 tested; next_action=Code Review; do NOT start EXT-003; do NOT touch DEV-006/PR#13"
historical_next_action_OPS-003_pre_plan: "OPS-003 planned / NOT AUTO-STARTED"
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
# STM-013 scope remediation — defect provenance for DEV-OPS-008 (do not merge via STM-013)
stm_013_scope_remediation:
  approved_at: "2026-08-11 12:12 UTC"
  remediation_plan: REMEDIATION_PLAN_APPROVED
  source_implementation_commit: 975e6029d9aef98988c65a0556cb74695d61adf6
  plan_commit_baseline: 39fab9e564d005d7a8c6409c7b293a6d337741f8
  out_of_scope_paths:
    - src/memory_system/infrastructure/runtime.py
    - scripts/migrations/003_elasticsearch_memory_v1.py
  c1_runtime_aiokafka:
    path: src/memory_system/infrastructure/runtime.py
    baseline_failure: "AttributeError AIOKafkaClient has no attribute bootstrap_connected after kafka_producer.start() (aiokafka>=0.13)"
    exposed_by: "STM-013 Fixture A memory-api container lifespan; Fixture B hybrid create_app_state"
    intended_fix: "hasattr bootstrap_connected guard; else kafka_ready=True after successful start()"
    restore_command: "git show 975e6029 -- src/memory_system/infrastructure/runtime.py"
  c2_es_mapping_read:
    path: scripts/migrations/003_elasticsearch_memory_v1.py
    baseline_failure: "assert_mapping_compatible ValueError element_type None != float on ES 9.4 GET mapping API response"
    exposed_by: "memory-api check_elasticsearch readiness; init-infra upgrade on existing index"
    intended_fix: "element_type compared only when both actual and expected non-None"
    restore_command: "git show 975e6029 -- scripts/migrations/003_elasticsearch_memory_v1.py"
  blocking_task_candidate: DEV-OPS-008
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
| STM-008 | Compression Finalize Lua | 2026-08-10 15:48 | `d619ca2` | `ac61680098d2ae2644bc8b990f057816c3218fca` | #27 merged |
| STM-009 | Compression Coordinator + Message Write API | 2026-08-11 01:17 | `1b6270b` | `924ca8c8af94793e76be9376c4514ef417ce5e33` | #28 merged |
| STM-010 | Session Close | 2026-08-11 02:14 | `ebb90e4` | `722e42d9e24d085b0ed671478730952ef7c92ad6` | #29 merged |

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

**下游**：**STM-013** **completed**；**STM-011** **completed**；**EXT-001** **completed**（PR #34 MERGED `ae346dd27cda39f93fa38b7316ec17559df217ef` mergedAt `2026-08-11T13:57:07Z`；implementation `afd8b64dfd4856b4a2f00f82846dace76617e0d1`；scoped **61** passed；ruff/mypy **PASS**）；**STM-012** **completed**（PR #35 MERGED `d73207752bbf004a4b20bf8fff00720cc0ca456b` mergedAt `2026-08-11T15:20:30Z`；implementation `26aa710d62123d341fb79349c9ad86fc5d58c0a6`；integration **1** passed；ruff/mypy **PASS**；production_delta **NONE**）；**EXT-002** **completed**（PR #36 MERGED `59e9f7f0cf6effd34d1f13ad022f9b9eb00b8f2d`）；**EXT-003** **completed**（PR #37 MERGED `0eb45e20c64777a03dc770be70cba2316b47fdf6` mergedAt `2026-08-12T06:06:31Z`；implementation `7c6309ee68b01a6604b79253cea65be6fa26a0c6`；scoped **63** passed；ruff/mypy **PASS**）；**EXT-004** **completed**（PR #38 MERGED `229f5e960f51e55a7389599eeccdf650a9a7beff` mergedAt `2026-08-12T07:49:18Z`；implementation `0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c`；scoped **53** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2；read-only Neo4j alignment only；feat 分支已删）；**EXT-005** **completed**（PR #39 MERGED `638598080b2d24e9291933c5ef92d3e4d65a0612` mergedAt `2026-08-12T09:47:46Z`；implementation `c6e619d312bfd83fef30c9f394e16b42a65cba81`；record `775992943ae0eb349301defb990c59c7089cf32e`；scoped **63** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=0；zero Mongo/Neo4j writes；MF-001/SF-001–SF-004；feat 分支已删）；**EXT-006** **completed**（PR #40 MERGED `372e0232c1e5cfa1d71e2bb0152a22f59e60cd03` mergedAt `2026-08-12T12:12:38Z`；implementation `b19e913af3848e932b8adb404dc5d5304167fb73`；record `eafc07a3e01f376f4bd2c6c658c1dd5536c3b61f`；scoped **44** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2 non-blocking；atomic Neo4j graph write + `index_sync_memory_set` handoff；zero task completed/offset；OI-006 non-blocking；feat 分支已删）；**EXT-007** **completed**（PR #41 MERGED `afb2fee9ca6f7a5e049f0d9b1b22825de4c665dd` mergedAt `2026-08-12T13:27:51Z`；implementation `2cf93ec5bcb03daae6e266984df2804a09f19a0c`；record `d385f4b3553d310f89b17e832ea07c29b50d9761`；scoped **30** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=2 non-blocking；§2.2.3 index sync + ES bulk upsert + first `mark_completed` gate；completed-before-offset gate preserved；zero upstream/offset diff；OI-006 non-blocking；feat 分支已删）；**EXT-008** **completed**（PR #42 MERGED `8bee66be25e140cd59a8dd74faa733211ab44382` mergedAt `2026-08-12T14:07:04Z`；implementation `e8f15b458a6f1fa6e204393d5300a018bfc5c27b`；record `eefb52edea62c1d1a917f2393ff157c64421a2b0`；scoped **25** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=3 non-blocking；GET/retry/rebuild Admin HTTP；OI-006 **resolved_by_task**；LD-3 Mongo before Kafka；zero consumer/worker/pipeline diff；feat 分支已删）；**EXT-009** prerequisites **SATISFIED**（EXT-008 **completed**）— **planned / NOT AUTO-STARTED**；**不得触碰 DEV-006/PR#13**。

## 实施前置条件

| ID | 项 | 说明 | 状态 |
|---|---|---|---|
| PRE-ENV-001 | 缺少 `uv` | DEV-001 **实施编码前**必须安装 `uv` | satisfied（uv 0.12.2） |
| PRE-ENV-002 | 主机 Python 3.13.9 | DEV-001 **实施编码前**必须使用 Python 3.12.13（经 uv） | satisfied（uv python find 3.12.13 成功；.venv 为 3.12.13） |

## 规格歧义

见 `02_开发管理/open_issues.md`。OI-009、OI-010、**OI-011**、**OI-012** 为 `resolved`；未解决项不得自行解释为新 Contract。

**EXT-004 阻塞歧义**：~~OI-EXT-004-001/002 blocking~~ → Round 2 **已闭合**（Task Plan Amendment 002 MVP_LOCAL_DECISION；`resolved_by_plan`）。**OI-EXT-004-003**（归一化 micro-semantics）与 **OI-EXT-004-004**（`canonical_name` 替换、用户实体别名）已在 Task Plan 固定字面读法，非阻塞。

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
| 2026-08-15 08:45 UTC | DEV-010 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #61 MERGED `29e4a3d7d747d2ec80d4a345da55e70f11076cf1` mergedAt `2026-08-15T08:41:28Z`；ff-only 同步 main；main 含 merge `29e4a3d`、implementation `7bf341ee7cd988d5a1f728ad138c38bbc4f31932`、record `83f3443aff413b458c900c3f59ee4a63384676bc`；仅更新 DEV-010 三份治理文件并创建 `docs(status): complete DEV-010 after PR merge`；exact feat 已删；未 git tag；`next_action=DEV-010 completed — NO AUTO-START`；REL-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 08:40 UTC | DEV-010 | reviewed → committed | Release Operator IMPLEMENTATION_RELEASE on feat；implementation `7bf341ee7cd988d5a1f728ad138c38bbc4f31932`；PR #61 OPEN https://github.com/xu-jia-ming/memory_system/pull/61；base=main head=feat/DEV-010-siliconflow-embedding-token-estimation-routing；`docs(status): record` 同 feat 不推 main；REL-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 08:30 UTC | DEV-010 | tested → reviewed | CODE_REVIEW_APPROVED session 93de8d64-bcaf-478c-8c57-f0c77c8e8670；P0=0 P1=0 P3=2；Commit Recorder READY_FOR_HUMAN_COMMIT session 44cb5320-381f-4ebe-95ac-b46b9f74c9ab；implementation_commit=null until feat `git rev-parse`；`next_action=IMPLEMENTATION_RELEASE`；REL-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 08:25 UTC | DEV-010 | in_progress → implemented → tested | Developer：spec 六处 delta + `create_tokenize_client` + HeuristicTokenCountAdapter + 两处生产接线 + SHOULD_FIX RET runtime/C1；unit+contract **18 passed**；ruff PASS；mypy src 0；focused regression **56 passed**；未 Git commit；`next_action=CODE_REVIEW`；REL-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 08:11 UTC | DEV-010 | approved → in_progress | Developer on exact feat `feat/DEV-010-siliconflow-embedding-token-estimation-routing` HEAD `a55f99167863f508ef09033e13134348ab5e8b60`；persist `developer_authorized=true`；吸收 SHOULD_FIX Step 0（RET runtime assertion + C1 import tighten）；无 Git 写；`next_action=implement whitelist then Code Review`；REL-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 08:06 UTC | DEV-010 | planned → approved / PLAN_LANDING | Human PLAN_APPROVED 2026-08-15 08:03 UTC；Round 1 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=2（实施 Step 0，本 phase 无 Amendment）；`human_plan_approved=true`；`developer_authorized=false` until feat exists；Release Operator PLAN_LANDING docs(plan) on main then create `feat/DEV-010-siliconflow-embedding-token-estimation-routing`；`next_action=Developer on feat after PLAN_LANDING`；未实施；REL-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 07:50 UTC | DEV-010 | NOT AUTO-STARTED → planned | Planner 创建 Task Plan `02_开发管理/tasks/DEV-010-siliconflow-embedding-token-estimation-routing.md`；用户显式 NEW_UNPLANNED_FEATURE（workflow_mode=NORMAL explicit）；baseline `fc3fbd0fdc410aef2e21e6e3932cc6b9f7560a8a` MATCH；git status 规划前 clean；最小 spec delta + provider-aware tokenize 路由；`changes_technical_spec=true`；不单独 OI-013；`approval_posture=AWAIT_PLAN_REVIEW`；`next_action=计划审查`；`human_plan_approved=false`；`developer_authorized=false`；不得 PLAN_LANDING/实施本轮；REL-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 06:05 UTC | REL-001 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #60 MERGED `4e8ceff74b95880b1c035d518bf2be43d2bbc907` mergedAt `2026-08-15T06:01:06Z`；ff-only 同步 main；main 含 merge `4e8ceff` 与 implementation `703bb105`；仅更新 REL-001 三份治理文件并创建 `docs(status): complete REL-001 after PR merge`；exact feat 已删；未 git tag；未勾 A.1；清单 F.Git干净保持未勾（POST_MERGE 不 add 清单；POST_MERGE 后工作树干净）；`next_action=本任务完成 / NOT AUTO-STARTED`（Phase 5 无后续 Task）；HUMAN `v0.9.0-mvp-rc1` 仅人工 tag（建议对象 `412fb7b858120927aecad63962990587038df340`）；`v1.0.0-mvp` 不得创建（A.1 Preflight 仍未勾）；E2E-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 04:50 UTC | REL-001 | approved → in_progress → implemented → tested | Developer exact feat `feat/REL-001-mvp-rc-review-acceptance-checklist` HEAD `04c4a7e8`；吸收 SHOULD_FIX=5；Preflight `--mode=cpu` exit 1（`vm.max_map_count`）A.1 未勾；ruff PASS / mypy src 0；清单除 A.1/F.Git干净/F.Review 外已按证据勾选；未 git tag；未改 src/tests；`next_action=Code Review`；E2E-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 04:25 UTC | REL-001 | planned → approved / PLAN_LANDING | Human PLAN_APPROVED；Round 1 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=5（实施 Step 0，本 phase 无 Amendment）；`human_plan_approved=true`；`developer_authorized=false` until feat exists；Release Operator PLAN_LANDING docs(plan) on main then create `feat/REL-001-mvp-rc-review-acceptance-checklist`；`next_action=PLAN_LANDING`；未实施；E2E-001 completed 事实不变；不得触碰 DEV-006/PR#13 |
| 2026-08-15 04:15 UTC | REL-001 | NOT AUTO-STARTED → planned | Planner 创建 Task Plan `02_开发管理/tasks/REL-001-mvp-rc-review-acceptance-checklist.md`；人类 START_EXISTING_TASK 覆盖 E2E-001 `next_action=REL-001 planned / NOT AUTO-STARTED`；baseline `412fb7b858120927aecad63962990587038df340` MATCH；git status 规划前 clean；RC Review + 清单证据化；`production_file_whitelist=NONE`；`test_file_whitelist=NONE`；tag HALT/人工；`approval_posture=AWAIT_PLAN_REVIEW`；`next_action=计划审查`；`human_plan_approved=false`；`developer_authorized=false`；不得 PLAN_LANDING/实施本轮；不得触碰 DEV-006/PR#13 |
| 2026-08-15 03:55 UTC | E2E-001 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #59 MERGED `43b6975a5dc4a92cde2f898acacd73a508831a48` mergedAt `2026-08-15T03:53:42Z`；ff-only 同步 main；main 含 merge `43b6975` 与 implementation `4a44e99`；仅更新 E2E-001 三份治理文件并创建 `docs(status): complete E2E-001 after PR merge`；exact feat 已删；`next_action=REL-001 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13；不得自动启动 REL-001 |
| 2026-08-15 02:38 UTC | E2E-001 | planned → approved / PLAN_LANDING | Human PLAN_APPROVED；Round 2 PLAN_APPROVED（session 20220a4e-dd78-4a44-b130-9eeec0b11d74；BLOCKER=0 MUST_FIX=0）；Amendment 001 absorbed；`human_plan_approved=true`；`developer_authorized=false` until feat exists；Release Operator PLAN_LANDING docs(plan) on main then create `feat/E2E-001-full-chain-e2e-failure-injection`；next_action=Developer on feat after this phase；未实施 | 未运行（规划-only） | OPS-004 completed records unchanged；不得触碰 DEV-006/PR#13 |
| 2026-08-15 02:25 UTC | E2E-001 | planned (Amendment 001 / Round 2) | Round 1 PLAN_REJECTED（session 570cb388；BLOCKER=0 MUST_FIX=3）修订：MF-1 INJ-1 §1.2.6 #10/I-I（Mongo Archive 保存点，不要求 WM 仍持消息）；MF-2 HP Compression succeeded + compressed_context；MF-3 INJ-5 两次 close（503 closing → 200 closed）；SF-1 生产 ES wrap；SF-2 INJ-4 F1 二次 run_worker_once；SF-3 SIGTERM lag=0；SF-4 -v 起止；SF-5 PLAN_LANDING 后才 Developer；SF-6 白名单 §12；SF-8 mypy src only；未实施、未 Git 写 | 未运行（规划-only） | `plan_review_round=2`；`next_action=计划审查`；`human_plan_approved=false`；Developer NOT authorized；不得触碰 DEV-006/PR#13 |
| 2026-08-15 02:10 UTC | E2E-001 | NOT AUTO-STARTED → planned | Planner 创建 Task Plan `02_开发管理/tasks/E2E-001-full-chain-e2e-failure-injection.md`；人类 START_EXISTING_TASK 覆盖 OPS-004 `next_action=E2E-001 planned / NOT AUTO-STARTED`；baseline `bb0d387f509c38194cf511f580b98cf86f44b5a7` MATCH；git status clean；组合 STM-013/EXT-009/RET-006/CON-005 为 §3.32 #4 全链；§3.28 五条失败注入；`production_file_whitelist=NONE`；不扩 OPS-004 CI；不吸收 REL-001；`approval_posture=AWAIT_PLAN_REVIEW`；`next_action=计划审查`；Developer NOT authorized；不得触碰 DEV-006/PR#13 |
| 2026-08-15 02:00 UTC | OPS-004 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #58 MERGED `3e6f8fa2b7c1bf36a332e28f027fe79445bcf1ec` mergedAt `2026-08-15T01:56:08Z`；ff-only 同步 main；CI GREEN 1399 unit+contract / 246 integration（run 31857428972）；exact feat 已删；`next_action=E2E-001 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13；不得自动启动 E2E-001 |
| 2026-08-15 01:40 UTC | OPS-004 | committed (CI hotfix) | PR #58：pytest_plugins 不得加载 test_*.py；EXT-002 改加载 mongo_kafka_fixtures（无 autouse）；避免 migrate/OPS-003 down -v 后 stale Mongo ping；契约扫描回归 | unit/contract scoped | 待 push 后等 CI；不得触碰 DEV-006/PR#13 |
| 2026-08-14 07:55 UTC | OPS-004 | planned (Amendment 002) → tested | Amendment 002：`uv run mypy src` CI scope；BL-RUFF-001 8-file ruff auto-fix；ruff/mypy src PASS；1395 pass / 91.26% cov；9 C-OPS4 PASS；merge_gate static+unit PASS | 未 Git 写 | `next_action=Code Reviewer`；不得触碰 DEV-006/PR#13 |
| 2026-08-14 07:47 UTC | OPS-004 | tested → planned (Amendment 002) | CODE_REVIEW_REJECTED P1-1 — CI static job ruff/mypy baseline debt；Amendment 002：`uv run mypy src` CI scope + BL-RUFF-001 8-file whitelist auto-fix + BL-MYPY-001 DEFERRED | 未实施 | `next_action=DEVELOPER_RESUME Amendment 002`；不得触碰 DEV-006/PR#13 |
| 2026-08-14 06:06 UTC | OPS-004 | approved → PLAN_LANDING | Release Operator PLAN_LANDING；plan_commit `4d5d519` on main；push via 17890 proxy；feat `feat/OPS-004-ci-gates-coverage-threshold` created @ 4d5d519 | 未实施 | 不得触碰 DEV-006/PR#13 |
| 2026-08-14 04:05 UTC | OPS-003 | approved → PLAN_LANDING | Release Operator PLAN_LANDING；plan_commit `6d007ea` on main；push via 17890 proxy；feat `feat/OPS-003-full-migration-compose-blank-environment-validation` created @ 6d007ea | 未实施 | 不得触碰 DEV-006/PR#13 |
| 2026-08-14 04:30 UTC | OPS-003 | tested → committed | IMPLEMENTATION_RELEASE；implementation `978ae9c` pushed feat；docs(status): record on feat | scoped 53 pass / 1 skip | WAITING_FOR_PR_MERGE；禁 push main |
| 2026-08-14 04:32 UTC | OPS-003 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `978ae9ccaf80a87c772a6691a7f1b66db2b3c846`、record `815da73b4207c4972d19a7de59b9c3ff4c28c902`、merge `89912ec53d802dc527a32e3c132737c01197897f`；仅更新 OPS-003 三份治理文件并创建 `docs(status): complete OPS-003 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0；BLANK-ENV-001 `--embedding=none`；production NONE；scoped 53 pass / 1 skip；ruff/mypy PASS；`next_action=OPS-004 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-14 10:29 UTC | OPS-002 | planned (Amendment 001) | Round 1 PLAN_REJECTED 修订：MF-1 `api/app.py`；MF-2 F-006 方案 A（7-file HARD_BLOCK inventory + 4-file DEFERRED）；SF-1 MET-AUDIT-001 解释 A；SF-2 F-007 optional；SF-3 scoped test commands；SF-4 structlog rationale；未实施 | MUST_FIX #1/#2 + SHOULD_FIX 已落实；`next_action=计划审查 Round 2`；不得触碰 DEV-006/PR#13 |
| 2026-08-14 02:17 UTC | OPS-002 | NOT AUTO-STARTED → planned | Planner 创建 Task Plan；preliminary Findings §12；同步 progress/master_plan 规划态；baseline `c7011aa` MATCH | `approval_posture=AWAIT_PLAN_REVIEW`；`next_action=计划审查`；Developer NOT authorized；不得触碰 DEV-006/PR#13 |
| 2026-08-14 10:04 UTC | OPS-001 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `61afe0d9fc44116e8a8f08b1058840a3d3f4701c`、record `70b5084cc67251dbfb193459b3840a6fb52141e7`、merge `9749bd6a86d94919daf4a59be4035872d070fe1e`；仅更新 OPS-001 三份治理文件并创建 `docs(status): complete OPS-001 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED R2 P0=0/P1=0/P2=2/P3=2 non-blocking；F-008/F-011 shared 270s budget；scoped 20 unit + entrypoint regression passed；ruff/mypy PASS；Amendment 001；`next_action=OPS-002 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-14 10:00 UTC | OPS-001 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `61afe0d9fc44116e8a8f08b1058840a3d3f4701c`；docs(status): record on feat | scoped 20 OPS-001 unit + entrypoint regression passed；ruff/mypy PASS；CODE_REVIEW_APPROVED R2 P0=0 P1=0；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；不得触碰 DEV-006/PR#13 |
| 2026-08-14 00:45 UTC | OPS-001 | planned (Amendment 001) | Round 1 PLAN_REJECTED 修订：§5.1 共享 270s 总预算；F-008 consumer 白名单；F-011 current_run_task+mutex；U10a/b/c/U12/U13；未实施 | MUST_FIX #1/#2 + SHOULD_FIX 已落实；`next_action=计划审查` Round 2 |
| 2026-08-14 09:11 UTC | OPS-001 | approved → PLAN_LANDING | Release Operator PLAN_LANDING；plan_commit `1ce8b65` on main；push via 17890 proxy；feat `feat/OPS-001-graceful-shutdown-pools-timeout-retry` created @ 1ce8b65 | 未实施 | 不得触碰 DEV-006/PR#13 |
| 2026-08-13 23:40 UTC | CON-005 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `a8625ea81f21a686f2c84a0a9e204e313c4e95c9`、record `7875e92feb417e6e9705c90396ba6e7d5d2e3034`、merge `8427868a2448fe11c9af64e3faedf5752badf8e9`；仅更新 CON-005 三份治理文件并创建 `docs(status): complete CON-005 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED R2 P0=0/P1=0/P2=0/P3=3 non-blocking；production src/** diff=NONE；real Neo4j INT 6 + E2E 6 + CON-001..004 regression 92 passed；Amendment 001 recovery semantics preserved（Run A@T1 partial+fail；Run B@T2>T1 full rescan；T1 rows re-eligible；last_consolidated_time=T2；no checkpoint）；closes `v0.5.0-consolidation` milestone ONLY；`next_action=OPS-001 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 23:30 UTC | CON-005 | tested → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `a8625ea81f21a686f2c84a0a9e204e313c4e95c9`；PR #54 OPEN；docs(status): record on feat | scoped INT 6 + E2E 6 + contract 4 + unit 92 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0/P1=0/P2=0/P3=3；零 src/** diff；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；不得触碰 DEV-006/PR#13 |
| 2026-08-13 22:55 UTC | CON-005 | approved → tested | Developer Steps 1-7；§12 九文件；INT-1..6 + E2E-1..6 green；CON-001..004 unit 92 passed；contract/ruff/mypy PASS；零 src/** diff | `next_action=Code Reviewer on feat/CON-005-consolidation-integration-e2e`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 14:37 UTC | CON-005 | planned → approved | Human PLAN_APPROVED; Release Operator `PLAN_LANDING`; docs(plan) on main; feat `feat/CON-005-consolidation-integration-e2e` created | `approval_posture=PLAN_APPROVED`; `next_action=Developer on feat/CON-005-consolidation-integration-e2e`; Developer authorized post-PLAN_LANDING; 不得触碰 DEV-006/PR#13 |
| 2026-08-13 14:45 UTC | CON-005 | planned (amendment round 2) | Planner Amendment 001 — MF-1 E2E-6/INJ-7 option 1（Run B@T2>T1；T1 行再 eligible；§6.3 十断言）；SF-1..SF-5（INT 标题、pytest_plugins、CON-004 §15 取代边界、MV-4 invalid_memory_count、mypy 全模块）；无规格变更；`approval_posture=AWAIT_PLAN_REVIEW`；`next_action=计划审查`；Developer NOT authorized |
| 2026-08-13 22:15 UTC | CON-005 | NOT AUTO-STARTED → planned | Planner 创建 Task Plan `02_开发管理/tasks/CON-005-consolidation-integration-e2e.md`；同步 progress/master_plan 规划态字段；baseline `010d74112fb760907e710f2ba27123e021dd3d61` MATCH；git status clean；§2.3.11–13 consolidation vertical slice Integration+E2E（Neo4j-only；in-process ConsolidationRunService 生产接线；INT-1..6 + E2E-1..6）；`production_file_whitelist=NONE`；APScheduler E2E deferred（CON-004 unit 足够）；closes `v0.5.0-consolidation` on POST_MERGE_CLEANUP；`approval_posture=AWAIT_PLAN_REVIEW`；`next_action=计划审查`；Developer NOT authorized；不得触碰 DEV-006/PR#13 |
| 2026-08-13 22:00 UTC | CON-004 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `abb2ceaf6579f9dfff9e46f4782d3d9d181d31c1`、merge `ae70a94fd08382ffd43fbdc0e64ec613423fc403`；仅更新 CON-004 三份治理文件并创建 `docs(status): complete CON-004 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=1 non-blocking（P2-1 C1 untracked blind spot；P2-2 Prometheus failure-path assertions；P3-1 telemetry naming）；scoped 37 passed；ruff/mypy PASS；§2.3.11 run orchestration — one evaluation_time per run；process-local mutex/finally release；per-user cursor orchestration；non-fatal version conflicts；no persistent cursor/run-state；zero CON-001/002/003 semantics diff；`next_action=CON-005 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 11:30 UTC | CON-003 | NOT AUTO-STARTED → planned | Planner 创建 Task Plan `02_开发管理/tasks/CON-003-optimistic-lock-batch-update.md`；同步 progress/master_plan 规划态字段；baseline `cabcc6f98e5cd676b962b49e3b0c943587a11689` MATCH；git status clean；§2.3.9 optimistic-lock batch write（importance + last_consolidated_time only；不递增 memory_version；不写 updated_time）；CON-002 scored handoff only；Integration DEFERRED CON-005；`approval_posture=AWAIT_PLAN_REVIEW`；`next_action=计划审查`；Developer NOT authorized；不得触碰 DEV-006/PR#13 |
| 2026-08-13 19:20 UTC | CON-002 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `a13ab31bb98598740198001d8bfee3f21d6b565a`、merge `3b26549c41b91a1bbdd72237865a5d3d4fb5324d`；仅更新 CON-002 三份治理文件并创建 `docs(status): complete CON-002 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=2 non-blocking（P2-1 C1 untracked blind spot；P2-2 null archive_id test gap）；scoped 39 passed；ruff/mypy PASS；§2.3.4 read-only + per-user isolation + `count(DISTINCT archive_id)` + zero-Evidence→missing_evidence；零 durable write；`next_action=CON-003 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 18:55 UTC | CON-002 | approved → tested | Developer implementation on `feat/CON-002-cursor-batch-evidence-count`；3 生产 + 3 测试白名单文件；§2.3.4 cursor batch Neo4j read + `independent_archive_count` + CON-001 handoff | scoped **39 passed**；ruff PASS；mypy PASS（3 new src files）；零 durable write；OPTIONAL MATCH 零 Evidence；U13-U15 pagination metadata；`next_action=CODE_REVIEW`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 10:30 UTC | CON-001 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `41932b93431e43fa1d134cfed76dfedb9ec7f363`、record `bef3ae23e8b12592cbdfcfb563654fb91c97cea2`、merge `e9469d8ee61d363d7367a9b17ca2680794ce39f0`；仅更新 CON-001 三份治理文件并创建 `docs(status): complete CON-001 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=1/P3=2 non-blocking；scoped 49 passed；ruff/mypy PASS；§2.3.5–2.3.7 consolidation importance pure functions；零 durable I/O；`next_action=CON-002 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 10:02 UTC | CON-001 | tested → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `41932b93431e43fa1d134cfed76dfedb9ec7f363`；PR #50 OPEN；docs(status): record on feat | scoped 49 passed；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；零 durable I/O；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；不得触碰 DEV-006/PR#13 |
| 2026-08-13 09:40 UTC | CON-001 | planned → approved | Human PLAN_APPROVED; Release Operator `PLAN_LANDING`; docs(plan) on main; feat `feat/CON-001-importance-decay-protection-formulas` created | `approval_posture=PLAN_APPROVED`; `next_action=Developer on feat/CON-001-importance-decay-protection-formulas`; Developer NOT authorized until in_progress; 不得触碰 DEV-006/PR#13 |
| 2026-08-13 08:57 UTC | CON-001 | planned | Planner created `02_开发管理/tasks/CON-001-importance-decay-protection-formulas.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `2159ad6cc5e3f31365677671d9588c69b776e8a0` verified (main, clean tree); scope = §2.3.5–2.3.7 importance/decay/protection pure functions; `durable_read_scope=NONE`; `durable_write_scope=NONE`; `missing_evidence` skip semantics; determinism; `dependency_changes_expected=NONE`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-13 08:50 UTC | RET-006 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `6e5517c11f0c7b6417264064d718937dd0aca62b`、record `4637279313e2fac61b986bbe45be8dfb847318b2`、merge `295c5faa3b0160db349b926dc8eb0a001d67c7ce`；仅更新 RET-006 三份治理文件并创建 `docs(status): complete RET-006 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=1/P3=2 non-blocking；scoped 9 passed（E2E-1,2,3,4a,4b,5a,5b,6 + auth）；零 src/** diff；closes `v0.4.0-memory-retrieval` milestone；`next_action=CON-001 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 08:45 UTC | RET-006 | tested → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `6e5517c11f0c7b6417264064d718937dd0aca62b`；PR #49 OPEN；docs(status): record on feat | scoped 9 passed；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；零 src/** diff；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；不得触碰 DEV-006/PR#13 |
| 2026-08-13 08:08 UTC | RET-006 | planned → approved | Human PLAN_APPROVED Round 2；Release Operator `PLAN_LANDING`；docs(plan) on main；feat `feat/RET-006-retrieval-e2e-failure-injection` created | Round 2 PLAN_APPROVED MF-1/SF-1；E2E-4a/4b + INJ-1..6；`next_action=Developer on feat/RET-006-retrieval-e2e-failure-injection`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 07:48 UTC | RET-005 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `9baf16a7c6f7b0ad3cec8155b54c9fdeeb8c4250`、merge `5b577d6e04c8b1e0a7336169a18855c66e4a2a3a`；仅更新 RET-005 四份治理文件并创建 `docs(status): complete RET-005 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=3/P3=2 non-blocking；scoped 48 passed（unit 34 + contract 8 + integration HTTP 8）；§2.2.5 HTTP Retrieval API + §2.2.13 Neo4j stats + §2.2.15 degradation/timeout；OI-008 resolved_by_task（canonical DR-1..DR-10）；零 RET-001..004 production semantic diff；`next_action=RET-006 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 16:00 UTC | RET-005 | tested (P2 remediation) | Developer：P2-1 ruff import/E501；P2-2 `validate_retrieval_input` 返回 canonical stripped `user_id` 并全链路传播；P2-3 vector search 包裹 `_await_with_deadline` | scoped **48 passed**；ruff PASS；未 Git commit；`next_action=代码审查` |
| 2026-08-13 15:30 UTC | RET-005 | planned → tested | Developer：§15 生产 7 文件 + §16 测试 8 文件；`POST /api/v1/memory/retrieval` + `RetrievalApiService` 编排（tokenize gate、bypass HybridRetrievalService.search、超时降级、Neo4j stats） | scoped **48 passed**（unit 34 + contract 8 + integration HTTP 8）；RET-001..004 unit regression **34 passed**；ruff/mypy PASS；Neo4j I3 integration 需 compose 网络（本环境 DNS 未解析 neo4j）；未 Git commit；`next_action=代码审查`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 07:00 UTC | RET-005 | planned | Planner created `02_开发管理/tasks/RET-005-retrieval-api-degradation-statistics.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `c086b9953829d0ca19e930cde9b1c64dadde5fb9` verified (main, clean tree); scope = §2.2.5 HTTP Retrieval API + §2.2.12 Response DTO + §2.2.13 Neo4j stats + §2.2.15 degradation/timeout; OI-008 canonical DR-1..DR-10 `resolved_by_plan`; `dependency_changes_expected=NONE`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-13 06:48 UTC | RET-004 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 已通过 `--ff-only` 同步；验证 main 包含 implementation `e631d206b26175d341602ffdfd42a3d8f43edd3f`、merge `f505c25572f5695a772ac8598be9c8602b36aa9e`；仅更新 RET-004 三份治理文件并创建 `docs(status): complete RET-004 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=2 non-blocking；scoped 52 passed（unit 47 + integration 5）；§2.2.11 ACT-R scoring；Top-K before Evidence；Evidence does not affect final_score；零 durable write；`next_action=RET-005 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 14:30 UTC | RET-004 | approved → tested | Developer：白名单 5 生产 + 6 测试文件；ACT-R 纯函数 + Evidence 聚合 + 编排服务 + Neo4j Evidence 读仓储 | scoped unit **44 passed**；ruff/mypy PASS；integration I1-I5 待 Neo4j compose；plan_commit=e3e98ee；零 durable write；未 Git commit；`next_action=代码审查`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 06:01 UTC | RET-004 | planned | Planner created `02_开发管理/tasks/RET-004-act-r-scoring-evidence-aggregation.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `c8d9d38d92414b9e041dd3d97dcbfd17b9e61582` verified (main, clean tree); scope = §2.2.11 ACT-R scoring + §2.2.12 Evidence batch aggregation; consume RET-003 AuthoritativeRecallSuccess; new `act_r_scoring` + `retrieval_scoring_service` + `retrieval_evidence_read_repository`（禁止混用 EXT-005）；Integration Neo4j Evidence Fixture; `dependency_changes_expected=NONE`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-13 13:04 UTC | RET-003 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 领先本地 main，已通过 `--ff-only` 同步；验证 main 包含 implementation `64f71690d6c7ac08762b45d76a34158b49570e24`、merge `3746f1bce38b4f6e4c0ab4d7899eff5622cc21c0`；仅更新 RET-003 三份治理文件并创建 `docs(status): complete RET-003 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=2 non-blocking；scoped 53 passed（30 RET-003 unit + 7 integration + 16 RET-002 regression）；§2.2.10 Neo4j authoritative recall + one-hop expansion + ES MGET read-only internal path；新建 `retrieval_memory_read_repository` + `mget_retrieval_repository`；Integration Neo4j+ES Fixture；`next_action=RET-004 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 11:50 UTC | RET-003 | planned | Planner created `02_开发管理/tasks/RET-003-neo4j-graph-expansion-mget.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `21a99a5b217f45cd4e4c67b8758bf1705d9d0a74` verified (main, clean tree); scope = §2.2.10 Neo4j authoritative recall + one-hop expansion + ES MGET; consume RET-002 HybridRetrievalSuccess; new `retrieval_memory_read_repository` + `mget_retrieval_repository`（禁止混用 EXT-007 扩展语义）; Integration Neo4j+ES Fixture; `dependency_changes_expected=NONE`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-13 03:15 UTC | RET-002 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 领先本地 main，已通过 `--ff-only` 同步；验证 main 包含 implementation `3bf3a1b760080d4f581ab53dad0961a28dfb63a4`、merge `2bfc2b2ddbd5ef69a2a3f473722b32a9ead3d461`；仅更新 RET-002 三份治理文件并创建 `docs(status): complete RET-002 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=1 non-blocking；scoped 71 passed（31 RET-002 unit + 7 integration + 33 RET-001 regression）；§2.2.6/§2.2.8/§2.2.9 Vector+RRF internal path；共享 `retrieval_filter_builder`；Integration ES Fixture + Fake embed；`next_action=RET-003 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 03:01 UTC | RET-002 | approved → tested | Developer：Vector kNN + RRF fusion + Hybrid 并行编排；共享 `retrieval_filter_builder`；BM25 repository 零语义变更 | scoped **71 passed**（31 RET-002 unit + 7 integration + 33 RET-001 regression）；ruff/mypy PASS；未 Git 写；`next_action=代码审查`；不得触碰 DEV-006/PR#13 |
| 2026-08-13 02:40 UTC | RET-002 | planned | Planner created `02_开发管理/tasks/RET-002-vector-retrieval-rrf.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `e5f5c9de9883d04759f19080c01f1f50d2c62513` verified (main, clean tree); scope = §2.2.6 retrieval-path query norm + embed, §2.2.8 Vector kNN, §2.2.9 RRF fusion; reuse RET-001 BM25 + DEV-007 EmbeddingClient; shared filter builder; Integration ES Fixture + Fake embed; LD-1 no local token pre-check on SiliconFlow; `dependency_changes_expected=NONE`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-13 02:30 UTC | RET-001 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；fetch 后 origin/main 领先本地 main，已通过 `--ff-only` 同步；验证 main 包含 implementation `fc435db722ed29c05980d6a1a60d9f57fda80968`、merge `a4dda57366b9e0cb2a1fb34b6526a07daa30ed31`；仅更新 RET-001 三份治理文件并创建 `docs(status): complete RET-001 after PR merge`；exact feat 分支已删 | CODE_REVIEW_APPROVED P0=0/P1=0/P2=2/P3=2 non-blocking；scoped 33 passed（25 unit + 8 integration）；§2.2.7 BM25 internal channel read-only；Integration ES Fixture not EXT-007 pipeline；`next_action=RET-002 planned / NOT AUTO-STARTED`；不得触碰 DEV-006/PR#13 |
| 2026-08-12 14:47 UTC | EXT-009 | planned → in_progress | Developer：新建 `ProductionExtractionPipeline`，接线 extraction worker，consumer 增加 LD-1 terminal reload；新增 pipeline/consumer unit、contract、compose integration、E2E-1..4 测试与 Fake provider helpers；吸收 SF-1 同轮 reload/fall-through 与 SF-2 injectable F1 hook、SF-3 ASGI Admin auth | 首轮 scoped pipeline/consumer/contract 通过；worker 旧测试暴露的未初始化 consumer 已修复待复跑；compose/E2E 尚待环境验证；EXT-002..007 与 `PipelineTerminalDecision` 零 diff；未 Git 写；`next_action=实现`；不得触碰 DEV-006/PR#13 |
| 2026-08-12 15:03 UTC | EXT-009 | in_progress → tested | 完成 pipeline/worker/consumer 接线、SF-1 同轮 fall-through、SF-2 F1 hook、SF-3 ASGI Admin auth；补齐共享 Kafka producer 与 integration 本地 fixture 包装 | scoped unit/contract/worker **35 passed**（4 个既有 AsyncMock warning）；compose integration **1 passed**；E2E-1..4 **4 passed**；Ruff PASS；Mypy（3 个 changed production modules）PASS；IDE lints clean；combined collection **5 collected**；未 Git 写；不得触碰 DEV-006/PR#13；`next_action=代码审查` |
| 2026-08-13 00:26 UTC | EXT-009 | tested → in_progress | Developer：处理当前 Code Review 两项 finding；修复 Task Plan YAML 缩进，收紧 COMPLETE/FAIL terminal reload 异常为 fail-closed，并补充 focused tests | — | 不改 PipelineTerminalDecision、EXT-007 terminal ownership、Kafka offset、阶段内部或生产 scope；未 Git 写；`next_action=实现` |
| 2026-08-13 00:30 UTC | EXT-009 | in_progress → implemented | terminal reload 异常经 `TerminalPersistError` 链式传播；focused tests 覆盖 COMPLETE/FAIL 的 expected-terminal、non-terminal、TypeError、repository exception；Task Plan YAML 已可解析 | terminal idempotency **10 passed**；YAML parse PASS；Ruff PASS；Mypy PASS；IDE lints clean；EXT-009 scoped suite 验证中；未 Git 写；`next_action=验证` |
| 2026-08-13 00:32 UTC | EXT-009 | implemented → tested | 完成两项 Code Review remediation：Task Plan YAML 缩进修复；COMPLETE/FAIL reload 异常 fail-closed 并保留 cause；未改生产 scope 或终态/Offset contract | focused terminal idempotency **10 passed**；EXT-009 scoped **33 passed**；YAML parse PASS；full Ruff PASS；Mypy（remediation files）PASS；IDE lints clean；full-repository Mypy 143 baseline errors；legacy EXT-001 consumer unit 3 个旧 fixture failures 未修改（超出本轮窄白名单）；未 Git 写；`next_action=代码审查` |
| 2026-08-12 22:30 UTC | EXT-009 | planned | Planner created `02_开发管理/tasks/EXT-009-extraction-e2e-pipeline-wiring.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `779963257e33a93ad02ef4e3f997b3c9f6706802` verified (main, clean tree); scope = production pipeline wiring + worker + consumer LD-1 terminal idempotency + E2E-1..4; authoritative closure of EXT-003→EXT-007 DEFERRED_FOR_MVP; Fake LLM/embedding/tokenize; zero EXT-002..007 service diff; `dependency_changes_expected=NONE`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 14:10 UTC | EXT-008 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #42 MERGED (`8bee66be25e140cd59a8dd74faa733211ab44382` mergedAt `2026-08-12T14:07:04Z`)；implementation `e8f15b458a6f1fa6e204393d5300a018bfc5c27b`；record `eefb52edea62c1d1a917f2393ff157c64421a2b0`；feat 分支已删 | scoped 25 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=3 non-blocking；GET/retry/rebuild Admin HTTP；OI-006 resolved_by_task；LD-3 Mongo before Kafka；zero consumer/worker/pipeline diff；`next_action=EXT-009 planned / NOT AUTO-STARTED`；governance completion commit created |
| 2026-08-12 22:00 UTC | EXT-008 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `e8f15b458a6f1fa6e204393d5300a018bfc5c27b`；PR #42 OPEN；docs(status): record on feat | scoped 25 passed；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge** |
| 2026-08-12 21:40 UTC | EXT-008 | planned | Planner created `02_开发管理/tasks/EXT-008-extraction-admin-api.md`; synchronized progress/master_plan/open_issues only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `d55bf53e715378463243fcf80e49277e603c1bb5` verified (main, clean tree); scope = §2.1.14 GET/retry + OI-006 rebuild (LD-1); Mongo-only durable; STM-011 republish reuse; zero offset/consumer/worker/pipeline diff; OI-006 resolved_by_plan; `dependency_changes_expected=NONE`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 13:30 UTC | EXT-007 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #41 MERGED (`afb2fee9ca6f7a5e049f0d9b1b22825de4c665dd` mergedAt `2026-08-12T13:27:51Z`)；implementation `2cf93ec5bcb03daae6e266984df2804a09f19a0c`；record `d385f4b3553d310f89b17e832ea07c29b50d9761`；feat 分支已删 | scoped 30 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=2 non-blocking；§2.2.3 index sync invariants + completed-before-offset gate preserved；zero upstream/offset diff；OI-006 non-blocking；EXT-006→EXT-007 continuation DEFERRED_FOR_MVP；`next_action=EXT-008 planned / NOT AUTO-STARTED`；governance completion commit created |
| 2026-08-12 21:25 UTC | EXT-007 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `2cf93ec5bcb03daae6e266984df2804a09f19a0c`；PR #41 OPEN；docs(status): record on feat | scoped 30 passed；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge** |
| 2026-08-12 20:55 UTC | EXT-007 | planned | Planner created `02_开发管理/tasks/EXT-007-retrieval-document-sync.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `2db6f5a8957e26a672aa4fcba3bf69eb65b0de1e` verified (main, clean tree); scope = §2.2.3 full index sync + §2.2.4 ES document upsert; expand LD-8 handoff via Neo4j; TEI /tokenize for alias budget; create_embedding_client; mark_completed/failed; zero offset; zero upstream diff; `dependency_changes_expected=NONE`; non-blocking `OI-006`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 12:15 UTC | EXT-006 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #40 MERGED (`372e0232c1e5cfa1d71e2bb0152a22f59e60cd03` mergedAt `2026-08-12T12:12:38Z`)；implementation `b19e913af3848e932b8adb404dc5d5304167fb73`；record `eafc07a3e01f376f4bd2c6c658c1dd5536c3b61f`；completion `6b00287e663f96d0729a2474a678fa5e960cd051`；feat 分支已删 | scoped 44 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2 non-blocking；atomic Neo4j graph write + index_sync_memory_set handoff；zero task completed/offset；OI-006 non-blocking；EXT-003→EXT-006 continuation DEFERRED_FOR_MVP；`next_action=EXT-007 planned / NOT AUTO-STARTED`；governance completion commit created |
| 2026-08-12 18:10 UTC | EXT-006 | planned | Planner created `02_开发管理/tasks/EXT-006-neo4j-graph-transaction-write.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `59281d1e8d6e3fabfc0fe55f70b3fa50ac44bac2` verified (main, clean tree); scope = §2.1.13 steps 8–10 + atomic Neo4j write; §2.1.12 apply planned values; `index_sync_memory_set` handoff; `failed_stage=graph_write`; zero task completed/offset; EXT-003→EXT-006 continuation DEFERRED_FOR_MVP; `dependency_changes_expected=NONE`; non-blocking `OI-006`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 10:48 UTC | EXT-006 | planned → tested | Developer implemented graph write library on `feat/EXT-006-neo4j-graph-transaction-write`; 9 production + 7 test whitelist files; no commit | scoped **41** passed; ruff/mypy PASS; single Neo4j write transaction; Evidence MERGE idempotency + SKIP path; `index_sync_memory_set` handoff; task/offset untouched; upstream zero diff; `next_action=CODE_REVIEW` |
| 2026-08-12 09:10 UTC | EXT-005 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `c6e619d312bfd83fef30c9f394e16b42a65cba81`；PR #39 OPEN；docs(status): record on feat | scoped 63 passed；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge** |
| 2026-08-12 08:50 UTC | EXT-005 | approved → tested | Developer implemented whitelist (9 prod + 8 test); reconciliation read-only recall + LLM + plan builder; zero Mongo/Neo4j writes; upstream zero diff | scoped 63 passed; ruff/mypy PASS; integration Neo4j+Mongo PASS; `next_action=Code Review`; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 08:35 UTC | EXT-005 | planned → approved | Release Operator `PLAN_LANDING`；human PLAN_APPROVED Round 2 Amendment 001；docs(plan) on main；feat branch created | Round 2 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=0; MF-001/SF-001–SF-004; `next_action=Developer on feat/EXT-005-reconciliation-aggregation-gate`; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 16:30 UTC | EXT-005 | planned (Round 2) | Planner Amendment 001 remediation; §5.7–§5.11 MF-001 PlannedMemoryCreate self-contained output (`create_kind` + link fields); SF-001 normalization in `aligned_memory_key.py` only; SF-002 LLM SKIP excluded from aggregation; SF-003 session_id from task doc (not reconciliation output); SF-004 MERGE mixed null/non-null merged_content; no src/tests/spec-body change; no Git write | `next_action=计划审查 Round 2`; `approval_posture=AWAIT_PLAN_REVIEW_ROUND_2`; `plan_review_round=2`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 16:15 UTC | EXT-005 | planned | Planner created `02_开发管理/tasks/EXT-005-reconciliation-aggregation-gate.md`; synchronized progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `5deb8949ee5ac367a08f173ef67c0c0689c26f5d` verified (main, clean tree); scope = §2.1.11 read-only recall + LLM Reconciliation + aligned_memory_key + aggregation + reconciliation_plan_conflict; §2.1.12 planning output; §2.1.13 steps 1/6/7; transient plan for EXT-006; zero writes; `failed_stage=reconciliation`; EXT-004→EXT-005 continuation DEFERRED_FOR_MVP; `dependency_changes_expected=NONE`; non-blocking `OI-006`; `next_action=计划审查`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 15:53 UTC | EXT-004 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #38 MERGED (`229f5e960f51e55a7389599eeccdf650a9a7beff`)；implementation `0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c`；record `c975394369d2f0f64c973cc8aa701cded6b2c54d`；sha_backfill `22ff20af43dbb1ddd851ac5c1477aad30bb0c950`；completion `db8945596e316727ec35de20830db6c31c714dfc`；feat 分支已删 | scoped 53 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2 non-blocking；read-only Neo4j alignment only；OI-EXT-004-003/004 non-blocking；`next_action=EXT-005 planned / NOT AUTO-STARTED`；governance completion commit created |
| 2026-08-12 15:35 UTC | EXT-004 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c`；PR #38 OPEN；docs(status): record on feat | scoped 53 passed；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge** |
| 2026-08-12 14:50 UTC | EXT-004 | planned (Round 2) | Planner Amendment 002 remediation; §5.2.1/§5.2.2/§5.4.1/S4 Q3/same-batch entity_key/LD-9; OI-EXT-004-001/002 downgraded to `resolved_by_plan`; SAFE_AUTO_REMEDIATION recorded (progress duplicate `next_action` key → `historical_next_action_EXT-002`); no src/tests/spec-body change; no Git write | `next_action=计划审查 Round 2`; `approval_posture=AWAIT_PLAN_REVIEW_ROUND_2`; blocking Open Issues **none**; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 06:20 UTC | EXT-004 | planned | Planner created `02_开发管理/tasks/EXT-004-entity-alignment-neo4j-model-basis.md`; synchronized open_issues/progress/master_plan only; no `src/**`, `tests/**`, config, dependency, migration, or specification-body change; no Git write | baseline `8330d42a9f2fe9365e180bdd68c6c9dc7add6e48` verified (main, clean tree); scope = §2.1.9 Entity model basis + §2.1.10 deterministic alignment, read-only Neo4j queries, transient non-persisted alignment output; `entity_alignment_failed` is the only authorized EXT-004 code and `graph_query_failed` is reserved for §2.1.11 recall (EXT-005); EXT-003→EXT-004 continuation stays `DEFERRED_FOR_MVP`; `dependency_changes_expected=NONE`; `migration_changes_expected=NONE`; blocking `OI-EXT-004-001` / `OI-EXT-004-002`; non-blocking `OI-EXT-004-003` / `OI-EXT-004-004`; `next_action=计划审查`; `approval_posture=FAIL_CLOSED_BLOCKED`; Developer NOT authorized; 不得触碰 DEV-006/PR#13 |
| 2026-08-12 14:10 UTC | EXT-003 | committed → completed | Release Operator `POST_MERGE_CLEANUP`；PR #37 MERGED (`0eb45e20c64777a03dc770be70cba2316b47fdf6`)；implementation `7c6309ee68b01a6604b79253cea65be6fa26a0c6`；record `b14d53d840e7ba69139ce050a5225eae92def220`；completion `5d9349f7ed6984aee5000422bc55ab5e7031285b`；feat 分支已删 | scoped 63 passed；ruff/mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=1 non-blocking；OI-EXT-003-005 DEFERRED_FOR_MVP；EXT-004 continuation deferred；`next_action=EXT-004 planned / NOT AUTO-STARTED`；governance completion commit created |
| 2026-08-12 06:02 UTC | EXT-003 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `7c6309ee68b01a6604b79253cea65be6fa26a0c6`；PR #37 OPEN；docs(status): record on feat | scoped 63 passed；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED Round 2 P0=0 P1=0；仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge** |
| 2026-08-12 05:45 UTC | EXT-003 | planned → approved | Human PLAN_APPROVED Amendment 002; SF-1 MVP_LOCAL_DECISION orchestration owner=`extraction_llm_service.py`; approval gates updated; PLAN_LANDING pending Release Operator | Round 2 PLAN_APPROVED BLOCKER=0 MUST_FIX=0 SHOULD_FIX=1; preprocessing compose-only; no whitelist expansion; `next_action=Developer on feat/EXT-003-llm-extraction-fingerprint` post-PLAN_LANDING |
| 2026-08-12 10:56 UTC | EXT-002 | committed → completed | Release Operator `POST_MERGE_CLEANUP`; PR #36 MERGED (`59e9f7f0cf6effd34d1f13ad022f9b9eb00b8f2d`); implementation `7fdf84827b2c253a6e6734b8051467f3ec1151f1`; amendment `985613be08814b1e9eea521888b61dd5cb8d94ff`; record `036d770268c3a3bbb95fe4687fd0007805e284a4`; completion `cd0b1a33848b294b5b068891f2a02422767becf1` | scoped 165 passed; RAW-01..12 PASS; RED-01..27 PASS; mandatory skips=0; scoped rerun=165 passed; Ruff/mypy PASS; CODE_REVIEW_APPROVED P0/P1/P2/P3=0; Amendment 004 behavior, terminal/offset gate, privacy and production scope verified; STM-007 completed; EXT-003 prerequisites SATISFIED, planned/NOT AUTO-STARTED; governance completion commit created |
| 2026-08-12 03:05 UTC | EXT-003 | planned | Planner created `02_开发管理/tasks/EXT-003-llm-extraction-fingerprint.md`; synchronized progress/master_plan/open_issues only; no business code/tests/Git write | `next_action=计划审查`; approval posture `FAIL_CLOSED_BLOCKED`; OI-EXT-003-001/002/003/004 blocking; authoritative specification unchanged; no Developer/Reviewer/Release Operator |
| 2026-08-12 03:06 UTC | EXT-003 | planned → plan_rejected | Independent Plan Reviewer returned `PLAN_REJECTED`; BLOCKER=7, MUST_FIX=2, SHOULD_FIX=3; no business code/tests/Git write | Additional blocking conflicts: collision policy, legal empty-result terminal handling, source-reference error mapping, blank-output error mapping; wait for authoritative resolutions and plan amendment |
| 2026-08-12 05:35 UTC | EXT-003 | plan_rejected → planned (Amendment 002) | Planner recorded Appendix B Amendment EXT-003; remediated Task Plan Amendment 002; synchronized open_issues/progress/master_plan; no business code/tests/Git write | `AUTHORIZED_EXT_003_MVP_AMENDMENT` items 1–13; OI-EXT-003-001/002/003/004 resolved; OI-EXT-003-005 deferred_for_mvp; `next_action=计划审查`; `approval_posture=AWAIT_PLAN_REVIEW`; `amendment_recorded=true`; `formal_EXT-003_plan_review=pending` |
| 2026-08-12 10:40 UTC | EXT-002 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`; implementation `7fdf84827b2c253a6e6734b8051467f3ec1151f1`; PR #36 OPEN; approved governance record on feat | scoped 165 passed; Amendment 004/raw/redaction/offset/privacy/scope gates PASS; Ruff/mypy PASS; release_gate=WAITING_FOR_PR_MERGE; no merge; no main write |
| 2026-08-12 10:15 UTC | EXT-002 | tested → in_progress | Remediating P1-001 exception classification and P1-002 explicit RAW/RED matrix on the approved whitelist; no Git write and no scope expansion |
| 2026-08-12 10:30 UTC | EXT-002 | in_progress → tested | P1-001 exception classification narrowed; explicit RAW-01..RAW-12 and RED-01..RED-27 coverage added; scoped 133 passed / 1 optional Mongo skipped; relevant EXT-001/Mongo gates 35 passed; Ruff/mypy/lints PASS; no Git write |
| 2026-08-12 10:10 UTC | EXT-002 | tested → in_progress | Remediation Round 2 reopened only to replace P1 mock/AST evidence with real EXT-002 pipeline and EXT-001 consumer-gate evidence; approved whitelist only; no Git write |
| 2026-08-12 10:16 UTC | EXT-002 | in_progress → implemented | Real pipeline RAW matrix and RED-16/17/21/22/23/27 evidence added; real Kafka/Mongo RED-18/19 gate tests added; unit/contract 172 passed, RED-18/19 2 passed, EXT-002 Mongo 2 passed/1 optional skip, EXT-001 Kafka 8 passed; Ruff/mypy PASS |
| 2026-08-12 10:18 UTC | EXT-002 | implemented → tested | Final scoped suite `161 passed, 1 optional URI-only skip`; RED-18/19 real gate `2 passed`; relevant EXT-001 Kafka/Mongo `8 passed`; Ruff/mypy/lints PASS; mandatory RAW/RED evidence skipped=0; no Git write |
|---|---|---|---|
| 2026-08-12 10:02 UTC | EXT-002 | in_progress → tested | Developer resumed and completed the approved whitelist: strict raw BSON validation, read-only archive lookup, deterministic normalization/redaction, internal handoff, terminal-gate tests; scoped 40 passed / 1 optional Mongo skipped; Ruff/mypy/lints PASS | No EXT-003, worker wiring, dependency, schema, Kafka, task-status, or Git write; next_action=Code Review |
| 2026-08-12 09:16 UTC | EXT-002 | planned（Round 4 effective-wording synchronization） | Planning-only；active validation wording fixed to `error_code=invalid_archive`, `failed_stage=archive_validate`; historical Amendment 003 wording preserved；未实施、未启动 Developer/EXT-003、未 Git 写 | `next_action=计划审查`；baseline `13e1dae36a0b0d94415d9581b2a5fe53c990545f`；dependency changes NONE；不得触碰 DEV-006/PR#13 |
| 2026-08-12 09:00 UTC | EXT-002 | planned（Round 4 governance amendment） | Planning-only；authoritative specification Amendment EXT-002-004 与 Task Plan/open_issues/master_plan 同步；terminal mappings、strict raw validation、deterministic content-only redaction、handoff order、OI dispositions 已记录；未实施、未启动 Developer/EXT-003、未 Git 写 | `next_action=计划审查`；baseline `13e1dae36a0b0d94415d9581b2a5fe53c990545f`；dependency changes NONE；不得触碰 DEV-006/PR#13 |
| 2026-08-12 08:48 UTC | EXT-002 | planned（Round 3 remediation；historical, superseded by Round 4） | Planning-only；Amendment 003；raw read-only repository boundary、strict all-field/no-coercion matrix、no-partial-output gate、EXT-001 terminal/offset consequences、`REDACTION_SPEC_STATUS=BLOCKED_PENDING_SPEC_DECISION`、OI-EXT-002-001 decision packet、`output_contract_status=BLOCKED` 已同步至 Task Plan/master_plan/open_issues；未 Git 写、未实施、未启动 Developer/EXT-003 | `next_action=计划审查`；baseline `13e1dae36a0b0d94415d9581b2a5fe53c990545f`；dependency changes NONE；不得触碰 DEV-006/PR#13 |
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
| 2026-08-11 12:30 UTC | DEV-OPS-008 | planned | 创建 Task Plan `02_开发管理/tasks/DEV-OPS-008-compose-test-stack-runtime-compatibility.md`；master_plan CHANGE-050；C1/C2 contract 闭合；SOURCE-ALIGNED fresh image gate；blocks STM-013 PR #30 | baseline main `390af52`；aiokafka 0.13.0 无 `bootstrap_connected`；ES 9.4.4 GET mapping 省略 element_type | `next_action=计划审查`；未实施、未 Git 写；**不得 merge PR #30**；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 04:12 UTC | STM-013 | scope remediation | REMEDIATION_PLAN_APPROVED；SCOPE_REMEDIATION：C1/C2 从 PR #30 effective diff 移除；`release_gate=BLOCKED_BY_DEFECT_FIX`；blocking `DEV-OPS-008`；provenance `975e6029` 记入 progress | 待 remediation commit push；E2E 预期 FAIL；PR #30 OPEN 不得 merge；CODE_REVIEW superseded | **不得 merge PR #30**；**不得实施 DEV-OPS-008 本轮**；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 13:57 UTC | EXT-001 | committed → completed | POST_MERGE_CLEANUP：PR #34 MERGED（`ae346dd27cda39f93fa38b7316ec17559df217ef` mergedAt `2026-08-11T13:57:07Z`）；docs(status): complete on main；删 exact feat | scoped 61 passed（unit/contract 49、Mongo/migration 5、Kafka 8）；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED Round 2 P0=0 P1=0 P2=0 P3=1；STM-012 prerequisites **SATISFIED** — **READY_FOR_PLANNING only**；**do NOT auto-start** STM-012；EXT-002 remains planned；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 15:15 UTC | STM-012 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `26aa710d62123d341fb79349c9ad86fc5d58c0a6`；PR #35 OPEN；docs(status): record on feat | integration 1 passed（59.97s）；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0；production_delta NONE | 仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 15:20 UTC | STM-012 | committed → completed | POST_MERGE_CLEANUP：PR #35 MERGED（`d73207752bbf004a4b20bf8fff00720cc0ca456b` mergedAt `2026-08-11T15:20:30Z`）；docs(status): complete on main；删 exact feat | integration 1 passed（59.97s）；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=2；production_delta NONE；EXT-002 remains planned — **NOT auto-started**；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 12:17 UTC | STM-011 | committed → completed | POST_MERGE_CLEANUP：PR #33 MERGED（`19fdb55359acd97380a8b5f0d8ae788134f75307` mergedAt `2026-08-11T12:17:49Z`）；docs(status): complete on main；删 exact feat | unit 16 / contract 3 / integration 5；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3；**STM-012 NOT ready**（needs EXT-001）；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 12:10 UTC | STM-011 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `23939a3f3d25f5243978e967949beb4fe6282e2f`；PR OPEN pending；docs(status): record on feat | unit 16 / contract 3 / integration 5；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3 | 仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 11:46 UTC | STM-011 | planned → approved | PLAN_LANDING：docs(plan) `68cee46011f011f3074662f846c64da670741cb3`；创建 `feat/STM-011-republish-archive-event` | 未实施 | `next_action=实施`；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 02:14 UTC | STM-010 | committed → completed | POST_MERGE_CLEANUP：PR #29 MERGED（`722e42d9e24d085b0ed671478730952ef7c92ad6` mergedAt `2026-08-11T02:14:24Z`）；docs(status): complete on main；删 exact feat | scoped unit 36 / contract 11 / integration 19；full unit 446 / contract 101；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=3；OI-003/OI-004 resolved；STM-011/STM-013 READY_FOR_PLANNING only；STM-012 NOT ready；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 01:47 UTC | STM-010 | planned → approved | Round 2 PLAN_APPROVED（BLOCKER=0 MUST_FIX=0）；人工确认 PLAN_APPROVED；Amendment 001；治理回写 Task Plan / progress / master_plan / open_issues（OI-003 resolved at plan time） | 未实施 | `next_action=实施`；PLAN_LANDING 进行中；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 01:17 UTC | STM-009 | committed → completed | PR #28 MERGED（`924ca8c8af94793e76be9376c4514ef417ce5e33` mergedAt `2026-08-11T01:17:29Z`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | scoped unit 21 / contract 10 / redis int 10 / kafka int 2；full unit 410 / contract 90；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3；OI-001/OI-002/OI-005 resolved；OI-004 remains open；STM-010 READY_FOR_PLANNING only（STM-006+STM-009 SATISFIED）；STM-011 READY_FOR_PLANNING only；STM-013 NOT ready（needs STM-010）；**不得触碰 DEV-006/PR#13** |
| 2026-08-11 01:12 UTC | STM-009 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `1b6270b663b6326efb32f096a0e67e2742bb6794`；PR #28 OPEN；docs(status): record on feat | scoped unit 21 / contract 10 / integration 12；full unit 410 / contract 90；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 | 仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；OI-004 remains open；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 15:48 UTC | STM-008 | committed → completed | PR #27 MERGED（`ac61680098d2ae2644bc8b990f057816c3218fca` mergedAt `2026-08-10T15:48:17Z`）；POST_MERGE_CLEANUP docs(status): complete on main；删 exact feat | scoped unit 20 / contract 4 / integration 27；full unit 393 / contract 80；ruff PASS；mypy PASS；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2；单 Lua Finalize + token 公式 I18/I27 + safety/idempotency；无 Kafka/Mongo/LLM；OI-004/OI-005 remain open | STM-009 READY_FOR_PLANNING only（prerequisites SATISFIED）；STM-011 READY_FOR_PLANNING only；STM-010 NOT ready（needs STM-009）；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 23:50 UTC | STM-008 | reviewed → committed | Release Operator `IMPLEMENTATION_RELEASE`；implementation `d619ca2f7e2e20d2d944794c2ca21e8e6d5752ef`；PR #27 OPEN；docs(status): record on feat | scoped unit 20 / contract 4 / integration 27；full unit 393 / contract 80；ruff PASS；mypy PASS | 仅 feat push；禁 push main；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 23:01 UTC | STM-008 | planned | 创建 Task Plan `02_开发管理/tasks/STM-008-compression-finalize-lua.md`；master_plan CHANGE-045；progress 规划态回写 | baseline `ff9a609`；§5.0 十六项 Contract；23 Integration 场景；OI-004/OI-005 open acknowledged | `next_action=计划审查`；未实施、未 Git 写；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 23:45 UTC | STM-008 | approved → tested | Developer 实施：compression_finalize.lua + domain service + repository；unit 13 / contract 4 / integration 27；ruff/mypy PASS | I18 new=500；I27 clamp 0；OI-004/OI-005 remain open | `next_action=CODE_REVIEW`；未 commit；**不得触碰 DEV-006/PR#13** |
| 2026-08-10 23:30 UTC | STM-008 | planned（Amendment 001 / Round 2） | Round 1 MUST_FIX：HM-1 I18 算术修正（770-300-50+80=500）；HM-2 clamp 语义；吸收 SHOULD_FIX（畸形 Redis 整数、ARGV[11]==ARGV[7]、畸形 JSON）；Integration 27 场景；master_plan CHANGE-046 | 未运行（规划-only） | `plan_review_round: 2`；`next_action=计划审查`；未实施、未 Git 写；**不得触碰 DEV-006/PR#13** |
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

1. **STM-010**：`completed`（PR #29 MERGED `722e42d9e24d085b0ed671478730952ef7c92ad6` mergedAt `2026-08-11T02:14:24Z`；implementation `ebb90e49c4eed8b7fd64a35611d7af87521d3d5a`；scoped unit **36** / contract **11** / integration **19**；full unit **446** / contract **101**；ruff **PASS**；mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=3；OI-003/OI-004 resolved；feat 分支待删）。
2. **STM-011**：`completed`（PR #33 MERGED `19fdb55359acd97380a8b5f0d8ae788134f75307` mergedAt `2026-08-11T12:17:49Z`；implementation `23939a3f3d25f5243978e967949beb4fe6282e2f`；scoped unit **16** / contract **3** / integration **5**；ruff **PASS**；mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3；feat 分支待删）。
3. **STM-013**：`completed`（PR #30 MERGED；milestone `v0.2.0-short-term-memory` closed）。
4. **STM-012**：`planned` — prerequisites **SATISFIED**（STM-011+EXT-001 **completed**）；**READY_FOR_PLANNING only** — **do NOT auto-start** until explicit human authorization。
5. **EXT-001**：`completed`（PR #34 MERGED `ae346dd27cda39f93fa38b7316ec17559df217ef` mergedAt `2026-08-11T13:57:07Z`；implementation `afd8b64dfd4856b4a2f00f82846dace76617e0d1`；record `b16c2e05c351cf5402489262a601f9e3afcd20ba`；scoped unit/contract **49** / Mongo/migration **5** / Kafka **8** / total **61**；ruff **PASS**；mypy **PASS**；CODE_REVIEW_APPROVED Round 2 P0=0 P1=0 P2=0 P3=1；feat 分支待删）。
6. **STM-009**：`completed`（PR #28 MERGED `924ca8c8af94793e76be9376c4514ef417ce5e33` mergedAt `2026-08-11T01:17:29Z`；implementation `1b6270b663b6326efb32f096a0e67e2742bb6794`；record `63232d837add2b4a6c6918d145f115f4762b88f7`；scoped unit **21** / contract **10** / redis int **10** / kafka int **2**；full unit **410** / contract **90**；ruff **PASS**；mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=3；OI-001/OI-002/OI-005 resolved；feat 分支待删）。
7. **STM-008**：`completed`（PR #27 MERGED `ac61680098d2ae2644bc8b990f057816c3218fca` mergedAt `2026-08-10T15:48:17Z`；implementation `d619ca2f7e2e20d2d944794c2ca21e8e6d5752ef`；record `a938220f8937b0e8af7e52dd34019ad1b558e789`；scoped unit **20** / contract **4** / integration **27**；full unit **393** / contract **80**；ruff **PASS**；mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2；feat 分支待删）。
8. **STM-007**：`completed`（PR #26 MERGED `7a72b3a4c159032a411bd48dc920e52973ddab3e` mergedAt `2026-08-10T14:45:58Z`；implementation `87dc9c4a442aff113ac220b9604010aa135f721e`；record `357893a75fe6c95950c6e55d17ef4354194dfc20`；scoped unit **20** / contract **4** / integration(fake) **5** / total **29**；full unit **369** / contract **76**；ruff **PASS**；mypy **PASS**；real integration **SKIPPED**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1；feat 分支待删）。
9. **STM-006**：`completed`（PR #25 MERGED `d704bc5421d346d46a48cb69a3a7ad956e94dbb8`；implementation `683caab306e082d58f577977ba3ecee5c550aa6e`）。
10. **DEV-006**：`PAUSED / SUPERSEDED_FOR_MVP`；PR #13 **DO_NOT_MERGE**；不得触碰。
11. **EXT-003**：`completed`（PR #37 MERGED `0eb45e20c64777a03dc770be70cba2316b47fdf6` mergedAt `2026-08-12T06:06:31Z`；implementation `7c6309ee68b01a6604b79253cea65be6fa26a0c6`；scoped **63** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=1 P3=1；feat 分支已删）。
12. **EXT-004**：`completed`（PR #38 MERGED `229f5e960f51e55a7389599eeccdf650a9a7beff` mergedAt `2026-08-12T07:49:18Z`；implementation `0641ac3c7648c0c12cb881f3a0f501c7b3f8dc9c`；scoped **53** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=2 P3=2；read-only Neo4j alignment only；feat 分支已删）。
13. **EXT-005**：`completed`（PR #39 MERGED `638598080b2d24e9291933c5ef92d3e4d65a0612` mergedAt `2026-08-12T09:47:46Z`；implementation `c6e619d312bfd83fef30c9f394e16b42a65cba81`；record `775992943ae0eb349301defb990c59c7089cf32e`；scoped **63** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=0；zero Mongo/Neo4j writes；feat 分支已删）。
14. **EXT-006**：`completed`（PR #40 MERGED `372e0232c1e5cfa1d71e2bb0152a22f59e60cd03` mergedAt `2026-08-12T12:12:38Z`；implementation `b19e913af3848e932b8adb404dc5d5304167fb73`；record `eafc07a3e01f376f4bd2c6c658c1dd5536c3b61f`；scoped **44** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=0 P3=2 non-blocking；atomic Neo4j graph write + `index_sync_memory_set` handoff；zero task completed/offset；OI-006 non-blocking；feat 分支已删）。
15. **EXT-007**：`completed`（PR #41 MERGED `afb2fee9ca6f7a5e049f0d9b1b22825de4c665dd` mergedAt `2026-08-12T13:27:51Z`；implementation `2cf93ec5bcb03daae6e266984df2804a09f19a0c`；record `d385f4b3553d310f89b17e832ea07c29b50d9761`；scoped **30** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0 P2=3 P3=2 non-blocking；§2.2.3 index sync + ES bulk upsert + first `mark_completed` gate；completed-before-offset gate preserved；zero upstream/offset diff；feat 分支已删；不得触碰 DEV-006/PR#13）。
16. **EXT-008**：`committed`（PR #42 OPEN `https://github.com/xu-jia-ming/memory_system/pull/42`；implementation `e8f15b458a6f1fa6e204393d5300a018bfc5c27b`；scoped **25** passed；ruff/mypy **PASS**；CODE_REVIEW_APPROVED P0=0 P1=0；§2.1.14 GET/retry/rebuild Admin HTTP + OI-006 rebuild；LD-3 Mongo before Kafka；zero consumer/worker/pipeline diff；`next_action=WAITING_FOR_PR_MERGE`；**不得自动 merge**；不得触碰 DEV-006/PR#13）。
