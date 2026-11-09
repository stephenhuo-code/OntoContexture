"""006 开发态元数据导入：fixture 由 003 表定义生成（FR-016；research R12、R13）。"""

from collections import Counter

import pytest

from mockfactory.om_import import fixture as fx
from mockfactory.schema import TABLES

OWNERS = {
    "admin": {"id": "00000000-0000-0000-0000-00000000000a", "type": "team"},
    "ai-engineer": {"id": "00000000-0000-0000-0000-00000000000b", "type": "team"},
}


@pytest.fixture(scope="module")
def entities() -> list[fx.Entity]:
    return fx.build(OWNERS)


def _of(entities: list[fx.Entity], kind: str) -> list[fx.Entity]:
    return [e for e in entities if e.kind == kind]


def _tag_fqns(body: dict) -> set[str]:
    return {t["tagFQN"] for t in body.get("tags") or []}


def test_write_order_puts_dependencies_first(entities: list[fx.Entity]) -> None:
    order = [e.kind for e in entities]
    first = {k: order.index(k) for k in dict.fromkeys(order)}
    assert list(first) == [
        "classification",
        "tag",
        "domain",
        "glossary",
        "glossaryTerm",
        "databaseService",
        "database",
        "databaseSchema",
        "table",
    ]


def test_every_003_table_is_generated_with_chinese_descriptions(entities: list[fx.Entity]) -> None:
    tables = {e.body["name"]: e for e in _of(entities, "table")}
    for t in TABLES:
        assert t.name in tables, t.name
    by_fqn = {e.fqn: e for e in _of(entities, "table")}
    for t in TABLES:
        match = [e for e in by_fqn.values() if e.body["name"] == t.name and e.system == t.system]
        assert match, t.name
        body = match[0].body
        assert body["description"] == t.comment
        cols = {c["name"]: c for c in body["columns"]}
        for c in t.columns:
            assert cols[c.name]["description"] == c.comment
        assert body["tableConstraints"] == [
            {"constraintType": "PRIMARY_KEY", "columns": list(t.primary_key)}
        ]


def test_services_have_no_connection_and_say_they_are_dev_test(entities: list[fx.Entity]) -> None:
    services = _of(entities, "databaseService")
    assert {s.body["name"] for s in services} == {
        f"{fx.SERVICE_PREFIX}{s}" for s in ("mes", "qms", "dw")
    }
    for s in services:
        assert "connection" not in s.body
        assert set(s.body) <= {"name", "serviceType", "description", "displayName", "tags"}
        assert "开发态测试元数据，由 testdata 导入工具生成" in s.body["description"]
        assert fx.MARKER_FQN in _tag_fqns(s.body)


@pytest.mark.parametrize(
    "kind", ["database", "databaseSchema", "table", "glossary", "glossaryTerm", "domain"]
)
def test_owned_entities_carry_the_dev_test_marker(entities: list[fx.Entity], kind: str) -> None:
    items = _of(entities, kind)
    assert items
    for e in items:
        assert fx.MARKER_FQN in _tag_fqns(e.body), e.fqn


def test_marker_tag_display_name(entities: list[fx.Entity]) -> None:
    tags = {e.fqn: e for e in _of(entities, "tag")}
    assert tags[fx.MARKER_FQN].body["displayName"] == "开发态测试元数据"
    marker_cls = next(
        e for e in _of(entities, "classification") if e.fqn == fx.MARKER_CLASSIFICATION
    )
    assert marker_cls.body["description"].startswith(fx.OWNED_SENTINEL)


def test_same_name_tables_exist_in_different_schemas(entities: list[fx.Entity]) -> None:
    counts = Counter(e.body["name"] for e in _of(entities, "table"))
    dup = [n for n, c in counts.items() if c > 1]
    assert dup
    schemas = {e.body["databaseSchema"] for e in _of(entities, "table") if e.body["name"] == dup[0]}
    assert len(schemas) >= 2


def test_samples_cover_missing_attributes_and_combinations(entities: list[fx.Entity]) -> None:
    tables = [e.body for e in _of(entities, "table")]
    assert any(not t.get("owners") for t in tables), "缺负责人"
    assert any(not any(f.startswith("Tier.") for f in _tag_fqns(t)) for t in tables), "缺分级"
    assert any(not t.get("domains") for t in tables), "缺业务域"
    combos = {
        (
            tuple(t.get("domains") or []),
            tuple(sorted(f for f in _tag_fqns(t) if f.startswith("Tier."))),
            tuple(sorted(f for f in _tag_fqns(t) if f.startswith(fx.SAMPLE_CLASSIFICATION))),
        )
        for t in tables
    }
    full = [c for c in combos if c[0] and c[1] and c[2]]
    assert len(full) >= 2, "业务域 × 分级 × 标签至少两种完整组合"
    tiers = {f for t in tables for f in _tag_fqns(t) if f.startswith("Tier.")}
    assert len(tiers) >= 2, "同维度多选需要至少两个分级取值"


def test_data_level_tags_on_columns(entities: list[fx.Entity]) -> None:
    levels = {
        tag["tagFQN"]
        for e in _of(entities, "table")
        for c in e.body["columns"]
        for tag in c.get("tags") or []
    }
    assert {f for f in levels if f.startswith("数据级别.")}


def test_some_entity_has_no_display_name(entities: list[fx.Entity]) -> None:
    tables = _of(entities, "table")
    assert any("displayName" not in e.body for e in tables)
    assert any("displayName" in e.body for e in tables)


def test_owners_only_use_existing_teams(entities: list[fx.Entity]) -> None:
    refs = [o for e in entities for o in e.body.get("owners") or []]
    assert refs
    assert all(o in OWNERS.values() for o in refs)


def test_glossary_terms_are_linked_to_tables(entities: list[fx.Entity]) -> None:
    terms = {e.fqn for e in _of(entities, "glossaryTerm")}
    linked = {
        t["tagFQN"]
        for e in _of(entities, "table")
        for t in e.body.get("tags") or []
        if t.get("source") == "Glossary"
    }
    assert linked and linked <= terms
