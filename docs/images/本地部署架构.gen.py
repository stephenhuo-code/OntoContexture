"""生成 docs/images/本地部署架构.svg（同目录同名）：001 完成后本地 kind 集群中的服务与调用关系。用法：python3 docs/images/本地部署架构.gen.py"""
from html import escape
W, H = 1600, 1080
FG, MUTED, BORDER = "#1f2328", "#59636e", "#d0d7de"
SELF_FILL, SELF_STROKE = "#e8f0fe", "#1a73e8"     # 自建
OSS_FILL, OSS_STROKE = "#ffffff", "#8c959f"       # 开源组件
EXT_FILL = "#f6f8fa"                              # 集群外
GROUP_FILL = "#fafbfc"
BLUE, RED, GREEN, GREY = "#1a73e8", "#d93025", "#1e8e3e", "#6e7781"
out = []
def add(s): out.append(s)

def text(x, y, s, size=13, color=FG, weight="normal", anchor="start"):
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(s)}</text>')

def box(x, y, w, h, title, sub=None, kind="oss", dashed=False):
    fill, stroke = {"self": (SELF_FILL, SELF_STROKE), "oss": (OSS_FILL, OSS_STROKE), "ext": (EXT_FILL, GREY)}[kind]
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.3"{dash}/>')
    cx = x + w / 2
    lines = sub.split("\n") if sub else []
    total = 16 + 15 * len(lines)
    top = y + (h - total) / 2 + 13
    text(cx, top, title, 13, FG, "600", "middle")
    for i, line in enumerate(lines):
        text(cx, top + 18 + i * 15, line, 11.5, MUTED, anchor="middle")

def group(x, y, w, h, title, note=None):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{GROUP_FILL}" stroke="{BORDER}"/>')
    text(x + 12, y + 20, title, 13, "#57606a", "600")
    if note:
        text(x + w - 12, y + 20, note, 11.5, MUTED, anchor="end")

def arrow(d, color=BLUE, marker="mu", dash=None, label=None, lx=None, ly=None, lanchor="middle"):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"{da} marker-end="url(#{marker})"/>')
    if label:
        text(lx, ly, label, 11.5, color, anchor=lanchor)

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="PingFang SC, Microsoft YaHei, Noto Sans CJK SC, Helvetica, Arial, sans-serif" role="img" aria-label="织境本地部署架构（001）">')
add("<defs>" + "".join(
    f'<marker id="{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
    for i, c in [("mu", BLUE), ("ma", RED), ("mp", GREEN), ("mg", GREY)]) + "</defs>")
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(20, 34, "织境本地部署架构（001 完成，2026-10-22）", 22, FG, "600")
text(20, 58, "make up 在本地 kind 集群中部署全部服务（helmfile 编排，deploy/helmfile.yaml.gotmpl）。单租户 tenant_id = local。蓝框为自建服务，白框为开源组件，灰框在集群外。", 13, MUTED)

# ---------- 集群外 ----------
box(40, 80, 250, 72, "浏览器", "织境 Web 用户（测试账号 user1 等）", "ext")
box(560, 80, 400, 72, "Keycloak 26.8.0（集群外，Paperclip 自带）", "sso.127.0.0.1.nip.io · realm digital-workforce\n织境配置由导入任务增量写入", "ext")
box(1230, 80, 330, 72, "模型服务商（OpenAI 兼容）", "DeepSeek / OpenAI 等 · key 待配置", "ext", dashed=True)
text(300, 106, "http://localhost:8080", 11.5, MUTED)
text(300, 121, "（宿主机 8080 → 节点 30080）", 11.5, MUTED)

# ---------- 集群 ----------
add(f'<rect x="20" y="166" width="{W-40}" height="{1012-166}" rx="12" fill="none" stroke="#57606a" stroke-width="1.5"/>')
text(36, 190, "kind 集群 contexture（1 控制面 + 2 工作节点）", 14, "#57606a", "600")

# 系统命名空间
add(f'<rect x="40" y="202" width="{W-80}" height="82" rx="8" fill="{GROUP_FILL}" stroke="{BORDER}"/>')
text(W - 52, 222, "envoy-gateway-system · cnpg-system · doris-system", 12, "#57606a", "600", "end")
box(70, 230, 400, 46, "Envoy 代理（入口，Envoy Gateway v1.9.2）", "/ → web · /bff/* → bff · /mcp、/v1 → ai-gateway")
box(610, 234, 200, 38, "envoy-gateway 控制器")
box(890, 234, 290, 38, "CloudNativePG 1.30.1")
box(1240, 234, 290, 38, "Doris Operator 25.8.0")

# contexture 命名空间
add(f'<rect x="40" y="296" width="{W-80}" height="{996-296}" rx="10" fill="none" stroke="{BORDER}" stroke-width="1.2" stroke-dasharray="6 4"/>')
text(56, 318, "命名空间 contexture", 13, "#57606a", "600")

# Row A：入口与取数
box(70, 332, 240, 74, "web（自建）", "nginx 提供 React 单页\n页面 /objects/equipment", "self")
box(370, 332, 290, 74, "bff（自建）", "OIDC 登录与会话（Cookie）\n对象定义 + 对象列表接口", "self")
box(740, 332, 330, 74, "ai-gateway（agentgateway v1.6.0）", "令牌校验（受众 contexture-ai-gateway）\n按角色授权工具 · 审计 · 模型网关")
box(1150, 332, 380, 74, "mcp-toolbox 1.14.0", "MCP 工具 list_objects（参数化只读查询）\nDoris 只读账号 ctx_reader")

# Row B：本体与数据
group(56, 432, 620, 172, "本体与元数据")
box(76, 460, 580, 54, "openmetadata 2.0.3（自建镜像，源码构建）", "本体：术语库 quality（设备对象与属性，已审批）· 自定义属性 ctx_* · 关系 hasProperty")
box(76, 526, 285, 64, "opensearch 3.4.0", "OM 搜索索引 · 服务日志 ctx-logs")
box(371, 526, 285, 64, "fuseki 6.2.0", "OM 的 RDF 存储")
group(696, 432, 848, 172, "数据存储")
box(716, 460, 250, 54, "doris-fe 4.1.5", "查询入口（MySQL 协议 9030）")
box(716, 522, 250, 72, "doris-be 4.1.5", "本体实例库 ctx_local\n表 equipment（10 行示例）")
box(990, 460, 534, 134, "PostgreSQL 17.6（pg-1）", "每个组件一个独立 database 与账号：\nopenmetadata · langfuse · airflow · bff（会话）")

# Row C：轨迹与编排
group(56, 616, 620, 150, "决策轨迹（Langfuse 4.63.0）")
box(76, 644, 185, 48, "langfuse-web", "界面与 API · OTLP 入口")
box(271, 644, 185, 48, "langfuse-worker", "异步处理")
box(466, 644, 190, 48, "clickhouse 26.9", "轨迹存储（单节点）")
box(76, 702, 285, 48, "langfuse-redis（Valkey 8.0）", "缓存与队列")
box(371, 702, 285, 48, "langfuse-s3（SeaweedFS 4.23）", "对象存储")
group(696, 616, 848, 150, "管线编排（Airflow 3.3.2，KubernetesExecutor）", "001 只验证就绪，管线在后续特性中加入")
box(716, 644, 400, 48, "airflow-api-server", "界面与 REST API")
box(1126, 644, 398, 48, "airflow-scheduler")
box(716, 702, 400, 48, "airflow-dag-processor")
box(1126, 702, 398, 48, "airflow-triggerer")

# Row D：可观测
group(56, 784, 1488, 196, "可观测（D10 选定）")
box(76, 812, 360, 72, "otel-collector 0.163.1（网关）", "接收各服务 OTLP；补租户与用户属性\n追踪 → Langfuse、Jaeger；指标 → Prometheus")
box(76, 894, 360, 54, "otel-collector-agent（每个节点一份）", "采集各 Pod 标准输出日志 → OpenSearch")
box(466, 812, 290, 58, "jaeger 2.22.0", "服务追踪查看（内存存储）")
box(786, 812, 290, 58, "prometheus v3.15.0", "抓取 otel-collector、ai-gateway 指标")
box(1106, 812, 418, 58, "opensearch-dashboards 3.4.0", "查看服务日志（索引 ctx-logs，可按 trace 检索）")
text(466, 902, "发送追踪的服务：入口 Envoy、bff、ai-gateway、mcp-toolbox（同一 trace 编号贯穿全链路，见页面底部）", 12, MUTED)
text(466, 922, "本机查看：make ports → Langfuse :3000 · Jaeger :16686 · Prometheus :9090 · Dashboards :5601 · OM :8585 · Airflow :8081", 12, MUTED)
text(466, 942, "一次性任务（Job）：keycloak 配置导入 · doris 初始化（库、只读账号、workload group）· bff 会话库迁移（Alembic）", 12, MUTED)
text(466, 962, "make seed：在 OM 建并审批“设备”对象与属性；在 Doris 写入 10 台设备；为 bff 写入 OM 机器人令牌", 12, MUTED)

# ---------- 调用关系 ----------
# 业务请求（蓝）
arrow("M 165 152 L 165 228", BLUE, "mu")
arrow("M 190 276 L 190 330", BLUE, "mu")
arrow("M 400 276 L 460 330", BLUE, "mu")
arrow("M 470 262 C 600 270, 740 290, 800 330", BLUE, "mu", label="/mcp、/v1：外部 Agent 平台", lx=640, ly=300, lanchor="start")
arrow("M 660 369 L 738 369", BLUE, "mu", label="MCP", lx=699, ly=361)
arrow("M 1070 369 L 1148 369", BLUE, "mu", label="MCP", lx=1109, ly=361)
arrow("M 1300 406 C 1260 430, 1020 440, 920 458", BLUE, "mu", label="SQL（只读账号）", lx=1320, ly=428, lanchor="start")
arrow("M 470 406 L 400 458", BLUE, "mu", label="REST：已审批对象定义", lx=452, ly=436, lanchor="start")
arrow("M 640 406 C 760 430, 1060 430, 1180 458", BLUE, "mu", label="会话", lx=1150, ly=447)
# 身份与令牌（红）
arrow("M 540 332 L 540 190 C 540 166, 570 156, 600 154", RED, "ma", dash="6 4", label="登录（授权码 + PKCE）、令牌交换", lx=548, ly=222, lanchor="start")
arrow("M 850 332 L 850 154", RED, "ma", dash="6 4", label="JWKS 验签", lx=858, ly=178, lanchor="start")
# 模型调用（绿）
arrow("M 1040 332 C 1120 316, 1210 306, 1210 286 L 1210 186 C 1210 166, 1260 156, 1300 154", GREEN, "mp", dash="6 4", label="模型调用（厂商 key 只在网关）", lx=1200, ly=200, lanchor="end")
# 遥测（灰）
arrow("M 436 840 L 464 840", GREY, "mg", dash="3 3")

# ---------- 图例 ----------
ly = H - 36
def leg(x, color, marker, dash, label):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<path d="M {x} {ly} L {x+40} {ly}" stroke="{color}" stroke-width="1.6"{da} marker-end="url(#{marker})"/>')
    text(x + 48, ly + 4, label, 12, MUTED)
leg(40, BLUE, "mu", None, "业务请求")
leg(180, RED, "ma", "6 4", "身份与令牌（Keycloak）")
leg(420, GREEN, "mp", "6 4", "模型调用")
leg(560, GREY, "mg", "3 3", "遥测（追踪、日志、指标）")
add(f'<rect x="800" y="{ly-9}" width="22" height="16" rx="3" fill="{SELF_FILL}" stroke="{SELF_STROKE}"/>')
text(830, ly + 4, "自建服务", 12, MUTED)
add(f'<rect x="910" y="{ly-9}" width="22" height="16" rx="3" fill="{OSS_FILL}" stroke="{OSS_STROKE}"/>')
text(940, ly + 4, "开源组件（版本锁定，见 deploy/components/*/component.yaml）", 12, MUTED)
add(f'<rect x="1330" y="{ly-9}" width="22" height="16" rx="3" fill="{EXT_FILL}" stroke="{GREY}"/>')
text(1360, ly + 4, "集群外", 12, MUTED)
add("</svg>")
open(__import__("pathlib").Path(__file__).with_suffix("").with_suffix(".svg"), "w", encoding="utf-8").write("\n".join(out))
print("ok")
