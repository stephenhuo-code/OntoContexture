"""登录、回调、会话、登出（BFF 模式：令牌只在 bff，浏览器只持有会话 Cookie）。"""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import httpx2
import pytest
from bff_fakes import FakeSessions, TokenOidc
from fastapi.testclient import TestClient
from support.jwt import ISSUER, JWKS_URL, LocalIssuer

from contexture_bff.adapters.keycloak import TokenSet
from contexture_bff.main import Services, create_app
from contexture_bff.settings import BffSettings
from contexture_core.auth import Authenticator, TokenVerifier


@pytest.fixture
def issuer() -> LocalIssuer:
    return LocalIssuer()


@pytest.fixture
def oidc(issuer: LocalIssuer) -> TokenOidc:
    return TokenOidc(issuer)


@pytest.fixture
def sessions() -> FakeSessions:
    return FakeSessions()


@pytest.fixture
def client(issuer: LocalIssuer, oidc: TokenOidc, sessions: FakeSessions) -> TestClient:
    settings = BffSettings(tenant_id="local", public_url="http://testserver")
    verifier = TokenVerifier(
        jwks_url=JWKS_URL,
        issuer=ISSUER,
        audience="contexture-bff",
        http=httpx.Client(transport=issuer.transport()),
    )
    services = Services(
        sessions=sessions,
        oidc=oidc,
        object_types=None,
        object_data=None,
        authenticator=Authenticator(tenant_id="local", verifier=verifier),
    )
    return TestClient(
        create_app(settings, services=services),
        follow_redirects=False,
        raise_server_exceptions=False,
    )


def login(client: TestClient, return_to: str | None = None) -> httpx2.Response:
    params = {"return_to": return_to} if return_to else {}
    resp = client.get("/bff/v1/auth/login", params=params)
    assert resp.status_code == 302
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
    return client.get("/bff/v1/auth/callback", params={"code": "c1", "state": state})


def test_login_redirects_to_keycloak_with_pkce(client: TestClient) -> None:
    resp = client.get("/bff/v1/auth/login")
    assert resp.status_code == 302
    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query["state"][0]
    assert query["code_challenge"][0]
    assert "set-cookie" not in resp.headers


def test_callback_creates_session_cookie_only(client: TestClient, sessions: FakeSessions) -> None:
    resp = login(client, "/objects")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/objects"
    cookies = resp.headers.get_list("set-cookie")
    assert len(cookies) == 1
    cookie = cookies[0]
    assert cookie.startswith("ctx_session=")
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    # 浏览器拿到的只是会话 ID，不是令牌
    session_id = cookie.split(";")[0].split("=", 1)[1]
    assert session_id in sessions.sessions
    assert "." not in session_id


def test_me_with_session(client: TestClient) -> None:
    login(client)
    resp = client.get("/bff/v1/me")
    assert resp.status_code == 200
    assert resp.json() == {
        "tenant_id": "local",
        "user_id": "user-1-id",
        "display_name": "User One",
        "roles": ["ai-engineer", "offline_access"],
    }


def test_me_with_bearer(client: TestClient, issuer: LocalIssuer) -> None:
    resp = client.get(
        "/bff/v1/me",
        headers={
            "Authorization": f"Bearer {issuer.token(realm_access={'roles': ['ai-engineer']})}"
        },
    )
    assert resp.status_code == 200


def test_bearer_with_wrong_audience_is_403(client: TestClient, issuer: LocalIssuer) -> None:
    token = issuer.token(aud="contexture-ai-gateway")
    resp = client.get("/bff/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "auth.invalid_audience"


def test_no_session_is_401(client: TestClient) -> None:
    resp = client.get("/bff/v1/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "auth.invalid_token"


def test_unknown_state_is_rejected(client: TestClient) -> None:
    resp = client.get("/bff/v1/auth/callback", params={"code": "c", "state": "forged"})
    assert resp.status_code == 303
    assert "reason=invalid_response" in resp.headers["location"]


def test_state_is_single_use(client: TestClient) -> None:
    resp = client.get("/bff/v1/auth/login")
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
    assert (
        client.get("/bff/v1/auth/callback", params={"code": "c", "state": state}).status_code == 302
    )
    again = client.get("/bff/v1/auth/callback", params={"code": "c", "state": state})
    assert again.status_code == 303


@pytest.mark.parametrize("target", ["https://evil.example/x", "//evil.example", "javascript:x"])
def test_open_redirect_is_blocked(client: TestClient, target: str) -> None:
    resp = login(client, target)
    assert resp.headers["location"] == "/home"


def test_logout_clears_session(client: TestClient, oidc: TokenOidc, sessions: FakeSessions) -> None:
    login(client)
    resp = client.post("/bff/v1/auth/logout")
    assert resp.status_code == 204
    assert "ctx_session=" in resp.headers["set-cookie"]
    assert sessions.sessions == {}
    assert oidc.logged_out == []
    assert client.get("/bff/v1/me").status_code == 401


def test_logout_without_session_is_204(client: TestClient) -> None:
    assert client.post("/bff/v1/auth/logout").status_code == 204


def test_expired_access_token_is_refreshed(
    client: TestClient, oidc: TokenOidc, sessions: FakeSessions
) -> None:
    login(client)
    ((session_id, record),) = sessions.sessions.items()
    record.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/bff/v1/me").status_code == 200
    assert oidc.refreshed == ["refresh-1"]
    assert sessions.sessions[session_id].refresh_token == "refresh-2"


def test_explicit_invalid_refresh_ends_session(
    client: TestClient, oidc: TokenOidc, sessions: FakeSessions
) -> None:
    login(client)
    ((_, record),) = sessions.sessions.items()
    record.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    async def broken(refresh_token: str) -> TokenSet:
        from contexture_core.errors import InvalidToken

        raise InvalidToken()

    oidc.refresh = broken  # type: ignore[method-assign]
    assert client.get("/bff/v1/me").status_code == 401
    assert sessions.sessions == {}


@pytest.mark.parametrize(
    ("name", "username", "expected"),
    [
        ("张三", "zhangsan", "张三"),
        (None, "zhangsan", "zhangsan"),
        (None, None, "user-1-id"),
        ("", "", "user-1-id"),
    ],
)
def test_me_display_name_fallback(
    client: TestClient, issuer: LocalIssuer, name: str | None, username: str | None, expected: str
) -> None:
    token = issuer.token(
        name=name, preferred_username=username, realm_access={"roles": ["ai-engineer"]}
    )
    response = client.get("/bff/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["display_name"] == expected


@pytest.mark.parametrize(
    "target,expected",
    [
        ("/assets?type=table", "/assets?type=table"),
        ("https://evil.example/x", "/home"),
        ("//evil.example", "/home"),
        ("/\\evil", "/home"),
        ("/%5cevil", "/home"),
        ("/%2f%2fevil", "/home"),
        ("/home\r\nX-Bad: yes", "/home"),
        ("/auth/error?reason=x", "/home"),
    ],
)
def test_safe_login_destination(client: TestClient, target: str, expected: str) -> None:
    assert login(client, target).headers["location"] == expected


@pytest.mark.parametrize(
    "params,reason",
    [
        ({"error": "access_denied"}, "cancelled"),
        ({"error": "server_error"}, "invalid_response"),
        ({}, "invalid_response"),
        ({"code": "c", "error": "access_denied"}, "invalid_response"),
        ({"code": ""}, "invalid_response"),
    ],
)
def test_callback_failure_consumes_state_without_code_exchange(
    client: TestClient, oidc: TokenOidc, sessions: FakeSessions, params: dict[str, str], reason: str
) -> None:
    client.get("/bff/v1/auth/login", params={"return_to": "/assets?q=safe"})
    state = next(iter(sessions.logins))
    response = client.get(
        "/bff/v1/auth/callback", params={"state": state, **params, "error_description": "PRIVATE"}
    )
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["reason"] == [reason]
    assert query["return_to"] == ["/assets?q=safe"]
    assert state not in sessions.logins
    assert not oidc.exchanged
    assert not sessions.sessions
    assert "PRIVATE" not in response.headers["location"]


@pytest.mark.parametrize("query", ["code=a&code=b", "code=a&error=x", "code=a&state=other"])
def test_duplicate_and_conflicting_callback_params_are_rejected(
    client: TestClient, oidc: TokenOidc, sessions: FakeSessions, query: str
) -> None:
    client.get("/bff/v1/auth/login")
    state = next(iter(sessions.logins))
    response = client.get(f"/bff/v1/auth/callback?state={state}&{query}")
    assert response.status_code == 303
    assert not oidc.exchanged


def test_expired_state_is_rejected_without_exchanging(
    client: TestClient, oidc: TokenOidc, sessions: FakeSessions
) -> None:
    client.get("/bff/v1/auth/login")
    state = next(iter(sessions.logins))
    sessions.logins[state].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    response = client.get("/bff/v1/auth/callback", params={"state": state, "code": "private-code"})
    assert response.status_code == 303
    assert not oidc.exchanged


def test_local_logout_does_not_call_idp(client: TestClient, oidc: TokenOidc) -> None:
    login(client)
    assert client.post("/bff/v1/auth/logout").status_code == 204
    assert oidc.logged_out == []


def test_logout_storage_failure_is_not_success(client: TestClient, sessions: FakeSessions) -> None:
    login(client)

    async def broken(session_id: str) -> None:
        raise RuntimeError("private storage details")

    sessions.delete_session = broken  # type: ignore[method-assign]
    response = client.post("/bff/v1/auth/logout")
    assert response.status_code == 500
    assert "private storage details" not in response.text
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("status", [502, 500])
def test_refresh_fault_preserves_record_and_lifetime(
    client: TestClient, oidc: TokenOidc, sessions: FakeSessions, status: int
) -> None:
    from contexture_core.errors import UpstreamUnavailable

    login(client)
    session_id, record = next(iter(sessions.sessions.items()))
    expires_at = record.expires_at
    record.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    async def broken(refresh_token: str) -> TokenSet:
        if status == 502:
            raise UpstreamUnavailable()
        raise RuntimeError("private")

    oidc.refresh = broken  # type: ignore[method-assign]
    response = client.get("/bff/v1/me")
    assert response.status_code == status
    assert sessions.sessions[session_id].expires_at == expires_at
    assert "private" not in response.text


def test_refresh_does_not_extend_session_lifetime(
    client: TestClient, sessions: FakeSessions
) -> None:
    login(client)
    session_id, record = next(iter(sessions.sessions.items()))
    lifetime = record.expires_at
    record.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/bff/v1/me").status_code == 200
    assert sessions.sessions[session_id].expires_at == lifetime


@pytest.mark.parametrize(
    "status,reason", [(401, "invalid_response"), (502, "unavailable"), (500, "internal")]
)
def test_callback_dependency_failure_preserves_existing_session(
    client: TestClient, oidc: TokenOidc, sessions: FakeSessions, status: int, reason: str
) -> None:
    from contexture_core.errors import InvalidToken, UpstreamUnavailable

    login(client)
    cookie = client.cookies["ctx_session"]
    client.get("/bff/v1/auth/login", params={"return_to": "/assets"})
    state = next(iter(sessions.logins))

    async def fail(*, code: str, code_verifier: str) -> TokenSet:
        if status == 401:
            raise InvalidToken()
        if status == 502:
            raise UpstreamUnavailable()
        raise RuntimeError("PRIVATE_TOKEN")

    oidc.exchange_code = fail  # type: ignore[method-assign]
    response = client.get("/bff/v1/auth/callback", params={"code": "secret-code", "state": state})
    assert response.status_code == 303
    assert parse_qs(urlparse(response.headers["location"]).query)["reason"] == [reason]
    assert "PRIVATE_TOKEN" not in response.text + response.headers["location"]
    assert "set-cookie" not in response.headers
    assert cookie in sessions.sessions
    assert client.get("/bff/v1/me").status_code == 200


def test_login_storage_failure_is_recoverable_navigation(
    client: TestClient, sessions: FakeSessions
) -> None:
    async def fail(login_request: object) -> None:
        raise RuntimeError("private database URL")

    sessions.create_login = fail  # type: ignore[method-assign]
    response = client.get("/bff/v1/auth/login", params={"return_to": "//evil"})
    assert response.status_code == 303
    assert "reason=internal" in response.headers["location"]
    assert "private" not in response.headers["location"]
