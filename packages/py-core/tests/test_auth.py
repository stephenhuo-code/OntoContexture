import time

import httpx
import httpx2
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from support.jwt import ISSUER, JWKS_URL, LocalIssuer

from contexture_core.auth import Authenticator, RequestContext, TokenVerifier
from contexture_core.errors import install_error_handlers


@pytest.fixture
def issuer() -> LocalIssuer:
    return LocalIssuer()


@pytest.fixture
def verifier(issuer: LocalIssuer) -> TokenVerifier:
    return TokenVerifier(
        jwks_url=JWKS_URL,
        issuer=ISSUER,
        audience="contexture-bff",
        http=httpx.Client(transport=issuer.transport()),
    )


@pytest.fixture
def client(verifier: TokenVerifier) -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    authenticate = Authenticator(tenant_id="local", verifier=verifier)

    @app.get("/whoami")
    def whoami(ctx: RequestContext = Depends(authenticate)) -> dict[str, object]:  # noqa: B008
        return {
            "tenant_id": ctx.tenant_id,
            "user_id": ctx.user_id,
            "agent_id": ctx.agent_id,
            "roles": list(ctx.roles),
            "token_id": ctx.token_id,
            "username": ctx.username,
        }

    return TestClient(app)


def call(client: TestClient, token: str | None) -> httpx2.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/whoami", headers=headers)


def test_valid_token_builds_context(client: TestClient, issuer: LocalIssuer) -> None:
    resp = call(client, issuer.token(jti="jti-1"))
    assert resp.status_code == 200
    assert resp.json() == {
        "tenant_id": "local",
        "user_id": "user-1-id",
        "agent_id": "contexture-bff",
        "roles": ["business-user", "offline_access"],
        "token_id": "jti-1",
        "username": "user1",
    }


def test_tenant_comes_from_config_not_token(client: TestClient, issuer: LocalIssuer) -> None:
    resp = call(client, issuer.token(tenant_id="other"))
    assert resp.json()["tenant_id"] == "local"


def test_missing_token_is_401(client: TestClient) -> None:
    resp = call(client, None)
    assert resp.status_code == 401
    assert resp.json()["code"] == "auth.invalid_token"


def test_bad_signature_is_401(client: TestClient) -> None:
    other = LocalIssuer()  # 同 kid、不同密钥
    resp = call(client, other.token())
    assert resp.status_code == 401
    assert resp.json()["code"] == "auth.invalid_token"


def test_expired_token_is_401(client: TestClient, issuer: LocalIssuer) -> None:
    resp = call(client, issuer.token(exp=int(time.time()) - 120))
    assert resp.status_code == 401
    assert resp.json()["code"] == "auth.invalid_token"


def test_wrong_issuer_is_401(client: TestClient, issuer: LocalIssuer) -> None:
    resp = call(client, issuer.token(iss="https://evil/realms/x"))
    assert resp.status_code == 401


def test_garbage_token_is_401(client: TestClient) -> None:
    assert call(client, "not-a-jwt").status_code == 401


def test_wrong_audience_is_403(client: TestClient, issuer: LocalIssuer) -> None:
    resp = call(client, issuer.token(aud="contexture-ai-gateway"))
    assert resp.status_code == 403
    assert resp.json()["code"] == "auth.invalid_audience"


def test_missing_jti_is_401(client: TestClient, issuer: LocalIssuer) -> None:
    assert call(client, issuer.token(jti=None)).status_code == 401


def test_jwks_is_cached(client: TestClient, issuer: LocalIssuer) -> None:
    for _ in range(3):
        assert call(client, issuer.token()).status_code == 200
    assert issuer.jwks_requests == 1


def test_custom_token_source(verifier: TokenVerifier, issuer: LocalIssuer) -> None:
    """服务可以改变令牌来源（如 bff 从会话取令牌），验签与上下文构建仍由公共库完成。"""
    token = issuer.token()

    async def from_cookie(request: object) -> str | None:
        return token

    app = FastAPI()
    install_error_handlers(app)
    authenticate = Authenticator(tenant_id="local", verifier=verifier, token_source=from_cookie)

    @app.get("/me")
    def me(ctx: RequestContext = Depends(authenticate)) -> str:  # noqa: B008
        return ctx.user_id or ""

    assert TestClient(app).get("/me").json() == "user-1-id"
