from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Any

import anyio

from .models import AuditEvent, Organization, Page, Role, User
from .providers.logto.account import AsyncLogtoAccountAdapter
from .oidc import OidcDiscovery, OidcVerifier
from .principal import Principal
from .providers.logto.management import AsyncLogtoManagementAdapter


class _AsyncUsers:
    def __init__(self, adapter: AsyncLogtoManagementAdapter) -> None:
        self._a = adapter

    async def list(self, **kwargs: Any) -> Page[User]:
        return await self._a.list_users(**kwargs)

    async def get(self, user_id: str) -> User:
        return await self._a.get_user(user_id)

    async def create(self, user: User | dict[str, Any]) -> User:
        return await self._a.create_user(user)

    async def update(self, user_id: str, changes: dict[str, Any]) -> User:
        return await self._a.update_user(user_id, changes)

    async def delete(self, user_id: str) -> None:
        return await self._a.delete_user(user_id)

    async def revoke_all_sessions(self, user_id: str) -> None:
        return await self._a.revoke_all_user_sessions(user_id)

    async def set_roles(self, user_id: str, role_ids: builtins.list[str]) -> None:
        return await self._a.set_user_roles(user_id, role_ids)


class _AsyncRoles:
    def __init__(self, adapter: AsyncLogtoManagementAdapter) -> None:
        self._a = adapter

    async def list(self, **kwargs: Any) -> Page[Role]:
        return await self._a.list_roles(**kwargs)

    async def get(self, role_id: str) -> Role:
        return await self._a.get_role(role_id)

    async def create(self, role: dict[str, Any]) -> Role:
        return await self._a.create_role(role)

    async def update(self, role_id: str, changes: dict[str, Any]) -> Role:
        return await self._a.update_role(role_id, changes)

    async def delete(self, role_id: str) -> None:
        return await self._a.delete_role(role_id)


class _AsyncOrganizations:
    def __init__(self, adapter: AsyncLogtoManagementAdapter) -> None:
        self._a = adapter

    async def list(self, **kwargs: Any) -> Page[Organization]:
        return await self._a.list_organizations(**kwargs)

    async def list_roles(self, **kwargs: Any) -> Page[Role]:
        return await self._a.list_organization_roles(**kwargs)

    async def get(self, organization_id: str) -> Organization:
        return await self._a.get_organization(organization_id)

    async def create(self, organization: dict[str, Any]) -> Organization:
        return await self._a.create_organization(organization)

    async def update(self, organization_id: str, changes: dict[str, Any]) -> Organization:
        return await self._a.update_organization(organization_id, changes)

    async def delete(self, organization_id: str) -> None:
        return await self._a.delete_organization(organization_id)

    async def list_members(self, organization_id: str, **kwargs: Any) -> Page[User]:
        return await self._a.list_members(organization_id, **kwargs)

    async def add_members(self, organization_id: str, user_ids: builtins.list[str]) -> None:
        return await self._a.add_members(organization_id, user_ids)

    async def remove_member(self, organization_id: str, user_id: str) -> None:
        return await self._a.remove_member(organization_id, user_id)

    async def set_member_roles(
        self, organization_id: str, user_id: str, role_ids: builtins.list[str]
    ) -> None:
        return await self._a.set_member_roles(organization_id, user_id, role_ids)


class _AsyncAudit:
    def __init__(self, adapter: AsyncLogtoManagementAdapter) -> None:
        self._a = adapter

    async def list(self, **kwargs: Any) -> Page[AuditEvent]:
        return await self._a.list_audit(**kwargs)


class OidcService:
    """Provider-neutral OIDC discovery and JWT verification helpers."""

    def __init__(self, *, claims_namespace: str) -> None:
        self.claims_namespace = claims_namespace

    def discovery(self, issuer: str) -> OidcDiscovery:
        return OidcDiscovery.fetch(issuer)

    def verifier(self, *, issuer: str, audience: str) -> OidcVerifier:
        return OidcVerifier(
            issuer=issuer,
            audience=audience,
            claims_namespace=self.claims_namespace,
        )

    def verify(self, token: str, *, issuer: str, audience: str) -> Principal:
        return self.verifier(issuer=issuer, audience=audience).verify(token)


class AsyncIdentityClient:
    def __init__(
        self,
        adapter: AsyncLogtoManagementAdapter,
        *,
        claims_namespace: str = "https://lingxi.dev/claims/",
    ) -> None:
        self._adapter = adapter
        self._account_adapter = AsyncLogtoAccountAdapter(base_url=adapter.base_url)
        self.users = _AsyncUsers(adapter)
        self.roles = _AsyncRoles(adapter)
        self.organizations = _AsyncOrganizations(adapter)
        self.audit = _AsyncAudit(adapter)
        self.oidc = OidcService(claims_namespace=claims_namespace)

    class _Account:
        def __init__(self, adapter: AsyncLogtoAccountAdapter) -> None:
            self._a = adapter

        async def get_profile(self, access_token: str) -> User:
            return await self._a.get_profile(access_token)

        async def update_profile(
            self, access_token: str, changes: dict[str, Any], *, verification_id: str | None = None
        ) -> User:
            return await self._a.update_profile(
                access_token, changes, verification_id=verification_id
            )

        async def update_other_profile(self, access_token: str, changes: dict[str, Any]) -> dict[str, Any]:
            return await self._a.update_other_profile(access_token, changes)

        async def verify_password(self, access_token: str, password: str) -> Any:
            return await self._a.verify_password(access_token, password)

        async def send_verification_code(self, access_token: str, **kwargs: Any) -> Any:
            return await self._a.send_verification_code(access_token, **kwargs)

        async def verify_code(self, access_token: str, **kwargs: Any) -> Any:
            return await self._a.verify_code(access_token, **kwargs)

        async def update_password(self, access_token: str, **kwargs: Any) -> None:
            await self._a.update_password(access_token, **kwargs)

        async def update_email(self, access_token: str, **kwargs: Any) -> User:
            return await self._a.update_email(access_token, **kwargs)

        async def list_sessions(
            self, access_token: str, *, verification_id: str | None = None
        ) -> Any:
            return await self._a.list_sessions(access_token, verification_id=verification_id)

        async def revoke_session(self, access_token: str, session_id: str) -> None:
            await self._a.revoke_session(access_token, session_id)

    @property
    def account(self) -> "AsyncIdentityClient._Account":
        return self._Account(self._account_adapter)

    @classmethod
    def from_logto(
        cls,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        api_indicator: str = "https://default.logto.app/api",
        scope: str = "all",
        claims_namespace: str = "https://lingxi.dev/claims/",
    ) -> "AsyncIdentityClient":
        return cls(
            AsyncLogtoManagementAdapter(
                base_url=base_url,
                client_id=client_id,
                client_secret=client_secret,
                api_indicator=api_indicator,
                scope=scope,
            ),
            claims_namespace=claims_namespace,
        )

    async def aclose(self) -> None:
        await self._account_adapter.aclose()
        await self._adapter.aclose()


class _SyncProxy:
    def __init__(self, resource: Any, runner: Callable[..., Any]) -> None:
        self._resource = resource
        self._runner = runner

    def __getattr__(self, name: str) -> Any:
        async_method = getattr(self._resource, name)

        def call(*args: Any, **kwargs: Any) -> Any:
            return self._runner(async_method(*args, **kwargs))

        return call


class IdentityClient:
    """Synchronous facade over AsyncIdentityClient for worker and CLI applications."""

    def __init__(self, client: AsyncIdentityClient) -> None:
        self._client = client
        self.users = _SyncProxy(client.users, self._run)
        self.roles = _SyncProxy(client.roles, self._run)
        self.organizations = _SyncProxy(client.organizations, self._run)
        self.audit = _SyncProxy(client.audit, self._run)
        self.account = _SyncProxy(client.account, self._run)
        self.oidc = client.oidc

    @classmethod
    def from_logto(cls, **kwargs: Any) -> "IdentityClient":
        return cls(AsyncIdentityClient.from_logto(**kwargs))

    @staticmethod
    def _run(awaitable: Any) -> Any:
        return anyio.run(lambda: awaitable)

    def close(self) -> None:
        self._run(self._client.aclose())
