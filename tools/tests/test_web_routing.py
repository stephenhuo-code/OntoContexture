"""006：数据资产页的地址 /assets/* 必须回落到单页应用，不能被构建产物的静态目录截走。

Vite 默认把构建产物放在 /assets/；006 起 /assets 是「数据资产」页面（含 /assets/sources 等子视图），
2026-11-09 e2e 实测部署后访问 /assets/sources 得到 nginx 404。
"""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "apps" / "web"


def test_nginx_does_not_treat_assets_routes_as_static_files() -> None:
    conf = (WEB / "nginx.conf").read_text(encoding="utf-8")
    assert not re.search(r"location\s+(=\s*)?/assets/", conf)
    assert re.search(r"location\s+/static/", conf)


def test_vite_emits_build_assets_outside_the_assets_route() -> None:
    config = (WEB / "vite.config.ts").read_text(encoding="utf-8")
    assert re.search(r'assetsDir:\s*"static"', config)
