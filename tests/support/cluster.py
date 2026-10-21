"""端到端测试访问本地集群的辅助代码：以测试用户登录（经 contexture-bff）、令牌交换、端口转发。

需要 make up、make seed 已完成，凭证来自 .env.local。
"""

import base64
import contextlib
import json
import os
import re
import ssl
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
NS = "contexture"
APP_URL = "http://localhost:8080"
TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"


def env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (REPO_ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    return values


def trusted_ca() -> ssl.SSLContext:
    """本机 Keycloak 经 Paperclip 的 Caddy，证书由 Caddy 本地 CA 签发。"""
    pem = subprocess.run(
        [
            "docker",
            "exec",
            "paperclip-caddy-1",
            "cat",
            "/data/caddy/pki/authorities/local/root.crt",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return ssl.create_default_context(cadata=pem)


def issuer() -> str:
    e = env()
    return f"{e['KEYCLOAK_URL']}/realms/{e['KEYCLOAK_REALM']}"


def claims(token: str) -> dict[str, Any]:
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(part)))


def _action(html: str) -> str:
    match = re.search(r'action="([^"]+)"', html)
    assert match, "找不到 Keycloak 登录表单"
    return match.group(1).replace("&amp;", "&")


def keycloak_login(authorize_url: str, username: str, password: str) -> str:
    """在 Keycloak 登录页完成登录（兼容两步登录），返回带 code 的回调地址。"""
    with httpx.Client(verify=trusted_ca(), follow_redirects=False) as kc:
        page = kc.get(authorize_url)
        resp = kc.post(_action(page.text), data={"username": username, "password": password})
        if resp.status_code == 200:  # 两步登录：先用户名，再密码
            resp = kc.post(_action(resp.text), data={"password": password})
        assert resp.status_code == 302, resp.text[:300]
        return resp.headers["location"]


def browser_session(username: str, password: str) -> httpx.Client:
    """像浏览器一样经 bff 登录，返回带会话 Cookie 的客户端（base_url = 织境入口）。"""
    app = httpx.Client(base_url=APP_URL, follow_redirects=False, timeout=30)
    resp = app.get("/bff/v1/auth/login", params={"return_to": "/"})
    callback = keycloak_login(resp.headers["location"], username, password)
    done = app.get(callback.removeprefix(APP_URL))
    assert done.status_code == 302, done.text
    return app


def user_token(username: str, password: str) -> str:
    """以 contexture-bff 走授权码登录，返回登录令牌（受众含 contexture-bff 与 AI 网关）。"""
    e = env()
    redirect = f"{e.get('CTX_PUBLIC_URL', APP_URL)}/bff/v1/auth/callback"
    verifier = base64.urlsafe_b64encode(os.urandom(48)).rstrip(b"=").decode()
    import hashlib

    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    query = httpx.QueryParams(
        client_id="contexture-bff",
        response_type="code",
        scope="openid",
        redirect_uri=redirect,
        code_challenge=challenge.decode(),
        code_challenge_method="S256",
    )
    callback = keycloak_login(
        f"{issuer()}/protocol/openid-connect/auth?{query}", username, password
    )
    code = parse_qs(urlparse(callback).query)["code"][0]
    resp = httpx.post(
        f"{issuer()}/protocol/openid-connect/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect,
            "code_verifier": verifier,
            "client_id": "contexture-bff",
            "client_secret": e["CONTEXTURE_BFF_CLIENT_SECRET"],
        },
        verify=trusted_ca(),
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def exchange(subject_token: str, audience: str = "contexture-ai-gateway") -> str:
    e = env()
    resp = httpx.post(
        f"{issuer()}/protocol/openid-connect/token",
        data={
            "grant_type": TOKEN_EXCHANGE,
            "client_id": "contexture-bff",
            "client_secret": e["CONTEXTURE_BFF_CLIENT_SECRET"],
            "subject_token": subject_token,
            "subject_token_type": ACCESS_TOKEN,
            "audience": audience,
        },
        verify=trusted_ca(),
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


@contextlib.contextmanager
def port_forward(target: str, remote_port: int) -> Iterator[str]:
    """kubectl port-forward 到本机随机端口，返回 http://127.0.0.1:<端口>。"""
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        local = s.getsockname()[1]
    proc = subprocess.Popen(
        ["kubectl", "-n", NS, "port-forward", target, f"{local}:{remote_port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{local}"
    try:
        for _ in range(100):  # 端口能建立 TCP 连接即视为就绪（适用于 HTTP 与 MySQL 协议）
            try:
                with socket.create_connection(("127.0.0.1", local), timeout=1):
                    break
            except OSError:
                time.sleep(0.2)
        time.sleep(0.5)
        yield url
    finally:
        proc.terminate()


def logs(target: str, since: str = "2m") -> list[str]:
    out = subprocess.run(
        ["kubectl", "-n", NS, "logs", target, f"--since={since}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.splitlines()


def tmp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="ctx-e2e-"))
