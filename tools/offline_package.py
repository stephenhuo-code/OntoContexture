"""离线安装包（D9）：汇总全部 component.yaml 的镜像清单，导出镜像与 Chart 到 deploy/offline/dist/。

用法：python -m tools.offline_package [--list]
  --list  只打印镜像清单
产物：dist/images.txt、images/<镜像>.tar、charts/（helmfile fetch）、repo/（部署文件）
镜像来源依次为：本机 Docker、本地 kind 集群节点（containerd，集群已在用）、网络拉取（失败重试）
安装：deploy/offline/install.sh（在无外网的集群中导入镜像并以本地 Chart 部署）
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = REPO_ROOT / "deploy" / "components"
DIST = REPO_ROOT / "deploy" / "offline" / "dist"
# 自建服务的镜像（开源组件之外）
SELF_BUILT_SERVICES = ["contexture/bff:dev", "contexture/web:dev"]
# 目标架构：默认与本机一致（kind 节点同架构）；为其他架构的集群打包时设置 CTX_OFFLINE_PLATFORM
PLATFORM = os.environ.get("CTX_OFFLINE_PLATFORM") or (
    "linux/arm64" if platform.machine() in ("arm64", "aarch64") else "linux/amd64"
)
# 冒烟测试与安装脚本使用的工具镜像
TOOL_IMAGES = ["curlimages/curl:8.17.0"]


def collect_images(components_dir: Path = COMPONENTS) -> list[str]:
    images: set[str] = {*SELF_BUILT_SERVICES, *TOOL_IMAGES}
    for manifest in sorted(components_dir.glob("*/component.yaml")):
        data = cast(dict[str, Any], yaml.safe_load(manifest.read_text(encoding="utf-8")))
        images.update(str(r) for r in data["image"]["refs"])
    return sorted(images)


def normalize(image: str) -> str:
    """与 containerd 中的名称一致：补全 docker.io 与 library/ 前缀。"""
    first = image.split("/", 1)[0]
    if "/" not in image:
        return f"docker.io/library/{image}"
    if "." not in first and ":" not in first and first != "localhost":
        return f"docker.io/{image}"
    return image


def archive_name(image: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", normalize(image)) + ".tar"


def _run(*cmd: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)  # noqa: S603


def _kind_nodes(cluster: str) -> list[str]:
    out = _run("kind", "get", "nodes", "--name", cluster, check=False)
    return out.stdout.split() if out.returncode == 0 else []


def _export_from_kind(image: str, target: Path, nodes: list[str]) -> bool:
    ref = normalize(image)
    for node in nodes:
        listed = _run(
            "docker", "exec", node, "ctr", "-n", "k8s.io", "images", "ls", "-q", check=False
        )
        if ref not in listed.stdout.split():
            continue
        inside = f"/tmp/{target.name}"  # noqa: S108 kind 节点容器内的临时文件，导出后删除
        exported = _run(
            "docker",
            "exec",
            node,
            "ctr",
            "-n",
            "k8s.io",
            "images",
            "export",
            "--platform",
            "linux/arm64",
            "--platform",
            "linux/amd64",
            inside,
            ref,
            check=False,
        )
        if exported.returncode != 0:
            exported = _run(
                "docker",
                "exec",
                node,
                "ctr",
                "-n",
                "k8s.io",
                "images",
                "export",
                inside,
                ref,
                check=False,
            )
        if exported.returncode == 0:
            _run("docker", "cp", f"{node}:{inside}", str(target))
            _run("docker", "exec", node, "rm", "-f", inside, check=False)
            return True
    return False


def _save_image(image: str, target: Path, nodes: list[str], retries: int = 6) -> str:
    if _run("docker", "image", "inspect", image, check=False).returncode == 0:
        # 只导出目标架构：多架构索引中缺少的其他架构层会使 kind / containerd 导入失败
        _run("docker", "save", "--platform", PLATFORM, "-o", str(target), image)
        return "本机 Docker"
    if _export_from_kind(image, target, nodes):
        return "kind 节点"
    for attempt in range(1, retries + 1):
        if _run("docker", "pull", "-q", "--platform", PLATFORM, image, check=False).returncode == 0:
            _run("docker", "save", "--platform", PLATFORM, "-o", str(target), image)
            return "网络拉取"
        time.sleep(10 * attempt)
    raise RuntimeError(f"无法获取镜像 {image}")


def flatten_charts(charts: Path) -> None:
    """helmfile fetch 的产物为 charts/<发布名>/<Chart 名>/，且同一 Chart 只下载一次；
    整理为 charts/<Chart 名>/（离线时 helmfile 按 Chart 名引用）。
    本地 Chart 不留副本（离线时用 repo/ 中的）。"""
    flat = charts.parent / ".charts-flat"
    if flat.exists():
        shutil.rmtree(flat)
    flat.mkdir()
    for release in [p for p in charts.iterdir() if p.is_dir()]:
        if (release / "Chart.yaml").exists():
            continue
        for chart in [c for c in release.iterdir() if (c / "Chart.yaml").exists()]:
            if not (flat / chart.name).exists():
                shutil.move(str(chart), str(flat / chart.name))
    shutil.rmtree(charts)
    flat.rename(charts)


def build(dist: Path = DIST, cluster: str = "contexture") -> None:
    images = collect_images()
    # 断点续做：保留已导出的镜像归档，只重建其余产物
    for stale in ("charts", "repo", "images.txt"):
        path = dist / stale
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    (dist / "images").mkdir(parents=True, exist_ok=True)
    wanted = {archive_name(i) for i in images}
    for leftover in (dist / "images").glob("*.tar"):
        if leftover.name not in wanted:
            leftover.unlink()
    (dist / "images.txt").write_text("\n".join(images) + "\n", encoding="utf-8")
    nodes = _kind_nodes(cluster)
    for image in images:
        target = dist / "images" / archive_name(image)
        if target.exists() and target.stat().st_size > 0:
            print(f"  {image}（已存在）", flush=True)
            continue
        partial = target.with_suffix(".partial")
        source = _save_image(image, partial, nodes)
        partial.rename(target)
        print(f"  {image}（{source}）", flush=True)
    _run(
        "helmfile",
        "-f",
        str(REPO_ROOT / "deploy" / "helmfile.yaml.gotmpl"),
        "-e",
        "local",
        "fetch",
        "--output-dir",
        str(dist / "charts"),
        "--output-dir-template",
        "{{ .OutputDir }}/{{ .Release.Name }}",
    )
    flatten_charts(dist / "charts")
    shutil.copytree(
        REPO_ROOT / "deploy", dist / "repo" / "deploy", ignore=shutil.ignore_patterns("dist")
    )
    print(f"离线包：{dist}（{len(images)} 个镜像）")


def main(argv: list[str]) -> int:
    if "--list" in argv:
        print("\n".join(collect_images()))
        return 0
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
