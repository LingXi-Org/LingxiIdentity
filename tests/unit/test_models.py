from lingxi_identity import User


def test_user_maps_provider_fields() -> None:
    user = User.model_validate(
        {"id": "u1", "primaryEmail": "a@example.com", "hasPassword": True, "isSuspended": True}
    )
    assert user.primary_email == "a@example.com"
    assert user.has_password is True
    assert user.suspended is True
