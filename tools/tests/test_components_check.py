"""组件检查测试：每个组件 MUST 有清单、版本锁定、许可在白名单内、镜像可离线打包、带冒烟测试。"""

from pathlib import Path

import pytest
import yaml

from tools.components_check import check_components

ALLOWLIST = {
    "allowed": ["Apache-2.0", "MIT"],
    "denied": ["AGPL-3.0"],
    "exceptions": [{"license": "CCL-1.0", "component": "openmetadata"}],
}

VALID: dict[str, object] = {
    "name": "keycloak",
    "version": "26.8.0",
    "image": {"source": "official", "refs": ["quay.io/keycloak/keycloak:26.8.0"]},
    "license": "Apache-2.0",
    "customization": "config",
    "upstream": "https://github.com/keycloak/keycloak",
    "owner": "@stephenhuo-code",
    "smoke_test": "tests/smoke.sh",
}


def make_repo(tmp_path: Path, manifest: dict[str, object] | None, name: str = "keycloak") -> Path:
    components = tmp_path / "deploy" / "components"
    comp = components / name
    (comp / "tests").mkdir(parents=True)
    (comp / "tests" / "smoke.sh").write_text("#!/bin/sh\n")
    if manifest is not None:
        (comp / "component.yaml").write_text(yaml.safe_dump(manifest))
    (tmp_path / "license-allowlist.yaml").write_text(yaml.safe_dump(ALLOWLIST))
    return tmp_path


def run(repo: Path) -> list[str]:
    return check_components(repo / "deploy" / "components", repo / "license-allowlist.yaml")


def with_(**changes: object) -> dict[str, object]:
    return {**VALID, **changes}


def test_valid_component_passes(tmp_path: Path) -> None:
    assert run(make_repo(tmp_path, VALID)) == []


def test_missing_manifest_fails(tmp_path: Path) -> None:
    errors = run(make_repo(tmp_path, None))
    assert any("component.yaml" in e for e in errors)


@pytest.mark.parametrize("version", ["latest", "^26.0", "26.x", ">=1.0"])
def test_unpinned_version_fails(tmp_path: Path, version: str) -> None:
    errors = run(make_repo(tmp_path, with_(version=version)))
    assert any("version" in e for e in errors)


def test_denied_license_fails(tmp_path: Path) -> None:
    errors = run(make_repo(tmp_path, with_(license="AGPL-3.0")))
    assert any("license" in e for e in errors)


def test_unknown_license_fails(tmp_path: Path) -> None:
    errors = run(make_repo(tmp_path, with_(license="Proprietary")))
    assert any("license" in e for e in errors)


def test_approved_exception_passes_only_for_its_component(tmp_path: Path) -> None:
    om = with_(name="openmetadata", license="CCL-1.0")
    assert run(make_repo(tmp_path / "a", om, name="openmetadata")) == []
    errors = run(make_repo(tmp_path / "b", with_(license="CCL-1.0")))
    assert any("license" in e for e in errors)


@pytest.mark.parametrize("ref", ["quay.io/keycloak/keycloak", "quay.io/keycloak/keycloak:latest"])
def test_unpinned_image_cannot_be_packaged_offline(tmp_path: Path, ref: str) -> None:
    image = {"source": "official", "refs": [ref]}
    errors = run(make_repo(tmp_path, with_(image=image)))
    assert any("offline" in e for e in errors)


def test_image_pinned_by_digest_passes(tmp_path: Path) -> None:
    ref = "quay.io/keycloak/keycloak@sha256:" + "a" * 64
    image = {"source": "official", "refs": [ref]}
    assert run(make_repo(tmp_path, with_(image=image))) == []


def test_missing_smoke_test_fails(tmp_path: Path) -> None:
    errors = run(make_repo(tmp_path, with_(smoke_test="tests/missing.sh")))
    assert any("smoke_test" in e for e in errors)


def test_name_must_match_directory(tmp_path: Path) -> None:
    errors = run(make_repo(tmp_path, with_(name="other")))
    assert any("name" in e for e in errors)
