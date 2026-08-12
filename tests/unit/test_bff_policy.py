from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from lingxi_bff.api.routes import _assert_tenant, login
from lingxi_identity import Principal


def request_with_app(app: FastAPI) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/auth/login",
            "headers": [],
            "query_string": b"",
            "server": ("localhost", 8080),
            "client": ("127.0.0.1", 12345),
            "scheme": "https",
            "app": app,
        }
    )


@pytest.mark.asyncio
async def test_login_cookie_is_secure_and_httponly() -> None:
    app = FastAPI()
    app.state.settings = SimpleNamespace(session_cookie_secure=True)
    app.state.oidc = SimpleNamespace(
        authorize=AsyncMock(return_value=("https://id/login", "signed"))
    )
    response = await login(request_with_app(app))
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie


def test_tenant_path_mismatch_is_forbidden() -> None:
    principal = Principal(subject="u1", tenant_id="tenant-a")
    with pytest.raises(HTTPException) as error:
        _assert_tenant(principal, "tenant-b")
    assert error.value.status_code == 403


def test_global_admin_can_cross_tenant_for_admin_operations() -> None:
    principal = Principal(subject="u1", tenant_id="tenant-a", roles=frozenset({"identity.admin"}))
    _assert_tenant(principal, "tenant-b")
