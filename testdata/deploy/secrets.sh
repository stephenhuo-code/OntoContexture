#!/usr/bin/env bash
# 模拟源系统（003）的命名空间与凭证：已存在的不覆盖。由 tools/up.sh 与 make mock-data 调用。
set -euo pipefail
CTX=${KUBE_CONTEXT:-kind-contexture}
NS=mock-sources
k() { kubectl --context "$CTX" "$@"; }
rand() { openssl rand -hex 12; }
k get namespace "$NS" >/dev/null 2>&1 || k create namespace "$NS" >/dev/null
ensure() {  # ensure <名称> <kubectl create secret generic 的其余参数...>
  local name=$1; shift
  k -n "$NS" get secret "$name" >/dev/null 2>&1 || k -n "$NS" create secret generic "$name" "$@" >/dev/null
}
ensure mock-mes --from-literal=root-password="$(rand)"
ensure mock-qms-superuser --type=kubernetes.io/basic-auth --from-literal=username=postgres \
  --from-literal=password="$(rand)"
ensure mock-dw-reader --from-literal=password="$(rand)"
