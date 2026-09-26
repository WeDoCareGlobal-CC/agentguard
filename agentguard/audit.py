"""Append-only audit log using SQLite + SQLAlchemy."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import Session, declarative_base

from .models import AuditEntry

Base = declarative_base()


class AuditORM(Base):
    __tablename__ = "audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    agent = Column(String, index=True, nullable=False)
    tool = Column(String, nullable=False)
    input_ = Column("input", Text, nullable=False)
    output_ = Column("output", Text, nullable=False)
    decision = Column(String, nullable=False)
    approved_by = Column(String, nullable=True)
    prev_hash = Column(String(64), nullable=False, default="")
    entry_hash = Column(String(64), nullable=False, default="")

    def to_model(self) -> AuditEntry:
        return AuditEntry(
            id=self.id,
            timestamp=self.timestamp,
            agent=self.agent,
            tool=self.tool,
            input=self.input_,
            output=self.output_,
            decision=self.decision,
            approved_by=self.approved_by,
            prev_hash=self.prev_hash or "",
            entry_hash=self.entry_hash or "",
        )


def get_engine(db_url: str | None = None):
    if db_url is None:
        db_url = os.getenv("DATABASE_URL", "sqlite:///./data/audit.db")
    # sqlite refuses to create a file in a missing directory -> make it first.
    prefix = "sqlite:///"
    if db_url.startswith(prefix):
        raw = db_url[len(prefix):].lstrip("/")
        if raw and raw != ":memory:":
            parent = pathlib.Path(raw).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
    return create_engine(db_url, future=True, echo=False)


def init_db(engine):
    Base.metadata.create_all(engine)


def _payload(e: AuditEntry) -> str:
    """Canonical serialisation of an entry, excluding the hash fields."""
    return json.dumps(
        {
            "timestamp": e.timestamp.isoformat(),
            "agent": e.agent,
            "tool": e.tool,
            "input": e.input,
            "output": e.output,
            "decision": e.decision,
            "approved_by": e.approved_by,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def compute_entry_hash(entry: AuditEntry, prev_hash: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{_payload(entry)}".encode()).hexdigest()


def add_audit(session: Session, entry: AuditEntry) -> AuditEntry:
    orm = AuditORM(
        timestamp=entry.timestamp,
        agent=entry.agent,
        tool=entry.tool,
        input_=entry.input,
        output_=entry.output,
        decision=entry.decision,
        approved_by=entry.approved_by,
    )
    last = session.scalars(select(AuditORM).order_by(AuditORM.id.desc()).limit(1)).first()
    prev = last.entry_hash if last is not None else ""
    entry.prev_hash = prev
    entry.entry_hash = compute_entry_hash(entry, prev)

    orm.prev_hash = prev
    orm.entry_hash = entry.entry_hash

    session.add(orm)
    session.commit()
    session.refresh(orm)
    return orm.to_model()


def verify_chain(session: Session) -> tuple[bool, int]:
    """Walk the audit table oldest->newest and recompute every hash.

    Returns (ok, first_broken_id). ok is False as soon as a row's stored
    prev_hash does not match its predecessor's entry_hash, or a row's
    entry_hash does not match its recomputed value.
    """
    rows = session.scalars(select(AuditORM).order_by(AuditORM.id.asc())).all()
    prev = ""
    for row in rows:
        if row.prev_hash != prev:
            return False, row.id
        model = row.to_model()
        if row.entry_hash != compute_entry_hash(model, prev):
            return False, row.id
        prev = row.entry_hash
    return True, -1


def list_audit(session: Session, limit: int = 100) -> list[AuditEntry]:
    stmt = select(AuditORM).order_by(AuditORM.id.desc()).limit(limit)
    return [r.to_model() for r in session.scalars(stmt).all()]
