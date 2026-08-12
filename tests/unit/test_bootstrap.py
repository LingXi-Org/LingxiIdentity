from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from bootstrap.cli import ensure_application
from bootstrap.manifest import BootstrapManifest
from httpx import Response


def test_manifest_contains_lingxilearn_resource_and_scopes() -> None:
    manifest = BootstrapManifest()
    assert manifest.learn_resource == "https://learn.lingxi.dev/api"
    assert tuple(name for name, _ in manifest.learn_scopes) == ("learn.read", "learn.write")


@pytest.mark.asyncio
async def test_public_spa_has_no_secret_configuration() -> None:
    api = AsyncMock()
    api.list_all.return_value = []
    api.request.return_value = Response(
        201,
        json={"id": "learn-web", "type": "SPA", "name": "LingxiLearn Web"},
    )

    app = await ensure_application(api, name="LingxiLearn Web", app_type="SPA")

    body = api.request.call_args.kwargs["body"]
    assert app["type"] == "SPA"
    assert body["type"] == "SPA"
    assert "secret" not in body
    assert body["oidcClientMetadata"]["redirectUris"] == []
