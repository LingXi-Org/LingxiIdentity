from __future__ import annotations

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lingxi_bff.db.models import Base
from lingxi_bff.security.sessions import SessionManager


async def test_session_tokens_are_encrypted_and_revocable() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    manager = SessionManager(
        key=Fernet.generate_key().decode(),
        ttl_seconds=300,
        claims_namespace="https://lingxi.dev/claims/",
    )
    claims = {"sub": "user-1", "iss": "https://identity.example.com/oidc", "aud": "admin"}
    async with sessions() as db:
        context = await manager.create(
            db,
            claims=claims,
            access_token="access-secret",
            refresh_token="refresh-secret",
            id_token="id-secret",
        )
        loaded = await manager.get(db, context.session_id)
        assert loaded is not None
        assert loaded.access_token == "access-secret"
        assert loaded.refresh_token == "refresh-secret"
        assert await manager.csrf_valid(db, context.session_id, context.csrf_token)
        assert "access-secret" not in str(loaded.claims)
        await manager.revoke(db, context.session_id)
        assert await manager.get(db, context.session_id) is None
    await engine.dispose()
