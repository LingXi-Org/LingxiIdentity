from cryptography.fernet import Fernet

from lingxi_bff.settings import Settings


def test_production_settings_require_https() -> None:
    settings = Settings(
        app_env="production",
        session_encryption_key=Fernet.generate_key().decode(),
        session_cookie_secure=True,
        bff_public_url="https://admin.example.com",
        logto_public_endpoint="https://identity.example.com",
        oidc_client_id="web",
        logto_m2m_client_id="m2m",
        logto_m2m_client_secret="secret",
    )
    settings.validate_runtime()


def test_allowed_hosts_always_include_internal_docker_gateway() -> None:
    settings = Settings(bff_allowed_hosts="identity.lingxilearn.cn")

    assert settings.allowed_hosts == [
        "identity.lingxilearn.cn",
        "localhost",
        "127.0.0.1",
        "host.docker.internal",
    ]


def test_allowed_hosts_preserve_wildcard() -> None:
    settings = Settings(bff_allowed_hosts="*")

    assert settings.allowed_hosts == ["*"]
