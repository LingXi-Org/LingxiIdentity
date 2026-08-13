from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from lingxi_identity import AsyncIdentityClient, IdentityError

from .api.routes import api_router, auth_router
from .auth.oidc_flow import OidcFlow
from .db.database import Database
from .security.sessions import SessionManager
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime.validate_runtime()
        app.state.settings = runtime
        app.state.database = Database(runtime.lingxi_database_url)
        app.state.oidc = OidcFlow(runtime)
        app.state.session_manager = SessionManager(
            key=runtime.session_encryption_key,
            ttl_seconds=runtime.session_ttl_seconds,
            claims_namespace=runtime.lingxi_claims_namespace,
        )
        app.state.identity = AsyncIdentityClient.from_logto(
            base_url=runtime.logto_internal_endpoint,
            client_id=runtime.logto_m2m_client_id,
            client_secret=runtime.resolved_m2m_secret,
            api_indicator=runtime.logto_management_api_indicator,
            claims_namespace=runtime.lingxi_claims_namespace,
        )
        app.state.ready = True
        try:
            yield
        finally:
            await app.state.identity.aclose()
            await app.state.database.dispose()

    app = FastAPI(title="LingxiIdentity BFF", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=runtime.allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Logto-Verification-Id"],
    )

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request) -> JSONResponse:
        try:
            async with request.app.state.database.sessions() as session:
                await session.execute(text("SELECT 1"))
            return JSONResponse({"ok": True})
        except Exception:
            return JSONResponse({"ok": False, "error": "dependencies unavailable"}, status_code=503)

    @app.exception_handler(IdentityError)
    async def identity_error(_: Request, exc: IdentityError) -> JSONResponse:
        status = exc.status_code if exc.status_code and 400 <= exc.status_code < 600 else 502
        code = "identity.upstream_error"
        if exc.status_code == 401:
            code = "identity.unauthorized"
        elif exc.status_code == 403:
            code = "identity.forbidden"
        elif exc.status_code == 404:
            code = "identity.not_found"
        elif exc.status_code in (409, 422):
            code = "identity.conflict"
        return JSONResponse(
            {"type": "https://lingxi.dev/problems/identity", "code": code, "detail": str(exc)},
            status_code=status,
        )

    app.include_router(auth_router)
    app.include_router(api_router)
    return app


app = create_app()
