"""集成测试：真实 Keycloak 26.8.0 + PostgreSQL 17，走完登录 → 会话 → /me → 登出。"""

from collections.abc import Iterator
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from support.keycloak import Admin, import_config, keycloak, submit_login
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from contexture_bff.main import create_app
from contexture_bff.migrate import upgrade
from contexture_bff.settings import BffSettings

pytestmark = pytest.mark.integration

PUBLIC_URL = "http://testserver"


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
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
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        yield f"postgresql+asyncpg://bff:bff@{host}:{port}/bff"


@pytest.fixture(scope="module")
def settings(postgres_url: str) -> Iterator[BffSettings]:
    with keycloak() as env:
        Admin(env.base_url).create_realm()
        import_config(env, PUBLIC_URL)
        settings = BffSettings(
            tenant_id="local",
            public_url=PUBLIC_URL,
            keycloak_url=env.base_url,
            keycloak_realm="digital-workforce",
            client_secret="test-bff-secret",  # type: ignore[arg-type]
            database_url=postgres_url,
        )
        upgrade(settings.database_url)
        yield settings


def browser_login(client: TestClient, username: str) -> None:
    resp = client.get("/bff/v1/auth/login", params={"return_to": "/objects"})
    assert resp.status_code == 302
    callback = submit_login(resp.headers["location"], username, username)
    parsed = urlparse(callback)
    resp = client.get(f"{parsed.path}?{parsed.query}")
    assert resp.status_code == 302, resp.text
    assert resp.headers["location"] == "/objects"


def test_login_session_me_logout(settings: BffSettings) -> None:
    with TestClient(create_app(settings), follow_redirects=False) as client:
        browser_login(client, "user1")

        # 浏览器侧只有会话 Cookie，没有令牌
        assert set(client.cookies.keys()) == {"ctx_session"}

        me = client.get("/bff/v1/me")
        assert me.status_code == 200, me.text
        body = me.json()
        assert body["tenant_id"] == "local"
        assert body["user_id"]
        assert "business-user" in body["roles"]

        assert client.post("/bff/v1/auth/logout").status_code == 204
        assert client.get("/bff/v1/me").status_code == 401


def test_session_survives_app_restart(settings: BffSettings) -> None:
    """会话存在 PostgreSQL：bff 重启（新实例）后会话仍有效。"""
    with TestClient(create_app(settings), follow_redirects=False) as first:
        browser_login(first, "engineer1")
        cookie = first.cookies["ctx_session"]
    with TestClient(create_app(settings), follow_redirects=False) as second:
        second.cookies.set("ctx_session", cookie)
        me = second.get("/bff/v1/me")
        assert me.status_code == 200
        assert "ai-engineer" in me.json()["roles"]
