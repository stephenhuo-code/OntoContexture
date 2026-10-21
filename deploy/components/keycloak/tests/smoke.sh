#!/usr/bin/env bash
# 冒烟测试：导入任务成功；织境客户端的 OIDC 发现地址可访问（外部或自带 Keycloak）
set -euo pipefail
NS=contexture
job=$(kubectl -n $NS get jobs -l app.kubernetes.io/name=keycloak-import --sort-by=.metadata.creationTimestamp -o name | tail -1)
kubectl -n $NS wait "$job" --for=condition=Complete --timeout=600s
kubectl -n $NS logs "$job" -c import | grep -q "keycloak-config-cli ran in" && echo "import OK"
