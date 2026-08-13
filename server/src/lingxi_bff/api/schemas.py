from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_email: str | None = Field(default=None, alias="primaryEmail")
    primary_phone: str | None = Field(default=None, alias="primaryPhone")
    username: str | None = None
    password: SecretStr | None = None
    name: str | None = None
    avatar: str | None = None
    custom_data: dict[str, Any] = Field(default_factory=dict, alias="customData")


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    username: str | None = None
    primary_email: str | None = Field(default=None, alias="primaryEmail")
    primary_phone: str | None = Field(default=None, alias="primaryPhone")
    name: str | None = None
    avatar: str | None = None
    custom_data: dict[str, Any] | None = Field(default=None, alias="customData")
    profile: dict[str, Any] | None = None
    suspended: bool | None = Field(default=None, alias="isSuspended")


class RoleCreate(BaseModel):
    name: str
    description: str | None = None
    scope_ids: list[str] = Field(default_factory=list, alias="scopeIds")


class RolePatch(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleAssignment(BaseModel):
    role_ids: list[str] = Field(alias="roleIds")


class OrganizationCreate(BaseModel):
    name: str
    description: str | None = None
    custom_data: dict[str, Any] = Field(default_factory=dict, alias="customData")


class OrganizationPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    custom_data: dict[str, Any] | None = Field(default=None, alias="customData")


class MemberAssignment(BaseModel):
    user_ids: list[str] = Field(alias="userIds")


class CsrfResponse(BaseModel):
    csrf_token: str = Field(alias="csrfToken")


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    username: str | None = None
    name: str | None = None
    avatar: str | None = None
    custom_data: dict[str, Any] | None = Field(default=None, alias="customData")
    verification_id: str | None = Field(default=None, alias="verificationId")


class PasswordVerification(BaseModel):
    password: SecretStr


class VerificationCodeRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    verification_id: str = Field(alias="verificationId")
    identifier: str
    identifier_type: str = Field(default="email", alias="identifierType")


class VerificationCodeSend(BaseModel):
    identifier: str
    identifier_type: str = Field(default="email", alias="identifierType")


class EmailPatch(BaseModel):
    email: str
    verification_id: str = Field(alias="verificationId")
    new_identifier_verification_id: str = Field(alias="newIdentifierVerificationId")


class PasswordPatch(BaseModel):
    password: SecretStr
    verification_id: str = Field(alias="verificationId")


class SessionItem(BaseModel):
    id: str
    user_id: str | None = Field(default=None, alias="userId")
    application_id: str | None = Field(default=None, alias="applicationId")
    application_name: str | None = Field(default=None, alias="applicationName")
    created_at: Any | None = Field(default=None, alias="createdAt")
    last_used_at: Any | None = Field(default=None, alias="lastUsedAt")
    is_current: bool = Field(default=False, alias="isCurrent")
