"""Keycloak 配置测试（ADR-0009：导入后实际做一次令牌交换，核对 sub、azp、受众）。

预置一个代表 Paperclip 的已有客户端，再增量导入织境配置；验证已有客户端不变、
user1 登录后经 contexture-bff 做标准令牌交换得到的令牌正确。
"""

import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from support.keycloak import (
    BFF_SECRET,
    REALM,
    Admin,
    KeycloakEnv,
    audiences,
    import_config,
    jwt_claims,
    keycloak,
    login,
)

pytestmark = pytest.mark.integration

PUBLIC_URL = "http://localhost:8080"
REDIRECT_URI = f"{PUBLIC_URL}/bff/v1/auth/callback"
PAPERCLIP: dict[str, Any] = {
    "clientId": "paperclip",
    "publicClient": False,
    "secret": "paperclip-secret",
    "standardFlowEnabled": True,
    "directAccessGrantsEnabled": True,
    "redirectUris": ["https://paperclip.example/*"],
}


@pytest.fixture(scope="module")
def imported() -> Iterator[tuple[KeycloakEnv, Admin, dict[str, Any]]]:
    with keycloak() as env:
        admin = Admin(env.base_url)
        admin.create_realm()
        assert admin.http.post(f"/{REALM}/clients", json=PAPERCLIP).status_code == 201
        paperclip_before = admin.client("paperclip")
        import_config(env, PUBLIC_URL)
        yield env, admin, paperclip_before


def exchange(env: KeycloakEnv, subject_token: str, audience: str) -> httpx.Response:
    return httpx.post(
        f"{env.oidc}/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "client_id": "contexture-bff",
            "client_secret": BFF_SECRET,
            "subject_token": subject_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "audience": audience,
        },
    )


def user1_token(env: KeycloakEnv) -> str:
    return str(login(env, "user1", "user1", REDIRECT_URI)["access_token"])


def test_existing_client_unchanged(imported: tuple[KeycloakEnv, Admin, dict[str, Any]]) -> None:
    _, admin, before = imported
    assert admin.client("paperclip") == before


def test_login_theme_is_client_scoped_and_served(
    imported: tuple[KeycloakEnv, Admin, dict[str, Any]],
) -> None:
    env, admin, before = imported
    assert admin.client("contexture-bff")["attributes"].get("login_theme") == "contexture"
    realm = admin.http.get(f"/{REALM}").json()
    assert realm.get("loginTheme") != "contexture"
    assert admin.client("paperclip") == before
    page = httpx.get(
        f"{env.oidc}/auth",
        params={
            "client_id": "contexture-bff",
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "openid",
            "code_challenge": "t" * 43,
            "code_challenge_method": "S256",
            "prompt": "login",
        },
    )
    assert page.status_code == 200
    assert "/contexture/identity/identity.css" in page.text
    assert 'id="kc-form-login"' in page.text and 'name="password"' in page.text


def test_roles_and_clients_created(imported: tuple[KeycloakEnv, Admin, dict[str, Any]]) -> None:
    _, admin, _ = imported
    roles = {r["name"] for r in admin.http.get(f"/{REALM}/roles").json()}
    assert {"admin", "ai-engineer", "business-user"} <= roles
    bff = admin.client("contexture-bff")
    assert bff["publicClient"] is False
    assert bff["directAccessGrantsEnabled"] is False
    assert bff["attributes"].get("standard.token.exchange.enabled") == "true"
    assert bff["attributes"].get("pkce.code.challenge.method") == "S256"
    gateway = admin.client("contexture-ai-gateway")
    assert gateway["standardFlowEnabled"] is False
    assert gateway["directAccessGrantsEnabled"] is False


def test_login_token_audiences(imported: tuple[KeycloakEnv, Admin, dict[str, Any]]) -> None:
    env, _, _ = imported
    claims = jwt_claims(user1_token(env))
    assert claims["azp"] == "contexture-bff"
    assert {"contexture-bff", "contexture-ai-gateway"} <= set(audiences(claims))


def test_token_exchange_for_ai_gateway(
    imported: tuple[KeycloakEnv, Admin, dict[str, Any]],
) -> None:
    env, admin, _ = imported
    resp = exchange(env, user1_token(env), "contexture-ai-gateway")
    assert resp.status_code == 200, resp.text
    claims = jwt_claims(resp.json()["access_token"])
    assert claims["sub"] == admin.user_id("user1")
    assert claims["preferred_username"] == "user1"
    assert claims["azp"] == "contexture-bff"
    assert audiences(claims) == ["contexture-ai-gateway"]
    assert "business-user" in claims["realm_access"]["roles"]
    assert claims["exp"] > time.time()


def test_exchange_to_unknown_audience_rejected(
    imported: tuple[KeycloakEnv, Admin, dict[str, Any]],
) -> None:
    env, _, _ = imported
    assert exchange(env, user1_token(env), "paperclip").status_code >= 400


# ---------- 005：BFF 以用户委托令牌调用 OpenMetadata（research R5、R13） ----------
OM_AUDIENCE = "contexture-openmetadata"


def test_login_token_includes_openmetadata_audience(
    imported: tuple[KeycloakEnv, Admin, dict[str, Any]],
) -> None:
    env, _, _ = imported
    assert OM_AUDIENCE in audiences(jwt_claims(user1_token(env)))


def test_token_exchange_for_openmetadata(
    imported: tuple[KeycloakEnv, Admin, dict[str, Any]],
) -> None:
    env, admin, _ = imported
    resp = exchange(env, user1_token(env), OM_AUDIENCE)
    assert resp.status_code == 200, resp.text
    claims = jwt_claims(resp.json()["access_token"])
    assert claims["sub"] == admin.user_id("user1")
    assert claims["preferred_username"] == "user1"
    assert claims["azp"] == "contexture-bff"
    assert audiences(claims) == [OM_AUDIENCE]
    assert "business-user" in claims["realm_access"]["roles"]


def test_bff_service_account_token(
    imported: tuple[KeycloakEnv, Admin, dict[str, Any]],
) -> None:
    """BFF 以自身服务账号在 OM 中建档用户、同步团队（R13）。"""
    env, _, _ = imported
    resp = httpx.post(
        f"{env.oidc}/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "contexture-bff",
            "client_secret": BFF_SECRET,
        },
    )
    assert resp.status_code == 200, resp.text
    claims = jwt_claims(resp.json()["access_token"])
    assert claims["preferred_username"] == "service-account-contexture-bff"
    assert claims["azp"] == "contexture-bff"
    assert OM_AUDIENCE in audiences(claims)
