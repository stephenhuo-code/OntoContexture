"""SC-009 中文检索观察（-m cluster，D10）：固定关键词取自 003 表定义的中文说明；只记录，不判定。

结果写入 test-results/006-sc009.json，由负责人在验收时按 D10 判定是否另立项改用中文分词。
"""

import asyncio
import json
from pathlib import Path

import pytest
from cluster_assets import CTX, TABLES, dev_filter, om

pytestmark = pytest.mark.cluster
KEYWORDS = [
    "生产工单",
    "产线",
    "设备事件",
    "物料批次",
    "供应商",
    "检验实测值",
    "不合格报告",
    "缺陷码",
    "质量汇总",
    "投料记录",
]
OUT = Path(__file__).resolve().parents[4] / "test-results" / "006-sc009.json"


def test_chinese_keyword_observation() -> None:
    async def run() -> list[dict[str, object]]:
        rows = []
        with om() as (svc, _, _):
            for kw in KEYWORDS:
                expected = sorted({t.body["name"] for t in TABLES if kw in t.body["description"]})
                page = await svc.search(
                    CTX,
                    {
                        "keyword": kw,
                        "entityType": "table",
                        "filters": dev_filter(),
                        "sort": {"field": "relevance"},
                    },
                )
                top3 = [h["name"] for h in page["hits"][:3]]
                rows.append(
                    {
                        "keyword": kw,
                        "total": page["total"],
                        "expected": expected,
                        "top3": top3,
                        "expected_in_top3": bool(set(expected) & set(top3)),
                    }
                )
        return rows

    rows = asyncio.run(run())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in rows:
        print(f"\n[006 SC-009] {r}")
    assert len(rows) == len(KEYWORDS)
