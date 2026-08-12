from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from typing import Any

import httpx
import typer

from .manifest import BootstrapManifest

app = typer.Typer(add_completion=False, help="Idempotently provision LingxiIdentity on Logto OSS.")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class ManagementApi:
    def __init__(
        self, *, base_url: str, client_id: str, client_secret: str, indicator: str
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.indicator = indicator
        self.client = httpx.AsyncClient(timeout=20, follow_redirects=True)
        self.access_token = ""

    async def close(self) -> None:
        await self.client.aclose()

    async def token(self) -> str:
        if self.access_token:
            return self.access_token
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = await self.client.post(
            f"{self.base_url}/oidc/token",
            headers={"Authorization": f"Basic {basic}"},
            data={"grant_type": "client_credentials", "resource": self.indicator, "scope": "all"},
        )
        response.raise_for_status()
        self.access_token = str(response.json()["access_token"])
        return self.access_token

    async def request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None, body: Any = None
    ) -> httpx.Response:
        response = await self.client.request(
            method,
            f"{self.base_url}{path}",
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {await self.token()}", "Accept": "application/json"},
        )
        if response.status_code == 401:
            self.access_token = ""
            response = await self.client.request(
                method,
                f"{self.base_url}{path}",
                params=params,
                json=body,
                headers={
                    "Authorization": f"Bearer {await self.token()}",
                    "Accept": "application/json",
                },
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Logto Management API {method} {path} returned {response.status_code}: {response.text[:500]}"
            )
        return response

    async def list_all(self, path: str) -> list[dict[str, Any]]:
        response = await self.request("GET", path, params={"page": 1, "page_size": 100})
        payload = response.json()
        return (
            payload if isinstance(payload, list) else payload.get("data", payload.get("items", []))
        )


def json_object(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Logto Management API response must be a JSON object")
    return {str(key): value for key, value in payload.items()}


def marker(name: str) -> dict[str, str]:
    return {"managedBy": "LingxiIdentity", "manifest": "v1", "name": name}


async def first_by_name(api: ManagementApi, path: str, name: str) -> dict[str, Any] | None:
    for item in await api.list_all(path):
        if item.get("name") == name:
            return item
    return None


async def ensure_resource(api: ManagementApi, *, name: str, indicator: str) -> dict[str, Any]:
    existing = await first_by_name(api, "/api/resources", name)
    if existing:
        return existing
    return json_object(
        await api.request(
            "POST",
            "/api/resources",
            body={
                "tenantId": "default",
                "name": name,
                "indicator": indicator,
                "accessTokenTtl": 3600,
            },
        )
    )


async def ensure_scope(
    api: ManagementApi, resource_id: str, name: str, description: str
) -> dict[str, Any]:
    existing = await api.list_all(f"/api/resources/{resource_id}/scopes")
    for item in existing:
        if item.get("name") == name:
            return item
    return json_object(
        await api.request(
            "POST",
            f"/api/resources/{resource_id}/scopes",
            body={"name": name, "description": description},
        )
    )


async def ensure_global_role(
    api: ManagementApi, *, name: str, description: str, scope_ids: list[str]
) -> dict[str, Any]:
    existing = await first_by_name(api, "/api/roles", name)
    if existing:
        return existing
    return json_object(
        await api.request(
            "POST",
            "/api/roles",
            body={"name": name, "description": description, "type": "User", "scopeIds": scope_ids},
        )
    )


async def ensure_organization_role(
    api: ManagementApi, *, name: str, description: str, resource_scope_ids: list[str]
) -> dict[str, Any]:
    existing = await first_by_name(api, "/api/organization-roles", name)
    if existing:
        role = existing
    else:
        role = json_object(
            await api.request(
                "POST",
                "/api/organization-roles",
                body={
                    "tenantId": "default",
                    "name": name,
                    "description": description,
                    "type": "User",
                    "organizationScopeIds": [],
                    "resourceScopeIds": resource_scope_ids,
                },
            )
        )
    await api.request(
        "POST",
        f"/api/organization-roles/{role['id']}/resource-scopes",
        body={"scopeIds": resource_scope_ids},
    )
    return role


async def ensure_organization(api: ManagementApi, manifest: BootstrapManifest) -> dict[str, Any]:
    existing = await first_by_name(api, "/api/organizations", manifest.organization_name)
    if existing:
        return existing
    return json_object(
        await api.request(
            "POST",
            "/api/organizations",
            body={
                "name": manifest.organization_name,
                "description": "Lingxi default organization",
                "customData": marker(manifest.organization_name),
            },
        )
    )


async def ensure_application(
    api: ManagementApi,
    *,
    name: str,
    app_type: str,
    redirect_uri: str | None = None,
    post_logout_uri: str | None = None,
) -> dict[str, Any]:
    existing = await first_by_name(api, "/api/applications", name)
    if existing:
        return existing
    metadata: dict[str, Any] = {
        "redirectUris": [redirect_uri] if redirect_uri else [],
        "postLogoutRedirectUris": [post_logout_uri] if post_logout_uri else [],
    }
    body = {
        "name": name,
        "description": "Managed by LingxiIdentity bootstrap",
        "type": app_type,
        "oidcClientMetadata": metadata,
        "customData": marker(name),
        "customClientMetadata": {"alwaysIssueRefreshToken": True, "rotateRefreshToken": True},
    }
    return json_object(await api.request("POST", "/api/applications", body=body))


async def ensure_m2m_management_role(api: ManagementApi, application_id: str) -> None:
    roles = await api.list_all("/api/roles")
    role = next((item for item in roles if item.get("name") == "Logto Management API access"), None)
    if not role:
        raise RuntimeError("The built-in 'Logto Management API access' M2M role was not found")
    assigned = await api.list_all(f"/api/roles/{role['id']}/applications")
    if any(item.get("id") == application_id for item in assigned):
        return
    await api.request(
        "POST", f"/api/roles/{role['id']}/applications", body={"applicationIds": [application_id]}
    )


async def ensure_user(
    api: ManagementApi, email: str, password: str, role_id: str
) -> dict[str, Any] | None:
    if not email or not password:
        return None
    users = await api.list_all("/api/users")
    user = next((item for item in users if item.get("primaryEmail") == email), None)
    if not user:
        user = json_object(
            await api.request(
                "POST",
                "/api/users",
                body={"primaryEmail": email, "password": password, "name": "Lingxi Administrator"},
            )
        )
    await api.request("PUT", f"/api/users/{user['id']}/roles", body={"roleIds": [role_id]})
    return user


async def ensure_organization_membership(
    api: ManagementApi, *, organization_id: str, user_id: str, organization_role_id: str
) -> None:
    members = await api.list_all(f"/api/organizations/{organization_id}/users")
    if not any(item.get("id") == user_id for item in members):
        await api.request(
            "POST",
            f"/api/organizations/{organization_id}/users",
            body={"userIds": [user_id]},
        )
    await api.request(
        "PUT",
        f"/api/organizations/{organization_id}/users/{user_id}/roles",
        body={"organizationRoleIds": [organization_role_id]},
    )


async def configure_claims(api: ManagementApi, manifest: BootstrapManifest) -> None:
    namespace = manifest.claims_namespace
    script = f"""const getCustomJwtClaims = async ({{ token, context }}) => {{
  const permissions = (token.scope || '').split(' ').filter(Boolean).filter((item) => !['openid', 'profile', 'email', 'offline_access'].includes(item));
  const user = context && context.user;
  const roles = user ? (user.roles || []).map((role) => role.name) : [];
  const organizationId = token.organization_id || (context && context.organization && context.organization.id) || null;
  const organizationRoles = user ? (user.organizationRoles || []).filter((item) => !organizationId || item.organizationId === organizationId).map((item) => item.roleName) : [];
  return {{
    '{namespace}tenant_id': organizationId,
    '{namespace}roles': [...new Set([...roles, ...organizationRoles])],
    '{namespace}permissions': [...new Set(permissions)],
  }};
}};"""
    sample = {"user": {"id": "sample", "roles": [], "organizations": [], "organizationRoles": []}}
    token_sample = {
        "aud": manifest.graph_resource,
        "scope": "graph.read",
        "clientId": "sample",
        "kind": "AccessToken",
    }
    body = {
        "script": script,
        "environmentVariables": {},
        "contextSample": sample,
        "tokenSample": token_sample,
    }
    await api.request("PUT", "/api/configs/jwt-customizer/access-token", body=body)


async def configure_branding(api: ManagementApi) -> None:
    current = (await api.request("GET", "/api/sign-in-exp")).json()
    current["tenantId"] = "default"
    current["color"] = {
        "primaryColor": "#2563EB",
        "isDarkModeEnabled": True,
        "darkPrimaryColor": "#60A5FA",
    }
    current["languageInfo"] = {"autoDetect": True, "fallbackLanguage": "zh-CN"}
    current["customContent"] = {"/": "LingxiIdentity"}
    await api.request("PATCH", "/api/sign-in-exp", body=current)


async def run() -> dict[str, str]:
    seed_id = env("BOOTSTRAP_SEED_CLIENT_ID") or env("LOGTO_M2M_CLIENT_ID")
    seed_secret = env("BOOTSTRAP_SEED_CLIENT_SECRET") or env("LOGTO_M2M_CLIENT_SECRET")
    if not seed_id or not seed_secret:
        raise typer.BadParameter(
            "Set BOOTSTRAP_SEED_CLIENT_ID and BOOTSTRAP_SEED_CLIENT_SECRET first"
        )
    manifest = BootstrapManifest(
        admin_resource=env("LINGXI_ADMIN_RESOURCE", "https://id.lingxi.dev/admin"),
        graph_resource=env("LINGXI_GRAPH_RESOURCE", "https://graph.lingxi.dev/api"),
        organization_name=env("BOOTSTRAP_ORGANIZATION_NAME", "Lingxi"),
        claims_namespace=env("LINGXI_CLAIMS_NAMESPACE", "https://lingxi.dev/claims/"),
    )
    api = ManagementApi(
        base_url=env("LOGTO_INTERNAL_ENDPOINT", "http://logto:3001"),
        client_id=seed_id,
        client_secret=seed_secret,
        indicator=env("LOGTO_MANAGEMENT_API_INDICATOR", "https://default.logto.app/api"),
    )
    try:
        admin_resource = await ensure_resource(
            api, name="Lingxi Admin API", indicator=manifest.admin_resource
        )
        graph_resource = await ensure_resource(
            api, name="Lingxi Graph API", indicator=manifest.graph_resource
        )
        admin_scopes = [
            await ensure_scope(api, admin_resource["id"], name, description)
            for name, description in manifest.admin_scopes
        ]
        _graph_scopes = [
            await ensure_scope(api, graph_resource["id"], name, description)
            for name, description in manifest.graph_scopes
        ]
        admin_role = await ensure_global_role(
            api,
            name="lingxi-admin",
            description="LingxiIdentity administrators",
            scope_ids=[item["id"] for item in admin_scopes],
        )
        tenant_admin_role = await ensure_organization_role(
            api,
            name=manifest.organization_roles[0][0],
            description=manifest.organization_roles[0][1],
            resource_scope_ids=[item["id"] for item in admin_scopes],
        )
        organization = await ensure_organization(api, manifest)
        user = await ensure_user(
            api, env("BOOTSTRAP_ADMIN_EMAIL"), env("BOOTSTRAP_ADMIN_PASSWORD"), admin_role["id"]
        )
        if user:
            await ensure_organization_membership(
                api,
                organization_id=str(organization["id"]),
                user_id=str(user["id"]),
                organization_role_id=str(tenant_admin_role["id"]),
            )
        web_app = await ensure_application(
            api,
            name="Lingxi Admin BFF",
            app_type="Traditional",
            redirect_uri=f"{env('BFF_PUBLIC_URL', 'http://localhost:8080')}/auth/callback",
            post_logout_uri=env("BFF_PUBLIC_URL", "http://localhost:8080"),
        )
        m2m_app = await ensure_application(
            api, name="Lingxi Admin BFF Management M2M", app_type="MachineToMachine"
        )
        await ensure_m2m_management_role(api, m2m_app["id"])
        await configure_claims(api, manifest)
        await configure_branding(api)
        output = {
            "OIDC_CLIENT_ID": env("OIDC_CLIENT_ID") or str(web_app.get("id", "")),
            "OIDC_CLIENT_SECRET": env("OIDC_CLIENT_SECRET") or str(web_app.get("secret", "")),
            "LOGTO_M2M_CLIENT_ID": env("LOGTO_M2M_CLIENT_ID") or str(m2m_app.get("id", "")),
            "LOGTO_M2M_CLIENT_SECRET": env("LOGTO_M2M_CLIENT_SECRET")
            or str(m2m_app.get("secret", "")),
            "BOOTSTRAP_ADMIN_USER_ID": str(user.get("id", "")) if user else "",
            "GRAPH_RESOURCE": manifest.graph_resource,
        }
        return output
    finally:
        await api.close()


@app.command()
def provision(
    output_file: str = typer.Option(
        "", envvar="BOOTSTRAP_OUTPUT_FILE", help="Write generated credentials to this file."
    ),
) -> None:
    """Provision resources, roles, applications, branding and JWT claims."""
    result = asyncio.run(run())
    lines = [f"{key}={value}" for key, value in result.items() if value]
    rendered = "\n".join(lines) + "\n"
    if output_file:
        target = Path(output_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        typer.echo(f"Bootstrap completed. Credentials written to {target}.")
    else:
        typer.echo(rendered)


if __name__ == "__main__":
    app()
