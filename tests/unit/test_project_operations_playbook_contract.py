"""Contract tests for DEV-OPS-005 human project operations playbook.

Locks durable behavior in 03_AI_Prompts/01_项目日常操作手册.md via
substring / existence assertions — not fragile full-paragraph copies.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_PATH = REPO_ROOT / "03_AI_Prompts" / "01_项目日常操作手册.md"

TEMPLATE_IDS = (
    "START_EXISTING_TASK",
    "PLAN_APPROVED",
    "AFTER_PR_MERGE",
    "RECOVERY_MODE",
    "NEW_UNPLANNED_FEATURE",
    "FAILURE_AND_RECOVERY",
)

RULE_LABELS = ("规则 A", "规则 B", "规则 C", "规则 D", "规则 E")

FORBIDDEN_COMMAND_MARKERS = (
    "gh pr merge",
    "--force",
    "reset --hard",
    "clean -fd",
    "branch -D",
)


def _playbook_text() -> str:
    assert PLAYBOOK_PATH.is_file(), f"missing file: {PLAYBOOK_PATH}"
    return PLAYBOOK_PATH.read_text(encoding="utf-8")


def _section_after(text: str, marker: str) -> str:
    assert marker in text, f"missing section marker: {marker}"
    start = text.index(marker)
    # Slice until the next top-level ### heading if present, else rest of file.
    rest = text[start:]
    next_heading = rest.find("\n### ", 1)
    if next_heading == -1:
        return rest
    return rest[:next_heading]


def test_playbook_file_exists() -> None:
    assert PLAYBOOK_PATH.is_file()


def test_memory_burden_heading() -> None:
    text = _playbook_text()
    assert "我以后只需要记住什么？" in text


def test_six_template_ids_present() -> None:
    text = _playbook_text()
    for template_id in TEMPLATE_IDS:
        assert template_id in text, f"missing template id: {template_id}"


def test_rule_a_through_e_labels_and_topics() -> None:
    text = _playbook_text()
    for label in RULE_LABELS:
        assert label in text, f"missing rule label: {label}"

    assert "no blind retry" in text or "盲目重试" in text
    assert "规则 A" in text and ("盲目重试" in text or "no blind retry" in text)

    rule_b = _section_after(text, "规则 B")
    assert "00_全局开发规则.md" in rule_b
    assert "Mihomo" in rule_b or "mihomo" in rule_b or "Docker" in rule_b

    rule_c = _section_after(text, "规则 C")
    assert "SHA" in rule_c or "commit" in rule_c
    assert "自身" in rule_c or "self-ref" in rule_c or "self-referential" in rule_c

    rule_d = _section_after(text, "规则 D")
    assert "WAITING" in rule_d or "WAITING_FOR_PR_MERGE" in rule_d
    assert "干净" in rule_d or "clean" in rule_d

    rule_e = _section_after(text, "规则 E")
    assert "governance deviation" in rule_e or "治理偏差" in rule_e or "GD-" in rule_e


def test_normal_exactly_two_routine_human_gates() -> None:
    text = _playbook_text()
    assert "恰好两扇" in text
    assert "PLAN_APPROVED" in text
    assert "Human PR" in text or "人工 Merge" in text or "PR Merge" in text
    # Must not imply a third routine human gate beyond the two named gates.
    assert "不是第三扇" in text or "非第三扇" in text or "不是第三" in text


def test_ready_for_human_commit_is_compat_marker_not_third_gate() -> None:
    text = _playbook_text()
    assert "READY_FOR_HUMAN_COMMIT" in text
    assert "兼容" in text or "边界标记" in text
    assert "不是第三扇" in text or "非第三扇" in text or "不是第三" in text
    assert "IMPLEMENTATION_RELEASE" in text
    assert "自动" in text


def test_start_existing_task_planning_only() -> None:
    section = _section_after(_playbook_text(), "START_EXISTING_TASK")
    assert "planning-only" in section or "planning only" in section or "仅规划" in section
    assert "Planner" in section
    assert "Plan Reviewer" in section
    assert "PLAN_APPROVED" in section
    assert "禁止" in section and ("短描述" in section or "发明实现" in section)
    assert "权威源" in section


def test_plan_approved_normal_auto_chain() -> None:
    text = _playbook_text()
    assert "PLAN_LANDING" in text
    assert "Developer" in text
    assert "Code Reviewer" in text
    assert "Commit Recorder" in text
    assert "IMPLEMENTATION_RELEASE" in text
    assert "WAITING_FOR_PR_MERGE" in text
    assert "无第二次手工" in text or "无第二次" in text
    assert "PLAN_LANDING" in text


def test_plan_before_coding() -> None:
    text = _playbook_text()
    assert "先规划" in text or "PLAN_APPROVED" in text
    assert "禁止直接编码" in text or "不得编写业务代码" in text or "禁止立即编码" in text


def test_normal_release_operator_handles_commit_not_human_git_commit_gate() -> None:
    text = _playbook_text()
    assert "Release Operator" in text
    assert "自动" in text
    assert "手工 `git commit`" in text or "人类手工" in text or "非人类手工" in text


def test_pr_merge_is_human_agent_forbidden() -> None:
    text = _playbook_text()
    assert "人工" in text and ("Merge" in text or "merge" in text)
    assert "gh pr merge" in text
    assert "禁止" in text


def test_post_merge_cleanup_automatic_after_merged() -> None:
    text = _playbook_text()
    assert "POST_MERGE_CLEANUP" in text
    assert "自动" in text
    assert "第三次" in text or "无需第三次" in text or "无再一次" in text


def test_recovery_mode_read_only_first() -> None:
    section = _section_after(_playbook_text(), "RECOVERY_MODE")
    assert "先只读" in section
    assert "progress" in section or "progress.md" in section
    assert "git status" in section or "git" in section
    assert "无 Git 写" in section or "禁止 Git 写" in section


def test_no_blind_retry() -> None:
    text = _playbook_text()
    assert "盲目重试" in text or "禁止盲目重试" in text


def test_fix_not_equal_retry() -> None:
    text = _playbook_text()
    assert (
        "fix≠retry" in text
        or "fix != retry" in text
        or "修复 ≠ 重试" in text
        or "fix permission != retry permission" in text
    )


def test_forbidden_git_commands_locked() -> None:
    text = _playbook_text()
    for marker in FORBIDDEN_COMMAND_MARKERS:
        assert marker in text, f"missing forbidden command marker: {marker}"
    assert "force" in text.lower()


def test_self_ref_sha_forbidden() -> None:
    text = _playbook_text()
    assert "SHA" in text
    assert (
        "自身" in text
        or "self-ref" in text
        or "self-referential" in text
        or "即将产生" in text
    )
    assert "不可稳定" in text or "禁止" in text


def test_daemon_proxy_not_buildkit_proxy() -> None:
    text = _playbook_text()
    assert "daemon" in text
    assert "BuildKit" in text or "ad-hoc" in text
    assert "≠" in text or "不等于" in text or "不是" in text


def test_7890_not_mihomo_17890_referenced() -> None:
    text = _playbook_text()
    assert "7890" in text
    assert "17890" in text
    assert "Mihomo" in text or "mihomo" in text
    assert "00_全局开发规则.md" in text
    assert "SSH" in text or "forwarding" in text


def test_secrets_forbidden() -> None:
    text = _playbook_text()
    assert "Secret" in text or "secret" in text
    assert "禁止提交" in text or "不提交" in text


def test_waiting_requires_clean_working_tree() -> None:
    text = _playbook_text()
    assert "WAITING_FOR_PR_MERGE" in text
    assert "干净" in text or "clean" in text


def test_playbook_distinct_from_backlog_prompt() -> None:
    text = _playbook_text()
    assert "01_初始化与Backlog.md" in text or "初始化与Backlog" in text
    assert "≠" in text or "不是" in text or "职责" in text


def test_should_fix1_normal_vs_strict_contrast() -> None:
    """SHOULD_FIX 1: NORMAL auto-chain vs STRICT detailed human gates."""
    text = _playbook_text()
    assert "NORMAL" in text
    assert "STRICT" in text
    assert "自动串联" in text or "自动链" in text
    assert "详细人工" in text or "人工 gate" in text
    assert "不得" in text and "NORMAL" in text and "STRICT" in text
    # STRICT must not inherit NORMAL auto-chaining; semantics unchanged.
    assert "不改变" in text or "不得因 NORMAL" in text


def test_fix_permission_not_retry_permission() -> None:
    text = _playbook_text()
    assert (
        "fix permission != retry permission" in text
        or "修复权限 ≠ 重试权限" in text
        or "允许修代码" in text
    )


def test_final_tests_pass_not_workflow_compliance() -> None:
    text = _playbook_text()
    assert "workflow compliance" in text or "治理合规" in text
    assert "PASS" in text or "全绿" in text or "测试" in text


def test_host_workaround_must_not_pollute_general_deployment() -> None:
    text = _playbook_text()
    assert "host-specific" in text or "host workaround" in text or "本机" in text
    assert "污染" in text or "通用部署" in text


def test_container_to_host_proxy_must_not_be_guessed() -> None:
    text = _playbook_text()
    assert "container" in text.lower() or "容器" in text
    assert "猜" in text or "猜测" in text


def test_slow_command_no_concurrent_reexecution() -> None:
    text = _playbook_text()
    assert "slow" in text.lower() or "慢" in text
    assert "并发" in text
