"""由 docs/images/平台服务架构.svg（Phase 1 目标架构）生成实现状态图：平台服务架构-实现状态.svg。

用法：python3 docs/images/平台服务架构-实现状态.gen.py。特性推进后更新下方的 BOXES、LINES 与 NOTES。
"""

import re
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "平台服务架构.svg"
DST = HERE / "平台服务架构-实现状态.svg"
AS_OF = "截至 001 完成（2026-10-22）"

STATUS = {
    "done": ("#e6f4ea", "#1e8e3e", None, "已实现"),
    "partial": ("#fef7e0", "#e37400", None, "部分"),
    "todo": ("#f6f8fa", "#9aa0a6", "6 4", "未实现"),
}
# 框（按原图坐标）→ 状态、标签中的分类
BOXES = {
    (250, 92): ("partial", "外部"),
    (800, 92): ("todo", "外部"),
    (150, 182): ("partial", "开源"),
    (150, 232): ("partial", "自建"),
    (350, 232): ("partial", "自建"),
    (800, 232): ("done", "开源"),
    (1220, 252): ("todo", "外部"),
    (150, 432): ("partial", "开源"),
    (360, 432): ("partial", "开源"),
    (570, 432): ("partial", "开源"),
    (780, 432): ("todo", "开源"),
    (990, 432): ("done", "开源"),
    (1200, 432): ("partial", "开源"),
    (150, 618): ("done", "存储"),
    (332, 618): ("done", "存储"),
    (514, 618): ("done", "存储"),
    (696, 618): ("done", "存储"),
    (878, 618): ("done", "存储"),
    (1060, 618): ("todo", "外部"),
    (1242, 618): ("done", "存储"),
    (150, 740): ("done", "开源"),
    (470, 740): ("done", "自建"),
}
# 连线（起点坐标）→ 是否已打通
LINES = {
    (330, 148): True,   # 浏览器 → web
    (500, 148): True,   # 浏览器 → bff
    (1010, 148): False,  # 客户侧 Agent → AI 网关（数字员工平台在 007 接入）
    (700, 300): True,   # bff → AI 网关（页面取数）
    (1180, 287): False,  # AI 网关 → 大模型（已用桩服务验证，key 未配置）
    (430, 342): False,  # bff → Langfuse（轨迹页面，006）
    (610, 342): True,   # bff → OM（已打通读取已审批本体；写入与审批在 016、020）
    (830, 342): False,  # AI 网关 → OM 内置 MCP（014）
    (880, 432): False,  # Omnigent → AI 网关（009）
    (1090, 342): True,  # AI 网关 → MCP Toolbox
    (1100, 550): False,  # Toolbox → 客户数据库（011、005）
    (1170, 550): True,  # Toolbox → Doris
    (1325, 550): False,  # Airflow → Doris 物化写入（019）
}
# 连线标签（文本）→ 是否已打通（未打通的标签改为灰色）
LABELS_TODO = ["轨迹页面", "上下文（MCP）", "客户库（MCP）", "物化写入", "取数 / 上下文 / 模型"]

NOTES = [
    "部分实现的内容：Envoy Gateway — 路由已配置，TLS 与限流未配置；web — 最小外壳（登录、设备定义与列表），首页、审批中心、探索资产等在 004 及之后；",
    "bff — 登录与会话、对象定义与列表，本体写入、审批、轨迹页面、Omnigent 代理未做；Keycloak — 织境客户端与角色已导入，Agent 客户端登记在 002；",
    "Langfuse — 已接收全链路追踪，人工修订与样本数据集在 006；OpenMetadata — 本体共用字段、hasProperty 与示例对象已就绪，审批工作流、上下文中心、",
    "OKF、内置 MCP 在 014、016、020；Airflow — 已部署就绪，管线（采集、物化、同步）在 011、019 等。另：可观测后端 Jaeger、Prometheus、OpenSearch Dashboards 已部署（图中未画）。",
]


def restyle_box(svg: str, x: int, y: int, status: str, kind: str) -> str:
    fill, stroke, dash, label = STATUS[status]
    pattern = re.compile(rf'<rect x="{x}" y="{y}" width="(\d+)" height="(\d+)"([^>]*)/>')
    match = pattern.search(svg)
    assert match, (x, y)
    width = int(match.group(1))
    attrs = match.group(3)
    attrs = re.sub(r'fill="[^"]*"', f'fill="{fill}"', attrs)
    attrs = re.sub(r'stroke="[^"]*"', f'stroke="{stroke}"', attrs)
    attrs = re.sub(r' stroke-dasharray="[^"]*"', "", attrs)
    if dash:
        attrs += f' stroke-dasharray="{dash}"'
    badge_text = label
    bw = 11 * len(badge_text) + 14
    # 标签骑在框的上边线右侧，不压标题
    bx, by = x + width - bw - 10, y - 8
    badge = (
        f'<rect x="{bx:.0f}" y="{by}" width="{bw:.0f}" height="16" rx="8" fill="{stroke}"/>'
        f'<text x="{bx + bw / 2:.0f}" y="{by + 12}" font-size="10.5" fill="#ffffff" '
        f'text-anchor="middle" font-weight="600">{badge_text}</text>'
    )
    replacement = f'<rect x="{x}" y="{y}" width="{match.group(1)}" height="{match.group(2)}"{attrs}/>'
    # 标签放在该框的文字之后，避免被其他元素遮挡：先替换框，再在 </svg> 前统一追加
    restyle_box.badges.append(badge)
    return svg[: match.start()] + replacement + svg[match.end() :]


restyle_box.badges = []


def restyle_lines(svg: str) -> str:
    def repl(m: re.Match[str]) -> str:
        x1, y1 = int(float(m.group(1))), int(float(m.group(2)))
        done = LINES.get((x1, y1))
        if done is None or done:
            return m.group(0)
        tag = re.sub(r'stroke="[^"]*"', 'stroke="#9aa0a6"', m.group(0))
        tag = tag.replace('marker-end="url(#mu)"', 'marker-end="url(#mg)"')
        tag = tag.replace('marker-end="url(#ma)"', 'marker-end="url(#mg)"')
        tag = tag.replace('marker-end="url(#mp)"', 'marker-end="url(#mg)"')
        return tag.replace("<line ", '<line stroke-dasharray="6 4" ', 1)

    return re.sub(r'<line x1="([\d.]+)" y1="([\d.]+)"[^>]*marker-end[^>]*/>', repl, svg)


def main() -> None:
    svg = SRC.read_text(encoding="utf-8")
    for (x, y), (status, kind) in BOXES.items():
        svg = restyle_box(svg, x, y, status, kind)
    svg = restyle_lines(svg)
    for label in LABELS_TODO:
        svg = re.sub(rf'(<text [^>]*fill=")#[0-9a-fA-F]{{6}}("[^>]*>{re.escape(label)}</text>)', r"\1#9aa0a6\2", svg)

    # 标题、尺寸
    svg = svg.replace("织境平台服务架构（Phase 1）</text>", f"织境平台服务架构（Phase 1）— 实现状态，{AS_OF}</text>", 1)
    svg = svg.replace('width="1440" height="880" viewBox="0 0 1440 880"', 'width="1440" height="1000" viewBox="0 0 1440 1000"')
    svg = svg.replace('<rect width="1440" height="880" fill="#ffffff"/>', '<rect width="1440" height="1000" fill="#ffffff"/>')

    # 图例：分类 → 实现状态
    legend_old = re.compile(r'<rect x="820" y="748"[\s\S]*?外部系统</text>')
    legend = []
    for i, (status, (fill, stroke, dash, label)) in enumerate(STATUS.items()):
        lx = 820 + (i % 2) * 110
        ly = 748 + (i // 2) * 26
        d = f' stroke-dasharray="{dash}"' if dash else ""
        legend.append(f'<rect x="{lx}" y="{ly}" width="22" height="14" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.5"{d}/>')
        legend.append(f'<text x="{lx + 30}" y="{ly + 12}" font-size="12" fill="#59636e">{label}</text>')
    legend.append('<line x1="930" y1="781" x2="960" y2="781" stroke="#9aa0a6" stroke-width="2" stroke-dasharray="6 4"/>')
    legend.append('<text x="966" y="786" font-size="12" fill="#59636e">未打通</text>')
    svg = legend_old.sub("".join(legend), svg, count=1)

    notes = "".join(
        f'<text x="20" y="{905 + i * 20}" font-size="12" fill="#59636e">{line}</text>' for i, line in enumerate(NOTES)
    )
    svg = svg.replace("</svg>", notes + "".join(restyle_box.badges) + "</svg>")
    DST.write_text(svg, encoding="utf-8")
    print(f"写入 {DST}")


if __name__ == "__main__":
    main()
