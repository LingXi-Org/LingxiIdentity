from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class LingxiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Page(LingxiModel, Generic[T]):
    items: list[T]
    page: int = 1
    page_size: int = 20
    total: int | None = None
    total_is_capped: bool = False


class User(LingxiModel):
    id: str
    username: str | None = None
    primary_email: str | None = Field(default=None, alias="primaryEmail")
    primary_phone: str | None = Field(default=None, alias="primaryPhone")
    name: str | None = None
    avatar: str | None = None
    suspended: bool = Field(default=False, alias="isSuspended")
    has_password: bool | None = Field(default=None, alias="hasPassword")
    custom_data: dict[str, Any] = Field(default_factory=dict, alias="customData")
    profile: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class AccountSession(LingxiModel):
    id: str
    user_id: str | None = Field(default=None, alias="userId")
    application_id: str | None = Field(default=None, alias="applicationId")
    application_name: str | None = Field(default=None, alias="applicationName")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    last_used_at: datetime | None = Field(default=None, alias="lastUsedAt")
    is_current: bool = Field(default=False, alias="isCurrent")


class VerificationRecord(LingxiModel):
    verification_record_id: str = Field(alias="verificationRecordId")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")


class Permission(LingxiModel):
    name: str
    description: str | None = None
    resource: str | None = None


class Role(LingxiModel):
    id: str
    name: str
    description: str | None = None
    permissions: list[Permission] = Field(default_factory=list)


class Organization(LingxiModel):
    id: str
    name: str
    description: str | None = None
    custom_data: dict[str, Any] = Field(default_factory=dict, alias="customData")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class Membership(LingxiModel):
    user_id: str = Field(alias="userId")
    organization_id: str = Field(alias="organizationId")
    roles: list[Role] = Field(default_factory=list)


class AuditEvent(LingxiModel):
    id: str
    key: str
    result: str
    user_id: str | None = Field(default=None, alias="userId")
    application_id: str | None = Field(default=None, alias="applicationId")
    ip: str | None = None
    user_agent: str | None = Field(default=None, alias="userAgent")
    params: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(default=None, alias="createdAt")
