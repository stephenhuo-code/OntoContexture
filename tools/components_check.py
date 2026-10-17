"""组件检查：遍历 deploy/components/*/component.yaml，按 Schema 与许可白名单校验。

规则见 ADR-0009 第 2 节。

用法：python -m tools.components_check [组件目录] [许可白名单]
"""

import re
import sys
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPONENTS = REPO_ROOT / "deploy" / "components"
DEFAULT_ALLOWLIST = REPO_ROOT / "tools" / "license-allowlist.yaml"
SCHEMA_FILE = "component.schema.json"

DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
TAG = re.compile(r":(?P<tag>[\w][\w.-]{0,127})$")


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], data) if isinstance(data, dict) else {}


def _image_pinned(ref: str) -> bool:
    """镜像须带确切标签或摘要，才能汇总进离线安装包。"""
    if DIGEST.search(ref):
        return True
    last = ref.rsplit("/", 1)[-1]
    match = TAG.search(last)
    return match is not None and match.group("tag") != "latest"


def _license_errors(name: str, license_id: str, allowlist: dict[str, Any]) -> list[str]:
    if license_id in allowlist.get("denied", []):
        return [f"{name}: license {license_id} 被禁止（宪法 III）"]
    if license_id in allowlist.get("allowed", []):
        return []
    for exc in allowlist.get("exceptions", []):
        if exc.get("license") == license_id and exc.get("component") == name:
            return []
    return [f"{name}: license {license_id} 不在白名单内，也没有已批准的例外"]


def check_component(
    comp_dir: Path, validator: Draft202012Validator, allowlist: dict[str, Any]
) -> list[str]:
    name = comp_dir.name
    manifest_path = comp_dir / "component.yaml"
    if not manifest_path.is_file():
        return [f"{name}: 缺少 component.yaml"]

    manifest = _load_yaml(manifest_path)
    errors = [
        f"{name}: {'.'.join(str(p) for p in err.absolute_path) or '<root>'} {err.message}"
        # types-jsonschema 的重载签名含未知类型
        for err in validator.iter_errors(manifest)  # pyright: ignore[reportUnknownMemberType]
    ]
    if errors:
        return errors

    if manifest["name"] != name:
        errors.append(f"{name}: name 须与目录名一致，实际为 {manifest['name']}")
    errors += _license_errors(name, manifest["license"], allowlist)
    errors += [
        f"{name}: 镜像 {ref} 未锁定标签或摘要，无法列入 offline 安装包"
        for ref in manifest["image"]["refs"]
        if not _image_pinned(ref)
    ]
    if not (comp_dir / manifest["smoke_test"]).is_file():
        errors.append(f"{name}: smoke_test {manifest['smoke_test']} 不存在")
    return errors


def check_components(components_dir: Path, allowlist_path: Path) -> list[str]:
    schema_path = DEFAULT_COMPONENTS / SCHEMA_FILE
    schema: dict[str, Any] = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    allowlist = _load_yaml(allowlist_path)
    errors: list[str] = []
    for comp_dir in sorted(p for p in components_dir.iterdir() if p.is_dir()):
        errors += check_component(comp_dir, validator, allowlist)
    return errors


def main(argv: list[str]) -> int:
    components = Path(argv[1]) if len(argv) > 1 else DEFAULT_COMPONENTS
    allowlist = Path(argv[2]) if len(argv) > 2 else DEFAULT_ALLOWLIST
    errors = check_components(components, allowlist)
    for e in errors:
        print(f"FAIL {e}", file=sys.stderr)
    if not errors:
        print("components-check: OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
