"""数据说明：由表定义生成，与仓库中的 testdata/数据说明.md 一致（SC-006）。"""

from pathlib import Path

from mockfactory.docs import DOC_PATH, render_docs
from mockfactory.schema import TABLES


def test_doc_up_to_date() -> None:
    assert Path(__file__).resolve().parents[2] / "数据说明.md" == DOC_PATH
    assert DOC_PATH.read_text(encoding="utf-8") == render_docs(), (
        "请运行 python -m mockfactory docs 重新生成"
    )


def test_doc_sections_and_fields() -> None:
    doc = render_docs()
    for heading in ("工厂组成", "编号规则", "跨系统关联键", "案例", "人员与班组"):
        assert any(line.startswith("## ") and heading in line for line in doc.splitlines()), heading
    for table in TABLES:
        assert f"`{table.name}`" in doc
        for column in table.columns:
            assert f"| `{column.name}` |" in doc and column.comment in doc
    assert "L2-CNC-03" in doc
