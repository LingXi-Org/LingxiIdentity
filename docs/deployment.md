# Deployment

## Development

```powershell
Copy-Item .env.example .env
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.bootstrap.yaml up -d --build postgres logto
```

The bootstrap overlay binds Admin Console to `127.0.0.1:3002` only. Create the initial Logto admin and seed M2M application once, then run the bootstrap command after Logto is healthy. The bootstrap service has no Compose dependency on Logto, so it cannot indirectly start the already-completed seed/migration job. Store its generated server credentials in `.env` or a deployment secret before starting `bff`.

## Production

Set at least:

```text
APP_ENV=production
LOGTO_PUBLIC_ENDPOINT=https://identity.example.com
LOGTO_ISSUER=https://identity.example.com/oidc
BFF_PUBLIC_URL=https://admin.example.com
BFF_ALLOWED_HOSTS=admin.example.com
SESSION_COOKIE_SECURE=true
LOGTO_TRUST_PROXY_HEADER=1
```

Run only:

```powershell
docker compose --env-file .env -f deployment/compose.yaml up -d --build
```

The `postgres`, `logto`, and `bff` services use `restart: unless-stopped`, so Docker
will bring them back after a host or Docker daemon restart. The one-shot
`logto-migrate` service is intentionally not configured for automatic restart.

Terminate TLS at the external ingress and forward `X-Forwarded-Proto: https`. Route the identity hostname to Logto port 3001 and the BFF hostname to port 8080. Logto port 3002 is bound to loopback only and must never be exposed by the ingress or firewall.

Minimal Nginx, Caddy and Kubernetes Ingress examples are in `docs/edge-proxy/`. Adapt service names, certificates and network policy to the target environment.

## Upgrade

The deployment uses the pinned `${LOGTO_IMAGE}` value (default `ghcr.io/logto-io/logto:1.33.0`). Recreate the stack and verify `logto-migrate` completes before Logto starts. The migration service runs the official Logto seed/alteration commands; it never changes Logto source code.
`LOGTO_IMAGE` defaults to the pinned `ghcr.io/logto-io/logto:1.33.0` image. Upgrade it deliberately after validating the Experience, Account and Verification API contracts.
