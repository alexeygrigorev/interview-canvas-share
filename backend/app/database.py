"""SQLAlchemy database configuration and persistence models."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL_ENV = "SDIP_DATABASE_URL"
DEFAULT_DATABASE_URL = "sqlite:///./sdip.db"


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    organization_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    password_hash: Mapped[str] = mapped_column(Text)


class InterviewSessionRow(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), index=True)
    candidate_editing_enabled: Mapped[bool] = mapped_column(Boolean)
    cursors_visible: Mapped[bool] = mapped_column(Boolean)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ParticipantRow(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    connection: Mapped[str] = mapped_column(String(20))
    cursor: Mapped[dict[str, float] | None] = mapped_column(JSON)


class GuestLinkRow(Base):
    __tablename__ = "guest_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role_granted: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int | None] = mapped_column(Integer)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GuestSessionRow(Base):
    __tablename__ = "guest_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CanvasRow(Base):
    __tablename__ = "canvases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id"), unique=True, index=True
    )
    schema_version: Mapped[int] = mapped_column(Integer)
    elements: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id"), index=True
    )
    event: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[str] = mapped_column(String(200))


def database_url() -> str:
    """Return the configured SQLAlchemy URL."""

    return os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)


def create_database_engine(url: str | None = None) -> Engine:
    """Create an engine without coupling the application to a specific backend."""

    resolved_url = url or database_url()
    options: dict[str, object] = {"pool_pre_ping": True}
    if resolved_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if resolved_url in {"sqlite://", "sqlite:///:memory:"}:
            options["poolclass"] = StaticPool
        elif resolved_url.startswith("sqlite:///"):
            database_path = Path(resolved_url.removeprefix("sqlite:///"))
            if str(database_path) != ":memory:":
                database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(resolved_url, **options)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
