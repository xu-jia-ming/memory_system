"""Contract tests for DEV-OPS-003 NORMAL / STRICT workflow modes and release phases.

Covers mode declaration, auto-continue differences, RELEASE_PHASE allow/deny,
fail-closed negatives, and MF-001 / DD-006 (IMPLEMENTATION_RELEASE never pushes main).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".cursor" / "agents"
ORCHESTRATOR_PATH = REPO_ROOT / ".cursor" / "commands" / "orchestrate-task.md"
RELEASE_OPERATOR_PATH = AGENTS_DIR / "release-operator.md"
COMMIT_RECORDER_PATH = AGENTS_DIR / "commit-recorder.md"
GOVERNANCE_RULE_PATH = (
    REPO_ROOT / ".cursor" / "rules" / "00-memory-system-governance.mdc"
)
GLOBAL_PROMPT_PATH = REPO_ROOT / "03_AI_Prompts" / "00_全局开发规则.md"
GIT_WORKFLOW_PATH = REPO_ROOT / "04_Git规范" / "git_workflow.md"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing file: {path}"
    return path.read_text(encoding="utf-8")


def _orchestrator() -> str:
    return _read(ORCHESTRATOR_PATH)


def _release() -> str:
    return _read(RELEASE_OPERATOR_PATH)


def _implementation_release_section() -> str:
    text = _release()
    match = re.search(
        r"## PHASE=IMPLEMENTATION_RELEASE([\s\S]*?)(?=\n## PHASE=|\n## 结束标记|\Z)",
        text,
    )
    assert match, "IMPLEMENTATION_RELEASE section missing"
    return match.group(1)


def _post_merge_section() -> str:
    text = _release()
    match = re.search(
        r"## PHASE=POST_MERGE_CLEANUP([\s\S]*?)(?=\n## 结束标记|\Z)",
        text,
    )
    assert match, "POST_MERGE_CLEANUP section missing"
    return match.group(1)


def test_mode_declaration_contract() -> None:
    text = _orchestrator()
    assert "WORKFLOW_MODE" in text
    assert "NORMAL" in text
    assert "STRICT" in text
    assert re.search(r"默认.*NORMAL|缺省.*NORMAL|若缺失：默认 `NORMAL`", text)
    assert "workflow_mode=" in text
    assert "explicit" in text
    assert "default" in text
    assert "不得静默切换" in text


def test_normal_two_human_gates() -> None:
    text = _orchestrator()
    assert "PLAN_APPROVED" in text
    assert "WAITING_FOR_PR_MERGE" in text
    assert re.search(r"常规人工门禁仅两个|仅两个：", text)
    assert "Human PR" in text or "PR Review / Merge" in text or "Human PR Merge" in text


def test_normal_auto_continue_after_success_only() -> None:
    text = _orchestrator()
    assert "NORMAL" in text
    assert re.search(
        r"唯一成功标记[\s\S]*自动调用|成功标记校验后[\s\S]*自动调用",
        text,
    )
    assert "WAITING_FOR_PR_MERGE" in text
    assert "PLAN_LANDING" in text
    assert "IMPLEMENTATION_RELEASE" in text
    assert "POST_MERGE_CLEANUP" in text


def test_role_section_mode_conditional_auto_continue() -> None:
    """DEV-OPS-003 P2: role section must not read as unconditional ban on auto-call.

    Keep literal「不得自动切换到下一角色」for five-command shared substring, but
    clarify it means no role morph/兼; auto-call next role/phase is mode-conditional.
    """
    text = _orchestrator()
    role_section = re.search(r"## 角色([\s\S]*?)(?=\n## )", text)
    assert role_section, "orchestrate-task missing ## 角色 section"
    role = role_section.group(1)
    assert "不得自动切换到下一角色" in role
    assert re.search(r"不得变身|兼任", role)
    assert "mode-conditional" in role
    assert re.search(r"STRICT[\s\S]*禁止自动续跑|STRICT[\s\S]*仍然禁止自动续跑", role)
    assert re.search(
        r"NORMAL[\s\S]*唯一成功结束标记[\s\S]*自动调用下一角色"
        r"|NORMAL[\s\S]*唯一成功结束标记[\s\S]*下一 Release phase",
        role,
    )
    assert "ORCHESTRATOR_HALTED" in role
    assert re.search(
        r"缺标记[\s\S]*不得[\s\S]*自动续跑|一律 `ORCHESTRATOR_HALTED`[\s\S]*不得[\s\S]*自动续跑",
        role,
    )


def test_strict_forbids_auto_continue_and_extra_phases() -> None:
    text = _orchestrator()
    assert re.search(r"STRICT[\s\S]*不得自动调用下一角色", text)
    assert re.search(
        r"STRICT[\s\S]*禁止[\s\S]*PLAN_LANDING[\s\S]*POST_MERGE_CLEANUP"
        r"|禁止[\s\S]*调度 `PLAN_LANDING` / `POST_MERGE_CLEANUP`",
        text,
    )
    assert "显式调用" in text or "显式人工触发" in text


def test_orchestrator_schedules_release_never_writes_git() -> None:
    text = _orchestrator()
    assert "DD-001" in text or "唯一 Git 写" in text or "永不执行" in text
    assert re.search(r"不得执行[\s\S]*git add|永不执行[\s\S]*git add", text)
    assert "Release Operator" in text
    assert "Foreground" in text


def test_release_three_phases_named() -> None:
    text = _release()
    assert "PLAN_LANDING" in text
    assert "IMPLEMENTATION_RELEASE" in text
    assert "POST_MERGE_CLEANUP" in text
    assert "RELEASE_PHASE" in text
    assert "phase=PLAN_LANDING" in text
    assert "phase=IMPLEMENTATION_RELEASE" in text
    assert "phase=POST_MERGE_CLEANUP" in text


def test_plan_landing_allows_main_docs_and_ff_only() -> None:
    text = _release()
    assert "git pull --ff-only origin main" in text
    assert "docs(plan)" in text
    assert "git push origin main" in text
    assert "git switch -c" in text or "git checkout -b" in text
    assert "仅 NORMAL" in text


def test_implementation_release_forbids_push_main_mf001() -> None:
    """MF-001 / DD-006: IMPLEMENTATION_RELEASE must permanently forbid main write."""
    section = _implementation_release_section()
    assert "git push origin main" in section
    assert re.search(
        r"永久禁止[\s\S]*git push origin main|禁止[\s\S]*git push origin main",
        section,
    )
    assert re.search(r"在 `main` 上 `git commit`|在 main 上", section)
    assert "docs(status): record" in section
    assert re.search(r"仅.*feat|同一 feat", section)
    assert (
        "自动**推到 `main`" in section
        or "自动推到 `main`" in section
        or "推到 `main`" in section
    )
    # Must not describe record as an allowed auto-push onto main (MF-001)
    assert not re.search(
        r"允许[\s\S]{0,80}docs\(status\): record[\s\S]{0,80}push origin main",
        section,
    )
    assert "将 `docs(status): record` **自动**推到 `main`" in section or (
        "record" in section and "禁止" in section and "main" in section
    )


def test_implementation_release_fails_if_current_branch_main() -> None:
    section = _implementation_release_section()
    assert re.search(r"当前分支为 `main`[\s\S]*RELEASE_OPERATOR_FAILED", section)
    assert "**非** `main`" in section or "非** `main`" in section


def test_post_merge_requires_merged_before_delete() -> None:
    section = _post_merge_section()
    assert "state=MERGED" in section
    assert "git branch -d" in section
    assert "git push origin --delete" in section
    assert "git branch -D" in section  # must still forbid -D
    assert "未 MERGED" in section
    assert "git fetch" in section
    assert "docs(status): complete" in section


def test_strict_requesting_plan_landing_or_post_merge_fails() -> None:
    text = _release()
    assert re.search(
        r"STRICT[\s\S]*PLAN_LANDING[\s\S]*POST_MERGE_CLEANUP[\s\S]*RELEASE_OPERATOR_FAILED"
        r"|误调[\s\S]*PLAN_LANDING[\s\S]*POST_MERGE[\s\S]*FAILED",
        text,
    )


def test_fail_closed_negatives_present_in_orchestrator() -> None:
    text = _orchestrator()
    for needle in (
        "缺少期望结束标记",
        "成功与失败标记同时出现",
        "非零退出",
        "无法解析",
        "不得自动调用下一角色",
        "ORCHESTRATOR_HALTED",
        "dirty",
        "WAITING_FOR_PR_MERGE",
    ):
        assert needle in text or (
            needle == "dirty" and ("dirty" in text or "working tree" in text)
        ), f"missing fail-closed needle: {needle!r}"


def test_permanent_forbidden_ops_still_documented() -> None:
    text = _release()
    for forbidden in (
        "git push --force",
        "git reset --hard",
        "git clean -fd",
        "git branch -D",
        "gh pr merge",
    ):
        assert forbidden in text, f"release-operator must still forbid {forbidden!r}"
    # Content merge remains forbidden; ff-only pull is not "git merge"
    assert "git merge" in text
    assert "git pull --ff-only" in text


def test_commit_recorder_normal_does_not_block_auto_release() -> None:
    text = _read(COMMIT_RECORDER_PATH)
    assert "READY_FOR_HUMAN_COMMIT" in text
    assert "NORMAL" in text
    assert "不阻止" in text or "自动调度" in text
    assert "STRICT" in text
    assert "git add" in text
    assert "禁止" in text
    assert "唯一角色 = Commit Recorder" in text


def test_governance_and_global_rules_phase_narrow_exception() -> None:
    governance = _read(GOVERNANCE_RULE_PATH)
    global_prompt = _read(GLOBAL_PROMPT_PATH)
    for text in (governance, global_prompt):
        assert "PLAN_LANDING" in text
        assert "IMPLEMENTATION_RELEASE" in text
        assert "POST_MERGE_CLEANUP" in text
        assert "git push origin main" in text or "push origin main" in text
        assert "DD-006" in text or "永久禁止" in text
        assert "gh pr merge" in text or "gh pr merge" in global_prompt
        assert "git branch -D" in text or "branch -D" in text


def test_git_workflow_sf002_release_exception_pointer() -> None:
    text = _read(GIT_WORKFLOW_PATH)
    assert "自动 Push" in text
    assert "Release Operator" in text
    assert "RELEASE_PHASE" in text
    assert "IMPLEMENTATION_RELEASE" in text
    assert "git push origin main" in text


def test_waiting_for_pr_merge_resume_without_third_gate() -> None:
    text = _orchestrator()
    assert "WAITING_FOR_PR_MERGE" in text
    assert "MERGED" in text
    assert "POST_MERGE_CLEANUP" in text
    assert "webhook" in text.lower() or "不引入 webhook" in text
    assert "第三次人工批准" in text or "不再**要求第三次" in text
