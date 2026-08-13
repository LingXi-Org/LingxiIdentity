from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from lingxi_identity import (
    AsyncIdentityClient,
    AuditEvent,
    Organization,
    Page,
    Principal,
    Role,
    User,
)

from ..security.sessions import SessionContext
from .dependencies import (
    get_db,
    get_identity,
    get_principal,
    get_session_context,
    require_permission,
    validate_csrf,
)
from .schemas import (
    CsrfResponse,
    EmailPatch,
    MemberAssignment,
    OrganizationCreate,
    OrganizationPatch,
    PasswordPatch,
    PasswordVerification,
    ProfilePatch,
    RoleAssignment,
    RoleCreate,
    RolePatch,
    UserCreate,
    UserPatch,
    SessionItem,
    VerificationCodeRequest,
    VerificationCodeSend,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
api_router = APIRouter(prefix="/api/v1", tags=["identity"])


async def _revoke_subject(request: Request, db: AsyncSession, subject: str) -> None:
    await request.app.state.session_manager.revoke_subject(db, subject)


def _safe_next_path(value: str) -> str:
    return value if value.startswith("/") and not value.startswith("//") and "\\" not in value else "/"


@auth_router.get("/login")
async def login(request: Request, next_path: str = "/") -> Response:
    url, state = await request.app.state.oidc.authorize(
        next_path=_safe_next_path(next_path)
    )
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "lingxi_oauth_state",
        state,
        httponly=True,
        secure=request.app.state.settings.session_cookie_secure,
        samesite="lax",
        max_age=600,
        path=getattr(request.app.state.settings, "oidc_redirect_path", "/auth/callback"),
    )
    return response


async def _auth_entry(request: Request, *, first_screen: str, next_path: str) -> Response:
    url, state = await request.app.state.oidc.authorize(
        next_path=_safe_next_path(next_path),
        # Only relative paths are carried through the signed OAuth state.
        extra_params={"first_screen": first_screen},
    )
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "lingxi_oauth_state",
        state,
        httponly=True,
        secure=request.app.state.settings.session_cookie_secure,
        samesite="lax",
        max_age=600,
        path=getattr(request.app.state.settings, "oidc_redirect_path", "/auth/callback"),
    )
    return response


@auth_router.get("/register")
async def register(request: Request, next_path: str = "/") -> Response:
    return await _auth_entry(request, first_screen="register", next_path=next_path)


@auth_router.get("/forgot-password")
async def forgot_password(request: Request, next_path: str = "/") -> Response:
    return await _auth_entry(request, first_screen="reset_password", next_path=next_path)


@auth_router.get("/callback")
async def callback(
    request: Request, code: str, state: str, db: AsyncSession = Depends(get_db)
) -> Response:
    signed_state = request.cookies.get("lingxi_oauth_state")
    if not signed_state:
        raise HTTPException(status_code=400, detail={"code": "identity.oauth_state_missing"})
    try:
        oauth_state = request.app.state.oidc.decode_state(signed_state)
    except ValueError:
        response = JSONResponse({"code": "identity.oauth_state_invalid"}, status_code=400)
        response.delete_cookie("lingxi_oauth_state", path=request.app.state.settings.oidc_redirect_path)
        return response
    if state != oauth_state.state:
        response = JSONResponse({"code": "identity.oauth_state_mismatch"}, status_code=400)
        response.delete_cookie("lingxi_oauth_state", path=request.app.state.settings.oidc_redirect_path)
        return response
    tokens = await request.app.state.oidc.exchange(code=code, state=oauth_state)
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail={"code": "identity.id_token_missing"})
    access_token = str(tokens["access_token"])
    try:
        id_claims = request.app.state.oidc.verifier().decode(id_token, nonce=oauth_state.nonce)
        access_claims = request.app.state.oidc.verifier(
            audience=request.app.state.settings.oidc_resource
        ).decode(access_token)
        if id_claims.get("sub") != access_claims.get("sub"):
            raise ValueError("OIDC subject mismatch between ID token and access token")
        claims = {**id_claims, **access_claims}
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"code": "identity.id_token_invalid"}) from exc
    expires_in = tokens.get("expires_in")
    access_expiry = request.app.state.oidc.token_expiry(access_claims)
    refresh_expiry = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in and tokens.get("refresh_token")
        else None
    )
    context = await request.app.state.session_manager.create(
        db,
        claims=claims,
        access_token=access_token,
        refresh_token=tokens.get("refresh_token"),
        id_token=id_token,
        access_token_expires_at=access_expiry,
        refresh_token_expires_at=refresh_expiry,
    )
    response = RedirectResponse(oauth_state.next_path, status_code=302)
    response.delete_cookie("lingxi_oauth_state", path=request.app.state.settings.oidc_redirect_path)
    response.set_cookie(
        request.app.state.settings.session_cookie_name,
        context.session_id,
        httponly=True,
        secure=request.app.state.settings.session_cookie_secure,
        samesite="lax",
        max_age=request.app.state.settings.session_ttl_seconds,
        path=request.app.state.settings.session_cookie_path,
        domain=request.app.state.settings.session_cookie_domain or None,
    )
    return response


@auth_router.get("/csrf", response_model=CsrfResponse)
async def csrf(
    request: Request,
    context: SessionContext = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
) -> CsrfResponse:
    raw_id = request.cookies.get(request.app.state.settings.session_cookie_name, "")
    token = await request.app.state.session_manager.csrf_token(db, raw_id)
    if not token:
        raise HTTPException(status_code=401, detail={"code": "identity.session_expired"})
    return CsrfResponse(csrfToken=token)


@auth_router.post("/refresh", dependencies=[Depends(validate_csrf)])
async def refresh(
    request: Request,
    context: SessionContext = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    raw_id = request.cookies.get(request.app.state.settings.session_cookie_name, "")
    if not context.refresh_token:
        raise HTTPException(status_code=401, detail={"code": "identity.refresh_unavailable"})
    try:
        tokens = await request.app.state.oidc.refresh(context.refresh_token)
        access_token = str(tokens["access_token"])
        access_claims = request.app.state.oidc.verifier(
            audience=request.app.state.settings.oidc_resource
        ).decode(access_token)
        claims = {**context.claims, **access_claims}
        rotated = await request.app.state.session_manager.rotate(
            db,
            raw_id,
            access_token=access_token,
            refresh_token=tokens.get("refresh_token"),
            id_token=tokens.get("id_token"),
            claims=claims,
            access_token_expires_at=request.app.state.oidc.token_expiry(access_claims),
            refresh_token_expires_at=(
                datetime.now(timezone.utc) + timedelta(seconds=int(tokens["expires_in"]))
                if tokens.get("expires_in") and tokens.get("refresh_token")
                else context.refresh_token_expires_at
            ),
        )
        if rotated is None:
            raise RuntimeError("session was revoked")
        return {"ok": True, "expiresAt": rotated.access_token_expires_at}
    except Exception as exc:
        await request.app.state.session_manager.revoke(db, raw_id)
        raise HTTPException(status_code=401, detail={"code": "identity.session_refresh_failed"}) from exc


@auth_router.post("/logout", dependencies=[Depends(validate_csrf)])
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: SessionContext = Depends(get_session_context),
) -> Response:
    raw_id = request.cookies.get(request.app.state.settings.session_cookie_name)
    if raw_id:
        await request.app.state.session_manager.revoke(db, raw_id)
    for token, hint in ((context.refresh_token, "refresh_token"), (context.access_token, "access_token")):
        if token:
            try:
                await request.app.state.oidc.revoke(token, token_type_hint=hint)
            except Exception:
                # Local revocation and cookie clearing remain authoritative if the provider is down.
                pass
    response = JSONResponse({"ok": True})
    response.delete_cookie(
        request.app.state.settings.session_cookie_name,
        path=request.app.state.settings.session_cookie_path,
        domain=request.app.state.settings.session_cookie_domain or None,
    )
    return response


@api_router.get("/me")
async def me(
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> dict[str, Any]:
    profile = await client.account.get_profile(context.access_token)
    return {"principal": context.principal.model_dump(), "user": profile.model_dump(by_alias=True)}


@api_router.patch("/me/profile", dependencies=[Depends(validate_csrf)])
async def update_me_profile(
    body: ProfilePatch,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> User:
    changes = body.model_dump(by_alias=True, exclude_none=True)
    verification_id = changes.pop("verificationId", None)
    profile = changes.pop("profile", None)
    result = await client.account.update_profile(
        context.access_token, changes, verification_id=verification_id
    )
    if profile is not None:
        await client.account.update_other_profile(context.access_token, profile)
        result = await client.account.get_profile(context.access_token)
    return result


@api_router.post("/me/verifications/password", dependencies=[Depends(validate_csrf)])
async def verify_me_password(
    body: PasswordVerification,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> dict[str, Any]:
    record = await client.account.verify_password(context.access_token, body.password.get_secret_value())
    return record.model_dump(by_alias=True)


@api_router.post("/me/verifications/email", dependencies=[Depends(validate_csrf)])
async def send_me_email_code(
    body: VerificationCodeSend,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> dict[str, Any]:
    record = await client.account.send_verification_code(
        context.access_token,
        identifier_type=body.identifier_type,
        identifier=body.identifier,
    )
    return record.model_dump(by_alias=True)


@api_router.post("/me/verifications/email/verify", dependencies=[Depends(validate_csrf)])
async def verify_me_email_code(
    body: VerificationCodeRequest,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> dict[str, Any]:
    record = await client.account.verify_code(
        context.access_token,
        identifier_type=body.identifier_type,
        identifier=body.identifier,
        verification_id=body.verification_id,
        code=body.code,
    )
    return record.model_dump(by_alias=True)


@api_router.patch("/me/email", dependencies=[Depends(validate_csrf)])
async def update_me_email(
    body: EmailPatch,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> User:
    return await client.account.update_email(
        context.access_token,
        verification_id=body.verification_id,
        email=body.email,
        new_identifier_verification_id=body.new_identifier_verification_id,
    )


@api_router.post("/me/password", dependencies=[Depends(validate_csrf)])
async def update_me_password(
    body: PasswordPatch,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> Response:
    await client.account.update_password(
        context.access_token,
        verification_id=body.verification_id,
        password=body.password.get_secret_value(),
    )
    return Response(status_code=204)


@api_router.get("/me/sessions")
async def list_me_sessions(
    request: Request,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> list[SessionItem]:
    sessions = await client.account.list_sessions(
        context.access_token,
        verification_id=request.headers.get("X-Logto-Verification-Id"),
    )
    return [SessionItem.model_validate(item.model_dump(by_alias=True)) for item in sessions]


@api_router.delete("/me/sessions/{session_id}", status_code=204, dependencies=[Depends(validate_csrf)])
async def revoke_me_session(
    session_id: str,
    request: Request,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
) -> Response:
    await client.account.revoke_session(context.access_token, session_id)
    return Response(status_code=204)


@api_router.post("/me/deactivate", dependencies=[Depends(validate_csrf)])
async def deactivate_me(
    request: Request,
    context: SessionContext = Depends(get_session_context),
    client: AsyncIdentityClient = Depends(get_identity),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await client.users.update(context.principal.subject, {"isSuspended": True})
    await client.users.revoke_all_sessions(context.principal.subject)
    await request.app.state.session_manager.revoke_subject(db, context.principal.subject)
    response = Response(status_code=204)
    response.delete_cookie(
        request.app.state.settings.session_cookie_name,
        path=request.app.state.settings.session_cookie_path,
        domain=request.app.state.settings.session_cookie_domain or None,
    )
    return response


@api_router.get("/users", dependencies=[Depends(require_permission("identity.users.read"))])
async def list_users(
    client: AsyncIdentityClient = Depends(get_identity),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
) -> Page[User]:
    return await client.users.list(page=page, page_size=page_size, search=search)


@api_router.post(
    "/users",
    dependencies=[Depends(require_permission("identity.users.write")), Depends(validate_csrf)],
)
async def create_user(
    body: UserCreate, client: AsyncIdentityClient = Depends(get_identity)
) -> User:
    payload = body.model_dump(by_alias=True, exclude_none=True)
    if body.password is not None:
        payload["password"] = body.password.get_secret_value()
    return await client.users.create(payload)


@api_router.get(
    "/users/{user_id}", dependencies=[Depends(require_permission("identity.users.read"))]
)
async def get_user(user_id: str, client: AsyncIdentityClient = Depends(get_identity)) -> User:
    return await client.users.get(user_id)


@api_router.patch(
    "/users/{user_id}",
    dependencies=[Depends(require_permission("identity.users.write")), Depends(validate_csrf)],
)
async def update_user(
    user_id: str,
    body: UserPatch,
    request: Request,
    client: AsyncIdentityClient = Depends(get_identity),
    db: AsyncSession = Depends(get_db),
) -> User:
    changes = body.model_dump(by_alias=True, exclude_none=True)
    user = await client.users.update(user_id, changes)
    if body.suspended is True:
        await _revoke_subject(request, db, user_id)
    return user


@api_router.post(
    "/users/{user_id}/suspend",
    dependencies=[Depends(require_permission("identity.users.write")), Depends(validate_csrf)],
)
async def suspend_user(
    user_id: str,
    request: Request,
    client: AsyncIdentityClient = Depends(get_identity),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await client.users.update(user_id, {"isSuspended": True})
    await client.users.revoke_all_sessions(user_id)
    await _revoke_subject(request, db, user_id)
    return user


@api_router.post(
    "/users/{user_id}/restore",
    dependencies=[Depends(require_permission("identity.users.write")), Depends(validate_csrf)],
)
async def restore_user(
    user_id: str, client: AsyncIdentityClient = Depends(get_identity)
) -> User:
    return await client.users.update(user_id, {"isSuspended": False})


@api_router.delete(
    "/users/{user_id}",
    status_code=204,
    dependencies=[Depends(require_permission("identity.users.write")), Depends(validate_csrf)],
)
async def delete_user(
    user_id: str,
    request: Request,
    client: AsyncIdentityClient = Depends(get_identity),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _revoke_subject(request, db, user_id)
    await client.users.revoke_all_sessions(user_id)
    await client.users.delete(user_id)
    return Response(status_code=204)


@api_router.get("/roles", dependencies=[Depends(require_permission("identity.roles.read"))])
async def list_roles(
    client: AsyncIdentityClient = Depends(get_identity),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[Role]:
    return await client.roles.list(page=page, page_size=page_size)


@api_router.post(
    "/roles",
    dependencies=[Depends(require_permission("identity.roles.write")), Depends(validate_csrf)],
)
async def create_role(
    body: RoleCreate, client: AsyncIdentityClient = Depends(get_identity)
) -> Role:
    return await client.roles.create(body.model_dump(by_alias=True))


@api_router.patch(
    "/roles/{role_id}",
    dependencies=[Depends(require_permission("identity.roles.write")), Depends(validate_csrf)],
)
async def update_role(
    role_id: str, body: RolePatch, client: AsyncIdentityClient = Depends(get_identity)
) -> Role:
    return await client.roles.update(role_id, body.model_dump(exclude_none=True))


@api_router.put(
    "/users/{user_id}/roles",
    dependencies=[Depends(require_permission("identity.roles.write")), Depends(validate_csrf)],
)
async def set_user_roles(
    user_id: str, body: RoleAssignment, client: AsyncIdentityClient = Depends(get_identity)
) -> Response:
    await client.users.set_roles(user_id, body.role_ids)
    return Response(status_code=204)


@api_router.get(
    "/organizations", dependencies=[Depends(require_permission("identity.organizations.read"))]
)
async def list_organizations(
    client: AsyncIdentityClient = Depends(get_identity),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[Organization]:
    return await client.organizations.list(page=page, page_size=page_size)


@api_router.post(
    "/organizations",
    dependencies=[
        Depends(require_permission("identity.organizations.write")),
        Depends(validate_csrf),
    ],
)
async def create_organization(
    body: OrganizationCreate, client: AsyncIdentityClient = Depends(get_identity)
) -> Organization:
    return await client.organizations.create(body.model_dump(by_alias=True))


@api_router.patch(
    "/organizations/{organization_id}",
    dependencies=[
        Depends(require_permission("identity.organizations.write")),
        Depends(validate_csrf),
    ],
)
async def update_organization(
    organization_id: str,
    body: OrganizationPatch,
    client: AsyncIdentityClient = Depends(get_identity),
) -> Organization:
    return await client.organizations.update(
        organization_id, body.model_dump(by_alias=True, exclude_none=True)
    )


@api_router.delete(
    "/organizations/{organization_id}",
    status_code=204,
    dependencies=[
        Depends(require_permission("identity.organizations.write")),
        Depends(validate_csrf),
    ],
)
async def delete_organization(
    organization_id: str, client: AsyncIdentityClient = Depends(get_identity)
) -> Response:
    await client.organizations.delete(organization_id)
    return Response(status_code=204)


def _assert_tenant(principal: Principal, organization_id: str) -> None:
    if (
        principal.tenant_id != organization_id
        and "identity.admin" not in principal.roles
        and "identity.admin" not in principal.permissions
    ):
        raise HTTPException(status_code=403, detail={"code": "identity.tenant_mismatch"})


@api_router.get(
    "/organizations/{organization_id}/roles",
    dependencies=[Depends(require_permission("identity.organizations.read"))],
)
async def list_organization_roles(
    organization_id: str,
    principal: Principal = Depends(get_principal),
    client: AsyncIdentityClient = Depends(get_identity),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[Role]:
    _assert_tenant(principal, organization_id)
    return await client.organizations.list_roles(page=page, page_size=page_size)


@api_router.get(
    "/organizations/{organization_id}/members",
    dependencies=[Depends(require_permission("identity.organizations.read"))],
)
async def list_members(
    organization_id: str,
    principal: Principal = Depends(get_principal),
    client: AsyncIdentityClient = Depends(get_identity),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[User]:
    _assert_tenant(principal, organization_id)
    return await client.organizations.list_members(organization_id, page=page, page_size=page_size)


@api_router.post(
    "/organizations/{organization_id}/members",
    dependencies=[
        Depends(require_permission("identity.organizations.write")),
        Depends(validate_csrf),
    ],
)
async def add_members(
    organization_id: str,
    body: MemberAssignment,
    principal: Principal = Depends(get_principal),
    client: AsyncIdentityClient = Depends(get_identity),
) -> Response:
    _assert_tenant(principal, organization_id)
    await client.organizations.add_members(organization_id, body.user_ids)
    return Response(status_code=204)


@api_router.delete(
    "/organizations/{organization_id}/members/{user_id}",
    status_code=204,
    dependencies=[
        Depends(require_permission("identity.organizations.write")),
        Depends(validate_csrf),
    ],
)
async def remove_member(
    organization_id: str,
    user_id: str,
    principal: Principal = Depends(get_principal),
    client: AsyncIdentityClient = Depends(get_identity),
) -> Response:
    _assert_tenant(principal, organization_id)
    await client.organizations.remove_member(organization_id, user_id)
    return Response(status_code=204)


@api_router.put(
    "/organizations/{organization_id}/members/{user_id}/roles",
    dependencies=[
        Depends(require_permission("identity.organizations.write")),
        Depends(validate_csrf),
    ],
)
async def set_member_roles(
    organization_id: str,
    user_id: str,
    body: RoleAssignment,
    principal: Principal = Depends(get_principal),
    client: AsyncIdentityClient = Depends(get_identity),
) -> Response:
    _assert_tenant(principal, organization_id)
    await client.organizations.set_member_roles(organization_id, user_id, body.role_ids)
    return Response(status_code=204)


@api_router.get("/audit", dependencies=[Depends(require_permission("identity.audit.read"))])
async def list_audit(
    client: AsyncIdentityClient = Depends(get_identity),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_time: int | None = None,
    end_time: int | None = None,
) -> Page[AuditEvent]:
    return await client.audit.list(
        page=page, page_size=page_size, start_time=start_time, end_time=end_time
    )
