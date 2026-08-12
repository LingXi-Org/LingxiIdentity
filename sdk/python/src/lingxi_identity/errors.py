from __future__ import annotations

from typing import Any


class IdentityError(Exception):
    """Base error for provider-neutral identity operations."""

    def __init__(
        self, message: str, *, status_code: int | None = None, details: Any = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class IdentityAuthenticationError(IdentityError):
    pass


class IdentityAuthorizationError(IdentityError):
    pass


class IdentityNotFoundError(IdentityError):
    pass


class IdentityConflictError(IdentityError):
    pass


class IdentityProviderUnavailableError(IdentityError):
    pass
