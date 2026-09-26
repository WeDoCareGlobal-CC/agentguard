"""Simple YAML policy loader and evaluator."""
from __future__ import annotations

from pathlib import Path

import yaml

from .models import Policy


def load_policy(path: str | Path) -> Policy:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Policy(**data)

def is_allowed(policy: Policy, tool: str) -> bool:
    if tool in policy.denied_tools:
        return False
    if policy.allowed_tools and tool not in policy.allowed_tools:
        return False
    return True
