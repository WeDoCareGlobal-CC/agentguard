from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Policy(BaseModel):
    agent: str
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    limits: dict = Field(default_factory=dict)

class AuditEntry(BaseModel):
    id: int | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: str
    tool: str
    input: str
    output: str
    decision: str  # ALLOWED, DENIED, APPROVAL_REQUIRED
    approved_by: str | None = None
