from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from lingxi_identity import IdentityAuthorizationError, Page, User
from lingxi_identity.providers.logto.management import AsyncLogtoManagementAdapter, _TokenCache


@pytest.mark.asyncio
@respx.mock
async def test_management_token_cache_merges_concurrent_refreshes() -> None:
    token_route = respx.post("http://logto:3001/oidc/token").mock(
        return_value=httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
    )
    cache = _TokenCache(
        base_url="http://logto:3001",
        client_id="client",
        client_secret="secret",
        resource="https://default.logto.app/api",
        scope="all",
    )
    async with httpx.AsyncClient() as client:
        values = await asyncio.gather(*(cache.get(client) for _ in range(20)))
    assert values == ["token-1"] * 20
    assert token_route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_management_token_cache_refreshes_after_expiry() -> None:
    token_route = respx.post("http://logto:3001/oidc/token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "token-1", "expires_in": 30}),
            httpx.Response(200, json={"access_token": "token-2", "expires_in": 3600}),
        ]
    )
    cache = _TokenCache(
        base_url="http://logto:3001",
        client_id="client",
        client_secret="secret",
        resource="https://default.logto.app/api",
        scope="all",
    )
    async with httpx.AsyncClient() as client:
        assert await cache.get(client) == "token-1"
        cache._expires_at = 0
        assert await cache.get(client) == "token-2"
    assert token_route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_management_adapter_retries_401_and_maps_dtos() -> None:
    token_route = respx.post("http://logto:3001/oidc/token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600}),
            httpx.Response(200, json={"access_token": "token-2", "expires_in": 3600}),
        ]
    )
    api_route = respx.get("http://logto:3001/api/users").mock(
        side_effect=[
            httpx.Response(401, json={"code": "token_expired"}),
            httpx.Response(
                200,
                headers={"Total-Number": "1"},
                json=[{"id": "u1", "primaryEmail": "u1@example.com"}],
            ),
        ]
    )
    adapter = AsyncLogtoManagementAdapter(
        base_url="http://logto:3001",
        client_id="client",
        client_secret="secret",
    )
    page = await adapter.list_users()
    await adapter.aclose()
    assert isinstance(page, Page)
    assert isinstance(page.items[0], User)
    assert page.items[0].primary_email == "u1@example.com"
    assert api_route.call_count == 2
    assert token_route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_management_adapter_maps_forbidden_error() -> None:
    respx.post("http://logto:3001/oidc/token").mock(
        return_value=httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
    )
    respx.get("http://logto:3001/api/users/u1").mock(
        return_value=httpx.Response(403, json={"code": "forbidden"})
    )
    adapter = AsyncLogtoManagementAdapter(
        base_url="http://logto:3001",
        client_id="client",
        client_secret="secret",
    )
    with pytest.raises(IdentityAuthorizationError):
        await adapter.get_user("u1")
    await adapter.aclose()
