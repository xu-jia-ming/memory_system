"""Static contract tests for project Cursor slash command Markdown files."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / ".cursor" / "commands"

ORIGINAL_FIVE_COMMAND_ROLE_MAP: dict[str, str] = {
    "plan-task.md": "Planner",
    "review-plan.md": "Plan Reviewer",
    "develop-task.md": "Developer",
    "review-code.md": "Code Reviewer",
    "close-task.md": "Commit Recorder",
}

COMMAND_ROLE_MAP: dict[str, str] = {
    **ORIGINAL_FIVE_COMMAND_ROLE_MAP,
    "orchestrate-task.md": "Orchestrator",
}

REQUIRED_END_MARKERS: dict[str, tuple[str, ...]] = {
    "plan-task.md": ("READY_FOR_PLAN_REVIEW",),
    "review-plan.md": ("PLAN_APPROVED", "PLAN_REJECTED"),
    "develop-task.md": ("READY_FOR_CODE_REVIEW",),
    "review-code.md": ("CODE_REVIEW_APPROVED", "CODE_REVIEW_REJECTED"),
    "close-task.md": ("READY_FOR_HUMAN_COMMIT",),
    "orchestrate-task.md": ("ORCHESTRATOR_PAUSED_FOR_HUMAN", "ORCHESTRATOR_HALTED"),
}

REQUIRED_SUBSTRINGS: tuple[str, ...] = (
    "git add",
    "git commit",
    "git push",
    "git merge",
    "git rebase",
    "progress.md",
    "不得自动切换到下一角色",
)

REQUIRED_SECTION_HEADINGS: tuple[str, ...] = (
    "## 角色",
    "## 必读文件",
    "## 前置只读检查",
    "## 允许修改范围",
    "## 阶段验证",
    "## 结束标记",
)

ALL_ORIGINAL_ROLES: tuple[str, ...] = tuple(ORIGINAL_FIVE_COMMAND_ROLE_MAP.values())
ALL_COMMAND_ROLES: tuple[str, ...] = tuple(COMMAND_ROLE_MAP.values())


def _command_path(filename: str) -> Path:
    return COMMANDS_DIR / filename


def _read_command(filename: str) -> str:
    path = _command_path(filename)
    assert path.is_file(), f"missing command file: {path}"
    return path.read_text(encoding="utf-8")


def test_commands_directory_contains_exactly_whitelist_files() -> None:
    assert COMMANDS_DIR.is_dir(), f"missing commands directory: {COMMANDS_DIR}"
    actual = sorted(path.name for path in COMMANDS_DIR.iterdir() if path.is_file())
    expected = sorted(COMMAND_ROLE_MAP)
    assert actual == expected


def test_each_command_file_exists() -> None:
    for filename in COMMAND_ROLE_MAP:
        assert _command_path(filename).is_file()


def test_each_command_contains_required_substrings() -> None:
    for filename in COMMAND_ROLE_MAP:
        text = _read_command(filename)
        for required in REQUIRED_SUBSTRINGS:
            assert required in text, f"{filename} missing required substring: {required!r}"


def test_each_command_has_six_section_structure() -> None:
    for filename in COMMAND_ROLE_MAP:
        text = _read_command(filename)
        positions = [text.find(heading) for heading in REQUIRED_SECTION_HEADINGS]
        missing = [
            heading
            for heading, pos in zip(REQUIRED_SECTION_HEADINGS, positions, strict=True)
            if pos < 0
        ]
        assert not missing, f"{filename} missing section headings: {missing}"
        assert positions == sorted(positions), f"{filename} section headings out of order"


def test_original_five_role_mapping_is_one_to_one() -> None:
    assert len(ORIGINAL_FIVE_COMMAND_ROLE_MAP) == 5
    assert set(ORIGINAL_FIVE_COMMAND_ROLE_MAP.values()) == set(ALL_ORIGINAL_ROLES)
    for filename, role in ORIGINAL_FIVE_COMMAND_ROLE_MAP.items():
        text = _read_command(filename)
        unique_role_decl = f"唯一角色 = {role}"
        assert unique_role_decl in text, f"{filename} missing unique role declaration for {role}"
        for other_role in ALL_ORIGINAL_ROLES:
            if other_role == role:
                continue
            other_decl = f"唯一角色 = {other_role}"
            assert other_decl not in text, (
                f"{filename} must not declare unique role for other role {other_role}"
            )


def test_orchestrator_role_is_isolated() -> None:
    text = _read_command("orchestrate-task.md")
    assert "唯一角色 = Orchestrator" in text
    for other_role in ALL_ORIGINAL_ROLES:
        assert f"唯一角色 = {other_role}" not in text


def test_no_super_agent_merge_declaration() -> None:
    forbidden_phrases = (
        "超级 Agent",
        "合并为超级 Agent",
    )
    for filename, role in COMMAND_ROLE_MAP.items():
        text = _read_command(filename)
        assert any(phrase in text for phrase in forbidden_phrases), (
            f"{filename} must explicitly prohibit super Agent merge"
        )
        assert text.count(f"唯一角色 = {role}") == 1
        assert "唯一角色 = Planner、Plan Reviewer" not in text
        assert "唯一角色 = Planner/Plan Reviewer" not in text


def test_end_markers_match_role_and_are_not_cross_used() -> None:
    for filename, markers in REQUIRED_END_MARKERS.items():
        text = _read_command(filename)
        for marker in markers:
            assert marker in text, f"{filename} missing end marker {marker}"

    review_code = _read_command("review-code.md")
    close_task = _read_command("close-task.md")
    orchestrator = _read_command("orchestrate-task.md")

    assert "CODE_REVIEW_APPROVED" in review_code
    assert "CODE_REVIEW_REJECTED" in review_code
    assert "最后一行必须且仅为：`READY_FOR_HUMAN_COMMIT`" not in review_code
    assert "最后一行必须且仅为：READY_FOR_HUMAN_COMMIT" not in review_code

    assert "READY_FOR_HUMAN_COMMIT" in close_task
    assert "最后一行必须且仅为：`CODE_REVIEW_APPROVED`" not in close_task
    assert "最后一行必须且仅为：`CODE_REVIEW_REJECTED`" not in close_task
    assert "最后一行必须且仅为：CODE_REVIEW_APPROVED" not in close_task
    assert "最后一行必须且仅为：CODE_REVIEW_REJECTED" not in close_task

    assert "最后一行必须且仅为：`READY_FOR_COMMIT`" not in review_code
    assert "最后一行必须且仅为：`READY_FOR_COMMIT`" not in close_task
    assert "最后一行必须且仅为：READY_FOR_COMMIT" not in review_code
    assert "最后一行必须且仅为：READY_FOR_COMMIT" not in close_task

    assert "最后一行必须且仅为：`PLAN_APPROVED`" not in orchestrator
    assert "最后一行必须且仅为：`CODE_REVIEW_APPROVED`" not in orchestrator


def test_review_code_explicitly_forbids_commit_end_markers() -> None:
    text = _read_command("review-code.md")
    assert "READY_FOR_COMMIT" in text
    assert "READY_FOR_HUMAN_COMMIT" in text
    assert "禁止" in text
