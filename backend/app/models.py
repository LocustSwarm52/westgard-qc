"""Database tables."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="tech")  # tech | supervisor


class Control(Base):
    """One control material at one level, on one instrument, for one analyte."""
    __tablename__ = "controls"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument: Mapped[str] = mapped_column(String(100))
    analyte: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(50))
    lot: Mapped[str] = mapped_column(String(50))
    target_mean: Mapped[float]
    target_sd: Mapped[float]
    units: Mapped[str] = mapped_column(String(30), default="")
    active: Mapped[bool] = mapped_column(default=True)
    results: Mapped[list["Result"]] = relationship(back_populates="control", order_by="Result.measured_at")


class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("controls.id"), index=True)
    value: Mapped[float]
    run_id: Mapped[str] = mapped_column(String(50), index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    entered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(10), default="accept")  # accept | warning | reject
    control: Mapped[Control] = relationship(back_populates="results")
    violations: Mapped[list["Violation"]] = relationship(back_populates="result", cascade="all, delete-orphan")


class Violation(Base):
    __tablename__ = "violations"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("results.id"), index=True)
    rule: Mapped[str] = mapped_column(String(10))
    scope: Mapped[str] = mapped_column(String(20))  # across-runs | within-run
    corrective_action: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[Result] = relationship(back_populates="violations")


class AuditEntry(Base):
    """Who changed what, and when."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str] = mapped_column(Text, default="")
