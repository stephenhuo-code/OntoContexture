"""006：OM tags 的拆分规则（data-model 第 3 节；FR-014）。

Tier、数据安全级别（分类「数据级别」）、业务术语、开发态标识与普通分类标签同存于 OM 的 tags，
卡片、摘要与详情须分开展示。
"""

from contexture_bff.adapters.om_sources import DEV_TEST_MARKER, split_tags


def _t(fqn: str, source: str = "Classification") -> dict[str, str]:
    return {"tagFQN": fqn, "source": source}


def test_split_into_tier_data_level_glossary_origin_and_tags() -> None:
    out = split_tags(
        [
            _t("Tier.Tier1"),
            _t("数据级别.三级"),
            _t(DEV_TEST_MARKER),
            _t("标准术语.不良率", "Glossary"),
            _t("PII.Sensitive"),
            _t("质量合规.ISO9001"),
        ]
    )
    assert out.tier == "Tier.Tier1"
    assert out.data_level == "数据级别.三级"
    assert out.origin == "devTest"
    assert out.glossary_terms == ["标准术语.不良率"]
    assert out.tags == ["PII.Sensitive", "质量合规.ISO9001"]


def test_defaults_when_nothing_is_set() -> None:
    out = split_tags(None)
    assert out.tier is None
    assert out.data_level is None
    assert out.origin == "collected"
    assert out.glossary_terms == []
    assert out.tags == []


def test_marker_never_appears_as_a_classification_tag() -> None:
    assert DEV_TEST_MARKER not in split_tags([_t(DEV_TEST_MARKER)]).tags


def test_marker_matches_the_testdata_import_tool() -> None:
    from mockfactory.om_import.fixture import MARKER_FQN

    assert DEV_TEST_MARKER == MARKER_FQN
