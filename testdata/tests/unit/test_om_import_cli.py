"""006 开发态元数据导入：写入、统计、自有资产、撤除与目标环境检查（FR-016、FR-017；R13）。

OM 以内存假实现代替，只验证工具自身的规则；真实写入由 tests/cluster/test_om_import_cluster.py 验证。
"""

import json
from typing import Any

import pytest

from mockfactory.__main__ import main
from mockfactory.om_import import fixture as fx
from mockfactory.om_import.writer import NotOwned, OmWriter, Response

TEAMS = {
    "admin": "00000000-0000-0000-0000-00000000000a",
    "ai-engineer": "00000000-0000-0000-0000-00000000000b",
}


class FakeOM:
    """按 FQN 存储实体；PUT 时按内容比较返回 entityCreated / entityUpdated / entityNoChange。"""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], dict[str, Any]] = {}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> Response:
        self.calls.append((method, path))
        if method == "GET" and path.startswith("/v1/teams/name/"):
            name = path.rsplit("/", 1)[1]
            return Response(200, {}, {"id": TEAMS[name], "name": name})
        if method == "GET":
            collection, _, fqn = path.removeprefix("/v1/").partition("/name/")
            key = (collection, fqn.split("?", 1)[0])
            if key in self.store:
                return Response(200, {}, self.store[key])
            return Response(404, {}, {"message": "not found"})
        if method == "PUT":
            assert body is not None
            collection = path.removeprefix("/v1/")
            key = (collection, fx.fqn_of(collection, body))
            if key not in self.store:
                self.store[key] = body
                return Response(201, {"X-OpenMetadata-Change": "entityCreated"}, body)
            if self.store[key] == body:
                return Response(200, {"X-OpenMetadata-Change": "entityNoChange"}, body)
            self.store[key] = body
            return Response(200, {"X-OpenMetadata-Change": "entityUpdated"}, body)
        if method == "DELETE":
            collection, _, rest = path.removeprefix("/v1/").partition("/name/")
            self.store.pop((collection, rest.split("?", 1)[0]), None)
            return Response(200, {}, {})
        raise AssertionError(f"unexpected {method} {path}")


def test_first_import_creates_and_second_is_unchanged() -> None:
    om = FakeOM()
    first = OmWriter(om).import_all()
    assert first.created > 0 and first.updated == 0
    second = OmWriter(om).import_all()
    assert second.created == 0
    assert second.unchanged == first.created
    assert all(m in {"GET", "PUT"} for m, _ in om.calls)


def test_changed_entity_counts_as_updated() -> None:
    om = FakeOM()
    OmWriter(om).import_all()
    key = next(k for k in om.store if k[0] == "tables")
    om.store[key] = {**om.store[key], "description": "被改过"}
    stats = OmWriter(om).import_all()
    assert stats.updated == 1


def test_refuses_existing_service_without_marker() -> None:
    om = FakeOM()
    name = f"{fx.SERVICE_PREFIX}mes"
    om.store[("services/databaseServices", name)] = {
        "name": name,
        "serviceType": "Mysql",
        "tags": [],
    }
    with pytest.raises(NotOwned):
        OmWriter(om).import_all()
    assert not any(m == "PUT" for m, _ in om.calls)


def test_refuses_existing_glossary_without_marker() -> None:
    om = FakeOM()
    om.store[("glossaries", fx.GLOSSARY)] = {"name": fx.GLOSSARY, "tags": []}
    with pytest.raises(NotOwned):
        OmWriter(om).import_all()


def test_remove_deletes_only_marked_entities() -> None:
    om = FakeOM()
    OmWriter(om).import_all()
    om.store[("services/databaseServices", "mock-mes")] = {"name": "mock-mes", "tags": []}
    OmWriter(om).remove()
    deletes = [p for m, p in om.calls if m == "DELETE"]
    assert all("mock-mes" not in p for p in deletes)
    service_deletes = [p for p in deletes if p.startswith("/v1/services/databaseServices/")]
    assert len(service_deletes) == 3
    assert all("hardDelete=true" in p and "recursive=true" in p for p in service_deletes)
    assert ("services/databaseServices", "mock-mes") in om.store


def test_cli_refuses_without_explicit_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    called: list[Any] = []
    monkeypatch.setattr(
        "mockfactory.om_import.writer.urllib_transport", lambda *a, **k: called.append(a)
    )
    monkeypatch.setenv("OM_TOKEN", "x")
    code = main(["om-import", "--om-url", "http://localhost:8585"])
    assert code != 0
    assert not called
    assert "--target local" in capsys.readouterr().err


def test_cli_requires_credentials_from_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for k in ("OM_TOKEN", "KEYCLOAK_PROVISIONER_CLIENT_ID", "KEYCLOAK_PROVISIONER_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    code = main(["om-import", "--target", "local", "--om-url", "http://localhost:8585"])
    assert code != 0
    assert "OM_TOKEN" in capsys.readouterr().err


def test_cli_prints_counts_without_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    om = FakeOM()
    monkeypatch.setenv("OM_TOKEN", "secret-token-value")
    monkeypatch.setattr("mockfactory.om_import.writer.urllib_transport", lambda url, token: om)
    code = main(["om-import", "--target", "local", "--om-url", "http://localhost:8585"])
    out = capsys.readouterr()
    assert code == 0
    assert "新建" in out.out and "更新" in out.out and "未变化" in out.out
    assert "secret-token-value" not in out.out + out.err


def test_stats_are_json_serialisable() -> None:
    stats = OmWriter(FakeOM()).import_all()
    assert json.loads(json.dumps(stats.as_dict()))["created"] == stats.created
