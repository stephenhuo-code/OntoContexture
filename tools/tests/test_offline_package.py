"""离线包：镜像清单由全部 component.yaml 汇总（去重、排序），另含自建服务镜像。"""

from pathlib import Path

import yaml

from tools.offline_package import SELF_BUILT_SERVICES, TOOL_IMAGES, collect_images


def write_component(root: Path, name: str, refs: list[str]) -> None:
    comp = root / name
    comp.mkdir(parents=True)
    (comp / "component.yaml").write_text(
        yaml.safe_dump({"name": name, "image": {"source": "official", "refs": refs}})
    )


def test_collects_and_dedupes(tmp_path: Path) -> None:
    write_component(tmp_path, "a", ["x/a:1", "alpine:3.22"])
    write_component(tmp_path, "b", ["x/b:2", "alpine:3.22"])
    images = collect_images(tmp_path)
    assert images == sorted({"x/a:1", "x/b:2", "alpine:3.22", *SELF_BUILT_SERVICES, *TOOL_IMAGES})


def test_skips_dirs_without_manifest(tmp_path: Path) -> None:
    write_component(tmp_path, "a", ["x/a:1"])
    (tmp_path / "notes").mkdir()
    assert "x/a:1" in collect_images(tmp_path)


def test_real_components_are_pinned() -> None:
    images = collect_images(Path(__file__).resolve().parents[2] / "deploy" / "components")
    assert images
    assert all(":" in i.rsplit("/", 1)[-1] or "@sha256:" in i for i in images)
    assert not any(i.endswith(":latest") for i in images)


def test_normalize_matches_containerd_names() -> None:
    from tools.offline_package import normalize

    assert normalize("alpine:3.22") == "docker.io/library/alpine:3.22"
    assert normalize("apache/doris:be-4.1.5") == "docker.io/apache/doris:be-4.1.5"
    assert normalize("docker.io/envoyproxy/gateway:v1.9.2") == "docker.io/envoyproxy/gateway:v1.9.2"
    assert normalize("quay.io/keycloak/keycloak:26.8.0") == "quay.io/keycloak/keycloak:26.8.0"
    assert normalize("contexture/bff:dev") == "docker.io/contexture/bff:dev"


def test_archive_names_are_unique_and_safe() -> None:
    from tools.offline_package import archive_name

    names = {
        archive_name(i) for i in ["apache/doris:fe-4.1.5", "apache/doris:be-4.1.5", "alpine:3.22"]
    }
    assert len(names) == 3
    assert all(n.endswith(".tar") and "/" not in n and ":" not in n for n in names)


def testflatten_charts(tmp_path: Path) -> None:
    from tools.offline_package import flatten_charts

    charts = tmp_path / "charts"
    for release, chart in [
        ("airflow", "airflow"),
        ("otel-collector-agent", "opentelemetry-collector"),
    ]:
        (charts / release / chart).mkdir(parents=True)
        (charts / release / chart / "Chart.yaml").write_text("name: x\n")
    (charts / "web").mkdir()
    (charts / "web" / "Chart.yaml").write_text("name: web\n")
    (charts / "airflow.lock").write_text("")
    flatten_charts(charts)
    assert sorted(p.name for p in charts.iterdir()) == ["airflow", "opentelemetry-collector"]
    assert (charts / "airflow" / "Chart.yaml").exists()
