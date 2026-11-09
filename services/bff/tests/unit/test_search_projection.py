"""006 结果投影：高亮片段、命中字段、来源、位置、列的所属表、类型计数（research R7、R8、R10）。"""

from contexture_bff.adapters.om_search import (
    default_type,
    group_suggestions,
    matched_fields,
    project_hit,
    segments,
)


def test_highlight_segments_unescape_entities_and_never_emit_html() -> None:
    hl = '<span class="text-highlighter">{}</span>'
    frag = "开发态样例术语&#xff1a;生产" + hl.format("工") + hl.format("单") + "&lt;script&gt;"
    segs = segments(frag)
    assert "".join(s["text"] for s in segs) == "开发态样例术语：生产工单<script>"
    assert [s["text"] for s in segs if s["match"]] == ["工", "单"]
    assert all("<span" not in s["text"] for s in segs)


def test_matched_fields_skip_ngram_and_entity_name_keys() -> None:
    hl = {
        "displayName": ["a", "b"],
        "description": ["c"],
        "displayName.ngram": ["x"],
        "table_name": ["y"],
        "columns.name": ["d", "e", "f"],
    }
    assert matched_fields(hl) == [
        {"field": "displayName", "count": 2},
        {"field": "description", "count": 1},
        {"field": "columns.name", "count": 3},
    ]


def _hit(**src: object) -> dict:
    base = {
        "id": "id-1",
        "entityType": "table",
        "name": "work_order",
        "fullyQualifiedName": "s.d.sc.work_order",
        "service": {"name": "s", "displayName": "MES"},
        "database": {"name": "d", "displayName": "d"},
        "databaseSchema": {"name": "sc", "displayName": "sc"},
        "tags": [],
    }
    return {"_source": {**base, **src}}


def test_origin_breadcrumb_and_governance() -> None:
    h = project_hit(
        {
            **_hit(
                tags=[
                    {"tagFQN": "ContextureDevTest.DevTestMetadata", "source": "Classification"},
                    {"tagFQN": "Tier.Tier2", "source": "Classification"},
                    {"tagFQN": "数据级别.二级", "source": "Classification"},
                ],
                certification={"tagLabel": {"tagFQN": "Certification.Gold"}},
                owners=[
                    {"id": "00000000-0000-0000-0000-00000000000a", "type": "team", "name": "admin"}
                ],
            ),
            "highlight": {"description": ['<span class="text-highlighter">工</span>单']},
        }
    )
    assert h["ref"] == {"entityType": "table", "id": "id-1", "fqn": "s.d.sc.work_order"}
    assert h["origin"] == "devTest"
    assert [b["label"] for b in h["breadcrumb"]] == ["MES", "d", "sc"]
    g = h["governance"]
    assert (g["tier"], g["dataLevel"], g["certification"]) == (
        "Tier.Tier2",
        "数据级别.二级",
        "Certification.Gold",
    )
    assert g["tags"] == [] and g["owners"][0]["name"] == "admin"
    assert h["descriptionHighlight"][0] == {"text": "工", "match": True}
    assert h["parentTable"] is None
    assert project_hit(_hit())["origin"] == "collected"


def test_column_hit_carries_parent_table() -> None:
    h = project_hit(
        _hit(
            entityType="tableColumn",
            name="wo_no",
            fullyQualifiedName='s.d.sc."a.b".wo_no',
            table={"id": "t-1", "fullyQualifiedName": 's.d.sc."a.b"'},
        )
    )
    assert h["parentTable"] == {"entityType": "table", "id": "t-1", "fqn": 's.d.sc."a.b"'}
    assert h["columnName"] == "wo_no"


def test_default_type_rule() -> None:
    counts = [{"entityType": "table", "count": 9}, {"entityType": "tableColumn", "count": 30}]
    assert default_type(counts, "table") == "table"
    assert default_type(counts, "tag") == "tableColumn"
    assert default_type(counts, None) == "tableColumn"
    assert default_type([], None) is None


def test_suggestions_grouped_max_five_per_type() -> None:
    hits = [_hit(id=f"t{i}", name=f"t{i}", fullyQualifiedName=f"s.d.sc.t{i}") for i in range(7)]
    hits.append(_hit(entityType="glossaryTerm", id="g", name="工单", fullyQualifiedName="G.工单"))
    groups = group_suggestions(hits)
    assert [(g["entityType"], len(g["items"])) for g in groups] == [
        ("table", 5),
        ("glossaryTerm", 1),
    ]
    assert groups[0]["items"][0]["location"] == "s.d.sc.t0"


def test_name_highlight_never_replaces_display_name() -> None:
    """e2e 实测：只命中 name 时，卡片标题仍应是 displayName，不能显示成高亮的 name。"""
    hl = '<span class="text-highlighter">work_order</span>'
    h = project_hit({**_hit(displayName="生产工单"), "highlight": {"name": [hl]}})
    assert h["nameHighlight"] == []
    same = project_hit({**_hit(displayName="work_order"), "highlight": {"name": [hl]}})
    assert "".join(s["text"] for s in same["nameHighlight"]) == "work_order"
