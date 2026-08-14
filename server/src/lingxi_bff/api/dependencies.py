from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from lingxi_identity import AsyncIdentityClient, Principal

from ..db.database import Database
from ..security.sessions import SessionContext


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database = request.app.state.database
    async with database.sessions() as session:
        yield session


async def get_session_context(
    request: Request, db: AsyncSession = Depends(get_db)
) -> SessionContext:
    raw_id = request.cookies.get(request.app.state.settings.session_cookie_name)
    if not raw_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "identity.unauthorized"}
        )
    context = await request.app.state.session_manager.get(db, raw_id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "identity.session_expired"}
        )
    context = cast(SessionContext, context)
    expiry = context.access_token_expires_at
    skew = request.app.state.settings.session_refresh_skew_seconds
    if expiry and expiry <= datetime.now(timezone.utc) + timedelta(seconds=skew):
        if not context.refresh_token:
            await request.app.state.session_manager.revoke(db, raw_id)
            raise HTTPException(status_code=401, detail={"code": "identity.session_expired"})
        try:
            tokens = await request.app.state.oidc.refresh(context.refresh_token)
            access_token = str(tokens["access_token"])
            id_token = tokens.get("id_token")
            claims = context.claims
            expires_in = tokens.get("expires_in")
            refreshed = await request.app.state.session_manager.rotate(
                db,
                raw_id,
                access_token=access_token,
                refresh_token=tokens.get("refresh_token"),
                id_token=str(id_token) if id_token else None,
                claims=claims,
                access_token_expires_at=(
                    datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                    if expires_in
                    else None
                ),
                refresh_token_expires_at=(
                    datetime.now(timezone.utc) + timedelta(seconds=int(tokens["expires_in"]))
                    if tokens.get("expires_in") and tokens.get("refresh_token")
                    else context.refresh_token_expires_at
                ),
            )
            if refreshed is None:
                raise RuntimeError("session was revoked during refresh")
            context = cast(SessionContext, refreshed)
        except Exception as exc:
            await request.app.state.session_manager.revoke(db, raw_id)
            raise HTTPException(
                status_code=401, detail={"code": "identity.session_refresh_failed"}
            ) from exc
    return context


async def get_principal(context: SessionContext = Depends(get_session_context)) -> Principal:
    return context.principal


async def get_identity(request: Request) -> AsyncIdentityClient:
    client = request.app.state.identity
    if client is None:
        raise HTTPException(status_code=503, detail={"code": "identity.management_unavailable"})
    return client


def require_permission(permission: str) -> Callable[..., Any]:
    async def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if (
            permission not in principal.permissions
            and "identity.admin" not in principal.permissions
            and "identity.admin" not in principal.roles
        ):
            raise HTTPException(
                status_code=403, detail={"code": "identity.forbidden", "permission": permission}
            )
        return principal

    return dependency


async def validate_csrf(
    request: Request,
    context: SessionContext = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    token = request.headers.get("X-CSRF-Token", "")
    raw_id = request.cookies.get(request.app.state.settings.session_cookie_name, "")
    if (
        not token
        or not raw_id
        or not await request.app.state.session_manager.csrf_valid(db, raw_id, token)
    ):
        raise HTTPException(status_code=403, detail={"code": "identity.csrf_failed"})
