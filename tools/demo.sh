#!/usr/bin/env bash
# 手动验收的辅助命令（acceptance.md 引用）：
#   tools/demo.sh audit <trace 编号>   列出 AI 网关中该次请求的审计记录
#   tools/demo.sh auth-check           无令牌、受众不符的令牌直接调 bff，显示返回码与错误体
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  audit)
    TRACE=${2:?用法：tools/demo.sh audit <trace 编号>}
    kubectl -n contexture logs deploy/ai-gateway --since=24h | grep "$TRACE" | python3 -c '
import json, sys
rows = [json.loads(l) for l in sys.stdin if l.startswith("{")]
rows = [r for r in rows if r.get("audit.mcp.tool")]
if not rows:
    sys.exit("没有找到该 trace 的取数审计记录（确认 trace 编号，或请求是否在 24 小时内）")
for r in rows:
    print("时间        ", r.get("time"))
    print("人（sub）   ", r.get("audit.sub"), "（用户名", r.get("audit.user"), "）")
    print("调用方（azp）", r.get("audit.azp"))
    print("租户        ", r.get("audit.tenant"))
    print("工具        ", r.get("audit.mcp.tool"))
    print("查询参数    ", json.dumps(r.get("audit.mcp.arguments"), ensure_ascii=False))
    print("返回行数    ", r.get("audit.mcp.rows"))
    print("trace       ", r.get("trace.id"))
    print("-" * 60)
'
    ;;
  auth-check)
    echo "① 无令牌："
    curl -s -w "\n   → HTTP %{http_code}\n" http://localhost:8080/bff/v1/me
    echo "② 受众不符的令牌（user1 登录后交换为只给 AI 网关用的令牌，不含 bff）："
    TOKEN=$(PYTHONPATH=tests uv run python tests/e2e/wrong_audience_token.py)
    curl -s -w "\n   → HTTP %{http_code}\n" -H "Authorization: Bearer $TOKEN" http://localhost:8080/bff/v1/me
    ;;
  *)
    sed -n '2,4p' "$0"; exit 1 ;;
esac
