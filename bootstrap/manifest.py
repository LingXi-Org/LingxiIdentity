from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BootstrapManifest:
    admin_resource: str = "https://id.lingxi.dev/admin"
    graph_resource: str = "https://graph.lingxi.dev/api"
    organization_name: str = "Lingxi"
    claims_namespace: str = "https://lingxi.dev/claims/"

    @property
    def admin_scopes(self) -> tuple[tuple[str, str], ...]:
        return (
            ("identity.users.read", "Read users"),
            ("identity.users.write", "Create, update and delete users"),
            ("identity.roles.read", "Read global roles"),
            ("identity.roles.write", "Manage global roles"),
            ("identity.organizations.read", "Read organizations and members"),
            ("identity.organizations.write", "Manage organizations and members"),
            ("identity.audit.read", "Read audit events"),
            ("identity.admin", "Full LingxiIdentity administrator access"),
        )

    @property
    def graph_scopes(self) -> tuple[tuple[str, str], ...]:
        return (
            ("graph.read", "Read LingxiGraph data"),
            ("graph.write", "Write LingxiGraph data"),
        )

    @property
    def organization_roles(self) -> tuple[tuple[str, str], ...]:
        return (("lingxi-tenant-admin", "Lingxi tenant administrators"),)
