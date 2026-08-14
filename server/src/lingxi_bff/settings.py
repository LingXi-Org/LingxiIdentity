from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    bff_host: str = "0.0.0.0"
    bff_port: int = 8080
    bff_public_url: str = "http://localhost:8080"
    bff_web_public_url: str = ""
    bff_default_next_path: str = "/"
    bff_allowed_origins: str = "http://localhost:8080"
    bff_allowed_hosts: str = "*"

    logto_public_endpoint: str = "http://localhost:3001"
    logto_internal_endpoint: str = "http://logto:3001"
    logto_image: str = "ghcr.io/logto-io/logto:1.33.0"
    logto_issuer: str = "http://localhost:3001/oidc"
    logto_management_api_indicator: str = "https://default.logto.app/api"
    logto_m2m_client_id: str = ""
    logto_m2m_client_secret: str = ""
    logto_m2m_client_secret_file: str = ""

    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_scopes: str = "openid profile email offline_access roles urn:logto:scope:organizations urn:logto:scope:organization_roles"
    oidc_resource: str = "https://id.lingxi.dev/admin"
    oidc_redirect_path: str = "/auth/callback"

    lingxi_database_url: str = "postgresql+asyncpg://lingxi:change-me@postgres:5432/lingxi"
    session_cookie_name: str = "lingxi_session"
    session_cookie_secure: bool = False
    session_ttl_seconds: int = 28800
    session_refresh_skew_seconds: int = 120
    session_cookie_domain: str | None = None
    session_cookie_path: str = "/"
    verification_record_ttl_seconds: int = 600
    session_encryption_key: str = ""
    lingxi_claims_namespace: str = "https://lingxi.dev/claims/"

    @field_validator("bff_allowed_origins", mode="before")
    @classmethod
    def normalize_origins(cls, value: object) -> str:
        if isinstance(value, list):
            return ",".join(str(item) for item in value)
        return str(value)

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.bff_allowed_origins.split(",") if item.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [item.strip() for item in self.bff_allowed_hosts.split(",") if item.strip()]

    @property
    def effective_session_cookie_path(self) -> str:
        # The BFF session is consumed by /auth, /api and the web app. A
        # narrower configured path can make /api/v1/me succeed while the
        # workspace route sees no session and redirects back to /login.
        return "/"

    @property
    def resolved_m2m_secret(self) -> str:
        if self.logto_m2m_client_secret:
            return self.logto_m2m_client_secret
        if self.logto_m2m_client_secret_file:
            return Path(self.logto_m2m_client_secret_file).read_text(encoding="utf-8").strip()
        return ""

    @property
    def oidc_redirect_uri(self) -> str:
        return f"{self.bff_public_url.rstrip('/')}{self.oidc_redirect_path}"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    def validate_runtime(self) -> None:
        if self.bff_web_public_url and not self.bff_web_public_url.startswith(
            ("http://", "https://")
        ):
            raise ValueError("BFF_WEB_PUBLIC_URL must be an absolute HTTP(S) URL")
        if self.is_production:
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true in production")
            if not self.bff_public_url.startswith("https://"):
                raise ValueError("BFF_PUBLIC_URL must use HTTPS in production")
            if not self.logto_public_endpoint.startswith("https://"):
                raise ValueError("LOGTO_PUBLIC_ENDPOINT must use HTTPS in production")
            if self.bff_web_public_url and not self.bff_web_public_url.startswith("https://"):
                raise ValueError("BFF_WEB_PUBLIC_URL must use HTTPS in production")
        if not self.session_encryption_key:
            raise ValueError("SESSION_ENCRYPTION_KEY is required")
        if not self.oidc_client_id:
            raise ValueError("OIDC_CLIENT_ID is required")
        if not self.logto_m2m_client_id or not self.resolved_m2m_secret:
            raise ValueError("Logto Management M2M credentials are required")
        if self.session_refresh_skew_seconds < 0:
            raise ValueError("SESSION_REFRESH_SKEW_SECONDS must be non-negative")
        if self.verification_record_ttl_seconds <= 0:
            raise ValueError("VERIFICATION_RECORD_TTL_SECONDS must be positive")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime()
    return settings
