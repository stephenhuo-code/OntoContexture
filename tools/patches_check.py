"""补丁一致性检查（宪法 VI、ADR-0011）。

对 third_party/<组件>/：子仓库当前提交必须在发布分支上；发布分支相对上游基线提交的每个提交都必须在
PATCHES.md 登记，登记的提交也必须在发布分支上。子仓库为浅克隆时，逐步加深直到包含上游基线。

用法：python -m tools.patches_check [组件目录 ...]
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
THIRD_PARTY = REPO_ROOT / "third_party"
SHA = re.compile(r"^[0-9a-f]{7,40}$")


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    # 只调用固定的 git 子命令，参数来自仓库内的登记文件
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), *args],  # noqa: S607
        check=check,
        capture_output=True,
        text=True,
    )


def _has_commit(repo: Path, sha: str) -> bool:
    return _git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant, check=False)
    return result.returncode == 0


def _ensure_base(repo: Path, base: str, max_rounds: int = 20) -> bool:
    """浅克隆时逐步加深历史，直到上游基线是当前提交的祖先。"""
    for _ in range(max_rounds):
        if _has_commit(repo, base) and _is_ancestor(repo, base, "HEAD"):
            return True
        if _git(repo, "rev-parse", "--is-shallow-repository").stdout.strip() != "true":
            return False
        _git(repo, "fetch", "-q", "--deepen=50", "origin", check=False)
    return _has_commit(repo, base) and _is_ancestor(repo, base, "HEAD")


def _release_ref(repo: Path, branch: str) -> str | None:
    for ref in (branch, f"origin/{branch}"):
        if _git(repo, "rev-parse", "--verify", "-q", ref, check=False).returncode == 0:
            return ref
    # CI 以 detached HEAD 浅检出子仓库，没有分支引用：从远程补取发布分支
    remote_ref = f"refs/remotes/origin/{branch}"
    fetched = _git(
        repo, "fetch", "-q", "--depth=50", "origin", f"+{branch}:{remote_ref}", check=False
    )
    return f"origin/{branch}" if fetched.returncode == 0 else None


def registered_commits(patches_md: Path) -> list[str]:
    """读取 PATCHES.md 表格第二列（提交）中的 SHA。"""
    commits: list[str] = []
    for line in patches_md.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and SHA.match(cells[1]):
            commits.append(cells[1])
    return commits


def check_component(component_dir: Path, src: Path | None = None) -> list[str]:
    upstream = cast(dict[str, Any], yaml.safe_load((component_dir / "UPSTREAM.yaml").read_text()))
    name = str(upstream.get("component", component_dir.name))
    src = src or REPO_ROOT / str(upstream["submodule_path"])
    base = str(upstream["upstream"]["commit"])
    branch = str(upstream["mirror"]["release_branch"])
    if not (src / ".git").exists():
        return [f"{name}: 子仓库 {src} 未检出（git submodule update --init）"]

    errors: list[str] = []
    ref = _release_ref(src, branch)
    if ref is None:
        errors.append(f"{name}: 找不到发布分支 {branch}")
    elif not _is_ancestor(src, "HEAD", ref):
        errors.append(f"{name}: 子仓库当前提交不在发布分支 {branch} 上")
    if not _ensure_base(src, base):
        return [*errors, f"{name}: 上游基线 {base[:12]} 不是当前提交的祖先"]

    actual = _git(src, "rev-list", "--reverse", f"{base}..HEAD").stdout.split()
    registered = registered_commits(component_dir / "PATCHES.md")
    for sha in actual:
        if not any(sha.startswith(r) for r in registered):
            errors.append(f"{name}: 提交 {sha[:12]} 未登记在 PATCHES.md")
    for r in registered:
        if not any(sha.startswith(r) for sha in actual):
            errors.append(f"{name}: PATCHES.md 登记的 {r} 不在发布分支的补丁中")
    return errors


def main(argv: list[str]) -> int:
    dirs = [Path(a) for a in argv[1:]] or sorted(
        p for p in THIRD_PARTY.iterdir() if (p / "UPSTREAM.yaml").is_file()
    )
    errors = [e for d in dirs for e in check_component(d)]
    for e in errors:
        print(f"FAIL {e}", file=sys.stderr)
    if not errors:
        print(f"patches-check: OK（{', '.join(d.name for d in dirs)}）")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
