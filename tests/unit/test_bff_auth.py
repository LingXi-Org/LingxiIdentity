from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet

from lingxi_bff.auth.oidc_flow import OidcFlow
from lingxi_bff.settings import Settings
from lingxi_identity import OidcDiscovery


@pytest.mark.asyncio
async def test_authorize_url_contains_pkce_without_client_secret() -> None:
    settings = Settings(
        session_encryption_key=Fernet.generate_key().decode(),
        oidc_client_id="web-client",
        oidc_client_secret="server-only-secret",
    )
    flow = OidcFlow(settings)
    flow._metadata = OidcDiscovery(
        issuer=settings.logto_issuer,
        authorization_endpoint="http://logto:3001/oidc/auth",
        token_endpoint="http://logto:3001/oidc/token",
        jwks_uri="http://logto:3001/oidc/keys",
    )
    url, signed_state = await flow.authorize(next_path="/admin")
    query = parse_qs(urlsplit(url).query)
    assert query["client_id"] == ["web-client"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"]
    assert "server-only-secret" not in url
    assert flow.decode_state(signed_state).next_path == "/admin"
