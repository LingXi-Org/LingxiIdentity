from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str
    tenant_id: str | None = None
    roles: frozenset[str] = Field(default_factory=frozenset)
    permissions: frozenset[str] = Field(default_factory=frozenset)
    issuer: str | None = None
    audience: frozenset[str] = Field(default_factory=frozenset)


def _as_strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {part for part in value.split() if part}
    if isinstance(value, (list, tuple, set, frozenset)):
        return {str(part) for part in value if part}
    return set()


def principal_from_claims(
    claims: Mapping[str, Any], *, claims_namespace: str = "https://lingxi.dev/claims/"
) -> Principal:
    subject = claims.get("sub")
    if not subject:
        raise ValueError("JWT is missing required sub claim")

    tenant_id = claims.get(f"{claims_namespace}tenant_id") or claims.get("organization_id")
    roles = _as_strings(claims.get(f"{claims_namespace}roles") or claims.get("roles"))
    permissions = _as_strings(
        claims.get(f"{claims_namespace}permissions")
        or claims.get("permissions")
        or claims.get("scope")
    )
    permissions -= {"openid", "profile", "email", "offline_access"}

    organization_roles = _as_strings(claims.get("organization_roles"))
    if tenant_id:
        prefix = f"{tenant_id}:"
        roles.update(
            item.removeprefix(prefix) for item in organization_roles if item.startswith(prefix)
        )

    audience = _as_strings(claims.get("aud"))
    return Principal(
        subject=str(subject),
        tenant_id=str(tenant_id) if tenant_id else None,
        roles=frozenset(roles),
        permissions=frozenset(permissions),
        issuer=str(claims["iss"]) if claims.get("iss") else None,
        audience=frozenset(audience),
    )
