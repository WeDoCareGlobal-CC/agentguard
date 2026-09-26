"""Append-only audit log using SQLite + SQLAlchemy."""
from __future__ import annotations

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
    session.add(orm)
    session.commit()
    session.refresh(orm)
    return orm.to_model()


def list_audit(session: Session, limit: int = 100) -> list[AuditEntry]:
    stmt = select(AuditORM).order_by(AuditORM.id.desc()).limit(limit)
    return [r.to_model() for r in session.scalars(stmt).all()]
