from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from httpx import Response

from lingxi_identity.oidc import OidcDiscovery, OidcVerifier, extract_bearer_token


def verifier() -> OidcVerifier:
    return OidcVerifier(
        issuer="https://identity.example.com/oidc",
        audience="https://graph.example.com/api",
        discovery=OidcDiscovery(
            issuer="https://identity.example.com/oidc",
            authorization_endpoint="https://identity.example.com/oidc/auth",
            token_endpoint="https://identity.example.com/oidc/token",
            jwks_uri="https://identity.example.com/oidc/keys",
        ),
    )


@pytest.mark.parametrize(
    "header",
    ["", "Basic token", "Bearer", "Bearer ", "Bearer token extra", "Bearer token,other"],
)
def test_extract_bearer_token_rejects_invalid_headers(header: str) -> None:
    with pytest.raises(jwt.InvalidTokenError):
        extract_bearer_token(header)


def test_extract_bearer_token_accepts_case_insensitive_scheme() -> None:
    assert extract_bearer_token("bEaReR access-token") == "access-token"


def test_verify_claims_accepts_string_and_array_audience() -> None:
    base = {"iss": "https://identity.example.com/oidc", "sub": "u1"}
    assert (
        verifier().verify_claims({**base, "aud": "https://graph.example.com/api"}).subject == "u1"
    )
    assert (
        verifier()
        .verify_claims({**base, "aud": ["other", "https://graph.example.com/api"]})
        .subject
        == "u1"
    )


def test_verify_claims_rejects_wrong_audience() -> None:
    with pytest.raises(jwt.InvalidAudienceError):
        verifier().verify_claims(
            {
                "iss": "https://identity.example.com/oidc",
                "sub": "u1",
                "aud": "https://other.example.com/api",
            }
        )


def test_verify_claims_rejects_wrong_issuer() -> None:
    with pytest.raises(jwt.InvalidIssuerError):
        verifier().verify_claims(
            {
                "iss": "https://other.example.com/oidc",
                "sub": "u1",
                "aud": "https://graph.example.com/api",
            }
        )


@respx.mock
def test_jwks_verifier_accepts_es384_tokens() -> None:
    private_key = ec.generate_private_key(ec.SECP384R1())
    public_jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = "ec-key-1"
    respx.get("https://identity.example.com/oidc/keys").mock(
        return_value=Response(200, json={"keys": [public_jwk]})
    )
    claims = {
        "iss": "https://identity.example.com/oidc",
        "aud": "https://graph.example.com/api",
        "sub": "u1",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(claims, private_key, algorithm="ES384", headers={"kid": "ec-key-1"})
    assert verifier().verify(token).subject == "u1"


@respx.mock
def test_discovery_rejects_issuer_mismatch() -> None:
    respx.get("https://identity.example.com/oidc/.well-known/openid-configuration").mock(
        return_value=Response(
            200,
            json={
                "issuer": "https://attacker.example.com/oidc",
                "authorization_endpoint": "https://attacker.example.com/auth",
                "token_endpoint": "https://attacker.example.com/token",
                "jwks_uri": "https://attacker.example.com/keys",
            },
        )
    )
    with pytest.raises(RuntimeError):
        OidcDiscovery.fetch("https://identity.example.com/oidc")


@respx.mock
def test_jwks_cache_refreshes_after_key_rotation() -> None:
    first_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    second_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    first_key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(first_private.public_key()))
    first_key["kid"] = "key-1"
    second_key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(second_private.public_key()))
    second_key["kid"] = "key-2"
    jwks = respx.get("https://identity.example.com/oidc/keys").mock(
        side_effect=[
            Response(200, json={"keys": [first_key]}),
            Response(200, json={"keys": [second_key]}),
        ]
    )
    claims = {
        "iss": "https://identity.example.com/oidc",
        "aud": "https://graph.example.com/api",
        "sub": "u1",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    first_token = jwt.encode(claims, first_private, algorithm="RS256", headers={"kid": "key-1"})
    second_token = jwt.encode(claims, second_private, algorithm="RS256", headers={"kid": "key-2"})
    target = verifier()
    assert target.verify(first_token).subject == "u1"
    assert target.verify_authorization_header(f"Bearer {first_token}").subject == "u1"
    assert target.verify(second_token).subject == "u1"
    assert jwks.call_count == 2
