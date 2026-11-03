"""集成测试：真实 Keycloak 26.8.0 + PostgreSQL 17，走完登录 → 会话 → /me → 登出。"""

import time
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from support.keycloak import Admin, KeycloakEnv, import_config, keycloak, submit_login
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from contexture_bff.main import create_app
from contexture_bff.migrate import upgrade
from contexture_bff.settings import BffSettings

pytestmark = pytest.mark.integration

PUBLIC_URL = "http://testserver"


@pytest.fixture(scope="module")
def postgres_container() -> Iterator[DockerContainer]:
    container = (
        DockerContainer("postgres:17")
        .with_env("POSTGRES_USER", "bff")
        .with_env("POSTGRES_PASSWORD", "bff")
        .with_env("POSTGRES_DB", "bff")
        .with_exposed_ports(5432)
        .waiting_for(
            LogMessageWaitStrategy(
                "database system is ready to accept connections", times=2
            ).with_startup_timeout(60)
        )
    )
    with container:
        yield container


@pytest.fixture(scope="module")
def postgres_url(postgres_container: DockerContainer) -> str:
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://bff:bff@{host}:{port}/bff"


@pytest.fixture(scope="module")
def identity_env() -> Iterator[KeycloakEnv]:
    with keycloak() as env:
        admin = Admin(env.base_url)
        admin.create_realm()
        import_config(env, PUBLIC_URL)
        for username, roles in [("norole1", []), ("mixed1", ["business-user", "ai-engineer"])]:
            response = admin.http.post(
                "/digital-workforce/users",
                json={
                    "username": username,
                    "enabled": True,
                    "firstName": "Test",
                    "lastName": username,
                    "email": f"{username}@example.invalid",
                    "emailVerified": True,
                    "credentials": [{"type": "password", "value": username, "temporary": False}],
                },
            )
            assert response.status_code == 201
            user_id = admin.user_id(username)
            if roles:
                mapping = [
                    admin.http.get(f"/digital-workforce/roles/{role}").json() for role in roles
                ]
                assert (
                    admin.http.post(
                        f"/digital-workforce/users/{user_id}/role-mappings/realm", json=mapping
                    ).status_code
                    == 204
                )
        yield env


@pytest.fixture(scope="module")
def settings(postgres_url: str, identity_env: KeycloakEnv) -> BffSettings:
    settings = BffSettings(
        tenant_id="local",
        public_url=PUBLIC_URL,
        keycloak_url=identity_env.base_url,
        keycloak_realm="digital-workforce",
        client_secret=SecretStr("test-bff-secret"),
        database_url=postgres_url,
    )  # type: ignore[arg-type]
    upgrade(settings.database_url)
    return settings


def browser_login(
    client: TestClient, username: str, identity_browser: httpx.Client | None = None
) -> None:
    resp = client.get("/bff/v1/auth/login", params={"return_to": "/objects"})
    assert resp.status_code == 302
    callback = submit_login(resp.headers["location"], username, username, browser=identity_browser)
    parsed = urlparse(callback)
    resp = client.get(f"{parsed.path}?{parsed.query}")
    assert resp.status_code == 302, resp.text
    assert resp.headers["location"] == "/objects"


def test_login_session_me_logout(settings: BffSettings) -> None:
    with TestClient(
        create_app(settings), follow_redirects=False, raise_server_exceptions=False
    ) as client:
        browser_login(client, "engineer1")

        # 浏览器侧只有会话 Cookie，没有令牌
        assert set(client.cookies.keys()) == {"ctx_session"}

        me = client.get("/bff/v1/me")
        assert me.status_code == 200, me.text
        body = me.json()
        assert body["tenant_id"] == "local"
        assert body["user_id"]
        assert "ai-engineer" in body["roles"]

        assert client.post("/bff/v1/auth/logout").status_code == 204
        assert client.get("/bff/v1/me").status_code == 401


def test_session_survives_app_restart(settings: BffSettings) -> None:
    """会话存在 PostgreSQL：bff 重启（新实例）后会话仍有效。"""
    with TestClient(
        create_app(settings), follow_redirects=False, raise_server_exceptions=False
    ) as first:
        browser_login(first, "engineer1")
        cookie = first.cookies["ctx_session"]
    with TestClient(
        create_app(settings), follow_redirects=False, raise_server_exceptions=False
    ) as second:
        second.cookies.set("ctx_session", cookie)
        me = second.get("/bff/v1/me")
        assert me.status_code == 200
        assert "ai-engineer" in me.json()["roles"]


@pytest.mark.parametrize(
    "username,allowed",
    [("admin1", True), ("engineer1", True), ("user1", False), ("norole1", False), ("mixed1", True)],
)
def test_real_cookie_and_bearer_role_matrix(
    settings: BffSettings, username: str, allowed: bool
) -> None:
    with TestClient(
        create_app(settings), follow_redirects=False, raise_server_exceptions=False
    ) as client:
        browser_login(client, username)
        response = client.get("/bff/v1/me")
        assert response.status_code == (200 if allowed else 403)
        assert client.portal is not None
        record = client.portal.call(
            cast(FastAPI, client.app).state.services.sessions.get_session,
            client.cookies["ctx_session"],
        )
        assert record is not None
        client.cookies.clear()
        direct = client.get(
            "/bff/v1/me", headers={"Authorization": f"Bearer {record.access_token}"}
        )
        assert direct.status_code == (200 if allowed else 403)


def test_local_logout_keeps_idp_refresh_usable(settings: BffSettings) -> None:
    with TestClient(
        create_app(settings), follow_redirects=False, raise_server_exceptions=False
    ) as client:
        browser_login(client, "engineer1")
        cookie = client.cookies["ctx_session"]
        assert client.portal is not None
        svc = cast(FastAPI, client.app).state.services
        record = client.portal.call(svc.sessions.get_session, cookie)
        assert record is not None
        response = client.post("/bff/v1/auth/logout")
        assert response.status_code == 204
        assert "HttpOnly" in response.headers["set-cookie"]
        client.cookies.set("ctx_session", cookie)
        assert client.get("/bff/v1/me").status_code == 401
        refreshed = client.portal.call(svc.oidc.refresh, record.refresh_token)
        assert bool(refreshed.access_token)


def test_relogin_with_live_sso_requires_credentials(settings: BffSettings) -> None:
    with (
        TestClient(create_app(settings), follow_redirects=False) as client,
        httpx.Client(follow_redirects=False) as identity_browser,
    ):
        browser_login(client, "engineer1", identity_browser)
        assert client.get("/bff/v1/me").status_code == 200
        assert client.post("/bff/v1/auth/logout").status_code == 204
        assert client.get("/bff/v1/me").status_code == 401

        # 先以同一 Cookie 证明企业 SSO 确实仍有效；探测授权不消费 BFF callback。
        probe = client.get("/bff/v1/auth/login")
        parsed = urlparse(probe.headers["location"])
        query = [(key, value) for key, value in parse_qsl(parsed.query) if key != "prompt"]
        for cookie in identity_browser.cookies.jar:
            cookie.secure = False
        silent = identity_browser.get(parsed._replace(query=urlencode(query)).geturl())
        assert silent.status_code == 302
        assert "code=" in silent.headers["location"]

        # 正常 BFF 入口应重新显示认证表单，不能因 SSO 有效直接重建织境会话。
        fresh = client.get("/bff/v1/auth/login", params={"return_to": "/assets?q=reauth"})
        for cookie in identity_browser.cookies.jar:
            cookie.secure = False
        form = identity_browser.get(fresh.headers["location"])
        assert form.status_code == 200
        assert 'id="password"' in form.text
        assert client.get("/bff/v1/me").status_code == 401
        callback = submit_login(
            fresh.headers["location"], "engineer1", "engineer1", browser=identity_browser
        )
        returned = urlparse(callback)
        done = client.get(f"{returned.path}?{returned.query}")
        assert done.status_code == 302
        assert done.headers["location"] == "/assets?q=reauth"
        assert client.get("/bff/v1/me").status_code == 200


def test_real_refresh_preserves_lifetime_and_revocation_ends_session(settings: BffSettings) -> None:
    with TestClient(
        create_app(settings), follow_redirects=False, raise_server_exceptions=False
    ) as client:
        browser_login(client, "engineer1")
        assert client.portal is not None
        svc = cast(FastAPI, client.app).state.services
        cookie = client.cookies["ctx_session"]
        record = client.portal.call(svc.sessions.get_session, cookie)
        assert record is not None
        lifetime = record.expires_at
        client.portal.call(
            svc.sessions.update_session,
            cookie,
            replace(record, access_expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        )
        assert client.get("/bff/v1/me").status_code == 200
        updated = client.portal.call(svc.sessions.get_session, cookie)
        assert updated is not None
        assert updated.expires_at == lifetime
        admin = Admin(settings.keycloak_url)
        assert (
            admin.http.post(
                f"/digital-workforce/users/{admin.user_id('engineer1')}/logout"
            ).status_code
            == 204
        )
        client.portal.call(
            svc.sessions.update_session,
            cookie,
            replace(updated, access_expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        )
        assert client.get("/bff/v1/me").status_code == 401
        assert client.portal.call(svc.sessions.get_session, cookie) is None


def wait_identity(url: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise AssertionError("isolated identity service did not restart")


@pytest.mark.parametrize("stage", ["refresh", "jwks"])
def test_real_identity_outage_is_recoverable(
    settings: BffSettings, identity_env: KeycloakEnv, stage: str
) -> None:
    with TestClient(
        create_app(settings), follow_redirects=False, raise_server_exceptions=False
    ) as client:
        browser_login(client, "engineer1")
        assert client.portal is not None and identity_env.container is not None
        svc = cast(FastAPI, client.app).state.services
        cookie = client.cookies["ctx_session"]
        record = client.portal.call(svc.sessions.get_session, cookie)
        assert record is not None
        if stage == "refresh":
            client.portal.call(
                svc.sessions.update_session,
                cookie,
                replace(record, access_expires_at=datetime.now(UTC) - timedelta(seconds=1)),
            )
        else:
            svc.authenticator.verifier._keys.clear()
        container = identity_env.container.get_wrapped_container()
        container.pause()
        try:
            assert client.get("/bff/v1/me").status_code == 502
            assert client.portal.call(svc.sessions.get_session, cookie) is not None
        finally:
            container.unpause()
            wait_identity(settings.issuer + "/.well-known/openid-configuration")
        assert client.get("/bff/v1/me").status_code == 200


def test_real_database_outage_is_500(
    settings: BffSettings, postgres_container: DockerContainer
) -> None:
    with TestClient(
        create_app(settings), follow_redirects=False, raise_server_exceptions=False
    ) as client:
        browser_login(client, "engineer1")
        container = postgres_container.get_wrapped_container()
        container.stop(timeout=5)
        try:
            response = client.get("/bff/v1/me")
            assert response.status_code == 500
            assert response.json()["code"] == "internal.error"
        finally:
            container.start()
