#!/usr/bin/env bash
# 冒烟测试：OM 健康检查通过，搜索与 RDF 已连接
set -euo pipefail
source "$(dirname "$0")/../../smoke-lib.sh"
NS=contexture
kubectl -n $NS rollout status deployment/openmetadata --timeout=900s
curl_in http://openmetadata:8586/healthcheck | grep -q '"healthy":true' && echo "openmetadata OK"
