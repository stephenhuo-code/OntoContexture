"""主动登录的重新认证要求来自真实适配器，不能只测试 FakeOidc。"""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from contexture_bff.adapters.keycloak import KeycloakOidc
from contexture_bff.main import Services, create_app
from contexture_bff.settings import BffSettings


def test_authorization_requires_login_and_preserves_pkce(settings: BffSettings) -> None:
    url = KeycloakOidc(settings).authorization_url(
        state="fresh-state", code_challenge="fresh-challenge", nonce="fresh-nonce"
    )
    query = parse_qs(urlparse(url).query)
    assert query["prompt"] == ["login"]
    assert query["state"] == ["fresh-state"]
    assert query["nonce"] == ["fresh-nonce"]
    assert query["code_challenge"] == ["fresh-challenge"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == [settings.redirect_uri]


@pytest.mark.parametrize("caller_prompt", [None, "none", "select_account"])
def test_login_endpoint_always_requires_reauthentication(
    settings: BffSettings, services: Services, caller_prompt: str | None
) -> None:
    services.oidc = KeycloakOidc(settings)
    with TestClient(create_app(settings, services=services), follow_redirects=False) as client:
        params = {"return_to": "/assets?q=reauth"}
        if caller_prompt is not None:
            params["prompt"] = caller_prompt
        response = client.get("/bff/v1/auth/login", params=params)
        assert response.status_code == 302
        query = parse_qs(urlparse(response.headers["location"]).query)
        assert query["prompt"] == ["login"]
        assert query["state"] and query["nonce"] and query["code_challenge"]
