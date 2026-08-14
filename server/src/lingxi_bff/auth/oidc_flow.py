from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from itsdangerous import BadSignature, URLSafeTimedSerializer

from lingxi_identity import OidcDiscovery, OidcVerifier

from ..settings import Settings


@dataclass(frozen=True)
class OAuthState:
    state: str
    code_verifier: str
    nonce: str
    next_path: str


class OidcFlow:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._metadata: OidcDiscovery | None = None
        self._serializer = URLSafeTimedSerializer(
            settings.session_encryption_key, salt="lingxi-oidc-state"
        )

    async def metadata(self) -> OidcDiscovery:
        if self._metadata:
            return self._metadata
        base = self.settings.logto_internal_endpoint.rstrip("/")
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            for url in (
                f"{base}/oidc/.well-known/openid-configuration",
                f"{base}/.well-known/openid-configuration",
            ):
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    self._metadata = OidcDiscovery(
                        issuer=self.settings.logto_issuer.rstrip("/"),
                        authorization_endpoint=str(data["authorization_endpoint"]),
                        token_endpoint=str(data["token_endpoint"]),
                        jwks_uri=str(data["jwks_uri"]),
                        userinfo_endpoint=data.get("userinfo_endpoint"),
                        end_session_endpoint=data.get("end_session_endpoint"),
                        revocation_endpoint=data.get("revocation_endpoint"),
                    )
                    return self._metadata
        raise RuntimeError("Logto OIDC discovery is unavailable")

    def _public_endpoint(self, internal_url: str) -> str:
        internal = urlsplit(internal_url)
        public = urlsplit(self.settings.logto_public_endpoint)
        return urlunsplit((public.scheme, public.netloc, internal.path, internal.query, ""))

    async def authorize(
        self, *, next_path: str = "/", extra_params: dict[str, str] | None = None
    ) -> tuple[str, str]:
        metadata = await self.metadata()
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        nonce = secrets.token_urlsafe(32)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        payload = {
            "state": state,
            "code_verifier": verifier,
            "nonce": nonce,
            "next_path": next_path,
        }
        signed = self._serializer.dumps(payload)
        async with AsyncOAuth2Client(
            client_id=self.settings.oidc_client_id,
            redirect_uri=self.settings.oidc_redirect_uri,
            scope=self.settings.oidc_scopes,
        ) as client:
            authorization_url, _ = client.create_authorization_url(
                self._public_endpoint(metadata.authorization_endpoint),
                state=state,
                nonce=nonce,
                code_challenge=challenge,
                code_challenge_method="S256",
                **(extra_params or {}),
            )
        return authorization_url, signed

    def decode_state(self, value: str) -> OAuthState:
        try:
            payload = self._serializer.loads(value, max_age=600)
        except BadSignature as exc:
            raise ValueError("Invalid or expired OAuth state") from exc
        return OAuthState(**payload)

    async def exchange(self, *, code: str, state: OAuthState) -> dict[str, Any]:
        metadata = await self.metadata()
        async with AsyncOAuth2Client(
            client_id=self.settings.oidc_client_id,
            client_secret=self.settings.oidc_client_secret,
            redirect_uri=self.settings.oidc_redirect_uri,
        ) as client:
            token = await client.fetch_token(
                metadata.token_endpoint,
                grant_type="authorization_code",
                code=code,
                code_verifier=state.code_verifier,
            )
        return dict(token)

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        metadata = await self.metadata()
        async with AsyncOAuth2Client(
            client_id=self.settings.oidc_client_id,
            client_secret=self.settings.oidc_client_secret,
        ) as client:
            token = await client.refresh_token(
                metadata.token_endpoint,
                refresh_token=refresh_token,
            )
        return dict(token)

    async def revoke(self, token: str, *, token_type_hint: str | None = None) -> None:
        metadata = await self.metadata()
        endpoint = metadata.revocation_endpoint
        if not endpoint:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                endpoint,
                data={
                    "token": token,
                    "token_type_hint": token_type_hint or "refresh_token",
                    "client_id": self.settings.oidc_client_id,
                    "client_secret": self.settings.oidc_client_secret,
                },
            )
            if response.status_code >= 400:
                raise RuntimeError("OIDC token revocation failed")

    def verifier(self, *, audience: str | None = None) -> OidcVerifier:
        if self._metadata is None:
            raise RuntimeError("OIDC metadata has not been loaded")
        return OidcVerifier(
            issuer=self.settings.logto_issuer,
            audience=audience or self.settings.oidc_client_id,
            claims_namespace=self.settings.lingxi_claims_namespace,
            discovery=self._metadata,
        )

    def decode_token_claims(self, token: str, *, audience: str | None = None) -> dict[str, Any]:
        return self.verifier(audience=audience).decode(token)

    @staticmethod
    def token_expiry(claims: dict[str, Any]) -> datetime | None:
        value = claims.get("exp")
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return None
