from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BffSession(Base):
    __tablename__ = "bff_sessions"
    __table_args__ = (
        Index("ix_bff_sessions_subject", "subject"),
        Index("ix_bff_sessions_expires_at", "expires_at"),
    )

    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(256), nullable=False)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_id_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    claims: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_csrf_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
