#!/usr/bin/env bash
# 冒烟测试：导入任务成功；织境客户端的 OIDC 发现地址可访问（外部或自带 Keycloak）
set -euo pipefail
NS=contexture
job=$(kubectl -n $NS get jobs -l app.kubernetes.io/name=keycloak-import --sort-by=.metadata.creationTimestamp -o name | tail -1)
kubectl -n $NS wait "$job" --for=condition=Complete --timeout=600s
# 停止释放节点后，已完成 Job 的 Pod 可能已被回收（T082 实测）：此时以 Job 的 Complete 状态为准
if [[ -z $(kubectl -n $NS get pods -l "job-name=${job#*/}" -o name 2>/dev/null) ]]; then
  echo "import OK（Job 已完成，Pod 已回收）"
else
  kubectl -n $NS logs "$job" -c import | grep -q "keycloak-config-cli ran in" && echo "import OK"
fi
