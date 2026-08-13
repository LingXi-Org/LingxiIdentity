# Security baseline

- Production sets `ADMIN_DISABLE_LOCALHOST=true`, leaves `ADMIN_ENDPOINT` unset and publishes no Logto port 3002.
- M2M credentials are server-only environment variables or secret files. They are never returned by BFF endpoints and must not be logged.
- BFF cookies are HttpOnly, Secure in production and SameSite=Lax. State/nonce/PKCE protect the OIDC callback.
- Configure `BFF_ALLOWED_HOSTS` to the public BFF hostnames in production; CORS origins should be explicit rather than wildcard.
- BFF mutating requests require `X-CSRF-Token`; the token is stored encrypted server-side and compared by hash.
- JWT validation requires issuer, audience, expiry, `sub`, `iss`, `aud`, `exp` and an allow-listed signing algorithm. JWKS is cached and refreshed on unknown `kid`.
- Logto owns password hashing, OAuth/OIDC protocol behavior and JWT signing. Lingxi does not implement any of those primitives.
- PostgreSQL is not exposed publicly in production. Back up Logto and Lingxi databases independently.
- Set a unique production `SESSION_ENCRYPTION_KEY`; the value in `.env.example` is only a development placeholder.
- Account API is enabled by bootstrap with editable name/avatar/profile/email/password/username/custom data and session fields. Keep the Logto email connector configured for registration, password recovery, and permission-validation templates.
- Passwords, verification codes and provider tokens are never logged or returned by the BFF. Verification record IDs are returned only to the authenticated caller over TLS, are short-lived Logto artifacts, and should be treated as secrets.
- Self-service account closure is suspension plus revocation of all BFF sessions. Permanent deletion remains an administrator-only Management API operation.
