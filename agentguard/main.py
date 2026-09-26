"""FastAPI service – the agentguard sidecar."""
from __future__ import annotations

import os

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .audit import add_audit, get_engine, init_db, list_audit
from .models import AuditEntry, Policy
from .policy import is_allowed, load_policy

app = FastAPI(title="agentguard", version="0.1.0")

# Trusted host (adjust for production)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Dependency: DB session
def get_db():
    engine = get_engine()
    with Session(engine, future=True) as session:
        yield session

# Load policy at startup (can be overridden via env)
POLICY_PATH = os.getenv("AGENTGUARD_POLICY", "policy.yaml")
try:
    POLICY: Policy = load_policy(POLICY_PATH)
except Exception as e:
    raise RuntimeError(f"Failed to load policy from {POLICY_PATH}: {e}")

# Ensure DB tables exist
init_db(get_engine())

class ToolCallRequest(BaseModel):
    agent: str
    tool: str
    input: str

class ToolCallResponse(BaseModel):
    decision: str  # ALLOWED, DENIED, APPROVAL_REQUIRED
    audit_id: int
    message: str | None = None

@app.post("/toolcall", response_model=ToolCallResponse)
def toolcall(req: ToolCallRequest, session: Session = Depends(get_db)):
    # Simple agent name match – extend as needed
    if req.agent != POLICY.agent:
        raise HTTPException(status_code=403, detail="Agent mismatch")

    allowed = is_allowed(POLICY, req.tool)
    decision = "ALLOWED" if allowed else "DENIED"

    # For demo, treat DENIED as requiring approval (you can change logic)
    if not allowed:
        decision = "APPROVAL_REQUIRED"

    audit_entry = add_audit(
        session,
        AuditEntry(
            agent=req.agent,
            tool=req.tool,
            input=req.input,
            output="",  # output filled later by caller
            decision=decision,
        ),
    )

    return ToolCallResponse(
        decision=decision,
        audit_id=audit_entry.id,
        message=None if allowed else "Tool denied – awaiting approval",
    )

# Optional: endpoint to fetch recent audit
@app.get("/audit", response_model=list[AuditEntry])
def get_audit(limit: int = 50, session: Session = Depends(get_db)):
    return list_audit(session, limit=limit)

if __name__ == "__main__":
    uvicorn.run("agentguard.main:app", host="0.0.0.0", port=8000, reload=False)
