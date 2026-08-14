from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingxi_identity import Principal, principal_from_claims

from ..db.models import BffSession


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _expired(value: datetime) -> bool:
    normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return normalized <= datetime.now(timezone.utc)


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    principal: Principal
    claims: dict[str, Any]
    access_token: str
    refresh_token: str | None
    csrf_token: str
    access_token_expires_at: datetime | None = None
    refresh_token_expires_at: datetime | None = None


class SessionManager:
    def __init__(self, *, key: str, ttl_seconds: int, claims_namespace: str) -> None:
        self.cipher = Fernet(key.encode("ascii"))
        self.ttl_seconds = ttl_seconds
        self.claims_namespace = claims_namespace

    def _encrypt(self, value: str | None) -> str | None:
        return self.cipher.encrypt(value.encode()).decode() if value else None

    def _decrypt(self, value: str | None) -> str | None:
        return self.cipher.decrypt(value.encode()).decode() if value else None

    async def create(
        self,
        db: AsyncSession,
        *,
        claims: dict[str, Any],
        access_token: str,
        refresh_token: str | None,
        id_token: str | None,
        access_token_expires_at: datetime | None = None,
        refresh_token_expires_at: datetime | None = None,
    ) -> SessionContext:
        raw_id = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        record = BffSession(
            id_hash=_hash(raw_id),
            subject=str(claims["sub"]),
            encrypted_access_token=self._encrypt(access_token) or "",
            encrypted_refresh_token=self._encrypt(refresh_token),
            encrypted_id_token=self._encrypt(id_token),
            access_token_expires_at=access_token_expires_at,
            refresh_token_expires_at=refresh_token_expires_at,
            token_updated_at=now,
            claims=claims,
            csrf_hash=_hash(csrf),
            encrypted_csrf_token=self._encrypt(csrf) or "",
            expires_at=now + timedelta(seconds=self.ttl_seconds),
            created_at=now,
            last_seen_at=now,
        )
        db.add(record)
        await db.commit()
        return SessionContext(
            raw_id,
            principal_from_claims(claims, claims_namespace=self.claims_namespace),
            claims,
            access_token,
            refresh_token,
            csrf,
            access_token_expires_at,
            refresh_token_expires_at,
        )

    async def get(self, db: AsyncSession, raw_id: str) -> SessionContext | None:
        record = await db.get(BffSession, _hash(raw_id))
        if not record or record.revoked_at or _expired(record.expires_at):
            return None
        record.last_seen_at = datetime.now(timezone.utc)
        await db.commit()
        return SessionContext(
            raw_id,
            principal_from_claims(record.claims, claims_namespace=self.claims_namespace),
            record.claims,
            self._decrypt(record.encrypted_access_token) or "",
            self._decrypt(record.encrypted_refresh_token),
            self._decrypt(record.encrypted_csrf_token) or "",
            record.access_token_expires_at,
            record.refresh_token_expires_at,
        )

    async def rotate(
        self,
        db: AsyncSession,
        raw_id: str,
        *,
        access_token: str,
        refresh_token: str | None,
        id_token: str | None,
        claims: dict[str, Any],
        access_token_expires_at: datetime | None,
        refresh_token_expires_at: datetime | None,
    ) -> SessionContext | None:
        result = await db.execute(
            select(BffSession).where(BffSession.id_hash == _hash(raw_id)).with_for_update()
        )
        record = result.scalar_one_or_none()
        if not record or record.revoked_at or _expired(record.expires_at):
            return None
        now = datetime.now(timezone.utc)
        record.subject = str(claims["sub"])
        record.claims = claims
        record.encrypted_access_token = self._encrypt(access_token) or ""
        if refresh_token is not None:
            record.encrypted_refresh_token = self._encrypt(refresh_token)
        if id_token is not None:
            record.encrypted_id_token = self._encrypt(id_token)
        record.access_token_expires_at = access_token_expires_at
        record.refresh_token_expires_at = refresh_token_expires_at
        record.token_updated_at = now
        record.last_seen_at = now
        await db.commit()
        return SessionContext(
            raw_id,
            principal_from_claims(claims, claims_namespace=self.claims_namespace),
            claims,
            access_token,
            refresh_token
            if refresh_token is not None
            else self._decrypt(record.encrypted_refresh_token),
            self._decrypt(record.encrypted_csrf_token) or "",
            access_token_expires_at,
            refresh_token_expires_at,
        )

    async def revoke_subject(self, db: AsyncSession, subject: str) -> None:
        await db.execute(
            update(BffSession)
            .where(BffSession.subject == subject, BffSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()

    async def csrf_token(self, db: AsyncSession, raw_id: str) -> str | None:
        record = await db.get(BffSession, _hash(raw_id))
        if not record or record.revoked_at or _expired(record.expires_at):
            return None
        return self._decrypt(record.encrypted_csrf_token)

    async def csrf_valid(self, db: AsyncSession, raw_id: str, csrf_token: str) -> bool:
        record = await db.get(BffSession, _hash(raw_id))
        return bool(
            record
            and not record.revoked_at
            and not _expired(record.expires_at)
            and secrets.compare_digest(record.csrf_hash, _hash(csrf_token))
        )

    async def revoke(self, db: AsyncSession, raw_id: str) -> None:
        await db.execute(
            update(BffSession)
            .where(BffSession.id_hash == _hash(raw_id))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()
