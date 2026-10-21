"""CI 门禁的故意失败用例（T041）：许可检查与组件检查必须拦截。"""

import json
from pathlib import Path

from tools.components_check import DEFAULT_ALLOWLIST, check_components
from tools.license_check import check_sbom

FIXTURES = Path(__file__).parent / "fixtures"


def test_agpl_dependency_is_blocked() -> None:
    result = check_sbom(FIXTURES / "agpl-package" / "sbom.cdx.json", DEFAULT_ALLOWLIST)
    assert [d.name for d in result.denied] == ["some-agpl-lib"]
    assert not result.ok


def test_component_without_version_is_blocked() -> None:
    errors = check_components(FIXTURES / "components-no-version", DEFAULT_ALLOWLIST)
    assert any("version" in e for e in errors)


def test_permissive_sbom_passes(tmp_path: Path) -> None:
    sbom = json.loads((FIXTURES / "agpl-package" / "sbom.cdx.json").read_text())
    sbom["components"] = sbom["components"][:1]
    path = tmp_path / "ok.cdx.json"
    path.write_text(json.dumps(sbom))
    assert check_sbom(path, DEFAULT_ALLOWLIST).ok


def test_unknown_licenses_are_reported_not_blocking(tmp_path: Path) -> None:
    sbom = {
        "bomFormat": "CycloneDX",
        "components": [
            {"name": "no-license", "version": "1"},
            {"name": "weak", "version": "1", "licenses": [{"license": {"id": "MPL-2.0"}}]},
            {"name": "expr", "version": "1", "licenses": [{"expression": "MIT OR GPL-3.0"}]},
        ],
    }
    path = tmp_path / "s.cdx.json"
    path.write_text(json.dumps(sbom))
    result = check_sbom(path, DEFAULT_ALLOWLIST)
    assert result.ok
    assert {d.name for d in result.review} == {"no-license", "weak"}


def test_approved_exception_needs_matching_component(tmp_path: Path) -> None:
    sbom = {
        "bomFormat": "CycloneDX",
        "components": [{"name": "x", "version": "1", "licenses": [{"license": {"id": "CCL-1.0"}}]}],
    }
    path = tmp_path / "s.cdx.json"
    path.write_text(json.dumps(sbom))
    assert [d.name for d in check_sbom(path, DEFAULT_ALLOWLIST).review] == ["x"]
