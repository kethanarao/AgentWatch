from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import settings


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RecordMixin:
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    payload: Mapped[dict] = mapped_column(JSON)


class Trace(RecordMixin, Base):
    __tablename__ = "traces"


class Span(RecordMixin, Base):
    __tablename__ = "spans"
    trace_id: Mapped[str] = mapped_column(String(80), index=True)


class Evaluation(RecordMixin, Base):
    __tablename__ = "evaluations"


class ToolCall(RecordMixin, Base):
    __tablename__ = "tool_calls"
    trace_id: Mapped[str] = mapped_column(String(80), index=True)


class Alert(RecordMixin, Base):
    __tablename__ = "alerts"


class Feedback(RecordMixin, Base):
    __tablename__ = "feedback"


class Candidate(RecordMixin, Base):
    __tablename__ = "candidate_regression_cases"


class Experiment(RecordMixin, Base):
    __tablename__ = "experiments"


class RegressionRun(RecordMixin, Base):
    __tablename__ = "regression_runs"


class DriftSnapshot(RecordMixin, Base):
    __tablename__ = "drift_snapshots"


class Store:
    def __init__(self, url: str = settings.database_url):
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if ":memory:" in url:
                from sqlalchemy.pool import StaticPool

                kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)
        Base.metadata.create_all(self.engine)

    def put(self, model, id: str, payload: dict, **extra):
        with Session(self.engine) as session:
            row = session.get(model, id)
            if row:
                row.payload = payload
            else:
                session.add(model(id=id, payload=payload, **extra))
            session.commit()

    def get(self, model, id: str):
        with Session(self.engine) as session:
            row = session.get(model, id)
            return row.payload if row else None

    def list(self, model, limit: int = 1000):
        with Session(self.engine) as session:
            return [
                r.payload
                for r in session.scalars(
                    select(model).order_by(model.created_at.desc()).limit(limit)
                )
            ]

    def save_trace(self, trace: dict):
        # Atomic trace persistence: the explorer never sees a partially committed request.
        with Session(self.engine) as session:
            when = datetime.fromisoformat(trace["timestamp"])
            session.add(Trace(id=trace["trace_id"], payload=trace, created_at=when))
            session.add(
                Evaluation(
                    id=trace["trace_id"],
                    payload={
                        "trace_id": trace["trace_id"],
                        "timestamp": trace["timestamp"],
                        **trace["evaluation"],
                    },
                    created_at=when,
                )
            )
            for span in trace["spans"]:
                session.add(
                    Span(
                        id=span["span_id"],
                        trace_id=trace["trace_id"],
                        payload=span,
                        created_at=when,
                    )
                )
            for call in trace["tool_calls"]:
                session.add(
                    ToolCall(
                        id=call["id"], trace_id=trace["trace_id"], payload=call, created_at=when
                    )
                )
            session.commit()
