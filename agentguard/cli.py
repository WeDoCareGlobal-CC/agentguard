"""Typer‑based CLI for agentguard."""
from __future__ import annotations

import os
from pathlib import Path

import typer
import uvicorn
import yaml

from .policy import Policy, load_policy

app = typer.Typer(add_completion=False, help="agentguard CLI")
# Back-compat alias: earlier docs/READMEs refer to `cli`.
cli = app

@app.command()
def init(
    agent: str = typer.Option(..., help="Agent name, e.g. research-bot"),
    out: Path = typer.Option("policy.yaml", help="Where to write example policy"),
):
    """Create a starter policy.yaml."""
    example = Policy(
        agent=agent,
        allowed_tools=["web_search", "read_file"],
        denied_tools=["send_email", "transfer_funds"],
        limits={"max_usd_per_day": 5.00, "max_tokens_per_call": 4000},
    )
    out.write_text(yaml.dump(example.model_dump(), sort_keys=False))
    typer.secho(f"✅ Example policy written to {out}", fg=typer.colors.GREEN)

@app.command()
def run(
    policy: Path = typer.Option("policy.yaml", help="Path to policy YAML"),
    host: str = typer.Option("0.0.0.0", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
    reload: bool = typer.Option(False, help="Enable uvicorn reload (dev)"),
):
    """Run the agentguard FastAPI server."""
    # Validate policy early
    try:
        load_policy(policy)
    except Exception as e:
        typer.secho(f"❌ Invalid policy: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(f"🚀 Starting agentguard on http://{host}:{port}", fg=typer.colors.BLUE)
    # uvicorn.run() has no `env` parameter: set it in the process environment
    # so agentguard.main picks the policy path up at import time.
    os.environ["AGENTGUARD_POLICY"] = str(policy)
    uvicorn.run(
        "agentguard.main:app",
        host=host,
        port=port,
        reload=reload,
    )

if __name__ == "__main__":
    app()
