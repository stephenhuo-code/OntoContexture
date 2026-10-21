#!/usr/bin/env bash
# 冒烟测试：Jaeger 就绪；查询接口列出服务（bff 的追踪经 OTel Collector 转入）
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
kubectl -n "$NS" rollout status deployment/jaeger --timeout=180s
# 新环境尚无业务追踪，只检查查询接口可用
curl_in -sf http://jaeger:16686/api/v3/services | grep -q '"services"' && echo "jaeger OK"
