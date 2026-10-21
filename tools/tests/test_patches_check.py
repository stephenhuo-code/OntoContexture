"""补丁一致性检查（宪法 VI）：发布分支相对上游标签的每个提交都必须在 PATCHES.md 登记，反之亦然。"""

import subprocess
from pathlib import Path

import pytest
import yaml

from tools.patches_check import check_component

HEADER = """# 补丁登记

| # | 提交 | 目的 | 上游 issue / PR | 状态 | 能否随上游升级 | 删除条件 |
| --- | --- | --- | --- | --- | --- | --- |
"""


def git(repo: Path, *args: str) -> str:
    cmd = ["git", "-C", str(repo), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", name)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def component(tmp_path: Path) -> tuple[Path, Path, str]:
    """返回（组件目录，子仓库目录，上游基线提交）；子仓库当前在发布分支上。"""
    src = tmp_path / "comp" / "src"
    src.mkdir(parents=True)
    git(src, "init", "-q", "-b", "main")
    base = commit(src, "upstream.txt")
    git(src, "checkout", "-qb", "ctx/1.0")
    comp = tmp_path / "comp"
    (comp / "UPSTREAM.yaml").write_text(
        yaml.safe_dump(
            {
                "component": "comp",
                "upstream": {"tag": "1.0", "commit": base},
                "mirror": {"release_branch": "ctx/1.0"},
                "submodule_path": "comp/src",
            }
        )
    )
    return comp, src, base


def write_patches(comp: Path, commits: list[str]) -> None:
    if commits:
        rows = "".join(
            f"| {i} | {c[:12]} | 目的 | — | 已合入 | 是 | — |\n" for i, c in enumerate(commits, 1)
        )
    else:
        rows = "| — | （暂无） | | | | | |\n"
    (comp / "PATCHES.md").write_text(HEADER + rows)


def test_no_patches_passes(component: tuple[Path, Path, str]) -> None:
    comp, src, _ = component
    write_patches(comp, [])
    assert check_component(comp, src) == []


def test_all_registered_passes(component: tuple[Path, Path, str]) -> None:
    comp, src, _ = component
    patches = [commit(src, "p1.txt"), commit(src, "p2.txt")]
    write_patches(comp, patches)
    assert check_component(comp, src) == []


def test_unregistered_commit_fails(component: tuple[Path, Path, str]) -> None:
    comp, src, _ = component
    p1 = commit(src, "p1.txt")
    p2 = commit(src, "p2.txt")
    write_patches(comp, [p1])
    errors = check_component(comp, src)
    assert any(p2[:12] in e and "未登记" in e for e in errors)


def test_registered_but_missing_commit_fails(component: tuple[Path, Path, str]) -> None:
    comp, src, _ = component
    p1 = commit(src, "p1.txt")
    write_patches(comp, [p1, "deadbeefdead"])
    errors = check_component(comp, src)
    assert any("deadbeefdead" in e and "不在发布分支" in e for e in errors)


def test_wrong_branch_fails(component: tuple[Path, Path, str]) -> None:
    comp, src, _ = component
    write_patches(comp, [])
    git(src, "checkout", "-qb", "feature")
    commit(src, "wip.txt")
    errors = check_component(comp, src)
    assert any("ctx/1.0" in e for e in errors)


def test_fetches_release_branch_when_missing(tmp_path: Path) -> None:
    """CI 中子仓库以 detached HEAD 浅检出，没有发布分支的引用：检查时从远程补取。"""
    upstream = tmp_path / "mirror"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "main")
    base = commit(upstream, "upstream.txt")
    git(upstream, "checkout", "-qb", "ctx/1.0")
    patch = commit(upstream, "p1.txt")

    comp = tmp_path / "comp"
    src = comp / "src"
    subprocess.run(["git", "clone", "-q", "--no-checkout", str(upstream), str(src)], check=True)
    git(src, "checkout", "-q", "--detach", patch)
    for ref in git(
        src, "for-each-ref", "--format=%(refname)", "refs/remotes", "refs/heads"
    ).split():
        git(src, "update-ref", "-d", ref)
    assert git(src, "for-each-ref", "refs/heads", "refs/remotes") == ""
    (comp / "UPSTREAM.yaml").write_text(
        yaml.safe_dump(
            {
                "component": "comp",
                "upstream": {"tag": "1.0", "commit": base},
                "mirror": {"release_branch": "ctx/1.0"},
                "submodule_path": "comp/src",
            }
        )
    )
    write_patches(comp, [patch])
    assert check_component(comp, src) == []
