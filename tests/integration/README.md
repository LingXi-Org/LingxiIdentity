# Integration tests

Integration coverage uses a real PostgreSQL and Logto OSS stack. Start the configured Compose services, then run the provider adapter and Alembic checks with:

```powershell
make smoke
```

The default CI suite remains deterministic and does not require external Logto credentials; publish-time verification uses the same stack plus the bootstrap M2M credentials.
