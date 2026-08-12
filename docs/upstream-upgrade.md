# Upstream upgrade policy

1. Pin a released `ghcr.io/logto-io/logto:vX.Y.Z` image; never use `latest` in production.
2. Read the Logto release notes for database alterations and Management API changes.
3. Set `LOGTO_VERSION` in a disposable environment and run `make compose-config`, `make test` and `make smoke`.
4. Back up both PostgreSQL databases.
5. Deploy the new image and wait for the official alteration command to finish.
6. Verify Discovery, JWKS, M2M token acquisition, BFF health and representative user/organization operations.

The adapter deliberately isolates Logto paths and field names so upstream changes are localized to `sdk/python/src/lingxi_identity/providers/logto/`.
