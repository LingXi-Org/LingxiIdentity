from __future__ import annotations

import re
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx
import jwt

from .principal import Principal, principal_from_claims


def extract_bearer_token(authorization: str) -> str:
    """Extract one bearer token from an RFC 6750 Authorization header value."""
    if not authorization:
        raise jwt.InvalidTokenError("Authorization header is required")
    parts = authorization.strip().split()
    if (
        len(parts) != 2
        or parts[0].lower() != "bearer"
        or not re.fullmatch(r"[A-Za-z0-9\-._~+/]+=*", parts[1])
    ):
        raise jwt.InvalidTokenError("Authorization header must be 'Bearer <token>'")
    return parts[1]


@dataclass(frozen=True)
class OidcDiscovery:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str | None = None
    end_session_endpoint: str | None = None
    revocation_endpoint: str | None = None

    @classmethod
    def fetch(cls, issuer: str, *, timeout: float = 10.0) -> "OidcDiscovery":
        base = issuer.rstrip("/")
        candidates = [
            f"{base}/.well-known/openid-configuration",
            f"{base}/oidc/.well-known/openid-configuration",
        ]
        last_error: Exception | None = None
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            for url in candidates:
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    discovered_issuer = str(data["issuer"]).rstrip("/")
                    if discovered_issuer != base.rstrip("/"):
                        raise ValueError(
                            "OIDC discovery issuer does not match the requested issuer"
                        )
                    return cls(
                        issuer=discovered_issuer,
                        authorization_endpoint=str(data["authorization_endpoint"]),
                        token_endpoint=str(data["token_endpoint"]),
                        jwks_uri=str(data["jwks_uri"]),
                        userinfo_endpoint=data.get("userinfo_endpoint"),
                        end_session_endpoint=data.get("end_session_endpoint"),
                    )
                except Exception as exc:  # pragma: no cover - error detail is preserved below
                    last_error = exc
        raise RuntimeError(f"OIDC discovery failed for {issuer}: {last_error}")


class _JwksCache:
    def __init__(self, jwks_uri: str, *, ttl_seconds: int = 300, timeout: float = 10.0) -> None:
        self.jwks_uri = jwks_uri
        self.ttl_seconds = ttl_seconds
        self.timeout = timeout
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._lock = Lock()

    def _refresh(self) -> None:
        response = httpx.get(self.jwks_uri, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        self._keys = {
            str(item["kid"]): jwt.PyJWK(item).key
            for item in payload.get("keys", [])
            if item.get("kid")
        }
        self._expires_at = time.monotonic() + self.ttl_seconds

    def key_for(self, token: str) -> Any:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise jwt.InvalidTokenError("JWT is missing kid")
        with self._lock:
            if time.monotonic() >= self._expires_at or kid not in self._keys:
                self._refresh()
            key = self._keys.get(kid)
            if key is None:
                self._refresh()
                key = self._keys.get(kid)
        if key is None:
            raise jwt.InvalidTokenError(f"No JWKS key found for kid={kid}")
        return key


class OidcVerifier:
    """JWT verifier using OIDC discovery and the provider's JWKS endpoint."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithms: tuple[str, ...] = ("RS256", "ES256", "ES384"),
        claims_namespace: str = "https://lingxi.dev/claims/",
        timeout: float = 10.0,
        discovery: OidcDiscovery | None = None,
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.algorithms = algorithms
        self.claims_namespace = claims_namespace
        self.discovery = discovery or OidcDiscovery.fetch(self.issuer, timeout=timeout)
        self._jwks = _JwksCache(self.discovery.jwks_uri, timeout=timeout)

    def decode(self, token: str, *, nonce: str | None = None) -> dict[str, Any]:
        key = self._jwks.key_for(token)
        claims = jwt.decode(
            token,
            key=key,
            algorithms=list(self.algorithms),
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["sub", "iss", "aud", "exp"]},
        )
        if nonce is not None and claims.get("nonce") != nonce:
            raise jwt.InvalidTokenError("OIDC nonce mismatch")
        return claims

    def verify(self, token: str, *, nonce: str | None = None) -> Principal:
        return principal_from_claims(
            self.decode(token, nonce=nonce), claims_namespace=self.claims_namespace
        )

    def verify_authorization_header(self, authorization: str) -> Principal:
        return self.verify(extract_bearer_token(authorization))

    def verify_claims(self, claims: dict[str, Any], *, nonce: str | None = None) -> Principal:
        if claims.get("iss") != self.issuer:
            raise jwt.InvalidIssuerError("OIDC issuer mismatch")
        audience = claims.get("aud")
        audiences = {audience} if isinstance(audience, str) else set(audience or [])
        if self.audience not in audiences:
            raise jwt.InvalidAudienceError("OIDC audience mismatch")
        if nonce is not None and claims.get("nonce") != nonce:
            raise jwt.InvalidTokenError("OIDC nonce mismatch")
        return principal_from_claims(claims, claims_namespace=self.claims_namespace)
