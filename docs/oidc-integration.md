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

## LingxiLearn Web (Public SPA)

Bootstrap provisions the `LingxiLearn API` resource with the `learn.read` and
`learn.write` scopes, plus a public `LingxiLearn Web` SPA application. Configure
the exact SPA callback URI with `LINGXI_LEARN_WEB_REDIRECT_URI`; no client
secret is used or emitted for this application.

The SPA uses Authorization Code + PKCE with:

```text
OIDC_ISSUER=<LOGTO_ISSUER>
OIDC_CLIENT_ID=<LINGXI_LEARN_OIDC_CLIENT_ID>
OIDC_RESOURCE=<LINGXI_LEARN_RESOURCE>
OIDC_SCOPES=openid profile email offline_access roles urn:logto:scope:organizations urn:logto:scope:organization_roles learn.read learn.write
```

The access token request must include `resource=<LINGXI_LEARN_RESOURCE>`, so
the resulting JWT has the LingxiLearn API as its audience. Send that token only
as `Authorization: Bearer <access_token>` when calling LingxiLearn APIs. Do not
put tokens in query parameters or request bodies.

The BFF continues to use its existing HttpOnly Cookie Session. This SPA flow is
separate from the BFF session and does not change `OidcVerifier.verify(token)`.
