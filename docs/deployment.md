# Deployment

## Development

```powershell
Copy-Item .env.example .env
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.bootstrap.yaml up -d --build postgres logto
```

The bootstrap overlay binds Admin Console to `127.0.0.1:3002` only. Create the initial Logto admin and seed M2M application once, then run the bootstrap command. Store its generated server credentials in `.env` or a deployment secret before starting `bff`.

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

Terminate TLS at the external ingress and forward `X-Forwarded-Proto: https`. Route the identity hostname to Logto port 3001 and the BFF hostname to port 8080. Never route or publish Logto port 3002.

Minimal Nginx, Caddy and Kubernetes Ingress examples are in `docs/edge-proxy/`. Adapt service names, certificates and network policy to the target environment.

## Upgrade

Set `LOGTO_VERSION` to the tested upstream tag, recreate the stack, and verify `logto-migrate` completes before Logto starts. The migration service runs the official Logto seed/alteration commands; it never changes Logto source code.
