#!/usr/bin/env bash
# 冒烟测试：Toolbox 就绪，MCP 端点列出 list_objects 工具
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
kubectl -n $NS rollout status deployment/mcp-toolbox --timeout=180s
curl_in -X POST http://mcp-toolbox:5000/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | grep -q '"list_objects"' && echo "toolbox OK"
