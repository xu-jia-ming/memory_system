"""Static contract tests for Cursor Orchestrator, Subagents, and release permissions."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".cursor" / "agents"
COMMANDS_DIR = REPO_ROOT / ".cursor" / "commands"
PERMISSIONS_PATH = REPO_ROOT / ".cursor" / "permissions.json"
CLI_PATH = REPO_ROOT / ".cursor" / "cli.json"
ORCHESTRATOR_PATH = COMMANDS_DIR / "orchestrate-task.md"

AGENT_ROLE_MAP: dict[str, str] = {
    "planner.md": "Planner",
    "plan-reviewer.md": "Plan Reviewer",
    "developer.md": "Developer",
    "code-reviewer.md": "Code Reviewer",
    "commit-recorder.md": "Commit Recorder",
    "release-operator.md": "Release Operator",
}

FRONTMATTER_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "model",
    "readonly",
    "is_background",
)

ORCHESTRATOR_FAIL_CLOSED_PATTERNS: tuple[str, ...] = (
    "不得猜测",
    "不得冒充",
    "ORCHESTRATOR_HALTED",
    r"缺少.*结束标记",
    r"成功.*失败.*同时",
    "非零退出",
    "无法解析",
    "不得自动调用下一角色",
)

RELEASE_OPERATOR_REQUIRED_SUBSTRINGS: tuple[str, ...] = (
    "检查退出码",
    "非零立即停止",
    "不得假设成功",
    "不得猜测",
    "git rev-parse HEAD",
    "gh pr view --json",
    "RELEASE_OPERATOR_FAILED",
    "RELEASE_COMPLETED",
)

RELEASE_OPERATOR_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "git push --force",
    "git reset --hard",
    "git clean -fd",
    "git branch -D",
    "git merge",
    "gh pr merge",
)

ALL_AGENT_ROLES: tuple[str, ...] = tuple(AGENT_ROLE_MAP.values())

# Each rule must be present in orchestrate-task.md; removing any rule should fail its test.
WRITABLE_SCOPE_CONTRACT_RULES: tuple[dict[str, str], ...] = (
    {
        "rule_id": "compute_each_round",
        "pattern": r"每轮.*先计算.*实际可写集合",
        "description": "must compute writable scope at start of each round",
    },
    {
        "rule_id": "intersection_formula",
        "pattern": r"实际可写集合\s*=\s*[\s\S]*∩[\s\S]*∩",
        "description": "writable scope uses three-way intersection",
    },
    {
        "rule_id": "user_explicit_forbid_priority",
        "pattern": r"用户.*显式.*优先|用户显式约束优先",
        "description": "user explicit forbid takes priority",
    },
    {
        "rule_id": "task_plan_whitelist_priority",
        "pattern": r"Task Plan 白名单优先",
        "description": "task plan whitelist constrains orchestrator writes",
    },
    {
        "rule_id": "no_governance_when_not_whitelisted",
        "pattern": r"白名单[\s\S]*不含[\s\S]*progress\.md[\s\S]*不得写",
        "description": "cannot write progress when not in task plan whitelist",
    },
    {
        "rule_id": "empty_intersection_no_writes",
        "pattern": r"实际可写集合.*为空.*不得写任何文件",
        "description": "empty intersection forbids all file writes",
    },
    {
        "rule_id": "report_only_no_persist",
        "pattern": (
            r"仅在.*最终回复.*报告.*current_stage.*last_role_result"
            r".*blocking_reason.*不得持久化"
        ),
        "description": "report orchestration fields in reply only when empty",
    },
    {
        "rule_id": "no_whitelist_expansion",
        "pattern": r"不得因为需要记录编排态而扩大白名单|不得扩大白名单",
        "description": "must not expand whitelist for orchestration logging",
    },
    {
        "rule_id": "conflict_halt",
        "pattern": (
            r"用户约束与 Task Plan.*冲突.*ORCHESTRATOR_HALTED"
            r"|无法确定交集时.*ORCHESTRATOR_HALTED"
        ),
        "description": "conflict or unknown intersection triggers halt",
    },
    {
        "rule_id": "manual_gates_unchanged",
        "pattern": r"不放宽.*approved.*reviewed.*committed.*completed",
        "description": "manual status gates remain unchanged",
    },
)


def _read_agent(filename: str) -> str:
    path = AGENTS_DIR / filename
    assert path.is_file(), f"missing agent file: {path}"
    return path.read_text(encoding="utf-8")


def _read_orchestrator() -> str:
    assert ORCHESTRATOR_PATH.is_file(), f"missing orchestrator: {ORCHESTRATOR_PATH}"
    return ORCHESTRATOR_PATH.read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    assert match, "missing YAML frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_agents_directory_contains_exactly_whitelist_files() -> None:
    assert AGENTS_DIR.is_dir(), f"missing agents directory: {AGENTS_DIR}"
    actual = sorted(path.name for path in AGENTS_DIR.iterdir() if path.is_file())
    expected = sorted(AGENT_ROLE_MAP)
    assert actual == expected


def test_each_agent_has_required_frontmatter_fields() -> None:
    for filename in AGENT_ROLE_MAP:
        meta = _parse_frontmatter(_read_agent(filename))
        for field in FRONTMATTER_FIELDS:
            assert field in meta, f"{filename} missing frontmatter field {field!r}"
        assert meta["model"] == "inherit"
        assert meta["is_background"] == "false"


def test_agent_readonly_flags_match_plan() -> None:
    readonly_true = {"plan-reviewer.md", "code-reviewer.md", "commit-recorder.md"}
    for filename in AGENT_ROLE_MAP:
        meta = _parse_frontmatter(_read_agent(filename))
        expected = "true" if filename in readonly_true else "false"
        assert meta["readonly"] == expected, f"{filename} readonly mismatch"


def test_agent_role_mapping_is_one_to_one() -> None:
    assert len(AGENT_ROLE_MAP) == 6
    assert set(AGENT_ROLE_MAP.values()) == set(ALL_AGENT_ROLES)
    for filename, role in AGENT_ROLE_MAP.items():
        text = _read_agent(filename)
        assert f"唯一角色 = {role}" in text
        for other_role in ALL_AGENT_ROLES:
            if other_role == role:
                continue
            assert f"唯一角色 = {other_role}" not in text


def test_agents_do_not_spawn_deeper_subagents() -> None:
    for filename in AGENT_ROLE_MAP:
        text = _read_agent(filename)
        assert "不得再启动更深一层 Subagent" in text, f"{filename} must forbid nested spawn"


def test_orchestrator_fail_closed_substrings() -> None:
    text = _read_orchestrator()
    for pattern in ORCHESTRATOR_FAIL_CLOSED_PATTERNS:
        assert re.search(pattern, text), f"orchestrate-task missing pattern: {pattern!r}"


def test_orchestrator_does_not_self_approve() -> None:
    text = _read_orchestrator()
    assert "唯一角色 = Orchestrator" in text
    assert "不得输出 `PLAN_APPROVED`" in text or "禁止**将 `PLAN_APPROVED`" in text
    assert "CODE_REVIEW_APPROVED" in text
    assert "最后一行必须且仅为：`PLAN_APPROVED`" not in text
    assert "最后一行必须且仅为：`CODE_REVIEW_APPROVED`" not in text
    assert "唯一角色 = Planner" not in text
    assert "唯一角色 = Release Operator" not in text


@pytest.mark.parametrize(
    "rule",
    WRITABLE_SCOPE_CONTRACT_RULES,
    ids=[rule["rule_id"] for rule in WRITABLE_SCOPE_CONTRACT_RULES],
)
def test_orchestrator_writable_scope_contract_rule(rule: dict[str, str]) -> None:
    text = _read_orchestrator()
    assert re.search(rule["pattern"], text, re.DOTALL), (
        f"orchestrate-task missing writable-scope rule {rule['rule_id']}: "
        f"{rule['description']}"
    )


def test_orchestrator_writable_scope_intersection_operands_explicit() -> None:
    text = _read_orchestrator()
    assert "命令默认允许字段" in text or "命令默认允许" in text
    assert "当前 Task Plan 允许路径/字段" in text or "当前 Task Plan" in text
    assert "用户本轮显式允许范围" in text
    assert "∩" in text


def test_orchestrator_forbids_unconditional_progress_write() -> None:
    text = _read_orchestrator()
    assert "**仅可**回写 `progress.md`" not in text
    assert "无条件" not in text or "不是**无条件可写" in text
    assert "默认字段**不是**无条件可写" in text or "默认字段不是无条件可写" in text


def test_release_operator_exit_code_and_fact_substrings() -> None:
    text = _read_agent("release-operator.md")
    for required in RELEASE_OPERATOR_REQUIRED_SUBSTRINGS:
        assert required in text, f"release-operator missing {required!r}"
    for forbidden in RELEASE_OPERATOR_FORBIDDEN_SUBSTRINGS:
        assert forbidden in text, f"release-operator must forbid {forbidden!r}"
    assert "不是安全边界" in text


def test_permissions_and_cli_files_exist_with_key_policies() -> None:
    assert PERMISSIONS_PATH.is_file()
    assert CLI_PATH.is_file()

    permissions_text = PERMISSIONS_PATH.read_text(encoding="utf-8")
    assert "terminalAllowlist" in permissions_text
    assert "block_instructions" in permissions_text
    assert "不是安全边界" in permissions_text
    permissions = json.loads(re.sub(r"//.*", "", permissions_text))
    allowlist = permissions["terminalAllowlist"]
    assert "git" not in allowlist
    assert "git status" in allowlist
    assert "git push" in allowlist

    cli = json.loads(CLI_PATH.read_text(encoding="utf-8"))
    deny = cli["permissions"]["deny"]
    assert any("Read(.env*)" in item for item in deny)
    assert any("git push --force" in item for item in deny)
    assert any("git merge" in item for item in deny)
