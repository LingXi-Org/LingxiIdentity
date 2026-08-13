from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from typing import Any

import httpx

from ...errors import (
    IdentityAuthenticationError,
    IdentityAuthorizationError,
    IdentityConflictError,
    IdentityError,
    IdentityNotFoundError,
    IdentityProviderUnavailableError,
)
from ...models import AuditEvent, Organization, Page, Role, User


class _TokenCache:
    def __init__(
        self, *, base_url: str, client_id: str, client_secret: str, resource: str, scope: str
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.resource = resource
        self.scope = scope
        self._value: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get(self, client: httpx.AsyncClient) -> str:
        now = datetime.now(timezone.utc).timestamp()
        if self._value and now < self._expires_at:
            return self._value
        async with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            if self._value and now < self._expires_at:
                return self._value
            auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            try:
                response = await client.post(
                    f"{self.base_url}/oidc/token",
                    headers={"Authorization": f"Basic {auth}"},
                    data={
                        "grant_type": "client_credentials",
                        "resource": self.resource,
                        "scope": self.scope,
                    },
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise IdentityProviderUnavailableError(
                    "Unable to obtain Management API token"
                ) from exc
            if not isinstance(payload, dict):
                raise IdentityAuthenticationError(
                    "Management API token response must be a JSON object"
                )
            token = payload.get("access_token")
            if not token:
                raise IdentityAuthenticationError(
                    "Management API token response has no access_token"
                )
            expires_in = max(int(payload.get("expires_in", 3600)), 30)
            self._value = str(token)
            self._expires_at = datetime.now(timezone.utc).timestamp() + max(expires_in - 60, 5)
            return self._value

    def invalidate(self) -> None:
        self._value = None
        self._expires_at = 0.0


class AsyncLogtoManagementAdapter:
    """The only module that knows Logto Management API paths and field names."""

    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        api_indicator: str = "https://default.logto.app/api",
        scope: str = "all",
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self._tokens = _TokenCache(
            base_url=self.base_url,
            client_id=client_id,
            client_secret=client_secret,
            resource=api_indicator,
            scope=scope,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, *, query: dict[str, Any] | None = None, json: Any = None
    ) -> httpx.Response:
        token = await self._tokens.get(self._client)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        try:
            response = await self._client.request(
                method, f"{self.base_url}{path}", headers=headers, params=query, json=json
            )
        except httpx.HTTPError as exc:
            raise IdentityProviderUnavailableError("Management API request failed") from exc
        if response.status_code == 401:
            self._tokens.invalidate()
            token = await self._tokens.get(self._client)
            headers["Authorization"] = f"Bearer {token}"
            try:
                response = await self._client.request(
                    method, f"{self.base_url}{path}", headers=headers, params=query, json=json
                )
            except httpx.HTTPError as exc:
                raise IdentityProviderUnavailableError("Management API retry failed") from exc
        if response.status_code >= 400:
            self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        detail: Any
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        message = f"Identity provider returned HTTP {response.status_code}"
        if response.status_code == 401:
            raise IdentityAuthenticationError(message, status_code=401, details=detail)
        if response.status_code == 403:
            raise IdentityAuthorizationError(message, status_code=403, details=detail)
        if response.status_code == 404:
            raise IdentityNotFoundError(message, status_code=404, details=detail)
        if response.status_code in (409, 422):
            raise IdentityConflictError(message, status_code=response.status_code, details=detail)
        if response.status_code >= 500:
            raise IdentityProviderUnavailableError(
                message, status_code=response.status_code, details=detail
            )
        raise IdentityError(message, status_code=response.status_code, details=detail)

    @staticmethod
    def _page(response: httpx.Response, model: Any, page: int, page_size: int) -> Page[Any]:
        total_header = response.headers.get("Total-Number")
        capped = response.headers.get("Total-Number-Is-Capped", "").lower() == "true"
        total = int(total_header) if total_header and total_header.isdigit() else None
        return Page(
            items=[model.model_validate(item) for item in response.json()],
            page=page,
            page_size=page_size,
            total=total,
            total_is_capped=capped,
        )

    async def list_users(
        self, *, page: int = 1, page_size: int = 20, search: str | None = None
    ) -> Page[User]:
        query: dict[str, Any] = {"page": page, "page_size": page_size}
        if search:
            query["search"] = search
        return self._page(
            await self._request("GET", "/api/users", query=query), User, page, page_size
        )

    async def get_user(self, user_id: str) -> User:
        return User.model_validate((await self._request("GET", f"/api/users/{user_id}")).json())

    async def create_user(self, user: User | dict[str, Any]) -> User:
        payload = (
            user.model_dump(by_alias=True, exclude_none=True) if isinstance(user, User) else user
        )
        return User.model_validate((await self._request("POST", "/api/users", json=payload)).json())

    async def update_user(self, user_id: str, changes: dict[str, Any]) -> User:
        return User.model_validate(
            (await self._request("PATCH", f"/api/users/{user_id}", json=changes)).json()
        )

    async def delete_user(self, user_id: str) -> None:
        await self._request("DELETE", f"/api/users/{user_id}")

    async def list_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        payload = (
            await self._request("GET", f"/api/users/{user_id}/sessions")
        ).json()
        return list(payload if isinstance(payload, list) else payload.get("sessions", []))

    async def revoke_user_session(self, user_id: str, session_id: str) -> None:
        await self._request("DELETE", f"/api/users/{user_id}/sessions/{session_id}")

    async def revoke_all_user_sessions(self, user_id: str) -> None:
        for session in await self.list_user_sessions(user_id):
            session_id = session.get("id") or session.get("payload", {}).get("uid")
            if session_id:
                await self.revoke_user_session(user_id, str(session_id))

    async def set_user_roles(self, user_id: str, role_ids: list[str]) -> None:
        await self._request("PUT", f"/api/users/{user_id}/roles", json={"roleIds": role_ids})

    async def list_roles(self, *, page: int = 1, page_size: int = 20) -> Page[Role]:
        response = await self._request(
            "GET", "/api/roles", query={"page": page, "page_size": page_size}
        )
        return self._page(response, Role, page, page_size)

    async def get_role(self, role_id: str) -> Role:
        return Role.model_validate((await self._request("GET", f"/api/roles/{role_id}")).json())

    async def create_role(self, role: dict[str, Any]) -> Role:
        return Role.model_validate((await self._request("POST", "/api/roles", json=role)).json())

    async def update_role(self, role_id: str, changes: dict[str, Any]) -> Role:
        return Role.model_validate(
            (await self._request("PATCH", f"/api/roles/{role_id}", json=changes)).json()
        )

    async def delete_role(self, role_id: str) -> None:
        await self._request("DELETE", f"/api/roles/{role_id}")

    async def list_organizations(self, *, page: int = 1, page_size: int = 20) -> Page[Organization]:
        response = await self._request(
            "GET", "/api/organizations", query={"page": page, "page_size": page_size}
        )
        return self._page(response, Organization, page, page_size)

    async def list_organization_roles(self, *, page: int = 1, page_size: int = 20) -> Page[Role]:
        response = await self._request(
            "GET", "/api/organization-roles", query={"page": page, "page_size": page_size}
        )
        return self._page(response, Role, page, page_size)

    async def get_organization(self, organization_id: str) -> Organization:
        return Organization.model_validate(
            (await self._request("GET", f"/api/organizations/{organization_id}")).json()
        )

    async def create_organization(self, organization: dict[str, Any]) -> Organization:
        return Organization.model_validate(
            (await self._request("POST", "/api/organizations", json=organization)).json()
        )

    async def update_organization(
        self, organization_id: str, changes: dict[str, Any]
    ) -> Organization:
        return Organization.model_validate(
            (
                await self._request("PATCH", f"/api/organizations/{organization_id}", json=changes)
            ).json()
        )

    async def delete_organization(self, organization_id: str) -> None:
        await self._request("DELETE", f"/api/organizations/{organization_id}")

    async def list_members(
        self, organization_id: str, *, page: int = 1, page_size: int = 20
    ) -> Page[User]:
        response = await self._request(
            "GET",
            f"/api/organizations/{organization_id}/users",
            query={"page": page, "page_size": page_size},
        )
        return self._page(response, User, page, page_size)

    async def add_members(self, organization_id: str, user_ids: list[str]) -> None:
        await self._request(
            "POST", f"/api/organizations/{organization_id}/users", json={"userIds": user_ids}
        )

    async def remove_member(self, organization_id: str, user_id: str) -> None:
        await self._request("DELETE", f"/api/organizations/{organization_id}/users/{user_id}")

    async def set_member_roles(
        self, organization_id: str, user_id: str, role_ids: list[str]
    ) -> None:
        await self._request(
            "PUT",
            f"/api/organizations/{organization_id}/users/{user_id}/roles",
            json={"organizationRoleIds": role_ids},
        )

    async def list_audit(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> Page[AuditEvent]:
        query: dict[str, Any] = {"page": page, "page_size": page_size, "enableCap": "true"}
        if start_time is not None:
            query["start_time"] = start_time
        if end_time is not None:
            query["end_time"] = end_time
        response = await self._request("GET", "/api/logs", query=query)
        events = []
        for raw in response.json():
            payload = raw.get("payload", {})
            event = {
                "id": raw.get("id", ""),
                "key": raw.get("key", ""),
                "result": payload.get("result", "Unknown"),
                "userId": payload.get("userId"),
                "applicationId": payload.get("applicationId"),
                "ip": payload.get("ip"),
                "userAgent": payload.get("userAgent"),
                "params": payload.get("params", {}),
                "createdAt": raw.get("createdAt"),
            }
            events.append(AuditEvent.model_validate(event))
        return Page(
            items=events,
            page=page,
            page_size=page_size,
            total=int(response.headers["Total-Number"])
            if response.headers.get("Total-Number", "").isdigit()
            else None,
            total_is_capped=response.headers.get("Total-Number-Is-Capped") == "true",
        )
