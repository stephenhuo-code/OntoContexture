"""030：e2e 辅助代码可在云端工具箱运行（无 .env.local 时读环境变量；公网证书用系统 CA）。"""

import importlib
import ssl
from pathlib import Path

import pytest
from support import cluster


def test_env_falls_back_to_process_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cluster, "REPO_ROOT", tmp_path)  # 没有 .env.local
    monkeypatch.setenv("KEYCLOAK_URL", "https://sso.ctx.example.com")
    monkeypatch.setenv("KEYCLOAK_REALM", "digital-workforce")
    assert cluster.issuer() == "https://sso.ctx.example.com/realms/digital-workforce"


def test_cloud_uses_system_ca_without_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTX_E2E_BASE_URL", "https://ctx.example.com")

    def no_docker(*_: object, **__: object) -> None:
        raise AssertionError("云端不应调用 docker")

    monkeypatch.setattr(cluster.subprocess, "run", no_docker)
    assert isinstance(cluster.trusted_ca(), ssl.SSLContext)


def test_app_url_follows_cloud_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTX_E2E_BASE_URL", "https://ctx.example.com")
    assert importlib.reload(cluster).APP_URL == "https://ctx.example.com"
    monkeypatch.delenv("CTX_E2E_BASE_URL")
    assert importlib.reload(cluster).APP_URL == "http://localhost:8080"
