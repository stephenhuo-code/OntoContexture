#!/usr/bin/env bash
# 冒烟测试：模拟 QMS 集群就绪并可执行查询
set -euo pipefail
k() { kubectl --context "${KUBE_CONTEXT:-kind-contexture}" -n mock-sources "$@"; }
k wait cluster/mock-qms --for=condition=Ready --timeout=300s
k exec mock-qms-1 -c postgres -- psql -tAc "select 1" | grep -qx 1
echo "mock-qms OK"
