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
from .models import AccountSession, AuditEvent, Organization, Page, Role, User, VerificationRecord
from .oidc import OidcDiscovery, OidcVerifier, extract_bearer_token
from .principal import Principal, principal_from_claims

__all__ = [
    "AsyncIdentityClient",
    "AccountSession",
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
    "extract_bearer_token",
    "Organization",
    "Page",
    "Principal",
    "Role",
    "User",
    "VerificationRecord",
    "principal_from_claims",
]
