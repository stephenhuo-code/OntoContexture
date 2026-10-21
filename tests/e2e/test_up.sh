#!/usr/bin/env bash
# 部署验收（T040，SC-002）：make up 之后，所有组件的冒烟测试通过，contexture 命名空间的 Pod 均就绪。
set -euo pipefail
cd "$(dirname "$0")/../.."
NS=contexture

for t in deploy/components/*/tests/smoke.sh deploy/charts/*/tests/smoke.sh; do
  echo "--- $(basename "$(dirname "$(dirname "$t")")")"
  "$t"
done

# 除已完成的一次性任务外，所有 Pod 就绪
not_ready=$(kubectl -n "$NS" get pods --no-headers | awk '$3 != "Completed" && $3 != "Succeeded" { split($2, r, "/"); if (r[1] != r[2]) print $1 }')
if [[ -n $not_ready ]]; then
  echo "未就绪的 Pod：$not_ready"; exit 1
fi
# 入口：经 Envoy Gateway 访问 bff，未登录时返回 401
code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/bff/v1/me)
[[ $code == 401 ]] || { echo "入口返回 $code，期望 401"; exit 1; }
echo "部署验收通过"
