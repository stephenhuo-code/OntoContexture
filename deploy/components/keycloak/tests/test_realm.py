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
