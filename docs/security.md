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
