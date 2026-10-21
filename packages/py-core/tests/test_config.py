from pathlib import Path

import pytest
from pydantic import ValidationError

from contexture_core.config import CoreSettings, load_settings


def test_missing_tenant_id_fails_startup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CTX_TENANT_ID", raising=False)
    with pytest.raises(ValidationError):
        load_settings(secrets_dir=tmp_path)


def test_loads_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CTX_KEYCLOAK_URL", "https://sso.example")
    monkeypatch.setenv("CTX_KEYCLOAK_REALM", "digital-workforce")
    settings = load_settings(secrets_dir=tmp_path)
    assert settings.tenant_id == "local"
    assert settings.issuer == "https://sso.example/realms/digital-workforce"
    assert settings.jwks_url == f"{settings.issuer}/protocol/openid-connect/certs"
    assert settings.token_url == f"{settings.issuer}/protocol/openid-connect/token"


def test_loads_secrets_from_mounted_files(tmp_path: Path) -> None:
    (tmp_path / "ctx_client_secret").write_text("s3cret\n")
    settings = load_settings(secrets_dir=tmp_path)
    assert settings.client_secret.get_secret_value() == "s3cret"


def test_environment_overrides_mounted_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "ctx_client_secret").write_text("from-file")
    monkeypatch.setenv("CTX_CLIENT_SECRET", "from-env")
    assert load_settings(secrets_dir=tmp_path).client_secret.get_secret_value() == "from-env"


def test_services_extend_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class BffSettings(CoreSettings):
        session_ttl_seconds: int = 3600

    monkeypatch.setenv("CTX_SESSION_TTL_SECONDS", "60")
    settings = load_settings(BffSettings, secrets_dir=tmp_path)
    assert settings.session_ttl_seconds == 60
    assert settings.tenant_id == "local"
