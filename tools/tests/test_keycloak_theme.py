"""主题资源必须可重复打包，并能发现部署副本过期。"""

from pathlib import Path

import pytest
import yaml

from tools.keycloak_theme import theme_files, values_text, write_theme


def test_cli_detects_stale_values_and_bundles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools import keycloak_theme

    values = tmp_path / "theme.yaml"
    monkeypatch.setattr(keycloak_theme, "VALUES", values)
    assert keycloak_theme.main(["--check"]) == 1
    monkeypatch.setattr(keycloak_theme, "ROOT", tmp_path)
    monkeypatch.setattr(keycloak_theme, "values_text", lambda: "theme: {}\n")
    assert keycloak_theme.main(["--write-values"]) == 0
    assert keycloak_theme.main(["--check"]) == 0
    values.write_text("stale")
    assert keycloak_theme.main(["--check"]) == 1
    monkeypatch.setattr(
        keycloak_theme, "theme_files", lambda: {"theme.properties": "parent=keycloak"}
    )
    assert keycloak_theme.main(["--bundle", str(tmp_path / "bundle")]) == 0


def test_theme_bundle_contains_shared_resources_and_no_prototype(tmp_path: Path) -> None:
    files = theme_files()
    assert "resources/identity/identity.css" in files
    assert "resources/identity/hero.svg" in files
    assert "resources/js/contexture.js" in files
    assert "parent=keycloak" in files["theme.properties"]
    assert not any("prototype" in path for path in files)
    target = write_theme(tmp_path)
    assert (target / "login/resources/identity/identity.css").read_text() == files[
        "resources/identity/identity.css"
    ]


def test_generated_values_preserve_all_bytes() -> None:
    files = theme_files()
    assert yaml.safe_load(values_text())["theme"]["files"] == files


def test_theme_only_augments_official_form() -> None:
    files = theme_files()
    assert "login.ftl" not in files and "template.ftl" not in files
    assert "fetch(" not in files["resources/js/contexture.js"]
