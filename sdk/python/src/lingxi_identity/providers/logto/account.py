from __future__ import annotations

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
from ...models import AccountSession, User, VerificationRecord


class AsyncLogtoAccountAdapter:
    """Logto Account/Verification API adapter using an end-user access token."""

    def __init__(self, *, base_url: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        request_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)
        try:
            response = await self._client.request(
                method, f"{self.base_url}{path}", headers=request_headers, json=json
            )
        except httpx.HTTPError as exc:
            raise IdentityProviderUnavailableError("Account API request failed") from exc
        if response.status_code >= 400:
            self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            detail: Any = response.json()
        except ValueError:
            detail = response.text
        message = f"Account API returned HTTP {response.status_code}"
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

    async def get_profile(self, access_token: str) -> User:
        response = await self._request("GET", "/api/my-account", access_token)
        return User.model_validate(response.json())

    async def update_profile(
        self, access_token: str, changes: dict[str, Any], *, verification_id: str | None = None
    ) -> User:
        headers = {"logto-verification-id": verification_id} if verification_id else None
        response = await self._request(
            "PATCH", "/api/my-account", access_token, headers=headers, json=changes
        )
        return User.model_validate(response.json())

    async def update_other_profile(self, access_token: str, changes: dict[str, Any]) -> dict[str, Any]:
        response = await self._request(
            "PATCH", "/api/my-account/profile", access_token, json=changes
        )
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def verify_password(self, access_token: str, password: str) -> VerificationRecord:
        response = await self._request(
            "POST", "/api/verifications/password", access_token, json={"password": password}
        )
        return VerificationRecord.model_validate(response.json())

    async def send_verification_code(
        self, access_token: str, *, identifier_type: str, identifier: str
    ) -> VerificationRecord:
        response = await self._request(
            "POST",
            "/api/verifications/verification-code",
            access_token,
            json={"identifier": {"type": identifier_type, "value": identifier}},
        )
        return VerificationRecord.model_validate(response.json())

    async def verify_code(
        self,
        access_token: str,
        *,
        identifier_type: str,
        identifier: str,
        verification_id: str,
        code: str,
    ) -> VerificationRecord:
        response = await self._request(
            "POST",
            "/api/verifications/verification-code/verify",
            access_token,
            json={
                "identifier": {"type": identifier_type, "value": identifier},
                "verificationId": verification_id,
                "code": code,
            },
        )
        return VerificationRecord.model_validate(response.json())

    async def update_password(
        self, access_token: str, *, verification_id: str, password: str
    ) -> None:
        await self._request(
            "POST",
            "/api/my-account/password",
            access_token,
            headers={"logto-verification-id": verification_id},
            json={"password": password},
        )

    async def update_email(
        self,
        access_token: str,
        *,
        verification_id: str,
        email: str,
        new_identifier_verification_id: str,
    ) -> User:
        response = await self._request(
            "POST",
            "/api/my-account/primary-email",
            access_token,
            headers={"logto-verification-id": verification_id},
            json={
                "email": email,
                "newIdentifierVerificationRecordId": new_identifier_verification_id,
            },
        )
        return User.model_validate(response.json())

    async def list_sessions(
        self, access_token: str, *, verification_id: str | None = None
    ) -> list[AccountSession]:
        headers = {"logto-verification-id": verification_id} if verification_id else None
        response = await self._request(
            "GET", "/api/my-account/sessions", access_token, headers=headers
        )
        payload = response.json()
        items = payload if isinstance(payload, list) else payload.get("sessions", payload.get("data", []))
        normalized: list[AccountSession] = []
        for item in items:
            if "id" in item:
                normalized.append(AccountSession.model_validate(item))
                continue
            normalized.append(
                AccountSession.model_validate(
                    {
                        "id": item.get("payload", {}).get("uid", ""),
                        "applicationId": item.get("clientId"),
                        "createdAt": item.get("payload", {}).get("loginTs"),
                        "lastUsedAt": item.get("payload", {}).get("loginTs"),
                        "isCurrent": item.get("isCurrent", False),
                    }
                )
            )
        return normalized

    async def revoke_session(self, access_token: str, session_id: str) -> None:
        await self._request(
            "DELETE", f"/api/my-account/sessions/{session_id}", access_token
        )
