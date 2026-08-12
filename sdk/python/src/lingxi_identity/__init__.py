"""Provider-neutral Lingxi identity SDK."""

from .client import AsyncIdentityClient, IdentityClient, OidcService
from .errors import (
    IdentityAuthenticationError,
    IdentityAuthorizationError,
    IdentityConflictError,
    IdentityError,
    IdentityNotFoundError,
    IdentityProviderUnavailableError,
)
from .models import AuditEvent, Organization, Page, Role, User
from .oidc import OidcDiscovery, OidcVerifier
from .principal import Principal, principal_from_claims

__all__ = [
    "AsyncIdentityClient",
    "AuditEvent",
    "IdentityAuthenticationError",
    "IdentityAuthorizationError",
    "IdentityClient",
    "IdentityConflictError",
    "IdentityError",
    "IdentityNotFoundError",
    "IdentityProviderUnavailableError",
    "OidcDiscovery",
    "OidcService",
    "OidcVerifier",
    "Organization",
    "Page",
    "Principal",
    "Role",
    "User",
    "principal_from_claims",
]
