"""登录、回调、会话、登出（BFF 模式：令牌只在 bff，浏览器只持有会话 Cookie）。"""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import httpx2
import pytest
from bff_fakes import FakeOidc, FakeSessions
from fastapi.testclient import TestClient
from support.jwt import ISSUER, JWKS_URL, LocalIssuer

from contexture_bff.adapters.keycloak import TokenSet
from contexture_bff.main import Services, create_app
from contexture_bff.settings import BffSettings
from contexture_core.auth import Authenticator, TokenVerifier


class TokenOidc(FakeOidc):
    """签发真实令牌的假 Keycloak，使 bff 的验签路径与生产一致。"""

    def __init__(self, issuer: LocalIssuer, expires_in: int = 300) -> None:
        super().__init__()
        self.issuer = issuer
        self.expires_in = expires_in

    def _tokens(self, refresh: str) -> TokenSet:
        return TokenSet(
            access_token=self.issuer.token(),
            refresh_token=refresh,
            id_token="id",
            expires_in=self.expires_in,
            refresh_expires_in=1800,
        )

    async def exchange_code(self, *, code: str, code_verifier: str) -> TokenSet:
        return self._tokens("refresh-1")

    async def refresh(self, refresh_token: str) -> TokenSet:
        self.refreshed.append(refresh_token)
        return self._tokens("refresh-2")


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
    return TestClient(create_app(settings, services=services), follow_redirects=False)


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
        "roles": ["business-user", "offline_access"],
    }


def test_me_with_bearer(client: TestClient, issuer: LocalIssuer) -> None:
    resp = client.get("/bff/v1/me", headers={"Authorization": f"Bearer {issuer.token()}"})
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
    assert resp.status_code == 401
    assert resp.json()["code"] == "auth.invalid_state"


def test_state_is_single_use(client: TestClient) -> None:
    resp = client.get("/bff/v1/auth/login")
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
    assert (
        client.get("/bff/v1/auth/callback", params={"code": "c", "state": state}).status_code == 302
    )
    again = client.get("/bff/v1/auth/callback", params={"code": "c", "state": state})
    assert again.status_code == 401


@pytest.mark.parametrize("target", ["https://evil.example/x", "//evil.example", "javascript:x"])
def test_open_redirect_is_blocked(client: TestClient, target: str) -> None:
    resp = login(client, target)
    assert resp.headers["location"] == "/"


def test_logout_clears_session(client: TestClient, oidc: TokenOidc, sessions: FakeSessions) -> None:
    login(client)
    resp = client.post("/bff/v1/auth/logout")
    assert resp.status_code == 204
    assert "ctx_session=" in resp.headers["set-cookie"]
    assert sessions.sessions == {}
    assert oidc.logged_out == ["refresh-1"]
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


def test_failed_refresh_ends_session(
    client: TestClient, oidc: TokenOidc, sessions: FakeSessions
) -> None:
    login(client)
    ((_, record),) = sessions.sessions.items()
    record.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    async def broken(refresh_token: str) -> TokenSet:
        raise RuntimeError("refresh rejected")

    oidc.refresh = broken  # type: ignore[method-assign]
    assert client.get("/bff/v1/me").status_code == 401
    assert sessions.sessions == {}
