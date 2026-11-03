"""合并 Python / LCOV，检查 git 变更中的可执行行覆盖率，缺报告时失败。"""

import argparse
import json
import posixpath
import re
import shutil
import subprocess
from pathlib import Path

Coverage = dict[str, dict[int, bool]]
GIT = shutil.which("git") or "/usr/bin/git"
ROOT = Path(__file__).resolve().parent.parent
SOURCE_PREFIXES = (
    "apps/web/src/",
    "packages/ui/src/",
    "packages/py-core/src/",
    "services/bff/src/",
    "tools/",
    "testdata/mockfactory/",
    "extensions/keycloak/",
)


def source_file(path: str) -> bool:
    return (
        path.startswith(SOURCE_PREFIXES)
        and path.endswith((".py", ".ts", ".tsx", ".js"))
        and "/tests/" not in path
        and "/__tests__/" not in path
        and not path.endswith((".d.ts", "test-setup.ts"))
    )


def read_lcov(path: Path, prefix: Path) -> Coverage:
    result: Coverage = {}
    current: dict[int, bool] | None = None
    for line in path.read_text().splitlines():
        if line.startswith("SF:"):
            source = Path(line[3:])
            key = source.relative_to(ROOT) if source.is_absolute() else prefix / source
            current = result.setdefault(posixpath.normpath(key.as_posix()), {})
        elif line.startswith("DA:") and current is not None:
            number, count, *_ = line[3:].split(",")
            current[int(number)] = int(count) > 0
    return result


def read_python(path: Path) -> Coverage:
    payload = json.loads(path.read_text())
    return {
        name: {
            **dict.fromkeys(data["missing_lines"], False),
            **dict.fromkeys(data["executed_lines"], True),
        }
        for name, data in payload["files"].items()
    }


def changed_lines(diff: str) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif current and (match := re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)):
            start, count = int(match[1]), int(match[2] or 1)
            result.setdefault(current, set()).update(range(start, start + count))
    return result


def check_diff(changes: dict[str, set[int]], reports: Coverage) -> tuple[int, int]:
    covered = total = 0
    for name, lines in changes.items():
        if not source_file(name):
            continue
        if name not in reports:
            raise ValueError(f"缺少源码覆盖率报告：{name}")
        executable = lines & reports[name].keys()
        total += len(executable)
        covered += sum(reports[name][number] for number in executable)
    percentage = covered / total * 100 if total else 100
    if percentage < 80:
        raise ValueError(f"变更行覆盖率 {percentage:.2f}% ({covered}/{total}) < 80%")
    return covered, total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--python", type=Path)
    parser.add_argument("--lcov", type=Path, action="append", default=[])
    args = parser.parse_args()
    reports: Coverage = read_python(args.python) if args.python else {}
    for report in args.lcov:
        reports.update(read_lcov(report, report.parent.parent))
    # 参数作为 argv 传入，不通过 shell；未跟踪的新文件也必须纳入本地门禁。
    diff = subprocess.run(  # noqa: S603
        [GIT, "diff", "--no-ext-diff", "--unified=0", args.base, "--"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    changes = changed_lines(diff)
    untracked = subprocess.run(  # noqa: S603 — 固定 git ls-files，未通过 shell
        [GIT, "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    for name in untracked:
        if source_file(name):
            changes[name] = set(range(1, len((ROOT / name).read_text().splitlines()) + 1))
    try:
        covered, total = check_diff(changes, reports)
    except ValueError as error:
        print(error)
        return 1
    print(f"变更行覆盖率：{covered}/{total} ({covered / total * 100 if total else 100:.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
