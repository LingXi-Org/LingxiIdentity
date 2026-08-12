from __future__ import annotations

import json
import os
import urllib.request
from urllib.error import HTTPError, URLError


def get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, error.read().decode()


def main() -> None:
    bff = os.getenv("SMOKE_BFF_URL", "http://localhost:8080")
    logto = os.getenv("SMOKE_LOGTO_URL", "http://localhost:3001")
    assert get(f"{bff}/health/live")[0] == 200
    assert get(f"{bff}/health/ready")[0] == 200
    assert get(f"{bff}/api/v1/me")[0] == 401
    status, discovery = get(f"{logto}/oidc/.well-known/openid-configuration")
    assert status == 200
    assert "jwks_uri" in discovery
    assert "issuer" in discovery
    access_token = os.getenv("SMOKE_ACCESS_TOKEN")
    if access_token:
        from lingxi_identity import OidcVerifier

        metadata = json.loads(discovery)
        principal = OidcVerifier(
            issuer=os.getenv("SMOKE_ISSUER", metadata["issuer"]),
            audience=os.getenv("SMOKE_AUDIENCE", "https://graph.lingxi.dev/api"),
        ).verify(access_token)
        assert principal.subject
    if os.getenv("SMOKE_EXPECT_ADMIN_DISABLED", "true").lower() == "true":
        try:
            admin_status, _ = get(f"{logto.replace(':3001', ':3002')}/")
        except URLError:
            admin_status = 0
        assert admin_status == 0 or admin_status >= 400
    print("LingxiIdentity smoke test passed")


if __name__ == "__main__":
    main()
