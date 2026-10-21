#!/usr/bin/env bash
# 冒烟测试：网关就绪；无令牌访问 MCP 被拒绝（401）
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
kubectl -n "$NS" rollout status deployment/ai-gateway --timeout=180s
code=$(curl_in -o /dev/null -w "%{http_code}" -X POST http://ai-gateway:8080/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}')
[[ $code == 401 ]] && echo "ai-gateway OK"
