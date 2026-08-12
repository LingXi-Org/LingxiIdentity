# Upstream upgrade policy

1. The deployment uses `ghcr.io/logto-io/logto:latest`; review the upstream release before upgrading.
2. Read the Logto release notes for database alterations and Management API changes.
3. Run `make compose-config`, `make test` and `make smoke` in a disposable environment.
4. Back up both PostgreSQL databases.
5. Deploy the new image and wait for the official alteration command to finish.
6. Verify Discovery, JWKS, M2M token acquisition, BFF health and representative user/organization operations.

The adapter deliberately isolates Logto paths and field names so upstream changes are localized to `sdk/python/src/lingxi_identity/providers/logto/`.
