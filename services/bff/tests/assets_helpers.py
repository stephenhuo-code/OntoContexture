"""006 单元与契约测试共用：在内存 OM 中登记索引文档与实体（测试夹具，不进入生产代码）。"""

from typing import Any

import httpx
from om_fake import FakeOM
from sources_helpers import FakeExchanger

from contexture_bff.adapters.om_assets import AssetReader
from contexture_bff.adapters.om_client import OmClient
from contexture_bff.adapters.om_search import SearchService

MARKER = {"tagFQN": "ContextureDevTest.DevTestMetadata", "source": "Classification"}
OWNER = {"id": "00000000-0000-0000-0000-00000000000a", "type": "team", "name": "admin"}
DOMAIN = {
    "id": "00000000-0000-0000-0000-0000000000d1",
    "type": "domain",
    "name": "DevTestProduction",
    "displayName": "开发态-生产域",
}
TABLE_FQN = "devtest-mes.default.mes.work_order"


def om_client(om: FakeOM) -> OmClient:
    return OmClient(
        om_url="http://om:8585",
        exchanger=FakeExchanger(),
        http=httpx.AsyncClient(transport=om.transport()),
    )


def search_service(om: FakeOM) -> SearchService:
    return SearchService(om_client(om))


def reader(om: FakeOM) -> AssetReader:
    return AssetReader(om_client(om))


def _place(fqn: str) -> dict[str, Any]:
    svc, db, schema = fqn.split(".")[:3]
    return {
        "service": {"name": svc, "displayName": svc},
        "database": {"name": db, "displayName": db},
        "databaseSchema": {"name": schema, "displayName": schema},
        "serviceType": "Mysql",
    }


def seed(om: FakeOM) -> None:
    """开发态表（Tier1、数据级别字段）及其一列、005 采集的同名表、一个术语、一个指标。"""
    om.add_search_doc(
        "table",
        TABLE_FQN,
        displayName="生产工单",
        description="生产工单主表",
        tags=[
            MARKER,
            {"tagFQN": "Tier.Tier1", "source": "Classification"},
            {"tagFQN": "ContextureDevGlossary.工单", "source": "Glossary"},
            {"tagFQN": "ContextureDevSample.生产相关", "source": "Classification"},
        ],
        owners=[OWNER],
        domains=[DOMAIN],
        certification={"tagLabel": {"tagFQN": "Certification.Gold"}},
        **_place(TABLE_FQN),
    )
    om.add_search_doc(
        "table",
        "mock-mes.default.mes.work_order",
        displayName="work_order",
        description="005 采集的工单表",
        **_place("mock-mes.default.mes.work_order"),
    )
    om.add_search_doc(
        "tableColumn",
        f"{TABLE_FQN}.wo_no",
        description="工单号",
        table={"id": "00000000-0000-0000-0000-0000000000t1", "fullyQualifiedName": TABLE_FQN},
        **_place(TABLE_FQN),
    )
    om.add_search_doc(
        "glossaryTerm",
        "ContextureDevGlossary.工单",
        description="开发态样例术语：生产工单。",
        tags=[MARKER],
    )
    om.add_search_doc("metric", "line_yield", description="产线良率")
    om.add_tables(
        "devtest-mes",
        "default",
        "mes",
        {
            "work_order": [
                ("wo_no", "varchar(32)", "PRIMARY_KEY"),
                ("line_code", "varchar(32)", None),
            ]
        },
    )
    table = next(t for t in om.tables if t["fullyQualifiedName"] == TABLE_FQN)
    table["tags"] = [MARKER, {"tagFQN": "Tier.Tier1", "source": "Classification"}]
    table["owners"] = [OWNER]
    table["domains"] = [DOMAIN]
    table["description"] = "生产工单主表"
    table["columns"][0]["tags"] = [{"tagFQN": "数据级别.一级", "source": "Classification"}]
    table["columns"][0]["description"] = "工单号"
    om.glossary_terms["ContextureDevGlossary.工单"] = {
        "id": "00000000-0000-0000-0000-0000000000g1",
        "name": "工单",
        "displayName": "工单",
        "fullyQualifiedName": "ContextureDevGlossary.工单",
        "description": "开发态样例术语：生产工单。",
        "glossary": {
            "id": "00000000-0000-0000-0000-0000000000g0",
            "type": "glossary",
            "name": "ContextureDevGlossary",
        },
        "synonyms": ["Work Order"],
        "relatedTerms": [],
        "references": [{"name": "手册", "endpoint": "https://example.invalid/wo"}],
        "owners": [OWNER],
        "reviewers": [],
        "domains": [],
        "tags": [MARKER],
        "entityStatus": "Approved",
    }
    om.tag_entities["数据级别.一级"] = {
        "id": "00000000-0000-0000-0000-0000000000a1",
        "name": "一级",
        "fullyQualifiedName": "数据级别.一级",
        "description": "公开或内部一般数据",
        "classification": {
            "id": "00000000-0000-0000-0000-0000000000c1",
            "type": "classification",
            "name": "数据级别",
        },
        "owners": [],
        "reviewers": [],
        "domains": [],
        "deprecated": False,
    }
