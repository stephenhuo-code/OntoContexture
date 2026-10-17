"""测试用 Keycloak：Testcontainers 启动 26.8.0，并用 keycloak-config-cli 增量导入织境配置。

Keycloak 配置测试与 bff 集成测试共用。
"""

import base64
import hashlib
import json
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import httpx
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.8.0"
CONFIG_CLI_IMAGE = "adorsys/keycloak-config-cli:6.5.1-26.5.5"
COMPONENT_DIR = Path(__file__).resolve().parents[2] / "deploy" / "components" / "keycloak"
CONFIG_DIR = COMPONENT_DIR / "config"
REALM = "digital-workforce"
BFF_SECRET = "test-bff-secret"


@dataclass
class KeycloakEnv:
    base_url: str
    network: Network

    @property
    def issuer(self) -> str:
        return f"{self.base_url}/realms/{REALM}"

    @property
    def oidc(self) -> str:
        return f"{self.issuer}/protocol/openid-connect"


def jwt_claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(payload)))


def audiences(claims: dict[str, Any]) -> list[str]:
    aud: object = claims["aud"]
    if isinstance(aud, list):
        return [str(a) for a in cast(list[object], aud)]
    return [str(aud)]


class Admin:
    def __init__(self, base_url: str) -> None:
        token = httpx.post(
            f"{base_url}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "admin",
                "password": "admin",
            },
        ).json()["access_token"]
        self.http = httpx.Client(
            base_url=f"{base_url}/admin/realms", headers={"Authorization": f"Bearer {token}"}
        )

    def create_realm(self) -> None:
        resp = self.http.post("", json={"realm": REALM, "enabled": True})
        assert resp.status_code == 201, resp.text

    def client(self, client_id: str) -> dict[str, Any]:
        found = self.http.get(f"/{REALM}/clients", params={"clientId": client_id}).json()
        assert found, f"客户端 {client_id} 不存在"
        return cast(dict[str, Any], found[0])

    def user_id(self, username: str) -> str:
        users = self.http.get(f"/{REALM}/users", params={"username": username, "exact": True})
        return str(users.json()[0]["id"])


@contextmanager
def keycloak() -> Iterator[KeycloakEnv]:
    with Network() as network:
        container = (
            DockerContainer(KEYCLOAK_IMAGE)
            .with_network(network)
            .with_network_aliases("keycloak")
            .with_env("KC_BOOTSTRAP_ADMIN_USERNAME", "admin")
            .with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", "admin")
            .with_exposed_ports(8080)
            .with_command("start-dev")
            .waiting_for(LogMessageWaitStrategy("Listening on:").with_startup_timeout(180))
        )
        with container:
            host = container.get_container_host_ip()
            yield KeycloakEnv(f"http://{host}:{container.get_exposed_port(8080)}", network)


def import_env() -> dict[str, str]:
    """部署与测试共用的导入参数（deploy/components/keycloak/import.env）。"""
    env: dict[str, str] = {}
    for raw in (COMPONENT_DIR / "import.env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key] = value
    return env


def import_config(env: KeycloakEnv, public_url: str) -> None:
    """以 keycloak-config-cli 增量导入织境配置与测试用户。"""
    cli = (
        DockerContainer(CONFIG_CLI_IMAGE)
        .with_network(env.network)
        .with_volume_mapping(str(CONFIG_DIR), "/config", "ro")
        .with_env("KEYCLOAK_URL", "http://keycloak:8080")
        .with_env("KEYCLOAK_USER", "admin")
        .with_env("KEYCLOAK_PASSWORD", "admin")
        .with_env("IMPORT_FILES_LOCATIONS", "/config/*.yaml")
        .with_env("CONTEXTURE_BFF_CLIENT_SECRET", BFF_SECRET)
        .with_env("CTX_PUBLIC_URL", public_url)
    )
    for key, value in import_env().items():
        cli = cli.with_env(key, value)
    with cli:
        result = cli.get_wrapped_container().wait(timeout=180)
        logs = cli.get_wrapped_container().logs().decode()
    assert result["StatusCode"] == 0, logs


def submit_login(authorize_url: str, username: str, password: str) -> str:
    """在 Keycloak 登录页提交用户名与密码，返回带 code 的回调地址。"""
    with httpx.Client(follow_redirects=False) as http:
        page = http.get(authorize_url)
        assert page.status_code == 200, page.text
        # Keycloak 的会话 Cookie 带 Secure 标记，测试走 http，需手动回传
        cookies = "; ".join(c.split(";", 1)[0] for c in page.headers.get_list("set-cookie"))
        action = re.search(r'action="([^"]+)"', page.text)
        assert action, "找不到登录表单"
        resp = http.post(
            action.group(1).replace("&amp;", "&"),
            data={"username": username, "password": password},
            headers={"Cookie": cookies},
        )
        assert resp.status_code == 302, resp.text
        return resp.headers["location"]


def login(env: KeycloakEnv, username: str, password: str, redirect_uri: str) -> dict[str, Any]:
    """以 contexture-bff 走授权码 + PKCE 登录，返回令牌响应。"""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    query = httpx.QueryParams(
        client_id="contexture-bff",
        response_type="code",
        scope="openid",
        redirect_uri=redirect_uri,
        code_challenge=challenge,
        code_challenge_method="S256",
    )
    callback = submit_login(f"{env.oidc}/auth?{query}", username, password)
    code = parse_qs(urlparse(callback).query)["code"][0]
    tokens = httpx.post(
        f"{env.oidc}/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "client_id": "contexture-bff",
            "client_secret": BFF_SECRET,
        },
    )
    assert tokens.status_code == 200, tokens.text
    return cast(dict[str, Any], tokens.json())
