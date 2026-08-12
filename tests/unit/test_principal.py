from lingxi_identity import principal_from_claims


def test_principal_prefers_lingxi_claims_and_filters_oidc_scopes() -> None:
    principal = principal_from_claims(
        {
            "sub": "user-1",
            "iss": "https://id.example/oidc",
            "aud": "https://graph.example/api",
            "organization_id": "tenant-1",
            "roles": ["reader"],
            "organization_roles": ["tenant-1:tenant-admin", "tenant-2:other"],
            "scope": "openid profile graph.read",
        }
    )
    assert principal.subject == "user-1"
    assert principal.tenant_id == "tenant-1"
    assert principal.roles == {"reader", "tenant-admin"}
    assert principal.permissions == {"graph.read"}


def test_principal_uses_namespaced_claims() -> None:
    principal = principal_from_claims(
        {
            "sub": "service-1",
            "aud": ["https://graph.example/api"],
            "https://lingxi.dev/claims/tenant_id": "tenant-1",
            "https://lingxi.dev/claims/roles": ["service"],
            "https://lingxi.dev/claims/permissions": ["graph.read"],
        }
    )
    assert principal.tenant_id == "tenant-1"
    assert principal.roles == {"service"}
    assert principal.permissions == {"graph.read"}
