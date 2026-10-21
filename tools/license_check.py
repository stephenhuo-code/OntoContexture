"""许可检查（宪法 III）：读取 Syft 产出的 CycloneDX SBOM，按 tools/license-allowlist.yaml 判定。

- 命中禁止项（AGPL、SSPL、BUSL）→ 失败；
- 在白名单内（或许可表达式中有一个分支全部在白名单内）→ 通过；
- 其余（无许可信息、弱 copyleft、未知名称）→ 列入待人工复核清单，不阻断构建。

用法：python -m tools.license_check <sbom.cdx.json> [许可白名单]
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

from tools.components_check import DEFAULT_ALLOWLIST

OS_PURLS = ("pkg:deb/", "pkg:apk/", "pkg:rpm/")

# 常见的非 SPDX 写法
ALIASES = {
    "mit license": "MIT",
    "apache 2.0": "Apache-2.0",
    "apache-2": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "bsd license": "BSD-3-Clause",
    "new bsd license": "BSD-3-Clause",
    "isc license": "ISC",
    "3-clause bsd license": "BSD-3-Clause",
    "bsd-3-clause license": "BSD-3-Clause",
    "psf": "PSF-2.0",
    "python software foundation license": "PSF-2.0",
}


@dataclass
class Dependency:
    name: str
    version: str
    licenses: list[str]


@dataclass
class Result:
    denied: list[Dependency] = field(default_factory=list)
    review: list[Dependency] = field(default_factory=list)
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.denied


def _normalize(name: str) -> str:
    return ALIASES.get(name.strip().lower(), name.strip())


def _licenses(component: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for entry in component.get("licenses") or []:
        if "expression" in entry:
            found.append(str(entry["expression"]))
        lic = entry.get("license") or {}
        if lic.get("id") or lic.get("name"):
            found.append(_normalize(str(lic.get("id") or lic.get("name"))))
    return found


def _classify(expr: str, allowed: set[str], denied: list[str]) -> str:
    """返回 allowed / denied / review。"""
    alternatives = [a.strip(" ()") for a in re.split(r"\s+OR\s+", expr)]
    verdicts: list[str] = []
    for alt in alternatives:
        parts = [_normalize(p.strip(" ()")) for p in re.split(r"\s+AND\s+", alt)]
        if all(p in allowed for p in parts):
            return "allowed"
        if any(any(p.upper().startswith(d.upper()) for d in denied) for p in parts):
            verdicts.append("denied")
        else:
            verdicts.append("review")
    return "denied" if all(v == "denied" for v in verdicts) else "review"


def check_sbom(sbom_path: Path, allowlist_path: Path = DEFAULT_ALLOWLIST) -> Result:
    allowlist = cast(dict[str, Any], yaml.safe_load(allowlist_path.read_text(encoding="utf-8")))
    allowed = set(allowlist.get("allowed", []))
    denied_prefixes = sorted({re.split(r"[-.]", d)[0] for d in allowlist.get("denied", [])})
    exceptions = {(e["license"], e["component"]) for e in allowlist.get("exceptions", [])}
    sbom = cast(dict[str, Any], json.loads(sbom_path.read_text(encoding="utf-8")))

    # 同一依赖可能既来自锁文件（无许可信息）又来自已安装的包，按名称与版本合并
    merged: dict[tuple[str, str], Dependency] = {}
    for comp in sbom.get("components") or []:
        if comp.get("type") in ("file", "operating-system"):  # 只检查软件包
            continue
        if str(comp.get("purl", "")).startswith(OS_PURLS):  # 基础镜像的系统软件包随发行版提供
            continue
        key = (str(comp.get("name")), str(comp.get("version", "")))
        if key[0].startswith("contexture-") or key[0].startswith("@contexture/"):  # 织境自己的包
            continue
        dep = merged.setdefault(key, Dependency(key[0], key[1], []))
        dep.licenses += [lic for lic in _licenses(comp) if lic not in dep.licenses]

    result = Result()
    for dep in merged.values():
        result.checked += 1
        if not dep.licenses:
            result.review.append(dep)
            continue
        verdicts = {
            "allowed" if (lic, dep.name) in exceptions else _classify(lic, allowed, denied_prefixes)
            for lic in dep.licenses
        }
        if "allowed" in verdicts:
            continue
        if verdicts == {"denied"}:
            result.denied.append(dep)
        else:
            result.review.append(dep)
    return result


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    allowlist = Path(argv[2]) if len(argv) > 2 else DEFAULT_ALLOWLIST
    result = check_sbom(Path(argv[1]), allowlist)
    for d in result.denied:
        print(f"FAIL 禁止的许可：{d.name} {d.version} {d.licenses}", file=sys.stderr)
    for d in result.review:
        print(f"REVIEW 待复核：{d.name} {d.version} {d.licenses or '（无许可信息）'}")
    print(
        f"license-check: 检查 {result.checked} 个依赖，禁止 {len(result.denied)}，"
        f"待复核 {len(result.review)}"
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
