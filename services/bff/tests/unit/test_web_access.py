from typing import cast
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PATHS = ["/bff/v1/me", "/bff/v1/object-types/equipment", "/bff/v1/object-types/equipment/objects"]
ROLES = [("admin",), ("ai-engineer",), ("business-user",), (), ("business-user", "ai-engineer")]


def authenticate(client: TestClient, roles: tuple[str, ...], source: str) -> dict[str, str]:
    svc = cast(FastAPI, client.app).state.services
    svc.oidc.roles = roles
    if source == "bearer":
        return {
            "Authorization": f"Bearer {svc.oidc.issuer.token(realm_access={'roles': list(roles)})}"
        }
    response = client.get("/bff/v1/auth/login")
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    assert (
        client.get("/bff/v1/auth/callback", params={"code": "code", "state": state}).status_code
        == 302
    )
    return {}


@pytest.mark.parametrize("roles", ROLES)
@pytest.mark.parametrize("source", ["cookie", "bearer"])
@pytest.mark.parametrize("path", PATHS)
def test_web_role_matrix(
    signed_client: TestClient, roles: tuple[str, ...], source: str, path: str
) -> None:
    headers = authenticate(signed_client, roles, source)
    response = signed_client.get(
        path, headers={**headers, "X-User-Id": "admin", "X-Roles": "admin", "X-Tenant-Id": "other"}
    )
    allowed = bool({"admin", "ai-engineer"} & set(roles))
    assert response.status_code == (200 if allowed else 403)
    svc = cast(FastAPI, signed_client.app).state.services
    if not allowed:
        assert response.json()["code"] == "auth.web_access_denied"
        assert not svc.object_data.calls
        assert not svc.object_types.calls
        assert "user_id" not in response.json()
    elif path == "/bff/v1/me":
        assert response.json()["tenant_id"] == "local"
        assert response.json()["user_id"] == "user-1-id"


def test_no_role_can_login_and_logout_without_login_loop(signed_client: TestClient) -> None:
    authenticate(signed_client, (), "cookie")
    response = signed_client.get("/bff/v1/me")
    assert response.status_code == 403
    assert "location" not in response.headers
    assert signed_client.post("/bff/v1/auth/logout").status_code == 204
    assert signed_client.post("/bff/v1/auth/logout").status_code == 204
