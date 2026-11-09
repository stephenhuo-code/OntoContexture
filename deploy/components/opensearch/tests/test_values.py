"""OpenSearch 内存配置测试（006 D11：本地 OpenSearch 因 OOMKilled 反复重启）。

JVM 的堆外直接内存（MaxDirectMemorySize）默认等于堆大小，另有元空间、代码缓存、线程栈等原生开销。
容器内存上限至少要容纳「2 × 堆 + 512Mi」，否则会被 cgroup 杀掉（exit 137 OOMKilled）。
2026-11-09 本地 lite 环境实测：堆 384m、上限 1Gi，重启 321 次，lastState=OOMKilled。
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

VALUES = Path(__file__).resolve().parents[1] / "values"
NATIVE_OVERHEAD_MI = 512


def _mi(quantity: str) -> int:
    match = re.fullmatch(r"(\d+)(Mi|Gi|m|g)", quantity.strip())
    assert match, f"无法解析容量：{quantity}"
    number, unit = int(match.group(1)), match.group(2)
    return number * 1024 if unit in {"Gi", "g"} else number


def _merged(env: str) -> dict[str, Any]:
    base: dict[str, Any] = yaml.safe_load((VALUES / "base.yaml").read_text(encoding="utf-8")) or {}
    overlay: dict[str, Any] = (
        yaml.safe_load((VALUES / f"{env}.yaml").read_text(encoding="utf-8")) or {}
    )
    merged: dict[str, Any] = {**base, **overlay}
    merged["resources"] = {**base.get("resources", {}), **overlay.get("resources", {})}
    return merged


@pytest.mark.parametrize("env", ["local", "lite"])
def test_memory_limit_covers_heap_and_native_memory(env: str) -> None:
    values = _merged(env)
    heap = re.search(r"-Xmx(\d+[mg])", values["opensearchJavaOpts"])
    assert heap, "opensearchJavaOpts 必须显式设置 -Xmx"
    heap_mi = _mi(heap.group(1))
    limit_mi = _mi(values["resources"]["limits"]["memory"])
    assert limit_mi >= 2 * heap_mi + NATIVE_OVERHEAD_MI, (
        f"{env}: 内存上限 {limit_mi}Mi 小于 2×堆({heap_mi}Mi)+{NATIVE_OVERHEAD_MI}Mi"
    )


@pytest.mark.parametrize("env", ["local", "lite"])
def test_heap_is_at_least_512m(env: str) -> None:
    """2026-11-09 e2e 实测：堆 384m 时存活对象约 370MB，熔断器反复触发 GC，并再次 OOMKilled。"""
    heap = re.search(r"-Xmx(\d+[mg])", _merged(env)["opensearchJavaOpts"])
    assert heap and _mi(heap.group(1)) >= 512
