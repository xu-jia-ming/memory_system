"""Contract tests for DEV-OPS-004 local Mihomo network fallback policy.

Locks the authoritative AI-facing policy in 03_AI_Prompts/00_全局开发规则.md.
Static substring assertions only — no real network, /opt/mihomo, or docker pull.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GLOBAL_PROMPT_PATH = REPO_ROOT / "03_AI_Prompts" / "00_全局开发规则.md"

# English classification codes required in the policy body.
REQUIRED_CLASSIFICATION_CODES = (
    "PROXY_DOWN",
    "TRANSIENT",
    "PROXY_UP_STILL_FAILING",
    "NON_PROXY_APP_ERROR",
    "AUTH_BLOCKED",
    "PORT_CONFLICT_HINT",
)

# Failure-signal phrases that must appear (map to the codes above).
REQUIRED_FAILURE_SIGNAL_PHRASES = (
    "proxy unavailable",
    "DNS/network timeout",
    "upstream registry/server failure",
    "authentication/authorization",
    "rate limiting",
    "missing package/image/version",
    "unrelated application error",
)

# Signals that must be explicitly forbidden from proxy-failure misclassification.
NON_PROXY_MISCLASSIFICATION_GUARDS = (
    "auth",
    "404",
    "invalid digest/version",
    "rate-limit",
)


def _policy_text() -> str:
    assert GLOBAL_PROMPT_PATH.is_file(), f"missing file: {GLOBAL_PROMPT_PATH}"
    return GLOBAL_PROMPT_PATH.read_text(encoding="utf-8")


def _mihomo_section(text: str) -> str:
    marker = "本机 Mihomo 网络回退"
    assert marker in text, "Mihomo network fallback section missing"
    # Prefer the fenced fixed-constraint block content after the marker.
    start = text.index(marker)
    return text[start:]


def test_global_rules_file_exists() -> None:
    assert GLOBAL_PROMPT_PATH.is_file()


def test_environment_ports_and_unit() -> None:
    text = _policy_text()
    section = _mihomo_section(text)
    assert "17890" in section
    assert "19090" in section
    assert "mihomo" in section
    assert "mihomo.service" in section
    assert "127.0.0.1:17890" in section


def test_7890_is_ssh_forwarding_not_mihomo() -> None:
    """7890 is SSH/sshd forwarding; must not be idle or Mihomo-owned."""
    section = _mihomo_section(_policy_text())
    assert "7890" in section
    assert "SSH" in section or "sshd" in section
    assert "forwarding" in section
    assert "非空闲" in section or "非 Mihomo" in section
    assert "非 Mihomo 使用" in section
    assert "不得占用" in section or "不得" in section and "干扰" in section
    # Mihomo listens on 17890, not 7890.
    assert "Mihomo 仅使用 `127.0.0.1:17890`" in section or "Mihomo 仅使用" in section
    assert "17890" in section


def test_spec_7890_coexistence_not_silent_rewrite() -> None:
    section = _mihomo_section(_policy_text())
    assert "§3.15" in section or "3.15" in section
    assert "共存" in section or "Contract" in section
    assert "静默" in section or "不得静默改写" in section


def test_all_classification_codes_present() -> None:
    section = _mihomo_section(_policy_text())
    for code in REQUIRED_CLASSIFICATION_CODES:
        assert code in section, f"missing classification code: {code}"


def test_all_failure_signal_phrases_present() -> None:
    section = _mihomo_section(_policy_text())
    for phrase in REQUIRED_FAILURE_SIGNAL_PHRASES:
        assert phrase in section, f"missing failure-signal phrase: {phrase}"


def test_non_proxy_signals_not_misclassified_as_proxy_failure() -> None:
    section = _mihomo_section(_policy_text())
    assert "不得" in section and "误判" in section and "proxy failure" in section
    for guard in NON_PROXY_MISCLASSIFICATION_GUARDS:
        assert guard in section, f"missing non-proxy misclassification guard: {guard}"
    # Explicit NON_PROXY bucket covers auth / rate-limit / missing artifact / app error.
    assert "NON_PROXY_APP_ERROR" in section
    assert "不" in section and "代理修复" in section


def test_docker_no_adhoc_proxy() -> None:
    section = _mihomo_section(_policy_text())
    assert "ad-hoc" in section
    assert "HTTP_PROXY" in section
    assert "HTTPS_PROXY" in section
    assert "docker" in section.lower() or "docker" in section
    assert "禁止" in section


def test_health_check_readonly() -> None:
    section = _mihomo_section(_policy_text())
    assert "systemctl is-active mihomo" in section
    assert "17890" in section
    assert "19090" in section


def test_active_no_restart_for_slowness() -> None:
    section = _mihomo_section(_policy_text())
    assert "active" in section
    assert "主观慢" in section or "感觉慢" in section
    assert "restart" in section


def test_inactive_conditional_start_and_auth_halt() -> None:
    section = _mihomo_section(_policy_text())
    assert "systemctl start mihomo" in section
    assert "AUTH_BLOCKED" in section
    assert "HALT" in section
    assert "inactive" in section


def test_never_list_core_items() -> None:
    section = _mihomo_section(_policy_text())
    assert "Never" in section or "不提交" in section
    assert "/opt/mihomo" in section
    assert "7890" in section
    assert "permissions.json" in section or ".cursor/permissions.json" in section
    assert "DEV-004" in section


def test_bounded_retry() -> None:
    section = _mihomo_section(_policy_text())
    assert "有界" in section
    assert "≤3" in section or "最多" in section
    assert "HALT" in section


def test_writable_vs_nonwritable_security_boundary() -> None:
    section = _mihomo_section(_policy_text())
    assert "可写" in section or "可写入" in section
    assert "不可写" in section
    assert "Secret" in section or "secret" in section
    assert "/opt/mihomo" in section
    assert "订阅" in section or "凭据" in section


def test_working_tree_clean_plan_landing_vs_unexpected_dirty() -> None:
    """PLAN_LANDING may hold planning whitelist changes; unexpected dirty fail-closed."""
    section = _mihomo_section(_policy_text())
    assert "PLAN_LANDING" in section
    assert "planning whitelist" in section or "whitelist" in section
    assert "unexpected dirty" in section
    assert "fail-closed" in section
