# Logto deployment boundary

LingxiIdentity keeps Logto Core, Console, OIDC, connectors and migrations on a
pinned upstream image. `Dockerfile.custom` builds the source-controlled
`experience/` SPA and overlays only its static assets at the published v1.33.0
workspace path `packages/experience/dist`; it does not fork or patch Logto
server code. The same custom image is used by `logto` and `logto-migrate` in
Compose.

See [custom-experience.md](../../docs/custom-experience.md) for the API
adapter, local build, rollback and security boundary. To restore the official
UI, set `LOGTO_IMAGE=ghcr.io/logto-io/logto:1.33.0` and recreate the services.

The migration service forwards arguments to the pinned v1.33.0 CLI with
`npm run cli -- db seed --swe` followed by
`npm run cli -- db alteration deploy latest`; v1.33.0 no longer accepts the
older `--disable-admin-pwned-password-check` flag.
