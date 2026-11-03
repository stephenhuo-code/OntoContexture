from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


def test_browser_failure_has_safe_redirect_contract(signed_client: TestClient) -> None:
    response = signed_client.get(
        "/bff/v1/auth/callback",
        params={"code": "SECRET", "state": "forged", "error_description": "PRIVATE"},
    )
    assert response.status_code == 303
    location = urlparse(response.headers["location"])
    assert location.path == "/auth/error"
    assert not location.netloc
    query = parse_qs(location.query)
    assert query["reason"] == ["invalid_response"]
    assert query["return_to"] == ["/home"]
    assert set(query) <= {"reason", "return_to", "trace_id"}
    assert "SECRET" not in response.text + response.headers["location"]
    assert "PRIVATE" not in response.text + response.headers["location"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize(
    "path",
    ["/bff/v1/me", "/bff/v1/object-types/equipment", "/bff/v1/object-types/equipment/objects"],
)
def test_json_auth_failure_is_not_a_browser_redirect(signed_client: TestClient, path: str) -> None:
    response = signed_client.get(path)
    assert response.status_code == 401
    assert "location" not in response.headers
    assert set(response.json()) >= {"code", "message", "trace_id"}


def test_local_logout_contract_is_empty_and_idempotent(signed_client: TestClient) -> None:
    response = signed_client.post("/bff/v1/auth/logout")
    assert response.status_code == 204
    assert response.content == b""
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
