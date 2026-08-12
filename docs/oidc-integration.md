# OIDC integration

Resource services should configure only these values:

```text
OIDC_ISSUER=https://identity.example.com/oidc
OIDC_AUDIENCE=https://graph.example.com/api
OIDC_JWKS_URI=<discovered jwks_uri>
```

Use standard OIDC Discovery and JWKS. Validate issuer, audience, signature, expiry and required claims locally. For organization APIs, require the JWT `organization_id` to match the requested tenant. Permissions come from `scope` or the Lingxi namespaced permissions claim.

```python
from lingxi_identity import OidcVerifier

principal = OidcVerifier(
    issuer="https://identity.example.com/oidc",
    audience="https://graph.example.com/api",
).verify(access_token)
```

No resource service should import `logto`, call `/api/users`, or hold the Lingxi Admin M2M secret.
