import yaml

from agentguard.policy import is_allowed, load_policy


def test_policy_load_and_eval(tmp_path):
    policy_content = {
        "agent": "test-bot",
        "allowed_tools": ["web_search"],
        "denied_tools": ["send_email"],
        "limits": {"max_usd_per_day": 10},
    }
    p = tmp_path / "policy.yaml"
    p.write_text(yaml.dump(policy_content))
    pol = load_policy(p)
    assert pol.agent == "test-bot"
    assert is_allowed(pol, "web_search") is True
    assert is_allowed(pol, "send_email") is False
    assert is_allowed(pol, "unknown_tool") is False  # not in allowed list
