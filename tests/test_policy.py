import yaml

from agentguard.audit import compute_entry_hash
from agentguard.models import AuditEntry, Limits, Policy
from agentguard.policy import (
    PolicyError,
    check_rate_limit,
    is_allowed,
    load_policy,
    reset_rate_limits,
)


def _write(tmp_path, content):
    p = tmp_path / "policy.yaml"
    p.write_text(yaml.dump(content))
    return p


def test_policy_load_and_eval(tmp_path):
    policy_content = {
        "agent": "test-bot",
        "allowed_tools": ["web_search"],
        "denied_tools": ["send_email"],
        "limits": {"max_usd_per_day": 10},
    }
    pol = load_policy(_write(tmp_path, policy_content))
    assert pol.agent == "test-bot"
    assert is_allowed(pol, "web_search") is True
    assert is_allowed(pol, "send_email") is False
    assert is_allowed(pol, "unknown_tool") is False  # not in allowed list
    # limits are now a typed model, not a bare dict
    assert pol.limits.max_usd_per_day == 10
    assert pol.limits.max_calls_per_minute is None


# --- improvement 1: enforced rate limits ---

def test_rate_limit_enforced(tmp_path):
    pol = Policy(agent="a", limits=Limits(max_calls_per_minute=3))
    reset_rate_limits()
    assert [check_rate_limit(pol, "a") for _ in range(5)] == [
        True, True, True, False, False,
    ]


def test_rate_limit_window_slides(tmp_path):
    pol = Policy(agent="a", limits=Limits(max_calls_per_minute=2))
    reset_rate_limits()
    t0, t1, t2 = 1000.0, 1001.0, 1002.0
    assert check_rate_limit(pol, "a", now=t0) is True
    assert check_rate_limit(pol, "a", now=t1) is True
    assert check_rate_limit(pol, "a", now=t2) is False  # over budget
    # 61s later the first two have fallen out of the 60s window
    assert check_rate_limit(pol, "a", now=t0 + 61) is True


def test_rate_limit_unlimited_when_unset():
    pol = Policy(agent="a", limits=Limits())
    reset_rate_limits()
    assert all(check_rate_limit(pol, "a") for _ in range(100))


def test_rate_limit_is_per_agent():
    pol = Policy(agent="a", limits=Limits(max_calls_per_minute=1))
    reset_rate_limits()
    assert check_rate_limit(pol, "a") is True
    assert check_rate_limit(pol, "a") is False
    assert check_rate_limit(pol, "other-agent") is True


# --- improvement 2: actionable policy errors ---

def test_missing_policy_gives_actionable_error(tmp_path):
    missing = tmp_path / "nope.yaml"
    try:
        load_policy(missing)
    except PolicyError as exc:
        msg = str(exc)
        assert "not found" in msg
        assert "agentguard init" in msg          # tells you how to fix it
        assert "policy.example.yaml" in msg
    else:
        raise AssertionError("expected PolicyError")


def test_policy_error_is_runtime_error_subclass():
    assert issubclass(PolicyError, RuntimeError)


def test_invalid_yaml_is_reported(tmp_path):
    bad = tmp_path / "policy.yaml"
    bad.write_text("agent: [unclosed\n")
    try:
        load_policy(bad)
    except PolicyError as exc:
        assert "not valid YAML" in str(exc)
    else:
        raise AssertionError("expected PolicyError")


# --- improvement 3: tamper-evident hash chain ---

def test_hash_is_deterministic_and_chained():
    e = AuditEntry(agent="a", tool="t", input="i", output="", decision="ALLOWED")
    h1 = compute_entry_hash(e, "")
    h2 = compute_entry_hash(e, h1)
    assert h1 == compute_entry_hash(e, "")   # stable
    assert h1 != h2                          # depends on the previous hash
    e2 = AuditEntry(agent="a", tool="t", input="TAMPERED", output="", decision="ALLOWED")
    assert compute_entry_hash(e2, h1) != h2  # any field change breaks it
