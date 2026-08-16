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
BFF_WEB_PUBLIC_URL=https://www.example.com
BFF_DEFAULT_NEXT_PATH=/workspace/lingxi/home/
BFF_ALLOWED_HOSTS=admin.example.com
SESSION_COOKIE_SECURE=true
LOGTO_TRUST_PROXY_HEADER=1
```

`BFF_PUBLIC_URL` is the identity service origin and must remain the OIDC
callback origin. `BFF_WEB_PUBLIC_URL` is the public web application origin;
after a successful BFF login, relative `next_path` values are redirected there.
For example, with `BFF_WEB_PUBLIC_URL=https://lingxilearn.cn` and
`BFF_DEFAULT_NEXT_PATH=/workspace/lingxi/home/`, an ordinary `/auth/login`
redirects to `https://lingxilearn.cn/workspace/lingxi/home/`. Visiting the web
application home page directly is unaffected.

Run only:

```powershell
docker compose --env-file .env -f deployment/compose.yaml up -d --build
```

The `postgres`, `logto`, and `bff` services use `restart: unless-stopped`, so Docker
will bring them back after a host or Docker daemon restart. The one-shot
`logto-migrate` service is in the opt-in `migration` profile and is never started
by the normal `up` command. Run it explicitly for an initial setup or deliberate
Logto upgrade:

```powershell
docker compose --env-file .env -f deployment/compose.yaml --profile migration run --rm logto-migrate
```

Terminate TLS at the external ingress and forward `X-Forwarded-Proto: https`. Route the identity hostname to Logto port 3001 and the BFF hostname to port 8080. Logto port 3002 is bound to loopback only and must never be exposed by the ingress or firewall.

Minimal Nginx, Caddy and Kubernetes Ingress examples are in `docs/edge-proxy/`. Adapt service names, certificates and network policy to the target environment.

## Custom Experience image

The default `LOGTO_IMAGE=lingxi-logto:1.33.0-experience` is built locally from
`deployment/logto/Dockerfile.custom`. The build compiles `experience/` and
overlays only the static Experience bundle on the pinned upstream
`ghcr.io/logto-io/logto:1.33.0` runtime. See [custom-experience.md](custom-experience.md)
for the API contract, security boundary and manual smoke flow.

For a safe rollback, set `LOGTO_IMAGE=ghcr.io/logto-io/logto:1.33.0`, recreate
`logto` and `logto-migrate`, and leave the database and BFF unchanged.

The migration profile uses the Logto 1.33.0 CLI contract:
`npm run cli -- db seed --swe && npm run cli -- db alteration deploy latest`.
The npm `--` separator is required to forward the flags to Logto; the removed
`--disable-admin-pwned-password-check` option is intentionally not used.

## Upgrade

The deployment uses the pinned `${LOGTO_IMAGE}` value (default
`lingxi-logto:1.33.0-experience`). Recreate the stack and verify
`logto-migrate` completes before Logto starts. The migration service runs the
official Logto seed/alteration commands; it never changes Logto source code.
Upgrade `LOGTO_UPSTREAM_VERSION` deliberately only after validating the
Experience, Account and Verification API contracts and rebuilding the custom
image; do not use `latest`.
