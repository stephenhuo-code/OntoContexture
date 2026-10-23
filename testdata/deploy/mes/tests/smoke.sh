#!/usr/bin/env bash
# 冒烟测试：模拟 MES 就绪并可执行查询
set -euo pipefail
k() { kubectl --context "${KUBE_CONTEXT:-kind-contexture}" -n mock-sources "$@"; }
k rollout status statefulset/mock-mes --timeout=300s
k exec mock-mes-0 -c mysql -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "select 1"' 2>/dev/null | grep -qx 1
echo "mock-mes OK"
